# Come perdere al lotto: documentazione

7 ottobre 2026 · Saverio Pititto

## Cosa fa

"Come perdere al lotto" è un'app Streamlit didattica che calcola il sistema ridotto di ambi più economico per una data garanzia e mostra quanto si perde, in media, giocandolo.

L'idea di base: i numeri che scegli sono i nodi di un grafo e gli ambi che giochi sono i suoi archi. Dato un livello di garanzia $t$ (oppure un budget), l'app costruisce il sistema di costo minimo e ne calcola la distribuzione esatta delle vincite, il valore atteso e la perdita media.

Il risultato chiave è che nessun design cambia la perdita attesa. Con quota ambo 250 si perde in media circa il 37,6% di quanto si gioca, circa il 42,6% con la ritenuta dell'8% sulle vincite. Cambiano solo la frequenza e la varianza delle vincite.

Questo è quello che dimostra l'app: un sistema ridotto non batte il banco, redistribuisce il rischio.

## Il modello matematico

Su una ruota escono $d = 5$ numeri tra $N = 90$, e un ambo vince se i suoi due numeri sono tra i cinque estratti. La probabilità di un singolo ambo è quindi 10/4005, cioè 1 su 400,5.

$$
P(\text{ambo}) = \frac{\binom{5}{2}}{\binom{90}{2}} = \frac{10}{4005}
$$

### Grafo e garanzia

I $k$ numeri scelti sono i nodi di un grafo $G$ e gli ambi giocati sono gli archi. La garanzia $t$ significa: se escono almeno $t$ dei tuoi $k$ numeri, vinci almeno un ambo. Equivale a dire che ogni gruppo di $t$ nodi contiene almeno un arco, cioè che il grafo non ha insiemi indipendenti di taglia $t$: $\alpha(G) \le t - 1$.

Trovare il sistema più economico è un problema di programmazione lineare intera, con una variabile $x_e$ per ogni possibile ambo $e$:

$$
\min \sum_{e \subset S} x_e \quad \text{s.t.} \quad \sum_{e \subset T} x_e \ge 1 \;\; \forall\, T \subset S,\ |T| = t, \qquad x_e \in \{0,1\}
$$

### Soluzione chiusa (Turán)

Il minimo si ottiene dividendo i $k$ numeri in $t-1$ gruppi il più possibile bilanciati e giocando tutti gli ambi dentro ogni gruppo ($t-1$ "cricche" disgiunte). Per il principio dei cassetti, $t$ numeri su $t-1$ gruppi ne mettono due nello stesso gruppo, e quell'ambo è giocato.

$$
|E|_{\min} = \sum_{i=1}^{t-1} \binom{n_i}{2}, \qquad n_i \in \left\{\left\lfloor \tfrac{k}{t-1} \right\rfloor,\ \left\lceil \tfrac{k}{t-1} \right\rceil\right\}
$$

Poiché escono solo 5 numeri, $t$ può arrivare al massimo a 5: per $t \ge 6$ la garanzia non scatta mai.

### Distribuzione esatta delle vincite

Sia $X$ quanti dei $k$ numeri escono (distribuzione ipergeometrica). Dato $X = m$, i numeri usciti sono un sottoinsieme uniforme di $m$ tra i tuoi $k$, e gli ambi vincenti sono gli archi che contiene.

- Per grafi a cricche disgiunte, come quelli di Turán, si conta con una programmazione dinamica esatta.
- Per grafi generici si enumerano gli $m$-sottoinsiemi, fino a 2,5 milioni di combinazioni.
- Con più ruote o più concorsi indipendenti la distribuzione è la convoluzione di quella di una ruota con sé stessa, calcolata per quadrature successive.

### Valore atteso

Per linearità il ritorno atteso dipende solo dal numero di ambi, non da come sono disposti:

$$
E[\text{ritorno}] = |E| \cdot \text{puntata} \cdot \text{ruote} \cdot \text{concorsi} \cdot \text{quota} \cdot (1 - \text{ritenuta}) \cdot P(\text{ambo})
$$

