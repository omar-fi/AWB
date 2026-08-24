import os
import sys
import json
import joblib
import pandas as pd
import mysql.connector
import datetime
import holidays
import numpy as np
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

import asyncio
USE_MCP = os.getenv("AGENT2_USE_MCP", "1") != "0"

CONTRACTION_VISITE = float(os.getenv("CONTRACTION_VISITE", "1.0"))

_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVER_SCRIPT = os.path.join(_MCP_DIR, "mcp_ia_server.py")


async def _call_mcp_tool_async(tool_name: str, args: dict) -> dict:
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
            result  = await session.call_tool(tool_name, args)
            content = result.content[0].text if result.content else ""
            return json.loads(content) if isinstance(content, str) else content


def _call_mcp_tool(tool_name: str, args: dict) -> dict | None:
    """Wrapper synchrone d'un appel d'outil MCP. Retourne None si échec."""
    try:
        return asyncio.run(_call_mcp_tool_async(tool_name, args))
    except Exception as exc:
        print(f"⚠️ [MCP] Appel '{tool_name}' échoué ({exc}). Fallback SQL direct.")
        return None

try:
    model_visite = joblib.load('xgboost_optimise.pkl')
    print("🧠 Modèle XGBoost (visite) chargé avec succès par l'Agent 2 !")
except Exception as e:
    print(f"❌ Impossible de charger xgboost_optimise.pkl : {e}")
    exit(1)

try:
    model_operation  = joblib.load('xgboost_model.pkl')
    encoder_segment  = joblib.load('encoder_segment.pkl')
    encoder_motif    = joblib.load('encoder_motif.pkl')
    print("🧠 Modèle XGBoost (operation) chargé avec succès par l'Agent 2 !")
except Exception as e:
    print(f"⚠️  Modèle opération indisponible ({e})")
    model_operation = None

try:
    model_next_date = joblib.load('xgboost_next_date.pkl')
    model_next_time = joblib.load('xgboost_next_time.pkl')
    model_next_operation = joblib.load('xgboost_next_operation.pkl')
    encoder_segment_next = joblib.load('encoder_segment_next.pkl')
    encoder_type_compte = joblib.load('encoder_type_compte.pkl')
    encoder_next_operation = joblib.load('encoder_next_operation.pkl')
    print("🧠 Modèles Next Event chargés avec succès par l'Agent 2 !")
except Exception as e:
    print(f"⚠️  Modèles Next Event indisponibles ({e})")
    model_next_date = None
    model_next_time = None
    model_next_operation = None
    encoder_segment_next = None
    encoder_type_compte = None
    encoder_next_operation = None

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

# Canal d'un passage au guichet : seule source valable pour l'« opération
# prévue » d'une visite. Aligné sur agent_entrainement.CANAL_AGENCE.
CANAL_AGENCE = "AGENCE"
OPERATION_AGENCE_DEFAUT = "Retrait Guichet"

# Explicabilité de la prédiction. Le LLM n'est sollicité que pour les visites
# imminentes : c'est là que le conseiller lit le texte. Au-delà, une phrase
# factuelle générée par règles suffit — et évite 100 appels d'inférence par
# nuit, que les quotas Groq ne supportent pas.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"
HORIZON_EXPLICATION_JOURS = 7

# Modèle « motif de la prochaine visite ». Chargé au démarrage ; en son absence
# on retombe sur le mode d'agence du client, qui reste une réponse défendable
# mais ne varie jamais d'une visite à l'autre.
try:
    from features_visite import construire_features as _features_visite
    _modele_op_visite  = joblib.load("xgboost_operation_visite.pkl")
    _encodeur_op_visite = joblib.load("encoder_operation_visite.pkl")
    _colonnes_op_visite = joblib.load("operation_visite_features.pkl")
    _meta_op_visite     = joblib.load("types_operation_visite.pkl")
    print("🧠 Modèle 'motif de visite' chargé avec succès par l'Agent 2 !")
except Exception as _exc:
    _modele_op_visite = None
    print(f"⚠️  Modèle 'motif de visite' indisponible ({_exc}) — repli sur le mode d'agence.")

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
    "PAIEMENT_CARTE":    "Paiement par Carte",
    "REMISE_CHEQUE":     "Remise de Chèque",
    "PAIEMENT TPE":      "Paiement TPE",
    "RETRAIT GUICHET":   "Retrait Guichet",
    "DEMANDE DE CREDIT": "Demande de Crédit",
    "PLACEMENT":         "Placement Épargne",
    "RETRAIT_EPARGNE":   "Retrait Épargne",
    "CREATION_CLIENT":   "Création de Profil Client",
}

