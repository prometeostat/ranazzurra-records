"""Conversione dei tempi di gara.

Dentro il codice un tempo e' sempre un ``int`` di centesimi di secondo: i
confronti sono esatti e non dipendono dagli arrotondamenti dei float.
A database resta ``DECIMAL(10,2)`` in secondi (``tempo_secondi``) piu' la
stringa ``tempo_formattato`` nel formato storico ``M:SS.CC`` (``0:25.58``,
``19:04.67``) oppure ``H:MM:SS.CC`` sopra l'ora.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

# [ore:]minuti:secondi[.cc] oppure secondi[.cc]; i decimi sono ammessi
# ("01:04.9" nei PDF con cronometraggio a decimi) e diventano centesimi.
_RX_TEMPO = re.compile(
    r"^\s*(?:(?:(?P<h>\d+):)?(?P<m>\d{1,3}):)?(?P<s>\d{1,2})(?:[.,](?P<c>\d{1,2}))?\s*$"
)


class TempoNonValido(ValueError):
    """Stringa che non rappresenta un tempo di gara."""


def parse_tempo(testo: str | None) -> int:
    """Converte un tempo in centesimi.

    Accetta ``1:23.45``, ``0:32.10``, ``32.10``, ``32,10``, ``1:02:03.45`` e
    ``01:04.9`` (decimi). Rifiuta secondi >= 60 quando ci sono i minuti,
    stringhe vuote e qualunque altra forma.
    """
    if testo is None:
        raise TempoNonValido("tempo mancante")
    m = _RX_TEMPO.match(str(testo))
    if not m:
        raise TempoNonValido(f"formato tempo non valido: {testo!r}")
    ore = int(m.group("h") or 0)
    minuti = int(m.group("m") or 0)
    secondi = int(m.group("s"))
    cent = m.group("c") or "0"
    centesimi = int(cent.ljust(2, "0"))
    if (m.group("m") is not None) and secondi >= 60:
        raise TempoNonValido(f"secondi fuori scala in {testo!r}")
    if m.group("h") is not None and minuti >= 60:
        raise TempoNonValido(f"minuti fuori scala in {testo!r}")
    totale = ((ore * 60 + minuti) * 60 + secondi) * 100 + centesimi
    if totale <= 0:
        raise TempoNonValido(f"tempo nullo: {testo!r}")
    return totale


def prova_parse_tempo(testo: str | None) -> int | None:
    """Come :func:`parse_tempo` ma restituisce ``None`` invece di sollevare."""
    try:
        return parse_tempo(testo)
    except TempoNonValido:
        return None


def formatta(centesimi: int | None) -> str:
    """Centesimi -> ``M:SS.CC`` (o ``H:MM:SS.CC``), formato usato a DB e sul sito."""
    if centesimi is None:
        return ""
    cent = int(centesimi)
    secondi_tot, cc = divmod(cent, 100)
    minuti_tot, ss = divmod(secondi_tot, 60)
    ore, mm = divmod(minuti_tot, 60)
    if ore:
        return f"{ore}:{mm:02d}:{ss:02d}.{cc:02d}"
    return f"{minuti_tot}:{ss:02d}.{cc:02d}"


def a_decimal(centesimi: int) -> Decimal:
    """Centesimi -> ``Decimal`` in secondi per la colonna ``tempo_secondi``."""
    return (Decimal(int(centesimi)) / Decimal(100)).quantize(Decimal("0.01"))


def da_db(valore) -> int | None:
    """Valore di ``tempo_secondi`` letto da MySQL (Decimal/float/str) -> centesimi."""
    if valore is None:
        return None
    d = Decimal(str(valore)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)


def differenza(nuovo: int | None, precedente: int | None) -> int | None:
    """Differenza in centesimi (negativa = miglioramento)."""
    if nuovo is None or precedente is None:
        return None
    return int(nuovo) - int(precedente)


def formatta_differenza(diff: int | None) -> str:
    """``-123`` -> ``-1.23``; ``0`` -> ``0.00``; ``None`` -> ``""``."""
    if diff is None:
        return ""
    segno = "-" if diff < 0 else ("+" if diff > 0 else "")
    v = abs(int(diff))
    return f"{segno}{v // 100}.{v % 100:02d}"


# Intervalli di plausibilita' in secondi per distanza (gare individuali,
# squadra di categoria). Larghi apposta: servono a scovare errori di lettura
# del PDF, non a giudicare la prestazione.
PLAUSIBILITA = {
    50: (20, 120),
    100: (45, 240),
    200: (95, 480),
    400: (210, 900),
    800: (440, 1800),
    1500: (840, 3300),
}


def plausibile(centesimi: int, distanza: int) -> bool:
    """True se il tempo e' credibile per la distanza (vedi :data:`PLAUSIBILITA`)."""
    lim = PLAUSIBILITA.get(int(distanza))
    if lim is None:
        return True
    return lim[0] * 100 <= centesimi <= lim[1] * 100
