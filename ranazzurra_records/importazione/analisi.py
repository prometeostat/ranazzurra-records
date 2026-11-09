"""Analisi di un PDF FIN contro lo stato del database, senza scrivere niente.

``analizza()`` e' deterministica: dati il documento, una fotografia del
database (:class:`Fotografia`) e le decisioni dell'utente (:class:`Decisioni`)
produce sempre la stessa :class:`Analisi`. L'interfaccia la ricalcola a ogni
modifica delle decisioni; il salvataggio (``salvataggio.py``) scrive soltanto
quello che l'analisi ha dichiarato importabile e l'utente ha selezionato.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .. import queries as Q
from .. import tempi
from ..db import Database
from ..fin_pdf import DocumentoFIN, GaraFIN, RigaFIN
from ..records import VASCA_DA_METRI, Esito, Valutazione, top, valuta
from .matching import AtletaRif, Livello, Riconoscimento, chiave_token, riconosci

# Stati di una riga nell'analisi
IMPORTABILE = "importabile"
GIA_PRESENTE = "già presente"
NON_VALIDA = "non valida"
ATLETA_DA_RISOLVERE = "atleta da risolvere"
ESCLUSA = "esclusa"


@dataclass
class Fotografia:
    """Lo stato del database che serve all'analisi, letto in una volta."""
    atleti: list[AtletaRif]
    alias: dict[tuple[str, int], int]
    gare: dict[tuple[str, int], int]                    # (stile, distanza) -> gara_id
    descrizione_gare: dict[int, str]
    vasche: dict[str, int]                              # 'VC'/'VL' -> id
    personali: dict[tuple[int, int], dict[int, int]]    # (gara_id, vasca_id) -> {atleta_id: cent}
    manifestazione_id: int | None = None
    risultati_esistenti: set[tuple] = field(default_factory=set)  # (atleta, gara, vasca, turno)
    importazioni_stesso_file: list[dict] = field(default_factory=list)

    def atleta(self, atleta_id: int) -> AtletaRif | None:
        return next((a for a in self.atleti if a.id == atleta_id), None)


def fotografa(db: Database, doc: DocumentoFIN) -> Fotografia:
    atleti = [AtletaRif(r["id"], r["cognome"], r["nome"], r["sesso"], r["anno_nascita"], bool(r["attivo"]))
              for r in db.query(Q.ATLETI.format(where=""))]
    gare_rows = db.query(Q.GARE)
    vasche = {r["codice"]: r["id"] for r in db.query(Q.TIPI_VASCA)}
    personali: dict[tuple[int, int], dict[int, int]] = defaultdict(dict)
    for r in db.query("SELECT atleta_id, gara_id, tipo_vasca_id, tempo_secondi FROM record_personali "
                      "WHERE tempo_secondi IS NOT NULL"):
        personali[(r["gara_id"], r["tipo_vasca_id"])][r["atleta_id"]] = tempi.da_db(r["tempo_secondi"])
    alias, manif_id, esistenti, stesso_file = {}, None, set(), []
    if db.tabella_esiste("atleti_alias"):
        alias = {(r["alias_normalizzato"], int(r["anno_nascita"])): r["atleta_id"] for r in db.query(Q.ALIAS_TUTTI)}
    if db.tabella_esiste("manifestazioni") and doc.data_inizio:
        m = db.query_uno(Q.MANIFESTAZIONE_CERCA, (doc.nome, doc.data_inizio))
        if m:
            manif_id = m["id"]
            esistenti = {(r["atleta_id"], r["gara_id"], r["tipo_vasca_id"], r["turno"])
                         for r in db.query(Q.RISULTATI_DELLA_MANIFESTAZIONE, (manif_id,))}
    if db.tabella_esiste("importazioni"):
        stesso_file = db.query(Q.IMPORTAZIONI_PER_FILE, (doc.sha256,))
    return Fotografia(
        atleti=atleti, alias=alias,
        gare={(g["stile"], int(g["distanza"])): g["id"] for g in gare_rows},
        descrizione_gare={g["id"]: g["descrizione"] for g in gare_rows},
        vasche=vasche, personali=dict(personali), manifestazione_id=manif_id,
        risultati_esistenti=esistenti, importazioni_stesso_file=stesso_file,
    )


