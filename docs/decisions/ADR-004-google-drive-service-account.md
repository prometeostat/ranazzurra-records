# ADR-004 · Google Drive con service account in sola lettura

Stato: accettata, 09/11/2026.

## Contesto

I PDF dei risultati stanno in Google Drive. Scaricarli e ricaricarli nell'app e' un passaggio manuale da eliminare. Le opzioni: OAuth 2.0 per utente oppure service account.

## Decisione

Service account con scope `drive.readonly`, cartella dedicata condivisa con il service account come Visualizzatore, chiave nei secrets (`[gdrive.service_account]`). Chiamate all'API REST v3 con `google-auth` (`AuthorizedSession`), senza `google-api-python-client`.

## Motivazioni

- Un flusso OAuth dentro Streamlit richiede redirect, gestione e rinnovo dei token per sessione: complessita' sproporzionata per un'app usata da una o due persone.
- Il service account vede solo le cartelle condivise con lui e non puo' scrivere.
- `google-auth` e' leggero; `requests` c'e' gia' con Streamlit.

## Conseguenze

- Configurazione una tantum su Google Cloud (docs/google-drive-integration.md).
- Senza configurazione l'app ripiega sul caricamento manuale del PDF.
- La chiave JSON e' una credenziale: solo nei secrets, mai nel repository ne' in Drive.
