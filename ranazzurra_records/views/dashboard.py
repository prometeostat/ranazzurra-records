"""Dashboard: numeri principali, record societari, podio e progressione di una gara."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import repository as R
from ..records import chiave_ordinamento_gara
from . import comuni as C


def _filtri_record(df: pd.DataFrame) -> pd.DataFrame:
    col1, col2, col3 = st.columns(3)
    with col1:
        vasca = st.selectbox("Vasca", ["Tutte", "VC", "VL"],
                             format_func=lambda v: v if v == "Tutte" else C.nome_vasca(v),
                             key="dash_vasca")
    if vasca != "Tutte":
        df = df[df["tipo_vasca"] == vasca]
    with col2:
        nomi = sorted(df["gara"].unique(),
                      key=lambda g: chiave_ordinamento_gara(*df.loc[df["gara"] == g, ["stile", "distanza"]].iloc[0]))
        gara = st.selectbox("Gara", ["Tutte"] + nomi, key="dash_gara")
    if gara != "Tutte":
        df = df[df["gara"] == gara]
    with col3:
        sesso = st.selectbox("Sesso", ["Tutti", "M", "F"],
                             format_func=lambda s: C.SESSI.get(s, s), key="dash_sesso")
    if sesso != "Tutti":
        df = df[df["sesso"] == sesso]
    return df


def _grafico_progressione(prog: pd.DataFrame, titolo: str) -> go.Figure:
    fig = go.Figure()
    for sesso, nome, colore in (("M", "Maschile", "#1E88E5"), ("F", "Femminile", "#E91E63")):
        d = prog[prog["sesso"] == sesso].sort_values("data").copy()
        if d.empty:
            continue
        d["miglior"] = d["centesimi"].cummin()
        punti = d[d["centesimi"] == d["miglior"]].drop_duplicates("miglior")
        fig.add_trace(go.Scatter(
            x=punti["data"], y=punti["centesimi"] / 100, mode="lines+markers", name=nome,
            line=dict(color=colore, width=3), marker=dict(size=10),
            text=punti.apply(lambda r: f"{r['atleta']}<br>{r['tempo_formattato']}", axis=1),
            hovertemplate="%{text}<br>%{x|%d/%m/%Y}<extra></extra>",
        ))
    fig.update_layout(
        title=f"Progressione del record: {titolo}", xaxis_title="Data",
        yaxis_title="Tempo (secondi)", hovermode="closest", height=480,
        yaxis=dict(autorange="reversed"),   # tempi migliori in alto
        xaxis=dict(autorange="reversed"),   # date piu' recenti a sinistra
    )
    return fig


def mostra() -> None:
    C.intestazione("🏊 Ranazzurra Conegliano · Records Manager")
    db = C.db()

    n = C.conteggi(db)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Atleti attivi", n["atleti_attivi"])
    c2.metric("🏅 Personali registrati", n["personali"])
    c3.metric("⭐ Atleti con personali", n["atleti_con_personali"])
    c4.metric("🎯 Gare", n["gare"])

    st.markdown("---")
    st.subheader("🏆 Record societari")
    top = C.top3(db)
    if top.empty:
        st.info("Nessun tempo registrato.")
        return
    filtrati = _filtri_record(top)
    primi = filtrati[filtrati["posizione"] == 1].copy()
    if primi.empty:
        st.info("Nessun record con i filtri selezionati.")
    else:
        primi["ord"] = primi.apply(lambda r: chiave_ordinamento_gara(r["stile"], r["distanza"]), axis=1)
        primi = primi.sort_values(["tipo_vasca", "ord", "sesso"])
        vista = pd.DataFrame({
            "Gara": primi["gara"],
            "Vasca": primi["tipo_vasca"],
            "Sesso": primi["sesso"],
            "Atleta": primi["cognome"] + " " + primi["nome"],
            "Anno": primi["anno_nascita"],
            "Tempo": primi["tempo_formattato"],
            "Data": primi["data_record"].map(C.data_it),
            "Luogo": primi["luogo"].fillna(""),
        })
        st.dataframe(vista, use_container_width=True, hide_index=True)
        st.caption("Primo tempo della societa' per gara, vasca e sesso (ex aequo inclusi). "
                   "La top 3 completa e' nella pagina Record Top 3.")

    st.markdown("---")
    st.subheader("📈 Podio e progressione di una gara")
    gare = C.gare(db)
    vasche = C.tipi_vasca(db)
    col1, col2 = st.columns(2)
    with col1:
        vasca = st.selectbox("Vasca", list(vasche), format_func=C.nome_vasca, key="prog_vasca")
    with col2:
        gara = st.selectbox("Gara", gare, format_func=lambda g: g["descrizione"], key="prog_gara")
    if gara:
        sel = top[(top["gara_id"] == gara["id"]) & (top["tipo_vasca"] == vasca)]
        col_m, col_f = st.columns(2)
        for col, sesso in ((col_m, "M"), (col_f, "F")):
            with col:
                st.markdown(f"**{'🔵' if sesso == 'M' else '🔴'} {C.SESSI[sesso]} · top 3**")
                righe = sel[sel["sesso"] == sesso].sort_values(["posizione", "cognome"])
                if righe.empty:
                    st.info("Nessun tempo registrato")
                for _, r in righe.iterrows():
                    st.markdown(C.card_record(r), unsafe_allow_html=True)
        prog = C.progressione(db, gara["id"], vasche[vasca])
        if prog.empty:
            st.info("Nessuna prestazione con data per questa gara.")
        else:
            st.plotly_chart(_grafico_progressione(prog, f"{gara['descrizione']} · {C.nome_vasca(vasca)}"),
                            use_container_width=True)

    st.markdown("---")
    st.subheader("🕒 Ultimi personali registrati")
    ultimi = C.ultimi_personali(db, 10)
    if ultimi.empty:
        st.info("Nessun personale con data.")
    else:
        st.dataframe(pd.DataFrame({
            "Data": ultimi["data_record"].map(C.data_it),
            "Atleta": ultimi["atleta"],
            "Gara": ultimi["gara"],
            "Vasca": ultimi["tipo_vasca"],
            "Tempo": ultimi["tempo_formattato"],
            "Luogo": ultimi["luogo"].fillna(""),
        }), use_container_width=True, hide_index=True)

    imp = R.importazioni(db, 5)
    if not imp.empty:
        st.markdown("---")
        st.subheader("📥 Ultime importazioni FIN")
        st.dataframe(pd.DataFrame({
            "Quando": imp["created_at"].map(lambda v: pd.to_datetime(v).strftime("%d/%m/%Y %H:%M")),
            "Manifestazione": imp["manifestazione"],
            "Data gara": imp["data_inizio"].map(C.data_it),
            "Risultati": imp["risultati_inseriti"],
            "Personali aggiornati": imp["personali_aggiornati"],
        }), use_container_width=True, hide_index=True)
