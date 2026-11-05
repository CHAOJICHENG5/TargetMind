#!/usr/bin/env python3
"""tm-novelty: deterministic novelty tiers for candidate targets of one disease.

For every gene it counts PubMed records where the gene (official symbol plus up
to two common aliases) and the disease (name or any synonym) co-occur in the
title/abstract, checks Open Targets for clinical-stage drugs against the gene in
the disease (and optional related diseases), and flags classic markers from a
file the Chief Scientist compiled with sources. Tiers:

  known     cooccurrence >= --known-min, or a clinical drug hit, or classic marker
  emerging  --novel-max < cooccurrence < --known-min
  novel     cooccurrence <= --novel-max
  unknown   PubMed count could not be retrieved (review by hand, never novel)

  tm-novelty --disease "renal fibrosis" --synonyms "kidney fibrosis,renal interstitial fibrosis" \\
             --efo MONDO_0000494,EFO_1001517 --related-efo MONDO_0005300 \\
             --genes-file evidence/evidence_matrix_screen.csv \\
             --markers evidence/classic_markers.csv --out evidence/novelty.csv

Standard library only. Writes the CSV plus <out>.meta.json (date, parameters,
exact queries) so the screen is reproducible.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Sibling modules (same directory in the image: /opt/targetmind/tools).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tm_data  # noqa: E402

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
# Platform relay for NCBI (global rate limit across users, platform API key kept
# on the host, shared cache); NCBI is called directly only without it.
EUTILS_RELAY = os.environ.get('TM_EUTILS_URL', '').rstrip('/')
RELAY_INTERVAL = 0.11
HGNC = 'https://rest.genenames.org/fetch'
CTGOV = 'https://clinicaltrials.gov/api/v2/studies'
DATA_DIR = Path(os.environ.get('TM_DATA_DIR', '/opt/targetmind/data'))
REF_DIR = Path(os.environ.get('TM_REF_DIR', str(DATA_DIR / 'ref')))


def data_path(source: str, name: str = '') -> Path:
    """Path of a local source (rule in tm_data.data_path)."""
    return tm_data.data_path(source, name, data_dir=DATA_DIR, ref_dir=REF_DIR)


# Interventional drug trials whose title/summary names the gene as what the drug
# acts on. Free text cannot separate "drug against APOL1" from "trial enrolling
# APOL1 carriers", so hits are candidates for the Chief Scientist to confirm,
# they never change the tier on their own.
_TRIAL_TYPES = set()  # redacted
_TARGET_VERBS = (
    ''  # redacted
)
OPENTARGETS = 'https://api.platform.opentargets.org/api/v4/graphql'
TIMEOUT = 30
RETRIES = 2
OUT_COLUMNS = [
    'gene',
    'pubmed_cooccurrence',
    'clinical_drug',
    'trial_candidates',
    'classic_marker',
    'tier',
    'evidence_lines',
    'notes',
]
# Open Targets maxClinicalStage values that count as "clinical". UNKNOWN means a
# clinical report without a phase, which still rules out "novel".
CLINICAL_STAGES = {
    'EARLY_PHASE_1': 1,
    'PHASE_1': 2,
    'PHASE_1_2': 3,
    'PHASE_2': 4,
    'PHASE_2_3': 5,
    'PHASE_3': 6,
    'PREAPPROVAL': 7,
    'APPROVAL': 8,
    'UNKNOWN': 0,
}
_ALIAS_OK = re.compile(r'(?!)')  # redacted
_ALIAS_JUNK = re.compile(r'^(FLJ|MGC|KIAA|DKFZ|LOC|HSPC|PRO\d)|ORF', re.IGNORECASE)


# --------------------------------------------------------------------------
# Pure helpers (unit tested)
# --------------------------------------------------------------------------


@dataclass
class Candidate:
    gene: str
    evidence_lines: str = ''
    proposed_by: str = ''
    notes: list[str] = field(default_factory=list)


def classify(
    cooccurrence: int | None,
    clinical_drug: bool,
    classic_marker: bool,
    known_min: int = 20,
    novel_max: int = 2,
) -> str:
    raise NotImplementedError('available on the TargetMind platform')


def _clean_symbol(raw: str) -> str:
    return raw.strip().strip('"\'').upper()


def parse_genes(text: str) -> list[Candidate]:
    """Plain list (one gene per line, '#' comments) or CSV with a `gene` column
    and optional `evidence_lines`, `proposed_by`. Duplicates keep the first row."""
    lines = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith('#')
    ]
    if not lines:
        return []
    out: dict[str, Candidate] = {}
    header = [h.strip().lower() for h in next(csv.reader([lines[0]]))]
    if 'gene' in header:
        for row in csv.DictReader(lines[1:], fieldnames=header):
            gene = _clean_symbol(row.get('gene') or '')
            if gene and gene not in out:
                out[gene] = Candidate(
                    gene=gene,
                    evidence_lines=(row.get('evidence_lines') or '').strip(),
                    proposed_by=(row.get('proposed_by') or '').strip(),
                )
    else:
        for ln in lines:
            for token in re.split(r'[,\s]+', ln):
                gene = _clean_symbol(token)
                if gene and gene not in out:
                    out[gene] = Candidate(gene=gene)
    return list(out.values())


def parse_markers(text: str) -> dict[str, str]:
    """classic_markers.csv (`gene,reason,source`) → {GENE: 'reason (source)'}."""
    lines = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith('#')
    ]
    if not lines:
        return {}
    header = [h.strip().lower() for h in next(csv.reader([lines[0]]))]
    if 'gene' not in header:
        return {_clean_symbol(ln.split(',')[0]): '' for ln in lines}
    markers: dict[str, str] = {}
    for row in csv.DictReader(lines[1:], fieldnames=header):
        gene = _clean_symbol(row.get('gene') or '')
        if gene:
            reason = (row.get('reason') or '').strip()
            source = (row.get('source') or '').strip()
            markers[gene] = f'{reason} ({source})' if source else reason
    return markers


def split_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def tiab(term: str) -> str:
    term = term.replace('"', '')
    return f'"{term}"[tiab]' if re.search(r'[\s-]', term) else f'{term}[tiab]'


def disease_query(disease: str, synonyms: list[str]) -> str:
    terms = list(dict.fromkeys([disease, *synonyms]))
    return '(' + ' OR '.join(tiab(t) for t in terms) + ')'


def gene_query(names: list[str]) -> str:
    return '(' + ' OR '.join(tiab(n) for n in dict.fromkeys(names)) + ')'


def alias_candidates(symbol: str, prev: list[str], aliases: list[str]) -> list[str]:
    """Aliases worth searching: previous official symbols (e.g. CTGF for CCN2)"""
    raise NotImplementedError('available on the TargetMind platform')


def clinical_by_target(rows: list[dict], disease_id: str) -> dict[str, list[str]]:
    """Open Targets drugAndClinicalCandidates rows → {SYMBOL: ['drug (STAGE, id)']}."""
    raise NotImplementedError('available on the TargetMind platform')


def summarise_clinical(entries: list[str]) -> str:
    raise NotImplementedError('available on the TargetMind platform')


def context_related_ids(path: Path) -> list[str]:
    """Related indications from disease_context.csv: `related_indication` and"""
    raise NotImplementedError('available on the TargetMind platform')


def check_trials(http: 'Http', names: list[str], conditions: list[str]) -> list[str]:
    return trial_hits(http.ctgov_studies(names, conditions), names)


def trial_mentions_target(text: str, names: list[str]) -> bool:
    """Title/summary says the intervention acts on one of the gene names."""
    raise NotImplementedError('available on the TargetMind platform')


def trial_hits(studies: list[dict], names: list[str]) -> list[str]:
    """ClinicalTrials.gov v2 studies -> ['NCT… (PHASE2: drug)'] that name the gene as the drug's target."""
    raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------


