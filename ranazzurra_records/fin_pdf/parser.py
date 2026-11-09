"""Parser dei PDF dei risultati FIN (riepiloghi del portale finveneto.org).

Adattato da ``import_risultati.py`` del progetto Master Conegliano
(``prometeostat/ranazzurra_streamlit``), dove e' stato validato su decine di
manifestazioni reali; le regole sono le stesse, il codice e' riscritto per
questo progetto. Le differenze: niente database e niente domande a terminale
(il modulo restituisce solo dati), si conserva la posizione in classifica, il
luogo, il cronometraggio e la data di ogni gara, e si tengono soltanto le
righe della societa' RANAZZURRA CONEGLIANO SSD.

Impaginati riconosciuti (lo dice l'intestazione di colonna, non il nome del file):

- ``RISULTATI RIEPILOGATIVI`` con colonne ``Pos Ser. Cor Atleta Anno Societa' Tempo Pti``;
- ``Risultati completi per Categoria`` con colonne ``Pos Cognome e nome Anno ...``
  (sola posizione, con i parziali incollati prima del tempo finale).

Le pagine di continuazione non ripetono il titolo: ereditano la gara precedente.
Le staffette vengono riconosciute e ignorate (i record sono individuali).
Un PDF senza testo (scansione) viene rifiutato: l'OCR non e' supportato.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from .. import tempi

# Societa' importata. Le varianti grafiche (S.S.D., SSD A R.L., codice
# numerico davanti) si normalizzano prima del confronto.
SOCIETA = "RANAZZURRA CONEGLIANO"

# --------------------------------------------------------------------- #
# Espressioni regolari
# --------------------------------------------------------------------- #
RX_TEMPO = r"\d{1,3}:\d{2}:\d{2}\.\d{1,2}|\d{1,3}:\d{2}\.\d{1,2}|\d{1,2}\.\d{1,2}"
RX_STATI = r"ASS|SQS?|SQU|DSQ|RIT|RT|NP|NC|Da disp\."

# Pos Ser Cor ATLETA ANNO [REG] SOCIETA' TEMPO [FG] [PTI]
RX_RIGA_3 = re.compile(
    r"^(?P<pos>\d+|-)\s+\d+\s+\d+\s+(?P<atleta>.+?)\s+(?P<anno>(?:19|20)\d{2})\s+"
    r"(?:[A-Z]{2,3}\s+)?(?P<soc>.+?)\s+(?P<tempo>" + RX_TEMPO + r")(?P<fg>\s+FG)?"
    r"(?:\s+\d{1,4}(?:\.\d{1,2})?)?\s*$"
)
RX_RIGA_3_NT = re.compile(
    r"^(?P<pos>\d+|-)\s+\d+\s+\d+\s+(?P<atleta>.+?)\s+(?P<anno>(?:19|20)\d{2})\s+"
    r"(?:[A-Z]{2,3}\s+)?(?P<soc>.+?)\s+(?P<stato>" + RX_STATI + r")\s*$"
)
# Pos ATLETA ANNO [REG] SOCIETA' [parziali] TEMPO [FG] [PTI]
RX_RIGA_1 = re.compile(
    r"^(?P<pos>\d+|-)\s+(?P<atleta>.+?)\s+(?P<anno>(?:19|20)\d{2})\s+(?:[A-Z]{2,3}\s+)?"
    r"(?P<soc>.+?)\s+(?:(?:" + RX_TEMPO + r")\s*)*?(?P<tempo>" + RX_TEMPO + r")(?P<fg>\s+FG)?"
    r"(?:\s+\d{1,4}(?:\.\d{1,2})?)?\s*$"
)
RX_RIGA_1_NT = re.compile(
    r"^(?P<pos>\d+|-)\s+(?P<atleta>.+?)\s+(?P<anno>(?:19|20)\d{2})\s+(?:[A-Z]{2,3}\s+)?"
    r"(?P<soc>.+?)\s+(?P<stato>" + RX_STATI + r")\s*$"
)
RX_COLONNE_UNA_POS = re.compile(r"^Pos\s+(Cognome|Atleta|Nome)\b", re.I)
RX_COLONNE_TRE_POS = re.compile(r"^Pos\b.*\b(?:Ser\.?|Cor)\b.*\b(?:Ser\.?|Cor)\b", re.I)
RX_INTESTAZIONE = re.compile(r"RISULTATI RIEPILOGATIVI|Risultati completi", re.I)
RX_PRIMA_DEL_TITOLO = re.compile(r"^Foglio n\.|^\d{2}/\d{2}/\d{4}\s*$")
RX_PAGINE_DA_SALTARE = re.compile(r"^(Programma gare|Statistiche|Classifica)|^\d+\s*[°º]\s")
RX_LUOGO_DATA = re.compile(
    r"^(?P<luogo>[^,]+?)\s*,\s*(?:Luned[iì]|Marted[iì]|Mercoled[iì]|Gioved[iì]|Venerd[iì]|Sabato|Domenica)"
    r"[, ]+(?P<data>\d{2}/\d{2}/\d{4})", re.I)
RX_DATA = re.compile(r"(\d{2}/\d{2}/\d{4})")
RX_CRON = re.compile(r"Cron\.?:\s*([AM])\b")
RX_BASE_VASCA = re.compile(r"Base v\.?:\s*(\d+)")
RX_TURNO = re.compile(r"\b(finale\s*[a-d]?|semifinal[ei]|batterie|eliminatorie)\b", re.I)

STATI = {
    "SQ": "SQ", "SQS": "SQ", "SQU": "SQ", "DSQ": "SQ",
    "RIT": "RIT", "RT": "RIT",
    "NP": "NP", "NC": "NC",
    "ASS": "ASS", "DA DISP.": "ASS",
}


class PDFNonLeggibile(ValueError):
    """Il PDF non e' un riepilogo risultati FIN leggibile."""


