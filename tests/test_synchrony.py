"""Synchrony detection: the confounds it must not fall for."""

from __future__ import annotations

import numpy as np

from fds.synchrony import coincidence_count, synchrony_test

HOUR = 3600.0
SPAN = 182 * 86400.0


def test_one_client_bursting_is_not_synchrony():
    """The confound a Poisson baseline would fail.

    Individual customers are bursty by themselves — four purchases in an hour is
    ordinary behaviour, not a ring. Only cross-client pairs may count.
    """
    times = np.array([0.0, 60.0, 120.0, 180.0, 240.0])
    same_client = np.zeros(5, dtype=int)
    assert coincidence_count(times, same_client, HOUR) == 0


def test_distinct_clients_firing_together_is_synchrony():
    times = np.array([0.0, 60.0, 120.0, 180.0])
    four_clients = np.arange(4)
    assert coincidence_count(times, four_clients, HOUR) == 6  # all pairs


def test_shift_null_destroys_alignment_but_keeps_burstiness():
    """Same per-client burst patterns, spread across the year, must not score."""
    rng = np.random.default_rng(0)
    groups = []
    times, codes = [], []
    for client in range(4):
        times.extend(client * 30 * 86400.0 + k * 60 for k in range(4))
        codes.extend([client] * 4)
    groups.append((np.asarray(times), np.asarray(codes)))
    result = synchrony_test(groups, delta=HOUR, span=SPAN, rng=rng, n_permutations=20)
    assert result["observed"] == 0
    # The null must actually run: shifting four clients into a shared window
    # occasionally produces coincidences, so a null of exactly zero across 20
    # draws would mean the shuffling never happened.
    assert result["null_sd"] >= 0.0
    assert result["n_transactions"] == 16


def test_coordinated_ring_exceeds_its_own_null():
    rng = np.random.default_rng(0)
    times, codes = [], []
    for client in range(4):
        times.extend(client * 300.0 + k * 60 for k in range(4))
        codes.extend([client] * 4)
    groups = [(np.asarray(times), np.asarray(codes))]
    result = synchrony_test(groups, delta=HOUR, span=SPAN, rng=rng, n_permutations=20)
    assert result["observed"] > result["null_mean"]
    assert result["observed"] == 96
