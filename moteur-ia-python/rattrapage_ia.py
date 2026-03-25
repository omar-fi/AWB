import time
import mysql.connector
# On importe ta fonction directement depuis ton autre fichier !
from consumer_ia import recalculer_prediction, get_db_connection

print("🚀 Lancement de la mise à jour des anciennes prédictions...")

try:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # On cherche tous les clients qui ont une prédiction mais dont la colonne insight_genai est vide
    cursor.execute("""
        SELECT client_id 
        FROM prediction_visite 
        WHERE insight_genai IS NULL OR insight_genai = ''
    """)
    clients_a_mettre_a_jour = cursor.fetchall()

    total = len(clients_a_mettre_a_jour)
    print(f"📊 {total} clients trouvés nécessitant l'intervention de l'Agent IA.")

    # On boucle sur chaque client pour faire travailler Mixtral
    for index, client in enumerate(clients_a_mettre_a_jour):
        cid = client['client_id']
        print(f"\n⏳ [{index + 1}/{total}] Traitement du client ID: {cid}")
        
        # On appelle ta fonction exactement comme si un message Kafka était arrivé
        recalculer_prediction(cid, action="MIGRATION_IA")
        
        # Pause de 3 secondes pour ne pas surcharger l'API OpenRouter
        time.sleep(3)

    print("\n✅ Tâche terminée ! Toutes les prédictions ont maintenant leur Insight GenAI.")

except Exception as e:
    print(f"❌ Erreur lors du rattrapage : {e}")
finally:
    if 'conn' in locals() and conn.is_connected():
        conn.close()