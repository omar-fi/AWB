import time
import sys
import os

# Ajout du chemin actuel pour importer consumer_ia
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from consumer_ia import recalculer_prediction, get_db_connection

def force_refresh():
    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion DB")
        return
        
    try:
        cursor = conn.cursor(dictionary=True)
        # On récupère tous les clients qui ont une prédiction
        cursor.execute("SELECT client_id FROM prediction_visite")
        clients = cursor.fetchall()
        cursor.close()
        conn.close()
        
        total = len(clients)
        print(f"🚀 Début du rafraîchissement forcé pour {total} prédictions...")
        
        for idx, c in enumerate(clients):
            cid = c['client_id']
            try:
                # On force le recalcul pour générer un nouvel insight LLM sans "INCONNU"
                recalculer_prediction(cid, action="FORCE_UPGRADE")
                if (idx + 1) % 10 == 0:
                    print(f"   ✅ {idx+1}/{total} insights rafraîchis...")
                # Court délai pour ne pas saturer l'API
                time.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Erreur client {cid}: {e}")
                
        print("\n✨ Mission accomplie. Toutes les analyses ont été régénérées proprement.")
    except Exception as e:
        print(f"❌ Erreur critique : {e}")

if __name__ == "__main__":
    force_refresh()
