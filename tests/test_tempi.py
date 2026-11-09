from decimal import Decimal

import pytest

from ranazzurra_records import tempi


@pytest.mark.parametrize("testo,cent", [
    ("1:23.45", 8345),
    ("0:32.10", 3210),
    ("32.10", 3210),
    ("32,10", 3210),
    ("00:28.31", 2831),
    ("17:39.23", 105923),
    ("1:02:03.45", 372345),
    ("01:04.9", 6490),       # decimi
    ("59", 5900),
    (" 2:12.63 ", 13263),
])
def test_parse(testo, cent):
    assert tempi.parse_tempo(testo) == cent


@pytest.mark.parametrize("testo", ["", None, "abc", "1:60.00", "1:2:3:4", "0:00.00", "1.2.3", "12:3"])
def test_parse_rifiuta(testo):
    with pytest.raises(tempi.TempoNonValido):
        tempi.parse_tempo(testo)
    assert tempi.prova_parse_tempo(testo) is None


@pytest.mark.parametrize("cent,testo", [
    (2558, "0:25.58"), (6490, "1:04.90"), (114467, "19:04.67"), (372345, "1:02:03.45"), (None, ""),
])
def test_formatta_come_il_database(cent, testo):
    assert tempi.formatta(cent) == testo


def test_andata_e_ritorno_decimal():
    for c in (1, 99, 100, 2558, 114467, 372345):
        assert tempi.da_db(tempi.a_decimal(c)) == c
    assert tempi.a_decimal(2558) == Decimal("25.58")
    assert tempi.da_db(25.58) == 2558      # float letto male non perde il centesimo
    assert tempi.da_db("114.67") == 11467
    assert tempi.da_db(None) is None


def test_differenza():
    assert tempi.differenza(3009, 3070) == -61
    assert tempi.formatta_differenza(-61) == "-0.61"
    assert tempi.formatta_differenza(123) == "+1.23"
    assert tempi.formatta_differenza(0) == "0.00"
    assert tempi.differenza(None, 1) is None


def test_plausibile():
    assert tempi.plausibile(2831, 50)
    assert not tempi.plausibile(831, 50)       # 8"31 sui 50: errore di lettura
    assert not tempi.plausibile(105923, 50)
    assert tempi.plausibile(105923, 1500)
    assert tempi.plausibile(1, 75)             # distanza sconosciuta: non giudica
