"""
esporta_records.py
──────────────────
Legge i record societari (top 3) dal database, genera ``records.json`` e lo
carica via FTP sul sito Register.it, dove lo legge ``record_societari.html``.

Uso (dalla cartella del progetto):
    python esporta_records.py                # genera e carica
    python esporta_records.py --solo-locale  # genera soltanto, niente FTP
    python esporta_records.py --output percorso/records.json

Credenziali: sezioni [mysql] e [ftp] di .streamlit/secrets.toml (vedi
.streamlit/secrets.toml.example) oppure variabili MYSQL_* e FTP_*.
Nessuna credenziale va scritta in questo file.
"""

from __future__ import annotations

import argparse
import ftplib
import io
import json
import sys
from pathlib import Path

from ranazzurra_records.config import ConfigurazioneMancante, config_ftp, config_mysql
from ranazzurra_records.db import Database
from ranazzurra_records.export import costruisci_payload, leggi_top3


def carica_ftp(contenuto: bytes) -> None:
    cfg = config_ftp()
    print(f"📤 Connessione FTP{' (TLS)' if cfg.tls else ''} a {cfg.host}...")
    ftp = ftplib.FTP_TLS() if cfg.tls else ftplib.FTP()
    try:
        ftp.connect(cfg.host, 21, timeout=30)
        ftp.login(cfg.user, cfg.password)
        if cfg.tls:
            ftp.prot_p()  # cifra anche il canale dati
        ftp.set_pasv(True)
        try:
            ftp.cwd(cfg.cartella)
        except ftplib.error_perm:
            print(f"   ⚠ Cartella '{cfg.cartella}' non trovata, provo a crearla...")
            ftp.mkd(cfg.cartella)
            ftp.cwd(cfg.cartella)
        ftp.storbinary("STOR records.json", io.BytesIO(contenuto))
        print(f"   ✓ records.json caricato ({len(contenuto):,} byte)")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Esporta i record societari per il sito")
    ap.add_argument("--solo-locale", action="store_true", help="genera il file senza caricarlo via FTP")
    ap.add_argument("--output", default="records.json", help="percorso del file locale (default: records.json)")
    args = ap.parse_args(argv)

    print("=" * 55)
    print("  Esportazione Record Societari — Ranazzurra")
    print("=" * 55)
    try:
        db = Database(config_mysql())
        print("📡 Lettura dal database...")
        righe = leggi_top3(db)
        db.chiudi()
    except ConfigurazioneMancante as e:
        print(f"✗ {e}")
        return 2
    print(f"   ✓ {len(righe)} righe in top 3")

    payload = costruisci_payload(righe)
    testo = json.dumps(payload, ensure_ascii=False, indent=2)
    Path(args.output).write_text(testo, encoding="utf-8")
    print(f"   ✓ {args.output} salvato in locale")

    if not args.solo_locale:
        try:
            carica_ftp(testo.encode("utf-8"))
        except ConfigurazioneMancante as e:
            print(f"✗ {e}")
            return 2
        except (ftplib.all_errors) as e:  # type: ignore[misc]
            print(f"✗ Caricamento FTP non riuscito: {e}")
            print("  Se Register.it non accetta FTP su TLS imposta tls = false nella sezione [ftp].")
            return 1

    print()
    print(f"✅ Fatto. Aggiornato alle {payload['aggiornato']}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    sys.exit(main())
