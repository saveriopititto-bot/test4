"""Regole ufficiali del Lotto per il calcolo delle vincite.

- 5 numeri estratti (in ordine) tra 1 e 90 su 10 ruote cittadine + ruota Nazionale.
- Giocata: da 1 a 10 numeri, una o piu' sorti, una o piu' ruote ("tutte" = le 10 cittadine,
  esclusa la Nazionale).
- La posta di ogni sorte e' divisa tra le combinazioni giocate e tra le ruote: i coefficienti
  si riferiscono a una giocata su una singola ruota.
- Importo per scontrino: minimo 1 EUR, incrementi di 0,50 EUR, massimo 200 EUR.
- Vincita massima per scontrino: 6 milioni di EUR. Ritenuta dell'8% sulle vincite.
- Abbonamento: fino a 50 concorsi consecutivi.

Ambetto (d.d. 2013/7649): vince ogni coppia {x, z} estratta in cui x e' un numero giocato e z e'
il precedente o il successivo di un ALTRO numero giocato. Assunzioni del modello: z non deve essere
a sua volta un numero giocato (altrimenti la coppia e' un ambo) e la numerazione e' circolare
(il precedente di 1 e' 90, il successivo di 90 e' 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb, isclose
from typing import Mapping, Sequence

N_NUMERI = 90
N_ESTRATTI = 5
MAX_NUMERI_GIOCATA = 10

RUOTE_CITTADINE = ("Bari", "Cagliari", "Firenze", "Genova", "Milano",
                   "Napoli", "Palermo", "Roma", "Torino", "Venezia")
NAZIONALE = "Nazionale"
RUOTE = RUOTE_CITTADINE + (NAZIONALE,)
TUTTE = "Tutte"  # le 10 ruote cittadine, esclusa la Nazionale

SEDI_ESTRAZIONE = {
    "Roma, Via Anicia 11": ("Roma", "Cagliari", "Firenze", NAZIONALE),
    "Milano, Viale Fulvio Testi 117": ("Milano", "Genova", "Torino", "Venezia"),
    "Napoli, Via Amerigo Vespucci 170": ("Napoli", "Palermo", "Bari"),
}

ESTRATTO = "estratto"
ESTRATTO_DETERMINATO = "estratto determinato"
AMBO = "ambo"
AMBETTO = "ambetto"
TERNO = "terno"
QUATERNA = "quaterna"
CINQUINA = "cinquina"

COEFFICIENTI = {
    ESTRATTO: 11.233,
    ESTRATTO_DETERMINATO: 55.0,
    AMBO: 250.0,
    AMBETTO: 260.0,
    TERNO: 4_500.0,
    QUATERNA: 120_000.0,
    CINQUINA: 6_000_000.0,
}
# numeri minimi da giocare e taglia delle combinazioni per le sorti "classiche"
_TAGLIA = {ESTRATTO: 1, AMBO: 2, TERNO: 3, QUATERNA: 4, CINQUINA: 5}
_MIN_NUMERI = {**_TAGLIA, ESTRATTO_DETERMINATO: 1, AMBETTO: 2}

IMPORTO_MIN = 1.0
IMPORTO_STEP = 0.5
IMPORTO_MAX = 200.0
VINCITA_MAX_SCONTRINO = 6_000_000.0
RITENUTA = 0.08
MAX_CONCORSI = 50


# --------------------------------------------------------------------------- #
# Ruote
# --------------------------------------------------------------------------- #
def espandi_ruote(ruote: Sequence[str]) -> tuple[str, ...]:
    """Normalizza l'elenco ruote: "Tutte" diventa le 10 cittadine (la Nazionale va aggiunta a parte)."""
    out: list[str] = []
    for r in ruote:
        nomi = RUOTE_CITTADINE if r == TUTTE else (r,)
        for n in nomi:
            if n not in RUOTE:
                raise ValueError(f"Ruota sconosciuta: {n}")
            if n not in out:
                out.append(n)
    if not out:
        raise ValueError("Serve almeno una ruota")
    return tuple(out)


# --------------------------------------------------------------------------- #
# Combinazioni per sorte
# --------------------------------------------------------------------------- #
def _prec(n: int) -> int:
    return N_NUMERI if n == 1 else n - 1


