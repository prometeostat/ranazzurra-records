"""Gestione dei personali (tabella record_personali)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .. import repository as R
from . import comuni as C

DATA_MIN = date(1900, 1, 1)
DATA_MAX = date(2100, 12, 31)


def _etichetta_personale(r) -> str:
    return f"{r['cognome']} {r['nome']} · {r['gara']} ({r['tipo_vasca']}) · {r['tempo_formattato']}"


def _elenco(db) -> None:
    df = C.personali(db)
    if df.empty:
        st.info("Nessun tempo registrato")
        return
    df = df.copy()
    df["atleta"] = df.apply(lambda r: R.etichetta_atleta(r), axis=1)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        atleta = st.selectbox("Atleta", ["Tutti"] + sorted(df["atleta"].unique()))
    with col2:
        vasca = st.selectbox("Vasca", ["Tutte", "VC", "VL"])
    with col3:
        stile = st.selectbox("Stile", ["Tutti", "SL", "DO", "RA", "DF", "MX"])
    with col4:
        sesso = st.selectbox("Sesso", ["Tutti", "M", "F"])
    f = df
    if atleta != "Tutti":
        f = f[f["atleta"] == atleta]
    if vasca != "Tutte":
        f = f[f["tipo_vasca"] == vasca]
    if stile != "Tutti":
        f = f[f["stile"] == stile]
    if sesso != "Tutti":
        f = f[f["sesso"] == sesso]
    vista = pd.DataFrame({
        "Cognome": f["cognome"], "Nome": f["nome"], "Vasca": f["tipo_vasca"], "Gara": f["gara"],
        "Tempo": f["tempo_formattato"], "Data": f["data_record"].map(C.data_it),
        "Luogo": f["luogo"].fillna(""), "Manifestazione": f["manifestazione"].fillna(""),
    })
    st.dataframe(vista, use_container_width=True, hide_index=True)
    st.caption(f"Totale: {len(f)} tempi")
    st.download_button("📥 Esporta in CSV", vista.to_csv(index=False).encode("utf-8"),
                       file_name="record_personali.csv", mime="text/csv")


def _nuovo(db) -> None:
    atleti = C.atleti(db, True)
    if atleti.empty:
        st.warning("⚠️ Nessun atleta attivo. Inserisci prima l'atleta.")
        return
    per_id = atleti.set_index("id")
    gare = C.gare(db)
    with st.form("form_nuovo_record", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            atleta_id = st.selectbox("Atleta *", atleti["id"].tolist(),
                                     format_func=lambda i: R.etichetta_atleta(per_id.loc[i]))
            vasca = st.selectbox("Tipo vasca *", ["VC", "VL"], format_func=C.nome_vasca)
            tempo = st.text_input("Tempo *", placeholder="1:23.45 o 0:32.10",
                                  help="Formato M:SS.CC (anche SS.CC sotto il minuto)")
        with col2:
            gara = st.selectbox("Gara *", gare, format_func=lambda g: g["descrizione"])
            data_rec = st.date_input("Data", value=None, min_value=DATA_MIN, max_value=DATA_MAX,
                                     format="DD/MM/YYYY")
            luogo = st.text_input("Luogo", placeholder="Citta', piscina")
        manifestazione = st.text_input("Manifestazione")
        note = st.text_area("Note", max_chars=500)
        sovrascrivi = st.checkbox(
            "Correzione: sostituisci il personale anche se il nuovo tempo e' piu' lento",
            help="Da usare solo per correggere un tempo registrato per errore.")
        if st.form_submit_button("💾 Salva tempo", use_container_width=True):
            if not tempo.strip():
                st.error("❌ Il tempo e' obbligatorio.")
                return
            esito = R.salva_personale_manuale(db, int(atleta_id), int(gara["id"]), vasca, tempo,
                                              data_rec, luogo.strip(), manifestazione.strip(),
                                              note.strip(), sovrascrivi_peggiore=sovrascrivi)
            (st.success if esito.ok else st.warning)(esito.messaggio)
            if esito.ok:
                C.dopo_scrittura()


def _modifica(db) -> None:
    df = C.personali(db)
    if df.empty:
        st.info("Nessun tempo da modificare")
        return
    per_id = df.set_index("id")
    rid = st.selectbox("Tempo da modificare", df["id"].tolist(), key="select_record_mod",
                       format_func=lambda i: _etichetta_personale(per_id.loc[i]))
    r = per_id.loc[rid]
    st.caption("Qui si corregge un dato registrato: il tempo viene sostituito anche se piu' lento.")
    with st.form("form_modifica_record"):
        col1, col2 = st.columns(2)
        with col1:
            tempo = st.text_input("Tempo *", value=r["tempo_formattato"])
            data_val = pd.to_datetime(r["data_record"]).date() if pd.notna(r["data_record"]) else None
            data_rec = st.date_input("Data", value=data_val, min_value=DATA_MIN, max_value=DATA_MAX,
                                     format="DD/MM/YYYY")
        with col2:
            luogo = st.text_input("Luogo", value=r["luogo"] if pd.notna(r["luogo"]) else "")
            manif = st.text_input("Manifestazione",
                                  value=r["manifestazione"] if pd.notna(r["manifestazione"]) else "")
        note = st.text_area("Note", value=r["note"] if pd.notna(r["note"]) else "", max_chars=500)
        if st.form_submit_button("💾 Aggiorna", use_container_width=True):
            esito = R.correggi_personale(db, int(rid), tempo, data_rec, luogo.strip(),
                                         manif.strip(), note.strip())
            (st.success if esito.ok else st.error)(esito.messaggio)
            if esito.ok:
                C.dopo_scrittura()


def _elimina(db) -> None:
    df = C.personali(db)
    if df.empty:
        st.info("Nessun tempo da eliminare")
        return
    per_id = df.set_index("id")
    st.warning("⚠️ L'eliminazione e' definitiva.")
    rid = st.selectbox("Tempo da eliminare", df["id"].tolist(), key="select_record_del",
                       format_func=lambda i: _etichetta_personale(per_id.loc[i]))
    conferma = st.text_input("Scrivi ELIMINA per confermare", key="conferma_elimina_record")
    if st.button("🗑️ Elimina definitivamente", type="primary"):
        if conferma.strip() != "ELIMINA":
            st.error("❌ Scrivi ELIMINA per confermare.")
            return
        esito = R.elimina_personale(db, int(rid))
        st.success(esito.messaggio)
        C.dopo_scrittura()


def mostra() -> None:
    st.header("🏅 Gestione personali")
    db = C.db()
    t1, t2, t3, t4 = st.tabs(["📋 Elenco", "➕ Nuovo tempo", "✏️ Modifica", "🗑️ Elimina"])
    with t1:
        _elenco(db)
    with t2:
        _nuovo(db)
    with t3:
        _modifica(db)
    with t4:
        _elimina(db)
