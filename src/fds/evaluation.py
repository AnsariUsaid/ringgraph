"""Metrics for the fixed-FPR comparison.

plan.md §Part 6: the primary metric is TPR at a fixed false-positive rate, which
is what "at the same false positive cost" means. ROC-AUC alone is misleading at
3.5% prevalence, so PR-AUC is the secondary.

The part that converts "M2 scored higher" into "the lift is real" is the
confidence interval on the *difference*, not two separate point estimates. That
bootstrap must be **paired** (D-17): the same resample indices applied to both
models' score vectors. Independently seeded bootstraps produce a wrong and
materially wider interval, which would undercut exactly the claim the project is
built around.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

FIXED_FPRS = (0.01, 0.001)


def fpr_label(target_fpr: float) -> str:
    """Readable metric suffix: 0.01 -> "1pct", 0.001 -> "0.1pct"."""
    return f"{target_fpr * 100:g}pct"


def tpr_at_fpr(y_true: np.ndarray, y_score: np.ndarray, target_fpr: float) -> dict[str, float]:
    """True-positive rate at a fixed false-positive rate, with its threshold."""
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    # sklearn prepends an infinite threshold; it breaks interpolation.
    fpr, tpr, thresholds = fpr[1:], tpr[1:], thresholds[1:]
    if fpr.size == 0:
        return {"tpr": float("nan"), "threshold": float("nan")}
    return {
        "tpr": float(np.interp(target_fpr, fpr, tpr)),
        "threshold": float(np.interp(target_fpr, fpr, thresholds)),
    }


def evaluate(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {
        "n": int(y_true.size),
        "n_positive": int(y_true.sum()),
        "prevalence": float(y_true.mean()),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
    }
    for target in FIXED_FPRS:
        point = tpr_at_fpr(y_true, y_score, target)
        label = fpr_label(target)
        result[f"tpr_at_fpr_{label}"] = point["tpr"]
        result[f"threshold_at_fpr_{label}"] = point["threshold"]
    return result


def confusion_at_threshold(
    y_true: np.ndarray, y_score: np.ndarray, threshold: float
) -> dict[str, int]:
    predicted = y_score >= threshold
    return {
        "tp": int((predicted & (y_true == 1)).sum()),
        "fp": int((predicted & (y_true == 0)).sum()),
        "fn": int((~predicted & (y_true == 1)).sum()),
        "tn": int((~predicted & (y_true == 0)).sum()),
    }


def paired_bootstrap_difference(
    y_true: np.ndarray,
    score_a: np.ndarray,
    score_b: np.ndarray,
    *,
    target_fpr: float,
    rng: np.random.Generator,
    n_boot: int = 1000,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Confidence interval on TPR@FPR(b) - TPR@FPR(a).

    One set of resample indices is drawn per iteration and applied to *both*
    score vectors, so the models are compared on identical resamples and the
    interval reflects only the difference between them.
    """
    n = y_true.size
    differences = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)  # shared by both models
        truth = y_true[idx]
        if truth.sum() == 0 or truth.sum() == truth.size:
            differences[i] = np.nan
            continue
        a = tpr_at_fpr(truth, score_a[idx], target_fpr)["tpr"]
        b = tpr_at_fpr(truth, score_b[idx], target_fpr)["tpr"]
        differences[i] = b - a

    valid = differences[~np.isnan(differences)]
    observed = (
        tpr_at_fpr(y_true, score_b, target_fpr)["tpr"]
        - tpr_at_fpr(y_true, score_a, target_fpr)["tpr"]
    )
    return {
        "observed_difference": float(observed),
        "ci_low": float(np.quantile(valid, alpha / 2)),
        "ci_high": float(np.quantile(valid, 1 - alpha / 2)),
        "n_boot": int(valid.size),
        "excludes_zero": bool(
            np.quantile(valid, alpha / 2) > 0 or np.quantile(valid, 1 - alpha / 2) < 0
        ),
    }


def mcnemar(y_true: np.ndarray, pred_a: np.ndarray, pred_b: np.ndarray) -> dict[str, float]:
    """Exact McNemar on paired predictions at a fixed threshold.

    Counts only the discordant pairs — cases one model gets right and the other
    gets wrong. Cases both models agree on carry no information about which is
    better, which is precisely why an unpaired test is the wrong instrument.
    """
    from scipy.stats import binomtest

    a_right = pred_a == y_true
    b_right = pred_b == y_true
    b_only = int((~a_right & b_right).sum())
    a_only = int((a_right & ~b_right).sum())
    discordant = a_only + b_only
    if discordant == 0:
        return {"b_only": 0, "a_only": 0, "p_value": 1.0}
    return {
        "b_only": b_only,
        "a_only": a_only,
        "p_value": float(binomtest(b_only, discordant, 0.5).pvalue),
    }
