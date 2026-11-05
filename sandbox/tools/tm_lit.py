#!/usr/bin/env python3
"""tm-lit: literature search on the local PubMed library (no rate limits, no outages).

  tm-lit search '<PubMed query>' [--limit 20] [--sort relevance|date]
                [--since 2015] [--until 2024] [--no-reviews] [--abstracts]
                [--format table|csv|json] [--online]
  tm-lit count  '<query>' ['<query>' ...] | --batch queries.tsv (name<TAB>query)
  tm-lit show   <PMID>[,<PMID>...]          title, abstract, MeSH, type flags
  tm-lit info                               library version, coverage, size

Queries use PubMed syntax, so SOP queries work unchanged:
  "phrase"[tiab]  word[tiab]  [ti] [ab] [ot] [mh] [nm]  word*  AND OR NOT ( )
  review[pt]  "clinical trial"[pt]  2015:2024[dp]
Untagged terms search title, abstract, keywords, MeSH and substances. Operators
are applied left to right as in PubMed; use parentheses. [tiab] covers title,
abstract and author keywords (as in PubMed); Greek letters match their names
(TGF-β1 = TGF-beta1). Unsupported tags fail with a clear message.

The library is a fixed snapshot (see `tm-lit info`). `--online` adds PubMed
records newer than the snapshot through the platform relay; if NCBI is down the
local results are still printed. Retracted papers and errata are flagged in the
type column and never count as evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tm_data  # noqa: E402

LIBRARY = ('pubmed', 'pubmed.sqlite')
TEXT_COLUMNS = ('title', 'abstract', 'keywords', 'mesh', 'substances')
TIAB = ('title', 'abstract', 'keywords')
FIELD_COLUMNS = {
    'tiab': TIAB, 'title/abstract': TIAB, 'tw': TIAB, 'text word': TIAB,
    'ti': ('title',), 'title': ('title',),
    'ab': ('abstract',), 'abstract': ('abstract',),
    'ot': ('keywords',), 'other term': ('keywords',), 'kw': ('keywords',),
    'mh': ('mesh',), 'mesh': ('mesh',), 'mesh terms': ('mesh',),
    'majr': ('mesh',), 'mesh major topic': ('mesh',), 'mh:noexp': ('mesh',),
    'nm': ('substances',), 'substance name': ('substances',),
    'all': TEXT_COLUMNS, 'all fields': TEXT_COLUMNS,
}  # fmt: skip
DATE_FIELDS = {'dp', 'pdat', 'publication date', 'date - publication'}
TYPE_FIELDS = {'pt', 'publication type'}
# bm25 weights in FTS column order: a hit in the title counts most.
BM25_WEIGHTS = (3.0, 1.0, 1.5, 1.0, 1.0)


class QueryError(ValueError):
    """The query cannot be run (syntax or unsupported field)."""


# --------------------------------------------------------------------------
# Query parsing (PubMed subset) -> SQL / FTS5
# --------------------------------------------------------------------------

_TOKEN = re.compile(
    r'\s*(?:(?P<lp>\()|(?P<rp>\))|'
    r'(?P<phrase>"[^"]*")(?P<pstar>\*)?|'
    r'(?P<word>[^\s()"\[\]]+))'
    r'(?:\s*\[(?P<tag>[^\]]+)\])?'
)


@dataclass
class Term:
    text: str
    columns: tuple[str, ...]
    prefix: bool = False


@dataclass
class Filter:
    sql: str
    params: list = field(default_factory=list)
    label: str = ''


@dataclass
class Op:
    op: str  # AND | OR | NOT
    left: object
    right: object


def _tokens(query: str) -> list[tuple[str, str, str]]:
    """[(kind, value, tag)] with kind in ( ) AND OR NOT term."""
    out: list[tuple[str, str, str]] = []
    pos = 0
    query = query.strip()
    while pos < len(query):
        m = _TOKEN.match(query, pos)
        if not m or m.end() == pos:
            raise QueryError(f'cannot parse the query near: {query[pos : pos + 30]!r}')
        pos = m.end()
        tag = (m.group('tag') or '').strip().lower()
        if m.group('lp'):
            out.append(('(', '(', ''))
        elif m.group('rp'):
            out.append((')', ')', ''))
        elif m.group('phrase'):
            text = m.group('phrase')[1:-1]
            out.append(('term', text + ('*' if m.group('pstar') else ''), tag))
        else:
            word = m.group('word')
            if word in ('AND', 'OR', 'NOT') and not tag:
                out.append((word, word, ''))
            else:
                out.append(('term', word, tag))
    return out


def _date_filter(text: str) -> Filter:
    years = re.findall(r'(\d{4})', text)
    if not years or len(years) > 2:
        raise QueryError(
            f'cannot read the date {text!r}[dp]; use 2015[dp] or 2015:2024[dp]'
        )
    lo, hi = int(years[0]), int(years[-1])
    return Filter('a.year BETWEEN ? AND ?', [min(lo, hi), max(lo, hi)], f'{lo}-{hi}')


def _type_filter(text: str) -> Filter:
    value = text.strip().lower()
    if value in ('review', 'reviews'):
        return Filter('a.review = 1', [], 'review')
    if value in ('retracted publication',):
        return Filter('a.retracted = 1', [], 'retracted')
    return Filter(
        "('; ' || lower(a.pubtypes) || '; ') LIKE ?", [f'%; {value}; %'], value
    )


def _leaf(text: str, tag: str) -> Term | Filter:
    if tag in DATE_FIELDS:
        return _date_filter(text)
    if tag in TYPE_FIELDS:
        return _type_filter(text)
    if tag and tag not in FIELD_COLUMNS:
        raise QueryError(
            f'field [{tag}] is not available locally; use [tiab], [ti], [ab], [ot], '
            '[mh], [nm], [pt] or [dp] (or tm-lit search --online for other fields)'
        )
    columns = FIELD_COLUMNS[tag] if tag else TEXT_COLUMNS
    prefix = text.endswith('*')
    text = text.rstrip('*').strip()
    if not re.search(r'\w', text):
        raise QueryError(f'empty search term {text!r}')
    return Term(text, columns, prefix)


def parse(query: str):
    """PubMed-style query -> tree of Term / Filter / Op (left to right)."""
    tokens = _tokens(query)
    pos = 0

    def unit():
        nonlocal pos
        if pos >= len(tokens):
            raise QueryError('the query ends where a term was expected')
        kind, value, tag = tokens[pos]
        if kind == '(':
            pos += 1
            node = expr()
            if pos >= len(tokens) or tokens[pos][0] != ')':
                raise QueryError('unbalanced parentheses')
            pos += 1
            return node
        if kind == 'term':
            pos += 1
            # "2015"[dp] : "2024"[dp] style ranges arrive as two date terms.
            return _leaf(value, tag)
        raise QueryError(f'unexpected {value!r}')

    def expr():
        nonlocal pos
        node = unit()
        while pos < len(tokens) and tokens[pos][0] != ')':
            kind = tokens[pos][0]
            if kind in ('AND', 'OR', 'NOT'):
                pos += 1
                op = kind
                # "a AND NOT b" (common outside PubMed) means "a NOT b".
                if op == 'AND' and pos < len(tokens) and tokens[pos][0] == 'NOT':
                    pos += 1
                    op = 'NOT'
            else:
                op = 'AND'  # adjacent terms: implicit AND, as in PubMed
            node = Op(op, node, unit())
        return node

    tree = expr()
    if pos != len(tokens):
        raise QueryError('unbalanced parentheses')
    return tree


def _is_fts(node) -> bool:
    if isinstance(node, Term):
        return True
    if isinstance(node, Op):
        return _is_fts(node.left) and _is_fts(node.right)
    return False


_ALNUM_SPLIT = re.compile(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])')


def symbol_variants(text: str) -> list[str]:
    """Hyphenated spellings PubMed finds for a gene-symbol-like word.

    PubMed matches CDK4 to "CDK-4", VEGFA to "VEGF-A" and MMP9 to "MMP-9"; the
    local tokenizer splits hyphenated words, so the split spellings are searched
    too. Only single uppercase symbols (letters with digits, or >= 4 capitals
    ending in an isoform letter A-E) are expanded; ordinary words are left alone.
    """
    if not re.fullmatch(r'[A-Z][A-Za-z0-9]*', text) or len(text) < 3:
        return []
    out: list[str] = []
    # The hyphen can sit at any letter/digit boundary (IL-1Ra, IL1-RA, COL4A-4),
    # and the tokenizer keeps "1Ra" together, so try every combination of
    # boundaries (at most 3 boundaries -> 7 variants).
    cuts = [m.start() for m in _ALNUM_SPLIT.finditer(text)][:3]
    for mask in range(1, 1 << len(cuts)):
        chosen = [c for i, c in enumerate(cuts) if mask >> i & 1]
        pieces, last = [], 0
        for c in chosen:
            pieces.append(text[last:c])
            last = c
        pieces.append(text[last:])
        out.append(' '.join(pieces))
    if re.fullmatch(r'[A-Z]{3,}[A-E]', text):  # isoform letter: VEGF-A, PDGF-B
        out.append(f'{text[:-1]} {text[-1]}')
    return out


def _phrase(text: str, prefix: bool) -> str:
    phrase = '"' + text.replace('"', '""') + '"'
    return phrase + ' *' if prefix else phrase


def _fts(node, norm) -> str:
    if isinstance(node, Term):
        forms = [node.text, *symbol_variants(node.text)]
        phrases = [_phrase(norm(f), node.prefix) for f in forms]
        phrase = phrases[0] if len(phrases) == 1 else '(' + ' OR '.join(phrases) + ')'
        cols = ' '.join(node.columns)
        return f'{{{cols}}} : {phrase}' if node.columns != TEXT_COLUMNS else phrase
    return f'({_fts(node.left, norm)} {node.op} {_fts(node.right, norm)})'


@dataclass
class Neg:
    node: object


def _conjuncts(node) -> list:
    """Top-level AND parts; `a NOT b` is `a AND (not b)`."""
    if isinstance(node, Op) and node.op == 'AND':
        return _conjuncts(node.left) + _conjuncts(node.right)
    if isinstance(node, Op) and node.op == 'NOT':
        return _conjuncts(node.left) + [Neg(node.right)]
    return [node]


def _sql(node, norm) -> tuple[str, list]:
    if _is_fts(node):
        return 'a.pmid IN (SELECT rowid FROM fts WHERE fts MATCH ?)', [_fts(node, norm)]
    if isinstance(node, Filter):
        return node.sql, list(node.params)
    ls, lp = _sql(node.left, norm)
    rs, rp = _sql(node.right, norm)
    if node.op == 'NOT':
        return f'({ls} AND NOT ({rs}))', lp + rp
    return f'({ls} {node.op} {rs})', lp + rp


def terms_of(node) -> list[Term]:
    if isinstance(node, Term):
        return [node]
    if isinstance(node, Op):
        return terms_of(node.left) + (terms_of(node.right) if node.op != 'NOT' else [])
    return []


@dataclass
class Compiled:
    match: str  # FTS5 expression of the text part ANDed at the top level
    where: str  # remaining SQL conditions on `a` (article)
    params: list
    terms: list[Term]


def compile_query(query: str, norm=lambda s: s) -> Compiled:
    tree = parse(query)
    fts_parts, fts_not, other = [], [], []
    for c in _conjuncts(tree):
        if isinstance(c, Neg):
            (fts_not if _is_fts(c.node) else other).append(c)
        else:
            (fts_parts if _is_fts(c) else other).append(c)
    if not fts_parts:
        raise QueryError('the query needs at least one text term (not only [pt]/[dp])')
    match = ' AND '.join(f'({_fts(c, norm)})' for c in fts_parts)
    if fts_not:
        match = f'({match})' + ''.join(f' NOT ({_fts(c.node, norm)})' for c in fts_not)
    where, params = [], []
    for c in other:
        s, p = _sql(c.node if isinstance(c, Neg) else c, norm)
        where.append(f'NOT ({s})' if isinstance(c, Neg) else s)
        params += p
    return Compiled(match, ' AND '.join(where), params, terms_of(tree))


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------


class Library:
    """Read-only access to pubmed.sqlite (one connection per thread)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else tm_data.data_path(*LIBRARY)
        self._local = threading.local()
        self._meta: dict | None = None
        self._table = None

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def db(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            if not self.available:
                raise FileNotFoundError(
                    f'local PubMed library not found ({self.path}); see `tm-data list`'
                )
            conn = tm_data.open_sqlite(self.path)
            self._local.conn = conn
        return conn

    def meta(self) -> dict:
        if self._meta is None:
            self._meta = {
                k: json.loads(v)
                for k, v in self.db().execute('SELECT key, value FROM meta')
            }
        return self._meta

    def version(self) -> str:
        current = tm_data.data_versions().get('pubmed')
        return current or self.meta().get('built_utc', '')[:10]

    def norm(self, text: str) -> str:
        if self._table is None:
            self._table = str.maketrans(self.meta().get('normalisation') or {})
        return text.translate(self._table)

    def compile(self, query: str) -> Compiled:
        return compile_query(query, self.norm)

    def _run(self, sql: str, params: list) -> list:
        try:
            return self.db().execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            raise QueryError(f'query failed: {e}') from e

    def count(self, query: str) -> int:
        c = self.compile(query)
        if not c.where:
            return self._run('SELECT count(*) FROM fts WHERE fts MATCH ?', [c.match])[
                0
            ][0]
        return self._run(
            'SELECT count(*) FROM fts JOIN article a ON a.pmid = fts.rowid '
            f'WHERE fts MATCH ? AND {c.where}',
            [c.match, *c.params],
        )[0][0]

    def search(
        self,
        query: str,
        limit: int = 20,
        sort: str = 'relevance',
        since: int | None = None,
        until: int | None = None,
        no_reviews: bool = False,
    ) -> tuple[int, list[str]]:
        """(total hits, PMIDs of the first `limit` by relevance or date)."""
        c = self.compile(query)
        where, params = [c.where] if c.where else [], list(c.params)
        if since:
            where.append('a.year >= ?')
            params.append(since)
        if until:
            where.append('a.year <= ?')
            params.append(until)
        if no_reviews:
            where.append('a.review = 0')
        cond = ''.join(f' AND {w}' for w in where)
        base = f'FROM fts JOIN article a ON a.pmid = fts.rowid WHERE fts MATCH ?{cond}'
        total = (
            self.count(query)
            if not where
            else self._run(f'SELECT count(*) {base}', [c.match, *params])[0][0]
        )
        order = (
            'a.year DESC, a.pmid DESC'
            if sort == 'date'
            else f'bm25(fts, {", ".join(map(str, BM25_WEIGHTS))})'
        )
        rows = self._run(
            f'SELECT a.pmid {base} ORDER BY {order} LIMIT ?',
            [c.match, *params, max(0, limit)],
        )
        return total, [str(r[0]) for r in rows]

    def search_ranked_by(
        self, query: str, rank_query: str, limit: int
    ) -> tuple[int, list[str]]:
        """(total hits of `query`, its first `limit` PMIDs ordered by the
        relevance of `rank_query`).

        bm25 needs the document frequency of every phrase in the expression, and
        reading that for very common words ("cells", "mice", "inhibition")
        costs seconds per query. For many similar queries (one per gene) rank by
        the selective part only (`rank_query`, e.g. gene AND disease, which
        `query` must imply) and keep the full query as the filter.
        """
        hits = {
            r[0]
            for r in self._run(
                'SELECT rowid FROM fts WHERE fts MATCH ?', [self.compile(query).match]
            )
        }
        if len(hits) <= limit:
            ranked_rows = (
                self._run(
                    'SELECT a.pmid FROM article a WHERE a.pmid IN '
                    f'({",".join("?" * len(hits))}) ORDER BY a.year DESC',
                    list(hits),
                )
                if hits
                else []
            )
            return len(hits), [str(r[0]) for r in ranked_rows]
        weights = ', '.join(map(str, BM25_WEIGHTS))
        cursor = self.db().execute(
            f'SELECT rowid FROM fts WHERE fts MATCH ? ORDER BY bm25(fts, {weights})',
            [self.compile(rank_query).match],
        )
        ranked: list[str] = []
        for (rowid,) in cursor:
            if rowid in hits:
                ranked.append(str(rowid))
                if len(ranked) >= limit:
                    break
        cursor.close()
        return len(hits), ranked

    def get(self, pmids: list[str]) -> dict[str, dict]:
        """PMID -> record (title, abstract, year, journal, pubtypes, mesh, flags).
        `erratum` is true for errata, retraction notices and retracted papers
        (never evidence)."""
        ids = [int(p) for p in pmids if str(p).strip().isdigit()]
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            rows = self.db().execute(
                'SELECT pmid, year, journal, pubtypes, mesh, substances, keywords, '
                'doi, pmcid, title, abstract, review, retracted, erratum FROM article '
                f'WHERE pmid IN ({",".join("?" * len(chunk))})',
                chunk,
            )
            for r in rows:
                out[str(r[0])] = {
                    'pmid': str(r[0]),
                    'year': str(r[1] or ''),
                    'journal': r[2] or '',
                    'pubtypes': r[3] or '',
                    'mesh': r[4] or '',
                    'substances': r[5] or '',
                    'keywords': r[6] or '',
                    'doi': r[7] or '',
                    'pmcid': r[8] or '',
                    'title': r[9] or '',
                    'abstract': r[10] or '',
                    'review': bool(r[11]),
                    'retracted': bool(r[12]),
                    'erratum': bool(r[13] or r[12]),
                }
        return out


_LIBRARY: list[Library] = []


def library() -> Library | None:
    """The mounted library, or None (tools then fall back to online PubMed)."""
    if not _LIBRARY:
        _LIBRARY.append(Library())
    lib = _LIBRARY[0]
    return lib if lib.available else None


def article_type(rec: dict) -> str:
    if rec.get('retracted'):
        return 'RETRACTED'
    if rec.get('erratum'):
        return 'erratum'
    return 'review' if rec.get('review') else 'primary'


def snippet(rec: dict, terms: list[Term], norm, width: int = 260) -> str:
    """First sentence of title/abstract that contains a query term."""
    patterns = []
    for t in terms:
        if not set(t.columns) & {'title', 'abstract'}:
            continue
        words = [re.escape(w) for w in re.findall(r'\w+', norm(t.text))]
        if words:
            tail = r'\w*' if t.prefix else r'\b'
            patterns.append(r'\b' + r'\W+'.join(words) + tail)
    if not patterns:
        return ''
    rx = re.compile('|'.join(patterns), re.I)
    text = f'{rec.get("title", "")} {rec.get("abstract", "")}'
    for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text):
        if rx.search(norm(sentence)):
            s = sentence.strip()
            return s if len(s) <= width else s[: width - 1] + '…'
    return ''


