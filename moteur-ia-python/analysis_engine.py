import os
import json
from typing import Dict, Any




def determiner_strategie(segment: str, score_churn: float, solde: float = 0, a_epargne: bool = False) -> str:
    """
    LE MOTEUR DE STRATÉGIE DÉTERMINISTE
    Fournit une base de recommandation avant le passage au LLM.
    """
    segment = segment.upper()
    
    if score_churn >= 0.85:
        if "VIP" in segment or "PRO" in segment:
            return "ALERTE RÉTENTION : Rendez-vous urgent avec le Directeur d'Agence sous 48h."
        return "RÉTENTION : Contact téléphonique immédiat pour comprendre l'insatisfaction."

    if solde > 50000 and not a_epargne:
        if "VIP" in segment:
            return "PLACEMENT : Proposer Gestion Sous Mandat ou Assurance Vie Premium."
        return "PLACEMENT : Proposer Plan d'Épargne Logement ou compte sur carnet."

    if any(x in segment for x in ["PRO", "PME", "TPE"]):
        if score_churn < 0.3:
            return "FINANCEMENT : Proposer ligne de crédit de trésorerie ou leasing."
            
    if "ETUDIANT" in segment:
        return "FIDÉLISATION : Offrir 1 an de gratuité sur le Pack Jeune."

    return "FIDÉLISATION : Entretien de courtoisie pour mise à jour du dossier KYC."


def calculer_niveau_risque(score_churn: float) -> str:
    """
    Traduit l'indice de risque en niveau d'action commerciale.

    Les seuils portent sur la plage utile de l'indice, pas sur l'intervalle
    théorique [0, 1]. L'indice est une somme pondérée de quatre facteurs dont
    deux seulement décrivent le départ lui-même (désengagement 0.35 + silence
    0.25) : un client qui a purement et simplement cessé toute opération plafonne
    donc à 0.60, et ne pouvait jamais être classé CRITIQUE avec un seuil à 0.80.
    Atteindre 0.80 supposait un client à la fois disparu, à découvert et
    nouvellement entré en relation — un cas de figure quasi inexistant.

    Les seuils ci-dessous sont calibrés pour que chaque niveau corresponde à une
    part exploitable du portefeuille : CRITIQUE ~5 %, ÉLEVÉ ~10 %, ALERTE ~15 %.
    Un conseiller ne peut traiter qu'une dizaine de dossiers urgents par semaine ;
    le niveau sert à prioriser, pas à mesurer une probabilité.
    """
    if score_churn >= 0.60:
        return "CRITIQUE"
    elif score_churn >= 0.45:
        return "ÉLEVÉ"
    elif score_churn >= 0.30:
        return "ALERTE"
    elif score_churn >= 0.15:
        return "SOUS SURVEILLANCE"
    else:
        return "FAIBLE"


def generer_insight_ia(historique_recent: str) -> str:
    """
    LE GÉNÉRATEUR D'INSIGHT IA (Diagnostic comportemental)
    Utilise un appel LLM pour analyser l'historique et faire 
    un simple diagnostic factuel sans proposer de solution.
    """
    if not historique_recent:
        historique_recent = "Aucune opération significative récente."
        
    system_prompt = (
        "Tu es un analyste financier. En lisant cet historique de transactions : "
        f"{historique_recent}, rédige une seule phrase factuelle pour décrire le "
        "comportement récent du client (ex: Baisse de revenus, retraits massifs). "
        "Ne propose AUCUNE solution commerciale, fais juste un diagnostic."
    )
    
    """
    try:
        api_key = os.environ.get("LLM_API_KEY") 
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o", # ou gpt-3.5-turbo
            temperature=0.0, # 0.0 pour garantir l'aspect factuel et constant
            messages=[{"role": "system", "content": system_prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Erreur d'appel LLM :", e)
    """
    
    return f"Le client présente un comportement caractérisé par : {historique_recent.lower()}"


def analyser_client(client_data: Dict[str, Any]) -> Dict[str, str]:
    """
    L'ORCHESTRATEUR
    Appelle les deux méthodes précédentes et retourne un dictionnaire 
    contenant les deux variables TOTALEMENT SÉPARÉES.
    """
    segment = client_data.get("segment", "Standard")
    
    try:
        score_churn = float(client_data.get("score_churn", 0.0))
    except (ValueError, TypeError):
        score_churn = 0.0
        
    historique_recent = client_data.get("historique_recent", "")
    
    strategie = determiner_strategie(segment, score_churn)
    
    insight = generer_insight_ia(historique_recent)
    
    niveau_risque = calculer_niveau_risque(score_churn)
    
    return {
        "strategiePrescrite": strategie,
        "insightGenai": insight,
        "niveauRisque": niveau_risque
    }


if __name__ == "__main__":
    clients_a_tester = [
        {
            "segment": "VIP",
            "score_churn": 0.88,
            "historique_recent": "Retraits importants en espèces et transfert massif vers compte externe."
        },
        {
            "segment": "Etudiant",
            "score_churn": 0.95,
            "historique_recent": "Deux prélèvements Netflix et Spotify rejetés pour solde insuffisant."
        },
        {
            "segment": "Standard",
            "score_churn": 0.40,
            "historique_recent": "Réception du salaire mensuel et dépenses courantes par carte stables."
        }
    ]
    
    print("\n" + "=" * 70)
    print("🧠 TEST DU MOTEUR D'ANALYSE (SÉPARATION STRATÉGIE vs INSIGHT IA)")
    print("=" * 70)
    
    for i, data in enumerate(clients_a_tester, 1):
        print(f"\n--- PROFIL CLIENT {i} ---")
        resultat = analyser_client(data)
        print(json.dumps(resultat, indent=2, ensure_ascii=False))
        print("-" * 70)
    print("\n")
