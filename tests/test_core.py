"""Test del modello: Turan vs ILP, probabilita' note, EV indipendente dal design, simulazione."""
from itertools import combinations
from math import comb

import numpy as np
import pytest

from core import (
    AMBO_PAYOUT, N_DRAWN, N_NUMBERS, P_AMBO, _counts_by_enumeration, analyze, best_t_for_edges,
    clique_sizes, complete_design, make_design, matching_design, max_edges_for_budget,
    max_k_for_edges, ortools_available, p_guarantee, simulate_wins, solve_ilp,
    theoretical_ev_return, turan_design, turan_group_sizes, turan_min_edges, wins_counts, wins_pmf,
)

needs_ortools = pytest.mark.skipif(not ortools_available(), reason="OR-Tools non installato")


# ------------------------------------------------------------------ Turan
def test_p_ambo():
    assert P_AMBO == pytest.approx(1 / 400.5)


@pytest.mark.parametrize("k,t", [(10, 3), (11, 4), (7, 5), (5, 2)])
def test_turan_group_sizes_balanced(k, t):
    sizes = turan_group_sizes(k, t)
    assert len(sizes) == t - 1 and sum(sizes) == k and max(sizes) - min(sizes) <= 1


@pytest.mark.parametrize("k,t,expected", [(8, 2, 28), (8, 3, 12), (10, 3, 20), (9, 4, 9), (6, 5, 2)])
def test_turan_min_edges_values(k, t, expected):
    assert turan_min_edges(k, t) == expected


@pytest.mark.parametrize("k,t", [(8, 3), (10, 4), (9, 5)])
def test_turan_design_guarantees(k, t):
    d = turan_design(k, t)
    edges = set(d.edges)
    assert d.n_edges == turan_min_edges(k, t)
    assert all(any(p in edges for p in combinations(T, 2)) for T in combinations(range(k), t))


def test_turan_t_too_small():
    with pytest.raises(ValueError):
        turan_group_sizes(5, 1)


@needs_ortools
@pytest.mark.parametrize("k,t", [(6, 3), (8, 3), (8, 4), (9, 5)])
def test_ilp_matches_turan(k, t):
    res = solve_ilp(k, t, time_limit=20)
    assert res.status == "OPTIMAL"
    assert res.objective == turan_min_edges(k, t)


# ------------------------------------------------------------------ design
def test_make_design_normalizes_edges():
    d = make_design("x", [(1, 0), (0, 1), (2, 2), (2, 1)], 3)
    assert d.edges == ((0, 1), (1, 2))


def test_make_design_rejects_out_of_range():
    with pytest.raises(ValueError):
        make_design("x", [(0, 5)], 5)


def test_clique_sizes():
    assert clique_sizes(turan_design(10, 3).edges) == [5, 5]
    assert clique_sizes([(0, 1), (1, 2)]) is None


def test_matching_limit():
    assert matching_design(N_NUMBERS // 2).k == N_NUMBERS
    with pytest.raises(ValueError):
        matching_design(N_NUMBERS // 2 + 1)


# ------------------------------------------------------------------ distribuzione esatta
@pytest.mark.parametrize("design", [turan_design(8, 3), turan_design(10, 4), complete_design(7)])
def test_dp_matches_enumeration(design):
    assert wins_counts(design) == _counts_by_enumeration(design.edges, design.k, N_NUMBERS, N_DRAWN)


def test_counts_sum_to_total():
    assert sum(wins_counts(make_design("path", [(0, 1), (1, 2), (2, 3)], 4))) == comb(N_NUMBERS, N_DRAWN)


def test_single_ambo_probability():
    pmf = wins_pmf(make_design("1", [(0, 1)], 2))
    assert pmf[1] == pytest.approx(P_AMBO)
    assert pmf[2:].sum() == 0


def test_guarantee_implies_win():
    k, t = 10, 3
    d = turan_design(k, t)
    assert analyze(d).p_win_any >= p_guarantee(k, t) - 1e-15


def test_p_guarantee_hypergeometric():
    assert p_guarantee(5, 5) == pytest.approx(1 / comb(N_NUMBERS, N_DRAWN))


# ------------------------------------------------------------------ valore atteso
@pytest.mark.parametrize("design", [turan_design(10, 3), matching_design(20), complete_design(7),
                                    make_design("path", [(0, 1), (1, 2), (2, 3)], 4)])
def test_ev_independent_of_design(design):
    s = analyze(design, stake=2.0, wheels=3, payout=AMBO_PAYOUT)
    assert s.ev_return == pytest.approx(theoretical_ev_return(design.n_edges, 2.0, 3, AMBO_PAYOUT))
    assert s.loss_pct == pytest.approx((1 - AMBO_PAYOUT * P_AMBO) * 100)


def test_multi_wheel_pmf_sums_to_one():
    s = analyze(turan_design(8, 3), wheels=4)
    assert s.pmf.sum() == pytest.approx(1.0)
    assert len(s.pmf) == 4 * comb(N_DRAWN, 2) + 1


# ------------------------------------------------------------------ budget
def test_max_edges_for_budget():
    assert max_edges_for_budget(20, 1, 1) == 20
    assert max_edges_for_budget(20, 0.1, 2) == 100
    assert max_edges_for_budget(0.5, 1, 1) == 0


def test_budget_duals():
    assert max_k_for_edges(3, 20) == 10
    assert best_t_for_edges(10, 20) == 3
    assert max_k_for_edges(3, 0) is None
    assert best_t_for_edges(10, 0) is None


# ------------------------------------------------------------------ simulazione
def test_simulation_close_to_exact():
    d = turan_design(8, 3)
    W = simulate_wins(d, 300_000, seed=1)
    p = 1 - wins_pmf(d)[0]
    se = np.sqrt(p * (1 - p) / len(W))
    assert abs((W >= 1).mean() - p) < 4 * se


def test_simulation_multi_wheel_shape():
    W = simulate_wins(turan_design(6, 3), 1000, wheels=3, seed=0)
    assert W.shape == (1000,) and W.max() <= 3 * comb(N_DRAWN, 2)