# --------------------------------------------------------------------- #
@dataclass
class NuovoAtleta:
    cognome: str
    nome: str
    sesso: str
    anno_nascita: int


@dataclass
class Decisioni:
    """Scelte dell'utente nella schermata di anteprima.

    ``associazioni``: per ogni atleta del PDF (chiave ``nome|anno``) l'id di un
    atleta esistente, ``"nuovo"`` (crearlo con i dati di ``nuovi``) oppure
    ``None`` (escludere tutte le sue righe).
    ``ricorda``: chiavi per cui salvare l'associazione come alias.
    ``escluse``: righe tolte a mano; ``incluse``: righe con avvisi che
    l'utente ha deciso di importare comunque.
    """
    associazioni: dict[str, object] = field(default_factory=dict)
    nuovi: dict[str, NuovoAtleta] = field(default_factory=dict)
    ricorda: set[str] = field(default_factory=set)
    escluse: set[str] = field(default_factory=set)
    incluse: set[str] = field(default_factory=set)


def chiave_atleta(riga: RigaFIN) -> str:
    return f"{riga.nome}|{riga.anno}"


@dataclass
class RigaAnalisi:
    chiave: str
    gara: GaraFIN
    riga: RigaFIN
    gara_id: int | None
    vasca: str | None
    vasca_id: int | None
    data_gara: date | None
    riconoscimento: Riconoscimento
    atleta_id: int | None = None      # positivo: esistente; negativo: da creare
    atleta_etichetta: str = ""
    sesso: str | None = None
    stato: str = IMPORTABILE
    valutazione: Valutazione | None = None
    avvisi: list[str] = field(default_factory=list)
    da_verificare: bool = False        # avvisi che tolgono la selezione automatica
    selezionata: bool = True

    @property
    def esito(self) -> Esito | None:
        return self.valutazione.esito if self.valutazione else None

    @property
    def descrizione_gara(self) -> str:
        d = f"{self.gara.distanza}m " if self.gara.distanza else ""
        nomi = {"DF": "Delfino", "DO": "Dorso", "RA": "Rana", "SL": "Stile Libero", "MX": "Misti"}
        return d + nomi.get(self.gara.stile or "", self.gara.titolo)


@dataclass
class Analisi:
    doc: DocumentoFIN
    foto: Fotografia
    decisioni: Decisioni
    righe: list[RigaAnalisi]
    atleti_pdf: dict[str, Riconoscimento]   # chiave_atleta -> riconoscimento automatico
    top3_prima_dopo: dict[tuple[int, str, str], tuple[list, list]]

    # ---- riepiloghi per l'anteprima ---------------------------------- #
    def righe_con(self, *stati: str) -> list[RigaAnalisi]:
        return [r for r in self.righe if r.stato in stati]

    def selezionate(self) -> list[RigaAnalisi]:
        return [r for r in self.righe if r.stato == IMPORTABILE and r.selezionata]

    def per_esito(self, *esiti: Esito, solo_selezionate: bool = True) -> list[RigaAnalisi]:
        base = self.selezionate() if solo_selezionate else self.righe_con(IMPORTABILE)
        return [r for r in base if r.esito in esiti]

    @property
    def atleti_riconosciuti(self) -> int:
        return len({r.atleta_id for r in self.righe if r.atleta_id and r.atleta_id > 0})

    @property
    def atleti_da_risolvere(self) -> list[str]:
        return sorted({chiave_atleta(r.riga) for r in self.righe if r.stato == ATLETA_DA_RISOLVERE})

    @property
    def gia_importato(self) -> bool:
        return bool(self.foto.importazioni_stesso_file)


