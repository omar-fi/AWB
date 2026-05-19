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
    
    # Lancement de l'Agent 2 (Prédiction)
    logger.info("🚀 Démarrage de la Phase 1 (Agent 2 - Prédiction)...")
    try:
        from agent_prediction import run_batch_predictions
        nb_ok, nb_ko = run_batch_predictions()
        duration = round(time.time() - start_time, 2)
        logger.info("=" * 60)
        logger.info(f"✅ Phase 1 (Agent 2 - Prédiction) terminée en {duration:.1f}s | OK={nb_ok} | KO={nb_ko}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ Erreur critique lors de l'exécution de l'Agent 2 : {e}")

    # Lancement de l'Agent 3 (Stratégie)
    logger.info("🚀 Démarrage de la Phase 2 (Agent 3 - Analyse Santé et Stratégie)...")
    try:
        from agent_strategie import run_batch_strategies
        s_ok, s_ko = run_batch_strategies(force_all=False)
        logger.info("=" * 60)
        logger.info(f"✅ Phase 2 (Agent 3 - Stratégie) terminée | OK={s_ok} | KO={s_ko}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ Erreur critique lors de l'exécution de l'Agent 3 : {e}")

if __name__ == "__main__":
    main()
