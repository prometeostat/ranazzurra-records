"""
Script di importazione CORRETTO per Excel con struttura complessa
Versione 2.0 - Fix per Ranazzurra Records
"""

import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# CONFIGURAZIONE
DB_CONFIG = {
    'host': 'record-societari-swim-project.j.aivencloud.com',
    'port': 17236,
    'database': 'defaultdb',  
    'user': 'avnadmin',
    'password': 'AVNS_LTr1C2g3vj2OyE10NgR',
    'ssl_ca': 'ca.pem',
    'ssl_disabled': False
}

def converti_tempo_a_secondi(tempo_str: str) -> Optional[float]:
    """Converte tempo stringa in secondi"""
    if pd.isna(tempo_str) or tempo_str == '' or str(tempo_str).strip() == '':
        return None
    
    tempo_str = str(tempo_str).strip()
    
    pattern2 = r'^(\d+):(\d+):(\d+\.?\d*)$'
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
        return None
    
    ore = int(secondi // 3600)
    minuti = int((secondi % 3600) // 60)
    sec = secondi % 60
    
    if ore > 0:
        return f"{ore}:{minuti:02d}:{sec:05.2f}"
    else:
        return f"{minuti}:{sec:05.2f}"

def parse_excel_vasca_corta(file_path: str):
    """Parse specifico per vasca corta con header complesso"""
    # Leggi con header in riga 1 (0-indexed)
    df = pd.read_excel(file_path, sheet_name='vasca_corta', header=1)
    
    # Mappa stili dalle colonne (basato sull'analisi dell'Excel)
    # L'Excel ha: Cognome, Nome, Sex, Classe, poi blocchi per ogni stile
    # DF: 50, 100, 200
    # DO: 50, 100, 200  
    # RA: 50, 100, 200
    # MX: 100, 200, 400
    # SL: 50, 100, 200, 400, 800, 1500
    
    col_mapping = {
        # Indice colonna: (stile, distanza)
        4: ('DF', 50),
        5: ('DF', 100),
        6: ('DF', 200),
        7: ('DO', 50),
        8: ('DO', 100),
        9: ('DO', 200),
        10: ('RA', 50),
        11: ('RA', 100),
        12: ('RA', 200),
        13: ('MX', 100),
        14: ('MX', 200),
        15: ('MX', 400),
        16: ('SL', 50),
        17: ('SL', 100),
        18: ('SL', 200),
        19: ('SL', 400),
        20: ('SL', 800),
        21: ('SL', 1500)
    }
    
    return df, col_mapping

def parse_excel_vasca_lunga(file_path: str):
    """Parse specifico per vasca lunga"""
    df = pd.read_excel(file_path, sheet_name='vasca_lunga', header=1)
    
    # Stesso mapping ma potrebbe avere colonne diverse
    col_mapping = {
        4: ('DF', 50),
        5: ('DF', 100),
        6: ('DF', 200),
        7: ('DO', 50),
        8: ('DO', 100),
        9: ('DO', 200),
        10: ('RA', 50),
        11: ('RA', 100),
        12: ('RA', 200),
        13: ('MX', 100),
        14: ('MX', 200),
        15: ('SL', 50),
        16: ('SL', 100),
        17: ('SL', 200),
        18: ('SL', 400),
        19: ('SL', 800),
        20: ('SL', 1500)
    }
    
    return df, col_mapping

class ImportatoreRecordSocietari:
    """Importatore ottimizzato"""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        self.gare_cache = {}
    
    def connetti(self):
        """Connessione al database"""
        try:
            self.conn = mysql.connector.connect(**self.db_config)
            self.cur = self.conn.cursor(dictionary=True)
            print(f"✓ Connesso a database: {self.db_config['database']}")
        except Error as e:
            print(f"✗ Errore connessione: {e}")
            raise
    
    def chiudi(self):
        """Chiude connessione"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
    
    def carica_gare_cache(self):
        """Carica gare in cache"""
        query = """
            SELECT g.id, g.codice_gara, sn.codice as stile, d.metri
            FROM gare g
            JOIN stili_nuoto sn ON g.stile_id = sn.id
            JOIN distanze d ON g.distanza_id = d.id
        """
        self.cur.execute(query)
        for row in self.cur.fetchall():
            self.gare_cache[row['codice_gara']] = row['id']
        print(f"✓ Caricate {len(self.gare_cache)} gare")
    
    def get_gara_id(self, distanza: int, stile: str) -> Optional[int]:
        """Recupera ID gara"""
        codice = f"{distanza}_{stile}"
        return self.gare_cache.get(codice)
    
    def importa_atleti_e_record(self, df: pd.DataFrame, col_mapping: Dict, tipo_vasca: str):
        """Importa atleti e record in un'unica passata"""
        print(f"\n=== {tipo_vasca} ===")
        
        # Ottieni tipo_vasca_id
        self.cur.execute("SELECT id FROM tipi_vasca WHERE codice = %s", (tipo_vasca,))
        result = self.cur.fetchone()
        if not result:
            print(f"✗ Tipo vasca {tipo_vasca} non trovato!")
            return
        tipo_vasca_id = result['id']
        
        atleti_nuovi = 0
        record_importati = 0
        
        for idx, row in df.iterrows():
            # Dati atleta
            cognome = str(row.get('Cognome', '')).strip()
            nome = str(row.get('Nome', '')).strip()
            sesso = str(row.get('Sex', '')).strip().upper()
            
            if not cognome or not nome or cognome == 'nan' or nome == 'nan':
                continue
            
            try:
                anno = int(row.get('Classe')) if pd.notna(row.get('Classe')) else None
            except:
                anno = None
            
            # Inserisci/recupera atleta
            self.cur.execute(
                "SELECT id FROM atleti WHERE cognome = %s AND nome = %s AND anno_nascita <=> %s",
                (cognome, nome, anno)
            )
            atleta_result = self.cur.fetchone()
            
            if not atleta_result:
                self.cur.execute(
                    "INSERT INTO atleti (cognome, nome, sesso, anno_nascita) VALUES (%s, %s, %s, %s)",
                    (cognome, nome, sesso if sesso in ['M', 'F'] else None, anno)
                )
                atleta_id = self.cur.lastrowid
                atleti_nuovi += 1
            else:
                atleta_id = atleta_result['id']
            
            # Importa record per questo atleta
            for col_idx, (stile, distanza) in col_mapping.items():
                if col_idx >= len(row):
                    continue
                
                tempo_val = row.iloc[col_idx]
                if pd.isna(tempo_val) or str(tempo_val).strip() == '':
                    continue
                
                tempo_secondi = converti_tempo_a_secondi(str(tempo_val))
                if not tempo_secondi:
                    continue
                
                gara_id = self.get_gara_id(distanza, stile)
                if not gara_id:
                    continue
                
                tempo_fmt = formatta_tempo(tempo_secondi)
                
                try:
                    self.cur.execute(
                        """
                        INSERT INTO record_personali 
                        (atleta_id, gara_id, tipo_vasca_id, tempo_secondi, tempo_formattato)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            tempo_secondi = VALUES(tempo_secondi),
                            tempo_formattato = VALUES(tempo_formattato)
                        """,
                        (atleta_id, gara_id, tipo_vasca_id, tempo_secondi, tempo_fmt)
                    )
                    if self.cur.rowcount > 0:
                        record_importati += 1
                except Error as e:
                    print(f"  ⚠ Errore record {cognome} {distanza}{stile}: {e}")
        
        self.conn.commit()
        print(f"✓ Atleti nuovi: {atleti_nuovi}")
        print(f"✓ Record importati: {record_importati}")
    
    def processa_excel(self, file_path: str):
        """Processa Excel completo"""
        print("="*70)
        print("IMPORTAZIONE RECORD SOCIETARI RANAZZURRA")
        print("="*70)
        
        self.connetti()
        self.carica_gare_cache()
        
        try:
            # Vasca corta
            df_vc, map_vc = parse_excel_vasca_corta(file_path)
            self.importa_atleti_e_record(df_vc, map_vc, 'VC')
            
            # Vasca lunga
            df_vl, map_vl = parse_excel_vasca_lunga(file_path)
            self.importa_atleti_e_record(df_vl, map_vl, 'VL')
            
            # Statistiche finali
            print("\n" + "="*70)
            print("STATISTICHE FINALI")
            print("="*70)
            
            self.cur.execute("SELECT COUNT(*) as cnt FROM atleti")
            print(f"Totale atleti: {self.cur.fetchone()['cnt']}")
            
            self.cur.execute("SELECT COUNT(*) as cnt FROM record_personali")
            print(f"Totale record: {self.cur.fetchone()['cnt']}")
            
            self.cur.execute("""
                SELECT tv.descrizione, COUNT(*) as cnt
                FROM record_personali rp
                JOIN tipi_vasca tv ON rp.tipo_vasca_id = tv.id
                GROUP BY tv.descrizione
            """)
            for row in self.cur.fetchall():
                print(f"  - {row['descrizione']}: {row['cnt']}")
            
            print("\n✅ IMPORTAZIONE COMPLETATA!")
            print("\nProssimo passo: streamlit run streamlit_app.py")
            
        except Exception as e:
            print(f"\n✗ Errore: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            raise
        finally:
            self.chiudi()

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python import_v2.py Record_Societari.xlsx")
        sys.exit(1)
    
    importatore = ImportatoreRecordSocietari(DB_CONFIG)
    importatore.processa_excel(sys.argv[1])

if __name__ == "__main__":
    main()