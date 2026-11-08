# Stage-2 full-text extraction: per-paper instructions

You are extracting structured data from ONE research article for a systematic
review of AI methods for angiographic (DSA / X-ray / fluoroscopic) sequence
analysis. Your record ID is given in the task prompt.

## Steps

1. Read `schema.json` (the authoritative field list, types and enums).
2. Read `fulltext/<RECORD_ID>.md` completely. Long files: read in chunks until the end.
3. Write `out/<RECORD_ID>.json`: one JSON object that validates against `schema.json`.
4. Run `python3 validate.py <RECORD_ID>`. If it reports errors, fix the JSON and re-run.
   Stop after 3 attempts; leave the last version in place.
5. Reply with exactly one line: `<RECORD_ID> OK` or `<RECORD_ID> FAIL: <short reason>`.
   Do not summarize the paper in your reply.

Do not read any other paper, any other output file, or anything outside this
repository. Do not edit `schema.json`, `validate.py` or this file.

## Evidence rules

- Use only what the article states. Never infer from general knowledge of a
  method, dataset or venue.
- Unknown or not reported: `null` for scalars, `[]` for lists, `"not_reported"`
  where the enum offers it.
- Every `quote` field must be copied VERBATIM from the article text (the
  validator checks this after normalizing whitespace and case). Max 40 words.
  Pick the shortest span that supports the claim. Do not paraphrase inside quotes.
- `section` fields name where the quote came from: one of
  `abstract, introduction, methods, results, discussion, conclusion, other`.
- Numbers: copy as reported. `value_0_100` rescales fractions (0.91 -> 91.0)
  for percentage-type metrics only (accuracy, Dice, IoU, AUC, sensitivity,
  specificity, precision, recall, F1, kappa); otherwise null.

## Field guidance

### study
`publication_type`: `journal`, `conference_full_paper` (full paper in proceedings,
e.g. MICCAI, SPIE, ISBI), `conference_abstract` (abstract/poster/supplement with no
full methods), `preprint` (arXiv, medRxiv, etc., not peer reviewed), `book_chapter`, `other`.
`text_is_full_paper`: false when the available text is only an abstract or a web
page without methods.

### imaging
`modality`: `DSA`, `xray_fluoroscopy` (non-subtracted X-ray angiography, cine,
fluoroscopy, roadmap), `DSA_and_fluoroscopy` (both used), `other`.
`territory` (pick the main one; `multi` if two or more are central):
`neurologic` (cerebral, spinal, head & neck), `cardiac` (coronary, ventricular),
`aortic_thoracic` (aorta, intercostal, pulmonary, other thoracic),
`abdominopelvic` (hepatic, renal, mesenteric, pelvic, GI bleeding),
`peripheral` (limb arteries/veins), `multi`, `other`, `not_reported`.
`acquisition_geometry`: `monoplane`, `biplane`, `rotational_3D`, `mixed`, `not_reported`.

### dataset
Counts are integers as reported for the main study cohort (sum across sites if
stated). `n_centers` counts distinct institutions contributing images.
`n_vendors` counts distinct scanner manufacturers named. `public_dataset_used`:
a publicly downloadable dataset was used (name it). `data_released`: the authors
release their own data. `split_level`: the unit at which train/test were separated.

### task
`primary_task` must be one of the ten canonical categories:
- `vessel_segmentation`: pixel-wise delineation of vessels or vessel parts.
- `object_detection_localization`: detecting/localizing lesions, stenoses, aneurysms,
  landmarks or anatomical targets (boxes, points, regions).
- `catheter_device_tracking`: segmenting/tracking guidewires, catheters, stents,
  coils or other devices over frames.
- `disease_classification_grading`: classifying or grading disease, stenosis
  severity, view/phase/sequence type, or image category.
- `background_subtraction`: producing DSA-like subtracted images, removing
  bones/soft tissue or motion artifacts in subtraction.
- `image_enhancement_denoising`: denoising, dose reduction, super-resolution,
  frame interpolation, artifact reduction (other than subtraction).
- `temporal_sequence_modeling`: the sequence itself is the object of study
  (phase detection, keyframe selection, sequence-level representation).
- `contrast_flow_analysis`: perfusion, flow velocity, filling time, TIMI frame
  count, hemodynamic parameters from contrast dynamics.
- `motion_correction_registration`: registration between frames/views/modalities,
  motion compensation, 2D/3D registration, 3D reconstruction from projections.
- `outcome_prediction`: predicting a clinical outcome or event (rupture,
  reperfusion, mortality, complications, treatment response).
- `other`: only if none fits; fill `other_label`.
`secondary_tasks`: other canonical categories the study itself performs AND
evaluates or reports results for (never repeat the primary; a component used only
internally, e.g. a segmentation step feeding a classifier with no reported
segmentation result, is not a secondary task).

### method
`architecture_names`: as the authors name them. `architecture_family`: the
dominant family of the PROPOSED model.
`temporal_category` (operational taxonomy; classify the PROPOSED model's use of
time, not the baselines):
- `none`: each frame (or one pooled/MinIP/single image) is processed independently.
- `frame_aggregation`: frames combined by fixed, non-learned operations
  (channel stacking, concatenation, differencing) before a 2D model.
- `optical_flow_registration`: explicit frame-to-frame motion estimation,
  registration, or classical tracking/association across frames.
