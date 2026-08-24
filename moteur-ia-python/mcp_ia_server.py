import os
import joblib
import pandas as pd
import mysql.connector
import datetime
import random
import math
import numpy as np
import holidays
from typing import Dict, Any, Optional

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("AWB_IA_MCP_Server")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

try:
    model_visite = joblib.load('xgboost_optimise.pkl')
    model_operation  = joblib.load('xgboost_model.pkl')
    encoder_segment  = joblib.load('encoder_segment.pkl')
    encoder_motif    = joblib.load('encoder_motif.pkl')
    
    model_next_date = joblib.load('xgboost_next_date.pkl')
    model_next_time = joblib.load('xgboost_next_time.pkl')
    model_next_operation = joblib.load('xgboost_next_operation.pkl')
    encoder_segment_next = joblib.load('encoder_segment_next.pkl')
    encoder_type_compte = joblib.load('encoder_type_compte.pkl')
    encoder_next_operation = joblib.load('encoder_next_operation.pkl')
except Exception as e:
    print(f"⚠️  Erreur chargement modèles : {e}")

COLONNES_VISITE = [
    'nombre_operations', 'montant_total', 'montant_moyen', 'moy_retrait',
    'nb_ops_30j', 'Demande de Crédit', 'PAIEMENT_CARTE', 'PAIEMENT_FACTURE',
    'PLACEMENT', 'Paiement TPE', 'REMISE_CHEQUE', 'RETRAIT', 'RETRAIT_EPARGNE',
    'Retrait Guichet', 'VERSEMENT', 'VIREMENT_EMIS', 'VIREMENT_RECU',
    'Versement Espèces', 'Remise de Chèque', 'Virement Reçu', 'solde_total',
    'has_compte_epargne', 'solde_moyen_compte', 'ratio_solde_habitude'
]

COLONNES_VISITE_ENRICHIES = COLONNES_VISITE + [
    'nb_ops_weekend', 'nb_ops_samedi', 'nb_ops_dimanche', 'nb_ops_ferie',
    'nb_ops_hors_horaires', 'nb_ops_heure_pointe', 'heure_moyenne_operation',
    'heure_derniere_operation', 'dernier_jour_semaine', 'derniere_est_weekend',
    'derniere_est_ferie', 'derniere_dans_horaires_agence',
    'jours_depuis_derniere_operation', 'ratio_ops_weekend', 'ratio_ops_ferie',
    'ratio_ops_hors_horaires', 'nb_comptes', 'nb_comptes_courant',
    'nb_comptes_epargne', 'nb_comptes_credit'
]

try:
    COLONNES_VISITE = joblib.load('xgboost_visite_features.pkl')
except Exception:
    if 'model_visite' in globals() and getattr(model_visite, "n_features_in_", 24) == len(COLONNES_VISITE_ENRICHIES):
        COLONNES_VISITE = COLONNES_VISITE_ENRICHIES

ALL_OP_TYPES = [
    "RETRAIT", "VERSEMENT", "VIREMENT_EMIS", "VIREMENT_RECU",
    "PAIEMENT_FACTURE", "PAIEMENT_CARTE", "REMISE_CHEQUE",
    "Paiement TPE", "Demande de Crédit", "Retrait Guichet",
    "Versement Espèces", "Remise de Chèque", "Virement Reçu",
    "PLACEMENT", "RETRAIT_EPARGNE"
]

NEXT_FEATURE_COLS = [
    "seg_enc", "type_compte_enc", "nombre_operations", "montant_total",
    "montant_moyen", "moy_retrait", "nb_ops_30j", "ratio_solde_habitude",
    "has_compte_epargne", "solde_total", "solde_moyen_compte", "montant_courant"
] + ALL_OP_TYPES

NEXT_FEATURE_COLS_ENRICHIES = NEXT_FEATURE_COLS + [
    "current_heure_decimale", "current_jour_semaine", "current_est_weekend",
    "current_est_ferie", "current_dans_horaires_agence", "current_est_heure_pointe",
]

