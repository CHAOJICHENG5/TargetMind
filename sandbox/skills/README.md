# TargetMind SOPs

Standard procedures read by the Chief Scientist and the experts on demand.
Installed into the sandbox image at `/opt/targetmind/skills/`.

| File | Use |
|---|---|
| data-access.md | Local data first (`tm-data list`; PubMed via `tm-lit`, GWAS, Open Targets, HGNC, gnomAD…), NCBI relay, batching, retries, tested queries |
| disease-context.md | Chief Scientist: proxy traits, KG anchors, related indications; `tm-discover pool` |
| target-discovery.md | Discovery = evidence completion: omics / genetics review / mechanism columns |
| novelty-screening.md | Chief Scientist: `tm-discover merge`, classic markers, `tm-novelty`, shortlist |
| geo-deg.md | Find a GEO dataset and run differential expression |
| enrichment.md | GO / KEGG / Reactome / Hallmark enrichment |
| survival.md | Kaplan-Meier and Cox survival analysis |
| genetics-evidence.md | Human genetic evidence and gene constraint |
| druggability.md | Structure, pockets, ligands, tractability, safety |
| report-template.md | Structure of the final report.md |

Tools (source `sandbox/tools/`):
* `tm-discover` — candidate pool (Open Targets, GWAS Catalog, PrimeKG KGE ensemble),
  genetics evidence table, evidence matrix, shortlist, `gwas` lookup. Reference data:
  read-only mount `/opt/targetmind/data` (`ref/<source>/current/`, versions in `manifest.json`).
* `tm-novelty` — PubMed co-occurrence (local PubMed library), Open Targets clinical
  drugs and classic markers → novelty tier.
* `tm-lit` — literature search on the local PubMed library (PubMed query syntax):
  `search`, `count`, `show`, `info`.
* `tm-data` — which local data exists (`list`, `info <source>`): versions, coverage,
  how to use each source.
