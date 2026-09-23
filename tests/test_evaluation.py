"""The statistical core of the headline claim.

These functions decide whether the project reports a lift or a null, and they
had no tests. A paired-versus-unpaired bootstrap regression would have been
invisible, and the TPR interpolation contained a silent optimistic bug.
"""

from __future__ import annotations

import numpy as np
import pytest

from fds.evaluation import (
    confusion_at_threshold,
    evaluate,
    mcnemar,
    paired_bootstrap_difference,
    tpr_at_fpr,
)


class TestTprAtFpr:
    def test_perfect_separation_reaches_full_recall(self):
        y = np.array([0] * 100 + [1] * 100)
        scores = np.concatenate([np.zeros(100), np.ones(100)])
        assert tpr_at_fpr(y, scores, 0.01)["tpr"] == pytest.approx(1.0)

    def test_random_scores_sit_near_the_diagonal(self):
        rng = np.random.default_rng(0)
        y = (rng.random(20_000) < 0.035).astype(int)
        assert tpr_at_fpr(y, rng.random(20_000), 0.01)["tpr"] == pytest.approx(0.01, abs=0.02)

    def test_does_not_clamp_to_a_looser_fpr_than_requested(self):
        """The bug this test exists for.

        With 20 negatives the smallest achievable non-zero FPR is 0.05, well
        above a 0.01 target. Dropping sklearn's infinite-threshold row also
        dropped the (0, 0) origin, so np.interp clamped and returned the TPR at
        FPR=0.05 -- reporting 1.0 where interpolation from the origin gives 0.2.
        """
        y = np.array([0] * 20 + [1] * 20)
        scores = np.concatenate([np.zeros(20), np.ones(20)])
        scores[:1] = 1.0  # one false positive at the top
        value = tpr_at_fpr(y, scores, 0.01)["tpr"]
        assert value < 0.9, f"clamped to a looser FPR and reported {value}"

    def test_threshold_separates_at_the_requested_rate(self):
        rng = np.random.default_rng(1)
        y = (rng.random(10_000) < 0.1).astype(int)
        scores = rng.random(10_000) + y * 0.4
        point = tpr_at_fpr(y, scores, 0.05)
        counts = confusion_at_threshold(y, scores, point["threshold"])
        realised = counts["fp"] / (counts["fp"] + counts["tn"])
        assert realised == pytest.approx(0.05, abs=0.01)


class TestPairedBootstrap:
    def test_identical_models_give_an_interval_containing_zero(self):
        rng = np.random.default_rng(2)
        y = (rng.random(5_000) < 0.05).astype(int)
        scores = rng.random(5_000) + y * 0.3
        result = paired_bootstrap_difference(
            y, scores, scores, target_fpr=0.05, rng=rng, n_boot=200
        )
        assert result["observed_difference"] == pytest.approx(0.0)
        assert not result["excludes_zero"]

    def test_detects_a_genuinely_better_model(self):
        rng = np.random.default_rng(3)
        y = (rng.random(20_000) < 0.05).astype(int)
        weak = rng.random(20_000) + y * 0.2
        strong = rng.random(20_000) + y * 1.2
        result = paired_bootstrap_difference(y, weak, strong, target_fpr=0.01, rng=rng, n_boot=300)
        assert result["observed_difference"] > 0
        assert result["excludes_zero"]

    def test_pairing_narrows_the_interval_versus_unpaired_resampling(self):
        """Pairing is the whole point (D-17), so it has to be demonstrable.

        Two correlated models resampled on shared indices must give a tighter
        interval on the difference than resampling each independently.
        """
        rng = np.random.default_rng(4)
        y = (rng.random(8_000) < 0.08).astype(int)
        a = rng.random(8_000) + y * 0.5
        b = a + rng.normal(scale=0.02, size=8_000)  # highly correlated with a

        paired = paired_bootstrap_difference(
            y, a, b, target_fpr=0.05, rng=np.random.default_rng(5), n_boot=300
        )
        paired_width = paired["ci_high"] - paired["ci_low"]

        unpaired_rng = np.random.default_rng(5)
        n = y.size
        diffs = []
        for _ in range(300):
            ia, ib = unpaired_rng.integers(0, n, n), unpaired_rng.integers(0, n, n)
            if y[ia].sum() == 0 or y[ib].sum() == 0:
                continue
            diffs.append(
                tpr_at_fpr(y[ib], b[ib], 0.05)["tpr"] - tpr_at_fpr(y[ia], a[ia], 0.05)["tpr"]
            )
        unpaired_width = float(np.quantile(diffs, 0.975) - np.quantile(diffs, 0.025))
        assert paired_width < unpaired_width


class TestMcNemar:
    def test_identical_predictions_are_not_significant(self):
        y = np.array([0, 1, 0, 1, 1, 0])
        assert mcnemar(y, y.copy(), y.copy())["p_value"] == 1.0

    def test_counts_only_discordant_pairs(self):
        y = np.array([1, 1, 1, 1, 0, 0])
        a = np.array([1, 0, 0, 0, 0, 0])  # right on 1 of the positives
        b = np.array([1, 1, 1, 1, 0, 0])  # right on all
        result = mcnemar(y, a, b)
        assert result["b_only"] == 3
        assert result["a_only"] == 0


def test_evaluate_reports_prevalence_and_both_fixed_fprs():
    rng = np.random.default_rng(6)
    y = (rng.random(5_000) < 0.04).astype(int)
    result = evaluate(y, rng.random(5_000) + y * 0.5)
    assert result["prevalence"] == pytest.approx(y.mean())
    assert "tpr_at_fpr_1pct" in result
    assert "tpr_at_fpr_0.1pct" in result
    assert 0.0 <= result["pr_auc"] <= 1.0
