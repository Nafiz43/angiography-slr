# Angiography SLR

## One repository for the manuscript, data, and code

**This is the canonical, actively maintained repository for the AngioVision systematic literature review. All future manuscript edits, screening updates, extraction corrections, and analysis changes should be made here.**

It brings together the manuscript for *Artificial Intelligence for Angiographic Sequence Analysis: A Systematic Review of Temporal Modeling, Clinical Readiness, and Research Gaps*, its supplementary material, screening decisions, human screening validation, structured study extractions, and the code used to produce the analyses. You do not need to clone or use the former `angiovision-slr-data` repository to work on the paper or regenerate analyses from the committed extraction records.

The repository contains the project's shared manuscript and reproducibility materials. It does **not** distribute copyrighted full-text articles, private credentials, or a complete model runtime. Repeating full-text quotation checks or rerunning external searches requires the additional inputs described below.

## Review scope and current corpus

The review examines computational methods for temporally ordered catheter-based angiographic image sequences, including digital subtraction angiography (DSA) and contrast fluoroscopy. It covers clinical applications, tasks, architectures, temporal modeling, evaluation, reporting, reproducibility, and research gaps.

The current manuscript reports searches of PubMed/MEDLINE and Semantic Scholar through **31 July 2026**:

| Stage | Records | Where to inspect |
| --- | ---: | --- |
| Records retrieved before deduplication | 5,829 | Search log in `06-appendix.tex` |
| Unique records screened | 5,064 | `screening/stage1_llm_decisions.csv` |
| Initial pipeline inclusions | 134 | `llm_decision` in the screening CSV |
| Records independently reviewed by two humans | 491 | `screening/screening_double_annotation.csv` |
| Eligible studies after reviewed screening decisions | 122 | `extraction/manifest.csv` |
| Reports with retrievable full text assessed at full text | 120 | `extraction/out/` + `extraction/out_excluded/` |
| Studies included in synthesis (2 meeting abstracts excluded, 3 earlier versions merged) | 115 | `extraction/out/R*.json` |

The 491-record validation sample contains all 134 pipeline inclusions and 357 sampled exclusions. The final screening decisions incorporate human consensus for sampled records. Eligible records `R4468` and `R4475` have no extraction record because their full texts were not retrievable. These stages have different denominators; 122 eligible reports should not be confused with the 115 studies analyzed. Full-text exclusions and merges are in `extraction/out_excluded/`: R1725 and R2430 are meeting abstracts excluded under E1 at full text; R4154, R2434 and R4671 are earlier versions (preprint or conference paper) of the included journal articles R3555, R1238 and R4479 and are counted once. R4482 was reclassified by the reviewers from `none` to `frame_aggregation` (temporal pooling of frames).

## What is included

| Location | Contents and purpose |
| --- | --- |
| [`00-main.tex`](00-main.tex) | Main manuscript entry point, title, authors, abstract, declarations, bibliography setup, and section inclusion. |
| [`01-intro.tex`](01-intro.tex) | Background, motivation, and review objectives. |
| [`02-methodology.tex`](02-methodology.tex) | Search, eligibility, screening validation, extraction, and statistical methods. |
| [`03-analysis.tex`](03-analysis.tex) | Review results and descriptive analyses. |
| [`04-research_gaps.tex`](04-research_gaps.tex) | Research gaps identified in the review. |
| [`05-discussion.tex`](05-discussion.tex) | Interpretation, limitations, and conclusions. |
| [`06-appendix.tex`](06-appendix.tex) | Database-specific search log, screening prompts, extraction schema description, and availability details. |
| [`references.bib`](references.bib) | Bibliography used by the main manuscript. |
| [`figs/`](figs/) and [`tables/`](tables/) | Committed figures, tables, and supporting summaries for the manuscript. |
| [`supplementary/`](supplementary/) | Separate supplementary LaTeX document, Table S1 screening validation records, and Table S2 PRISMA checklist. |
| [`submission/`](submission/) + [`tools/split_submission.py`](tools/split_submission.py) | `00-main.tex` compiles every upload item in one PDF (manuscript, supplementary Tables S1-S3, cover letter, highlights, abstract, ethics statement). `python3 tools/split_submission.py` rebuilds it and writes the separate upload files to `~/Documents/CBM submission`. Revision edits are wrapped in `\edit{}`; set `\colorlet{editcolor}{black}` in `00-main.tex` before submitting. |
| [`screening/`](screening/) | Screening decisions for all 5,064 records, dual-review annotations, agreement calculation, and search/screening pipeline. |
| [`extraction/`](extraction/) | Extraction instructions, JSON schema, schema generator, validator, study manifest, conversion script, and 115 study-level JSON records (plus 5 excluded or merged reports in `out_excluded/`). |
| [`analysis/`](analysis/) | Scripts for topical, metric, task/architecture, reporting-cluster, overlap, and task-clustering analyses. |
| [`validation/`](validation/) | Original manuscript-side screening agreement script and annotation CSV, retained during consolidation. Use `screening/` for the consolidated screening workflow. |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Additional descriptions of the data files, extraction process, and reproduction dependencies. |

