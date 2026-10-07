"""Modello matematico dei sistemi ridotti per ambi al Lotto (ruota singola).

Idea: i k numeri scelti sono i nodi di un grafo G, gli ambi giocati sono gli archi.
"Garanzia t" = se escono almeno t dei tuoi k numeri, almeno un ambo giocato vince.
Equivale a dire che G non ha insiemi indipendenti di taglia t (alpha(G) <= t-1).
Il minimo di archi e' dato dal teorema di Turan (forma complementare):
t-1 cliche disgiunte, il piu' bilanciate possibile.

Nessun design cambia il valore atteso: per linearita' vale sempre
E[ritorno] = n_ambi * puntata * ruote * quota * P(ambo).
"""
from __future__ import annotations

import importlib.util
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain, combinations
from math import comb, floor, sqrt
from typing import Sequence

import numpy as np

N_NUMBERS = 90          # numeri su una ruota
N_DRAWN = 5             # numeri estratti per ruota
AMBO_PAYOUT = 250.0     # vincita per 1 euro puntato su ambo (parametrizzabile)
P_AMBO = comb(N_DRAWN, 2) / comb(N_NUMBERS, 2)   # 10/4005 = 1/400,5
MAX_WINS = comb(N_DRAWN, 2)                       # max ambi vincenti su una ruota (10)

Edge = tuple[int, int]


# --------------------------------------------------------------------------- #
# Design (grafo di ambi)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Design:
    """Insieme di ambi giocati. I nodi sono 0..k-1 (k numeri scelti, anche isolati)."""

    name: str
    edges: tuple[Edge, ...]
    k: int

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    def clique_sizes(self) -> list[int] | None:
        """Taglie delle componenti (con >=2 nodi) se il grafo e' unione di cliche, altrimenti None."""
        return clique_sizes(self.edges)


def make_design(name: str, edges: Sequence[Edge], k: int) -> Design:
    norm = tuple(sorted({(min(a, b), max(a, b)) for a, b in edges if a != b}))
    if norm and (norm[0][0] < 0 or max(b for _, b in norm) >= k):
        raise ValueError("Gli archi devono usare nodi in 0..k-1")
    if k > N_NUMBERS:
        raise ValueError(f"k non puo' superare {N_NUMBERS}")
    return Design(name, norm, k)


def clique_sizes(edges: Sequence[Edge]) -> list[int] | None:
    """Se ogni componente connessa e' una clique ne restituisce le taglie, altrimenti None."""
    parent: dict[int, int] = {}

    def find(a: int) -> int:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    nodes: dict[int, set[int]] = defaultdict(set)
    for v in list(parent):
        nodes[find(v)].add(v)
    n_edges: dict[int, int] = defaultdict(int)
    for a, _ in edges:
        n_edges[find(a)] += 1
    sizes = []
    for root, members in nodes.items():
        n = len(members)
        if n_edges[root] != comb(n, 2):
            return None
        sizes.append(n)
    return sorted(sizes, reverse=True)


# --------------------------------------------------------------------------- #
# Turan: costruzione ottima per la garanzia t
# --------------------------------------------------------------------------- #
def turan_group_sizes(k: int, t: int) -> list[int]:
    """Taglie dei t-1 gruppi piu' bilanciati in cui dividere i k numeri."""
    if t < 2:
        raise ValueError("t deve essere >= 2")
    g = t - 1
    base, extra = divmod(k, g)
    return [base + 1] * extra + [base] * (g - extra)


def turan_min_edges(k: int, t: int) -> int:
    """Minimo numero di ambi che garantisce un ambo se escono t dei k numeri."""
    return sum(comb(n, 2) for n in turan_group_sizes(k, t))


def turan_design(k: int, t: int) -> Design:
    edges: list[Edge] = []
    start = 0
    for n in turan_group_sizes(k, t):
        edges += combinations(range(start, start + n), 2)
        start += n
    name = "Tutti gli ambi" if t == 2 else f"Sistema ridotto (garanzia t={t})"
    return make_design(name, edges, k)


def complete_design(k: int) -> Design:
    return turan_design(k, 2)


def matching_design(n_edges: int) -> Design:
    """Coppie disgiunte: nessuna garanzia, ma overlap minimo tra gli ambi (max frequenza di vincita)."""
    if 2 * n_edges > N_NUMBERS:
        raise ValueError(f"Servono 2*{n_edges} numeri distinti: massimo {N_NUMBERS // 2} ambi")
    edges = [(2 * i, 2 * i + 1) for i in range(n_edges)]
    return make_design("Coppie disgiunte (nessuna garanzia)", edges, 2 * n_edges)


