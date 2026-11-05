#!/usr/bin/env python3
"""tm-discover: deterministic candidate pool and evidence matrix for one disease.

  tm-discover prepare --disease-id EFO_1001517,MONDO_0000494 --add "<names;...>"
  tm-discover pool  --disease-id MONDO_0000494 --disease-name "renal fibrosis" \\
                    --context evidence/disease_context.csv --out evidence/pool.csv
  tm-discover merge --pool evidence/pool.csv \\
                    --omics experts/bioinformatics/omics_full.csv \\
                    --genetics experts/genetics/genetics_review.csv \\
                    --mechanism experts/molecular-biology/mechanism.csv \\
                    --out evidence/evidence_matrix.csv
  tm-discover kg    --disease-id MONDO_0005300 [--top 50]       # KG ranking only
  tm-discover selftest                                           # numpy KG == PyKEEN

pool   Open Targets per-datatype scores for the disease and its proxies, GWAS
       Catalog hits for proxy traits, and the PrimeKG KGE ensemble (RotatE,
       DistMult, HolE; numpy) over the disease and its KG anchors. Writes
       pool.csv (entry genes, sorted by prior_rank), ot_scores.csv (every
       gene Open Targets returned) and pool.csv.meta.json.
merge  Adds the experts' columns and counts the three independent evidence
       lines (omics, genetic, mechanism). KG and literature only rank. Writes
       the matrix and <out>_screen.csv: the genes worth a novelty screen.

disease_context.csv (Chief Scientist): kind,id,name,reason,source with kind in
  proxy_disease       related disease used for genetic evidence (e.g. CKD)
  proxy_measure       quantitative trait (e.g. eGFR): ranks and informs the genetics
                      review, never makes the genetic line on its own;
                      `name` must be the trait's EFO/OBA label (GWAS Catalog query)
  kg_anchor           related disease (MONDO) the KG also scores from
  related_indication  for tm-novelty --related-efo (ignored here)

Standard library + numpy only. Network calls time out, retry twice and are
recorded as missing in the meta file rather than silently skipped.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Sibling modules (same directory in the image: /opt/targetmind/tools).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tm_data  # noqa: E402

OPENTARGETS = 'https://api.platform.opentargets.org/api/v4/graphql'
GWAS = 'https://www.ebi.ac.uk/gwas/rest/api/v2/associations'
# Local reference data (ops/build_reference_data.py), mounted read-only:
# <data>/ref/<source>/current/... with <data>/manifest.json listing the versions.
DATA_DIR = Path(os.environ.get('TM_DATA_DIR', '/opt/targetmind/data'))
REF_DIR = Path(os.environ.get('TM_REF_DIR', str(DATA_DIR / 'ref')))


def data_path(source: str, name: str = '') -> Path:
    """Path of a local source (rule in tm_data.data_path: current version, else
    the previous flat layout)."""
    if source == 'primekg' and not (REF_DIR / source / 'current').exists():
        return DATA_DIR / 'kg' / name if name else DATA_DIR / 'kg'
    return tm_data.data_path(source, name, data_dir=DATA_DIR, ref_dir=REF_DIR)


def data_versions() -> dict[str, str]:
    """Current version of every local source, for the meta files."""
    versions = tm_data.data_versions(DATA_DIR)
    if versions:
        return versions
    release = gwas_release()  # previous layout: GWAS release only
    return {'gwas': release} if release else {}


KG_DIR = Path(os.environ.get('TM_KG_DIR', str(data_path('primekg'))))
TIMEOUT = 120
RETRIES = 2
KG_MODELS = ('rotate', 'distmult', 'hole')
RARE_SOURCES = ()  # redacted
TRUE = {'yes', 'y', 'true', '1'}


# --------------------------------------------------------------------------
# Pure helpers (unit tested)
# --------------------------------------------------------------------------


def norm_gene(raw: str | None) -> str:
    return (raw or '').strip().strip('"\'').upper()


def is_yes(value: str | None) -> bool:
    return (value or '').strip().lower() in TRUE


def to_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(out) else out


def read_csv(path: Path) -> list[dict[str, str]]:
    """CSV rows with lower-case keys. Unquoted commas in the last column (common in
    hand-written `reason` fields) are folded back into that column."""
    with path.open(newline='') as fh:
        reader = csv.DictReader(
            line for line in fh if not line.lstrip().startswith('#')
        )
        rows = list(reader)
        last = (reader.fieldnames or [''])[-1]
    out = []
    for r in rows:
        extra = r.pop(None, None)  # type: ignore[call-overload]
        if extra:
            r[last] = ','.join([r.get(last) or '', *extra])
        out.append({(k or '').strip().lower(): (v or '').strip() for k, v in r.items()})
    return out


def names_agree(given: str, found: str) -> bool:
    """Loose check that an ID's Open Targets name matches the name written next to it."""
    words = lambda t: {w for w in re.findall(r'[a-z0-9]+', t.lower()) if len(w) > 2}  # noqa: E731
    g, f = words(given), words(found)
    return not g or not f or bool(g & f)


