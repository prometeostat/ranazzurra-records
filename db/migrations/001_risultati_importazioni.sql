-- Migrazione 001 · storico risultati e importazioni FIN
--
-- Cosa fa: crea le tabelle nuove (schema_migrazioni, manifestazioni,
-- importazioni, risultati, atleti_alias) e aggiunge a record_personali la
-- colonna facoltativa risultato_id, per sapere da quale risultato importato
-- viene un personale.
--
-- Cosa NON fa: non modifica, sposta o cancella nessun dato esistente. Le
-- tabelle atleti, record_personali, gare e le anagrafiche restano come sono.
--
-- Si puo' rieseguire: ogni passo controlla se e' gia' stato fatto.
-- Modo consigliato:   python -m ranazzurra_records.migrazioni --applica
--                     (fa prima un backup JSON di atleti e personali)
-- In alternativa: eseguire il file intero da MySQL Workbench.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS schema_migrazioni (
    versione     VARCHAR(50)  NOT NULL PRIMARY KEY,
    descrizione  VARCHAR(255) NULL,
    applicata_il TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Manifestazioni da cui arrivano i risultati importati
CREATE TABLE IF NOT EXISTS manifestazioni (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nome          VARCHAR(200) NOT NULL,
    data_inizio   DATE         NOT NULL,
    data_fine     DATE         NULL,
    luogo         VARCHAR(200) NULL,
    tipo_vasca_id INT          NULL,
    fonte         VARCHAR(50)  NULL,
    note          TEXT         NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_manifestazione (nome, data_inizio),
    CONSTRAINT fk_manif_vasca FOREIGN KEY (tipo_vasca_id) REFERENCES tipi_vasca(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Una riga per ogni conferma di importazione: quale file, quando, cosa ha scritto
CREATE TABLE IF NOT EXISTS importazioni (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    file_sha256          CHAR(64)     NOT NULL,
    file_nome            VARCHAR(255) NOT NULL,
    drive_file_id        VARCHAR(128) NULL,
    manifestazione_id    INT          NULL,
    utente               VARCHAR(100) NULL,
    righe_lette          INT          NOT NULL DEFAULT 0,
    righe_ranazzurra     INT          NOT NULL DEFAULT 0,
    risultati_inseriti   INT          NOT NULL DEFAULT 0,
    personali_aggiornati INT          NOT NULL DEFAULT 0,
    atleti_creati        INT          NOT NULL DEFAULT 0,
    riepilogo            JSON         NULL,
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_import_sha (file_sha256),
    KEY idx_import_drive (drive_file_id),
    CONSTRAINT fk_import_manif FOREIGN KEY (manifestazione_id) REFERENCES manifestazioni(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Storico di tutte le prestazioni importate (non solo i personali).
-- La chiave unica rende l'importazione idempotente: la stessa prestazione
-- (manifestazione, atleta, gara, vasca, turno) non entra due volte.
CREATE TABLE IF NOT EXISTS risultati (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    atleta_id         INT           NOT NULL,
    gara_id           INT           NOT NULL,
    tipo_vasca_id     INT           NOT NULL,
    manifestazione_id INT           NOT NULL,
    turno             VARCHAR(20)   NOT NULL DEFAULT '',
    data_gara         DATE          NOT NULL,
    tempo_secondi     DECIMAL(10,2) NULL,
    tempo_formattato  VARCHAR(20)   NULL,
    stato             VARCHAR(10)   NOT NULL DEFAULT 'OK',
    posizione         INT           NULL,
    cronometraggio    CHAR(1)       NULL,
    titolo_gara       VARCHAR(255)  NULL,
    pagina_pdf        INT           NULL,
    esito             VARCHAR(60)   NULL,
    importazione_id   INT           NULL,
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_risultato (manifestazione_id, atleta_id, gara_id, tipo_vasca_id, turno),
    KEY idx_ris_atleta (atleta_id, gara_id, tipo_vasca_id),
    KEY idx_ris_import (importazione_id),
    CONSTRAINT fk_ris_atleta FOREIGN KEY (atleta_id) REFERENCES atleti(id),
    CONSTRAINT fk_ris_gara FOREIGN KEY (gara_id) REFERENCES gare(id),
    CONSTRAINT fk_ris_vasca FOREIGN KEY (tipo_vasca_id) REFERENCES tipi_vasca(id),
    CONSTRAINT fk_ris_manif FOREIGN KEY (manifestazione_id) REFERENCES manifestazioni(id),
    CONSTRAINT fk_ris_import FOREIGN KEY (importazione_id) REFERENCES importazioni(id),
    CONSTRAINT ck_ris_stato CHECK (stato IN ('OK', 'SQ', 'RIT', 'NP', 'NC')),
    CONSTRAINT ck_ris_tempo CHECK ((stato = 'OK' AND tempo_secondi IS NOT NULL)
                                   OR (stato <> 'OK' AND tempo_secondi IS NULL)),
    CONSTRAINT ck_ris_cron CHECK (cronometraggio IS NULL OR cronometraggio IN ('A', 'M'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Grafie alternative di un atleta confermate a mano durante un'importazione
-- (alias normalizzato come lo produce importazione/matching.py)
CREATE TABLE IF NOT EXISTS atleti_alias (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    alias_normalizzato VARCHAR(200) NOT NULL,
    anno_nascita       INT          NOT NULL DEFAULT 0,
    atleta_id          INT          NOT NULL,
    origine            VARCHAR(100) NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_alias (alias_normalizzato, anno_nascita),
    CONSTRAINT fk_alias_atleta FOREIGN KEY (atleta_id) REFERENCES atleti(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- record_personali.risultato_id (facoltativa): solo se non c'e' gia'
SET @c := (SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema = DATABASE() AND table_name = 'record_personali'
             AND column_name = 'risultato_id');
SET @s := IF(@c = 0,
    'ALTER TABLE record_personali ADD COLUMN risultato_id INT NULL, ADD CONSTRAINT fk_rp_risultato FOREIGN KEY (risultato_id) REFERENCES risultati(id) ON DELETE SET NULL',
    'SELECT 1');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO schema_migrazioni (versione, descrizione)
VALUES ('001', 'storico risultati e importazioni FIN')
ON DUPLICATE KEY UPDATE versione = versione;