_FERIES_MAROC = holidays.Morocco()

def _format_operation_label(motif: str) -> str:
    if motif is None: return motif
    return OPERATION_LABELS.get(motif) or OPERATION_LABELS.get(str(motif).upper()) or motif

def _today_maroc() -> datetime.date:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).date()

def _est_jour_ferie_maroc(date: datetime.date) -> bool:
    return date in _FERIES_MAROC

def _features_calendrier_dt(value) -> dict:
    if not value:
        return {
            "heure_derniere_operation": 12.0,
            "dernier_jour_semaine": 0,
            "derniere_est_weekend": 0,
            "derniere_est_ferie": 0,
            "derniere_dans_horaires_agence": 1,
            "jours_depuis_derniere_operation": 999,
        }
    if isinstance(value, str):
        dt = datetime.datetime.fromisoformat(value)
    elif isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        dt = datetime.datetime.combine(value, datetime.time(12, 0))
    else:
        dt = value
    heure = dt.hour + dt.minute / 60.0
    d = dt.date()
    est_samedi = int(d.weekday() == 5)
    est_dimanche = int(d.weekday() == 6)
    est_ferie = int(_est_jour_ferie_maroc(d))
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
    if _est_jour_ferie_maroc(date): return False   
    return True                                    

def _next_jour_ouvre(date: datetime.date) -> datetime.date:
    while not _est_jour_ouvrable(date):
        date += datetime.timedelta(days=1)
    return date

def _get_last_type_compte(client_id: int) -> str:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COALESCE(co.type_compte, 'AUCUN') AS type_compte FROM historique_operation h LEFT JOIN compte co ON h.compte_id = co.id WHERE h.client_id = %s ORDER BY h.date_heure_operation DESC LIMIT 1", (client_id,))
        row = cursor.fetchone()
        cursor.close(); conn.close()
        return row["type_compte"] if row else "AUCUN"
    except Exception: return "AUCUN"