def parse_context(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    kinds: dict[str, list[dict[str, str]]] = {
        'proxy_disease': [],
        'proxy_measure': [],
        'kg_anchor': [],
        'related_indication': [],
    }
    for r in rows:
        kind = r.get('kind', '').lower()
        if kind == 'proxy_trait':  # tolerated: treat as a disease-type proxy
            kind = 'proxy_disease'
        if kind in kinds and (r.get('id') or r.get('name')):
            kinds[kind].append(r)
    return kinds


def mondo_node_ids(disease_id: str) -> str | None:
    """MONDO_0000494 -> '494' (PrimeKG disease node_id)."""
    m = re.fullmatch(r'MONDO[_:](\d+)', disease_id.strip(), re.IGNORECASE)
    return str(int(m.group(1))) if m else None


def match_primekg_disease(node_id: str, rows: list[dict[str, str]]) -> list[int]:
    """Rows whose node_id is `node_id` or a MONDO_grouped id containing it."""
    exact = [i for i, r in enumerate(rows) if r['node_id'] == node_id]
    if exact:
        return exact
    return [i for i, r in enumerate(rows) if node_id in r['node_id'].split('_')]


# Cross-reference ontologies that link an Open Targets disease to a PrimeKG (MONDO)
# disease, most specific first: EFO/DOID map 1:1 in PrimeKG's MONDO release, MeSH and
# UMLS are coarser. Used only when no MONDO id and no name match is available.
XREF_ORDER = ('EFO', 'DOID', 'OMIM', 'ORPHANET', 'NCIT', 'MESH', 'ICD10', 'UMLS')


def norm_disease_name(name: str) -> str:
    """Case/punctuation-insensitive disease name; PrimeKG suffixes some single
    terms with "(disease)" to tell them from a grouped node of the same name."""
    name = re.sub(r'\s*\(disease\)\s*$', '', (name or '').lower())
    return re.sub(r'[^a-z0-9]+', ' ', name).strip()


def split_ids(spec: str | list[str]) -> list[str]:
    items = spec if isinstance(spec, list) else re.split(r'[,\s]+', spec or '')
    return list(dict.fromkeys(x.strip() for x in items if x and x.strip()))


_OT_RECORD = (
    'query($id:String!){ disease(efoId:$id){ id name dbXRefs '
    'synonyms{ relation terms } } }'
)
_ot_records: dict[str, dict | None] = {}


def opentargets_disease_record(disease_id: str) -> dict | None:
    """Name, cross-references and exact synonyms of an Open Targets disease (cached)."""
    if disease_id not in _ot_records:
        local = ot_local()
        _ot_records[disease_id] = (
            local.disease(disease_id)
            if local
            else graphql(_OT_RECORD, {'id': disease_id}).get('disease')
        )
    return _ot_records[disease_id]


def genetic_line(
    scores: dict[str, float],
    disease_sources: set[str],
    rare: float,
    min_score: float = 0.5,
) -> tuple[bool, str]:
    """Tool value of the genetic line from Open Targets genetic scores per source."""
    raise NotImplementedError('available on the TargetMind platform')


def fuse_reciprocal_ranks(
    ranks: dict[str, dict[int, int]], weights: dict[str, float]
) -> dict[int, float]:
    """{model: {gene_row: rank}} -> {gene_row: sum_m w_m / rank_m} (weights renormalised)."""
    raise NotImplementedError('available on the TargetMind platform')


def omics_line(row: dict[str, str]) -> tuple[bool, str]:
    """>=2 datasets significant in the same direction and none in the opposite one."""
    raise NotImplementedError('available on the TargetMind platform')


OMICS_DATASET_COLUMNS = [
    'dataset',
    'compartment',
    'composition_adjusted',
    'method',
    'n_case',
    'n_control',
]


def normalise_dataset(d: dict[str, str]) -> tuple[str, bool]:
    """(compartment in matched/whole_tissue/other, composition-adjusted) from the"""
    raise NotImplementedError('available on the TargetMind platform')


def countable_datasets(datasets: list[dict[str, str]]) -> dict[str, str]:
    """Scheme C-A: dataset -> why it counts. Matched compartment / cell type counts;"""
    raise NotImplementedError('available on the TargetMind platform')


def _dataset_columns(row: dict[str, str], ds: str) -> tuple[str | None, str | None]:
    """logFC / padj column names of one dataset; the composition-adjusted padj (and
    logFC) win when present. Dataset names may carry a platform suffix. Matching
    is case-insensitive (read_csv lower-cases the header)."""
    lower = {k.lower(): k for k in row}
    name = ds.lower()

    def find(prefixes: tuple[str, ...]) -> str | None:
        for pre in prefixes:
            if (pre + name).lower() in lower:
                return lower[(pre + name).lower()]
        for pre in prefixes:  # GSE104954 vs GSE104954-GPL22945
            stem = (pre + name + '-').lower()
            hit = next((k for k in lower if k.startswith(stem)), None)
            if hit:
                return lower[hit]
        return None

    lfc = find(('logFCadj_', 'logFC_adj_', 'logFC_'))
    padj = find(('padj_adj_', 'padjadj_', 'padj_adjComp_', 'padj_adjusted_', 'padj_'))
    return lfc, padj


def recount_omics(
    row: dict[str, str], counted: dict[str, str], padj_max: float = 0.05
) -> dict[str, str]:
    """n_sig_up / n_sig_down recomputed from the per-dataset logFC / padj columns"""
    raise NotImplementedError('available on the TargetMind platform')


def omics_counts(
    consistent: bool, direction: str, has_mechanism: bool
) -> tuple[bool, str]:
    """Whether a consistent omics signal counts as the omics line."""
    raise NotImplementedError('available on the TargetMind platform')


def mechanism_line(row: dict[str, str]) -> bool:
    raise NotImplementedError('available on the TargetMind platform')


def screen_selection(
    rows: list[dict], max_genes: int = 200, min_genes: int = 30, min_lines: int = 2
) -> list[dict]:
    """Genes for tm-novelty: every gene with >= min_lines evidence lines (up to"""
    raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# Workflow notification and progress
# --------------------------------------------------------------------------

AGENT_RUNTIME = os.environ.get('TM_AGENT_RUNTIME_URL', 'http://127.0.0.1:8000')
_POST_SCRIPT = (
    'import os,sys,urllib.request\n'
    'req=urllib.request.Request(sys.argv[1],data=sys.argv[2].encode(),'
    'headers={"Content-Type":"application/json",'
    '"X-Session-API-Key":os.environ["TM_SESSION_API_KEY"]})\n'
    'urllib.request.urlopen(req,timeout=1800).read()\n'
)


def task_conversation_id(cwd: Path) -> str | None:
    """Conversation id from the task folder /workspace/project/<id>[/...]."""
    parts = cwd.resolve().parts
    for i, part in enumerate(parts[:-1]):
        if part == 'project' and re.fullmatch(r'[0-9a-f]{32}', parts[i + 1]):
            return parts[i + 1]
    return None


def notify_chief(text: str) -> bool:
    """Print the next workflow step and queue it as a user message for the"""
    raise NotImplementedError('available on the TargetMind platform')


class Heartbeat:
    """Prints a line every `every` seconds so long steps (GWAS Catalog) never
    look idle to the terminal's no-output timeout."""

    def __init__(self, label: str, every: float = 20.0) -> None:
        self.label, self.every = label, every
        self.started = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            print(
                f'[{self.label}] still working ({time.monotonic() - self.started:.0f}s)',
                flush=True,
            )

    def __enter__(self) -> 'Heartbeat':
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()


DISCOVERY_REMINDER = (
    'evidence/pool.csv is ready ({n} genes; columns gene, prior_rank, line_genetic_tool, '
    'genetic_basis, genetic_best, kg_rank, ...; genetics table evidence/genetics_evidence.csv). '
    'Next: (1) update the plan in one task_tracker call (candidate pool done, "{n} genes"; '
    'discovery batch in_progress, note "bioinformatics, genetics, molecular-biology dispatched '
    'together (3 task calls)"); (2) the response right after that plan update must be exactly '
    'three `task` calls and nothing else (no terminal, no checks): bioinformatics, genetics, '
    'molecular-biology, each brief starting with `PHASE: discovery`, at most ~1200 characters '
    "(methods are in the experts' SOPs)."
)
EVALUATION_REMINDER = (
    'shortlist.csv is ready ({n} genes). Next: (1) write the report.md draft in ONE edit; '
    '(2) update the plan in one task_tracker call (novelty screen + shortlist done, "{n} genes"; '
    'evaluation batch in_progress, note "bioinformatics, genetics, molecular-biology, '
    'medicinal-chemistry dispatched together (4 task calls)"); (3) the response right after '
    'that plan update must be exactly four `task` calls and nothing else (no terminal, no '
    'checks), each brief starting with `PHASE: evaluation`, at most ~1200 characters.'
)


# --------------------------------------------------------------------------
# Shortlist (pure)
# --------------------------------------------------------------------------

TIER_WEIGHT = {'novel': 3, 'emerging': 2}


def shortlist_rows(
    matrix: dict[str, dict[str, str]],
    novelty: list[dict[str, str]],
    max_genes: int = 10,
    user_genes: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """D3/D7/D8/D24: drop known and unknown tiers, novel and emerging genes need"""
    raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------


# Polite, stable calls: one request at a time per host with a minimum interval,
# exponential backoff with jitter on 429/5xx/timeouts (Retry-After honoured), and
# no retry on other 4xx (a malformed query fails the same way every time).
_MIN_INTERVAL = {
    'api.platform.opentargets.org': 0.25,
    'www.ebi.ac.uk': 0.5,
    'eutils.ncbi.nlm.nih.gov': 0.34,
    'ftp.ncbi.nlm.nih.gov': 0.5,
    'www.ncbi.nlm.nih.gov': 0.5,
    'clinicaltrials.gov': 0.3,
    'ftp.ebi.ac.uk': 0.0,
}
_host_lock: dict[str, Any] = {}
_host_last: dict[str, float] = {}
_locks_guard = threading.Lock()


class RequestFailed(RuntimeError):
    pass


# Static file servers that allow a few parallel downloads (per-sample EBI files).
_PARALLEL_HOSTS = {'ftp.ebi.ac.uk': 6}
# (The NCBI relay is called by _relay_open, not _open: it paces all users itself.)


def _pace(host: str) -> threading.Lock | threading.BoundedSemaphore:
    with _locks_guard:
        lock = _host_lock.setdefault(
            host,
            threading.BoundedSemaphore(_PARALLEL_HOSTS[host])  # type: ignore[arg-type]
            if host in _PARALLEL_HOSTS
            else threading.Lock(),
        )
    return lock


def _open(req: urllib.request.Request, timeout: int = TIMEOUT) -> bytes:
    host = urllib.parse.urlparse(req.full_url).hostname or ''
    last: Exception | None = None
    for attempt in range(RETRIES + 2):
        with _pace(host):
            wait = _MIN_INTERVAL.get(host, 0.2) - (
                time.monotonic() - _host_last.get(host, 0.0)
            )
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                last = e
                body = e.read()[:300].decode(errors='replace')
                if e.code not in (408, 429) and e.code < 500:
                    raise RequestFailed(
                        f'{req.full_url[:90]}: HTTP {e.code} {body}'
                    ) from e
                retry_after = e.headers.get('Retry-After') if e.headers else None
                delay = (
                    float(retry_after) if retry_after and retry_after.isdigit() else 0.0
                )
            except Exception as e:  # noqa: BLE001 - timeouts / connection resets
                last, delay = e, 0.0
            finally:
                _host_last[host] = time.monotonic()
        time.sleep(max(delay, min(60.0, 2.0 * 2**attempt)) + random.uniform(0, 1))
    raise RequestFailed(f'{req.full_url[:90]}: {last}')


class OTLocal:
    """Local Open Targets subset (ops/build_opentargets.py), read-only. Tools use it
    first and call the GraphQL API only without it (or for literature similarity,
    which is not in the download)."""

    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(
            f'file:{path}?mode=ro&immutable=1', uri=True, check_same_thread=False
        )
        meta = dict(self.db.execute('SELECT key, value FROM meta'))
        self.release = json.loads(meta.get('release', '""'))

    def disease(self, disease_id: str) -> dict | None:
        row = self.db.execute(
            'SELECT id, name, dbxrefs, exact_synonyms, parents, children, '
            'therapeutic_areas FROM disease WHERE id = ?',
            (disease_id,),
        ).fetchone()
        if not row:
            return None
        ids = {
            k: json.loads(v)
            for k, v in zip(
                ('dbXRefs', 'exact', 'parents', 'children', 'therapeuticAreas'),
                row[2:],
                strict=True,
            )
        }
        names = self.names(ids['parents'] + ids['children'] + ids['therapeuticAreas'])
        return {
            'id': row[0],
            'name': row[1],
            'dbXRefs': ids['dbXRefs'],
            'synonyms': [{'relation': 'hasExactSynonym', 'terms': ids['exact']}],
            **{
                k: [{'id': i, 'name': names.get(i, i)} for i in ids[k]]
                for k in ('parents', 'children', 'therapeuticAreas')
            },
        }

    def names(self, ids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        ids = list(dict.fromkeys(ids))
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            out.update(
                self.db.execute(
                    f'SELECT id, name FROM disease WHERE id IN ({",".join("?" * len(chunk))})',
                    chunk,
                )
            )
        return out

    def search(self, name: str) -> tuple[str, str] | None:
        """Exact (case-insensitive) disease name, then exact synonym."""
        key = name.strip().lower()
        row = self.db.execute(
            'SELECT id, name FROM disease WHERE lower(name) = ? ORDER BY id LIMIT 1',
            (key,),
        ).fetchone()
        if row:
            return row[0], row[1]
        for did, dname, syn in self.db.execute(
            'SELECT id, name, exact_synonyms FROM disease WHERE exact_synonyms LIKE ?',
            (f'%{name.strip()}%',),
        ):
            if key in (t.lower() for t in json.loads(syn)):
                return did, dname
        return None

    _DATATYPES = (
        'genetic_association',
        'somatic_mutation',
        'known_drug',
        'affected_pathway',
        'rna_expression',
        'literature',
        'animal_model',
        'genetic_literature',
    )

    def associations(self, disease_id: str) -> list[dict]:
        """Indirect associations shaped like the API rows (all of them, no paging).
        `datasourceScores` carries `rare` (max of RARE_SOURCES) and
        `gwas_credible_sets`."""
        cols = ', '.join(f'a.{c}' for c in self._DATATYPES)
        rows = []
        for r in self.db.execute(
            f'SELECT t.symbol, t.biotype, {cols}, a.rare, a.gwas_credible_sets '
            'FROM assoc a JOIN target t ON t.id = a.target_id WHERE a.disease_id = ?',
            (disease_id,),
        ):
            n = len(self._DATATYPES)
            rows.append(
                {
                    'target': {'approvedSymbol': r[0], 'biotype': r[1]},
                    'datatypeScores': [
                        {'id': k, 'score': v}
                        for k, v in zip(self._DATATYPES, r[2 : 2 + n], strict=True)
                        if v
                    ],
                    'datasourceScores': [
                        {'id': k, 'score': v}
                        for k, v in (
                            ('rare', r[2 + n]),
                            ('gwas_credible_sets', r[3 + n]),
                        )
                        if v
                    ],
                }
            )
        return rows

    def metrics(self, disease_id: str) -> dict:
        gen, total = self.db.execute(
            'SELECT count(CASE WHEN gwas_credible_sets > 0 THEN 1 END), count(*) '
            'FROM assoc WHERE disease_id = ?',
            (disease_id,),
        ).fetchone()
        drugs = self.db.execute(
            'SELECT count(DISTINCT drug_id) FROM clinical WHERE disease_id = ?',
            (disease_id,),
        ).fetchone()[0]
        return {'genetic_targets': gen, 'clinical_drugs': drugs, 'all_targets': total}

    def own_genetic_genes(self, disease_id: str, min_score: float) -> int:
        return self.db.execute(
            'SELECT count(*) FROM assoc a JOIN target t ON t.id = a.target_id '
            "WHERE a.disease_id = ? AND a.genetic_association >= ? AND t.biotype = 'protein_coding'",
            (disease_id, min_score),
        ).fetchone()[0]

    def credible_set_rows(self, disease_id: str, ensembl_ids: list[str]) -> list[dict]:
        out = []
        for i in range(0, len(ensembl_ids), 500):
            chunk = ensembl_ids[i : i + 500]
            out += [
                dict(
                    zip(
                        (
                            'symbol',
                            'score',
                            'study',
                            'variant',
                            'p',
                            'beta',
                            'l2g_symbol',
                            'l2g_score',
                            'trait',
                            'pmid',
                        ),
                        r,
                        strict=True,
                    )
                )
                for r in self.db.execute(
                    'SELECT t.symbol, e.score, l.study_id, l.variant, l.p, l.beta, '
                    'l.l2g_symbol, l.l2g_score, s.trait, s.pmid FROM cs_evidence e '
                    'JOIN target t ON t.id = e.target_id '
                    'LEFT JOIN locus l ON l.study_locus_id = e.study_locus_id '
                    'LEFT JOIN study s ON s.study_id = l.study_id '
                    f'WHERE e.disease_id = ? AND e.target_id IN ({",".join("?" * len(chunk))})',
                    [disease_id, *chunk],
                )
            ]
        return out


_OT_LOCAL: list[OTLocal | None] = []


def ot_local() -> OTLocal | None:
    """The local Open Targets subset if mounted (cached)."""
    if not _OT_LOCAL:
        path = data_path('opentargets', 'opentargets.sqlite')
        _OT_LOCAL.append(OTLocal(path) if path.exists() else None)
    return _OT_LOCAL[0]


def ot_source() -> str:
    local = ot_local()
    return f'local Open Targets {local.release}' if local else 'Open Targets API'


def graphql(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        OPENTARGETS,
        data=json.dumps({'query': query, 'variables': variables}).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'tm-discover'},
    )
    data = json.loads(_open(req))
    if data.get('errors'):
        raise RuntimeError(f'Open Targets: {data["errors"][0].get("message")}')
    return data.get('data') or {}


_OT_ASSOC = (
    'query($id:String!,$i:Int!){ disease(efoId:$id){ id name associatedTargets('
    'page:{index:$i,size:500}){ count rows{ target{ approvedSymbol biotype } '
    'datatypeScores{ id score } datasourceScores{ id score } } } } }'
)


def opentargets_associations(
    disease_id: str, max_pages: int = 30
) -> tuple[str, list[dict]]:
    local = ot_local()
    if local:
        disease = local.disease(disease_id)
        if not disease:
            raise LookupError(f'{disease_id} not found in Open Targets {local.release}')
        return disease['name'], local.associations(disease_id)
    first = graphql(_OT_ASSOC, {'id': disease_id, 'i': 0}).get('disease')
    if not first:
        raise LookupError(f'{disease_id} not found in Open Targets')
    assoc = first['associatedTargets']
    rows = list(assoc['rows'])
    pages = min(max_pages, (assoc['count'] + 499) // 500)
    for i in range(1, pages):
        rows += graphql(_OT_ASSOC, {'id': disease_id, 'i': i})['disease'][
            'associatedTargets'
        ]['rows']
    return first['name'], rows


def opentargets_mondo(disease_id: str) -> str | None:
    """EFO/other ID -> MONDO via Open Targets cross-references."""
    data = graphql(
        'query($id:String!){ disease(efoId:$id){ id dbXRefs } }', {'id': disease_id}
    )
    disease = data.get('disease') or {}
    if mondo_node_ids(disease.get('id', '')):
        return disease['id']
    for ref in disease.get('dbXRefs') or []:
        if mondo_node_ids(ref.replace(':', '_')):
            return ref.replace(':', '_')
    return None


def opentargets_search(name: str) -> tuple[str, str] | None:
    """Best Open Targets disease/phenotype/measurement match for a name -> (id, name):
    an exact name or synonym in the local subset, else the API's fuzzy search."""
    local = ot_local()
    hit = local.search(name) if local else None
    if hit:
        return hit
    data = graphql(
        'query($q:String!){ search(queryString:$q, entityNames:["disease"], '
        'page:{index:0,size:5}){ hits{ id name } } }',
        {'q': name},
    )
    hits = (data.get('search') or {}).get('hits') or []
    exact = [h for h in hits if h['name'].lower() == name.strip().lower()]
    best = (exact or hits or [None])[0]
    return (best['id'], best['name']) if best else None


def resolve_disease_id(spec: str) -> tuple[str, str, list[str]]:
    """First id in a comma/space-separated list that Open Targets indexes ->
    (id, name, ids tried before it). Titles carry several ids (EFO, MONDO) and
    Open Targets often indexes only one of them (e.g. renal fibrosis: MONDO_0000494,
    not EFO_1001517). Raises LookupError listing every id tried."""
    ids = list(dict.fromkeys(x for x in re.split(r'[,\s]+', spec or '') if x))
    if not ids:
        raise LookupError('no disease id given')
    tried: list[str] = []
    local = ot_local()
    for did in ids:
        d = (
            local.disease(did)
            if local
            else graphql(
                'query($id:String!){ disease(efoId:$id){ id name } }', {'id': did}
            ).get('disease')
        )
        if d:
            return d['id'], d['name'], tried
        tried.append(did)
    raise LookupError(
        f'none of {", ".join(tried)} is a disease in Open Targets. Pass every id from '
        'the <DISEASE_WORKSPACE> block comma-separated (e.g. --disease-id '
        'EFO_x,MONDO_y); the first one Open Targets knows is used.'
    )


def use_disease_id(args: argparse.Namespace) -> bool:
    """Resolve args.disease_id in place; prints the choice or the error."""
    try:
        did, name, skipped = resolve_disease_id(args.disease_id)
    except (LookupError, RequestFailed, RuntimeError) as e:
        print(f'tm-discover: ERROR {e}', file=sys.stderr)
        return False
    if skipped:
        print(
            f'Using {did} ({name}); not in Open Targets: {", ".join(skipped)}. '
            f'Use --disease-id {did} in the next commands.'
        )
    # The other ids still identify the disease elsewhere (a MONDO id finds the
    # PrimeKG node even when Open Targets indexes the disease under EFO).
    args.disease_ids = split_ids([did, *split_ids(args.disease_id)])
    args.disease_id = did
    return True


_OT_NEIGHBOURS = (
    'query($id:String!){ disease(efoId:$id){ id name parents{ id name } '
    'children{ id name } therapeuticAreas{ id name } '
    'similarEntities(entityNames:["disease"], size:30, threshold:0.5){ score object{ ... on Disease { id name } } } } }'
)
_OT_METRICS = (
    'query($id:String!){ disease(efoId:$id){ id name drugAndClinicalCandidates{ count } '
    'gen:associatedTargets(datasources:[{id:"gwas_credible_sets",weight:1,propagate:true,required:true}],'
    'page:{index:0,size:1}){ count } all:associatedTargets(page:{index:0,size:1}){ count } } }'
)


def opentargets_neighbours(disease_id: str) -> tuple[dict, list[dict]]:
    """Related diseases: ontology parents/children/siblings/therapeutic areas and"""
    raise NotImplementedError('available on the TargetMind platform')


_OT_METRIC_FIELDS = (
    'id drugAndClinicalCandidates{ count } '
    'gen:associatedTargets(datasources:[{id:"gwas_credible_sets",weight:1,propagate:true,required:true}],'
    'page:{index:0,size:1}){ count } all:associatedTargets(page:{index:0,size:1}){ count }'
)


def opentargets_metrics_many(
    disease_ids: list[str], per_request: int = 15
) -> list[dict]:
    """Metrics for many diseases with GraphQL aliases: ~15 diseases per request
    instead of one request each (same numbers as opentargets_metrics)."""
    local = ot_local()
    if local:
        return [local.metrics(did) for did in disease_ids]
    out: dict[str, dict] = {}
    ids = list(dict.fromkeys(disease_ids))
    for i in range(0, len(ids), per_request):
        chunk = ids[i : i + per_request]
        query = (
            '{ '
            + ' '.join(
                f'd{k}: disease(efoId:{json.dumps(did)}){{ {_OT_METRIC_FIELDS} }}'
                for k, did in enumerate(chunk)
            )
            + ' }'
        )
        try:
            data = graphql(query, {})
        except Exception as e:  # noqa: BLE001
            print(f'tm-discover: WARNING metrics batch: {e}', file=sys.stderr)
            data = {}
        for k, did in enumerate(chunk):
            d = data.get(f'd{k}') or {}
            out[did] = {
                'genetic_targets': (d.get('gen') or {}).get('count', '') if d else '',
                'clinical_drugs': (d.get('drugAndClinicalCandidates') or {}).get(
                    'count', ''
                )
                if d
                else '',
                'all_targets': (d.get('all') or {}).get('count', '') if d else '',
            }
    return [out[did] for did in disease_ids]


def opentargets_metrics(disease_id: str) -> dict:
    local = ot_local()
    if local:
        return local.metrics(disease_id)
    d = graphql(_OT_METRICS, {'id': disease_id}).get('disease') or {}
    return {
        'genetic_targets': (d.get('gen') or {}).get('count', 0),
        'clinical_drugs': (d.get('drugAndClinicalCandidates') or {}).get('count', 0),
        'all_targets': (d.get('all') or {}).get('count', 0),
    }


def gwas_db() -> sqlite3.Connection | None:
    """Local GWAS Catalog snapshot (ops/build_reference_data.py), read-only."""
    path = data_path('gwas', 'gwas_catalog.sqlite')
    if not path.exists():
        return None
    return sqlite3.connect(
        f'file:{path}?mode=ro&immutable=1', uri=True, check_same_thread=False
    )


def gwas_release() -> str:
    try:
        sources = json.loads((DATA_DIR / 'manifest.json').read_text())['sources']
        return sources['gwas']['current']
    except Exception:  # noqa: BLE001
        pass
    try:
        return json.loads((REF_DIR / 'manifest.json').read_text())['gwas']['release']
    except Exception:  # noqa: BLE001
        return ''


def gwas_hits(trait_name: str, trait_id: str = '') -> dict[str, dict]:
    """Genome-wide significant associations (p < 5e-8, mapped genes) for a trait
    -> {GENE: {'studies': set, 'pmids': set, 'best_p': float}}. Uses the local
    snapshot (whole catalog, matched by EFO/OBA/MONDO id or exact label); falls
    back to the REST API (slow: ~17 s per 200 associations) without one."""
    db = gwas_db()
    hits: dict[str, dict] = {}

    def add(gene: str, study: str, pmid: str, p: float) -> None:
        h = hits.setdefault(
            norm_gene(gene), {'studies': set(), 'pmids': set(), 'best_p': 1.0}
        )
        h['studies'].add(study)
        if pmid:
            h['pmids'].add(str(pmid))
        h['best_p'] = min(h['best_p'], p)

    if db is not None:
        where, arg = (
            ('trait_id = ?', trait_id)
            if trait_id
            else ('trait = ?', trait_name.strip().lower())
        )
        rows = db.execute(
            f'SELECT gene, study, pmid, p FROM assoc WHERE {where} AND mapped = 1 AND p < 5e-8',
            (arg,),
        ).fetchall()
        if not rows and trait_id and trait_name:
            rows = db.execute(
                'SELECT gene, study, pmid, p FROM assoc WHERE trait = ? AND mapped = 1 AND p < 5e-8',
                (trait_name.strip().lower(),),
            ).fetchall()
        for gene, study, pmid, p in rows:
            add(gene, study, pmid, p)
        return hits

    def page(i: int) -> dict:
        query = urllib.parse.urlencode(
            {'efo_trait': trait_name, 'size': 200, 'page': i}
        )
        req = urllib.request.Request(
            f'{GWAS}?{query}', headers={'User-Agent': 'tm-discover'}
        )
        return json.loads(_open(req, timeout=180))

    first = page(0)
    pages = [first] + [
        page(i) for i in range(1, min(60, first.get('page', {}).get('totalPages', 0)))
    ]
    for pg in pages:
        for a in (pg.get('_embedded') or {}).get('associations', []):
            p = to_float(a.get('p_value'), 1.0)
            if p < 5e-8:
                for gene in a.get('mapped_genes') or []:
                    add(gene, a.get('accession_id'), a.get('pubmed_id'), p)
    return hits


def gwas_gene_rows(genes: list[str], limit_per_gene: int = 25) -> list[dict]:
    """All genome-wide significant GWAS Catalog associations of the given genes
    (any trait), strongest first: the genetics expert's lookup table."""
    db = gwas_db()
    if db is None:
        raise FileNotFoundError('local GWAS Catalog snapshot not mounted')
    out = []
    for g in dict.fromkeys(norm_gene(x) for x in genes if x):
        rows = db.execute(
            'SELECT gene, mapped, trait_id, trait, reported_trait, p, effect, ci, snp, risk_allele, '
            'context, study, pmid, sample FROM assoc WHERE gene = ? AND p < 5e-8 ORDER BY p LIMIT ?',
            (g, limit_per_gene),
        ).fetchall()
        cols = [
            'gene',
            'mapped',
            'trait_id',
            'trait',
            'reported_trait',
            'p',
            'effect',
            'ci',
            'snp',
            'risk_allele',
            'context',
            'study',
            'pmid',
            'sample',
        ]
        out += [dict(zip(cols, r, strict=False)) for r in rows]
    return out


_HGNC: dict[str, dict[str, str]] | None = None


def hgnc_symbols() -> dict[str, dict[str, str]]:
    """Local HGNC complete set: SYMBOL -> row (also indexed by previous symbols)."""
    global _HGNC
    if _HGNC is None:
        _HGNC = {}
        path = data_path('hgnc', 'hgnc_complete_set.txt')
        if path.exists():
            with path.open(newline='') as fh:
                rows = list(csv.DictReader(fh, delimiter='\t'))
            for r in rows:
                _HGNC[r['symbol'].upper()] = r
            for r in rows:
                for prev in (r.get('prev_symbol') or '').strip('"').split('|'):
                    if prev:
                        _HGNC.setdefault(prev.upper(), r)
    return _HGNC


# --------------------------------------------------------------------------
# KG (numpy)
# --------------------------------------------------------------------------


class KG:
    def __init__(self, root: Path = KG_DIR) -> None:
        raise NotImplementedError('available on the TargetMind platform')

    def scores(self, model: str, disease_row: int):
        raise NotImplementedError('available on the TargetMind platform')

    def resolve(self, disease_id: str | list[str]) -> list[int]:
        raise NotImplementedError('available on the TargetMind platform')

    def locate(self, disease_ids: str | list[str]) -> tuple[list[int], str]:
        """PrimeKG rows of a disease given one or more ids -> (rows, how matched)."""
        raise NotImplementedError('available on the TargetMind platform')

    def _prefer_single(self, rows: set[int]) -> int | None:
        """One row, preferring a single MONDO term over a grouped node."""
        raise NotImplementedError('available on the TargetMind platform')

    def _by_name(self, name: str) -> int | None:
        raise NotImplementedError('available on the TargetMind platform')

    def _by_xrefs(self, xrefs: list[str]) -> int | None:
        """Weighted vote of the cross-reference ontologies (only ids that map to"""
        raise NotImplementedError('available on the TargetMind platform')

    def known_edges(
        self, disease_id: str | list[str], lookup: bool = False
    ) -> int | None:
        """Known disease-gene edges. Without `lookup` only MONDO ids are matched:"""
        raise NotImplementedError('available on the TargetMind platform')

    def candidate_mask(self, hub_quantile: float):
        raise NotImplementedError('available on the TargetMind platform')

    def rank(
        self,
        target_id: str,
        anchors: list[str],
        model_top_k: int = 200,
        hub_quantile: float = 0.99,
        target_ids: list[str] | None = None,
    ) -> tuple[list[dict], dict]:
        """Ensemble ranking over the target disease and its anchors."""
        raise NotImplementedError('available on the TargetMind platform')

    def selftest(self) -> list[str]:
        raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

POOL_COLUMNS = [
    'gene',
    'prior_rank',
    'entry',
    'line_genetic_tool',
    'genetic_basis',
    'genetic_best',
    'genetic_best_source',
    'rare_variant',
    'gwas_studies',
    'gwas_best_p',
    'gwas_pmids',
    'ot_expression',
    'ot_literature',
    'kg_rank',
    'kg_score',
    'kg_models',
    'kg_anchors',
]


def cmd_pool(args: argparse.Namespace) -> int:
    if not use_disease_id(args):
        return 2
    with Heartbeat('tm-discover pool'):
        rc = _pool(args)
    if rc == 0:
        meta = json.loads(Path(str(args.out) + '.meta.json').read_text())
        notify_chief(DISCOVERY_REMINDER.format(n=meta['pool_size']))
    return rc


def resolve_context_names(context: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    """Fill missing ids from names (Open Targets search); returns name -> id/problem."""
    raise NotImplementedError('available on the TargetMind platform')


def write_resolved_context(
    context: dict[str, list[dict[str, str]]], path: Path
) -> Path:
    """<context>_resolved.csv with every id filled in; tm-novelty --context reads it."""
    out = path.with_name(path.stem + '_resolved.csv')
    with out.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['kind', 'id', 'name', 'reason', 'source'])
        for kind, rows in context.items():
            for r in rows:
                w.writerow(
                    [
                        kind,
                        r.get('id', ''),
                        r.get('name', ''),
                        r.get('reason', ''),
                        r.get('source', ''),
                    ]
                )
    return out


def _pool(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


MATRIX_COLUMNS = [
    'rank',
    'gene',
    'evidence_lines',
    'line_omics',
    'line_genetic',
    'line_mechanism',
    'proposed_by',
    'omics_direction',
    'omics_source',
    'genetic_basis',
    'genetic_source',
    'mechanism_effect',
    'mechanism_source',
    'kg_rank',
    'kg_models',
    'ot_literature',
    'rank_score',
    'in_pool',
]


def watch_list(
    matrix: dict[str, dict[str, str]], novelty: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Empty shortlist: the screened novel/emerging genes with one evidence line."""
    raise NotImplementedError('available on the TargetMind platform')


def cmd_merge(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


PREPARE_COLUMNS = [
    'suggest',
    'relation',
    'id',
    'name',
    'similarity',
    'genetic_targets',
    'clinical_drugs',
    'all_targets',
    'primekg_edges',
]


# Self-sufficiency (D20): related diseases are used only when the disease's own
# evidence is too thin. Genetics: protein-coding genes with the disease's OWN Open
# Targets genetic score >= 0.5 — the genetic-line rule itself. Calibrated on 8
# diseases (2026-11-02): renal fibrosis 0, MASH 1, systemic sclerosis 18, IPF 24
# need proxies; psoriasis 133, colorectal cancer 160, Alzheimer 174, T2D 731 do not.
GENETIC_SELF_MIN = 50
KG_SELF_MIN_EDGES = 10
_OT_GENETIC_TOP = (
    'query($id:String!){ disease(efoId:$id){ associatedTargets('
    'orderByScore:"genetic_association", page:{index:0,size:500}){ '
    'rows{ target{ biotype } datatypeScores{ id score } } } } }'
)


def own_genetic_genes(disease_id: str, min_score: float = 0.5) -> tuple[int, bool]:
    """Protein-coding targets with the disease's own genetic score >= min_score, from"""
    raise NotImplementedError('available on the TargetMind platform')


def assess_context(
    genetic: int | None, capped: bool, kg_edges: int | None, kg_match: str
) -> dict:
    """Which related-disease kinds disease_context.csv needs (D20). Unknown values"""
    raise NotImplementedError('available on the TargetMind platform')


def assessment_lines(a: dict) -> list[str]:
    raise NotImplementedError('available on the TargetMind platform')


def suggest_kinds(row: dict, need_proxy: bool = True, need_anchor: bool = True) -> str:
    """Hints only; the Chief Scientist decides."""
    raise NotImplementedError('available on the TargetMind platform')


def cmd_prepare(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


def _safe_metrics(disease_id: str) -> dict:
    try:
        return opentargets_metrics(disease_id)
    except Exception as e:  # noqa: BLE001
        print(f'tm-discover: WARNING metrics for {disease_id}: {e}', file=sys.stderr)
        return {'genetic_targets': '', 'clinical_drugs': '', 'all_targets': ''}


SHORTLIST_COLUMNS = [
    'rank',
    'check',
    'gene',
    'tier',
    'evidence_lines',
    'proposed_by',
    'rationale',
    'pubmed_cooccurrence',
]


def cmd_shortlist(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


_OT_CREDIBLE = (
    'query($id:String!,$ens:[String!]!,$cursor:String){ disease(efoId:$id){ id name '
    'evidences(ensemblIds:$ens, datasourceIds:["gwas_credible_sets"], size:500, cursor:$cursor){ '
    'cursor rows{ target{ approvedSymbol } score credibleSet{ studyId '
    'study{ traitFromSource pubmedId nSamples } variant{ rsIds } pValueMantissa pValueExponent beta '
    'l2GPredictions(page:{index:0,size:1}){ rows{ score target{ approvedSymbol } } } } } } } }'
)
GENETICS_EVIDENCE_COLUMNS = [
    'gene',
    'source',
    'disease_or_trait',
    'study',
    'pmid',
    'variant',
    'p',
    'beta_or_or',
    'score',
    'l2g_top_gene',
    'detail',
]


def write_genetics_evidence(
    genes: list[str], diseases: list[str], path: Path, meta: dict
) -> int:
    """Long table the genetics expert reviews instead of fetching: Open Targets"""
    raise NotImplementedError('available on the TargetMind platform')


def cmd_gwas(args: argparse.Namespace) -> int:
    genes = [g for g in re.split(r'[,\s]+', args.genes) if g]
    if args.genes_file:
        genes += [r.get('gene', '') for r in read_csv(Path(args.genes_file))]
    rows = gwas_gene_rows(genes, args.limit)
    if args.trait:
        t = args.trait.lower()
        rows = [
            r
            for r in rows
            if t in r['trait']
            or t in (r['reported_trait'] or '').lower()
            or t == r['trait_id'].lower()
        ]
    w = csv.DictWriter(
        sys.stdout if not args.out else open(args.out, 'w', newline=''),
        fieldnames=list(rows[0]) if rows else ['gene'],
    )
    w.writeheader()
    w.writerows(rows)
    print(
        f'# {len(rows)} associations (GWAS Catalog snapshot {gwas_release()})',
        file=sys.stderr,
    )
    return 0


# --------------------------------------------------------------------------
# GEO (validated downloads)
# --------------------------------------------------------------------------

GEO_FTP = 'https://ftp.ncbi.nlm.nih.gov/geo'
GEO_QUERY = 'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi'
GEO_COUNTS = 'https://www.ncbi.nlm.nih.gov/geo/download/'
_GZIP_MAGIC = b'\x1f\x8b'
_SAMPLE_KEYS = ('geo_accession', 'title', 'source_name', 'characteristics')


def geo_stub(acc: str) -> str:
    """GSE104954 -> GSE104nnn; GPL571 -> GPLnnn (NCBI FTP directory layout)."""
    m = re.fullmatch(r'(GSE|GPL|GSM)(\d+)', acc.upper())
    if not m:
        raise ValueError(f'not a GEO accession: {acc}')
    prefix, num = m.groups()
    return prefix + (num[:-3] if len(num) > 3 else '') + 'nnn'


def fetch_validated(url: str, dest: Path, gzip_expected: bool, tries: int = 5) -> Path:
    """Download and check the content: NCBI sometimes answers 200 with an empty
    body or an HTML error page. Retries with backoff; raises if every try is bad.
    An existing non-empty file is reused (no second download)."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = ''
    for attempt in range(tries):
        data = b''
        try:
            data = _open(
                urllib.request.Request(url, headers={'User-Agent': 'tm-discover'}),
                timeout=600,
            )
        except RequestFailed as e:
            last = str(e)
            if 'HTTP 404' in last:
                break
        if data and (not gzip_expected or data[:2] == _GZIP_MAGIC):
            tmp = dest.with_suffix(dest.suffix + '.part')
            tmp.write_bytes(data)
            tmp.replace(dest)
            return dest
        if data or not last:
            last = (
                'empty response' if not data else 'not a gzip file (HTML error page?)'
            )
        time.sleep(min(60.0, 3.0 * 2**attempt) + random.uniform(0, 1))
    raise RequestFailed(f'{url}: {last}')


def geo_matrix_files(gse: str, tries: int = 4) -> list[str]:
    """Real series-matrix file names (multi-platform series have one per GPL).
    The NCBI listing itself is sometimes returned truncated, so an empty list
    is retried before concluding there is no matrix."""
    url = f'{GEO_FTP}/series/{geo_stub(gse)}/{gse}/matrix/'
    pattern = r'(' + re.escape(gse) + r'[^"/<>]*_series_matrix\.txt\.gz)'
    for attempt in range(tries):
        html = _open(urllib.request.Request(url)).decode(errors='replace')
        names = sorted(set(re.findall(pattern, html)))
        if names:
            return names
        time.sleep(3.0 * 2**attempt + random.uniform(0, 1))
    return []


def parse_series_matrix(
    path: Path,
) -> tuple[dict[str, list[str]], list[str], list[list[str]]]:
    """(sample metadata {field: values}, column names, data rows) of a series matrix."""
    import gzip

    meta: dict[str, list[str]] = {}
    header: list[str] = []
    rows: list[list[str]] = []
    in_table = False
    with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.startswith('!series_matrix_table_begin'):
                in_table = True
                continue
            if line.startswith('!series_matrix_table_end'):
                break
            if in_table:
                cells = [c.strip('"') for c in line.split('\t')]
                if not header:
                    header = cells
                else:
                    rows.append(cells)
            elif line.startswith('!Sample_'):
                key, *vals = line.split('\t')
                key = key[len('!Sample_') :]
                n = sum(1 for k in meta if k == key or k.startswith(key + '.'))
                meta[key if n == 0 else f'{key}.{n}'] = [v.strip('"') for v in vals]
    return meta, header, rows


def platform_symbols(gpl: str, raw: Path) -> dict[str, str]:
    """Probe -> gene symbol from the GEO annotation file, else the platform table."""
    import gzip

    try:
        url = f'{GEO_FTP}/platforms/{geo_stub(gpl)}/{gpl}/annot/{gpl}.annot.gz'
        path = fetch_validated(url, raw / f'{gpl}.annot.gz', True)
        with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as fh:
            lines = fh.read().splitlines()
    except RequestFailed:
        path = raw / f'{gpl}_table.txt'
        if not path.exists():
            url = f'{GEO_QUERY}?acc={gpl}&targ=self&form=text&view=data'
            text = _open(urllib.request.Request(url), timeout=600).decode(
                errors='replace'
            )
            if '!platform_table_begin' not in text:
                raise RequestFailed(f'{gpl}: no platform table') from None
            path.write_text(text)
        lines = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith('ID\t'))
    cols = [c.lower() for c in lines[start].split('\t')]
    sym_col = next(
        (
            i
            for i, c in enumerate(cols)
            if c in ('gene symbol', 'symbol', 'gene_symbol')
        ),
        None,
    )
    entrez_col = next(
        (
            i
            for i, c in enumerate(cols)
            if c
            in ('entrez_gene_id', 'gene id', 'gene_id', 'geneid', 'entrez_id', 'entrez')
        ),
        None,
    )
    by_entrez: dict[str, str] = {}
    if sym_col is None:
        if entrez_col is None:
            raise RequestFailed(f'{gpl}: no gene-symbol or Entrez column ({cols[:6]})')
        # Entrez ids only (e.g. Brainarray CDFs): symbols from the local HGNC set
        by_entrez = {
            r['entrez_id']: r['symbol']
            for r in hgnc_symbols().values()
            if r.get('entrez_id')
        }
    out = {}
    for ln in lines[start + 1 :]:
        if ln.startswith('!'):
            break
        cells = ln.split('\t')
        if sym_col is not None:
            if len(cells) > sym_col and cells[sym_col]:
                out[cells[0]] = cells[sym_col].split('///')[0].strip().strip('"')
        elif entrez_col is not None and len(cells) > entrez_col:
            entrez = cells[entrez_col].split('///')[0].strip().strip('"')
            if by_entrez.get(entrez):
                out[cells[0]] = by_entrez[entrez]
    return out


def write_sample_sheet(meta: dict[str, list[str]], path: Path) -> int:
    keys = [k for k in meta if k.startswith(_SAMPLE_KEYS)]
    n = len(meta.get('geo_accession', []))
    with path.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(keys)
        for i in range(n):
            w.writerow([meta[k][i] if i < len(meta[k]) else '' for k in keys])
    return n


def write_gene_matrix(
    header: list[str], rows: list[list[str]], symbols: dict[str, str], path: Path
) -> dict:
    """gene x sample matrix: probes collapsed by highest mean; log2(x+1) applied
    when the values look linear (max > 50), as in geo-deg.md."""
    import gzip
    import statistics

    best: dict[str, tuple[float, list[float]]] = {}
    top = 0.0
    for r in rows:
        sym = symbols.get(r[0], '')
        if not sym:
            continue
        try:
            vals = [float(v) for v in r[1:]]
        except ValueError:
            continue
        top = max(top, *vals) if vals else top
        mean = statistics.fmean(vals) if vals else 0.0
        if sym not in best or mean > best[sym][0]:
            best[sym] = (mean, vals)
    linear = top > 50
    with gzip.open(path, 'wt', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['gene', *header[1:]])
        for sym, (_, vals) in sorted(best.items()):
            if linear:
                vals = [math.log2(max(v, 0.0) + 1) for v in vals]
            w.writerow([sym, *(f'{v:.4f}' for v in vals)])
    return {'genes': len(best), 'log2_applied': linear}


def write_count_matrix(counts: Path, path: Path) -> int:
    """NCBI raw-count table (GeneID rows) -> symbol x sample counts for DESeq2.
    Uses the local HGNC Entrez mapping (the NCBI annotation download sits
    behind a CAPTCHA)."""
    import gzip

    by_entrez = {
        r['entrez_id']: r['symbol']
        for r in hgnc_symbols().values()
        if r.get('entrez_id')
    }
    n = 0
    with gzip.open(counts, 'rt') as src, gzip.open(path, 'wt', newline='') as dst:
        reader = csv.reader(src, delimiter='\t')
        w = csv.writer(dst)
        header = next(reader)
        w.writerow(['gene', *header[1:]])
        seen = set()
        for row in reader:
            sym = by_entrez.get(row[0])
            if sym and sym not in seen:
                seen.add(sym)
                w.writerow([sym, *row[1:]])
                n += 1
    return n


# --------------------------------------------------------------------------
# Shared GEO cache (host directory mounted read-write into every sandbox)
# --------------------------------------------------------------------------

CACHE_DIR = Path(os.environ.get('TM_CACHE_DIR', '/opt/targetmind/cache'))
GEO_CACHE_VERSION = 'geo-cache-1'


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open('rb') as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


class GeoCache:
    """geo/series/<GSE>/{source,processed}/ + manifest.json, geo/platforms/<GPL>/,
    geo/search/<hash>.json under the shared cache. Writes go to `.part` files that
    are renamed into place under a per-accession file lock, so parallel sandboxes
    download a series once. Every file is recorded with its sha256 and checked on
    read; a mismatch (corrupt or tampered file) means a fresh download. The cache
    holds public data only. Without a writable cache everything stays in the task
    folder (`fallback`), with a warning."""

    def __init__(self, root: Path = CACHE_DIR, fallback: Path | None = None) -> None:
        self.root = root / 'geo'
        self.fallback = fallback
        self.enabled = False
        self.warning = ''
        self._held: set[tuple[str, str]] = set()
        self._write_lock = threading.Lock()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / f'.probe-{os.getpid()}'
            probe.write_text('x')
            probe.unlink()
            self.enabled = True
        except OSError as e:
            self.warning = f'shared GEO cache unavailable ({e}); files stay in the task folder only'

    def dir(self, kind: str, acc: str) -> Path:
        if not self.enabled:
            assert self.fallback is not None
            return self.fallback / acc
        return self.root / kind / acc

    def lock(self, kind: str, acc: str):
        import contextlib
        import fcntl

        key = (kind, acc)

        @contextlib.contextmanager
        def held():
            # Re-entrant within this process (flock on a second descriptor of the
            # same file would block on itself), exclusive across processes.
            if not self.enabled or key in self._held:
                yield
                return
            d = self.dir(kind, acc)
            d.mkdir(parents=True, exist_ok=True)
            with open(d / '.lock', 'w') as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                self._held.add(key)
                try:
                    yield
                finally:
                    self._held.discard(key)
                    fcntl.flock(fh, fcntl.LOCK_UN)

        return held()

    def _manifest(self, kind: str, acc: str) -> tuple[Path, dict]:
        path = self.dir(kind, acc) / 'manifest.json'
        try:
            return path, json.loads(path.read_text())
        except (OSError, ValueError):
            return path, {'accession': acc, 'files': {}}

    def valid(self, kind: str, acc: str, rel: str) -> Path | None:
        """The cached file if present and its sha256 matches the manifest."""
        path = self.dir(kind, acc) / rel
        _, man = self._manifest(kind, acc)
        entry = man['files'].get(rel)
        if not path.exists() or not entry:
            return None
        if _sha256(path) != entry['sha256']:
            print(
                f'tm-discover: WARNING {acc}/{rel} fails its checksum; downloading again',
                file=sys.stderr,
            )
            path.unlink()
            return None
        os.utime(path)  # access time for prune_cache.py
        return path

    def record(self, kind: str, acc: str, rel: str, url: str = '') -> Path:
        path = self.dir(kind, acc) / rel
        digest = _sha256(path)
        with self._write_lock:  # threads of one process share the manifest
            return self._record(kind, acc, rel, url, path, digest)

    def _record(
        self, kind: str, acc: str, rel: str, url: str, path: Path, digest: str
    ) -> Path:
        mpath, man = self._manifest(kind, acc)
        man['files'][rel] = {
            'sha256': digest,
            'bytes': path.stat().st_size,
            'url': url,
            'fetched_utc': dt.datetime.now(dt.timezone.utc).isoformat(
                timespec='seconds'
            ),
            'tool': GEO_CACHE_VERSION,
        }
        tmp = mpath.with_suffix(f'.json.part{os.getpid()}-{threading.get_ident()}')
        tmp.write_text(json.dumps(man, indent=1))
        tmp.replace(mpath)
        return path

    def fetch(
        self, kind: str, acc: str, rel: str, url: str, gzip_expected: bool
    ) -> Path:
        path = self.valid(kind, acc, rel)
        if path:
            return path
        dest = self.dir(kind, acc) / rel
        if dest.exists():
            dest.unlink()  # unrecorded leftover
        fetch_validated(url, dest, gzip_expected)
        return self.record(kind, acc, rel, url)

    def search_get(self, key: str, max_age_days: int = 7) -> dict | None:
        path = (
            (self.root if self.enabled else (self.fallback or Path('.')))
            / 'search'
            / f'{key}.json'
        )
        try:
            if time.time() - path.stat().st_mtime < max_age_days * 86400:
                return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        return None

    def search_put(self, key: str, data: dict) -> None:
        base = self.root if self.enabled else (self.fallback or Path('.'))
        path = base / 'search' / f'{key}.json'
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f'.part{os.getpid()}')
            tmp.write_text(json.dumps(data))
            tmp.replace(path)
        except OSError:
            pass


def cached_platform_symbols(cache: GeoCache, gpl: str) -> dict[str, str]:
    with cache.lock('platforms', gpl):
        raw = cache.dir('platforms', gpl)
        raw.mkdir(parents=True, exist_ok=True)
        annot = f'{gpl}.annot.gz'
        if cache.enabled and not cache.valid('platforms', gpl, annot):
            for stale in (raw / annot, raw / f'{gpl}_table.txt'):
                if stale.exists() and not cache.valid('platforms', gpl, stale.name):
                    stale.unlink()
        symbols = platform_symbols(gpl, raw)
        if cache.enabled:
            for name in (annot, f'{gpl}_table.txt'):
                if (raw / name).exists() and not cache.valid('platforms', gpl, name):
                    cache.record('platforms', gpl, name)
        return symbols


def cmd_geo(args: argparse.Namespace) -> int:
    """Validated GEO downloads -> gene x sample matrices + sample sheets. Raw and
    processed files live in the shared cache (one download per series across
    conversations); the task folder gets copies of the processed files."""
    import shutil

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    cache = GeoCache(fallback=outdir / 'raw')
    if cache.warning:
        print(f'tm-discover: WARNING {cache.warning}', file=sys.stderr)
    summary: dict[str, dict] = {}
    for gse in [a.strip().upper() for a in re.split(r'[,\s]+', args.gse) if a.strip()]:
        try:
            with cache.lock('series', gse):
                base = cache.dir('series', gse)
                (base / 'source').mkdir(parents=True, exist_ok=True)
                (base / 'processed').mkdir(parents=True, exist_ok=True)
                _, man = cache._manifest('series', gse)
                done = man.get('processed') if cache.enabled else None
                if done and all(
                    cache.valid('series', gse, f'processed/{f}') for f in done['files']
                ):
                    entries = done['series']
                    print(f'{gse}: from the shared cache (no download)', flush=True)
                else:
                    entries = geo_series_to_cache(cache, gse, base)
                for name, info in entries.items():
                    for f in info['files']:
                        shutil.copyfile(base / 'processed' / f, outdir / f)
                    summary[name] = {k: v for k, v in info.items() if k != 'files'}
                    summary[name]['cached'] = cache.enabled
                    print(f'{name}: {summary[name]}', flush=True)
        except Exception as e:  # noqa: BLE001
            summary[gse] = {'error': str(e)}
            print(f'tm-discover: WARNING {gse}: {e}', file=sys.stderr)
    (outdir / 'geo_fetch.json').write_text(json.dumps(summary, indent=2))
    print(
        f'wrote {outdir}/<series>_samples.csv, <series>_expr_genes.csv.gz, geo_fetch.json'
    )
    return 0 if all('error' not in v for v in summary.values()) else 1


def geo_series_to_cache(cache: GeoCache, gse: str, base: Path) -> dict[str, dict]:
    """Download and process one series into <base>/{source,processed}/ (caller
    holds the lock); records every file in the manifest."""
    try:
        files = geo_matrix_files(gse)
    except RequestFailed as e:
        # ftp.ncbi.nlm.nih.gov answers 403 to tool requests at times; the other
        # NCBI endpoints and EBI still work.
        print(
            f'{gse}: NCBI FTP unavailable ({str(e)[-60:]}); trying the fallbacks',
            flush=True,
        )
        return geo_series_fallback(cache, gse, base, str(e))
    if not files:
        raise RequestFailed('no series matrix on the NCBI FTP site')
    entries: dict[str, dict] = {}
    for fname in files:
        url = f'{GEO_FTP}/series/{geo_stub(gse)}/{gse}/matrix/{fname}'
        src = cache.fetch('series', gse, f'source/{fname}', url, True)
        meta, header, rows = parse_series_matrix(src)
        name = fname.replace('_series_matrix.txt.gz', '')
        gpl = (meta.get('platform_id') or [''])[0]
        proc = base / 'processed'
        info: dict = {
            'platform': gpl,
            'samples': write_sample_sheet(meta, proc / f'{name}_samples.csv'),
            'files': [f'{name}_samples.csv'],
        }
        if len(rows) > 100:
            info['type'] = 'array'
            info.update(
                write_gene_matrix(
                    header,
                    rows,
                    cached_platform_symbols(cache, gpl),
                    proc / f'{name}_expr_genes.csv.gz',
                )
            )
            info['files'].append(f'{name}_expr_genes.csv.gz')
        else:
            counts_name = f'{gse}_raw_counts_GRCh38.p13_NCBI.tsv.gz'
            counts = cache.fetch(
                'series',
                gse,
                f'source/{counts_name}',
                f'{GEO_COUNTS}?type=rnaseq_counts&acc={gse}&format=file&file={counts_name}',
                True,
            )
            info.update(
                type='RNA-seq raw counts (NCBI-processed; Entrez ids mapped with local HGNC)',
                genes=write_count_matrix(counts, proc / f'{name}_counts_genes.csv.gz'),
            )
            info['files'].append(f'{name}_counts_genes.csv.gz')
        entries[name] = info
    return _record_processed(cache, gse, entries)


EBI_ATLAS = 'https://ftp.ebi.ac.uk/pub/databases/microarray/data/atlas/experiments'
EBI_BIOSTUDIES = 'https://www.ebi.ac.uk/biostudies/api/v1/studies'


def brief_sample_meta(samples: list[dict]) -> dict[str, list[str]]:
    """Sample records (acc.cgi brief) in the series-matrix metadata shape."""
    meta: dict[str, list[str]] = {
        'geo_accession': [x['gsm'] for x in samples],
        'title': [x['title'] for x in samples],
        'source_name_ch1': [x['source'] for x in samples],
    }
    keys = list(dict.fromkeys(k for x in samples for k in x['ch']))
    for i, k in enumerate(keys):
        meta['characteristics_ch1' + (f'.{i}' if i else '')] = [
            f'{k}: {x["ch"].get(k, "")}' for x in samples
        ]
    return meta


def _get_text(url: str, timeout: int = 300) -> str:
    return _open(
        urllib.request.Request(url, headers={'User-Agent': 'tm-discover'}),
        timeout=timeout,
    ).decode(errors='replace')


def geo_series_fallback(
    cache: GeoCache, gse: str, base: Path, why: str
) -> dict[str, dict]:
    """Series without the NCBI FTP: RNA-seq -> NCBI-computed counts; arrays ->"""
    raise NotImplementedError('available on the TargetMind platform')


def _record_processed(
    cache: GeoCache, gse: str, entries: dict[str, dict]
) -> dict[str, dict]:
    if cache.enabled:
        for info in entries.values():
            for f in info['files']:
                cache.record('series', gse, f'processed/{f}')
        mpath, man = cache._manifest('series', gse)
        man['processed'] = {
            'series': entries,
            'files': [f for i in entries.values() for f in i['files']],
        }
        mpath.write_text(json.dumps(man, indent=1))
    return entries


# --------------------------------------------------------------------------
# geo-search: candidate datasets for THIS disease, with groups and tissue
# --------------------------------------------------------------------------

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
GEO_CANDIDATE_COLUMNS = [
    'gse',
    'relation',
    'recommendation',
    'reason',
    'data',
    'technology',
    'title',
    'platform',
    'n_samples',
    'tissue',
    'compartment',
    'group_field',
    'case_label',
    'n_case',
    'control_label',
    'n_control',
    'groups_clear',
    'pmid',
    'date',
    'matched_terms',
]
_CONTROL_WORDS = re.compile(
    r'\b(control|controls|normal|healthy|non[- ]?disease[d]?|unaffected|living donor|'
    r'donor|tumou?r nephrectomy|nephrectomy|ctrl|sham|baseline|non[- ]?fibrotic|'
    r'reference)\b',
    re.IGNORECASE,
)
_SINGLE_CELL = re.compile(
    r'single[- ]?(cell|nucleus|nuclei)|scrna|snrna|10x|drop-?seq', re.I
)
_IN_VITRO = re.compile(r'(?!)')  # redacted
_NOT_EXPRESSION = re.compile(r'(?!)')  # redacted


# NCBI E-utilities go through the platform relay when the sandbox has one
# (TM_EUTILS_URL): one global rate limit for all users, the platform API key kept
# on the host, and a shared cache. Without it (or if it is unreachable) calls go
# to NCBI directly at 3 requests/s.
EUTILS_RELAY = os.environ.get('TM_EUTILS_URL', '').rstrip('/')
_relay_state = {'down': False, 'relay': 0, 'direct': 0, 'cache_hits': 0}


def _relay_open(tool: str, data: bytes, timeout: int) -> bytes | None:
    """POST through the relay; None when it is unusable (caller falls back)."""
    key = os.environ.get('TM_SESSION_API_KEY')
    if not EUTILS_RELAY or not key or _relay_state['down']:
        return None
    req = urllib.request.Request(
        f'{EUTILS_RELAY}/{tool}.fcgi',
        data=data,
        headers={
            'X-Session-API-Key': key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'tm-discover',
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _relay_state['relay'] += 1
                if resp.headers.get('X-TM-Cache') == 'hit':
                    _relay_state['cache_hits'] += 1
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode(errors='replace')
            if e.headers and e.headers.get('X-TM-Upstream') == 'error':
                # The relay reached NCBI and already retried: NCBI itself is
                # failing, so neither retrying nor going direct would help.
                raise RequestFailed(f'NCBI {tool} unavailable: {body}') from e
            if e.code in (400, 413):  # a bad query fails the same way upstream
                raise RequestFailed(f'E-utilities {tool}: HTTP {e.code} {body}') from e
            if e.code in (401, 403, 404):  # relay not available to this sandbox
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 0:
                break  # relay unreachable: do not wait, use NCBI directly
        time.sleep(2.0 * 2**attempt + random.uniform(0, 1))
    _relay_state['down'] = True
    return None


_NCBI_XML_ERROR = re.compile(
    rb'<(?:eSearchResult|eFetchResult|eSummaryResult|eLinkResult)\b.{0,2000}?'
    rb'<ERROR>(.*?)</ERROR>',
    re.S,
)


def ncbi_error(body: bytes) -> str | None:
    """NCBI's error message when a response is an error, else None.

    E-utilities often report failures (e.g. "Search Backend failed ... temporarily
    unavailable") with HTTP 200 and an ERROR field; read naively that looks like
    zero hits.
    """
    head = body[:4096].lstrip()
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
    m = _NCBI_XML_ERROR.search(head)
    return m.group(1).decode(errors='replace').strip() if m else None


def eutils_raw(tool: str, params: dict, timeout: int = TIMEOUT) -> bytes:
    """One E-utilities call (relay first, NCBI directly as a fallback).

    Raises RequestFailed when NCBI answers with an error, so a failed search is
    never mistaken for an empty one.
    """
    p = {k: v for k, v in params.items() if v is not None}
    data = urllib.parse.urlencode(p, doseq=True).encode()
    body = _relay_open(tool, data, timeout)
    if body is None:
        direct = dict(p, tool='tm-discover')
        if os.environ.get('NCBI_API_KEY'):
            direct['api_key'] = os.environ['NCBI_API_KEY']
        _relay_state['direct'] += 1
        body = _open(
            urllib.request.Request(
                f'{EUTILS}/{tool}.fcgi',
                data=urllib.parse.urlencode(direct, doseq=True).encode(),
                headers={'User-Agent': 'tm-discover'},
            ),
            timeout=timeout,
        )
    error = ncbi_error(body)
    if error:
        raise RequestFailed(f'NCBI {tool}: {error[:200]}')
    return body


def eutils_json(tool: str, params: dict) -> dict:
    return json.loads(eutils_raw(tool, dict(params, retmode='json')))


def geo_query(terms: list[str]) -> str:
    phrase = ' OR '.join(f'"{t}"[All Fields]' for t in terms if t.strip())
    return f'({phrase}) AND "Homo sapiens"[Organism] AND gse[Entry Type]'


def parse_gsm_brief(text: str) -> list[dict[str, Any]]:
    """GEO `targ=gsm&form=text&view=brief` -> one dict per sample (title, source,
    characteristics {key: value})."""
    samples: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith('^SAMPLE'):
            cur = {
                'gsm': line.split('=', 1)[1].strip(),
                'title': '',
                'source': '',
                'ch': {},
            }
            samples.append(cur)
        elif cur is not None and ' = ' in line:
            key, val = line.split(' = ', 1)
            if key == '!Sample_title':
                cur['title'] = val
            elif key == '!Sample_source_name_ch1':
                cur['source'] = val
            elif key == '!Sample_characteristics_ch1':
                k, sep, v = val.partition(':')
                cur['ch'][(k.strip().lower() if sep else 'value')] = (
                    v if sep else k
                ).strip()
            elif key == '!Sample_platform_id':
                cur['platform'] = val.strip()
            elif key == '!Sample_description' and not cur.get('description'):
                cur['description'] = val
    return samples


def classify_groups(samples: list[dict], disease_terms: list[str]) -> dict:
    """Best grouping field: a characteristic (or the source/title) whose values"""
    raise NotImplementedError('available on the TargetMind platform')


def assess_dataset(
    summary: dict,
    samples: list[dict],
    disease_terms: list[str],
    tissue_terms: list[str],
    relation: str,
) -> dict:
    """One geo_candidates.csv row: technology, tissue match, groups, recommendation."""
    raise NotImplementedError('available on the TargetMind platform')


def prefilter_reason(summary: dict) -> str:
    """Why a series can be ruled out from its summary alone (no sample download)."""
    raise NotImplementedError('available on the TargetMind platform')


def geo_data_source(cache: GeoCache, gse: str, tech: str) -> str:
    """Where `tm-discover geo` can get processed data for a series, '' if nowhere.
    Checked for candidate datasets only, so experts never pick a series whose data
    cannot be fetched."""
    try:
        if geo_matrix_files(gse, tries=1):
            return 'NCBI series matrix'
    except RequestFailed:
        pass
    if tech in ('rnaseq', 'single-cell'):
        name = f'{gse}_raw_counts_GRCh38.p13_NCBI.tsv.gz'
        try:
            cache.fetch(
                'series',
                gse,
                f'source/{name}',
                f'{GEO_COUNTS}?type=rnaseq_counts&acc={gse}&format=file&file={name}',
                True,
            )
            return 'NCBI-computed counts'
        except RequestFailed:
            return ''
    acc = 'E-GEOD-' + gse[3:]
    try:
        if '-normalized-expressions.tsv' in _get_text(f'{EBI_ATLAS}/{acc}/', 60):
            return 'EBI Expression Atlas'
    except RequestFailed:
        pass
    try:
        if json.loads(_get_text(f'{EBI_BIOSTUDIES}/{acc}/info', 60) or '{}').get(
            'httpLink'
        ):
            return 'EBI BioStudies'
    except (RequestFailed, ValueError):
        pass
    return ''


def geo_search_terms(terms: list[str], cache: GeoCache, limit: int) -> list[dict]:
    import hashlib

    q = geo_query(terms)
    key = hashlib.sha256(f'{q}|{limit}'.encode()).hexdigest()[:16]
    hit = cache.search_get(key)
    if hit is not None:
        return hit['summaries']
    ids = eutils_json('esearch', {'db': 'gds', 'term': q, 'retmax': limit})[
        'esearchresult'
    ]['idlist']
    summaries: list[dict] = []
    for i in range(0, len(ids), 100):
        res = eutils_json('esummary', {'db': 'gds', 'id': ','.join(ids[i : i + 100])})[
            'result'
        ]
        summaries += [res[u] for u in res.get('uids', [])]
    cache.search_put(key, {'query': q, 'summaries': summaries})
    return summaries


def gsm_brief(cache: GeoCache, gse: str) -> str:
    with cache.lock('series', gse):
        path = cache.valid('series', gse, 'source/samples_brief.txt')
        if path:
            return path.read_text()
        url = f'{GEO_QUERY}?acc={gse}&targ=gsm&form=text&view=brief'
        text = _open(
            urllib.request.Request(url, headers={'User-Agent': 'tm-discover'}),
            timeout=300,
        ).decode(errors='replace')
        if '^SAMPLE' not in text:
            raise RequestFailed(f'{gse}: no sample records')
        dest = cache.dir('series', gse) / 'source'
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'samples_brief.txt').write_text(text)
        if cache.enabled:
            cache.record('series', gse, 'source/samples_brief.txt', url)
        return text


def cmd_geo_search(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# HPA: cell-type and tissue expression (local snapshot)
# --------------------------------------------------------------------------


def hpa_db() -> sqlite3.Connection | None:
    path = data_path('hpa', 'hpa.sqlite')
    if not path.exists():
        return None
    return sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)


def hpa_gene_profile(db: sqlite3.Connection, gene: str, top: int = 3) -> dict:
    """Top cell types / tissues of a gene and a specificity ratio (top / second)."""
    out: dict[str, Any] = {'gene': gene}
    for table, col in (('cell', 'cell_type'), ('tissue', 'tissue')):
        rows = db.execute(
            f'SELECT {col}, value FROM {table} WHERE symbol = ? ORDER BY value DESC',
            (gene.upper(),),
        ).fetchall()
        out[f'top_{table}'] = '; '.join(f'{n} {v:g}' for n, v in rows[:top])
        out[f'{table}_specificity'] = (
            round(rows[0][1] / max(rows[1][1], 1.0), 2) if len(rows) > 1 else ''
        )
    return out


def hpa_markers(db: sqlite3.Connection, cell_type: str, top: int) -> list[dict]:
    """Marker genes of a cell type: highest enrichment over the best other type
    (HPA single-cell nCPM), expressed >= 10 nCPM."""
    rows = db.execute(
        'SELECT c.symbol, c.value, (SELECT max(o.value) FROM cell o WHERE o.symbol = c.symbol '
        'AND o.cell_type != c.cell_type) FROM cell c WHERE c.cell_type = ? AND c.value >= 10',
        (cell_type,),
    ).fetchall()
    scored = sorted(
        (
            {'gene': g, 'ncpm': v, 'enrichment': round(v / max(o or 0.0, 1.0), 2)}
            for g, v, o in rows
        ),
        key=lambda r: -r['enrichment'],
    )
    return scored[:top]


def cmd_hpa(args: argparse.Namespace) -> int:
    db = hpa_db()
    if db is None:
        print('tm-discover: ERROR HPA snapshot not mounted (ref/hpa)', file=sys.stderr)
        return 2
    version = data_path('hpa').resolve().name
    if args.list_cell_types:
        for (name,) in db.execute('SELECT DISTINCT cell_type FROM cell ORDER BY 1'):
            print(name)
        return 0
    rows: list[dict] = []
    if args.markers:
        known = {n for (n,) in db.execute('SELECT DISTINCT cell_type FROM cell')}
        for ct in [c.strip() for c in args.markers.split(';') if c.strip()]:
            if ct not in known:
                close = sorted(n for n in known if ct.lower() in n.lower())
                print(
                    f'tm-discover: WARNING unknown cell type "{ct}"; matches: {close[:8]}',
                    file=sys.stderr,
                )
                continue
            rows += [{'cell_type': ct, **r} for r in hpa_markers(db, ct, args.top)]
        cols = ['cell_type', 'gene', 'ncpm', 'enrichment']
    else:
        genes = _gene_args(args)
        rows = [hpa_gene_profile(db, g) for g in genes]
        cols = [
            'gene',
            'top_cell',
            'cell_specificity',
            'top_tissue',
            'tissue_specificity',
        ]
    fh = Path(args.out).open('w', newline='') if args.out else sys.stdout
    if not args.out:
        print(f'# HPA {version}')
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
    if args.out:
        fh.close()
        print(f'wrote {args.out} ({len(rows)} rows, HPA {version})')
    return 0


def _gene_args(args: argparse.Namespace) -> list[str]:
    genes = [g for g in re.split(r'[,\s]+', args.genes or '') if g]
    if args.genes_file:
        genes += [
            norm_gene(r.get('gene'))
            for r in read_csv(Path(args.genes_file))
            if r.get('gene')
        ]
    return list(dict.fromkeys(norm_gene(g) for g in genes))


def cmd_kg(args: argparse.Namespace) -> int:
    ranked, info = KG(Path(args.kg_dir)).rank(
        args.disease_id, [a for a in args.anchors.split(',') if a]
    )
    print(json.dumps(info, indent=1))
    for r in ranked[: args.top]:
        print(
            r['kg_rank'],
            r['gene'],
            r['kg_score'],
            f'models={r["kg_models"]}',
            r['kg_anchors'],
        )
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    problems = KG(Path(args.kg_dir)).selftest()
    if problems:
        print('KG self-test FAILED: ' + ', '.join(problems))
        return 1
    print('KG self-test ok: numpy rankings match the PyKEEN reference')
    return 0


# --------------------------------------------------------------------------
# mechanism-search: perturbation literature for the mechanism line
# --------------------------------------------------------------------------

PERTURBATION_TERMS = []  # redacted  # fmt: skip
# Experimental systems: the mechanism line is about perturbation experiments,
# so clinical-only papers (trials of approved drugs) are filtered out.
EXPERIMENT_TERMS = []  # redacted  # fmt: skip
_EXPERIMENTAL_MODELS = set()  # redacted
_PERTURB = re.compile(r'(?!)')  # redacted
_PERTURB_TYPE = []  # redacted
_MODEL_HINTS = []  # redacted
_EFFECT_WORDS = re.compile(r'(?!)')  # redacted
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(\[])')
MECHANISM_GENE_COLUMNS = [
    'gene', 'prior_rank', 'status', 'pubmed_hits', 'fetched', 'evidence_papers',
    'primary_evidence_papers', 'top_pmids', 'query',
]  # fmt: skip
MECHANISM_PAPER_COLUMNS = [
    'gene', 'pmid', 'year', 'journal', 'article_type', 'perturbation', 'models',
    'effect_words', 'n_evidence_sentences', 'title', 'evidence_sentences',
]  # fmt: skip


def _tiab_or(terms: list[str]) -> str:
    quoted = [f'"{t}"[tiab]' for t in dict.fromkeys(t.strip() for t in terms) if t]
    return '(' + ' OR '.join(quoted) + ')'


def mechanism_disease_terms(
    context_path: Path, assessment_path: Path, extra: list[str], proxies: bool
) -> tuple[str, list[str]]:
    """(disease name, PubMed disease terms): the disease, its exact synonyms"""
    raise NotImplementedError('available on the TargetMind platform')


def gene_terms(symbol: str) -> list[str]:
    """Symbol plus the HGNC approved name (when short enough to be cited)."""
    raise NotImplementedError('available on the TargetMind platform')


def parse_pubmed_xml(xml_bytes: bytes) -> dict[str, dict]:
    import xml.etree.ElementTree as ET

    out: dict[str, dict] = {}
    for art in ET.fromstring(xml_bytes).iter('PubmedArticle'):
        pmid = (art.findtext('.//MedlineCitation/PMID') or '').strip()
        if not pmid:
            continue
        title = (
            ''.join(art.find('.//ArticleTitle').itertext()).strip()
            if art.find('.//ArticleTitle') is not None
            else ''
        )
        parts = []
        for node in art.findall('.//Abstract/AbstractText'):
            text = ''.join(node.itertext()).strip()
            if text:
                parts.append(text)
        year = (
            art.findtext('.//JournalIssue/PubDate/Year')
            or (art.findtext('.//JournalIssue/PubDate/MedlineDate') or '')[:4]
        )
        types = [t.text or '' for t in art.findall('.//PublicationType')]
        out[pmid] = {
            'pmid': pmid,
            'title': title,
            'abstract': ' '.join(parts),
            'year': year,
            'journal': art.findtext('.//Journal/ISOAbbreviation')
            or art.findtext('.//Journal/Title')
            or '',
            'review': any(t in ('Review', 'Systematic Review', 'Meta-Analysis')
                          for t in types),
            'erratum': any(t in ('Published Erratum', 'Retraction of Publication',
                                 'Retracted Publication', 'Expression of Concern')
                           for t in types)
            or title.lower().startswith(('correction:', 'erratum', 'retraction')),
        }  # fmt: skip
    return out


def paper_evidence(gene_names: list[str], paper: dict) -> dict:
    """Sentences naming the gene, with perturbation and effect cues."""
    raise NotImplementedError('available on the TargetMind platform')


def literature_library():
    """The local PubMed library (tm_lit.Library) or None when not mounted."""
    import tm_lit

    return tm_lit.library()


def cmd_mechanism_search(args: argparse.Namespace) -> int:
    if args.show:
        return _mechanism_search(args)
    # One run per output folder: a re-issued command (e.g. the terminal returned
    # before the run finished and the agent started it again in the background)
    # would race on the same CSVs.
    import fcntl

    out = Path(args.out)
    if out.suffix.lower() in ('.csv', '.md', '.json', '.tsv', '.txt'):
        out = out.parent
    out.mkdir(parents=True, exist_ok=True)
    lock_path = out / '.mechanism_search.lock'
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                f'mechanism-search: another run is already writing {out}/; it '
                'keeps running when the terminal returns early. Wait for its '
                '"wrote ..." line (or for mechanism_search.meta.json to update) '
                'instead of starting a new one.',
                file=sys.stderr,
            )
            return 3
        try:
            return _mechanism_search(args)
        finally:
            lock_path.unlink(missing_ok=True)


def _mechanism_search(args: argparse.Namespace) -> int:
    raise NotImplementedError('available on the TargetMind platform')


# --------------------------------------------------------------------------
# report-check: deterministic last step of the Chief's integration
# --------------------------------------------------------------------------

# Markers of an unfinished report (not ordinary words: "results pending" in a trial
# description is fine). A line that starts with "Draft" (any emphasis), "(draft)",
# TODO/TBD/FIXME, placeholders, and "to be completed / completed after ...".
_REPORT_MARKERS = re.compile(
    r'^\W{0,4}draft\b|\(draft\)|\bdraft report\b|\b(?:TODO|TBD|FIXME)\b|'
    r'\bplaceholder\b|\bto be (?:completed|added|filled in)\b|'
    r'\b(?:are|is|will be) completed after\b|\[(?:fill|insert)[^\]]*\]',
    re.I,
)
_MD_LINK = re.compile(r'(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')


def check_report(path: Path) -> list[str]:
    """Problems that must not reach the user in a finished report.md."""
    if not path.is_file():
        return [f'{path} does not exist']
    text = path.read_text(errors='replace')
    if len(text.strip()) < 200:
        return [f'{path} is (nearly) empty']
    problems = []
    in_code = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _REPORT_MARKERS.search(line)
        if m:
            problems.append(
                f'line {n}: unfinished-report marker "{m.group(0)}": {line.strip()[:120]}'
            )
        for bang, _label, target in _MD_LINK.findall(line):
            if re.match(r'[a-z]+:', target) or target.startswith('#'):
                continue  # URLs and anchors
            local = (path.parent / target.split('#')[0]).resolve()
            if not local.exists():
                kind = 'image' if bang else 'link'
                problems.append(f'line {n}: {kind} target missing: {target}')
    return problems


def cmd_report_check(args: argparse.Namespace) -> int:
    problems = check_report(Path(args.report))
    if not problems:
        print(f'report-check: {args.report} OK (no draft markers, all links resolve)')
        return 0
    print(
        f'report-check: {len(problems)} problem(s) in {args.report} — fix them, then re-run:'
    )
    for p_ in problems:
        print(f'  - {p_}')
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='tm-discover',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--kg-dir', default=str(KG_DIR))
    sub = p.add_subparsers(dest='cmd', required=True)
    pool = sub.add_parser('pool', help='build the candidate pool')
    pool.add_argument(
        '--disease-id',
        required=True,
        help='MONDO/EFO id(s) of the disease, comma-separated: the first one Open Targets knows is used',
    )
    pool.add_argument('--disease-name', default='')
    pool.add_argument('--context', default='', help='evidence/disease_context.csv')
    pool.add_argument('--out', required=True)
    pool.add_argument('--genetic-min', type=float, default=0.5)
    pool.add_argument('--kg-top', type=int, default=200)
    pool.add_argument('--hub-quantile', type=float, default=0.99)
    pool.add_argument('--no-gwas', action='store_true')
    merge = sub.add_parser('merge', help='expert columns + pool -> evidence matrix')
    merge.add_argument('--pool', required=True)
    merge.add_argument('--omics', default='')
    merge.add_argument('--genetics', default='')
    merge.add_argument('--mechanism', default='')
    merge.add_argument(
        '--omics-datasets',
        default='',
        help='omics_datasets.csv (default: next to --omics); the omics counts are recomputed from it',
    )
    merge.add_argument('--out', required=True)
    merge.add_argument('--screen-max', type=int, default=200)
    merge.add_argument('--screen-min', type=int, default=30)
    prep = sub.add_parser(
        'prepare', help='related-disease candidates for disease_context.csv'
    )
    prep.add_argument(
        '--disease-id',
        required=True,
        help='MONDO/EFO id(s) of the disease, comma-separated: the first one Open Targets knows is used',
    )
    prep.add_argument(
        '--add', default='', help='extra diseases/traits by name, ";"-separated'
    )
    prep.add_argument('--out', default='evidence/context_candidates.csv')
    prep.add_argument('--min-similarity', type=float, default=0.55)
    prep.add_argument('--show', type=int, default=40)
    sl = sub.add_parser(
        'shortlist', help='novelty tiers + evidence matrix -> shortlist.csv (D3/D7/D8)'
    )
    sl.add_argument('--matrix', default='evidence/evidence_matrix.csv')
    sl.add_argument('--novelty', default='evidence/novelty.csv')
    sl.add_argument('--out', default='shortlist.csv')
    sl.add_argument('--excluded', default='evidence/excluded_targets.csv')
    sl.add_argument('--max', type=int, default=10)
    sl.add_argument(
        '--user-genes',
        action='store_true',
        help='keep every gene (user-named candidates)',
    )
    sl.add_argument(
        '--exclude',
        default='',
        help='genes confirmed known by hand (e.g. a trial drug acts on them), comma-separated',
    )
    geo = sub.add_parser(
        'geo', help='validated GEO series download -> gene x sample matrices'
    )
    geo.add_argument('gse', help='GSE accessions, comma/space-separated')
    geo.add_argument('--out', default='experts/bioinformatics/geo')
    gw = sub.add_parser(
        'gwas', help='local GWAS Catalog lookup for genes (no API calls)'
    )
    gw.add_argument('--genes', default='', help='comma/space-separated symbols')
    gw.add_argument('--genes-file', default='', help='CSV with a gene column')
    gw.add_argument(
        '--trait', default='', help='substring of the trait label, or a trait id'
    )
    gw.add_argument(
        '--limit', type=int, default=25, help='associations per gene, strongest first'
    )
    gw.add_argument('--out', default='')
    gs = sub.add_parser(
        'geo-search',
        help='GEO series for this disease with groups and tissue -> geo_candidates.csv',
    )
    gs.add_argument('--disease', required=True)
    gs.add_argument('--synonyms', default='', help='comma-separated')
    gs.add_argument(
        '--tissue', default='', help='comma-separated tissue/compartment keywords'
    )
    gs.add_argument(
        '--related',
        default='',
        help='";"-separated related diseases (searched only if < 2 usable)',
    )
    gs.add_argument('--max-search', type=int, default=200)
    gs.add_argument(
        '--max-series',
        type=int,
        default=25,
        help='series checked per search (largest first)',
    )
    gs.add_argument('--out', default='experts/bioinformatics/geo_candidates.csv')
    ms = sub.add_parser(
        'mechanism-search',
        help='perturbation literature per gene (PubMed) -> mechanism_search_*.csv',
    )
    ms.add_argument('--pool', default='evidence/pool.csv')
    ms.add_argument('--top', type=int, default=60, help='top pool genes by prior_rank')
    ms.add_argument('--genes', default='', help='explicit genes (overrides --top)')
    ms.add_argument('--context', default='evidence/disease_context.csv')
    ms.add_argument('--assessment', default='evidence/context_assessment.json')
    ms.add_argument(
        '--terms', default='', help='";"-separated extra disease/model terms'
    )
    ms.add_argument(
        '--no-proxies', action='store_true', help='do not add proxy diseases'
    )
    ms.add_argument('--per-gene', type=int, default=25, help='papers per gene')
    ms.add_argument(
        '--no-model-filter',
        action='store_true',
        help='also keep papers without an experimental system (clinical-only)',
    )
    ms.add_argument('--show', default='', help='print abstracts of these PMIDs')
    ms.add_argument(
        '--online',
        action='store_true',
        help='search PubMed online instead of the local library',
    )
    ms.add_argument(
        '--digest', type=int, default=3, help='evidence papers per gene in the digest'
    )
    ms.add_argument('--out', default='experts/molecular-biology')
    hp = sub.add_parser('hpa', help='HPA cell-type / tissue expression (local)')
    hp.add_argument('--genes', default='')
    hp.add_argument('--genes-file', default='')
    hp.add_argument(
        '--markers', default='', help='";"-separated HPA cell types -> marker genes'
    )
    hp.add_argument('--top', type=int, default=30)
    hp.add_argument('--list-cell-types', action='store_true')
    hp.add_argument('--out', default='')
    kg = sub.add_parser('kg', help='KG ranking only')
    kg.add_argument('--disease-id', required=True)
    kg.add_argument('--anchors', default='')
    kg.add_argument('--top', type=int, default=50)
    sub.add_parser(
        'selftest', help='check numpy KG scoring against the PyKEEN reference'
    )
    rc = sub.add_parser(
        'report-check',
        help='last integration step: no draft/TODO markers, every image/link resolves',
    )
    rc.add_argument('--report', default='report.md')
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {
        'prepare': cmd_prepare,
        'pool': cmd_pool,
        'merge': cmd_merge,
        'shortlist': cmd_shortlist,
        'gwas': cmd_gwas,
        'geo': cmd_geo,
        'geo-search': cmd_geo_search,
        'hpa': cmd_hpa,
        'mechanism-search': cmd_mechanism_search,
        'report-check': cmd_report_check,
        'kg': cmd_kg,
        'selftest': cmd_selftest,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