Per questo nessun design può cambiare la perdita media: può solo cambiarne la forma, cioè quanto spesso e quanto a lungo si vince.

### Quanto si aspetta prima di vincere

Se $p$ è la probabilità di vincere almeno un ambo in un'estrazione (sulle ruote giocate), le estrazioni $N$ fino alla prima vincita, compresa quella vincente, seguono una distribuzione geometrica:

$$
P(N = n) = (1-p)^{n-1}\, p, \qquad E[N] = \frac{1}{p}, \qquad n_a = \left\lceil \frac{\ln(1-a)}{\ln(1-p)} \right\rceil
$$

dove $n_a$ è il numero di estrazioni entro cui si vince con probabilità almeno $a$ (la mediana per $a = 0{,}5$, il 90° percentile per $a = 0{,}9$). In media si spendono quindi $E[N] \cdot \text{costo per estrazione}$ prima di vincere. Lo stesso vale per la prima estrazione chiusa in attivo, con $P(\text{profitto})$ al posto di $p$. Le estrazioni sono indipendenti: aver aspettato a lungo non avvicina la vincita.

Esempio: con $k = 8$ e $t = 3$ su una ruota $p \approx 2{,}85\%$, quindi servono in media 35 estrazioni (circa 12 settimane con 3 estrazioni a settimana): metà delle volte ne bastano 24, 9 volte su 10 al massimo 80.

### Vincita certa

Su una ruota escono 5 numeri, quindi si vince **sempre** almeno un ambo se ogni gruppo di 5 numeri contiene un ambo giocato, cioè se

$$
\alpha(G) \le 4
$$

La scheda "Vincita certa" parte dal sistema di Turán $(k, t)$, che ha $\alpha = t - 1$, e aggiunge ambi usando solo gli altri $90 - k$ numeri. Poiché i nuovi ambi non toccano i numeri già giocati, gli insiemi indipendenti delle due parti si sommano: sui numeri liberi possono restare al massimo $5 - t$ gruppi che non si giocano tra loro. Il minimo è di nuovo quello di Turán, con $5 - t$ cricche bilanciate:

$$
|E|_{\text{in più}} = \sum_{i=1}^{5-t} \binom{m_i}{2}, \qquad m_i \in \left\{\left\lfloor \tfrac{90-k}{5-t} \right\rfloor,\ \left\lceil \tfrac{90-k}{5-t} \right\rceil\right\}
$$

Con $t = 5$ non ci sono gruppi disponibili: senza collegare i numeri nuovi a quelli già giocati la vincita certa è impossibile. Partendo da zero, senza vincoli, il minimo assoluto è $|E|_{\min}(90, 5) = 968$ ambi; tenere separati i numeri già giocati costa di più. Esempio: con $k = 8$ e $t = 3$ servono $2 \cdot \binom{41}{2} = 1640$ ambi in più, 1652 in tutto.

Vincere sempre non vuol dire guadagnare: nel caso peggiore può uscire un solo ambo, e la perdita media resta quella di qualsiasi altro sistema con la stessa quota.

### Percorso minimo

La scheda "Percorso minimo" toglie il vincolo di non toccare i numeri già giocati. I $t - 1$ gruppi del sistema si allargano con numeri nuovi e se ne aprono altri $5 - t$, per un totale di al massimo 4 gruppi $n_1, \dots, n_4$ che coprono tutti i 90 numeri:

$$
|E|_{\text{totale}} = \sum_{i=1}^{4} \binom{n_i}{2}, \qquad \sum_{i=1}^{4} n_i = 90, \qquad n_i \ge n_i^{(0)}
$$

dove $n_i^{(0)}$ è la taglia di partenza di ogni gruppo ($0$ per quelli nuovi). Il costo $\binom{n}{2}$ è convesso, quindi conviene mettere ogni numero libero nel gruppo più piccolo: il risultato è il minimo possibile con i gruppi di partenza come vincolo, verificato a forza bruta su casi piccoli.

