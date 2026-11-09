"""Applicazione controllata delle migrazioni SQL di ``db/migrations``.

Uso (dalla cartella del progetto, con ``.streamlit/secrets.toml`` compilato):

    python -m ranazzurra_records.migrazioni            # stato, nessuna scrittura
    python -m ranazzurra_records.migrazioni --applica  # backup + migrazioni mancanti

Prima di scrivere salva in ``backup/`` una copia JSON di ``atleti``,
``record_personali`` e ``record_societari``; dopo verifica che i conteggi di
quelle tabelle non siano cambiati. Le migrazioni aggiungono tabelle e colonne,
non toccano i dati esistenti.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .config import RADICE, ConfigurazioneMancante, config_mysql
from .db import Database

CARTELLA = RADICE / "db" / "migrations"
TABELLE_PROTETTE = ("atleti", "record_personali", "record_societari")


def migrazioni_disponibili() -> list[tuple[str, Path]]:
    out = []
    for p in sorted(CARTELLA.glob("*.sql")):
        m = re.match(r"^(\d{3})_", p.name)
        if m:
            out.append((m.group(1), p))
    return out


def migrazioni_applicate(db: Database) -> set[str]:
    if not db.tabella_esiste("schema_migrazioni"):
        return set()
    return {r["versione"] for r in db.query("SELECT versione FROM schema_migrazioni")}


def istruzioni(sql: str) -> list[str]:
    """Divide un file SQL in istruzioni (i file di migrazione non hanno
    punti e virgola dentro le stringhe, ne' DELIMITER)."""
    senza_commenti = "\n".join(
        r for r in sql.splitlines() if not r.strip().startswith("--")
    )
    return [s.strip() for s in senza_commenti.split(";") if s.strip()]


def _json_default(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def backup(db: Database, cartella: Path | None = None) -> Path:
    cartella = cartella or (RADICE / "backup")
    cartella.mkdir(parents=True, exist_ok=True)
    dati = {t: db.query(f"SELECT * FROM {t}") for t in TABELLE_PROTETTE if db.tabella_esiste(t)}
    p = cartella / f"backup_{datetime.now():%Y%m%d_%H%M%S}.json"
    p.write_text(json.dumps(dati, default=_json_default, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def conteggi(db: Database) -> dict[str, int]:
    return {t: db.query_uno(f"SELECT COUNT(*) AS n FROM {t}")["n"]
            for t in TABELLE_PROTETTE if db.tabella_esiste(t)}


def applica(db: Database, versione: str, percorso: Path) -> None:
    with db.cursore() as cur:
        for s in istruzioni(percorso.read_text(encoding="utf-8")):
            cur.execute(s)
            if cur.with_rows:
                cur.fetchall()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Migrazioni del database Ranazzurra Records")
    ap.add_argument("--applica", action="store_true", help="applica le migrazioni mancanti")
    ap.add_argument("--senza-backup", action="store_true", help="salta il backup JSON (sconsigliato)")
    args = ap.parse_args(argv)
    try:
        db = Database(config_mysql())
    except ConfigurazioneMancante as e:
        print(f"✗ {e}")
        return 2

    fatte = migrazioni_applicate(db)
    mancanti = [(v, p) for v, p in migrazioni_disponibili() if v not in fatte]
    for v, p in migrazioni_disponibili():
        print(f"  {'✓' if v in fatte else '·'} {p.name}")
    if not mancanti:
        print("Database aggiornato, niente da applicare.")
        return 0
    if not args.applica:
        print(f"{len(mancanti)} migrazioni da applicare. Rilancia con --applica.")
        return 0

    prima = conteggi(db)
    if not args.senza_backup:
        print(f"💾 Backup: {backup(db)}")
    for v, p in mancanti:
        print(f"▶ Applico {p.name}...")
        applica(db, v, p)
    dopo = conteggi(db)
    if prima != dopo:
        print(f"✗ ATTENZIONE: i conteggi sono cambiati {prima} -> {dopo}. Controlla il backup.")
        return 1
    print(f"✓ Fatto. Conteggi invariati: {dopo}")
    print(f"✓ Migrazioni registrate: {sorted(migrazioni_applicate(db))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
