"""Model capability overrides for the sandboxes' LiteLLM.

The the agent framework agent runtime decides whether a model can see images from LiteLLM's model
map (``supports_vision``). LiteLLM's bundled map does not know new models such
as DeepSeek's native-multimodal V4 flash, so the agent drops every image.

Operators list such capabilities in ``ops/litellm-model-overrides.json`` (path
overridable with ``TM_LITELLM_MODEL_OVERRIDES``). The app server serves
LiteLLM's bundled map plus those entries, and every new sandbox points
``LITELLM_MODEL_COST_MAP_URL`` at it. LiteLLM validates the fetched map (it
must not shrink) and falls back to its bundled copy on any failure, so an
unreachable or broken map only means "no extra capabilities", never a broken
agent. Without an overrides file nothing changes at all.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_MAP_PATH = '/sandbox-assets/litellm-model-map.json'
COST_MAP_URL_VARIABLE = 'LITELLM_MODEL_COST_MAP_URL'
_DEFAULT_OVERRIDES = (
    Path(__file__).resolve().parents[3] / 'ops' / 'litellm-model-overrides.json'
)


def overrides_path() -> Path:
    return Path(os.getenv('TM_LITELLM_MODEL_OVERRIDES') or _DEFAULT_OVERRIDES)


def load_overrides(path: Path | None = None) -> dict[str, dict]:
    """Model entries to add to / merge into LiteLLM's map ({} when none)."""
    path = path or overrides_path()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logger.exception('Ignoring unreadable model overrides %s', path)
        return {}
    if not isinstance(data, dict):
        logger.error('Ignoring model overrides %s: not a JSON object', path)
        return {}
    return {
        name: entry
        for name, entry in data.items()
        if not name.startswith('_') and isinstance(entry, dict)
    }


def overrides_fingerprint(overrides: dict[str, dict] | None = None) -> str | None:
    """Short hash of the overrides (None without overrides)."""
    overrides = load_overrides() if overrides is None else overrides
    if not overrides:
        return None
    payload = json.dumps(overrides, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _bundled_model_map() -> dict:
    from litellm.litellm_core_utils.get_model_cost_map import GetModelCostMap

    return GetModelCostMap.load_local_model_cost_map()


def build_model_map(overrides: dict[str, dict], bundled: dict) -> dict:
    """LiteLLM's bundled map with the override entries merged in."""
    merged = dict(bundled)
    for name, entry in overrides.items():
        merged[name] = {**merged.get(name, {}), **entry}
    return merged


@lru_cache(maxsize=4)
def _model_map_bytes(fingerprint: str | None) -> bytes:
    del fingerprint  # cache key only
    return json.dumps(build_model_map(load_overrides(), _bundled_model_map())).encode()


def model_map_bytes() -> bytes:
    """Serialized map for the sandboxes (cached per overrides version)."""
    return _model_map_bytes(overrides_fingerprint())


def sandbox_model_map_url(host_port: int) -> tuple[str, str] | None:
    """(URL, fingerprint) for new sandboxes, or None without overrides."""
    fingerprint = overrides_fingerprint()
    if fingerprint is None:
        return None
    return (
        f'http://host.docker.internal:{host_port}{MODEL_MAP_PATH}?v={fingerprint}',
        fingerprint,
    )