def _succ(n: int) -> int:
    return 1 if n == N_NUMERI else n + 1


def combinazioni_ambetto(numeri: Sequence[int]) -> set[frozenset[int]]:
    giocati = set(numeri)
    out: set[frozenset[int]] = set()
    for x in giocati:
        for y in giocati - {x}:
            for z in (_prec(y), _succ(y)):
                if z not in giocati:
                    out.add(frozenset((x, z)))
    return out


def n_combinazioni(sorte: str, numeri: Sequence[int]) -> int:
    n = len(numeri)
    if sorte in _TAGLIA:
        return comb(n, _TAGLIA[sorte])
    if sorte == ESTRATTO_DETERMINATO:
        return n
    if sorte == AMBETTO:
        return len(combinazioni_ambetto(numeri))
    raise ValueError(f"Sorte sconosciuta: {sorte}")


def combinazioni_vincenti(sorte: str, numeri: Sequence[int], estratti: Sequence[int],
                          posizione: int | None = None) -> int:
    """Quante combinazioni della giocata risultano vincenti su una ruota (estratti in ordine)."""
    usciti = set(numeri) & set(estratti)
    if sorte in _TAGLIA:
        return comb(len(usciti), _TAGLIA[sorte])
    if sorte == ESTRATTO_DETERMINATO:
        if posizione is None:
            raise ValueError("L'estratto determinato richiede la posizione (1-5)")
        return int(estratti[posizione - 1] in set(numeri))
    if sorte == AMBETTO:
        e = set(estratti)
        return sum(c <= e for c in combinazioni_ambetto(numeri))
    raise ValueError(f"Sorte sconosciuta: {sorte}")


# --------------------------------------------------------------------------- #
# Giocata e scontrino
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Giocata:
    """Numeri giocati, posta per sorte (in EUR, per l'intera giocata) e ruote."""

    numeri: tuple[int, ...]
    poste: Mapping[str, float]
    ruote: tuple[str, ...] = ("Bari",)
    posizione: int | None = None  # solo per l'estratto determinato

    def __post_init__(self) -> None:
        nums = tuple(int(n) for n in self.numeri)
        if not 1 <= len(nums) <= MAX_NUMERI_GIOCATA:
            raise ValueError(f"Si giocano da 1 a {MAX_NUMERI_GIOCATA} numeri")
        if len(set(nums)) != len(nums) or any(not 1 <= n <= N_NUMERI for n in nums):
            raise ValueError(f"I numeri devono essere distinti e tra 1 e {N_NUMERI}")
        object.__setattr__(self, "numeri", nums)
        object.__setattr__(self, "ruote", espandi_ruote(self.ruote))
        poste = {s: float(p) for s, p in self.poste.items() if p}
        if not poste:
            raise ValueError("Serve una puntata su almeno una sorte")
        for s, p in poste.items():
            if s not in COEFFICIENTI:
                raise ValueError(f"Sorte sconosciuta: {s}")
            if p < 0:
                raise ValueError("Le poste devono essere positive")
            if len(nums) < _MIN_NUMERI[s]:
                raise ValueError(f"Per {s} servono almeno {_MIN_NUMERI[s]} numeri")
            if n_combinazioni(s, nums) == 0:
                raise ValueError(f"Nessuna combinazione di {s} con questi numeri")
        if ESTRATTO_DETERMINATO in poste and self.posizione not in range(1, N_ESTRATTI + 1):
            raise ValueError("L'estratto determinato richiede una posizione tra 1 e 5")
        object.__setattr__(self, "poste", poste)

    @property
    def importo(self) -> float:
        return sum(self.poste.values())


@dataclass(frozen=True)
class RigaVincita:
    giocata: int
    ruota: str
    sorte: str
    vincenti: int
    combinazioni: int
    lordo: float


@dataclass(frozen=True)
class EsitoScontrino:
    righe: tuple[RigaVincita, ...]
    lordo: float          # somma delle vincite prima del tetto
    lordo_pagabile: float  # dopo il tetto di 6 milioni per scontrino
    ritenuta: float
    netto: float
    importo: float


