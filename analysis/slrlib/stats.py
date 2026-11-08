"""Statistics helpers shared by the SLR analysis scripts.

wilson_ci had FOUR copies with two incompatible contracts: three took p as a
proportion, analysis/d_02_forest_plot.py took p as a success COUNT. They are
kept as separate functions on purpose — merging them would silently corrupt
whichever caller got the other convention.
"""
import math


def wilson_ci_prop(p, n, z=1.96):
    """Wilson score CI from a PROPORTION p. Returns (lo, hi), clamped to [0,1].

    Was wilson_ci in 06_claim2024_checklist_graph.py,
    analysis/07_claim_side_by_side_comparison.py, analysis/d_02_forest_plot2.py.
    Returns (p, p) when n == 0, matching those callers.
    """
    if n == 0:
        return (p, p)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def wilson_ci_count(k, n, z=1.96):
    """Wilson score CI from a success COUNT k out of n. Returns (lo, hi).

    Was wilson_ci in analysis/d_02_forest_plot.py, which passes a count and
    divides internally. Equivalent to wilson_ci_prop(k / n, n) apart from the
    n == 0 case, which that caller returns as (0, 0).

    ONE intentional difference from the original: this clamps to [0, 1]. The
    original did not, so at k == 0 it returned a lower bound of -2.8e-17
    instead of 0.0. Nothing else changes; see slrlib/test_slrlib.py.
    """
    if n == 0:
        return (0, 0)
    return wilson_ci_prop(k / n, n, z)


def cohens_kappa(labels_a, labels_b):
    """Cohen's kappa for two raters. Returns (kappa, p_observed, p_expected).

    The copies in 10_merge_validation_results.py and
    annotation_consistency_calculate.py differed only in loop style.
    """
    n = len(labels_a)
    assert n == len(labels_b) and n > 0
    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    categories = sorted(set(labels_a) | set(labels_b))
    pe = 0.0
    for c in categories:
        pa = sum(1 for a in labels_a if a == c) / n
        pb = sum(1 for b in labels_b if b == c) / n
        pe += pa * pb
    if pe == 1.0:
        return (1.0, po, pe)
    return ((po - pe) / (1 - pe), po, pe)


def precision_recall_f1(y_true, y_pred, positive_label="INCLUDE"):
    """Confusion counts plus precision / recall / F1 / accuracy.

    The two copies differed only in `if x` vs `if x > 0` on non-negative
    counts, which is the same test.
    """
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p == positive_label)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != positive_label and p == positive_label)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p != positive_label)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t != positive_label and p != positive_label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    return {
        "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "true_negative": tn,
        "precision": precision, "recall": recall,
        "f1": f1, "accuracy": accuracy,
    }