@dataclass
class RigaFIN:
    nome: str            # "COGNOME NOME" come scritto nel PDF, spazi normalizzati
    anno: int
    societa: str
    posizione: int | None
    tempo: int | None    # centesimi; None se c'e' uno stato (SQ, RIT, ...)
    stato: str           # OK, SQ, RIT, NP, NC, ASS
    fuori_gara: bool
    pagina: int
    testo: str


@dataclass
class GaraFIN:
    titolo: str
    stile: str | None        # codice DB: DF, DO, RA, SL, MX
    distanza: int | None
    sesso: str | None        # M, F, X (mista) o None se il titolo non lo dice
    vasca_metri: int | None  # 25 o 50
    staffetta: bool
    cronometraggio: str | None  # A automatico, M manuale
    data: date | None
    luogo: str | None
    turno: str
    pagina: int
    righe: list[RigaFIN] = field(default_factory=list)      # solo la nostra societa'
    righe_totali: int = 0                                    # tutte le societa'
    altre_ranazzurra: list[str] = field(default_factory=list)


@dataclass
class DocumentoFIN:
    nome: str
    data_inizio: date | None
    data_fine: date | None
    luogo: str | None
    pagine: int
    sha256: str
    gare: list[GaraFIN]
    anomalie: list[str]

    @property
    def righe_totali(self) -> int:
        return sum(g.righe_totali for g in self.gare)

    @property
    def righe_nostre(self) -> list[tuple[GaraFIN, RigaFIN]]:
        return [(g, r) for g in self.gare for r in g.righe]


# --------------------------------------------------------------------- #
def _spazi(s: str) -> str:
    return " ".join(s.split())


def normalizza_societa(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"^\d{1,5}\s+", "", s.strip())  # codice numerico del club fuso nel nome
    s = s.replace(".", " ")
    return _spazi(s)


def e_nostra(societa: str) -> bool:
    return normalizza_societa(societa).startswith(SOCIETA)


