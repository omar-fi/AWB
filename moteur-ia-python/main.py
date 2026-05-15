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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
