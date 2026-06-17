
import mysql.connector

DB_CONFIG = {

    'host': 'record-societari-swim-project.j.aivencloud.com',

    'port': 17236,

    'database': 'defaultdb',

    'user': 'avnadmin',

    'password': 'AVNS_LTr1C2g3vj2OyE10NgR',

    'ssl_ca': 'ca.pem',

    'ssl_disabled': False

}

print("Calcolo record societari...")

conn = mysql.connector.connect(**DB_CONFIG)

cur = conn.cursor(dictionary=True)

# Esegui la stored procedure

cur.callproc('aggiorna_record_societari')

conn.commit()

# Verifica

cur.execute("SELECT COUNT(*) as cnt FROM record_societari")

totale = cur.fetchone()['cnt']

print(f"✓ Calcolati {totale} record societari")

# Mostra alcuni esempi

cur.execute("""

    SELECT categoria, COUNT(*) as cnt

    FROM record_societari

    GROUP BY categoria

""")

print("\nRecord per categoria:")

for row in cur.fetchall():

    print(f"  - {row['categoria']}: {row['cnt']}")

cur.close()

conn.close()

print("\n✅ Fatto! Ricarica Streamlit (F5 nel browser)")

