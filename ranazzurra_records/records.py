"""Regole dei record societari, senza database ne' interfaccia.

Definizioni (vedi docs/records-management.md):

- **personale (PB)**: il miglior tempo di un atleta per gara + vasca; sta in
  ``record_personali``, una riga per combinazione;
- **record societari**: i primi 3 tempi della societa' per gara + vasca +
  sesso, calcolati dai personali con un DENSE_RANK (gli ex aequo condividono
  la posizione e la successiva scala di uno: 1, 2, 2, 3). E' la stessa
  classifica pubblicata sul sito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

STILI = {
    "DF": "Delfino",
    "DO": "Dorso",
    "RA": "Rana",
    "SL": "Stile Libero",
    "MX": "Misti",
}
ORDINE_STILI = {"DF": 1, "DO": 2, "RA": 3, "SL": 4, "MX": 5}
ORDINE_DISTANZE = {50: 1, 100: 2, 200: 3, 400: 4, 800: 5, 1500: 6}
VASCHE = {"VC": "Vasca Corta (25m)", "VL": "Vasca Lunga (50m)"}
VASCA_DA_METRI = {25: "VC", 50: "VL"}
POSIZIONI_PUBBLICATE = 3


def chiave_ordinamento_gara(stile: str, distanza: int) -> tuple[int, int]:
    """Ordine delle gare usato ovunque (app e sito): stile, poi distanza."""
    return (ORDINE_STILI.get(stile, 99), ORDINE_DISTANZE.get(int(distanza), 99))


def dense_rank(tempi: dict) -> dict:
    """``{chiave: centesimi}`` -> ``{chiave: posizione}`` con DENSE_RANK."""
    distinti = sorted(set(tempi.values()))
    pos = {t: i + 1 for i, t in enumerate(distinti)}
    return {k: pos[t] for k, t in tempi.items()}


def top(tempi: dict, n: int = POSIZIONI_PUBBLICATE) -> list[tuple]:
    """Righe ``(chiave, centesimi, posizione)`` con posizione <= n, ordinate."""
    rank = dense_rank(tempi)
    righe = [(k, tempi[k], rank[k]) for k in tempi if rank[k] <= n]
    return sorted(righe, key=lambda r: (r[2], r[1], str(r[0])))


class Esito(str, Enum):
    NUOVO_RECORD = "Nuovo record societario"
    RECORD_EGUAGLIATO = "Record societario eguagliato"
    TOP3 = "Record societari migliorati (top 3)"
    PB = "Nuovo primato personale"
    PRIMO_TEMPO = "Primo tempo registrato"
    NESSUNO = "Nessun miglioramento"
    NON_VALUTABILE = "Senza tempo valido"

    @property
    def aggiorna_pb(self) -> bool:
        return self in {
            Esito.NUOVO_RECORD,
            Esito.RECORD_EGUAGLIATO,
            Esito.TOP3,
            Esito.PB,
            Esito.PRIMO_TEMPO,
        }

    @property
    def tocca_record(self) -> bool:
        return self in {Esito.NUOVO_RECORD, Esito.RECORD_EGUAGLIATO, Esito.TOP3}


@dataclass
class Valutazione:
    esito: Esito
    pb_precedente: int | None = None
    record_precedente: int | None = None  # 1° tempo della societa' prima
    posizione_prima: int | None = None
    posizione_dopo: int | None = None
    note: list[str] = field(default_factory=list)

    @property
    def riferimento_precedente(self) -> int | None:
        """Il tempo con cui confrontare: il record se il risultato tocca la
        top 3, altrimenti il personale."""
        if self.esito in {Esito.NUOVO_RECORD, Esito.RECORD_EGUAGLIATO}:
            return self.record_precedente
        return self.pb_precedente


def valuta(
    atleta_id,
    tempo: int | None,
    personali_stessa_gara: dict,
) -> Valutazione:
    """Classifica un risultato rispetto ai personali gia' registrati.

    ``personali_stessa_gara`` e' ``{atleta_id: centesimi}`` per la stessa
    gara, vasca e sesso (lo stato *prima* dell'importazione). La funzione non
    modifica il dizionario.
    """
    pb_prec = personali_stessa_gara.get(atleta_id)
    record_prec = min(personali_stessa_gara.values()) if personali_stessa_gara else None
    pos_prima = dense_rank(personali_stessa_gara).get(atleta_id) if pb_prec is not None else None

    if tempo is None:
        return Valutazione(Esito.NON_VALUTABILE, pb_prec, record_prec, pos_prima, pos_prima)

    if pb_prec is not None and tempo >= pb_prec:
        v = Valutazione(Esito.NESSUNO, pb_prec, record_prec, pos_prima, pos_prima)
        if tempo == pb_prec:
            v.note.append("eguaglia il personale: nessun aggiornamento")
        return v

    dopo = dict(personali_stessa_gara)
    dopo[atleta_id] = tempo
    pos_dopo = dense_rank(dopo)[atleta_id]

    if record_prec is None or tempo < record_prec:
        v = Valutazione(Esito.NUOVO_RECORD, pb_prec, record_prec, pos_prima, pos_dopo)
        if pos_prima == 1:
            v.note.append("migliora il proprio record")
        if record_prec is None:
            v.note.append("primo tempo registrato per questa gara")
        return v
    if tempo == record_prec:
        return Valutazione(Esito.RECORD_EGUAGLIATO, pb_prec, record_prec, pos_prima, pos_dopo)
    if pos_dopo <= POSIZIONI_PUBBLICATE:
        return Valutazione(Esito.TOP3, pb_prec, record_prec, pos_prima, pos_dopo)
    esito = Esito.PB if pb_prec is not None else Esito.PRIMO_TEMPO
    return Valutazione(esito, pb_prec, record_prec, pos_prima, pos_dopo)