# --------------------------------------------------------------------------- #
# Budget (problema duale)
# --------------------------------------------------------------------------- #
def max_edges_for_budget(budget: float, stake: float, wheels: int = 1) -> int:
    return int(floor(budget / (stake * wheels) + 1e-9))


def best_t_for_edges(k: int, max_edges: int, t_max: int = N_DRAWN) -> int | None:
    """Garanzia migliore (t minimo) ottenibile con k numeri e al massimo max_edges ambi."""
    for t in range(2, min(k, t_max) + 1):
        if turan_min_edges(k, t) <= max_edges:
            return t
    return None


def max_k_for_edges(t: int, max_edges: int, k_cap: int = N_NUMBERS) -> int | None:
    """Massimo numero di numeri coperti con garanzia t e al massimo max_edges ambi."""
    best = None
    for k in range(t, k_cap + 1):
        if turan_min_edges(k, t) <= max_edges:
            best = k
        else:
            break
    return best


# --------------------------------------------------------------------------- #
# Distribuzione esatta degli ambi vincenti su UNA ruota
# --------------------------------------------------------------------------- #
def _counts_from_cliques(sizes: Sequence[int], N: int, d: int) -> list[int]:
    """DP esatto per grafi a cliche disgiunte: conta le d-uple per numero di ambi vincenti."""
    used = sum(sizes)
    if used > N:
        raise ValueError("Troppi nodi per la ruota")
    dp: dict[tuple[int, int], int] = {(0, 0): 1}
    for n in sizes:
        nxt: dict[tuple[int, int], int] = defaultdict(int)
        for (m, w), c in dp.items():
            for a in range(min(n, d - m) + 1):
                nxt[(m + a, w + comb(a, 2))] += c * comb(n, a)
        dp = nxt
    free = N - used
    counts = [0] * (comb(d, 2) + 1)
    for (m, w), c in dp.items():
        counts[w] += c * comb(free, d - m)
    return counts


def _counts_by_enumeration(edges: Sequence[Edge], k: int, N: int, d: int,
                           max_combos: int = 2_500_000) -> list[int]:
    """Enumerazione per grafi generici: condiziona su m = quanti dei k numeri escono."""
    A = np.zeros((k, k), dtype=np.int8)
    for a, b in edges:
        A[a, b] = A[b, a] = 1
    counts = [0] * (comb(d, 2) + 1)
    for m in range(0, min(k, d) + 1):
        rest = comb(N - k, d - m)
        n_comb = comb(k, m)
        if m < 2:
            counts[0] += n_comb * rest
            continue
        if n_comb > max_combos:
            raise ValueError("Grafo troppo grande per l'enumerazione esatta")
        combos = np.fromiter(chain.from_iterable(combinations(range(k), m)),
                             dtype=np.int16, count=n_comb * m).reshape(n_comb, m)
        w = np.zeros(n_comb, dtype=np.int64)
        for i in range(m):
            for j in range(i + 1, m):
                w += A[combos[:, i], combos[:, j]]
        for val, cnt in enumerate(np.bincount(w, minlength=len(counts))):
            counts[val] += int(cnt) * rest
    return counts


def wins_counts(design: Design, N: int = N_NUMBERS, d: int = N_DRAWN) -> list[int]:
    """Conteggi esatti (interi) delle cinquine per numero di ambi vincenti; somma = C(N,d)."""
    sizes = design.clique_sizes()
    if sizes is not None:
        return _counts_from_cliques(sizes, N, d)
    return _counts_by_enumeration(design.edges, design.k, N, d)


def wins_pmf(design: Design, N: int = N_NUMBERS, d: int = N_DRAWN) -> np.ndarray:
    counts = wins_counts(design, N, d)
    return np.array(counts, dtype=float) / comb(N, d)


def p_guarantee(k: int, t: int, N: int = N_NUMBERS, d: int = N_DRAWN) -> float:
    """P(escono almeno t dei k numeri) su una ruota (ipergeometrica)."""
    return sum(comb(k, m) * comb(N - k, d - m) for m in range(t, min(k, d) + 1)) / comb(N, d)


# --------------------------------------------------------------------------- #
# Statistiche economiche
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stats:
    n_edges: int
    stake: float
    wheels: int
    payout: float
    cost: float
    pmf: np.ndarray            # P(totale ambi vincenti = j), su tutte le ruote
    ev_return: float
    ev_net: float
    loss_pct: float
    std_net: float
    p_win_any: float
    p_profit: float
    p_guarantee: float | None  # per singola ruota; None se il design non ha garanzia

    @property
    def net_values(self) -> np.ndarray:
        return np.arange(len(self.pmf)) * self.stake * self.payout - self.cost


