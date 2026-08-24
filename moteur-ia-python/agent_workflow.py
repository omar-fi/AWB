"""
Workflow LangGraph pour l'orchestration multi-agent AWB
Orchestre : Agent Prédiction → Agent Analyse → Agent Stratégie
"""
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from agent_prediction import calculer_predictions_pour_client
from agent_analyse import run_agent_analyse
from agent_strategie import analyser_strategie_pour_client

load_dotenv()

class AgentState(TypedDict):
    """État partagé entre les agents du workflow."""
    client_id: int
    prediction: dict | None
    analyse: dict | None
    strategie: dict | None
    erreur: str | None


def agent_prediction(state: AgentState) -> AgentState:
    """Nœud : Agent Prédiction (XGBoost)."""
    try:
        client_id = state["client_id"]
        print(f"🤖 Agent Prédiction : Traitement client {client_id}")
        prediction = calculer_predictions_pour_client(client_id, action="WORKFLOW")
        return {**state, "prediction": prediction, "erreur": None}
    except Exception as e:
        print(f"❌ Erreur Agent Prédiction : {e}")
        return {**state, "erreur": f"Erreur prédiction : {str(e)}"}


def agent_analyse(state: AgentState) -> AgentState:
    """Nœud : Agent Analyse (LangChain + Groq + SHAP)."""
    if state["erreur"]:
        return state
    try:
        client_id = state["client_id"]
        print(f"🤖 Agent Analyse : Traitement client {client_id}")
        analyse = run_agent_analyse(client_id)
        return {**state, "analyse": analyse, "erreur": None}
    except Exception as e:
        print(f"❌ Erreur Agent Analyse : {e}")
        return {**state, "erreur": f"Erreur analyse : {str(e)}"}


def agent_strategie(state: AgentState) -> AgentState:
    """Nœud : Agent Stratégie (Règles métier + LLM)."""
    if state["erreur"]:
        return state
    try:
        client_id = state["client_id"]
        print(f"🤖 Agent Stratégie : Traitement client {client_id}")
        strategie = analyser_strategie_pour_client(client_id, state.get("prediction"))
        return {**state, "strategie": strategie, "erreur": None}
    except Exception as e:
        print(f"❌ Erreur Agent Stratégie : {e}")
        return {**state, "erreur": f"Erreur stratégie : {str(e)}"}


def should_continue(state: AgentState) -> str:
    """Condition d'arrêt : si erreur, arrêter ; sinon continuer."""
    if state["erreur"]:
        return END
    return "agent_analyse"



def create_agent_workflow() -> StateGraph:
    """Créer et compiler le workflow LangGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("agent_prediction", agent_prediction)
    graph.add_node("agent_analyse", agent_analyse)
    graph.add_node("agent_strategie", agent_strategie)

    graph.set_entry_point("agent_prediction")
    graph.add_edge("agent_prediction", "agent_analyse")
    graph.add_edge("agent_analyse", "agent_strategie")
    graph.add_edge("agent_strategie", END)

    return graph.compile()



def run_full_workflow(client_id: int) -> dict:
    """Exécuter le workflow complet pour un client."""
    workflow = create_agent_workflow()
    initial_state: AgentState = {
        "client_id": client_id,
        "prediction": None,
        "analyse": None,
        "strategie": None,
        "erreur": None
    }
    result = workflow.invoke(initial_state)
    return result


if __name__ == "__main__":
    print("🧪 Test du workflow LangGraph avec client_id=1")
    test_result = run_full_workflow(1)
    print("\n📋 Résultat final du workflow :")
    print(test_result)
