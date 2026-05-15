import logging
import time

# --- CONFIGURATION DU LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("nightly_batch.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _charger_clients():
    """
    Charge tous les clients depuis MySQL.
    Le batch nocturne doit recalculer une prédiction pour chaque client.
    """
    from consumer_ia import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM client ORDER BY id")
    clients = cursor.fetchall()
    cursor.close()
    conn.close()
    return clients


def main():
    logger.info("🚀 Démarrage du Batch de nuit IA autonome (MySQL → XGBoost → MySQL)...")
    start_time = time.time()
    nb_ok = 0
    nb_ko = 0
    
    try:
        from consumer_ia import recalculer_prediction

        clients = _charger_clients()
        logger.info(f"📊 Clients à recalculer : {len(clients)}")

        for client in clients:
            client_id = client["id"]
            try:
                recalculer_prediction(client_id, action="BATCH_NOCTURNE")
                nb_ok += 1
            except Exception as e:
                nb_ko += 1
                logger.error(f"❌ Client {client_id} non traité : {e}")

    except Exception as e:
        logger.error(f"❌ Erreur critique lors de l'exécution du batch : {e}")

    duration = round(time.time() - start_time, 2)
    logger.info("=" * 60)
    logger.info(f"✅ Batch terminé en {duration:.1f}s | OK={nb_ok} | KO={nb_ko}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
