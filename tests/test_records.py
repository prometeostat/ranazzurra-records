from ranazzurra_records.records import Esito, chiave_ordinamento_gara, dense_rank, top, valuta


def test_dense_rank_con_ex_aequo():
    r = dense_rank({"a": 2959, "b": 3056, "c": 3056, "d": 3161})
    assert r == {"a": 1, "b": 2, "c": 2, "d": 3}


def test_top_include_tutti_gli_ex_aequo():
    righe = top({"a": 2959, "b": 3056, "c": 3056, "d": 3161, "e": 3200})
    assert [(k, p) for k, _, p in righe] == [("a", 1), ("b", 2), ("c", 2), ("d", 3)]


def test_ordinamento_gare_come_il_sito():
    gare = [("SL", 50), ("DF", 100), ("MX", 200), ("DF", 50), ("DO", 50)]
    assert sorted(gare, key=lambda g: chiave_ordinamento_gara(*g)) == \
        [("DF", 50), ("DF", 100), ("DO", 50), ("SL", 50), ("MX", 200)]


BASE = {1: 2900, 2: 3000, 3: 3100, 4: 3300}


def test_nuovo_record():
    v = valuta(4, 2850, BASE)
    assert v.esito == Esito.NUOVO_RECORD
    assert (v.pb_precedente, v.record_precedente, v.posizione_prima, v.posizione_dopo) == (3300, 2900, 4, 1)
    assert v.riferimento_precedente == 2900


def test_il_detentore_migliora_il_proprio_record():
    v = valuta(1, 2890, BASE)
    assert v.esito == Esito.NUOVO_RECORD and "migliora il proprio record" in v.note


def test_record_eguagliato():
    assert valuta(4, 2900, BASE).esito == Esito.RECORD_EGUAGLIATO


def test_ingresso_in_top3_ed_ex_aequo():
    v = valuta(4, 3000, BASE)                  # pari al secondo
    assert v.esito == Esito.TOP3 and v.posizione_dopo == 2
    assert valuta(4, 3050, BASE).esito == Esito.TOP3


def test_migliora_dentro_la_top3():
    v = valuta(3, 3050, BASE)
    assert v.esito == Esito.TOP3 and (v.posizione_prima, v.posizione_dopo) == (3, 3)


def test_personale_senza_top3():
    v = valuta(4, 3200, BASE)
    assert v.esito == Esito.PB and v.riferimento_precedente == 3300


def test_primo_tempo_fuori_top3():
    assert valuta(9, 3500, BASE).esito == Esito.PRIMO_TEMPO


def test_primo_tempo_dentro_la_top3():
    assert valuta(9, 3050, BASE).esito == Esito.TOP3


def test_nessun_miglioramento_e_pari_al_personale():
    assert valuta(2, 3001, BASE).esito == Esito.NESSUNO
    v = valuta(2, 3000, BASE)
    assert v.esito == Esito.NESSUNO and v.note


def test_gara_senza_record():
    v = valuta(1, 4000, {})
    assert v.esito == Esito.NUOVO_RECORD and v.record_precedente is None


def test_senza_tempo():
    assert valuta(1, None, BASE).esito == Esito.NON_VALUTABILE


def test_non_modifica_l_input():
    base = dict(BASE)
    valuta(4, 2000, base)
    assert base == BASE


def test_proprieta_esiti():
    assert Esito.PRIMO_TEMPO.aggiorna_pb and not Esito.NESSUNO.aggiorna_pb
    assert Esito.TOP3.tocca_record and not Esito.PB.tocca_record