# --------------------------------------------------------------------- #
def _risolvi_atleta(riga: RigaFIN, gara: GaraFIN, auto: Riconoscimento, dec: Decisioni,
                    foto: Fotografia, temporanei: dict[str, int]) -> tuple[int | None, str, str | None, str | None]:
    """(atleta_id, etichetta, sesso, problema) applicando le decisioni utente
    sopra il riconoscimento automatico."""
    k = chiave_atleta(riga)
    scelta = dec.associazioni.get(k, "auto")
    if scelta is None:
        return None, "", None, "escluso dall'utente"
    if scelta == "nuovo" and auto.livello == Livello.CERTO and auto.atleta:
        # l'atleta e' stato creato nel frattempo (per esempio da un'importazione
        # precedente): si usa quello invece di crearne un doppione
        return auto.atleta.id, auto.atleta.etichetta, auto.atleta.sesso, None
    if scelta == "nuovo":
        n = dec.nuovi.get(k)
        if n is None or not n.cognome.strip() or not n.nome.strip() or n.sesso not in ("M", "F"):
            return None, "", None, "dati del nuovo atleta incompleti"
        tid = temporanei.setdefault(k, -(len(temporanei) + 1))
        return tid, f"{n.cognome} {n.nome} ({n.anno_nascita}) · nuovo", n.sesso, None
    if isinstance(scelta, int):
        a = foto.atleta(scelta)
        if a is None:
            return None, "", None, "atleta scelto non piu' presente"
        return a.id, a.etichetta, a.sesso, None
    if auto.livello == Livello.CERTO and auto.atleta:
        return auto.atleta.id, auto.atleta.etichetta, auto.atleta.sesso, None
    return None, "", None, auto.motivo or auto.livello.value


