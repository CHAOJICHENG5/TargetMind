"""Platform relay for NCBI E-utilities (PubMed, GEO) used by the sandboxes.

NCBI allows 3 requests/s per IP without an API key and 10/s per key. Every
sandbox leaves the host through the same IP, so without coordination all users
together share 3/s and concurrent tasks trip HTTP 429. The sandbox tools
(``tm-discover``, ``tm-novelty``) therefore call this relay, which

* authenticates the sandbox by its session API key (like the webhooks);
* forwards only read-only endpoints (esearch, esummary, efetch, elink) for a
  few databases;
* paces *all* upstream requests through one global limiter (~9/s with the
  platform key, ~3/s without);
* adds the platform API key server-side, in the POST body — it never reaches a
  sandbox, a URL or a log line;
* caches successful responses on disk (searches 7 days, records 30 days), so
  repeated queries across users and re-runs cost nothing;
* retries 429/5xx with backoff (Retry-After honoured), including NCBI's
  "HTTP 200 + ERROR" answers ("Search Backend failed ... temporarily
  unavailable"), which are never cached;
* when NCBI keeps failing, answers 502 with ``X-TM-Upstream: error`` (the tools
  then report the gene/query as *failed*, never as zero hits) and, for
  ``OUTAGE_SECONDS``, tries each request once instead of backing off, so an
  outage does not clog the global limiter.

Key: ``NCBI_API_KEY`` in the environment, else ``<platform state>/ncbi.env``
(``NCBI_API_KEY=...``, mode 600). Cache: ``$TM_SERVICE_CACHE_DIR/ncbi-eutils``.

Literature searches normally run on the local PubMed library (``tm-lit``); the
relay serves the online remainder (newest papers, GEO, ClinVar, Gene).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Annotated, NamedTuple
from urllib.parse import parse_qsl, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from agent_core import depends_httpx_client, get_global_config
from agent_core import valid_sandbox
from agent_core import SandboxRecord

_logger = logging.getLogger(__name__)

UPSTREAM = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
TOOL_NAME = 'targetmind'
ENDPOINTS = {'esearch', 'esummary', 'efetch', 'elink'}
DATABASES = {'pubmed', 'pmc', 'gene', 'gds', 'clinvar'}
# Caller-supplied identity/auth parameters are replaced by the platform's.
_STRIPPED = {'api_key', 'tool', 'email'}
MAX_PARAM_BYTES = 64 * 1024
MAX_IDS = 500
CACHE_TTL = {'esearch': 7 * 86400, 'elink': 7 * 86400}
DEFAULT_TTL = 30 * 86400
RETRIES = 4
OUTAGE_SECONDS = 30.0
UPSTREAM_HEADER = 'X-TM-Upstream'

_XML_ERROR = re.compile(
    rb'<(?:eSearchResult|eFetchResult|eSummaryResult|eLinkResult)\b.{0,2000}?'
    rb'<ERROR>(.*?)</ERROR>',
    re.S,
)
# NCBI error messages that mean "try again later" (vs. a bad query).
_TRANSIENT = re.compile(
    r'temporar|backend|time ?out|timed out|rate limit|try again|unavailable|'
    r'internal|too many',
    re.I,
)


def ncbi_error(body: bytes) -> str | None:
    """NCBI's message when a 200 response is really an error, else None."""
    head = body[:4096].lstrip()
    if not head:
        return 'empty response'
    if head.startswith(b'{'):
        try:
            data = json.loads(body)
        except ValueError:
            return 'unreadable JSON response'
        if not isinstance(data, dict):
            return None
        for key in ('error', 'ERROR'):
            if isinstance(data.get(key), str) and data[key]:
                return data[key]
        res = data.get('esearchresult')
        if isinstance(res, dict) and res.get('ERROR'):
            return str(res['ERROR'])
        return None
    m = _XML_ERROR.search(head)
    return m.group(1).decode(errors='replace').strip() if m else None


def is_transient(message: str) -> bool:
    return bool(_TRANSIENT.search(message))


