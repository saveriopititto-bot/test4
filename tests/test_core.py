"""Test del modello: Turan vs ILP, probabilita' note, EV indipendente dal design, simulazione."""
from itertools import combinations
from math import comb

import numpy as np
import pytest

from core import (
    draws_until_first, waiting_gaps,
    AMBO_PAYOUT, N_DRAWN, N_NUMBERS, P_AMBO, _counts_by_enumeration, analyze, best_t_for_edges,
    certain_win_design, certain_win_extension, clique_sizes, complete_design, make_design, matching_design, max_edges_for_budget,
    max_k_for_edges, minimal_path, minimal_path_design, ortools_available, p_guarantee, simulate_wins, solve_ilp,
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


# ------------------------------------------------------------------ vincita certa
def _min_extra_bruteforce(k, t, N, d):
    """Minimo di ambi da aggiungere sui numeri liberi, provando tutti i sottoinsiemi (N piccolo)."""
    base = set(turan_design(k, t).edges)
    pairs = list(combinations(range(k, N), 2))
    groups = [set(g) for g in combinations(range(N), d)]
    best = None
    for mask in range(1 << len(pairs)):
        n_extra = bin(mask).count("1")
        if best is not None and n_extra >= best:
            continue
        edges = base | {pairs[i] for i in range(len(pairs)) if mask >> i & 1}
        if all(any(a in g and b in g for a, b in edges) for g in groups):
            best = n_extra
    return best


@pytest.mark.parametrize("k,t,N,d", [(3, 2, 8, 4), (2, 2, 7, 4), (4, 3, 8, 4), (3, 3, 7, 4), (4, 4, 7, 4)])
def test_certain_win_extension_matches_bruteforce(k, t, N, d):
    ext = certain_win_extension(k, t, N, d)
    brute = _min_extra_bruteforce(k, t, N, d)
    if brute is None:
        assert not ext.possible
    else:
        assert ext.possible and ext.extra_edges == brute


@pytest.mark.parametrize("k,t", [(8, 3), (3, 2), (10, 4), (40, 4), (90, 3)])
def test_certain_win_design_always_wins(k, t):
    d = certain_win_design(k, t)
    assert wins_counts(d)[0] == 0
    assert analyze(d).p_win_any == pytest.approx(1.0)
    ext = certain_win_extension(k, t)
    assert d.n_edges == ext.total_edges == turan_min_edges(k, t) + ext.extra_edges
    assert ext.total_edges >= ext.from_scratch_edges == turan_min_edges(N_NUMBERS, N_DRAWN)


def test_certain_win_values():
    ext = certain_win_extension(8, 3)
    assert ext.extra_groups == (41, 41) and ext.extra_edges == 1640 and ext.total_edges == 1652
    assert certain_win_extension(N_NUMBERS, 3).extra_edges == 0       # nessun numero libero


def test_certain_win_impossible_with_t_equal_d():
    ext = certain_win_extension(8, N_DRAWN)
    assert not ext.possible
    with pytest.raises(ValueError):
        certain_win_design(8, N_DRAWN)


# --------------------------------------------------------------------------- #
# Percorso minimo verso la vincita certa
# --------------------------------------------------------------------------- #
def _min_extra_supergraph(base_edges, N, d):
    """Minimo di ambi da aggiungere a base_edges perche' ogni d-upla di N numeri contenga un ambo."""
    base = {tuple(sorted(e)) for e in base_edges}
    others = [p for p in combinations(range(N), 2) if p not in base]
    subs = list(combinations(range(N), d))
    for r in range(len(others) + 1):
        for extra in combinations(others, r):
            e = base | set(extra)
            if all(any(p in e for p in combinations(s, 2)) for s in subs):
                return r
    return None


@pytest.mark.parametrize("N,d,k,t", [(6, 3, 3, 2), (6, 3, 4, 2), (7, 3, 4, 3), (7, 3, 5, 2), (7, 4, 4, 3), (8, 4, 6, 3)])
def test_minimal_path_matches_bruteforce(N, d, k, t):
    mp = minimal_path(k, t, N, d)
    assert mp.extra_edges == _min_extra_supergraph(turan_design(k, t).edges, N, d)


@pytest.mark.parametrize("k,t", [(8, 3), (20, 2), (40, 4), (5, 5), (60, 2), (3, 2)])
def test_minimal_path_design_always_wins(k, t):
    des = minimal_path_design(k, t)
    assert wins_counts(des)[0] == 0
    assert len(des.edges) == minimal_path(k, t).total_edges


def test_minimal_path_values():
    mp = minimal_path(8, 3)
    assert mp.total_edges == 968 and mp.extra_edges == 956
    assert mp.extra_edges <= certain_win_extension(8, 3).extra_edges
    assert minimal_path(60, 2).total_edges == 1905
    assert minimal_path(90, 3).extra_edges == 0   # tutti i numeri sono gia' tuoi: non serve aggiungere nulla


# ------------------------------------------------------------------ attesa prima di vincere
def test_draws_until_first_values():
    w = draws_until_first(0.5)
    assert (w.mean, w.median, w.q90) == (2.0, 1, 4)
    w = draws_until_first(0.1)
    assert w.mean == pytest.approx(10)
    assert w.median == 7 and w.q90 == 22          # 1 - 0.9**7 = 0.52, 1 - 0.9**22 = 0.90
    assert draws_until_first(1.0).median == 1
    assert draws_until_first(0.0) is None
    with pytest.raises(ValueError):
        draws_until_first(1.5)


@pytest.mark.parametrize("p", [0.003, 0.0285, 0.3])
def test_draws_until_first_quantiles_are_minimal(p):
    w = draws_until_first(p)
    for n, a in ((w.median, 0.5), (w.q90, 0.9)):
        assert 1 - (1 - p) ** n >= a > 1 - (1 - p) ** (n - 1)


def test_waiting_gaps():
    assert waiting_gaps(np.array([0, 0, 1, 0, 1, 1, 0])).tolist() == [3, 2, 1]
    assert len(waiting_gaps(np.zeros(5, dtype=bool))) == 0


def test_simulated_waits_match_geometric():
    d = turan_design(8, 3)
    W = simulate_wins(d, 300_000, seed=3)
    gaps = waiting_gaps(W >= 1)
    w = draws_until_first(analyze(d).p_win_any)
    se = gaps.std(ddof=1) / np.sqrt(len(gaps))
    assert abs(gaps.mean() - w.mean) < 4 * se