# --------------------------------------------------------------------------
# Online supplement (records newer than the snapshot), via tm-discover's client
# --------------------------------------------------------------------------


def online_search(query: str, since_date: str, limit: int) -> tuple[int, dict]:
    """(count, {pmid: record}) of PubMed records added on/after since_date
    (YYYY/MM/DD). Raises on NCBI failure."""
    import tm_discover as td

    term = f'({query}) AND ("{since_date}"[edat] : "3000"[edat])'
    res = td.eutils_json(
        'esearch', {'db': 'pubmed', 'term': term, 'retmax': limit, 'sort': 'relevance'}
    )['esearchresult']
    ids = res.get('idlist', [])
    records = {}
    if ids:
        papers = td.parse_pubmed_xml(
            td.eutils_raw(
                'efetch',
                {
                    'db': 'pubmed',
                    'id': ','.join(ids),
                    'rettype': 'abstract',
                    'retmode': 'xml',
                },
            )
        )
        for pmid, p in papers.items():
            records[pmid] = {**p, 'pmid': pmid, 'retracted': False, 'source': 'online'}
    return int(res.get('count', 0)), records


def online_get(pmids: list[str]) -> dict[str, dict]:
    import tm_discover as td

    papers = td.parse_pubmed_xml(
        td.eutils_raw(
            'efetch',
            {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'rettype': 'abstract',
                'retmode': 'xml',
            },
        )
    )
    return {k: {**v, 'pmid': k, 'source': 'online'} for k, v in papers.items()}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _need_library() -> Library:
    lib = library()
    if lib is None:
        print(
            f'tm-lit: local PubMed library not found ({Library().path}). '
            'Use `tm-lit search --online` or the NCBI relay (data-access SOP).',
            file=sys.stderr,
        )
        raise SystemExit(2)
    return lib


