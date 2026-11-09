import pytest

from conftest import crea_pdf
from ranazzurra_records.fin_pdf import PDFNonLeggibile, leggi_pdf
from ranazzurra_records.fin_pdf.parser import _riga, e_nostra, interpreta_titolo


@pytest.mark.parametrize("soc,attesa", [
    ("RANAZZURRA CONEGLIANO SSD", True),
    ("RANAZZURRA CONEGLIANO S.S.D. A R.L.", True),
    ("418 RANAZZURRA CONEGLIANO", True),        # codice club fuso nel nome
    ("Ranazzurra Conegliano", True),
    ("RANAZZURRA SPRESIANO", False),            # altra societa' (Master)
    ("RANAZZURRA Lido", False),
    ("NUOTO VENEZIA SSD", False),
])
def test_societa(soc, attesa):
    assert e_nostra(soc) is attesa


@pytest.mark.parametrize("titolo,attesa", [
    ("200 Stile Libero Serie Cat.: Assoluti Femmine Agonisti", ("SL", 200, "F", False, "")),
    ("100 Farfalla Serie Cat.: Assoluti Maschi Agonisti", ("DF", 100, "M", False, "")),
    ("400 Misti Serie Cat.: Assoluti Femmine Agonisti", ("MX", 400, "F", False, "")),
    ("1500 Stile Libero Serie Cat.: Assoluti", ("SL", 1500, None, False, "")),
    ("50 Rana Finale A Maschi", ("RA", 50, "M", False, "FINALE A")),
    ("4x50 Mista Staffetta Maschi", ("MX", None, "M", True, "")),
])
def test_titolo(titolo, attesa):
    t = interpreta_titolo(titolo)
    assert (t["stile"], t["distanza"], t["sesso"], t["staffetta"], t["turno"]) == attesa


def test_riga_tre_colonne():
    r = _riga("8 2 7 PECCOLO ALICE 2013 RANAZZURRA CONEGLIANO SSD 02:12.63", False, 1)
    assert (r.nome, r.anno, r.posizione, r.tempo, r.stato) == ("PECCOLO ALICE", 2013, 8, 13263, "OK")
    r = _riga("20 4 4 BATTISTUZZI TONON RACHELE 2014 RANAZZURRA CONEGLIANO SSD 02:16.64", False, 1)
    assert r.nome == "BATTISTUZZI TONON RACHELE" and r.societa == "RANAZZURRA CONEGLIANO SSD"
    r = _riga("19 3 7 VENTURINI NICOLO' 2010 CLODIA PISCINA & F - CHIO 02:09.33", False, 1)
    assert r.nome == "VENTURINI NICOLO'" and r.tempo == 12933


def test_riga_con_punti_e_fuori_gara():
    r = _riga("3 1 6 ROSSI MARIO 2010 RANAZZURRA CONEGLIANO SSD 00:28.31 FG 734.29", False, 1)
    assert r.tempo == 2831 and r.fuori_gara


def test_riga_senza_tempo():
    r = _riga("- 1 3 PAIN RICCARDO FEDERICO 2010 NUOTO VENEZIA SSD SQU", False, 4)
    assert (r.posizione, r.tempo, r.stato) == (None, None, "SQ")
    assert _riga("- 5 3 DAL ZENNARO GABRIELE 2013 NUOTO VENEZIA SSD ASS", False, 1).stato == "ASS"


def test_riga_una_colonna_con_parziali():
    r = _riga("4 ROSSI MARIO 2010 VEN RANAZZURRA CONEGLIANO SSD 01:19.8101:29.02 02:48.83", True, 1)
    assert r.tempo == 16883 and r.posizione == 4


def test_tre_colonne_non_legge_serie_e_corsia_come_nome():
    assert _riga("12 3 4 MARIO 2010", False, 1) is None


# --- PDF sintetici --------------------------------------------------------
INTESTA = ["Meeting di prova Foglio n. 1", "08/11/2026", "RISULTATI RIEPILOGATIVI"]


