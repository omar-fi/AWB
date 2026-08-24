import asyncio
import json
import os
import mysql.connector
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("agent_ia.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def sauvegarder_prediction(client_id, prediction, risque, insight):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM prediction_visite WHERE client_id = %s", (client_id,))
        exists = cursor.fetchone()
        
        prob = prediction.get("score_probabilite", 0.0)
        op = prediction.get("operation_prevue", "Opération")
        date = prediction.get("date_prevue")
        heure = prediction.get("plage_horaire", "09:00")
        strat = risque.get("strategie_prescrite", "")
        niv_risque = risque.get("niveau_risque", "FAIBLE")
        
        if exists:
            query = """
                UPDATE prediction_visite 
                SET score_probabilite_global=%s, operation_prevue=%s, date_prevue=%s, 
                    insight_genai=%s, plage_horaire_prevue=%s, strategie_prescrite=%s, 
                    niveau_risque=%s, date_dernier_calcul=NOW() 
                WHERE client_id=%s
            """
            cursor.execute(query, (prob, op, date, insight, heure, strat, niv_risque, client_id))
        else:
            query = """
                INSERT INTO prediction_visite 
                (client_id, score_probabilite_global, operation_prevue, date_prevue, 
                 insight_genai, plage_horaire_prevue, strategie_prescrite, niveau_risque, date_dernier_calcul) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(query, (client_id, prob, op, date, insight, heure, strat, niv_risque))
            
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde DB pour client {client_id} : {e}")

async def run_agent():
    logger.info("🤖 Démarrage de l'Agent IA AWB (via MCP)...")
    
    import sys
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_ia_server.py"],
        env=os.environ.copy()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id FROM client")
                clients = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"❌ Impossible de charger les clients : {e}")
                return

            logger.info(f"📊 Traitement de {len(clients)} clients...")

            for client in clients:
                cid = client['id']
                try:
                    result_profil = await session.call_tool("get_client_history", {"client_id": cid})
                    profil = result_profil.content[0].text
                    if isinstance(profil, str):
                        profil_dict = json.loads(profil)
                    else:
                        profil_dict = profil
                    profil_json = json.dumps(profil_dict)

                    result_pred = await session.call_tool("predict_visite", {"profil_json": profil_json})
                    pred = result_pred.content[0].text
                    pred_dict = json.loads(pred) if isinstance(pred, str) else pred
                    prediction_json = json.dumps(pred_dict)

                    result_risque = await session.call_tool("calculate_risk_and_strategy", {"profil_json": profil_json})
                    risque = result_risque.content[0].text
                    risque_dict = json.loads(risque) if isinstance(risque, str) else risque
                    risque_json = json.dumps(risque_dict)

                    result_insight = await session.call_tool("generate_insight", {
                        "profil_json": profil_json,
                        "prediction_json": prediction_json,
                        "risque_json": risque_json
                    })
                    insight = result_insight.content[0].text
                    if "Stratégie :" in insight:
                        try:
                            parts = insight.split("Stratégie :")
                            risque_dict["strategie_prescrite"] = parts[1].strip()
                            insight = parts[0].replace("Santé :", "").strip()
                            if insight.endswith("|"):
                                insight = insight[:-1].strip()
                        except: pass

                    sauvegarder_prediction(cid, pred_dict, risque_dict, insight)
                    
                    logger.info(f"✅ Client {cid} traité | Score: {pred_dict.get('score_probabilite'):.1f}% | Stratégie: {risque_dict.get('strategie_prescrite')[:50]}...")

                except Exception as e:
                    logger.error(f"❌ Erreur sur le client {cid} : {e}")

    logger.info("🏁 Agent IA a terminé sa mission.")

if __name__ == "__main__":
    asyncio.run(run_agent())
