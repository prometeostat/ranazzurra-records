"""Importazione dei risultati FIN: scelta del PDF, anteprima, conferma.

Niente viene scritto finche' l'utente non conferma. Lo stato della pagina sta
in ``st.session_state`` (documento letto, decisioni sugli atleti, selezione
delle righe); l'analisi si ricalcola a ogni giro da quello stato.
"""

from __future__ import annotations

import hashlib
import logging

import pandas as pd
import streamlit as st

from .. import repository as R
from .. import tempi
from ..config import config_drive
from ..fin_pdf import PDFNonLeggibile, leggi_pdf
from ..gdrive import ClientDrive, ErroreDrive
from ..importazione.analisi import (ATLETA_DA_RISOLVERE, ESCLUSA, GIA_PRESENTE, IMPORTABILE, NON_VALIDA,
                                    Decisioni, NuovoAtleta, analizza, chiave_atleta, fotografa)
from ..importazione.matching import Livello, proponi_cognome_nome
from ..importazione.salvataggio import ImportazioneNonValida, salva
from ..records import Esito
from . import comuni as C

log = logging.getLogger(__name__)

DA_DECIDERE = "— da decidere —"
CREA = "➕ Crea nuovo atleta"
ESCLUDI = "⏭ Escludi le sue righe"
K = "imp_"  # prefisso delle chiavi di sessione di questa pagina


def _reset() -> None:
    for k in [k for k in st.session_state if str(k).startswith(K)]:
        del st.session_state[k]


def _utente() -> str | None:
    for nome in ("user", "experimental_user"):
        u = getattr(st, nome, None)
        try:
            email = getattr(u, "email", None) if u is not None else None
            if email:
                return str(email)
        except Exception:
            pass
    return None


# --------------------------------------------------------------------- #
# 1. Scelta del PDF
# --------------------------------------------------------------------- #
@st.cache_data(ttl=120, show_spinner="Leggo la cartella su Google Drive...")
def _elenco_drive(folder_id: str) -> list[dict]:
    cfg = config_drive()
    files = ClientDrive(cfg).elenca_pdf()
    return [{"id": f.id, "etichetta": f.etichetta, "nome": f.nome} for f in files]


def _scelta_pdf(db) -> None:
    cfg = config_drive()
    origini = (["Google Drive", "Carica dal computer"] if cfg else ["Carica dal computer"])
    if not cfg:
        st.caption("Google Drive non e' configurato (sezione [gdrive] dei secrets): "
                   "per ora il PDF si carica dal computer. Vedi docs/google-drive-integration.md.")
    origine = st.radio("Da dove arriva il PDF", origini, horizontal=True, key=K + "origine")
    contenuto, nome, drive_id = None, None, None

    if origine == "Google Drive":
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Aggiorna elenco"):
                _elenco_drive.clear()
        try:
            files = _elenco_drive(cfg.folder_id)
        except ErroreDrive as e:
            st.error(f"❌ {e}")
            return
        if not files:
            st.info("Nella cartella configurata non ci sono PDF.")
            return
        gia = set()
        if db.tabella_esiste("importazioni"):
            gia = {r["drive_file_id"] for r in db.query(
                "SELECT DISTINCT drive_file_id FROM importazioni WHERE drive_file_id IS NOT NULL")}
        with col1:
            scelto = st.selectbox("PDF dei risultati", files, key=K + "drive_scelta",
                                  format_func=lambda f: ("✅ " if f["id"] in gia else "") + f["etichetta"])
        if scelto["id"] in gia:
            st.caption("✅ = file gia' importato in passato: l'analisi mostrera' cosa e' gia' presente.")
        if st.button("🔍 Analizza il PDF", type="primary"):
            try:
                with st.spinner("Scarico il PDF da Google Drive..."):
                    contenuto = ClientDrive(cfg).scarica(scelto["id"])
                nome, drive_id = scelto["nome"], scelto["id"]
            except ErroreDrive as e:
                st.error(f"❌ {e}")
                return
    else:
        up = st.file_uploader("PDF dei risultati FIN (riepilogo risultati)", type=["pdf"], key=K + "upload")
        if up is not None and st.button("🔍 Analizza il PDF", type="primary"):
            contenuto, nome = up.getvalue(), up.name

    if contenuto is not None:
        try:
            with st.spinner("Leggo il PDF..."):
                doc = leggi_pdf(contenuto)
        except PDFNonLeggibile as e:
            st.error(f"❌ {e}")
            return
        _reset()
        st.session_state[K + "doc"] = doc
        st.session_state[K + "file"] = {"nome": nome, "drive_id": drive_id,
                                        "sha": hashlib.sha256(contenuto).hexdigest()}
        st.session_state[K + "dec"] = Decisioni()
        st.rerun()


