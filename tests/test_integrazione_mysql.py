"""Integrazione su un MySQL vero (usa-e-getta).

Parte solo con RANAZZURRA_TEST_MYSQL=1 e le variabili MYSQL_HOST, MYSQL_PORT,
MYSQL_USER, MYSQL_PASSWORD di un server di prova (l'utente deve poter creare
database). Crea ``ranazzurra_test`` da db/schema_base.sql, applica le
migrazioni, lo popola con dati sintetici e lo cancella alla fine.
MAI puntare queste variabili al database di produzione.
"""

from __future__ import annotations

import os
import re
from dataclasses import replace

import pytest

from conftest import RADICE, crea_pdf

pytestmark = pytest.mark.skipif(os.environ.get("RANAZZURRA_TEST_MYSQL") != "1",
                                reason="test MySQL disattivati (RANAZZURRA_TEST_MYSQL=1 per attivarli)")

NOME_DB = "ranazzurra_test"


def _istruzioni_schema() -> list[str]:
    sql = (RADICE / "db" / "schema_base.sql").read_text(encoding="utf-8")
    sql = re.sub(r"DELIMITER //.*?DELIMITER ;", "", sql, flags=re.S)  # funzioni e procedure dismesse
    sql = "\n".join(r for r in sql.splitlines() if not r.strip().startswith("--"))
    return [s.strip() for s in sql.split(";") if s.strip()]


