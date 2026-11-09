# Architettura

## Componenti

```text
            Google Drive (cartella PDF FIN)            PDF caricato a mano
                        │  service account, sola lettura       │
                        ▼                                       ▼
 ┌──────────────── App Streamlit (Community Cloud) ─────────────────────┐
 │ streamlit_app.py → views/ (dashboard, top3, atleti, personali,       │
 │                            importa)                                  │
 │ fin_pdf/parser → importazione/matching → analisi → salvataggio       │
 │ repository / queries / records / tempi / db / config                 │
 └──────────────────────────────┬───────────────────────────────────────┘
                                │ TLS (ca.pem)
                     MySQL 8.4 su Aiven (record-societari)
                                │
        esporta_records.py (in locale) → records.json → FTP (TLS) → Register.it
                                                     record_societari.html
```

L'app e' l'unico punto di scrittura. Il sito e' statico: legge `records.json`, che viene rigenerato e caricato da `esporta_records.py` (lanciato a mano) oppure scaricato dalla pagina *Record Top 3* e caricato via FTP.

## Moduli

| Modulo | Responsabilita' | Streamlit? |
|---|---|---|
| `streamlit_app.py` | configurazione pagina, menu, gestione degli errori di configurazione e database | si' |
| `views/comuni.py` | connessione per sessione, letture cachate (TTL 60 s), formattazione, card | si' |
| `views/*.py` | una pagina per file, funzione `mostra()` | si' |
| `config.py` | secrets da `st.secrets`, `.streamlit/secrets.toml` o variabili d'ambiente | no |
| `db.py` | connessione MySQL con riconnessione, `transazione()` con commit/rollback | no |
| `queries.py` | tutto l'SQL | no |
| `repository.py` | letture e scritture usate da pagine e script | no |
| `tempi.py` | parsing e formattazione dei tempi su centesimi interi, plausibilita' | no |
| `records.py` | DENSE_RANK, top 3, classificazione di un risultato (`Esito`) | no |
| `export.py` | payload di `records.json` (contratto con il sito) | no |
| `migrazioni.py` | applicazione controllata di `db/migrations/*.sql` con backup | no |
| `gdrive.py` | elenco e download dei PDF da Google Drive | no |
| `fin_pdf/parser.py` | lettura dei riepiloghi risultati FIN | no |
| `importazione/matching.py` | riconoscimento degli atleti del PDF | no |
| `importazione/analisi.py` | confronto con lo storico, anteprima (nessuna scrittura) | no |
| `importazione/salvataggio.py` | scrittura transazionale dell'importazione confermata | no |

I moduli senza Streamlit si provano da terminale e con `pytest`.

## Flusso di importazione

1. La pagina ottiene i byte del PDF (Drive o caricamento) e chiama `leggi_pdf()`, che restituisce un `DocumentoFIN` con le gare e le sole righe della societa'.
2. `fotografa()` legge in una volta lo stato del database che serve: atleti, alias, gare, personali, risultati gia' registrati per la stessa manifestazione, importazioni dello stesso file.
3. `analizza(documento, fotografia, decisioni)` produce l'anteprima. E' deterministica: a ogni modifica dell'utente (associazioni atleti, righe escluse o incluse) la pagina la ricalcola.
4. Alla conferma, `salva()` scrive in una sola transazione e poi rilegge quello che ha scritto.

Le decisioni dell'utente stanno in `st.session_state` (chiavi con prefisso `imp_`) e si azzerano con *Annulla* o dopo il salvataggio.

## Connessioni e cache

Ogni sessione utente ha la sua `Database` (i connettori MySQL non sono thread-safe). Le letture delle pagine sono cachate per 60 secondi con `st.cache_data`; ogni scrittura svuota la cache. L'anteprima dell'importazione legge sempre dal database senza cache.
