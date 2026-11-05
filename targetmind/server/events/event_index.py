"""In-memory index of conversation event files for fast history paging.

Event files are named by event id (not time-sortable), so ordering a
conversation used to mean reading and parsing *every* file on every page
request — O(N) per page, O(N²) for a full history (minutes for a 13k-event
discovery run). The index keeps only ``(timestamp, kind, filename)`` per event
(~200 bytes), is updated incrementally (only files not seen before are read)
and lets a page request parse just the files on that page.

Bounded by ``TM_EVENT_INDEX_MAX_MB`` (default 1024) with least-recently-used
eviction, and entries unused for ``TM_EVENT_INDEX_TTL_MIN`` (default 60) are
dropped. An evicted conversation is simply re-indexed on its next request.
Files that cannot be read yet (e.g. being written by a webhook) are retried on
the next request rather than remembered as missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

_logger = logging.getLogger(__name__)

# (timestamp, filename, kind) — sorts by time, ties broken by filename.
IndexEntry = tuple[str, str, str]

# Rough per-entry overhead of the tuple, its strings and the dict slot.
_ENTRY_OVERHEAD = 200


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def read_event_meta(path: Path) -> tuple[str, str] | None:
    """(timestamp, kind) of an event file, or None if it cannot be read yet."""
    try:
        data = json.loads(path.read_bytes())
        timestamp, kind = data['timestamp'], data['kind']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(timestamp, str) or not isinstance(kind, str):
        return None
    return timestamp, kind


@dataclass
class _ConversationIndex:
    meta: dict[str, tuple[str, str]] = field(default_factory=dict)
    ordered: list[IndexEntry] | None = None
    nbytes: int = 0
    last_used: float = 0.0


def _entry_bytes(name: str, timestamp: str, kind: str) -> int:
    return len(name) + len(timestamp) + len(kind) + _ENTRY_OVERHEAD


def _scan(directory: Path) -> list[str]:
    try:
        with os.scandir(directory) as it:
            return [e.name for e in it if e.is_file()]
    except FileNotFoundError:
        return []


class EventIndexCache:
    def __init__(self, max_bytes: int, ttl_seconds: float):
        self.max_bytes = max_bytes
        self.ttl_seconds = ttl_seconds
        self._indexes: OrderedDict[str, _ConversationIndex] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._total_bytes = 0

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    def __len__(self) -> int:
        return len(self._indexes)

    def _drop(self, key: str) -> None:
        index = self._indexes.pop(key, None)
        if index is not None:
            self._total_bytes -= index.nbytes
        self._locks.pop(key, None)

    def _expire(self, now: float) -> None:
        if self.ttl_seconds <= 0:
            return
        for key in [
            k
            for k, idx in self._indexes.items()
            if now - idx.last_used > self.ttl_seconds
        ]:
            self._drop(key)

    def _evict(self, keep: str) -> None:
        while self._total_bytes > self.max_bytes and len(self._indexes) > 1:
            oldest = next(iter(self._indexes))
            if oldest == keep:
                break
            self._drop(oldest)

    def _refresh(self, directory: Path, index: _ConversationIndex) -> int:
        """Bring the index up to date with the directory; returns byte delta."""
        names = _scan(directory)
        present = set(names)
        delta = 0
        changed = False
        for name in [n for n in index.meta if n not in present]:
            timestamp, kind = index.meta.pop(name)
            delta -= _entry_bytes(name, timestamp, kind)
            changed = True
        for name in names:
            if name in index.meta:
                continue
            meta = read_event_meta(directory / name)
            if meta is None:
                continue  # retried on the next request
            index.meta[name] = meta
            delta += _entry_bytes(name, *meta)
            changed = True
        if changed or index.ordered is None:
            index.ordered = sorted(
                (timestamp, name, kind)
                for name, (timestamp, kind) in index.meta.items()
            )
        return delta

    async def ordered(self, directory: Path) -> list[IndexEntry]:
        """Events of a conversation directory in timestamp order."""
        key = str(directory)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            self._expire(now)
            index = self._indexes.get(key) or _ConversationIndex()
            loop = asyncio.get_running_loop()
            delta = await loop.run_in_executor(None, self._refresh, directory, index)
            index.nbytes += delta
            index.last_used = now
            if key in self._indexes:
                self._indexes.move_to_end(key)
            else:
                self._indexes[key] = index
                self._locks[key] = lock
            self._total_bytes += delta
            self._evict(keep=key)
            return list(index.ordered or [])


EVENT_INDEX = EventIndexCache(
    max_bytes=_env_int('TM_EVENT_INDEX_MAX_MB', 1024) * 1024 * 1024,
    ttl_seconds=_env_int('TM_EVENT_INDEX_TTL_MIN', 60) * 60,
)
