import mysql.connector
from faker import Faker
import random

fake = Faker('fr_FR')

def generate_data():
    print("⏳ Connexion à la base de données MySQL...")
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="", # N'oublie pas de mettre "root" si tu es sur MAMP/Mac
            database="attijari_predict_db"
        )
        cursor = conn.cursor()

        # ==========================================
        # 0. NETTOYAGE DES ANCIENNES DONNÉES
        # ==========================================
        print("🧹 Nettoyage de l'ancienne base de données...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("TRUNCATE TABLE HISTORIQUE_OPERATION;")
        cursor.execute("TRUNCATE TABLE PREDICTION_VISITE;")
        cursor.execute("TRUNCATE TABLE COMPTE;")
        cursor.execute("TRUNCATE TABLE CLIENT;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        # ==========================================
        # 1. GÉNÉRATION DES CLIENTS & COMPTES
        # ==========================================
        print("👤 Génération de 100 clients et de leurs comptes...")
        segments = ["Particulier", "Professionnel", "TPE", "PME", "VIP"]
        client_ids = []
        
        for _ in range(100):
            # Création du Client
            cin = fake.bothify(text='??######').upper()
            nom_complet = fake.name()
            segment = random.choice(segments)
            date_creation = fake.date_time_between(start_date='-5y', end_date='now')

            query_client = "INSERT INTO CLIENT (cin, nom_complet, segment_metier, date_creation) VALUES (%s, %s, %s, %s)"
            cursor.execute(query_client, (cin, nom_complet, segment, date_creation))
            client_id = cursor.lastrowid
            client_ids.append(client_id)
            
            # --- Création du Compte Chèque (Obligatoire) ---
            num_compte_cheque = fake.bothify(text='RIB########################')
            # Astuce IA : On génère des soldes entre -2000 DH et 50 000 DH
            solde_cheque = round(random.uniform(-2000.0, 50000.0), 2) 
            
            query_compte = "INSERT INTO COMPTE (numero_compte, type_compte, solde, date_ouverture, client_id) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query_compte, (num_compte_cheque, "CHEQUE", solde_cheque, date_creation, client_id))
            
            # --- Création d'un Compte Épargne (Pour 30% des clients seulement) ---
            if random.random() < 0.3:
                num_compte_epargne = fake.bothify(text='RIB########################')
                solde_epargne = round(random.uniform(5000.0, 300000.0), 2)
                cursor.execute(query_compte, (num_compte_epargne, "EPARGNE", solde_epargne, date_creation, client_id))

        conn.commit()

        # ==========================================
        # 2. GÉNÉRATION DE L'HISTORIQUE
        # ==========================================
        print("💸 Génération de 10 000 opérations bancaires...")
        types_operation = ["Versement Espèces", "Retrait Guichet", "Remise de Chèque", "Virement Reçu", "Paiement TPE", "Demande de Crédit"]
        
        for _ in range(10000):
            client_id = random.choice(client_ids)
            date_op = fake.date_time_between(start_date='-2y', end_date='now')
            type_op = random.choice(types_operation)
            montant = round(random.uniform(100.0, 15000.0), 2) 

            query_op = "INSERT INTO HISTORIQUE_OPERATION (date_heure_operation, type_operation, montant, client_id) VALUES (%s, %s, %s, %s)"
            cursor.execute(query_op, (date_op, type_op, montant, client_id))

        conn.commit()
        print("✅ SUCCÈS : Base de données remplie ! L'IA a maintenant accès aux soldes financiers.")

    except mysql.connector.Error as err:
        print(f"❌ Erreur MySQL : {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    generate_data()