# 🏊 Sistema Gestione Record Societari - Ranazzurra S.r.l.

Sistema completo per la gestione dei record societari di nuoto con database MySQL su AIVEN e frontend Streamlit.

## 📋 Indice

1. [Architettura](#architettura)
2. [Setup Database AIVEN](#setup-database-aiven)
3. [Installazione e Configurazione](#installazione-e-configurazione)
4. [Import Dati da Excel](#import-dati-da-excel)
5. [Avvio Applicazione Streamlit](#avvio-applicazione-streamlit)
6. [Funzionalità](#funzionalità)
7. [Struttura Database](#struttura-database)

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                     AIVEN CLOUD                             │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │         MySQL Database                       │          │
│  │  - Atleti                                    │          │
│  │  - Record Personali                          │          │
│  │  - Record Societari                          │          │
│  │  - Gare, Stili, Distanze                    │          │
│  └──────────────────────────────────────────────┘          │
│                        ▲                                    │
└────────────────────────┼────────────────────────────────────┘
                         │ SSL/TLS
                         │
┌────────────────────────┼────────────────────────────────────┐
│                 LOCAL/CLOUD                                 │
│                                                             │
│  ┌──────────────┐     ┌────────────────────────┐          │
│  │ Import Script│     │  Streamlit Frontend   │          │
│  │  (Python)    │     │  - Dashboard          │          │
│  └──────────────┘     │  - CRUD Atleti        │          │
│                       │  - CRUD Record        │          │
│                       │  - Statistiche        │          │
│                       └────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Setup Database AIVEN

### 1. Crea Servizio MySQL su AIVEN

1. Vai su [Aiven Console](https://console.aiven.io/)
2. Crea un nuovo servizio MySQL:
   - **Cloud Provider**: scegli il provider preferito (AWS, Google Cloud, Azure)
   - **Region**: seleziona la region più vicina (es. `aws-eu-south-1` per Milano)
   - **Plan**: inizia con lo Startup-4 (sufficiente per iniziare)
   - **Service Name**: `ranazzurra-mysql`

3. Attendi che il servizio sia completamente avviato (circa 5-10 minuti)

### 2. Scarica Certificati SSL

1. Nella console AIVEN, vai al tuo servizio MySQL
2. Vai alla tab **Overview**
3. Scarica il file **CA Certificate** (`ca.pem`)
4. Salva il file in una cartella sicura (es. `~/aiven-certs/ca.pem`)

### 3. Recupera Credenziali di Connessione

Dalla tab **Overview** del servizio, annota:
- **Service URI** (hostname e porta)
- **Username**: `avnadmin`
- **Password**: (clicca su "Show" per visualizzarla)
- **Port**: generalmente `12345` o `3306`
- **Database**: `defaultdb` (puoi creare il database `ranazzurra_records`)

### 4. Crea Database

Connettiti al database MySQL usando MySQL Workbench, DBeaver, o CLI:

```bash
mysql -h your-host.aivencloud.com -P 12345 -u avnadmin -p --ssl-ca=~/aiven-certs/ca.pem
```

Crea il database:

```sql
CREATE DATABASE ranazzurra_records CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ranazzurra_records;
```

### 5. Esegui Schema SQL

```bash
mysql -h your-host.aivencloud.com -P 12345 -u avnadmin -p ranazzurra_records --ssl-ca=~/aiven-certs/ca.pem < ranazzurra_schema_mysql.sql
```

Oppure dalla console MySQL:

```sql
USE ranazzurra_records;
SOURCE /path/to/ranazzurra_schema_mysql.sql;
```

---

## 💻 Installazione e Configurazione

### 1. Prerequisiti

- Python 3.9 o superiore
- pip

### 2. Installa Dipendenze

```bash
pip install -r requirements.txt
```

### 3. Configura Connessione Database

#### Per Script Import

Modifica `import_excel_mysql.py` alla riga 25:

```python
DB_CONFIG = {
    'host': 'ranazzurra-mysql-your-org.aivencloud.com',
    'port': 12345,
    'database': 'ranazzurra_records',
    'user': 'avnadmin',
    'password': 'YOUR_PASSWORD_HERE',
    'ssl_ca': '/Users/tuonome/aiven-certs/ca.pem',
    'ssl_disabled': False
}
```

#### Per Streamlit

Crea la cartella `.streamlit` nella directory del progetto:

```bash
mkdir .streamlit
```

Crea il file `.streamlit/secrets.toml`:

```toml
[mysql]
host = "ranazzurra-mysql-your-org.aivencloud.com"
port = 12345
database = "ranazzurra_records"
user = "avnadmin"
password = "YOUR_PASSWORD_HERE"
ssl_ca = "/Users/tuonome/aiven-certs/ca.pem"
```

⚠️ **IMPORTANTE**: Aggiungi `.streamlit/secrets.toml` al tuo `.gitignore`!

---

## 📥 Import Dati da Excel

### 1. Prepara il File Excel

Assicurati che il file `Record_Societari.xlsx` abbia la struttura corretta con i fogli:
- `vasca_corta`
- `vasca_lunga`

### 2. Esegui Import

```bash
python import_excel_mysql.py /path/to/Record_Societari.xlsx
```

Lo script:
1. ✓ Importa tutti gli atleti
2. ✓ Importa i record personali per vasca corta
3. ✓ Importa i record personali per vasca lunga
4. ✓ Calcola automaticamente i record societari (M, F, ASSOLUTO)
5. ✓ Mostra statistiche finali

### Output Atteso

```
=== Inizio importazione da Record_Societari.xlsx ===

✓ Connessione al database MySQL stabilita
✓ Caricate 33 gare in cache

### VASCA CORTA ###

--- Importazione atleti da VC ---
✓ Atleti importati: 135, esistenti: 0

--- Importazione record personali VC ---
✓ Record importati: 542, aggiornati: 0, errori: 0

### VASCA LUNGA ###
...

--- Aggiornamento record societari ---
✓ Record societari aggiornati

=== Importazione completata con successo ===

--- Statistiche Database ---
Totale atleti: 135
Totale record personali: 1089
...
```

---

## 🎨 Avvio Applicazione Streamlit

### 1. Avvia il Server

```bash
streamlit run streamlit_app.py
```

### 2. Accedi all'App

L'applicazione si aprirà automaticamente nel browser all'indirizzo:
```
http://localhost:8501
```

---

## 🎯 Funzionalità

### Dashboard 🏠

- **Metriche Principali**: Atleti attivi, record totali, gare disponibili
- **Grafici Statistici**:
  - Distribuzione record per stile
  - Record per distanza
- **Record Societari**: visualizzazione per categoria (M, F, ASSOLUTO)

### Gestione Atleti 👤

#### Elenco Atleti
- Visualizzazione completa atleti
- Filtri: sesso, anno nascita, ricerca nome
- Esportazione CSV

#### Nuovo Atleta
- Form inserimento con validazione
- Campi: Cognome, Nome, Sesso, Anno nascita, Note

#### Modifica Atleta
- Aggiornamento dati esistenti
- Disattivazione atleta (soft delete)

### Gestione Record 🏅

#### Elenco Record
- Visualizzazione tutti i record personali
- Filtri multipli: atleta, vasca, stile, sesso
- Esportazione CSV

#### Nuovo Record
- Form inserimento con validazione tempi
- Formato tempo: `MM:SS.CC` o `HH:MM:SS.CC`
- Campi opzionali: data, luogo, manifestazione, note
- **Aggiornamento automatico record societari**

---

## 🗄️ Struttura Database

### Tabelle Principali

#### `atleti`
```sql
- id (PK)
- cognome
- nome
- sesso (M/F)
- anno_nascita
- attivo (BOOLEAN)
- note
- created_at, updated_at
```

#### `record_personali`
```sql
- id (PK)
- atleta_id (FK)
- gara_id (FK)
- tipo_vasca_id (FK)
- tempo_secondi (DECIMAL)
- tempo_formattato (VARCHAR)
- data_record
- luogo
- manifestazione
- note
- created_at, updated_at
```

#### `record_societari`
```sql
- id (PK)
- gara_id (FK)
- tipo_vasca_id (FK)
- categoria (M/F/ASSOLUTO)
- atleta_id (FK)
- tempo_secondi
- tempo_formattato
- data_record
- created_at, updated_at
```

### Tabelle di Riferimento

- `tipi_vasca`: VC (25m), VL (50m)
- `stili_nuoto`: SL, DO, RA, DF, MX
- `distanze`: 50, 100, 200, 400, 800, 1500
- `gare`: combinazioni stile + distanza

### View

- `v_record_personali`: join completo record con atleti e gare
- `v_record_societari`: join record societari con dettagli

### Stored Procedures

- `aggiorna_record_societari()`: calcola automaticamente i migliori record per categoria

---

## 🔐 Sicurezza

### Best Practices Implementate

1. ✓ **Connessione SSL/TLS** obbligatoria ad AIVEN
2. ✓ **Secrets gestiti** via `secrets.toml` (escluso da git)
3. ✓ **SQL Injection Prevention** tramite parametrizzazione query
4. ✓ **Soft Delete** per atleti (non eliminazione fisica)
5. ✓ **Timestamp automatici** per audit trail

### Raccomandazioni

- NON committare mai `secrets.toml` su Git
- Usa password complesse per AIVEN
- Abilita IP Whitelist su AIVEN per ambienti production
- Implementa autenticazione Streamlit per deploy pubblico

---

## 📊 Query Utili

### Top 10 Record per Stile

```sql
SELECT 
    CONCAT(a.cognome, ' ', a.nome) as atleta,
    sn.descrizione as stile,
    d.metri,
    rp.tempo_formattato,
    tv.codice as vasca
FROM record_personali rp
JOIN atleti a ON rp.atleta_id = a.id
JOIN gare g ON rp.gara_id = g.id
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d ON g.distanza_id = d.id
JOIN tipi_vasca tv ON rp.tipo_vasca_id = tv.id
WHERE sn.codice = 'SL'
ORDER BY rp.tempo_secondi
LIMIT 10;
```

### Progressione Temporale Atleta

```sql
SELECT 
    g.descrizione as gara,
    tv.codice as vasca,
    rp.tempo_formattato,
    rp.data_record
FROM record_personali rp
JOIN gare g ON rp.gara_id = g.id
JOIN tipi_vasca tv ON rp.tipo_vasca_id = tv.id
WHERE rp.atleta_id = ?
ORDER BY rp.data_record DESC;
```

---

## 🚀 Deploy in Produzione

### Opzione 1: Streamlit Cloud

1. Push codice su GitHub (escludi secrets!)
2. Vai su [share.streamlit.io](https://share.streamlit.io/)
3. Connetti repository
4. Configura secrets nella dashboard Streamlit Cloud

### Opzione 2: Docker

Crea `Dockerfile`:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501"]
```

Build e run:

```bash
docker build -t ranazzurra-app .
docker run -p 8501:8501 -v ~/.streamlit:/root/.streamlit ranazzurra-app
```

### Opzione 3: VPS (AWS/DigitalOcean/etc.)

```bash
# Installa Python e dipendenze
sudo apt update
sudo apt install python3-pip
pip3 install -r requirements.txt

# Usa screen o tmux per mantenere attivo
screen -S streamlit
streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0

# Configura nginx come reverse proxy
```

---

## 🆘 Troubleshooting

### Errore Connessione Database

```
mysql.connector.errors.DatabaseError: 2026 (HY000): SSL connection error
```

**Soluzione**: Verifica che il percorso `ssl_ca` punti al file `ca.pem` corretto.

### Errore Import Excel

```
KeyError: 'Cognome'
```

**Soluzione**: Verifica che il file Excel abbia le colonne corrette nei fogli `vasca_corta` e `vasca_lunga`.

### Streamlit Non Trova secrets.toml

```
FileNotFoundError: Secrets file not found
```

**Soluzione**: Assicurati che `.streamlit/secrets.toml` esista nella directory del progetto.

---

## 📝 TODO / Roadmap

- [ ] Autenticazione utenti Streamlit
- [ ] Export PDF report atleta
- [ ] Grafici progressione temporale
- [ ] Import automatico risultati gara
- [ ] Notifiche email nuovi record
- [ ] API REST per integrazioni esterne
- [ ] App mobile (React Native/Flutter)

---

## 👨‍💻 Sviluppo

### Struttura File

```
ranazzurra-records/
├── ranazzurra_schema_mysql.sql    # Schema database
├── import_excel_mysql.py          # Script import dati
├── streamlit_app.py               # Frontend Streamlit
├── requirements.txt               # Dipendenze Python
├── README.md                      # Questa guida
├── .streamlit/
│   └── secrets.toml              # Configurazione DB
└── Record_Societari.xlsx          # Dati Excel
```

### Contribuire

1. Fork del repository
2. Crea branch feature (`git checkout -b feature/nuova-funzionalita`)
3. Commit modifiche (`git commit -am 'Aggiunge nuova funzionalità'`)
4. Push branch (`git push origin feature/nuova-funzionalita`)
5. Apri Pull Request

---

## 📄 Licenza

Proprietario: **Logos Technologies - Ranazzurra S.r.l.**

---

## 📞 Supporto

Per supporto tecnico:
- Email: [email protected]
- Team DEV - Logos Technologies

---

**Creato con ❤️ per Ranazzurra S.r.l.**
