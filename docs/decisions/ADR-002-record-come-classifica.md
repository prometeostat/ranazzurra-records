# ADR-002 · I record societari sono una classifica calcolata, non una tabella

Stato: accettata, 09/11/2026.

## Contesto

Esistevano due nozioni di record: la tabella `record_societari` (un record per gara, vasca e categoria M/F/ASSOLUTO, alimentata dalla procedura `aggiorna_record_societari`) usata dalla dashboard, e la top 3 calcolata dai personali con `DENSE_RANK` usata dal sito. La procedura raggruppa per gara e vasca selezionando `atleta_id` non aggregato (atleta arbitrario, data del personale piu' recente) e, con lo `sql_mode` di Aiven che include `ONLY_FULL_GROUP_BY`, va in errore 1055 a ogni chiamata (verificato su MySQL 8 con lo stesso `sql_mode`). L'app la chiamava dopo ogni salvataggio: il personale veniva salvato e l'utente vedeva comunque un errore.

## Decisione

L'unica definizione di record e' la top 3 per gara + vasca + sesso calcolata con `DENSE_RANK` dai personali (`queries.CLASSIFICA`), uguale per app e sito. La tabella e la procedura non vengono piu' usate ne' chiamate; restano nel database finche' una migrazione esplicita non le rimuove.

## Conseguenze

- Nessuna tabella derivata da tenere allineata: il record cambia quando cambia un personale.
- Gli ex aequo condividono la posizione; la pagina del sito deve usare `filter()`.
- Il record 1° posto della dashboard e' la stessa riga del sito.
