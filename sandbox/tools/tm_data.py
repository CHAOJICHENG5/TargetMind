#!/usr/bin/env python3
"""tm-data: what local data this sandbox has, and the one place tools resolve it.

  tm-data list              every local source: version, coverage, how to use it
  tm-data info <source>     details of one source (files, sizes, fields, interface)

Local data tiers (host layout: ops/storage.md in the platform repo):

  /opt/targetmind/data    reference library, read-only, versioned snapshots
                          (ref/<source>/current/...; manifest.json lists versions)
  /opt/targetmind/cache   shared download cache, read-write (GEO series)

Rule for every analysis: local reference library first, then the shared cache,
then online services (NCBI through the platform relay); never write your own
scraper for data that is available here.

Tools import this module (``data_path``, ``data_versions``, ``open_sqlite``) so
every tool reads the same versions and records them in its meta files.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get('TM_DATA_DIR', '/opt/targetmind/data'))
REF_DIR = Path(os.environ.get('TM_REF_DIR', str(DATA_DIR / 'ref')))
CACHE_DIR = Path(os.environ.get('TM_CACHE_DIR', '/opt/targetmind/cache'))


def data_path(
    source: str,
    name: str = '',
    *,
    data_dir: Path | None = None,
    ref_dir: Path | None = None,
) -> Path:
    """The current version of a source (ref/<source>/current/<name>), else the
    previous flat layout (ref/<source>/<name>; kg/ for PrimeKG)."""
    data_dir = data_dir or DATA_DIR
    ref_dir = ref_dir or REF_DIR
    current = ref_dir / source / 'current'
    if current.exists():
        base = current
    elif source == 'primekg' and (data_dir / 'kg').exists():
        base = data_dir / 'kg'
    else:
        base = ref_dir / source
    return base / name if name else base


def manifest(data_dir: Path | None = None) -> dict:
    """manifest.json of the reference library ({} if absent)."""
    try:
        return json.loads(((data_dir or DATA_DIR) / 'manifest.json').read_text())
    except (OSError, ValueError):
        return {}


def data_versions(data_dir: Path | None = None) -> dict[str, str]:
    """Current version of every local source, for the tools' meta files."""
    sources = manifest(data_dir).get('sources') or {}
    return {k: v.get('current', '') for k, v in sorted(sources.items())}


def open_sqlite(path: Path) -> sqlite3.Connection:
    """Read-only, immutable connection (shared safely by all sandboxes)."""
    db = sqlite3.connect(
        f'file:{path}?mode=ro&immutable=1', uri=True, check_same_thread=False
    )
    db.execute('PRAGMA query_only = 1')
    return db


def _size(files: dict) -> str:
    total = sum(f.get('bytes', 0) for f in files.values())
    return f'{total / 1e9:.1f} GB' if total >= 1e9 else f'{total / 1e6:.0f} MB'


def cmd_list(_args: argparse.Namespace) -> int:
    sources = manifest().get('sources') or {}
    if not sources:
        print(f'no reference library at {DATA_DIR} (manifest.json missing)')
        return 1
    print(f'Reference library {DATA_DIR} (read-only):')
    for name, entry in sorted(sources.items()):
        current = entry.get('current', '')
        version = entry.get('versions', {}).get(current, {})
        about = entry.get('about') or {}
        print(f'\n{name}  [{current}, {_size(version.get("files", {}))}]')
        if about.get('description'):
            print(f'  {about["description"]}')
        coverage = about.get('coverage') or (version.get('info') or {}).get('coverage')
        if coverage:
            print(f'  coverage: {coverage}')
        if about.get('use'):
            print(f'  use: {about["use"]}')
    cache = CACHE_DIR
    print(
        f'\nShared cache {cache} ('
        + ('read-write' if os.access(cache, os.W_OK) else 'not mounted')
        + '): GEO series downloaded by `tm-discover geo` (reused by every task).'
    )
    print(
        '\nOrder: local library -> shared cache -> online (NCBI via the platform '
        'relay). Do not write scrapers for data listed here.'
    )
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    entry = (manifest().get('sources') or {}).get(args.source)
    if not entry:
        print(f'unknown source {args.source!r}; see `tm-data list`', file=sys.stderr)
        return 2
    current = entry.get('current', '')
    version = entry.get('versions', {}).get(current, {})
    print(
        json.dumps(
            {
                'source': args.source,
                'current': current,
                'path': str(data_path(args.source)),
                'about': entry.get('about') or {},
                'built_utc': version.get('built_utc'),
                'info': version.get('info') or {},
                'files': {
                    k: v.get('bytes') for k, v in version.get('files', {}).items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog='tm-data',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='local sources, versions, coverage, how to use them')
    info = sub.add_parser('info', help='details of one source')
    info.add_argument('source')
    args = p.parse_args(argv)
    return {'list': cmd_list, 'info': cmd_info}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
