#!/usr/bin/env python3
"""Stage-1 screening with a deterministic pre-filter in front of the LLM gates.

Design (2026-08-30). Three phases instead of two:

  2026-09-29: the pre-filter no longer skips anything. Every record meets
  the inclusion gate; the deterministic E2 code below only ORs into the
  exclusion-gate verdict of records that pass inclusion.

  Phase 0  Deterministic pre-filter, no LLM.
           E2 when PubMed PublicationType names the record a non-research
           document (editorial, letter, comment, erratum, retraction, ...).
           Records with no retrievable abstract are NOT pre-filtered
           (2026-09-29): they run both gates on the title alone and are all
           adjudicated by a human, since absence of an abstract proves nothing.

  Phase 1  Inclusion gate (I1-I4), LLM. Runs on UNFLAGGED records only.
           Flagged records are skipped here deliberately: their fate is already
           settled by publication metadata, so asking a 27B model whether an
           erratum reports a quantitative evaluation wastes compute and invites
           a wrong answer. It also keeps the flow logically coherent, since a
           record excluded for what it IS never needs judging for what it says.

  Phase 2  Exclusion gate (E1-E3), LLM. Runs on records that passed phase 1
           PLUS every flagged record, so the flagged ones are counted in the
           exclusion stage of PRISMA rather than vanishing before it. For a
           flagged record the deterministic code is ORed into the verdict, so
           the LLM can add an exclusion reason but can never overturn one.

Reuses the prompts and gate plumbing from 03_stage1_screening.py verbatim.
"""
import argparse, csv, importlib.util, json, sys, time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("s1", HERE / "03_stage1_screening.py")
s1 = importlib.util.module_from_spec(_spec)
sys.modules["s1"] = s1
_spec.loader.exec_module(s1)

E2_HARD = {
    "Editorial", "Letter", "Comment", "Published Erratum",
    "Retraction of Publication", "Retracted Publication",
    "Expression of Concern", "News", "Newspaper Article",
    "Biography", "Autobiography", "Interview", "Address",
    "Patient Education Handout", "Bibliography",
}

OUT_COLUMNS = [
    "record_id", "title", "abstract_present",
    "prefilter_flag", "prefilter_codes", "prefilter_detail",
    "phase1_run", "llm_inclusion_pass", "llm_inclusion_criteria", "llm_inclusion_reason",
    "phase2_run", "llm_exclusion_pass", "llm_exclusion_criteria", "llm_exclusion_reason",
    "exclusion_codes_final", "decision", "excluded_at",
]


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def prefilter(rows, pubtypes):
    """Attach phase-0 verdicts. pubtypes: record_id -> [PublicationType]."""
    for r in rows:
        abstract = (r.get("abstract") or "").strip()
        types = pubtypes.get(r["record_id"], [])
        hits = sorted(set(types) & E2_HARD)
        codes, detail = [], []
        # The PubMed type is metadata, so it applies whether or not an abstract
        # exists. A missing abstract is not evidence of anything: those records
        # go through both gates on the title and a human adjudicates them.
        if hits:
            codes.append("E2")
            detail.append("PublicationType: " + "; ".join(hits))
        if not abstract:
            detail.append("no abstract retrieved; screened on title, human-adjudicated")
        r["_abstract"] = abstract
        r["_codes"] = codes
        r["_detail"] = " | ".join(detail)
    return rows


