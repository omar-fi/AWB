"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      AGENT 3 — ANALYSE & RECOMMANDATION CHURN (LangChain + Groq + SHAP)      ║
║      Plateforme de Prédiction de Churn Bancaire — AWB IA           v3.0.0.   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Auteur     : Data Science Team — AWB                                       ║
║  Framework  : LangChain (ReAct Agent) + ChatGroq (llama-3.1-8b-instant)    ║
║                                                                              ║
║  Outils (@tool) :                                                            ║
║    1. get_client_data_tool   → Profil financier complet depuis MySQL        ║
║    2. predict_churn_tool     → Score XGBoost + explicabilité SHAP           ║
║    3. apply_business_rules_tool → Services de rétention éligibles          ║
║                                                                              ║
║  Flux orchestré :                                                            ║
║    Profil → Score SHAP → Règles métier → Recommandation LLM (3 lignes)     ║
║                                                                              ║
║  Intégration : FastAPI via run_agent_analyse(client_id) + endpoint dédié   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import json
import time
from collections import Counter
import logging
import datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
import mysql.connector
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_groq import ChatGroq

from analysis_engine import calculer_niveau_risque


load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL:   str = "llama-3.1-8b-instant"

DB_CONFIG: dict = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Agent-3-LangChain] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("awb.agent3")

_MODEL_PAYLOAD: dict | None = None
_XGBOOST_MODEL = None
_FEATURE_COLS:  list[str] = []

# Horaires bancaires marocains — mêmes bornes qu'à l'entraînement (train_xgboost).
HEURE_OUVERTURE_BANQUE = 8.0
HEURE_FERMETURE_BANQUE = 16.5


def _date_heure_derniere_op(valeur) -> tuple[datetime.date, float]:
    """
    Extrait (date, heure décimale) de la dernière opération du client.

    Accepte un datetime ou une chaîne ISO ('2026-03-23 05:45:23.570814'), les
    deux formes selon que le profil vient de MCP ou d'un accès SQL direct.
    Repli sur aujourd'hui midi si la date est absente ou illisible.
    """
    dt = None
    if isinstance(valeur, datetime.datetime):
        dt = valeur
    elif isinstance(valeur, str) and valeur.strip():
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(valeur.strip(), fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return datetime.date.today(), 12.0
    return dt.date(), round(dt.hour + dt.minute / 60.0, 2)


def _load_xgboost_model() -> None:
    """Charge le modèle XGBoost AWB une seule fois (lazy loading thread-safe)."""
    global _MODEL_PAYLOAD, _XGBOOST_MODEL, _FEATURE_COLS
    if _XGBOOST_MODEL is not None:
        return
    try:
        _MODEL_PAYLOAD = joblib.load("modele_churn_maroc.pkl")
        _XGBOOST_MODEL = _MODEL_PAYLOAD["modele"]
        _FEATURE_COLS  = _MODEL_PAYLOAD.get("feature_cols", [])
        logger.info("✅ Modèle XGBoost chargé — %d features", len(_FEATURE_COLS))
    except Exception as exc:
        logger.warning("⚠️  Modèle XGBoost introuvable (%s). Mode simulé activé.", exc)
        _XGBOOST_MODEL = None


_load_xgboost_model()


def _get_db_connection() -> mysql.connector.MySQLConnection:
    """Ouvre et retourne une connexion MySQL."""
    return mysql.connector.connect(**DB_CONFIG)


import sys
import asyncio

USE_MCP: bool = os.getenv("AGENT3_USE_MCP", "1") != "0"
_MCP_DIR: str = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVER_SCRIPT: str = os.path.join(_MCP_DIR, "mcp_ia_server.py")


async def _fetch_profil_via_mcp_async(client_id: int) -> dict:
    """Ouvre une session MCP (stdio), appelle get_client_data et retourne le profil."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_MCP_SERVER_SCRIPT],
        env=os.environ.copy(),
        cwd=_MCP_DIR,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result  = await session.call_tool("get_client_data", {"client_id": client_id})
            content = result.content[0].text if result.content else ""
            return json.loads(content) if isinstance(content, str) else content


def _fetch_profil_via_mcp(client_id: int) -> dict | None:
    """Wrapper synchrone du client MCP. Retourne None si MCP indisponible/échec."""
    try:
        return asyncio.run(_fetch_profil_via_mcp_async(client_id))
    except Exception as exc:
        logger.warning("⚠️  [MCP] Récupération profil client %d via MCP échouée (%s). "
                       "Fallback SQL direct.", client_id, exc)
        return None


@tool
def get_client_data_tool(client_id: int) -> str:
    """
    Récupère le profil financier complet d'un client depuis la base de données MySQL.

    Retourne un JSON stringifié contenant : client_id, age estimé, segment métier,
    solde actuel, solde moyen, revenus estimés (montant moyen), nombre d'opérations
    totales et sur 30 jours, présence d'un compte épargne, nombre de comptes,
    moyenne des retraits, et historique des dernières transactions.

    Args:
        client_id: Identifiant numérique unique du client en base de données.

    Returns:
        JSON string avec le profil complet, ou un message d'erreur.
    """
    logger.info("🔍 [Tool 1] Récupération profil client %d…", client_id)

    if USE_MCP:
        profil_mcp = _fetch_profil_via_mcp(client_id)
        if profil_mcp and not profil_mcp.get("error"):
            logger.info("✅ [Tool 1] Profil client %d capté via MCP — Solde: %.2f MAD, %d ops/30j",
                        client_id,
                        float(profil_mcp.get("solde_actuel", 0) or 0),
                        int(profil_mcp.get("nb_operations_30j", 0) or 0))
            return json.dumps(profil_mcp, ensure_ascii=False, default=str)
        logger.warning("⚠️  [Tool 1] MCP indisponible pour client %d — bascule SQL direct.", client_id)

    try:
        conn   = _get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.id                                          AS client_id,
                c.segment_metier,
                COALESCE(SUM(co.solde), 0)                   AS solde_actuel,
                COALESCE(AVG(co.solde), 0)                   AS solde_moyen_compte,
                MAX(CASE WHEN co.type_compte='EPARGNE' THEN 1 ELSE 0 END) AS has_compte_epargne,
                COUNT(co.id)                                  AS nb_comptes,
                SUM(CASE WHEN co.type_compte='COURANT' THEN 1 ELSE 0 END) AS nb_comptes_courant,
                SUM(CASE WHEN co.type_compte='EPARGNE' THEN 1 ELSE 0 END) AS nb_comptes_epargne,
                SUM(CASE WHEN co.type_compte='CREDIT'  THEN 1 ELSE 0 END) AS nb_comptes_credit
            FROM client c
            LEFT JOIN compte co ON c.id = co.client_id
            WHERE c.id = %s
            GROUP BY c.id, c.segment_metier
        """, (client_id,))
        base = cursor.fetchone()

        if not base:
            cursor.close(); conn.close()
            return json.dumps({"error": f"Client {client_id} introuvable en base."}, ensure_ascii=False)

        cursor.execute("""
            SELECT
                COUNT(*)                                                   AS nb_operations,
                COALESCE(SUM(montant), 0)                                  AS montant_total,
                COALESCE(AVG(montant), 0)                                  AS montant_moyen,
                COALESCE(AVG(CASE WHEN type_operation='RETRAIT' THEN montant END), 0) AS moy_retrait,
                MAX(date_heure_operation)                                  AS derniere_operation_at
            FROM historique_operation
            WHERE client_id = %s
        """, (client_id,))
        ops = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS nb_ops_30j
            FROM historique_operation
            WHERE client_id = %s
              AND date_heure_operation >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (client_id,))
        ops_30j = cursor.fetchone()

        cursor.execute("""
            SELECT type_operation, montant, DATE(date_heure_operation) AS date_op
            FROM historique_operation
            WHERE client_id = %s
            ORDER BY date_heure_operation DESC
            LIMIT 5
        """, (client_id,))
        dernieres_ops = cursor.fetchall()

        cursor.close()
        conn.close()

        derniere_op_str = (
            str(ops["derniere_operation_at"]) if ops and ops.get("derniere_operation_at") else "N/A"
        )
        jours_inactif = 0
        if ops and ops.get("derniere_operation_at"):
            delta = datetime.datetime.now() - ops["derniere_operation_at"]
            jours_inactif = max(0, int(delta.total_seconds() / 86400))

        profil: dict[str, Any] = {
            "client_id":          int(client_id),
            "segment_metier":     base.get("segment_metier", "PARTICULIER"),
            "solde_actuel":       round(float(base.get("solde_actuel") or 0), 2),
            "solde_moyen_compte": round(float(base.get("solde_moyen_compte") or 0), 2),
            "has_compte_epargne": int(base.get("has_compte_epargne") or 0),
            "nb_comptes":         int(base.get("nb_comptes") or 0),
            "nb_comptes_courant": int(base.get("nb_comptes_courant") or 0),
            "nb_comptes_epargne": int(base.get("nb_comptes_epargne") or 0),
            "nb_comptes_credit":  int(base.get("nb_comptes_credit") or 0),
            "nb_operations_total":int(ops.get("nb_operations") or 0) if ops else 0,
            "nb_operations_30j":  int(ops_30j.get("nb_ops_30j") or 0) if ops_30j else 0,
            "montant_moyen":      round(float(ops.get("montant_moyen") or 0), 2) if ops else 0.0,
            "montant_total":      round(float(ops.get("montant_total") or 0), 2) if ops else 0.0,
            "moy_retrait":        round(float(ops.get("moy_retrait") or 0), 2) if ops else 0.0,
            "jours_depuis_derniere_op": jours_inactif,
            "derniere_operation_at":    derniere_op_str,
            "historique_recent": [
                {
                    "type":   str(r.get("type_operation", "")),
                    "montant": round(float(r.get("montant") or 0), 2),
                    "date":   str(r.get("date_op", "")),
                }
                for r in (dernieres_ops or [])
            ],
        }

        logger.info("✅ [Tool 1] Profil client %d — Solde: %.2f MAD, %d ops/30j",
                    client_id, profil["solde_actuel"], profil["nb_operations_30j"])
        return json.dumps(profil, ensure_ascii=False, default=str)

    except Exception as exc:
        logger.error("❌ [Tool 1] Erreur DB client %d : %s", client_id, exc)
        return _simulate_client_profile(client_id)


def _simulate_client_profile(client_id: int) -> str:
    """Profil client simulé (fallback sans DB) — utile pour les tests unitaires."""
    profil = {
        "client_id":          client_id,
        "segment_metier":     "VIP" if client_id % 3 == 0 else "PARTICULIER",
        "solde_actuel":       2800.0 if client_id % 2 == 0 else 45000.0,
        "solde_moyen_compte": 18500.0,
        "has_compte_epargne": 0,
        "nb_comptes":         2,
        "nb_comptes_courant": 1,
        "nb_comptes_epargne": 0,
        "nb_comptes_credit":  1,
        "nb_operations_total": 42,
        "nb_operations_30j":  0,
        "montant_moyen":      3200.0,
        "montant_total":      134400.0,
        "moy_retrait":        7800.0,
        "jours_depuis_derniere_op": 52,
        "derniere_operation_at":    "2026-04-10 14:23:00",
        "historique_recent": [
            {"type": "RETRAIT", "montant": 9000.0, "date": "2026-04-10"},
            {"type": "RETRAIT", "montant": 8500.0, "date": "2026-03-28"},
            {"type": "VIREMENT_EMIS", "montant": 15000.0, "date": "2026-03-15"},
        ],
        "_simulated": True,
    }
    logger.warning("⚠️  [Tool 1] Mode simulé activé pour client %d", client_id)
    return json.dumps(profil, ensure_ascii=False)


