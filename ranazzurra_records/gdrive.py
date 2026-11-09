"""Lettura dei PDF dei risultati da una cartella Google Drive.

Accesso con un *service account* in sola lettura (scope ``drive.readonly``):
la cartella va condivisa, come Visualizzatore, con l'indirizzo email del
service account. Niente flusso OAuth interattivo dentro Streamlit, niente
token da rinnovare. Configurazione e passi in docs/google-drive-integration.md.

Le chiamate usano l'API REST v3 tramite ``google-auth`` (``AuthorizedSession``),
senza la libreria ``google-api-python-client``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .config import ConfigDrive

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
API = "https://www.googleapis.com/drive/v3"
MIME_CARTELLA = "application/vnd.google-apps.folder"
MIME_PDF = "application/pdf"
DIMENSIONE_MASSIMA = 30 * 1024 * 1024  # un riepilogo FIN pesa poche centinaia di KB


class ErroreDrive(RuntimeError):
    """Errore comprensibile per l'utente (permessi, rete, file mancante)."""


@dataclass(frozen=True)
class FilePDF:
    id: str
    nome: str
    cartella: str          # percorso relativo alla cartella configurata
    modificato: datetime | None
    dimensione: int | None

    @property
    def etichetta(self) -> str:
        quando = self.modificato.strftime("%d/%m/%Y") if self.modificato else "?"
        dove = f"{self.cartella}/" if self.cartella else ""
        return f"{dove}{self.nome} · {quando}"


def _sessione(cfg: ConfigDrive):
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as e:  # pragma: no cover
        raise ErroreDrive("Manca la libreria google-auth (pip install google-auth).") from e
    try:
        cred = service_account.Credentials.from_service_account_info(cfg.service_account, scopes=SCOPES)
    except Exception as e:
        raise ErroreDrive(f"Credenziali del service account non valide: {e}") from e
    return AuthorizedSession(cred)


def _data(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class ClientDrive:
    def __init__(self, cfg: ConfigDrive, sessione=None):
        self.cfg = cfg
        self._s = sessione  # iniettabile nei test

    @property
    def s(self):
        if self._s is None:
            self._s = _sessione(self.cfg)
        return self._s

    def _get(self, url: str, params: dict | None = None, timeout: int = 30):
        import requests

        try:
            r = self.s.get(url, params=params or {}, timeout=timeout)
        except requests.RequestException as e:
            raise ErroreDrive(f"Google Drive non raggiungibile: {e}") from e
        if r.status_code in (401, 403):
            raise ErroreDrive(
                "Accesso negato da Google Drive. Controlla che la cartella sia condivisa "
                f"con {self.cfg.service_account.get('client_email', 'il service account')} "
                "e che l'API Drive sia abilitata nel progetto Google Cloud."
            )
        if r.status_code == 404:
            raise ErroreDrive("Cartella o file non trovato su Google Drive (o non condiviso col service account).")
        if r.status_code >= 400:
            raise ErroreDrive(f"Errore Google Drive {r.status_code}: {r.text[:200]}")
        return r

    def verifica_cartella(self) -> str:
        """Nome della cartella configurata; errore se non e' accessibile."""
        r = self._get(f"{API}/files/{self.cfg.folder_id}",
                      {"fields": "id,name,mimeType", "supportsAllDrives": "true"}).json()
        if r.get("mimeType") != MIME_CARTELLA:
            raise ErroreDrive("L'id configurato in [gdrive] folder_id non e' una cartella.")
        return r.get("name", "")

    def _figli(self, cartella_id: str) -> list[dict]:
        out, token = [], None
        while True:
            params = {
                "q": f"'{cartella_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id,name,mimeType,modifiedTime,size)",
                "pageSize": 200,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if token:
                params["pageToken"] = token
            dati = self._get(f"{API}/files", params).json()
            out.extend(dati.get("files", []))
            token = dati.get("nextPageToken")
            if not token:
                return out

    def elenca_pdf(self) -> list[FilePDF]:
        """PDF della cartella configurata e delle sue sottocartelle (fino a
        ``profondita_massima`` livelli), dal piu' recente."""
        pdf: list[FilePDF] = []
        coda = [(self.cfg.folder_id, "", 0)]
        visti = set()
        while coda:
            cid, percorso, livello = coda.pop(0)
            if cid in visti:
                continue
            visti.add(cid)
            for f in self._figli(cid):
                if f.get("mimeType") == MIME_CARTELLA:
                    if livello < self.cfg.profondita_massima:
                        coda.append((f["id"], f"{percorso}/{f['name']}".strip("/"), livello + 1))
                elif f.get("mimeType") == MIME_PDF or f.get("name", "").lower().endswith(".pdf"):
                    pdf.append(FilePDF(
                        id=f["id"], nome=f["name"], cartella=percorso,
                        modificato=_data(f.get("modifiedTime")),
                        dimensione=int(f["size"]) if f.get("size") else None,
                    ))
        return sorted(pdf, key=lambda p: p.modificato.timestamp() if p.modificato else 0.0, reverse=True)

    def scarica(self, file_id: str) -> bytes:
        r = self._get(f"{API}/files/{file_id}", {"alt": "media", "supportsAllDrives": "true"}, timeout=60)
        dati = r.content
        if len(dati) > DIMENSIONE_MASSIMA:
            raise ErroreDrive("File troppo grande per essere un riepilogo risultati.")
        if not dati.startswith(b"%PDF"):
            raise ErroreDrive("Il file scaricato non e' un PDF.")
        return dati
