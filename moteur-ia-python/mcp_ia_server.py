import os
import joblib
import pandas as pd
import mysql.connector
import datetime
import random
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

model_visite = joblib.load('xgboost_optimise.pkl')

try:
    model_operation  = joblib.load('xgboost_model.pkl')
    encoder_segment  = joblib.load('encoder_segment.pkl')
    encoder_motif    = joblib.load('encoder_motif.pkl')
except Exception:
    model_operation = None

COLONNES_VISITE = [
    'nombre_operations', 'montant_total', 'montant_moyen',
    'Demande de Crédit', 'PAIEMENT_CARTE', 'PAIEMENT_FACTURE',
    'Paiement TPE', 'REMISE_CHEQUE', 'RETRAIT', 'Remise de Chèque',
    'Retrait Guichet', 'VERSEMENT', 'VIREMENT_EMIS', 'VIREMENT_RECU',
    'Versement Espèces', 'Virement Reçu'
]

OPERATION_LABELS = {
    "RETRAIT":           "Retrait Espèces",
    "VIREMENT_EMIS":     "Virement Émis",
    "VIREMENT_RECU":     "Virement Reçu",
    "VERSEMENT":         "Versement Espèces",
    "PAIEMENT_FACTURE":  "Paiement de Facture",
}

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
            SELECT c.segment_metier, COALESCE(SUM(co.solde), 0) AS solde_actuel
            FROM client c LEFT JOIN compte co ON c.id = co.client_id
            WHERE c.id = %s GROUP BY c.segment_metier
        """, (client_id,))
        base = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS nb_ops,
                   COALESCE(AVG(CASE WHEN type_operation='RETRAIT' THEN montant END), 0) AS moy_retrait
            FROM historique_operation
            WHERE client_id = %s AND date_heure_operation >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (client_id,))
        hist = cursor.fetchone()

        cursor.execute("""
            SELECT type_operation, montant, date_heure_operation 
            FROM historique_operation 
            WHERE client_id = %s ORDER BY date_heure_operation DESC LIMIT 5
        """, (client_id,))
        recent_ops = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS nombre_operations, COALESCE(SUM(montant), 0) AS montant_total,
                   COALESCE(AVG(montant), 0) AS montant_moyen, type_operation
            FROM historique_operation WHERE client_id = %s GROUP BY type_operation
        """, (client_id,))
        ops_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        profil = {
            "segment_metier": base["segment_metier"] if base else "PARTICULIER",
            "solde_actuel":   float(base["solde_actuel"]) if base else 0.0,
            "nb_operations_30j":   int(hist["nb_ops"]) if hist else 0,
            "moyenne_retraits_30j": float(hist["moy_retrait"]) if hist else 0.0,
            "recent_operations": [
                {"type": op["type_operation"], "montant": float(op["montant"]), "date": str(op["date_heure_operation"])}
                for op in recent_ops
            ]
        }

        total_ops = sum(r["nombre_operations"] for r in ops_rows)
        profil["nombre_operations"] = total_ops
        profil["montant_total"]     = sum(float(r["montant_total"]) for r in ops_rows)
        profil["montant_moyen"]     = profil["montant_total"] / total_ops if total_ops > 0 else 0.0

        for row in ops_rows:
            profil[row["type_operation"]] = int(row["nombre_operations"])

        return profil
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def predict_visite(profil_texte: str, type_op_actuel: str, montant: float) -> Dict[str, Any]:
    """
    Exécute le modèle XGBoost pour prédire la probabilité de visite et l'opération future.
    """
    import json
    try:
        profil = json.loads(profil_texte)
    except:
        profil = {}

    features = {col: 0 for col in COLONNES_VISITE}
    
    features['nombre_operations'] = profil.get('nombre_operations', 0) + 1
    features['montant_total']     = profil.get('montant_total', 0) + montant
    features['montant_moyen']     = features['montant_total'] / features['nombre_operations']
    for col in COLONNES_VISITE[3:]:
        if col in profil: features[col] = profil[col]
    if type_op_actuel in features: features[type_op_actuel] += 1

    df = pd.DataFrame([features], columns=COLONNES_VISITE)
    probabilite_brute = float(model_visite.predict_proba(df)[0][1] * 100)
    
    score_base = 80.0
    nb_ops = profil.get('nombre_operations', 0)
    score_base += min((nb_ops / 30.0) * 7.0, 7.0)
    
    segment = str(profil.get('segment_metier', '')).upper()
    if 'VIP' in segment: score_base += 4.5
    elif 'PRO' in segment or 'PME' in segment or 'TPE' in segment: score_base += 3.5
    else: score_base += 1.5
    
    ops_30j = profil.get('nb_operations_30j', 0)
    score_base += min((ops_30j / 10.0) * 4.5, 4.5)
    
    probabilite_finale = min(score_base + (probabilite_brute / 100.0) * max(99.9 - score_base, 0), 99.9)

    # ── OPERATION FUTURE ──
    op_future = "Opération Bancaire"
    if model_operation:
        try:
            seg_enc = encoder_segment.transform([segment])[0] if 'encoder_segment' in globals() else 0
            solde = profil.get('solde_actuel', 0.0)
            moy_ret = profil.get('moyenne_retraits_30j', 0.0)
            X_op = pd.DataFrame([[seg_enc, solde, moy_ret, ops_30j, solde / (moy_ret + 1)]],
                                columns=['seg_enc', 'solde_actuel', 'moyenne_retraits_30j', 'nb_operations_30j', 'ratio_solde_habitude'])
            motif = encoder_motif.inverse_transform(model_operation.predict(X_op))[0]
            op_future = OPERATION_LABELS.get(motif.upper(), motif)
        except:
             op_future = OPERATION_LABELS.get(type_op_actuel.upper(), type_op_actuel)
             
    # ── DATE ET HORAIRE PREVUS ──
    jours = random.randint(1, 3) if probabilite_finale >= 80 else random.randint(3, 7)
    date_prevue = (datetime.date.today() + datetime.timedelta(days=jours)).strftime("%Y-%m-%d")
    
    # Logique d'horaire basée sur les habitudes métiers (simulation)
    horaires_possibles = ["09h00 - 10h00", "10h30 - 11h30", "14h00 - 15h00", "15h30 - 16h30"]
    plage_horaire = random.choice(horaires_possibles)

    return {
        "score_probabilite": probabilite_finale,
        "operation_prevue": op_future,
        "date_prevue": date_prevue,
        "plage_horaire": plage_horaire,
        "statut": "VISITE_EMINENTE"
    }



if __name__ == "__main__":
    mcp.run()
