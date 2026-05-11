"""
Applicazione Streamlit per Gestione Record Societari
Ranazzurra S.r.l.

Gestione CRUD completa per atleti, record personali e record societari
Database: MySQL su AIVEN
"""

import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import re
from typing import Optional, Dict, List

# Configurazione pagina
st.set_page_config(
    page_title="Ranazzurra Records Manager",
    page_icon="🏊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stili CSS personalizzati
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1E88E5;
    }
    .success-msg {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-msg {
        padding: 1rem;
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Configurazione Database
@st.cache_resource
def init_connection():
    """Inizializza connessione al database MySQL"""
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            port=st.secrets["mysql"]["port"],
            database=st.secrets["mysql"]["database"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            ssl_ca=st.secrets["mysql"].get("ssl_ca", None),
            ssl_disabled=False
        )
    except Exception as e:
        st.error(f"Errore connessione database: {e}")
        st.stop()

def get_db_cursor():
    """Ottiene un cursor per il database"""
    conn = init_connection()
    return conn.cursor(dictionary=True)

# Utility functions
def converti_tempo_a_secondi(tempo_str: str) -> Optional[float]:
    """Converte tempo stringa in secondi"""
    if not tempo_str or tempo_str.strip() == '':
        return None
    
    tempo_str = str(tempo_str).strip()
    
    # Pattern per HH:MM:SS.CC
    pattern2 = r'^(\d+):(\d+):(\d+\.?\d*)$'
    # Pattern per MM:SS.CC
    pattern1 = r'^(\d+):(\d+\.?\d*)$'
    
    match2 = re.match(pattern2, tempo_str)
    match1 = re.match(pattern1, tempo_str)
    
    if match2:
        ore = int(match2.group(1))
        minuti = int(match2.group(2))
        secondi = float(match2.group(3))
        return ore * 3600 + minuti * 60 + secondi
    elif match1:
        minuti = int(match1.group(1))
        secondi = float(match1.group(2))
        return minuti * 60 + secondi
    else:
        try:
            return float(tempo_str)
        except:
            return None

def formatta_tempo(secondi: float) -> str:
    """Converte secondi in formato stringa"""
    if secondi is None:
        return ""
    
    ore = int(secondi // 3600)
    minuti = int((secondi % 3600) // 60)
    sec = secondi % 60
    
    if ore > 0:
        return f"{ore}:{minuti:02d}:{sec:05.2f}"
    else:
        return f"{minuti}:{sec:05.2f}"

# CRUD Operations - ATLETI
@st.cache_data(ttl=60)
def carica_atleti(filtro_attivi: bool = True) -> pd.DataFrame:
    """Carica lista atleti"""
    conn = init_connection()
    cur = conn.cursor(dictionary=True)
    
    query = "SELECT id, cognome, nome, sesso, anno_nascita, attivo, note FROM atleti"
    if filtro_attivi:
        query += " WHERE attivo = TRUE"
    query += " ORDER BY cognome, nome"
    
    cur.execute(query)
    df = pd.DataFrame(cur.fetchall())
    cur.close()
    return df

def inserisci_atleta(cognome: str, nome: str, sesso: str, anno_nascita: int, note: str = ""):
    """Inserisce nuovo atleta"""
    conn = init_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO atleti (cognome, nome, sesso, anno_nascita, note)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (cognome, nome, sesso, anno_nascita, note)
        )
        conn.commit()
        st.cache_data.clear()
        return True, "✅ Atleta inserito con successo!"
    except mysql.connector.IntegrityError:
        conn.rollback()
        return False, "❌ Errore: Atleta già esistente"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore: {str(e)}"
    finally:
        cur.close()

def aggiorna_atleta(atleta_id: int, cognome: str, nome: str, sesso: str, 
                   anno_nascita: int, attivo: bool, note: str):
    """Aggiorna dati atleta"""
    conn = init_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE atleti 
            SET cognome = %s, nome = %s, sesso = %s, 
                anno_nascita = %s, attivo = %s, note = %s
            WHERE id = %s
            """,
            (cognome, nome, sesso, anno_nascita, attivo, note, atleta_id)
        )
        conn.commit()
        st.cache_data.clear()
        return True, "✅ Atleta aggiornato con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore: {str(e)}"
    finally:
        cur.close()

def elimina_atleta(atleta_id: int):
    """Elimina atleta (soft delete)"""
    conn = init_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE atleti SET attivo = FALSE WHERE id = %s", (atleta_id,))
        conn.commit()
        st.cache_data.clear()
        return True, "✅ Atleta disattivato con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore: {str(e)}"
    finally:
        cur.close()

# CRUD Operations - RECORD PERSONALI
@st.cache_data(ttl=60)
def carica_record_personali(atleta_id: int = None) -> pd.DataFrame:
    """Carica record personali con filtro opzionale per atleta"""
    conn = init_connection()
    cur = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM v_record_personali"
    if atleta_id:
        query += f" WHERE id IN (SELECT id FROM record_personali WHERE atleta_id = {atleta_id})"
    query += " ORDER BY cognome, nome, tipo_vasca, stile, distanza"
    
    cur.execute(query)
    df = pd.DataFrame(cur.fetchall())
    cur.close()
    return df

@st.cache_data(ttl=300)
def carica_gare() -> List[Dict]:
    """Carica lista gare disponibili"""
    conn = init_connection()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("""
        SELECT g.id, g.codice_gara, g.descrizione,
               sn.codice as stile_codice, d.metri
        FROM gare g
        JOIN stili_nuoto sn ON g.stile_id = sn.id
        JOIN distanze d ON g.distanza_id = d.id
        ORDER BY d.metri, sn.codice
    """)
    result = cur.fetchall()
    cur.close()
    return result

def inserisci_record_personale(atleta_id: int, gara_id: int, tipo_vasca: str,
                               tempo_str: str, data_record: date = None,
                               luogo: str = "", manifestazione: str = "", note: str = ""):
    """Inserisce nuovo record personale"""
    tempo_secondi = converti_tempo_a_secondi(tempo_str)
    if tempo_secondi is None:
        return False, "❌ Formato tempo non valido (usa MM:SS.CC)"
    
    tempo_formattato = formatta_tempo(tempo_secondi)
    
    conn = init_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Ottieni tipo_vasca_id
        cur.execute("SELECT id FROM tipi_vasca WHERE codice = %s", (tipo_vasca,))
        result = cur.fetchone()
        if not result:
            return False, "❌ Tipo vasca non valido"
        tipo_vasca_id = result['id']
        
        cur.execute(
            """
            INSERT INTO record_personali 
            (atleta_id, gara_id, tipo_vasca_id, tempo_secondi, tempo_formattato,
             data_record, luogo, manifestazione, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                tempo_secondi = VALUES(tempo_secondi),
                tempo_formattato = VALUES(tempo_formattato),
                data_record = VALUES(data_record),
                luogo = VALUES(luogo),
                manifestazione = VALUES(manifestazione),
                note = VALUES(note)
            """,
            (atleta_id, gara_id, tipo_vasca_id, tempo_secondi, tempo_formattato,
             data_record, luogo, manifestazione, note)
        )
        conn.commit()
        
        # Aggiorna record societari
        cur.callproc('aggiorna_record_societari')
        conn.commit()
        
        st.cache_data.clear()
        return True, "✅ Record inserito/aggiornato con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore: {str(e)}"
    finally:
        cur.close()

def elimina_record_personale(record_id: int):
    """Elimina record personale"""
    conn = init_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM record_personali WHERE id = %s", (record_id,))
        conn.commit()
        
        # Aggiorna record societari
        cur.callproc('aggiorna_record_societari')
        conn.commit()
        
        st.cache_data.clear()
        return True, "✅ Record eliminato con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore: {str(e)}"
    finally:
        cur.close()

# Dashboard e Statistiche
def mostra_dashboard():
    """Mostra dashboard con statistiche principali"""
    st.markdown('<div class="main-header">🏊 Ranazzurra Conegliano - Records Manager</div>', unsafe_allow_html=True)
    
    conn = init_connection()
    cur = conn.cursor(dictionary=True)
    
    # Statistiche principali
    col1, col2, col3, col4 = st.columns(4)
    
    cur.execute("SELECT COUNT(*) as cnt FROM atleti WHERE attivo = TRUE")
    num_atleti = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM record_personali")
    num_record = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(DISTINCT atleta_id) as cnt FROM record_personali")
    atleti_con_record = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM gare")
    num_gare = cur.fetchone()['cnt']
    
    with col1:
        st.metric("👥 Atleti Attivi", num_atleti)
    with col2:
        st.metric("🏅 Record Totali", num_record)
    with col3:
        st.metric("⭐ Atleti con Record", atleti_con_record)
    with col4:
        st.metric("🎯 Gare Disponibili", num_gare)
    
    st.markdown("---")
    
    # Record societari con filtri
    st.subheader("🏆 Record Societari")
    
    # Filtri
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Carica lista gare per filtro
        cur.execute("""
            SELECT DISTINCT g.id, g.descrizione 
            FROM gare g
            JOIN record_societari rs ON g.id = rs.gara_id
            ORDER BY g.descrizione
        """)
        gare_disponibili = cur.fetchall()
        gare_options = ["Tutte"] + [g['descrizione'] for g in gare_disponibili]
        filtro_gara = st.selectbox("Filtra per Gara", gare_options)
    
    with col2:
        filtro_vasca = st.selectbox("Filtra per Vasca", ["Tutte", "Vasca Corta (25m)", "Vasca Lunga (50m)"])
    
    with col3:
        filtro_categoria = st.selectbox("Categoria", ["Tutti", "Maschili", "Femminili", "Assoluti"])
    
    # Costruisci query con filtri
    query = """
        SELECT 
            rs.id,
            rs.categoria,
            g.descrizione as gara,
            tv.descrizione as vasca,
            CONCAT(a.cognome, ' ', a.nome) as atleta,
            rs.tempo_formattato as tempo,
            rs.data_record,
            rs.gara_id,
            rs.tipo_vasca_id
        FROM record_societari rs
        JOIN gare g ON rs.gara_id = g.id
        JOIN tipi_vasca tv ON rs.tipo_vasca_id = tv.id
        LEFT JOIN atleti a ON rs.atleta_id = a.id
        WHERE 1=1
    """
    
    params = []
    
    # Applica filtro gara
    if filtro_gara != "Tutte":
        query += " AND g.descrizione = %s"
        params.append(filtro_gara)
    
    # Applica filtro vasca
    if filtro_vasca != "Tutte":
        query += " AND tv.descrizione = %s"
        params.append(filtro_vasca)
    
    # Applica filtro categoria
    if filtro_categoria == "Maschili":
        query += " AND rs.categoria = 'M'"
    elif filtro_categoria == "Femminili":
        query += " AND rs.categoria = 'F'"
    elif filtro_categoria == "Assoluti":
        query += " AND rs.categoria = 'ASSOLUTO'"
    
    query += " ORDER BY g.descrizione, tv.codice, rs.categoria"
    
    cur.execute(query, params)
    df_record_soc = pd.DataFrame(cur.fetchall())
    
    if not df_record_soc.empty:
        # Tabella record
        df_display = df_record_soc[['categoria', 'gara', 'vasca', 'atleta', 'tempo']].copy()
        df_display.columns = ['Categoria', 'Gara', 'Vasca', 'Atleta', 'Tempo']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Grafici progressione per ogni gara
        st.subheader("📈 Progressione Record nel Tempo")
        
        # Ottieni gare uniche dai record filtrati
        gare_uniche = df_record_soc[['gara_id', 'gara', 'tipo_vasca_id', 'vasca']].drop_duplicates()
        
        if len(gare_uniche) > 0:
            # Selezione gara per vedere progressione
            gara_options_prog = [f"{row['gara']} - {row['vasca']}" for _, row in gare_uniche.iterrows()]
            gara_selezionata = st.selectbox("Seleziona gara per vedere la progressione", gara_options_prog)
            
            # Estrai gara_id e tipo_vasca_id
            idx = gara_options_prog.index(gara_selezionata)
            gara_row = gare_uniche.iloc[idx]
            gara_id = gara_row['gara_id']
            tipo_vasca_id = gara_row['tipo_vasca_id']
            
            # Query per ottenere tutti i record di quella gara nel tempo
            cur.execute("""
                SELECT 
                    DATE_FORMAT(rp.data_record, '%Y-%m-%d') as data,
                    rp.tempo_secondi,
                    rp.tempo_formattato,
                    CONCAT(a.cognome, ' ', a.nome) as atleta,
                    a.sesso
                FROM record_personali rp
                JOIN atleti a ON rp.atleta_id = a.id
                WHERE rp.gara_id = %s 
                  AND rp.tipo_vasca_id = %s
                  AND rp.data_record IS NOT NULL
                ORDER BY rp.data_record
            """, (gara_id, tipo_vasca_id))
            
            df_progressione = pd.DataFrame(cur.fetchall())
            
            if not df_progressione.empty:
                # Calcola il miglior tempo progressivo (record rolling)
                df_progressione['data'] = pd.to_datetime(df_progressione['data'])
                
                # Separa per sesso
                df_m = df_progressione[df_progressione['sesso'] == 'M'].copy()
                df_f = df_progressione[df_progressione['sesso'] == 'F'].copy()
                
                fig = go.Figure()
                
                # Maschili
                if not df_m.empty:
                    df_m = df_m.sort_values('data')
                    df_m['miglior_tempo'] = df_m['tempo_secondi'].cummin()
                    
                    # Mostra solo i punti dove c'è stato un miglioramento
                    df_m_record = df_m[df_m['tempo_secondi'] == df_m['miglior_tempo']].drop_duplicates('miglior_tempo')
                    
                    fig.add_trace(go.Scatter(
                        x=df_m_record['data'],
                        y=df_m_record['tempo_secondi'],
                        mode='lines+markers',
                        name='Maschile',
                        line=dict(color='#1E88E5', width=3),
                        marker=dict(size=10),
                        text=df_m_record.apply(lambda r: f"{r['atleta']}<br>{r['tempo_formattato']}", axis=1),
                        hovertemplate='%{text}<br>%{x|%d/%m/%Y}<extra></extra>'
                    ))
                
                # Femminili
                if not df_f.empty:
                    df_f = df_f.sort_values('data')
                    df_f['miglior_tempo'] = df_f['tempo_secondi'].cummin()
                    
                    df_f_record = df_f[df_f['tempo_secondi'] == df_f['miglior_tempo']].drop_duplicates('miglior_tempo')
                    
                    fig.add_trace(go.Scatter(
                        x=df_f_record['data'],
                        y=df_f_record['tempo_secondi'],
                        mode='lines+markers',
                        name='Femminile',
                        line=dict(color='#E91E63', width=3),
                        marker=dict(size=10),
                        text=df_f_record.apply(lambda r: f"{r['atleta']}<br>{r['tempo_formattato']}", axis=1),
                        hovertemplate='%{text}<br>%{x|%d/%m/%Y}<extra></extra>'
                    ))
                
                fig.update_layout(
                    title=f"Progressione Record: {gara_selezionata}",
                    xaxis_title="Data",
                    yaxis_title="Tempo (secondi)",
                    hovermode='closest',
                    height=500,
                    yaxis=dict(autorange='reversed')  # Tempi più bassi in alto
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabella dettagliata miglioramenti
                st.subheader("📋 Storico Miglioramenti")
                
                col_m, col_f = st.columns(2)
                
                with col_m:
                    st.write("**Maschili**")
                    if not df_m.empty:
                        df_m_display = df_m_record[['data', 'atleta', 'tempo_formattato']].copy()
                        df_m_display.columns = ['Data', 'Atleta', 'Tempo']
                        df_m_display['Data'] = df_m_display['Data'].dt.strftime('%d/%m/%Y')
                        st.dataframe(df_m_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nessun record maschile con data")
                
                with col_f:
                    st.write("**Femminili**")
                    if not df_f.empty:
                        df_f_display = df_f_record[['data', 'atleta', 'tempo_formattato']].copy()
                        df_f_display.columns = ['Data', 'Atleta', 'Tempo']
                        df_f_display['Data'] = df_f_display['Data'].dt.strftime('%d/%m/%Y')
                        st.dataframe(df_f_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nessun record femminile con data")
            else:
                st.warning("Nessun record con data disponibile per questa gara")
        
    else:
        st.info("Nessun record societario trovato con i filtri selezionati")
    
    cur.close()

# Sezione Gestione Atleti
def sezione_atleti():
    """Interfaccia gestione atleti"""
    st.header("👤 Gestione Atleti")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Elenco", "➕ Nuovo Atleta", "✏️ Modifica", "🗑️ Elimina"])
    
    with tab1:
        st.subheader("Elenco Atleti")
        
        mostra_inattivi = st.checkbox("Mostra anche atleti inattivi", False)
        df_atleti = carica_atleti(not mostra_inattivi)
        
        if not df_atleti.empty:
            # Filtri
            col1, col2, col3 = st.columns(3)
            with col1:
                filtro_sesso = st.multiselect("Filtra per sesso", 
                                            options=['M', 'F'],
                                            default=['M', 'F'])
            with col2:
                search = st.text_input("🔍 Cerca atleta (cognome/nome)")
            with col3:
                anno_min = st.number_input("Anno nascita da:", min_value=1900, max_value=2024, value=1990)
            
            df_filtrato = df_atleti.copy()
            if filtro_sesso:
                df_filtrato = df_filtrato[df_filtrato['sesso'].isin(filtro_sesso)]
            if search:
                mask = (df_filtrato['cognome'].str.contains(search, case=False, na=False) | 
                       df_filtrato['nome'].str.contains(search, case=False, na=False))
                df_filtrato = df_filtrato[mask]
            if anno_min:
                df_filtrato = df_filtrato[df_filtrato['anno_nascita'] >= anno_min]
            
            # Mostra dataframe con formato migliorato
            df_display = df_filtrato[['cognome', 'nome', 'sesso', 'anno_nascita']].copy()
            df_display.columns = ['Cognome', 'Nome', 'Sesso', 'Anno Nascita']
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.caption(f"Totale: {len(df_filtrato)} atleti")
        else:
            st.info("Nessun atleta presente nel database")
    
    with tab2:
        st.subheader("Inserisci Nuovo Atleta")
        
        with st.form("form_nuovo_atleta", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                cognome = st.text_input("Cognome *", max_chars=100, placeholder="Rossi")
                sesso = st.selectbox("Sesso *", options=['M', 'F'], index=0)
            
            with col2:
                nome = st.text_input("Nome *", max_chars=100, placeholder="Mario")
                anno_nascita = st.number_input("Anno di Nascita *", 
                                              min_value=1900, 
                                              max_value=datetime.now().year,
                                              value=2000)
            
            note = st.text_area("Note", max_chars=500, placeholder="Note aggiuntive...")
            
            submitted = st.form_submit_button("💾 Salva Atleta", use_container_width=True)
            
            if submitted:
                if not cognome or not nome:
                    st.error("❌ Cognome e Nome sono obbligatori!")
                else:
                    success, message = inserisci_atleta(cognome.strip().title(), 
                                                       nome.strip().title(), 
                                                       sesso, anno_nascita, note.strip())
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    with tab3:
        st.subheader("✏️ Modifica Atleta")
        
        df_atleti = carica_atleti(False)
        if not df_atleti.empty:
            atleta_options = {f"{row['cognome']} {row['nome']} ({row['anno_nascita']})": row['id'] 
                            for _, row in df_atleti.iterrows()}
            
            atleta_sel = st.selectbox("Seleziona Atleta da Modificare", 
                                     options=list(atleta_options.keys()),
                                     key="select_atleta_mod")
            
            if atleta_sel:
                atleta_id = atleta_options[atleta_sel]
                atleta = df_atleti[df_atleti['id'] == atleta_id].iloc[0]
                
                st.info(f"📝 Modifica: {atleta['cognome']} {atleta['nome']}")
                
                with st.form("form_modifica_atleta"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        cognome = st.text_input("Cognome *", value=atleta['cognome'])
                        sesso = st.selectbox("Sesso *", options=['M', 'F'], 
                                           index=0 if atleta['sesso'] == 'M' else 1)
                        attivo = st.checkbox("Attivo", value=bool(atleta['attivo']))
                    
                    with col2:
                        nome = st.text_input("Nome *", value=atleta['nome'])
                        anno_nascita = st.number_input("Anno di Nascita *", 
                                                      min_value=1900,
                                                      max_value=datetime.now().year,
                                                      value=int(atleta['anno_nascita']))
                    
                    note = st.text_area("Note", value=atleta['note'] if atleta['note'] else "", max_chars=500)
                    
                    submit_mod = st.form_submit_button("💾 Aggiorna Atleta", use_container_width=True)
                    
                    if submit_mod:
                        if not cognome or not nome:
                            st.error("❌ Cognome e Nome sono obbligatori!")
                        else:
                            success, message = aggiorna_atleta(atleta_id, cognome.strip().title(), 
                                                              nome.strip().title(), 
                                                              sesso, anno_nascita, attivo, note.strip())
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
        else:
            st.info("Nessun atleta disponibile")
    
    with tab4:
        st.subheader("🗑️ Elimina Atleta")
        
        df_atleti = carica_atleti(False)
        if not df_atleti.empty:
            st.warning("⚠️ **ATTENZIONE**: Eliminare un atleta eliminerà anche tutti i suoi record personali!")
            
            atleta_options = {f"{row['cognome']} {row['nome']} ({row['anno_nascita']})": row['id'] 
                            for _, row in df_atleti.iterrows()}
            
            atleta_sel = st.selectbox("Seleziona Atleta da Eliminare", 
                                     options=list(atleta_options.keys()),
                                     key="select_atleta_del")
            
            if atleta_sel:
                atleta_id = atleta_options[atleta_sel]
                atleta = df_atleti[df_atleti['id'] == atleta_id].iloc[0]
                
                # Conta i record dell'atleta
                conn = init_connection()
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT COUNT(*) as cnt FROM record_personali WHERE atleta_id = %s", (atleta_id,))
                num_record = cur.fetchone()['cnt']
                cur.close()
                
                st.error(f"🗑️ Eliminerai: **{atleta['cognome']} {atleta['nome']}** ({atleta['anno_nascita']})")
                st.error(f"⚠️ Verranno eliminati anche **{num_record} record** associati a questo atleta!")
                
                st.markdown("---")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    conferma = st.text_input("Scrivi 'ELIMINA DEFINITIVAMENTE' per confermare", key="conferma_elimina_atleta")
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Elimina Definitivamente", type="primary", use_container_width=True):
                        if conferma == "ELIMINA DEFINITIVAMENTE":
                            # Elimina atleta (cascade eliminerà anche i record)
                            conn = init_connection()
                            cur = conn.cursor()
                            try:
                                cur.execute("DELETE FROM atleti WHERE id = %s", (atleta_id,))
                                conn.commit()
                                
                                # Aggiorna record societari
                                cur.callproc('aggiorna_record_societari')
                                conn.commit()
                                
                                st.cache_data.clear()
                                st.success(f"✅ Atleta {atleta['cognome']} {atleta['nome']} e {num_record} record eliminati!")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ Errore: {str(e)}")
                            finally:
                                cur.close()
                        else:
                            st.error("❌ Devi scrivere 'ELIMINA DEFINITIVAMENTE' per confermare!")
        else:
            st.info("Nessun atleta disponibile")

# Sezione Gestione Record
def sezione_record():
    """Interfaccia gestione record personali"""
    st.header("🏅 Gestione Record Personali")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Elenco Record", "➕ Nuovo Record", "✏️ Modifica Record", "🗑️ Elimina Record"])
    
    with tab1:
        st.subheader("Record Personali")
        
        df_record = carica_record_personali()
        
        if not df_record.empty:
            # Filtri
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                atleti_unici = sorted(df_record['cognome'].unique())
                filtro_atleta = st.selectbox("Atleta", ["Tutti"] + atleti_unici)
            
            with col2:
                filtro_vasca = st.selectbox("Vasca", ["Tutte", "VC", "VL"])
            
            with col3:
                filtro_stile = st.selectbox("Stile", ["Tutti", "SL", "DO", "RA", "DF", "MX"])
            
            with col4:
                filtro_sesso = st.selectbox("Sesso", ["Tutti", "M", "F"])
            
            # Applica filtri
            df_filtrato = df_record.copy()
            
            if filtro_atleta != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['cognome'] == filtro_atleta]
            
            if filtro_vasca != "Tutte":
                df_filtrato = df_filtrato[df_filtrato['tipo_vasca'] == filtro_vasca]
            
            if filtro_stile != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['stile'] == filtro_stile]
            
            if filtro_sesso != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['sesso'] == filtro_sesso]
            
            # Prepara display
            df_display = df_filtrato[['cognome', 'nome', 'tipo_vasca', 'gara_descrizione', 
                                     'tempo_formattato', 'data_record']].copy()
            df_display.columns = ['Cognome', 'Nome', 'Vasca', 'Gara', 'Tempo', 'Data']
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.caption(f"Totale: {len(df_filtrato)} record")
            
            # Export CSV
            if st.button("📥 Esporta in CSV"):
                csv = df_display.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Scarica CSV",
                    data=csv,
                    file_name="record_personali.csv",
                    mime="text/csv"
                )
        else:
            st.info("Nessun record presente nel database")
    
    with tab2:
        st.subheader("Inserisci Nuovo Record Personale")
        
        df_atleti = carica_atleti(True)
        gare_list = carica_gare()
        
        if df_atleti.empty:
            st.warning("⚠️ Nessun atleta attivo disponibile. Inserisci prima degli atleti.")
        else:
            with st.form("form_nuovo_record", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    atleta_options = {f"{row['cognome']} {row['nome']}": row['id'] 
                                    for _, row in df_atleti.iterrows()}
                    atleta_sel = st.selectbox("Atleta *", options=list(atleta_options.keys()))
                    
                    tipo_vasca = st.selectbox("Tipo Vasca *", options=['VC', 'VL'])
                    
                    tempo_str = st.text_input("Tempo *", placeholder="1:23.45 o 0:32.10",
                                            help="Formato: MM:SS.CC o HH:MM:SS.CC")
                
                with col2:
                    gara_options = {f"{g['descrizione']}": g['id'] for g in gare_list}
                    gara_sel = st.selectbox("Gara *", options=list(gara_options.keys()))
                    
                    data_record = st.date_input("Data Record", value=None)
                    
                    luogo = st.text_input("Luogo", placeholder="Città, Piscina")
                
                manifestazione = st.text_input("Manifestazione", 
                                              placeholder="Nome della competizione")
                note_record = st.text_area("Note", max_chars=500)
                
                submitted = st.form_submit_button("💾 Salva Record", use_container_width=True)
                
                if submitted:
                    if not atleta_sel or not gara_sel or not tempo_str:
                        st.error("❌ Atleta, Gara e Tempo sono obbligatori!")
                    else:
                        atleta_id = atleta_options[atleta_sel]
                        gara_id = gara_options[gara_sel]
                        
                        success, message = inserisci_record_personale(
                            atleta_id, gara_id, tipo_vasca, tempo_str,
                            data_record, luogo, manifestazione, note_record
                        )
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
    
    with tab3:
        st.subheader("✏️ Modifica Record Esistente")
        
        df_record = carica_record_personali()
        
        if not df_record.empty:
            # Selezione record da modificare
            record_options = {}
            for _, row in df_record.iterrows():
                label = f"{row['cognome']} {row['nome']} - {row['gara_descrizione']} ({row['tipo_vasca']}) - {row['tempo_formattato']}"
                record_options[label] = row['id']
            
            record_sel = st.selectbox("Seleziona Record da Modificare", 
                                     options=list(record_options.keys()),
                                     key="select_record_mod")
            
            if record_sel:
                record_id = record_options[record_sel]
                record = df_record[df_record['id'] == record_id].iloc[0]
                
                st.info(f"📝 Modifica: {record['cognome']} {record['nome']} - {record['gara_descrizione']}")
                
                with st.form("form_modifica_record"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nuovo_tempo = st.text_input("Nuovo Tempo *", 
                                                    value=record['tempo_formattato'],
                                                    help="Formato: MM:SS.CC")
                        
                        nuova_data = st.date_input("Data Record", 
                                                  value=pd.to_datetime(record['data_record']).date() if pd.notna(record['data_record']) else None)
                    
                    with col2:
                        nuovo_luogo = st.text_input("Luogo", 
                                                   value=record['luogo'] if pd.notna(record['luogo']) else "")
                        
                        nuova_manifestazione = st.text_input("Manifestazione",
                                                            value=record['manifestazione'] if pd.notna(record['manifestazione']) else "")
                    
                    nuove_note = st.text_area("Note", 
                                             value=record['note'] if pd.notna(record['note']) else "",
                                             max_chars=500)
                    
                    submit_mod = st.form_submit_button("💾 Aggiorna Record", use_container_width=True)
                    
                    if submit_mod:
                        if not nuovo_tempo:
                            st.error("❌ Il tempo è obbligatorio!")
                        else:
                            # Aggiorna il record
                            tempo_secondi = converti_tempo_a_secondi(nuovo_tempo)
                            if tempo_secondi is None:
                                st.error("❌ Formato tempo non valido!")
                            else:
                                tempo_fmt = formatta_tempo(tempo_secondi)
                                
                                conn = init_connection()
                                cur = conn.cursor()
                                try:
                                    cur.execute("""
                                        UPDATE record_personali
                                        SET tempo_secondi = %s,
                                            tempo_formattato = %s,
                                            data_record = %s,
                                            luogo = %s,
                                            manifestazione = %s,
                                            note = %s
                                        WHERE id = %s
                                    """, (tempo_secondi, tempo_fmt, nuova_data, nuovo_luogo, 
                                         nuova_manifestazione, nuove_note, record_id))
                                    
                                    conn.commit()
                                    
                                    # Aggiorna record societari
                                    cur.callproc('aggiorna_record_societari')
                                    conn.commit()
                                    
                                    st.cache_data.clear()
                                    st.success("✅ Record aggiornato con successo!")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"❌ Errore: {str(e)}")
                                finally:
                                    cur.close()
        else:
            st.info("Nessun record disponibile per modifica")
    
    with tab4:
        st.subheader("🗑️ Elimina Record")
        
        df_record = carica_record_personali()
        
        if not df_record.empty:
            st.warning("⚠️ **ATTENZIONE**: L'eliminazione è permanente e non può essere annullata!")
            
            # Selezione record da eliminare
            record_options = {}
            for _, row in df_record.iterrows():
                label = f"{row['cognome']} {row['nome']} - {row['gara_descrizione']} ({row['tipo_vasca']}) - {row['tempo_formattato']}"
                record_options[label] = row['id']
            
            record_sel = st.selectbox("Seleziona Record da Eliminare", 
                                     options=list(record_options.keys()),
                                     key="select_record_del")
            
            if record_sel:
                record_id = record_options[record_sel]
                record = df_record[df_record['id'] == record_id].iloc[0]
                
                st.error(f"🗑️ Eliminerai: {record['cognome']} {record['nome']} - {record['gara_descrizione']} - {record['tempo_formattato']}")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    conferma = st.text_input("Scrivi 'ELIMINA' per confermare", key="conferma_elimina_record")
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Elimina Definitivamente", type="primary", use_container_width=True):
                        if conferma == "ELIMINA":
                            success, message = elimina_record_personale(record_id)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("❌ Devi scrivere 'ELIMINA' per confermare!")
        else:
            st.info("Nessun record disponibile per eliminazione")

# Main App
def main():
    """Funzione principale dell'applicazione"""
    
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/200x100/1E88E5/FFFFFF?text=Ranazzurra", 
                use_container_width=True)
        
        st.markdown("---")
        
        menu = st.radio(
            "🧭 Menu Navigazione",
            ["🏠 Dashboard", "👤 Gestione Atleti", "🏅 Gestione Record"],
            key="menu_nav"
        )
        
        st.markdown("---")
        st.markdown("### ℹ️ Info")
        st.markdown("""
        **Ranazzurra Conegliano**  
        Sistema di Gestione Record Societari
        
        Database: MySQL (AIVEN)  
        Versione: 1.0
        """)
        
        if st.button("🔄 Aggiorna Dati"):
            st.cache_data.clear()
            st.success("Cache aggiornata!")
            st.rerun()
    
    # Routing
    if menu == "🏠 Dashboard":
        mostra_dashboard()
    elif menu == "👤 Gestione Atleti":
        sezione_atleti()
    elif menu == "🏅 Gestione Record":
        sezione_record()

if __name__ == "__main__":
    main()