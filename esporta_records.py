"""
esporta_records.py
──────────────────
Legge i Top 3 record dal DB Aiven, genera records.json
e lo carica via FTP sul sito Register.it.

Uso:
    python esporta_records.py

Requisiti:
    pip install mysql-connector-python
    (ftplib è già nella libreria standard Python)
"""

import json
import ftplib
import io
from datetime import date, datetime
from collections import defaultdict
import mysql.connector

# ════════════════════════════════════════════════════════════
#  CONFIGURAZIONE  —  modifica solo questa sezione
# ════════════════════════════════════════════════════════════

DB_CONFIG = {
    "host":       "record-societari-swim-project.j.aivencloud.com",
    "port":       17236,
    "database":   "defaultdb",
    "user":       "avnadmin",
    "password":   "AVNS_LTr1C2g3vj2OyE10NgR",
    "ssl_ca":     "ca.pem",       # deve essere nella stessa cartella dello script
    "ssl_disabled": False,
}

FTP_CONFIG = {
    "host":     "lhwp3363.webapps.net",       # ← trovi questo nel pannello Register.it
    "user":     "ftp_ranazzurra@ranazzurra.it",           # ← username FTP Register.it
    "password": "fX~`WqH*N|JCm6F",         # ← password FTP Register.it
    "cartella": "/public_html/records", # ← cartella sul server dove mettere il file
                                        #   (creala tu via FTP prima della prima esecuzione)
}

# ════════════════════════════════════════════════════════════

QUERY = """
SELECT
    g.descrizione                                        AS gara,
    d.metri                                              AS distanza,
    sn.codice                                            AS stile,
    tv.codice                                            AS tipo_vasca,
    a.sesso,
    a.cognome,
    a.nome,
    a.anno_nascita,
    rp.tempo_formattato,
    rp.data_record,
    rp.luogo,
    rp.manifestazione,
    ROW_NUMBER() OVER (
        PARTITION BY g.id, rp.tipo_vasca_id, a.sesso
        ORDER BY rp.tempo_secondi ASC
    ) AS posizione
FROM record_personali rp
JOIN atleti        a  ON rp.atleta_id     = a.id
JOIN gare          g  ON rp.gara_id       = g.id
JOIN stili_nuoto   sn ON g.stile_id       = sn.id
JOIN distanze      d  ON g.distanza_id    = d.id
JOIN tipi_vasca    tv ON rp.tipo_vasca_id = tv.id
WHERE rp.tempo_secondi IS NOT NULL
  AND a.sesso IN ('M', 'F')
ORDER BY d.metri, sn.codice, tv.codice, a.sesso, posizione
"""

ORDINE_STILI    = {"DF": 1, "DO": 2, "RA": 3, "SL": 4, "MX": 5}
ORDINE_DISTANZE = {50: 1, 100: 2, 200: 3, 400: 4, 800: 5, 1500: 6}


def ordina_gare(meta_index: dict) -> list:
    def chiave(nome):
        m = meta_index.get(nome, {})
        return (
            ORDINE_STILI.get(m.get("stile", ""), 99),
            ORDINE_DISTANZE.get(m.get("distanza", 0), 99),
        )
    return sorted(meta_index.keys(), key=chiave)


def serializza(val):
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    return val


# ── Step 1: leggi dal DB ─────────────────────────────────────────────────────
def leggi_da_db() -> list:
    print("📡 Connessione al database Aiven...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cur  = conn.cursor(dictionary=True)
    cur.execute(QUERY)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    print(f"   ✓ {len(rows)} righe lette")
    return rows


# ── Step 2: costruisci il JSON ───────────────────────────────────────────────
def costruisci_payload(rows: list) -> dict:
    vasche = {
        "VL": defaultdict(lambda: {"meta": {}, "M": [], "F": []}),
        "VC": defaultdict(lambda: {"meta": {}, "M": [], "F": []}),
    }

    for r in rows:
        if r["posizione"] > 3:
            continue
        tv    = r["tipo_vasca"]
        gara  = r["gara"]
        sesso = r["sesso"]

        vasche[tv][gara]["meta"] = {
            "distanza": r["distanza"],
            "stile":    r["stile"],
        }
        vasche[tv][gara][sesso].append({
            "posizione":      int(r["posizione"]),
            "cognome":        r["cognome"],
            "nome":           r["nome"],
            "anno_nascita":   int(r["anno_nascita"]) if r["anno_nascita"] else None,
            "tempo":          r["tempo_formattato"],
            "data":           serializza(r["data_record"]),
            "luogo":          r["luogo"] or "",
            "manifestazione": r["manifestazione"] or "",
        })

    def build_list(vasca_dict):
        meta_index  = {nome: vasca_dict[nome]["meta"] for nome in vasca_dict}
        gare_ordinate = ordina_gare(meta_index)
        return [
            {
                "gara":      nome,
                "distanza":  vasca_dict[nome]["meta"].get("distanza"),
                "stile":     vasca_dict[nome]["meta"].get("stile"),
                "maschile":  vasca_dict[nome]["M"],
                "femminile": vasca_dict[nome]["F"],
            }
            for nome in gare_ordinate
        ]

    return {
        "vasca_lunga": build_list(vasche["VL"]),
        "vasca_corta": build_list(vasche["VC"]),
        "aggiornato":  datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# ── Step 3: carica via FTP ───────────────────────────────────────────────────
def carica_ftp(contenuto_json: str):
    cfg = FTP_CONFIG
    print(f"📤 Connessione FTP a {cfg['host']}...")

    with ftplib.FTP() as ftp:
        ftp.connect(cfg["host"], 21, timeout=30)
        ftp.login(cfg["user"], cfg["password"])
        ftp.set_pasv(True)

        # Entra nella cartella di destinazione (la crea se non esiste)
        try:
            ftp.cwd(cfg["cartella"])
        except ftplib.error_perm:
            print(f"   ⚠ Cartella '{cfg['cartella']}' non trovata, provo a crearla...")
            ftp.mkd(cfg["cartella"])
            ftp.cwd(cfg["cartella"])

        # Carica records.json
        dati = contenuto_json.encode("utf-8")
        ftp.storbinary("STOR records.json", io.BytesIO(dati))
        print(f"   ✓ records.json caricato ({len(dati):,} byte)")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Esportazione Record Societari — Ranazzurra")
    print("=" * 55)

    # 1. Leggi DB
    rows = leggi_da_db()

    # 2. Costruisci payload
    print("🔧 Costruzione JSON...")
    payload = costruisci_payload(rows)
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)

    # Salva anche in locale come backup
    with open("records.json", "w", encoding="utf-8") as f:
        f.write(json_str)
    print("   ✓ records.json salvato in locale")

    # 3. Carica su FTP
    carica_ftp(json_str)

    print()
    print("✅ Fatto! Il sito è aggiornato.")
    print(f"   Aggiornato alle: {payload['aggiornato']}")
    print("=" * 55)


if __name__ == "__main__":
    main()