class RelayResult(NamedTuple):
    status: int
    content_type: str
    body: bytes
    cached: bool
    upstream_failed: bool = False


router = APIRouter(prefix='/ncbi', tags=['NCBI'])
httpx_client_dependency = depends_httpx_client()


def _read_key() -> str | None:
    key = os.getenv('NCBI_API_KEY')
    if key:
        return key.strip()
    path = Path(os.path.expanduser('<platform state>/ncbi.env'))
    try:
        for line in path.read_text().splitlines():
            name, _, value = line.partition('=')
            if name.strip() == 'NCBI_API_KEY' and value.strip():
                return value.strip().strip('"\'')
    except OSError:
        return None
    return None


class RateLimiter:
    """Global FIFO pacing: at most one upstream request per ``interval``."""

    def __init__(self, per_second: float) -> None:
        self.interval = 1.0 / per_second
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            await asyncio.sleep(delay)


class EutilsRelay:
    def __init__(self, cache_dir: Path, api_key: str | None) -> None:
        self.cache_dir = cache_dir
        self.api_key = api_key
        # Stay just under NCBI's documented limits.
        self.limiter = RateLimiter(9.0 if api_key else 2.8)
        self.stats = {
            'requests': 0,
            'cache_hits': 0,
            'upstream': 0,
            'retries': 0,
            'upstream_failed': 0,
        }
        # While NCBI is failing, each request gets one attempt (no backoff).
        self._outage_until = 0.0

    # -- cache --------------------------------------------------------------
    def _cache_path(self, endpoint: str, params: list[tuple[str, str]]) -> Path:
        digest = hashlib.sha256(
            json.dumps([endpoint, sorted(params)]).encode()
        ).hexdigest()
        return self.cache_dir / digest[:2] / f'{digest}.json'

    def _cache_get(self, path: Path, endpoint: str) -> dict | None:
        try:
            entry = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if time.time() - entry.get('t', 0) > CACHE_TTL.get(endpoint, DEFAULT_TTL):
            return None
        if ncbi_error(entry.get('body', '').encode()):
            return None  # never serve an error body (older caches stored some)
        return entry

    def _cache_put(self, path: Path, content_type: str, body: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f'.{os.getpid()}.tmp')
            tmp.write_text(
                json.dumps(
                    {'t': time.time(), 'ct': content_type, 'body': body.decode()}
                )
            )
            tmp.replace(path)
        except (OSError, UnicodeDecodeError):
            _logger.warning('NCBI relay: could not cache a response', exc_info=True)

    # -- upstream -----------------------------------------------------------
    async def fetch(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        params: list[tuple[str, str]],
    ) -> RelayResult:
        self.stats['requests'] += 1
        path = self._cache_path(endpoint, params)
        cached = await asyncio.to_thread(self._cache_get, path, endpoint)
        if cached is not None:
            self.stats['cache_hits'] += 1
            return RelayResult(200, cached['ct'], cached['body'].encode(), True)

        form = [*params, ('tool', TOOL_NAME)]
        if self.api_key:
            form.append(('api_key', self.api_key))
        attempts = 1 if time.monotonic() < self._outage_until else RETRIES + 1
        last_body = b'NCBI unavailable'
        for attempt in range(attempts):
            await self.limiter.wait()
            self.stats['upstream'] += 1
            delay = min(30.0, 1.5 * 2**attempt) + random.uniform(0, 0.5)
            try:
                resp = await client.post(
                    f'{UPSTREAM}/{endpoint}.fcgi',
                    content=urlencode(form).encode(),
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=httpx.Timeout(20.0, read=90.0),
                )
            except httpx.HTTPError as exc:
                _logger.warning(
                    'NCBI relay: %s attempt %d failed: %s',
                    endpoint,
                    attempt + 1,
                    type(exc).__name__,
                )
                last_body = b'NCBI unreachable'
            else:
                content_type = resp.headers.get('content-type', 'text/plain')
                if resp.status_code == 200:
                    body = resp.content
                    error = ncbi_error(body)
                    if error is None:
                        self._outage_until = 0.0
                        await asyncio.to_thread(
                            self._cache_put, path, content_type, body
                        )
                        return RelayResult(200, content_type, body, False)
                    if not is_transient(error):
                        # A query NCBI rejects: the caller reads the message.
                        return RelayResult(200, content_type, body, False)
                    _logger.warning(
                        'NCBI relay: %s attempt %d: NCBI error %s',
                        endpoint,
                        attempt + 1,
                        error[:120],
                    )
                    last_body = f'NCBI error: {error[:300]}'.encode()
                elif resp.status_code != 429 and resp.status_code < 500:
                    return RelayResult(
                        resp.status_code, content_type, resp.content[:2000], False
                    )
                else:
                    _logger.warning(
                        'NCBI relay: %s attempt %d: HTTP %d',
                        endpoint,
                        attempt + 1,
                        resp.status_code,
                    )
                    last_body = f'NCBI HTTP {resp.status_code}'.encode()
                    retry_after = resp.headers.get('retry-after', '')
                    if retry_after.isdigit():
                        delay = max(delay, float(retry_after))
            if attempt + 1 < attempts:
                self.stats['retries'] += 1
                await asyncio.sleep(delay)
        self.stats['upstream_failed'] += 1
        self._outage_until = time.monotonic() + OUTAGE_SECONDS
        return RelayResult(502, 'text/plain', last_body, False, upstream_failed=True)


