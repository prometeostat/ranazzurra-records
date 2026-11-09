"""Scrittura di un'importazione confermata, in un'unica transazione.

Scrive solo le righe che l'analisi ha dichiarato importabili e che l'utente
ha lasciato selezionate. Ordine: manifestazione, importazione, atleti nuovi,
alias, risultati, personali migliorati, riepilogo. Qualunque errore annulla
tutto. Dopo il commit rilegge dal database quello che ha scritto.

Idempotenza: la chiave unica di ``risultati`` (manifestazione, atleta, gara,
vasca, turno) impedisce di registrare due volte la stessa prestazione; un
personale si aggiorna solo con un tempo strettamente migliore di quello che
c'e' a database in quel momento (letto con ``SELECT ... FOR UPDATE``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import mysql.connector

from .. import queries as Q
from .. import tempi
from ..db import Database
from ..records import Esito
from .analisi import IMPORTABILE, Analisi, chiave_atleta
from .matching import chiave_token

log = logging.getLogger(__name__)


class ImportazioneNonValida(RuntimeError):
    pass


@dataclass
class EsitoImportazione:
    importazione_id: int
    manifestazione_id: int
    risultati_inseriti: int
    risultati_gia_presenti: int
    personali_aggiornati: int
    atleti_creati: int
    alias_salvati: int
    verifiche: list[str] = field(default_factory=list)


def salva(db: Database, an: Analisi, file_nome: str, utente: str | None = None,
          drive_file_id: str | None = None) -> EsitoImportazione:
    righe = an.selezionate()
    if not righe:
        raise ImportazioneNonValida("Nessuna riga selezionata da importare.")
    if any(r.stato != IMPORTABILE or r.atleta_id is None for r in righe):
        raise ImportazioneNonValida("Ci sono righe selezionate non importabili: ricalcola l'anteprima.")
    doc = an.doc
    dec = an.decisioni

    with db.transazione() as cur:
        # 1. manifestazione
        cur.execute(Q.MANIFESTAZIONE_CERCA + " FOR UPDATE", (doc.nome, doc.data_inizio))
        m = cur.fetchone()
        if m:
            manif_id = m["id"]
        else:
            vasche = {r.vasca_id for r in righe}
            cur.execute(Q.MANIFESTAZIONE_INSERT, (
                doc.nome, doc.data_inizio, doc.data_fine if doc.data_fine != doc.data_inizio else None,
                doc.luogo, vasche.pop() if len(vasche) == 1 else None, "PDF FIN"))
            manif_id = cur.lastrowid

        # 2. importazione
        cur.execute(Q.IMPORTAZIONE_INSERT, (doc.sha256, file_nome[:255], drive_file_id, manif_id,
                                            utente, doc.righe_totali, len(doc.righe_nostre)))
        imp_id = cur.lastrowid

        # 3. atleti nuovi (id temporanei negativi -> id veri)
        veri: dict[int, int] = {}
        creati = 0
        for r in righe:
            if r.atleta_id < 0 and r.atleta_id not in veri:
                n = dec.nuovi[chiave_atleta(r.riga)]
                try:
                    cur.execute(Q.ATLETA_INSERT, (n.cognome.strip(), n.nome.strip(), n.sesso,
                                                  int(n.anno_nascita), f"Creato dall'importazione #{imp_id}"))
                except mysql.connector.IntegrityError as e:
                    raise ImportazioneNonValida(
                        f"L'atleta {n.cognome} {n.nome} ({n.anno_nascita}) esiste gia' in anagrafica: "
                        "associalo invece di crearlo.") from e
                veri[r.atleta_id] = cur.lastrowid
                creati += 1

        def vero(aid: int) -> int:
            return veri.get(aid, aid)

        # 4. alias confermati a mano
        alias = 0
        for k in dec.ricorda:
            scelta = dec.associazioni.get(k)
            r = next((x for x in righe if chiave_atleta(x.riga) == k), None)
            if r is None or not isinstance(scelta, int):
                continue
            cur.execute(Q.ALIAS_INSERT, (chiave_token(r.riga.nome), r.riga.anno, scelta,
                                         f"importazione #{imp_id}"))
            alias += cur.rowcount > 0

        # 5. risultati
        inseriti, presenti = 0, 0
        id_risultato: dict[str, int] = {}
        for r in righe:
            t = r.riga.tempo if r.riga.stato == "OK" else None
            cur.execute(Q.RISULTATO_ESISTE, (manif_id, vero(r.atleta_id), r.gara_id, r.vasca_id, r.gara.turno))
            if cur.fetchone():
                presenti += 1
                continue
            cur.execute(Q.RISULTATO_INSERT, (
                vero(r.atleta_id), r.gara_id, r.vasca_id, manif_id, r.gara.turno, r.data_gara,
                tempi.a_decimal(t) if t is not None else None, tempi.formatta(t) if t is not None else None,
                r.riga.stato, r.riga.posizione, r.gara.cronometraggio, r.gara.titolo[:255],
                r.riga.pagina, r.esito.value if r.esito else None, imp_id))
            inseriti += 1
            id_risultato[r.chiave] = cur.lastrowid

        # 6. personali: solo tempi strettamente migliori di quelli a DB
        aggiornati = 0
        for r in righe:
            if not (r.esito and r.esito.aggiorna_pb) or r.chiave not in id_risultato:
                continue
            aid, t = vero(r.atleta_id), r.riga.tempo
            cur.execute(Q.PERSONALE_DI_PER_UPDATE, (aid, r.gara_id, r.vasca_id))
            pb = cur.fetchone()
            valori = (tempi.a_decimal(t), tempi.formatta(t), r.data_gara, r.gara.luogo or doc.luogo, doc.nome)
            if pb is None:
                cur.execute(Q.PERSONALE_INSERT, (aid, r.gara_id, r.vasca_id) + valori + (None,))
                pb_id = cur.lastrowid
            elif t < tempi.da_db(pb["tempo_secondi"]):
                cur.execute("UPDATE record_personali SET tempo_secondi = %s, tempo_formattato = %s, "
                            "data_record = %s, luogo = %s, manifestazione = %s WHERE id = %s",
                            valori + (pb["id"],))
                pb_id = pb["id"]
            else:
                continue  # nel frattempo a DB e' arrivato un tempo uguale o migliore
            cur.execute(Q.PERSONALE_COLLEGA_RISULTATO, (id_risultato[r.chiave], pb_id))
            aggiornati += 1

        # 7. riepilogo
        riepilogo = {
            "manifestazione": doc.nome, "data": str(doc.data_inizio), "luogo": doc.luogo,
            "esiti": {e.value: len([r for r in righe if r.esito == e]) for e in Esito},
            "righe": [{"atleta": vero(r.atleta_id), "gara_id": r.gara_id, "vasca": r.vasca,
                       "tempo": tempi.formatta(r.riga.tempo) if r.riga.tempo else r.riga.stato,
                       "esito": r.esito.value if r.esito else None, "avvisi": r.avvisi}
                      for r in righe],
            "escluse": [r.chiave for r in an.righe if r.stato == IMPORTABILE and not r.selezionata],
            "anomalie_pdf": doc.anomalie,
        }
        cur.execute(Q.IMPORTAZIONE_CHIUDI, (inseriti, aggiornati, creati,
                                            json.dumps(riepilogo, ensure_ascii=False, default=str), imp_id))

    esito = EsitoImportazione(imp_id, manif_id, inseriti, presenti, aggiornati, creati, int(alias))
    esito.verifiche = verifica(db, esito)
    log.info("Importazione #%s: %s risultati, %s personali, %s atleti nuovi",
             imp_id, inseriti, aggiornati, creati)
    return esito


def verifica(db: Database, e: EsitoImportazione) -> list[str]:
    """Rilettura dopo il commit: quello che l'importazione dice di aver
    scritto deve esserci davvero."""
    out = []
    n = db.query_uno("SELECT COUNT(*) AS n FROM risultati WHERE importazione_id = %s", (e.importazione_id,))["n"]
    out.append(("✓" if n == e.risultati_inseriti else "✗") + f" risultati a database per l'importazione: {n}")
    p = db.query_uno("SELECT COUNT(*) AS n FROM record_personali rp JOIN risultati r ON rp.risultato_id = r.id "
                     "WHERE r.importazione_id = %s", (e.importazione_id,))["n"]
    out.append(("✓" if p == e.personali_aggiornati else "✗") + f" personali collegati all'importazione: {p}")
    d = db.query_uno("SELECT COUNT(*) AS n FROM (SELECT manifestazione_id, atleta_id, gara_id, tipo_vasca_id, turno, "
                     "COUNT(*) c FROM risultati WHERE manifestazione_id = %s GROUP BY manifestazione_id, atleta_id, "
                     "gara_id, tipo_vasca_id, turno HAVING COUNT(*) > 1) x", (e.manifestazione_id,))["n"]
    out.append(("✓" if d == 0 else "✗") + f" prestazioni doppie nella manifestazione: {d}")
    return out
