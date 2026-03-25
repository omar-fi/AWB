import time
from consumer_ia import get_db_connection, recalculer_prediction

print("🚀 Lancement de l'initialisation de l'IA pour TOUS les clients...")

try:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Récupérer tous les clients de la base
    cursor.execute("SELECT id FROM client")
    clients = cursor.fetchall()
    conn.close()

    total = len(clients)
    print(f"📊 {total} clients trouvés. L'IA va scanner tous les profils...")

    for index, client in enumerate(clients):
        cid = client['id']
        print(f"\n⏳ [{index + 1}/{total}] Traitement du client ID: {cid}")
        
        # Le modèle va analyser l'historique de chaque client et générer la prévision
        recalculer_prediction(cid, action="INITIALISATION", type_op="", montant=0.0)
        
        # Pause légère pour ne pas saturer l'API
        time.sleep(1.5)

    print("\n✅ Tâche terminée ! Tous les clients ont maintenant une prédiction d'IA.")

except Exception as e:
    print(f"❌ Erreur lors du scan : {e}")
