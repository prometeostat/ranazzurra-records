"""Letture e scritture sul database, senza Streamlit.

Le funzioni ricevono una :class:`~ranazzurra_records.db.Database` e
restituiscono strutture Python semplici (liste di dict o DataFrame), cosi' le
usano allo stesso modo l'app, gli script e i test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import queries as Q
from . import tempi
from .db import Database
from .records import chiave_ordinamento_gara


@dataclass
class EsitoScrittura:
    ok: bool
    messaggio: str


# --------------------------------------------------------------------- #
# Anagrafiche di base
# --------------------------------------------------------------------- #
def gare(db: Database) -> list[dict]:
    righe = db.query(Q.GARE)
    return sorted(righe, key=lambda g: chiave_ordinamento_gara(g["stile"], g["distanza"]))


def tipi_vasca(db: Database) -> dict[str, int]:
    return {r["codice"]: r["id"] for r in db.query(Q.TIPI_VASCA)}


def migrazione_001_applicata(db: Database) -> bool:
    return all(
        db.tabella_esiste(t) for t in ("manifestazioni", "importazioni", "risultati", "atleti_alias")
    )


# --------------------------------------------------------------------- #
# Atleti
# --------------------------------------------------------------------- #
def atleti(db: Database, solo_attivi: bool = False) -> pd.DataFrame:
    where = "WHERE attivo = TRUE" if solo_attivi else ""
    df = pd.DataFrame(db.query(Q.ATLETI.format(where=where)))
    if df.empty:
        return pd.DataFrame(columns=["id", "cognome", "nome", "sesso", "anno_nascita", "attivo", "note"])
    df["attivo"] = df["attivo"].astype(bool)
    return df


def etichetta_atleta(r) -> str:
    anno = r.get("anno_nascita") if isinstance(r, dict) else r["anno_nascita"]
    anno_txt = f" ({int(anno)})" if anno is not None and not pd.isna(anno) else ""
    return f"{r['cognome']} {r['nome']}{anno_txt}"


def inserisci_atleta(db: Database, cognome: str, nome: str, sesso: str,
                     anno_nascita: int | None, note: str = "") -> EsitoScrittura:
    import mysql.connector

    try:
        db.esegui(Q.ATLETA_INSERT, (cognome, nome, sesso, anno_nascita, note or None))
        return EsitoScrittura(True, "✅ Atleta inserito.")
    except mysql.connector.IntegrityError:
        return EsitoScrittura(False, "❌ Esiste gia' un atleta con stesso cognome, nome e anno di nascita.")


def aggiorna_atleta(db: Database, atleta_id: int, cognome: str, nome: str, sesso: str,
                    anno_nascita: int | None, attivo: bool, note: str) -> EsitoScrittura:
    import mysql.connector

    try:
        db.esegui(Q.ATLETA_UPDATE, (cognome, nome, sesso, anno_nascita, attivo, note or None, atleta_id))
        return EsitoScrittura(True, "✅ Atleta aggiornato.")
    except mysql.connector.IntegrityError:
        return EsitoScrittura(False, "❌ Esiste gia' un altro atleta con stesso cognome, nome e anno di nascita.")


def disattiva_atleta(db: Database, atleta_id: int) -> EsitoScrittura:
    db.esegui(Q.ATLETA_DISATTIVA, (atleta_id,))
    return EsitoScrittura(True, "✅ Atleta disattivato: i suoi tempi restano nello storico.")


def conta_personali(db: Database, atleta_id: int) -> int:
    return int(db.query_uno(Q.ATLETA_CONTA_RECORD, (atleta_id,))["n"])


def elimina_atleta_senza_tempi(db: Database, atleta_id: int) -> EsitoScrittura:
    """Cancellazione fisica ammessa solo per anagrafiche senza tempi (per
    esempio un doppione inserito per errore). Con dei tempi si disattiva."""
    if conta_personali(db, atleta_id):
        return EsitoScrittura(False, "❌ L'atleta ha dei tempi registrati: si puo' solo disattivare.")
    if db.tabella_esiste("risultati"):
        n = db.query_uno("SELECT COUNT(*) AS n FROM risultati WHERE atleta_id = %s", (atleta_id,))["n"]
        if n:
            return EsitoScrittura(False, "❌ L'atleta ha risultati importati: si puo' solo disattivare.")
    db.esegui(Q.ATLETA_DELETE, (atleta_id,))
    return EsitoScrittura(True, "✅ Anagrafica eliminata.")


# --------------------------------------------------------------------- #
# Personali
# --------------------------------------------------------------------- #
def personali(db: Database, atleta_id: int | None = None) -> pd.DataFrame:
    if atleta_id is None:
        righe = db.query(Q.PERSONALI.format(where=""))
    else:
        righe = db.query(Q.PERSONALI.format(where="WHERE rp.atleta_id = %s"), (int(atleta_id),))
    return pd.DataFrame(righe)


def salva_personale_manuale(
    db: Database,
    atleta_id: int,
    gara_id: int,
    codice_vasca: str,
    tempo_testo: str,
    data_record: date | None,
    luogo: str = "",
    manifestazione: str = "",
    note: str = "",
    sovrascrivi_peggiore: bool = False,
) -> EsitoScrittura:
    """Inserisce un personale, oppure lo migliora se esiste gia'.

    Un tempo **piu' lento** del personale esistente non lo sostituisce, a
    meno di ``sovrascrivi_peggiore=True`` (correzione esplicita di un errore).
    """
    try:
        cent = tempi.parse_tempo(tempo_testo)
    except tempi.TempoNonValido as e:
        return EsitoScrittura(False, f"❌ {e}. Usa M:SS.CC, per esempio 1:05.32 o 0:29.87.")
    vasche = tipi_vasca(db)
    if codice_vasca not in vasche:
        return EsitoScrittura(False, "❌ Tipo vasca non valido.")
    tv = vasche[codice_vasca]
    with db.transazione() as cur:
        cur.execute(Q.PERSONALE_DI_PER_UPDATE, (atleta_id, gara_id, tv))
        esistente = cur.fetchone()
        valori = (tempi.a_decimal(cent), tempi.formatta(cent), data_record,
                  luogo or None, manifestazione or None, note or None)
        if esistente is None:
            cur.execute(Q.PERSONALE_INSERT, (atleta_id, gara_id, tv) + valori)
            return EsitoScrittura(True, f"✅ Personale registrato: {tempi.formatta(cent)}.")
        prec = tempi.da_db(esistente["tempo_secondi"])
        if cent >= prec and not sovrascrivi_peggiore:
            return EsitoScrittura(
                False,
                f"⚠️ Il tempo {tempi.formatta(cent)} non migliora il personale esistente "
                f"({tempi.formatta(prec)}): nessuna modifica. Se il personale registrato e' "
                "sbagliato, correggilo dalla scheda Modifica.",
            )
        cur.execute(Q.PERSONALE_UPDATE, valori + (esistente["id"],))
    return EsitoScrittura(
        True, f"✅ Personale aggiornato: {tempi.formatta(prec)} → {tempi.formatta(cent)}."
    )


def correggi_personale(db: Database, personale_id: int, tempo_testo: str, data_record: date | None,
                       luogo: str, manifestazione: str, note: str) -> EsitoScrittura:
    """Correzione esplicita di un personale (anche verso un tempo peggiore)."""
    try:
        cent = tempi.parse_tempo(tempo_testo)
    except tempi.TempoNonValido as e:
        return EsitoScrittura(False, f"❌ {e}.")
    db.esegui(Q.PERSONALE_UPDATE, (tempi.a_decimal(cent), tempi.formatta(cent), data_record,
                                   luogo or None, manifestazione or None, note or None, personale_id))
    return EsitoScrittura(True, "✅ Personale corretto.")


def elimina_personale(db: Database, personale_id: int) -> EsitoScrittura:
    db.esegui(Q.PERSONALE_DELETE, (personale_id,))
    return EsitoScrittura(True, "✅ Personale eliminato.")


# --------------------------------------------------------------------- #
# Classifiche
# --------------------------------------------------------------------- #
def top3(db: Database) -> pd.DataFrame:
    df = pd.DataFrame(db.query(Q.TOP3))
    if df.empty:
        return df
    df["posizione"] = df["posizione"].astype(int)
    return df


def conteggi(db: Database) -> dict:
    return db.query_uno(Q.CONTEGGI)


def progressione(db: Database, gara_id: int, tipo_vasca_id: int) -> pd.DataFrame:
    righe = db.query(Q.PROGRESSIONE_PERSONALI, (gara_id, tipo_vasca_id))
    if db.tabella_esiste("risultati"):
        righe += db.query(Q.PROGRESSIONE_RISULTATI, (gara_id, tipo_vasca_id))
    df = pd.DataFrame(righe)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    df["centesimi"] = df["tempo_secondi"].map(tempi.da_db)
    return df.drop_duplicates(subset=["data", "centesimi", "atleta"]).sort_values("data")


def ultimi_personali(db: Database, quanti: int = 10) -> pd.DataFrame:
    return pd.DataFrame(db.query(Q.ULTIMI_PERSONALI, (int(quanti),)))


def importazioni(db: Database, quante: int = 20) -> pd.DataFrame:
    if not db.tabella_esiste("importazioni"):
        return pd.DataFrame()
    return pd.DataFrame(db.query(Q.IMPORTAZIONI_ELENCO, (int(quante),)))