class Http:
    """Polite, stable calls: per-host minimum interval, exponential backoff with
    jitter on 429/5xx/timeouts (Retry-After honoured), no retry on other 4xx,
    and an on-disk cache of PubMed counts and ClinicalTrials.gov searches so a
    re-run (e.g. a wider screen) only queries new genes."""

    MIN_INTERVAL = {
        'clinicaltrials.gov': 0.3,
        'rest.genenames.org': 0.2,
        'api.platform.opentargets.org': 0.25,
    }

    def __init__(self, ncbi_interval: float, cache_path: Path | None = None) -> None:
        self.ncbi_interval = ncbi_interval
        self._last: dict[str, float] = {}
        self.cache_path = cache_path
        self.cache: dict[str, Any] = {}
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text())
            except ValueError:
                self.cache = {}
        self.calls = 0
        self.cache_hits = 0
        self.relay_calls = 0
        self.relay_down = False
        # Local PubMed library (tm-lit); online PubMed only without it.
        self.lit: Any = None
        self.local_counts = 0
        self._lock = threading.Lock()

    def save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                text = json.dumps(self.cache)
            self.cache_path.write_text(text)

    def _open(self, req: urllib.request.Request) -> bytes:
        host = urllib.parse.urlparse(req.full_url).hostname or ''
        interval = (
            self.ncbi_interval
            if host == 'eutils.ncbi.nlm.nih.gov'
            else self.MIN_INTERVAL.get(host, 0.2)
        )
        last: Exception | None = None
        for attempt in range(RETRIES + 2):
            wait = interval - (time.monotonic() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            delay = 0.0
            try:
                self.calls += 1
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                last = e
                if e.code not in (408, 429) and e.code < 500:
                    raise RuntimeError(f'{req.full_url[:80]}: HTTP {e.code}') from e
                ra = e.headers.get('Retry-After') if e.headers else None
                delay = float(ra) if ra and ra.isdigit() else 0.0
            except Exception as e:  # noqa: BLE001 - timeouts / connection resets
                last = e
            finally:
                self._last[host] = time.monotonic()
            time.sleep(max(delay, min(60.0, 2.0 * 2**attempt)) + random.uniform(0, 1))
        raise RuntimeError(f'{req.full_url[:80]}: {last}')

    def get_json(self, url: str, headers: dict | None = None) -> dict:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'tm-novelty', **(headers or {})}
        )
        return json.loads(self._open(req))

    def post_json(self, url: str, payload: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'User-Agent': 'tm-novelty'},
        )
        return json.loads(self._open(req))

    def ctgov_studies(self, gene_names: list[str], conditions: list[str]) -> list[dict]:
        key = 'ctgov|' + '|'.join(gene_names) + '|' + '|'.join(conditions)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        params = {
            'query.intr': ' OR '.join(f'"{n}"' if ' ' in n else n for n in gene_names),
            'query.cond': ' OR '.join(f'"{c}"' for c in conditions),
            'pageSize': '100',
            'fields': 'NCTId,Phase,InterventionType,InterventionName,BriefTitle,OfficialTitle,BriefSummary',
        }
        data = self.get_json(f'{CTGOV}?{urllib.parse.urlencode(params)}')
        studies = data.get('studies') or []
        with self._lock:
            self.cache[key] = studies
        return studies

    def _relay_esearch(self, params: dict) -> dict | None:
        """esearch through the platform relay; None when it is unusable."""
        session_key = os.environ.get('TM_SESSION_API_KEY')
        if not EUTILS_RELAY or not session_key or self.relay_down:
            return None
        req = urllib.request.Request(
            f'{EUTILS_RELAY}/esearch.fcgi',
            data=urllib.parse.urlencode(params).encode(),
            headers={
                'X-Session-API-Key': session_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'tm-novelty',
            },
        )
        for attempt in range(3):
            wait = RELAY_INTERVAL - (time.monotonic() - self._last.get('relay', 0.0))
            if wait > 0:
                time.sleep(wait)
            try:
                self.calls += 1
                with urllib.request.urlopen(req, timeout=TIMEOUT + 60) as resp:
                    self.relay_calls += 1
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.headers and e.headers.get('X-TM-Upstream') == 'error':
                    # The relay reached NCBI and already retried: PubMed itself
                    # is failing, going direct would not help.
                    raise RuntimeError('PubMed unavailable (NCBI error)') from e
                if e.code == 400:
                    raise RuntimeError(f'PubMed query rejected: HTTP {e.code}') from e
                if e.code in (401, 403, 404):
                    break  # relay not available to this sandbox
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 0:
                    break  # unreachable: fall back at once
            finally:
                self._last['relay'] = time.monotonic()
            time.sleep(2.0 * 2**attempt + random.uniform(0, 1))
        self.relay_down = True
        return None

    def pubmed_count(self, term: str) -> int:
        if self.lit is not None:
            key = f'pubmed-local-{self.lit.version()}|{term}'
            if key in self.cache:
                self.cache_hits += 1
                return int(self.cache[key])
            count = self.lit.count(term)
            with self._lock:
                self.local_counts += 1
                self.cache[key] = count
            return count
        key = 'pubmed|' + term
        if key in self.cache:
            self.cache_hits += 1
            return int(self.cache[key])
        params = {'db': 'pubmed', 'rettype': 'count', 'retmode': 'json', 'term': term}
        data = self._relay_esearch(params)
        if data is None:
            if os.environ.get('NCBI_API_KEY'):
                params['api_key'] = os.environ['NCBI_API_KEY']
            data = self.get_json(f'{EUTILS}?{urllib.parse.urlencode(params)}')
        # NCBI reports failures with HTTP 200 and an ERROR field ("Search Backend
        # failed ..."); never read that as a count.
        res = data.get('esearchresult') if isinstance(data, dict) else None
        if not isinstance(res, dict) or res.get('ERROR') or 'count' not in res:
            error = (res or {}).get('ERROR') if isinstance(res, dict) else None
            error = error or (data.get('error') if isinstance(data, dict) else None)
            raise RuntimeError(f'PubMed error: {str(error or "no count")[:160]}')
        count = int(res['count'])
        with self._lock:
            self.cache[key] = count
        return count


