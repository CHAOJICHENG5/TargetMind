"""TargetMind expert panel: sub-agent definitions sent to the agent runtime.

The Chief Scientist (main agent) delegates to these experts with the ``task``
tool; several task calls in one turn run in parallel. the agent runtime prepends its own
generic sub-agent prompt, so each definition opens by restating the TargetMind
identity and the expert's scope.
"""

import hashlib
import json

from agent_core import AgentDefinition

# Safety ceiling per dispatch against runaway loops only: experts are not told
# about it and normal briefs stay far below it.
# Experts finish their whole brief in one run instead of being cut off and
# completed by a second batch.
EXPERT_MAX_STEPS = 300
EXPERT_TOOLS = ['terminal', 'file_editor', 'browser_tool_set']
SKILLS_DIR = '/opt/targetmind/skills'
# Experts that complete the evidence matrix in the discovery phase; the others only evaluate.
DISCOVERY_EXPERTS = ('bioinformatics', 'genetics', 'molecular-biology')

_COMMON = '[redacted]'

# Discovery = evidence completion: every expert works on the same candidate pool
# (`tm-discover pool`) and fills the one evidence column databases cannot give.
_DISCOVERY = {
    'bioinformatics': '[redacted]',
    'genetics': '[redacted]',
    'molecular-biology': '[redacted]',
}

_NO_DISCOVERY = '[redacted]'

_EXPERTS: dict[str, dict[str, str]] = {
    'molecular-biology': {
        'title': 'Molecular Biology',
        'description': (
            'Disease mechanisms, signalling pathways, cell types and functional '
            'evidence (knockout phenotypes, animal models, perturbation studies).'
        ),
        'skills': 'target-discovery.md, enrichment.md',
        'dimension': 'mechanism and causality',
        'figures': '[redacted]',
        'scope': '[redacted]',
    },
    'genetics': {
        'title': 'Genetics',
        'description': (
            'Human genetic evidence (GWAS, rare variants, Mendelian disease, eQTL) '
            'and gene constraint as a safety signal.'
        ),
        'skills': 'target-discovery.md, genetics-evidence.md',
        'dimension': 'human genetics and gene constraint',
        'figures': '[redacted]',
        'scope': '[redacted]',
    },
    'bioinformatics': {
        'title': 'Bioinformatics',
        'description': (
            'Omics analysis (GEO/TCGA/GTEx differential expression, enrichment, '
            'networks, survival) plus clinical context: trials, biomarkers, patients.'
        ),
        'skills': 'target-discovery.md, geo-deg.md, enrichment.md, survival.md',
        'dimension': 'expression and clinical relevance',
        'figures': '[redacted]',
        'scope': '[redacted]',
    },
    'medicinal-chemistry': {
        'title': 'Medicinal Chemistry',
        'description': (
            '[redacted]'
        ),
        'skills': 'druggability.md',
        'dimension': 'druggability and safety',
        'figures': '[redacted]',
        'scope': '[redacted]',
    },
}


def expert_definitions() -> list[AgentDefinition]:
    definitions = []
    for name, spec in _EXPERTS.items():
        prompt = _COMMON.format(
            name=name,
            title=spec['title'],
            skills_dir=SKILLS_DIR,
            skills=spec['skills'],
            discovery=_DISCOVERY.get(name, _NO_DISCOVERY),
            dimension=spec['dimension'],
            scope=spec['scope'],
            figures=spec['figures'],
        )
        definitions.append(
            AgentDefinition(
                name=name,
                description=spec['description'],
                tools=list(EXPERT_TOOLS),
                system_prompt=prompt,
                max_iteration_per_run=EXPERT_MAX_STEPS,
            )
        )
    return definitions


def experts_fingerprint() -> str:
    """Short hash of the expert definitions. A running agent runtime keeps the
    definitions it registered first, so sandboxes are only reused while this
    matches (changing an expert makes new tasks start a fresh sandbox)."""
    payload = json.dumps(
        [d.model_dump(mode='json', exclude={'source'}) for d in expert_definitions()],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def expert_roster() -> str:
    """One line per expert for the Chief Scientist's prompt."""
    return '\n'.join(
        f'| `{name}` | {spec["title"]} | {spec["description"]} |'
        for name, spec in _EXPERTS.items()
    )
