# Guida allo sviluppo

## Ambiente

Python 3.11 (come Streamlit Cloud). Dipendenze dell'app in `requirements.txt` (vincoli `>=`, salvo `tornado<6.5` per compatibilita' con Streamlit); strumenti di sviluppo in `requirements-dev.txt`.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run streamlit_app.py
```

Per sviluppare senza toccare il database vero conviene un MySQL locale: crea un database vuoto, carica `db/schema_base.sql` con il client `mysql` (contiene `DELIMITER`) e applica le migrazioni con `python -m ranazzurra_records.migrazioni --applica`. Le variabili `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` (e `MYSQL_SSL_DISABLED=1` se il server non ha TLS) vincono sui secrets.

## Test

```bash
python -m pytest                          # unitari: niente database, niente rete
RANAZZURRA_TEST_MYSQL=1 python -m pytest  # anche integrazione MySQL
```

| File | Cosa copre |
|---|---|
| `test_tempi.py` | parsing, formattazione, centesimi, plausibilita' |
| `test_records.py` | DENSE_RANK, top 3, tutti gli esiti |
| `test_parser.py` | righe e titoli, PDF sintetici (continuazioni, gara mista, altre societa'), PDF scansionato, PDF reale dell'08/11/2026 |
| `test_matching.py` | normalizzazione, ordine invertito, doppi cognomi, refusi, omonimi, alias, sesso |
| `test_analisi.py` | anteprima in memoria: esiti, decisioni, duplicati, controlli, batterie e finale |
| `test_export_config_drive.py` | JSON del sito, configurazione, Google Drive con sessione finta |
| `test_integrazione_mysql.py` | migrazioni rieseguibili, personale piu' lento, importazione idempotente, rollback completo |

I test d'integrazione creano e cancellano un database `ranazzurra_test` sul server indicato da `MYSQL_*`: usare solo un server di prova, mai Aiven di produzione. L'utente deve poter creare quel database.

Il PDF reale dell'08/11/2026 contiene nomi di minori e non e' nel repository: per eseguire il suo test va copiato in `tests/fixtures_privati/riepilogo_20261108.pdf` (cartella ignorata da git) o indicato con `RANAZZURRA_PDF_TEST`. I PDF sintetici richiedono `reportlab` (solo sviluppo).

Interfaccia: `streamlit.testing.v1.AppTest` per far girare le pagine senza browser (con `PYTHONPATH=.`); per le tabelle modificabili (`st.data_editor`) serve una prova in un browser vero su `streamlit run`.

## Convenzioni

- Codice, commenti, docstring e testi a video in italiano.
- SQL solo in `queries.py`, parametrizzato. Niente doppi apici nelle stringhe SQL (`ANSI_QUOTES`).
- Tempi in centesimi interi; conversione a/da DB con `tempi.a_decimal` e `tempi.da_db`.
- La logica sta fuori da `views/`; una pagina chiama `repository`, `importazione` o `export`.
- Scritture multi-riga in `db.transazione()`. Dopo una scrittura da una pagina, `comuni.dopo_scrittura()`.
- Nuova colonna o tabella: nuova migrazione numerata in `db/migrations/`, aggiornamento di `docs/database.md`.
- Ogni modifica al parser porta un test con la riga o il PDF che l'ha resa necessaria.

## Aggiungere una pagina

Un file in `ranazzurra_records/views/` con `mostra()`, una voce nel dizionario `PAGINE` di `streamlit_app.py`, una riga in `docs/architecture.md`.