_HGNC_LOCAL: dict[str, list[dict[str, str]]] | None = None


def hgnc_local() -> dict[str, list[dict[str, str]]]:
    """Local HGNC complete set (mounted snapshot): key -> rows, keys are symbols,
    previous symbols and aliases (upper case)."""
    global _HGNC_LOCAL
    if _HGNC_LOCAL is None:
        _HGNC_LOCAL = {}
        path = data_path('hgnc', 'hgnc_complete_set.txt')
        if path.exists():
            with path.open(newline='') as fh:
                for r in csv.DictReader(fh, delimiter='\t'):
                    if r.get('status') and r['status'] != 'Approved':
                        continue
                    _HGNC_LOCAL.setdefault('S:' + r['symbol'].upper(), []).append(r)
                    for f, tag in (('prev_symbol', 'P:'), ('alias_symbol', 'A:')):
                        for v in (r.get(f) or '').strip('"').split('|'):
                            if v:
                                _HGNC_LOCAL.setdefault(tag + v.upper(), []).append(r)
    return _HGNC_LOCAL


def _split(v: str | None) -> list[str]:
    return [x for x in (v or '').strip('"').split('|') if x]


def hgnc_lookup(http: Http, gene: str) -> tuple[str, list[str], list[str], str]:
    """(official symbol, previous symbols, aliases, note). Local snapshot first."""
    local = hgnc_local()
    if local:
        for tag, field_name in (
            ('S:', 'symbol'),
            ('P:', 'prev_symbol'),
            ('A:', 'alias_symbol'),
        ):
            docs = local.get(tag + gene.upper(), [])
            if len(docs) == 1:
                doc = docs[0]
                note = (
                    ''
                    if field_name == 'symbol'
                    else f'input {gene} -> HGNC {doc["symbol"]}'
                )
                return (
                    doc['symbol'],
                    _split(doc.get('prev_symbol')),
                    _split(doc.get('alias_symbol')),
                    note,
                )
            if len(docs) > 1:
                return (
                    gene,
                    [],
                    [],
                    f'{gene} is ambiguous in HGNC ({field_name}); symbol kept',
                )
        return gene, [], [], f'{gene} not found in HGNC; symbol kept'
    for field_name in ('symbol', 'prev_symbol', 'alias_symbol'):
        url = f'{HGNC}/{field_name}/{urllib.parse.quote(gene)}'
        data = http.get_json(url, headers={'Accept': 'application/json'})
        docs = data.get('response', {}).get('docs', [])
        if len(docs) == 1:
            doc = docs[0]
            symbol = doc['symbol']
            note = '' if field_name == 'symbol' else f'input {gene} -> HGNC {symbol}'
            return (
                symbol,
                doc.get('prev_symbol') or [],
                doc.get('alias_symbol') or [],
                note,
            )
        if len(docs) > 1:
            return (
                gene,
                [],
                [],
                f'{gene} is ambiguous in HGNC ({field_name}); symbol kept',
            )
    return gene, [], [], f'{gene} not found in HGNC; symbol kept'


