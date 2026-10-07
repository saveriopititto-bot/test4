"""Come perdere al lotto: sistemi ridotti per ambi, modello a grafo (app Streamlit, layout 1a)."""
from __future__ import annotations

import math
import re
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import ilp_pulp
import regole
import style
import viz
from core import (
    AMBO_PAYOUT, N_DRAWN, N_NUMBERS, P_AMBO, Design, analyze, best_t_for_edges, certain_win_design,
    certain_win_extension, complete_design, minimal_path, minimal_path_design, make_design, matching_design, max_edges_for_budget,
    max_k_for_edges, ortools_available, draws_until_first, waiting_gaps, simulate_wins, solve_ilp, turan_design, turan_min_edges,
)

st.set_page_config(page_title="Come perdere al lotto", page_icon="🎯", layout="wide")
style.apply_style()

PLOTLY_CONFIG = {"displayModeBar": False}
MAX_DIST_ROWS = 30  # oltre, la distribuzione si mostra a fasce


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
# I contenitori fissano l'ordine visivo; puntata e ruote si leggono prima perché servono al budget.
sb_mode, sb_params, sb_money, sb_adv, sb_nums = (st.sidebar.container() for _ in range(5))
MODE_1 = "Scelgo numeri e garanzia"
MODE_2 = "Ho un budget e una garanzia"
MODE_3 = "Ho un budget e dei numeri"
T_HELP = "Se escono almeno t dei tuoi k numeri, vinci almeno un ambo."
with sb_mode:
    style.section("1 · Da dove parti?")
    mode = st.radio("Da dove parti?", [MODE_1, MODE_2, MODE_3], label_visibility="collapsed",
                    captions=["ti dico quanto costa", "ti dico quanti numeri copri", "ti dico che garanzia ottieni"])

with sb_money:
    style.section("3 · Quanto giochi")
    stake = st.number_input("Puntata per ogni ambo (€)", min_value=0.05, value=1.0, step=0.05,
                            help="Posta per ogni ambo e per ogni ruota. Importo per scontrino tra 1 e 200 €, "
                                 "a incrementi di 0,50 €.")
    if st.checkbox("Tutte le ruote",
                   help="Le 10 ruote cittadine: le giocate \"su tutte le ruote\" non comprendono la Nazionale."):
        ruote = regole.RUOTE_CITTADINE
        if st.checkbox("Anche la Nazionale"):
            ruote += (regole.NAZIONALE,)
    else:
        ruote = tuple(st.multiselect("Ruote", regole.RUOTE, default=["Bari"], label_visibility="collapsed",
                                     placeholder="Scegli le ruote"))
        if not ruote:
            st.error("Scegli almeno una ruota.")
            st.stop()
    wheels = len(ruote)

with sb_adv, st.expander("Opzioni avanzate"):
    draws = int(st.number_input("Concorsi consecutivi", min_value=1, max_value=regole.MAX_CONCORSI, value=1,
                                step=1, help=f"Abbonamento: stessa giocata per più concorsi, fino a "
                                             f"{regole.MAX_CONCORSI}."))
    payout = st.number_input("Quota ambo", min_value=1.0, value=AMBO_PAYOUT, step=10.0,
                             help="Vincita per 1 € puntato. Coefficiente ufficiale per l'ambo su una ruota: 250.")
    tax = regole.RITENUTA if st.checkbox(f"Ritenuta {regole.RITENUTA:.0%} sulle vincite", value=True,
                                         help="Ritenuta sull'ammontare delle vincite.") else 0.0
    numbers_text = st.text_input("I tuoi numeri", placeholder="Se vuoi, scrivili qui (es. 7, 18, 42)",
                                 help="Se li lasci vuoti, nella schedina compaiono 1…k.")

k: int
t: int
err: str | None = None
budget: float | None = None
with sb_params:
    style.section("2 · I tuoi dati")
    if mode == MODE_1:
        k = st.slider("Quanti numeri giochi (k)", 3, 40, 8)
        t = st.slider("Garanzia (t)", 2, min(N_DRAWN, k), min(3, k), help=T_HELP)
    elif mode == MODE_2:
        budget = st.number_input("Budget totale (€)", min_value=0.0, value=20.0, step=1.0)
        t = st.slider("Garanzia (t)", 2, N_DRAWN, 3, help=T_HELP)
        k_best = max_k_for_edges(t, max_edges_for_budget(budget, stake, wheels * draws))
        if k_best is None:
            err = f"Con {eur(budget)} non si copre nemmeno il minimo: serve almeno {eur(stake * wheels * draws)}."
            k = max(t, 3)
        else:
            k = k_best
    else:
        budget = st.number_input("Budget totale (€)", min_value=0.0, value=20.0, step=1.0)
        k = st.slider("Quanti numeri giochi (k)", 3, 40, 10)
        t_best = best_t_for_edges(k, max_edges_for_budget(budget, stake, wheels * draws))
        if t_best is None:
            t = min(N_DRAWN, k)
            need = turan_min_edges(k, t) * stake * wheels * draws
            err = f"Con {k} numeri la garanzia più debole (t={t}) costa almeno {eur(need)}."
        else:
            t = t_best
    if err is None:
        st.caption(f"Se escono almeno **{t}** dei tuoi **{k}** numeri, vinci almeno un ambo.")

with sb_nums:
    labels, num_err = parse_numbers(numbers_text, k)
    if num_err:
        style.html(f'<p class="x-note" style="color:{style.A700};margin-top:-12px">{num_err}</p>')
    style.numbers_box(k, labels)
    style.html('<p class="x-note">Strumento didattico. Il gioco d\'azzardo può causare dipendenza ed è vietato '
               'ai minori.</p>')