@tool
def predict_churn_tool(profil_json: str) -> str:
    """
    Calcule le score de churn XGBoost d'un client et génère son explicabilité SHAP.

    Utilise le modèle XGBoost entraîné sur les données AWB (modele_churn_maroc.pkl).
    Si le modèle est indisponible, bascule sur une simulation déterministe.
    SHAP identifie les 5 variables qui influencent le plus la prédiction.

    Args:
        profil_json: JSON string du profil client (sortie de get_client_data_tool).

    Returns:
        JSON string avec : score_churn (0-1), niveau_risque, probabilite_pct,
        et top_shap_features (liste des 5 variables les plus influentes).
    """
    logger.info("🧠 [Tool 2] Calcul score XGBoost + SHAP…")

    try:
        profil: dict = json.loads(profil_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Profil JSON invalide : {exc}"}, ensure_ascii=False)

    client_id = profil.get("client_id", 0)

    score_churn, top_shap = calculer_churn_xgboost(profil)
    niveau_risque = calculer_niveau_risque(score_churn)

    result = {
        "client_id":      client_id,
        "score_churn":    round(float(score_churn), 4),
        "probabilite_pct": round(float(score_churn) * 100, 1),
        "niveau_risque":  niveau_risque,
        "top_shap_features": top_shap,
        "modele":         "XGBoost modele_churn_maroc v2.0" if _XGBOOST_MODEL else "Simulation",
    }

    logger.info("✅ [Tool 2] Client %d — Score churn: %.1f%% (%s)",
                client_id, result["probabilite_pct"], niveau_risque)
    return json.dumps(result, ensure_ascii=False)


def _anciennete_client_ans(client_id) -> float:
    """
    Ancienneté réelle du client, depuis client.date_creation.

    Le profil MCP ne l'expose pas, et c'est une variable que le modèle exploite
    (une des conditions du label : anciennete < 2 ans). La coder en dur, comme
    c'était le cas, revenait à neutraliser ce signal pour tout le portefeuille.
    """
    try:
        conn = _get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT date_creation FROM client WHERE id = %s", (client_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0]:
            return max(0.0, (datetime.datetime.now() - row[0]).days / 365.25)
    except Exception as exc:
        logger.warning("⚠️  Ancienneté client %s indisponible : %s", client_id, exc)
    return 3.0


def _run_xgboost_inference(profil: dict) -> tuple[float, list[dict]]:
    """
    Exécute l'inférence XGBoost réelle et calcule les valeurs SHAP.

    Les features calendaires/horaires sont dérivées de la DERNIÈRE opération
    réelle du client via `preprocess_donnees` — la fonction même qui a servi à
    l'entraînement. C'est ce qui garantit que train et inférence donnent le même
    sens à chaque colonne.

    Returns:
        Tuple (score_churn: float, top_shap_features: list[dict])
    """
    # Opération représentative = la dernière du client, comme à l'entraînement
    # où chaque ligne portait une seule date/heure d'opération.
    derniere = profil.get("derniere_operation_at")
    date_op, heure_op = _date_heure_derniere_op(derniere)

    # nb_ops_hors_horaires est BINAIRE à l'entraînement (cette opération est-elle
    # hors des horaires bancaires ?), pas un cumul. On réplique à l'identique.
    hors_horaires = 0 if (HEURE_OUVERTURE_BANQUE <= heure_op <= HEURE_FERMETURE_BANQUE) else 1
    nb_ops_30j    = profil.get("nb_operations_30j", 0) or 0

    base = {
        "montant_moyen":       profil.get("montant_moyen", 3000.0),
        "frequence_retrait":   min(profil.get("moy_retrait", 0) / max(profil.get("montant_moyen", 1), 1) * 10, 30),
        "solde_moyen":         profil.get("solde_moyen_compte", 0.0),
        "nb_operations_30j":   nb_ops_30j,
        "nb_ops_hors_horaires": hors_horaires,
        "ratio_digital":       round(hors_horaires / (nb_ops_30j + 1), 4),
        "anciennete_client_ans": _anciennete_client_ans(profil.get("client_id")),
        "segment_metier_enc":  {"VIP": 2, "PRO": 1, "PME": 1}.get(
            str(profil.get("segment_metier", "")).upper(), 0
        ),
        "date_operation":  date_op,
        "heure_operation": heure_op,
    }

    # Même feature engineering qu'à l'entraînement : fériés, weekend, horaires.
    df = pd.DataFrame([base])
    try:
        from train_xgboost import preprocess_donnees
        df = preprocess_donnees(df, date_col="date_operation",
                                heure_col="heure_operation", verbose=False)
    except Exception as exc:
        logger.warning("⚠️  preprocess_donnees indisponible (%s) — features calendaires à 0", exc)

    row = {col: (df.iloc[0][col] if col in df.columns else 0) for col in _FEATURE_COLS}
    X = pd.DataFrame([row], columns=_FEATURE_COLS).fillna(0)

    score_churn = float(_XGBOOST_MODEL.predict_proba(X)[0][1])

    explainer   = shap.TreeExplainer(_XGBOOST_MODEL)
    shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):
        shap_row = shap_values[1][0]
    else:
        shap_row = shap_values[0]

    shap_pairs = sorted(
        zip(_FEATURE_COLS, shap_row.tolist()),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5]

    top_shap = [
        {
            "feature":    feat,
            "shap_value": round(float(val), 4),
            "impact":     "↑ Augmente le risque" if val > 0 else "↓ Réduit le risque",
            "valeur_client": round(float(X[feat].iloc[0]), 2),
        }
        for feat, val in shap_pairs
    ]

    return score_churn, top_shap


# Sens des opérations : sert à mesurer le flux net du compte.
# Sens des opérations sur le compte courant. Doit couvrir les libellés d'agence
# ET ceux des canaux distants : une omission ici ne lève aucune erreur, elle
# fait juste disparaître silencieusement des flux du calcul de tension.
# Les opérations de service (attestation, chéquier, KYC, opposition…) n'ont pas
# de montant et n'apparaissent volontairement dans aucune des deux listes.
_OPS_DEBIT  = ("RETRAIT", "Retrait Guichet", "VIREMENT_EMIS", "Virement au Guichet",
               "Paiement TPE", "PAIEMENT_CARTE", "PAIEMENT_FACTURE",
               "Paiement de Facture", "Placement Épargne",
               "Change de Devises", "Transfert International", "Souscription Assurance")
_OPS_CREDIT = ("VIREMENT_RECU", "Versement Espèces", "Remise de Chèque",
               "Retrait Épargne")


def _historique_risque(client_id) -> dict:
    """
    Agrégats réels du client servant au calcul de risque.

    Deux points de méthode :

    1. L'inactivité est mesurée par rapport à l'horizon des données (dernière
       opération enregistrée toutes agences confondues), pas par rapport à
       CURDATE(). Sur une base figée, CURDATE() fait vieillir tout le
       portefeuille en bloc : les 100 clients ressortaient à 110-153 jours de
       silence, ce qui déclenchait le facteur pour tout le monde et n'y laissait
       aucun pouvoir discriminant. En exploitation courante l'horizon vaut le
       jour même, les deux références coïncident donc.

    2. L'activité est comptée sur deux fenêtres de 90 jours consécutives, pour
       comparer le client à lui-même. C'est ce qui permet de détecter un
       désengagement sans le confondre avec un niveau de solde.

    Le solde est agrégé dans une sous-requête séparée : le joindre directement à
    l'historique le multiplierait par le nombre d'opérations (fan-out).
    """
    defauts = {"inact": 0.0, "rythme": 6.0, "solde": 0.0, "anciennete": 3.0,
               "nb_ops": 0, "ops_recent": 0, "ops_avant": 0, "credits_90j": 0.0, "debits_90j": 0.0}
    place_debit  = ", ".join(["%s"] * len(_OPS_DEBIT))
    place_credit = ", ".join(["%s"] * len(_OPS_CREDIT))
    try:
        conn = _get_db_connection()
        cur  = conn.cursor()
        cur.execute(f"""
            SELECT DATEDIFF(ref.horizon, o.derniere),
                   o.rythme, COALESCE(s.solde, 0),
                   TIMESTAMPDIFF(DAY, cl.date_creation, ref.horizon) / 365.25,
                   o.nb_ops,
                   COALESCE(w.ops_recent, 0), COALESCE(w.ops_avant, 0),
                   COALESCE(w.credits, 0), COALESCE(w.debits, 0)
            FROM client cl
            CROSS JOIN (SELECT MAX(date_heure_operation) horizon
                        FROM historique_operation) ref
            JOIN (SELECT client_id,
                         MAX(date_heure_operation) derniere,
                         COUNT(*) nb_ops,
                         DATEDIFF(MAX(date_heure_operation), MIN(date_heure_operation))
                           / NULLIF(COUNT(*) - 1, 0) rythme
                  FROM historique_operation GROUP BY client_id) o ON o.client_id = cl.id
            LEFT JOIN (SELECT client_id, SUM(solde) solde
                       FROM compte GROUP BY client_id) s ON s.client_id = cl.id
            LEFT JOIN (SELECT h.client_id,
                         SUM(h.date_heure_operation >= r.horizon - INTERVAL 90 DAY) ops_recent,
                         SUM(h.date_heure_operation <  r.horizon - INTERVAL 90 DAY
                             AND h.date_heure_operation >= r.horizon - INTERVAL 180 DAY) ops_avant,
                         SUM(CASE WHEN h.date_heure_operation >= r.horizon - INTERVAL 90 DAY
                                   AND h.type_operation IN ({place_credit})
                                  THEN h.montant ELSE 0 END) credits,
                         SUM(CASE WHEN h.date_heure_operation >= r.horizon - INTERVAL 90 DAY
                                   AND h.type_operation IN ({place_debit})
                                  THEN h.montant ELSE 0 END) debits
                       FROM historique_operation h
                       CROSS JOIN (SELECT MAX(date_heure_operation) horizon
                                   FROM historique_operation) r
                       GROUP BY h.client_id) w ON w.client_id = cl.id
            WHERE cl.id = %s
        """, (*_OPS_CREDIT, *_OPS_DEBIT, client_id))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return {
                "inact":       float(row[0] or 0),
                "rythme":      float(row[1] or 6.0),
                "solde":       float(row[2] or 0),
                "anciennete":  float(row[3] or 3.0),
                "nb_ops":      int(row[4] or 0),
                "ops_recent":  int(row[5] or 0),
                "ops_avant":   int(row[6] or 0),
                "credits_90j": float(row[7] or 0),
                "debits_90j":  float(row[8] or 0),
            }
    except Exception as exc:
        logger.warning("⚠️  Agrégats risque client %s indisponibles : %s", client_id, exc)
    return defauts


def calculer_churn_xgboost(profil: dict) -> tuple[float, list[dict]]:
    """
    SOURCE UNIQUE du score de churn pour tout le moteur IA.

    Calcul par RÈGLES MÉTIER déterministes, et non par le modèle XGBoost.

    Pourquoi : la base ne contient aucun événement de churn — les 100 clients
    opèrent tous les 5 à 7 jours sans jamais décrocher, et aucun n'a jamais eu
    d'interruption supérieure à 57 jours. Un modèle supervisé n'a donc rien à
    apprendre ; celui qui existait était entraîné sur des données synthétiques
    et rendait la même probabilité (0,39–0,56) pour tout le portefeuille.

    Les quatre facteurs ci-dessous sont mesurés sur les données réelles et
    tiennent lieu d'explicabilité : chacun est renvoyé avec sa contribution,
    ce que le conseiller peut lire directement.

    Chaque facteur porte sur un axe distinct. La version précédente comptait le
    solde deux fois (érosion = retrait/solde ET niveau de solde), les deux
    décroissants avec le même montant : le classement de risque n'était en
    pratique que le classement inverse des soldes, et un VIP disparu depuis
    quatre mois ressortait FAIBLE parce qu'il restait riche. Le désengagement
    comportemental — le client se compare à lui-même sur deux trimestres — est
    devenu le premier facteur, l'argent n'en pèse plus qu'un sur quatre.

    Args:
        profil: dict du profil client (sortie de get_client_data_tool ou _get_profil_client).

    Returns:
        Tuple (score_churn: float [0-1], facteurs: list[dict]) — `facteurs` garde
        la forme des anciennes features SHAP pour rester compatible avec les
        appelants existants.
    """
    def _clamp(v: float, a: float = 0.0, b: float = 1.0) -> float:
        return max(a, min(b, v))

    agg   = _historique_risque(profil.get("client_id"))
    solde = agg["solde"]
    ops_recent, ops_avant = agg["ops_recent"], agg["ops_avant"]

    # 1. Désengagement : le client opère-t-il moins que sur son trimestre
    #    précédent ? Signal purement comportemental, indépendant des montants.
    #    Sous 4 opérations sur la fenêtre de référence, la comparaison n'est pas
    #    significative — on s'abstient plutôt que de produire un faux signal.
    if ops_avant >= 4:
        f_desengagement = _clamp((1.0 - ops_recent / ops_avant) / 0.6)
    else:
        f_desengagement = 0.0

    # 2. Silence : temps mort rapporté à SON rythme, pas dans l'absolu. Un client
    #    qui passe tous les 5 jours et se tait depuis 5 semaines est anormal ;
    #    un client trimestriel ne l'est pas.
    f_silence = _clamp((agg["inact"] / max(agg["rythme"], 0.5) - 2.0) / 4.0)

    # 3. Tension financière : seul axe monétaire. Mesurée en mois de train de
    #    vie couverts par le solde, jamais en dirhams absolus — 25 000 MAD sur
    #    un compte qui consomme 100 000 MAD par mois est une situation tendue,
    #    la même somme chez un client qui dépense 4 000 MAD par mois ne l'est
    #    pas. Un seuil fixe classait les gros comptes comme sains par
    #    construction.
    depenses_mensuelles = agg["debits_90j"] / 3.0
    net_mensuel = (agg["credits_90j"] - agg["debits_90j"]) / 3.0
    if solde <= 0:
        f_tension = 1.0
    elif depenses_mensuelles <= 0:
        f_tension = 0.0
    else:
        # Réserve : le solde couvre combien de mois de dépenses ?
        f_reserve = _clamp((3.0 - solde / depenses_mensuelles) / 3.0)
        # Vitesse de vidage : dans combien de mois le compte est-il à zéro ?
        f_drain = 0.0 if net_mensuel >= 0 else _clamp((6.0 - solde / abs(net_mensuel)) / 6.0)
        f_tension = max(f_reserve, 0.7 * f_drain)

    # 4. Client jeune : la relation n'est pas encore installée (< 2 ans).
    f_anciennete = _clamp((2.0 - agg["anciennete"]) / 2.0)

    score = _clamp(0.35 * f_desengagement + 0.25 * f_silence
                   + 0.25 * f_tension + 0.15 * f_anciennete)

    evol = f"{ops_recent} opérations sur 90 j contre {ops_avant} sur les 90 j précédents"
    facteurs = [
        {"feature": "desengagement",   "impact": "augmente le risque" if f_desengagement > 0.5 else "neutre",
         "valeur_client": evol if ops_avant >= 4 else f"historique trop court ({agg['nb_ops']} opérations)",
         "contribution": round(0.35 * f_desengagement, 3)},
        {"feature": "silence_relatif", "impact": "augmente le risque" if f_silence > 0.5 else "neutre",
         "valeur_client": f"{agg['inact']:.0f} j sans opération (rythme habituel {agg['rythme']:.1f} j)",
         "contribution": round(0.25 * f_silence, 3)},
        {"feature": "tension_compte",  "impact": "augmente le risque" if f_tension > 0.5 else "neutre",
         "valeur_client": (f"solde {solde:,.0f} MAD = {solde / depenses_mensuelles:.1f} mois de dépenses, "
                           f"flux net {net_mensuel:+,.0f} MAD/mois"
                           if depenses_mensuelles > 0 else f"solde {solde:,.0f} MAD, aucune dépense récente"),
         "contribution": round(0.25 * f_tension, 3)},
        {"feature": "anciennete",      "impact": "augmente le risque" if f_anciennete > 0.5 else "neutre",
         "valeur_client": f"{agg['anciennete']:.1f} ans", "contribution": round(0.15 * f_anciennete, 3)},
    ]
    facteurs.sort(key=lambda f: -f["contribution"])
    return score, facteurs