def _stile(titolo: str) -> str | None:
    t = titolo.lower()
    if "stile" in t or re.search(r"\bsl\b", t):
        return "SL"
    if "dorso" in t:
        return "DO"
    if "rana" in t:
        return "RA"
    if "farfalla" in t or "delfino" in t:
        return "DF"
    if re.search(r"mist(i|a)\b|misti|mixed", t):
        return "MX"
    return None


def _sesso(titolo: str) -> str | None:
    t = titolo.lower()
    if "femmine" in t and "maschi" in t:
        return "X"
    if "femmin" in t:
        return "F"
    if "maschi" in t:
        return "M"
    if re.search(r"\bmx\b", t) or "mixed" in t or "mistaff" in t:
        return "X"
    return None


def interpreta_titolo(titolo: str) -> dict:
    t = titolo.lower()
    staffetta = "staff" in t or bool(re.search(r"\d+\s*x\s*\d+", t))
    m = re.search(r"\b(\d{2,4})\b", titolo)
    turno = RX_TURNO.search(titolo)
    return {
        "stile": _stile(titolo),
        "distanza": int(m.group(1)) if m and not staffetta else None,
        "sesso": _sesso(titolo),
        "staffetta": staffetta,
        "turno": _spazi(turno.group(1).upper()) if turno else "",
    }


def _riga(testo: str, una_pos: bool, pagina: int) -> RigaFIN | None:
    # Nell'impaginato a tre colonne si prova solo quello: la regex a una
    # colonna leggerebbe serie e corsia come parte del nome. Nell'impaginato
    # a una colonna si riprova con l'altro se l'intestazione era cambiata.
    formati = [(RX_RIGA_1, RX_RIGA_1_NT), (RX_RIGA_3, RX_RIGA_3_NT)] if una_pos \
        else [(RX_RIGA_3, RX_RIGA_3_NT)]
    for rx, rx_nt in formati:
        m = rx.match(testo)
        if m:
            return RigaFIN(
                nome=_spazi(m.group("atleta").upper()), anno=int(m.group("anno")),
                societa=_spazi(m.group("soc")),
                posizione=None if m.group("pos") == "-" else int(m.group("pos")),
                tempo=tempi.prova_parse_tempo(m.group("tempo")), stato="OK",
                fuori_gara=bool(m.group("fg")), pagina=pagina, testo=testo,
            )
        m = rx_nt.match(testo)
        if m:
            return RigaFIN(
                nome=_spazi(m.group("atleta").upper()), anno=int(m.group("anno")),
                societa=_spazi(m.group("soc")),
                posizione=None if m.group("pos") == "-" else int(m.group("pos")),
                tempo=None, stato=STATI.get(m.group("stato").upper(), m.group("stato").upper()),
                fuori_gara=False, pagina=pagina, testo=testo,
            )
    return None


def _e_titolo(testo: str) -> bool:
    """La prima riga utile dopo l'intestazione e' il titolo di una gara,
    a meno che sia gia' un risultato (pagina di continuazione)."""
    if any(rx.match(testo) for rx in (RX_RIGA_3, RX_RIGA_3_NT, RX_RIGA_1, RX_RIGA_1_NT)):
        return False
    if re.match(r"^[A-ZÀÈÉÌÒÙ' ]+ (19|20)\d{2}", testo):  # frazionista di staffetta
        return False
    if testo.startswith("Categoria "):
        return False
    return True


