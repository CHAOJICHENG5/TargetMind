"""Which sandboxes a user is looking at right now.

The conversation page sends a heartbeat while it is the visible browser tab
(``POST /api/v1/app-conversations/{id}/viewing``). The idle reaper and the
capacity eviction treat a sandbox viewed within their idle window as active,
so a finished conversation someone is reading is not stopped under them.
In-process state: the app server runs as a single process.
"""

from __future__ import annotations

from datetime import datetime

from agent_core import utc_now

_last_viewed: dict[str, datetime] = {}


def mark_viewed(sandbox_id: str, when: datetime | None = None) -> None:
    _last_viewed[sandbox_id] = when or utc_now()


def last_viewed(sandbox_id: str) -> datetime | None:
    return _last_viewed.get(sandbox_id)


def forget(sandbox_id: str) -> None:
    _last_viewed.pop(sandbox_id, None)
