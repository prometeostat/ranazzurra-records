"""Accesso a MySQL.

Una istanza di :class:`Database` tiene una connessione e la ripristina da sola
se e' caduta (Aiven chiude le connessioni inattive). Le letture girano in
autocommit; le scritture che toccano piu' righe passano da
:meth:`Database.transazione`, che fa commit alla fine o rollback su errore.

Il modulo non importa Streamlit: l'app tiene una ``Database`` per sessione
(vedi ``views/comuni.py``), gli script ne creano una propria.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import mysql.connector
from mysql.connector import Error as MySQLError

from .config import ConfigMySQL

log = logging.getLogger(__name__)


class Database:
    def __init__(self, cfg: ConfigMySQL):
        self.cfg = cfg
        self._conn = None

    # ------------------------------------------------------------------ #
    def connessione(self):
        """Connessione attiva, ricreata o riconnessa se necessario."""
        if self._conn is None:
            self._conn = mysql.connector.connect(**self.cfg.parametri_connessione())
            return self._conn
        try:
            self._conn.ping(reconnect=True, attempts=3, delay=1)
        except MySQLError:
            log.warning("Connessione MySQL persa, la ricreo")
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = mysql.connector.connect(**self.cfg.parametri_connessione())
        return self._conn

    def chiudi(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # ------------------------------------------------------------------ #
    @contextmanager
    def cursore(self) -> Iterator[Any]:
        cur = self.connessione().cursor(dictionary=True)
        try:
            yield cur
        finally:
            cur.close()

    @contextmanager
    def transazione(self) -> Iterator[Any]:
        """Cursore dentro una transazione esplicita: commit se il blocco
        termina senza eccezioni, rollback altrimenti."""
        conn = self.connessione()
        if conn.in_transaction:
            conn.rollback()
        conn.start_transaction()
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: tuple | list | dict | None = None) -> list[dict]:
        with self.cursore() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def query_uno(self, sql: str, params: tuple | list | dict | None = None) -> dict | None:
        righe = self.query(sql, params)
        return righe[0] if righe else None

    def esegui(self, sql: str, params: tuple | list | dict | None = None) -> int:
        """Esegue una singola istruzione in autocommit; restituisce lastrowid
        se c'e', altrimenti il numero di righe toccate."""
        with self.cursore() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid or cur.rowcount

    def tabella_esiste(self, nome: str) -> bool:
        r = self.query_uno(
            "SELECT COUNT(*) AS n FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            (nome,),
        )
        return bool(r and r["n"])

    def colonna_esiste(self, tabella: str, colonna: str) -> bool:
        r = self.query_uno(
            "SELECT COUNT(*) AS n FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            (tabella, colonna),
        )
        return bool(r and r["n"])
