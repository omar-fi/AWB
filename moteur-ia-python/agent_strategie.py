import os
import time
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from agent_prediction import (
    get_db_connection,
    _get_profil_client,
    _get_derniere_operation_reelle,
    ALL_OP_TYPES
)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-DÉTECTION DES SIGNAUX DE RÉCLAMATION depuis le comportement bancaire
# ══════════════════════════════════════════════════════════════════════════════

def _detecter_signaux_reclamation(profil: dict, niveau_risque: str) -> dict:
    """
    Analyse automatiquement le profil comportemental du client et détecte
    les signaux d'insatisfaction potentiels SANS saisie manuelle.

    Retourne un résumé structuré : types détectés, urgence, description textuelle.
    """
    if not profil:
        return {"signaux": [], "urgence": "FAIBLE", "resume_texte": "", "nb_signaux": 0}

    signaux      = []   # liste de dicts {type, description, poids}
    poids_total  = 0.0

    solde         = profil.get("solde_actuel", 0.0)
    solde_moyen   = profil.get("solde_moyen_compte", 0.0)
    moy_retraits  = profil.get("moyenne_retraits_30j", 0.0)
    nb_ops        = profil.get("nombre_operations", 0)
    nb_ops_30j    = profil.get("nb_operations_30j", 0)
    nb_ops_hors   = profil.get("nb_ops_hors_horaires", 0)
    nb_ops_weekend= profil.get("nb_ops_weekend", 0)
    has_epargne   = bool(profil.get("has_compte_epargne", 0))
    montant_moyen = profil.get("montant_moyen", 0.0)
    segment       = str(profil.get("segment_metier", "")).upper()

    ratio_hors    = nb_ops_hors  / max(1, nb_ops)
    ratio_weekend = nb_ops_weekend / max(1, nb_ops)

    # ── 1. Signal FRAIS — Retraits excessifs par rapport au solde ────────────
    if solde > 0 and moy_retraits > 0:
        ratio_retrait = moy_retraits / max(1, solde)
        if ratio_retrait > 0.5:
            poids = 0.7 if ratio_retrait > 0.8 else 0.4
            signaux.append({
                "type": "FRAIS",
                "description": (
                    f"Retraits mensuels ({moy_retraits:,.0f} MAD) très élevés par rapport au solde "
                    f"({solde:,.0f} MAD) — risque de friction sur les frais ou de tension financière."
                ),
                "poids": poids
            })
            poids_total += poids

    # ── 2. Signal DELAI — Baisse marquée de l'activité récente ───────────────
    if nb_ops > 15 and nb_ops_30j == 0:
        signaux.append({
            "type": "DELAI",
            "description": (
                f"Client historiquement actif ({nb_ops} opérations au total) "
                f"mais aucune opération ces 30 derniers jours — signe d'abandon ou d'insatisfaction."
            ),
            "poids": 0.6
        })
        poids_total += 0.6
    elif nb_ops > 10 and nb_ops_30j <= 1:
        signaux.append({
            "type": "DELAI",
            "description": (
                f"Forte baisse d'activité : seulement {nb_ops_30j} opération(s) ce mois "
                f"pour un client qui en comptait {nb_ops} au total."
            ),
            "poids": 0.3
        })
        poids_total += 0.3

    # ── 3. Signal SERVICE — Opérations hors horaires / weekend fréquentes ────
    if ratio_hors >= 0.40 or ratio_weekend >= 0.30:
        signaux.append({
            "type": "SERVICE",
            "description": (
                f"{int(ratio_hors * 100)}% des opérations hors horaires bancaires, "
                f"{int(ratio_weekend * 100)}% le weekend — le client ne peut pas être servi "
                f"aux moments où il en a besoin (manque de disponibilité digitale ou en agence)."
            ),
            "poids": 0.4
        })
        poids_total += 0.4

    # ── 4. Signal ERREUR_OPERATION — Solde anormalement bas vs historique ────
    if solde_moyen > 2000 and solde < solde_moyen * 0.30:
        signaux.append({
            "type": "ERREUR_OPERATION",
            "description": (
                f"Solde actuel ({solde:,.0f} MAD) très inférieur à la moyenne historique "
                f"({solde_moyen:,.0f} MAD) — possible opération non désirée, erreur ou prélèvement anormal."
            ),
            "poids": 0.65
        })
        poids_total += 0.65

    # ── 5. Signal COMPORTEMENT — Risque critique confirmé ─────────────────────
    if "CRITIQUE" in niveau_risque:
        signaux.append({
            "type": "COMPORTEMENT",
            "description": (
                "Profil de risque CRITIQUE détecté : la combinaison d'indicateurs signale "
                "une insatisfaction sérieuse nécessitant une intervention immédiate du conseiller."
            ),
            "poids": 0.8
        })
        poids_total += 0.8

    # ── 6. Signal PRODUIT — Client éligible mais sans épargne ────────────────
    if solde > 30000 and not has_epargne:
        signaux.append({
            "type": "PRODUIT",
            "description": (
                f"Solde élevé ({solde:,.0f} MAD) sans compte épargne — le client n'est pas "
                f"accompagné sur ses opportunités de placement, risque de départ vers la concurrence."
            ),
            "poids": 0.35
        })
        poids_total += 0.35

    # ── 7. Signal SEGMENT — Besoins professionnels non adressés ──────────────
    if any(x in segment for x in ["PRO", "PME", "TPE", "PROFESSIONNEL"]) and nb_ops_30j == 0:
        signaux.append({
            "type": "SERVICE",
            "description": (
                f"Client professionnel ({segment}) sans activité récente — "
                f"ses besoins de trésorerie ou d'encaissements semblent non couverts."
            ),
            "poids": 0.5
        })
        poids_total += 0.5

    # ── Calcul de l'urgence globale ───────────────────────────────────────────
    if poids_total >= 1.5 or "CRITIQUE" in niveau_risque:
        urgence = "CRITIQUE"
    elif poids_total >= 0.8:
        urgence = "ALERTE"
    elif poids_total >= 0.3:
        urgence = "ATTENTION"
    else:
        urgence = "FAIBLE"

    types_detectes = list({s["type"] for s in signaux})
    resume_lignes  = [f"[{s['type']}] {s['description']}" for s in signaux]
    resume_texte   = " | ".join(resume_lignes)

    return {
        "signaux":     signaux,
        "types":       types_detectes,
        "urgence":     urgence,
        "nb_signaux":  len(signaux),
        "resume_texte": resume_texte,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  STRATÉGIE DÉTERMINISTE — Règles métier enrichies des signaux auto-détectés
# ══════════════════════════════════════════════════════════════════════════════

def _generer_strategie_comportementale(
    profil: dict, niveau_risque: str, probabilite: float,
    operation_prevue: str, date_prevue: str, plage_horaire: str,
    signaux_rec: dict = None
) -> str:
    """
    Génère une stratégie de rétention basée sur le comportement bancaire
    et les signaux d'insatisfaction auto-détectés.
    """
    if not profil:
        return "Contacter le client pour comprendre ses attentes et mettre à jour son profil."

    segment       = str(profil.get("segment_metier", "")).upper()
    solde         = profil.get("solde_actuel", 0.0)
    solde_moyen   = profil.get("solde_moyen_compte", 0.0)
    moy_retraits  = profil.get("moyenne_retraits_30j", 0.0)
    has_epargne   = bool(profil.get("has_compte_epargne", 0))
    nb_ops        = profil.get("nombre_operations", 0)
    nb_ops_30j    = profil.get("nb_operations_30j", 0)
    nb_ops_hors   = profil.get("nb_ops_hors_horaires", 0)
    nb_ops_weekend= profil.get("nb_ops_weekend", 0)
    ratio_hors    = nb_ops_hors  / max(1, nb_ops)
    ratio_weekend = nb_ops_weekend / max(1, nb_ops)
    rec           = signaux_rec or {}
    types_signaux = [t.upper() for t in rec.get("types", [])]
    urgence       = rec.get("urgence", "FAIBLE")

    actions = []

    # ── Priorité 1 : Actions basées sur les signaux auto-détectés ────────────
    if urgence == "CRITIQUE":
        actions.append("organiser en urgence un entretien avec le Directeur d'Agence pour sécuriser la relation")
    elif urgence == "ALERTE":
        actions.append("contacter le client sous 48h pour un entretien de satisfaction personnalisé")
    elif urgence == "ATTENTION":
        actions.append("programmer un appel de courtoisie pour évaluer les besoins actuels du client")

    if "FRAIS" in types_signaux:
        actions.append("analyser les frais prélevés et proposer un geste commercial ou une offre plus adaptée")
    if "DELAI" in types_signaux:
        actions.append("comprendre la raison de l'inactivité récente et proposer une offre de réactivation")
    if "SERVICE" in types_signaux:
        actions.append("proposer un accompagnement digital (app mobile, virement en ligne) pour plus de flexibilité")
    if "ERREUR_OPERATION" in types_signaux:
        actions.append("vérifier avec le client les dernières opérations et corriger toute anomalie détectée")
    if "PRODUIT" in types_signaux:
        actions.append(f"proposer un compte épargne ou placement adapté à son solde de {solde:,.0f} MAD")
    if "COMPORTEMENT" in types_signaux:
        actions.append("escalader le dossier au responsable agence pour une prise en charge prioritaire")

    # ── Priorité 2 : Règles comportementales complémentaires ─────────────────
    if solde_moyen > 1000 and solde < solde_moyen * 0.6 and "ERREUR_OPERATION" not in types_signaux:
        actions.append("analyser la baisse du solde et proposer une solution de sécurisation des flux")
    if solde > 50000 and not has_epargne and "PRODUIT" not in types_signaux:
        actions.append("proposer une solution d'épargne ou de placement adaptée au profil")
    if ratio_hors >= 0.35 or ratio_weekend >= 0.25:
        if "SERVICE" not in types_signaux:
            actions.append("présenter les solutions digitales AWB pour une disponibilité 24h/24")

    # ── Priorité 3 : Segment métier ───────────────────────────────────────────
    if any(x in segment for x in ["PRO", "PME", "TPE", "PROFESSIONNEL"]):
        actions.append("étudier ses besoins de trésorerie, TPE, leasing ou optimisation des encaissements")
    elif "VIP" in segment:
        actions.append("préparer une offre premium et un traitement prioritaire en agence")
    elif "ETUDIANT" in segment or "JEUNE" in segment:
        actions.append("proposer un pack jeune, frais réduits et accompagnement budget")

    # Dédoublonnage
    vus = []
    for a in actions:
        if a not in vus:
            vus.append(a)

    prefix = ""
    if urgence in ("CRITIQUE", "ALERTE"):
        prefix = f"⚠️ PRIORITÉ {urgence} — "

    return (
        f"{prefix}Pour fidéliser ce client : "
        f"{'; '.join(vus[:4])}. "
        f"Prochaine visite prévue le {date_prevue} à {plage_horaire} "
        f"pour '{operation_prevue}' (score {probabilite:.1f}%)."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  INSIGHT LLM (Groq) — Enrichi des signaux comportementaux auto-détectés
# ══════════════════════════════════════════════════════════════════════════════

def _generer_insight_llm(
    client_id, type_op, montant, probabilite, operation_prevue,
    date_prevue, plage_horaire, profil=None, niveau_risque="FAIBLE",
    signaux_rec: dict = None
):
    """
    Génère un diagnostic de santé bancaire à partir du comportement du client
    et des signaux d'insatisfaction auto-détectés par l'Agent 3.
    """
    rec = signaux_rec or {}

    # ── Fallback sans clé Groq ────────────────────────────────────────────────
    if not GROQ_API_KEY:
        if profil:
            nb_ops    = profil.get('nombre_operations', 0)
            urgence   = rec.get('urgence', 'FAIBLE')
            nb_sig    = rec.get('nb_signaux', 0)
            strategie = _generer_strategie_comportementale(
                profil, niveau_risque, probabilite,
                operation_prevue, date_prevue, plage_horaire, rec
            )
            return (
                f"Santé : {urgence} — {nb_ops} opérations historiques"
                + (f", {nb_sig} signal(s) d'insatisfaction détectés automatiquement" if nb_sig > 0 else "")
                + f". | Stratégie : {strategie}"
            )
        return f"Stratégie de l'Agent : Adapter l'approche lors de la visite du {date_prevue} (Risque: {niveau_risque})."

    time.sleep(1.2)  # Pacing Groq

    try:
        # ── Construction du contexte comportemental ───────────────────────────
        if profil:
            nb_ops      = profil.get('nombre_operations', 0)
            solde       = profil.get('solde_actuel', 0)
            segment     = profil.get('segment_metier', 'Particulier')
            ops_30j     = profil.get('nb_operations_30j', 0)
            moy_ret     = profil.get('moyenne_retraits_30j', 0)
            has_epargne = profil.get('has_compte_epargne', 0)
            op_counts   = {op: profil.get(op, 0) for op in ALL_OP_TYPES}
            op_dominante= max(op_counts, key=op_counts.get) if any(v > 0 for v in op_counts.values()) else type_op
            contexte_comportement = (
                f"Segment: {segment} | Solde: {solde:,.0f} MAD | Opérations totales: {nb_ops} | "
                f"Activité 30j: {ops_30j} ops | Retrait moyen: {moy_ret:,.0f} MAD | "
                f"Opération dominante: {op_dominante} | Épargne: {'Oui' if has_epargne else 'Non'} | "
                f"Dernière op: {type_op} de {montant:,.0f} MAD"
            )
        else:
            contexte_comportement = f"Données limitées. Dernière opération: {type_op} de {montant:,.0f} MAD."

        # ── Contexte des signaux auto-détectés ───────────────────────────────
        nb_sig    = rec.get("nb_signaux", 0)
        urgence   = rec.get("urgence", "FAIBLE")
        if nb_sig > 0:
            context_signaux = (
                f"\nSIGNAUX D'INSATISFACTION DÉTECTÉS AUTOMATIQUEMENT ({nb_sig} signal(s) — Urgence: {urgence}) :\n"
                f"{rec.get('resume_texte', '')}"
            )
        else:
            context_signaux = "\nAucun signal d'insatisfaction comportementale détecté — client globalement satisfait."

        prompt = (
            f"Tu es l'Expert en Relation Client et Santé Bancaire d'Attijariwafa Bank.\n"
            f"Voici le profil complet d'un client :\n\n"
            f"[COMPORTEMENT BANCAIRE]\n{contexte_comportement}\n\n"
            f"[ANALYSE COMPORTEMENTALE IA]{context_signaux}\n\n"
            f"L'IA XGBoost prédit une visite le {date_prevue} ({probabilite:.1f}% de confiance) "
            f"pour '{operation_prevue}'. Niveau de risque global : {niveau_risque}.\n\n"
            f"Sur la base de ces données comportementales, propose une stratégie relationnelle concrète "
            f"pour anticiper les insatisfactions, fidéliser ce client et préparer la meilleure expérience "
            f"possible lors de sa prochaine visite en agence.\n\n"
            f"Réponds en français, percutant et factuel, sur UNE SEULE ligne :\n"
            f"Santé : [Diagnostic bref du comportement et des risques détectés] | "
            f"Stratégie : [Action commerciale concrète personnalisée]"
        )

        llm    = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=GROQ_API_KEY,
                          temperature=0.75, max_tokens=220, timeout=25, max_retries=5)
        result = (ChatPromptTemplate.from_messages([("user", "{prompt}")]) | llm).invoke({"prompt": prompt})
        raw    = result.content.strip()
        if "Santé :" not in raw:
            raw = f"Santé : Stable | Stratégie : {raw}"
        return raw

    except Exception as e:
        print(f"⚠️ Erreur LLM ({client_id}): {e}")
        strategie = _generer_strategie_comportementale(
            profil, niveau_risque, probabilite,
            operation_prevue, date_prevue, plage_horaire, rec
        )
        return f"Santé : Suivi attentif ({niveau_risque}). | Stratégie : {strategie}"


# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTANCE
# ══════════════════════════════════════════════════════════════════════════════

def _sauvegarder_analyse_db(client_id, insight, strategie):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prediction_visite
            SET insight_genai = %s, strategie_prescrite = %s
            WHERE client_id = %s
        """, (insight, strategie, client_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erreur sauvegarde Analyse DB pour client {client_id} : {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATION — Analyse d'un client
# ══════════════════════════════════════════════════════════════════════════════

def analyser_strategie_pour_client(client_id: int, prediction_data: dict = None) -> dict:
    """
    Workflow complet de l'Agent 3 :
    1. Charge le profil comportemental du client
    2. Auto-détecte les signaux d'insatisfaction depuis le comportement
    3. Génère l'insight (LLM ou déterministe) enrichi des signaux
    4. Sauvegarde la stratégie dans prediction_visite
    """
    if not prediction_data:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT client_id, score_probabilite_global, operation_prevue, date_prevue,
                       plage_horaire_prevue, niveau_risque
                FROM prediction_visite
                WHERE client_id = %s
            """, (client_id,))
            prediction_data = cursor.fetchone()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Impossible de charger la prédiction pour le client {client_id} : {e}")
            return {}

    if not prediction_data:
        print(f"⚠️ Aucune prédiction trouvée pour le client {client_id}.")
        return {}

    probabilite   = prediction_data.get('score_probabilite_global', 0.0)
    op_p          = prediction_data.get('operation_prevue', 'Opération Bancaire')
    date_p        = str(prediction_data.get('date_prevue', ''))
    time_p        = prediction_data.get('plage_horaire_prevue', '')
    niveau_risque = prediction_data.get('niveau_risque', 'FAIBLE')

    profil      = _get_profil_client(client_id)
    derniere_op = _get_derniere_operation_reelle(client_id)
    type_op     = derniere_op["type_op"]
    montant     = derniere_op["montant"]

    # ── AUTO-DÉTECTION des signaux d'insatisfaction ───────────────────────────
    signaux = _detecter_signaux_reclamation(profil, niveau_risque)
    nb_sig  = signaux.get("nb_signaux", 0)
    urgence = signaux.get("urgence", "FAIBLE")
    if nb_sig > 0:
        print(f"   🔍 Client {client_id} : {nb_sig} signal(s) auto-détecté(s) [{urgence}] → {signaux['types']}")

    # ── Génération de l'insight ───────────────────────────────────────────────
    insight = _generer_insight_llm(
        client_id, type_op, montant, probabilite,
        op_p, date_p, time_p,
        profil=profil, niveau_risque=niveau_risque,
        signaux_rec=signaux
    )

    # ── Extraction de la stratégie depuis le retour LLM ──────────────────────
    final_strategie = ""
    if "Stratégie :" in insight:
        try:
            parts           = insight.split("Stratégie :")
            final_strategie = parts[1].strip()
            insight_clean   = parts[0].replace("Santé :", "").strip().rstrip("|").strip()
            insight         = insight_clean
        except Exception:
            pass

    if not final_strategie:
        final_strategie = _generer_strategie_comportementale(
            profil, niveau_risque, probabilite, op_p, date_p, time_p, signaux
        )

    _sauvegarder_analyse_db(client_id, insight, final_strategie)
    print(f"✅ [Agent 3] Client {client_id} | Urgence: {urgence} | Stratégie : {final_strategie[:60]}...")
    return {
        "client_id":           client_id,
        "insight_genai":       insight,
        "strategie_prescrite": final_strategie,
        "signaux_detectes":    signaux,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BATCH — Traitement de tous les clients en attente
# ══════════════════════════════════════════════════════════════════════════════

def run_batch_strategies(force_all=False) -> tuple:
    print("🚀 [Agent 3] Début de la génération des stratégies (Batch)...")
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if force_all:
            cursor.execute("""
                SELECT client_id, score_probabilite_global, operation_prevue, date_prevue,
                       plage_horaire_prevue, niveau_risque
                FROM prediction_visite
            """)
        else:
            cursor.execute("""
                SELECT client_id, score_probabilite_global, operation_prevue, date_prevue,
                       plage_horaire_prevue, niveau_risque
                FROM prediction_visite
                WHERE insight_genai = 'Analyse IA en attente...' OR insight_genai IS NULL
            """)
        predictions = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erreur DB Agent 3 : {e}")
        return 0, 0

    total = len(predictions)
    print(f"📊 Clients à analyser : {total}")
    nb_ok = nb_ko = 0

    for p in predictions:
        try:
            analyser_strategie_pour_client(p['client_id'], p)
            nb_ok += 1
        except Exception as e:
            nb_ko += 1
            print(f"⚠️ Erreur Agent 3 sur client {p['client_id']}: {e}")

    print(f"✅ [Agent 3] Terminé. Réussites: {nb_ok}, Échecs: {nb_ko}")
    return nb_ok, nb_ko


if __name__ == "__main__":
    run_batch_strategies()
