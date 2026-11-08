"""Differential test: slrlib must match the original in-script implementations.

Extracts each original function straight out of the pipeline .py files (by AST,
without importing them) and asserts slrlib returns identical results over a
sweep of inputs. This is the proof that the refactor changed no behaviour.

Run:  python3 slrlib/test_slrlib.py
"""
import ast
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slrlib import (  # noqa: E402
    extract_json, load_jsonl, iter_jsonl,
    wilson_ci_prop, wilson_ci_count, cohens_kappa, precision_recall_f1,
)


def original(filename, func_name):
    """Exec one pre-refactor function out of git HEAD and return it.

    The originals no longer exist in the working tree — that is the point of the
    refactor — so they are read from the last commit, which is the state this
    library must reproduce. Requires the repo to still contain that commit.
    """
    blob = f"HEAD:review-paper/{filename}"
    try:
        src = subprocess.run(
            ["git", "show", blob], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"cannot read {blob} from git ({e.stderr.strip()}). "
            "This test compares against the pre-refactor code in git HEAD."
        )
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == func_name)
    ns = {"json": json, "re": re, "math": math, "Path": Path}
    exec(compile(ast.Module([fn], []), "<orig>", "exec"), ns)
    return ns[func_name]


def check(label, got, want):
    assert got == want, f"{label}: slrlib={got!r} original={want!r}"


def check_close(label, got, want, tol=1e-12):
    """Same as check(), but tolerates sub-1e-12 float noise.

    Only wilson_ci_count needs this: the original in d_02_forest_plot.py does
    not clamp, so at k=0 it returns a lower bound of -2.8e-17 where slrlib
    returns 0.0. A negative probability is never wanted, so slrlib keeps the
    clamp; the values are otherwise bit-identical.
    """
    assert len(got) == len(want), f"{label}: arity {got!r} vs {want!r}"
    for g, w in zip(got, want):
        assert abs(g - w) <= tol, f"{label}: slrlib={got!r} original={want!r}"


def test_extract_json():
    orig = original("03_stage1_screening.py", "_extract_json")
    cases = [
        None, "", "   ",
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"decision": "INCLUDE"}\n```',
        'Sure! Here is the result:\n{"decision": "EXCLUDE", "why": "n/a"}\nHope that helps.',
        'not json at all',
        '{"broken": ',
        '{"nested": {"deep": [1, 2, {"x": null}]}}',
        'prefix {"a": 1} middle {"b": 2} suffix',
        '```JSON\n{"upper": true}\n```',
        '{"unicode": "\\u00e9chec"}',
    ]
    for c in cases:
        check(f"extract_json({c!r})", extract_json(c), orig(c))
    print(f"  extract_json:        {len(cases)} cases match")


def test_wilson():
    orig_prop = original("06_claim2024_checklist_graph.py", "wilson_ci")
    orig_count = original("analysis/d_02_forest_plot.py", "wilson_ci")
    n_prop = n_count = 0
    for n in [0, 1, 2, 5, 10, 70, 168, 276, 444, 5064]:
        for p in [0.0, 0.001, 0.05, 0.5, 0.9, 0.999, 1.0]:
            check(f"wilson_ci_prop({p},{n})", wilson_ci_prop(p, n), orig_prop(p, n))
            n_prop += 1
        for k in {0, 1, n // 2, max(0, n - 1), n}:
            check_close(f"wilson_ci_count({k},{n})", wilson_ci_count(k, n), orig_count(k, n))
            n_count += 1
    print(f"  wilson_ci_prop:      {n_prop} cases match")
    print(f"  wilson_ci_count:     {n_count} cases match to 1e-12 (clamped at k=0; see check_close)")


def test_agreement():
    orig_k = original("annotation_consistency_calculate.py", "cohens_kappa")
    orig_k2 = original("10_merge_validation_results.py", "cohens_kappa")
    orig_prf = original("annotation_consistency_calculate.py", "precision_recall_f1")
    orig_prf2 = original("10_merge_validation_results.py", "precision_recall_f1")
    rng = random.Random(42)
    labels = ["INCLUDE", "EXCLUDE"]
    for trial in range(300):
        n = rng.randint(1, 60)
        a = [rng.choice(labels) for _ in range(n)]
        b = [x if rng.random() < 0.8 else rng.choice(labels) for x in a]
        check(f"kappa[{trial}]", cohens_kappa(a, b), orig_k(a, b))
        check(f"kappa2[{trial}]", cohens_kappa(a, b), orig_k2(a, b))
        check(f"prf[{trial}]", precision_recall_f1(a, b), orig_prf(a, b))
        check(f"prf2[{trial}]", precision_recall_f1(a, b), orig_prf2(a, b))
    # perfect-agreement edge: pe == 1.0 branch
    same = ["INCLUDE"] * 10
    check("kappa[all-same]", cohens_kappa(same, same), orig_k(same, same))
    print("  cohens_kappa:        301 cases match (both original copies)")
    print("  precision_recall_f1: 300 cases match (both original copies)")


def test_jsonl(tmp):
    good = tmp / "good.jsonl"
    good.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
    bad = tmp / "bad.jsonl"
    bad.write_text('{"a": 1}\nNOT JSON\n{"b": 2}\n', encoding="utf-8")

    orig_lenient = original("06_claim2024_checklist_graph.py", "load_jsonl")
    check("load_jsonl(good)", load_jsonl(good), orig_lenient(good))
    check("load_jsonl(bad)", load_jsonl(bad), orig_lenient(bad))
    assert load_jsonl(bad) == [{"a": 1}, {"b": 2}], "lenient variant must skip bad lines"

    orig_strict = original("analysis/04_task-archi.py", "load_jsonl")
    check("iter_jsonl(good)", list(iter_jsonl(good)), list(orig_strict(good)))
    for fn, name in ((iter_jsonl, "slrlib"), (orig_strict, "original")):
        try:
            list(fn(bad))
        except json.JSONDecodeError:
            pass
        else:
            raise AssertionError(f"{name} iter_jsonl must raise on a bad line")
    print("  load_jsonl/iter_jsonl: lenient-skip and strict-raise both preserved")


def main():
    import tempfile
    print("slrlib differential test — new code vs the original in-script copies")
    test_extract_json()
    test_wilson()
    test_agreement()
    with tempfile.TemporaryDirectory() as d:
        test_jsonl(Path(d))
    print("ALL PASS — slrlib is behaviourally identical to the originals")


if __name__ == "__main__":
    main()
