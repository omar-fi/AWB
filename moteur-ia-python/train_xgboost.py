import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import classification_report
import joblib
from sqlalchemy import create_engine
import os
import numpy as np
from dotenv import load_dotenv

print("🚀 Démarrage de l'extraction et du Feature Engineering...")

load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_name = os.getenv("DB_NAME", "attijari_predict_db")

try:
    engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")
    print("✅ Connexion à MySQL réussie !")
    
    # On récupère ta table exacte
    query = "SELECT * FROM historique_operation"
    df_raw = pd.read_sql(query, con=engine)
    print(f"📊 {len(df_raw)} opérations brutes récupérées.")

except Exception as e:
    print(f"❌ Erreur lors de l'extraction : {e}")
    exit()

# --- ETAPE CRUCIALE : LE FEATURE ENGINEERING ---
# --- ETAPE CRUCIALE : LE FEATURE ENGINEERING ---
print("⚙️ Transformation des opérations en profils clients...")

# Petite astuce de pro : On affiche les vrais noms des colonnes pour vérifier
print(f"📌 Noms des colonnes en base : {list(df_raw.columns)}")

# 1. On regroupe par client_id pour créer des statistiques
df_clients = df_raw.groupby('client_id').agg(
    nombre_operations=('id', 'count'),
    montant_total=('montant', 'sum'),
    montant_moyen=('montant', 'mean')
).reset_index()

# 2. On compte le nombre d'opérations par type (Correction de 'typeOperation' en 'type_operation')
types_ops = pd.crosstab(df_raw['client_id'], df_raw['type_operation']).reset_index()
df_final = pd.merge(df_clients, types_ops, on='client_id')

# 3. Création de la Cible (Target) pour le POC
# Utilisation de la médiane pour garantir une séparation 50% de 0 et 50% de 1
mediane_montant = df_final['montant_total'].median()

df_final['cible_prediction'] = np.where(
    (df_final['nombre_operations'] > 15) & (df_final['montant_total'] > mediane_montant), 1, 0
)

# Petite astuce pour vérifier que l'erreur ne se reproduira pas
print("\n📊 Répartition des clients pour l'entraînement :")
print(df_final['cible_prediction'].value_counts())

# On retire l'ID client qui n'est pas une donnée mathématique pertinente
X = df_final.drop(['client_id', 'cible_prediction'], axis=1) 
y = df_final['cible_prediction']
# --- ENTRAÎNEMENT XGBOOST ---
print("🔍 Début de l'entraînement intensif GridSearchCV...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

xgb_model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss')
param_grid = {
    'max_depth': [3, 5],
    'learning_rate': [0.1, 0.2],
    'n_estimators': [100, 200]
}

grid_search = GridSearchCV(xgb_model, param_grid, scoring='accuracy', cv=3, n_jobs=-1)
grid_search.fit(X_train, y_train)

print("\n✅ Optimisation terminée !")
best_model = grid_search.best_estimator_

y_pred = best_model.predict(X_test)
print("\n--- Rapport de Classification Final ---")
print(classification_report(y_test, y_pred))

joblib.dump(best_model, 'xgboost_optimise.pkl')
print("💾 Modèle 'xgboost_optimise.pkl' sauvegardé avec succès en local !")