def _print_records(order: list[str], recs: dict, args, terms, norm) -> None:
    if args.format == 'json':
        print(
            json.dumps(
                [recs[p] for p in order if p in recs], ensure_ascii=False, indent=1
            )
        )
        return
    if args.format == 'csv':
        w = csv.writer(sys.stdout)
        w.writerow(['pmid', 'year', 'type', 'journal', 'title', 'snippet', 'source'])
        for p in order:
            r = recs.get(p)
            if r:
                w.writerow([p, r.get('year'), article_type(r), r.get('journal'),
                            r.get('title'), snippet(r, terms, norm),
                            r.get('source', 'local')])  # fmt: skip
        return
    for p in order:
        r = recs.get(p)
        if not r:
            continue
        flag = '' if r.get('source', 'local') == 'local' else '  [online]'
        print(f'{p:>9}  {r.get("year", ""):4}  {article_type(r):9}  '
              f'{(r.get("journal") or "")[:22]:22}  {r.get("title", "")[:150]}{flag}')  # fmt: skip
        if args.abstracts:
            print(f'           {r.get("abstract") or "(no abstract)"}\n')
        else:
            s = snippet(r, terms, norm)
            if s:
                print(f'           > {s}')


def cmd_search(args) -> int:
    lib = _need_library() if not args.online_only else library()
    order: list[str] = []
    recs: dict[str, dict] = {}
    terms: list[Term] = []
    norm = lib.norm if lib else (lambda s: s)
    if lib:
        try:
            total, order = lib.search(
                args.query,
                args.limit,
                args.sort,
                args.since,
                args.until,
                args.no_reviews,
            )
            terms = lib.compile(args.query).terms
        except QueryError as e:
            print(f'tm-lit: {e}', file=sys.stderr)
            return 2
        recs = lib.get(order)
        for r in recs.values():
            r['source'] = 'local'
        if args.format == 'table':
            print(
                f'{total:,} hits in local PubMed ({lib.version()}; '
                f'{lib.meta().get("coverage", "")}); showing {len(order)} by {args.sort}'
            )
    if args.online or args.online_only:
        since = (lib.meta().get('snapshot_date') if lib else '') or '1800/01/01'
        try:
            n, online = online_search(args.query, since, args.limit)
            fresh = [p for p in online if p not in recs]
            order += fresh
            recs.update({p: online[p] for p in fresh})
            if args.format == 'table':
                print(
                    f'online (PubMed since {since}): {n} hits, {len(fresh)} new shown'
                )
        except Exception as e:  # noqa: BLE001 - online is only a supplement
            print(f'online supplement unavailable: {e}', file=sys.stderr)
    _print_records(order, recs, args, terms, norm)
    return 0


