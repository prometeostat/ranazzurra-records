# Ranazzurra Records

Gestione dei record societari della **squadra agonistica di categoria** di Ranazzurra Conegliano SSD: anagrafica atleti, personali, classifica dei record (i primi 3 tempi per gara, vasca e sesso) e importazione dei risultati dai PDF pubblicati dalla FIN.

L'applicazione e' una app Streamlit su Streamlit Community Cloud con database MySQL su Aiven. La pagina pubblica `record_societari.html` del sito della societa' legge il file `records.json` generato da `esporta_records.py`.

Il progetto Master Conegliano (app `ranazzurra_streamlit`, database PostgreSQL) e' un'altra cosa e vive in un altro repository.

## Funzionalita'

- **Dashboard**: numeri principali, record societari, podio e progressione di una gara, ultimi personali e ultime importazioni.
- **Record Top 3**: la stessa classifica pubblicata sul sito, ex aequo compresi, con il download di `records.json`.
- **Gestione atleti** e **Gestione record** (personali): inserimento, modifica, disattivazione. Un tempo piu' lento non sostituisce mai un personale, salvo correzione esplicita.
- **Importa risultati FIN**: lettura del PDF da Google Drive o dal computer, riconoscimento degli atleti, confronto con lo storico, anteprima con nuovi record e primati personali, conferma esplicita, storico delle importazioni.

## Avvio in locale

Serve Python 3.11 (la versione di Streamlit Cloud, vedi `runtime.txt`).

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # e compilalo
streamlit run streamlit_app.py
```

`.streamlit/secrets.toml` contiene le credenziali e non va mai nel repository (e' in `.gitignore`). Le sezioni sono descritte nell'esempio e in [docs/deployment.md](docs/deployment.md).

## Operazioni ricorrenti

| Cosa | Come |
|---|---|
| Aggiornare lo schema del database | `python -m ranazzurra_records.migrazioni --applica` (fa prima un backup) |
| Importare i risultati di una gara | pagina *Importa risultati FIN*, vedi [docs/fin-results-import.md](docs/fin-results-import.md) |
| Pubblicare i record sul sito | `python esporta_records.py` (genera `records.json` e lo carica via FTP) |
| Lanciare i test | `pip install -r requirements-dev.txt` e poi `python -m pytest` |

## Documentazione

| Documento | Contenuto |
|---|---|
| [CLAUDE.md](CLAUDE.md) | regole operative per chi lavora sul codice (persone e Claude) |
| [docs/architecture.md](docs/architecture.md) | componenti, moduli, flussi |
| [docs/database.md](docs/database.md) | tabelle, vincoli, migrazioni, backup |
| [docs/records-management.md](docs/records-management.md) | regole dei personali e dei record societari |
| [docs/fin-results-import.md](docs/fin-results-import.md) | procedura di importazione dei PDF FIN |
| [docs/google-drive-integration.md](docs/google-drive-integration.md) | configurazione dell'accesso a Google Drive |
| [docs/development-guide.md](docs/development-guide.md) | ambiente di sviluppo, test, convenzioni |
| [docs/deployment.md](docs/deployment.md) | Streamlit Cloud, Aiven, secrets, pubblicazione sul sito |
| [docs/project-status.md](docs/project-status.md) | stato attuale, problemi noti, prossimi passi |
| [docs/decisions/](docs/decisions/) | decisioni architetturali (ADR) |