# --------------------------------------------------------------------- #
# 2. Anteprima
# --------------------------------------------------------------------- #
def _riepilogo(an) -> None:
    doc = an.doc
    st.subheader(f"📄 {doc.nome}")
    st.caption(f"{C.data_it(doc.data_inizio)}"
               + (f" – {C.data_it(doc.data_fine)}" if doc.data_fine and doc.data_fine != doc.data_inizio else "")
               + (f" · {doc.luogo}" if doc.luogo else "")
               + f" · {doc.pagine} pagine · file {st.session_state[K + 'file']['nome']}")
    individuali = [g for g in doc.gare if not g.staffetta]
    c = st.columns(5)
    c[0].metric("Gare individuate", len(individuali))
    c[1].metric("Righe lette (tutte le societa')", doc.righe_totali)
    c[2].metric("Prestazioni Ranazzurra", len(an.righe))
    c[3].metric("Atleti riconosciuti", an.atleti_riconosciuti)
    c[4].metric("Atleti da verificare", len(an.atleti_da_risolvere))

    if an.gia_importato:
        quando = ", ".join(f"#{i['id']} del {pd.to_datetime(i['created_at']).strftime('%d/%m/%Y %H:%M')}"
                           for i in an.foto.importazioni_stesso_file)
        st.warning(f"⚠️ Questo stesso file e' gia' stato importato ({quando}). "
                   "Le prestazioni gia' registrate sono segnate come 'già presente' e non verranno riscritte.")
    staff = [g for g in doc.gare if g.staffetta]
    if staff:
        st.caption(f"Staffette ignorate (i record sono individuali): {len(staff)}")
    altre = sorted({x for g in doc.gare for x in g.altre_ranazzurra})
    if altre:
        st.info("Righe di altre societa' Ranazzurra non importate: " + "; ".join(altre))
    if doc.anomalie:
        with st.expander(f"⚠️ {len(doc.anomalie)} righe del PDF non interpretate: controllale sul PDF", expanded=True):
            for a in doc.anomalie:
                st.text(a)


