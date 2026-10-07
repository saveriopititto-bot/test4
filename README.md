# Come perdere al lotto

Sistemi ridotti per ambi al Lotto, con un modello a grafo.

App Streamlit didattica. Numeri scelti = nodi, ambi giocati = archi.
Dato un livello di garanzia `t` (o un budget) calcola il sistema ridotto di costo minimo e mostra
distribuzione esatta delle vincite, valore atteso e perdita media.

**Risultato chiave:** nessun design cambia la perdita attesa (≈ 37,6% con quota ambo 250, ≈ 42,6%
con la ritenuta dell'8% sulle vincite); cambiano solo frequenza e varianza delle vincite.

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pip install pytest
pytest
```

## Deploy su Streamlit Community Cloud

1. Carica la cartella su un repository GitHub (file in radice: `app.py`, `core.py`, `ilp_pulp.py`, `regole.py`, `style.py`, `viz.py`, `DOCUMENTAZIONE.md`, `requirements.txt`, `.streamlit/config.toml`).
2. Su share.streamlit.io: *New app* → scegli repo e branch → *Main file path*: `app.py`.
3. In *Advanced settings* scegli Python 3.12 (o 3.13) e premi *Deploy*.

OR-Tools è usato solo nella scheda "Verifica ILP" (sotto "Approfondimenti") e PuLP solo in "ILP con PuLP": se uno dei due manca, il resto dell'app funziona comunque. PuLP è fissato a `<4` perché dalla 4.0 non include più il solver CBC.

Il modulo PuLP si può lanciare anche da solo: `python ilp_pulp.py` (esempio k=6, t=3).

## Struttura

| File | Contenuto |
|---|---|
| `core.py` | Turán, budget duale, distribuzione esatta (DP su cliche / enumerazione), statistiche, ILP CP-SAT, Monte Carlo |
| `viz.py` | Grafici Plotly (grafo, distribuzione, frontiera, saldo simulato) |
| `style.py` | Stile dell'interfaccia (layout 1a): CSS, schede arrotondate e blocchi HTML |
| `.streamlit/config.toml` | Tema: palette e angoli arrotondati |
| `DOCUMENTAZIONE.md` | Documentazione completa (formule in LaTeX), mostrata anche nell'app in Approfondimenti → Documentazione |
| `ilp_pulp.py` | ILP con PuLP/CBC e metriche per enumerazione diretta (controllo indipendente) |
| `regole.py` | Regole ufficiali: ruote, coefficienti di tutte le sorti, ambetto, limiti di importo, tetto di vincita, ritenuta, abbonamento; calcolo delle vincite di uno scontrino |
| `app.py` | Interfaccia Streamlit |
| `tests/test_core.py` | 38 test: Turán vs ILP, probabilità note, EV indipendente dal design, budget, simulazione |
| `tests/test_ilp_pulp.py` | 11 test: ottimo PuLP = Turán, metriche identiche a `core.py` |
| `tests/test_regole.py` | 43 test: regole di gioco e calcolo vincite (anche su più scontrini), ritenuta e concorsi nel modello |

## Interfaccia

Layout "1a": barra di navigazione a pillole, barra laterale e sezioni come schede bianche arrotondate,
palette sky blue `#8ecae6`, blue green `#219ebc`, deep space blue `#023047`, amber flame `#ffb703`,
princeton orange `#fb8500`, font Archivo. Lo stile in `style.py` si aggancia ad attributi interni di
Streamlit (`data-testid`, `role`), testati con Streamlit 1.65: se dopo un aggiornamento un elemento
perde lo stile, va aggiornato il selettore.

## Modello in breve

- Ruota con N = 90 numeri, d = 5 estratti; P(ambo) = C(5,2)/C(90,2) = 1/400,5.
- Garanzia `t`: ogni gruppo di `t` dei tuoi `k` numeri contiene un ambo giocato (α(G) ≤ t−1).
- Minimo ambi (Turán): `t−1` cliche disgiunte bilanciate, `Σ C(n_i, 2)`.
- Poiché escono 5 numeri, `t ≤ 5`: per `t ≥ 6` la garanzia non scatta mai.
- Più ruote: estrazioni indipendenti, distribuzione = convoluzione.
- Negli slider k arriva a 40; in modalità "Ho un budget e una garanzia" k può salire fino a 90 (tutta la ruota).

## Regole di gioco applicate

- 5 numeri estratti tra 1 e 90 su 10 ruote cittadine (Bari, Cagliari, Firenze, Genova, Milano, Napoli,
  Palermo, Roma, Torino, Venezia) e sulla ruota Nazionale; "tutte le ruote" = le 10 cittadine.
- Giocata da 1 a 10 numeri. Coefficienti per una singola ruota: estratto 11,233 · estratto determinato 55 ·
  ambo 250 · ambetto 260 · terno 4.500 · quaterna 120.000 · cinquina 6.000.000. La posta di ogni sorte è
  divisa tra le combinazioni giocate e tra le ruote.
- Importo per scontrino da 1 € a 200 €, a incrementi di 0,50 €; oltre i 200 € servono più scontrini.
- Vincita massima 6 milioni di € per scontrino (con sole puntate su ambo non viene mai raggiunta).
- Ritenuta dell'8% sulle vincite (disattivabile nelle opzioni avanzate della barra laterale per confronto).
- Abbonamento fino a 50 concorsi consecutivi: costo e distribuzione delle vincite sommano i concorsi.

La scheda **Controlla una giocata** applica le regole a uno scontrino (il sistema ridotto e/o una giocata libera su
qualsiasi sorte) contro un'estrazione casuale o inserita a mano.

## Limiti

Ambetto (d.d. 2013/7649): vince ogni coppia estratta formata da un numero giocato e dal precedente o
successivo di un altro numero giocato. Si assume la numerazione circolare (il precedente di 1 è 90) e che
il numero vicino non sia a sua volta giocato (in quel caso la coppia è un ambo).
Orari di raccolta e modalità di compilazione della schedina non incidono sul calcolo. Strumento a scopo didattico: il gioco d'azzardo può
causare dipendenza ed è vietato ai minori.
