# ADR-003 · Importazione dei risultati FIN

Stato: accettata, 09/11/2026.

## Contesto

I risultati delle gare arrivano come PDF del portale FIN. Prima venivano riportati a mano. Il database aveva solo i personali (una riga per atleta, gara e vasca) senza storico, quindi non si poteva sapere da quale gara venisse un tempo ne' evitare di registrare due volte la stessa prestazione.

Il progetto Master Conegliano (`prometeostat/ranazzurra_streamlit`, altro database, altri atleti) ha un parser dei riepiloghi FIN validato su decine di manifestazioni.

## Decisione

- **Parser**: adattato e copiato da quello del progetto Master, senza dipendenze dal suo database ne' interazioni a terminale. Nessun pacchetto condiviso fra i due repository: i due progetti hanno cicli di vita diversi e il parser e' un modulo di poche centinaia di righe.
- **Niente OCR**: i PDF del portale hanno il testo. Un PDF scansionato viene rifiutato con un messaggio. Evita dipendenze di sistema (tesseract) che Streamlit Cloud non ha.
- **Storico**: tabelle `manifestazioni`, `importazioni`, `risultati`, `atleti_alias` (migrazione 001). `record_personali` resta la fonte dei record e si aggiorna solo con tempi strettamente migliori, con `risultato_id` per la tracciabilita'.
- **Riconoscimento atleti** con la sola libreria standard (`unicodedata`, `difflib`): automatico solo con nome e anno identici, il resto su conferma.
- **Anteprima obbligatoria**: niente viene scritto prima della conferma; la scrittura e' un'unica transazione.
- **Idempotenza** sulla prestazione, non sul file: chiave unica (manifestazione, atleta, gara, vasca, turno). Lo stesso PDF si puo' rielaborare (per aggiungere righe escluse la prima volta) senza duplicati.
- **Societa'**: solo RANAZZURRA CONEGLIANO; staffette ignorate.

## Conseguenze

- Una dipendenza nuova: `pdfplumber`.
- Le regole del parser vanno tenute a mano allineate con quelle del Master se emergono layout nuovi; ogni correzione porta un test.
- I tempi a cronometraggio manuale entrano solo se l'utente li include (regola definitiva ancora da decidere).