def _get_profil_client(client_id):
    if USE_MCP:
        profil_mcp = _call_mcp_tool("get_profil_visite", {"client_id": client_id})
        if profil_mcp and not profil_mcp.get("error"):
            return profil_mcp
        print(f"⚠️ MCP indisponible pour client {client_id} — bascule SQL direct.")

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
        nb_ops_ferie = sum(1 for r in dates_rows if r.get("d") and _est_jour_ferie_maroc(r["d"]))
        derniere_feats = _features_calendrier_dt(hist.get("derniere_operation_at") if hist else None)
        profil = {
            "client_id": client_id,
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
        for row in ops_rows: profil[row["type_operation"]] = int(row["nombre_operations"])
        return profil
    except Exception as e:
        print(f"⚠️ Erreur profil client {client_id} : {e}")
        return None

def _predire_visite(profil, type_op_actuel, montant):
    features = {col: 0 for col in COLONNES_VISITE}
    if profil:
        features['nombre_operations'] = profil.get('nombre_operations', 1) + 1
        features['montant_total'] = profil.get('montant_total', 0) + montant
        nb = features['nombre_operations']
        features['montant_moyen'] = features['montant_total'] / nb if nb > 0 else montant
        features['moy_retrait'] = profil.get('moyenne_retraits_30j', 0.0)
        features['nb_ops_30j'] = profil.get('nb_operations_30j', 0)
        features['solde_total'] = profil.get('solde_actuel', 0.0)
        features['solde_moyen_compte'] = profil.get('solde_moyen_compte', 0.0)
        features['ratio_solde_habitude'] = features['solde_total'] / (features['moy_retrait'] + 1)
        for col in COLONNES_VISITE_ENRICHIES:
            if col in profil and col in features:
                features[col] = profil.get(col, 0)
        for col in ['Demande de Crédit', 'PAIEMENT_CARTE', 'PAIEMENT_FACTURE', 'PLACEMENT',
                    'Paiement TPE', 'REMISE_CHEQUE', 'RETRAIT', 'RETRAIT_EPARGNE',
                    'Retrait Guichet', 'VERSEMENT', 'VIREMENT_EMIS', 'VIREMENT_RECU',
                    'Versement Espèces', 'Remise de Chèque', 'Virement Reçu']:
            if col in profil: features[col] = profil[col]
        features['has_compte_epargne'] = profil.get('has_compte_epargne', 0)
    else:
        features['nombre_operations'] = 1
        features['montant_total'] = montant
        features['montant_moyen'] = montant
        features['moy_retrait'] = montant if type_op_actuel == "RETRAIT" else 0.0
        features['nb_ops_30j'] = 1
        features['solde_total'] = montant
        features['solde_moyen_compte'] = montant
        features['ratio_solde_habitude'] = montant / (features['moy_retrait'] + 1)

    if type_op_actuel in features: features[type_op_actuel] += 1
    df = pd.DataFrame([features], columns=COLONNES_VISITE)

    if hasattr(model_visite, "predict_proba"):
        raw_proba = float(model_visite.predict_proba(df)[0][1])
    else:
        raw_proba = float(model_visite.predict(df)[0])
    pred_label = 1 if raw_proba >= 0.5 else 0

    raw_pct = raw_proba * 100.0
    probabilite_finale = 50.0 + (raw_pct - 50.0) * CONTRACTION_VISITE
    ajustement = 0.0
    if profil:
        segment = str(profil.get('segment_metier', '')).upper()
        nb_ops_30j = profil.get('nb_operations_30j', 0)
        jours_inactif = float(profil.get("jours_depuis_derniere_operation", 999) or 999)
        ratio_hors_horaires = float(profil.get("ratio_ops_hors_horaires", 0.0) or 0.0)
        solde_total = float(profil.get("solde_actuel", 0.0) or 0.0)

        if 'VIP' in segment:
            ajustement += 2.0
        elif any(x in segment for x in ['PRO', 'PME', 'TPE', 'PROFESSIONNEL']):
            ajustement += 1.0

        if nb_ops_30j >= 6:
            ajustement += 4.0
        elif nb_ops_30j >= 3:
            ajustement += 2.0
        elif nb_ops_30j == 0:
            ajustement -= 5.0

        if jours_inactif > 45:
            ajustement -= 8.0
        elif jours_inactif > 20:
            ajustement -= 4.0
        elif jours_inactif <= 3:
            ajustement += 3.0

        if ratio_hors_horaires >= 0.5:
            ajustement += 1.5
        if solde_total < 1000:
            ajustement -= 2.0

    probabilite_finale = float(np.clip(probabilite_finale + ajustement, 5.0, 93.0))

    if probabilite_finale >= 80:
        statut = "VISITE_QUASI_CERTAINE"
    elif probabilite_finale >= 75:
        statut = "VISITE_PROBABLE"
    elif probabilite_finale >= 55:
        statut = "VISITE_INCERTAINE"
    else:
        statut = "VISITE_PEU_PROBABLE"

    return pred_label, probabilite_finale, statut

_CRENEAUX_HAUTE_FREQUENTATION  = [(9, 0), (9, 30), (10, 0), (10, 30), (11, 0), (11, 30)]
_CRENEAUX_NORMALE_FREQUENTATION = [(8, 30), (13, 0), (13, 30), (14, 0), (14, 30), (15, 0)]
_CRENEAUX_BASSE_FREQUENTATION   = [(8, 0), (15, 30), (16, 0), (16, 30)]

def _choisir_creneau(probabilite: float, date: datetime.date, profil: dict | None = None) -> tuple:
    if probabilite >= 75:
        creneaux = _CRENEAUX_HAUTE_FREQUENTATION
    elif probabilite >= 50:
        creneaux = _CRENEAUX_HAUTE_FREQUENTATION + _CRENEAUX_NORMALE_FREQUENTATION
    else:
        creneaux = _CRENEAUX_NORMALE_FREQUENTATION + _CRENEAUX_BASSE_FREQUENTATION

    seed_client = 0
    if profil:
        seed_client = int(profil.get("client_id", 0) or 0)
        if seed_client == 0:
            seed_client = int(profil.get("nombre_operations", 0) or 0)
    idx = (int(probabilite * 10) + seed_client + date.day) % len(creneaux)
    return creneaux[idx]

def _predire_date_visite(probabilite, base_datetime=None, profil=None, forcer_aujourdhui=False):
    today = _today_maroc()
    seed = int((probabilite % 1.0) * 100) if probabilite % 1.0 > 0 else int(probabilite)

    if forcer_aujourdhui or probabilite >= 62:
        if _est_jour_ouvrable(today):
            target_date = today
        else:
            target_date = _next_jour_ouvre(today + datetime.timedelta(days=1))
    elif probabilite >= 55:
        decalage = (seed % 3) + 1
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)
    elif probabilite >= 45:
        decalage = (seed % 7) + 4
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)
    else:
        decalage = (seed % 15) + 11
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)

    h, m = _choisir_creneau(probabilite, target_date, profil=profil)
    return target_date.strftime("%Y-%m-%d"), f"{h:02d}:{m:02d}"