def run(rows, out_path, limit=0):
    done = {}
    if Path(out_path).exists():
        for r in load(out_path):
            done[r["record_id"]] = r
        print(f"[resume] {len(done)} records already screened", flush=True)

    todo = [r for r in rows if r["record_id"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"[run] {len(todo)} records to screen", flush=True)

    if todo:
        s1._preload_model()

    fh = open(out_path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=OUT_COLUMNS)
    if not done:
        w.writeheader(); fh.flush()

    t0 = time.time()
    for i, r in enumerate(todo, 1):
        title = (r.get("title") or "").strip()
        abstract = r["_abstract"][: s1.ABSTRACT_MAX_LEN]
        flagged = bool(r["_codes"])

        row = {
            "record_id": r["record_id"], "title": title,
            "abstract_present": "yes" if r["_abstract"] else "no",
            "prefilter_flag": "yes" if flagged else "no",
            "prefilter_codes": ";".join(r["_codes"]),
            "prefilter_detail": r["_detail"],
            "phase1_run": "no", "llm_inclusion_pass": "SKIPPED (prefilter)",
            "llm_inclusion_criteria": "[]",
            "llm_inclusion_reason": "Not screened for inclusion: deterministically flagged at phase 0",
            "phase2_run": "no", "llm_exclusion_pass": "", "llm_exclusion_criteria": "[]",
            "llm_exclusion_reason": "", "exclusion_codes_final": "",
            "decision": "", "excluded_at": "",
        }

        # ── Phase 1: inclusion, every record (no pre-filter shortcut, 2026-09-29)
        inc_pass = None
        if True:  # kept as a block so the diff stays small
            row["phase1_run"] = "yes"
            parsed, raw = s1._call_gate("inclusion", s1.INCLUSION_SYSTEM, title, abstract)
            parsed = s1._yesno_to_gate(parsed, s1.INCLUSION_CODES, "inclusion")
            if parsed is None:
                row.update(llm_inclusion_pass="ERROR", llm_inclusion_reason="LLM call failed",
                           decision="ERROR", excluded_at="inclusion")
                w.writerow(row); fh.flush(); continue
            inc_pass = bool(parsed["pass"])
            row["llm_inclusion_pass"] = inc_pass
            row["llm_inclusion_criteria"] = json.dumps(
                {"met": parsed["triggered_criteria"], "failed": parsed["failed_criteria"]})
            row["llm_inclusion_reason"] = (
                "Met: " + ", ".join(parsed["triggered_criteria"]) if inc_pass
                else "Failed: " + ", ".join(parsed["failed_criteria"]))
            if not inc_pass and not flagged:  # PubMed-typed non-research docs go on to E2
                row.update(decision="EXCLUDE", excluded_at="inclusion")
                w.writerow(row); fh.flush()
                if i % 100 == 0:
                    el = time.time() - t0
                    print(f"  {i}/{len(todo)}  {el/i:.2f}s/rec  eta {(len(todo)-i)*el/i/60:.0f}m", flush=True)
                continue

        # ── Phase 2: exclusion, phase-1 survivors + PubMed-typed non-research documents ──
        row["phase2_run"] = "yes"
        parsed, raw = s1._call_gate("exclusion", s1.EXCLUSION_SYSTEM, title, abstract)
        parsed = s1._yesno_to_gate(parsed, s1.EXCLUSION_CODES, "exclusion")
        llm_codes = []
        if parsed is None:
            row["llm_exclusion_pass"] = "ERROR"
            row["llm_exclusion_reason"] = "LLM call failed"
        else:
            llm_codes = list(parsed["triggered_criteria"])
            row["llm_exclusion_pass"] = bool(parsed["pass"])
            row["llm_exclusion_criteria"] = json.dumps(llm_codes)
            row["llm_exclusion_reason"] = ("no exclusion criterion triggered" if parsed["pass"]
                                           else "Triggered: " + ", ".join(llm_codes))

        # deterministic codes OR in: the LLM may add a reason, never remove one
        final = sorted(set(llm_codes) | set(r["_codes"]))
        row["exclusion_codes_final"] = ";".join(final)
        if final:
            row.update(decision="EXCLUDE", excluded_at="exclusion")
        else:
            row.update(decision="INCLUDE", excluded_at="")
        w.writerow(row); fh.flush()

        if i % 100 == 0:
            el = time.time() - t0
            print(f"  {i}/{len(todo)}  {el/i:.2f}s/rec  eta {(len(todo)-i)*el/i/60:.0f}m", flush=True)

    fh.close()
    print(f"[done] {time.time()-t0:.0f}s", flush=True)


def summarise(out_path, total):
    rows = load(out_path)
    n = len(rows)
    flagged = [r for r in rows if r["prefilter_flag"] == "yes"]
    p1 = [r for r in rows if r["phase1_run"] == "yes"]
    p1_fail = [r for r in p1 if r["excluded_at"] == "inclusion"]
    p1_pass = [r for r in p1 if r["llm_inclusion_pass"] == "True"]
    p2 = [r for r in rows if r["phase2_run"] == "yes"]
    inc = [r for r in rows if r["decision"] == "INCLUDE"]
    exc2 = [r for r in rows if r["excluded_at"] == "exclusion"]

    pf = Counter(c for r in flagged for c in r["prefilter_codes"].split(";") if c)
    ec = Counter(c for r in exc2 for c in r["exclusion_codes_final"].split(";") if c)
    ic = Counter()
    for r in p1_fail:
        try: ic.update(json.loads(r["llm_inclusion_criteria"]).get("failed", []))
        except Exception: pass

    L = []
    A = L.append
    A("=" * 68)
    A("PRISMA -- stage 1 screening with deterministic pre-filter")
    A("=" * 68)
    A(f"Records screened                              {total}")
    A("")
    A(f"PubMed-type E2 codes (ORed at the exclusion gate only)")
    A(f"  records carrying one                        {len(flagged)}")
    for c, k in sorted(pf.items()):
        lbl = {"E1": "E1 abstract-only (no abstract retrievable)",
               "E2": "E2 non-research document type"}.get(c, c)
        A(f"    {lbl:<42} {k}")
    A("")
    A(f"PHASE 1  inclusion gate I1-I4 (LLM)")
    A(f"  screened                                    {len(p1)}")
    A(f"  failed inclusion  -> EXCLUDED               {len(p1_fail)}")
    for c, k in sorted(ic.items()):
        A(f"    {c:<42} {k}")
    A(f"  passed inclusion                            {len(p1_pass)}")
    A("")
    A(f"PHASE 2  exclusion gate E1-E3 (LLM + pre-filter codes)")
    A(f"  assessed  = phase-1 survivors + E2-typed    {len(p2)}")
    A(f"  excluded at exclusion stage                 {len(exc2)}")
    for c, k in sorted(ec.items()):
        lbl = {"E1": "E1 not a full-length publication",
               "E2": "E2 non-research document type",
               "E3": "E3 not in English"}.get(c, c)
        A(f"    {lbl:<42} {k}")
    A("")
    A(f"INCLUDED for full-text screening              {len(inc)}")
    A("=" * 68)
    A(f"check: {len(p1_fail)} + {len(exc2)} + {len(inc)} = {len(p1_fail)+len(exc2)+len(inc)}  (want {total})")
    out = "\n".join(L)
    print(out)
    Path(out_path).with_name("PRISMA_prefiltered.txt").write_text(out + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  default="results/stage1_all_5064_with_abstracts_2026-08-30.csv")
    ap.add_argument("--pmids",  default="results/pubtype_pmids.json")
    ap.add_argument("--ptypes", default="results/pubtype_by_pmid.json")
    ap.add_argument("--output", default="results/stage1_prefiltered.csv")
    ap.add_argument("--limit",  type=int, default=0)
    ap.add_argument("--summary-only", action="store_true")
    a = ap.parse_args()

    rows = load(HERE / a.input)
    pm = json.loads((HERE / a.pmids).read_text())
    pt = json.loads((HERE / a.ptypes).read_text())
    pubtypes = {rid: pt.get(pmid, []) for rid, pmid in pm.items() if pmid}
    rows = prefilter(rows, pubtypes)
    print(f"loaded {len(rows)} records; pubtypes for {sum(1 for r in rows if pubtypes.get(r['record_id']))}", flush=True)

    if not a.summary_only:
        run(rows, HERE / a.output, a.limit)
    summarise(HERE / a.output, len(rows))
