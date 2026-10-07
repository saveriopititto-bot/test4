# Sistemi ridotti per ambi al Lotto — modello a grafo

App Streamlit didattica. Numeri scelti = nodi, ambi giocati = archi.
Dato un livello di garanzia `t` (o un budget) calcola il sistema ridotto di costo minimo e mostra
distribuzione esatta delle vincite, valore atteso e perdita media.

**Risultato chiave:** nessun design cambia la perdita attesa (≈ 37,6% con quota ambo 250);
cambiano solo frequenza e varianza delle vincite.

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

1. Carica la cartella su un repository GitHub (file in radice: `app.py`, `core.py`, `ilp_pulp.py`, `viz.py`, `requirements.txt`).
2. Su share.streamlit.io: *New app* → scegli repo e branch → *Main file path*: `app.py`.
3. In *Advanced settings* scegli Python 3.12 (o 3.13) e premi *Deploy*.

OR-Tools è usato solo nel tab "Verifica ILP" e PuLP solo nel tab "ILP con PuLP": se uno dei due manca, il resto dell'app funziona comunque. PuLP è fissato a `<4` perché dalla 4.0 non include più il solver CBC.

Il modulo PuLP si può lanciare anche da solo: `python ilp_pulp.py` (esempio k=6, t=3).

## Struttura

| File | Contenuto |
|---|---|
| `core.py` | Turán, budget duale, distribuzione esatta (DP su cliche / enumerazione), statistiche, ILP CP-SAT, Monte Carlo |
| `viz.py` | Grafici Plotly (grafo, distribuzione, frontiera, saldo simulato) |
| `style.py` | Stile dell'interfaccia (layout 1a): CSS, schede arrotondate e blocchi HTML |
| `.streamlit/config.toml` | Tema: palette e angoli arrotondati |
| `ilp_pulp.py` | ILP con PuLP/CBC e metriche per enumerazione diretta (controllo indipendente) |
| `app.py` | Interfaccia Streamlit |
| `tests/test_core.py` | 38 test: Turán vs ILP, probabilità note, EV indipendente dal design, budget, simulazione |
| `tests/test_ilp_pulp.py` | 11 test: ottimo PuLP = Turán, metriche identiche a `core.py` |

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
- Negli slider k arriva a 40; in modalità "Budget + garanzia" k può salire fino a 90 (tutta la ruota).

## Limiti

Quota e puntata sono parametri. Tasse sulle vincite, limiti di puntata e regole di ripartizione
della schedina reale non sono modellati. Strumento a scopo didattico: il gioco d'azzardo può
causare dipendenza ed è vietato ai minori.
