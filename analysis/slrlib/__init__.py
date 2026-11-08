"""
slrlib — shared helpers for the AngioVision SLR pipeline.

Extracted verbatim from the numbered pipeline scripts. Every function here is
behaviour-identical to the copies it replaced; where copies had genuinely
different semantics they are exposed as separately named functions rather than
merged (see stats.wilson_ci_prop vs wilson_ci_count, jsonio.load_jsonl vs
iter_jsonl). Nothing here changes pipeline output.

Verify with:  python3 slrlib/test_slrlib.py
"""
from .bootstrap import ensure
from .jsonio import extract_json, load_jsonl, iter_jsonl
from .stats import wilson_ci_prop, wilson_ci_count, cohens_kappa, precision_recall_f1

__all__ = [
    "ensure",
    "extract_json", "load_jsonl", "iter_jsonl",
    "wilson_ci_prop", "wilson_ci_count", "cohens_kappa", "precision_recall_f1",
]
