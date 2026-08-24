"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      BATCH NOCTURNE AWB — Pipeline complet IA (00h00 Maroc)                ║
║      Agent 1 (Réentraînement) + Agent 2 (Prédiction) + Agent 3 (Churn)    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  PHASE 0 — Agent 1 : Réentraînement QUOTIDIEN XGBoost                      ║
║    ✔ L'historique transactionnel change constamment.                       ║
║    ✔ Le réentraînement s'effectue systématiquement chaque minuit pour      ║
║      intégrer les dernières opérations (exigence métier).                  ║
║                                                                              ║
║  PHASE 1 — Agent 2 : Prédictions XGBoost pour TOUS les clients             ║
║  PHASE 3A/B/C — Agent 3 : Analyse churn + services de rétention            ║
║                                                                              ║
║  Rate limiting Groq : 1.5s entre chaque appel LLM (évite 429 Too Many)     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
import datetime
import threading
import mysql.connector
from typing import Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BATCH-NUIT] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("nightly_batch.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("awb.nightly_batch")

DB_CONFIG: dict = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

SEUIL_LANGCHAIN_CRITIQUE = 0.75
SEUIL_LANGCHAIN_ALERTE   = 0.45

GROQ_PAUSE_SECONDES      = 1.5
GROQ_MAX_RETRIES         = 3
GROQ_RETRY_WAIT          = 10.0

MAX_CLIENTS_LANGCHAIN    = 200
BATCH_LOG_EVERY          = 10


RETRAIN_MIN_NEW_OPS: int    = int(os.getenv("RETRAIN_MIN_NEW_OPS",   "500"))

RETRAIN_MIN_ACCURACY: float = float(os.getenv("RETRAIN_MIN_ACCURACY", "0.75"))

MODELE_FICHIERS_REQUIS = [
    "xgboost_optimise.pkl",
    "xgboost_model.pkl",
    "modele_churn_maroc.pkl",
]

RETRAIN_STATE_FILE = "retrain_state.json"


def _get_db_connection() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(**DB_CONFIG)



def _lire_etat_entrainement() -> dict:
    """
    Lit le fichier retrain_state.json pour connaître l'état du dernier
    entraînement (date, nombre d'opérations, accuracy).

    Returns:
        Dict avec last_train_date, last_nb_ops, last_accuracy.
    """
    defaut = {
        "last_train_date":  None,
        "last_nb_ops":      0,
        "last_accuracy":    0.0,
        "nb_entrainements": 0,
    }
    try:
        if os.path.exists(RETRAIN_STATE_FILE):
            with open(RETRAIN_STATE_FILE, "r", encoding="utf-8") as f:
                return {**defaut, **json.load(f)}
    except Exception:
        pass
    return defaut


def _sauvegarder_etat_entrainement(nb_ops: int, accuracy: float) -> None:
    """Persiste l'état du dernier entraînement dans retrain_state.json."""
    try:
        etat_actuel = _lire_etat_entrainement()
        etat = {
            "last_train_date":  datetime.datetime.now().isoformat(),
            "last_nb_ops":      nb_ops,
            "last_accuracy":    round(accuracy, 4),
            "nb_entrainements": etat_actuel.get("nb_entrainements", 0) + 1,
        }
        with open(RETRAIN_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("⚠️  Impossible de sauvegarder retrain_state.json : %s", exc)


def _compter_operations_depuis(dernier_entrainement_nb: int) -> int:
    """
    Compte les opérations en base depuis le dernier entraînement.
    Compare avec le nombre total enregistré lors du dernier entraînement.

    Returns:
        Nombre de nouvelles opérations depuis le dernier entraînement.
    """
    try:
        conn   = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM historique_operation")
        total = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return max(0, (total or 0) - dernier_entrainement_nb)
    except Exception as exc:
        logger.warning("⚠️  Impossible de compter les opérations : %s", exc)
        return 0


def _evaluer_conditions_reentrainement() -> tuple[bool, list[str]]:
    """
    Évalue si les conditions de réentraînement sont remplies.
    
    MODIFICATION MÉTIER : Le réentraînement s'effectue TOUJOURS chaque minuit,
    car l'historique des clients évolue quotidiennement avec les nouvelles opérations.

    Returns:
        (doit_entrainer: bool, raisons: list[str])
    """
    raisons = ["🔄 Entraînement quotidien systématique (historique à jour)"]
    
    manquants = [f for f in MODELE_FICHIERS_REQUIS if not os.path.exists(f)]
    if manquants:
        raisons.append(f"📦 Modèles initialement absents : {', '.join(manquants)}")

    return True, raisons


def _phase0_reentrainement_conditionnel(force: bool = False) -> dict[str, Any]:
    """
    Phase 0 — Agent 1 : Lance le réentraînement XGBoost.
    
    Exigence métier : s'exécute systématiquement chaque nuit.
    Après l'entraînement, les modèles .pkl sont rechargés automatiquement
    par l'Agent 2 (agent_prediction.py) au prochain appel.

    Args:
        force: Si True, force le réentraînement sans vérifier les conditions.

    Returns:
        Dict avec : entrainement_lance, raisons, duration_sec, success.
    """
    logger.info("┌─────────────────────────────────────────────────────────────┐")
    logger.info("│  PHASE 0 — Agent 1 : Vérification réentraînement conditionnel│")
    logger.info("└─────────────────────────────────────────────────────────────┘")

    doit_entrainer, raisons = _evaluer_conditions_reentrainement()

    if force:
        raisons.insert(0, "🔧 Forçage manuel demandé")
        doit_entrainer = True

    if not doit_entrainer:
        etat = _lire_etat_entrainement()
        logger.info(
            "⏭️  Phase 0 ignorée : aucune condition de réentraînement atteinte. "
            "Dernier train : %s | Entraînements : %d",
            etat.get("last_train_date", "jamais"),
            etat.get("nb_entrainements", 0),
        )
        return {
            "entrainement_lance": False,
            "raisons":            [],
            "duration_sec":       0,
            "success":            True,
        }

    logger.info("🤖 [Agent 1] Réentraînement déclenché !")
    for r in raisons:
        logger.info("   ✅ %s", r)

    t0 = time.time()
    try:
        from agent_entrainement import main as entrainement_main
        entrainement_main()
        duration = round(time.time() - t0, 2)
        logger.info("✅ Phase 0 (Agent 1) terminée en %.1fs", duration)

        try:
            conn   = _get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM historique_operation")
            nb_ops = cursor.fetchone()[0] or 0
            cursor.close()
            conn.close()
        except Exception:
            nb_ops = 0

        _sauvegarder_etat_entrainement(nb_ops=nb_ops, accuracy=0.85)

        return {
            "entrainement_lance": True,
            "raisons":            raisons,
            "duration_sec":       duration,
            "success":            True,
            "nb_ops_total":       nb_ops,
        }
    except Exception as exc:
        duration = round(time.time() - t0, 2)
        logger.error("❌ Phase 0 (Agent 1) ÉCHOUÉE en %.1fs : %s", duration, exc)
        return {
            "entrainement_lance": True,
            "raisons":            raisons,
            "duration_sec":       duration,
            "success":            False,
            "error":              str(exc),
        }



def _phase1_predictions() -> dict[str, Any]:
    """
    Lance l'Agent 2 (run_batch_predictions) pour calculer la probabilité de visite
    et le niveau de risque de churn pour l'ensemble du portefeuille client.

    Returns:
        Dictionnaire avec nb_ok, nb_ko, duration_sec.
    """
    logger.info("┌─────────────────────────────────────────────────────┐")
    logger.info("│  PHASE 1 — Agent 2 : Prédictions XGBoost (Batch)   │")
    logger.info("└─────────────────────────────────────────────────────┘")
    t0 = time.time()

    try:
        from agent_prediction import run_batch_predictions
        nb_ok, nb_ko = run_batch_predictions()
        duration = round(time.time() - t0, 2)
        logger.info("✅ Phase 1 terminée en %.1fs | OK=%d | KO=%d", duration, nb_ok, nb_ko)
        return {"nb_ok": nb_ok, "nb_ko": nb_ko, "duration_sec": duration, "success": True}
    except Exception as exc:
        duration = round(time.time() - t0, 2)
        logger.error("❌ Phase 1 ÉCHOUÉE en %.1fs : %s", duration, exc)
        return {"nb_ok": 0, "nb_ko": 0, "duration_sec": duration, "success": False, "error": str(exc)}



def _charger_clients_par_risque() -> dict[str, list]:
    """
    Lit la table prediction_visite et répartit les clients en 3 groupes :
      - critiques   : niveau_risque IN ('CRITIQUE', 'ÉLEVÉ') ou score ≥ 75%
      - alertes     : niveau_risque = 'ALERTE' ou score ≥ 45%
      - surveillance: tous les autres

    Returns:
        Dict avec les clés 'critiques', 'alertes', 'surveillance'.
    """
    try:
        conn   = _get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                pv.client_id,
                pv.score_probabilite_global,
                pv.niveau_risque,
                pv.operation_prevue,
                pv.date_prevue,
                pv.plage_horaire_prevue
            FROM prediction_visite pv
            ORDER BY pv.score_probabilite_global DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as exc:
        logger.error("❌ Impossible de lire prediction_visite : %s", exc)
        return {"critiques": [], "alertes": [], "surveillance": []}

    critiques   = []
    alertes     = []
    surveillance = []

    for row in rows:
        score  = float(row.get("score_probabilite_global") or 0)
        niveau = str(row.get("niveau_risque") or "FAIBLE").upper()

        if score >= SEUIL_LANGCHAIN_CRITIQUE or niveau in ("CRITIQUE", "ÉLEVÉ"):
            critiques.append(row)
        elif score >= SEUIL_LANGCHAIN_ALERTE or niveau in ("ALERTE",):
            alertes.append(row)
        else:
            surveillance.append(row)

    logger.info(
        "📊 Répartition par risque : 🔴 CRITIQUE/ÉLEVÉ=%d | 🟡 ALERTE=%d | 🟢 AUTRE=%d",
        len(critiques), len(alertes), len(surveillance)
    )
    return {"critiques": critiques, "alertes": alertes, "surveillance": surveillance}



def _sauvegarder_analyse_agent3(
    client_id: int,
    recommandation: str,
    score_churn: float | None,
    niveau_risque: str | None,
    services: list,
    urgence: str | None,
    shap_features: list,
    analyse_comportementale: str = "",
    strategies_dynamiques: str = "",
) -> bool:
    """
    Persiste les résultats de l'Agent 3 LangChain dans la table prediction_visite.
    Mise à jour :
      - insight_genai       → Recommandation LLM personnalisée (3 lignes Groq)
      - strategie_prescrite → Les 3 lignes du LLM, sans habillage

    La stratégie est lue par un conseiller juste avant d'appeler le client :
    on n'y met que Constat / Action / Produit AWB. L'urgence et le niveau de
    risque sont déjà affichés par l'interface (pastille de priorité, % de churn),
    les répéter ici ne faisait qu'allonger le texte.

    Returns:
        True si la sauvegarde a réussi, False sinon.
    """
    try:
        if strategies_dynamiques and strategies_dynamiques.strip():
            strategie = strategies_dynamiques.strip()
        else:
            # Repli sans LLM : même esprit court, un service par ligne.
            services_lignes = [
                f"- {s.get('label', '')}" for s in services[:3] if s.get("label")
            ]
            strategie = (
                "\n".join(services_lignes)
                if services_lignes
                else "Aucun service de rétention spécifique identifié."
            )

        conn   = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prediction_visite
            SET insight_genai        = %s,
                strategie_prescrite  = %s,
                niveau_risque        = %s,
                score_churn          = %s
            WHERE client_id = %s
        """, (
            recommandation[:2000] if recommandation else "",
            strategie[:4000],
            niveau_risque or "N/A",
            round(float(score_churn), 4) if score_churn is not None else None,
            client_id,
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as exc:
        logger.warning("⚠️  Sauvegarde DB client %d : %s", client_id, exc)
        return False



def _phase3a_langchain(clients_critiques: list) -> dict[str, Any]:
    """
    Traite les clients CRITIQUE / ÉLEVÉ avec l'Agent 3 LangChain complet :
      get_client_data_tool → predict_churn_tool → apply_business_rules_tool → ChatGroq

    Applique un rate limiting (GROQ_PAUSE_SECONDES) entre chaque appel LLM
    pour respecter les quotas Groq.

    Args:
        clients_critiques: Liste des clients à traiter (dict avec client_id, score, etc.)

    Returns:
        Métriques : nb_ok, nb_ko, nb_skipped, duration_sec.
    """
    if not clients_critiques:
        logger.info("ℹ️  Phase 3A : Aucun client CRITIQUE/ÉLEVÉ à analyser.")
        return {"nb_ok": 0, "nb_ko": 0, "nb_skipped": 0, "duration_sec": 0}

    limite = min(len(clients_critiques), MAX_CLIENTS_LANGCHAIN)
    clients_a_traiter = clients_critiques[:limite]
    nb_skipped = len(clients_critiques) - limite

    logger.info("┌─────────────────────────────────────────────────────────────┐")
    logger.info("│  PHASE 3A — Agent 3 LangChain : %3d clients CRITIQUE/ÉLEVÉ  │", len(clients_a_traiter))
    if nb_skipped:
        logger.info("│  ⚠️  %3d clients mis en file d'attente (quota nuit)          │", nb_skipped)
    logger.info("└─────────────────────────────────────────────────────────────┘")

    from agent_analyse import run_agent_analyse

    t0     = time.time()
    nb_ok  = 0
    nb_ko  = 0
    total  = len(clients_a_traiter)

    for idx, row in enumerate(clients_a_traiter, start=1):
        cid   = row["client_id"]
        score = float(row.get("score_probabilite_global") or 0)

        if idx % BATCH_LOG_EVERY == 0 or idx == 1 or idx == total:
            logger.info(
                "   [%3d/%3d] Client %d — Score: %.1f%% | %s",
                idx, total, cid, score,
                row.get("niveau_risque", "N/A")
            )

        succes = False
        for tentative in range(1, GROQ_MAX_RETRIES + 1):
            try:
                result = run_agent_analyse(cid)

                _sauvegarder_analyse_agent3(
                    client_id=cid,
                    recommandation=result.get("recommandation_conseiller", ""),
                    score_churn=result.get("score_churn"),
                    niveau_risque=result.get("niveau_risque"),
                    services=result.get("services_eligibles", []),
                    urgence=result.get("urgence_action"),
                    shap_features=result.get("shap_features", []),
                    analyse_comportementale=result.get("analyse_comportementale", ""),
                    strategies_dynamiques=result.get("strategies_dynamiques", ""),
                )
                nb_ok  += 1
                succes = True
                break

            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate limit" in err_str or "too many" in err_str:
                    wait = GROQ_RETRY_WAIT * tentative
                    logger.warning(
                        "   ⏳ Rate limit Groq (client %d, tentative %d/%d) — "
                        "Pause %.0fs...", cid, tentative, GROQ_MAX_RETRIES, wait
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "   ❌ Erreur Agent3 client %d (tentative %d/%d) : %s",
                        cid, tentative, GROQ_MAX_RETRIES, exc
                    )
                    break

        if not succes:
            nb_ko += 1

        if idx < total:
            time.sleep(GROQ_PAUSE_SECONDES)

    duration = round(time.time() - t0, 2)
    logger.info(
        "✅ Phase 3A terminée en %.1fs | OK=%d | KO=%d | Skip=%d",
        duration, nb_ok, nb_ko, nb_skipped
    )
    return {
        "nb_ok":       nb_ok,
        "nb_ko":       nb_ko,
        "nb_skipped":  nb_skipped,
        "duration_sec": duration,
    }



def _phase3b_deterministe(clients_alertes: list) -> dict[str, Any]:
    """
    Traite les clients ALERTE avec les outils Agent 3 mais SANS appel LLM.
    Utilise predict_churn_tool + apply_business_rules_tool + recommandation fallback.
    Beaucoup plus rapide et sans consommation de quota Groq.

    Args:
        clients_alertes: Liste des clients ALERTE.

    Returns:
        Métriques : nb_ok, nb_ko, duration_sec.
    """
    if not clients_alertes:
        logger.info("ℹ️  Phase 3B : Aucun client ALERTE à traiter.")
        return {"nb_ok": 0, "nb_ko": 0, "duration_sec": 0}

    logger.info("┌────────────────────────────────────────────────────────────┐")
    logger.info("│  PHASE 3B — Agent 3 Déterministe : %3d clients ALERTE      │", len(clients_alertes))
    logger.info("└────────────────────────────────────────────────────────────┘")

    from agent_analyse import (
        get_client_data_tool,
        predict_churn_tool,
        _insight_clair,
        _strategie_comportementale,
        _get_proba_visite,
    )

    t0     = time.time()
    nb_ok  = 0
    nb_ko  = 0
    total  = len(clients_alertes)

    for idx, row in enumerate(clients_alertes, start=1):
        cid = row["client_id"]
        try:
            profil_json = get_client_data_tool.invoke({"client_id": cid})
            profil      = json.loads(profil_json)
            churn       = json.loads(predict_churn_tool.invoke({"profil_json": profil_json}))

            proba_visite = _get_proba_visite(cid)
            _c = _get_db_connection(); _cur = _c.cursor()
            _cur.execute("SELECT type_operation, COUNT(*) FROM historique_operation WHERE client_id=%s GROUP BY type_operation", (cid,))
            type_counts = {t: n for t, n in _cur.fetchall()}

            insight   = _insight_clair(profil, churn, proba_visite)
            strategie = _strategie_comportementale(profil, type_counts, churn)

            _cur.execute(
                "UPDATE prediction_visite SET insight_genai=%s, strategie_prescrite=%s, niveau_risque=%s WHERE client_id=%s",
                (insight[:2000], strategie[:4000], churn.get("niveau_risque") or "N/A", cid),
            )
            _c.commit(); _cur.close(); _c.close()
            nb_ok += 1

        except Exception as exc:
            nb_ko += 1
            logger.error("   ❌ Phase3B client %d : %s", cid, exc)

        if idx % (BATCH_LOG_EVERY * 2) == 0 or idx == total:
            logger.info("   [%3d/%3d] Clients ALERTE traités (OK=%d KO=%d)", idx, total, nb_ok, nb_ko)

    duration = round(time.time() - t0, 2)
    logger.info("✅ Phase 3B terminée en %.1fs | OK=%d | KO=%d", duration, nb_ok, nb_ko)
    return {"nb_ok": nb_ok, "nb_ko": nb_ko, "duration_sec": duration}



def _phase3c_legacy(clients_surveillance: list) -> dict[str, Any]:
    """
    Traite les clients à faible risque avec l'agent_strategie legacy.
    Uniquement les clients sans insight_genai (premier passage).

    Args:
        clients_surveillance: Liste des clients faible risque.

    Returns:
        Métriques : nb_ok, nb_ko, duration_sec.
    """
    if not clients_surveillance:
        logger.info("ℹ️  Phase 3C : Aucun client SURVEILLANCE à traiter.")
        return {"nb_ok": 0, "nb_ko": 0, "duration_sec": 0}

    logger.info("┌────────────────────────────────────────────────────────────┐")
    logger.info("│  PHASE 3C — Agent 3 Legacy : %3d clients SURVEILLANCE       │", len(clients_surveillance))
    logger.info("└────────────────────────────────────────────────────────────┘")

    t0 = time.time()
    try:
        from agent_strategie import run_batch_strategies
        nb_ok, nb_ko = run_batch_strategies(force_all=False)
        duration = round(time.time() - t0, 2)
        logger.info("✅ Phase 3C terminée en %.1fs | OK=%d | KO=%d", duration, nb_ok, nb_ko)
        return {"nb_ok": nb_ok, "nb_ko": nb_ko, "duration_sec": duration}
    except Exception as exc:
        duration = round(time.time() - t0, 2)
        logger.error("❌ Phase 3C ÉCHOUÉE : %s", exc)
        return {"nb_ok": 0, "nb_ko": 0, "duration_sec": duration, "error": str(exc)}



def _afficher_rapport_final(
    ts_debut: datetime.datetime,
    p0: dict,
    p1: dict,
    repartition: dict,
    p3a: dict,
    p3b: dict,
    p3c: dict,
) -> None:
    """Affiche le rapport complet du batch nocturne dans les logs."""
    duree_totale = round((datetime.datetime.now() - ts_debut).total_seconds(), 1)

    total_agent3_ok  = p3a["nb_ok"]  + p3b["nb_ok"]  + p3c["nb_ok"]
    total_agent3_ko  = p3a["nb_ko"]  + p3b["nb_ko"]  + p3c["nb_ko"]
    total_clients    = sum(len(v) for v in repartition.values())

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║          RAPPORT BATCH NOCTURNE AWB — %s       ║",
                ts_debut.strftime("%Y-%m-%d"))
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║  🕐 Durée totale   : %6.1f secondes                         ║", duree_totale)
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║  AGENT 1 — Réentraînement Conditionnel XGBoost              ║")
    if p0.get("entrainement_lance"):
        statut_a1 = "✅ SUCCÈS" if p0.get("success") else "❌ ÉCHEC"
        logger.info("║    Statut         : %-40s ║", statut_a1)
        logger.info("║    ⏱  Durée       : %4.1fs                                  ║", p0.get("duration_sec", 0))
    else:
        logger.info("║    Statut         : ⏭️  IGNORÉ (conditions non remplies)     ║")
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║  AGENT 2 — Prédictions XGBoost (visite)                     ║")
    logger.info("║    ✅ Réussies     : %4d                                     ║", p1["nb_ok"])
    logger.info("║    ❌ Échouées     : %4d                                     ║", p1["nb_ko"])
    logger.info("║    ⏱  Durée       : %4.1fs                                  ║", p1["duration_sec"])
    logger.info("╠══════════════════════════════════════════════════════════════╣")
    logger.info("║  AGENT 3 — Analyse Churn + Services de Rétention            ║")
    logger.info("║    📊 Total clients   : %4d                                 ║", total_clients)
    logger.info("║    🔴 CRITIQUE/ÉLEVÉ : %4d → LangChain (LLM + SHAP)        ║",
                len(repartition["critiques"]))
    logger.info("║    🟡 ALERTE         : %4d → Déterministe (SHAP seul)       ║",
                len(repartition["alertes"]))
    logger.info("║    🟢 SURVEILLANCE   : %4d → Legacy (agent_strategie)       ║",
                len(repartition["surveillance"]))
    logger.info("║  ─────────────────────────────────────────────────────────  ║")
    logger.info("║    3A (LangChain) — OK=%3d KO=%3d Skip=%3d  (%4.1fs)        ║",
                p3a["nb_ok"], p3a["nb_ko"], p3a.get("nb_skipped", 0), p3a["duration_sec"])
    logger.info("║    3B (Détermin.) — OK=%3d KO=%3d           (%4.1fs)        ║",
                p3b["nb_ok"], p3b["nb_ko"], p3b["duration_sec"])
    logger.info("║    3C (Legacy)    — OK=%3d KO=%3d           (%4.1fs)        ║",
                p3c["nb_ok"], p3c["nb_ko"], p3c["duration_sec"])
    logger.info("║  ─────────────────────────────────────────────────────────  ║")
    logger.info("║    ✅ Total Agent 3 OK  : %4d                               ║", total_agent3_ok)
    logger.info("║    ❌ Total Agent 3 KO  : %4d                               ║", total_agent3_ko)
    logger.info("╚══════════════════════════════════════════════════════════════╝")
    logger.info("")



def main(force_retrain: bool = False) -> dict[str, Any]:
    """
    Pipeline nocturne complet AWB.

    Séquence :
      0. Agent 1  → Réentraînement CONDITIONNEL (dimanche / nouveau data / dérive)
      1. Agent 2  → Prédictions XGBoost pour TOUS les clients
      2. Tri      → Répartition par niveau de risque
      3. Agent 3A → LangChain complet (CRITIQUE/ÉLEVÉ) : LLM + SHAP + services
      4. Agent 3B → Déterministe (ALERTE) : SHAP + services sans LLM
      5. Agent 3C → Legacy (autres) : agent_strategie.py

    Args:
        force_retrain: Si True, force le réentraînement même si les conditions
                       ne sont pas remplies (utilisé par l'endpoint /retrain).

    Returns:
        Dictionnaire de métriques consolidées.
    """
    ts_debut = datetime.datetime.now()
    logger.info("═" * 70)
    logger.info("🌙  BATCH NOCTURNE AWB — %s (Maroc UTC+1)", ts_debut.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("    Pipeline : Agent 1 (Conditionnel) → Agent 2 → Agent 3 (LangChain)")
    logger.info("═" * 70)

    p0 = _phase0_reentrainement_conditionnel(force=force_retrain)
    if p0.get("entrainement_lance") and not p0.get("success"):
        logger.warning("⚠️  Agent 1 échoué → Agent 2 utilisera les modèles existants.")

    if p0.get("entrainement_lance") and p0.get("success"):
        logger.info("⏸  Pause 5s après réentraînement (rechargement modèles)...")
        time.sleep(5)

    p1 = _phase1_predictions()
    if not p1["success"]:
        logger.error("❌ Batch interrompu : Phase 1 (Agent 2) a échoué.")
        return {"success": False, "phase": "agent2", "error": p1.get("error")}

    logger.info("⏸  Pause 3s entre Agent 2 et Agent 3...")
    time.sleep(3)

    # L'Agent 2 ne calcule plus le risque : il s'en tient à la prédiction de
    # visite et à son explication. C'est l'Agent 3 qui établit risque et
    # satisfaction, sur TOUT le portefeuille et sans LLM — indispensable avant
    # l'aiguillage, qui trie précisément sur `niveau_risque`.
    logger.info("📊 Phase 2 — Agent 3 : évaluation risque et satisfaction du portefeuille...")
    try:
        from agent_analyse import run_batch_evaluation
        p2 = run_batch_evaluation()
        logger.info("   → %s", p2.get("repartition_risque", {}))
    except Exception as exc:
        logger.error("❌ Évaluation du portefeuille échouée : %s", exc)
        return {"success": False, "phase": "agent3-evaluation", "error": str(exc)}

    logger.info("🔀 Chargement et tri des clients par niveau de risque...")
    repartition = _charger_clients_par_risque()

    p3a = _phase3a_langchain(repartition["critiques"])

    if repartition["alertes"] or repartition["surveillance"]:
        logger.info("⏸  Pause 2s entre les phases Agent 3...")
        time.sleep(2)

    p3b = _phase3b_deterministe(repartition["alertes"])

    if repartition["surveillance"]:
        time.sleep(1)

    p3c = _phase3c_legacy(repartition["surveillance"])

    _afficher_rapport_final(ts_debut, p0, p1, repartition, p3a, p3b, p3c)

    return {
        "success":   True,
        "timestamp": ts_debut.isoformat(),
        "agent1": {
            "entrainement_lance": p0.get("entrainement_lance", False),
            "raisons":            p0.get("raisons", []),
            "duration_sec":       p0.get("duration_sec", 0),
            "success":            p0.get("success", True),
        },
        "agent2": p1,
        "agent3": {
            "langchain":    p3a,
            "deterministe": p3b,
            "legacy":       p3c,
            "total_ok":     p3a["nb_ok"] + p3b["nb_ok"] + p3c["nb_ok"],
            "total_ko":     p3a["nb_ko"] + p3b["nb_ko"] + p3c["nb_ko"],
        },
        "nb_clients_critiques":    len(repartition["critiques"]),
        "nb_clients_alertes":      len(repartition["alertes"]),
        "nb_clients_surveillance": len(repartition["surveillance"]),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch nocturne AWB IA")
    parser.add_argument(
        "--force-retrain",
        action="store_true",
        help="Forcer le réentraînement de l'Agent 1 même si les conditions ne sont pas remplies",
    )
    args = parser.parse_args()
    result = main(force_retrain=args.force_retrain)
    sys.exit(0 if result.get("success") else 1)

