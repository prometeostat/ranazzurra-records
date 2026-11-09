# Personali e record societari

## Definizioni

**Personale (PB).** Il miglior tempo di un atleta per una gara (stile + distanza) in una vasca. Sta in `record_personali`, una riga per combinazione.

**Record societari.** I primi 3 tempi della societa' per gara + vasca + sesso, calcolati dai personali con `DENSE_RANK`: gli ex aequo condividono la posizione e la successiva scala di uno (1, 2, 2, 3). Con gli ex aequo le righe possono essere piu' di tre. E' la classifica della pagina *Record Top 3*, della dashboard e del sito (`queries.CLASSIFICA`, `queries.TOP3`). Non ci sono categorie d'eta': i record sono assoluti.

Il sesso viene sempre dall'anagrafica dell'atleta, non dal titolo della gara.

## Ordine delle gare

Ovunque (app e sito): stile Delfino, Dorso, Rana, Stile Libero, Misti; dentro lo stile per distanza (`records.chiave_ordinamento_gara`).

## Inserimento manuale

- Un tempo nuovo crea il personale se non c'e', lo migliora se e' **strettamente** piu' veloce.
- Un tempo piu' lento o uguale non cambia niente e l'app lo dice. Per correggere un personale sbagliato si usa la scheda *Modifica* (correzione esplicita) oppure la casella "Correzione" nell'inserimento.
- Un atleta con tempi registrati si puo' solo disattivare. Si cancella fisicamente solo un'anagrafica senza tempi (doppione).
- Formato dei tempi: `M:SS.CC` (anche `SS.CC` sotto il minuto, `H:MM:SS.CC` sopra l'ora); con i minuti i secondi vanno scritti con due cifre.

## Esiti di un risultato importato

Ogni risultato si confronta con i personali di quella gara + vasca + sesso. Dentro la stessa importazione i risultati si valutano dal piu' veloce al piu' lento e ogni miglioramento entra subito nella classifica di lavoro: se due atleti battono lo stesso record, il primo e' "nuovo record" e il secondo entra in top 3; se lo stesso atleta ha due tempi (batterie e finale) conta il migliore.

| Esito | Quando | Aggiorna il personale |
|---|---|---|
| Nuovo record societario | tempo piu' veloce del 1° tempo della societa', o gara senza tempi | si' |
| Record societario eguagliato | tempo pari al 1° tempo | si' (se migliora il PB) |
| Record societari migliorati (top 3) | l'atleta entra in top 3 o vi migliora il suo tempo, senza diventare 1° | si' |
| Nuovo primato personale | migliora il PB senza toccare la top 3 | si' |
| Primo tempo registrato | l'atleta non aveva un personale su quella gara, fuori top 3 | si' (lo crea) |
| Nessun miglioramento | tempo uguale o piu' lento del PB | no |
| Senza tempo valido | SQ, RIT, NP, NC: entra solo nello storico | no |

Nell'anteprima, per ogni record o personale migliorato si vedono tempo precedente (il record per gli esiti di record, altrimenti il PB), nuovo tempo, differenza in secondi, posizione in top 3 prima e dopo, manifestazione.

## Il JSON del sito

`export.costruisci_payload()` produce:

```json
{
  "vasca_lunga": [{"gara": "50m Delfino", "distanza": 50, "stile": "DF",
                   "maschile": [{"posizione": 1, "cognome": "...", "nome": "...", "anno_nascita": 2007,
                                 "tempo": "0:25.58", "data": "13/06/2026", "luogo": "Verona",
                                 "manifestazione": ""}],
                   "femminile": []}],
  "vasca_corta": [],
  "aggiornato": "09/11/2026 12:00"
}
```

Il formato non va cambiato senza aggiornare `record_societari.html`. La pagina deve leggere le posizioni con `filter()` (piu' atleti nella stessa posizione), non con `find()`.
