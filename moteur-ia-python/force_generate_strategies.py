"""
force_generate_strategies.py
============================
Génère IMMÉDIATEMENT les stratégies de rétention (Agent 3 déterministe)
pour TOUS les clients qui n'ont pas encore de strategie_prescrite.

Usage :
    python force_generate_strategies.py

Sans appel LLM → rapide (quelques secondes pour des centaines de clients).
"""

import os, sys, json, time, logging, mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FORCE-STRAT] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("awb.force_strategies")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "attijari_predict_db"),
}

def _get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def _sauvegarder_strategie(client_id: int, recommandation: str, services: list,
                            urgence: str, shap_features: list, niveau_risque: str,
                            analyse_comportementale: str = "") -> bool:
    """
    Persiste la strategie dans prediction_visite.

    Meme format court que nightly_batch : le conseiller ne lit que
    Constat / Action / Produit AWB. Pas d'habillage URGENCE/SHAP, deja
    presents ailleurs dans l'interface.
    """
    try:
        services_lignes = [
            f"- {s.get('label', '')}" for s in services[:3] if s.get("label")
        ]
        strategie = (
            "\n".join(services_lignes)
            if services_lignes
            else "Aucun service de retention specifique identifie."
        )

        conn   = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prediction_visite
            SET strategie_prescrite = %s,
                insight_genai       = CASE
                    WHEN insight_genai IS NULL OR insight_genai = 'Analyse IA en attente...' OR insight_genai = ''
                    THEN %s
                    ELSE insight_genai
                END
            WHERE client_id = %s
        """, (strategie[:3000], recommandation[:2000] if recommandation else "", client_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as exc:
        logger.warning("⚠️  Sauvegarde DB client %d : %s", client_id, exc)
        return False


def main():
    logger.info("=" * 60)
    logger.info("🚀  GÉNÉRATION FORCÉE DES STRATÉGIES — Tous les clients")
    logger.info("=" * 60)

    try:
        from agent_analyse import (
            get_client_data_tool,
            predict_churn_tool,
            apply_business_rules_tool,
            _recommandation_fallback,
        )
        logger.info("✅ Outils Agent 3 chargés")
    except Exception as exc:
        logger.error("❌ Impossible de charger agent_analyse : %s", exc)
        sys.exit(1)

    try:
        conn   = _get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT pv.client_id, pv.score_probabilite_global, pv.niveau_risque
            FROM prediction_visite pv
            WHERE pv.strategie_prescrite IS NULL
               OR pv.strategie_prescrite = ''
               OR pv.strategie_prescrite LIKE '[Agent3%'
            ORDER BY pv.score_probabilite_global DESC
        """)
        clients = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info("📊 Clients sans stratégie : %d", len(clients))
    except Exception as exc:
        logger.error("❌ Erreur DB : %s", exc)
        sys.exit(1)

    if not clients:
        logger.info("✅ Tous les clients ont déjà une stratégie. Rien à faire.")
        return

    nb_ok = nb_ko = 0
    total = len(clients)

    for idx, row in enumerate(clients, 1):
        cid = row["client_id"]
        try:
            profil_json = get_client_data_tool.invoke({"client_id": cid})
            profil      = json.loads(profil_json)

            churn_json  = predict_churn_tool.invoke({"profil_json": profil_json})
            churn       = json.loads(churn_json)

            combined    = json.dumps({"churn": churn, "profil": profil})
            rules_json  = apply_business_rules_tool.invoke({"churn_et_profil_json": combined})
            rules       = json.loads(rules_json)

            recommandation = _recommandation_fallback(profil, churn, rules)

            _sauvegarder_strategie(
                client_id              = cid,
                recommandation         = recommandation,
                services               = rules.get("services_eligibles", []),
                urgence                = rules.get("urgence_action"),
                shap_features          = churn.get("top_shap_features", []),
                niveau_risque          = churn.get("niveau_risque"),
                analyse_comportementale= rules.get("analyse_comportementale", ""),
            )
            nb_ok += 1

            if idx % 10 == 0 or idx == 1 or idx == total:
                logger.info("   [%3d/%3d] Client %d ✅ — Risque: %s | Services: %d",
                            idx, total, cid,
                            churn.get("niveau_risque", "N/A"),
                            len(rules.get("services_eligibles", [])))

        except Exception as exc:
            nb_ko += 1
            logger.error("   ❌ Client %d : %s", cid, exc)

    logger.info("=" * 60)
    logger.info("✅ Terminé — OK: %d | KO: %d / %d clients", nb_ok, nb_ko, total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