Esempio: con $k = 8$ e $t = 3$ i due gruppi da 4 diventano da 23 e se ne aprono due da 22, per $2\binom{23}{2} + 2\binom{22}{2} = 968$ ambi in tutto: 956 in più, contro i 1640 della vincita certa che non tocca i numeri già giocati. Se un gruppo di partenza è già più grande della media finale non si può ridurre, e il minimo assoluto di 968 non si raggiunge (per esempio con $k = 40$, $t = 2$).

## Come funziona il codice

Il progetto sono sette moduli Python in radice più una cartella di test. `core.py` contiene la matematica, `regole.py` le regole di gioco, e `app.py` li usa per costruire l'interfaccia.

| File | Cosa contiene |
|---|---|
| `core.py` | Design (grafo di ambi), costruzione di Turán, budget duale, distribuzione esatta (DP su cricche o enumerazione), statistiche, ILP con OR-Tools CP-SAT, Monte Carlo |
| `ilp_pulp.py` | ILP con PuLP/CBC e metriche per enumerazione diretta: un controllo indipendente da `core.py`. Si può lanciare da solo con `python ilp_pulp.py` (esempio $k=6$, $t=3$) |
| `regole.py` | Regole ufficiali: ruote, coefficienti di tutte le sorti, ambetto, limiti di importo, tetto di vincita, ritenuta, abbonamento; calcolo delle vincite di uno scontrino |
| `ritardi.py` | Lettura del «tabellone analitico» dei ritardi caricato a mano: ritardo di ogni numero per ruota e classifiche |
| `viz.py` | Grafici Plotly: grafo, frontiera costo/probabilità, saldo simulato |
| `style.py` | Stile dell'interfaccia: CSS, schede arrotondate e blocchi HTML |
| `app.py` | Interfaccia Streamlit: barra laterale, sette schede principali e cinque sottoschede in "Approfondimenti" |
| `DOCUMENTAZIONE.md` | Questa documentazione, mostrata anche in Approfondimenti → Documentazione |
| `.streamlit/config.toml` | Tema: palette e angoli arrotondati |
| `tests/` | `test_core.py` (69 test), `test_ilp_pulp.py` (11), `test_regole.py` (43), `test_ritardi.py` (3) |

### Flusso di un calcolo

Streamlit riesegue `app.py` da capo a ogni modifica di un controllo. Ogni esecuzione fa questi passi:

1. Legge la barra laterale: modalità, puntata, concorsi, ruote, quota ambo, ritenuta e i parametri della modalità scelta.
2. Se la modalità parte da un budget, ricava $k$ oppure $t$ con `max_k_for_edges` o `best_t_for_edges`.
3. Costruisce il sistema con `turan_design(k, t)`.
4. Calcola le statistiche con `analyze(...)`, che restituisce un oggetto `Stats`.
5. Disegna le schede usando quelle statistiche; i calcoli pesanti (frontiera, simulazione) sono in cache con `st.cache_data`.

### Le funzioni principali di core.py

| Funzione | Cosa fa |
|---|---|
| `turan_group_sizes(k, t)` | Taglie dei $t-1$ gruppi più bilanciati |
| `turan_min_edges(k, t)` | Numero minimo di ambi per la garanzia $t$ |
| `turan_design(k, t)` | Costruisce il sistema ottimo come oggetto `Design` |
| `matching_design(n)` | Coppie disgiunte: nessuna garanzia, massima probabilità di incassare almeno una volta |
| `wins_counts(design)` | Conteggi esatti delle cinquine per numero di ambi vincenti; la somma è $\binom{90}{5}$ |
| `analyze(design, ...)` | Distribuzione, valore atteso, perdita %, deviazione standard, P(profitto) |
| `solve_ilp(k, t, min_wins)` | ILP con CP-SAT; `min_wins` permette di garantire più di un ambo |
| `simulate_wins(design, n)` | Monte Carlo con estrazioni casuali |
| `max_k_for_edges`, `best_t_for_edges` | Problema duale: dato il budget, quanti numeri o quale garanzia |
| `certain_win_extension(k, t)` | Ambi da aggiungere sui numeri non ancora giocati per vincere sempre almeno un ambo (oggetto `CertainWin`) |
| `certain_win_design(k, t)` | Sistema completo per la vincita certa: quello di partenza più l'aggiunta, su tutti i 90 numeri |
| `minimal_path(k, t)` | Percorso minimo verso la vincita certa allargando anche i gruppi già giocati (oggetto `MinimalPath`) |
| `minimal_path_design(k, t)` | Sistema completo del percorso minimo, su tutti i 90 numeri |
| `draws_until_first(p)` | Attesa del primo successo (geometrica): media, mediana e 90° percentile in estrazioni |
| `waiting_gaps(hits)` | Attese osservate in una simulazione: fino al primo successo e tra un successo e il successivo |

