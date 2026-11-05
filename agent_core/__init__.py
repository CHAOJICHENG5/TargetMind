"""agent_core: the interfaces TargetMind's server modules are written against.

TargetMind runs its Chief Scientist and expert agents on an agent runtime
(conversations, tool execution, sandboxes, event streaming) behind these
interfaces. Only the contracts are published here; the runtime itself is part
of the TargetMind platform and is not included in this repository.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Protocol

__all__ = [
    'ADMIN',
    'USER_CONTEXT_ATTR',
    'AgentDefinition',
    'Base',
    'DefaultUserAuth',
    'InjectorState',
    'SandboxLimits',
    'SandboxRecord',
    'SandboxService',
    'UserAuth',
    'depends_db_session',
    'depends_httpx_client',
    'get_global_config',
    'get_sandbox_service',
    'utc_now',
    'valid_sandbox',
]


# ------------------------------------------------------------------ agents
class AgentDefinition(Protocol):
    """A sub-agent (expert) the main agent can delegate to with ``task``."""

    name: str
    description: str
    system_prompt: str
    tools: list[str]
    max_iteration_per_run: int


# ------------------------------------------------------------------ sandboxes
@dataclass(frozen=True)
class SandboxLimits:
    """Resources of one sandbox container (CPU, memory, shm, pids)."""

    cpus: str = ...  # type: ignore[assignment]
    memory: str = ...  # type: ignore[assignment]
    shm_size: str = ...  # type: ignore[assignment]
    pids: int = ...  # type: ignore[assignment]


class SandboxRecord(Protocol):
    """A running or paused sandbox owned by one user."""

    id: str
    created_by_user_id: str | None
    status: str


class SandboxService(Protocol):
    """Creates, reuses, pauses and stops the per-user sandboxes."""

    limits: SandboxLimits

    async def stop_idle_sandboxes(self, idle_minutes: int) -> list[str]: ...

    async def get_sandbox(self, sandbox_id: str) -> SandboxRecord | None: ...


# ------------------------------------------------------------------ auth
ADMIN: Any = ...
"""User context with access to every user's data (webhooks, maintenance)."""

USER_CONTEXT_ATTR: str = ...  # type: ignore[assignment]
"""Request-state attribute that carries the resolved user context."""


class UserAuth(ABC):
    """Resolves the acting user of a request."""

    @abstractmethod
    async def get_user_id(self) -> str | None: ...

    @classmethod
    @abstractmethod
    async def get_instance(cls, request: Any) -> 'UserAuth': ...


class DefaultUserAuth(UserAuth, ABC):
    """Single-user fallback used when platform accounts are disabled."""


# ------------------------------------------------------------------ app wiring
class InjectorState(Protocol):
    """Per-request dependency-injection state."""


class Base:
    """Declarative base of the platform's SQL models."""


def get_global_config() -> Any:
    """Platform configuration (persistence directory, web URL, services)."""
    raise NotImplementedError


def get_sandbox_service(state: InjectorState) -> AsyncIterator[SandboxService]:
    """Sandbox service bound to the acting user."""
    raise NotImplementedError


def depends_db_session() -> Any:
    """FastAPI dependency: an async database session."""
    raise NotImplementedError


def depends_httpx_client() -> Any:
    """FastAPI dependency: the shared async HTTP client."""
    raise NotImplementedError


async def valid_sandbox(request: Any) -> SandboxRecord:
    """FastAPI dependency: the sandbox authenticated by its session key."""
    raise NotImplementedError


def utc_now() -> datetime:
    """Current time, timezone-aware UTC."""
    raise NotImplementedError