def cmd_count(args) -> int:
    lib = _need_library()
    queries: list[tuple[str, str]] = [(q, q) for q in args.queries]
    if args.batch:
        for line in Path(args.batch).read_text().splitlines():
            if line.strip() and not line.startswith('#'):
                name, _, q = line.partition('\t')
                queries.append((name.strip(), (q or name).strip()))
    if not queries:
        print('tm-lit count: give queries or --batch FILE', file=sys.stderr)
        return 2
    status = 0
    print('name\tcount')
    for name, q in queries:
        try:
            print(f'{name}\t{lib.count(q)}')
        except QueryError as e:
            status = 2
            print(f'{name}\tERROR {e}')
    return status


def cmd_show(args) -> int:
    pmids = [p for p in re.split(r'[,\s]+', ' '.join(args.pmids)) if p.isdigit()]
    lib = library()
    recs = lib.get(pmids) if lib else {}
    missing = [p for p in pmids if p not in recs]
    if missing:
        try:
            recs.update(online_get(missing))
        except Exception as e:  # noqa: BLE001
            print(
                f'online lookup unavailable for {", ".join(missing)}: {e}',
                file=sys.stderr,
            )
    if args.format == 'json':
        print(
            json.dumps(
                [recs[p] for p in pmids if p in recs], ensure_ascii=False, indent=1
            )
        )
        return 0
    for p in pmids:
        r = recs.get(p)
        if not r:
            print(f'PMID {p}: not found\n')
            continue
        src = '' if r.get('source', 'local') == 'local' else ' [online]'
        print(f'PMID {p} ({r.get("year")}, {r.get("journal")}; {article_type(r)}){src}')
        print(r.get('title', ''))
        print(r.get('abstract') or '(no abstract)')
        if r.get('mesh'):
            print(f'MeSH: {r["mesh"]}')
        if r.get('pubtypes'):
            print(f'Types: {r["pubtypes"]}')
        print()
    return 0


