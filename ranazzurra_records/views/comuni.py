"""Pezzi condivisi dalle pagine: connessione per sessione, letture cachate, stile."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import repository as R
from ..config import config_mysql
from ..db import Database
from ..records import VASCHE

TTL = 60  # secondi: dopo ogni scrittura la cache si svuota comunque

CSS = """
<style>
    .main-header { font-size: 2.2rem; font-weight: bold; color: #1E88E5;
                   text-align: center; margin-bottom: 1.5rem; }
    div[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
"""

MEDAGLIE = {1: "🥇", 2: "🥈", 3: "🥉"}
COLORI_MEDAGLIA = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
SESSI = {"M": "Maschile", "F": "Femminile"}


def db() -> Database:
    """Una connessione per sessione utente (i connettori MySQL non sono
    thread-safe, e Streamlit serve ogni sessione su un thread suo)."""
    if "_db" not in st.session_state:
        st.session_state["_db"] = Database(config_mysql())
    return st.session_state["_db"]


def dopo_scrittura() -> None:
    st.cache_data.clear()


def intestazione(titolo: str) -> None:
    st.markdown(f'<div class="main-header">{titolo}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------- #
# Letture cachate (il parametro _db non entra nella chiave di cache)
# --------------------------------------------------------------------- #
@st.cache_data(ttl=TTL, show_spinner=False)
def atleti(_db: Database, solo_attivi: bool = False) -> pd.DataFrame:
    return R.atleti(_db, solo_attivi)


@st.cache_data(ttl=TTL, show_spinner=False)
def personali(_db: Database) -> pd.DataFrame:
    return R.personali(_db)


@st.cache_data(ttl=300, show_spinner=False)
def gare(_db: Database) -> list[dict]:
    return R.gare(_db)


@st.cache_data(ttl=300, show_spinner=False)
def tipi_vasca(_db: Database) -> dict[str, int]:
    return R.tipi_vasca(_db)


@st.cache_data(ttl=TTL, show_spinner=False)
def top3(_db: Database) -> pd.DataFrame:
    return R.top3(_db)


@st.cache_data(ttl=TTL, show_spinner=False)
def conteggi(_db: Database) -> dict:
    return R.conteggi(_db)


@st.cache_data(ttl=TTL, show_spinner=False)
def progressione(_db: Database, gara_id: int, tipo_vasca_id: int) -> pd.DataFrame:
    return R.progressione(_db, gara_id, tipo_vasca_id)


@st.cache_data(ttl=TTL, show_spinner=False)
def ultimi_personali(_db: Database, quanti: int = 10) -> pd.DataFrame:
    return R.ultimi_personali(_db, quanti)


# --------------------------------------------------------------------- #
# Formattazione
# --------------------------------------------------------------------- #
def data_it(val) -> str:
    if val is None or (not isinstance(val, str) and pd.isna(val)):
        return ""
    try:
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except Exception:
        return str(val)


def nome_vasca(codice: str) -> str:
    return VASCHE.get(codice, codice)


def card_record(row) -> str:
    """Card HTML di una riga di classifica (leggibile in tema chiaro e scuro)."""
    pos = int(row["posizione"])
    anno = f" <span style='color:#aaaaaa;'>({int(row['anno_nascita'])})</span>" \
        if pd.notna(row["anno_nascita"]) else ""
    data = data_it(row["data_record"])
    data = f" &nbsp;·&nbsp; {data}" if data else ""
    luogo = ""
    if pd.notna(row["luogo"]) and str(row["luogo"]).strip():
        luogo = f"<br/><span style='font-size:0.85em; color:#aaaaaa;'>📍 {row['luogo']}</span>"
    return f"""
    <div style="background-color:#1e2a3a; color:#f0f0f0; padding:0.8rem 1rem;
                border-radius:0.5rem; margin-bottom:0.7rem;
                border-left:5px solid {COLORI_MEDAGLIA.get(pos, '#888888')};
                font-family:sans-serif; line-height:1.5;">
        <span style="font-size:1.2em;">{MEDAGLIE.get(pos, '')}</span>
        <strong style="color:#ffffff; font-size:1.05em;"> {row['tempo_formattato']}</strong>
        <span style="color:#cccccc;"> · {row['cognome']} {row['nome']}{anno}{data}</span>
        {luogo}
    </div>
    """
