from ranazzurra_records.importazione.matching import (AtletaRif, Livello, chiave_token, normalizza,
                                                      proponi_cognome_nome, riconosci)

ATLETI = [
    AtletaRif(1, "Peccolo", "Alice", "F", 2013),
    AtletaRif(2, "Dal Bianco", "Noemi", "F", 2013),
    AtletaRif(3, "De La Rosa Brioso", "Francesca", "F", 2013),
    AtletaRif(4, "Morello", "Alessandro", "M", 2012),
    AtletaRif(5, "Venturini", "Nicolò", "M", 2010),
    AtletaRif(6, "Rossi", "Mario", "M", 2010),
    AtletaRif(7, "Rossi", "Mario", "M", 2010),
    AtletaRif(8, "Masut", "Christian", "M", None),
    AtletaRif(9, "Carniato", "Arianna", "F", 2013),
]


def test_normalizzazione():
    assert normalizza("Nicolò D'Agostino-Rossi") == "NICOLO DAGOSTINO ROSSI"
    assert normalizza("  venturini   NICOLO' ") == "VENTURINI NICOLO"
    assert chiave_token("ALICE PECCOLO") == chiave_token("Peccolo Alice")


def test_identico_e_stesso_anno_e_automatico():
    r = riconosci("PECCOLO ALICE", 2013, "F", ATLETI)
    assert r.livello == Livello.CERTO and r.atleta.id == 1


def test_ordine_invertito_e_accenti():
    assert riconosci("ALICE PECCOLO", 2013, "F", ATLETI).atleta.id == 1
    r = riconosci("VENTURINI NICOLO'", 2010, "M", ATLETI)
    assert r.livello == Livello.CERTO and r.atleta.id == 5


def test_doppio_cognome_chiede_conferma():
    r = riconosci("DAL BIANCO DA SILVA NOEMI", 2013, "F", ATLETI)
    assert r.livello == Livello.DA_CONFERMARE and r.atleta is None
    assert r.candidati[0].atleta.id == 2


def test_refuso_chiede_conferma():
    r = riconosci("DE LA ROSA BRIOSO FRANCHESCA", 2013, "F", ATLETI)
    assert r.livello == Livello.DA_CONFERMARE and r.candidati[0].atleta.id == 3


def test_nome_simile_con_anno_diverso_non_e_un_candidato():
    r = riconosci("MERLO ALESSANDRO", 2013, "M", ATLETI)
    assert r.livello == Livello.NON_TROVATO
    assert [c.atleta.id for c in r.candidati] == [4]   # resta come suggerimento


def test_omonimi():
    r = riconosci("ROSSI MARIO", 2010, "M", ATLETI)
    assert r.livello == Livello.AMBIGUO and len(r.candidati) == 2


def test_anno_mancante_o_diverso():
    assert riconosci("MASUT CHRISTIAN", 2002, "M", ATLETI).livello == Livello.DA_CONFERMARE
    r = riconosci("CARNIATO ARIANNA", 2012, "F", ATLETI)
    assert r.livello == Livello.DA_CONFERMARE and "anno" in r.motivo


def test_sesso_incoerente_non_e_automatico():
    r = riconosci("PECCOLO ALICE", 2013, "M", ATLETI)
    assert r.livello == Livello.DA_CONFERMARE and "sesso" in r.motivo
    # gara mista o senza sesso: nessun problema
    assert riconosci("PECCOLO ALICE", 2013, None, ATLETI).livello == Livello.CERTO


def test_alias_confermato():
    alias = {(chiave_token("DAL BIANCO DA SILVA NOEMI"), 2013): 2}
    r = riconosci("DAL BIANCO DA SILVA NOEMI", 2013, "F", ATLETI, alias)
    assert r.livello == Livello.CERTO and r.atleta.id == 2


def test_sconosciuto():
    assert riconosci("SOCOLOVSCHI DARIA", 2014, "F", ATLETI).livello == Livello.NON_TROVATO


def test_proposta_cognome_nome():
    assert proponi_cognome_nome("BATTISTUZZI TONON RACHELE") == ("Battistuzzi Tonon", "Rachele")
    assert proponi_cognome_nome("D'AGOSTINO LEONARDO") == ("D'Agostino", "Leonardo")