def local_clinical(disease_id: str) -> tuple[str, list[dict]] | None:
    """Clinical candidates of one disease from the local Open Targets subset, in"""
    raise NotImplementedError('available on the TargetMind platform')


def opentargets_release() -> str:
    path = data_path('opentargets', 'opentargets.sqlite')
    return f'local {path.resolve().parent.name}' if path.exists() else 'API'


def opentargets_clinical(
    http: Http, disease_id: str
) -> tuple[str, dict[str, list[str]]]:
    local = local_clinical(disease_id)
    if local is not None:
        return local[0], clinical_by_target(local[1], disease_id)
    query = (
        'query($id:String!){ disease(efoId:$id){ id name drugAndClinicalCandidates{ '
        'count rows{ maxClinicalStage drug{ name mechanismsOfAction{ rows{ '
        'targets{ approvedSymbol } } } } } } } }'
    )
    data = http.post_json(
        OPENTARGETS, {'query': query, 'variables': {'id': disease_id}}
    )
    if data.get('errors'):
        raise RuntimeError(f'Open Targets: {data["errors"][0].get("message")}')
    disease = (data.get('data') or {}).get('disease')
    if not disease:
        raise LookupError(f'{disease_id} not found in Open Targets')
    rows = (disease.get('drugAndClinicalCandidates') or {}).get('rows') or []
    return disease['name'], clinical_by_target(rows, disease['id'])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='tm-novelty',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        '--disease', required=True, help='disease name as used in titles/abstracts'
    )
    p.add_argument('--synonyms', default='', help='comma-separated synonyms')
    p.add_argument(
        '--efo',
        default='',
        help='comma-separated Open Targets disease IDs (EFO/MONDO); the first one found is used',
    )
    p.add_argument(
        '--related-efo',
        default='',
        help='comma-separated IDs of closely related indications; their clinical drugs also count',
    )
    p.add_argument(
        '--genes-file', required=True, help='gene list (txt) or CSV with a gene column'
    )
    p.add_argument(
        '--markers', default='', help='classic_markers.csv (gene,reason,source)'
    )
    p.add_argument('--out', required=True, help='output CSV, e.g. evidence/novelty.csv')
    p.add_argument('--known-min', type=int, default=20)
    p.add_argument('--novel-max', type=int, default=2)
    p.add_argument('--max-aliases', type=int, default=2)
    p.add_argument(
        '--context',
        default='',
        help='evidence/disease_context.csv: adds its related_indication and proxy_disease ids '
        'to --related-efo (uses the _resolved.csv written by tm-discover pool)',
    )
    p.add_argument(
        '--trial-conditions',
        default=None,
        help='";"-separated condition names for the ClinicalTrials.gov check '
        "(default: the disease, its synonyms and the related indications' names; "
        'empty string disables it)',
    )
    p.add_argument(
        '--online-pubmed',
        action='store_true',
        help='count on PubMed online instead of the local PubMed library',
    )
    return p


def run(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # One run per output file: a second launch (e.g. a re-issued background
    # command) would double the NCBI request rate and race on the same CSV.
    lock_path = Path(str(args.out) + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                f'tm-novelty: another run is already writing {args.out}; '
                'wait for it to finish instead of starting a new one',
                file=sys.stderr,
            )
            return 3
        try:
            return run(args)
        finally:
            lock_path.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
