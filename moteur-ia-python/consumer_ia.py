import json
import joblib
import pandas as pd
import mysql.connector
import os
import requests
import datetime
import random
import math
import numpy as np
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

print("🚀 Initialisation du Microservice IA Hybride (Full Batch MySQL)...")

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

# ── Chargement des modèles XGBoost ────────────────────────────────────────────
try:
    model_visite = joblib.load('xgboost_optimise.pkl')
    print("🧠 Modèle XGBoost (visite) chargé avec succès !")
except Exception as e:
    print(f"❌ Impossible de charger xgboost_optimise.pkl : {e}")
    exit()

try:
    model_operation  = joblib.load('xgboost_model.pkl')
    encoder_segment  = joblib.load('encoder_segment.pkl')
    encoder_motif    = joblib.load('encoder_motif.pkl')
    print("🧠 Modèle XGBoost (operation) chargé avec succès !")
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
    print("🧠 Modèles Next Event chargés avec succès !")
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
    print(f"🧩 Features visite enrichies chargées ({len(COLONNES_VISITE)} colonnes).")
except Exception:
    # Compatibilité avec les anciens modèles XGBoost entraînés sur 24 colonnes.
    COLONNES_VISITE = COLONNES_VISITE_ENRICHIES if getattr(model_visite, "n_features_in_", 24) == len(COLONNES_VISITE_ENRICHIES) else COLONNES_VISITE

ALL_OP_TYPES = [
    "RETRAIT", "VERSEMENT", "VIREMENT_EMIS", "VIREMENT_RECU",
    "PAIEMENT_FACTURE", "PAIEMENT_CARTE", "REMISE_CHEQUE",
    "Paiement TPE", "Demande de Crédit", "Retrait Guichet",
    "Versement Espèces", "Remise de Chèque", "Virement Reçu",
    "PLACEMENT", "RETRAIT_EPARGNE"
]

NEXT_FEATURE_COLS = (
    [
        "seg_enc", "type_compte_enc", "nombre_operations", "montant_total",
        "montant_moyen", "moy_retrait", "nb_ops_30j", "ratio_solde_habitude",
        "has_compte_epargne", "solde_total", "solde_moyen_compte", "montant_courant",
    ] + ALL_OP_TYPES
)

NEXT_FEATURE_COLS_ENRICHIES = NEXT_FEATURE_COLS + [
    "current_heure_decimale", "current_jour_semaine", "current_est_weekend",
    "current_est_ferie", "current_dans_horaires_agence", "current_est_heure_pointe",
]

try:
    NEXT_FEATURE_COLS = joblib.load('xgboost_next_features.pkl')
    print(f"🧩 Features next-event enrichies chargées ({len(NEXT_FEATURE_COLS)} colonnes).")
except Exception:
    if 'model_next_date' in globals() and getattr(model_next_date, "n_features_in_", len(NEXT_FEATURE_COLS)) == len(NEXT_FEATURE_COLS_ENRICHIES):
        NEXT_FEATURE_COLS = NEXT_FEATURE_COLS_ENRICHIES

def _format_operation_label(motif: str) -> str:
    if motif is None: return motif
    return OPERATION_LABELS.get(motif) or OPERATION_LABELS.get(str(motif).upper()) or motif

import holidays
_FERIES_MAROC = holidays.Morocco()

def _today_maroc() -> datetime.date:
    """
    Retourne la date du jour côté Maroc (UTC+1, fixe depuis 2019).
    Indispensable pour que le batch nocturne (00h00 Maroc = 23h00 UTC)
    stocke la bonne date (aujourd'hui Maroc, pas hier UTC).
    """
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
    """
    Retourne True si la banque est ouverte ce jour-là (Maroc AWB).
    • Lundi–Vendredi (weekday 0–4) : ouvert 08h00–16h30
    • Samedi (weekday 5)             : fermé
    • Dimanche (weekday 6)           : fermé
    • Jours fériés marocains          : fermé
    """
    if date.weekday() == 5: return False          # Samedi : fermé
    if date.weekday() == 6: return False          # Dimanche : fermé
    if _est_jour_ferie_maroc(date): return False   # Férié : fermé
    return True                                    # Lun–Ven : ouvert

