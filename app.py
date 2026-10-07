"""Sistemi ridotti per ambi al Lotto — modello a grafo (app Streamlit)."""
from __future__ import annotations

import re
from math import comb

import numpy as np
import pandas as pd
import streamlit as st

import ilp_pulp
import regole
import viz
from core import (
    AMBO_PAYOUT, N_DRAWN, N_NUMBERS, P_AMBO, Design, analyze, best_t_for_edges, complete_design,
    make_design, matching_design, max_edges_for_budget, max_k_for_edges, ortools_available,
    simulate_wins, solve_ilp, turan_design, turan_min_edges,
)

st.set_page_config(page_title="Sistemi ridotti per ambi", page_icon="🎯", layout="wide")


# ------------------------------------------------------------------ formattazione
def _it(s: str) -> str:
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def eur(x: float) -> str:
    return _it(f"{x:,.2f}") + " €"


def pct(x: float, d: int = 3) -> str:
    return _it(f"{x:.{d}f}") + "%"


def one_in(p: float) -> str:
    return "—" if p <= 0 else "1 su " + _it(f"{1 / p:,.0f}")


def parse_numbers(text: str, k: int) -> tuple[list[int], str | None]:
    default = list(range(1, k + 1))
    if not text.strip():
        return default, None
    try:
        nums = [int(x) for x in re.split(r"[,\s;]+", text.strip()) if x]
    except ValueError:
        return default, "Inserisci solo numeri interi separati da virgole: uso 1…k."
    if any(n < 1 or n > N_NUMBERS for n in nums) or len(set(nums)) != len(nums):
        return default, f"I numeri devono essere distinti e tra 1 e {N_NUMBERS}: uso 1…k."
    if len(nums) != k:
        return default, f"Servono esattamente {k} numeri (ne hai inseriti {len(nums)}): uso 1…k."
    return nums, None


# ------------------------------------------------------------------ sidebar
st.sidebar.header("Parametri")
MODE_1 = "Garanzia → costo minimo"
MODE_2 = "Budget + garanzia → quanti numeri"
MODE_3 = "Budget + numeri → garanzia migliore"
mode = st.sidebar.radio("Cosa vuoi fissare?", [MODE_1, MODE_2, MODE_3])

stake = st.sidebar.number_input(
    "Puntata per ambo e per ruota (€)", min_value=0.05, value=1.0, step=0.05,
    help="Le regole chiedono un importo per scontrino tra 1 e 200 €, a incrementi di 0,50 €.")
if st.sidebar.checkbox("Tutte le ruote (le 10 cittadine)",
                       help="Le giocate \"su tutte le ruote\" non comprendono la ruota Nazionale."):
    ruote = regole.RUOTE_CITTADINE
    if st.sidebar.checkbox("Aggiungi la ruota Nazionale"):
        ruote += (regole.NAZIONALE,)
else:
    ruote = tuple(st.sidebar.multiselect("Ruote", regole.RUOTE, default=["Bari"],
                                         help="Stessi ambi su più ruote: estrazioni indipendenti."))
    if not ruote:
        st.sidebar.error("Scegli almeno una ruota.")
        st.stop()
wheels = len(ruote)
draws = int(st.sidebar.number_input(
    "Concorsi (abbonamento)", min_value=1, max_value=regole.MAX_CONCORSI, value=1, step=1,
    help=f"Stessa giocata per più concorsi consecutivi, fino a {regole.MAX_CONCORSI}."))
payout = st.sidebar.number_input("Quota ambo (x puntata)", min_value=1.0, value=AMBO_PAYOUT, step=10.0,
                                 help="Coefficiente ufficiale per l'ambo su una singola ruota: 250.")
tax = regole.RITENUTA if st.sidebar.checkbox(
    f"Ritenuta {regole.RITENUTA:.0%} sulle vincite", value=True,
    help="Sull'ammontare delle vincite è applicata la ritenuta dell'8%.") else 0.0

k: int
t: int
if mode == MODE_1:
    k = st.sidebar.slider("Numeri scelti (k)", 3, 40, 8)
    t = st.sidebar.slider("Garanzia t", 2, min(N_DRAWN, k), min(3, k),
                          help="Se escono almeno t dei tuoi k numeri, vinci almeno un ambo.")
