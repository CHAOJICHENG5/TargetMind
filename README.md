<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/targetmind-lockup-dark.svg">
  <img src="assets/targetmind-lockup.svg" alt="TargetMind" width="440">
</picture>

<br>
<br>

**A multi-agent AI system for therapeutic target discovery**

*A virtual target review board, built from AI experts.*

<br>

<a href="https://www.lilab-ecust.cn/targetmind/"><b>🌐&nbsp; Website</b></a>
&nbsp;&nbsp;·&nbsp;&nbsp;
<a href="https://www.lilab-ecust.cn/targetmind/"><b>📝&nbsp; Request access</b></a>
&nbsp;&nbsp;·&nbsp;&nbsp;
<a href="#virtual-roundtable-deliberation"><b>🧭&nbsp; How it deliberates</b></a>
&nbsp;&nbsp;·&nbsp;&nbsp;
<a href="#expert-workflows"><b>🧪&nbsp; Workflows</b></a>

<br>
<br>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](#quick-start)
[![Node.js](https://img.shields.io/badge/Node.js-22-5FA04E?style=flat-square&logo=nodedotjs&logoColor=white)](#quick-start)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](#quick-start)
[![FastAPI](https://img.shields.io/badge/FastAPI-service-009688?style=flat-square&logo=fastapi&logoColor=white)](#quick-start)
[![Docker](https://img.shields.io/badge/Docker-sandboxed%20agents-2496ED?style=flat-square&logo=docker&logoColor=white)](#quick-start)
<br>
[![Agents](https://img.shields.io/badge/agents-Chief%20Scientist%20%2B%204%20experts-0E7490?style=flat-square)](#the-expert-panel)
[![Consensus](https://img.shields.io/badge/consensus-evidence--gap--guided-2A9D8F?style=flat-square)](#evidence-gap-guided-consensus)
[![Website](https://img.shields.io/badge/website-lilab--ecust.cn%2Ftargetmind-1E3A5F?style=flat-square&logo=googlechrome&logoColor=white)](https://www.lilab-ecust.cn/targetmind/)
[![Access](https://img.shields.io/badge/access-by%20application-3D7A8C?style=flat-square)](https://www.lilab-ecust.cn/targetmind/)
[![License](https://img.shields.io/badge/license-all%20rights%20reserved-555555?style=flat-square)](LICENSE)

</div>

<br>

## Overview

Finding a new therapeutic target remains one of the hardest steps in drug
development. The evidence exists — in genetics, omics, the literature and
pharmacology — but it is fragmented, and turning it into a defensible decision has
depended on multidisciplinary experts integrating it by hand.

**TargetMind** is a multi-agent AI system that introduces a **virtual roundtable
deliberation mechanism** to emulate the cross-examination dynamics of a real-world
target review board. Independent domain-expert agents evaluate every candidate from
their own discipline, and an **evidence-gap-guided consensus framework** makes them
debate and resolve cross-disciplinary contradictions before a target is ranked. The
result is a transparent target-selection funnel that converts scarce expert-level
judgment into an **autonomous, scalable and fully traceable** discovery process.

<div align="center">
<br>
<img src="assets/expert-panel.webp" alt="A Chief Scientist and four domain-expert agents deliberating over structural, single-cell, genetic and membrane-target evidence" width="600">
<br>
<sub>The virtual roundtable: a Chief Scientist convenes four independent domain experts.</sub>
<br>
<br>
</div>

<br>

## Why TargetMind

> Approved drugs act on only about **854 human protein targets**, and only around
> **one in five** newly approved drugs engages a genuinely novel one. Some **92%** of
> more than 17,000 characterised diseases — and about **95%** of rare diseases — still
> have no FDA-approved treatment.

The data to change this already exists at unprecedented scale — over **40 million**
literature records, **6.5 million** omics samples and **20.3 million** bioactivity
measurements. What is missing is the step from raw data to causal, druggable and
safe targets, and the judgement it takes to get there:

- **Causality matters.** Across more than 28,000 prematurely terminated clinical
  trials, programmes without causal human genetic support were markedly more likely
  to fail for lack of efficacy.
- **Associations are not decisions.** Most computational methods stop at statistical
  association, without systematic assessment of causal role, tractability or safety.
- **Black boxes do not translate.** Ranked lists without traceable mechanistic
  reasoning are hard to act on.
- **Linear AI pipelines hallucinate.** LLMs and early agents process evidence in a
  single pass; with no mechanism to resolve conflicts, they inherit prior-knowledge
  bias and lack the dialectical rigour that high-stakes target triage requires.

<br>

## From linear pipelines to deliberation

| | Conventional pipelines and single agents | **TargetMind** |
|:--|:--|:--|
| **Reasoning** | One pass, one perspective | Independent expert evaluations, then structured deliberation |
| **Conflicting evidence** | Averaged, ignored or hidden | Classified, debated and resolved explicitly |
| **Missing evidence** | Silently treated as absence | Named as an evidence gap and filled by targeted retrieval |
| **Bias control** | Prior knowledge dominates | Blinded, mutually independent expert assessments |
| **Output** | A ranked list | A candidate × dimension matrix with reasons for and against every target |
| **Traceability** | Limited | Every claim linked to its PMID, dataset, study or variant |
| **Novelty** | Favours well-studied genes | Prioritises underexplored targets with robust disease-linked support |

<br>

## Virtual roundtable deliberation

TargetMind is organised like a target review board: a Chief Scientist chairs the
session, domain experts bring their own evidence, and a target is ranked only when
its evidence holds up under cross-examination.

**1 · Candidate nomination** — Knowledge-graph link prediction is combined with
explicit reasoning rules over human genetics and disease biology to nominate an
unbiased pool of candidate targets.

**2 · Independent, blinded evaluation** — Experts in genetics, disease biology,
omics and medicinal chemistry assess the candidates in parallel and independently of
one another, guarding against confirmation bias and anchoring on a single line of
evidence.

**3 · Evidence-gap-guided consensus** — The Chief Scientist confronts the expert
verdicts and resolves them through the consensus framework below.

**4 · Adjudication and ranking** — Targets that survive deliberation are ranked on a
candidate × dimension matrix and written up with their evidence, risks and open
questions.

### Evidence-gap-guided consensus

At the core of the system, every expert finding is placed in one of three categories:

| Category | Meaning | What the board does |
|:--|:--|:--|
| 🟢 **Aligned evidence** | Independent disciplines agree | Carried forward as support for the target |
| 🔴 **Critical risk** | A finding that could invalidate the target, such as a contrary causal direction or a safety liability | Weighed explicitly; the target is down-ranked or rejected with the reason recorded |
| 🟡 **Resolvable gap** | Evidence that is missing or conflicting but obtainable | Triggers **targeted orthogonal retrieval** and **cross-domain review** by the relevant experts |

Disagreement becomes a signal rather than noise: each round of deliberation either
closes a gap or exposes a risk, so the final ranking reflects evidence that has been
challenged from more than one discipline.

<br>

## The target selection funnel

| Stage | Question the board answers |
|:--|:--|
| **Disease grounding** | Which disease, under which ontology identifiers — and which related diseases, traits and indications inform it? |
| **Candidate nomination** | Which genes do genetics, disease association and the knowledge graph point to? |
| **Evidence completion** | Is there human genetic support, disease-relevant expression in matched tissue, and causal perturbation evidence? |
| **Novelty screen** | Is the target already established — in the literature, in the clinic, or as a classic disease marker? |
| **Multi-dimensional evaluation** | Is it causal, expressed where it matters, tractable and safe? |
| **Consensus and ranking** | Where do the experts agree, where do they not, and what would change the verdict? |

<br>

## Features

**Expert-level collaboration**

- **A review board, not a chatbot.** A Chief Scientist and four domain experts with
  distinct responsibilities; experts in the same phase run in parallel and never
  redo one another's analysis.
- **Dialectical rigour.** Contradictions are surfaced, debated and resolved rather
  than averaged away; a focused follow-up round addresses decisive gaps.
- **Phased, auditable reasoning.** A live research plan shows each stage of the
  funnel as it happens.

**Evidence you can trace**

- **Independent evidence lines.** Human genetics, expression in matched patient
  tissue and causal perturbation studies are collected separately; a novel candidate
  advances only when at least two lines support it.
- **Novelty by design.** Literature co-occurrence, clinical-stage drugs of the
  disease and related indications, trial registries and classic disease markers
  separate *known* targets from *emerging* and *novel* ones.
- **Every claim cites its source.** PMIDs, dataset accessions, study and variant
  identifiers, and the data versions behind each table.
- **Hallucination-resistant by construction.** Conclusions are drawn from retrieved
  primary data and literature and cross-checked by other disciplines — never from
  recalled knowledge alone.

**Research-grade infrastructure**

- **Integrated biomedical knowledge.** Target–disease associations, human genetics,
  expression atlases, knowledge graphs, pathways, clinical pipelines and the
  biomedical literature, queried directly by the experts.
- **Real analysis, not summaries.** Each expert runs code in an isolated sandbox with
  Python and R scientific stacks — differential expression, enrichment, genetic
  evidence review, structural and ligand analysis.
- **A research workspace.** Ontology-grounded disease search, live expert status, and
  every result as a file — tables, code, figures, reports and interactive 3D
  structures.

<br>

## The expert panel

| Agent | Evidence dimension | What it delivers |
|:--|:--|:--|
| 🧑‍🔬 **Chief Scientist** | Chairs the roundtable | Research plan, candidate nomination, novelty screen, consensus, final report |
| 🧬 **Genetics** | Human genetics and gene constraint | GWAS and credible sets, rare-variant and Mendelian evidence, direction of effect, loss-of-function intolerance |
| 🔬 **Disease Biology** | Mechanism and causality | Knockout, knock-down, overexpression and pharmacological studies in disease models; pathway and cell-type context |
| 📊 **Omics** | Expression and clinical relevance | Differential expression across curated human datasets, cell-type attribution, association with disease severity |
| 💊 **Medicinal Chemistry** | Druggability and safety | Tractability, known ligands and potency, structural pockets, tissue-safety profile |

<br>

## Expert workflows

<details open>
<summary><b>Scenario 1 — Discovering novel targets for a fibrotic disease</b></summary>

<br>

> *"Find novel therapeutic targets for renal fibrosis and give me a ranked report."*

1. **Disease grounding.** The Chief Scientist anchors the disease to its ontology
   identifiers and decides, from the disease's own evidence base, which related
   diseases, quantitative traits and indications should inform the search.
2. **Candidate nomination.** Genetic association, GWAS signals and knowledge-graph
   link prediction propose several hundred candidate genes.
3. **Independent evidence completion.**
   - *Omics* selects human kidney datasets with matched compartments and runs
     differential expression.
   - *Genetics* reviews each candidate's human genetic support and direction of
     effect.
   - *Disease Biology* collects perturbation studies across the standard injury
     models.
4. **Novelty screen.** Genes backed by two or more independent lines are checked
   against the literature and clinical pipelines; established targets are set aside
   with the reason recorded.
5. **Roundtable evaluation.** All four experts score the shortlist from their own
   dimension; aligned evidence, critical risks and resolvable gaps are separated, and
   gaps trigger a targeted follow-up.
6. **Report.** A ranked list with the evidence for and against each target, points of
   disagreement, limitations and recommended next experiments.

</details>

<details>
<summary><b>Scenario 2 — Pressure-testing targets a team already has in mind</b></summary>

<br>

> *"We are considering three genes for hypertrophic cardiomyopathy. Evaluate them."*

1. The Chief Scientist skips nomination and resolves the named genes and the
   disease's related indications.
2. A novelty screen places each gene on the known / emerging / novel spectrum and
   flags clinical programmes that already act on it.
3. The four experts evaluate every gene independently — expression in patient
   tissue, human genetic evidence and constraint, causal studies in disease models,
   tractability and safety liabilities.
4. The board reconciles the verdicts and reports, per gene and dimension, the
   decisive evidence and what would change the conclusion.

</details>

<details>
<summary><b>Scenario 3 — Asking a single, focused question</b></summary>

<br>

> *"What is the human genetic evidence linking this gene to chronic kidney disease?"*

The Chief Scientist recognises a one-dimension question and routes it to exactly one
expert — here *Genetics* — which returns the strongest associations, credible sets,
rare-variant evidence and direction of effect, each with its source.

</details>

<br>

## Validation

TargetMind was evaluated both computationally and at the bench.

- **Benchmarking.** In target-focused reasoning, TargetMind significantly
  outperforms state-of-the-art biomedical agents, while uniquely prioritising highly
  underexplored targets with robust disease-linked support.
- **Wet-lab validation** in three diseases with high translational failure rates and
  no curative options:

| Disease | Validation |
|:--|:--|
| **Renal fibrosis** | A novel target for first-in-class therapy, validated in murine models, non-human primates and human clinical samples |
| **Autosomal dominant polycystic kidney disease (ADPKD)** | One inhibition target and one activation target, validated *in vitro* and *in vivo* |
| **Hypertrophic cardiomyopathy (HCM)** | One inhibition target, validated *in vitro* and *in vivo* |

Together these results close the loop from autonomous computational triage to
experimental confirmation, establishing a hallucination-resistant paradigm for
AI-driven, first-in-class target discovery.

<br>

## Data foundation

| Domain | Sources |
|:--|:--|
| Target–disease association | Open Targets Platform — association scores, clinical candidates, credible sets |
| Human genetics | GWAS Catalog · gnomAD constraint · HGNC nomenclature |
| Expression | GTEx · Human Protein Atlas (single-cell types and tissues) · GEO series |
| Knowledge graph | PrimeKG knowledge-graph embeddings |
| Pathways | MSigDB Hallmark · Reactome · GO Biological Process · KEGG |
| Chemistry and structure | ChEMBL · PubChem · Protein Data Bank · UniProt |
| Literature and trials | PubMed · ClinicalTrials.gov |

<br>

## Quick start

**Requirements** — Python 3.12 · Node.js 22 · Docker · PostgreSQL 16

```bash
git clone https://github.com/CHAOJICHENG5/TargetMind.git
cd TargetMind

# 1. Python environment and agent tools
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Platform service
uvicorn targetmind.server.app:app --host 0.0.0.0 --port 12000

# 3. Web workspace
cd frontend
npm install
npm run dev          # http://localhost:3001
```

The agent tools also run on their own:

```bash
python sandbox/tools/tm_lit.py --help        # literature search
python sandbox/tools/tm_discover.py --help   # candidate pool, evidence matrix, shortlist
```

<div align="center">
<br>
<img src="assets/disease-search.webp" alt="TargetMind workspace: ontology-grounded disease search" width="820">
<br>
<sub>Start from a disease: search is grounded in EFO / MONDO ontology identifiers.</sub>
</div>

<br>

## Access

TargetMind is open to research groups by application. Visit the
**[TargetMind website](https://www.lilab-ecust.cn/targetmind/)** to learn more and
request an account; approved applicants receive their sign-in details by email.

<br>

## License

Copyright © 2026 TargetMind. All rights reserved. See [LICENSE](LICENSE).