def _next_jour_ouvre(date: datetime.date) -> datetime.date:
    while not _est_jour_ouvrable(date):
        date += datetime.timedelta(days=1)
    return date

def _prev_jour_ouvre(date: datetime.date) -> datetime.date:
    while not _est_jour_ouvrable(date):
        date -= datetime.timedelta(days=1)
    return date

def _fenetre_calendaire():
    today = _today_maroc()
    # La fenêtre commence AUJOURD'HUI si la banque est ouverte, sinon le prochain jour ouvrable
    min_date = today if _est_jour_ouvrable(today) else _next_jour_ouvre(today)
    if today.month == 12:
        next_month_year, next_month_month = today.year + 1, 1
    else:
        next_month_year, next_month_month = today.year, today.month + 1
    if next_month_month == 12:
        last_day = datetime.date(next_month_year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(next_month_year, next_month_month + 1, 1) - datetime.timedelta(days=1)
    max_date = _prev_jour_ouvre(last_day)
    return min_date, max_date

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

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
        # Nombre réel d'opérations sur les 30 derniers jours
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
    """
    Prédit la probabilité de visite basée sur le profil réel du client.
    Retourne le score honnête du modèle XGBoost sans forçage artificiel.
    Un ajustement métier léger est appliqué pour pondérer selon le segment
    et l'historique, mais sans imposer un plancher arbitraire.
    """
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

    # Calibration pour éviter les scores collés à 99% pour presque tout le monde.
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

    # ── Statut lisible selon le seuil de confiance ────────────────────────────
    if probabilite_finale >= 75:
        statut = "VISITE_PROBABLE"
    elif probabilite_finale >= 55:
        statut = "VISITE_INCERTAINE"
    else:
        statut = "VISITE_PEU_PROBABLE"

    return pred_label, probabilite_finale, statut

# ── Plages horaires bancaires AWB (Mohamed V / Maroc) ────────────────────────
# Lundi–Vendredi : 08h00–16h30 │ Samedi : Fermé │ Dimanche : Fermé
_HEURE_OUVERTURE_SEMAINE = 8
_HEURE_FERMETURE_SEMAINE = 16   # la dernière demie-heure clôt à 16:30

# Créneaux horaires d'affluence : (heure, minute, label)
# Chaque créneau est pondéré selon la probabilité de visite.
_CRENEAUX_HAUTE_FREQUENTATION  = [(9, 0), (9, 30), (10, 0), (10, 30), (11, 0), (11, 30)]
_CRENEAUX_NORMALE_FREQUENTATION = [(8, 30), (13, 0), (13, 30), (14, 0), (14, 30), (15, 0)]
_CRENEAUX_BASSE_FREQUENTATION   = [(8, 0), (15, 30), (16, 0), (16, 30)]
_CRENEAUX_SAMEDI                 = [(8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0), (11, 30), (12, 0), (12, 30)]


def _creneaux_valides_pour_date(date: datetime.date) -> list:
    """Retourne les créneaux (heure, minute) valides selon le jour de la semaine."""
    if date.weekday() == 5:   # Samedi fermé
        return [(9, 0)]
    elif date.weekday() == 6: # Dimanche — ne devrait jamais arriver (jour non ouvrable)
        return [(9, 0)]
    else:                     # Lundi–Vendredi
        return _CRENEAUX_HAUTE_FREQUENTATION + _CRENEAUX_NORMALE_FREQUENTATION


def _choisir_creneau(probabilite: float, date: datetime.date, profil: dict | None = None) -> tuple:
    """
    Choisit un créneau horaire déterministe (sans hasard) selon :
      - le jour de la semaine
      - la probabilité de visite (forte prob → heure de pointe)

    Règles AWB :
      Probabilité >= 75% → créneau de haute fréquentation (9h–12h)
      Probabilité >= 50% → créneau normal (8h30, 13h–15h)
      Probabilité <  50% → créneau bas (ouverture/fermeture)
    """
    if probabilite >= 75:
        creneaux = _CRENEAUX_HAUTE_FREQUENTATION
    elif probabilite >= 50:
        creneaux = _CRENEAUX_HAUTE_FREQUENTATION + _CRENEAUX_NORMALE_FREQUENTATION
    else:
        creneaux = _CRENEAUX_NORMALE_FREQUENTATION + _CRENEAUX_BASSE_FREQUENTATION

    # Sélection déterministe : on indexe par probabilité dans la liste de créneaux
    # → même probabilité = même créneau (reproductible, sans random)
    seed_client = 0
    if profil:
        seed_client = int(profil.get("client_id", 0) or 0)
        if seed_client == 0:
            seed_client = int(profil.get("nombre_operations", 0) or 0)
    idx = (int(probabilite * 10) + seed_client + date.day) % len(creneaux)
    return creneaux[idx]


def _predire_date_visite(probabilite, base_datetime=None, profil=None):
    """
    Prédit la date et l'heure de visite de façon DÉTERMINISTE.

    Règle métier AWB basée sur le score de probabilité :
      Prob >= 75% → visite AUJOURD'HUI (si jour ouvrable) sinon prochain jour ouvrable
      Prob >= 60% → visite dans 1 à 3 jours ouvrables
      Prob >= 50% → visite dans 4 à 10 jours ouvrables
      Prob <  50% → visite dans 11 à 25 jours ouvrables

    L'heure respecte les horaires bancaires AWB :
      Lundi–Vendredi : 08h00–16h30
      Samedi         : fermé
      Dimanche       : Fermé (jamais sélectionné)
    """
    today = _today_maroc()  # Date Maroc (UTC+1) pour cohérence avec le batch nocturne

    # ── Sélection déterministe du décalage en jours ouvrables ─────────────────
    # Déterministe : on utilise la partie décimale de la probabilité comme seed
    # pour choisir dans la plage → même score = même date (reproductible)
    seed = int((probabilite % 1.0) * 100) if probabilite % 1.0 > 0 else int(probabilite)

    if probabilite >= 62:
        # Haute probabilité → le client est attendu AUJOURD'HUI si l'agence est ouverte.
        if _est_jour_ouvrable(today):
            target_date = today          # Aujourd'hui !
        else:
            target_date = _next_jour_ouvre(today + datetime.timedelta(days=1))
    elif probabilite >= 55:
        # Probabilité élevée → dans 1 à 3 jours ouvrables
        decalage = (seed % 3) + 1        # 1, 2 ou 3
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)
    elif probabilite >= 45:
        # Probabilité moyenne → dans 4 à 10 jours ouvrables
        decalage = (seed % 7) + 4        # 4 à 10
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)
    else:
        # Probabilité basse → dans 11 à 25 jours ouvrables
        decalage = (seed % 15) + 11      # 11 à 25
        candidate = today + datetime.timedelta(days=decalage)
        target_date = _next_jour_ouvre(candidate)

    # ── Créneau horaire déterministe respectant les horaires bancaires ─────────
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
    # Cast colonnes enrichies en float64 pour éviter le FutureWarning pandas
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
    """
    Prédit la prochaine date/heure de visite via les modèles XGBoost next-event.
    Respecte intégralement les horaires et jours ouvrables AWB Maroc.
    """
    if not all([model_next_date, model_next_time, profil]): return None, None
    df = _build_features_next_event_at(profil, type_compte, montant, base_datetime)

    # ── Prédiction du nombre de jours jusqu'à la prochaine visite ─────────────
    delta_days = float(model_next_date.predict(df)[0])
    delta_days = max(0.0, delta_days)   # 0.0 = aujourd'hui autorisé si modèle le prédit

    base_dt = max(base_datetime, datetime.datetime.now())
    candidate = (base_dt + datetime.timedelta(days=delta_days)).date()

    # ── Forcer un jour ouvrable (exclut weekends + jours fériés Maroc) ────────
    # Si candidate est aujourd'hui et que c'est ouvrable, on garde aujourd'hui
    today = _today_maroc()  # Date Maroc (UTC+1)
    if candidate <= today and _est_jour_ouvrable(today):
        target_date = today
    else:
        target_date = _next_jour_ouvre(candidate)

    # ── Prédiction de l'heure (format décimal, ex: 10.5 = 10h30) ─────────────
    hour_float = float(model_next_time.predict(df)[0])
    hour_raw   = int(hour_float)
    minute_raw = int((hour_float - hour_raw) * 60)

    # ── Application des contraintes horaires AWB ──────────────────────────────
    hour   = max(8, min(hour_raw, 16))
    minute = min(minute_raw, 30) if hour == 16 else minute_raw

    return target_date.strftime("%Y-%m-%d"), f"{hour:02d}:{minute:02d}"


