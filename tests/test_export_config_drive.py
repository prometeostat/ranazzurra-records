"""Export del JSON per il sito, configurazione e client Google Drive (sessione finta)."""

import json
from datetime import date, datetime

import pytest

from ranazzurra_records import config
from ranazzurra_records.export import costruisci_payload
from ranazzurra_records.gdrive import ClientDrive, ErroreDrive


# --- export ---------------------------------------------------------------
def r(gara, stile, dist, vasca, sesso, pos, cognome, tempo, anno=2010, data=None, luogo=None):
    return {"gara": gara, "stile": stile, "distanza": dist, "tipo_vasca": vasca, "sesso": sesso,
            "posizione": pos, "cognome": cognome, "nome": "X", "anno_nascita": anno, "tempo_formattato": tempo,
            "data_record": data, "luogo": luogo, "manifestazione": None}


def test_payload_contratto_del_sito():
    righe = [
        r("50m Rana", "RA", 50, "VL", "M", 2, "Pasquali", "0:30.56"),
        r("50m Rana", "RA", 50, "VL", "M", 2, "Foscan", "0:30.56"),
        r("50m Rana", "RA", 50, "VL", "M", 1, "Collodel", "0:29.59", data=date(2025, 7, 19), luogo="Verona"),
        r("50m Delfino", "DF", 50, "VL", "F", 1, "Ongaro", "0:29.20", anno=float("nan")),
        r("50m Rana", "RA", 50, "VL", "M", 4, "Fuori", "0:33.00"),
    ]
    p = costruisci_payload(righe, adesso=datetime(2026, 11, 9, 12, 0))
    assert p["aggiornato"] == "09/11/2026 12:00" and p["vasca_corta"] == []
    assert [g["gara"] for g in p["vasca_lunga"]] == ["50m Delfino", "50m Rana"]
    rana = p["vasca_lunga"][1]
    assert [x["cognome"] for x in rana["maschile"]] == ["Collodel", "Foscan", "Pasquali"]
    assert rana["maschile"][0]["data"] == "19/07/2025" and rana["maschile"][0]["luogo"] == "Verona"
    assert p["vasca_lunga"][0]["femminile"][0]["anno_nascita"] is None
    json.dumps(p)  # serializzabile


# --- config ---------------------------------------------------------------
def test_config_da_variabili_ambiente(monkeypatch):
    for k, v in {"MYSQL_HOST": "h", "MYSQL_PORT": "1234", "MYSQL_DATABASE": "d",
                 "MYSQL_USER": "u", "MYSQL_PASSWORD": "Segreta-123"}.items():
        monkeypatch.setenv(k, v)
    c = config.config_mysql({})
    assert (c.host, c.port, c.user) == ("h", 1234, "u")
    assert "Segreta-123" not in repr(c)                      # la password non finisce nei log
    assert c.parametri_connessione()["autocommit"] is True


def test_config_mancante(monkeypatch):
    for k in ("MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(config.ConfigurazioneMancante, match="mancano"):
        config.config_mysql({"mysql": {"host": "h"}})


def test_ssl_ca_incollato_nei_secrets(monkeypatch):
    monkeypatch.delenv("MYSQL_SSL_CA", raising=False)
    pem = "-----BEGIN CERTIFICATE-----\nABC\n-----END CERTIFICATE-----"
    c = config.config_mysql({"mysql": {"host": "h", "database": "d", "user": "u", "password": "p", "ssl_ca": pem}})
    with open(c.ssl_ca) as f:
        assert f.read().startswith("-----BEGIN CERTIFICATE-----")


def test_drive_non_configurato(monkeypatch):
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    assert config.config_drive({}) is None


# --- Google Drive con una sessione finta -------------------------------
class Risposta:
    def __init__(self, status=200, dati=None, contenuto=b""):
        self.status_code, self._dati, self.content, self.text = status, dati, contenuto, ""

    def json(self):
        return self._dati


class SessioneFinta:
    """Albero: radice -> [a.pdf, sotto/ -> [b.pdf, profonda/ -> [c.pdf]], note.txt]"""
    def __init__(self, stato=200):
        self.stato = stato
        self.figli = {
            "root": [{"id": "a", "name": "a.pdf", "mimeType": "application/pdf",
                      "modifiedTime": "2026-11-08T10:00:00Z", "size": "100"},
                     {"id": "sub", "name": "sotto", "mimeType": "application/vnd.google-apps.folder"},
                     {"id": "t", "name": "note.txt", "mimeType": "text/plain"}],
            "sub": [{"id": "b", "name": "b.pdf", "mimeType": "application/pdf",
                     "modifiedTime": "2026-11-09T10:00:00Z"},
                    {"id": "deep", "name": "profonda", "mimeType": "application/vnd.google-apps.folder"}],
            "deep": [{"id": "c", "name": "c.pdf", "mimeType": "application/pdf"}],
        }

    def get(self, url, params=None, timeout=None):
        if self.stato != 200:
            return Risposta(self.stato)
        if url.endswith("/files"):
            cid = params["q"].split("'")[1]
            return Risposta(dati={"files": self.figli.get(cid, [])})
        fid = url.rsplit("/", 1)[1]
        if params.get("alt") == "media":
            return Risposta(contenuto=b"%PDF-1.4 ..." if fid != "t" else b"testo")
        return Risposta(dati={"id": fid, "name": "risultati", "mimeType": "application/vnd.google-apps.folder"})


def client(profondita=3, stato=200):
    cfg = config.ConfigDrive("root", {"client_email": "sa@progetto.iam.gserviceaccount.com"}, profondita)
    return ClientDrive(cfg, sessione=SessioneFinta(stato))


def test_drive_elenco_ricorsivo_e_ordinato():
    files = client().elenca_pdf()
    assert [f.nome for f in files] == ["b.pdf", "a.pdf", "c.pdf"]
    assert files[0].cartella == "sotto" and files[2].cartella == "sotto/profonda"
    assert [f.nome for f in client(profondita=1).elenca_pdf()] == ["b.pdf", "a.pdf"]


def test_drive_scarica_e_verifica():
    c = client()
    assert c.verifica_cartella() == "risultati"
    assert c.scarica("a").startswith(b"%PDF")
    with pytest.raises(ErroreDrive, match="non e' un PDF"):
        c.scarica("t")


def test_drive_permessi_negati():
    with pytest.raises(ErroreDrive, match="sa@progetto"):
        client(stato=403).elenca_pdf()
    with pytest.raises(ErroreDrive, match="non trovat"):
        client(stato=404).verifica_cartella()