def analizza(doc: DocumentoFIN, foto: Fotografia, dec: Decisioni | None = None) -> Analisi:
    dec = dec or Decisioni()
    atleti_pdf: dict[str, Riconoscimento] = {}
    righe: list[RigaAnalisi] = []
    temporanei: dict[str, int] = {}
    visti_in_gara: dict[tuple, list[RigaAnalisi]] = defaultdict(list)

    # riconoscimento automatico di tutti i nomi prima di decidere le righe
    for gara in doc.gare:
        for riga in gara.righe:
            k = chiave_atleta(riga)
            if k not in atleti_pdf:
                atleti_pdf[k] = riconosci(riga.nome, riga.anno, gara.sesso, foto.atleti, foto.alias)
    _togli_candidati_gia_presi(atleti_pdf)

    for gi, gara in enumerate(doc.gare):
        if gara.staffetta:
            continue
        vasca = VASCA_DA_METRI.get(gara.vasca_metri or 0)
        gara_id = foto.gare.get((gara.stile, gara.distanza)) if gara.stile and gara.distanza else None
        for ri, riga in enumerate(gara.righe):
            k = chiave_atleta(riga)
            if k not in atleti_pdf:
                atleti_pdf[k] = riconosci(riga.nome, riga.anno, gara.sesso, foto.atleti, foto.alias)
            ra = RigaAnalisi(
                chiave=f"{gi}-{ri}", gara=gara, riga=riga, gara_id=gara_id, vasca=vasca,
                vasca_id=foto.vasche.get(vasca) if vasca else None,
                data_gara=gara.data or doc.data_inizio, riconoscimento=atleti_pdf[k],
            )
            righe.append(ra)

            # -- validazione dei dati della gara e della riga ------------
            if riga.stato == "ASS":
                ra.stato, ra.selezionata = NON_VALIDA, False
                ra.avvisi.append("assente: non si registra")
                continue
            if gara_id is None:
                ra.stato, ra.selezionata = NON_VALIDA, False
                ra.avvisi.append(f"gara non riconosciuta nell'anagrafica gare: '{gara.titolo}'")
                continue
            if vasca is None:
                ra.stato, ra.selezionata = NON_VALIDA, False
                ra.avvisi.append("vasca non indicata nel PDF (manca 'Base v.: 25/50')")
                continue
            if ra.data_gara is None:
                ra.stato, ra.selezionata = NON_VALIDA, False
                ra.avvisi.append("data della gara non trovata nel PDF")
                continue
            if riga.stato == "OK" and riga.tempo is None:
                ra.stato, ra.selezionata = NON_VALIDA, False
                ra.avvisi.append("tempo illeggibile")
                continue

            # -- atleta --------------------------------------------------
            aid, etich, sesso, problema = _risolvi_atleta(riga, gara, atleti_pdf[k], dec, foto, temporanei)
            if problema == "escluso dall'utente":
                ra.stato, ra.selezionata = ESCLUSA, False
                continue
            if aid is None:
                ra.stato, ra.selezionata = ATLETA_DA_RISOLVERE, False
                ra.avvisi.append(problema or "atleta da associare")
                continue
            ra.atleta_id, ra.atleta_etichetta, ra.sesso = aid, etich, sesso
            if sesso not in ("M", "F"):
                ra.stato, ra.selezionata = ATLETA_DA_RISOLVERE, False
                ra.avvisi.append("sesso dell'atleta mancante in anagrafica")
                continue
            if gara.sesso in ("M", "F") and sesso != gara.sesso:
                ra.avvisi.append(f"gara {gara.sesso} ma atleta {sesso} in anagrafica")
                ra.da_verificare = True
            a = foto.atleta(aid) if aid > 0 else None
            if a is not None and a.anno_nascita and a.anno_nascita != riga.anno:
                ra.avvisi.append(f"anno di nascita: anagrafica {a.anno_nascita}, PDF {riga.anno}")
            if a is not None and not a.attivo:
                ra.avvisi.append("atleta inattivo in anagrafica")

            # -- duplicati ----------------------------------------------
            chiave_db = (aid, gara_id, ra.vasca_id, gara.turno)
            if aid > 0 and chiave_db in foto.risultati_esistenti:
                ra.stato, ra.selezionata = GIA_PRESENTE, False
                continue
            visti_in_gara[(aid, gara_id, ra.vasca_id, gara.turno)].append(ra)

            # -- controlli di coerenza (tolgono la selezione automatica) --
            if riga.stato != "OK":
                ra.avvisi.append(f"senza tempo valido ({riga.stato}): entra solo nello storico")
            elif not tempi.plausibile(riga.tempo, gara.distanza or 0):
                ra.avvisi.append("tempo fuori dalla scala plausibile per la distanza")
                ra.da_verificare = True
            if gara.cronometraggio == "M":
                ra.avvisi.append("cronometraggio manuale")
                ra.da_verificare = True
            if riga.fuori_gara:
                ra.avvisi.append("nuotata fuori gara (FG)")

    for gruppo in visti_in_gara.values():
        if len(gruppo) > 1:
            for ra in gruppo:
                ra.avvisi.append("stesso atleta due volte nella stessa gara del PDF")
                ra.da_verificare = True

    # -- selezione: default, poi le scelte dell'utente ---------------------
    for ra in righe:
        if ra.stato != IMPORTABILE:
            continue
        if ra.chiave in dec.escluse:
            ra.selezionata = False
        elif ra.da_verificare:
            ra.selezionata = ra.chiave in dec.incluse
        else:
            ra.selezionata = True

    _valuta_tutte(righe, foto)
    return Analisi(doc, foto, dec, righe, atleti_pdf, _top3_prima_dopo(righe, foto))


def _togli_candidati_gia_presi(atleti_pdf: dict[str, Riconoscimento]) -> None:
    """Un atleta riconosciuto con certezza sotto un nome del PDF non puo'
    essere anche il candidato di un altro nome dello stesso PDF (nella stessa
    manifestazione nuotano sia MORELLO ALESSANDRO sia MERLO ALESSANDRO)."""
    presi = {r.atleta.id for r in atleti_pdf.values() if r.livello == Livello.CERTO and r.atleta}
    for r in atleti_pdf.values():
        if r.livello in (Livello.DA_CONFERMARE, Livello.NON_TROVATO):
            r.candidati = [c for c in r.candidati if c.atleta.id not in presi]
            if r.livello == Livello.DA_CONFERMARE and not r.candidati:
                r.livello = Livello.NON_TROVATO
                r.motivo = "l'unico candidato e' gia' associato a un altro nome del PDF"


