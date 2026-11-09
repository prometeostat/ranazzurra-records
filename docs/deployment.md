# Deploy e configurazione

## Streamlit Community Cloud

App collegata al repository `prometeostat/ranazzurra-records`, branch `main`, file `streamlit_app.py`. Python da `runtime.txt` (3.11). Ogni push su `main` aggiorna l'app; dopo modifiche a `requirements.txt` o moduli nuovi conviene il *Reboot* dal pannello *Manage app*.

**Secrets** (*Settings > Secrets*), stessa struttura di `.streamlit/secrets.toml.example`:

- `[mysql]`: host, port, database, user, password, `ssl_ca = "ca.pem"` (il file e' nel repository);
- `[gdrive]`: facoltativa, vedi [google-drive-integration.md](google-drive-integration.md);
- `[ftp]`: non serve all'app, solo a `esporta_records.py` in locale.

**Repository privato.** Community Cloud puo' pubblicare anche da un repository privato, dopo aver autorizzato l'accesso ai repository privati nelle impostazioni dell'account. Un'app che arriva da un repository privato e' privata per impostazione (visibile solo a chi e' autorizzato) e il piano gratuito ammette una sola app privata alla volta; dalle impostazioni la si puo' rendere pubblica. L'app non ha un login proprio: se e' pubblica, chi ha l'URL puo' anche scrivere.

## Aiven (MySQL)

Servizio `record-societari` nel progetto `swim-project`, piano free. Se l'app dice che il database non risponde, controllare dalla console Aiven che il servizio sia acceso (*Power on*): a ottobre 2026 e' stato trovato spento. Backup giornaliero automatico.

`ip_filter` e' aperto (`0.0.0.0/0`) perche' Streamlit Cloud non ha indirizzi fissi: la protezione e' la password, che va tenuta solo nei secrets e ruotata se finisce dove non deve.

## Pubblicazione dei record sul sito

```bash
python esporta_records.py                # genera records.json e lo carica via FTP (TLS)
python esporta_records.py --solo-locale  # solo il file
```

Legge `[mysql]` e `[ftp]` da `.streamlit/secrets.toml`. L'FTP usa TLS (`FTP_TLS` con canale dati cifrato); se Register.it lo rifiutasse, `tls = false` nella sezione `[ftp]`. In alternativa: *Scarica records.json* dalla pagina Record Top 3 e caricamento manuale nella cartella `/public_html/records`.

## Rilascio di questa versione (2.0.0)

1. Ruotare le password MySQL (Aiven) e FTP (Register.it), aggiornare i secrets di Streamlit Cloud e il `secrets.toml` locale.
2. Applicare la migrazione 001: `python -m ranazzurra_records.migrazioni --applica`. Si puo' fare prima o dopo il merge: senza migrazione l'app funziona, manca solo l'importazione.
3. Merge della pull request su `main`, poi *Reboot* dell'app.
4. Controllare le pagine e fare una prima importazione con l'anteprima.
5. Controllare che la pagina pubblicata sia quella con `filter()` (copia nella cartella del sito su Drive), cosi' gli ex aequo restano visibili.
