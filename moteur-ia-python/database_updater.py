import os
import logging
import datetime
import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("database_updater")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}


def get_db_connection():
    """
    Crée et retourne une connexion robuste à MySQL.
    Lève une exception claire si la connexion échoue.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            logger.info("✅ Connexion à MySQL établie.")
            return conn
    except Error as e:
        logger.error(f"❌ Impossible de se connecter à MySQL : {e}")
        raise


def verifier_et_migrer_schema(conn):
    """
    Vérifie que les colonnes critiques existent dans la table 'prediction_visite'.
    Si une colonne est manquante, elle est créée automatiquement (migration douce / safe).
    Cela évite les erreurs en cas de discordance entre le modèle Python et le schéma SQL.
    """
    colonnes_requises = {
        "insight_genai":            "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS insight_genai TEXT;",
        "strategie_prescrite":      "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS strategie_prescrite TEXT;",
        "score_probabilite_global": "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS score_probabilite_global DOUBLE;",
        "date_dernier_calcul":      "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS date_dernier_calcul DATETIME;",
        "niveau_risque":            "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS niveau_risque VARCHAR(20);",
        "score_churn":              "ALTER TABLE prediction_visite ADD COLUMN IF NOT EXISTS score_churn DOUBLE;",
    }
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'prediction_visite'
        """, (DB_CONFIG["database"],))
        colonnes_existantes = {row["COLUMN_NAME"] for row in cursor.fetchall()}
        
        migrations = 0
        for colonne, sql_migration in colonnes_requises.items():
            if colonne not in colonnes_existantes:
                logger.warning(f"🔧 Colonne manquante détectée : '{colonne}' → Migration en cours...")
                cursor.execute(sql_migration)
                conn.commit()
                logger.info(f"   ✅ Colonne '{colonne}' ajoutée avec succès.")
                migrations += 1
        
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'prediction_visite'
              AND INDEX_NAME = 'uq_prediction_client'
        """, (DB_CONFIG["database"],))
        result = cursor.fetchone()
        if result["cnt"] == 0:
            logger.warning("🔧 Contrainte UNIQUE manquante sur client_id → Création en cours...")
            cursor.execute("""
                ALTER TABLE prediction_visite 
                ADD CONSTRAINT uq_prediction_client UNIQUE (client_id);
            """)
            conn.commit()
            logger.info("   ✅ Contrainte UNIQUE(client_id) ajoutée.")
            migrations += 1
        
        cursor.close()
        if migrations == 0:
            logger.info("🗂️  Schéma à jour, aucune migration nécessaire.")
        else:
            logger.info(f"🗂️  Migration terminée ({migrations} modification(s) appliquée(s)).")
    except Error as e:
        logger.warning(f"⚠️ Vérification du schéma partielle : {e}")


def sauvegarder_predictions(predictions_list: List[Dict[str, Any]]) -> bool:
    """
    Effectue un UPSERT en batch sur la table 'prediction_visite'.
    - Si la ligne (client_id) existe déjà : mise à jour des colonnes.
    - Si elle n'existe pas : insertion d'une nouvelle ligne.
    
    Utilise des requêtes préparées (paramétrées) pour une sécurité maximale.
    Rollback automatique en cas d'erreur de transaction.

    Retourne True si tout s'est passé correctement, False sinon.
    """
    if not predictions_list:
        logger.warning("⚠️ Aucune prédiction à sauvegarder.")
        return False

    UPSERT_SQL = """
        INSERT INTO prediction_visite 
            (client_id, score_probabilite_global, insight_genai, strategie_prescrite, niveau_risque, date_dernier_calcul)
        VALUES 
            (%s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            score_probabilite_global = VALUES(score_probabilite_global),
            insight_genai            = VALUES(insight_genai),
            strategie_prescrite      = VALUES(strategie_prescrite),
            niveau_risque            = VALUES(niveau_risque),
            date_dernier_calcul      = NOW();
    """

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        verifier_et_migrer_schema(conn)
        
        cursor = conn.cursor()
        
        data = [
            (
                p.get("client_id"),
                p.get("score_probabilite_global"),
                p.get("insight_genai", ""),
                p.get("strategie_prescrite", ""),
                p.get("niveau_risque", "FAIBLE"),
            )
            for p in predictions_list
        ]
        
        cursor.executemany(UPSERT_SQL, data)
        conn.commit()
        
        logger.info(f"✅ Mise à jour réussie pour {cursor.rowcount} lignes ({len(predictions_list)} clients traités).")
        return True

    except Error as e:
        logger.error(f"❌ Erreur de transaction MySQL : {e}")
        if conn and conn.is_connected():
            conn.rollback()
            logger.warning("↩️  Rollback effectué — aucune donnée corrompue.")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
            logger.info("🔌 Connexion MySQL fermée.")


if __name__ == "__main__":
    predictions_test = [
        {
            "client_id": 1,
            "score_probabilite_global": 0.92,
            "insight_genai": "Le client affiche une baisse de 40% de ses dépôts sur le trimestre.",
            "strategie_prescrite": "Rendez-vous Directeur + Proposition DAT."
        },
        {
            "client_id": 2,
            "score_probabilite_global": 0.78,
            "insight_genai": "Stabilité des flux entrants et dépenses courantes maîtrisées.",
            "strategie_prescrite": "Suivi classique."
        },
        {
            "client_id": 3,
            "score_probabilite_global": 0.95,
            "insight_genai": "Deux rejets de prélèvements constatés ce mois-ci.",
            "strategie_prescrite": "Offrir 1 an de gratuité sur le Pack."
        },
    ]
    
    print("\n" + "=" * 60)
    print("💾 TEST MODULE : DATABASE UPDATER (UPSERT BATCH)")
    print("=" * 60 + "\n")
    
    succes = sauvegarder_predictions(predictions_test)
    
    if succes:
        print("\n🎉 Test réussi — Base de données mise à jour.")
    else:
        print("\n💥 Test échoué — Vérifiez la connexion MySQL et le schéma.")
