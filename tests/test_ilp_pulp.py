"""Test del modulo PuLP: ottimo uguale a Turan e metriche uguali a quelle di core."""
from math import comb

import pytest

from core import P_AMBO, analyze, make_design, p_guarantee, turan_min_edges
from ilp_pulp import analizza_metriche_sistema, pulp_available, solve_ilp_lotto, turan_minimum_ambos

needs_pulp = pytest.mark.skipif(not pulp_available(), reason="PuLP non installato")


@pytest.mark.parametrize("k,t", [(6, 3), (10, 3), (9, 4), (11, 5), (7, 2)])
def test_turan_matches_core(k, t):
    assert turan_minimum_ambos(k, t) == turan_min_edges(k, t)


@needs_pulp
@pytest.mark.parametrize("k,t", [(6, 3), (8, 4), (9, 5)])
def test_pulp_optimum_is_turan(k, t):
    res = solve_ilp_lotto(k, t)
    assert res.stato == "Optimal"
    assert len(res.ambi) == turan_minimum_ambos(k, t)


@needs_pulp
def test_metrics_match_core():
    k, t = 8, 3
    res = solve_ilp_lotto(k, t)
    m = analizza_metriche_sistema(k, t, res.ambi, costo_per_ambo=2.0, quota=250)
    s = analyze(make_design("pulp", [(a - 1, b - 1) for a, b in res.ambi], k), stake=2.0, payout=250)
    assert m.prob_vincita_reale == pytest.approx(s.p_win_any, abs=1e-15)
    assert m.prob_garanzia == pytest.approx(p_guarantee(k, t))
    assert m.ritorno_atteso == pytest.approx(s.ev_return)
    assert m.perdita_pct == pytest.approx((1 - 250 * P_AMBO) * 100)


def test_metrics_single_ambo():
    m = analizza_metriche_sistema(2, 2, [(1, 2)])
    assert m.casi_vincita_reale == comb(88, 3)
    assert m.prob_vincita_reale == pytest.approx(P_AMBO)


def test_invalid_t():
    if not pulp_available():
        pytest.skip("PuLP non installato")
    with pytest.raises(ValueError):
        solve_ilp_lotto(4, 5)
