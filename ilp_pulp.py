"""Sistema ridotto via PuLP (ILP con CBC) e metriche calcolate per enumerazione diretta.

Approccio alternativo e indipendente da core.py: serve come controllo incrociato
(stesso ottimo di Turan, stesse probabilita' esatte, stesso valore atteso).
Eseguibile anche da riga di comando: `python ilp_pulp.py`.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

N = 90
ESTRAZIONI = 5
QUOTA_AMBO = 250.0


def pulp_available() -> bool:
    """PuLP installato e con CBC incluso (PuLP < 4: la 4.0 ha rimosso CBC e LpVariable.dicts)."""
    try:
        import pulp

        return hasattr(pulp, "PULP_CBC_CMD") and bool(pulp.PULP_CBC_CMD(msg=False).available())
    except Exception:
        return False


def turan_minimum_ambos(k: int, t: int) -> int:
    """
    Calcola il numero minimo di ambi necessari usando il Teorema di Turán.
    Partiziona i k nodi in (t-1) cricche disgiunte il più bilanciate possibile.
    """
    groups = t - 1
    base_size = k // groups
    remainder = k % groups

    # Abbiamo 'remainder' gruppi di dimensione base_size + 1
    # e 'groups - remainder' gruppi di dimensione base_size
    min_edges = 0
    min_edges += remainder * math.comb(base_size + 1, 2)
    min_edges += (groups - remainder) * math.comb(base_size, 2)
    return min_edges


@dataclass(frozen=True)
class RisultatoILP:
    stato: str
    ambi: list[tuple[int, int]]
    solver: str


def solve_ilp_lotto(k: int, t: int, time_limit: float | None = None) -> RisultatoILP:
    """
    Risolve il problema del sistema ridotto tramite Programmazione Lineare Intera.
    """
    import pulp

    if not 2 <= t <= k:
        raise ValueError("Serve 2 <= t <= k")
    numeri = list(range(1, k + 1))
    tutti_gli_ambi = list(itertools.combinations(numeri, 2))

    # Inizializzazione del problema di minimizzazione
    prob = pulp.LpProblem("Ottimizzazione_Sistema_Lotto", pulp.LpMinimize)

    # Variabili decisionali: x[e] = 1 se l'ambo 'e' viene giocato, 0 altrimenti
    x = pulp.LpVariable.dicts("ambo", tutti_gli_ambi, cat=pulp.LpBinary)

    # Funzione Obiettivo: minimizzare il numero totale di ambi giocati
    prob += pulp.lpSum([x[e] for e in tutti_gli_ambi]), "Minimizza_Costo"

    # Vincoli: per ogni sottoinsieme di cardinalità t, almeno un ambo deve essere giocato
    for t_subset in itertools.combinations(numeri, t):
        ambi_nel_subset = list(itertools.combinations(t_subset, 2))
        prob += pulp.lpSum([x[e] for e in ambi_nel_subset]) >= 1, f"Garanzia_{t_subset}"

    # Risoluzione silenziosa (nasconde i log del solver)
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
    prob.solve(solver)

    # Estrazione della soluzione (soglia 0,5: i valori del solver sono float)
    ambi_giocati = [e for e in tutti_gli_ambi if (x[e].varValue or 0) > 0.5]
    return RisultatoILP(pulp.LpStatus[prob.status], ambi_giocati, solver.name)


@dataclass(frozen=True)
class Metriche:
    k: int
    t: int
    n_ambi: int
    turan: int
    costo_totale: float
    casi_garanzia: int
    prob_garanzia: float
    casi_vincita_reale: int
    prob_vincita_reale: float
    combinazioni_totali: int
    ritorno_atteso: float
    perdita_pct: float


def analizza_metriche_sistema(k: int, t: int, ambi_giocati: list[tuple[int, int]],
                              costo_per_ambo: float = 1.0, quota: float = QUOTA_AMBO) -> Metriche:
    """
    Calcola le metriche ipergeometriche e il Valore Atteso (ambi su numeri 1..k).
    """
    combinazioni_totali = math.comb(N, ESTRAZIONI)
    costo_totale = len(ambi_giocati) * costo_per_ambo

    # 1. Probabilità della Garanzia (Probabilità che escano >= t numeri scelti)
    casi_garanzia = 0
    for m in range(t, min(k, ESTRAZIONI) + 1):
        casi_garanzia += math.comb(k, m) * math.comb(N - k, ESTRAZIONI - m)

    # 2. Probabilità Reale di vincere almeno un ambo (indipendentemente dalla garanzia)
    casi_vincita_reale = 0
    ambi = [set(a) for a in ambi_giocati]
    # Controlliamo tutti i possibili m-sottoinsiemi (da 2 a 5 estratti tra i k scelti)
    for m in range(2, min(k, ESTRAZIONI) + 1):
        for estratti_k in itertools.combinations(range(1, k + 1), m):
            # Se in questi estratti c'è almeno uno degli ambi che abbiamo giocato
            estratti = set(estratti_k)
            if any(ambo <= estratti for ambo in ambi):
                casi_vincita_reale += math.comb(N - k, ESTRAZIONI - m)

    # 3. Valore Atteso (Invariante)
    # Ritorno = Costo_Totale * Prob_Ambo_Singolo * Quota
    moltiplicatore_ev = math.comb(ESTRAZIONI, 2) / math.comb(N, 2) * quota
    return Metriche(
        k=k, t=t, n_ambi=len(ambi_giocati), turan=turan_minimum_ambos(k, t),
        costo_totale=costo_totale,
        casi_garanzia=casi_garanzia, prob_garanzia=casi_garanzia / combinazioni_totali,
        casi_vincita_reale=casi_vincita_reale,
        prob_vincita_reale=casi_vincita_reale / combinazioni_totali,
        combinazioni_totali=combinazioni_totali,
        ritorno_atteso=costo_totale * moltiplicatore_ev,
        perdita_pct=(1 - moltiplicatore_ev) * 100,
    )


def stampa_metriche(m: Metriche, ambi_giocati: list[tuple[int, int]]) -> None:
    print(f"--- METRICHE DEL SISTEMA RIDOTTO (k={m.k}, t={m.t}) ---")
    print(f"Numeri scelti (k): {m.k}")
    print(f"Garanzia (t): Almeno 1 ambo se escono {m.t} numeri")
    print(f"Ambi da giocare individuati dall'ILP: {m.n_ambi}")
    print(f"Limite teorico di Turán (oracolo): {m.turan}")
    print(f"Costo totale: {m.costo_totale:.2f} €")
    print("-" * 40)
    print(f"Probabilità garanzia nominale (X >= {m.t}): {m.prob_garanzia:.4%} "
          f"({m.casi_garanzia} casi su {m.combinazioni_totali})")
    print(f"Probabilità REALE di vincere >= 1 ambo: {m.prob_vincita_reale:.4%} "
          f"({m.casi_vincita_reale} casi su {m.combinazioni_totali})")
    print("-" * 40)
    print(f"Valore Atteso del Ritorno (EV): {m.ritorno_atteso:.2f} €")
    print(f"Perdita attesa matematicamente certa a lungo termine: {m.perdita_pct:.2f}%")
    print(f"Combinazioni giocate: {ambi_giocati}")


# --- ESECUZIONE DELL'ESEMPIO DIDATTICO ---
if __name__ == "__main__":
    K_NUMERI = 6
    T_GARANZIA = 3

    # 1. Risolve il grafo usando ILP
    risultato = solve_ilp_lotto(K_NUMERI, T_GARANZIA)

    # 2. Mostra i risultati esatti
    stampa_metriche(analizza_metriche_sistema(K_NUMERI, T_GARANZIA, risultato.ambi), risultato.ambi)
