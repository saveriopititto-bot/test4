"""Test delle regole di calcolo delle vincite."""
from math import comb

import pytest

import regole as r
from core import P_AMBO, analyze, theoretical_ev_return, turan_design

BARI = {"Bari": (10, 21, 5, 6, 7)}


def test_tutte_esclude_nazionale():
    assert r.espandi_ruote([r.TUTTE]) == r.RUOTE_CITTADINE
    assert r.NAZIONALE not in r.espandi_ruote([r.TUTTE])
    assert len(r.espandi_ruote([r.TUTTE, r.NAZIONALE])) == 11
    with pytest.raises(ValueError):
        r.espandi_ruote(["Atlantide"])


def test_sedi_coprono_tutte_le_ruote():
    ruote = [x for v in r.SEDI_ESTRAZIONE.values() for x in v]
    assert sorted(ruote) == sorted(r.RUOTE)


@pytest.mark.parametrize("importo,ok", [(1, True), (1.5, True), (200, True), (0.5, False),
                                         (1.2, False), (200.5, False)])
def test_valida_importo(importo, ok):
    assert (r.valida_importo(importo) == []) is ok


def test_scontrini_necessari():
    assert r.scontrini_necessari(12) == 1
    assert r.scontrini_necessari(200) == 1
    assert r.scontrini_necessari(200.5) == 2
    assert r.scontrini_necessari(1000) == 5


@pytest.mark.parametrize("numeri,poste,err", [
    ((), {r.AMBO: 1}, "da 1 a 10"),
    (tuple(range(1, 12)), {r.AMBO: 1}, "da 1 a 10"),
    ((1, 1), {r.AMBO: 1}, "distinti"),
    ((0, 5), {r.AMBO: 1}, "distinti"),
    ((5,), {r.AMBO: 1}, "almeno 2"),
    ((1, 2, 3), {r.QUATERNA: 1}, "almeno 4"),
    ((5,), {r.ESTRATTO_DETERMINATO: 1}, "posizione"),
    ((1, 2), {}, "almeno una sorte"),
])
def test_giocata_non_valida(numeri, poste, err):
    with pytest.raises(ValueError, match=err):
        r.Giocata(numeri, poste)


def test_ambo_singolo():
    e = r.calcola_vincita([r.Giocata((10, 21), {r.AMBO: 1})], BARI, ritenuta=0)
    assert e.lordo == pytest.approx(250)
    assert e.netto == pytest.approx(250)


def test_ritenuta_8_percento():
    e = r.calcola_vincita([r.Giocata((10, 21), {r.AMBO: 1})], BARI)
    assert e.ritenuta == pytest.approx(20)
    assert e.netto == pytest.approx(230)


def test_posta_divisa_tra_combinazioni():
    # ambo su 3 numeri: 3 combinazioni, ne esce una -> 250 * 1/3
    e = r.calcola_vincita([r.Giocata((10, 21, 50), {r.AMBO: 1})], BARI, ritenuta=0)
    assert e.lordo == pytest.approx(250 / 3)
    # terno su 3 numeri tutti estratti: 4500 + i tre ambi non giocati
    e = r.calcola_vincita([r.Giocata((5, 6, 7), {r.TERNO: 1, r.AMBO: 1})], BARI, ritenuta=0)
    assert e.lordo == pytest.approx(4500 + 250)


def test_posta_divisa_tra_ruote():
    estr = {x: (1, 2, 3, 4, 5) for x in r.RUOTE}
    e = r.calcola_vincita([r.Giocata((1, 2), {r.AMBO: 10}, (r.TUTTE,))], estr, ritenuta=0)
    assert len(e.righe) == 10                       # Nazionale esclusa
    assert e.lordo == pytest.approx(10 * 250)       # 1 euro per ruota


def test_estratto_e_determinato():
    g = [r.Giocata((21,), {r.ESTRATTO: 1}), r.Giocata((21,), {r.ESTRATTO_DETERMINATO: 1}, posizione=2),
         r.Giocata((21,), {r.ESTRATTO_DETERMINATO: 1}, posizione=1)]
    e = r.calcola_vincita(g, BARI, ritenuta=0)
    assert [x.giocata for x in e.righe] == [0, 1]
    assert e.lordo == pytest.approx(11.233 + 55)


