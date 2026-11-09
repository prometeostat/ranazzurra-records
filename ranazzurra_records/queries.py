"""Tutto l'SQL dell'applicazione, parametrizzato con ``%s``.

Regole:
- ``vasca_codice``/``tipo_vasca`` va sempre selezionato nelle query sulle
  gare, perche' l'ordinamento ne dipende;
- le classifiche usano ``DENSE_RANK`` partizionato per gara, vasca **e sesso**;
- niente stringhe tra doppi apici: su Aiven lo ``sql_mode`` contiene
  ``ANSI_QUOTES`` e ``"..."`` diventa un identificatore.
"""

# --------------------------------------------------------------------- #
# Anagrafiche di base
# --------------------------------------------------------------------- #
GARE = """
SELECT g.id, g.codice_gara, g.descrizione, sn.codice AS stile, d.metri AS distanza
FROM gare g
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d ON g.distanza_id = d.id
"""

TIPI_VASCA = "SELECT id, codice, descrizione FROM tipi_vasca"

# --------------------------------------------------------------------- #
# Atleti
# --------------------------------------------------------------------- #
ATLETI = """
SELECT id, cognome, nome, sesso, anno_nascita, attivo, note
FROM atleti
{where}
ORDER BY cognome, nome, anno_nascita
"""

ATLETA_INSERT = """
INSERT INTO atleti (cognome, nome, sesso, anno_nascita, note)
VALUES (%s, %s, %s, %s, %s)
"""

ATLETA_UPDATE = """
UPDATE atleti
SET cognome = %s, nome = %s, sesso = %s, anno_nascita = %s, attivo = %s, note = %s
WHERE id = %s
"""

ATLETA_DISATTIVA = "UPDATE atleti SET attivo = FALSE WHERE id = %s"
ATLETA_DELETE = "DELETE FROM atleti WHERE id = %s"
ATLETA_CONTA_RECORD = "SELECT COUNT(*) AS n FROM record_personali WHERE atleta_id = %s"

# --------------------------------------------------------------------- #
# Personali
# --------------------------------------------------------------------- #
PERSONALI = """
SELECT rp.id, rp.atleta_id, a.cognome, a.nome, a.sesso, a.anno_nascita,
       rp.gara_id, g.descrizione AS gara, sn.codice AS stile, d.metri AS distanza,
       tv.codice AS tipo_vasca, rp.tipo_vasca_id,
       rp.tempo_secondi, rp.tempo_formattato, rp.data_record, rp.luogo,
       rp.manifestazione, rp.note
FROM record_personali rp
JOIN atleti a       ON rp.atleta_id = a.id
JOIN gare g         ON rp.gara_id = g.id
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d     ON g.distanza_id = d.id
JOIN tipi_vasca tv  ON rp.tipo_vasca_id = tv.id
{where}
ORDER BY a.cognome, a.nome, tv.codice, sn.codice, d.metri
"""

PERSONALE_DI = """
SELECT id, tempo_secondi, tempo_formattato, data_record
FROM record_personali
WHERE atleta_id = %s AND gara_id = %s AND tipo_vasca_id = %s
"""

PERSONALE_DI_PER_UPDATE = PERSONALE_DI + " FOR UPDATE"

PERSONALE_INSERT = """
INSERT INTO record_personali
    (atleta_id, gara_id, tipo_vasca_id, tempo_secondi, tempo_formattato,
     data_record, luogo, manifestazione, note)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

PERSONALE_UPDATE = """
UPDATE record_personali
SET tempo_secondi = %s, tempo_formattato = %s, data_record = %s,
    luogo = %s, manifestazione = %s, note = %s
WHERE id = %s
"""

PERSONALE_DELETE = "DELETE FROM record_personali WHERE id = %s"

# Personali di tutti gli atleti per una gara+vasca: base del confronto.
PERSONALI_GARA_VASCA = """
SELECT rp.atleta_id, a.sesso, rp.tempo_secondi
FROM record_personali rp
JOIN atleti a ON rp.atleta_id = a.id
WHERE rp.gara_id = %s AND rp.tipo_vasca_id = %s AND rp.tempo_secondi IS NOT NULL
"""

# --------------------------------------------------------------------- #
# Record societari (top 3) - stessa classifica del sito
# --------------------------------------------------------------------- #
CLASSIFICA = """
SELECT g.id AS gara_id, g.descrizione AS gara, d.metri AS distanza, sn.codice AS stile,
       tv.codice AS tipo_vasca, a.sesso, a.id AS atleta_id, a.cognome, a.nome,
       a.anno_nascita, rp.tempo_secondi, rp.tempo_formattato, rp.data_record,
       rp.luogo, rp.manifestazione,
       DENSE_RANK() OVER (
           PARTITION BY g.id, rp.tipo_vasca_id, a.sesso
           ORDER BY rp.tempo_secondi ASC
       ) AS posizione
FROM record_personali rp
JOIN atleti a       ON rp.atleta_id = a.id
JOIN gare g         ON rp.gara_id = g.id
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d     ON g.distanza_id = d.id
JOIN tipi_vasca tv  ON rp.tipo_vasca_id = tv.id
WHERE rp.tempo_secondi IS NOT NULL
  AND a.sesso IN ('M', 'F')
