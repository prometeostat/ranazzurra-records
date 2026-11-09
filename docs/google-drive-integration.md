# Integrazione con Google Drive

L'app legge i PDF dei risultati direttamente da una cartella di Google Drive, senza scaricarli e ricaricarli a mano. Accesso con un **service account** in sola lettura (`drive.readonly`): niente flusso OAuth interattivo dentro Streamlit e niente token da rinnovare. Il service account vede soltanto le cartelle condivise con lui. Motivazioni in [ADR-004](decisions/ADR-004-google-drive-service-account.md).

Se la sezione `[gdrive]` dei secrets manca, la pagina di importazione offre solo il caricamento dal computer.

## Configurazione (una volta)

1. **Progetto Google Cloud.** Su console.cloud.google.com crea un progetto (per esempio `ranazzurra-records`) e abilita *Google Drive API* (API e servizi > Libreria).
2. **Service account.** IAM e amministrazione > Account di servizio > Crea. Nessun ruolo di progetto serve. Nella scheda *Chiavi* crea una chiave JSON e scaricala. Il file e' una credenziale: non va su Drive ne' nel repository.
3. **Cartella dei PDF.** Nella cartella di progetto `ranazzurra/record_societari` crea una sottocartella dedicata, per esempio `risultati_fin`, eventualmente con una sottocartella per stagione (`2026-2027`). Condividila con l'indirizzo `client_email` del service account come **Visualizzatore**.
4. **Id della cartella.** E' la parte finale dell'URL quando apri la cartella nel browser: `https://drive.google.com/drive/folders/<ID>`.
5. **Secrets.** In `.streamlit/secrets.toml` (in locale) e in *Settings > Secrets* dell'app su Streamlit Cloud:

```toml
[gdrive]
folder_id = "<ID della cartella risultati_fin>"
profondita_massima = 3

[gdrive.service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

I valori si copiano dal file JSON (la chiave privata resta su una riga con i `\n`). In locale, in alternativa, `service_account_file = "percorso/del/file.json"` oppure la variabile `GDRIVE_SERVICE_ACCOUNT_FILE`, sempre fuori dal repository (`.gitignore` esclude `service_account*.json`).

## Funzionamento

`gdrive.ClientDrive` usa l'API REST v3 tramite `google-auth`: elenca i PDF della cartella e delle sottocartelle fino a `profondita_massima` livelli, li ordina dal piu' recente, scarica il file scelto in memoria (limite 30 MB, controllo che sia davvero un PDF). L'elenco resta in cache due minuti; *Aggiorna elenco* lo rilegge. Nell'elenco, ✅ indica i file gia' importati (confronto con `importazioni.drive_file_id`).

## Errori

| Messaggio | Causa probabile |
|---|---|
| Accesso negato da Google Drive | cartella non condivisa con il service account, oppure API Drive non abilitata |
| Cartella o file non trovato | `folder_id` sbagliato o non condiviso |
| Credenziali del service account non valide | chiave copiata male nei secrets (spesso i `\n` della chiave privata) |
| Google Drive non raggiungibile | rete; riprovare |

## Verifica rapida

Con i secrets compilati, da terminale:

```bash
python -c "from ranazzurra_records.config import config_drive; from ranazzurra_records.gdrive import ClientDrive; c = ClientDrive(config_drive()); print(c.verifica_cartella()); print([f.etichetta for f in c.elenca_pdf()][:5])"
```
