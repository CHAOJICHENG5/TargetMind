"""TargetMind system prompt.

Replaces the agent runtime's general-purpose coding-assistant prompt (static part) for
default agents. Per-conversation context — the disease workspace, the task
folder, skills, secrets, date — is still appended as the dynamic suffix.
"""

import re

from targetmind.server.agents.experts import expert_roster
from agent_core import SandboxLimits

_DISEASE_TITLE = re.compile(
    r'^Target disease:\s*(?P<name>.+?)\s*\((?P<ids>[^)]*)\)\s*$'
)

_PROMPT = '[redacted]'


def targetmind_system_prompt() -> str:
    limits = SandboxLimits()
    memory = limits.memory.upper().replace('G', ' GB').replace('M', ' MB')
    return _PROMPT.format(cpus=limits.cpus, memory=memory, roster=expert_roster())


def disease_context_block(title: str | None) -> str | None:
    """<DISEASE_WORKSPACE> block from the start title the home page sends
    ("Target disease: <name> (EFO: EFO_x, MONDO: MONDO_y)")."""
    match = _DISEASE_TITLE.match(title or '')
    if not match:
        return None
    ids = [part.strip() for part in match['ids'].split(',') if part.strip()]
    lines = [f'Disease: {match["name"]}', *ids]
    return (
        '<DISEASE_WORKSPACE>\n'
        + '\n'.join(lines)
        + '\nThis workspace is dedicated to target discovery for this disease.\n'
        '</DISEASE_WORKSPACE>'
    )