def _build_features_next_event(profil, type_compte: str, montant_courant: float):
    features = {col: 0 for col in NEXT_FEATURE_COLS}
    if profil:
        for k in ["nombre_operations", "montant_total", "montant_moyen", "moy_retrait", "nb_ops_30j", "has_compte_epargne", "solde_total", "solde_moyen_compte"]:
            features[k] = profil.get(k, 0)
        features["ratio_solde_habitude"] = features["solde_total"] / (features["moy_retrait"] + 1.0)
    features["montant_courant"] = float(montant_courant)
    if encoder_segment_next:
        try: features["seg_enc"] = int(encoder_segment_next.transform([profil.get("segment_metier", "Particulier")])[0])
        except: pass
    if encoder_type_compte:
        try: features["type_compte_enc"] = int(encoder_type_compte.transform([str(type_compte)])[0])
        except: pass
    for op in ALL_OP_TYPES: features[op] = int(profil.get(op, 0) if profil else 0)
    return pd.DataFrame([features], columns=NEXT_FEATURE_COLS)

def _build_features_next_event_at(profil, type_compte: str, montant_courant: float, base_datetime: datetime.datetime):
    df = _build_features_next_event(profil, type_compte, montant_courant)
    if not set(NEXT_FEATURE_COLS_ENRICHIES).issubset(set(NEXT_FEATURE_COLS)):
        return df
    dt = base_datetime if isinstance(base_datetime, datetime.datetime) else datetime.datetime.now()
    heure = dt.hour + dt.minute / 60.0
    d = dt.date()
    enriched_cols = [
        "current_heure_decimale", "current_jour_semaine", "current_est_weekend",
        "current_est_ferie", "current_dans_horaires_agence", "current_est_heure_pointe"
    ]
    for col in enriched_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)
    df.loc[0, "current_heure_decimale"] = float(heure)
    df.loc[0, "current_jour_semaine"] = float(d.weekday())
    df.loc[0, "current_est_weekend"] = float(int(d.weekday() >= 5))
    df.loc[0, "current_est_ferie"] = float(int(_est_jour_ferie_maroc(d)))
    df.loc[0, "current_dans_horaires_agence"] = float(int(
        d.weekday() < 5 and not _est_jour_ferie_maroc(d) and 8.0 <= heure <= 16.5
    ))
    df.loc[0, "current_est_heure_pointe"] = float(int(11.0 <= heure <= 14.0))
    return df

def _predire_next_datetime(profil, type_compte: str, montant: float, base_datetime: datetime.datetime):
    if not all([model_next_date, model_next_time, profil]): return None, None
    df = _build_features_next_event_at(profil, type_compte, montant, base_datetime)

    delta_days = float(model_next_date.predict(df)[0])
    delta_days = max(0.0, delta_days)

    base_dt = max(base_datetime, datetime.datetime.now())
    candidate = (base_dt + datetime.timedelta(days=delta_days)).date()

    today = _today_maroc()
    if candidate <= today and _est_jour_ouvrable(today):
        target_date = today
    else:
        target_date = _next_jour_ouvre(candidate)

    hour_float = float(model_next_time.predict(df)[0])
    hour_raw   = int(hour_float)
    minute_raw = int((hour_float - hour_raw) * 60)

    hour   = max(8, min(hour_raw, 16))
    minute = min(minute_raw, 30) if hour == 16 else minute_raw

    return target_date.strftime("%Y-%m-%d"), f"{hour:02d}:{minute:02d}"

