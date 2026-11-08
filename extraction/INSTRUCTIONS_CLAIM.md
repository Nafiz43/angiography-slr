# Targeted CLAIM 2024 extraction: per-paper instructions

You are scoring ONE research article against 14 items of the official CLAIM 2024
checklist (Tejani et al., Radiol Artif Intell 2024;6(4):e240300) for a systematic
review of AI methods for angiographic (DSA / X-ray / fluoroscopic) sequence
analysis. Your record ID is given in the task prompt.

## Steps

1. Read `fulltext/<RECORD_ID>.md` completely. Long files: read in chunks until the end.
2. Write `out_claim/<RECORD_ID>.json` in exactly this shape (all 14 keys):

       {"record_id": "<RECORD_ID>",
        "items": {"6":  {"answer": "yes", "quote": "...", "section": "methods"},
                  "9":  {"answer": "no",  "quote": null,  "section": null},
                  ...}}

   Keys: "6", "9", "10", "12", "15", "17", "20", "21", "23", "26", "27", "34", "37", "38".
3. Run `python3 validate_claim.py <RECORD_ID>`. If it reports errors, fix the JSON
   and re-run. Stop after 3 attempts; leave the last version in place.
4. Reply with exactly one line: `<RECORD_ID> OK` or `<RECORD_ID> FAIL: <short reason>`.

Do not read any other paper, any file in `out/` or `out_claim/` other than your
own, or anything outside this repository. Do not edit any existing file.

## Answer rules

- `yes`: the article clearly reports the item. `quote` = the shortest VERBATIM
  span (max 40 words) that shows it; `section` = one of
  `abstract, introduction, methods, results, discussion, conclusion, other`.
- `no`: the item applies but is not reported. `quote` and `section` null.
- `na`: the item does not apply to this study (see per-item notes). `quote` and
  `section` null. Use `na` only where the notes allow it.
- Use only what the article states. Do not infer from general knowledge of a
  method, dataset or venue. Partial reporting that covers the core of the item
  counts as `yes`; a passing mention that gives the reader nothing to reproduce
  counts as `no`.

## Items (official CLAIM 2024 wording, shortened; notes are ours)

- **6 Study goal.** Describe the study's design and goals (e.g. model creation,
  exploratory, feasibility, noninferiority); for classification, the intended
  use (triage, diagnosis, screening, prognosis, ...); the type of predictive
  modeling and target of predictions. `yes` if the paper states what kind of
  study it is and what the model is for. Never `na`.
- **9 Data preprocessing.** Preprocessing steps reproducible by others:
  normalization, resampling/resizing, bit depth, window/level, rescaling,
  thresholding, outlier removal, software used. Never `na`.
- **10 Selection of data subsets.** Whether investigators selected subsets of the
  raw data during preprocessing (subset of images/frames, cropped regions,
  extracted report segments) and how. For sequence data, frame selection,
  key-frame picking or cropping counts. `no` if data selection is not described.
  Never `na`.
- **12 Missing data.** How missing data were handled (exclusion, imputation,
  proxy values). `yes` only if missing/incomplete data handling is described
  (e.g. "cases with incomplete runs were excluded"). Never `na`.
- **15 Rationale for choosing the reference standard.** Why this reference
  standard was chosen over alternatives, or its potential errors, biases or
  limitations. `na` only if the study has no reference standard at all
  (e.g. purely unsupervised enhancement with no-reference evaluation).
- **17 Annotation of test set.** How the test set was annotated, in enough
  detail to replicate: instructions, annotation software (and version),
  manual/semi-automatic/automatic labeling, labels mined from reports/EHR.
  `na` only if there is no annotated test set.
- **20 Level at which partitions are disjoint.** States the level (patient,
  study, series, sequence, image/frame) at which train/test sets are disjoint.
  `na` only if there is no data partitioning (no learned model evaluated on
  held-out data).
- **21 Intended sample size.** Size of the test set AND how it was determined
  (power calculation, justification, or established benchmark split). Stating
  only the number of test cases is `no`. `na` only if there is no test set.
- **23 Software libraries, frameworks, packages.** Names of the
  libraries/frameworks used for training and inference (e.g. PyTorch,
  TensorFlow, MONAI). Version numbers are encouraged but naming the framework
  counts as `yes`. Never `na`.
- **26 Method of selecting the final model.** Method and metric used to select
  the final/best model among those trained (e.g. best validation Dice,
  early-stopping checkpoint by validation loss). `na` only if no model was
  trained (e.g. a fixed non-learning algorithm).
- **27 Ensembling technique.** If the final algorithm is an ensemble, each
  component and how outputs are combined. `na` if the final algorithm is not an
  ensemble. `no` if it is an ensemble but the combination is not described.
- **34 Clinical trial registration.** Registration number in a public registry
  (ClinicalTrials.gov, WHO registries). `na` unless the study is a prospective
  clinical trial or prospective interventional study.
- **37 Performance metrics and measures of statistical uncertainty.** The final
  model's performance reported on all data partitions and datasets used,
  benchmarked against the reference standard (test results alone count as
  `yes` if every test dataset is reported). Never `na`.
- **38 Estimates of diagnostic performance and their precision.** For
  classification/detection tasks: diagnostic accuracy estimates WITH measures
  of uncertainty (95% CI, bootstrap CI, SD across folds), or ROC/calibration
  analysis. `na` for tasks that are not classification or detection (e.g. pure
  segmentation, enhancement, registration).
