"""
Script de génération de données de test pour la table `reclamation`.
Lance-le UNE SEULE FOIS pour peupler les réclamations fictives.

Usage :
    source venv/bin/activate
    python seed_reclamations.py
"""
import os
import random
import datetime
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

TYPES = ["FRAIS", "DELAI", "ERREUR_OPERATION", "COMPORTEMENT", "SERVICE", "AUTRE"]
STATUTS = ["OUVERTE", "EN_COURS", "RESOLUE"]

DESCRIPTIONS = {
    "FRAIS": [
        "Frais de tenue de compte prélevés deux fois ce mois.",
        "Commission sur virement injustifiée prélevée sur mon compte.",
        "Frais de carte bancaire non communiqués à l'avance.",
    ],
    "DELAI": [
        "Virement reçu en retard de 3 jours ouvrables.",
        "Délai de traitement du chèque déposé trop long.",
        "Carte bancaire commandée il y a 3 semaines non reçue.",
    ],
    "ERREUR_OPERATION": [
        "Montant erroné débité suite à un paiement en agence.",
        "Double débit constaté sur mon relevé de compte.",
        "Opération passée sur le mauvais compte.",
    ],
    "COMPORTEMENT": [
        "Conseiller peu disponible et peu à l'écoute lors de mon passage.",
        "Accueil en agence insatisfaisant, temps d'attente excessif.",
        "Information contradictoire fournie par deux conseillers différents.",
    ],
    "SERVICE": [
        "Application mobile inaccessible depuis plusieurs jours.",
        "Problème de connexion à l'espace client en ligne.",
        "Impossibilité d'effectuer un virement via l'application.",
    ],
    "AUTRE": [
        "Demande de modification d'adresse non prise en compte.",
        "Courrier bancaire reçu avec des informations incorrectes.",
        "Problème non résolu malgré plusieurs relances.",
    ],
}

def seed():
    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM client ORDER BY id")
    clients = [r["id"] for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) AS nb FROM reclamation")
    nb_existantes = cursor.fetchone()["nb"]
    if nb_existantes > 0:
        print(f"⚠️  {nb_existantes} réclamations existent déjà. Seed ignoré.")
        cursor.close()
        conn.close()
        return

    print(f"📊 {len(clients)} clients trouvés. Génération des réclamations...")

    insert_cursor = conn.cursor()
    nb_inserees = 0

    clients_avec_rec = random.sample(clients, k=max(1, int(len(clients) * 0.40)))

    for client_id in clients_avec_rec:
        nb_rec = random.randint(1, 3)
        for _ in range(nb_rec):
            type_rec  = random.choice(TYPES)
            description = random.choice(DESCRIPTIONS[type_rec])
            statut    = random.choices(STATUTS, weights=[50, 25, 25])[0]

            jours_ago = random.randint(1, 120)
            date_rec  = datetime.datetime.now() - datetime.timedelta(days=jours_ago)
            date_res  = None
            if statut == "RESOLUE":
                date_res = date_rec + datetime.timedelta(days=random.randint(1, 14))

            insert_cursor.execute("""
                INSERT INTO reclamation
                    (client_id, type_reclamation, description, statut, date_reclamation, date_resolution)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (client_id, type_rec, description, statut, date_rec, date_res))
            nb_inserees += 1

    conn.commit()
    insert_cursor.close()
    cursor.close()
    conn.close()
    print(f"✅ {nb_inserees} réclamations fictives insérées pour {len(clients_avec_rec)} clients.")

if __name__ == "__main__":
    seed()
