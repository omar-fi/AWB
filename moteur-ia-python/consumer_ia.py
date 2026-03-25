import json
import joblib
import pandas as pd
import mysql.connector
import os
import requests
import datetime
import random
from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv

# ── Configuration ─────────────────────────────────────────────────────────────
load_dotenv()

KAFKA_SERVER = 'localhost:9092'
TOPIC_ECOUTE = 'transactions-client-topic'   # Spring Boot → Python IA
TOPIC_RETOUR = 'predictions-ia-topic'         # Python IA  → Spring Boot

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

print("🚀 Initialisation du Microservice IA Hybride (Full Event-Driven)...")

# ── Traduction des types d'opération ─────────────────────────────────────────
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
}

# ── Chargement des modèles XGBoost ────────────────────────────────────────────
# Modèle 1 : Prédit SI le client va venir (score de probabilité de visite)
try:
    model_visite = joblib.load('xgboost_optimise.pkl')
    print("🧠 Modèle XGBoost (visite) chargé avec succès !")
except Exception as e:
    print(f"❌ Impossible de charger xgboost_optimise.pkl : {e}")
    exit()

# Modèle 2 : Prédit QUELLE opération le client va effectuer
try:
    model_operation  = joblib.load('xgboost_model.pkl')
    encoder_segment  = joblib.load('encoder_segment.pkl')
    encoder_motif    = joblib.load('encoder_motif.pkl')
    print("🧠 Modèle XGBoost (opération) + encodeurs chargés avec succès !")
except Exception as e:
    print(f"⚠️  Modèle opération indisponible ({e}) — fallback sur l'opération actuelle.")
    model_operation = None
    encoder_segment = None
    encoder_motif   = None

# ── Colonnes du modèle visite ─────────────────────────────────────────────────
COLONNES_VISITE = [
    'nombre_operations', 'montant_total', 'montant_moyen',
    'Demande de Crédit', 'PAIEMENT_CARTE', 'PAIEMENT_FACTURE',
    'Paiement TPE', 'REMISE_CHEQUE', 'RETRAIT', 'Remise de Chèque',
    'Retrait Guichet', 'VERSEMENT', 'VIREMENT_EMIS', 'VIREMENT_RECU',
    'Versement Espèces', 'Virement Reçu'
]


# ── Utilitaires ────────────────────────────────────────────────────────────────

def get_db_connection():
    """Retourne une connexion MySQL active."""
    return mysql.connector.connect(**DB_CONFIG)