Bundled LaTeX class and style files support typesetting. The root file named `README` and the `Makefile` are ACM template materials; **they are not the project guide or the manuscript build entry point**. This `README.md` is the project guide.

## Working with the manuscript in Overleaf

The manuscript stays at the repository root, with its existing figure, table, and bibliography paths. Data and Python folders can coexist with the manuscript; they are not executed during LaTeX compilation.

1. Use **angiography-slr** as the GitHub repository for the Overleaf project.
2. For an Overleaf project already linked to this repository, open its GitHub synchronization menu and pull the latest changes. Synchronization is manual.
3. For a new project, use **Import from GitHub** and select this repository. GitHub synchronization requires an eligible Overleaf subscription. A downloaded repository ZIP can also be uploaded as a project.
4. Select **`00-main.tex`** as the main document and **pdfLaTeX** as the compiler.
5. Recompile after pulling or editing. The supplementary material is part of `00-main.tex` (after the appendix); `tools/split_submission.py` extracts it as its own PDF.

Before changing files locally, synchronize any pending Overleaf edits back to GitHub and pull them locally. After pushing local changes, pull them into Overleaf. Avoid simultaneous unsynchronized edits to the same files.

Official guidance: [Overleaf GitHub synchronization](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/github-synchronization).

For a local build with Tectonic, run from the repository root:

```bash
mkdir -p output/pdf
tectonic -X compile 00-main.tex --outdir output/pdf --keep-logs
```

The PDF and logs are local build artifacts in `output/pdf/`. Successful compilation does not replace a visual review of layout, references, and warnings.

## Reproducing the analyses

### Set up Python dependencies

From the repository root, create a virtual environment outside the repository and activate it:

```bash
python3 -m venv ../angiovision-slr-venv
source ../angiovision-slr-venv/bin/activate
python -m pip install numpy pandas matplotlib seaborn scipy jsonschema
```

These are the analysis and extraction-validation dependencies. The live search and LLM-screening scripts have additional service and runtime requirements; inspect their source and screening design before rerunning them. Dependency versions are not currently pinned.

### Regenerate figures, tables, and reporting comparisons

```bash
bash analysis/run_all.sh
```

This command:

1. Converts the committed extraction records into analysis-compatible JSONL files under `results/` using `extraction/v2_to_legacy.py`.
2. Runs the figure and table scripts with a noninteractive plotting backend.
3. Writes generated artifacts and individual script logs under `analysis-results/`.
4. Prints reporting-cluster comparisons for studies published up to 2024 versus from 2025 onward, using Fisher's exact tests and Holm correction.

The generated `results/` and `analysis-results/` folders are ignored by Git. **Regeneration does not automatically replace the committed manuscript assets in `figs/` and `tables/`.** Review the generated output and copy the intended assets into the manuscript folders before committing a results update.

