import mysql.connector
import pandas as pd
import xgboost as xgb
import joblib
from sklearn.model_selection import train_test_split

def entrainer_ia_awb():
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="attijari_predict_db")
    query = """
        SELECT 
            c.solde, 
            cl.segment_metier, 
            (SELECT COUNT(*) FROM historique_operation h WHERE h.compte_id = c.id) as nb_ops,
            -- Ajoute ici d'autres calculs (moyenne montants, etc.)
            p.score_probabilite_global as target -- On utilise tes données actuelles pour apprendre
        FROM compte c
        JOIN client cl ON c.client_id = cl.id
        LEFT JOIN prediction_visite p ON cl.id = p.client_id
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df['segment_metier'] = pd.factorize(df['segment_metier'])[0]

    X = df.drop('target', axis=1)
    y = df['target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
    model.fit(X_train, y_train)

    joblib.dump(model, 'modele_xgboost_final.pkl')
    print("✅ Modèle XGBoost entraîné et sauvegardé !")

if __name__ == "__main__":
    entrainer_ia_awb()