@pytest.fixture(scope="module")
def db():
    import mysql.connector

    from ranazzurra_records import config, migrazioni
    from ranazzurra_records.db import Database

    base = config.ConfigMySQL(os.environ["MYSQL_HOST"], int(os.environ.get("MYSQL_PORT", 3306)), NOME_DB,
                              os.environ["MYSQL_USER"], os.environ["MYSQL_PASSWORD"])
    p = base.parametri_connessione()
    p.pop("database")
    c = mysql.connector.connect(**p)
    cur = c.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {NOME_DB}")
    cur.execute(f"CREATE DATABASE {NOME_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    d = Database(base)
    with d.cursore() as k:
        for s in _istruzioni_schema():
            k.execute(s)
            if k.with_rows:
                k.fetchall()
    for v, percorso in migrazioni.migrazioni_disponibili():
        migrazioni.applica(d, v, percorso)
    yield d
    d.chiudi()
    cur.execute(f"DROP DATABASE IF EXISTS {NOME_DB}")
    c.close()


@pytest.fixture(scope="module")
def dati(db):
    """Due atleti con personali in 50 dorso vasca lunga femminile."""
    from ranazzurra_records import repository as R

    R.inserisci_atleta(db, "Rossi", "Lucia", "F", 2012)
    R.inserisci_atleta(db, "Verdi", "Anna", "F", 2011)
    R.inserisci_atleta(db, "Blu", "Marco", "M", 2009)
    ids = {r["cognome"]: r["id"] for r in db.query("SELECT id, cognome FROM atleti")}
    gare = {(g["stile"], g["distanza"]): g["id"] for g in R.gare(db)}
    assert R.salva_personale_manuale(db, ids["Rossi"], gare[("DO", 50)], "VL", "0:32.50", None).ok
    assert R.salva_personale_manuale(db, ids["Verdi"], gare[("DO", 50)], "VL", "0:31.00", None).ok
    return ids, gare


def test_migrazioni_registrate_e_rieseguibili(db):
    from ranazzurra_records import migrazioni

    assert "001" in migrazioni.migrazioni_applicate(db)
    prima = migrazioni.conteggi(db)
    for v, p in migrazioni.migrazioni_disponibili():
        migrazioni.applica(db, v, p)          # seconda volta: nessun errore, nessun effetto
    assert migrazioni.conteggi(db) == prima


def test_personale_piu_lento_non_sovrascrive(db, dati):
    from ranazzurra_records import repository as R
    from ranazzurra_records import tempi

    ids, gare = dati
    e = R.salva_personale_manuale(db, ids["Verdi"], gare[("DO", 50)], "VL", "0:35.00", None)
    assert not e.ok
    pb = db.query_uno("SELECT tempo_secondi FROM record_personali WHERE atleta_id = %s", (ids["Verdi"],))
    assert tempi.da_db(pb["tempo_secondi"]) == 3100
    assert R.salva_personale_manuale(db, ids["Verdi"], gare[("DO", 50)], "VL", "0:35.00", None,
                                     sovrascrivi_peggiore=True).ok
    assert R.salva_personale_manuale(db, ids["Verdi"], gare[("DO", 50)], "VL", "0:31.00", None).ok


def test_atleta_con_tempi_non_si_cancella(db, dati):
    from ranazzurra_records import repository as R

    ids, _ = dati
    assert not R.elimina_atleta_senza_tempi(db, ids["Rossi"]).ok
    assert db.query_uno("SELECT COUNT(*) n FROM atleti WHERE id = %s", (ids["Rossi"],))["n"] == 1


PDF = [[
    "Meeting di prova Foglio n. 1", "08/11/2026", "RISULTATI RIEPILOGATIVI",
    "50 Dorso Serie Cat.: Assoluti Femmine Agonisti",
    "Treviso , Domenica 08/11/2026 ore 15:00",
    "Cron: A - Base v.: 50",
    "Pos Ser. Cor Atleta Anno Societa Tempo Pti",
    "1 1 4 ROSSI LUCIA 2012 RANAZZURRA CONEGLIANO SSD 00:30.80",
    "2 1 5 VERDI ANNA 2011 RANAZZURRA CONEGLIANO SSD 00:31.40",
    "3 1 6 NUOVA GIULIA 2013 RANAZZURRA CONEGLIANO SSD 00:33.10",
    "4 1 7 ALTRA SOFIA 2012 NUOTO VENEZIA SSD 00:33.50",
]]


def test_importazione_completa_e_idempotente(db, dati):
    from ranazzurra_records import repository as R
    from ranazzurra_records import tempi
    from ranazzurra_records.export import costruisci_payload, leggi_top3
    from ranazzurra_records.fin_pdf import leggi_pdf
    from ranazzurra_records.importazione.analisi import (GIA_PRESENTE, Decisioni, NuovoAtleta, analizza,
                                                         fotografa)
    from ranazzurra_records.importazione.salvataggio import ImportazioneNonValida, salva
    from ranazzurra_records.records import Esito

    ids, gare = dati
    doc = leggi_pdf(crea_pdf(PDF))
    an = analizza(doc, fotografa(db, doc))
    assert {r.riga.nome: r.esito for r in an.righe if r.esito} == {
        "ROSSI LUCIA": Esito.NUOVO_RECORD, "VERDI ANNA": Esito.NESSUNO}
    dec = Decisioni(associazioni={"NUOVA GIULIA|2013": "nuovo"},
                    nuovi={"NUOVA GIULIA|2013": NuovoAtleta("Nuova", "Giulia", "F", 2013)})
    an = analizza(doc, fotografa(db, doc), dec)
    assert len(an.selezionate()) == 3
    assert {r.riga.nome: r.esito for r in an.righe}["NUOVA GIULIA"] == Esito.TOP3

    e = salva(db, an, "prova.pdf", utente="test")
    assert (e.risultati_inseriti, e.personali_aggiornati, e.atleti_creati) == (3, 2, 1)
    assert all(v.startswith("✓") for v in e.verifiche)
    pb = {r["cognome"]: tempi.da_db(r["tempo_secondi"]) for r in R.personali(db).to_dict("records")}
    assert pb["Rossi"] == 3080 and pb["Verdi"] == 3100 and pb["Nuova"] == 3310

    # stesso PDF una seconda volta: tutto gia' presente, niente da scrivere
    an2 = analizza(doc, fotografa(db, doc))
    assert an2.gia_importato and {r.stato for r in an2.righe} == {GIA_PRESENTE}
    with pytest.raises(ImportazioneNonValida):
        salva(db, an2, "prova.pdf")
    assert db.query_uno("SELECT COUNT(*) n FROM risultati")["n"] == 3

    # tracciabilita': dal personale al PDF
    r = db.query_uno(
        "SELECT i.file_nome, m.nome FROM record_personali rp JOIN risultati r ON rp.risultato_id = r.id "
        "JOIN importazioni i ON r.importazione_id = i.id JOIN manifestazioni m ON r.manifestazione_id = m.id "
        "WHERE rp.atleta_id = %s", (ids["Rossi"],))
    assert r == {"file_nome": "prova.pdf", "nome": "Meeting di prova"}

    # il sito vede il nuovo record
    p = costruisci_payload(leggi_top3(db))
    dorso = next(g for g in p["vasca_lunga"] if g["gara"] == "50m Dorso")
    assert [(x["cognome"], x["tempo"]) for x in dorso["femminile"]] == \
        [("Rossi", "0:30.80"), ("Verdi", "0:31.00"), ("Nuova", "0:33.10")]


def test_errore_annulla_tutto(db, dati):
    """Se il salvataggio fallisce a meta', nessuna riga resta scritta."""
    from ranazzurra_records.fin_pdf import leggi_pdf
    from ranazzurra_records.importazione.analisi import Decisioni, NuovoAtleta, analizza, fotografa
    from ranazzurra_records.importazione.salvataggio import ImportazioneNonValida, salva

    pdf = [[r.replace("08/11/2026", "15/11/2026").replace("Meeting di prova", "Secondo meeting")
            .replace("00:30.80", "00:30.50") for r in PDF[0]]]
    doc = leggi_pdf(crea_pdf(pdf))
    # "crea" un atleta che esiste gia' -> errore di integrita' durante il salvataggio
    dec = Decisioni(associazioni={"ROSSI LUCIA|2012": "nuovo"},
                    nuovi={"ROSSI LUCIA|2012": NuovoAtleta("Rossi", "Lucia", "F", 2012)})
    an = analizza(doc, fotografa(db, doc), dec)
    an.righe[0].atleta_id = -1  # forza la creazione (l'analisi altrimenti riusa l'esistente)
    conteggi = {t: db.query_uno(f"SELECT COUNT(*) n FROM {t}")["n"]
                for t in ("risultati", "importazioni", "manifestazioni", "atleti", "record_personali")}
    with pytest.raises(ImportazioneNonValida, match="esiste gia'"):
        salva(db, an, "secondo.pdf")
    assert conteggi == {t: db.query_uno(f"SELECT COUNT(*) n FROM {t}")["n"] for t in conteggi}