### Reproduce screening agreement

```bash
python3 screening/screening_agreement.py
```

The script reads the 491-record annotation CSV, prints reviewer and pipeline agreement statistics, and generates `screening/screening_validation_table.tex`. That generated table is ignored by Git; review it before incorporating it into the manuscript or supplement.

### Inspect or validate study extractions

Start with [`extraction/INSTRUCTIONS.md`](extraction/INSTRUCTIONS.md), [`extraction/schema.json`](extraction/schema.json), and [`extraction/manifest.csv`](extraction/manifest.csv). Study records use stable identifiers such as `R0058` and contain study, imaging, dataset, task, method, evaluation, clinical, reproducibility, research-gap, and reporting-item fields.

For full schema and quotation validation, first supply legally obtained article text as `extraction/fulltext/R####.md`, then run:

```bash
python3 extraction/validate.py R0058
# Or, after supplying the article text for every extraction record:
python3 extraction/validate.py --all
```

The validator checks schema conformance and supporting quotations against those local full texts. Full-text files are not supplied by this repository; do not commit copyrighted article texts when reproducing these checks.

### Search and screening provenance

The exact historical queries and search date are recorded in the manuscript appendix. [`screening/pipeline/SCREENING_DESIGN.md`](screening/pipeline/SCREENING_DESIGN.md) describes the screening workflow. The pipeline includes:

- `02_slr_paper_fetcher.py`: PubMed and Semantic Scholar retrieval; configure `ENTREZ_EMAIL`, `NCBI_API_KEY`, and `S2_API_KEY` as appropriate.
- `03_stage1_screening.py`: inclusion and exclusion prompts and screening implementation.
- `03b_stage1_prefiltered.py`: the final screening variant, including publication-type handling.

The documented screening run used `qwen3.8:27b` through Ollama at temperature 0. Rerunning searches against live databases may return different records from the historical search. The committed screening CSVs preserve the decisions used in this review.

## How to maintain this repository

- Make manuscript changes in the root `.tex` files and update citations in `references.bib`.
- Make screening corrections in the consolidated `screening/` materials, preserving record identifiers and distinguishing pipeline decisions from final reviewed decisions.
- Make extraction corrections in `extraction/out/`, with supporting evidence and validation where the source text is available.
- Regenerate analyses after data corrections, inspect the outputs, and update the relevant manuscript assets and numerical claims together.
- Keep supplementary tables and any retained duplicate validation materials consistent when changing their underlying annotations.
- Use descriptive commits that explain the data or manuscript change. Do not maintain a second active copy in the archived repository.

## Consolidation and historical repository

The reproducibility materials were imported from `Nafiz43/angiovision-slr-data` at commit `9c1c441346224d595fe10e2465b1650e46bf936d`. Imported code and data were verified byte-for-byte; the old README became `REPRODUCIBILITY.md`, and ignore rules were extended for local manuscript builds.

**There is no runtime, build, or data-loading dependency on the old repository.** The manuscript's data-availability links now point here. The former repository is archived and has a redirect to this repository; it is retained only for historical commits and existing external links. Its separate Git history was not merged into this repository. Keeping that archive does not require maintaining two repositories.

Deleting the archive would not remove the imported files here, but it would break its GitHub URLs and remove access to its separate history. Preserve a history backup and account for external citations before considering permanent deletion.

## Known reporting issue requiring reconciliation

The operational reporting-item definitions in `extraction/INSTRUCTIONS.md` differ from the official CLAIM 2024 checklist. The C01--C12 group assignments used by the current analysis are implemented in `extraction/v2_to_legacy.py`; the displayed cluster labels are in `analysis/07_claim_side_by_side_comparison.py`.

Repository consolidation does not resolve this methodological issue or change any scores. Reconcile the operational definitions with the official checklist, reassess affected items, and update the figures, tables, appendix, and manuscript claims together before presenting these results as adherence to the official CLAIM 2024 checklist.