def analyze(design: Design, t: int | None = None, stake: float = 1.0, wheels: int = 1,
            payout: float = AMBO_PAYOUT) -> Stats:
    pmf1 = wins_pmf(design)
    pmf = pmf1
    for _ in range(wheels - 1):
        pmf = np.convolve(pmf, pmf1)
    cost = design.n_edges * stake * wheels
    net = np.arange(len(pmf)) * stake * payout - cost
    ev_net = float((pmf * net).sum())
    ev_return = ev_net + cost
    var = float((pmf * net ** 2).sum()) - ev_net ** 2
    return Stats(
        n_edges=design.n_edges, stake=stake, wheels=wheels, payout=payout, cost=cost, pmf=pmf,
        ev_return=ev_return, ev_net=ev_net,
        loss_pct=(-ev_net / cost * 100) if cost else 0.0,
        std_net=sqrt(max(var, 0.0)),
        p_win_any=float(1.0 - pmf[0]),
        p_profit=float(pmf[net > 1e-9].sum()),
        p_guarantee=p_guarantee(design.k, t) if t is not None else None,
    )


def theoretical_ev_return(n_edges: int, stake: float, wheels: int, payout: float) -> float:
    """EV del ritorno per linearita': identico per qualsiasi design con n_edges ambi."""
    return n_edges * stake * wheels * payout * P_AMBO


# --------------------------------------------------------------------------- #
# ILP (OR-Tools CP-SAT)
# --------------------------------------------------------------------------- #
def ortools_available() -> bool:
    return importlib.util.find_spec("ortools") is not None


@dataclass(frozen=True)
class ILPResult:
    status: str
    edges: tuple[Edge, ...]
    objective: int | None
    best_bound: float | None
    wall_time: float
    n_constraints: int


def solve_ilp(k: int, t: int, min_wins: int = 1, time_limit: float = 20.0, workers: int = 8,
              hint: Sequence[Edge] | None = None) -> ILPResult:
    """min sum x_e  s.t.  ogni t-sottoinsieme di {0..k-1} contiene almeno min_wins archi scelti."""
    from ortools.sat.python import cp_model

    if not 2 <= t <= k:
        raise ValueError("Serve 2 <= t <= k")
    if not 1 <= min_wins <= comb(t, 2):
        raise ValueError(f"min_wins deve essere tra 1 e C(t,2)={comb(t, 2)}")
    model = cp_model.CpModel()
    pairs = list(combinations(range(k), 2))
    x = {p: model.NewBoolVar(f"x_{p[0]}_{p[1]}") for p in pairs}
    n_con = 0
    for T in combinations(range(k), t):
        model.Add(sum(x[p] for p in combinations(T, 2)) >= min_wins)
        n_con += 1
    model.Minimize(sum(x.values()))
    if hint is not None:
        hs = {(min(a, b), max(a, b)) for a, b in hint}
        for p in pairs:
            model.AddHint(x[p], int(p in hs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_workers = int(workers)
    status = solver.Solve(model)
    name = solver.StatusName(status)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        edges = tuple(p for p in pairs if solver.Value(x[p]))
        return ILPResult(name, edges, len(edges), solver.BestObjectiveBound(),
                         solver.WallTime(), n_con)
    return ILPResult(name, (), None, None, solver.WallTime(), n_con)


# --------------------------------------------------------------------------- #
# Simulazione Monte Carlo
# --------------------------------------------------------------------------- #
def simulate_wins(design: Design, n_draws: int, wheels: int = 1, seed: int = 0,
                  N: int = N_NUMBERS, d: int = N_DRAWN, chunk: int = 50_000) -> np.ndarray:
    """Simula n_draws estrazioni (x wheels ruote indipendenti); ritorna gli ambi vincenti per estrazione."""
    rng = np.random.default_rng(seed)
    A = np.zeros((N, N), dtype=np.int8)
    for a, b in design.edges:
        A[a, b] = A[b, a] = 1
    total = n_draws * wheels
    out = np.empty(total, dtype=np.int16)
    pos = 0
    while pos < total:
        c = min(chunk, total - pos)
        draws = np.argpartition(rng.random((c, N), dtype=np.float32), d, axis=1)[:, :d]
        w = np.zeros(c, dtype=np.int16)
        for i in range(d):
            for j in range(i + 1, d):
                w += A[draws[:, i], draws[:, j]]
        out[pos:pos + c] = w
        pos += c
    return out.reshape(n_draws, wheels).sum(axis=1)
