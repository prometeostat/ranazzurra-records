# Database

MySQL 8.4 su Aiven: progetto `swim-project`, servizio `record-societari`, database `defaultdb`, piano free (1 GB). Connessione TLS con la CA in `ca.pem`.

Lo `sql_mode` del servizio e' `ANSI,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,NO_ZERO_DATE,NO_ZERO_IN_DATE,STRICT_ALL_TABLES`. `ANSI` comprende `ANSI_QUOTES` (le stringhe vanno tra apici singoli, `"x"` e' un identificatore) e `ONLY_FULL_GROUP_BY`.

## Tabelle

### Schema base (`db/schema_base.sql`)

| Tabella | Contenuto | Note |
|---|---|---|
| `atleti` | cognome, nome, sesso (M/F), anno_nascita, attivo, note | unico su (cognome, nome, anno_nascita) |
| `tipi_vasca` | VC (25 m), VL (50 m) | |
| `stili_nuoto` | SL, DO, RA, DF, MX | a video DF e' "Delfino" |
| `distanze` | 50, 100, 200, 400, 800, 1500 | |
| `gare` | combinazioni stile + distanza (18) | `codice_gara` tipo `50_DF` |
| `record_personali` | **il personale**: una riga per atleta + gara + vasca | unico su (atleta_id, gara_id, tipo_vasca_id); `tempo_secondi DECIMAL(10,2)`, `tempo_formattato`, data, luogo, manifestazione |
| `record_societari` | *dismessa* | non piu' usata dall'app (ADR-002) |

Viste `v_record_personali`, `v_record_societari`; funzioni `secondi_to_tempo`, `tempo_to_secondi`; procedura `aggiorna_record_societari` (*dismessa*: con `ONLY_FULL_GROUP_BY` va in errore 1055, verificato su MySQL con lo stesso `sql_mode`).

### Migrazione 001 (`db/migrations/001_risultati_importazioni.sql`)

| Tabella | Contenuto | Vincoli principali |
|---|---|---|
| `schema_migrazioni` | versioni applicate | chiave `versione` |
| `manifestazioni` | nome, date, luogo, vasca, fonte | unico su (nome, data_inizio) |
| `importazioni` | una riga per conferma: SHA-256 del file, nome, id Drive, utente, conteggi, `riepilogo` JSON | indice su sha e id Drive |
| `risultati` | **tutte** le prestazioni importate: atleta, gara, vasca, manifestazione, turno, data, tempo, stato, posizione, cronometraggio, titolo gara, pagina PDF, esito, importazione | unico su (manifestazione, atleta, gara, vasca, turno); CHECK su stato (OK, SQ, RIT, NP, NC), su tempo coerente con lo stato, su cronometraggio (A, M); FK senza cascata verso `atleti` |
| `atleti_alias` | grafie del PDF confermate a mano | unico su (alias_normalizzato, anno_nascita) |

Colonna aggiunta: `record_personali.risultato_id` (facoltativa, FK verso `risultati`, `ON DELETE SET NULL`). Dice quale risultato importato ha prodotto il personale.

Tracciabilita' completa, dal personale al file:

```sql
SELECT a.cognome, a.nome, g.descrizione, rp.tempo_formattato,
       m.nome AS manifestazione, i.file_nome, i.created_at, i.utente
FROM record_personali rp
JOIN atleti a ON a.id = rp.atleta_id
JOIN gare g ON g.id = rp.gara_id
JOIN risultati r ON r.id = rp.risultato_id
JOIN manifestazioni m ON m.id = r.manifestazione_id
JOIN importazioni i ON i.id = r.importazione_id;
```

## Migrazioni

Regole: una migrazione per file, numerata (`002_...sql`), solo aggiunte, rieseguibile (`IF NOT EXISTS`, controlli su `information_schema`), niente `DELIMITER` (il runner divide le istruzioni sul punto e virgola), registrazione finale in `schema_migrazioni`.

```bash
python -m ranazzurra_records.migrazioni            # stato
python -m ranazzurra_records.migrazioni --applica  # backup JSON in backup/ + migrazioni mancanti
```

Il runner salva prima `atleti`, `record_personali` e `record_societari` in `backup/backup_AAAAMMGG_hhmmss.json` (cartella ignorata da git: contiene dati personali) e alla fine controlla che i conteggi di quelle tabelle non siano cambiati. In alternativa il file SQL si puo' eseguire intero da MySQL Workbench.

L'app funziona anche senza la migrazione 001: manca solo la pagina di importazione, che lo segnala.

## Backup e ripristino

Aiven fa un backup giornaliero (alle 02:11 UTC). Prima di operazioni delicate conviene comunque il backup JSON del runner o un dump da MySQL Workbench. `db/schema_base.sql` ricrea lo schema da zero con `DROP TABLE`: solo per database di sviluppo.

Il 9/11/2026 il servizio e' stato trovato spento (stato `POWEROFF` dal 21/10, ultimo backup lo stesso giorno). Sul piano free puo' capitare: si riaccende dalla console Aiven e i dati restano.