def test_pdf_sintetico_con_continuazione_e_mista():
    pdf = crea_pdf([
        INTESTA + [
            "50 Dorso Serie Cat.: Assoluti Femmine Agonisti",
            "Treviso , Domenica 08/11/2026 ore 15:00",
            "Cron: A - Base v.: 50",
            "Pos Ser. Cor Atleta Anno Societa Tempo Pti",
            "1 1 4 VERDI ANNA 2011 NUOTO VENEZIA SSD 00:31.20",
            "2 1 5 ROSSI LUCIA 2012 RANAZZURRA CONEGLIANO SSD 00:31.90",
        ],
        ["Meeting di prova Foglio n. 2", "08/11/2026", "RISULTATI RIEPILOGATIVI",
         "3 2 1 BIANCHI SARA 2012 RANAZZURRA CONEGLIANO SSD 00:33.00",   # continuazione
         "- 2 2 NERI EVA 2013 RANAZZURRA CONEGLIANO SSD RIT"],
        INTESTA + [
            "1500 Stile Libero Serie Cat.: Assoluti",
            "Treviso , Lunedì 09/11/2026 ore 10:00",
            "Cron: M - Base v.: 50",
            "Pos Ser. Cor Atleta Anno Societa Tempo Pti",
            "1 1 4 BLU MARCO 2009 RANAZZURRA CONEGLIANO SSD 17:39.23",
            "2 1 5 GIALLI PIERO 2009 RANAZZURRA SPRESIANO 17:59.00",
        ],
    ])
    doc = leggi_pdf(pdf)
    assert doc.nome == "Meeting di prova"
    assert (str(doc.data_inizio), str(doc.data_fine), doc.luogo) == ("2026-11-08", "2026-11-09", "Treviso")
    assert len(doc.gare) == 2
    dorso, sl = doc.gare
    assert (dorso.stile, dorso.distanza, dorso.sesso, dorso.vasca_metri, dorso.cronometraggio) == ("DO", 50, "F", 50, "A")
    assert [r.nome for r in dorso.righe] == ["ROSSI LUCIA", "BIANCHI SARA", "NERI EVA"]
    assert dorso.righe_totali == 4 and dorso.righe[2].stato == "RIT"
    assert sl.sesso is None and sl.cronometraggio == "M" and str(sl.data) == "2026-11-09"
    assert [r.nome for r in sl.righe] == ["BLU MARCO"]
    assert sl.altre_ranazzurra == ["GIALLI PIERO (RANAZZURRA SPRESIANO)"]
    assert doc.anomalie == []


def test_pdf_senza_testo_rifiutato():
    with pytest.raises(PDFNonLeggibile, match="scansione"):
        leggi_pdf(crea_pdf([[]]))


def test_file_non_pdf():
    with pytest.raises(PDFNonLeggibile):
        leggi_pdf(b"non sono un pdf")


def test_pdf_senza_gare():
    with pytest.raises(PDFNonLeggibile, match="non ho trovato gare"):
        leggi_pdf(crea_pdf([["Iscrizioni", "Elenco atleti"]]))


# --- PDF reale dell'08/11/2026 (fuori dal repository) ---------------------
def test_pdf_reale_08_11_2026(pdf_reale):
    doc = leggi_pdf(pdf_reale)
    assert doc.nome == "1a Giornata Attività di Categoria Venezia"
    assert str(doc.data_inizio) == "2026-11-08" and doc.luogo == "Mestre"
    assert len(doc.gare) == 15 and doc.righe_totali == 360
    assert len(doc.righe_nostre) == 60 and doc.anomalie == []
    assert all(g.vasca_metri == 25 and g.cronometraggio == "A" for g in doc.gare)
    per_pagina = {g.pagina: len(g.righe) for g in doc.gare}
    assert per_pagina == {1: 8, 2: 6, 3: 1, 4: 3, 5: 3, 6: 0, 7: 5, 8: 7, 9: 4, 10: 4,
                          11: 3, 12: 4, 13: 2, 14: 6, 15: 4}
    righe = {(g.stile, g.distanza, g.sesso, r.nome): r for g, r in doc.righe_nostre}
    assert righe[("SL", 200, "F", "PECCOLO ALICE")].tempo == 13263
    assert righe[("SL", 200, "F", "PECCOLO ALICE")].posizione == 8
    assert righe[("DO", 100, "M", "MASUT CHRISTIAN")].tempo == 5828
    assert righe[("RA", 50, "M", "PASQUALI ANDREA")].tempo == 3009
    assert righe[("SL", 1500, None, "ZAMBET ALESSIO")].tempo == 105923
    assert all(r.stato == "OK" for _, r in doc.righe_nostre)