def _euro(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " €"


def valida_importo(importo: float) -> list[str]:
    """Errori sull'importo di uno scontrino (per concorso); lista vuota se valido."""
    err = []
    if importo < IMPORTO_MIN - 1e-9:
        err.append(f"L'importo minimo per scontrino è {_euro(IMPORTO_MIN)}")
    if importo > IMPORTO_MAX + 1e-9:
        err.append(f"L'importo massimo per scontrino è {_euro(IMPORTO_MAX)}")
    if not isclose(importo / IMPORTO_STEP, round(importo / IMPORTO_STEP), abs_tol=1e-9):
        err.append(f"L'importo deve variare a incrementi di {_euro(IMPORTO_STEP)}")
    return err


def scontrini_necessari(importo: float) -> int:
    """Numero minimo di scontrini da al massimo 200 EUR per coprire l'importo di un concorso."""
    return max(1, -int(-importo // IMPORTO_MAX)) if importo > 0 else 0


def vincita_lorda_giocata(g: Giocata, estrazione: Mapping[str, Sequence[int]],
                          indice: int = 0) -> list[RigaVincita]:
    righe = []
    for ruota in g.ruote:
        estratti = estrazione.get(ruota)
        if estratti is None:
            continue
        for sorte, posta in g.poste.items():
            n_comb = n_combinazioni(sorte, g.numeri)
            vinc = combinazioni_vincenti(sorte, g.numeri, estratti, g.posizione)
            if vinc:
                quota = posta / (n_comb * len(g.ruote))
                righe.append(RigaVincita(indice, ruota, sorte, vinc, n_comb,
                                         vinc * quota * COEFFICIENTI[sorte]))
    return righe


def calcola_vincita(giocate: Sequence[Giocata], estrazione: Mapping[str, Sequence[int]],
                    ritenuta: float = RITENUTA) -> EsitoScontrino:
    """Vincita di uno scontrino su un concorso: tetto di 6 milioni, poi ritenuta."""
    valida_estrazione(estrazione)
    righe: list[RigaVincita] = []
    for i, g in enumerate(giocate):
        righe += vincita_lorda_giocata(g, estrazione, i)
    lordo = sum(r.lordo for r in righe)
    pagabile = min(lordo, VINCITA_MAX_SCONTRINO)
    trattenuta = pagabile * ritenuta
    return EsitoScontrino(tuple(righe), lordo, pagabile, trattenuta, pagabile - trattenuta,
                          sum(g.importo for g in giocate))


def valida_estrazione(estrazione: Mapping[str, Sequence[int]]) -> None:
    for ruota, nums in estrazione.items():
        if ruota not in RUOTE:
            raise ValueError(f"Ruota sconosciuta: {ruota}")
        if len(nums) != N_ESTRATTI or len(set(nums)) != N_ESTRATTI \
                or any(not 1 <= n <= N_NUMERI for n in nums):
            raise ValueError(f"{ruota}: servono {N_ESTRATTI} numeri distinti tra 1 e {N_NUMERI}")


def estrazione_casuale(seed: int | None = None) -> dict[str, tuple[int, ...]]:
    import numpy as np

    rng = np.random.default_rng(seed)
    return {r: tuple(int(n) for n in rng.choice(np.arange(1, N_NUMERI + 1), N_ESTRATTI, replace=False))
            for r in RUOTE}


def p_singola_combinazione(sorte: str) -> float:
    """Probabilita' che una singola combinazione della sorte esca su una ruota."""
    if sorte == ESTRATTO_DETERMINATO:
        return 1 / N_NUMERI
    k = 2 if sorte == AMBETTO else _TAGLIA[sorte]
    return comb(N_ESTRATTI, k) / comb(N_NUMERI, k)


def ritorno_atteso_per_euro(sorte: str, ritenuta: float = 0.0) -> float:
    """EV del ritorno per 1 EUR giocato su una sorte (indipendente da numeri, combinazioni e ruote)."""
    return COEFFICIENTI[sorte] * p_singola_combinazione(sorte) * (1 - ritenuta)


def tetto_mai_raggiunto_ambo(importo_max: float = IMPORTO_MAX) -> bool:
    """Con sole puntate su ambo la vincita lorda di uno scontrino e' al massimo 250 x importo."""
    return COEFFICIENTI[AMBO] * importo_max <= VINCITA_MAX_SCONTRINO