OR-Tools serve solo alla sottoscheda "Verifica ILP" e PuLP solo a "ILP con PuLP" (entrambe in "Approfondimenti"): se uno dei due manca, il resto dell'app funziona comunque.

## Le regole di gioco

`regole.py` traduce le regole ufficiali del Lotto in codice e calcola la vincita di uno scontrino contro un'estrazione. Il sistema ridotto del resto dell'app usa solo l'ambo, mentre questo modulo gestisce tutte le sorti.

### Ruote e limiti

- 5 numeri estratti tra 1 e 90 su 10 ruote cittadine (Bari, Cagliari, Firenze, Genova, Milano, Napoli, Palermo, Roma, Torino, Venezia) e sulla ruota Nazionale.
- "Tutte le ruote" indica le 10 cittadine: la Nazionale va aggiunta a parte.
- Una giocata ha da 1 a 10 numeri.
- Importo per scontrino da 1 € a 200 €, a incrementi di 0,50 €. Oltre i 200 € le giocate vanno su più scontrini.
- Vincita massima di 6 milioni di euro per scontrino, poi ritenuta dell'8%.
- Abbonamento fino a 50 concorsi consecutivi.

### Coefficienti

I coefficienti valgono per una singola ruota. La posta di ogni sorte è divisa tra le combinazioni giocate e tra le ruote.

| Sorte | Coefficiente |
|---|---:|
| Estratto | 11,233 |
| Estratto determinato | 55 |
| Ambo | 250 |
| Ambetto | 260 |
| Terno | 4.500 |
| Quaterna | 120.000 |
| Cinquina | 6.000.000 |

### Come si calcola una vincita

Per ogni ruota e per ogni sorte puntata, `regole.py` conta quante combinazioni della giocata sono uscite. La vincita lorda è il numero di combinazioni vincenti, per la quota di ciascuna, per il coefficiente della sorte.

$$
\text{vincita lorda} = v \cdot \frac{\text{posta}}{n_{\text{comb}} \cdot n_{\text{ruote}}} \cdot \text{coefficiente}
$$

In questa formula $v$ è il numero di combinazioni vincenti e $n_{\text{comb}}$ quante ne ha la giocata. Le vincite di uno scontrino si sommano, si limitano a 6 milioni e poi si applica la ritenuta. Le giocate che superano i 200 € sono ripartite in scontrini con la funzione `dividi_in_scontrini`, che usa il criterio first-fit decrescente.

### Ambetto

Vince ogni coppia estratta formata da un numero giocato e dal precedente o dal successivo di un altro numero giocato (decreto dirigenziale 2013/7649). Il modello assume la numerazione circolare, quindi il precedente di 1 è 90, e che il numero vicino non sia a sua volta giocato: in quel caso la coppia sarebbe un ambo.

## L'interfaccia

L'app ha una barra laterale per i parametri e sette schede che mostrano i risultati; gli strumenti di verifica sono raccolti nella scheda "Approfondimenti". Lo stile è a pillole e schede bianche arrotondate, con palette sky blue, blue green, deep space blue, amber flame e princeton orange, e font Archivo.

### Barra laterale

La barra laterale è divisa in tre passi numerati più le opzioni avanzate.

**1 · Da dove parti?** Le tre modalità sono tre modi di porre lo stesso problema:

