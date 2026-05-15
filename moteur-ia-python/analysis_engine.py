import os
import json
from typing import Dict, Any




def determiner_strategie(segment: str, score_churn: float, solde: float = 0, a_epargne: bool = False) -> str:
    """
    LE MOTEUR DE STRATÉGIE DÉTERMINISTE
    Fournit une base de recommandation avant le passage au LLM.
    """
    segment = segment.upper()
    
    # 1. Gestion de l'urgence maximale
    if score_churn >= 0.85:
        if "VIP" in segment or "PRO" in segment:
            return "ALERTE RÉTENTION : Rendez-vous urgent avec le Directeur d'Agence sous 48h."
        return "RÉTENTION : Contact téléphonique immédiat pour comprendre l'insatisfaction."

    # 2. Opportunités de placement (Clients avec solde élevé sans épargne)
    if solde > 50000 and not a_epargne:
        if "VIP" in segment:
            return "PLACEMENT : Proposer Gestion Sous Mandat ou Assurance Vie Premium."
        return "PLACEMENT : Proposer Plan d'Épargne Logement ou compte sur carnet."

    # 3. Besoins de financement (Segments Professionnels / Entreprises)
    if any(x in segment for x in ["PRO", "PME", "TPE"]):
        if score_churn < 0.3: # Client fidèle
            return "FINANCEMENT : Proposer ligne de crédit de trésorerie ou leasing."
            
    # 4. Offres spécifiques Étudiants / Jeunes
    if "ETUDIANT" in segment:
        return "FIDÉLISATION : Offrir 1 an de gratuité sur le Pack Jeune."

    return "FIDÉLISATION : Entretien de courtoisie pour mise à jour du dossier KYC."


def calculer_niveau_risque(score_churn: float) -> str:
    """
    Évalue le niveau de risque global du client de façon segmentée.
    """
    if score_churn >= 0.8:
        return "CRITIQUE"
    elif score_churn >= 0.6:
        return "ÉLEVÉ"
    elif score_churn >= 0.4:
        return "ALERTE"
    elif score_churn >= 0.2:
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
    
    # Mock du LLM pour que le module fonctionne localement sans clé API
    return f"Le client présente un comportement caractérisé par : {historique_recent.lower()}"


def analyser_client(client_data: Dict[str, Any]) -> Dict[str, str]:
    """
    L'ORCHESTRATEUR
    Appelle les deux méthodes précédentes et retourne un dictionnaire 
    contenant les deux variables TOTALEMENT SÉPARÉES.
    """
    # Extraction sécurisée des données
    segment = client_data.get("segment", "Standard")
    
    try:
        score_churn = float(client_data.get("score_churn", 0.0))
    except (ValueError, TypeError):
        score_churn = 0.0
        
    historique_recent = client_data.get("historique_recent", "")
    
    # Obtention de l'action déterministe
    strategie = determiner_strategie(segment, score_churn)
    
    # Obtention du diagnostic de l'IA générative
    insight = generer_insight_ia(historique_recent)
    
    # Obtention du niveau de risque
    niveau_risque = calculer_niveau_risque(score_churn)
    
    return {
        "strategiePrescrite": strategie,
        "insightGenai": insight,
        "niveauRisque": niveau_risque
    }


# ==================================================================
# SIMULATION / ZONE DE TEST
# ==================================================================
if __name__ == "__main__":
    # Jeu de données de test
    clients_a_tester = [
        {
            "segment": "VIP",
            "score_churn": 0.88, # > 0.80 et VIP -> Rendez-vous Directeur
            "historique_recent": "Retraits importants en espèces et transfert massif vers compte externe."
        },
        {
            "segment": "Etudiant",
            "score_churn": 0.95, # > 0.85 et Etudiant -> Offrir 1 an de gratuité
            "historique_recent": "Deux prélèvements Netflix et Spotify rejetés pour solde insuffisant."
        },
        {
            "segment": "Standard",
            "score_churn": 0.40, # Cas par défaut -> Suivi classique
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
