import os
from dotenv import load_dotenv

# Chargement automatique du fichier .env s'il existe
load_dotenv()

# Vérification de la clé API au démarrage
api_key = os.environ.get("OPENROUTER_API_KEY", "")
if not api_key:
    print("⚠️  OPENROUTER_API_KEY non définie — les insights seront générés en mode fallback créatif.")
else:
    print(f"✅ Clé OpenRouter détectée : {api_key[:12]}***")

# ── 1. Rattrapage : enrichir les prédictions sans insight ──────────────────
print("\n" + "=" * 60)
print("  ÉTAPE 1 — Rattrapage des insights manquants")
print("=" * 60)

try:
    import time
    import mysql.connector
    from consumer_ia import recalculer_prediction, get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # On récupère les clients qui n'ont aucune prédiction ou dont l'insight est vide
    cursor.execute("""
        SELECT c.id AS client_id 
        FROM client c
        LEFT JOIN prediction_visite p ON c.id = p.client_id
        WHERE p.id IS NULL OR p.insight_genai IS NULL OR p.insight_genai = ''
    """)
    clients = cursor.fetchall()
    cursor.close()
    conn.close()

    total = len(clients)
    if total == 0:
        print("✅ Tous les clients ont déjà leur prédiction IA — aucun rattrapage nécessaire.")
    else:
        print(f"📊 {total} client(s) sans prédiction ou insight détectés. Scan complet en cours...")
        for index, client in enumerate(clients):
            cid = client['client_id']
            print(f"\n⏳ [{index + 1}/{total}] Traitement du client ID: {cid}")
            recalculer_prediction(cid, action="INITIALISATION", type_op="", montant=0.0)
            if index < total - 1:
                time.sleep(1.5)  # Pause légère pour ne pas saturer l'API OpenRouter
        print("\n✅ Initialisation IA terminée pour toute la base de données !")

except Exception as e:
    print(f"❌ Erreur lors du rattrapage : {e}")

# ── 2. Démarrage du Consumer Kafka (boucle infinie) ────────────────────────
print("\n" + "=" * 60)
print("  ÉTAPE 2 — Démarrage du Consumer Kafka (temps réel)")
print("=" * 60)

from consumer_ia import demarrer_ecoute
demarrer_ecoute()
