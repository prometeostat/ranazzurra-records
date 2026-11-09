"""Costruzione di ``records.json`` per la pagina ``record_societari.html``.

Il formato del JSON e' un contratto con la pagina del sito: non cambiarlo
senza aggiornare anche la pagina. Per ogni vasca un elenco di gare, per ogni
gara gli array ``maschile`` e ``femminile`` con le righe in top 3 (gli ex
aequo condividono ``posizione``, quindi possono esserci piu' di tre righe).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import queries as Q
from .db import Database
from .records import chiave_ordinamento_gara

# Streamlit Cloud gira in UTC: l'orario di aggiornamento va scritto in ora
# italiana. Su Windows senza il pacchetto tzdata il fuso non c'e': li' lo
# script gira gia' in ora locale e basta l'orologio del PC.
try:
    FUSO = ZoneInfo("Europe/Rome")
except Exception:  # pragma: no cover - dipende dalla macchina
    FUSO = None


def _vuoto(val) -> bool:
    """None, NaN o NaT (le righe possono arrivare anche da un DataFrame)."""
    return val is None or (isinstance(val, float) and math.isnan(val)) or str(val) in {"NaT", "nan"}


def _data(val) -> str | None:
    if _vuoto(val):
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    return str(val)


def leggi_top3(db: Database) -> list[dict]:
    return db.query(Q.TOP3)


def costruisci_payload(righe: list[dict], adesso: datetime | None = None) -> dict:
    vasche: dict[str, dict] = {
        "VL": defaultdict(lambda: {"meta": {}, "M": [], "F": []}),
        "VC": defaultdict(lambda: {"meta": {}, "M": [], "F": []}),
    }
    for r in righe:
        if int(r["posizione"]) > 3:
            continue
        g = vasche[r["tipo_vasca"]][r["gara"]]
        g["meta"] = {"distanza": int(r["distanza"]), "stile": r["stile"]}
        g[r["sesso"]].append({
            "posizione": int(r["posizione"]),
            "cognome": r["cognome"],
            "nome": r["nome"],
            "anno_nascita": None if _vuoto(r["anno_nascita"]) else int(r["anno_nascita"]),
            "tempo": r["tempo_formattato"],
            "data": _data(r["data_record"]),
            "luogo": "" if _vuoto(r["luogo"]) else r["luogo"],
            "manifestazione": "" if _vuoto(r["manifestazione"]) else r["manifestazione"],
        })

    def elenco(vasca: dict) -> list[dict]:
        nomi = sorted(vasca, key=lambda n: chiave_ordinamento_gara(
            vasca[n]["meta"].get("stile", ""), vasca[n]["meta"].get("distanza", 0)))
        out = []
        for n in nomi:
            for s in ("M", "F"):
                vasca[n][s].sort(key=lambda x: (x["posizione"], x["cognome"], x["nome"]))
            out.append({
                "gara": n,
                "distanza": vasca[n]["meta"].get("distanza"),
                "stile": vasca[n]["meta"].get("stile"),
                "maschile": vasca[n]["M"],
                "femminile": vasca[n]["F"],
            })
        return out

    return {
        "vasca_lunga": elenco(vasche["VL"]),
        "vasca_corta": elenco(vasche["VC"]),
        "aggiornato": (adesso or datetime.now(FUSO)).strftime("%d/%m/%Y %H:%M"),
    }
