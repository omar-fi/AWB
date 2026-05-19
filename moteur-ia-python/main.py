import os
import sys
import time
import json
import logging
import datetime
import threading
import uvicorn
import mysql.connector
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from typing import Dict, Any
from pydantic import BaseModel, Field
from fastapi import FastAPI, Depends, HTTPException, Query, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from security import verify_token

load_dotenv()

# ── Logging application ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AWB-AI-SERVICE] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("microservice_ia.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("awb.main")

# ──────────────────────────────────────────────────────────────────────────
#  LIFESPAN — Démarrage & arrêt automatique du Scheduler de prédictions
# ──────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager FastAPI :
      • AU DÉMARRAGE  → Lance le scheduler de prédictions en arrière-plan.
      • À L'ARRÊT    → Arrête proprement le scheduler.
    """
    logger.info("═" * 60)
    logger.info("🤖  AWB AI MICROSERVICE — Démarrage en cours...")
    logger.info("═" * 60)

    from scheduler import demarrer_scheduler_background, get_scheduler

    def _lancer_avec_delai():
        time.sleep(10)
        logger.info("🟢 Lancement du Scheduler de Prédictions AWB...")
        demarrer_scheduler_background(executer_maintenant=False)
        logger.info("⏰ Scheduler actif — en attente du prochain batch nocturne...")

    t = threading.Thread(target=_lancer_avec_delai, name="AWB-Scheduler-Starter", daemon=True)
    t.start()

    yield

    try:
        get_scheduler().arreter()
        logger.info("🔴 Scheduler arrêté proprement.")
    except Exception:
        pass


app = FastAPI(
    title="AWB AI Microservice (XGBoost)",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration DB ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
    "use_pure": True,
}

from fastapi import BackgroundTasks

# ── ENDPOINTS AGENTS IA ──────────────────────────────────────────────────────

@app.post("/api/v1/ia/train")
def trigger_training(background_tasks: BackgroundTasks):
    """
    Agent 1 : Déclenche le réentraînement des modèles XGBoost en arrière-plan.
    """
    from agent_entrainement import main as run_training
    logger.info("🚀 [Agent 1] Déclenchement du réentraînement des modèles...")
    
    def _train_task():
        try:
            run_training()
            logger.info("✅ [Agent 1] Réentraînement des modèles terminé avec succès.")
        except Exception as e:
            logger.error(f"❌ [Agent 1] Erreur lors de l'entraînement : {e}")

    background_tasks.add_task(_train_task)
    return {"status": "started", "message": "Réentraînement des modèles lancé en tâche de fond."}


@app.post("/api/v1/ia/predict")
def trigger_predictions(client_id: int = Query(None, description="ID client optionnel")):
    """
    Agent 2 : Calcule les prédictions de visite pour un client spécifique ou pour tous les clients.
    """
    from agent_prediction import calculer_predictions_pour_client, run_batch_predictions
    if client_id is not None:
        logger.info(f"🚀 [Agent 2] Calcul de prédiction pour le client {client_id}...")
        try:
            res = calculer_predictions_pour_client(client_id, action="MANUEL")
            return {"status": "success", "client_id": client_id, "data": res}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur prédiction client {client_id}: {e}")
    else:
        logger.info("🚀 [Agent 2] Lancement du batch de prédictions...")
        ok, ko = run_batch_predictions()
        return {"status": "success", "predictions_ok": ok, "predictions_ko": ko}


@app.post("/api/v1/ia/strategy")
def trigger_strategies(client_id: int = Query(None, description="ID client optionnel"), force: bool = Query(False, description="Forcer le recalcul de tous les clients")):
    """
    Agent 3 : Calcule les stratégies et GenAI insights pour les clients en attente.
    """
    from agent_strategie import analyser_strategie_pour_client, run_batch_strategies
    if client_id is not None:
        logger.info(f"🚀 [Agent 3] Calcul de stratégie pour le client {client_id}...")
        try:
            res = analyser_strategie_pour_client(client_id)
            return {"status": "success", "client_id": client_id, "data": res}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur stratégie client {client_id}: {e}")
    else:
        logger.info(f"🚀 [Agent 3] Lancement de la génération des stratégies (force={force})...")
        ok, ko = run_batch_strategies(force_all=force)
        return {"status": "success", "strategies_ok": ok, "strategies_ko": ko}


@app.post("/api/v1/ia/run-batch")
def trigger_full_batch():
    """
    Orchestrateur : Lance séquentiellement l'Agent 2 (Prédiction) puis l'Agent 3 (Stratégie) pour tous les clients.
    """
    logger.info("🚀 Lancement du batch IA complet (Prédictions puis Stratégies)...")
    from agent_prediction import run_batch_predictions
    from agent_strategie import run_batch_strategies
    
    start_time = time.time()
    
    # Phase 1 : Prédiction (Agent 2)
    p_ok, p_ko = run_batch_predictions()
    
    # Phase 2 : Stratégie (Agent 3)
    s_ok, s_ko = run_batch_strategies(force_all=False)
    
    duration = round(time.time() - start_time, 2)
    logger.info(f"✅ Batch IA complet exécuté en {duration}s. Prédictions OK/KO: {p_ok}/{p_ko}, Stratégies OK/KO: {s_ok}/{s_ko}")
    
    return {
        "status": "success",
        "duration_seconds": duration,
        "predictions": {"ok": p_ok, "ko": p_ko},
        "strategies": {"ok": s_ok, "ko": s_ko}
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
