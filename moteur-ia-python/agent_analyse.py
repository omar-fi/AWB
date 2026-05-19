from agent_strategie import analyser_strategie_pour_client, run_batch_strategies

def analyser_sante_client(client_id: int, prediction_data: dict):
    """
    Délègue à l'Agent de Stratégie (agent_strategie.py) pour maintenir la compatibilité.
    """
    analyser_strategie_pour_client(client_id, prediction_data)

def main():
    print("=" * 60)
    print("🧠 AGENT D'ANALYSE SANTÉ & STRATÉGIE (Compatibilité Agent 3) — AWB")
    print("=" * 60)
    run_batch_strategies(force_all=False)
    print("=" * 60)

if __name__ == "__main__":
    main()