- `recurrent`: LSTM, GRU, ConvLSTM or other hidden state propagated over frames.
- `cnn3d_video`: 3D/spatiotemporal convolutions or video-level learned representations.
- `transformer_ssm`: self-attention or state-space models across frames.
- `hemodynamic_physics`: explicit physiological/physics models of flow over time
  (reduced-order flow, contrast kinetics, time-density curve modeling).
- `not_determinable`: the text does not let you tell.
Give a quote that shows the mechanism. For `none`, the quote must show that frames
(or a single image) are processed individually; if no sentence shows how frames are
fed to the model, use `not_determinable` instead of guessing `none`.

### evaluation
`validation_design`: the strongest design actually reported:
`internal_split` < `cross_validation` < `external_validation`
(different institution or dataset never seen in training) < `prospective`.
`metrics`: list EVERY numeric performance result for the PROPOSED method
(not baselines) on test/validation data; one entry per metric x task x split,
max 25 entries (keep the headline ones if there are more). Never list the same
metric/value/task/split twice.

### clinical
`study_design`: `retrospective`, `prospective`, `rct`, `mixed`, `not_reported`.

### gaps (G1-G12)
For each gap, set `status`:
- `documents`: the paper itself states this as a limitation, open problem, or
  shortcoming of its own work or of the field.
- `addresses`: the paper's own contribution is a concrete step against this gap
  (e.g. releases a public dataset for G1, validates externally for G2).
- `both`: it does both.
- `none`: neither. Use `none` freely; most papers touch only a few gaps.
For `documents`/`addresses`/`both`, give `quote` + `section`. A study merely
having a small dataset is NOT `documents`; the paper must say so.

- G1 Absence of public benchmarks: small/private/single-center data, no public
  annotated benchmark, cross-study comparison impossible, inconsistent evaluation.
- G2 Generalizability & domain shift: single vendor/site/protocol, failure to
  transfer, synthetic-to-real gap, territory transfer, need for external validation.
- G3 Temporal modeling & video-level analysis: frames treated independently,
  short fixed clips, unmodeled phases, motion treated as noise.
- G4 2D constraints & 3D reconstruction: projection foreshortening/overlap/depth
  loss, single-plane limits, 3D reconstruction or 2D/3D registration difficulty.
- G5 Annotation scarcity & annotation-efficient learning: costly expert labels,
  inter/intra-observer variability, need for semi/self-supervised, active,
  synthetic or weak labels.
- G6 Prospective clinical validation & outcome assessment: retrospective only,
  need for prospective/RCT, effect on clinicians or patients unmeasured.
- G7 Explainability & model transparency: black-box predictions, attention maps
  insufficient, silent OOD failure, need for uncertainty/trust.
- G8 Multi-modal data integration: images used in isolation; IVUS, OCT, CTA,
  pressure wire, ECG, labs or reports unused; missing modalities.
- G9 Class imbalance & rare pathology coverage: rare events under-represented,
  majority-class bias, rare variants excluded, aggregate metrics hide failures.
- G10 Privacy-preserving & multi-institutional learning: data sharing barriers,
  federated learning, differential privacy, governance.
- G11 Imaging biomarkers & clinical outcome prediction: intermediate tasks only,
  no link to clinical endpoints, need for outcome-supervised or longitudinal designs.
- G12 Large language models & structured reporting: LLMs/VLMs, report generation
  or structuring, free-text reports unused.

`other_limitations`: limitations the paper states that fit none of G1-G12
(short phrases, max 5). `future_work`: directions the authors propose (short
phrases, max 6).

### claim2024
Score each of the 44 CLAIM 2024 items `yes` (clearly reported), `no` (not
reported), or `na` (not applicable to this study type). Items:
1 AI technique named in title/abstract. 2 Structured abstract (design, methods,
results, conclusions). 3 Scientific/clinical background. 4 Objectives explicitly
defined. 5 Rationale for using AI. 6 Study design (prospective/retrospective).
7 Data sources and acquisition. 8 Setting and dates of data collection.
9 Eligibility criteria for participants/images. 10 Participant characteristics.
11 De-identification/privacy. 12 IRB approval or waiver. 13 Image acquisition
protocol (manufacturer, parameters). 14 Reference standard definition and method.
15 Number and expertise of annotators. 16 Inter-rater agreement or annotation
quality. 17 Train/validation/test splits. 18 Partitioning method. 19 Data
augmentation. 20 Class imbalance handling. 21 Data leakage prevention.
22 Architecture in replicable detail. 23 Pretrained weights/transfer learning.
24 Loss functions. 25 Optimizer, learning rate, hyperparameters. 26 Stopping
criteria/training procedure. 27 Pre-specified metrics. 28 Statistical analysis
plan. 29 Confidence intervals or uncertainty. 30 Robustness/sensitivity analysis.
31 Explainability methods. 32 Internal held-out test results. 33 External
validation results. 34 Participant/image flow. 35 Failure/error analysis.
36 Comparison to experts or prior methods. 37 Demographics of study population.
38 Subgroup/stratified performance. 39 Fairness/bias evaluation. 40 Limitations.
41 Clinical implications/intended use. 42 Protocol or extra technical details
referenced. 43 Code/model/data availability. 44 Funding and funder role.
Give `items` as a 44-character string of y/n/a in item order
(e.g. `"yynyy..."`, `a` = na).