def _data(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


def leggi_pdf(contenuto: bytes) -> DocumentoFIN:
    """Analizza il PDF e restituisce le gare con le sole righe della societa'."""
    import pdfplumber

    sha = hashlib.sha256(contenuto).hexdigest()
    gare: list[GaraFIN] = []
    anomalie: list[str] = []
    nome = None
    data_stampa = None
    una_pos = False
    pagine_con_testo = 0

    try:
        pdf = pdfplumber.open(io.BytesIO(contenuto))
    except Exception as e:
        raise PDFNonLeggibile(f"Il file non e' un PDF valido ({e}).") from e
    with pdf:
        n_pagine = len(pdf.pages)
        for n_pag, pagina in enumerate(pdf.pages, start=1):
            righe = [r.strip() for r in (pagina.extract_text() or "").splitlines() if r.strip()]
            if righe:
                pagine_con_testo += 1
            else:
                continue
            if nome is None:
                nome = _spazi(re.sub(r"\s+Foglio n\..*$", "", righe[0]))
                m = next((RX_DATA.search(r) for r in righe[:4] if RX_DATA.search(r)), None)
                data_stampa = _data(m.group(1)) if m else None

            for r in righe:
                if RX_COLONNE_UNA_POS.match(r):
                    una_pos = True
                elif RX_COLONNE_TRE_POS.match(r):
                    una_pos = False

            idx = next((i for i, r in enumerate(righe) if RX_INTESTAZIONE.search(r)), None)
            if idx is None:
                continue
            dopo = next((r for r in righe[idx + 1:] if not RX_PRIMA_DEL_TITOLO.match(r)), "")
            if RX_PAGINE_DA_SALTARE.match(dopo):
                continue

            testo_pagina = "\n".join(righe)
            if _e_titolo(dopo):
                info = interpreta_titolo(dopo)
                m_ld = next((RX_LUOGO_DATA.search(r) for r in righe if RX_LUOGO_DATA.search(r)), None)
                m_cron = RX_CRON.search(testo_pagina)
                m_base = RX_BASE_VASCA.search(testo_pagina)
                gare.append(GaraFIN(
                    titolo=dopo, stile=info["stile"], distanza=info["distanza"],
                    sesso=info["sesso"], staffetta=info["staffetta"], turno=info["turno"],
                    vasca_metri=int(m_base.group(1)) if m_base else None,
                    cronometraggio=m_cron.group(1) if m_cron else None,
                    data=_data(m_ld.group("data")) if m_ld else None,
                    luogo=_spazi(m_ld.group("luogo")) if m_ld else None,
                    pagina=n_pag,
                ))
            elif not gare:
                anomalie.append(f"pag. {n_pag}: risultati prima di qualsiasi titolo di gara")
                continue
            gara = gare[-1]
            if gara.staffetta:
                continue  # i record societari sono individuali

            for r in righe:
                letta = _riga(r, una_pos, n_pag)
                if letta is None:
                    if "RANAZZURRA" in r.upper() and re.search(r"(19|20)\d{2}", r):
                        anomalie.append(f"pag. {n_pag}: riga non interpretata: {r}")
                    continue
                gara.righe_totali += 1
                if e_nostra(letta.societa):
                    gara.righe.append(letta)
                elif "RANAZZURRA" in normalizza_societa(letta.societa):
                    gara.altre_ranazzurra.append(f"{letta.nome} ({letta.societa})")

    if pagine_con_testo == 0:
        raise PDFNonLeggibile(
            "Il PDF non contiene testo: probabilmente e' una scansione. "
            "Serve il PDF originale pubblicato dalla FIN (l'OCR non e' supportato)."
        )
    if not gare:
        raise PDFNonLeggibile(
            "Nel PDF non ho trovato gare: non sembra un riepilogo risultati FIN "
            "(cerco l'intestazione 'RISULTATI RIEPILOGATIVI' o 'Risultati completi')."
        )
    date_gare = [g.data for g in gare if g.data]
    luoghi = [g.luogo for g in gare if g.luogo]
    return DocumentoFIN(
        nome=nome or "Manifestazione senza nome",
        data_inizio=min(date_gare) if date_gare else data_stampa,
        data_fine=max(date_gare) if date_gare else data_stampa,
        luogo=max(set(luoghi), key=luoghi.count) if luoghi else None,
        pagine=n_pagine,
        sha256=sha,
        gare=gare,
        anomalie=anomalie,
    )