"""

TOP3 = "SELECT * FROM (" + CLASSIFICA + ") c WHERE c.posizione <= 3 " \
       "ORDER BY c.distanza, c.stile, c.tipo_vasca, c.sesso, c.posizione, c.cognome"

# --------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------- #
CONTEGGI = """
SELECT
  (SELECT COUNT(*) FROM atleti WHERE attivo = TRUE) AS atleti_attivi,
  (SELECT COUNT(*) FROM atleti) AS atleti_totali,
  (SELECT COUNT(*) FROM record_personali) AS personali,
  (SELECT COUNT(DISTINCT atleta_id) FROM record_personali) AS atleti_con_personali,
  (SELECT COUNT(*) FROM gare) AS gare
"""

# Tutte le prestazioni datate di una gara+vasca (personali, piu' lo storico
# dei risultati importati quando la tabella esiste): servono alla curva di
# progressione del record.
PROGRESSIONE_PERSONALI = """
SELECT rp.data_record AS data, rp.tempo_secondi, rp.tempo_formattato,
       CONCAT(a.cognome, ' ', a.nome) AS atleta, a.sesso
FROM record_personali rp
JOIN atleti a ON rp.atleta_id = a.id
WHERE rp.gara_id = %s AND rp.tipo_vasca_id = %s AND rp.data_record IS NOT NULL
"""

PROGRESSIONE_RISULTATI = """
SELECT r.data_gara AS data, r.tempo_secondi, r.tempo_formattato,
       CONCAT(a.cognome, ' ', a.nome) AS atleta, a.sesso
FROM risultati r
JOIN atleti a ON r.atleta_id = a.id
WHERE r.gara_id = %s AND r.tipo_vasca_id = %s AND r.tempo_secondi IS NOT NULL
"""

ULTIMI_PERSONALI = """
SELECT rp.data_record, rp.tempo_formattato, CONCAT(a.cognome, ' ', a.nome) AS atleta,
       a.sesso, g.descrizione AS gara, tv.codice AS tipo_vasca, rp.luogo
FROM record_personali rp
JOIN atleti a      ON rp.atleta_id = a.id
JOIN gare g        ON rp.gara_id = g.id
JOIN tipi_vasca tv ON rp.tipo_vasca_id = tv.id
WHERE rp.data_record IS NOT NULL
ORDER BY rp.data_record DESC, rp.id DESC
LIMIT %s
"""

# --------------------------------------------------------------------- #
# Importazione risultati (tabelle della migrazione 001)
# --------------------------------------------------------------------- #
MANIFESTAZIONE_CERCA = """
SELECT id, nome, data_inizio, data_fine, luogo
FROM manifestazioni WHERE nome = %s AND data_inizio = %s
"""

MANIFESTAZIONE_INSERT = """
INSERT INTO manifestazioni (nome, data_inizio, data_fine, luogo, tipo_vasca_id, fonte)
VALUES (%s, %s, %s, %s, %s, %s)
"""

IMPORTAZIONI_PER_FILE = """
SELECT i.id, i.created_at, i.file_nome, i.utente, i.risultati_inseriti
FROM importazioni i WHERE i.file_sha256 = %s ORDER BY i.id
"""

IMPORTAZIONE_INSERT = """
INSERT INTO importazioni
    (file_sha256, file_nome, drive_file_id, manifestazione_id, utente,
     righe_lette, righe_ranazzurra)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

IMPORTAZIONE_CHIUDI = """
UPDATE importazioni
SET risultati_inseriti = %s, personali_aggiornati = %s, atleti_creati = %s, riepilogo = %s
WHERE id = %s
"""

IMPORTAZIONI_ELENCO = """
SELECT i.id, i.created_at, i.file_nome, i.utente, m.nome AS manifestazione,
       m.data_inizio, i.righe_ranazzurra, i.risultati_inseriti,
       i.personali_aggiornati, i.atleti_creati
FROM importazioni i
LEFT JOIN manifestazioni m ON i.manifestazione_id = m.id
ORDER BY i.id DESC
LIMIT %s
"""

RISULTATI_DELLA_MANIFESTAZIONE = """
SELECT atleta_id, gara_id, tipo_vasca_id, turno, tempo_secondi, stato
FROM risultati WHERE manifestazione_id = %s
"""

RISULTATO_INSERT = """
INSERT INTO risultati
    (atleta_id, gara_id, tipo_vasca_id, manifestazione_id, turno, data_gara,
     tempo_secondi, tempo_formattato, stato, posizione, cronometraggio,
     titolo_gara, pagina_pdf, esito, importazione_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE id = id
"""

ALIAS_TUTTI = "SELECT alias_normalizzato, anno_nascita, atleta_id FROM atleti_alias"

ALIAS_INSERT = """
INSERT INTO atleti_alias (alias_normalizzato, anno_nascita, atleta_id, origine)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE atleta_id = atleta_id
"""

PERSONALE_COLLEGA_RISULTATO = "UPDATE record_personali SET risultato_id = %s WHERE id = %s"
