-- Schema Database per Record Societari Ranazzurra S.r.l.
-- MySQL/MariaDB Schema per AIVEN

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Tabella Atleti
DROP TABLE IF EXISTS atleti;
CREATE TABLE atleti (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cognome VARCHAR(100) NOT NULL,
    nome VARCHAR(100) NOT NULL,
    sesso ENUM('M', 'F'),
    anno_nascita INT,
    attivo BOOLEAN DEFAULT TRUE,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_atleta (cognome, nome, anno_nascita),
    INDEX idx_cognome (cognome),
    INDEX idx_nome (nome),
    INDEX idx_attivo (attivo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella Tipi di Vasca
DROP TABLE IF EXISTS tipi_vasca;
CREATE TABLE tipi_vasca (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codice VARCHAR(10) UNIQUE NOT NULL,
    descrizione VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO tipi_vasca (codice, descrizione) VALUES 
    ('VC', 'Vasca Corta (25m)'),
    ('VL', 'Vasca Lunga (50m)');

-- Tabella Stili di Nuoto
DROP TABLE IF EXISTS stili_nuoto;
CREATE TABLE stili_nuoto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codice VARCHAR(10) UNIQUE NOT NULL,
    descrizione VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO stili_nuoto (codice, descrizione) VALUES 
    ('SL', 'Stile Libero'),
    ('DO', 'Dorso'),
    ('RA', 'Rana'),
    ('DF', 'Delfino'),
    ('MX', 'Misti');

-- Tabella Distanze
DROP TABLE IF EXISTS distanze;
CREATE TABLE distanze (
    id INT AUTO_INCREMENT PRIMARY KEY,
    metri INT UNIQUE NOT NULL,
    descrizione VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO distanze (metri, descrizione) VALUES 
    (50, '50 metri'),
    (100, '100 metri'),
    (200, '200 metri'),
    (400, '400 metri'),
    (800, '800 metri'),
    (1500, '1500 metri');

-- Tabella Gare (combinazione stile + distanza)
DROP TABLE IF EXISTS gare;
CREATE TABLE gare (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stile_id INT NOT NULL,
    distanza_id INT NOT NULL,
    codice_gara VARCHAR(20) UNIQUE NOT NULL,
    descrizione VARCHAR(100),
    FOREIGN KEY (stile_id) REFERENCES stili_nuoto(id) ON DELETE CASCADE,
    FOREIGN KEY (distanza_id) REFERENCES distanze(id) ON DELETE CASCADE,
    UNIQUE KEY unique_gara (stile_id, distanza_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Popolo le gare standard
INSERT INTO gare (stile_id, distanza_id, codice_gara, descrizione)
SELECT s.id, d.id, CONCAT(d.metri, '_', s.codice), CONCAT(d.metri, 'm ', s.descrizione)
FROM stili_nuoto s
CROSS JOIN distanze d
WHERE 
    -- SL: tutte le distanze
    (s.codice = 'SL') OR
    -- DO, RA, DF: 50, 100, 200
    (s.codice IN ('DO', 'RA', 'DF') AND d.metri IN (50, 100, 200)) OR
    -- MX: 100, 200, 400
    (s.codice = 'MX' AND d.metri IN (100, 200, 400));

-- Tabella Record Personali
DROP TABLE IF EXISTS record_personali;
CREATE TABLE record_personali (
    id INT AUTO_INCREMENT PRIMARY KEY,
    atleta_id INT NOT NULL,
    gara_id INT NOT NULL,
    tipo_vasca_id INT NOT NULL,
    tempo_secondi DECIMAL(10, 2) NOT NULL,
    tempo_formattato VARCHAR(20),
    data_record DATE,
    luogo VARCHAR(200),
    manifestazione VARCHAR(200),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (atleta_id) REFERENCES atleti(id) ON DELETE CASCADE,
    FOREIGN KEY (gara_id) REFERENCES gare(id) ON DELETE CASCADE,
    FOREIGN KEY (tipo_vasca_id) REFERENCES tipi_vasca(id) ON DELETE CASCADE,
    UNIQUE KEY unique_record (atleta_id, gara_id, tipo_vasca_id),
    INDEX idx_atleta (atleta_id),
    INDEX idx_gara (gara_id),
    INDEX idx_tempo (tempo_secondi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella Record Societari (migliori assoluti per categoria)
DROP TABLE IF EXISTS record_societari;
CREATE TABLE record_societari (
    id INT AUTO_INCREMENT PRIMARY KEY,
    gara_id INT NOT NULL,
    tipo_vasca_id INT NOT NULL,
    categoria ENUM('M', 'F', 'ASSOLUTO') NOT NULL,
    atleta_id INT,
    tempo_secondi DECIMAL(10, 2) NOT NULL,
    tempo_formattato VARCHAR(20),
    data_record DATE,
    luogo VARCHAR(200),
    manifestazione VARCHAR(200),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (gara_id) REFERENCES gare(id) ON DELETE CASCADE,
    FOREIGN KEY (tipo_vasca_id) REFERENCES tipi_vasca(id) ON DELETE CASCADE,
    FOREIGN KEY (atleta_id) REFERENCES atleti(id) ON DELETE SET NULL,
    UNIQUE KEY unique_record_societario (gara_id, tipo_vasca_id, categoria),
    INDEX idx_gara (gara_id),
    INDEX idx_categoria (categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- View per query facilitate
DROP VIEW IF EXISTS v_record_personali;
CREATE VIEW v_record_personali AS
SELECT 
    rp.id,
    a.cognome,
    a.nome,
    a.sesso,
    a.anno_nascita,
    tv.codice as tipo_vasca,
    tv.descrizione as vasca_descrizione,
    g.codice_gara,
    g.descrizione as gara_descrizione,
    sn.codice as stile,
    d.metri as distanza,
    rp.tempo_secondi,
    rp.tempo_formattato,
    rp.data_record,
    rp.luogo,
    rp.manifestazione,
    rp.note,
    rp.created_at,
    rp.updated_at
FROM record_personali rp
JOIN atleti a ON rp.atleta_id = a.id
JOIN gare g ON rp.gara_id = g.id
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d ON g.distanza_id = d.id
JOIN tipi_vasca tv ON rp.tipo_vasca_id = tv.id;

DROP VIEW IF EXISTS v_record_societari;
CREATE VIEW v_record_societari AS
SELECT 
    rs.id,
    rs.categoria,
    a.cognome,
    a.nome,
    tv.codice as tipo_vasca,
    tv.descrizione as vasca_descrizione,
    g.codice_gara,
    g.descrizione as gara_descrizione,
    sn.codice as stile,
    d.metri as distanza,
    rs.tempo_secondi,
    rs.tempo_formattato,
    rs.data_record,
    rs.luogo,
    rs.manifestazione,
    rs.note,
    rs.created_at,
    rs.updated_at
FROM record_societari rs
JOIN gare g ON rs.gara_id = g.id
JOIN stili_nuoto sn ON g.stile_id = sn.id
JOIN distanze d ON g.distanza_id = d.id
JOIN tipi_vasca tv ON rs.tipo_vasca_id = tv.id
LEFT JOIN atleti a ON rs.atleta_id = a.id;

-- Stored Function per convertire secondi a tempo formattato
DROP FUNCTION IF EXISTS secondi_to_tempo;
DELIMITER //
CREATE FUNCTION secondi_to_tempo(secondi DECIMAL(10,2))
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    DECLARE ore INT;
    DECLARE minuti INT;
    DECLARE sec DECIMAL(10,2);
    DECLARE result VARCHAR(20);
    
    SET ore = FLOOR(secondi / 3600);
    SET minuti = FLOOR((secondi - ore * 3600) / 60);
    SET sec = secondi - (ore * 3600) - (minuti * 60);
    
    IF ore > 0 THEN
        SET result = CONCAT(ore, ':', LPAD(minuti, 2, '0'), ':', LPAD(FORMAT(sec, 2), 5, '0'));
    ELSE
        SET result = CONCAT(minuti, ':', LPAD(FORMAT(sec, 2), 5, '0'));
    END IF;
    
    RETURN result;
END//
DELIMITER ;

-- Stored Function per convertire tempo formattato a secondi
DROP FUNCTION IF EXISTS tempo_to_secondi;
DELIMITER //
CREATE FUNCTION tempo_to_secondi(tempo VARCHAR(20))
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE secondi DECIMAL(10,2);
    DECLARE parti INT;
    DECLARE ore INT DEFAULT 0;
    DECLARE minuti INT DEFAULT 0;
    DECLARE sec DECIMAL(10,2) DEFAULT 0;
    
    SET tempo = TRIM(tempo);
    SET parti = LENGTH(tempo) - LENGTH(REPLACE(tempo, ':', '')) + 1;
    
    IF parti = 3 THEN
        -- Formato H:MM:SS.CC
        SET ore = CAST(SUBSTRING_INDEX(tempo, ':', 1) AS UNSIGNED);
        SET minuti = CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(tempo, ':', 2), ':', -1) AS UNSIGNED);
        SET sec = CAST(SUBSTRING_INDEX(tempo, ':', -1) AS DECIMAL(10,2));
        SET secondi = ore * 3600 + minuti * 60 + sec;
    ELSEIF parti = 2 THEN
        -- Formato M:SS.CC
        SET minuti = CAST(SUBSTRING_INDEX(tempo, ':', 1) AS UNSIGNED);
        SET sec = CAST(SUBSTRING_INDEX(tempo, ':', -1) AS DECIMAL(10,2));
        SET secondi = minuti * 60 + sec;
    ELSE
        -- Solo secondi
        SET secondi = CAST(tempo AS DECIMAL(10,2));
    END IF;
    
    RETURN secondi;
END//
DELIMITER ;

-- Procedure per aggiornare record societari automaticamente
DROP PROCEDURE IF EXISTS aggiorna_record_societari;
DELIMITER //
CREATE PROCEDURE aggiorna_record_societari()
BEGIN
    -- Aggiorna record maschili
    INSERT INTO record_societari (gara_id, tipo_vasca_id, categoria, atleta_id, tempo_secondi, tempo_formattato, data_record)
    SELECT 
        rp.gara_id,
        rp.tipo_vasca_id,
        'M' as categoria,
        rp.atleta_id,
        MIN(rp.tempo_secondi) as tempo_secondi,
        secondi_to_tempo(MIN(rp.tempo_secondi)) as tempo_formattato,
        MAX(rp.data_record) as data_record
    FROM record_personali rp
    JOIN atleti a ON rp.atleta_id = a.id
    WHERE a.sesso = 'M'
    GROUP BY rp.gara_id, rp.tipo_vasca_id
    ON DUPLICATE KEY UPDATE
        tempo_secondi = VALUES(tempo_secondi),
        tempo_formattato = VALUES(tempo_formattato),
        atleta_id = VALUES(atleta_id),
        data_record = VALUES(data_record);
    
    -- Aggiorna record femminili
    INSERT INTO record_societari (gara_id, tipo_vasca_id, categoria, atleta_id, tempo_secondi, tempo_formattato, data_record)
    SELECT 
        rp.gara_id,
        rp.tipo_vasca_id,
        'F' as categoria,
        rp.atleta_id,
        MIN(rp.tempo_secondi) as tempo_secondi,
        secondi_to_tempo(MIN(rp.tempo_secondi)) as tempo_formattato,
        MAX(rp.data_record) as data_record
    FROM record_personali rp
    JOIN atleti a ON rp.atleta_id = a.id
    WHERE a.sesso = 'F'
    GROUP BY rp.gara_id, rp.tipo_vasca_id
    ON DUPLICATE KEY UPDATE
        tempo_secondi = VALUES(tempo_secondi),
        tempo_formattato = VALUES(tempo_formattato),
        atleta_id = VALUES(atleta_id),
        data_record = VALUES(data_record);
    
    -- Aggiorna record assoluti
    INSERT INTO record_societari (gara_id, tipo_vasca_id, categoria, atleta_id, tempo_secondi, tempo_formattato, data_record)
    SELECT 
        rp.gara_id,
        rp.tipo_vasca_id,
        'ASSOLUTO' as categoria,
        rp.atleta_id,
        MIN(rp.tempo_secondi) as tempo_secondi,
        secondi_to_tempo(MIN(rp.tempo_secondi)) as tempo_formattato,
        MAX(rp.data_record) as data_record
    FROM record_personali rp
    GROUP BY rp.gara_id, rp.tipo_vasca_id
    ON DUPLICATE KEY UPDATE
        tempo_secondi = VALUES(tempo_secondi),
        tempo_formattato = VALUES(tempo_formattato),
        atleta_id = VALUES(atleta_id),
        data_record = VALUES(data_record);
END//
DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

-- Query di verifica
SELECT 'Schema creato con successo!' as Status;
SELECT COUNT(*) as 'Gare create' FROM gare;
