# Importazione dei risultati FIN

Pagina **📥 Importa risultati FIN**. Richiede la migrazione 001 (vedi [database.md](database.md)).

## Procedura

1. **Scegli il PDF.** Da Google Drive (elenco dei PDF della cartella configurata e delle sottocartelle, dal piu' recente; ✅ = gia' importato in passato) oppure caricandolo dal computer. Premi *Analizza il PDF*.
2. **Controlla il riepilogo.** Manifestazione, data, luogo, gare individuate, righe lette di tutte le societa', prestazioni Ranazzurra, atleti riconosciuti e da verificare. Se il file e' gia' stato importato compare un avviso. Le righe di altre societa' Ranazzurra (Spresiano, Lido) sono elencate ma non importate. Le righe del PDF con la nostra societa' che il parser non e' riuscito a leggere sono mostrate in evidenza: vanno controllate sul PDF.
3. **Risolvi gli atleti.** Nella tabella *Atleti* scegli per ognuno l'atleta dell'anagrafica, *Crea nuovo atleta* (cognome, nome e sesso modificabili) oppure *Escludi le sue righe*, poi *Applica le scelte*. *Crea come nuovi tutti i 'non trovato'* fa la scelta per tutti gli atleti senza candidati. *Ricorda* salva la grafia del PDF come alias, cosi' la prossima volta l'associazione e' automatica. Anche le associazioni automatiche si possono correggere.
4. **Controlla i risultati.** Tabella con la spunta *Importa*: le righe con avvisi partono senza spunta e vanno incluse a mano se sono giuste. Sotto, le righe che non verranno importate con il motivo (gia' presenti, non valide, atleta non risolto, escluse).
5. **Controlla record e primati.** Tabelle dei nuovi record societari, dei record migliorati (top 3) e dei nuovi primati personali, con tempo precedente, nuovo tempo, differenza e manifestazione; nel riquadro *Top 3 prima e dopo* la classifica di ogni gara toccata.
6. **Conferma.** Spunta *Ho controllato l'anteprima* e premi *Conferma importazione*. Tutto avviene in una transazione: o si scrive tutto o niente. Dopo il salvataggio l'app rilegge dal database e mostra le verifiche. *Annulla* abbandona senza scrivere.
7. **Pubblica sul sito.** `python esporta_records.py`, oppure *Scarica records.json* dalla pagina Record Top 3 e caricalo via FTP.

La scheda *Storico importazioni* elenca le importazioni con file, utente, conteggi e il dettaglio delle prestazioni scritte.

## Che cosa legge il parser

PDF del portale FIN (finveneto.org) con intestazione `RISULTATI RIEPILOGATIVI` o `Risultati completi per Categoria`. Per ogni gara: titolo (stile, distanza, sesso se indicato, turno se c'e' "Finale"/"Batterie"), luogo e data dalla riga "Mestre , Domenica 08/11/2026", cronometraggio (`Cron: A` automatico, `M` manuale), vasca (`Base v.: 25/50`). Per ogni riga: posizione, atleta, anno, societa', tempo o stato (SQ, RIT, NP, NC, ASS), eventuale FG (fuori gara). Le pagine di continuazione ereditano la gara precedente. Le staffette sono ignorate.

Societa' importata: solo **RANAZZURRA CONEGLIANO** (anche con S.S.D., SSD a r.l., codice numerico davanti). Un PDF senza testo (scansione) viene rifiutato: l'OCR non e' supportato, serve il PDF originale.

Il parser e' adattato da quello del progetto Master (ADR-003). Se un layout nuovo non viene letto, le righe Ranazzurra non interpretate compaiono tra le anomalie: si corregge il parser e si aggiunge un test in `tests/test_parser.py`.

## Riconoscimento degli atleti

| Livello | Quando | Effetto |
|---|---|---|
| certo | nome identico (anche in ordine inverso, senza accenti e apostrofi) e stesso anno, un solo atleta, sesso compatibile; oppure alias confermato | associazione automatica |
| da confermare | nome simile (refuso), nome contenuto (doppio cognome o secondo nome), anno diverso o mancante in anagrafica, sesso diverso | serve la scelta dell'utente |
| omonimi | piu' atleti con stesso nome e anno | serve la scelta dell'utente |
| non trovato | nessun candidato credibile | crea o escludi |

Un nome solo simile con anno di nascita diverso non viene proposto come candidato (MERLO 2013 non e' Morello 2012), e un atleta gia' riconosciuto con certezza non viene proposto per un altro nome dello stesso PDF.

## Controlli e avvisi

Righe **non valide** (mai importate): assenti (ASS), gara non presente nell'anagrafica gare, vasca o data mancanti nel PDF, tempo illeggibile.

Righe **gia' presenti**: stessa manifestazione, atleta, gara, vasca e turno gia' registrati. Rielaborare lo stesso PDF non duplica niente.

Avvisi che **tolgono la spunta** (si importano solo se l'utente le include): tempo fuori dalla scala plausibile per la distanza, cronometraggio manuale, sesso della gara diverso da quello in anagrafica, stesso atleta due volte nella stessa gara.

Avvisi informativi: anno di nascita diverso tra PDF e anagrafica, atleta inattivo, nuotata fuori gara (FG), risultato senza tempo (entra solo nello storico).

## Cosa viene scritto

Una riga in `manifestazioni` (se non c'e' gia'), una in `importazioni`, gli atleti nuovi, gli alias richiesti, una riga in `risultati` per ogni prestazione selezionata e l'aggiornamento di `record_personali` solo dove il tempo e' strettamente migliore di quello presente in quel momento (letto con `SELECT ... FOR UPDATE`), con `risultato_id` per risalire al PDF.

## Errori

| Messaggio | Cosa fare |
|---|---|
| "Il PDF non contiene testo" | serve il PDF originale scaricato dal portale FIN |
| "Nel PDF non ho trovato gare" | non e' un riepilogo risultati (per esempio una start list) |
| "L'atleta ... esiste gia' in anagrafica" | nella tabella atleti associalo invece di crearlo |
| "Accesso negato da Google Drive" | vedi [google-drive-integration.md](google-drive-integration.md) |
| "Importazione annullata, nessun dato scritto" | errore del database durante la scrittura: la transazione e' stata annullata, si puo' riprovare |

Gli errori vanno anche nel log dell'app (Streamlit Cloud, *Manage app*).