def _atleti(an, dec: Decisioni) -> None:
    atleti = an.foto.atleti
    etichette = {f"{a.etichetta} #{a.id}": a.id for a in sorted(atleti, key=lambda a: a.etichetta)}
    per_id = {v: k for k, v in etichette.items()}
    opzioni = [DA_DECIDERE, CREA, ESCLUDI] + list(etichette)

    # problemi prima, poi gli associati automaticamente (correggibili)
    voci = sorted(an.atleti_pdf.items(), key=lambda kv: (kv[1].livello == Livello.CERTO, kv[0]))
    da_vedere = len(an.atleti_da_risolvere)
    decisi = sum(1 for k, r in voci if r.livello != Livello.CERTO and k in dec.associazioni)
    titolo = (f"👥 Atleti da verificare: {da_vedere}" if da_vedere else "👥 Atleti: nessuno da verificare")
    if decisi:
        titolo += f" · scelte fatte: {decisi}"
    with st.expander(titolo + f" (su {len(voci)} nel PDF)", expanded=bool(da_vedere)):
        st.caption("Le associazioni automatiche valgono solo con nome e anno identici. Per gli altri "
                   "scegli l'atleta giusto, crealo o escludi le sue righe, poi premi Applica. "
                   "'Ricorda' salva la grafia del PDF per le prossime importazioni.")
        righe = []
        for k, rec in voci:
            nome, anno = k.rsplit("|", 1)
            gara_sesso = next((g.sesso for g in an.doc.gare for r in g.righe if chiave_atleta(r) == k), None)
            scelta = dec.associazioni.get(k, "auto")
            if scelta == "auto":
                azione = per_id.get(rec.atleta.id, DA_DECIDERE) if rec.livello == Livello.CERTO and rec.atleta else DA_DECIDERE
            elif scelta is None:
                azione = ESCLUDI
            elif scelta == "nuovo":
                azione = CREA
            else:
                azione = per_id.get(scelta, DA_DECIDERE)
            n = dec.nuovi.get(k)
            cognome, nome_p = (n.cognome, n.nome) if n else proponi_cognome_nome(nome)
            righe.append({
                "Nel PDF": nome, "Anno": int(anno),
                "Azione": azione,
                "Proposte": "; ".join(f"{c.atleta.etichetta} ({c.punteggio:.0%})" for c in rec.candidati),
                "Cognome (se nuovo)": cognome, "Nome (se nuovo)": nome_p,
                "Sesso (se nuovo)": (n.sesso if n else (gara_sesso if gara_sesso in ("M", "F") else None)),
                "Ricorda": k in dec.ricorda,
                "Riconoscimento": rec.livello.value + (f": {rec.motivo}" if rec.livello != Livello.CERTO else ""),
                "_k": k,
            })
        df = pd.DataFrame(righe)
        impronta = hashlib.md5("|".join(df["_k"]).encode()).hexdigest()[:8]
        modificato = st.data_editor(
            df.drop(columns=["_k"]), key=f"{K}editor_atleti_{impronta}", hide_index=True,
            use_container_width=True,
            disabled=["Nel PDF", "Anno", "Riconoscimento", "Proposte"],
            column_config={
                "Anno": st.column_config.NumberColumn(format="%d"),
                "Proposte": st.column_config.TextColumn(width="medium"),
                "Azione": st.column_config.SelectboxColumn(options=opzioni, required=True, width="large"),
                "Sesso (se nuovo)": st.column_config.SelectboxColumn(options=["M", "F"]),
                "Ricorda": st.column_config.CheckboxColumn(help="Salva questa grafia come alias dell'atleta scelto"),
            },
        )
        col1, col2 = st.columns(2)
        with col1:
            applica = st.button("✔️ Applica le scelte sugli atleti", type="primary")
        with col2:
            tutti_nuovi = st.button("➕ Crea come nuovi tutti i 'non trovato'")
        if tutti_nuovi:
            for k, rec in voci:
                if rec.livello == Livello.NON_TROVATO and k not in dec.associazioni:
                    nome, anno = k.rsplit("|", 1)
                    c, n = proponi_cognome_nome(nome)
                    s = next((g.sesso for g in an.doc.gare for r in g.righe if chiave_atleta(r) == k), None)
                    dec.associazioni[k] = "nuovo"
                    dec.nuovi[k] = NuovoAtleta(c, n, s if s in ("M", "F") else "", int(anno))
            st.rerun()
        if applica:
            errori = []
            for (_, orig), (_, nuovo) in zip(df.iterrows(), modificato.iterrows()):
                k = orig["_k"]
                rec = an.atleti_pdf[k]
                az = nuovo["Azione"]
                if az == DA_DECIDERE:
                    dec.associazioni.pop(k, None)
                elif az == ESCLUDI:
                    dec.associazioni[k] = None
                elif az == CREA:
                    sesso = nuovo["Sesso (se nuovo)"]
                    if not str(nuovo["Cognome (se nuovo)"] or "").strip() or not str(nuovo["Nome (se nuovo)"] or "").strip() \
                            or sesso not in ("M", "F"):
                        errori.append(f"{orig['Nel PDF']}: per crearlo servono cognome, nome e sesso")
                    dec.associazioni[k] = "nuovo"
                    dec.nuovi[k] = NuovoAtleta(str(nuovo["Cognome (se nuovo)"]).strip(),
                                               str(nuovo["Nome (se nuovo)"]).strip(), sesso or "", int(orig["Anno"]))
                else:
                    scelto = etichette[az]
                    if rec.livello == Livello.CERTO and rec.atleta and rec.atleta.id == scelto:
                        dec.associazioni.pop(k, None)  # resta l'automatica
                    else:
                        dec.associazioni[k] = scelto
                if bool(nuovo["Ricorda"]) and isinstance(dec.associazioni.get(k), int):
                    dec.ricorda.add(k)
                else:
                    dec.ricorda.discard(k)
            if errori:
                st.session_state[K + "errori_atleti"] = errori
            st.rerun()
        for e in st.session_state.pop(K + "errori_atleti", []):
            st.error(e)


def _fmt(cent) -> str:
    return tempi.formatta(cent) if cent is not None else ""


def _tabella_esiti(righe, nome_manif: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "Atleta": r.atleta_etichetta,
        "Gara": r.descrizione_gara,
        "Vasca": "25 m" if r.vasca == "VC" else "50 m",
        "Tempo precedente": _fmt(r.valutazione.riferimento_precedente) or "—",
        "Nuovo tempo": _fmt(r.riga.tempo),
        "Differenza (s)": tempi.formatta_differenza(
            tempi.differenza(r.riga.tempo, r.valutazione.riferimento_precedente)) or "—",
        "Posizione in top 3": (f"{r.valutazione.posizione_prima or '—'} → {r.valutazione.posizione_dopo}"
                               if r.esito and r.esito.tocca_record else ""),
        "Manifestazione": nome_manif,
        "Note": "; ".join(r.valutazione.note + r.avvisi),
    } for r in righe])