elif mode == MODE_2:
    budget = st.sidebar.number_input("Budget totale (€)", min_value=0.0, value=20.0, step=1.0)
    t = st.sidebar.slider("Garanzia t", 2, N_DRAWN, 3)
    max_edges = max_edges_for_budget(budget, stake, wheels * draws)
    k_best = max_k_for_edges(t, max_edges)
    if k_best is None:
        st.error(f"Con {eur(budget)} non si copre nemmeno il minimo: serve almeno {eur(stake * wheels * draws)}.")
        st.stop()
    k = k_best
else:
    budget = st.sidebar.number_input("Budget totale (€)", min_value=0.0, value=20.0, step=1.0)
    k = st.sidebar.slider("Numeri scelti (k)", 3, 40, 10)
    max_edges = max_edges_for_budget(budget, stake, wheels * draws)
    t_best = best_t_for_edges(k, max_edges)
    if t_best is None:
        need = turan_min_edges(k, min(N_DRAWN, k)) * stake * wheels * draws
        st.error(f"Con {k} numeri la garanzia più debole (t={min(N_DRAWN, k)}) costa almeno {eur(need)}.")
        st.stop()
    t = t_best

numbers_text = st.sidebar.text_input("I tuoi numeri (opzionale)", placeholder=f"{k} numeri separati da virgola")
labels, num_err = parse_numbers(numbers_text, k)
if num_err:
    st.sidebar.warning(num_err)
st.sidebar.caption(f"Numeri necessari: **{k}**")

