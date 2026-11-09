"""Riconoscimento degli atleti del PDF nell'anagrafica.

Il PDF scrive ``COGNOME NOME`` in un'unica stringa maiuscola; l'anagrafica ha
cognome e nome separati. Il confronto avviene su nomi normalizzati (senza
accenti, apostrofi e trattini, spazi compattati) e considera anche l'ordine
invertito e i doppi cognomi.

Livelli di confidenza:

- **CERTO**: nome identico (in qualunque ordine) e stesso anno di nascita,
  un solo atleta possibile, sesso compatibile; oppure un alias gia'
  confermato a mano. Solo in questo caso l'associazione e' automatica.
- **DA_CONFERMARE**: somiglianza alta ma non identita' (refuso, doppio
  cognome abbreviato), anno di nascita diverso o mancante, sesso diverso.
  Serve la conferma dell'utente.
- **AMBIGUO**: piu' atleti con lo stesso nome e anno (omonimi veri).
- **NON_TROVATO**: nessun candidato credibile; si puo' creare l'atleta.

Una corrispondenza approssimata non viene mai applicata da sola.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

SOGLIA_CANDIDATO = 0.80   # sotto questa somiglianza un atleta non e' proposto
SOGLIA_SUGGERIMENTO = 0.65
SOGLIA_ANNO_DIVERSO = 0.95  # somiglianza minima per proporre un atleta con anno diverso
MAX_CANDIDATI = 3


class Livello(str, Enum):
    CERTO = "certo"
    DA_CONFERMARE = "da confermare"
    AMBIGUO = "omonimi"
    NON_TROVATO = "non trovato"


@dataclass(frozen=True)
class AtletaRif:
    id: int
    cognome: str
    nome: str
    sesso: str | None
    anno_nascita: int | None
    attivo: bool = True

    @property
    def etichetta(self) -> str:
        anno = f" ({self.anno_nascita})" if self.anno_nascita else ""
        return f"{self.cognome} {self.nome}{anno}"


@dataclass
class Candidato:
    atleta: AtletaRif
    punteggio: float
    motivo: str


@dataclass
class Riconoscimento:
    livello: Livello
    atleta: AtletaRif | None = None
    candidati: list[Candidato] = field(default_factory=list)
    motivo: str = ""


def normalizza(s: str) -> str:
    """``"Nicolo' D'Agostino-Rossi"`` -> ``"NICOLO DAGOSTINO ROSSI"``."""
    s = unicodedata.normalize("NFKD", str(s).upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’`´]", "", s)
    s = re.sub(r"[^A-Z ]+", " ", s)
    return " ".join(s.split())


def chiave_token(s: str) -> str:
    return " ".join(sorted(normalizza(s).split()))


def _somiglianza(pdf: str, atleta: AtletaRif) -> tuple[float, str]:
    """Somiglianza fra il nome del PDF e un atleta, con il motivo."""
    tok_pdf = normalizza(pdf).split()
    tok_db = normalizza(f"{atleta.cognome} {atleta.nome}").split()
    if not tok_pdf or not tok_db:
        return 0.0, ""
    if sorted(tok_pdf) == sorted(tok_db):
        return 1.0, "nome identico"
    # doppio cognome o secondo nome presente solo da una parte
    piccolo, grande = (set(tok_db), set(tok_pdf)) if len(tok_db) < len(tok_pdf) else (set(tok_pdf), set(tok_db))
    if len(piccolo) >= 2 and piccolo <= grande:
        return 0.92, "nome contenuto (doppio cognome o secondo nome)"
    r_ord = difflib.SequenceMatcher(None, " ".join(tok_pdf), " ".join(tok_db)).ratio()
    r_tok = difflib.SequenceMatcher(None, " ".join(sorted(tok_pdf)), " ".join(sorted(tok_db))).ratio()
    r_unito = difflib.SequenceMatcher(None, "".join(sorted(tok_pdf)), "".join(sorted(tok_db))).ratio()
    return max(r_ord, r_tok, r_unito), "nome simile"


def _sesso_compatibile(sesso_gara: str | None, atleta: AtletaRif) -> bool:
    return sesso_gara not in ("M", "F") or atleta.sesso in (None, sesso_gara)


def riconosci(
    nome_pdf: str,
    anno: int,
    sesso_gara: str | None,
    atleti: list[AtletaRif],
    alias: dict[tuple[str, int], int] | None = None,
) -> Riconoscimento:
    alias = alias or {}
    per_id = {a.id: a for a in atleti}
    chiave = chiave_token(nome_pdf)

    a_id = alias.get((chiave, anno)) or alias.get((chiave, 0))
    if a_id in per_id:
        a = per_id[a_id]
        if _sesso_compatibile(sesso_gara, a):
            return Riconoscimento(Livello.CERTO, a, motivo="associazione confermata in passato")

    punteggi = []
    for a in atleti:
        p, motivo = _somiglianza(nome_pdf, a)
        if p >= SOGLIA_SUGGERIMENTO:
            punteggi.append(Candidato(a, p, motivo))
    punteggi.sort(key=lambda c: (-c.punteggio, c.atleta.anno_nascita != anno, c.atleta.etichetta))

    identici = [c for c in punteggi if c.punteggio == 1.0]
    stesso_anno = [c for c in identici if c.atleta.anno_nascita == anno]
    if len(stesso_anno) > 1:
        return Riconoscimento(Livello.AMBIGUO, None, stesso_anno[:MAX_CANDIDATI],
                              f"{len(stesso_anno)} atleti con lo stesso nome e anno")
    if len(stesso_anno) == 1:
        a = stesso_anno[0].atleta
        if not _sesso_compatibile(sesso_gara, a):
            return Riconoscimento(Livello.DA_CONFERMARE, None, stesso_anno,
                                  f"sesso in anagrafica ({a.sesso}) diverso da quello della gara ({sesso_gara})")
        return Riconoscimento(Livello.CERTO, a, motivo="nome e anno identici")

    # Un nome solo simile con anno di nascita diverso e' quasi sempre un'altra
    # persona (MERLO 2013 contro Morello 2012): resta un suggerimento, non un
    # candidato, salvo somiglianza altissima.
    candidati = [c for c in punteggi
                 if c.punteggio >= SOGLIA_CANDIDATO
                 and (c.atleta.anno_nascita in (anno, None) or c.punteggio >= SOGLIA_ANNO_DIVERSO)]
    if identici:
        a = identici[0].atleta
        motivo = ("anno di nascita mancante in anagrafica" if a.anno_nascita is None
                  else f"anno di nascita diverso (anagrafica {a.anno_nascita}, PDF {anno})")
        return Riconoscimento(Livello.DA_CONFERMARE, None, candidati[:MAX_CANDIDATI], motivo)
    if candidati:
        # a parita' di somiglianza vale l'anno: un candidato con anno diverso
        # resta proposto ma non e' mai il primo se ce n'e' uno coerente
        return Riconoscimento(Livello.DA_CONFERMARE, None, candidati[:MAX_CANDIDATI],
                              f"{candidati[0].motivo} ({candidati[0].punteggio:.0%})")
    return Riconoscimento(Livello.NON_TROVATO, None, punteggi[:MAX_CANDIDATI],
                          "nessun atleta corrispondente in anagrafica")


def proponi_cognome_nome(nome_pdf: str) -> tuple[str, str]:
    """Divisione proposta per un atleta nuovo: l'ultima parola e' il nome, il
    resto il cognome. E' solo una proposta: con due nomi propri ("BASSO
    GINEVRA VITTORIA") va corretta a mano nella schermata di importazione."""
    tok = nome_pdf.split()
    if len(tok) < 2:
        return nome_pdf.title(), ""
    return " ".join(tok[:-1]).title(), tok[-1].title()