def _risultati(an, dec: Decisioni) -> None:
    st.subheader("🏊 Risultati")
    importabili = an.righe_con(IMPORTABILE)
    if importabili:
        df = pd.DataFrame([{
            "Importa": r.selezionata,
            "Atleta": r.atleta_etichetta,
            "Gara": r.descrizione_gara + (f" {r.gara.turno}" if r.gara.turno else ""),
            "Vasca": r.vasca,
            "Tempo": _fmt(r.riga.tempo) or r.riga.stato,
            "Pos.": r.riga.posizione,
            "Esito": r.esito.value if r.esito else "",
            "PB prec.": _fmt(r.valutazione.pb_precedente) if r.valutazione else "",
            "Avvisi": "; ".join(r.avvisi),
            "_k": r.chiave,
        } for r in importabili])
        impronta = hashlib.md5("|".join(df["_k"]).encode()).hexdigest()[:8]
        mod = st.data_editor(
            df.drop(columns=["_k"]), key=f"{K}editor_righe_{impronta}", hide_index=True,
            use_container_width=True, disabled=[c for c in df.columns if c not in ("Importa", "_k")],
            column_config={"Importa": st.column_config.CheckboxColumn(
                help="Togli la spunta per escludere la riga. Le righe con avvisi partono senza spunta.")},
        )
        cambiato = False
        for (_, o), (_, n) in zip(df.iterrows(), mod.iterrows()):
            k, vuole = o["_k"], bool(n["Importa"])
            r = next(x for x in importabili if x.chiave == k)
            if vuole != r.selezionata:
                cambiato = True
                if vuole:
                    dec.escluse.discard(k)
                    if r.da_verificare:
                        dec.incluse.add(k)
                else:
                    dec.escluse.add(k)
                    dec.incluse.discard(k)
        if cambiato:
            st.rerun()

    altre = an.righe_con(GIA_PRESENTE, NON_VALIDA, ATLETA_DA_RISOLVERE, ESCLUSA)
    if altre:
        with st.expander(f"Righe che non verranno importate: {len(altre)}"):
            st.dataframe(pd.DataFrame([{
                "Stato": r.stato, "Nel PDF": f"{r.riga.nome} ({r.riga.anno})",
                "Gara": r.descrizione_gara, "Tempo": _fmt(r.riga.tempo) or r.riga.stato,
                "Motivo": "; ".join(r.avvisi),
            } for r in altre]), hide_index=True, use_container_width=True)


def _record(an) -> None:
    st.subheader("🏆 Record e primati personali")
    nome = an.doc.nome
    gruppi = [
        ("🥇 Nuovi record societari", (Esito.NUOVO_RECORD,)),
        ("🥈 Record societari migliorati (top 3)", (Esito.RECORD_EGUAGLIATO, Esito.TOP3)),
        ("⭐ Nuovi primati personali", (Esito.PB, Esito.PRIMO_TEMPO)),
    ]
    for titolo, esiti in gruppi:
        righe = an.per_esito(*esiti)
        st.markdown(f"**{titolo}: {len(righe)}**")
        if righe:
            st.dataframe(_tabella_esiti(righe, nome), hide_index=True, use_container_width=True)
    nessuno = an.per_esito(Esito.NESSUNO)
    senza = an.per_esito(Esito.NON_VALUTABILE)
    st.caption(f"Risultati senza miglioramenti: {len(nessuno)} · senza tempo valido: {len(senza)}")
    if an.top3_prima_dopo:
        with st.expander("Top 3 prima e dopo l'importazione"):
            for (gara_id, vasca, sesso), (prima, dopo) in sorted(an.top3_prima_dopo.items(), key=str):
                st.markdown(f"**{an.foto.descrizione_gare.get(gara_id, gara_id)} · {vasca} · {C.SESSI[sesso]}**")
                def nome_a(aid):
                    if aid > 0:
                        a = an.foto.atleta(aid)
                        return a.etichetta if a else f"#{aid}"
                    r = next((x for x in an.righe if x.atleta_id == aid), None)
                    return r.atleta_etichetta if r else "nuovo atleta"
                c1, c2 = st.columns(2)
                c1.dataframe(pd.DataFrame([{"Pos.": p, "Atleta": nome_a(a), "Tempo": _fmt(t)} for a, t, p in prima]),
                             hide_index=True, use_container_width=True)
                c2.dataframe(pd.DataFrame([{"Pos.": p, "Atleta": nome_a(a), "Tempo": _fmt(t)} for a, t, p in dopo]),
                             hide_index=True, use_container_width=True)


