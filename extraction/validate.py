"""Validate out/<RID>.json against schema.json and check every quote against fulltext/<RID>.md.

Usage: python3 validate.py R0058 [R0100 ...]   (or: python3 validate.py --all)
Exit code 0 only if every given record passes.
"""
import json, re, subprocess, sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "jsonschema"], check=True)
    import jsonschema

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "schema.json").read_text())
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def check(rid):
    path = ROOT / "out" / f"{rid}.json"
    if not path.exists():
        return [f"missing {path.name}"]
    try:
        rec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    errs = [f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message[:160]}"
            for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(rec)]
    if errs:
        return errs
    text = norm((ROOT / "fulltext" / f"{rid}.md").read_text(errors="replace"))
    if rec["record_id"] != rid:
        errs.append(f"record_id {rec['record_id']} != {rid}")
    quotes = [(f"gaps/{g}", v["quote"]) for g, v in rec["gaps"].items() if v["status"] != "none"]
    for g, v in rec["gaps"].items():
        if v["status"] == "none" and (v["quote"] or v["section"]):
            errs.append(f"gaps/{g}: status none must have quote/section null")
        if v["status"] != "none" and not (v["quote"] and v["section"]):
            errs.append(f"gaps/{g}: status {v['status']} needs quote and section")
    te = rec["method"]["temporal_evidence"]
    if rec["method"]["temporal_category"] != "not_determinable":
        if not te:
            errs.append("method/temporal_evidence required unless not_determinable")
        else:
            quotes.append(("method/temporal_evidence", te["quote"]))
    for where, q in quotes:
        if q and norm(q) not in text:
            errs.append(f"{where}: quote not found verbatim in fulltext: {q[:80]!r}")
        if q and len(q.split()) > 40:
            errs.append(f"{where}: quote longer than 40 words")
    t = rec["task"]
    if t["primary_task"] in t["secondary_tasks"]:
        errs.append("task: primary_task repeated in secondary_tasks")
    if (t["primary_task"] == "other") != bool(t["other_label"]):
        errs.append("task: other_label must be set iff primary_task is other")
    return errs


if __name__ == "__main__":
    ids = sorted(p.stem for p in (ROOT / "out").glob("R*.json")) if sys.argv[1:] == ["--all"] else sys.argv[1:]
    bad = 0
    for rid in ids:
        errs = check(rid)
        bad += bool(errs)
        print(f"{rid} {'OK' if not errs else 'FAIL'}")
        for e in errs[:15]:
            print("   ", e)
    sys.exit(1 if bad else 0)
