"""Validate out_claim/<RID>.json (targeted CLAIM 2024 items) and check quotes against fulltext/<RID>.md.

Usage: python3 validate_claim.py R0058 [R0100 ...]   (or: python3 validate_claim.py --all)
Exit code 0 only if every given record passes.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ITEMS = ["6", "9", "10", "12", "15", "17", "20", "21", "23", "26", "27", "34", "37", "38"]
NEVER_NA = {"6", "9", "10", "12", "23", "37"}
SECTIONS = {"abstract", "introduction", "methods", "results", "discussion", "conclusion", "other"}
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def check(rid):
    path = ROOT / "out_claim" / f"{rid}.json"
    if not path.exists():
        return [f"missing {path.name}"]
    try:
        rec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    errs = []
    if rec.get("record_id") != rid:
        errs.append(f"record_id {rec.get('record_id')} != {rid}")
    items = rec.get("items") or {}
    if sorted(items, key=int) != ITEMS:
        return errs + [f"items keys must be exactly {ITEMS}"]
    text = norm((ROOT / "fulltext" / f"{rid}.md").read_text(errors="replace"))
    for k in ITEMS:
        v = items[k]
        a, q, s = v.get("answer"), v.get("quote"), v.get("section")
        if set(v) != {"answer", "quote", "section"}:
            errs.append(f"{k}: keys must be answer, quote, section")
        if a not in ("yes", "no", "na"):
            errs.append(f"{k}: answer must be yes/no/na")
        elif a == "yes":
            if not (q and s in SECTIONS):
                errs.append(f"{k}: yes needs quote and a valid section")
            elif norm(q) not in text:
                errs.append(f"{k}: quote not found verbatim in fulltext: {q[:80]!r}")
            elif len(q.split()) > 40:
                errs.append(f"{k}: quote longer than 40 words")
        elif q is not None or s is not None:
            errs.append(f"{k}: {a} must have quote and section null")
        if a == "na" and k in NEVER_NA:
            errs.append(f"{k}: na not allowed for this item")
    return errs


if __name__ == "__main__":
    ids = sorted(p.stem for p in (ROOT / "out_claim").glob("R*.json")) if sys.argv[1:] == ["--all"] else sys.argv[1:]
    bad = 0
    for rid in ids:
        errs = check(rid)
        bad += bool(errs)
        print(f"{rid} {'OK' if not errs else 'FAIL'}")
        for e in errs[:15]:
            print("   ", e)
    sys.exit(1 if bad else 0)
