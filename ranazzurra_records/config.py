"""Configurazione: credenziali e parametri letti da secrets o variabili d'ambiente.

Nessuna credenziale sta nel codice. L'ordine di lettura e':

1. ``st.secrets`` quando il codice gira dentro Streamlit (Community Cloud o
   ``streamlit run`` in locale);
2. il file ``.streamlit/secrets.toml`` (stessa struttura), per gli script
   lanciati a mano come ``esporta_records.py``;
3. le variabili d'ambiente, che vincono su tutto il resto (utili nei test).

Struttura di ``secrets.toml``: vedi ``.streamlit/secrets.toml.example``.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

RADICE = Path(__file__).resolve().parent.parent
FILE_SECRETS = RADICE / ".streamlit" / "secrets.toml"


class ConfigurazioneMancante(RuntimeError):
    """Manca una sezione o una chiave obbligatoria nei secrets."""


def _secrets_streamlit() -> dict | None:
    try:
        import streamlit as st
        from streamlit import runtime

        if not runtime.exists():
            return None
        return st.secrets.to_dict()
    except Exception:  # secrets assenti o streamlit non installato
        return None


def leggi_secrets(percorso: Path | None = None) -> dict:
    """Tutti i secrets disponibili come dizionario (vuoto se non ce ne sono)."""
    da_st = _secrets_streamlit()
    if da_st is not None and percorso is None:
        return da_st
    p = percorso or FILE_SECRETS
    if p.exists():
        with p.open("rb") as f:
            return tomllib.load(f)
    return {}


def _env_bool(nome: str) -> bool | None:
    v = os.environ.get(nome)
    if v is None:
        return None
    return v.strip().lower() in {"1", "true", "yes", "si", "sì"}


def _risolvi_ssl_ca(valore: str | None) -> str | None:
    """Il certificato CA puo' essere un percorso (relativo alla radice del
    progetto o assoluto) oppure il PEM incollato direttamente nei secrets."""
    if not valore:
        return None
    valore = str(valore).strip()
    if valore.startswith("-----BEGIN"):
        f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        f.write(valore if valore.endswith("\n") else valore + "\n")
        f.close()
        return f.name
    p = Path(valore)
    if not p.is_absolute():
        p = RADICE / p
    return str(p) if p.exists() else None


@dataclass(frozen=True)
class ConfigMySQL:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    ssl_ca: str | None = None
    ssl_disabled: bool = False

    def parametri_connessione(self) -> dict:
        p = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "ssl_disabled": self.ssl_disabled,
            "connection_timeout": 15,
            "autocommit": True,
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
        }
        if self.ssl_ca and not self.ssl_disabled:
            p["ssl_ca"] = self.ssl_ca
        return p


def config_mysql(secrets: dict | None = None) -> ConfigMySQL:
    s = (secrets if secrets is not None else leggi_secrets()).get("mysql", {})
    env = os.environ
    valori = {
        "host": env.get("MYSQL_HOST", s.get("host")),
        "port": int(env.get("MYSQL_PORT", s.get("port", 3306))),
        "database": env.get("MYSQL_DATABASE", s.get("database")),
        "user": env.get("MYSQL_USER", s.get("user")),
        "password": env.get("MYSQL_PASSWORD", s.get("password")),
    }
    mancanti = [k for k, v in valori.items() if v in (None, "")]
    if mancanti:
        raise ConfigurazioneMancante(
            "Configurazione MySQL incompleta, mancano: " + ", ".join(mancanti)
            + ". Compila la sezione [mysql] di .streamlit/secrets.toml "
            "(o i secrets di Streamlit Cloud) oppure le variabili MYSQL_*."
        )
    ssl_disabled = _env_bool("MYSQL_SSL_DISABLED")
    if ssl_disabled is None:
        ssl_disabled = bool(s.get("ssl_disabled", False))
    return ConfigMySQL(
        ssl_ca=_risolvi_ssl_ca(env.get("MYSQL_SSL_CA", s.get("ssl_ca"))),
        ssl_disabled=ssl_disabled,
        **valori,
    )


@dataclass(frozen=True)
class ConfigFTP:
    host: str
    user: str
    password: str = field(repr=False)
    cartella: str = "/public_html/records"
    tls: bool = True


def config_ftp(secrets: dict | None = None) -> ConfigFTP:
    s = (secrets if secrets is not None else leggi_secrets()).get("ftp", {})
    env = os.environ
    host = env.get("FTP_HOST", s.get("host"))
    user = env.get("FTP_USER", s.get("user"))
    password = env.get("FTP_PASSWORD", s.get("password"))
    if not (host and user and password):
        raise ConfigurazioneMancante(
            "Configurazione FTP incompleta: servono host, user e password nella "
            "sezione [ftp] di .streamlit/secrets.toml o nelle variabili FTP_*."
        )
    tls = _env_bool("FTP_TLS")
    if tls is None:
        tls = bool(s.get("tls", True))
    return ConfigFTP(
        host=host,
        user=user,
        password=password,
        cartella=env.get("FTP_CARTELLA", s.get("cartella", "/public_html/records")),
        tls=tls,
    )


@dataclass(frozen=True)
class ConfigDrive:
    folder_id: str
    service_account: dict = field(repr=False)
    profondita_massima: int = 3


def config_drive(secrets: dict | None = None) -> ConfigDrive | None:
    """Configurazione Google Drive, oppure ``None`` se non e' impostata
    (in quel caso l'app offre solo il caricamento manuale del PDF)."""
    s = (secrets if secrets is not None else leggi_secrets()).get("gdrive", {})
    env = os.environ
    folder_id = env.get("GDRIVE_FOLDER_ID", s.get("folder_id"))
    sa = s.get("service_account")
    file_sa = env.get("GDRIVE_SERVICE_ACCOUNT_FILE", s.get("service_account_file"))
    if not sa and file_sa:
        import json

        p = Path(file_sa)
        if not p.is_absolute():
            p = RADICE / p
        if p.exists():
            sa = json.loads(p.read_text(encoding="utf-8"))
    if not folder_id or not sa:
        return None
    return ConfigDrive(
        folder_id=folder_id,
        service_account=dict(sa),
        profondita_massima=int(s.get("profondita_massima", 3)),
    )