def _personali_per_sesso(foto: Fotografia, gara_id: int, vasca_id: int, sesso: str) -> dict[int, int]:
    sessi = {a.id: a.sesso for a in foto.atleti}
    return {aid: t for aid, t in foto.personali.get((gara_id, vasca_id), {}).items() if sessi.get(aid) == sesso}


def _valuta_tutte(righe: list[RigaAnalisi], foto: Fotografia) -> None:
    """Ogni risultato si confronta con lo stato del database prima
    dell'importazione. Se lo stesso atleta ha piu' tempi selezionati sulla
    stessa gara e vasca (batterie e finale), conta il migliore."""
    migliori: dict[tuple, RigaAnalisi] = {}
    for ra in righe:
        if ra.stato != IMPORTABILE or ra.atleta_id is None:
            continue
        base = _personali_per_sesso(foto, ra.gara_id, ra.vasca_id, ra.sesso)
        ra.valutazione = valuta(ra.atleta_id, ra.riga.tempo if ra.riga.stato == "OK" else None, base)
        if ra.selezionata and ra.riga.stato == "OK":
            k = (ra.atleta_id, ra.gara_id, ra.vasca_id)
            if k not in migliori or ra.riga.tempo < migliori[k].riga.tempo:
                migliori[k] = ra
    for ra in righe:
        if (ra.valutazione and ra.valutazione.esito.aggiorna_pb and ra.selezionata
                and migliori.get((ra.atleta_id, ra.gara_id, ra.vasca_id)) is not ra):
            ra.valutazione = Valutazione(Esito.NESSUNO, ra.valutazione.pb_precedente,
                                         ra.valutazione.record_precedente,
                                         note=["nella stessa importazione c'e' un tempo migliore"])


def _top3_prima_dopo(righe: list[RigaAnalisi], foto: Fotografia) -> dict:
    """Per ogni gara+vasca+sesso toccata da un record: top 3 prima e dopo
    l'importazione delle righe selezionate."""
    out = {}
    toccate = {(ra.gara_id, ra.vasca, ra.sesso) for ra in righe
               if ra.stato == IMPORTABILE and ra.selezionata and ra.esito and ra.esito.tocca_record}
    for gara_id, vasca, sesso in toccate:
        vid = foto.vasche[vasca]
        prima = _personali_per_sesso(foto, gara_id, vid, sesso)
        dopo = dict(prima)
        for ra in righe:
            if (ra.gara_id, ra.vasca, ra.sesso) == (gara_id, vasca, sesso) and ra.selezionata \
                    and ra.stato == IMPORTABILE and ra.esito and ra.esito.aggiorna_pb:
                dopo[ra.atleta_id] = min(dopo.get(ra.atleta_id, ra.riga.tempo), ra.riga.tempo)
        out[(gara_id, vasca, sesso)] = (top(prima), top(dopo))
    return out


def etichetta_atleta(foto: Fotografia, dec: Decisioni, atleta_id: int, righe: list[RigaAnalisi]) -> str:
    if atleta_id > 0:
        a = foto.atleta(atleta_id)
        return a.etichetta if a else f"#{atleta_id}"
    ra = next((r for r in righe if r.atleta_id == atleta_id), None)
    return ra.atleta_etichetta if ra else "nuovo atleta"


__all__ = [
    "Analisi", "Decisioni", "Fotografia", "NuovoAtleta", "RigaAnalisi", "analizza", "chiave_atleta",
    "chiave_token", "fotografa", "IMPORTABILE", "GIA_PRESENTE", "NON_VALIDA", "ATLETA_DA_RISOLVERE", "ESCLUSA",
]
