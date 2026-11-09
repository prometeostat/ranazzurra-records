"""Analisi in memoria: documento costruito a mano, nessun database."""

from datetime import date

from ranazzurra_records.fin_pdf.parser import DocumentoFIN, GaraFIN, RigaFIN
from ranazzurra_records.importazione.analisi import (ATLETA_DA_RISOLVERE, ESCLUSA, GIA_PRESENTE, IMPORTABILE,
                                                     NON_VALIDA, Decisioni, Fotografia, NuovoAtleta, analizza)
from ranazzurra_records.importazione.matching import AtletaRif
from ranazzurra_records.records import Esito

GIORNO = date(2026, 11, 8)
ATLETI = [
    AtletaRif(1, "Pasquali", "Andrea", "M", 2011),
    AtletaRif(2, "Collodel", "Marco", "M", 2008),
    AtletaRif(3, "Recine", "Davide", "M", 2012),
    AtletaRif(4, "Dal Bianco", "Noemi", "F", 2013),
]
GARE = {("RA", 50): 10, ("SL", 50): 11}


def riga(nome, anno, tempo, pos=1, stato="OK", fg=False):
    return RigaFIN(nome, anno, "RANAZZURRA CONEGLIANO SSD", pos, tempo, stato, fg, 1, "")


def gara(stile, dist, sesso, righe, cron="A", vasca=25, turno=""):
    return GaraFIN(f"{dist} {stile}", stile, dist, sesso, vasca, False, cron, GIORNO, "Mestre", turno, 1,
                   righe, len(righe))


def documento(*gare):
    return DocumentoFIN("Meeting", GIORNO, GIORNO, "Mestre", 1, "abc", list(gare), [])


def foto(**kw):
    base = dict(atleti=ATLETI, alias={}, gare=GARE, descrizione_gare={10: "50m Rana", 11: "50m Stile Libero"},
                vasche={"VC": 1, "VL": 2}, personali={(10, 1): {1: 3070, 2: 2900, 3: 3200}})
    base.update(kw)
    return Fotografia(**base)


def test_record_e_personali():
    doc = documento(gara("RA", 50, "M", [
        riga("PASQUALI ANDREA", 2011, 3009),      # 30.70 -> 30.09: entra 2° (top 3)
        riga("COLLODEL MARCO", 2008, 2880),       # nuovo record
        riga("RECINE DAVIDE", 2012, 3300),        # piu' lento del PB
    ]))
    an = analizza(doc, foto())
    esiti = {r.atleta_id: r.esito for r in an.righe}
    assert esiti == {1: Esito.TOP3, 2: Esito.NUOVO_RECORD, 3: Esito.NESSUNO}
    assert all(r.selezionata and r.stato == IMPORTABILE for r in an.righe)
    prima, dopo = an.top3_prima_dopo[(10, "VC", "M")]
    assert [a for a, _, _ in prima] == [2, 1, 3]
    assert [a for a, _, _ in dopo] == [2, 1, 3] and dopo[0][1] == 2880


def test_atleta_da_risolvere_e_decisioni():
    doc = documento(gara("SL", 50, "F", [riga("DAL BIANCO DA SILVA NOEMI", 2013, 3380),
                                          riga("SOCOLOVSCHI DARIA", 2014, 3956)]))
    an = analizza(doc, foto())
    assert [r.stato for r in an.righe] == [ATLETA_DA_RISOLVERE, ATLETA_DA_RISOLVERE]
    assert not an.selezionate()

    dec = Decisioni(associazioni={"DAL BIANCO DA SILVA NOEMI|2013": 4, "SOCOLOVSCHI DARIA|2014": "nuovo"},
                    nuovi={"SOCOLOVSCHI DARIA|2014": NuovoAtleta("Socolovschi", "Daria", "F", 2014)})
    an = analizza(doc, foto(), dec)
    assert [r.stato for r in an.righe] == [IMPORTABILE, IMPORTABILE]
    assert an.righe[0].atleta_id == 4 and an.righe[1].atleta_id < 0
    assert {r.esito for r in an.righe} == {Esito.NUOVO_RECORD, Esito.TOP3}   # gara vuota: 1° e 2° tempo

    dec.associazioni["SOCOLOVSCHI DARIA|2014"] = None
    an = analizza(doc, foto(), dec)
    assert an.righe[1].stato == ESCLUSA


def test_nuovo_atleta_con_dati_incompleti_resta_fuori():
    doc = documento(gara("SL", 50, None, [riga("SOCOLOVSCHI DARIA", 2014, 3956)]))
    dec = Decisioni(associazioni={"SOCOLOVSCHI DARIA|2014": "nuovo"},
                    nuovi={"SOCOLOVSCHI DARIA|2014": NuovoAtleta("Socolovschi", "Daria", "", 2014)})
    r = analizza(doc, foto(), dec).righe[0]
    assert r.stato == ATLETA_DA_RISOLVERE and "incompleti" in r.avvisi[0]


def test_gia_presente():
    doc = documento(gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3009)]))
    an = analizza(doc, foto(manifestazione_id=5, risultati_esistenti={(1, 10, 1, "")}))
    assert an.righe[0].stato == GIA_PRESENTE and not an.selezionate()


def test_controlli_tolgono_la_selezione_automatica():
    doc = documento(
        gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3009)], cron="M"),
        gara("SL", 50, "M", [riga("RECINE DAVIDE", 2012, 800)]),             # 8"00 sui 50
    )
    an = analizza(doc, foto())
    assert [r.selezionata for r in an.righe] == [False, False]
    assert "cronometraggio manuale" in an.righe[0].avvisi
    dec = Decisioni(incluse={an.righe[0].chiave})
    an = analizza(doc, foto(), dec)
    assert [r.selezionata for r in an.righe] == [True, False]


def test_assenti_e_squalifiche():
    doc = documento(gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, None, None, "ASS"),
                                          riga("RECINE DAVIDE", 2012, None, None, "SQ")]))
    an = analizza(doc, foto())
    assert an.righe[0].stato == NON_VALIDA
    assert an.righe[1].stato == IMPORTABILE and an.righe[1].esito == Esito.NON_VALUTABILE


def test_gara_non_riconosciuta_e_vasca_mancante():
    doc = documento(gara("RA", 75, "M", [riga("PASQUALI ANDREA", 2011, 4000)]),
                    gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3000)], vasca=None))
    an = analizza(doc, foto())
    assert [r.stato for r in an.righe] == [NON_VALIDA, NON_VALIDA]


def test_due_tempi_stessa_gara_vale_il_migliore():
    doc = documento(gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3050)], turno="BATTERIE"),
                    gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3009)], turno="FINALE A"))
    an = analizza(doc, foto())
    lento, veloce = an.righe
    assert veloce.esito == Esito.TOP3
    assert lento.esito == Esito.NESSUNO and "tempo migliore" in lento.valutazione.note[0]


def test_esclusione_manuale():
    doc = documento(gara("RA", 50, "M", [riga("PASQUALI ANDREA", 2011, 3009)]))
    an = analizza(doc, foto())
    an = analizza(doc, foto(), Decisioni(escluse={an.righe[0].chiave}))
    assert not an.righe[0].selezionata and not an.top3_prima_dopo