def cmd_info(_args) -> int:
    lib = _need_library()
    meta = lib.meta()
    meta.pop('normalisation', None)
    print(
        json.dumps({'version': lib.version(), 'path': str(lib.path), **meta}, indent=2)
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog='tm-lit',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search', help='search (PubMed syntax)')
    s.add_argument('query')
    s.add_argument('--limit', type=int, default=20)
    s.add_argument('--sort', choices=('relevance', 'date'), default='relevance')
    s.add_argument('--since', type=int)
    s.add_argument('--until', type=int)
    s.add_argument('--no-reviews', action='store_true')
    s.add_argument('--abstracts', action='store_true', help='print full abstracts')
    s.add_argument('--format', choices=('table', 'csv', 'json'), default='table')
    s.add_argument('--online', action='store_true',
                   help='also search PubMed online for records newer than the snapshot')  # fmt: skip
    s.add_argument('--online-only', action='store_true', help=argparse.SUPPRESS)
    c = sub.add_parser('count', help='hit counts')
    c.add_argument('queries', nargs='*')
    c.add_argument('--batch', help='file with name<TAB>query lines')
    sh = sub.add_parser('show', help='full records')
    sh.add_argument('pmids', nargs='+')
    sh.add_argument('--format', choices=('text', 'json'), default='text')
    sub.add_parser('info', help='library version and coverage')
    args = p.parse_args(argv)
    return {
        'search': cmd_search,
        'count': cmd_count,
        'show': cmd_show,
        'info': cmd_info,
    }[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