try:
    NEXT_FEATURE_COLS = joblib.load('xgboost_next_features.pkl')
except Exception:
    if 'model_next_date' in globals() and getattr(model_next_date, "n_features_in_", len(NEXT_FEATURE_COLS)) == len(NEXT_FEATURE_COLS_ENRICHIES):
        NEXT_FEATURE_COLS = NEXT_FEATURE_COLS_ENRICHIES

OPERATION_LABELS = {
    "RETRAIT":           "Retrait Espèces",
    "VIREMENT_EMIS":     "Virement Émis",
    "VIREMENT_RECU":     "Virement Reçu",
    "VERSEMENT":         "Versement Espèces",
    "PAIEMENT_FACTURE":  "Paiement de Facture",
    "PLACEMENT":         "Placement Épargne",
    "RETRAIT_EPARGNE":   "Retrait Épargne",
}

_FERIES_MAROC = holidays.Morocco()

def _features_calendrier_dt(value) -> Dict[str, Any]:
    if not value:
        return {
            "heure_derniere_operation": 12.0,
            "dernier_jour_semaine": 0,
            "derniere_est_weekend": 0,
            "derniere_est_ferie": 0,
            "derniere_dans_horaires_agence": 1,
            "jours_depuis_derniere_operation": 999,
        }
    dt = datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
    heure = dt.hour + dt.minute / 60.0
    d = dt.date()
    est_samedi = int(d.weekday() == 5)
    est_dimanche = int(d.weekday() == 6)
    est_ferie = int(d in _FERIES_MAROC)
    dans_horaires = int(
        (not est_samedi and not est_dimanche and not est_ferie and 8.0 <= heure <= 16.5)
    )
    return {
        "heure_derniere_operation": heure,
        "dernier_jour_semaine": d.weekday(),
        "derniere_est_weekend": int(d.weekday() >= 5),
        "derniere_est_ferie": est_ferie,
        "derniere_dans_horaires_agence": dans_horaires,
        "jours_depuis_derniere_operation": max(0, (datetime.datetime.now() - dt).total_seconds() / 86400.0),
    }


def _est_jour_ouvrable(date: datetime.date) -> bool:
    if date.weekday() == 5: return False
    if date.weekday() == 6: return False
    if date in _FERIES_MAROC: return False
    return True

def _next_jour_ouvre(date: datetime.date) -> datetime.date:
    while not _est_jour_ouvrable(date):
        date += datetime.timedelta(days=1)
    return date

