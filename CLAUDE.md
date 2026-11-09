# CLAUDE.md · Ranazzurra Records

Record societari della **squadra agonistica di categoria** di Ranazzurra Conegliano SSD. App Streamlit (Community Cloud) su MySQL 8.4 (Aiven, servizio `record-societari`, progetto `swim-project`), piu' la pagina statica `record_societari.html` sul sito Register.it alimentata da `records.json`.

**Non e' il progetto Master.** L'app Master Conegliano (`prometeostat/ranazzurra_streamlit`, PostgreSQL `swim`) e' separata: niente tabelle, regole o atleti in comune. Da li' viene solo il parser dei PDF FIN, adattato e copiato qui (ADR-003). La societa' importata e' soltanto RANAZZURRA CONEGLIANO SSD, mai RANAZZURRA SPRESIANO o RANAZZURRA Lido.

## Struttura

`streamlit_app.py` e' solo l'entrypoint (menu e instradamento). Tutto il resto sta in `ranazzurra_records/`: `config` (secrets), `db` (connessione e transazioni), `tempi` (centesimi interi), `queries` (tutto l'SQL), `repository` (letture e scritture), `records` (regole di classifica), `export` (records.json), `migrazioni`, `gdrive`, `fin_pdf/parser`, `importazione/{matching,analisi,salvataggio}`, `views/` (una pagina per file). I moduli fuori da `views/` non importano Streamlit. Dettagli in `docs/architecture.md`.

## Regole sui dati (non negoziabili)

- I record societari sono la top 3 per gara + vasca + sesso calcolata con `DENSE_RANK` dai personali. La tabella `record_societari` e la procedura `aggiorna_record_societari` sono dismesse (falliscono con lo `sql_mode` di Aiven): non riusarle (ADR-002).
- Un personale si sostituisce solo con un tempo **strettamente migliore**. Le correzioni verso un tempo peggiore passano dalla scheda Modifica o da `sovrascrivi_peggiore=True`, mai di nascosto.
- Nessuna scrittura sui record senza conferma dell'utente: l'importazione mostra l'anteprima e scrive solo dopo il bottone di conferma, in un'unica transazione.
- Le associazioni atleta approssimate non si applicano mai da sole: automatico solo con nome e anno identici (o alias confermato).
- Niente cancellazioni a cascata: un atleta con tempi si disattiva. Non cancellare righe di `risultati`, `importazioni`, `record_personali` senza richiesta esplicita.
- Lo schema cambia solo con una migrazione numerata in `db/migrations/`, additiva e rieseguibile, applicata con `python -m ranazzurra_records.migrazioni --applica` (backup automatico). **Mai eseguire `db/schema_base.sql` sul database vero**: comincia con `DROP TABLE`.
- Non inventare dati mancanti dei PDF (data, luogo, vasca, tempo): la riga diventa non valida.

## Regole di codice

- SQL sempre parametrizzato con `%s`, tutto in `queries.py`. Su Aiven lo `sql_mode` include `ANSI_QUOTES` e `ONLY_FULL_GROUP_BY`: stringhe solo tra apici singoli, niente colonne non aggregate nei `GROUP BY`.
- Nelle query sulle gare va sempre selezionato il codice vasca; le classifiche partizionano per gara, vasca **e sesso**.
- Tempi: dentro il codice `int` di centesimi (`tempi.parse_tempo`, `tempi.formatta`), a DB `DECIMAL(10,2)` piu' `tempo_formattato` in formato `M:SS.CC`. Mai confrontare stringhe o float.
- Scritture multi-riga con `db.transazione()`; dopo ogni scrittura dalle pagine, `comuni.dopo_scrittura()` per svuotare la cache.
- Credenziali solo da `st.secrets` / `.streamlit/secrets.toml` / variabili d'ambiente (`config.py`). **Mai leggere, copiare o stampare `secrets.toml`**; la struttura e' in `secrets.toml.example`.
- `ca.pem` (CA pubblica di Aiven) resta nel repository: l'app su Streamlit Cloud lo usa.
- Testi a video, commenti e docstring in italiano. Contratto di `records.json` invariato (lo legge la pagina del sito).
- Nella JavaScript del sito usare `filter()` e non `find()` per le posizioni: con gli ex aequo `find()` perde gli atleti.

## Verifica prima di consegnare

```bash
python -m py_compile streamlit_app.py esporta_records.py ranazzurra_records/*.py ranazzurra_records/*/*.py
python -m pytest                        # unitari, senza DB ne' rete
RANAZZURRA_TEST_MYSQL=1 python -m pytest   # anche integrazione su un MySQL di prova (MAI quello vero)
```

Il PDF reale di prova (08/11/2026) contiene nomi di minori e non e' nel repository: si mette in `tests/fixtures_privati/` (ignorata da git). Per l'interfaccia: `streamlit.testing.v1.AppTest` o una prova in browser su `streamlit run`. Guida completa in `docs/development-guide.md`.

## Lavorare sul repository

- La cartella di lavoro di Mirko e' su Google Drive (`G:\Il mio Drive\Job\ranazzurra\record_societari`); il deploy parte dal branch `main` di `prometeostat/ranazzurra-records`. Lavorare su un branch e aprire una pull request; il merge lo decide Mirko.
- Dopo un push con dipendenze nuove o moduli nuovi, su Streamlit Cloud serve il Reboot dall'app manager.
- Ogni modifica significativa aggiorna la documentazione toccata (schema -> `docs/database.md`, import -> `docs/fin-results-import.md`, ecc.) e, se cambia lo stato del progetto, `docs/project-status.md`. Le decisioni definitive vanno in un ADR, non solo nello stato.
