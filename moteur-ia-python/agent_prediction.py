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

# --- CONFIGURATION DB ---
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- CHARGEMENT DES MODÈLES ---
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
    if date.weekday() == 5: return False          # Samedi : fermé
    if date.weekday() == 6: return False          # Dimanche : fermé
    if _est_jour_ferie_maroc(date): return False   # Férié : fermé
    return True                                    # Lun–Ven : ouvert

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

    raw_proba = float(model_visite.predict_proba(df)[0][1])
    pred_label = int(model_visite.predict(df)[0])

    raw_pct = raw_proba * 100.0
    probabilite_finale = 50.0 + (raw_pct - 50.0) * 0.45
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

    probabilite_finale = float(np.clip(probabilite_finale + ajustement, 12.0, 93.0))

    if probabilite_finale >= 75:
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

def _predire_date_visite(probabilite, base_datetime=None, profil=None):
    today = _today_maroc()
    seed = int((probabilite % 1.0) * 100) if probabilite % 1.0 > 0 else int(probabilite)

    if probabilite >= 62:
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

def _doit_venir_aujourdhui(profil: dict, probabilite: float, niveau_risque: str = "FAIBLE") -> bool:
    today = _today_maroc()
    if not _est_jour_ouvrable(today):
        return False
    if probabilite >= 62.0:
        return True
    if probabilite >= 55.0 and niveau_risque in ("CRITIQUE", "ÉLEVÉ", "ALERTE"):
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

def _predire_next_operation_from_history(client_id: int, type_op: str, montant: float, base_dt: datetime.datetime) -> str:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT type_operation, COUNT(*) AS freq
            FROM historique_operation
            WHERE client_id = %s
            GROUP BY type_operation
            ORDER BY freq DESC
            LIMIT 1
            """,
            (client_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return _format_operation_label(row["type_operation"]) or row["type_operation"]
    except Exception as e:
        print(f"⚠️ Erreur _predire_next_operation_from_history client {client_id}: {e}")
    return _format_operation_label(type_op) or type_op or "Opération Bancaire"

def _sauvegarder_prediction_db(client_id, probabilite, operation_prevue, date_prevue, explication, plage_horaire, strategie="", niveau_risque="FAIBLE"):
    try:
        conn = get_db_connection(); cursor = conn.cursor()
        cursor.execute("SELECT id FROM prediction_visite WHERE client_id = %s", (client_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE prediction_visite SET score_probabilite_global=%s, operation_prevue=%s, date_prevue=%s, insight_genai=%s, plage_horaire_prevue=%s, strategie_prescrite=%s, niveau_risque=%s, date_dernier_calcul=NOW() WHERE client_id=%s", (probabilite, operation_prevue, date_prevue, explication, plage_horaire, strategie, niveau_risque, client_id))
        else:
            cursor.execute("INSERT INTO prediction_visite (client_id, score_probabilite_global, operation_prevue, date_prevue, insight_genai, plage_horaire_prevue, strategie_prescrite, niveau_risque, date_dernier_calcul) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())", (client_id, probabilite, operation_prevue, date_prevue, explication, plage_horaire, strategie, niveau_risque))
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

    op_p = _predire_next_operation_from_history(client_id, type_op, montant, base_dt)
    if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
        op_p = _predire_next_operation_future(profil, type_compte, montant)

    if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
        op_p = "Opération Bancaire"

    # Calcul du niveau de risque basique pour décider s'il doit venir aujourd'hui
    from analysis_engine import calculer_niveau_risque
    solde_actuel  = profil.get("solde_actuel", 0.0)       if profil else 0.0
    solde_moyen   = profil.get("solde_moyen_compte", 0.0) if profil else 0.0
    nb_ops_30j    = profil.get("nb_operations_30j", 0)    if profil else 0
    tot_ops       = profil.get("nombre_operations", 0)    if profil else 0
    moy_retraits  = profil.get("moyenne_retraits_30j", 0.0) if profil else 0.0

    score_churn = 0.0
    if solde_moyen > 1000:
        ratio_solde = solde_actuel / solde_moyen
        if ratio_solde < 0.4:   score_churn += 0.6
        elif ratio_solde < 0.7: score_churn += 0.3
    if solde_actuel > 0 and moy_retraits > (solde_actuel * 0.4):
        score_churn += 0.4
    if tot_ops > 20 and nb_ops_30j == 0:
        score_churn += 0.5
    score_churn = min(score_churn, 0.95)
    niveau_risque = calculer_niveau_risque(score_churn)

    if _doit_venir_aujourdhui(profil, probabilite, niveau_risque):
        date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)

    insight_attente = "Analyse IA en attente..."
    strategie_attente = ""

    _sauvegarder_prediction_db(
        client_id, probabilite, op_p, date_p, 
        insight_attente, time_p, strategie_attente, niveau_risque
    )
    
    return {
        "client_id": client_id,
        "probabilite": probabilite,
        "operation_prevue": op_p,
        "date_prevue": date_p,
        "plage_horaire": time_p,
        "niveau_risque": niveau_risque
    }

def run_batch_predictions() -> tuple:
    print("🚀 [Agent 2] Début du calcul des prédictions (Batch)...")
    nb_ok = 0
    nb_ko = 0
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