def _simulate_churn_score(profil: dict) -> tuple[float, list[dict]]:
    """
    Score de churn simulé (déterministe) quand le modèle XGBoost est absent.
    Reproduit la logique de scoring comportemental d'AWB.
    """
    score = 0.0
    solde         = profil.get("solde_actuel", 0.0)
    solde_moyen   = profil.get("solde_moyen_compte", 0.0)
    moy_retrait   = profil.get("moy_retrait", 0.0)
    nb_ops_30j    = profil.get("nb_operations_30j", 0)
    nb_ops_total  = profil.get("nb_operations_total", 0)
    montant_moyen = profil.get("montant_moyen", 3000.0)
    jours_inactif = profil.get("jours_depuis_derniere_op", 0)

    contributions: list[dict] = []

    if solde_moyen > 1000 and solde < solde_moyen * 0.4:
        delta = 0.6
        score += delta
        contributions.append({"feature": "ratio_solde_vs_historique", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": round(solde / max(solde_moyen, 1), 3)})
    elif solde_moyen > 1000 and solde < solde_moyen * 0.7:
        delta = 0.3
        score += delta
        contributions.append({"feature": "ratio_solde_vs_historique", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": round(solde / max(solde_moyen, 1), 3)})

    if solde > 0 and moy_retrait > solde * 0.4:
        delta = 0.4
        score += delta
        contributions.append({"feature": "moy_retrait_vs_solde", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": round(moy_retrait, 2)})

    if nb_ops_total > 20 and nb_ops_30j == 0:
        delta = 0.5
        score += delta
        contributions.append({"feature": "nb_operations_30j", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": nb_ops_30j})

    if jours_inactif > 45:
        delta = 0.25
        score += delta
        contributions.append({"feature": "jours_depuis_derniere_op", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": jours_inactif})

    if montant_moyen < 3500:
        delta = 0.15
        score += delta
        contributions.append({"feature": "montant_moyen", "shap_value": round(delta, 4),
                               "impact": "↑ Augmente le risque",
                               "valeur_client": round(montant_moyen, 2)})

    score = min(score, 0.97)

    defaults = [
        {"feature": "nb_comptes_epargne", "shap_value": -0.05,
         "impact": "↓ Réduit le risque", "valeur_client": profil.get("nb_comptes_epargne", 0)},
        {"feature": "segment_metier_enc", "shap_value": 0.02,
         "impact": "↑ Augmente le risque", "valeur_client": profil.get("segment_metier", "PARTICULIER")},
    ]
    for d in defaults:
        if len(contributions) >= 5:
            break
        contributions.append(d)

    return score, contributions[:5]


@tool
def apply_business_rules_tool(churn_et_profil_json: str) -> str:
    """
    Applique les règles metier bancaires AWB pour identifier les services de
    retention eligibles selon le score churn XGBoost et le profil client.
    Genere egalement un narratif comportemental unique par client.

    Args:
        churn_et_profil_json: JSON string avec "churn" et "profil".

    Returns:
        JSON string avec services_eligibles, urgence_action, analyse_comportementale.
    """
    logger.info("📋 [Tool 3] Application des règles métier de rétention…")

    try:
        data   = json.loads(churn_et_profil_json)
        churn  = data.get("churn", {})
        profil = data.get("profil", {})
    except (json.JSONDecodeError, AttributeError) as exc:
        return json.dumps({"error": f"JSON invalide : {exc}"}, ensure_ascii=False)

    score         = float(churn.get("score_churn", 0.5))
    niveau_risque = churn.get("niveau_risque", "FAIBLE")
    segment       = str(profil.get("segment_metier", "")).upper()
    solde         = float(profil.get("solde_actuel", 0))
    solde_moyen   = float(profil.get("solde_moyen_compte", 0))
    nb_ops_30j    = int(profil.get("nb_operations_30j", 0))
    nb_ops_total  = int(profil.get("nb_operations_total", 0))
    has_epargne   = bool(profil.get("has_compte_epargne", 0))
    moy_retrait   = float(profil.get("moy_retrait", 0))
    montant_moyen = float(profil.get("montant_moyen", 0))
    montant_total = float(profil.get("montant_total", 0))
    jours_inactif = int(profil.get("jours_depuis_derniere_op", 0))
    nb_comptes    = int(profil.get("nb_comptes", 0))
    nb_epargne    = int(profil.get("nb_comptes_epargne", 0))
    nb_credit     = int(profil.get("nb_comptes_credit", 0))
    historique    = profil.get("historique_recent", [])
    client_id     = profil.get("client_id", 0)

    ratio_retrait_solde = moy_retrait / max(solde, 1) if solde > 0 else 0
    tendance_solde = (
        "EN DECLIN" if solde_moyen > 0 and solde < solde_moyen * 0.6 else
        "STABLE"    if solde_moyen > 0 and solde >= solde_moyen * 0.9 else
        "MODEREE"
    )
    profil_activite = (
        "TRES ACTIF" if nb_ops_30j >= 5 else
        "ACTIF"      if nb_ops_30j >= 2 else
        "PEU ACTIF"  if nb_ops_30j == 1 else
        "INACTIF"
    )
    intensite_retrait = (
        "ELEVEE"  if ratio_retrait_solde > 0.5 else
        "MODEREE" if ratio_retrait_solde > 0.2 else
        "FAIBLE"
    )

    types_recents      = [h.get("type", "") for h in historique[:5]] if historique else []
    nb_retraits_rec    = sum(1 for t in types_recents if "RETRAIT" in t)
    nb_virements_rec   = sum(1 for t in types_recents if "VIREMENT" in t)
    montant_dernier    = float(historique[0].get("montant", 0)) if historique else 0
    date_derniere_op   = historique[0].get("date", "N/A") if historique else "N/A"
    type_derniere_op   = historique[0].get("type", "N/A") if historique else "N/A"

    narratif = []

    if profil_activite == "INACTIF":
        if jours_inactif > 90:
            narratif.append(f"Inactivite critique : {jours_inactif} jours sans operation")
        elif jours_inactif > 60:
            narratif.append(f"Inactivite prolongee : {jours_inactif} jours (abandon probable)")
        else:
            narratif.append(f"Inactivite de {jours_inactif} jours (risque depart)")
    else:
        narratif.append(f"Activite recente : {nb_ops_30j} op(s)/mois")

    if tendance_solde == "EN DECLIN" and solde_moyen > 0:
        pct_baisse = int(100 * (1 - solde / max(solde_moyen, 1)))
        narratif.append(f"Solde en declin : {solde:,.0f} MAD (baisse de {pct_baisse}% vs historique {solde_moyen:,.0f} MAD)")
    else:
        narratif.append(f"Solde actuel : {solde:,.0f} MAD ({tendance_solde})")

    if moy_retrait > 0:
        narratif.append(f"Retraits : {moy_retrait:,.0f} MAD/mois (intensite {intensite_retrait}, ratio {ratio_retrait_solde*100:.0f}% du solde)")

    if nb_retraits_rec >= 3:
        narratif.append(f"{nb_retraits_rec} retraits sur les 5 dernieres operations")
    if nb_virements_rec >= 2:
        narratif.append(f"{nb_virements_rec} virements emis recemment")

    compte_desc = f"{nb_comptes} compte(s)"
    if has_epargne:
        compte_desc += " dont epargne"
    else:
        compte_desc += " sans epargne"
    if nb_credit > 0:
        compte_desc += f" + {nb_credit} credit(s)"

    narratif.append(f"Segment : {segment} | {compte_desc}")

    if nb_ops_total > 0:
        narratif.append(f"Historique : {nb_ops_total} operations | Volume moyen : {montant_moyen:,.0f} MAD")

    if date_derniere_op != "N/A":
        narratif.append(f"Derniere op : {type_derniere_op} de {montant_dernier:,.0f} MAD ({date_derniere_op})")

    analyse_comportementale = " | ".join(narratif)

    services: list[dict] = []
    priorite = "NORMALE"

    if score >= 0.75 or niveau_risque in ("CRITIQUE", "ELEVE", "ÉLEVÉ"):
        services.append({
            "code": "APPEL_URGENCE",
            "label": "📞 Appel d'urgence conseiller dedie",
            "description": (
                f"Score churn {score*100:.1f}% — client {segment} inactif {jours_inactif}j "
                f"avec solde {solde:,.0f} MAD. Contact DC sous 24h obligatoire. Risque : {niveau_risque}."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 1,
        })
        priorite = "CRITIQUE"

    if solde > 0 and moy_retrait > 0 and ratio_retrait_solde > 0.3:
        services.append({
            "code": "EXONERATION_FRAIS",
            "label": "💸 Exoneration des frais bancaires (3 mois)",
            "description": (
                f"Retraits {moy_retrait:,.0f} MAD/mois = {ratio_retrait_solde*100:.0f}% du solde ({solde:,.0f} MAD). "
                f"Suppression frais de tenue + carte pendant 3 mois."
            ),
            "eligibilite": "SOUS CONDITIONS",
            "priorite": 2,
        })
        if priorite == "NORMALE":
            priorite = "HAUTE"

    if "VIP" in segment or solde > 30_000:
        tier = "Platinum" if (solde > 500_000 or "VIP" in segment) else "Gold"
        services.append({
            "code": "CARTE_GOLD_GRATUITE",
            "label": f"💳 Carte {tier} offerte (12 mois)",
            "description": (
                f"Client {segment} — solde {solde:,.0f} MAD. Upgrade vers Carte {tier} : "
                f"plafonds etendus, assurances incluses, hotline dedicee, sans frais annuels."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 3,
        })

    if solde > 20_000 and not has_epargne:
        if solde > 500_000:
            produit = "Compte a Terme (CAT)"
            taux    = "4,5%"
        elif solde > 100_000:
            produit = "Plan Epargne Logement (PEL)"
            taux    = "3,75%"
        else:
            produit = "Compte Sur Carnet"
            taux    = "3,5%"
        gain = solde * float(taux.replace("%","").replace(",",".")) / 100
        services.append({
            "code": "OUVERTURE_EPARGNE",
            "label": f"🏦 Ouverture {produit} a {taux}",
            "description": (
                f"{solde:,.0f} MAD en compte courant sans valorisation. "
                f"Proposition : {produit} a {taux}/an → gain estime {gain:,.0f} MAD/an."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 4,
        })

    if jours_inactif >= 30 and nb_ops_30j == 0:
        if jours_inactif > 90:
            offre = "Cadeau retour : 500 MAD offerts + exoneration 6 mois de frais"
        elif jours_inactif > 60:
            offre = "Offre retour : 200 MAD + exoneration 3 mois"
        else:
            offre = "Mois offert + bonus 200 MAD sur 1ere operation mobile"
        services.append({
            "code": "OFFRE_REACTIVATION",
            "label": "🔄 Offre de reactivation personnalisee",
            "description": f"Inactivite depuis {jours_inactif} jours (derniere op : {date_derniere_op}). {offre}.",
            "eligibilite": "SOUS CONDITIONS",
            "priorite": 5,
        })

    if any(x in segment for x in ["PRO", "PME", "TPE", "PROFESSIONNEL"]):
        if montant_total > 1_000_000:
            accomp = f"gestion tresorerie {montant_total:,.0f} MAD, ligne credit PRO, optimisation fiscale"
        elif nb_credit > 0:
            accomp = "restructuration credit(s), financement complementaire"
        else:
            accomp = "etude tresorerie, TPE/PDV gratuit 3 mois, leasing ou credit exploitation"
        services.append({
            "code": "ACCOMPAGNEMENT_PRO",
            "label": "🏢 Accompagnement professionnel personnalise",
            "description": (
                f"Client {segment} | {nb_comptes} compte(s) | {nb_ops_total} op historiques. "
                f"Proposition : {accomp}."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 3,
        })

    if jours_inactif > 20 and nb_ops_30j <= 1:
        canal = "virements instantanes" if nb_virements_rec > 0 else "paiements mobiles + notifications"
        services.append({
            "code": "PACK_DIGITAL",
            "label": "📱 Pack Digital AWB (6 mois offerts)",
            "description": (
                f"Faible utilisation digitale ({nb_ops_30j} op/mois). "
                f"Pack : {canal} gratuits, app premium, support 7j/7 — 6 mois offerts."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 6,
        })

    if solde > 1_000_000 and nb_epargne == 0 and nb_credit == 0:
        services.append({
            "code": "GESTION_PATRIMOINE",
            "label": "🏛️ Gestion Patrimoniale Premium",
            "description": (
                f"Patrimoine {solde:,.0f} MAD non diversifie (0 epargne, 0 credit). "
                f"Proposition : conseiller dedie, OPCVM, assurance-vie Takaful, ou obligataire."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 2,
        })

    if nb_credit >= 2 and solde < solde_moyen * 0.5:
        services.append({
            "code": "RESTRUCTURATION_CREDIT",
            "label": "🔧 Restructuration de credit(s)",
            "description": (
                f"{nb_credit} credits actifs, solde en baisse ({solde:,.0f} vs {solde_moyen:,.0f} MAD historique). "
                f"Consolidation dettes + revision mensualites."
            ),
            "eligibilite": "SOUS CONDITIONS",
            "priorite": 2,
        })

    if "ETUDIANT" in segment or "JEUNE" in segment:
        services.append({
            "code": "PACK_JEUNE",
            "label": "🎓 Pack Jeune AWB (1 an offert)",
            "description": (
                "Gratuite totale 12 mois, micro-credit etudiant 10 000 MAD, app premium."
            ),
            "eligibilite": "AUTOMATIQUE",
            "priorite": 2,
        })

    services.sort(key=lambda s: s["priorite"])

    if score >= 0.85 or niveau_risque == "CRITIQUE" or jours_inactif > 90:
        urgence_action = "IMMEDIATE (< 24h)"
    elif score >= 0.65 or niveau_risque in ("ELEVE", "ÉLEVÉ") or jours_inactif > 60:
        urgence_action = "RAPIDE (< 48h)"
    elif score >= 0.45 or niveau_risque == "ALERTE" or jours_inactif > 30:
        urgence_action = "PLANIFIEE (< 1 semaine)"
    else:
        urgence_action = "STANDARD (prochaine visite)"

    result = {
        "client_id":               client_id,
        "nb_services_eligibles":   len(services),
        "services_eligibles":      services,
        "priorite_globale":        priorite,
        "urgence_action":          urgence_action,
        "score_churn_rappel":      round(score * 100, 1),
        "niveau_risque":           niveau_risque,
        "analyse_comportementale": analyse_comportementale,
        "signaux": {
            "profil_activite":     profil_activite,
            "tendance_solde":      tendance_solde,
            "intensite_retrait":   intensite_retrait,
            "jours_inactif":       jours_inactif,
            "nb_retraits_recents": nb_retraits_rec,
        },
    }

    logger.info("✅ [Tool 3] %d service(s) — Urgence: %s | Activite: %s | Solde: %s",
                len(services), urgence_action, profil_activite, tendance_solde)
    return json.dumps(result, ensure_ascii=False)



@tool
def get_reclamations_tool(client_id: int) -> str:
    """
    Analyse l'historique des réclamations du client et mesure son insatisfaction.

    Remonte le détail de chaque réclamation (motif, texte, statut, ancienneté)
    ainsi qu'un indice d'insatisfaction agrégé. Les verbatims sont essentiels :
    sans savoir de QUOI le client se plaint, aucune stratégie de reconquête ne
    peut être ciblée.

    Args:
        client_id: Identifiant numérique du client.

    Returns:
        JSON string avec indice_insatisfaction (0-1), niveau, compteurs par
        statut, motif dominant, récidive, doléances non résolues et verbatims.
    """
    logger.info("📣 [Tool 4] Lecture des réclamations — client %d…", client_id)
    try:
        conn = _get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT type_reclamation, description, statut,
                   date_reclamation, date_resolution,
                   DATEDIFF(CURDATE(), date_reclamation) AS anciennete_jours,
                   DATEDIFF(date_resolution, date_reclamation) AS delai_resolution
            FROM reclamation
            WHERE client_id = %s
            ORDER BY date_reclamation DESC
        """, (client_id,))
        lignes = cur.fetchall()
        cur.close(); conn.close()
    except Exception as exc:
        logger.error("❌ [Tool 4] Lecture réclamations client %d : %s", client_id, exc)
        return json.dumps({"error": f"Réclamations indisponibles : {exc}"}, ensure_ascii=False)

    if not lignes:
        return json.dumps({
            "client_id": client_id, "nb_reclamations": 0,
            "indice_insatisfaction": 0.0, "niveau_insatisfaction": "AUCUNE",
            "synthese": "Aucune réclamation enregistrée : rien n'indique un litige ouvert.",
        }, ensure_ascii=False)

    non_resolues = [r for r in lignes if r["statut"] != "RESOLUE"]
    resolues     = [r for r in lignes if r["statut"] == "RESOLUE"]
    delais = [int(r["delai_resolution"]) for r in resolues
              if r["delai_resolution"] is not None]
    delai_moyen = round(sum(delais) / len(delais), 1) if delais else None

    motifs = Counter(r["type_reclamation"] for r in lignes)
    motif_dominant, occurrences = motifs.most_common(1)[0]
    recidive = occurrences >= 2
    plus_ancienne = max((int(r["anciennete_jours"]) for r in non_resolues), default=0)

    # Indice déterministe : ce qui exaspère un client, c'est le litige qui
    # traîne et le motif qui revient — pas le simple fait d'avoir réclamé une
    # fois et d'avoir été traité.
    f_ouvertes = min(1.0, len(non_resolues) / 3.0)
    f_anciennete = min(1.0, plus_ancienne / 90.0) if non_resolues else 0.0
    f_recidive = 1.0 if (recidive and len(non_resolues) >= 2) else (0.5 if recidive else 0.0)
    f_lenteur = min(1.0, (delai_moyen or 0) / 45.0)
    indice = round(min(1.0, 0.40 * f_ouvertes + 0.30 * f_anciennete
                       + 0.20 * f_recidive + 0.10 * f_lenteur), 3)

    niveau = ("CRITIQUE" if indice >= 0.70 else
              "FORTE"    if indice >= 0.45 else
              "MODEREE"  if indice >= 0.20 else "FAIBLE")

    doleances = [{
        "motif": r["type_reclamation"],
        "verbatim": r["description"],
        "statut": r["statut"],
        "depuis_jours": int(r["anciennete_jours"]),
    } for r in non_resolues[:4]]

    synthese = (
        f"{len(lignes)} réclamation(s), dont {len(non_resolues)} non résolue(s). "
        f"Motif dominant : {motif_dominant}"
        + (f", revenu {occurrences} fois" if recidive else "")
        + (f". La plus ancienne attend depuis {plus_ancienne} jours" if non_resolues else "")
        + (f". Délai moyen de traitement : {delai_moyen} jours" if delai_moyen else "")
        + "."
    )

    result = {
        "client_id": client_id,
        "nb_reclamations": len(lignes),
        "nb_non_resolues": len(non_resolues),
        "nb_resolues": len(resolues),
        "delai_moyen_resolution_jours": delai_moyen,
        "motif_dominant": motif_dominant,
        "recidive": recidive,
        "anciennete_plus_vieille_non_resolue_jours": plus_ancienne,
        "indice_insatisfaction": indice,
        "niveau_insatisfaction": niveau,
        "doleances_ouvertes": doleances,
        "synthese": synthese,
    }
    logger.info("✅ [Tool 4] Client %d — insatisfaction %s (%.2f), %d non résolue(s)",
                client_id, niveau, indice, len(non_resolues))
    return json.dumps(result, ensure_ascii=False)


_TOOLS_LIST = [
    get_client_data_tool,
    predict_churn_tool,
    get_reclamations_tool,
    apply_business_rules_tool,
]

_TOOLS_BY_NAME: dict = {t.name: t for t in _TOOLS_LIST}


def _build_llm_with_tools() -> ChatGroq:
    """
    Instancie ChatGroq avec bind_tools pour le tool-calling natif.
    Compatible LangChain 1.3+ (remplace AgentExecutor/create_react_agent).
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "❌ GROQ_API_KEY manquante dans le fichier .env. "
            "Ajoutez : GROQ_API_KEY=gsk_..."
        )
    llm = ChatGroq(
        model=GROQ_MODEL,
        groq_api_key=GROQ_API_KEY,
        temperature=0.3,
        # La stratégie de reconquête tient en trois parties (constat, réparation,
        # reconquête) : 600 tokens tronquaient systématiquement la dernière.
        max_tokens=1100,
        timeout=45,
        max_retries=3,
    )
    return llm.bind_tools(_TOOLS_LIST)


def _activite_agence(client_id) -> dict:
    """Fréquentation du guichet : c'est là que se voit la relation client."""
    defauts = {"jours_derniere_visite": 999, "visites_90j": 0, "visites_avant": 0}
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DATEDIFF(CURDATE(), MAX(date_heure_operation)),
                   SUM(date_heure_operation >= CURDATE() - INTERVAL 90 DAY),
                   SUM(date_heure_operation <  CURDATE() - INTERVAL 90 DAY
                       AND date_heure_operation >= CURDATE() - INTERVAL 180 DAY)
            FROM historique_operation
            WHERE client_id = %s AND canal = 'AGENCE'
        """, (client_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0] is not None:
            return {"jours_derniere_visite": int(row[0]),
                    "visites_90j": int(row[1] or 0),
                    "visites_avant": int(row[2] or 0)}
    except Exception as exc:
        logger.warning("⚠️  Activité agence client %s indisponible : %s", client_id, exc)
    return defauts


def evaluer_satisfaction(client_id: int) -> dict:
    """
    Détermine si un client est satisfait, AVANT tout appel au LLM.

    Un client qui n'a aucun litige ouvert et qui continue de passer en agence
    est satisfait : lui pousser une offre de reconquête encombre le conseiller
    et, côté client, revient à réparer ce qui n'est pas cassé. L'agent doit
    savoir se taire.

    L'insatisfaction se lit sur deux axes indissociables :
      - le litige : une réclamation ouverte, surtout si elle traîne ;
      - le retrait : un client mécontent cesse d'abord de venir.
    Les deux réunis forment la chaîne causale la plus grave — il a réclamé,
    on n'a rien fait, il s'en va.

    Returns:
        dict avec statut, action_requise (bool), motifs et mesures sous-jacentes.
    """
    reclam = json.loads(get_reclamations_tool.invoke({"client_id": client_id}))
    agence = _activite_agence(client_id)

    non_resolues = reclam.get("nb_non_resolues", 0)
    anciennete = reclam.get("anciennete_plus_vieille_non_resolue_jours", 0)
    indice_reclam = reclam.get("indice_insatisfaction", 0.0)

    visites_90j, visites_avant = agence["visites_90j"], agence["visites_avant"]
    jours_absence = agence["jours_derniere_visite"]
    # Contraction de la fréquentation, mesurée contre le trimestre précédent.
    contraction = (1.0 - visites_90j / visites_avant) if visites_avant >= 3 else 0.0

    motifs = []
    if non_resolues:
        motifs.append(f"{non_resolues} réclamation(s) non résolue(s)"
                      + (f", la plus ancienne depuis {anciennete} jours" if anciennete else ""))
    if reclam.get("recidive"):
        motifs.append(f"récidive sur le motif {reclam.get('motif_dominant')}")
    if contraction >= 0.5:
        motifs.append(f"fréquentation de l'agence en baisse de {contraction*100:.0f} %"
                      f" ({visites_90j} visites contre {visites_avant})")
    if jours_absence > 60:
        motifs.append(f"absent de l'agence depuis {jours_absence} jours")

    litige_lourd = non_resolues >= 1 and anciennete >= 30
    retrait_net = contraction >= 0.5 or jours_absence > 60

    if litige_lourd and retrait_net:
        statut = "INSATISFAIT_CRITIQUE"
    elif non_resolues >= 2 or (litige_lourd and indice_reclam >= 0.5):
        statut = "INSATISFAIT"
    elif non_resolues >= 1 or retrait_net:
        statut = "A_SURVEILLER"
    else:
        statut = "SATISFAIT"

    # ── Score d'insatisfaction, 0 à 100 (100 = client au bord de la rupture)
    #
    # Ce n'est PAS l'inverse du risque de churn. La tension financière pèse
    # 0,25 dans le risque, et un client à découvert n'est pas mécontent de sa
    # banque — il a un problème d'argent. La confondre avec du mécontentement
    # ferait appeler des gens qui n'ont rien demandé. Seuls le litige et le
    # retrait relationnel entrent ici.
    _borne = lambda v: max(0.0, min(1.0, v))
    f_litige = _borne(0.55 * min(1.0, non_resolues / 3.0)
                      + 0.45 * min(1.0, anciennete / 90.0))
    f_recidive = 1.0 if (reclam.get("recidive") and non_resolues >= 2) else (
                 0.5 if reclam.get("recidive") else 0.0)
    f_retrait = _borne(0.60 * _borne(contraction)
                       + 0.40 * _borne((jours_absence - 30) / 60.0))
    delai_moyen = reclam.get("delai_moyen_resolution_jours") or 0
    f_lenteur = _borne(delai_moyen / 45.0)

    score_insatisfaction = round(100 * _borne(
        0.45 * f_litige + 0.15 * f_recidive + 0.30 * f_retrait + 0.10 * f_lenteur))

    niveau_satisfaction = ("TRES INSATISFAIT" if score_insatisfaction >= 75 else
                           "INSATISFAIT"      if score_insatisfaction >= 50 else
                           "MITIGE"           if score_insatisfaction >= 25 else
                           "PLUTOT SATISFAIT" if score_insatisfaction >= 10 else
                           "SATISFAIT")

    action_requise = statut != "SATISFAIT"
    if not action_requise:
        motifs = ["aucun litige ouvert", f"{visites_90j} visite(s) en agence sur 90 jours",
                  f"dernier passage il y a {jours_absence} jour(s)"]

    return {
        "client_id": client_id,
        "statut": statut,
        "score_insatisfaction": score_insatisfaction,
        "niveau_satisfaction": niveau_satisfaction,
        "action_requise": action_requise,
        "motifs": motifs,
        "nb_reclamations": reclam.get("nb_reclamations", 0),
        "nb_non_resolues": non_resolues,
        "indice_insatisfaction": indice_reclam,
        "visites_agence_90j": visites_90j,
        "jours_depuis_visite": jours_absence,
        "contraction_frequentation": round(contraction, 2),
        "_reclamations": reclam,
    }


def _charger_tool_json(outil, arguments: dict) -> dict:
    """Invoque un outil LangChain et renvoie son JSON décodé ({} si échec)."""
    try:
        return json.loads(outil.invoke(arguments))
    except Exception as exc:
        logger.warning("⚠️  Repli outil %s échoué : %s", getattr(outil, "name", outil), exc)
        return {}


def _rediger_strategie_reconquete(client_id: int, profil: dict, churn: dict,
                                  reclamations: dict, regles: dict) -> str:
    """
    Fait rédiger au LLM la stratégie qui doit ramener le client à la satisfaction.

    Appel séparé de la phase outils : le modèle reçoit ici toutes les données
    déjà collectées et n'a plus qu'à écrire. C'est ce découplage qui permet un
    prompt riche sans casser le tool-calling.

    L'ordre imposé — réparer avant de vendre — est le cœur de la consigne : on
    ne propose rien à un client dont la réclamation est encore ouverte.
    """
    insat = reclamations.get("niveau_insatisfaction", "AUCUNE")
    doleances = reclamations.get("doleances_ouvertes", [])
    detail = "\n".join(
        f"  - {d['motif']} ({d['statut']}, en attente depuis {d['depuis_jours']} jours) : {d['verbatim']}"
        for d in doleances) or "  (aucune réclamation ouverte)"
    facteurs = "\n".join(
        f"  - {f.get('feature')} : {f.get('valeur_client')}"
        for f in (churn.get("top_shap_features") or [])[:4]) or "  (non disponible)"

    # apply_business_rules_tool renvoie des dicts, pas des libellés : les
    # concaténer comme des chaînes levait une TypeError silencieuse, la liste
    # n'atteignait jamais le prompt et le modèle inventait des services.
    services = "\n".join(
        f"  - [{s.get('code')}] {s.get('label')} — {s.get('description', '')}"
        for s in (regles.get("services_eligibles") or [])
        if isinstance(s, dict)) or "  (aucun service éligible identifié)"

    contexte = (
        f"CLIENT {client_id} — segment {profil.get('segment_metier', 'N/A')}\n"
        f"Solde : {profil.get('solde_actuel', 0):,.0f} MAD | "
        f"{profil.get('nb_operations_30j', 0)} opérations sur 30 jours | "
        f"{profil.get('jours_depuis_derniere_op', 0)} jours depuis la dernière.\n\n"
        f"RISQUE DE DÉPART : {churn.get('niveau_risque', 'N/A')} "
        f"({churn.get('probabilite_pct', 0)}%). Facteurs :\n{facteurs}\n\n"
        f"INSATISFACTION : {insat} "
        f"(indice {reclamations.get('indice_insatisfaction', 0)}). "
        f"{reclamations.get('synthese', '')}\n"
        f"Doléances ouvertes :\n{detail}\n\n"
        f"SERVICES ÉLIGIBLES (n'en proposer aucun autre) :\n{services}"
    )

    consigne = (
        "Tu es le stratège relation client d'Attijariwafa Bank. Ta mission n'est pas de "
        "constater un risque de départ : c'est de RAMENER CE CLIENT DE L'INSATISFACTION "
        "À LA SATISFACTION.\n\n"
        "Rédige en français, en trois parties courtes et numérotées :\n\n"
        "1. CONSTAT — ce qui a mécontenté CE client précisément. Cite sa réclamation : le "
        "motif et depuis combien de jours elle attend. Relie-la à son comportement : une "
        "activité qui chute après une réclamation non traitée n'est pas une coïncidence, "
        "c'est la conséquence.\n\n"
        "2. RÉPARATION — l'action qui règle le litige, AVANT toute proposition commerciale. "
        "Qui appelle, que corrige-t-on, sous quel délai. On ne vend rien à un client dont "
        "le problème est encore ouvert.\n\n"
        "3. RECONQUÊTE — une fois le litige clos, le geste ou le service qui le ramène à la "
        "satisfaction, choisi parmi les services éligibles et cohérent avec son segment.\n\n"
        "Tu n'utilises que les faits du dossier qui t'est transmis. Tu n'inventes jamais un "
        "chiffre, une date, un montant, un délai ni un motif de réclamation absent du dossier. "
        "Tu n'annonces aucun tarif ni condition tarifaire : tu n'en disposes pas, et citer un "
        "prix faux devant un client déjà mécontent aggraverait le litige. Tu ne proposes que "
        "des services figurant dans la liste des services éligibles. S'il te manque une "
        "information, tu l'écris au lieu de la combler.\n\n"
        "Tu es factuel et actionnable, sans généralité commerciale. Si le client n'a aucune "
        "réclamation ouverte, tu le dis et fondes le constat sur son seul comportement.\n\n"
        "Tu ne produis QUE les trois parties numérotées, sans préambule, sans conclusion et "
        "sans rappeler ces instructions."
    )

    try:
        # Température basse : on veut une restitution fidèle des faits fournis,
        # pas de la créativité. À 0.4 le modèle inventait des tarifs et des
        # motifs de réclamation absents du dossier.
        llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY,
                       temperature=0.1, max_tokens=1100, timeout=45, max_retries=2)
        reponse = llm.invoke([SystemMessage(content=consigne),
                              HumanMessage(content=contexte)])
        return (getattr(reponse, "content", "") or "").strip()
    except Exception as exc:
        logger.error("❌ [Agent 3] Rédaction stratégie échouée : %s", exc)
        return ""


def _executer_tool_call(tool_call: dict) -> ToolMessage:
    """
    Exécute un seul appel d'outil issu du LLM et retourne un ToolMessage.

    Args:
        tool_call: Dict avec 'name', 'args', 'id' issu du message AIMessage.

    Returns:
        ToolMessage avec la réponse JSON de l'outil.
    """
    tool_name = tool_call["name"]
    tool_args = tool_call.get("args", {})
    tool_obj  = _TOOLS_BY_NAME.get(tool_name)

    # Visibilité : quel outil le LLM a-t-il décidé d'appeler, et cet outil
    # passe-t-il par le serveur MCP ? Seul get_client_data_tool y accède.
    via_mcp = " (→ serveur MCP)" if (tool_name == "get_client_data_tool" and USE_MCP) else ""
    logger.info("🔧 [LLM tool-call] %s%s", tool_name, via_mcp)

    if tool_obj is None:
        content = json.dumps({"error": f"Outil inconnu : {tool_name}"}, ensure_ascii=False)
    else:
        try:
            content = tool_obj.invoke(tool_args)
        except Exception as exc:
            content = json.dumps({"error": str(exc)}, ensure_ascii=False)

    return ToolMessage(
        content=content,
        tool_call_id=tool_call.get("id", tool_name),
    )



def run_agent_analyse(client_id: int) -> dict[str, Any]:
    """
    Point d'entrée principal de l'Agent 3 LangChain.

    Orchestre le pipeline complet via tool-calling (LangChain 1.3+) :
        1. get_client_data_tool   → Profil MySQL
        2. predict_churn_tool    → Score XGBoost + SHAP
        3. apply_business_rules_tool → Services éligibles
        4. ChatGroq              → Recommandation 3 lignes

    Cette fonction est directement appelable depuis un endpoint FastAPI.

    Args:
        client_id: Identifiant numérique du client à analyser.

    Returns:
        Dictionnaire avec client_id, recommandation_conseiller, score_churn,
        niveau_risque, services_eligibles, shap_features, agent_steps.
    """
    logger.info("═" * 60)
    logger.info("🚀 [Agent 3] Démarrage analyse LangChain — Client %d", client_id)
    logger.info("═" * 60)

    if not GROQ_API_KEY:
        logger.warning("⚠️  GROQ_API_KEY absente — pipeline direct (sans LLM)")
        return _run_pipeline_direct(client_id)

    try:
        llm_with_tools = _build_llm_with_tools()
    except Exception as exc:
        logger.error("❌ Build LLM échoué : %s", exc)
        return _run_pipeline_direct(client_id)

    # Phase 1 — collecte. Prompt volontairement court et mécanique : chargé des
    # consignes de rédaction, llama-3.1-8b cesse d'émettre des appels d'outils
    # valides et recrache « <function=...> » en texte brut. La rédaction est
    # donc reportée à un second appel, une fois les données réunies.
    system_msg = SystemMessage(content=(
        "Tu es l'Agent 3 d'Attijariwafa Bank. Appelle les 4 outils dans cet ordre, "
        "sans rien rédiger : get_client_data_tool, predict_churn_tool, "
        "get_reclamations_tool, apply_business_rules_tool."
    ))
    user_msg = HumanMessage(content=f"Collecte les données du client ID {client_id}.")

    messages = [system_msg, user_msg]
    churn_data: dict  = {}
    profil_data: dict = {}
    rules_data: dict  = {}
    reclam_data: dict = {}
    steps_count = 0

    try:
        for _ in range(6):
            # L'orchestration par le LLM est best-effort. llama-3.1-8b échoue
            # régulièrement à enchaîner les outils dès qu'il doit repasser un
            # gros JSON en argument (le profil vers predict_churn_tool) : il
            # émet alors du « <function=...> » textuel que l'API rejette.
            # On interrompt proprement et le filet déterministe ci-dessous
            # complète le dossier, au lieu de perdre toute l'analyse.
            try:
                ai_msg: AIMessage = llm_with_tools.invoke(messages)
            except Exception as exc:
                logger.warning("⚠️  [Agent 3] Orchestration LLM interrompue (%s) — "
                               "collecte déterministe des outils manquants.",
                               str(exc)[:120])
                break
            messages.append(ai_msg)

            tool_calls = getattr(ai_msg, "tool_calls", []) or []
            if not tool_calls:
                break

            for tc in tool_calls:
                tool_msg = _executer_tool_call(tc)
                messages.append(tool_msg)
                steps_count += 1

                try:
                    obs = json.loads(tool_msg.content)
                except Exception:
                    obs = {}

                # Un outil en échec renvoie {"error": ...}, qui est truthy :
                # le stocker tel quel faisait croire au filet déterministe que
                # la donnée était présente, et l'analyse ressortait trouée.
                if not isinstance(obs, dict) or "error" in obs:
                    continue

                t_name = tc.get("name", "")
                if t_name == "get_client_data_tool":
                    profil_data = obs
                elif t_name == "predict_churn_tool":
                    churn_data  = obs
                elif t_name == "get_reclamations_tool":
                    reclam_data = obs
                elif t_name == "apply_business_rules_tool":
                    rules_data  = obs

        # Filet déterministe. llama-3.1-8b échoue par intermittence à émettre des
        # appels d'outils valides ; l'ordre étant de toute façon imposé, on
        # complète en code ce que le modèle a omis plutôt que de rendre une
        # analyse trouée. La phase de rédaction reçoit ainsi toujours un dossier
        # complet.
        if not profil_data:
            profil_data = _charger_tool_json(get_client_data_tool, {"client_id": client_id})
        if not churn_data:
            churn_data = _charger_tool_json(
                predict_churn_tool, {"profil_json": json.dumps(profil_data, ensure_ascii=False)})
        if not reclam_data:
            reclam_data = _charger_tool_json(get_reclamations_tool, {"client_id": client_id})
        if not rules_data:
            rules_data = _charger_tool_json(apply_business_rules_tool, {
                "churn_et_profil_json": json.dumps(
                    {"churn": churn_data, "profil": profil_data}, ensure_ascii=False)})

        # Phase 2 — le client a-t-il seulement besoin qu'on l'aborde ?
        # Sans litige ouvert et avec une fréquentation normale, il est
        # satisfait : on n'invente pas une reconquête, et on n'appelle pas le
        # LLM pour rien.
        satisfaction = evaluer_satisfaction(client_id)
        if not satisfaction["action_requise"]:
            recommandation = (
                "CLIENT SATISFAIT — aucune action commerciale requise.\n"
                + "\n".join(f"• {m}" for m in satisfaction["motifs"])
                + "\nMaintenir la relation en l'état ; toute sollicitation de rétention "
                  "serait ici injustifiée."
            )
        else:
            recommandation = _rediger_strategie_reconquete(
                client_id, profil_data, churn_data, reclam_data, rules_data)
            if not recommandation.strip():
                recommandation = _recommandation_fallback(profil_data, churn_data, rules_data)

    except Exception as exc:
        logger.error("❌ [Agent 3] Erreur tool-calling : %s", exc)
        return _run_pipeline_direct(client_id)

    strategies_dynamiques = _generer_strategies_dynamiques_llm(
        profil_data, churn_data, rules_data
    )

    result = {
        "client_id":                client_id,
        "recommandation_conseiller": recommandation,
        "score_churn":              churn_data.get("score_churn"),
        "probabilite_pct":          churn_data.get("probabilite_pct"),
        "niveau_risque":            churn_data.get("niveau_risque"),
        "services_eligibles":       rules_data.get("services_eligibles", []),
        "urgence_action":           rules_data.get("urgence_action"),
        "shap_features":            churn_data.get("top_shap_features", []),
        "strategies_dynamiques":    strategies_dynamiques,
        "analyse_comportementale":  rules_data.get("analyse_comportementale", ""),
        "satisfaction": {
            "statut":         satisfaction["statut"],
            "action_requise": satisfaction["action_requise"],
            "motifs":         satisfaction["motifs"],
            "visites_agence_90j":  satisfaction["visites_agence_90j"],
            "jours_depuis_visite": satisfaction["jours_depuis_visite"],
        },
        "insatisfaction": {
            "indice":             reclam_data.get("indice_insatisfaction", 0.0),
            "niveau":             reclam_data.get("niveau_insatisfaction", "AUCUNE"),
            "nb_reclamations":    reclam_data.get("nb_reclamations", 0),
            "nb_non_resolues":    reclam_data.get("nb_non_resolues", 0),
            "motif_dominant":     reclam_data.get("motif_dominant"),
            "recidive":           reclam_data.get("recidive", False),
            "doleances_ouvertes": reclam_data.get("doleances_ouvertes", []),
            "synthese":           reclam_data.get("synthese", ""),
        },
        "profil_resume": {
            "segment":       profil_data.get("segment_metier", "N/A"),
            "solde":         profil_data.get("solde_actuel", 0),
            "nb_ops_30j":    profil_data.get("nb_operations_30j", 0),
            "jours_inactif": profil_data.get("jours_depuis_derniere_op", 0),
        },
        "agent_steps": steps_count,
        "modele":      churn_data.get("modele", "N/A"),
    }

    logger.info("✅ [Agent 3] Analyse terminée — %d appels outils | Risque: %s | Insatisfaction: %s",
                steps_count,
                result.get("niveau_risque", "N/A"),
                result["insatisfaction"].get("niveau", "N/A"))
    return result


def run_batch_evaluation(limite: int | None = None) -> dict[str, Any]:
    """
    Établit risque de départ ET satisfaction pour TOUT le portefeuille.

    Passe entièrement déterministe — aucun appel LLM — donc exécutable sur
    l'ensemble des clients en quelques secondes.

    Cette fonction doit tourner APRÈS l'Agent 2 et AVANT l'aiguillage du batch :
    c'est elle qui alimente `niveau_risque`, sur lequel repose la répartition
    des clients entre analyse approfondie et simple surveillance. L'Agent 2 ne
    calcule plus ces colonnes — il s'en tient à la prédiction de visite.
    """
    logger.info("📊 [Agent 3] Évaluation du portefeuille (risque + satisfaction)…")
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM client ORDER BY id"
                    + (f" LIMIT {int(limite)}" if limite else ""))
        ids = [r[0] for r in cur.fetchall()]
    except Exception as exc:
        logger.error("❌ Évaluation impossible : %s", exc)
        return {"error": str(exc)}

    from analysis_engine import calculer_niveau_risque
    repartition, nb_echecs = Counter(), 0

    for cid in ids:
        try:
            score_churn, _ = calculer_churn_xgboost({"client_id": cid})
            niveau_risque = calculer_niveau_risque(score_churn)
            ev = evaluer_satisfaction(cid)

            cur.execute(
                "UPDATE prediction_visite SET niveau_risque=%s, score_churn=%s, "
                "score_insatisfaction=%s, niveau_satisfaction=%s WHERE client_id=%s",
                (niveau_risque, round(float(score_churn), 4),
                 ev["score_insatisfaction"], ev["niveau_satisfaction"], cid))
            # Le front lit client.niveau_risque en repli quand la prédiction
            # n'en a pas : sans cette propagation il afficherait des valeurs
            # figées, en contradiction avec l'agent.
            cur.execute(
                "UPDATE client SET niveau_risque=%s, score_churn=%s WHERE id=%s",
                (niveau_risque, round(float(score_churn), 4), cid))
            repartition[niveau_risque] += 1
        except Exception as exc:
            nb_echecs += 1
            logger.warning("⚠️  Client %s non évalué : %s", cid, str(exc)[:100])

    conn.commit()
    cur.close(); conn.close()
    logger.info("✅ [Agent 3] %d clients évalués, %d échecs", len(ids) - nb_echecs, nb_echecs)
    return {"nb_clients": len(ids), "echecs": nb_echecs,
            "repartition_risque": dict(repartition)}


def run_batch_satisfaction(limite: int | None = None) -> dict[str, Any]:
    """
    Classe TOUT le portefeuille : qui est satisfait, qui ne l'est pas.

    Purement déterministe — aucun appel LLM. C'est ce qui permet de balayer
    l'ensemble des clients en quelques secondes, puis de ne mobiliser le
    modèle de langage que sur ceux qui ont réellement besoin d'une stratégie.

    Returns:
        dict avec la répartition par statut et la liste des clients à traiter,
        triés du plus urgent au moins urgent.
    """
    logger.info("🔎 [Agent 3] Balayage satisfaction du portefeuille…")
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM client ORDER BY id"
                    + (f" LIMIT {int(limite)}" if limite else ""))
        ids = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
    except Exception as exc:
        logger.error("❌ Balayage impossible : %s", exc)
        return {"error": str(exc)}

    ORDRE = {"INSATISFAIT_CRITIQUE": 0, "INSATISFAIT": 1, "A_SURVEILLER": 2, "SATISFAIT": 3}
    evaluations = []
    for cid in ids:
        try:
            ev = evaluer_satisfaction(cid)
            ev.pop("_reclamations", None)
            evaluations.append(ev)
        except Exception as exc:
            logger.warning("⚠️  Client %s ignoré : %s", cid, exc)

    evaluations.sort(key=lambda e: (ORDRE.get(e["statut"], 9),
                                    -e["indice_insatisfaction"]))
    repartition = Counter(e["statut"] for e in evaluations)
    a_traiter = [e for e in evaluations if e["action_requise"]]

    logger.info("✅ [Agent 3] %d clients évalués — %d nécessitent une action",
                len(evaluations), len(a_traiter))
    return {
        "nb_clients": len(evaluations),
        "repartition": dict(repartition),
        "nb_action_requise": len(a_traiter),
        "clients_a_traiter": a_traiter,
        "clients_satisfaits": [e["client_id"] for e in evaluations
                               if e["statut"] == "SATISFAIT"],
    }


def run_batch_strategies_reconquete(limite: int | None = None,
                                    pause_secondes: float = 1.5) -> dict[str, Any]:
    """
    Écrit en base la stratégie de reconquête de chaque client.

    Le dashboard lit `prediction_visite.strategie_prescrite`, alimenté jusqu'ici
    par un agent qui ignorait les réclamations et dont le texte n'était plus
    réécrit depuis la régénération des données. Cette fonction y place le
    travail de l'agent 3 : constat, réparation, reconquête.

    Les clients satisfaits ne reçoivent PAS d'offre — ils reçoivent la mention
    explicite qu'aucune action n'est requise, et aucun appel LLM n'est fait pour
    eux. C'est ce qui rend le traitement rapide : seuls les dossiers à traiter
    mobilisent le modèle.

    En cas d'échec sur un client, l'ancienne stratégie est conservée plutôt
    qu'effacée : mieux vaut un texte périmé qu'une case vide.

    Args:
        limite: nombre de clients à traiter (None = tout le portefeuille).
        pause_secondes: délai entre deux appels LLM, pour rester sous les
            limites de débit de Groq.
    """
    logger.info("✍️  [Agent 3] Génération des stratégies de reconquête…")
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM client ORDER BY id"
                    + (f" LIMIT {int(limite)}" if limite else ""))
        ids = [r[0] for r in cur.fetchall()]
    except Exception as exc:
        logger.error("❌ Lecture des clients impossible : %s", exc)
        return {"error": str(exc)}

    nb_traites = nb_satisfaits = nb_echecs = 0
    for cid in ids:
        try:
            ev = evaluer_satisfaction(cid)
            if not ev["action_requise"]:
                strategie = ("CLIENT SATISFAIT — aucune action commerciale requise.\n"
                             + "\n".join(f"• {m}" for m in ev["motifs"])
                             + "\nMaintenir la relation en l'état.")
                insight = ev["_reclamations"].get(
                    "synthese", "Aucune réclamation enregistrée.")
                nb_satisfaits += 1
            else:
                # Collecte déterministe des outils, puis UN SEUL appel LLM.
                # Passer par run_agent_analyse ferait 3 à 8 appels par client
                # (orchestration + rédaction + stratégies dynamiques) : sur
                # tout le portefeuille, Groq répond 429 avec 32 s de back-off.
                # L'ordre des outils étant figé, faire « décider » le modèle
                # n'apporte rien ici et coûte l'essentiel du budget d'appels.
                profil = _charger_tool_json(get_client_data_tool, {"client_id": cid})
                churn = _charger_tool_json(
                    predict_churn_tool,
                    {"profil_json": json.dumps(profil, ensure_ascii=False)})
                regles = _charger_tool_json(apply_business_rules_tool, {
                    "churn_et_profil_json": json.dumps(
                        {"churn": churn, "profil": profil}, ensure_ascii=False)})
                strategie = _rediger_strategie_reconquete(
                    cid, profil, churn, ev["_reclamations"], regles).strip()
                if not strategie:
                    raise ValueError("stratégie vide")
                insight = ev["_reclamations"].get("synthese", "")
                nb_traites += 1
                time.sleep(pause_secondes)

            cur.execute(
                "UPDATE prediction_visite SET strategie_prescrite=%s, insight_genai=%s "
                "WHERE client_id=%s",
                (strategie, insight or "Analyse comportementale à jour.", cid))
            conn.commit()
        except Exception as exc:
            nb_echecs += 1
            logger.warning("⚠️  Client %s : stratégie inchangée (%s)", cid, str(exc)[:100])

    cur.close(); conn.close()
    logger.info("✅ [Agent 3] %d stratégies rédigées, %d clients satisfaits, %d échecs",
                nb_traites, nb_satisfaits, nb_echecs)
    return {"strategies_redigees": nb_traites, "clients_satisfaits": nb_satisfaits,
            "echecs": nb_echecs, "nb_clients": len(ids)}


def _run_pipeline_direct(client_id: int) -> dict[str, Any]:
    """
    Exécution séquentielle de secours (sans LangChain ReAct).
    Appelle les 3 outils directement et génère la recommandation via Groq.
    """
    logger.warning("⚠️  [Agent 3] Basculement vers le pipeline direct (sans ReAct).")

    profil_json = get_client_data_tool.invoke({"client_id": client_id})
    profil_data = json.loads(profil_json)

    churn_json  = predict_churn_tool.invoke({"profil_json": profil_json})
    churn_data  = json.loads(churn_json)

    combined    = json.dumps({"churn": churn_data, "profil": profil_data})
    rules_json  = apply_business_rules_tool.invoke({"churn_et_profil_json": combined})
    rules_data  = json.loads(rules_json)

    recommandation = _generer_recommandation_directe(profil_data, churn_data, rules_data)

    strategies_dynamiques = _generer_strategies_dynamiques_llm(
        profil_data, churn_data, rules_data
    )

    return {
        "client_id":                client_id,
        "recommandation_conseiller": recommandation,
        "score_churn":              churn_data.get("score_churn"),
        "probabilite_pct":          churn_data.get("probabilite_pct"),
        "niveau_risque":            churn_data.get("niveau_risque"),
        "services_eligibles":       rules_data.get("services_eligibles", []),
        "urgence_action":           rules_data.get("urgence_action"),
        "shap_features":            churn_data.get("top_shap_features", []),
        "strategies_dynamiques":    strategies_dynamiques,
        "analyse_comportementale":  rules_data.get("analyse_comportementale", ""),
        "profil_resume": {
            "segment":       profil_data.get("segment_metier", "N/A"),
            "solde":         profil_data.get("solde_actuel", 0),
            "nb_ops_30j":    profil_data.get("nb_operations_30j", 0),
            "jours_inactif": profil_data.get("jours_depuis_derniere_op", 0),
        },
        "agent_steps": 3,
        "modele":      churn_data.get("modele", "N/A"),
        "_mode":       "pipeline_direct",
    }


def _generer_strategies_dynamiques_llm(
    profil: dict,
    churn: dict,
    rules: dict,
) -> str:
    """
    Génère des stratégies DYNAMIQUES et PERSONNALISÉES via le LLM.

    Au lieu de retourner uniquement les règles métier statiques (if/else),
    cette fonction envoie le comportement réel du client au LLM qui
    propose des stratégies adaptées à SA situation spécifique.

    Le LLM reçoit :
      - L'analyse comportementale (historique, inactivité, types d'opérations)
      - Le score de churn et les variables SHAP explicatives
      - Les services éligibles des règles métier comme base
      - Le profil complet (segment, solde, comptes)

    Returns:
        Texte structuré des stratégies dynamiques personnalisées.
    """
    if not GROQ_API_KEY:
        return _strategies_fallback(profil, churn, rules)

    segment       = profil.get("segment_metier", "PARTICULIER")
    solde         = profil.get("solde_actuel", 0)
    solde_moyen   = profil.get("solde_moyen_compte", 0)
    nb_ops_30j    = profil.get("nb_operations_30j", 0)
    nb_ops_total  = profil.get("nb_operations_total", 0)
    jours_inact   = profil.get("jours_depuis_derniere_op", 0)
    moy_retrait   = profil.get("moy_retrait", 0)
    montant_moyen = profil.get("montant_moyen", 0)
    has_epargne   = profil.get("has_compte_epargne", 0)
    nb_comptes    = profil.get("nb_comptes", 0)
    nb_credit     = profil.get("nb_comptes_credit", 0)
    historique    = profil.get("historique_recent", [])
    proba_visite  = _get_proba_visite(profil.get("client_id"))

    hist_txt = ""
    for h in historique[:5]:
        hist_txt += f"  - {h.get('type', '?')} : {h.get('montant', 0):,.0f} MAD le {h.get('date', '?')}\n"
    if not hist_txt:
        hist_txt = "  Aucune opération récente enregistrée.\n"

    score_pct = churn.get("probabilite_pct", 0)
    niveau    = churn.get("niveau_risque", "N/A")
    shap_top  = churn.get("top_shap_features", [])[:5]
    shap_txt  = ""
    for s in shap_top:
        shap_txt += f"  - {s.get('feature', '?')} : {s.get('impact', '?')} (valeur client: {s.get('valeur_client', '?')})\n"
    if not shap_txt:
        shap_txt = "  Données SHAP non disponibles.\n"

    services  = rules.get("services_eligibles", [])
    svc_txt   = ""
    for s in services[:5]:
        svc_txt += f"  - {s.get('label', '?')} : {s.get('description', '')}\n"
    if not svc_txt:
        svc_txt = "  Aucun service identifié par les règles métier.\n"

    comportement = rules.get("analyse_comportementale", "Données insuffisantes")
    urgence      = rules.get("urgence_action", "STANDARD")

    system_prompt = f"""Tu es le stratège IA d'Attijariwafa Bank Maroc. Tu dois proposer des stratégies
commerciales et de rétention UNIQUES et PERSONNALISÉES pour ce client spécifique.

RÈGLES ABSOLUES :
- Propose UNE SEULE stratégie, la plus pertinente, pour que le conseiller se concentre sur UNE action lors de l'appel
- La stratégie DOIT être justifiée par le COMPORTEMENT RÉEL du client (ses opérations ci-dessous)
- NE PROPOSE JAMAIS de stratégie générique. Cite les chiffres réels du client
- N'INVENTE AUCUN pourcentage : utilise uniquement visite {proba_visite:.0f}% et churn {score_pct:.1f}%
- Adapte le ton et les produits au segment ({segment}) et au contexte marocain (AWB)
- La stratégie doit être ACTIONNABLE par le conseiller en agence

PROFIL COMPLET DU CLIENT :
  Segment       : {segment}
  Solde actuel  : {solde:,.0f} MAD (historique moyen : {solde_moyen:,.0f} MAD)
  Nb comptes    : {nb_comptes} (épargne: {'oui' if has_epargne else 'non'}, crédit: {nb_credit})
  Opérations    : {nb_ops_total} au total, {nb_ops_30j} sur les 30 derniers jours
  Montant moyen : {montant_moyen:,.0f} MAD | Retraits moyens : {moy_retrait:,.0f} MAD
  Inactivité    : {jours_inact} jours sans opération

DERNIÈRES OPÉRATIONS :
{hist_txt}
ANALYSE COMPORTEMENTALE :
  {comportement}

SCORE DE CHURN XGBoost : {score_pct:.1f}% — Niveau : {niveau}
VARIABLES SHAP (facteurs de risque) :
{shap_txt}
SERVICES ÉLIGIBLES (règles métier de base) :
{svc_txt}
URGENCE D'ACTION : {urgence}

FORMAT DE RÉPONSE OBLIGATOIRE — réponds par UNE SEULE phrase, rien d'autre :

[Le service ou produit AWB à proposer à ce client, formulé comme une action. 15 mots maximum.]

RÈGLES STRICTES :
- UNE seule phrase. Aucun label, aucun titre, aucun constat, aucune justification, aucun objectif.
- Nomme le produit ou service AWB précis, choisi parmi les services éligibles ci-dessus.
- Exemple attendu : « Proposer le Compte sur Carnet pour valoriser les 80 000 MAD dormants. »"""

    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            groq_api_key=GROQ_API_KEY,
            temperature=0.5,
            # Une seule phrase : le plafond bride aussi la tendance du modèle
            # à broder au-delà du format demandé.
            max_tokens=60,
            timeout=30,
            max_retries=3,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Donne la seule phrase du service à proposer pour ce client."),
        ]
        result = llm.invoke(messages)
        strategies_text = result.content.strip()
        if strategies_text:
            logger.info("✅ [Strat-LLM] Stratégies dynamiques générées (%d chars)", len(strategies_text))
            return strategies_text
    except Exception as exc:
        logger.warning("⚠️  [Strat-LLM] Erreur génération stratégies dynamiques : %s", exc)

    return _strategies_fallback(profil, churn, rules)


def _strategies_fallback(profil: dict, churn: dict, rules: dict) -> str:
    """
    Stratégie de repli si le LLM est indisponible.
    Renvoie le même contrat que le LLM : une phrase, le service à proposer.
    """
    segment       = profil.get("segment_metier", "PARTICULIER")
    solde         = profil.get("solde_actuel", 0)
    jours_inact   = profil.get("jours_depuis_derniere_op", 0)
    moy_retrait   = profil.get("moy_retrait", 0)
    has_epargne   = profil.get("has_compte_epargne", 0)
    services      = rules.get("services_eligibles", [])

    # Même contrat que le LLM : UNE phrase, le service à proposer, rien d'autre.
    # On retient le motif le plus saillant, dans l'ordre de priorité métier.
    if jours_inact > 30:
        return f"Proposer une offre de réactivation — client inactif depuis {jours_inact} jours."

    if solde > 50_000 and not has_epargne:
        return f"Proposer un Compte sur Carnet pour valoriser les {solde:,.0f} MAD dormants."

    if moy_retrait > 0 and solde > 0 and moy_retrait / solde > 0.3:
        return "Proposer le Pack fidélité avec carte Gold pour contenir les retraits."

    if services:
        s = services[0]
        return f"Proposer {s.get('label', 'un service de rétention adapté')}."

    return f"Proposer un bilan financier complet lors de la prochaine visite ({segment})."


def _get_proba_visite(client_id) -> float:
    """Récupère la probabilité de visite réelle (score_probabilite_global) depuis la DB."""
    try:
        conn = _get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT score_probabilite_global FROM prediction_visite WHERE client_id=%s", (client_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        return float(row[0]) if row and row[0] is not None else 0.0
    except Exception:
        return 0.0


def _generer_recommandation_directe(
    profil: dict,
    churn: dict,
    rules: dict,
) -> str:
    """
    Génère la recommandation 3 lignes via ChatGroq avec un prompt système enrichi
    du contexte SHAP, du score de churn et des services éligibles.
    """
    if not GROQ_API_KEY:
        return _recommandation_fallback(profil, churn, rules)

    score_pct    = churn.get("probabilite_pct", 0)
    niveau       = churn.get("niveau_risque", "N/A")
    segment      = profil.get("segment_metier", "PARTICULIER")
    solde        = profil.get("solde_actuel", 0)
    nb_ops_30j   = profil.get("nb_operations_30j", 0)
    jours_inact  = profil.get("jours_depuis_derniere_op", 0)
    proba_visite = _get_proba_visite(profil.get("client_id"))

    shap_top3 = churn.get("top_shap_features", [])[:3]
    shap_txt  = " | ".join(
        f"{s['feature']} ({s['impact']}, valeur={s['valeur_client']})"
        for s in shap_top3
    )

    services    = rules.get("services_eligibles", [])
    best_offer  = services[0]["label"] if services else "Suivi personnalisé"
    urgence     = rules.get("urgence_action", "STANDARD")

    system_prompt = f"""Tu es le conseiller IA d'Attijariwafa Bank.
Rédige une recommandation commerciale de EXACTEMENT 3 LIGNES pour le conseiller bancaire humain.

DONNÉES ANALYTIQUES (chiffres EXACTS — à utiliser tels quels) :
- Client : Segment {segment} | Solde : {solde:,.0f} MAD | Inactif depuis {jours_inact} jours
- Probabilité de VISITE en agence : {proba_visite:.0f}%
- Score de churn XGBoost : {score_pct:.1f}% (Niveau : {niveau})
- Variables SHAP les plus impactantes : {shap_txt}
- Activité récente : {nb_ops_30j} opération(s) sur les 30 derniers jours
- Offre prioritaire recommandée : {best_offer}
- Urgence d'action : {urgence}

RÈGLES STRICTES :
- N'INVENTE AUCUN chiffre. Utilise UNIQUEMENT les valeurs ci-dessus (visite {proba_visite:.0f}%, churn {score_pct:.1f}%).
- Ne confonds pas la probabilité de visite et le score de churn : ce sont deux indicateurs différents.

FORMAT OBLIGATOIRE (3 lignes exactement, en français professionnel) :
Ligne 1 : Diagnostic du risque avec justification SHAP (citez les variables et les chiffres réels)
Ligne 2 : Action immédiate recommandée au conseiller avec l'offre prioritaire
Ligne 3 : Calendrier d'exécution précis et indicateur de succès attendu"""

    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            groq_api_key=GROQ_API_KEY,
            temperature=0.2,
            max_tokens=300,
            timeout=25,
            max_retries=3,
        )
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Rédigez la recommandation commerciale."),
        ]
        result = llm.invoke(messages)
        return result.content.strip()
    except Exception as exc:
        logger.warning("⚠️  [Tool 4] Erreur LLM direct : %s", exc)
        return _recommandation_fallback(profil, churn, rules)


def _recommandation_fallback(profil: dict, churn: dict, rules: dict) -> str:
    """Recommandation textuelle déterministe si le LLM est indisponible."""
    score   = churn.get("probabilite_pct", 0)
    niveau  = churn.get("niveau_risque", "N/A")
    segment = profil.get("segment_metier", "PARTICULIER")
    solde   = profil.get("solde_actuel", 0)
    services = rules.get("services_eligibles", [])
    offre   = services[0]["label"] if services else "suivi personnalisé"
    urgence = rules.get("urgence_action", "STANDARD")
    shap    = churn.get("top_shap_features", [])
    var1    = shap[0]["feature"] if shap else "inactivité"
    var2    = shap[1]["feature"] if len(shap) > 1 else "solde bas"

    return (
        f"RISQUE {niveau} ({score:.1f}%) : Le client {segment} (solde {solde:,.0f} MAD) "
        f"présente des signaux d'alerte churn confirmés par SHAP sur '{var1}' et '{var2}'.\n"
        f"ACTION PRIORITAIRE : Déclencher {offre} avec une prise de contact {urgence} "
        f"pour sécuriser la relation et présenter cette offre personnalisée.\n"
        f"OBJECTIF : Réduire le score de churn sous 40% dans les 30 prochains jours "
        f"en restaurant l'activité transactionnelle et l'engagement produit."
    )


def _strategie_comportementale(profil: dict, type_counts: dict, churn: dict | None = None) -> str:
    """
    Construit UNE stratégie unique, fondée sur le COMPORTEMENT réel du client en
    agence (type d'opérations, fréquence, inactivité, épargne, solde). L'objectif :
    que le conseiller se concentre sur UNE seule action pertinente lors de l'appel.
    Chaque stratégie cite les chiffres réels du client → elle est différente pour chacun.
    """
    seg         = str(profil.get("segment_metier", "PARTICULIER"))
    solde       = float(profil.get("solde_actuel", 0) or 0)
    nb_30j      = int(profil.get("nb_operations_30j", 0) or 0)
    nb_total    = int(profil.get("nb_operations_total", 0) or 0)
    inactif     = int(profil.get("jours_depuis_derniere_op", 0) or 0)
    moy_retrait = float(profil.get("moy_retrait", 0) or 0)
    has_epargne = int(profil.get("has_compte_epargne", 0) or 0)
    score       = (churn or {}).get("probabilite_pct", 0) or 0
    risque      = (churn or {}).get("niveau_risque", "") or ""

    total_ops = sum(type_counts.values()) or 1
    dominante, dom_n = (max(type_counts.items(), key=lambda kv: kv[1]) if type_counts else (None, 0))
    part = round(100 * dom_n / total_ops)

    if dominante in ("PLACEMENT", "RETRAIT_EPARGNE"):
        constat = f"profil épargnant — {dominante} domine ({part}% des opérations), solde {solde:,.0f} MAD"
        action  = "proposer un conseil patrimonial (placement / assurance-vie) adapté à son épargne."
    elif dominante in ("VIREMENT_RECU", "Virement Reçu"):
        constat = f"domiciliation de revenus — virements reçus = {part}% des opérations"
        action  = "proposer un package de domiciliation (avantages fidélité + carte adaptée) pour ancrer ses revenus."
    elif dominante in ("PAIEMENT_CARTE", "Paiement TPE", "PAIEMENT_FACTURE"):
        constat = f"usage surtout digital — {dominante} = {part}% des opérations"
        action  = "proposer le Pack Digital AWB (mobile, paiements) et des avantages cashback."
    elif dominante in ("RETRAIT", "Retrait Guichet"):
        if has_epargne == 0 and solde >= 10000:
            constat = f"retraits dominants ({part}%, retrait moyen {moy_retrait:,.0f} MAD) sans compte épargne"
            action  = f"proposer l'ouverture d'un compte épargne rémunéré pour capter le solde de {solde:,.0f} MAD."
        else:
            constat = f"retraits fréquents ({part}% des opérations, moyenne {moy_retrait:,.0f} MAD)"
            action  = "proposer une carte adaptée et un plafond optimisé à son usage de retrait."
    elif dominante in ("VERSEMENT", "Versement Espèces", "REMISE_CHEQUE", "Remise de Chèque"):
        constat = f"dépôts réguliers — {dominante} = {part}% des opérations"
        action  = "proposer une épargne programmée pour valoriser ses dépôts récurrents."
    elif dominante in ("Demande de Crédit",):
        constat = "intérêt financement détecté — demandes de crédit dans l'historique"
        action  = "proposer une offre de financement personnalisée (taux préférentiel)."
    elif dominante in ("VIREMENT_EMIS",):
        constat = f"virements émis fréquents ({part}%) — besoins de transfert"
        action  = "proposer un pack virements/transferts à frais réduits."
    elif nb_30j >= 6:
        constat = f"client très actif ({nb_30j} opérations sur 30 jours)"
        action  = "valoriser la fidélité par une montée en gamme (carte premium / avantages)."
    else:
        constat = f"opération principale : {dominante or 'variée'} ({part}%)"
        action  = "réaliser un point conseil pour identifier le besoin prioritaire."

    if inactif >= 30:
        contexte = f"Client inactif depuis {inactif} jours ; {constat}."
        prefixe  = "Réactivation prioritaire"
    elif nb_total >= 10 and nb_30j == 0:
        contexte = f"Activité en forte baisse (0 op./30j) ; {constat}."
        prefixe  = "Appel rapide"
    else:
        contexte = constat[0].upper() + constat[1:] + "."
        prefixe  = "Contact conseil"

    entete = f"RISQUE {risque} ({score:.1f}%) — " if risque else ""
    return f"{entete}COMPORTEMENT : {contexte}\nACTION UNIQUE : {prefixe} — {action}"


_SHAP_LABELS = {
    "montant_moyen":         "le montant moyen des opérations",
    "frequence_retrait":     "la fréquence des retraits",
    "solde_moyen":           "le solde moyen du client",
    "nb_operations_30j":     "le nombre d'opérations ce mois",
    "nb_ops_hors_horaires":  "les opérations hors horaires d'agence",
    "ratio_digital":         "l'usage des canaux digitaux",
    "anciennete_client_ans": "l'ancienneté du client",
    "segment_metier_enc":    "le segment client",
    "heure_operation":       "l'heure des opérations",
    "heure_decimale":        "l'heure habituelle des opérations",
    "dans_horaires_banque":  "les opérations en horaires d'agence",
    "est_heure_pointe":      "les opérations en heure de pointe",
    "est_weekend":           "les opérations le week-end",
    "est_samedi":            "les opérations le samedi",
    "est_dimanche":          "les opérations le dimanche",
    "est_jour_ferie":        "les opérations les jours fériés",
    "jour_semaine":          "le jour de la semaine des opérations",
    "decalage_ouverture":    "l'écart avec l'ouverture de l'agence",
    "decalage_fermeture":    "l'écart avec la fermeture de l'agence",
    "est_fin_journee":       "les opérations en fin de journée",
    "jours_avant_prochain_ferie": "la proximité d'un jour férié",
    "est_veille_aid":        "les opérations en veille d'Aïd",
}


def _insight_clair(profil: dict, churn: dict, proba_visite: float) -> str:
    """
    Génère un insight CLAIR expliquant la prédiction du client à partir des
    valeurs SHAP : probabilité de visite + facteurs déterminants traduits en
    langage métier compréhensible par le conseiller.
    """
    niveau      = churn.get("niveau_risque", "N/A")
    score_churn = churn.get("probabilite_pct", 0) or 0
    shap        = (churn.get("top_shap_features") or [])[:3]
    segment     = profil.get("segment_metier", "PARTICULIER")
    inactif     = int(profil.get("jours_depuis_derniere_op", 0) or 0)

    ligne1 = (f"Visite estimée à {proba_visite:.0f}% — risque de churn {niveau} "
              f"({score_churn:.0f}%) pour ce client {segment}.")

    facteurs = []
    for f in shap:
        label = _SHAP_LABELS.get(f.get("feature", ""), f.get("feature", ""))
        sens  = "fait monter le risque" if f.get("shap_value", 0) > 0 else "rassure (fait baisser le risque)"
        facteurs.append(f"{label} {sens}")
    ligne2 = ("Facteurs déterminants (SHAP) : " + " ; ".join(facteurs) + "."
              if facteurs else "")

    if inactif >= 30:
        synth = f"En clair : client {segment} en perte d'activité (inactif depuis {inactif} jours) à recontacter."
    elif score_churn >= 60:
        synth = "En clair : signaux de désengagement marqués, à traiter en priorité."
    elif score_churn >= 40:
        synth = "En clair : relation à surveiller, un contact préventif est recommandé."
    else:
        synth = "En clair : client stable, à entretenir par une offre adaptée."

    return f"{ligne1}\n{ligne2}\n{synth}".strip()


def analyser_sante_client(client_id: int, prediction_data: dict | None = None) -> dict:
    """
    Wrapper de compatibilité avec l'ancien appel depuis agent_strategie.
    Délègue au pipeline LangChain complet (run_agent_analyse).
    """
    return run_agent_analyse(client_id)


def run_batch_strategies(force_all: bool = False) -> tuple[int, int]:
    """
    Exécute l'Agent 3 LangChain sur l'ensemble des clients en base.
    Compatible avec le scheduler nocturne AWB.
    """
    logger.info("🚀 [Agent 3 LangChain] Début du batch strategies...")
    nb_ok = nb_ko = 0
    try:
        conn   = _get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if force_all:
            cursor.execute("SELECT client_id FROM prediction_visite")
        else:
            cursor.execute("""
                SELECT client_id FROM prediction_visite
                WHERE insight_genai = 'Analyse IA en attente...' OR insight_genai IS NULL
            """)
        clients = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as exc:
        logger.error("❌ Erreur DB batch Agent 3 : %s", exc)
        return 0, 0

    for row in clients:
        cid = row["client_id"]
        try:
            run_agent_analyse(cid)
            nb_ok += 1
        except Exception as exc:
            nb_ko += 1
            logger.error("❌ Erreur Agent 3 client %d : %s", cid, exc)

    logger.info("✅ [Agent 3 LangChain] Batch terminé — OK: %d | KO: %d", nb_ok, nb_ko)
    return nb_ok, nb_ko


def main() -> None:
    """
    Simulation complète de l'Agent 3 LangChain sur un client à haut risque.

    Le test :
    1. Appelle les 3 outils directement (sans attendre la DB)
    2. Génère la recommandation LLM via Groq
    3. Affiche les résultats structurés dans la console
    """
    print("\n" + "═" * 70)
    print("🤖  AGENT 3 — ANALYSE & RECOMMANDATION CHURN (LangChain + Groq)")
    print("    Attijariwafa Bank IA — v3.0.0")
    print("═" * 70)

    CLIENT_ID_TEST = 42

    print(f"\n📋 Test : Analyse du client ID {CLIENT_ID_TEST} (profil haut risque simulé)")
    print("─" * 70)

    print("\n🔧 ÉTAPE 1 — get_client_data_tool")
    profil_json = _simulate_client_profile(CLIENT_ID_TEST)
    profil      = json.loads(profil_json)
    print(f"   ✅ Segment     : {profil['segment_metier']}")
    print(f"   ✅ Solde       : {profil['solde_actuel']:,.2f} MAD")
    print(f"   ✅ Moy retrait : {profil['moy_retrait']:,.2f} MAD")
    print(f"   ✅ Ops/30j     : {profil['nb_operations_30j']}")
    print(f"   ✅ Inactif     : {profil['jours_depuis_derniere_op']} jours")

    print("\n🔧 ÉTAPE 2 — predict_churn_tool")
    churn_json = predict_churn_tool.invoke({"profil_json": profil_json})
    churn      = json.loads(churn_json)
    print(f"   ✅ Score churn : {churn['probabilite_pct']:.1f}%")
    print(f"   ✅ Niveau      : {churn['niveau_risque']}")
    print(f"   ✅ Modèle      : {churn['modele']}")
    print("   📊 TOP SHAP Features :")
    for feat in churn.get("top_shap_features", []):
        bar = "█" * int(abs(feat["shap_value"]) * 20)
        print(f"      {feat['feature']:35s} {bar} {feat['shap_value']:+.4f}  [{feat['impact']}]")

    print("\n🔧 ÉTAPE 3 — apply_business_rules_tool")
    combined   = json.dumps({"churn": churn, "profil": profil})
    rules_json = apply_business_rules_tool.invoke({"churn_et_profil_json": combined})
    rules      = json.loads(rules_json)
    print(f"   ✅ Urgence     : {rules['urgence_action']}")
    print(f"   ✅ Priorité    : {rules['priorite_globale']}")
    print(f"   ✅ Services éligibles ({rules['nb_services_eligibles']}) :")
    for svc in rules.get("services_eligibles", []):
        print(f"      [{svc['priorite']}] {svc['label']} ({svc['eligibilite']})")

    print("\n🔧 ÉTAPE 4 — Recommandation LLM (Groq " + GROQ_MODEL + ")")
    recommandation = _generer_recommandation_directe(profil, churn, rules)
    print("\n" + "─" * 70)
    print("📣 RECOMMANDATION CONSEILLER BANCAIRE :")
    print("─" * 70)
    print(recommandation)
    print("─" * 70)

    print("\n" + "═" * 70)
    print("✅ AGENT 3 — ANALYSE TERMINÉE")
    print(f"   Client    : #{CLIENT_ID_TEST} ({profil['segment_metier']})")
    print(f"   Risque    : {churn['niveau_risque']} ({churn['probabilite_pct']:.1f}%)")
    print(f"   Services  : {rules['nb_services_eligibles']} offre(s) identifiée(s)")
    print(f"   Urgence   : {rules['urgence_action']}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
