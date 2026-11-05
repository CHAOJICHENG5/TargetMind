"""Background loop that stops sandbox containers nobody is using.

Stopping (not deleting) frees the container's CPU and memory; its files and
conversation state stay on disk and the owner's next task restarts it.
"""

import asyncio
import logging
from datetime import timedelta

from agent_core import InjectorState
from agent_core import ADMIN, USER_CONTEXT_ATTR

_logger = logging.getLogger(__name__)
CHECK_INTERVAL_SECONDS = 300


async def reap_idle_sandboxes_once() -> list[str]:
    from agent_core import get_sandbox_service
    from agent_core import (
        SandboxService,
    )

    state = InjectorState()
    setattr(state, USER_CONTEXT_ATTR, ADMIN)  # every user's containers
    async with get_sandbox_service(state) as sandbox_service:
        if not isinstance(sandbox_service, SandboxService):
            return []
        minutes = sandbox_service.limits.idle_stop_minutes
        if minutes <= 0:
            return []
        return await sandbox_service.stop_idle_sandboxes(timedelta(minutes=minutes))


async def run_idle_reaper() -> None:
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            await reap_idle_sandboxes_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception('idle sandbox reaper failed')
