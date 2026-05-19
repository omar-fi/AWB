"""
Crée la table `reclamation` dans MySQL si elle n'existe pas encore.
Usage : source venv/bin/activate && python create_reclamation_table.py
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

SQL = """
CREATE TABLE IF NOT EXISTS reclamation (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    client_id         BIGINT       NOT NULL,
    type_reclamation  VARCHAR(100) NOT NULL,
    description       TEXT,
    statut            VARCHAR(50)  NOT NULL DEFAULT 'OUVERTE',
    date_reclamation  DATETIME     NOT NULL,
    date_resolution   DATETIME     DEFAULT NULL,
    CONSTRAINT fk_reclamation_client FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

if __name__ == "__main__":
    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(SQL)
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Table `reclamation` créée (ou déjà existante).")
