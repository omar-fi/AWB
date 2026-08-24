"""
Entraînement Next Event (Date, Heure, Opération) avec XGBoost.
Génère 3 modèles distincts pour une prédiction granulaire.
"""

import os
import holidays
import joblib
import pandas as pd
import numpy as np
import xgboost as xgb

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "attijari_predict_db")

ENGINE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

NEXT_DATE_MODEL_FILE = "xgboost_next_date.pkl"
NEXT_TIME_MODEL_FILE = "xgboost_next_time.pkl"
NEXT_OP_MODEL_FILE = "xgboost_next_operation.pkl"

ENCODER_SEGMENT_NEXT_FILE = "encoder_segment_next.pkl"
ENCODER_TYPE_COMPTE_FILE = "encoder_type_compte.pkl"
ENCODER_NEXT_OPERATION_FILE = "encoder_next_operation.pkl"
NEXT_FEATURES_FILE = "xgboost_next_features.pkl"
FERIES_MAROC = holidays.Morocco()

ALL_OP_TYPES = [
    "RETRAIT", "VERSEMENT", "VIREMENT_EMIS", "VIREMENT_RECU",
    "PAIEMENT_FACTURE", "PAIEMENT_CARTE", "REMISE_CHEQUE",
    "Paiement TPE", "Demande de Crédit", "Retrait Guichet",
    "Versement Espèces", "Remise de Chèque", "Virement Reçu",
    "PLACEMENT", "RETRAIT_EPARGNE",
]

def _calendar_features(ts):
    dt = pd.Timestamp(ts).to_pydatetime()
    heure = dt.hour + dt.minute / 60.0
    d = dt.date()
    est_weekend = int(d.weekday() >= 5)
    est_ferie = int(d in FERIES_MAROC)
    dans_horaires = int(
        (d.weekday() < 5 and not est_ferie and 8.0 <= heure <= 16.5)
    )
    return {
        "current_heure_decimale": heure,
        "current_jour_semaine": d.weekday(),
        "current_est_weekend": est_weekend,
        "current_est_ferie": est_ferie,
        "current_dans_horaires_agence": dans_horaires,
        "current_est_heure_pointe": int(11.0 <= heure <= 14.0),
    }

def _extraire_dataset_next_event(engine):
    query_ops = """
        SELECT
            h.client_id,
            cl.segment_metier,
            COALESCE(co.type_compte, 'AUCUN') AS type_compte,
            h.date_heure_operation,
            h.type_operation,
            h.montant
        FROM historique_operation h
        JOIN client cl ON h.client_id = cl.id
        LEFT JOIN compte co ON h.compte_id = co.id
        ORDER BY h.client_id, h.date_heure_operation
    """
    df_ops = pd.read_sql(query_ops, con=engine)
    
    df_client = pd.read_sql(
        """
        SELECT
            cl.id AS client_id,
            cl.segment_metier,
            COALESCE(SUM(co.solde), 0) AS solde_actuel,
            MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_compte_epargne,
            AVG(co.solde) AS solde_moyen_compte
        FROM client cl
        LEFT JOIN compte co ON cl.id = co.client_id
        GROUP BY cl.id, cl.segment_metier
        """,
        con=engine
    )

    df_ops["date_heure_operation"] = pd.to_datetime(df_ops["date_heure_operation"], errors="coerce")
    df_ops = df_ops.dropna(subset=["date_heure_operation"])
    return df_ops, df_client

