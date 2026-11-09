# ADR-001 · Refactoring incrementale su Streamlit e MySQL

Stato: accettata, 09/11/2026.

## Contesto

L'app era un unico file di 1360 righe con interfaccia, SQL e logica mescolati, credenziali in chiaro in quattro script di un repository pubblico, conversione dei tempi duplicata e su float. Funzionava ed era usata.

## Decisione

Restano Streamlit, Streamlit Community Cloud, MySQL su Aiven e il sito statico con `records.json`. Il codice viene diviso nel pacchetto `ranazzurra_records` (dominio senza Streamlit, pagine in `views/`), le credenziali passano a secrets e variabili d'ambiente, i tempi diventano centesimi interi. Nessuna riscrittura da zero; il formato di `records.json` non cambia.

## Conseguenze

- Le regole sui record si provano con `pytest` senza database.
- Gli script locali (`esporta_records.py`, migrazioni) leggono lo stesso `.streamlit/secrets.toml` dell'app.
- Rimossi `calcola_record*.py` (chiamavano una procedura che fallisce), `import_excel_mysql.py` (import iniziale una tantum, con credenziali), `Record_Societari.xlsx` (dati personali, anche di minori) e `records.json` (file generato). Restano nella storia di git e, l'Excel, in Drive.
