# Stato del progetto

Contesto operativo per riprendere il lavoro. Si aggiorna quando cambia lo stato, non a ogni sessione. Le decisioni definitive stanno negli ADR (`docs/decisions/`).

Ultimo aggiornamento: 09/11/2026, versione 2.0.0 (branch `evoluzione/import-fin`, pull request verso `main`).

## Funzionalita' presenti

- Dashboard, Record Top 3 (DENSE_RANK, ex aequo, download di `records.json`), gestione atleti e personali con le protezioni sui dati.
- Importazione dei risultati FIN da PDF, con riconoscimento atleti, confronto con lo storico, anteprima, conferma, idempotenza e storico delle importazioni.
- Lettura dei PDF da Google Drive con service account (da configurare, vedi sotto).
- `esporta_records.py` con credenziali dai secrets e FTP su TLS.
- Migrazioni controllate con backup; 99 test automatici.

Provato su: PDF reale "1a Giornata Attivita' di Categoria Venezia" (Mestre, 08/11/2026): 15 gare, 360 righe, 60 prestazioni RANAZZURRA CONEGLIANO SSD lette tutte, nessuna anomalia. Importazione completa provata su un MySQL locale con lo stesso `sql_mode` di Aiven, ricostruito dall'Excel originale e dal `records.json` del sito.

## Da fare per il rilascio

1. Rotazione delle password MySQL e FTP finite nella storia del repository pubblico (in carico a Mirko), aggiornamento dei secrets.
2. Migrazione 001 sul database Aiven.
3. Merge della pull request e Reboot dell'app.
4. Configurazione Google Drive: progetto Google Cloud, service account, sottocartella dei PDF (proposta: `ranazzurra/record_societari/risultati_fin`), secrets `[gdrive]`.
5. Controllare che sul sito sia pubblicata la versione di `record_societari.html` della cartella del sito su Drive, che legge le posizioni con `filter()` e impila gli ex aequo (VL 50 rana M: Foscan Riccardo e Pasquali Andrea a 0:30.56). La copia del file nel progetto Claude e' piu' vecchia e usa ancora `find()`: non va ripubblicata.

## Problemi noti e decisioni aperte

- **Allineamento DB / sito.** Il `records.json` pubblicato (21/08/2026) e quello nel repository (17/06/2026) differivano in 9 righe di vasca lunga. Va confrontato l'export dal database con il file pubblicato prima della prossima pubblicazione.
- **Date segnaposto.** Dieci record hanno date inventate (01/01/xxxx) e luogo vuoto; uno non ha data. Servono gli archivi FIN. Dettaglio nella nota di progetto `decisioni-aperte-record.md` (21/08/2026).
- **Tempi a cronometraggio manuale.** Nella nota del 21/08 era aperta la regola (accettarli, escluderli o maggiorarli). Oggi l'importatore legge `Cron: M`, li segnala e li lascia senza spunta: entrano solo se l'utente li include.
- **Accesso all'app.** Non c'e' un login: se l'app e' pubblica chiunque abbia l'URL puo' scrivere. Opzioni: app privata su Community Cloud con viewer autorizzati, oppure un'autenticazione.
- **Oggetti dismessi.** Tabella `record_societari`, viste e procedura `aggiorna_record_societari` restano nel database ma non sono usati (ADR-002); si possono eliminare con una migrazione quando si vuole.
- **Repository.** Le password erano nella storia di git; dopo la rotazione non servono piu' a nessuno, quindi ripulire la storia e' facoltativo.

## Prossimi sviluppi possibili

- Pubblicazione di `records.json` direttamente dall'app dopo un'importazione.
- Pagina di progressione per atleta usando lo storico `risultati`.
- Import storico dei PDF delle stagioni passate (stessa procedura, un PDF alla volta).