# ------------------------------------------------------------------ calcolo principale
design = turan_design(k, t)
stats = analyze(design, t=t, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
stats1 = stats if draws == 1 else analyze(design, t=t, stake=stake, wheels=wheels, payout=payout, tax=tax)
importo = stats1.cost                       # importo per concorso
n_scontrini = regole.scontrini_necessari(importo)
importo_err = [e for e in regole.valida_importo(importo) if "massimo" not in e]
ruote_txt = "tutte" if ruote == regole.RUOTE_CITTADINE else ", ".join(ruote)

st.title("🎯 Sistemi ridotti per ambi al Lotto")
st.caption("Modello a grafo: numeri = nodi, ambi giocati = archi. Strumento didattico: "
           "non esiste un sistema che renda il gioco conveniente.")

if mode != MODE_1:
    st.success(f"Soluzione ottima: **k = {k} numeri, garanzia t = {t}**, {design.n_edges} ambi "
               f"({eur(stats.cost)} su {eur(budget)} di budget).")

tab_res, tab_win, tab_cmp, tab_ilp, tab_pulp, tab_sim, tab_model = st.tabs(
    ["Risultato", "Calcolo vincite", "Confronto", "Verifica ILP", "ILP con PuLP", "Simulazione", "Modello"])

# ------------------------------------------------------------------ tab Risultato
with tab_res:
    c = st.columns(5)
    c[0].metric("Ambi da giocare", design.n_edges,
                help=f"Tutti gli ambi su {k} numeri sarebbero {comb(k, 2)}.")
    c[1].metric("Costo totale", eur(stats.cost),
                help=f"{eur(importo)} per concorso × {draws} concorsi, su {wheels} ruote ({ruote_txt}).")
    c[2].metric("Garanzia", f"{t} su {k}", help=f"Se escono almeno {t} dei tuoi {k} numeri vinci ≥ 1 ambo.")
    c[3].metric("P(garanzia scatta)", pct(stats.p_guarantee * 100), delta=one_in(stats.p_guarantee),
                delta_color="off", help="Per singola ruota: P(escono almeno t dei k numeri).")
    c[4].metric("P(vincere ≥ 1 ambo)", pct(stats.p_win_any * 100), delta=one_in(stats.p_win_any),
                delta_color="off")

    for e in importo_err:
        st.warning(f"Giocata non valida: {e} (importo per concorso {eur(importo)}).")
    if n_scontrini > 1:
        st.info(f"Importo per concorso {eur(importo)}: oltre il massimo di {eur(regole.IMPORTO_MAX)} per scontrino, "
                f"servono almeno **{n_scontrini} scontrini**.")
    tax_txt = f", ritenuta dell'{tax:.0%} inclusa" if tax else ", senza ritenuta"
    st.info(f"**Perdita media: {eur(-stats.ev_net)} su {eur(stats.cost)} giocati ({pct(stats.loss_pct, 1)}{tax_txt}).** "
            f"Vale per qualsiasi sistema con la stessa quota: il design cambia frequenza e varianza delle vincite, "
            f"non la perdita attesa. Deviazione standard del netto: {eur(stats.std_net)}; "
            f"probabilità di chiudere in positivo: {pct(stats.p_profit * 100)}.")

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Il grafo")
        if design.n_edges <= 1500:
            st.plotly_chart(viz.graph_figure(design, labels), width="stretch")
        else:
            st.caption("Grafo troppo fitto per essere disegnato (oltre 1500 archi).")
        sizes = design.clique_sizes() or []
        st.caption(f"{len(sizes)} gruppi di numeri che si giocano tutti tra loro: "
                   + ", ".join(str(s) for s in sizes) + ".")
    with right:
        st.subheader("Distribuzione dell'esito")
        rows = []
        for j, p in enumerate(stats.pmf):
            if p <= 1e-12:
                continue
            rows.append({
                "Ambi vincenti": j,
                "Vincita lorda": eur(j * stake * payout),
                "Vincita netta": eur(j * stats.win_value),
                "Saldo": eur(j * stats.win_value - stats.cost),
                "Probabilità": pct(p * 100, 4),
                "Frequenza": one_in(p),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if regole.tetto_mai_raggiunto_ambo():
            st.caption(f"Con sole puntate su ambo uno scontrino (max {eur(regole.IMPORTO_MAX)}) vince al massimo "
                       f"{eur(regole.COEFFICIENTI[regole.AMBO] * regole.IMPORTO_MAX)}: il tetto di "
                       f"{eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino non viene mai raggiunto.")
        if stats.pmf[1:].sum() > 0:
            st.plotly_chart(viz.pmf_figure(stats), width="stretch")

    st.subheader("Schedina")
    ticket = pd.DataFrame(
        [{"Ambo": i + 1, "Numero A": labels[a], "Numero B": labels[b],
          "Posta (€)": round(stake * wheels, 2), "Ruote": ruote_txt, "Concorsi": draws}
         for i, (a, b) in enumerate(design.edges)])
    st.caption("La posta di ogni ambo è divisa tra le ruote giocate (i coefficienti valgono per una singola ruota).")
    st.dataframe(ticket, hide_index=True, width="stretch", height=260)
    st.download_button("Scarica CSV", ticket.to_csv(index=False).encode("utf-8"),
                       file_name=f"ambi_k{k}_t{t}.csv", mime="text/csv")

# ------------------------------------------------------------------ tab Calcolo vincite
SORTI_LABEL = {
    regole.ESTRATTO: "Estratto", regole.ESTRATTO_DETERMINATO: "Estratto determinato",
    regole.AMBO: "Ambo", regole.AMBETTO: "Ambetto", regole.TERNO: "Terno",
    regole.QUATERNA: "Quaterna", regole.CINQUINA: "Cinquina",
}


def parse_list(text: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s;\-]+", text.strip()) if x]


with tab_win:
    st.subheader("Calcolo delle vincite su un'estrazione")
    st.markdown(
        "Applica le regole ufficiali: posta divisa tra combinazioni e ruote, coefficienti per singola ruota, "
        f"tetto di {eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino e ritenuta dell'{regole.RITENUTA:.0%}.")
    coeff = pd.DataFrame([{"Sorte": SORTI_LABEL[s_], "Coefficiente": _it(f"{c_:,.3f}".rstrip("0").rstrip(".")),
                           "Ritorno medio per 1 €": eur(regole.ritorno_atteso_per_euro(s_)),
                           "Con ritenuta": eur(regole.ritorno_atteso_per_euro(s_, regole.RITENUTA))}
                          for s_, c_ in regole.COEFFICIENTI.items()])
    with st.expander("Coefficienti e ritorno medio per sorte"):
        st.dataframe(coeff, hide_index=True, width="stretch")

    st.markdown("**Estrazione**")
    src = st.radio("Numeri estratti", ["Casuale", "Inseriti a mano"], horizontal=True, key="win_src")
    if src == "Casuale":
        seed_w = int(st.number_input("Seed", 0, 1_000_000, 1, key="win_seed"))
        estrazione = regole.estrazione_casuale(seed_w)
    else:
        estrazione = {}
        cols = st.columns(4)
        for i, r_ in enumerate(regole.RUOTE):
            txt = cols[i % 4].text_input(r_, key=f"win_e_{r_}", placeholder="5 numeri in ordine")
            if txt.strip():
                try:
                    estrazione[r_] = tuple(parse_list(txt))
                except ValueError:
                    st.error(f"{r_}: inserisci solo numeri interi.")
    try:
        regole.valida_estrazione(estrazione)
    except ValueError as e:
        st.error(str(e))
        estrazione = {}
    if estrazione:
        st.dataframe(pd.DataFrame([{"Ruota": r_, **{f"{i + 1}°": n for i, n in enumerate(v)}}
                                   for r_, v in estrazione.items()]), hide_index=True, width="stretch")

    st.markdown("**Scontrino**")
    giocate: list[regole.Giocata] = []
    if st.checkbox(f"Includi il sistema ridotto ({design.n_edges} ambi, posta {eur(stake * wheels)} "
                   f"ciascuno su {ruote_txt})", value=design.n_edges <= 2000, key="win_sys"):
        giocate += [regole.Giocata((labels[a], labels[b]), {regole.AMBO: stake * wheels}, ruote)
                    for a, b in design.edges]
    with st.expander("Aggiungi una giocata libera", expanded=not giocate):
        c = st.columns([2, 2, 1])
        nums_txt = c[0].text_input("Numeri (da 1 a 10)", key="win_nums", placeholder="es. 10, 20, 33")
        r_sel = c[1].multiselect("Ruote", [regole.TUTTE, *regole.RUOTE], default=["Bari"], key="win_ruote")
        pos = int(c[2].number_input("Posizione (estratto det.)", 1, regole.N_ESTRATTI, 1, key="win_pos"))
        c = st.columns(len(regole.COEFFICIENTI))
        poste = {s_: c[i].number_input(SORTI_LABEL[s_], 0.0, regole.IMPORTO_MAX, 0.0, step=0.5, key=f"win_p_{s_}")
                 for i, s_ in enumerate(regole.COEFFICIENTI)}
        if nums_txt.strip() and any(poste.values()):
            try:
                giocate.append(regole.Giocata(tuple(parse_list(nums_txt)), poste, tuple(r_sel), posizione=pos))
            except ValueError as e:
                st.error(f"Giocata libera non valida: {e}")

    if giocate and estrazione:
        imp = sum(g.importo for g in giocate)
        for e in regole.valida_importo(imp):
            st.warning(f"{e} (importo dello scontrino: {eur(imp)}).")
        esito = regole.calcola_vincita(giocate, estrazione, ritenuta=tax)
        c = st.columns(5)
        c[0].metric("Importo", eur(esito.importo))
        c[1].metric("Vincita lorda", eur(esito.lordo))
        c[2].metric("Dopo il tetto", eur(esito.lordo_pagabile),
                    help=f"Massimo {eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino.")
        c[3].metric(f"Ritenuta {tax:.0%}", eur(esito.ritenuta))
        c[4].metric("Vincita netta", eur(esito.netto), delta=eur(esito.netto - esito.importo))
        if esito.righe:
            st.dataframe(pd.DataFrame([{
                "Giocata": r_.giocata + 1, "Numeri": "-".join(map(str, giocate[r_.giocata].numeri)),
                "Ruota": r_.ruota, "Sorte": SORTI_LABEL[r_.sorte],
                "Combinazioni vincenti": f"{r_.vincenti} su {r_.combinazioni}",
                "Vincita lorda": eur(r_.lordo)} for r_ in esito.righe]), hide_index=True, width="stretch")
        else:
            st.caption("Nessuna combinazione vincente.")
    elif not giocate:
        st.caption("Includi il sistema o aggiungi una giocata per calcolare le vincite.")

# ------------------------------------------------------------------ tab Confronto
with tab_cmp:
    st.subheader("Stessa spesa, design diversi")

    def row(label: str, d: Design, guarantee_t: int | None) -> dict:
        s = analyze(d, t=guarantee_t, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
        return {
            "Design": label, "Ambi": d.n_edges, "Costo": eur(s.cost),
            "Garanzia": f"{guarantee_t} su {d.k}" if guarantee_t else "nessuna",
            "P(garanzia)": pct(s.p_guarantee * 100) if s.p_guarantee is not None else "—",
            "P(≥1 ambo)": pct(s.p_win_any * 100), "Frequenza": one_in(s.p_win_any),
            "Perdita media": eur(-s.ev_net), "Perdita %": pct(s.loss_pct, 1),
            "Dev. std netto": eur(s.std_net), "P(profitto)": pct(s.p_profit * 100),
        }

    rows = [row(f"Sistema ridotto k={k}, t={t}", design, t)]
    if k > 2 and t != 2:
        rows.append(row(f"Tutti gli ambi su {k} numeri", complete_design(k), 2))
    if 2 * design.n_edges <= N_NUMBERS:
        rows.append(row(f"Coppie disgiunte ({design.n_edges} ambi)", matching_design(design.n_edges), None))
    else:
        st.caption(f"Le coppie disgiunte con {design.n_edges} ambi richiederebbero "
                   f"{2 * design.n_edges} numeri (> {N_NUMBERS}): confronto non disponibile.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown(
        "La **perdita percentuale è identica** in tutte le righe (linearità del valore atteso). "
        "Cambia la *forma* del rischio: il sistema ridotto concentra gli ambi su pochi numeri e garantisce "
        "una vincita quando ne escono almeno *t*, ma gli ambi si sovrappongono; le coppie disgiunte non "
        "garantiscono nulla, però hanno la più alta probabilità di incassare almeno una volta."
    )

    @st.cache_data(show_spinner=False)
    def frontier(stake_: float, wheels_: int, payout_: float, tax_: float, draws_: int, k_max: int = 40) -> dict:
        out: dict[str, dict[str, list]] = {}
        for tt in range(2, N_DRAWN + 1):
            name = "Tutti gli ambi (t=2)" if tt == 2 else f"Sistema ridotto t={tt}"
            s: dict[str, list] = {"cost": [], "p": [], "k": [], "edges": []}
            for kk in range(tt, k_max + 1):
                d = turan_design(kk, tt)
                st_ = analyze(d, stake=stake_, wheels=wheels_, payout=payout_, tax=tax_, draws=draws_)
                s["cost"].append(st_.cost)
                s["p"].append(st_.p_win_any * 100)
                s["k"].append(kk)
                s["edges"].append(d.n_edges)
            out[name] = s
        s = {"cost": [], "p": [], "k": [], "edges": []}
        for e in range(1, N_NUMBERS // 2 + 1):
            d = matching_design(e)
            st_ = analyze(d, stake=stake_, wheels=wheels_, payout=payout_, tax=tax_, draws=draws_)
            s["cost"].append(st_.cost)
            s["p"].append(st_.p_win_any * 100)
            s["k"].append(d.k)
            s["edges"].append(e)
        out["Coppie disgiunte (nessuna garanzia)"] = s
        return out

    st.subheader("Frontiera: costo vs probabilità di vincita")
    st.plotly_chart(
        viz.frontier_figure(frontier(stake, wheels, payout, tax, draws), (stats.cost, stats.p_win_any * 100)),
        width="stretch")
    st.caption("Ogni punto è un design (k crescente lungo la curva). A parità di costo, più si alza la "
               "garanzia richiesta più si rinuncia a probabilità di vincita.")

# ------------------------------------------------------------------ tab ILP
with tab_ilp:
    st.subheader("Verifica con programmazione lineare intera")
    st.markdown("Risolve **min Σ x_e** con il vincolo che ogni gruppo di *t* numeri contenga almeno "
                "*m* ambi giocati. Con *m = 1* il risultato deve coincidere con la formula di Turán; "
                "con *m ≥ 2* non c'è una formula semplice e il solver è lo strumento giusto.")
    if not ortools_available():
        st.warning("OR-Tools non è installato: `pip install ortools`.")
    else:
        c = st.columns(4)
        k_i = c[0].slider("k (numeri)", 4, 14, min(max(k, 4), 10), key="ilp_k")
        t_i = c[1].slider("t (garanzia)", 2, min(N_DRAWN, k_i), min(t, k_i, N_DRAWN), key="ilp_t")
        m_i = c[2].number_input("m (ambi garantiti)", 1, comb(t_i, 2), 1, key="ilp_m")
        tl = c[3].number_input("Tempo max (s)", 5, 300, 30, step=5, key="ilp_tl")
        n_con = comb(k_i, t_i)
        st.caption(f"{comb(k_i, 2)} variabili, {n_con} vincoli.")
        if st.button("Risolvi con CP-SAT", type="primary"):
            with st.spinner("Calcolo in corso…"):
                res = solve_ilp(k_i, t_i, int(m_i), time_limit=float(tl))
            st.session_state["ilp"] = ((k_i, t_i, int(m_i)), res)
        if "ilp" in st.session_state:
            (kk, tt, mm), res = st.session_state["ilp"]
            st.markdown(f"**Ultimo risultato** — k={kk}, t={tt}, m={mm}")
            if res.objective is None:
                st.error(f"Nessuna soluzione trovata (stato: {res.status}).")
            else:
                d_ilp = make_design("ILP", res.edges, kk)
                turan = turan_min_edges(kk, tt)
                c = st.columns(4)
                c[0].metric("Stato", res.status)
                c[1].metric("Ambi (ILP)", res.objective)
                c[2].metric("Ambi (Turán)", turan if mm == 1 else "—")
                c[3].metric("Tempo", f"{res.wall_time:.2f} s")
                if mm == 1:
                    if res.status == "OPTIMAL" and res.objective == turan:
                        st.success("✔ L'ottimo ILP coincide con la formula di Turán.")
                    elif res.objective == turan:
                        st.info("Valore uguale a Turán, ma il solver non ha chiuso la prova di ottimalità.")
                    else:
                        st.warning("Valore diverso da Turán: soluzione non ottima entro il tempo limite.")
                sizes = d_ilp.clique_sizes()
                st.caption("Struttura trovata: "
                           + (f"cliche disgiunte di taglia {', '.join(map(str, sizes))}."
                              if sizes is not None else "non è un'unione di cliche."))
                s_ilp = analyze(d_ilp, t=tt if mm == 1 else None, stake=stake, wheels=wheels, payout=payout,
                                tax=tax, draws=draws)
                c = st.columns(3)
                c[0].metric("P(≥1 ambo)", pct(s_ilp.p_win_any * 100))
                c[1].metric("Perdita media", eur(-s_ilp.ev_net))
                c[2].metric("Perdita %", pct(s_ilp.loss_pct, 1))
                with st.expander("Elenco ambi (numeri 1…k)"):
                    st.write(", ".join(f"{a + 1}-{b + 1}" for a, b in res.edges))

# ------------------------------------------------------------------ tab PuLP
with tab_pulp:
    st.subheader("Sistema ridotto con PuLP (CBC)")
    st.markdown("Stesso modello ILP risolto con **PuLP** e metriche calcolate per **enumerazione diretta** "
                "dei sottoinsiemi estratti: un controllo indipendente dai calcoli del resto dell'app. "
                "Le metriche si riferiscono a una ruota.")
    if not ilp_pulp.pulp_available():
        st.warning("PuLP con il solver CBC non è disponibile: `pip install \"pulp<4\"` "
                   "(dalla 4.0 PuLP non include più CBC).")
    else:
        c = st.columns(3)
        k_p = c[0].slider("k (numeri)", 4, 12, min(max(k, 4), 12), key="pulp_k")
        t_p = c[1].slider("t (garanzia)", 2, min(N_DRAWN, k_p), min(t, k_p, N_DRAWN), key="pulp_t")
        tl_p = c[2].number_input("Tempo max (s)", 5, 300, 30, step=5, key="pulp_tl")
        st.caption(f"{comb(k_p, 2)} variabili, {comb(k_p, t_p)} vincoli.")
        if st.button("Risolvi con PuLP", type="primary"):
            with st.spinner("Calcolo in corso…"):
                res_p = ilp_pulp.solve_ilp_lotto(k_p, t_p, time_limit=float(tl_p))
                met = ilp_pulp.analizza_metriche_sistema(k_p, t_p, res_p.ambi, costo_per_ambo=stake,
                                                         quota=payout * (1 - tax))
            st.session_state["pulp"] = (res_p, met)
        if "pulp" in st.session_state:
            res_p, met = st.session_state["pulp"]
            st.markdown(f"**Ultimo risultato** — k={met.k}, t={met.t} (solver {res_p.solver})")
            if not res_p.ambi:
                st.error(f"Nessuna soluzione trovata (stato: {res_p.stato}).")
            else:
                c = st.columns(4)
                c[0].metric("Stato", res_p.stato)
                c[1].metric("Ambi (PuLP)", met.n_ambi)
                c[2].metric("Ambi (Turán)", met.turan)
                c[3].metric("Costo totale", eur(met.costo_totale))
                if met.n_ambi == met.turan:
                    st.success("✔ Il minimo trovato da PuLP coincide con la formula di Turán.")
                else:
                    st.warning("Valore diverso da Turán: soluzione non ottima entro il tempo limite.")
                c = st.columns(4)
                c[0].metric("P(garanzia scatta)", pct(met.prob_garanzia * 100, 4),
                            help=f"{met.casi_garanzia:,} casi su {met.combinazioni_totali:,}".replace(",", "."))
                c[1].metric("P(≥1 ambo) reale", pct(met.prob_vincita_reale * 100, 4),
                            help=f"{met.casi_vincita_reale:,} casi su {met.combinazioni_totali:,}".replace(",", "."))
                c[2].metric("Ritorno atteso", eur(met.ritorno_atteso))
                c[3].metric("Perdita %", pct(met.perdita_pct, 2))
                s_chk = analyze(make_design("PuLP", [(a - 1, b - 1) for a, b in res_p.ambi], met.k),
                                stake=stake, payout=payout)
                if abs(s_chk.p_win_any - met.prob_vincita_reale) < 1e-12:
                    st.caption("✔ P(≥1 ambo) coincide con il calcolo esatto del resto dell'app.")
                else:
                    st.caption(f"⚠ P(≥1 ambo) diversa dal calcolo esatto ({pct(s_chk.p_win_any * 100, 4)}).")
                with st.expander("Elenco ambi (numeri 1…k)"):
                    st.write(", ".join(f"{a}-{b}" for a, b in res_p.ambi))

# ------------------------------------------------------------------ tab Simulazione
with tab_sim:
    st.subheader("Monte Carlo vs valori esatti")
    c = st.columns(3)
    n_draws = int(c[0].number_input("Estrazioni simulate", 1_000, 2_000_000, 200_000, step=50_000))
    seed = int(c[1].number_input("Seed", 0, 10_000, 42))

    @st.cache_data(show_spinner=False)
    def run_sim(edges: tuple, k_: int, n: int, w: int, seed_: int) -> np.ndarray:
        return simulate_wins(make_design("sim", edges, k_), n, wheels=w, seed=seed_)

    if c[2].button("Simula", type="primary"):
        with st.spinner("Simulazione in corso…"):
            W = run_sim(design.edges, k, n_draws, wheels, seed)
        net = W * stats1.win_value - stats1.cost
        se = net.std(ddof=1) / np.sqrt(len(net))
        exact = pd.DataFrame([
            {"Misura": "P(≥ 1 ambo)", "Simulata": pct((W >= 1).mean() * 100), "Esatta": pct(stats1.p_win_any * 100)},
            {"Misura": "P(profitto)", "Simulata": pct((net > 1e-9).mean() * 100), "Esatta": pct(stats1.p_profit * 100)},
            {"Misura": "Netto medio per estrazione",
             "Simulata": f"{eur(net.mean())} ± {eur(1.96 * se)}", "Esatta": eur(stats1.ev_net)},
        ])
        st.dataframe(exact, hide_index=True, width="stretch")
        show = min(n_draws, 5000)
        st.plotly_chart(viz.bankroll_figure(net[:show], stats1.ev_net), width="stretch")
        st.caption(f"Saldo cumulato sulle prime {show} estrazioni: oscilla, ma la tendenza è quella attesa.")
    else:
        st.caption("Premi **Simula** per confrontare frequenze simulate e probabilità esatte.")

# ------------------------------------------------------------------ tab Modello
with tab_model:
    st.subheader("Il modello")
    st.markdown(f"""
**Setup.** Ruota con N = 90 numeri, d = 5 estratti. Scegli k numeri (insieme S). Un ambo vince se i suoi
due numeri sono tra i 5 estratti: P = C(5,2)/C(90,2) = 10/4005 = 1/400,5 ≈ {pct(P_AMBO * 100, 4)}.

**Grafo.** G = (S, E): gli archi E sono gli ambi giocati. Per l'uniformità dell'estrazione *quali* k numeri
scegli è indifferente.

**Garanzia t.** "Se escono almeno t dei miei k numeri vinco almeno un ambo" equivale a:
ogni sottoinsieme T ⊂ S con |T| = t contiene almeno un arco, cioè α(G) ≤ t − 1.
""")
    st.latex(r"\min \sum_{e\subset S} x_e \quad\text{s.t.}\quad \sum_{e\subset T} x_e \ge 1\ \ \forall T\subset S,\ |T|=t,\qquad x_e\in\{0,1\}")
    st.markdown("""
**Soluzione chiusa (Turán).** Il minimo si ottiene con t−1 cliche disgiunte il più bilanciate possibile:
""")
    st.latex(r"|E|_{\min}=\sum_{i=1}^{t-1}\binom{n_i}{2},\qquad n_i\in\{\lfloor k/(t-1)\rfloor,\lceil k/(t-1)\rceil\}")
    st.markdown(f"""
Per il principio dei cassetti, t numeri su t−1 gruppi ne mettono due nello stesso gruppo: quell'ambo è giocato.
Poiché escono solo {N_DRAWN} numeri, **t ≤ {N_DRAWN}**: con t ≥ 6 la garanzia non scatta mai.

**Distribuzione esatta.** Se X = quanti dei k numeri escono (ipergeometrica), dato X = m i numeri usciti sono
un m-sottoinsieme uniforme di S e gli ambi vincenti sono gli archi che contiene. Per grafi a cliche disgiunte
si conta con una programmazione dinamica esatta; per grafi generici si enumerano gli m-sottoinsiemi.
Con più ruote o più concorsi (estrazioni indipendenti) la distribuzione è la convoluzione.

**Valore atteso.** Per linearità, E[ritorno] = |E| · puntata · ruote · concorsi · quota · (1 − ritenuta) · P(ambo):
con quota {_it(f'{payout:g}')} si recupera in media il {_it(f'{payout * P_AMBO * 100:.2f}')}% di quanto giocato
(il {_it(f'{payout * (1 - regole.RITENUTA) * P_AMBO * 100:.2f}')}% dopo la ritenuta dell'{regole.RITENUTA:.0%})
per qualsiasi design.

**Regole di gioco applicate.** 5 numeri estratti tra 1 e 90 su 10 ruote cittadine e sulla ruota Nazionale
("tutte le ruote" = le 10 cittadine). Coefficienti per una singola ruota: la posta è divisa tra le ruote e tra
le combinazioni giocate. Importo per scontrino da {eur(regole.IMPORTO_MIN)} a {eur(regole.IMPORTO_MAX)} a
incrementi di {eur(regole.IMPORTO_STEP)}; vincita massima {eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino;
ritenuta dell'{regole.RITENUTA:.0%} sulle vincite; abbonamento fino a {regole.MAX_CONCORSI} concorsi.
Il tab *Calcolo vincite* applica le stesse regole a tutte le sorti (estratto, estratto determinato, ambo,
ambetto, terno, quaterna, cinquina).

**Limiti.** Nel calcolo dell'ambetto si assume la numerazione circolare (il precedente di 1 è 90) e che il
numero vicino non sia a sua volta giocato. Orari di raccolta e modalità di compilazione non incidono sul calcolo.
""")

st.divider()
st.caption("Strumento a scopo didattico. Il gioco d'azzardo può causare dipendenza ed è vietato ai minori.")
