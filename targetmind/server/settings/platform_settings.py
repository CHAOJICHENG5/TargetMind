"""Platform-managed settings for TargetMind accounts.

Everything that changes how tasks run (LLM and its key, agent, condenser,
verification, MCP, skills, sandbox grouping and image) is platform
configuration. It lives in the persistence root's ``settings.json`` (edited by
operators on the host, see ``ops/platform-settings.md``) and applies to every
account, admins included. Accounts only own the personal preferences in
``USER_OWNED_SETTINGS``; their ``users/<id>/settings.json`` stores nothing else.
"""

from __future__ import annotations

import re
from typing import Any

# Fields an account may change (Preferences page); everything else comes from
# the platform settings file.
USER_OWNED_SETTINGS: tuple[str, ...] = (
    'language',
    'enable_sound_notifications',
    'user_consents_to_analytics',
)

PLATFORM_SETTINGS_PATH = 'settings.json'

# Write endpoints that would change platform configuration (LLM profiles,
# secrets injected into sandboxes, skill marketplaces). Refused for every
# account; operators edit the platform settings file instead.
PLATFORM_LOCKED_API = re.compile(
    r'^/api/v1/('
    r'settings/profiles(/.*)?'
    r'|secrets(/.*)?'
    r'|skills/marketplace-skills'
    r')$'
)
LOCKED_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def is_platform_locked(method: str, path: str) -> bool:
    return method.upper() in LOCKED_METHODS and bool(PLATFORM_LOCKED_API.match(path))


def user_owned_fields(data: dict[str, Any]) -> dict[str, Any]:
    """The personal-preference subset of a settings dict."""
    return {key: data[key] for key in USER_OWNED_SETTINGS if key in data}


def disallowed_settings_keys(payload: dict[str, Any]) -> list[str]:
    """Keys of a ``POST /api/v1/settings`` payload an account may not change."""
    return sorted(key for key in payload if key not in USER_OWNED_SETTINGS)