def _doit_venir_aujourdhui(profil: dict, probabilite: float) -> bool:
    """
    Le client est-il attendu aujourd'hui ?

    Décision fondée sur la seule propension de visite : le niveau de risque de
    départ n'entre plus ici, l'Agent 2 ne le calcule plus. Faire dépendre une
    date de visite du risque de churn mélangeait d'ailleurs deux questions
    distinctes — quand le client vient, et s'il est en train de partir.
    """
    today = _today_maroc()
    if not _est_jour_ouvrable(today):
        return False
    if probabilite >= 62.0:
        return True
    if not profil:
        return False
    nb_ops_30j = int(profil.get("nb_operations_30j", 0) or 0)
    jours_inactif = float(profil.get("jours_depuis_derniere_operation", 999) or 999)
    ratio_hors_horaires = float(profil.get("ratio_ops_hors_horaires", 0.0) or 0.0)
    return probabilite >= 58.0 and (nb_ops_30j >= 3 or jours_inactif <= 2 or ratio_hors_horaires >= 0.45)

def _predire_next_operation_future(profil, type_compte: str, montant: float):
    if not all([model_next_operation, profil]): return None
    df = _build_features_next_event(profil, type_compte, montant)
    pred_idx = int(model_next_operation.predict(df)[0])
    try: motif = encoder_next_operation.inverse_transform([pred_idx])[0]
    except: motif = str(pred_idx)
    return _format_operation_label(str(motif))