def _conferma(db, an) -> None:
    st.subheader("✅ Conferma")
    sel = an.selezionate()
    nuovi = {r.atleta_id for r in sel if r.atleta_id < 0}
    pb = [r for r in sel if r.esito and r.esito.aggiorna_pb]
    non_risolti = an.righe_con(ATLETA_DA_RISOLVERE)
    st.markdown(f"Verranno scritti **{len(sel)} risultati**, aggiornati **{len(pb)} personali** "
                f"e creati **{len(nuovi)} atleti**. Nessun dato esistente viene cancellato.")
    if non_risolti:
        st.warning(f"{len(non_risolti)} prestazioni restano fuori perche' l'atleta non e' stato risolto.")
    ok = st.checkbox("Ho controllato l'anteprima", key=K + "controllato")
    col1, col2 = st.columns(2)
    with col1:
        conferma = st.button("✅ Conferma importazione", type="primary", disabled=not (ok and sel))
    with col2:
        if st.button("✖️ Annulla"):
            _reset()
            st.rerun()
    if conferma:
        try:
            with st.spinner("Scrivo nel database..."):
                esito = salva(db, an, st.session_state[K + "file"]["nome"], _utente(),
                              st.session_state[K + "file"]["drive_id"])
        except ImportazioneNonValida as e:
            st.error(f"❌ {e}")
            return
        except Exception as e:
            log.exception("Importazione fallita")
            st.error(f"❌ Importazione annullata, nessun dato scritto. Dettaglio: {e}")
            return
        C.dopo_scrittura()
        _reset()
        st.session_state[K + "esito"] = esito
        st.rerun()


def _storico(db) -> None:
    imp = R.importazioni(db, 50)
    if imp.empty:
        st.info("Nessuna importazione registrata.")
        return
    st.dataframe(pd.DataFrame({
        "#": imp["id"],
        "Quando": imp["created_at"].map(lambda v: pd.to_datetime(v).strftime("%d/%m/%Y %H:%M")),
        "File": imp["file_nome"], "Manifestazione": imp["manifestazione"],
        "Data gara": imp["data_inizio"].map(C.data_it), "Utente": imp["utente"].fillna(""),
        "Risultati": imp["risultati_inseriti"], "Personali": imp["personali_aggiornati"],
        "Atleti nuovi": imp["atleti_creati"],
    }), hide_index=True, use_container_width=True)
    scelta = st.selectbox("Dettaglio di un'importazione", imp["id"].tolist(),
                          format_func=lambda i: f"#{i} · {imp.set_index('id').loc[i, 'file_nome']}")
    righe = db.query(
        "SELECT CONCAT(a.cognome, ' ', a.nome) AS atleta, g.descrizione AS gara, tv.codice AS vasca, "
        "r.tempo_formattato, r.stato, r.posizione, r.esito, r.pagina_pdf, r.data_gara "
        "FROM risultati r JOIN atleti a ON a.id = r.atleta_id JOIN gare g ON g.id = r.gara_id "
        "JOIN tipi_vasca tv ON tv.id = r.tipo_vasca_id WHERE r.importazione_id = %s "
        "ORDER BY g.id, tv.codice, r.tempo_secondi", (int(scelta),))
    if righe:
        st.dataframe(pd.DataFrame(righe), hide_index=True, use_container_width=True)


def mostra() -> None:
    st.header("📥 Importa risultati FIN")
    db = C.db()
    if not R.migrazione_001_applicata(db):
        st.warning("Per importare i risultati serve la migrazione 001 del database. Dalla cartella del "
                   "progetto: `python -m ranazzurra_records.migrazioni --applica` "
                   "(fa prima un backup). Vedi docs/database.md.")
        return

    tab1, tab2 = st.tabs(["Nuova importazione", "Storico importazioni"])
    with tab2:
        _storico(db)
    with tab1:
        esito = st.session_state.pop(K + "esito", None)
        if esito:
            st.success(f"✅ Importazione #{esito.importazione_id} completata: {esito.risultati_inseriti} risultati, "
                       f"{esito.personali_aggiornati} personali aggiornati, {esito.atleti_creati} atleti nuovi.")
            for v in esito.verifiche:
                st.markdown(f"- {v}")
            st.info("Per pubblicare i record sul sito lancia `python esporta_records.py`, oppure scarica "
                    "records.json dalla pagina Record Top 3 e caricalo via FTP.")
        doc = st.session_state.get(K + "doc")
        if doc is None:
            _scelta_pdf(db)
            return
        dec: Decisioni = st.session_state[K + "dec"]
        an = analizza(doc, fotografa(db, doc), dec)
        _riepilogo(an)
        _atleti(an, dec)
        _risultati(an, dec)
        _record(an)
        _conferma(db, an)
