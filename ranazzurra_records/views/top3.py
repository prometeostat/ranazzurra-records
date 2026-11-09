"""Record Top 3: la stessa classifica pubblicata sul sito, con ex aequo."""

from __future__ import annotations

import json

import streamlit as st

from ..export import costruisci_payload
from ..records import chiave_ordinamento_gara
from . import comuni as C


def _vasca(top, codice: str) -> None:
    df = top[top["tipo_vasca"] == codice]
    if df.empty:
        st.warning("Nessun record disponibile per questa vasca")
        return
    gare = (df[["gara", "stile", "distanza"]].drop_duplicates()
            .assign(ord=lambda d: d.apply(lambda r: chiave_ordinamento_gara(r["stile"], r["distanza"]), axis=1))
            .sort_values("ord"))
    for _, g in gare.iterrows():
        st.markdown(f"#### {g['gara']}")
        col_m, col_f = st.columns(2)
        for col, sesso in ((col_m, "M"), (col_f, "F")):
            with col:
                st.markdown(f"**{'🔵' if sesso == 'M' else '🔴'} {C.SESSI[sesso]}**")
                righe = df[(df["gara"] == g["gara"]) & (df["sesso"] == sesso)].sort_values(["posizione", "cognome"])
                if righe.empty:
                    st.info(f"Nessun record {C.SESSI[sesso].lower()}")
                for _, r in righe.iterrows():
                    st.markdown(C.card_record(r), unsafe_allow_html=True)
        st.markdown("---")


def mostra() -> None:
    C.intestazione("🏆 Record Societari Top 3")
    st.info("📊 I migliori 3 tempi della societa' per ciascuna gara, divisi per vasca e sesso. "
            "Gli ex aequo condividono la posizione.")
    db = C.db()
    top = C.top3(db)
    if top.empty:
        st.warning("Nessun tempo registrato.")
        return

    payload = costruisci_payload(top.to_dict("records"))
    st.download_button(
        "⬇️ Scarica records.json per il sito",
        data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="records.json", mime="application/json",
        help="Lo stesso file che genera esporta_records.py. Per pubblicarlo serve "
             "caricarlo via FTP nella cartella records del sito (lo script lo fa da solo).",
    )

    tab_vl, tab_vc = st.tabs(["🏊 Vasca Lunga (50m)", "🏊 Vasca Corta (25m)"])
    with tab_vl:
        _vasca(top, "VL")
    with tab_vc:
        _vasca(top, "VC")
