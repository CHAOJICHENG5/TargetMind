"""Per-user lock around "find or create this user's sandbox".

Without it, tasks a user starts at the same moment each see no container yet
and each create one. The asyncio lock serialises requests inside one server
process; the file lock (flock) does the same across worker processes.
"""

import asyncio
import contextlib
import fcntl
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import AsyncIterator

_process_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@contextlib.asynccontextmanager
async def user_sandbox_lock(user_id: str | None) -> AsyncIterator[None]:
    from agent_core import get_global_config

    key = user_id or '_single_user'
    lock_dir = Path(get_global_config().persistence_dir) / 'locks'
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f'sandbox-{hashlib.sha256(key.encode()).hexdigest()[:16]}'

    async with _process_locks[key]:
        with open(lock_path, 'w') as handle:
            await asyncio.to_thread(fcntl.flock, handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
