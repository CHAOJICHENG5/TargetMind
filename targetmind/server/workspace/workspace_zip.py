"""ZIP download of Results-panel selections (files and whole folders).

The archive is built inside the conversation's sandbox by ``ZIP_SCRIPT`` (stdlib
only), written outside the workspace under ``/tmp`` and streamed to the browser
by the app server. It is kept for ``ZIP_TTL_SECONDS`` rather than removed after
the first response: browsers and download managers request the same URL
several times (parallel ranges, retries, resume). Expired archives are removed
by the next build; a stopped sandbox drops them with the container. Contents mirror the
Results listing: hidden files, noise directories and symlinks are skipped, and
every file must resolve inside the workspace.
"""

import base64
import json
import re
import shlex

# Uncompressed size limit for one download.
ZIP_MAX_BYTES = 200 * 1024 * 1024
ZIP_MAX_PATHS = 5000
ZIP_TTL_SECONDS = 15 * 60
ZIP_TMP_DIR = '/tmp'
ZIP_ID_RE = re.compile(r'^[0-9a-f]{32}$')
# Same pruned directories as the ``/files`` listing.
ZIP_SKIP_DIRS = (
    '.git',
    'node_modules',
    '__pycache__',
    '.venv',
    '.cache',
    '.ipynb_checkpoints',
)


def zip_path(zip_id: str) -> str:
    return f'{ZIP_TMP_DIR}/tm-zip-{zip_id}.zip'


ZIP_SCRIPT = r"""
import base64, glob, json, os, sys, time, zipfile
a = json.loads(base64.b64decode(sys.argv[1]))
root = os.path.realpath(a['root'])
skip = set(a['skip'])
for old in glob.glob(os.path.join(a['tmp'], 'tm-zip-*.zip*')):
    try:
        if time.time() - os.path.getmtime(old) > a['ttl']:
            os.remove(old)
    except OSError:
        pass

def inside(path):
    real = os.path.realpath(path)
    return real == root or real.startswith(root + os.sep)

def visible(path):
    rel = os.path.relpath(path, a['root'])
    return not any(p.startswith('.') or p in skip for p in rel.split(os.sep))

files = {}
def add(path):
    if os.path.islink(path) or not os.path.isfile(path):
        return
    if inside(path) and visible(path):
        files[os.path.relpath(path, a['root'])] = path

for path in a['paths']:
    if os.path.islink(path) or not inside(path):
        continue
    if os.path.isdir(path):
        for d, dirs, names in os.walk(path):
            dirs[:] = sorted(
                n for n in dirs
                if not n.startswith('.') and n not in skip
                and not os.path.islink(os.path.join(d, n))
            )
            for n in sorted(names):
                if not n.startswith('.'):
                    add(os.path.join(d, n))
    else:
        add(path)

if not files:
    print(json.dumps({'error': 'empty'}))
    sys.exit(0)
total = sum(os.path.getsize(p) for p in files.values())
if total > a['limit']:
    print(json.dumps({'error': 'too_large', 'size': total, 'count': len(files)}))
    sys.exit(0)
part = a['out'] + '.part'
fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
with os.fdopen(fd, 'wb') as fh, zipfile.ZipFile(
    fh, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
) as zf:
    for rel in sorted(files):
        zf.write(files[rel], rel)
os.replace(part, a['out'])
print(json.dumps({'count': len(files), 'size': total}))
"""


def build_zip_command(
    root: str, paths: list[str], zip_id: str, limit: int | None = None
) -> str:
    """Shell command that builds the archive and prints a one-line JSON result."""
    if limit is None:
        limit = ZIP_MAX_BYTES
    payload = {
        'root': root,
        'paths': paths,
        'out': zip_path(zip_id),
        'tmp': ZIP_TMP_DIR,
        'skip': list(ZIP_SKIP_DIRS),
        'limit': limit,
        'ttl': ZIP_TTL_SECONDS,
    }
    script = base64.b64encode(ZIP_SCRIPT.encode()).decode()
    arg = base64.b64encode(json.dumps(payload).encode()).decode()
    return (
        f'python3 -c "import base64;exec(base64.b64decode(\'{script}\'))" '
        f'{shlex.quote(arg)}'
    )


def parse_zip_result(stdout: str | None) -> dict:
    """Last JSON line printed by ``ZIP_SCRIPT`` ({} when there is none)."""
    for line in reversed((stdout or '').strip().splitlines()):
        try:
            result = json.loads(line)
        except ValueError:
            continue
        if isinstance(result, dict):
            return result
    return {}