def test_cinquina_e_tetto():
    g = [r.Giocata((10, 21, 5, 6, 7), {r.CINQUINA: 2})]
    e = r.calcola_vincita(g, BARI, ritenuta=0)
    assert e.lordo > r.VINCITA_MAX_SCONTRINO
    assert e.lordo_pagabile == r.VINCITA_MAX_SCONTRINO
    e = r.calcola_vincita(g, BARI)
    assert e.netto == pytest.approx(r.VINCITA_MAX_SCONTRINO * (1 - r.RITENUTA))


def test_ambetto_combinazioni():
    assert r.combinazioni_ambetto([10, 20]) == {frozenset(p) for p in [(10, 19), (10, 21), (20, 9), (20, 11)]}
    # numeri adiacenti: il vicino giocato non conta (sarebbe un ambo)
    assert r.combinazioni_ambetto([10, 11]) == {frozenset((10, 12)), frozenset((11, 9))}
    # numerazione circolare
    assert r.combinazioni_ambetto([1, 90]) == {frozenset((1, 89)), frozenset((90, 2))}


def test_ambetto_vincita():
    # esce 10 con 21 (successivo di 20): 1 combinazione su 4 -> 260 / 4 = 65
    e = r.calcola_vincita([r.Giocata((10, 20), {r.AMBETTO: 1})], BARI, ritenuta=0)
    assert e.lordo == pytest.approx(65)
    # l'ambo esatto non vince l'ambetto
    e = r.calcola_vincita([r.Giocata((10, 21), {r.AMBETTO: 1})], BARI, ritenuta=0)
    assert e.lordo == 0


def test_estrazione_non_valida():
    with pytest.raises(ValueError):
        r.calcola_vincita([], {"Bari": (1, 2, 3, 4)})
    with pytest.raises(ValueError):
        r.calcola_vincita([], {"Bari": (1, 2, 3, 4, 4)})


def test_estrazione_casuale():
    e = r.estrazione_casuale(0)
    r.valida_estrazione(e)
    assert set(e) == set(r.RUOTE)


@pytest.mark.parametrize("sorte", list(r.COEFFICIENTI))
def test_ritorno_atteso_sotto_la_posta(sorte):
    assert 0 < r.ritorno_atteso_per_euro(sorte, r.RITENUTA) < r.ritorno_atteso_per_euro(sorte) < 1


def test_ritorno_atteso_ambo_coincide_con_core():
    assert r.ritorno_atteso_per_euro(r.AMBO) == pytest.approx(250 * P_AMBO)


def test_tetto_mai_raggiunto_con_ambi():
    assert r.tetto_mai_raggiunto_ambo()


# ------------------------------------------------------------------ core: ritenuta e concorsi
def test_analyze_ritenuta():
    d = turan_design(8, 3)
    s = analyze(d, stake=1, tax=r.RITENUTA)
    assert s.loss_pct == pytest.approx((1 - 250 * 0.92 * P_AMBO) * 100)
    assert s.win_value == pytest.approx(230)


def test_analyze_concorsi():
    d = turan_design(8, 3)
    s = analyze(d, stake=1, wheels=3, tax=r.RITENUTA, draws=50)
    assert s.cost == pytest.approx(d.n_edges * 3 * 50)
    assert s.pmf.sum() == pytest.approx(1)
    assert len(s.pmf) == 3 * 50 * comb(5, 2) + 1
    assert s.ev_return == pytest.approx(theoretical_ev_return(d.n_edges, 1, 3, 250, r.RITENUTA, 50))
    s1 = analyze(d, stake=1, wheels=3)
    assert s.p_win_any == pytest.approx(1 - (1 - s1.p_win_any) ** 50)


def test_sistema_vs_calcolatore():
    """Il sistema giocato ambo per ambo nel calcolatore incassa quanto previsto dal modello."""
    d = turan_design(8, 3)
    estr = {"Bari": (1, 2, 3, 50, 60)}   # escono 1,2,3: gruppi {0..3},{4..7} -> ambi 1-2, 1-3, 2-3
    g = [r.Giocata((a + 1, b + 1), {r.AMBO: 1}, ("Bari",)) for a, b in d.edges]
    e = r.calcola_vincita(g, estr)
    assert e.netto == pytest.approx(3 * analyze(d, stake=1, tax=r.RITENUTA).win_value)
