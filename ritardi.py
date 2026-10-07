"""Lettura del tabellone dei ritardi (file di testo con colonne separate da tabulazioni).

Formato atteso: una riga di intestazione `Rit. <ruota> <ruota> ...` e poi righe `ritardo` seguito da 5 celle
per ogni ruota; ogni cella piena contiene un numero (1-90) con quel ritardo. L'intestazione si ripete ogni
tanto e viene ignorata. Una riga con ritardo 0 contiene i numeri dell'ultima estrazione.
"""
from __future__ import annotations

from dataclasses import dataclass

CELLE_PER_RUOTA = 5
N_NUMERI = 90


@dataclass(frozen=True)
class Ritardi:
    per_ruota: dict[str, dict[int, int]]   # ruota -> {numero: estrazioni di ritardo}

    @property
    def ruote(self) -> list[str]:
        return list(self.per_ruota)

    def top(self, ruota: str, n: int = 10) -> list[tuple[int, int]]:
        """I primi n numeri per ritardo decrescente, a parita' il piu' piccolo prima."""
        return sorted(self.per_ruota[ruota].items(), key=lambda t: (-t[1], t[0]))[:n]

    def top_assoluti(self, n: int = 10) -> list[tuple[str, int, int]]:
        tutti = [(r, num, rit) for r, d in self.per_ruota.items() for num, rit in d.items()]
        return sorted(tutti, key=lambda t: (-t[2], t[0], t[1]))[:n]


def parse_tabellone(text: str) -> Ritardi:
    """Legge il file; solleva ValueError con un messaggio comprensibile se il formato non torna."""
    righe = [r.rstrip("\r") for r in text.replace("﻿", "").split("\n")]
    intestazione = next((r.split("\t") for r in righe if r.strip().startswith("Rit.")), None)
    if intestazione is None:
        raise ValueError("Non trovo la riga di intestazione «Rit.» con i nomi delle ruote.")
    ruote = [c.strip() for c in intestazione[1:] if c.strip()]
    if not ruote:
        raise ValueError("L'intestazione non contiene nomi di ruote.")
    dati: dict[str, dict[int, int]] = {r: {} for r in ruote}
    for riga in righe:
        celle = riga.split("\t")
        if not celle[0].strip().isdigit():
            continue
        ritardo = int(celle[0])
        for j, cella in enumerate(celle[1:1 + CELLE_PER_RUOTA * len(ruote)]):
            c = cella.strip()
            if c.isdigit():
                num = int(c)
                if not 1 <= num <= N_NUMERI:
                    raise ValueError(f"Numero fuori dall'intervallo 1-{N_NUMERI}: {num}.")
                dati[ruote[j // CELLE_PER_RUOTA]][num] = ritardo
    mancanti = {r: N_NUMERI - len(d) for r, d in dati.items() if len(d) != N_NUMERI}
    if mancanti:
        elenco = ", ".join(f"{r} ({m} mancanti)" for r, m in mancanti.items())
        raise ValueError(f"Il file non contiene tutti i {N_NUMERI} numeri per ogni ruota: {elenco}.")
    return Ritardi(dati)