def _get_profil_client(client_id):
    """
    Interroge la DB pour obtenir le profil complet du client :
    segment, solde, historique des opérations.
    Retourne un dict avec toutes les features nécessaires.
    """
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Segment et solde courant
        cursor.execute("""
            SELECT c.segment_metier,
                   COALESCE(SUM(co.solde), 0) AS solde_actuel
            FROM client c
            LEFT JOIN compte co ON c.id = co.client_id
            WHERE c.id = %s
            GROUP BY c.segment_metier
        """, (client_id,))
        base = cursor.fetchone()

        # Statistiques des 30 derniers jours
        cursor.execute("""
            SELECT COUNT(*)                                        AS nb_ops,
                   COALESCE(AVG(CASE WHEN type_operation='RETRAIT'
                                     THEN montant END), 0)        AS moy_retrait,
                   COUNT(DISTINCT type_operation)                 AS types_distincts
            FROM historique_operation
            WHERE client_id = %s
              AND date_heure_operation >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (client_id,))
        hist = cursor.fetchone()

        # Statistiques globales (pour le modèle visite)
        cursor.execute("""
            SELECT COUNT(*)                                AS nombre_operations,
                   COALESCE(SUM(montant), 0)              AS montant_total,
                   COALESCE(AVG(montant), 0)              AS montant_moyen,
                   type_operation
            FROM historique_operation
            WHERE client_id = %s
            GROUP BY type_operation
        """, (client_id,))
        ops_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Construit le dictionnaire de profil
        profil = {
            "segment_metier": base["segment_metier"] if base else "PARTICULIER",
            "solde_actuel":   float(base["solde_actuel"]) if base else 0.0,
            "nb_operations_30j":   int(hist["nb_ops"]) if hist else 0,
            "moyenne_retraits_30j": float(hist["moy_retrait"]) if hist else 0.0,
        }

        # Stats globales par type d'opération pour le modèle visite
        total_ops = sum(r["nombre_operations"] for r in ops_rows)
        total_montant = sum(float(r["montant_total"]) for r in ops_rows)
        total_moyen   = total_montant / total_ops if total_ops > 0 else 0.0

        profil["nombre_operations"] = total_ops
        profil["montant_total"]     = total_montant
        profil["montant_moyen"]     = total_moyen

        # Comptage par type
        for row in ops_rows:
            profil[row["type_operation"]] = int(row["nombre_operations"])

        return profil

    except Exception as e:
        print(f"⚠️  Erreur profil client {client_id} : {e}")
        return None


def _predire_visite(profil, type_op_actuel, montant):
    """
    Utilise xgboost_optimise.pkl pour calculer la probabilité de visite
    basée sur le profil cumulatif du client + l'opération actuelle.
    """
    features = {col: 0 for col in COLONNES_VISITE}

    # Enrichit avec le profil DB
    if profil:
        features['nombre_operations'] = profil.get('nombre_operations', 1) + 1
        features['montant_total']     = profil.get('montant_total', 0) + montant
        nb = features['nombre_operations']
        features['montant_moyen']     = features['montant_total'] / nb if nb > 0 else montant

        for col in COLONNES_VISITE[3:]:   # colonnes de type d'opération
            if col in profil:
                features[col] = profil[col]
    else:
        # Fallback : uniquement l'opération actuelle
        features['nombre_operations'] = 1
        features['montant_total']     = montant
        features['montant_moyen']     = montant

    # Ajoute l'opération actuelle
    if type_op_actuel in features:
        features[type_op_actuel] = features.get(type_op_actuel, 0) + 1

    df = pd.DataFrame([features], columns=COLONNES_VISITE)
    prediction  = model_visite.predict(df)[0]
    probabilite = float(model_visite.predict_proba(df)[0][1] * 100)

    # ── RÈGLE MÉTIER : VISITE OBLIGATOIRE, CERTITUDE DYNAMIQUE > 80% ──
    # Rendre le score unique basé sur l'historique réel et le type de compte (segment)
    score_base = 80.0

    if profil:
        # 1. Activité globale (max +7.0 points)
        nb_ops = profil.get('nombre_operations', 0)
        score_base += min((nb_ops / 30.0) * 7.0, 7.0)
        
        # 2. Segment / Type de compte (VIP = +4.5, PRO/PME/TPE = +3.5, Particulier = +1.5)
        segment = str(profil.get('segment_metier', '')).upper()
        if 'VIP' in segment:
            score_base += 4.5
        elif 'PRO' in segment or 'PME' in segment or 'TPE' in segment:
            score_base += 3.5
        else:
            score_base += 1.5
            
        # 3. Activité récente sur 30 jours (max +4.5 points)
        ops_30j = profil.get('nb_operations_30j', 0)
        score_base += min((ops_30j / 10.0) * 4.5, 4.5)
        
        # 4. Le reste de probabilité (jusqu'à 99.9%) généré par l'aspect comportemental de XGBoost
        reste = 99.9 - score_base
        probabilite_finale = score_base + (probabilite / 100.0) * max(reste, 0)
    else:
        # Fallback (nouveau client sans historique)
        probabilite_finale = 80.0 + (probabilite / 100.0) * 10.0

    probabilite_finale = min(probabilite_finale, 99.9)
    statut      = "VISITE_EMINENTE"
    prediction  = 1

    print(f"➡️  Visite IA (Personnalisée) : {statut} ({probabilite_finale:.2f}%)")
    return prediction, probabilite_finale, statut


def _predire_operation_future(profil):
    """
    Utilise xgboost_model.pkl pour prédire quelle opération le client
    va effectuer lors de sa prochaine visite.
    Retourne un libellé lisible (ex: 'Retrait Espèces').
    """
    if model_operation is None or profil is None:
        return None

    try:
        segment    = profil.get("segment_metier", "PARTICULIER")
        solde      = profil.get("solde_actuel", 0.0)
        moy_ret    = profil.get("moyenne_retraits_30j", 0.0)
        nb_ops     = profil.get("nb_operations_30j", 0)
        ratio      = solde / (moy_ret + 1)

        try:
            seg_enc = encoder_segment.transform([segment])[0]
        except Exception:
            seg_enc = 0

        X = pd.DataFrame([[seg_enc, solde, moy_ret, nb_ops, ratio]],
                         columns=['seg_enc', 'solde_actuel',
                                  'moyenne_retraits_30j',
                                  'nb_operations_30j',
                                  'ratio_solde_habitude'])

        pred_idx = model_operation.predict(X)[0]
        motif    = encoder_motif.inverse_transform([pred_idx])[0]

        # Traduit en libellé lisible
        label = OPERATION_LABELS.get(motif.upper(), motif)
        print(f"🔮 Opération prévue : {label} (brut: {motif})")
        return label

    except Exception as e:
        print(f"⚠️  Erreur prédiction opération : {e}")
        return None


def _predire_date_visite(probabilite):
    """
    Calcule une date de visite probable et une plage horaire.
    Plus la probabilité est haute, plus la visite est proche.
    """
    if probabilite >= 80:
        jours = random.randint(1, 3)
    elif probabilite >= 60:
        jours = random.randint(3, 7)
    elif probabilite >= 40:
        jours = random.randint(7, 14)
    else:
        jours = random.randint(14, 30)

    date_prevue = (datetime.date.today() + datetime.timedelta(days=jours)).strftime("%Y-%m-%d")
    
    # Plage horaire
    horaires_possibles = ["09h00 - 10h00", "10h30 - 11h30", "14h00 - 15h00", "15h30 - 16h30"]
    plage_horaire = random.choice(horaires_possibles)
    
    return date_prevue, plage_horaire


def _generer_insight_llm(client_id, type_op, montant, probabilite, statut, operation_prevue, date_prevue, plage_horaire):
    """Appelle OpenRouter pour générer un insight contextuel."""
    if not OPENROUTER_API_KEY:
        return (
            f"Après son {OPERATION_LABELS.get(type_op.upper(), type_op)} de {montant:.0f} MAD, "
            f"le client {client_id} présente {probabilite:.1f}% de probabilité de visite. "
            f"Opération prévue : {operation_prevue} — date estimée : {date_prevue} ({plage_horaire})."
        )
    try:
        prompt = (
            f"Tu es un assistant IA pour les conseillers bancaires. "
            f"Analyse ce client (ID: {client_id}) qui vient de faire un(e) «{OPERATION_LABELS.get(type_op.upper(), type_op)}» de {montant:.0f} MAD. "
            f"Prédiction IA : Il reviendra en agence le {date_prevue} entre {plage_horaire} pour un(e) «{operation_prevue}» (Certitude: {probabilite:.1f}%). "
            f"Rédige un message direct au conseiller bancaire (max 3 phrases). "
            f"Dans ce message, explique de façon logique et experte : "
            f"1) POURQUOI le client risque de revenir à cette date et à cette heure, "
            f"2) POURQUOI il effectuera cette opération spécifique ({operation_prevue}). "
            f"Sois analytique, professionnel et donne une recommandation d'action au conseiller."
        )
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":    "mistralai/mixtral-8x7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️  LLM indisponible ({e}), fallback texte.")
        return (
            f"Alerte Conseiller : Le client {client_id} a effectué un(e) {OPERATION_LABELS.get(type_op.upper(), type_op)} de {montant:.0f} MAD. "
            f"L'analyse de son profil (certitude {probabilite:.1f}%) indique un besoin de {operation_prevue}. "
            f"Anticipez sa visite prévue le {date_prevue} pour structurer cette opération et le conseiller."
        )


def _sauvegarder_prediction_db(client_id, probabilite, operation_prevue, date_prevue, explication, plage_horaire):
    """Écrit ou met à jour la prédiction complète en MySQL."""
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM prediction_visite WHERE client_id = %s", (client_id,)
        )
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE prediction_visite
                SET score_probabilite_global = %s,
                    operation_prevue         = %s,
                    date_prevue              = %s,
                    insight_genai            = %s,
                    plage_horaire_prevue     = %s,
                    date_dernier_calcul      = NOW()
                WHERE client_id = %s
            """, (probabilite, operation_prevue, date_prevue, explication, plage_horaire, client_id))
        else:
            cursor.execute("""
                INSERT INTO prediction_visite
                (client_id, score_probabilite_global, operation_prevue,
                 date_prevue, insight_genai, plage_horaire_prevue, date_dernier_calcul)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (client_id, probabilite, operation_prevue, date_prevue, explication, plage_horaire))

        conn.commit()
        cursor.close()
        conn.close()
        print(f"💾 DB mise à jour : client {client_id} → {operation_prevue} le {date_prevue} ({probabilite:.1f}%)")
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde DB : {e}")


def recalculer_prediction(client_id, action="KAFKA_EVENT", type_op="INCONNU", montant=0.0):
    """
    Pipeline complet :
      1. Récupère le profil client depuis la DB
      2. Prédit SI le client va venir (xgboost_optimise.pkl)
      3. Prédit QUELLE opération il va faire (xgboost_model.pkl)
      4. Calcule une date de visite probable
      5. Génère un insight LLM
      6. Sauvegarde en MySQL
      7. Envoie le résultat via Kafka
    """
    try:
        print(f"📊 Récupération du profil client {client_id}...")
        profil = _get_profil_client(client_id)

        # 1. Probabilité de visite
        prediction, probabilite, statut = _predire_visite(profil, type_op, montant)

        # 2. Opération future prévue
        op_future = _predire_operation_future(profil)
        if not op_future:
            # Fallback : même type que l'opération actuelle
            op_future = OPERATION_LABELS.get(type_op.upper(), type_op if type_op else "Opération bancaire")

        # 3. Date et heure de visite estimées
        date_prevue, plage_horaire = _predire_date_visite(probabilite)

        # 4. Insight LLM
        explication = _generer_insight_llm(
            client_id, type_op, montant, probabilite, statut, op_future, date_prevue, plage_horaire
        )

        # 5. Sauvegarde MySQL
        _sauvegarder_prediction_db(client_id, probabilite, op_future, date_prevue, explication, plage_horaire)

        # 6. Retour Kafka → Spring Boot
        message_retour = {
            "clientId":        client_id,
            "probabilite":     probabilite,
            "statut":          statut,
            "explication":     explication,
            "operationPrevue": op_future,
            "datePrevue":      date_prevue,
            "plageHorairePrevue": plage_horaire,
        }
        producer.send(TOPIC_RETOUR, message_retour)
        producer.flush()
        print(f"📤 Kafka → Spring Boot : {op_future} le {date_prevue} ({probabilite:.1f}%)")

    except Exception as e:
        print(f"⚠️  Erreur recalculer_prediction({client_id}) : {e}")


# ── Kafka Producer (partagé) ───────────────────────────────────────────────────
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_SERVER],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


# ── Boucle principale Kafka ────────────────────────────────────────────────────

def demarrer_ecoute():
    """Démarre le consumer Kafka en boucle infinie (bloquant)."""
    consumer = KafkaConsumer(
        TOPIC_ECOUTE,
        bootstrap_servers=[KAFKA_SERVER],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print(f"🎧 En écoute sur : {TOPIC_ECOUTE}")
    print(f"📢 Prêt à publier sur : {TOPIC_RETOUR}\n")
    print("-" * 50)

    for message in consumer:
        event = message.value
        print(f"\n🔔 Transaction reçue : {event}")

        client_id = event.get('clientId', 'Inconnu')
        montant   = float(event.get('montant', 0.0))
        type_op   = event.get('typeOperation', '')

        recalculer_prediction(client_id, action="KAFKA_EVENT",
                              type_op=type_op, montant=montant)

        print("✅ Cycle terminé. En attente du prochain événement...")
        print("-" * 50)