| Modalità | Cosa fissi | Cosa ottieni |
|---|---|---|
| Scelgo numeri e garanzia | $k$ (3-40) e $t$ | Quanto costa: il sistema ridotto più economico |
| Ho un budget e una garanzia | Budget e $t$ | Quanti numeri copri: il massimo $k$ con quel budget |
| Ho un budget e dei numeri | Budget e $k$ (3-40) | Che garanzia ottieni: il $t$ più basso possibile |

**2 · I tuoi dati.** I cursori o il budget della modalità scelta, con sotto il riepilogo della garanzia ("se escono almeno $t$ dei tuoi $k$ numeri, vinci almeno un ambo").

**3 · Quanto giochi.**

- **Puntata per ogni ambo**, per ruota, da 0,05 €.
- **Ruote**: una selezione libera oppure "Tutte le ruote" con la Nazionale opzionale.

**Opzioni avanzate** (chiuse all'inizio):

- **Concorsi consecutivi**, da 1 a 50 (abbonamento).
- **Quota ambo**, di partenza 250.
- **Ritenuta** dell'8% sulle vincite, disattivabile per confronto.
- **I tuoi numeri**, facoltativi: se li inserisci sostituiscono l'etichetta 1…k nella schedina.

### Le schede

| Scheda | Cosa mostra |
|---|---|
| Risultato | Una frase di riepilogo, le metriche (ambi da giocare, costo, probabilità che la garanzia scatti e di vincere almeno un ambo) e quanto perdi in media. Poi cosa giocare (gli ambi, scaricabili in CSV), il grafo dei tuoi numeri e cosa può succedere: la distribuzione dell'esito, anche a fasce se i valori sono troppi |
| Confronto | A parità di spesa, confronta il sistema ridotto con tutti gli ambi e con le coppie disgiunte, e disegna la frontiera costo contro probabilità di vincita |
| Controlla una giocata | In tre passi: cosa giochi (il sistema ridotto e/o una giocata tua su qualsiasi sorte), l'estrazione (casuale, con un numero per cambiarla, o inserita a mano, solo per le ruote che giochi) e l'esito con le regole ufficiali, spiegato passaggio per passaggio |
| Vincita certa | Quanti ambi aggiungere, sui numeri non ancora giocati, per vincere sempre almeno un ambo: costo in più, vincita minima, i gruppi da giocare (anche in CSV) e perché vincere sempre non vuol dire guadagnare |
| Percorso minimo | Il modo più economico per arrivare alla vincita certa allargando anche i gruppi già giocati: ambi in più, risparmio rispetto a "Vincita certa", come allargare ogni gruppo (anche in CSV) |
| Ritardatari | Carichi il «tabellone analitico» dei ritardi (file di testo, da scaricare a mano: i siti che lo pubblicano bloccano lo scaricamento automatico) e vedi i 10 numeri più in ritardo per ruota e in assoluto. Un pulsante usa i $k$ più in ritardo come «I tuoi numeri» |
| Approfondimenti | Cinque sottoschede per chi vuole verificare i conti (sotto) |

Le sottoschede di "Approfondimenti":

| Sottoscheda | Cosa mostra |
|---|---|
| Simulazione | Monte Carlo fino a 2 milioni di estrazioni, confrontato con i valori esatti, più il saldo cumulato. Calcola anche quante estrazioni servono prima di vincere (attesa media, mediana, 90° percentile, spesa e tempo con 3 estrazioni a settimana), sia esatte sia osservate nella simulazione |
| Verifica ILP | Risolve l'ILP con CP-SAT ($k$ fino a 14) e lo confronta con Turán; permette anche di garantire $m \ge 2$ ambi |
| ILP con PuLP | Stesso modello con PuLP/CBC ($k$ fino a 12) e metriche per enumerazione diretta, come controllo indipendente |
| Come funziona | Riassunto teorico: setup, grafo, garanzia, ILP, Turán, distribuzione, valore atteso |
| Documentazione | Questa documentazione |

Se i parametri sono incoerenti, per esempio un budget troppo basso, la scheda mostra un messaggio d'errore invece dei risultati. Le giocate che superano i limiti di importo vengono segnalate.

## Come si usa

Si installano le dipendenze e si avvia con Streamlit. Le dipendenze sono Streamlit 1.50 o successivo, NumPy, pandas, Plotly, OR-Tools e PuLP (versione inferiore alla 4).

### Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Test

I 126 test passano tutti (69 per `core.py`, 11 per `ilp_pulp.py`, 43 per `regole.py`, 3 per `ritardi.py`). Controllano tra l'altro che Turán coincida con l'ILP, le probabilità note, l'indipendenza del valore atteso dal design, le regole di gioco e che vincita certa e percorso minimo usino davvero il minimo di ambi (confronto con la ricerca esaustiva su casi piccoli) e vincano sempre, e che le attese simulate prima di vincere tornino con la distribuzione geometrica.

```bash
pip install pytest
pytest
```

### Esempio da riga di comando

Il controllo con PuLP si può lanciare senza interfaccia: `python ilp_pulp.py` risolve $k=6$, $t=3$ e stampa le metriche.

### Deploy su Streamlit Community Cloud

1. Carica la cartella su un repository GitHub, con in radice `app.py`, `core.py`, `ilp_pulp.py`, `regole.py`, `ritardi.py`, `style.py`, `viz.py`, `DOCUMENTAZIONE.md`, `requirements.txt` e `.streamlit/config.toml`.
2. Su share.streamlit.io scegli *New app*, poi repository e branch, e come *Main file path* `app.py`.
3. In *Advanced settings* scegli Python 3.12 o 3.13 e premi *Deploy*.

PuLP è fissato a una versione inferiore alla 4 perché dalla 4.0 non include più il solver CBC.

### Un esempio d'uso

Vuoi giocare con 8 numeri e la garanzia di un ambo se ne escono 3 su una ruota. Scegli la modalità "Scelgo numeri e garanzia" con $k = 8$ e $t = 3$. Il sistema divide gli 8 numeri in 2 gruppi da 4 e gioca tutti gli ambi dentro ogni gruppo, cioè $2 \cdot \binom{4}{2} = 12$ ambi. La scheda Risultato mostra costo, probabilità e distribuzione, e la scheda Confronto mostra che tutti gli ambi su 8 numeri ($\binom{8}{2} = 28$) costerebbero più del doppio con la stessa perdita percentuale.

## Limiti e ipotesi

L'app è uno strumento didattico e non una guida per vincere: il valore atteso resta negativo qualunque sistema si scelga.

- **Estrazioni indipendenti.** Con più ruote o più concorsi si assume che le estrazioni siano indipendenti, per cui la distribuzione è una convoluzione.
- **Quali numeri scegli è indifferente.** L'estrazione è uniforme, quindi conta solo la struttura del sistema, non i numeri. Vale anche per i ritardatari: un numero che manca da molte estrazioni ha la stessa probabilità di uscire di qualsiasi altro.
- **Garanzia solo fino a $t = 5$.** Escono 5 numeri, quindi per $t \ge 6$ la garanzia non scatta mai.
- **Ambetto semplificato.** Si assume la numerazione circolare e che il numero vicino non sia a sua volta giocato.
- **Dimensioni massime.** Il sistema usa fino a 40 numeri; la modalità "Ho un budget e una garanzia" può salire fino a 90. L'enumerazione per grafi generici si ferma a 2,5 milioni di combinazioni, e i controlli ILP girano su $k$ fino a 14 (CP-SAT) e 12 (PuLP).
- **Fuori dal calcolo.** Orari di raccolta e modalità di compilazione della schedina non incidono sui risultati.
- **Stile legato a Streamlit.** Lo stile in `style.py` usa attributi interni di Streamlit (`data-testid`, `role`), testati con la versione 1.65: dopo un aggiornamento un elemento può perdere lo stile e il selettore va aggiornato.

Il gioco d'azzardo può causare dipendenza ed è vietato ai minori.
