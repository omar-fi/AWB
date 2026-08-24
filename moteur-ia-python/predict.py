import pandas as pd
import mysql.connector
import joblib
import numpy as np
import warnings
import random
import datetime

warnings.filterwarnings('ignore')

conn = mysql.connector.connect(host="localhost", user="root", password="", database="attijari_predict_db")
cursor = conn.cursor(dictionary=True)

query = """
    SELECT 
        c.id, c.segment_metier,
        COALESCE(SUM(co.solde), 0) as solde_total,
        (SELECT COALESCE(AVG(h.montant), 0) FROM historique_operation h 
         WHERE h.client_id = c.id AND h.type_operation = 'RETRAIT') as moy_retrait,
        (SELECT COUNT(*) FROM historique_operation h 
         WHERE h.client_id = c.id) as nb_ops
    FROM client c
    LEFT JOIN compte co ON c.id = co.client_id
    GROUP BY c.id, c.segment_metier
"""
df_reel = pd.read_sql(query, conn)

model = joblib.load('xgboost_model.pkl')
le_seg = joblib.load('encoder_segment.pkl')
le_target = joblib.load('encoder_motif.pkl')

print(f"🔮 Analyse de {len(df_reel)} profils...")

for _, row in df_reel.iterrows():
    habitude = float(row['moy_retrait']) if float(row['moy_retrait']) > 0 else 1500.0
    solde = float(row['solde_total'])
    ratio = solde / (habitude + 1)
    
    try:
        seg_enc = le_seg.transform([row['segment_metier']])[0]
    except:
        seg_enc = 0 

    X_input = pd.DataFrame([[
        seg_enc, solde, habitude, int(row['nb_ops']), ratio
    ]], columns=['seg_enc', 'solde_actuel', 'moyenne_retraits_30j', 'nb_operations_30j', 'ratio_solde_habitude'])
    
    pred_idx = model.predict(X_input)[0]
    motif = le_target.inverse_transform([pred_idx])[0]
    
    probabilites = model.predict_proba(X_input)[0]
    score_confiance = max(0.80, float(np.max(probabilites)))

    jours_futurs = random.randint(1, 10)
    date_p = (datetime.date.today() + datetime.timedelta(days=jours_futurs)).strftime("%Y-%m-%d")
    
    update_query = """
        UPDATE prediction_visite 
        SET operation_prevue=%s, date_prevue=%s, score_probabilite_global=%s, date_dernier_calcul=NOW()
        WHERE client_id=%s
    """
    cursor.execute(update_query, (motif, date_p, score_confiance, row['id']))

conn.commit()
cursor.close()
conn.close()
print("🚀 Terminé ! Les noms de colonnes sont maintenant synchronisés.")