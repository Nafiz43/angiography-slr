"""Convert v2 extractions (out/*.json) into the legacy stage2/CLAIM JSONL shapes read by the
existing review-paper/analysis/*.py figure scripts, so figures keep their original styling.

Usage: python3 v2_to_legacy.py OUTDIR [--exclude R4154,R2434,R4671]
Writes OUTDIR/stage2_results.jsonl, stage2_results.filtered.jsonl, claim2024_results.jsonl
"""
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK = {"vessel_segmentation": "Vessel Segmentation", "object_detection_localization": "Object Detection & Localization",
        "catheter_device_tracking": "Catheter & Device Tracking", "disease_classification_grading": "Disease Classification & Grading",
        "background_subtraction": "Background Subtraction", "image_enhancement_denoising": "Image Enhancement & Denoising",
        "temporal_sequence_modeling": "Temporal Sequence Modeling", "contrast_flow_analysis": "Contrast Flow Analysis",
        "motion_correction_registration": "Motion Correction & Registration", "outcome_prediction": "Outcome Prediction",
        "other": "other"}
MODALITY = {"DSA": "DSA", "xray_fluoroscopy": "fluoroscopy", "DSA_and_fluoroscopy": "DSA+fluoroscopy", "other": "other"}
ANATOMY = {"neurologic": "cerebral", "cardiac": "coronary", "aortic_thoracic": "thoracic", "abdominopelvic": "abdominal",
           "peripheral": "peripheral", "multi": "multi", "other": "other", "not_reported": None}
PUBTYPE = {"journal": "journal", "conference_full_paper": "conference", "conference_abstract": "conference",
           "preprint": "preprint", "book_chapter": "other", "other": "other"}
# Official CLAIM 2024 (Tejani 2024) items -> v2 schema items (1-based, extraction/INSTRUCTIONS.md list).
# None = scored separately against the official wording (out_claim/, INSTRUCTIONS_CLAIM.md in the kit).
# Several v2 items under one official item: reported only if ALL applicable sub-items are reported.
OFFICIAL = {1: [1], 2: [2], 3: [3, 5], 4: [4], 5: [6], 6: None, 7: [7], 8: [8, 9], 9: None, 10: None,
            11: [11], 12: None, 13: [13], 14: [14], 15: None, 16: [15], 17: None, 18: [16], 19: [17, 18],
            20: None, 21: None, 22: [22], 23: None, 24: [23], 25: [19, 24, 25, 26], 26: None, 27: None,
            28: [27, 36], 29: [28, 29], 30: [30], 31: [31], 32: [32], 33: [33], 34: None, 35: [34],
            36: [10, 37], 37: None, 38: None, 39: [35], 40: [40], 41: [41], 42: [42], 43: [43], 44: [44]}
# Groups = the official CLAIM 2024 checklist subsections.
CLUSTERS = [("1-2", 1, 2), ("3-4", 3, 4), ("5-6", 5, 6), ("7-13", 7, 13), ("14-18", 14, 18), ("19-20", 19, 20),
            ("21", 21, 21), ("22-24", 22, 24), ("25-27", 25, 27), ("28-34", 28, 34), ("35-36", 35, 36),
            ("37-39", 37, 39), ("40-41", 40, 41), ("42-44", 42, 44)]


def official(v2, extra):
    """44-char y/n/a string in official CLAIM 2024 order from the v2 string and the targeted items."""
    out = []
    for k in range(1, 45):
        if OFFICIAL[k] is None:
            out.append({"yes": "y", "no": "n", "na": "a"}[extra[str(k)]["answer"]])
            continue
        sub = [c for c in (v2[i - 1] for i in OFFICIAL[k]) if c != "a"]
        out.append("a" if not sub else "n" if "n" in sub else "y")
    return "".join(out)


def cluster(items, a, b):
    """Cluster adherence: NA if every item is n/a, else Yes when at least half of the applicable items are reported."""
    s = [c for c in items[a - 1:b] if c != "a"]
    if not s:
        return "NA"
    return "Yes" if s.count("y") * 2 >= len(s) else "No"


def main(outdir, exclude):
    meta = {r["record_id"]: r for r in csv.DictReader(open(ROOT / "manifest.csv"))}
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    s2, cl, seen = [], [], {}
    for p in sorted((ROOT / "out").glob("R*.json")):
        r = json.loads(p.read_text()); rid = r["record_id"]
        if rid in exclude:
            continue
        m, ev = meta[rid], r["evaluation"]
        head = next((x for x in ev["metrics"] if x["value_0_100"] is not None), None)
        year = int(m["year"]) if m["year"] else r["study"]["year"]
        venue = m["journal_venue"] or r["study"]["venue"] or ""
        if (re.search(r"spie", venue, re.I) or venue.strip().lower() == "medical imaging"
                or (m.get("doi") or "").startswith("10.1117/")):  # SPIE DOI prefix
            venue = "Proceedings of SPIE"
        elif re.fullmatch(r"arxiv(\.org)?", venue.strip(), re.I):
            venue = "arXiv.org"
        # one spelling per venue, so case variants are not counted as separate venues
        venue = seen.setdefault(venue.strip().lower(), venue.strip())
        s2.append({
            "title": m["title"], "year": year, "_source_file": f"{rid}.pdf", "_md_file": f"{rid}.md", "record_id": rid,
            "study_identity": {"title": m["title"], "journal_or_venue": venue,
                               "year": year, "publication_type": PUBTYPE[r["study"]["publication_type"]]},
            "imaging": {"modality": MODALITY[r["imaging"]["modality"]], "anatomy": ANATOMY[r["imaging"]["territory"]],
                        "anatomy_detail": r["imaging"]["territory_detail"]},
            "task": {"primary_task": TASK[r["task"]["primary_task"]],
                     "secondary_tasks": [TASK[t] for t in r["task"]["secondary_tasks"]]},
            "method": {"architecture_name": ", ".join(r["method"]["architecture_names"]),
                       "temporal_modelling": r["method"]["temporal_category"] not in ("none", "not_determinable"),
                       "temporal_category": r["method"]["temporal_category"]},
            "evaluation": {"primary_metric": head and head["metric"], "primary_metric_value": head and head["value_0_100"],
                           "validation_design": ev["validation_design"]},
        })
        items = official(r["claim2024"]["items"], json.loads((ROOT / "out_claim" / f"{rid}.json").read_text())["items"])
        cl.append({"title": m["title"], "year": year, "_source_file": f"{rid}.pdf", "record_id": rid,
                   "claim2024_adherence": {cid: {"adherence": cluster(items, a, b)} for cid, a, b in CLUSTERS}})
    for name, rows in [("stage2_results.jsonl", s2), ("stage2_results.filtered.jsonl", s2), ("claim2024_results.jsonl", cl)]:
        (outdir / name).write_text("".join(json.dumps(x) + "\n" for x in rows))
    print(f"wrote {len(s2)} records to {outdir}")


if __name__ == "__main__":
    ex = set(sys.argv[sys.argv.index("--exclude") + 1].split(",")) if "--exclude" in sys.argv else set()
    main(sys.argv[1], ex)
