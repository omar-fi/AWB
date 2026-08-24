"""
Démo — Agent 3 en mode ReAct : le LLM orchestre lui-même les outils.

Ici, contrairement au batch nocturne (déterministe), c'est le LLM qui décide
d'appeler les outils. L'un d'eux, get_client_data_tool, passe par le serveur
MCP pour lire le profil du client. On voit donc, dans les logs, le LLM
« utiliser MCP », puis rédiger la stratégie de reconquête.

À réserver à la démonstration (quelques clients) : le batch de production
reste sur run_batch_strategies_reconquete, plus fiable et économe en appels.

Prérequis : MySQL démarré (données présentes) et GROQ_API_KEY dans .env.
Sans clé Groq, l'agent bascule sur le pipeline déterministe (sans LLM).

Usage :
    python demo_strategie_mcp.py 12 47 88   # clients précis
    python demo_strategie_mcp.py            # 3 clients ayant une réclamation
"""
import os
import sys
import logging

# Le LLM doit pouvoir appeler MCP : on force le flag AVANT d'importer l'agent.
os.environ["AGENT3_USE_MCP"] = "1"

# Niveau INFO pour voir les lignes « 🔧 [LLM tool-call] … (→ serveur MCP) »
# et « ✅ [Tool 1] Profil … capté via MCP » émises par l'agent.
logging.basicConfig(level=logging.INFO, format="   %(message)s")

from agent_analyse import run_agent_analyse, _get_db_connection  # noqa: E402


def _clients_demo(n: int = 3) -> list[int]:
    """Quelques clients ayant au moins une réclamation — les cas les plus parlants."""
    try:
        conn = _get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT client_id FROM reclamation ORDER BY client_id LIMIT %s",
            (n,))
        ids = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return ids or [1, 2, 3]
    except Exception as exc:
        print(f"⚠️  Sélection auto impossible ({exc}) — repli sur [1, 2, 3].")
        return [1, 2, 3]


def main() -> None:
    ids = [int(a) for a in sys.argv[1:]] or _clients_demo()

    print("=" * 72)
    print("DÉMO — Agent 3 : le LLM orchestre les outils (dont MCP) puis rédige")
    print("=" * 72)
    print("Repère dans les logs :")
    print("   🔧 [LLM tool-call] get_client_data_tool (→ serveur MCP)")
    print("   → c'est le LLM qui, de lui-même, appelle un outil passant par MCP.")

    for cid in ids:
        print("\n" + "─" * 72)
        print(f"▶ CLIENT {cid}")
        print("─" * 72)

        res = run_agent_analyse(cid)

        satis = res.get("satisfaction", {})
        print(f"\n  Statut satisfaction : {satis.get('statut')}")
        print(f"  Niveau de risque    : {res.get('niveau_risque')} "
              f"({res.get('probabilite_pct')} %)")
        print("\n  STRATÉGIE RÉDIGÉE PAR LE LLM :\n")
        texte = (res.get("recommandation_conseiller", "") or "").strip()
        print("  " + texte.replace("\n", "\n  "))

    print("\n" + "=" * 72)
    print("Fin de la démo. Le batch nocturne, lui, reste déterministe et intact.")
    print("=" * 72)


if __name__ == "__main__":
    main()