_RELAY: EutilsRelay | None = None


def _cache_root() -> Path:
    """Platform-private service caches (never mounted into a sandbox, so a
    sandbox cannot poison what the relay serves to other users).

    ``TM_SERVICE_CACHE_DIR`` (``start-targetmind.sh``:
    <data dir>/service-cache), else ``<persistence>/cache``.
    """
    root = os.getenv('TM_SERVICE_CACHE_DIR')
    if root:
        return Path(root)
    return Path(get_global_config().persistence_dir) / 'cache'


def get_relay() -> EutilsRelay:
    global _RELAY
    if _RELAY is None:
        cache_dir = _cache_root() / 'ncbi-eutils'
        _RELAY = EutilsRelay(cache_dir, _read_key())
        _logger.info(
            'NCBI relay ready (%s key, cache %s)',
            'platform' if _RELAY.api_key else 'no',
            cache_dir,
        )
    return _RELAY


def validate_params(endpoint: str, params: list[tuple[str, str]]) -> None:
    if endpoint not in ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Unknown endpoint')
    size = sum(len(k) + len(v) for k, v in params)
    if size > MAX_PARAM_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Request too large'
        )
    db = [v for k, v in params if k == 'db']
    if endpoint != 'elink' and (len(db) != 1 or db[0] not in DATABASES):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f'db must be one of {sorted(DATABASES)}',
        )
    ids = [i for k, v in params if k == 'id' for i in v.split(',') if i]
    if len(ids) > MAX_IDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f'At most {MAX_IDS} ids per request'
        )


@router.api_route('/eutils/{endpoint}.fcgi', methods=['GET', 'POST'])
async def relay_eutils(
    endpoint: str,
    request: Request,
    sandbox: Annotated[SandboxRecord, Depends(valid_sandbox)],
    client: httpx.AsyncClient = httpx_client_dependency,
) -> Response:
    """Forward a read-only E-utilities call for a sandbox (see module doc)."""
    del sandbox  # authenticated by the dependency
    params = [(k, v) for k, v in request.query_params.multi_items()]
    if request.method == 'POST':
        body = await request.body()
        if len(body) > MAX_PARAM_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Request too large'
            )
        params += parse_qsl(body.decode(errors='replace'), keep_blank_values=True)
    params = [(k, v) for k, v in params if k not in _STRIPPED]
    validate_params(endpoint, params)

    result = await get_relay().fetch(client, endpoint, params)
    headers = {'X-TM-Cache': 'hit' if result.cached else 'miss'}
    if result.upstream_failed:
        headers[UPSTREAM_HEADER] = 'error'
    return Response(
        content=result.body,
        status_code=result.status,
        media_type=result.content_type,
        headers=headers,
    )
