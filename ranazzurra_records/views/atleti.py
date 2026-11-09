"""Gestione anagrafica atleti."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from .. import repository as R
from . import comuni as C

ANNO_MIN = 1900


def _scegli_atleta(df: pd.DataFrame, chiave: str, etichetta: str):
    if df.empty:
        return None
    ids = df["id"].tolist()
    per_id = df.set_index("id")
    return st.selectbox(
        etichetta, ids, key=chiave,
        format_func=lambda i: R.etichetta_atleta(per_id.loc[i]) + ("" if per_id.loc[i, "attivo"] else " · inattivo"),
    )


def _elenco(db) -> None:
    mostra_inattivi = st.checkbox("Mostra anche atleti inattivi", False)
    df = C.atleti(db, not mostra_inattivi)
    if df.empty:
        st.info("Nessun atleta presente nel database")
        return
    col1, col2, col3 = st.columns(3)
    with col1:
        sessi = st.multiselect("Sesso", options=["M", "F"], default=["M", "F"])
    with col2:
        cerca = st.text_input("🔍 Cerca (cognome o nome)")
    anni = df["anno_nascita"].dropna().astype(int)
    with col3:
        if anni.empty:
            intervallo = None
        else:
            lo, hi = int(anni.min()), int(anni.max())
            intervallo = st.slider("Anno di nascita", lo, max(hi, lo + 1), (lo, max(hi, lo + 1)))
    f = df.copy()
    if sessi:
        f = f[f["sesso"].isin(sessi)]
    if cerca:
        m = (f["cognome"].str.contains(cerca, case=False, na=False)
             | f["nome"].str.contains(cerca, case=False, na=False))
        f = f[m]
    if intervallo:
        # chi non ha l'anno resta visibile: il filtro non deve nascondere nessuno di nascosto
        f = f[f["anno_nascita"].isna() | f["anno_nascita"].between(*intervallo)]
    vista = pd.DataFrame({
        "Cognome": f["cognome"], "Nome": f["nome"], "Sesso": f["sesso"],
        "Anno nascita": C.anni(f["anno_nascita"]), "Attivo": f["attivo"],
    })
    st.dataframe(vista, use_container_width=True, hide_index=True)
    st.caption(f"Totale: {len(f)} atleti")


def _nuovo(db) -> None:
    with st.form("form_nuovo_atleta", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cognome = st.text_input("Cognome *", max_chars=100, placeholder="Rossi")
            sesso = st.selectbox("Sesso *", options=["M", "F"])
        with col2:
            nome = st.text_input("Nome *", max_chars=100, placeholder="Mario")
            anno = st.number_input("Anno di nascita *", min_value=ANNO_MIN,
                                   max_value=datetime.now().year, value=2012)
        note = st.text_area("Note", max_chars=500)
        if st.form_submit_button("💾 Salva atleta", use_container_width=True):
            if not cognome.strip() or not nome.strip():
                st.error("❌ Cognome e nome sono obbligatori.")
                return
            esito = R.inserisci_atleta(db, cognome.strip().title(), nome.strip().title(),
                                       sesso, int(anno), note.strip())
            (st.success if esito.ok else st.error)(esito.messaggio)
            if esito.ok:
                C.dopo_scrittura()


def _modifica(db) -> None:
    df = C.atleti(db, False)
    atleta_id = _scegli_atleta(df, "select_atleta_mod", "Atleta da modificare")
    if atleta_id is None:
        st.info("Nessun atleta disponibile")
        return
    a = df.set_index("id").loc[atleta_id]
    with st.form("form_modifica_atleta"):
        col1, col2 = st.columns(2)
        with col1:
            cognome = st.text_input("Cognome *", value=a["cognome"])
            sesso = st.selectbox("Sesso *", options=["M", "F"], index=0 if a["sesso"] == "M" else 1)
            attivo = st.checkbox("Attivo", value=bool(a["attivo"]))
        with col2:
            nome = st.text_input("Nome *", value=a["nome"])
            anno_val = int(a["anno_nascita"]) if pd.notna(a["anno_nascita"]) else 2012
            anno = st.number_input("Anno di nascita *", min_value=ANNO_MIN,
                                   max_value=datetime.now().year, value=anno_val)
        note = st.text_area("Note", value=a["note"] if pd.notna(a["note"]) else "", max_chars=500)
        if st.form_submit_button("💾 Aggiorna atleta", use_container_width=True):
            if not cognome.strip() or not nome.strip():
                st.error("❌ Cognome e nome sono obbligatori.")
                return
            esito = R.aggiorna_atleta(db, int(atleta_id), cognome.strip().title(), nome.strip().title(),
                                      sesso, int(anno), attivo, note.strip())
            (st.success if esito.ok else st.error)(esito.messaggio)
            if esito.ok:
                C.dopo_scrittura()


def _disattiva_elimina(db) -> None:
    df = C.atleti(db, False)
    atleta_id = _scegli_atleta(df, "select_atleta_del", "Atleta")
    if atleta_id is None:
        st.info("Nessun atleta disponibile")
        return
    a = df.set_index("id").loc[atleta_id]
    n = R.conta_personali(db, int(atleta_id))
    if n:
        st.info(f"{a['cognome']} {a['nome']} ha **{n} tempi** registrati: l'anagrafica si puo' "
                "disattivare (sparisce dagli elenchi degli attivi) ma non eliminare, "
                "per non perdere lo storico.")
        if not a["attivo"]:
            st.success("L'atleta e' gia' inattivo. Per riattivarlo usa la scheda Modifica.")
        elif st.button("🚫 Disattiva atleta", type="primary"):
            esito = R.disattiva_atleta(db, int(atleta_id))
            st.success(esito.messaggio)
            C.dopo_scrittura()
        return
    st.warning("Questo atleta non ha tempi registrati: l'anagrafica si puo' eliminare "
               "(per esempio un doppione inserito per errore).")
    conferma = st.text_input("Scrivi ELIMINA per confermare", key="conferma_elimina_atleta")
    if st.button("🗑️ Elimina anagrafica", type="primary"):
        if conferma.strip() != "ELIMINA":
            st.error("❌ Scrivi ELIMINA per confermare.")
            return
        esito = R.elimina_atleta_senza_tempi(db, int(atleta_id))
        (st.success if esito.ok else st.error)(esito.messaggio)
        if esito.ok:
            C.dopo_scrittura()


def mostra() -> None:
    st.header("👤 Gestione atleti")
    db = C.db()
    t1, t2, t3, t4 = st.tabs(["📋 Elenco", "➕ Nuovo atleta", "✏️ Modifica", "🚫 Disattiva / elimina"])
    with t1:
        _elenco(db)
    with t2:
        _nuovo(db)
    with t3:
        _modifica(db)
    with t4:
        _disattiva_elimina(db)