def _stats_agence_client(client_id: int) -> dict:
    """Fréquentation du guichet — matière première de l'explication."""
    defauts = {"visites_90j": 0, "jours_depuis": None, "rythme": None}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*),
                   DATEDIFF(CURDATE(), MAX(date_heure_operation)),
                   DATEDIFF(MAX(date_heure_operation), MIN(date_heure_operation))
                     / NULLIF(COUNT(*) - 1, 0)
            FROM historique_operation
            WHERE client_id = %s AND canal = %s
              AND date_heure_operation >= CURDATE() - INTERVAL 90 DAY
        """, (client_id, CANAL_AGENCE))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0]:
            return {"visites_90j": int(row[0]),
                    "jours_depuis": int(row[1]) if row[1] is not None else None,
                    "rythme": float(row[2]) if row[2] is not None else None}
    except Exception as exc:
        print(f"⚠️ Stats agence client {client_id} : {exc}")
    return defauts


def _explication_factuelle(probabilite, operation, date_prevue, plage, stats) -> str:
    """
    Explication produite par règles, sans LLM.

    Sert pour les visites lointaines, et de repli si l'appel au modèle échoue :
    une phrase factuelle vaut mieux qu'un champ vide, et elle ne peut rien
    inventer.
    """
    phrase = (f"Visite prévue le {date_prevue}"
              + (f" sur la plage {plage}" if plage else "")
              + f" pour un(e) {operation.lower()}, "
              + f"avec une propension estimée à {probabilite:.0f} %.")
    if stats["visites_90j"]:
        phrase += f" Le client a effectué {stats['visites_90j']} passage(s) en agence sur 90 jours"
        if stats["rythme"]:
            phrase += f", soit un rythme d'environ {stats['rythme']:.0f} jours"
        phrase += "."
    if stats["jours_depuis"] is not None:
        phrase += f" Dernier passage il y a {stats['jours_depuis']} jour(s)."
    return phrase


def _expliquer_prediction(client_id, profil, probabilite, operation,
                          date_prevue, plage, jours_avant_visite) -> str:
    """
    Explique POURQUOI cette visite est prédite, à destination du conseiller.

    Le LLM n'est appelé que si la visite est imminente et si les conditions
    sont réunies ; sinon on renvoie l'explication factuelle. L'agent ne
    transmet que des faits déjà calculés — il ne demande jamais au modèle
    d'estimer une date ou une probabilité.
    """
    stats = _stats_agence_client(client_id)
    factuelle = _explication_factuelle(probabilite, operation, date_prevue, plage, stats)

    if not GROQ_API_KEY or jours_avant_visite is None or jours_avant_visite > HORIZON_EXPLICATION_JOURS:
        return factuelle

    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage

        consigne = (
            "Tu expliques à un conseiller bancaire d'Attijariwafa Bank pourquoi le système "
            "attend un client en agence. Deux phrases maximum, en français.\n\n"
            "Tu n'utilises QUE les faits fournis. Tu n'inventes aucun chiffre, aucune date, "
            "aucun motif absent du dossier. Tu n'annonces ni tarif ni offre commerciale : ton "
            "rôle est d'expliquer une prévision, pas de vendre.\n"
            "Tu écris directement l'explication, sans préambule ni rappel de ces consignes."
        )
        lignes = [
            f"Segment : {profil.get('segment_metier', 'N/A')}",
            f"Visite prévue : {date_prevue}" + (f", plage {plage}" if plage else ""),
            f"Motif attendu au guichet : {operation}",
            f"Propension de visite : {probabilite:.0f} %",
            f"Passages en agence sur 90 jours : {stats['visites_90j']}"
            + (f" (rythme ≈ {stats['rythme']:.0f} jours)" if stats["rythme"] else ""),
        ]
        if stats["jours_depuis"] is not None:
            lignes.append(f"Dernier passage : il y a {stats['jours_depuis']} jour(s)")
        contexte = "\n".join(lignes)
        llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY,
                       temperature=0.2, max_tokens=180, timeout=25, max_retries=2)
        texte = llm.invoke([SystemMessage(content=consigne),
                            HumanMessage(content=contexte)]).content.strip()
        return texte or factuelle
    except Exception as exc:
        print(f"⚠️ Explication LLM indisponible pour le client {client_id} ({exc}) — repli factuel.")
        return factuelle


def _predire_motif_visite(client_id: int, date_visite) -> str:
    """
    Motif de la prochaine visite, par le modèle entraîné sur les séquences.

    La date étant déjà prédite en amont, on l'utilise comme contexte : le jour
    du mois porte les échéances de factures, le jour de semaine la cadence des
    commerçants. Retourne None si le modèle est absent ou si le client n'a pas
    assez d'historique en agence — l'appelant retombe alors sur son mode.
    """
    if _modele_op_visite is None or not date_visite:
        return None
    try:
        if isinstance(date_visite, str):
            date_visite = datetime.datetime.strptime(date_visite[:10], "%Y-%m-%d")
        elif not isinstance(date_visite, datetime.datetime):
            date_visite = datetime.datetime.combine(date_visite, datetime.time(12, 0))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT h.date_heure_operation, h.type_operation, h.montant, cl.segment_metier "
            "FROM historique_operation h JOIN client cl ON cl.id = h.client_id "
            "WHERE h.client_id = %s AND h.canal = %s "
            "ORDER BY h.date_heure_operation",
            (client_id, CANAL_AGENCE))
        lignes = cur.fetchall()
        cur.close(); conn.close()
        if not lignes:
            return None

        from collections import Counter
        historique = [(d, t) for d, t, _m, _s in lignes]
        compteurs = Counter(t for _d, t in historique)
        try:
            seg = int(_meta_op_visite["encoder_segment"].transform([lignes[-1][3] or "Particulier"])[0])
        except (ValueError, KeyError):
            seg = 0

        f = _features_visite(seg, date_visite, historique, compteurs,
                             _encodeur_op_visite, _meta_op_visite["types"])
        if f is None:
            return None
        f["montant_precedent"] = float(lignes[-1][2] or 0)
        X = pd.DataFrame([[f[c] for c in _colonnes_op_visite]], columns=_colonnes_op_visite)
        motif = _encodeur_op_visite.inverse_transform([int(_modele_op_visite.predict(X)[0])])[0]
        return _format_operation_label(str(motif)) or str(motif)
    except Exception as exc:
        print(f"⚠️ Erreur _predire_motif_visite client {client_id}: {exc}")
        return None


def _predire_next_operation_from_history(client_id: int, type_op: str, montant: float, base_dt: datetime.datetime) -> str:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Restreint au canal AGENCE : on annonce au conseiller ce que le client
        # vient faire AU GUICHET. Sans ce filtre, le mode ressortait à
        # PAIEMENT_CARTE pour tout le portefeuille — une opération qui, par
        # définition, ne se fait pas en agence.
        cursor.execute(
            """
            SELECT type_operation, COUNT(*) AS freq
            FROM historique_operation
            WHERE client_id = %s
              AND canal = %s
            GROUP BY type_operation
            ORDER BY freq DESC
            LIMIT 1
            """,
            (client_id, CANAL_AGENCE)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return _format_operation_label(row["type_operation"]) or row["type_operation"]
    except Exception as e:
        print(f"⚠️ Erreur _predire_next_operation_from_history client {client_id}: {e}")
    # Client sans aucun passage au guichet : sa dernière opération ne peut pas
    # servir de repli si elle s'est faite à distance.
    if type_op == OPERATION_AGENCE_DEFAUT:
        return _format_operation_label(type_op) or type_op
    return _format_operation_label("Retrait Guichet") or "Retrait Guichet"

def _sauvegarder_prediction_db(client_id, probabilite, operation_prevue, date_prevue,
                               explication, plage_horaire):
    """
    Enregistre la prédiction de visite et son explication.

    N'écrit ni `niveau_risque` ni `score_churn` : ces colonnes appartiennent à
    l'Agent 3. Les toucher ici écraserait son analyse à chaque batch, et deux
    agents écrivant la même donnée finissent toujours par diverger.
    """
    try:
        conn = get_db_connection(); cursor = conn.cursor()
        cursor.execute("SELECT id FROM prediction_visite WHERE client_id = %s", (client_id,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE prediction_visite "
                "SET score_probabilite_global=%s, operation_prevue=%s, date_prevue=%s, "
                "plage_horaire_prevue=%s, insight_genai=%s, date_dernier_calcul=NOW() "
                "WHERE client_id=%s",
                (probabilite, operation_prevue, date_prevue, plage_horaire, explication, client_id)
            )
        else:
            cursor.execute(
                "INSERT INTO prediction_visite "
                "(client_id, score_probabilite_global, operation_prevue, date_prevue, "
                "insight_genai, plage_horaire_prevue, strategie_prescrite, date_dernier_calcul) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
                (client_id, probabilite, operation_prevue, date_prevue,
                 explication, plage_horaire, "")
            )

        conn.commit(); cursor.close(); conn.close()
    except Exception as e: print(f"⚠️ Erreur sauvegarde DB : {e}")

def _get_derniere_operation_reelle(client_id: int) -> dict:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT type_operation, montant, date_heure_operation "
            "FROM historique_operation "
            "WHERE client_id = %s "
            "ORDER BY date_heure_operation DESC LIMIT 1",
            (client_id,)
        )
        row = cursor.fetchone()
        cursor.close(); conn.close()
        if row:
            return {
                "type_op": str(row["type_operation"]) if row["type_operation"] else "Profil Initial",
                "montant": float(row["montant"]) if row["montant"] else 0.0,
                "event_time": row["date_heure_operation"] or datetime.datetime.now(),
            }
    except Exception as e:
        print(f"⚠️  Erreur récupération dernière opération client {client_id} : {e}")
    return {"type_op": "Profil Initial", "montant": 0.0, "event_time": datetime.datetime.now()}


def calculer_predictions_pour_client(client_id: int, type_op: str = "Profil Initial", montant: float = 0.0, type_compte: str = None, event_time = None, action: str = "BATCH") -> dict:
    """
    Exécute les modèles de prédiction de visite XGBoost pour un client donné et sauvegarde en DB.
    """
    if action in ("BATCH", "BATCH_NOCTURNE") and (not type_op or type_op in ("Profil Initial", "")) and montant == 0.0:
        derniere = _get_derniere_operation_reelle(client_id)
        type_op   = derniere["type_op"]
        montant   = derniere["montant"]
        if event_time is None:
            event_time = derniere["event_time"]

    profil = _get_profil_client(client_id)
    prediction, probabilite, statut = _predire_visite(profil, type_op, montant)
    base_dt = event_time if isinstance(event_time, datetime.datetime) else datetime.datetime.now()
    type_compte = type_compte or _get_last_type_compte(client_id)

    if probabilite >= 62.0:
        date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)
    else:
        date_p, time_p = _predire_next_datetime(profil, type_compte, montant, base_dt)
        if not date_p or not time_p:
            date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)

    # Le modèle de séquence d'abord : il tient compte de la date visée et des
    # démarches récentes du client. Le mode d'agence ne sert plus que de repli
    # pour les clients trop peu vus au guichet — il renvoyait le même motif à
    # chaque passage, ce qui n'est pas une prédiction.
    op_p = _predire_motif_visite(client_id, date_p)
    if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
        op_p = _predire_next_operation_from_history(client_id, type_op, montant, base_dt)
    if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
        op_p = _predire_next_operation_future(profil, type_compte, montant)

    if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
        op_p = "Opération Bancaire"

    # Le risque de départ n'est PAS calculé ici : c'est le métier de l'Agent 3,
    # qui l'établit sur l'ensemble du portefeuille avant l'aiguillage du batch.
    # L'Agent 2 s'en tient à la prédiction de visite et à son explication.
    existing_date = None
    existing_time = None
    try:
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT date_prevue, plage_horaire_prevue FROM prediction_visite WHERE client_id = %s", (client_id,))
        row = c.fetchone()
        c.close(); conn.close()
        if row and row["date_prevue"]:
            if isinstance(row["date_prevue"], str):
                existing_date = datetime.datetime.strptime(row["date_prevue"][:10], "%Y-%m-%d").date()
            elif isinstance(row["date_prevue"], datetime.datetime):
                existing_date = row["date_prevue"].date()
            else:
                existing_date = row["date_prevue"]
            existing_time = row.get("plage_horaire_prevue")
    except Exception as e:
        print(f"⚠️ Erreur lecture existing_date pour client {client_id}: {e}")

    today_date = _today_maroc()
    last_op_date = base_dt.date() if isinstance(base_dt, datetime.datetime) else None
    a_deja_visite = bool(existing_date and last_op_date and last_op_date >= existing_date)

    if existing_date and existing_time and existing_date >= today_date and not a_deja_visite and probabilite < 62.0:
        # On conserve la date déjà annoncée au conseiller, mais sans jamais la
        # rendre telle quelle : une date stockée par une version antérieure
        # peut tomber un samedi, un dimanche ou un férié marocain. Les deux
        # moteurs de date appliquent _next_jour_ouvre ; ce chemin de reprise
        # était le seul à ne pas le faire, et laissait passer des visites
        # prévues agence fermée.
        date_retenue = existing_date if _est_jour_ouvrable(existing_date) else _next_jour_ouvre(existing_date)
        date_p, time_p = date_retenue.strftime("%Y-%m-%d"), existing_time
    else:
        doit_venir_aujourdhui = _doit_venir_aujourdhui(profil, probabilite)
        if existing_date and existing_date <= today_date and _est_jour_ouvrable(today_date) and not a_deja_visite:
            doit_venir_aujourdhui = True
        if doit_venir_aujourdhui:
            date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil, forcer_aujourdhui=True)

    # Explicabilité : l'Agent 2 justifie sa propre prédiction. Le LLM n'est
    # sollicité que si la visite est proche ; sinon la phrase est produite par
    # règles. Remplace le « Analyse IA en attente… » qui restait affiché pour
    # tous les clients que l'Agent 3 ne traitait pas.
    jours_avant = None
    try:
        jours_avant = (datetime.datetime.strptime(date_p[:10], "%Y-%m-%d").date() - today_date).days
    except Exception:
        pass

    explication = _expliquer_prediction(
        client_id, profil or {}, probabilite, op_p, date_p, time_p, jours_avant)

    _sauvegarder_prediction_db(
        client_id, probabilite, op_p, date_p, explication, time_p)

    return {
        "client_id": client_id,
        "probabilite": probabilite,
        "operation_prevue": op_p,
        "date_prevue": date_p,
        "plage_horaire": time_p,
        "explication": explication,
    }

def run_batch_predictions() -> tuple:
    print("🚀 [Agent 2] Début du calcul des prédictions (Batch)...")
    nb_ok = 0
    nb_ko = 0
    clients = None
    if USE_MCP:
        res = _call_mcp_tool("get_all_client_ids", {})
        if res and not res.get("error") and "client_ids" in res:
            clients = [{"id": cid} for cid in res["client_ids"]]
    if clients is None:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM client ORDER BY id")
            clients = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Erreur connexion DB : {e}")
            return 0, 0

    for client in clients:
        cid = client["id"]
        try:
            calculer_predictions_pour_client(cid, action="BATCH")
            nb_ok += 1
        except Exception as e:
            nb_ko += 1
            print(f"❌ Erreur prédiction client {cid} : {e}")
            
    print(f"✅ [Agent 2] Prédictions terminées. Réussites: {nb_ok}, Échecs: {nb_ko}")
    return nb_ok, nb_ko

if __name__ == "__main__":
    run_batch_predictions()
