import json
import asyncio
import requests
import os
from kafka import KafkaConsumer, KafkaProducer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# 1. Configuration des "Outils" (Ton serveur MCP que nous avons créé avant)
server_params = StdioServerParameters(
    command="python",
    args=["mcp_ia_server.py"], # Ton serveur qui contient XGBoost
)

async def run_agent():
    # 2. Connexion au Système Nerveux (Kafka) en lecture seule (Pull)
    consumer = KafkaConsumer(
        'transactions-client-topic', 
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print("🤖 Agent IA Hybride (Pull Mode + MCP) en écoute de Kafka...")

    # 3. Lancement de la session MCP
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Session MCP initialisée. Outils disponibles (BDD, XGBoost) connectés.\n" + "-"*50)
            
            for message in consumer:
                event = message.value
                client_id = event.get('clientId')
                montant = event.get('montant', 0.0)
                type_operation = event.get('typeOperation', 'INCONNU')

                print(f"\n📩 [KAFKA] Signal reçu : Transaction de {montant} MAD pour le client {client_id}")

                # --- ÉTAPE 1 : PULL DU CONTEXTE VIA MCP (Outil 1) ---
                print(f"🔍 [MCP] L'Agent invoque l'outil 'get_client_history'...")
                history_result = await session.call_tool("get_client_history", arguments={"client_id": client_id})
                profil_texte = history_result.content[0].text if history_result.content else "{}"
                
                # --- ÉTAPE 2 : INFERENCE XGBOOST VIA MCP (Outil 2) ---
                print(f"🧠 [MCP] L'Agent invoque l'outil 'predict_visite' (XGBoost)...")
                predict_result = await session.call_tool("predict_visite", arguments={
                    "profil_texte": profil_texte, 
                    "type_op_actuel": type_operation,
                    "montant": montant
                })
                
                try:
                    res_json = json.loads(predict_result.content[0].text)
                except Exception:
                    # Au cas où FastMCP retourne une string representation
                    import ast
                    res_json = ast.literal_eval(predict_result.content[0].text)
                    
                score = res_json.get("score_probabilite", 80.0)
                op_future = res_json.get("operation_prevue", "Opération")
                date_prevue = res_json.get("date_prevue", "Demain")
                plage_horaire = res_json.get("plage_horaire", "Matinale")

                print(f"🎯 [AGENT] XGBoost a statué : {op_future} à {score:.1f}% le {date_prevue} ({plage_horaire})")

                # --- ÉTAPE 3 : RAISONNEMENT LLM (Insight métier) ---
                print("🖋️  [LLM] L'Agent réfléchit et génère son Insight métier...")
                prompt = (
                    f"Tu es l'Agent IA de la banque. Client ID: {client_id}. "
                    f"Transaction en cours: {type_operation} de {montant} MAD.\n"
                    f"Profil extrait BDD : {profil_texte}\n"
                    f"XGBoost a statué : Visite prévue le {date_prevue} (créneau: {plage_horaire}) pour {op_future} (Score:{score:.1f}%).\n"
                    f"Rédige un message direct (max 3 phrases) au conseiller bancaire pour expliquer : "
                    f"1) Pourquoi tu anticipes ce retour à cette date et à cette heure, "
                    f"2) Pourquoi {op_future}. Finis avec une recommandation forte d'action."
                )
                
                explication = "Analyse en cours..."
                if OPENROUTER_API_KEY:
                    try:
                        resp = requests.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                            json={"model": "mistralai/mixtral-8x7b-instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
                            timeout=15
                        )
                        explication = resp.json()["choices"][0]["message"]["content"].strip()
                    except Exception as e:
                        explication = f"Alerte : Le client viendra le {date_prevue} pour un(e) {op_future}. Erreur IA ({e})"
                else:
                    explication = f"[Fallback] Préparez-vous à recevoir le client le {date_prevue} pour un(e) {op_future}."

                # --- ÉTAPE 4 : ENVOI DU RÉSULTAT A KAFKA (Spring Boot gérera la persistance et les week-ends) ---
                print(f"📨 [KAFKA] Envoi de la prédiction brute vers le topic 'predictions-ia-topic'...")
                producer = KafkaProducer(
                    bootstrap_servers='localhost:9092',
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                prediction_event = {
                    "clientId": client_id,
                    "probabilite": score,
                    "explication": explication,
                    "operationPrevue": op_future,
                    "datePrevue": date_prevue,
                    "plageHorairePrevue": plage_horaire,
                    "statut": "PREDITE"
                }
                producer.send('predictions-ia-topic', prediction_event)
                producer.flush()
                
                print(f"✅ RÉSULTAT : Prédiction publiée sur Kafka. En attente de validation métier (Backend).")
                print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_agent())