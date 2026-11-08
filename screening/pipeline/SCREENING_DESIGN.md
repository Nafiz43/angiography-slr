# Stage-1 screening: design, numbers, and how to reproduce

Last run 2026-08-31, `qwen3.8:27b`, 8,605 s on sugaree.

## Why there is a phase 0

The original flow had two gates and ran the exclusion gate **only** on records that
had already passed inclusion. An editorial fails the inclusion criteria
immediately, since it reports no computational task and no evaluation against
data, so editorials were being excluded but recorded as *inclusion* failures.

Across the whole previous run the exclusion gate was consulted 127 times and
**E2 (non-research document type) never fired once**. PRISMA reported 3 records
excluded on exclusion criteria, which understated what those criteria do.

PubMed already records a `PublicationType` for every indexed article. When that
field says `Editorial` or `Published Erratum`, it *is* the answer to E2. Asking a
27B model to infer it from prose is strictly worse than reading the field.

## The three phases

`03b_stage1_prefiltered.py` reuses the prompts and gate plumbing from
`03_stage1_screening.py` verbatim, so criteria wording is unchanged.

| Phase | What runs | On which records |
|---|---|---|
| 0 | Deterministic metadata rule, no LLM | all 5,064 |
| 1 | Inclusion gate I1-I4, LLM | unflagged only (4,961) |
| 2 | Exclusion gate E1-E3, LLM | phase-1 survivors **+** every flagged record (241) |

**Phase 0 flags** a record when either fires:
- **E2** — PubMed `PublicationType` intersects the hard set: Editorial, Letter,
  Comment, Published Erratum, Retraction of Publication, Retracted Publication,
  Expression of Concern, News, Newspaper Article, Biography, Autobiography,
  Interview, Address, Patient Education Handout, Bibliography.
- **E1** — no abstract could be retrieved from any source. This review treats
  such a record as an abstract-only publication. That is a design choice, not a
  fact about the record; it is stated in the methods.

**Flagged records skip phase 1 entirely.** A record excluded for what it *is*
does not need judging for what it *says*, so running an erratum through criteria
about imaging modality and quantitative evaluation is incoherent as well as
wasteful. They go straight to phase 2 so they are counted in the exclusion row
of the PRISMA flow rather than absorbed into the inclusion row.

**The deterministic code is ORed with the model verdict, never replaced by it.**
The model may add a further reason (a non-English editorial picks up E3) but
cannot overturn one established from metadata. Without the OR, a model reading an
abstract-less erratum could answer "no criterion triggered" and the record would
come out INCLUDED having never faced the inclusion gate at all.

## Numbers

```
identified from databases          5,829   (PubMed 4,071, Semantic Scholar 1,758)
duplicates removed                   765
records screened                   5,064

phase 0  pre-filtered                103   E1 47, E2 95
phase 1  assessed                  4,961
         failed inclusion          4,823   I1 4,146  I2 4,447  I3 1,097  I4 909
         passed                      138
phase 2  assessed                    241   138 from phase 1 + 103 from pre-filter
         excluded                    107   E1 50, E2 96, E3 1
included for full text               134
                                           4,823 + 107 + 134 = 5,064
```

Criterion counts sum past their totals because one record can trigger several,
typically an erratum that also has no retrievable abstract.

Against the previous run: included 124 → 134 (123 kept, 11 added, 1 dropped,
R3960). Exclusion-stage exclusions 3 → 107.

## Two things the methods section must say

**Abstract coverage bounds the screen.** 5,017 of 5,064 records have an abstract
(99.07%), after automated backfill recovered 62 and 47 were entered by hand.
**Five of the 11 newly included studies exist only because of the hand-entered
abstracts** (R1725, R3707, R3710, R4468, R4475) — on their titles alone they had
been rejected. The 47 still without one are all excluded records, 38 of them
document types that carry no abstract by construction.

**The gate is not bit-reproducible.** Seven records flipped verdict with
byte-identical abstracts: same model, same prompts, `temperature=0`. GPU
inference nondeterminism moved **13 of 4,961 records, 0.26%**. State that figure
rather than implying determinism; anyone rerunning the code will see it.

**Pre-filter reach is bounded.** Publication types resolved for 4,265 of 5,064
records (84.2%). The rest have no PubMed presence, receive no deterministic flag,
and are screened by the model alone.

## Open decision

The written E2 criterion also names reviews, meta-analyses and case reports.
Those are **not** deterministic here. PubMed types 592 records that way
(Review 499, Systematic Review 57, Case Reports 33, Meta-Analysis 28), so making
them deterministic would be a far larger and more consequential sweep. Left to
the model pending Dr. Goldman's call. Flipping it is a one-line change: move
`E2_SOFT` into `E2_HARD` in `03a_pubtype_prefilter.py` and rerun.

## Reproducing

```bash
cd AngioVision/review-paper

# 1. publication types (cached in pubtype_pmids.json / pubtype_by_pmid.json;
#    a second run costs nothing)
python3 03a_pubtype_prefilter.py --fetch --report

# 2. the three-phase screen (resumable per record; run it under tmux)
python3 03b_stage1_prefiltered.py

# 3. the PRISMA figure — reads every number from the run output and
#    asserts the three buckets sum to the record count before drawing
python3 analysis/09_prisma_prefiltered.py
```

## Files

| Path | What |
|---|---|
| `03b_stage1_prefiltered.py` | the three-phase pipeline |
| `03a_pubtype_prefilter.py` | PMID resolution + PublicationType fetch, cached |
| `analysis/09_prisma_prefiltered.py` | PRISMA figure generator |
| `results/stage1_prefiltered.csv` | per-record output, both gates and the phase-0 flag |
| `results/PRISMA_prefiltered.txt` | the flow summary above |
| `results/prisma_prefiltered.{pdf,png}` | the figure |
| `results/stage1_all_5064_with_abstracts_2026-08-30.csv` | screening input, 5,017 abstracts |
| `results/abstracts_manual_filled_2026-08-30.csv` | the hand-entered abstracts |
| `results/stage1_pubtype_e2.csv` | per-record publication type with tier A/B flags |