# ------------------------------------------------------------------ calcolo principale
design = turan_design(k, t)
stats = analyze(design, t=t, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
stats1 = stats if draws == 1 else analyze(design, t=t, stake=stake, wheels=wheels, payout=payout, tax=tax)
importo = stats1.cost                       # importo per concorso
n_scontrini = regole.scontrini_necessari(importo)
importo_err = [e for e in regole.valida_importo(importo) if "massimo" not in e]
ruote_txt = "tutte" if ruote == regole.RUOTE_CITTADINE else ", ".join(ruote)


def summary() -> None:
    """Messaggio di soluzione, metriche e scheda 'Perdita media' (tab Risultato e Confronto)."""
    if mode != MODE_1:
        style.solved(f"{k} numeri, garanzia {t}, {design.n_edges} ambi "
                     f"({eur(stats.cost)} su {eur(budget)} di budget).")
    style.lead(f"Giochi <strong>{design.n_edges} ambi</strong> sui tuoi <strong>{k} numeri</strong> per "
               f"<strong>{eur(stats.cost)}</strong>. Se escono almeno <strong>{t}</strong> dei tuoi numeri vinci "
               f"sicuramente almeno un ambo; in media perdi il <strong>{pct(stats.loss_pct, 1)}</strong> "
               f"di quanto spendi.")
    style.metrics([
        ("Ambi da giocare", str(design.n_edges), f"su {comb(k, 2)} possibili"),
        ("Costo totale", eur(stats.cost),
         f"{eur(importo)} × {draws} concorsi" if draws > 1 else f"{eur(stake)} × {wheels} ruota/e"),
        ("La garanzia scatta", pct(stats.p_guarantee * 100), one_in(stats.p_guarantee)),
        ("Vinci almeno un ambo", pct(stats.p_win_any * 100), one_in(stats.p_win_any)),
    ])
    for e in importo_err:
        style.error_card(f"Giocata non valida: {e} (importo per concorso {eur(importo)}).")
    if n_scontrini > 1:
        style.html(f'<p class="x-note">Importo per concorso {eur(importo)}: oltre il massimo di '
                   f'{eur(regole.IMPORTO_MAX)} per scontrino servono almeno <strong>{n_scontrini} scontrini</strong>.</p>')
    note = (f" Ritenuta dell'{tax:.0%} sulle vincite inclusa." if tax else " Senza ritenuta sulle vincite.")
    style.loss_card(pct(stats.loss_pct, 1), eur(-stats.ev_net), eur(stats.cost),
                    eur(stats.std_net), pct(stats.p_profit * 100), note)


tab_res, tab_cmp, tab_win, tab_cert, tab_path, tab_more = st.tabs(
    ["Risultato", "Confronto", "Controlla una giocata", "Vincita certa", "Percorso minimo", "Approfondimenti"])
with tab_more:
    st.caption("Strumenti per chi vuole verificare i conti: simulazione, controlli con solver, spiegazione del "
               "modello e documentazione completa.")
    tab_sim, tab_ilp, tab_pulp, tab_model, tab_doc = st.tabs(
        ["Simulazione", "Verifica ILP", "ILP con PuLP", "Come funziona", "Documentazione"])

# ------------------------------------------------------------------ tab Risultato
with tab_res:
    if err:
        style.error_card(err)
    else:
        summary()
        pairs = [(labels[a], labels[b]) for a, b in design.edges]
        ticket = pd.DataFrame(
            [{"Ambo": i + 1, "Numero A": a, "Numero B": b, "Posta (€)": round(stake * wheels, 2),
              "Ruote": ruote_txt, "Concorsi": draws} for i, (a, b) in enumerate(pairs)])
        with style.card("ticket"):
            c = st.columns([1, 0.2], vertical_alignment="center")
            with c[0]:
                style.title(f"Cosa giocare · {design.n_edges} ambi · ruote: {ruote_txt}")
            c[1].download_button("Scarica CSV", ticket.to_csv(index=False).encode("utf-8"),
                                 file_name=f"ambi_k{k}_t{t}.csv", mime="text/csv", width="stretch")
            style.pairs_grid(pairs)
            st.caption("La posta di ogni ambo è divisa tra le ruote giocate (i coefficienti valgono per una ruota).")
        left, right = st.columns(2, gap="medium")
        with left, style.card("graph"):
            style.title("Come sono legati i tuoi numeri")
            st.caption("Ogni linea è un ambo da giocare.")
            if design.n_edges <= 1500:
                st.plotly_chart(viz.graph_figure(design, labels), width="stretch", config=PLOTLY_CONFIG)
            else:
                st.caption("Grafo troppo fitto per essere disegnato (oltre 1500 archi).")
            sizes = [s for s in (design.clique_sizes() or []) if s >= 2]
            st.caption(f"{len(sizes)} gruppi di numeri che si giocano tutti tra loro: "
                       + ", ".join(str(s) for s in sizes) + ".")
        with right, style.card("dist"):
            style.title("Cosa può succedere")
            st.caption("Per ogni numero di ambi vincenti: quanto incassi, quanto resta dopo la spesa e quanto è probabile.")
            # righe (da, a, probabilita'): una per valore, o fasce di pari ampiezza se i valori sono troppi
            nz = [j for j, p in enumerate(stats.pmf) if p > 1e-12]
            j_lo, j_hi = nz[0], nz[-1]
            step = max(1, math.ceil((j_hi - j_lo + 1) / MAX_DIST_ROWS))
            bands = [(a, min(a + step - 1, j_hi), float(stats.pmf[a:a + step].sum()))
                     for a in range(j_lo, j_hi + 1, step)]
            bands = [b for b in bands if b[2] > 1e-12]
            lo = min(math.log10(p) for *_, p in bands) - 0.6

            def rng(a: int, b: int, f) -> str:
                return f(a) if a == b else f"{f(a)} – {f(b)}"

            rows = []
            for a, b, p in bands:
                net_color = style.DEEP if a * stats.win_value - stats.cost > 0 else style.A700
                width = max(2.0, (math.log10(p) - lo) / -lo * 100)
                rows.append([rng(a, b, str), rng(a, b, lambda j: eur(j * stake * payout)),
                             f'<span style="color:{net_color}">'
                             f'{rng(a, b, lambda j: eur(j * stats.win_value - stats.cost))}</span>',
                             pct(p * 100, 4),
                             f'<div style="display:flex;flex-direction:column;gap:4px">{style.bar(width)}'
                             f'<span style="font-size:12px">{one_in(p)}</span></div>'])
            style.table(["Ambi vincenti", "Incasso", "Saldo", "Probabilità", "Quanto spesso"],
                        rows, {4: "34%"})
            if step > 1:
                st.caption(f"Valori raggruppati in fasce di {step} ambi vincenti (probabilità sommate).")
            if regole.tetto_mai_raggiunto_ambo():
                st.caption(f"Saldo dopo la ritenuta. Con sole puntate su ambo uno scontrino vince al massimo "
                           f"{eur(regole.COEFFICIENTI[regole.AMBO] * regole.IMPORTO_MAX)}: il tetto di "
                           f"{eur(regole.VINCITA_MAX_SCONTRINO)} non viene mai raggiunto.")

# ------------------------------------------------------------------ tab Calcolo vincite
SORTI_LABEL = {
    regole.ESTRATTO: "Estratto", regole.ESTRATTO_DETERMINATO: "Estratto determinato",
    regole.AMBO: "Ambo", regole.AMBETTO: "Ambetto", regole.TERNO: "Terno",
    regole.QUATERNA: "Quaterna", regole.CINQUINA: "Cinquina",
}


def parse_list(text: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s;\-]+", text.strip()) if x]


def ruote_usate(giocate: list[regole.Giocata]) -> tuple[str, ...]:
    """Ruote su cui si gioca, senza doppioni e nell'ordine di comparsa."""
    out: list[str] = []
    for g_ in giocate:
        out += [r_ for r_ in g_.ruote if r_ not in out]
    return tuple(out)


with tab_win:
    st.caption("Tre passi: scegli cosa giochi, scegli l'estrazione e guarda quanto vinceresti con le regole ufficiali.")

    # ---- 1 · cosa giochi
    giocate: list[regole.Giocata] = []
    with style.card("win_ticket"):
        style.title("1 · Cosa giochi")
        if not err and st.checkbox(f"Gioca il sistema ridotto ({design.n_edges} ambi, {eur(stake * wheels)} "
                                   f"ciascuno, ruote: {ruote_txt})",
                                   value=design.n_edges <= 2000, key="win_sys"):
            giocate += [regole.Giocata((labels[a], labels[b]), {regole.AMBO: stake * wheels}, ruote)
                        for a, b in design.edges]
        with st.expander("Aggiungi una giocata tua", expanded=not giocate):
            c = st.columns(2)
            nums_txt = c[0].text_input("I tuoi numeri (da 1 a 10)", key="win_nums", placeholder="es. 10, 20, 33")
            r_sel = c[1].multiselect("Su quali ruote", [regole.TUTTE, *regole.RUOTE], default=["Bari"],
                                     key="win_ruote")
            st.caption("Quanto punti su ciascuna sorte (€). Lascia 0 le sorti che non giochi.")
            c = st.columns(4)
            poste = {s_: c[i % 4].number_input(f"{SORTI_LABEL[s_]} (€)", 0.0, regole.IMPORTO_MAX, 0.0, step=0.5,
                                               key=f"win_p_{s_}")
                     for i, s_ in enumerate(regole.COEFFICIENTI)}
            pos = 1
            if poste[regole.ESTRATTO_DETERMINATO] > 0:
                pos = int(st.number_input("Posizione dell'estratto determinato (1° … 5°)", 1, regole.N_ESTRATTI, 1,
                                          key="win_pos"))
            if nums_txt.strip() and any(poste.values()):
                try:
                    giocate.append(regole.Giocata(tuple(parse_list(nums_txt)), poste, tuple(r_sel), posizione=pos))
                except ValueError as e:
                    style.error_card(f"Giocata non valida: {e}")
        if not giocate:
            st.caption("Spunta il sistema ridotto oppure aggiungi una giocata tua per continuare.")

    # ---- 2 · estrazione (solo per le ruote su cui si gioca)
    estrazione: dict[str, tuple[int, ...]] = {}
    with style.card("win_draw"):
        style.title("2 · Estrazione")
        if not giocate:
            st.caption("Qui sceglierai l'estrazione per le ruote che giochi.")
        else:
            usate = ruote_usate(giocate)
            c = st.columns(2, vertical_alignment="bottom")
            src = c[0].radio("Numeri estratti", ["Casuale", "Inseriti a mano"], horizontal=True, key="win_src")
            if src == "Casuale":
                seed_ = int(c[1].number_input("Numero per cambiare estrazione", 0, 1_000_000, 1, key="win_seed",
                                              help="Lo stesso numero dà sempre la stessa estrazione."))
                estrazione = {r_: v for r_, v in regole.estrazione_casuale(seed_).items() if r_ in usate}
            else:
                st.caption("Scrivi i 5 numeri estratti per ogni ruota, separati da virgole.")
                cols = st.columns(4)
                for i, r_ in enumerate(usate):
                    txt = cols[i % 4].text_input(r_, key=f"win_e_{r_}", placeholder="es. 3, 17, 25, 48, 90")
                    if txt.strip():
                        try:
                            estrazione[r_] = tuple(parse_list(txt))
                        except ValueError:
                            style.error_card(f"{r_}: inserisci solo numeri interi.")
                mancano = [r_ for r_ in usate if r_ not in estrazione]
                if mancano:
                    st.caption("Mancano i numeri per: " + ", ".join(mancano) + ".")
                    estrazione = {}
            try:
                regole.valida_estrazione(estrazione)
            except ValueError as e:
                style.error_card(str(e))
                estrazione = {}
            if estrazione:
                style.table(["Ruota", "1°", "2°", "3°", "4°", "5°"],
                            [[r_, *map(str, v)] for r_, v in estrazione.items()])

    # ---- 3 · esito
    with style.card("win_result"):
        style.title("3 · Esito")
        if not giocate or not estrazione:
            st.caption("Completa i passi 1 e 2 per vedere quanto vinceresti.")
        else:
            try:
                esiti = regole.calcola_vincita_scontrini(giocate, estrazione, ritenuta=tax)
            except ValueError as e:
                esiti = []
                style.error_card(str(e))
            for n_, es in enumerate(esiti, 1):
                for e in regole.valida_importo(es.importo):
                    style.error_card(f"Scontrino {n_}: {e} (importo {eur(es.importo)}).")
            if esiti:
                imp = sum(es.importo for es in esiti)
                lordo = sum(es.lordo for es in esiti)
                pagabile = sum(es.lordo_pagabile for es in esiti)
                ritenuta_ = sum(es.ritenuta for es in esiti)
                netto = sum(es.netto for es in esiti)
                righe = [(n_, r_) for n_, es in enumerate(esiti, 1) for r_ in es.righe]
                if righe:
                    style.lead(f"Con questa estrazione vinci <strong>{eur(netto)}</strong> netti su "
                               f"<strong>{eur(imp)}</strong> giocati: saldo <strong>{eur(netto - imp)}</strong>.")
                else:
                    style.lead(f"Nessuna combinazione vincente: perdi i <strong>{eur(imp)}</strong> giocati.")
                style.metrics([
                    ("Giocato", eur(imp), f"{len(giocate)} giocate su {len(esiti)} scontrini"
                     if len(esiti) > 1 else f"{len(giocate)} giocate"),
                    ("Vinto netto", eur(netto), "dopo tetto e ritenuta"),
                    ("Saldo", eur(netto - imp), "vinto meno giocato"),
                ])
                if righe:
                    with st.expander("Come si arriva a questo importo"):
                        style.table(["Passaggio", "Importo"],
                                    [["Vincita lorda", eur(lordo)],
                                     [f"Dopo il tetto di {eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino",
                                      eur(pagabile)],
                                     [f"Ritenuta {tax:.0%}", "− " + eur(ritenuta_)],
                                     ["Vincita netta", eur(netto)]])
                        if len(esiti) > 1:
                            st.caption(f"Oltre {eur(regole.IMPORTO_MAX)} le giocate vanno su più scontrini: tetto e "
                                       "ritenuta si applicano a ciascuno.")
                    style.table(["Scontrino", "Giocata", "Numeri", "Ruota", "Sorte", "Uscite", "Vincita lorda"],
                                [[str(n_), str(r_.giocata + 1), "-".join(map(str, giocate[r_.giocata].numeri)),
                                  r_.ruota, SORTI_LABEL[r_.sorte], f"{r_.vincenti} su {r_.combinazioni}",
                                  eur(r_.lordo)] for n_, r_ in righe])

    with st.expander("Come si calcolano le vincite (coefficienti ufficiali)"):
        st.markdown("La posta di ogni sorte è divisa tra le combinazioni giocate e tra le ruote; i coefficienti "
                    f"valgono per una singola ruota. Tetto di {eur(regole.VINCITA_MAX_SCONTRINO)} per scontrino, "
                    f"poi ritenuta dell'{regole.RITENUTA:.0%}.")
        style.table(["Sorte", "Coefficiente", "Ritorno medio per 1 €", "Con ritenuta"],
                    [[SORTI_LABEL[s_], _it(f"{c_:,.3f}".rstrip("0").rstrip(".")),
                      eur(regole.ritorno_atteso_per_euro(s_)),
                      eur(regole.ritorno_atteso_per_euro(s_, regole.RITENUTA))]
                     for s_, c_ in regole.COEFFICIENTI.items()])

# ------------------------------------------------------------------ tab Vincita certa
with tab_cert:
    if err:
        style.error_card(err)
    else:
        cert = certain_win_extension(k, t)
        unit = stake * wheels * draws               # costo di ogni ambo giocato
        free = N_NUMBERS - k
        st.caption("Parte dal sistema della pagina principale e calcola quanti ambi servono ancora, usando solo i "
                   "numeri che non hai già giocato, per vincere sempre almeno un ambo (probabilità 100% su ogni ruota).")
        if not cert.possible:
            style.error_card(f"Con la garanzia t = {t} non si arriva al 100% usando solo numeri nuovi.")
            with style.card("cert_why"):
                st.markdown(
                    f"Su una ruota escono {N_DRAWN} numeri e si vince sempre solo se, tra qualsiasi {N_DRAWN} numeri, "
                    f"almeno due formano un ambo giocato. Il tuo sistema usa già {t - 1} gruppi di numeri che non si "
                    f"giocano tra loro e ne ammette al massimo {N_DRAWN - 1}: un numero nuovo, non collegato ai tuoi, "
                    f"ne aggiungerebbe uno e porterebbe a {N_DRAWN} la possibilità di estrarre {N_DRAWN} numeri senza "
                    f"nessun ambo giocato.\n\nPer arrivare al 100% dovresti collegare i numeri nuovi a quelli già "
                    f"giocati (qui esclusi) oppure scegliere una garanzia più bassa, con t ≤ {N_DRAWN - 1}.")
        else:
            others = [n for n in range(1, N_NUMBERS + 1) if n not in set(labels)]
            groups: list[list[int]] = []
            pos_ = 0
            for n_ in cert.extra_groups:
                groups.append(others[pos_:pos_ + n_])
                pos_ += n_
            extra_pairs = [p_ for g_ in groups for p_ in combinations(g_, 2)]
            total_design = certain_win_design(k, t)
            s_tot = analyze(total_design, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
            j_min = next(j for j, p_ in enumerate(s_tot.pmf) if p_ > 1e-12)
            min_win = j_min * s_tot.win_value
            min_net = min_win - s_tot.cost
            n_sc = regole.scontrini_necessari(cert.total_edges * stake * wheels)

            if cert.extra_edges == 0:
                style.lead("Il tuo sistema <strong>vince già sempre</strong> almeno un ambo: non serve aggiungere nulla.")
            else:
                style.lead(f"Per essere sicuro di vincere almeno un ambo devi aggiungere "
                           f"<strong>{_it(f'{cert.extra_edges:,}')} ambi</strong> sugli altri <strong>{free} numeri"
                           f"</strong>: <strong>{eur(cert.extra_edges * unit)}</strong> in più, "
                           f"<strong>{eur(s_tot.cost)}</strong> in tutto.")
            style.metrics([
                ("Ambi in più", _it(f"{cert.extra_edges:,}"), f"su {free} numeri nuovi"),
                ("Costo in più", eur(cert.extra_edges * unit), f"{eur(unit)} per ambo"),
                ("Costo totale", eur(s_tot.cost), _it(f"{cert.total_edges:,}") + " ambi in tutto"),
                ("Vincita minima", eur(min_win), "se esce un solo ambo"),
            ])
            with style.card("cert_gain"):
                style.title("Vincere sempre non vuol dire guadagnare")
                if min_net < 0:
                    st.markdown(
                        f"Nel caso peggiore esce un solo ambo e incassi {eur(min_win)} a fronte di {eur(s_tot.cost)} "
                        f"spesi: perdi almeno **{eur(-min_net)}**. In media la perdita resta del "
                        f"**{pct(s_tot.loss_pct, 1)}**, come per qualsiasi altro sistema con la stessa quota.")
                else:
                    st.markdown(f"Con questa quota anche il caso peggiore chiude in positivo: almeno "
                                f"**{eur(min_net)}** di saldo. In media si perde comunque il "
                                f"**{pct(s_tot.loss_pct, 1)}**.")
                st.caption(f"Controllo: probabilità di vincere almeno un ambo con il sistema completo = "
                           f"{pct(s_tot.p_win_any * 100, 4)}.")
                if n_sc > 1:
                    st.caption(f"Importo per concorso {eur(cert.total_edges * stake * wheels)}: oltre il massimo di "
                               f"{eur(regole.IMPORTO_MAX)} per scontrino servono almeno {n_sc} scontrini.")

            if cert.extra_edges:
                ticket_extra = pd.DataFrame(
                    [{"Ambo": i + 1, "Numero A": a, "Numero B": b, "Posta (€)": round(stake * wheels, 2),
                      "Ruote": ruote_txt, "Concorsi": draws} for i, (a, b) in enumerate(extra_pairs)])
                with style.card("cert_add"):
                    c = st.columns([1, 0.2], vertical_alignment="center")
                    with c[0]:
                        style.title(f"Cosa aggiungere · {_it(f'{cert.extra_edges:,}')} ambi")
                    c[1].download_button("Scarica CSV", ticket_extra.to_csv(index=False).encode("utf-8"),
                                         file_name=f"ambi_in_piu_k{k}_t{t}.csv", mime="text/csv", width="stretch")
                    st.caption("Dividi i numeri nuovi in questi gruppi e gioca tutti gli ambi dentro ogni gruppo.")
                    style.table(["Gruppo", "Numeri", "Ambi", "Quali numeri"],
                                [[str(i + 1), str(len(g_)), _it(f"{comb(len(g_), 2):,}"),
                                  '<div style="white-space:normal;min-width:320px">' + ", ".join(map(str, g_)) + "</div>"]
                                 for i, g_ in enumerate(groups) if g_])
                    style.pairs_grid(extra_pairs)

            with st.expander("Come si calcola"):
                st.markdown(
                    f"Su una ruota escono {N_DRAWN} numeri e si vince sempre solo se ogni gruppo di {N_DRAWN} numeri "
                    f"contiene almeno un ambo giocato. Il tuo sistema ha già {t - 1} gruppi di numeri che non si "
                    f"giocano tra loro; ne ammettiamo al massimo {N_DRAWN - 1}, quindi sui numeri nuovi ne restano "
                    f"{N_DRAWN - t}. Il minimo di ambi per {N_DRAWN - t} gruppi è dato ancora dal teorema di Turán: "
                    f"si dividono i numeri nuovi in {N_DRAWN - t} gruppi il più possibile uguali e si giocano tutti "
                    f"gli ambi dentro ogni gruppo.")
                st.markdown(
                    f"Se potessi collegare anche i numeri già giocati, partendo da zero ne basterebbero "
                    f"**{_it(f'{cert.from_scratch_edges:,}')}** in tutto. Tenere separati i tuoi {k} numeri costa "
                    f"{_it(f'{cert.total_edges - cert.from_scratch_edges:,}')} ambi in più rispetto a quel minimo.")

# ------------------------------------------------------------------ tab Percorso minimo
with tab_path:
    if err:
        style.error_card(err)
    else:
        mp = minimal_path(k, t)
        unit = stake * wheels * draws
        others = [n for n in range(1, N_NUMBERS + 1) if n not in set(labels)]
        cert_path = certain_win_extension(k, t)
        st.caption("Il modo più economico per passare dalla tua giocata alla vincita sicura: i gruppi di numeri che "
                   "hai già si allargano con numeri nuovi, invece di restare separati.")
        design_p = minimal_path_design(k, t)
        s_p = analyze(design_p, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
        j_min = next(j for j, p_ in enumerate(s_p.pmf) if p_ > 1e-12)
        min_win = j_min * s_p.win_value
        # numeri di ciascun gruppo (in ordine: prima i tuoi, poi i nuovi)
        members: list[list[int]] = []
        o_i = 0
        n_i = 0
        for n0, add in zip(mp.group_sizes, mp.added):
            members.append(list(labels[o_i:o_i + n0]) + others[n_i:n_i + add])
            o_i += n0
            n_i += add
        have_pairs = {tuple(sorted((labels[a], labels[b]))) for a, b in turan_design(k, t).edges}
        extra_pairs = [p_ for g_ in members for p_ in combinations(sorted(g_), 2) if p_ not in have_pairs]

        if mp.extra_edges == 0:
            style.lead("Il tuo sistema <strong>vince già sempre</strong> almeno un ambo: non serve aggiungere nulla.")
        else:
            style.lead(f"Servono <strong>{_it(f'{mp.extra_edges:,}')} ambi in più</strong>, "
                       f"<strong>{eur(mp.extra_edges * unit)}</strong>, per un totale di "
                       f"<strong>{eur(mp.total_edges * unit)}</strong>.")
        style.metrics([
            ("Ambi in più", _it(f"{mp.extra_edges:,}"), "collegando anche i tuoi numeri"),
            ("Costo totale", eur(mp.total_edges * unit), _it(f"{mp.total_edges:,}") + " ambi in tutto"),
            ("Risparmio", eur(max(cert_path.total_edges - mp.total_edges, 0) * unit) if cert_path.possible else "—",
             "rispetto a usare solo numeri nuovi" if cert_path.possible else "la scheda «Vincita certa» non è possibile"),
            ("Vincita minima", eur(min_win), "se esce un solo ambo"),
        ])
        with style.card("path_gain"):
            style.title("Minimo possibile")
            st.markdown(
                f"Partendo da zero ne servono **{_it(f'{mp.from_scratch_edges:,}')}**: è il minimo assoluto, "
                f"raggiunto solo se i gruppi sono tutti della stessa grandezza. " +
                (f"Il tuo percorso costa {_it(f'{mp.total_edges - mp.from_scratch_edges:,}')} ambi in più di quel "
                 f"minimo, perché i tuoi gruppi di partenza sono già grandi." if mp.total_edges > mp.from_scratch_edges
                 else "Il tuo percorso lo raggiunge esattamente."))
            min_net = min_win - s_p.cost
            st.caption(f"Nel caso peggiore incassi {eur(min_win)} contro {eur(s_p.cost)} spesi "
                       f"({'perdi almeno ' + eur(-min_net) if min_net < 0 else 'saldo positivo ' + eur(min_net)}). "
                       f"Perdita media: {pct(s_p.loss_pct, 1)}. Controllo: P(≥1 ambo) = "
                       f"{pct(s_p.p_win_any * 100, 4)}.")
        with style.card("path_groups"):
            c = st.columns([1, 0.2], vertical_alignment="center")
            with c[0]:
                style.title("Come allargare i gruppi")
            if extra_pairs:
                ticket_p = pd.DataFrame(
                    [{"Ambo": i + 1, "Numero A": a, "Numero B": b, "Posta (€)": round(stake * wheels, 2),
                      "Ruote": ruote_txt, "Concorsi": draws} for i, (a, b) in enumerate(extra_pairs)])
                c[1].download_button("Scarica CSV", ticket_p.to_csv(index=False).encode("utf-8"),
                                     file_name=f"percorso_minimo_k{k}_t{t}.csv", mime="text/csv", width="stretch")
            st.caption("Dentro ogni gruppo si giocano tutti gli ambi tra i numeri. Gli ambi che hai già restano; "
                       "aggiungi quelli che coinvolgono i numeri nuovi.")
            style.table(["Gruppo", "Prima", "Dopo", "Nuovi numeri", "Ambi in più"],
                        [[str(i + 1), str(n0), str(n0 + add), str(add),
                          _it(f"{comb(n0 + add, 2) - comb(n0, 2):,}")]
                         for i, (n0, add) in enumerate(zip(mp.group_sizes, mp.added))])
            if extra_pairs:
                style.pairs_grid(extra_pairs)
        with st.expander("Come si calcola"):
            st.markdown(
                f"Si vince sempre se ogni gruppo di {N_DRAWN} numeri contiene un ambo giocato, cioè se i numeri si "
                f"dividono in al massimo {N_DRAWN - 1} gruppi in cui ci si gioca tutti contro tutti. Il tuo "
                f"sistema ne ha già {t - 1}. Aggiungi {N_DRAWN - t} gruppi nuovi e assegni ogni numero rimasto, "
                f"uno alla volta, al gruppo più piccolo: l'ambo in più costa quanto la grandezza del gruppo, "
                f"quindi conviene sempre il più piccolo. È il risultato di Turán con i tuoi gruppi di partenza "
                f"come vincolo. Se un tuo gruppo è già più grande della media finale, non si può ridurre e il "
                f"minimo assoluto non si raggiunge.")

# ------------------------------------------------------------------ tab Confronto
with tab_cmp:
    if err:
        style.error_card(err)
    else:
        st.caption(f"Stessa spesa di {eur(stats.cost)}, diversi modi di giocarla: cambia la forma del rischio, "
                   "non quanto si perde in media.")

        def row(label: str, d: Design, guarantee_t: int | None) -> list[str]:
            s = analyze(d, t=guarantee_t, stake=stake, wheels=wheels, payout=payout, tax=tax, draws=draws)
            return [
                label, str(d.n_edges), eur(s.cost), f"{guarantee_t} su {d.k}" if guarantee_t else "nessuna",
                pct(s.p_guarantee * 100) if s.p_guarantee is not None else "—",
                pct(s.p_win_any * 100), one_in(s.p_win_any), eur(-s.ev_net),
                f'<span style="color:{style.A700};font-weight:600">{pct(s.loss_pct, 1)}</span>',
                eur(s.std_net), pct(s.p_profit * 100),
            ]

        with style.card("cmp"):
            style.title("Stessa spesa, design diversi")
            rows = [row(f"Sistema ridotto k={k}, t={t}", design, t)]
            if k > 2 and t != 2:
                rows.append(row(f"Tutti gli ambi su {k} numeri", complete_design(k), 2))
            if 2 * design.n_edges <= N_NUMBERS:
                rows.append(row(f"Coppie disgiunte ({design.n_edges} ambi)", matching_design(design.n_edges), None))
            style.table(["Come giochi", "Ambi", "Costo", "Garanzia", "Garanzia scatta", "Vinci qualcosa",
                         "Quanto spesso", "Perdita media", "Perdita %", "Oscillazione", "Chiudi in positivo"], rows)
            if 2 * design.n_edges > N_NUMBERS:
                st.caption(f"Le coppie disgiunte con {design.n_edges} ambi richiederebbero "
                           f"{2 * design.n_edges} numeri (> {N_NUMBERS}): confronto non disponibile.")
            st.markdown(
                "La **perdita percentuale è identica** in tutte le righe (linearità del valore atteso). "
                "Cambia la forma del rischio: il sistema ridotto concentra gli ambi su pochi numeri e garantisce "
                "una vincita quando ne escono almeno t, ma gli ambi si sovrappongono; le coppie disgiunte non "
                "garantiscono nulla, però hanno la più alta probabilità di incassare almeno una volta.")

        @st.cache_data(show_spinner=False)
        def frontier(stake_: float, wheels_: int, payout_: float, tax_: float, draws_: int,
                     k_max: int = 40) -> dict:
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

        with style.card("frontier"):
            style.title("Frontiera: costo vs probabilità di vincita")
            st.plotly_chart(
                viz.frontier_figure(frontier(stake, wheels, payout, tax, draws), (stats.cost, stats.p_win_any * 100)),
                width="stretch", config=PLOTLY_CONFIG)
            st.markdown("Ogni punto è un design (k crescente lungo la curva). A parità di costo, più si alza la "
                        "garanzia richiesta più si rinuncia a probabilità di vincita.")


def verdict(ok: bool, text: str) -> None:
    style.html(style.tag(text, "accent" if ok else "outline"))


# ------------------------------------------------------------------ tab ILP
with tab_ilp, style.card("ilp"):
    style.title("Verifica con programmazione lineare intera")
    st.markdown("Risolve **min Σ x<sub>e</sub>** con il vincolo che ogni gruppo di *t* numeri contenga almeno "
                "*m* ambi giocati. Con *m = 1* il risultato deve coincidere con la formula di Turán; "
                "con *m ≥ 2* non c'è una formula semplice e il solver è lo strumento giusto.",
                unsafe_allow_html=True)
    if not ortools_available():
        st.warning("OR-Tools non è installato: `pip install ortools`.")
    else:
        c = st.columns([1, 1, 1, 1, 1.1], vertical_alignment="bottom")
        k_i = c[0].slider("k (numeri)", 4, 14, min(max(k, 4), 10), key="ilp_k")
        t_i = c[1].slider("t (garanzia)", 2, min(N_DRAWN, k_i), min(t, k_i, N_DRAWN), key="ilp_t")
        m_i = c[2].number_input("m (ambi garantiti)", 1, comb(t_i, 2), 1, key="ilp_m")
        tl = c[3].number_input("Tempo max (s)", 5, 300, 30, step=5, key="ilp_tl")
        if c[4].button("Risolvi con CP-SAT", type="primary", width="stretch"):
            with st.spinner("Calcolo in corso…"):
                res = solve_ilp(k_i, t_i, int(m_i), time_limit=float(tl))
            st.session_state["ilp"] = ((k_i, t_i, int(m_i)), res)
        st.caption(f"{comb(k_i, 2)} variabili, {comb(k_i, t_i)} vincoli.")
        if "ilp" in st.session_state:
            (kk, tt, mm), res = st.session_state["ilp"]
            st.markdown(f"**Ultimo risultato** — k={kk}, t={tt}, m={mm}")
            if res.objective is None:
                style.error_card(f"Nessuna soluzione trovata (stato: {res.status}).")
            else:
                d_ilp = make_design("ILP", res.edges, kk)
                turan = turan_min_edges(kk, tt)
                c = st.columns(4)
                c[0].metric("Stato", res.status)
                c[1].metric("Ambi (ILP)", res.objective)
                c[2].metric("Ambi (Turán)", turan if mm == 1 else "—")
                c[3].metric("Tempo", _it(f"{res.wall_time:.2f}") + " s")
                if mm == 1:
                    if res.status == "OPTIMAL" and res.objective == turan:
                        verdict(True, "✔ L'ottimo ILP coincide con la formula di Turán.")
                    elif res.objective == turan:
                        verdict(False, "Valore uguale a Turán, ma il solver non ha chiuso la prova di ottimalità.")
                    else:
                        verdict(False, "Valore diverso da Turán: soluzione non ottima entro il tempo limite.")
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
with tab_pulp, style.card("pulp"):
    style.title("Sistema ridotto con PuLP (CBC)")
    st.markdown("Stesso modello ILP risolto con **PuLP** e metriche calcolate per **enumerazione diretta** "
                "dei sottoinsiemi estratti: un controllo indipendente dai calcoli del resto dell'app. "
                "Le metriche si riferiscono a una ruota.")
    if not ilp_pulp.pulp_available():
        st.warning("PuLP con il solver CBC non è disponibile: `pip install \"pulp<4\"` "
                   "(dalla 4.0 PuLP non include più CBC).")
    else:
        c = st.columns([1, 1, 1, 1], vertical_alignment="bottom")
        k_p = c[0].slider("k (numeri)", 4, 12, min(max(k, 4), 12), key="pulp_k")
        t_p = c[1].slider("t (garanzia)", 2, min(N_DRAWN, k_p), min(t, k_p, N_DRAWN), key="pulp_t")
        tl_p = c[2].number_input("Tempo max (s)", 5, 300, 30, step=5, key="pulp_tl")
        if c[3].button("Risolvi con PuLP", type="primary", width="stretch"):
            with st.spinner("Calcolo in corso…"):
                res_p = ilp_pulp.solve_ilp_lotto(k_p, t_p, time_limit=float(tl_p))
                met = ilp_pulp.analizza_metriche_sistema(k_p, t_p, res_p.ambi, costo_per_ambo=stake,
                                                         quota=payout * (1 - tax))
            st.session_state["pulp"] = (res_p, met)
        st.caption(f"{comb(k_p, 2)} variabili, {comb(k_p, t_p)} vincoli.")
        if "pulp" in st.session_state:
            res_p, met = st.session_state["pulp"]
            st.markdown(f"**Ultimo risultato** — k={met.k}, t={met.t} (solver {res_p.solver})")
            if not res_p.ambi:
                style.error_card(f"Nessuna soluzione trovata (stato: {res_p.stato}).")
            else:
                c = st.columns(4)
                c[0].metric("Stato", res_p.stato)
                c[1].metric("Ambi (PuLP)", met.n_ambi)
                c[2].metric("Ambi (Turán)", met.turan)
                c[3].metric("Costo totale", eur(met.costo_totale))
                if met.n_ambi == met.turan:
                    verdict(True, "✔ Il minimo trovato da PuLP coincide con la formula di Turán.")
                else:
                    verdict(False, "Valore diverso da Turán: soluzione non ottima entro il tempo limite.")
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
    if err:
        style.error_card(err)
    else:
        @st.cache_data(show_spinner=False)
        def run_sim(edges: tuple, k_: int, n: int, w: int, seed_: int) -> np.ndarray:
            return simulate_wins(make_design("sim", edges, k_), n, wheels=w, seed=seed_)

        with style.card("sim"):
            style.title("Monte Carlo vs valori esatti")
            c = st.columns([1, 1, 0.6], vertical_alignment="bottom")
            n_draws = int(c[0].number_input("Estrazioni simulate", 1_000, 2_000_000, 200_000, step=50_000))
            seed = int(c[1].number_input("Seed", 0, 10_000, 42))
            sim_key = (mode, k, t, budget, stake, ruote, payout, tax, tuple(labels), n_draws, seed)
            if c[2].button("Simula", type="primary", width="stretch"):
                with st.spinner("Simulazione in corso…"):
                    W = run_sim(design.edges, k, n_draws, wheels, seed)
                net = W * stats1.win_value - stats1.cost
                se = net.std(ddof=1) / np.sqrt(len(net))
                waits = {}
                for name_, hits_ in (("win", W >= 1), ("profit", net > 1e-9)):
                    g_ = waiting_gaps(hits_)
                    waits[name_] = None if len(g_) == 0 else {
                        "first": int(g_[0]), "mean": float(g_.mean()), "median": int(np.median(g_)),
                        "q90": int(np.ceil(np.quantile(g_, 0.9))), "count": int(len(g_))}
                st.session_state["sim"] = {
                    "key": sim_key, "n": n_draws, "ev": stats1.ev_net, "path": net[:min(n_draws, 5000)],
                    "waits": waits,
                    "rows": [
                        ["P(≥ 1 ambo)", pct((W >= 1).mean() * 100), pct(stats1.p_win_any * 100)],
                        ["P(profitto)", pct((net > 1e-9).mean() * 100), pct(stats1.p_profit * 100)],
                        ["Netto medio per estrazione", f"{eur(net.mean())} ± {eur(1.96 * se)}", eur(stats1.ev_net)],
                    ]}
            sim = st.session_state.get("sim")
            if sim is None:
                st.markdown("Premi **Simula** per confrontare frequenze simulate e probabilità esatte.")
            else:
                if sim["key"] != sim_key:
                    style.html(style.tag("Parametri cambiati: risimula per aggiornare", "neutral"))
                style.table(["Misura", "Simulata", "Esatta"], sim["rows"])
                st.plotly_chart(viz.bankroll_figure(sim["path"], sim["ev"]), width="stretch", config=PLOTLY_CONFIG)
                shown, total = _it(f"{len(sim['path']):,}"), _it(f"{sim['n']:,}")
                st.caption(f"Saldo cumulato sulle prime {shown} di {total} estrazioni: "
                           "oscilla, ma la tendenza è quella attesa.")

        def n_it(x: float) -> str:
            return _it(f"{x:,.0f}")

        def mean_it(x: float) -> str:
            """Attesa media: un decimale sotto le 10 estrazioni, altrimenti intera."""
            return _it(f"{x:,.1f}") if x < 10 else n_it(x)

        def as_time(n_draws_: float) -> str:
            weeks = n_draws_ / regole.ESTRAZIONI_SETTIMANA
            if weeks < 1:
                return "meno di una settimana"
            if weeks < 52:
                return f"circa {n_it(weeks)} settimane" if round(weeks) != 1 else "circa una settimana"
            years = weeks / 52
            return f"circa {_it(f'{years:,.1f}')} anni"

        wait_win = draws_until_first(stats1.p_win_any)
        wait_profit = draws_until_first(stats1.p_profit)
        with style.card("sim_wait"):
            style.title("Quanto aspetti prima di vincere")
            if wait_win is None:
                st.markdown("Con questo sistema non si vince mai un ambo.")
            else:
                style.lead(
                    f"In media servono <strong>{mean_it(wait_win.mean)} estrazioni</strong> per vincere almeno un ambo "
                    f"({as_time(wait_win.mean)} con {regole.ESTRAZIONI_SETTIMANA} estrazioni a settimana), "
                    f"spendendo nel frattempo circa <strong>{eur(wait_win.mean * stats1.cost)}</strong>. "
                    f"Metà delle volte basta aspettare <strong>{n_it(wait_win.median)}</strong> estrazioni, "
                    f"9 volte su 10 al massimo <strong>{n_it(wait_win.q90)}</strong>.")
                rows_w = []
                for label_, w_, key_ in (("Vincere almeno un ambo", wait_win, "win"),
                                         ("Chiudere un'estrazione in attivo", wait_profit, "profit")):
                    if w_ is None:
                        rows_w.append([label_, "mai", "—", "—", "—"])
                        continue
                    rows_w.append([label_, pct(w_.p * 100, 3), mean_it(w_.mean), n_it(w_.median), n_it(w_.q90)])
                style.table(["Obiettivo", "Probabilità per estrazione", "Attesa media", "Metà delle volte entro",
                             "9 volte su 10 entro"], rows_w)
                st.caption("Estrazioni contate fino a quella vincente compresa (distribuzione geometrica: "
                           "attesa media = 1 / probabilità). Ogni estrazione è indipendente: aver aspettato "
                           "a lungo non rende più vicina la vincita.")
                sim = st.session_state.get("sim")
                if sim is not None and sim.get("waits") and sim["key"] == sim_key:
                    rows_s = []
                    for label_, w_, key_ in (("Vincere almeno un ambo", wait_win, "win"),
                                             ("Chiudere un'estrazione in attivo", wait_profit, "profit")):
                        o_ = sim["waits"].get(key_)
                        if o_ is None:
                            rows_s.append([label_, "mai", "—", "—", "—", "0"])
                        else:
                            rows_s.append([label_, n_it(o_["first"]), mean_it(o_["mean"]) if w_ is None else
                                           f"{mean_it(o_['mean'])} (esatta {mean_it(w_.mean)})", n_it(o_["median"]),
                                           n_it(o_["q90"]), n_it(o_["count"])])
                    st.markdown("**Nella simulazione**")
                    style.table(["Obiettivo", "Prima volta all'estrazione", "Attesa media", "Metà delle volte entro",
                                 "9 volte su 10 entro", "Quante volte"], rows_s)
                else:
                    st.caption("Premi **Simula** qui sopra per confrontare questi valori con le attese osservate.")

# ------------------------------------------------------------------ tab Modello
with tab_model:
    style.kicker_cards([
        ("01 · Setup", "Ruota con N = 90 numeri, d = 5 estratti. Scegli k numeri (insieme S). Un ambo vince se i "
                       "suoi due numeri sono tra i 5 estratti: P = C(5,2)/C(90,2) = 10/4005 = 1/400,5 ≈ "
                       f"{pct(P_AMBO * 100, 4)}."),
        ("02 · Grafo", "G = (S, E): gli archi E sono gli ambi giocati. Per l'uniformità dell'estrazione "
                       "<em>quali</em> k numeri scegli è indifferente."),
        ("03 · Garanzia t", "“Se escono almeno t dei miei k numeri vinco almeno un ambo” equivale a: ogni "
                            "T ⊂ S con |T| = t contiene almeno un arco, cioè α(G) ≤ t − 1."),
    ])
    with style.card("model"):
        style.html('<span class="x-kicker">ILP</span>')
        st.latex(r"\min \sum_{e\subset S} x_e \quad\text{s.t.}\quad \sum_{e\subset T} x_e \ge 1\ \ "
                 r"\forall T\subset S,\ |T|=t,\qquad x_e\in\{0,1\}")
        style.html('<span class="x-kicker">Soluzione chiusa (Turán)</span>')
        st.latex(r"|E|_{\min}=\sum_{i=1}^{t-1}\binom{n_i}{2},\qquad n_i\in\{\lfloor k/(t-1)\rfloor,"
                 r"\lceil k/(t-1)\rceil\}")
        st.markdown(f"Il minimo si ottiene con t−1 cliche disgiunte il più bilanciate possibile. Per il principio "
                    f"dei cassetti, t numeri su t−1 gruppi ne mettono due nello stesso gruppo: quell'ambo è "
                    f"giocato. Poiché escono solo {N_DRAWN} numeri, **t ≤ {N_DRAWN}**: con t ≥ 6 la garanzia "
                    f"non scatta mai.")
    style.kicker_cards([
        ("04 · Distribuzione esatta", "Se X = quanti dei k numeri escono (ipergeometrica), dato X = m i numeri "
                                      "usciti sono un m-sottoinsieme uniforme di S e gli ambi vincenti sono gli "
                                      "archi che contiene. Per grafi a cliche disgiunte si conta con una "
                                      "programmazione dinamica esatta; per grafi generici si enumerano gli "
                                      "m-sottoinsiemi. Con più ruote la distribuzione è la convoluzione."),
        ("05 · Valore atteso", "Per linearità, E[ritorno] = |E| · puntata · ruote · concorsi · quota · "
                               "(1 − ritenuta) · P(ambo): con quota "
                               f"{_it(f'{payout:g}')} si recupera in media il "
                               f"<strong>{_it(f'{payout * P_AMBO * 100:.2f}')}%</strong> di quanto giocato "
                               f"(il <strong>{_it(f'{payout * (1 - regole.RITENUTA) * P_AMBO * 100:.2f}')}%"
                               f"</strong> dopo la ritenuta dell'{regole.RITENUTA:.0%}), per qualsiasi design."),
        ("06 · Regole di gioco", "10 ruote cittadine più la Nazionale (“tutte le ruote” = le 10 cittadine). "
                                 "Coefficienti per una singola ruota: la posta è divisa tra ruote e combinazioni. "
                                 f"Scontrino da {eur(regole.IMPORTO_MIN)} a {eur(regole.IMPORTO_MAX)} a passi di "
                                 f"{eur(regole.IMPORTO_STEP)}, vincita massima {eur(regole.VINCITA_MAX_SCONTRINO)}, "
                                 f"ritenuta dell'{regole.RITENUTA:.0%}, abbonamento fino a "
                                 f"{regole.MAX_CONCORSI} concorsi."),
        ("07 · Limiti", "Ambetto: si assume la numerazione circolare (il precedente di 1 è 90) e che il numero "
                        "vicino non sia a sua volta giocato. Orari di raccolta e modalità di compilazione non "
                        "incidono sul calcolo."),
    ])

# ------------------------------------------------------------------ tab Documentazione
DOC_PATH = Path(__file__).with_name("DOCUMENTAZIONE.md")


@st.cache_data(show_spinner=False)
def doc_sections(text: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Titolo, sottotitolo e capitoli (titolo ##, corpo markdown) della documentazione."""
    head, *chapters = re.split(r"^## ", text, flags=re.M)
    lines = [ln for ln in head.strip().splitlines() if ln.strip()]
    title = lines[0].lstrip("# ").strip() if lines else ""
    byline = " ".join(lines[1:])
    return title, byline, [(c.split("\n", 1)[0].strip(), c.split("\n", 1)[1].strip()) for c in chapters]


with tab_doc:
    if not DOC_PATH.exists():
        style.error_card("Documentazione non trovata: manca DOCUMENTAZIONE.md accanto ad app.py.")
    else:
        doc_title, doc_by, chapters = doc_sections(DOC_PATH.read_text(encoding="utf-8"))
        with style.card("doc-head"):
            style.title(doc_title)
            if doc_by:
                st.caption(doc_by)
        for i, (heading, body) in enumerate(chapters):
            with style.card(f"doc-{i}"):
                style.title(heading)
                st.markdown(body)