def _doit_venir_aujourdhui(profil: dict, probabilite: float, niveau_risque: str = "FAIBLE") -> bool:
    """
    Décide explicitement si un client doit être classé dans les visites d'aujourd'hui.
    XGBoost donne le score, puis on applique des signaux comportementaux simples
    pour éviter que le modèle next-event repousse tous les clients à demain.

    Seuils recalibrés sur la distribution réelle des scores (12–66%) :
      ≥ 62%          → prédit aujourd'hui inconditionnellement
      ≥ 55% + risque → priorité urgente (CRITIQUE/ALERTE)
      ≥ 58% + signal → activité récente / ratio hors-horaires
    """
    today = _today_maroc()  # Date Maroc (UTC+1)
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
    """
    Détermine l'opération la plus probable pour le prochain passage du client
    en se basant sur son historique réel (opération la plus fréquente).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Opération la plus fréquente dans l'historique (toutes périodes)
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
    # Dernier recours : l'opération actuelle
    return _format_operation_label(type_op) or type_op or "Opération Bancaire"


def _generer_strategie_comportementale(
    profil: dict,
    niveau_risque: str,
    probabilite: float,
    operation_prevue: str,
    date_prevue: str,
    plage_horaire: str,
) -> str:
    """
    Génère une stratégie de satisfaction/rétention sans dépendre du LLM.
    Elle exploite le comportement bancaire réel : activité récente, solde,
    retraits, comptes, opérations hors horaires, fériés/week-end et segment.
    """
    if not profil:
        return (
            f"Préparer un accueil personnalisé le {date_prevue} à {plage_horaire}, "
            f"vérifier le besoin lié à {operation_prevue} et mettre à jour le dossier client."
        )

    segment = str(profil.get("segment_metier", "Standard")).upper()
    solde = float(profil.get("solde_actuel", 0.0) or 0.0)
    solde_moyen = float(profil.get("solde_moyen_compte", 0.0) or 0.0)
    nb_ops = int(profil.get("nombre_operations", 0) or 0)
    nb_ops_30j = int(profil.get("nb_operations_30j", 0) or 0)
    moy_retraits = float(profil.get("moyenne_retraits_30j", 0.0) or 0.0)
    has_epargne = bool(profil.get("has_compte_epargne", 0))
    ratio_hors_horaires = float(profil.get("ratio_ops_hors_horaires", 0.0) or 0.0)
    ratio_weekend = float(profil.get("ratio_ops_weekend", 0.0) or 0.0)
    jours_inactif = float(profil.get("jours_depuis_derniere_operation", 999) or 999)

    actions = []

    if niveau_risque in ("CRITIQUE", "ÉLEVÉ"):
        actions.append("contacter le client avant sa visite pour comprendre le motif d'insatisfaction")
        actions.append("prévoir un entretien de rétention avec un conseiller senior ou le directeur d'agence")
    elif niveau_risque in ("ALERTE", "SOUS SURVEILLANCE"):
        actions.append("préparer un entretien de fidélisation et vérifier les irritants récents")
    else:
        actions.append("organiser un accueil de courtoisie et valoriser la relation avec l'agence")

    if solde_moyen > 1000 and solde < solde_moyen * 0.6:
        actions.append("analyser la baisse du solde et proposer une solution de sécurisation des flux")
    if solde > 50000 and not has_epargne:
        actions.append("proposer une solution d'épargne ou de placement adaptée au profil")
    if moy_retraits > 0 and solde > 0 and moy_retraits > solde * 0.35:
        actions.append("discuter des retraits importants et proposer une alternative plus sécurisée")
    if nb_ops > 20 and nb_ops_30j == 0:
        actions.append("réactiver le client avec une offre de retour et une vérification de satisfaction")
    if ratio_hors_horaires >= 0.35 or ratio_weekend >= 0.25:
        actions.append("proposer un accompagnement digital et un rendez-vous sur un créneau plus confortable")
    if any(x in segment for x in ["PRO", "PME", "TPE", "PROFESSIONNEL"]):
        actions.append("étudier un besoin de trésorerie, TPE, leasing ou optimisation des encaissements")
    elif "VIP" in segment:
        actions.append("préparer une offre premium et un traitement prioritaire en agence")
    elif "ETUDIANT" in segment or "JEUNE" in segment:
        actions.append("proposer un pack jeune, frais réduits et accompagnement budget")

    actions_uniques = []
    for action in actions:
        if action not in actions_uniques:
            actions_uniques.append(action)

    return (
        f"Pour éviter la perte du client et améliorer sa satisfaction : "
        f"{'; '.join(actions_uniques[:4])}. "
        f"À préparer pour {operation_prevue} le {date_prevue} à {plage_horaire} "
        f"(score visite {probabilite:.1f}%)."
    )


def _generer_insight_llm(client_id, type_op, montant, probabilite, statut, operation_prevue, date_prevue, plage_horaire, profil=None, niveau_risque="FAIBLE"):
    """
    Génère un message d'explication de l'Agent IA basé sur les données réelles
    du client. Si Groq est indisponible, un fallback factuel est utilisé.
    """
    import time

    # ── FALLBACK SANS CLÉ API ────────────────────────────────────────────────
    if not GROQ_API_KEY:
        if profil:
            nb_ops = profil.get('nombre_operations', 0)
            ops_30j = profil.get('nb_operations_30j', 0)
            solde = profil.get('solde_actuel', 0)
            segment = profil.get('segment_metier', 'Particulier')
            strategie = _generer_strategie_comportementale(
                profil, niveau_risque, probabilite, operation_prevue, date_prevue, plage_horaire
            )
            return (
                f"Analyse de l'Agent : Basé sur {nb_ops} opérations historiques ({ops_30j} ce mois) "
                f"et un solde de {solde:.0f} MAD ({segment}), le modèle prédit une visite "
                f"pour '{operation_prevue}' le {date_prevue} à {plage_horaire} "
                f"avec une fiabilité de {probabilite:.1f}%. Stratégie : {strategie}"
            )
        return f"Analyse de l'Agent : Prédiction '{operation_prevue}' le {date_prevue} ({probabilite:.1f}%)."

    # ── PACING : On espace les appels pour respecter les limites RPM de Groq ─
    time.sleep(1.2)

    try:
        # ── CONTEXTE FACTUEL COMPLET issu du profil client réel ─────────────
        segment = "Particulier"
        if profil:
            nb_ops  = profil.get('nombre_operations', 0)
            solde   = profil.get('solde_actuel', 0)
            segment = profil.get('segment_metier', 'Particulier')
            ops_30j = profil.get('nb_operations_30j', 0)
            moy_ret = profil.get('moyenne_retraits_30j', 0)
            montant_moyen = profil.get('montant_moyen', 0)
            has_epargne = profil.get('has_compte_epargne', 0)

            # On identifie l'opération la plus fréquente dans l'historique
            op_types = ALL_OP_TYPES
            op_counts = {op: profil.get(op, 0) for op in op_types}
            op_dominante = max(op_counts, key=op_counts.get) if any(v > 0 for v in op_counts.values()) else type_op

            contexte = (
                f"Profil client — Segment: {segment} | "
                f"Solde actuel: {solde:,.0f} MAD | "
                f"Total opérations: {nb_ops} | "
                f"Activité 30 jours: {ops_30j} opérations | "
                f"Retrait moyen mensuel: {moy_ret:,.0f} MAD | "
                f"Montant moyen par opération: {montant_moyen:,.0f} MAD | "
                f"Opération dominante dans l'historique: {op_dominante} | "
                f"Compte épargne: {'Oui' if has_epargne else 'Non'} | "
                f"Opérations hors horaires: {profil.get('nb_ops_hors_horaires', 0)} | "
                f"Opérations week-end/fériés: {profil.get('nb_ops_weekend', 0) + profil.get('nb_ops_ferie', 0)} | "
                f"Jours depuis dernière opération: {profil.get('jours_depuis_derniere_operation', 999):.0f} | "
                f"Dernière opération connue: {type_op} de {montant:,.0f} MAD."
            )
        else:
            contexte = f"Données limitées. Dernière opération: {type_op} de {montant:,.0f} MAD."

        prompt = (
            f"Tu es l'Expert en Relation Client et Santé Bancaire d'Attijariwafa Bank. "
            f"Analyse la SANTÉ BANCAIRE (Satisfaction, Fidélité, Risque d'Attrition) de ce client :\n"
            f"[{contexte}]\n"
            f"L'IA XGBoost prédit une visite le {date_prevue} ({probabilite:.1f}% de confiance) pour '{operation_prevue}'. "
            f"Le profil indique un NIVEAU DE RISQUE : {niveau_risque}.\n"
            f"Tâche : Analyse son comportement bancaire et propose une stratégie précise pour ne pas le perdre, "
            f"améliorer sa satisfaction en agence et préparer le bon service au bon moment.\n"
            f"Réponds en français, de façon percutante et factuelle, sur UNE SEULE ligne au format suivant :\n"
            f"Santé : [Diagnostic bref de satisfaction/comportement] | Stratégie : [Action commerciale concrète]"
        )

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=GROQ_API_KEY,
            temperature=0.75,
            max_tokens=200,
            timeout=25,
            max_retries=5
        )
        result = (ChatPromptTemplate.from_messages([("user", "{prompt}")]) | llm).invoke({"prompt": prompt})
        raw = result.content.strip()
        # S'assurer que le message respecte un minimum le format
        if "Santé :" not in raw:
            raw = f"Santé : Stable | Stratégie : {raw}"
        return raw

    except Exception as e:
        print(f"⚠️ Erreur LLM ({client_id}): {e}")
        # Fallback factuel structuré basé sur les données réelles
        if profil:
            nb_ops = profil.get('nombre_operations', 0)
            solde = profil.get('solde_actuel', 0)
            strategie = _generer_strategie_comportementale(
                profil, niveau_risque, probabilite, operation_prevue, date_prevue, plage_horaire
            )
            return (
                f"Santé : Suivi attentif ({niveau_risque}). Avec {nb_ops} opérations et un solde de "
                f"{solde:,.0f} MAD, une action personnalisée est nécessaire. Stratégie : {strategie}"
            )
        return f"Stratégie de l'Agent : Adapter l'approche commerciale lors de la visite du {date_prevue} (Risque: {niveau_risque})."


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
    """
    Récupère la dernière opération réelle du client depuis la DB.
    Utilisé par le batch nocturne quand montant=0 (pas d'événement Kafka récent).
    """
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


def recalculer_prediction(client_id, action="BATCH", type_op="Profil Initial", montant=0.0, type_compte=None, event_time=None):
    """
    Recalcule la prédiction de visite pour un client.
    Les prédictions respectent :
      - Les jours ouvrables (Lundi–Vendredi)
      - Les jours fériés marocains
      - Les horaires bancaires AWB (8h00–16h30 semaine)
    """
    try:
        # ── BATCH : si montant=0 et type_op vide, on charge la dernière opération réelle ──
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

        # ── Date de visite : logique selon la probabilité ──────────────────────
        # Prob >= 62% → la logique métier prime (peut prédire aujourd'hui)
        # Prob <  62% → on utilise le modèle XGBoost next-event en premier
        if probabilite >= 62.0:
            # Pour les clients très probables : on applique directement la règle métier
            # qui peut prédire une visite aujourd'hui
            date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)
        else:
            # Pour les autres : XGBoost en priorité, fallback déterministe si échec
            date_p, time_p = _predire_next_datetime(profil, type_compte, montant, base_dt)
            if not date_p or not time_p:
                date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)

        # ── Opération prévue : HISTORIQUE réel en priorité, modèle en backup ──
        # L'historique est plus fiable que le modèle XGBoost pour cette tâche
        op_p = _predire_next_operation_from_history(client_id, type_op, montant, base_dt)
        if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
            op_p = _predire_next_operation_future(profil, type_compte, montant)

        # Sécurité finale sur l'opération
        if not op_p or op_p in ("Opération Bancaire", "Profil Initial", ""):
            op_p = "Opération Bancaire"

        # ── STRATÉGIE & RISQUE : règles métier déterministes ──────────────────
        from analysis_engine import determiner_strategie, calculer_niveau_risque
        segment = str(profil.get("segment_metier", "Standard")) if profil else "Standard"

        # ── CALCUL DU SCORE DE RISQUE (Multi-critères) ────────────────────────
        solde_actuel  = profil.get("solde_actuel", 0.0)       if profil else 0.0
        solde_moyen   = profil.get("solde_moyen_compte", 0.0) if profil else 0.0
        nb_ops_30j    = profil.get("nb_operations_30j", 0)    if profil else 0
        tot_ops       = profil.get("nombre_operations", 0)    if profil else 0
        moy_retraits  = profil.get("moyenne_retraits_30j", 0.0) if profil else 0.0
        has_epargne   = bool(profil.get("has_compte_epargne", 0)) if profil else False

        score_churn = 0.0

        # 1. Critère Solde (Urgence si baisse > 40%)
        if solde_moyen > 1000:
            ratio_solde = solde_actuel / solde_moyen
            if ratio_solde < 0.4:   score_churn += 0.6
            elif ratio_solde < 0.7: score_churn += 0.3

        # 2. Critère Retraits (Alerte si retraits massifs par rapport au solde)
        if solde_actuel > 0 and moy_retraits > (solde_actuel * 0.4):
            score_churn += 0.4

        # 3. Critère Inactivité (client actif qui s'arrête soudainement)
        if tot_ops > 20 and nb_ops_30j == 0:
            score_churn += 0.5

        score_churn = min(score_churn, 0.95)

        niveau_risque = calculer_niveau_risque(score_churn)

        if _doit_venir_aujourdhui(profil, probabilite, niveau_risque):
            date_p, time_p = _predire_date_visite(probabilite, base_dt, profil=profil)

        strategie    = _generer_strategie_comportementale(
            profil, niveau_risque, probabilite, op_p, date_p, time_p
        )

        # ── INSIGHT IA : LLM nourri par le profil complet ─────────────────────
        insight = _generer_insight_llm(
            client_id, type_op, montant, probabilite, statut,
            op_p, date_p, time_p,
            profil=profil, niveau_risque=niveau_risque
        )

        # ── EXTRACTION DE LA STRATÉGIE LLM POUR LE CHAMP DÉDIÉ ────────────────
        final_strategie = strategie # Fallback déterministe
        if "Stratégie :" in insight:
            try:
                final_strategie = insight.split("Stratégie :")[1].strip()
            except: pass

        _sauvegarder_prediction_db(client_id, probabilite, op_p, date_p, insight, time_p, final_strategie, niveau_risque)
        print(f"✅ Client {client_id} | Score: {probabilite:.1f}% | {niveau_risque} | {final_strategie[:40]}...")

    except Exception as e:
        print(f"⚠️  Erreur client {client_id} : {e}")
