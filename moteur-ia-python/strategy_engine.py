import os
import json
from typing import Dict, Any


def determiner_action_prescrite(client_data: Dict[str, Any]) -> str:
    """
    Applique la matrice de décision stricte pour traduire les scores 
    prédictifs bruts (XGBoost) en une action commerciale concrète 
    pour le conseiller.
    """
    segment = client_data.get("segment_client", "Standard")
    score_churn = float(client_data.get("score_churn", 0.0))
    proba_visite = float(client_data.get("probabilite_visite", 0.0))
    risque_defaut = float(client_data.get("risque_defaut", 0.0))

    if risque_defaut > 0.90:
        return "Proposer Restructuration des dettes (baisse des mensualités)"
    
    elif score_churn > 0.85 and segment == "Etudiant":
        return "Offrir 1 an de gratuité sur le Pack Bancaire"
    
    elif score_churn > 0.80 and segment == "VIP":
        return "Rendez-vous Directeur + Proposition Placement DAT"
        
    elif proba_visite > 0.90 and segment == "Standard":
        return "Proposer Plan d'Épargne ou Assurance-Vie"
        
    elif proba_visite > 0.85 and segment == "Professionnel":
        return "Proposer Crédit Trésorerie ou TPE"
        
    else:
        return "Suivi régulier, aucune action urgente."

def generer_insight_llm(client_data: Dict[str, Any], action_prescrite: str) -> str:
    """
    Simule l'appel à une API LLM pour produire un insight actionnable et 
    concis destiné au banquier, justifiant l'action prescrite basée sur l'historique.
    """
    historique_resume = client_data.get("historique_resume", "Aucune donnée transactionnelle récente n'a été flaguée.")
    
    system_prompt = (
        "Tu es un expert en stratégie bancaire. Rédige une seule phrase très courte et "
        "professionnelle à l'attention du conseiller clientèle. Explique-lui pourquoi il doit "
        f"appliquer l'action prescrite suivante : {action_prescrite}, en te basant sur ce résumé : "
        f"{historique_resume}."
    )
    
    """
    api_key = os.environ.get("LLM_API_KEY")
    client = openai.OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4", # ou "gpt-3.5-turbo" 
            temperature=0.2, # Température basse = ton formel et strict (réduit les hallucinations)
            messages=[
                {"role": "system", "content": system_prompt},
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erreur API LLM : {e}")
        return f"Veuillez appliquer: {action_prescrite}. (Erreur d'analyse LLM)"
    """
    
    
    if "Suivi régulier" in action_prescrite:
        return "Le profil transactionnel du client est stable ; maintenez simplement la qualité du suivi relationnel actuel."
        
    return (
        f"Au vu des récents mouvements ({historique_resume.lower()}), "
        f"il est impératif de {action_prescrite.lower()} afin de prévenir tout risque majeur et consolider la relation."
    ).capitalize()

def analyser_profil_client(client_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Fonction orchestratrice du "Moteur de Stratégie".
    Combine les scores de l'IA prédictive (Règles métiers) et 
    l'IA Générative (Justificatif argumenté).
    
    Retourne un objet prêt à être injecté dans la vue du Dashboard.
    """
    action = determiner_action_prescrite(client_data)
    
    insight_ia = generer_insight_llm(client_data, action)
    
    return {
        "action_recommandee": action,
        "insightGenai": insight_ia
    }

if __name__ == "__main__":
    
    test_vip_churn = {
        "segment_client": "VIP",
        "score_churn": 0.88,
        "probabilite_visite": 0.40,
        "risque_defaut": 0.02,
        "historique_resume": "Baisse de 40% des virements entrants et 2 virements massifs sortants vers le Luxembourg."
    }
    
    test_pro_upsell = {
        "segment_client": "Professionnel",
        "score_churn": 0.10,
        "probabilite_visite": 0.95,
        "risque_defaut": 0.10,
        "historique_resume": "Volume TPE en croissance de +30%, pic saisonnier attendu ce trimestre."
    }
    
    print("\n" + "="*50)
    print("🧠 SIMULATION MODULE : STATÉGIE & GEN-AI")
    print("="*50)
    
    print("\n🔹 DOSSIER 1 : OPPORTUNITÉ CHURN VIP")
    res_vip = analyser_profil_client(test_vip_churn)
    print(json.dumps(res_vip, indent=2, ensure_ascii=False))
    
    print("\n🔹 DOSSIER 2 : OPPORTUNITÉ UP-SELL PROFESSIONNEL")
    res_pro = analyser_profil_client(test_pro_upsell)
    print(json.dumps(res_pro, indent=2, ensure_ascii=False))
    print("\n")
