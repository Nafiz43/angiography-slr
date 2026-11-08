"""Generates schema.json (kept as code so enums are defined once)."""
import json

def enum(*v): return {"enum": list(v)}
def nint(): return {"type": ["integer", "null"], "minimum": 0}
def nstr(): return {"type": ["string", "null"]}
def nbool(): return {"type": ["boolean", "null"]}
def strs(n=None):
    s = {"type": "array", "items": {"type": "string"}}
    if n: s["maxItems"] = n
    return s
def obj(props, req=None):
    return {"type": "object", "additionalProperties": False, "properties": props,
            "required": list(props) if req is None else req}

SECTION = enum("abstract", "introduction", "methods", "results", "discussion", "conclusion", "other")
EVID = obj({"quote": {"type": "string", "minLength": 3}, "section": SECTION})
TASKS = ["vessel_segmentation", "object_detection_localization", "catheter_device_tracking",
         "disease_classification_grading", "background_subtraction", "image_enhancement_denoising",
         "temporal_sequence_modeling", "contrast_flow_analysis", "motion_correction_registration",
         "outcome_prediction", "other"]
GAP = obj({"status": enum("documents", "addresses", "both", "none"),
           "quote": nstr(), "section": {"enum": SECTION["enum"] + [None]}})
FLAG = lambda: obj({"value": nbool(), "detail": nstr()})

schema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AngioVision SLR stage-2 extraction v2",
  **obj({
    "record_id": {"type": "string", "pattern": "^R[0-9]{4}$"},
    "schema_version": {"const": "2.0"},
    "study": obj({
      "title": {"type": "string"}, "year": nint(), "venue": nstr(),
      "publication_type": enum("journal", "conference_full_paper", "conference_abstract",
                               "preprint", "book_chapter", "other"),
      "text_is_full_paper": {"type": "boolean"},
      "country_of_data": nstr()}),
    "imaging": obj({
      "modality": enum("DSA", "xray_fluoroscopy", "DSA_and_fluoroscopy", "other"),
      "modality_detail": nstr(),
      "territory": enum("neurologic", "cardiac", "aortic_thoracic", "abdominopelvic",
                        "peripheral", "multi", "other", "not_reported"),
      "territory_detail": nstr(),
      "acquisition_geometry": enum("monoplane", "biplane", "rotational_3D", "mixed", "not_reported"),
      "frame_rate_fps": {"type": ["number", "null"]},
      "frames_per_sequence": nstr(),
      "vendors": strs()}),
    "dataset": obj({
      "n_patients": nint(), "n_sequences": nint(), "n_images_or_frames": nint(),
      "n_centers": nint(), "n_vendors": nint(),
      "data_origin": enum("clinical", "phantom", "synthetic", "clinical_plus_synthetic",
                          "clinical_plus_phantom", "mixed", "not_reported"),
      "public_dataset_used": FLAG(), "data_released": FLAG(),
      "split_level": enum("patient", "sequence", "frame", "site", "not_reported", "na"),
      "annotation": obj({
        "type": enum("manual", "semi_automatic", "automatic", "weak_or_derived", "none", "not_reported"),
        "n_annotators": nint(), "annotator_expertise": nstr(),
        "inter_rater_reported": {"type": "boolean"}, "inter_rater_value": nstr()})}),
    "task": obj({
      "primary_task": {"enum": TASKS}, "other_label": nstr(),
      "secondary_tasks": {"type": "array", "items": {"enum": TASKS[:-1]}, "uniqueItems": True},
      "task_description": {"type": "string"}, "clinical_application": nstr()}),
    "method": obj({
      "architecture_names": strs(),
      "architecture_family": enum("unet_encoder_decoder", "cnn_classifier", "detector", "transformer",
                                  "hybrid_cnn_transformer", "recurrent", "generative_gan_diffusion",
                                  "foundation_or_vlm", "classical_ml", "non_learning", "other"),
      "temporal_category": enum("none", "frame_aggregation", "optical_flow_registration", "recurrent",
                                "cnn3d_video", "transformer_ssm", "hemodynamic_physics", "not_determinable"),
      "temporal_evidence": {"oneOf": [EVID, {"type": "null"}]},
      "input_dimensionality": enum("2D_single_frame", "2D_multi_frame", "2D_plus_time_video",
                                   "multi_view", "3D_volume", "mixed", "not_reported"),
      "supervision": enum("fully_supervised", "semi_supervised", "self_supervised", "weakly_supervised",
                          "unsupervised", "mixed", "not_applicable"),
      "pretraining": nstr(),
      "uses_synthetic_training_data": {"type": "boolean"},
      "physics_informed": {"type": "boolean"},
      "multimodal_inputs": strs(),
      "class_imbalance_handling": nstr(),
      "uncertainty_quantification": {"type": "boolean"},
      "explainability_method": nstr(),
      "federated_or_privacy_preserving": {"type": "boolean"},
      "uses_llm_or_vlm": {"type": "boolean"},
      "real_time_or_inference_time_reported": {"type": "boolean"}}),
    "evaluation": obj({
      "validation_design": enum("internal_split", "cross_validation", "external_validation",
                                "prospective", "none", "not_reported"),
      "external_validation_detail": nstr(),
      "metrics": {"type": "array", "maxItems": 25, "items": obj({
        "metric": {"type": "string"},
        "family": enum("dice", "iou", "accuracy", "auc", "sensitivity_recall", "specificity",
                       "precision_ppv", "f1", "kappa", "psnr", "ssim", "error_distance",
                       "correlation", "time", "other"),
        "value_raw": {"type": "string"}, "value_0_100": {"type": ["number", "null"]},
        "split": enum("test", "validation", "cross_validation", "external", "other"),
        "task": nstr()})},
      "comparators": strs(15),
      "compared_with_humans": {"type": "boolean"},
      "ablation": {"type": "boolean"}, "statistical_testing": {"type": "boolean"},
      "confidence_intervals": {"type": "boolean"},
      "subgroup_or_per_class_reporting": {"type": "boolean"},
      "failure_analysis": {"type": "boolean"}}),
    "clinical": obj({
      "study_design": enum("retrospective", "prospective", "rct", "mixed", "not_reported"),
      "reader_study": {"type": "boolean"}, "patient_outcome_measured": {"type": "boolean"},
      "clinical_deployment_or_live_use": {"type": "boolean"},
      "regulatory_mentioned": {"type": "boolean"}}),
    "reproducibility": obj({
      "code_available": FLAG(), "model_weights_available": FLAG(),
      "hyperparameters_reported": {"type": "boolean"}}),
    "gaps": obj({f"G{i}": GAP for i in range(1, 13)}),
    "other_limitations": strs(5),
    "future_work": strs(6),
    "claim2024": obj({"items": {"type": "string", "pattern": "^[yna]{44}$"}}),
  }),
}
json.dump(schema, open("schema.json", "w"), indent=1)
print("ok", len(json.dumps(schema)))