def _fenetre_calendaire():
    today = datetime.date.today()
    min_date = today if _est_jour_ouvrable(today) else _next_jour_ouvre(today + datetime.timedelta(days=1))
    if today.month == 12:
        next_month_year, next_month_month = today.year + 1, 1
    else:
        next_month_year, next_month_month = today.year, today.month + 1
    if next_month_month == 12:
        last_day = datetime.date(next_month_year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(next_month_year, next_month_month + 1, 1) - datetime.timedelta(days=1)
    max_date = last_day
    return min_date, max_date

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


@mcp.tool()
def get_client_history(client_id: int) -> Dict[str, Any]:
    """
    Récupère le profil complet et l'historique financier du client depuis la base MySQL.
    """
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.segment_metier, COALESCE(SUM(co.solde), 0) AS solde_actuel,
                   MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_epargne,
                   AVG(co.solde) AS solde_moyen_compte,
                   COUNT(co.id) AS nb_comptes,
                   SUM(CASE WHEN co.type_compte = 'COURANT' THEN 1 ELSE 0 END) AS nb_comptes_courant,
                   SUM(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS nb_comptes_epargne,
                   SUM(CASE WHEN co.type_compte = 'CREDIT' THEN 1 ELSE 0 END) AS nb_comptes_credit
            FROM client c LEFT JOIN compte co ON c.id = co.client_id
            WHERE c.id = %s GROUP BY c.segment_metier
        """, (client_id,))
        base = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS nb_ops,
                   COALESCE(AVG(CASE WHEN type_operation='RETRAIT' THEN montant END), 0) AS moy_retrait,
                   COALESCE(AVG(HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60), 12) AS heure_moyenne_operation,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) IN (1, 7) THEN 1 ELSE 0 END) AS nb_ops_weekend,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) = 7 THEN 1 ELSE 0 END) AS nb_ops_samedi,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) = 1 THEN 1 ELSE 0 END) AS nb_ops_dimanche,
                   SUM(CASE
                       WHEN DAYOFWEEK(date_heure_operation) = 7
                            AND (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 8 AND 13
                       THEN 0
                       WHEN DAYOFWEEK(date_heure_operation) BETWEEN 2 AND 6
                            AND (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 8 AND 16.5
                       THEN 0
                       ELSE 1
                   END) AS nb_ops_hors_horaires,
                   SUM(CASE WHEN (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 11 AND 14 THEN 1 ELSE 0 END) AS nb_ops_heure_pointe
            FROM historique_operation
            WHERE client_id = %s
        """, (client_id,))
        hist = cursor.fetchone()

        cursor.execute("SELECT DATE(date_heure_operation) AS d FROM historique_operation WHERE client_id = %s", (client_id,))
        dates_rows = cursor.fetchall()

        cursor.execute("""
            SELECT type_operation, montant, date_heure_operation 
            FROM historique_operation 
            WHERE client_id = %s ORDER BY date_heure_operation DESC LIMIT 1
        """, (client_id,))
        last_op = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS nombre_operations, COALESCE(SUM(montant), 0) AS montant_total,
                   COALESCE(AVG(montant), 0) AS montant_moyen, type_operation
            FROM historique_operation WHERE client_id = %s GROUP BY type_operation
        """, (client_id,))
        ops_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        profil = {
            "client_id": client_id,
            "segment_metier":     base["segment_metier"] if base else "PARTICULIER",
            "solde_actuel":       float(base["solde_actuel"]) if base else 0.0,
            "solde_moyen_compte": float(base["solde_moyen_compte"]) if base and base["solde_moyen_compte"] else 0.0,
            "has_compte_epargne": int(base["has_epargne"]) if base else 0,
            "nb_comptes": int(base["nb_comptes"] or 0) if base else 0,
            "nb_comptes_courant": int(base["nb_comptes_courant"] or 0) if base else 0,
            "nb_comptes_epargne": int(base["nb_comptes_epargne"] or 0) if base else 0,
            "nb_comptes_credit": int(base["nb_comptes_credit"] or 0) if base else 0,
            "nb_operations_30j":  int(hist["nb_ops"]) if hist else 0,
            "moyenne_retraits_30j": float(hist["moy_retrait"]) if hist else 0.0,
            "nb_ops_weekend": int(hist["nb_ops_weekend"] or 0) if hist else 0,
            "nb_ops_samedi": int(hist["nb_ops_samedi"] or 0) if hist else 0,
            "nb_ops_dimanche": int(hist["nb_ops_dimanche"] or 0) if hist else 0,
            "nb_ops_ferie": sum(1 for r in dates_rows if r.get("d") and r["d"] in _FERIES_MAROC),
            "nb_ops_hors_horaires": int(hist["nb_ops_hors_horaires"] or 0) if hist else 0,
            "nb_ops_heure_pointe": int(hist["nb_ops_heure_pointe"] or 0) if hist else 0,
            "heure_moyenne_operation": float(hist["heure_moyenne_operation"] or 12.0) if hist else 12.0,
            "last_operation": {
                "type": last_op["type_operation"] if last_op else "Profil Initial",
                "montant": float(last_op["montant"]) if last_op else 0.0,
                "date": str(last_op["date_heure_operation"]) if last_op else str(datetime.datetime.now())
            }
        }

        total_ops = sum(r["nombre_operations"] for r in ops_rows)
        profil["nombre_operations"] = total_ops
        profil["montant_total"]     = sum(float(r["montant_total"]) for r in ops_rows)
        profil["montant_moyen"]     = profil["montant_total"] / total_ops if total_ops > 0 else 0.0
        profil.update(_features_calendrier_dt(last_op["date_heure_operation"] if last_op else None))
        denom = max(1, int(hist["nb_ops"]) if hist else 0)
        profil["ratio_ops_weekend"] = profil["nb_ops_weekend"] / denom
        profil["ratio_ops_ferie"] = profil["nb_ops_ferie"] / denom
        profil["ratio_ops_hors_horaires"] = profil["nb_ops_hors_horaires"] / denom

        for row in ops_rows:
            profil[row["type_operation"]] = int(row["nombre_operations"])

        return profil
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def predict_visite(profil_json: str) -> Dict[str, Any]:
    """
    Exécute le modèle XGBoost pour prédire la probabilité de visite et l'opération future.
    Utilise une logique déterministe respectant les horaires bancaires Maroc.
    """
    import json
    try:
        profil = json.loads(profil_json)
    except:
        return {"error": "Invalid profile JSON"}

    features = {col: 0 for col in COLONNES_VISITE}
    features['nombre_operations'] = profil.get('nombre_operations', 1)
    features['montant_total'] = profil.get('montant_total', 0)
    features['montant_moyen'] = profil.get('montant_moyen', 0)
    features['moy_retrait'] = profil.get('moyenne_retraits_30j', 0.0)
    features['nb_ops_30j'] = profil.get('nb_operations_30j', 0)
    features['solde_total'] = profil.get('solde_actuel', 0.0)
    features['solde_moyen_compte'] = profil.get('solde_moyen_compte', 0.0)
    features['has_compte_epargne'] = profil.get('has_compte_epargne', 0)
    features['ratio_solde_habitude'] = features['solde_total'] / (features['moy_retrait'] + 1)
    for col in COLONNES_VISITE_ENRICHIES:
        if col in profil and col in features:
            features[col] = profil.get(col, 0)
    
    for op in ALL_OP_TYPES:
        if op in profil: features[op] = profil[op]

    df = pd.DataFrame([features], columns=COLONNES_VISITE)
    if hasattr(model_visite, "predict_proba"):
        raw_proba = float(model_visite.predict_proba(df)[0][1])
    else:
        raw_proba = float(model_visite.predict(df)[0])
    raw_pct = raw_proba * 100.0
    _contraction = float(os.getenv("CONTRACTION_VISITE", "1.0"))
    probabilite_finale = round(float(np.clip(50.0 + (raw_pct - 50.0) * _contraction, 5.0, 93.0)), 1)

    op_future = "Opération Bancaire"
    try:
        segment = str(profil.get('segment_metier', 'PARTICULIER')).upper()
        try:
            seg_enc = encoder_segment_next.transform([segment])[0]
        except:
            seg_enc = 0
            
        try:
            type_compte_enc = encoder_type_compte.transform(["AUCUN"])[0]
        except:
            type_compte_enc = 0

        montant_courant = profil.get("last_operation", {}).get("montant", 0.0)

        features_next = {
            "seg_enc": seg_enc,
            "type_compte_enc": type_compte_enc,
            "nombre_operations": features['nombre_operations'],
            "montant_total": features['montant_total'],
            "montant_moyen": features['montant_moyen'],
            "moy_retrait": features['moy_retrait'],
            "nb_ops_30j": features['nb_ops_30j'],
            "ratio_solde_habitude": features['ratio_solde_habitude'],
            "has_compte_epargne": features['has_compte_epargne'],
            "solde_total": features['solde_total'],
            "solde_moyen_compte": features['solde_moyen_compte'],
            "montant_courant": montant_courant
        }
        for op in ALL_OP_TYPES:
            features_next[op] = features.get(op, 0)
        cal = _features_calendrier_dt(profil.get("last_operation", {}).get("date"))
        features_next.update({
            "current_heure_decimale": cal["heure_derniere_operation"],
            "current_jour_semaine": cal["dernier_jour_semaine"],
            "current_est_weekend": cal["derniere_est_weekend"],
            "current_est_ferie": cal["derniere_est_ferie"],
            "current_dans_horaires_agence": cal["derniere_dans_horaires_agence"],
            "current_est_heure_pointe": int(11.0 <= cal["heure_derniere_operation"] <= 14.0),
        })
            
        df_next = pd.DataFrame([[features_next.get(c, 0) for c in NEXT_FEATURE_COLS]], columns=NEXT_FEATURE_COLS)

        if 'model_next_operation' in globals():
            op_enc = model_next_operation.predict(df_next)[0]
            op_future_raw = encoder_next_operation.inverse_transform([op_enc])[0]
            op_future = OPERATION_LABELS.get(op_future_raw.upper(), op_future_raw)

        today = datetime.date.today()
        if probabilite_finale >= 88 and _est_jour_ouvrable(today):
            target_date = today
        elif 'model_next_date' in globals():
            delta_days = max(0, int(round(model_next_date.predict(df_next)[0])))
            target_date = today + datetime.timedelta(days=delta_days)
            target_date = today if target_date <= today and _est_jour_ouvrable(today) else _next_jour_ouvre(target_date)
        else:
            min_date, _ = _fenetre_calendaire()
            target_date = min_date

        if 'model_next_time' in globals():
            hour_float = model_next_time.predict(df_next)[0]
            h = max(8, min(16, int(round(hour_float))))
        else:
            h = 10

        h = min(16, max(8, h + ((int(profil.get("client_id", 0) or 0) + target_date.day) % 3) - 1))
    except Exception as e:
        print(f"Erreur lors de la prédiction next_event : {e}")
        min_date, _ = _fenetre_calendaire()
        target_date = min_date
        h = 10
    
    return {
        "score_probabilite": probabilite_finale,
        "operation_prevue": op_future,
        "date_prevue": target_date.strftime("%Y-%m-%d"),
        "plage_horaire": f"{h:02d}:00",
        "statut": "VISITE_PROBABLE" if probabilite_finale > 70 else "VISITE_INCERTAINE"
    }

@mcp.tool()
def calculate_risk_and_strategy(profil_json: str) -> Dict[str, Any]:
    """
    Calcule le niveau de risque et la stratégie prescrite.
    """
    import json
    try:
        profil = json.loads(profil_json)
    except:
        return {"error": "Invalid profile JSON"}

    solde_actuel = profil.get("solde_actuel", 0.0)
    solde_moyen = profil.get("solde_moyen_compte", 0.0)
    nb_ops_30j = profil.get("nb_operations_30j", 0)
    tot_ops = profil.get("nombre_operations", 0)
    moy_retraits = profil.get("moyenne_retraits_30j", 0.0)
    segment = profil.get("segment_metier", "Standard")
    has_epargne = bool(profil.get("has_compte_epargne", 0))
    ratio_hors_horaires = float(profil.get("ratio_ops_hors_horaires", 0.0) or 0.0)
    ratio_weekend = float(profil.get("ratio_ops_weekend", 0.0) or 0.0)
    jours_inactif = float(profil.get("jours_depuis_derniere_operation", 999) or 999)

    score_churn = 0.0
    if solde_moyen > 1000:
        ratio = solde_actuel / solde_moyen
        if ratio < 0.4: score_churn += 0.6
        elif ratio < 0.7: score_churn += 0.3
    if solde_actuel > 0 and moy_retraits > (solde_actuel * 0.4): score_churn += 0.4
    if tot_ops > 20 and nb_ops_30j == 0: score_churn += 0.5
    
    score_churn = min(score_churn, 0.95)
    
    if score_churn >= 0.7: niveau = "CRITIQUE"
    elif score_churn >= 0.4: niveau = "ALERTE"
    else: niveau = "FAIBLE"
    
    actions = []
    if niveau == "CRITIQUE":
        actions.append("appel urgent de rétention avant visite")
        actions.append("rendez-vous avec conseiller senior ou directeur d'agence")
    elif niveau == "ALERTE":
        actions.append("entretien de fidélisation pour identifier les irritants")
    else:
        actions.append("accueil personnalisé et entretien de satisfaction")

    if solde_moyen > 1000 and solde_actuel < solde_moyen * 0.6:
        actions.append("analyser la baisse de solde et sécuriser les flux")
    if solde_actuel > 50000 and not has_epargne:
        actions.append("proposer une épargne ou un placement adapté")
    if solde_actuel > 0 and moy_retraits > solde_actuel * 0.35:
        actions.append("traiter les retraits importants et proposer une alternative sécurisée")
    if tot_ops > 20 and nb_ops_30j == 0:
        actions.append("réactiver le client avec une offre de retour")
    if ratio_hors_horaires >= 0.35 or ratio_weekend >= 0.25:
        actions.append("proposer accompagnement digital et rendez-vous sur créneau confortable")
    if any(x in str(segment).upper() for x in ["PRO", "PME", "TPE", "PROFESSIONNEL"]):
        actions.append("étudier trésorerie, TPE, leasing ou optimisation des encaissements")
    elif "VIP" in str(segment).upper():
        actions.append("préparer une offre premium et un traitement prioritaire")

    strat = "Pour éviter la perte du client : " + "; ".join(dict.fromkeys(actions[:4])) + "."
    
    return {
        "score_churn": score_churn,
        "niveau_risque": niveau,
        "strategie_prescrite": strat
    }

@mcp.tool()
def generate_insight(profil_json: str, prediction_json: str, risque_json: str) -> str:
    """
    Génère un insight personnalisé via LLM (Groq) pour le conseiller.
    """
    import json
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    if not GROQ_API_KEY:
        return "Stratégie de l'Agent : Veuillez configurer la clé API Groq pour obtenir des insights personnalisés."

    try:
        profil = json.loads(profil_json)
        prediction = json.loads(prediction_json)
        risque = json.loads(risque_json)
        
        contexte = (
            f"Segment: {profil.get('segment_metier')} | "
            f"Solde: {profil.get('solde_actuel'):,.0f} MAD | "
            f"Opérations: {profil.get('nombre_operations')} | "
            f"Risque: {risque.get('niveau_risque')} | "
            f"Prédiction: {prediction.get('operation_prevue')} le {prediction.get('date_prevue')}."
        )

        prompt = (
            f"Tu es l'Expert en Rétention Client d'Attijariwafa Bank. Ton objectif est de NE PAS PERDRE CE CLIENT.\n"
            f"Analyse la SANTÉ BANCAIRE de ce client :\n"
            f"[{contexte}]\n"
            f"Tâche : Évalue sa santé financière. Ensuite, définis une STRATÉGIE DE RÉTENTION ultra-personnalisée et propose un SERVICE PRÉCIS (ex: renégociation, geste commercial, restructuration) pour le retenir.\n"
            f"Réponds en français sur UNE SEULE ligne au format suivant :\n"
            f"Santé : [Diagnostic du risque d'attrition] | Stratégie : [Action de rétention et service à proposer pour ne pas le perdre]"
        )

        llm = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=GROQ_API_KEY, temperature=0.7)
        result = (ChatPromptTemplate.from_messages([("user", "{prompt}")]) | llm).invoke({"prompt": prompt})
        return result.content.strip()
    except Exception as e:
        return f"Stratégie de l'Agent : Suivi personnalisé recommandé (Erreur IA: {str(e)})"

@mcp.tool()
def get_client_data(client_id: int) -> Dict[str, Any]:
    """
    Récupère le profil financier complet d'un client au format attendu par l'Agent 3
    (analyse churn). C'est le point d'accès UNIQUE aux données client pour l'Agent 3 :
    profil de base, statistiques opérationnelles, inactivité et 5 dernières transactions.

    Args:
        client_id: Identifiant numérique unique du client.

    Returns:
        Dict avec le profil complet, ou {"error": "..."} en cas d'échec.
    """
    import json
    try:
        conn   = get_db_connection()
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
            return {"error": f"Client {client_id} introuvable en base."}

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

        profil = {
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
            "_source": "MCP",
        }
        return profil
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_all_client_ids() -> Dict[str, Any]:
    """
    Retourne la liste de tous les identifiants clients (pour les batchs Agent 1 / Agent 2).

    Returns:
        Dict {"client_ids": [int, ...]} ou {"error": "..."}.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM client ORDER BY id")
        ids = [int(r[0]) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return {"client_ids": ids}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_profil_visite(client_id: int) -> Dict[str, Any]:
    """
    Récupère le profil client au schéma EXACT attendu par l'Agent 2 (prédiction de visite) :
    profil de base, statistiques opérationnelles, signaux calendrier/agence et ratios.

    Args:
        client_id: Identifiant numérique unique du client.

    Returns:
        Dict avec le profil complet, ou {"error": "..."}.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.segment_metier,
                   COALESCE(SUM(co.solde), 0) AS solde_actuel,
                   MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_epargne,
                   AVG(co.solde) AS solde_moyen_compte,
                   COUNT(co.id) AS nb_comptes,
                   SUM(CASE WHEN co.type_compte = 'COURANT' THEN 1 ELSE 0 END) AS nb_comptes_courant,
                   SUM(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS nb_comptes_epargne,
                   SUM(CASE WHEN co.type_compte = 'CREDIT' THEN 1 ELSE 0 END) AS nb_comptes_credit
            FROM client c
            LEFT JOIN compte co ON c.id = co.client_id
            WHERE c.id = %s
            GROUP BY c.segment_metier
        """, (client_id,))
        base = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) AS nb_ops,
                   COALESCE(AVG(CASE WHEN type_operation='RETRAIT' THEN montant END), 0) AS moy_retrait,
                   COALESCE(AVG(HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60), 12) AS heure_moyenne_operation,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) IN (1, 7) THEN 1 ELSE 0 END) AS nb_ops_weekend,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) = 7 THEN 1 ELSE 0 END) AS nb_ops_samedi,
                   SUM(CASE WHEN DAYOFWEEK(date_heure_operation) = 1 THEN 1 ELSE 0 END) AS nb_ops_dimanche,
                   SUM(CASE
                       WHEN DAYOFWEEK(date_heure_operation) = 7
                             AND (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 8 AND 13
                       THEN 0
                       WHEN DAYOFWEEK(date_heure_operation) BETWEEN 2 AND 6
                             AND (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 8 AND 16.5
                       THEN 0
                       ELSE 1
                   END) AS nb_ops_hors_horaires,
                   SUM(CASE WHEN (HOUR(date_heure_operation) + MINUTE(date_heure_operation) / 60) BETWEEN 11 AND 14 THEN 1 ELSE 0 END) AS nb_ops_heure_pointe,
                   MAX(date_heure_operation) AS derniere_operation_at
            FROM historique_operation
            WHERE client_id = %s
        """, (client_id,))
        hist = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS nb_ops_30j FROM historique_operation WHERE client_id = %s AND date_heure_operation >= DATE_SUB(NOW(), INTERVAL 30 DAY)", (client_id,))
        hist_30j = cursor.fetchone()
        cursor.execute("SELECT DATE(date_heure_operation) AS d FROM historique_operation WHERE client_id = %s", (client_id,))
        dates_rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS nombre_operations, COALESCE(SUM(montant), 0) AS montant_total, COALESCE(AVG(montant), 0) AS montant_moyen, type_operation FROM historique_operation WHERE client_id = %s GROUP BY type_operation", (client_id,))
        ops_rows = cursor.fetchall()
        cursor.close(); conn.close()

        nb_ops_total_hist = int(hist["nb_ops"]) if hist else 0
        nb_ops_ferie = sum(1 for r in dates_rows if r.get("d") and r["d"] in _FERIES_MAROC)
        derniere_feats = _features_calendrier_dt(
            str(hist.get("derniere_operation_at")) if hist and hist.get("derniere_operation_at") else None
        )
        profil = {
            "client_id": int(client_id),
            "segment_metier": base["segment_metier"] if base else "PARTICULIER",
            "solde_actuel": float(base["solde_actuel"]) if base else 0.0,
            "has_compte_epargne": int(base["has_epargne"]) if base else 0,
            "solde_moyen_compte": float(base["solde_moyen_compte"]) if base and base["solde_moyen_compte"] else 0.0,
            "nb_comptes": int(base["nb_comptes"] or 0) if base else 0,
            "nb_comptes_courant": int(base["nb_comptes_courant"] or 0) if base else 0,
            "nb_comptes_epargne": int(base["nb_comptes_epargne"] or 0) if base else 0,
            "nb_comptes_credit": int(base["nb_comptes_credit"] or 0) if base else 0,
            "nb_operations_30j": int(hist_30j["nb_ops_30j"]) if hist_30j else 0,
            "moyenne_retraits_30j": float(hist["moy_retrait"]) if hist else 0.0,
            "nb_ops_weekend": int(hist["nb_ops_weekend"] or 0) if hist else 0,
            "nb_ops_samedi": int(hist["nb_ops_samedi"] or 0) if hist else 0,
            "nb_ops_dimanche": int(hist["nb_ops_dimanche"] or 0) if hist else 0,
            "nb_ops_ferie": nb_ops_ferie,
            "nb_ops_hors_horaires": int(hist["nb_ops_hors_horaires"] or 0) if hist else 0,
            "nb_ops_heure_pointe": int(hist["nb_ops_heure_pointe"] or 0) if hist else 0,
            "heure_moyenne_operation": float(hist["heure_moyenne_operation"] or 12.0) if hist else 12.0,
        }
        profil.update(derniere_feats)
        total_ops = sum(r["nombre_operations"] for r in ops_rows)
        profil["nombre_operations"] = total_ops
        profil["montant_total"] = sum(float(r["montant_total"]) for r in ops_rows)
        profil["montant_moyen"] = profil["montant_total"] / total_ops if total_ops > 0 else 0.0
        denom = max(1, nb_ops_total_hist)
        profil["ratio_ops_weekend"] = profil["nb_ops_weekend"] / denom
        profil["ratio_ops_ferie"] = profil["nb_ops_ferie"] / denom
        profil["ratio_ops_hors_horaires"] = profil["nb_ops_hors_horaires"] / denom
        for row in ops_rows:
            profil[row["type_operation"]] = int(row["nombre_operations"])
        return profil
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_training_data() -> Dict[str, Any]:
    """
    Fournit le dataset brut d'entraînement à l'Agent 1 : toutes les opérations
    (historique_operation) + les agrégats par client (solde, comptes, segment).

    Returns:
        Dict {"operations": [...], "clients": [...]} (dates sérialisées en str),
        ou {"error": "..."}.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM historique_operation")
        operations = cursor.fetchall()
        cursor.execute("""
            SELECT
                cl.id                                                        AS client_id,
                cl.segment_metier,
                COALESCE(SUM(co.solde), 0)                                   AS solde_total,
                MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_compte_epargne,
                AVG(co.solde)                                                AS solde_moyen_compte,
                COUNT(co.id)                                                 AS nb_comptes,
                SUM(CASE WHEN co.type_compte = 'COURANT' THEN 1 ELSE 0 END)  AS nb_comptes_courant,
                SUM(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END)  AS nb_comptes_epargne,
                SUM(CASE WHEN co.type_compte = 'CREDIT' THEN 1 ELSE 0 END)   AS nb_comptes_credit
            FROM client cl
            LEFT JOIN compte co ON cl.id = co.client_id
            GROUP BY cl.id, cl.segment_metier
        """)
        clients = cursor.fetchall()
        cursor.close(); conn.close()

        from decimal import Decimal
        def _clean(rows):
            out = []
            for r in rows:
                d = {}
                for k, v in r.items():
                    if isinstance(v, (datetime.datetime, datetime.date)):
                        d[k] = str(v)
                    elif isinstance(v, Decimal):
                        d[k] = float(v)
                    else:
                        d[k] = v
                out.append(d)
            return out

        return {"operations": _clean(operations), "clients": _clean(clients)}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