def train_next_event():
    max_samples = int(os.getenv("NEXT_EVENT_MAX_SAMPLES", "50000"))
    max_pairs_per_client = int(os.getenv("NEXT_EVENT_MAX_PAIRS_PER_CLIENT", "2000"))

    engine = create_engine(ENGINE_URL)
    df_ops, df_client = _extraire_dataset_next_event(engine)

    if df_ops.empty:
        raise RuntimeError("Dataset vide.")

    print(f"✅ Ops: {len(df_ops)}, Clients: {len(df_client)}")

    enc_segment = LabelEncoder()
    enc_type_compte = LabelEncoder()
    enc_next_op = LabelEncoder()

    enc_segment.fit(df_client["segment_metier"].fillna("Particulier").astype(str))
    enc_type_compte.fit(df_ops["type_compte"].fillna("AUCUN").astype(str))
    enc_next_op.fit(df_ops["type_operation"].fillna("INCONNU").astype(str))

    client_map = df_client.set_index("client_id").to_dict(orient="index")

    feature_cols = [
        "seg_enc", "type_compte_enc", "nombre_operations", "montant_total",
        "montant_moyen", "moy_retrait", "nb_ops_30j", "ratio_solde_habitude",
        "has_compte_epargne", "solde_total", "solde_moyen_compte", "montant_courant"
    ] + ALL_OP_TYPES + [
        "current_heure_decimale", "current_jour_semaine", "current_est_weekend",
        "current_est_ferie", "current_dans_horaires_agence", "current_est_heure_pointe",
    ]

    X_rows, y_delta_days, y_hours, y_ops = [], [], [], []

    for client_id, ops in df_ops.groupby("client_id"):
        profile = client_map.get(client_id)
        if not profile: continue
        
        ops = ops.sort_values("date_heure_operation").reset_index(drop=True)
        if len(ops) < 2: continue

        start_i = max(0, len(ops) - 1 - max_pairs_per_client)
        seg_enc = int(enc_segment.transform([str(profile.get("segment_metier", "Particulier"))])[0])
        
        counts = {op: 0 for op in ALL_OP_TYPES}
        nb_ops, total_m = 0, 0.0

        for i in range(len(ops) - 1):
            current, nxt = ops.iloc[i], ops.iloc[i+1]
            diff = nxt["date_heure_operation"] - current["date_heure_operation"]
            d_days = diff.total_seconds() / (24 * 3600)
            
            if i < start_i:
                nb_ops += 1
                total_m += float(current["montant"] or 0)
                if str(current["type_operation"]) in counts: counts[str(current["type_operation"])] += 1
                continue

            if len(X_rows) >= max_samples: break
            
            nb_ops += 1
            total_m += float(current["montant"] or 0)
            if str(current["type_operation"]) in counts: counts[str(current["type_operation"])] += 1

            type_compte_enc = int(enc_type_compte.transform([str(current["type_compte"])])[0])
            
            feat = {
                "seg_enc": seg_enc, "type_compte_enc": type_compte_enc,
                "nombre_operations": nb_ops, "montant_total": total_m,
                "montant_moyen": total_m / nb_ops, "montant_courant": float(current["montant"] or 0),
                "has_compte_epargne": int(profile.get("has_compte_epargne", 0)),
                "solde_total": float(profile.get("solde_actuel", 0)),
                "solde_moyen_compte": float(profile.get("solde_moyen_compte", 0)),
            }
            feat["nb_ops_30j"] = nb_ops
            feat["moy_retrait"] = total_m / nb_ops
            feat["ratio_solde_habitude"] = feat["solde_total"] / (feat["moy_retrait"] + 1)
            
            for op in ALL_OP_TYPES: feat[op] = counts[op]
            feat.update(_calendar_features(current["date_heure_operation"]))

            X_rows.append([feat[c] for c in feature_cols])
            y_delta_days.append(max(0, d_days))
            y_hours.append(nxt["date_heure_operation"].hour + nxt["date_heure_operation"].minute / 60.0)
            y_ops.append(str(nxt["type_operation"]))

    X = pd.DataFrame(X_rows, columns=feature_cols)
    y_d = np.array(y_delta_days)
    y_h = np.array(y_hours)
    y_o = enc_next_op.transform(y_ops)

    print(f"🚀 Training 3 XGBoost models on {len(X)} samples...")
    
    model_date = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_date.fit(X, y_d)
    joblib.dump(model_date, NEXT_DATE_MODEL_FILE)

    model_hour = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_hour.fit(X, y_h)
    joblib.dump(model_hour, NEXT_TIME_MODEL_FILE)

    model_op = xgb.XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_op.fit(X, y_o)
    joblib.dump(model_op, NEXT_OP_MODEL_FILE)

    joblib.dump(enc_segment, ENCODER_SEGMENT_NEXT_FILE)
    joblib.dump(enc_type_compte, ENCODER_TYPE_COMPTE_FILE)
    joblib.dump(enc_next_op, ENCODER_NEXT_OPERATION_FILE)
    joblib.dump(feature_cols, NEXT_FEATURES_FILE)

    print("✅ All 3 XGBoost models, feature schema and encoders saved.")

if __name__ == "__main__":
    train_next_event()
