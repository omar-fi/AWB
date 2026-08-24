"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         SCHEDULER DE PRÉDICTIONS NOCTURNES — AWB IA                        ║
║         Pipeline complet IA chaque nuit à 00h00 (heure Maroc)              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Responsabilités :                                                           ║
║    1. Démarrer automatiquement avec l'application.                           ║
║    2. Attendre le prochain minuit Maroc sans recalcul au démarrage.          ║
║    3. Déclencher le batch chaque nuit à 00h00 (UTC+1 Maroc) :               ║
║         → Agent 2 : Prédictions XGBoost visite pour TOUS les clients        ║
║         → Agent 3A : LangChain LLM + SHAP (CRITIQUE/ÉLEVÉ)                 ║
║         → Agent 3B : Déterministe + SHAP (ALERTE)                           ║
║         → Agent 3C : Legacy agent_strategie (SURVEILLANCE)                  ║
║    4. Classifier chaque prédiction par horizon temporel :                    ║
║         AUJOURD_HUI / DEMAIN / CETTE_SEMAINE / CE_MOIS /                   ║
║         MOIS_PROCHAIN / PLUS_TARD                                            ║
║                                                                              ║
║  Usage — Lance le daemon manuellement :                                      ║
║    python scheduler.py                                                       ║
║                                                                              ║
║  Usage — Démarre depuis main.py (automatique au boot) :                      ║
║    from scheduler import demarrer_scheduler_background                       ║
║    demarrer_scheduler_background()                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import logging
import threading
import datetime
import signal

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("awb.scheduler")


MAROC_UTC_OFFSET_HEURES = 1

HEURE_DECLENCHEMENT = 0
MINUTE_DECLENCHEMENT = 0

ICONES_HORIZON = {
    "AUJOURD_HUI":  "🔴",
    "DEMAIN":       "🟠",
    "CETTE_SEMAINE":"🟡",
    "CE_MOIS":      "🟢",
    "MOIS_PROCHAIN":"🔵",
    "PLUS_TARD":    "⚫",
    "INCONNU":      "❓",
}

LABELS_HORIZON = {
    "AUJOURD_HUI":  "Aujourd'hui",
    "DEMAIN":       "Demain",
    "CETTE_SEMAINE":"Cette semaine (2–7j)",
    "CE_MOIS":      "Ce mois (8–30j)",
    "MOIS_PROCHAIN":"Mois prochain (31–60j)",
    "PLUS_TARD":    "Plus tard (> 60j)",
    "INCONNU":      "Date inconnue",
}



def classifier_horizon(date_prevue) -> str:
    """
    Classifie une date de prédiction en horizon temporel métier.

    Horizons
    --------
    AUJOURD_HUI   → date_prevue == aujourd'hui
    DEMAIN        → date_prevue == demain
    CETTE_SEMAINE → dans les 2 à 7 prochains jours
    CE_MOIS       → dans les 8 à 30 prochains jours
    MOIS_PROCHAIN → dans les 31 à 60 prochains jours
    PLUS_TARD     → au-delà de 60 jours
    INCONNU       → date non parsable

    Paramètres
    ----------
    date_prevue : str | datetime.date | datetime.datetime
        Date de la prédiction (format "YYYY-MM-DD" ou objet date/datetime).

    Retourne
    -------
    str : Code de l'horizon (ex: "CE_MOIS")
    """
    today = datetime.date.today()
    try:
        if isinstance(date_prevue, str):
            target = datetime.datetime.strptime(date_prevue[:10], "%Y-%m-%d").date()
        elif isinstance(date_prevue, datetime.datetime):
            target = date_prevue.date()
        elif isinstance(date_prevue, datetime.date):
            target = date_prevue
        else:
            return "INCONNU"
    except (ValueError, TypeError):
        return "INCONNU"

    delta = (target - today).days

    if delta < 0:
        return "AUJOURD_HUI"
    elif delta == 0:
        return "AUJOURD_HUI"
    elif delta == 1:
        return "DEMAIN"
    elif delta <= 7:
        return "CETTE_SEMAINE"
    elif delta <= 30:
        return "CE_MOIS"
    elif delta <= 60:
        return "MOIS_PROCHAIN"
    else:
        return "PLUS_TARD"



class PredictionScheduler:
    """
    Scheduler de prédictions nocturnes AWB.

    Ce service tourne en tâche de fond (thread daemon).
    Il se réveille chaque nuit à 00h00 (heure Maroc) et déclenche
    automatiquement le batch de prédictions pour l'ensemble du portefeuille.

    Attributs publics
    -----------------
    dernier_batch_ok  : bool    → True si le dernier batch s'est terminé sans erreur
    nb_batches_total  : int     → Nombre total de batches exécutés depuis le démarrage
    heure_dernier_run : str     → Timestamp du dernier batch (format lisible)
    """

    def __init__(self):
        self._stop_event   = threading.Event()
        self._thread       = None
        self._batch_lock   = threading.Lock()

        self.dernier_batch_ok      = None
        self.nb_batches_total      = 0
        self.heure_dernier_run     = "Jamais"

        self.dernier_batch_resultats: dict = {}


    def demarrer(self, executer_maintenant: bool = False) -> None:
        """
        Lance le scheduler en arrière-plan.

        Paramètres
        ----------
        executer_maintenant : bool
            Si True, un premier batch est lancé immédiatement au démarrage
            (sans attendre minuit). Défaut : False.
        """
        if self._thread and self._thread.is_alive():
            logger.warning("⚠️  Le scheduler est déjà actif.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._boucle_principale,
            name="AWB-Prediction-Scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("🟢 Scheduler démarré (thread daemon : AWB-Prediction-Scheduler)")

        if executer_maintenant:
            threading.Thread(
                target=self._executer_batch_complet,
                args=("DEMARRAGE",),
                daemon=True,
                name="AWB-Batch-Startup",
            ).start()

    def arreter(self) -> None:
        """Arrête proprement le scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🔴 Scheduler arrêté.")

    def executer_maintenant(self) -> None:
        """Déclenche un batch immédiat hors planning (pour tests ou rattrapage)."""
        if self._batch_lock.locked():
            logger.warning("⚠️  Un batch est déjà en cours d'exécution.")
            return
        threading.Thread(
            target=self._executer_batch_complet,
            args=("MANUEL",),
            daemon=True,
            name="AWB-Batch-Manual",
        ).start()

    def statut(self) -> dict:
        """Retourne un dictionnaire d'état du scheduler (utilisable par une API)."""
        secs = self._secondes_avant_prochain_minuit()
        h, m = divmod(int(secs / 60), 60)
        return {
            "actif":              self._thread.is_alive() if self._thread else False,
            "dernier_batch_ok":   self.dernier_batch_ok,
            "nb_batches_total":   self.nb_batches_total,
            "heure_dernier_run":  self.heure_dernier_run,
            "prochain_batch":     f"Dans {h}h {m}min (minuit Maroc)",
            "dernier_batch":      self.dernier_batch_resultats,
        }


    def _boucle_principale(self) -> None:
        """
        Boucle principale du scheduler.
        Dort jusqu'au prochain minuit Maroc, puis lance le batch,
        puis redort, etc. jusqu'au signal d'arrêt.
        """
        while not self._stop_event.is_set():
            secs = self._secondes_avant_prochain_minuit()
            hh   = int(secs // 3600)
            mm   = int((secs % 3600) // 60)
            logger.info(
                f"⏰ Prochain batch nocturne dans {hh}h {mm}min "
                f"(minuit heure Maroc — {self._heure_maroc_actuelle()})"
            )

            self._stop_event.wait(timeout=secs)

            if not self._stop_event.is_set():
                self._executer_batch_complet("MINUIT")

    def _executer_batch_complet(self, declencheur: str = "SCHEDULED") -> None:
        """
        Exécute le pipeline IA nocturne complet :
          1. Agent 2  → Prédictions XGBoost (visite) pour tous les clients
          2. Agent 3A → LangChain LLM + SHAP (clients CRITIQUE / ÉLEVÉ)
          3. Agent 3B → Déterministe + SHAP (clients ALERTE)
          4. Agent 3C → Legacy agent_strategie (clients SURVEILLANCE)

        Puis affiche la distribution par horizon temporel.
        Le verrou `_batch_lock` garantit qu'un seul batch tourne à la fois.

        Paramètres
        ----------
        declencheur : str
            Motif du déclenchement (ex: "MINUIT", "DEMARRAGE", "MANUEL").
        """
        if not self._batch_lock.acquire(blocking=False):
            logger.warning(f"⏸️  [{declencheur}] Batch ignoré : un batch est déjà en cours.")
            return

        try:
            ts_debut = datetime.datetime.now()
            logger.info("=" * 60)
            logger.info(
                f"🌙 [{declencheur}] BATCH NOCTURNE IA — "
                f"{ts_debut.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info("   Pipeline : Agent 2 (XGBoost) → Agent 3 (LangChain + SHAP)")
            logger.info("=" * 60)

            resultats = {}
            try:
                from nightly_batch import main as batch_main
                resultats = batch_main()
                self.dernier_batch_ok       = resultats.get("success", False)
                self.dernier_batch_resultats = resultats
            except Exception as e:
                logger.error(f"❌ Erreur critique batch nocturne : {e}")
                self.dernier_batch_ok        = False
                self.dernier_batch_resultats = {"success": False, "error": str(e)}
                return

            self._afficher_distribution_horizons()

            duree = (datetime.datetime.now() - ts_debut).total_seconds()
            self.nb_batches_total  += 1
            self.heure_dernier_run  = ts_debut.strftime("%Y-%m-%d %H:%M:%S")

            a2 = resultats.get("agent2", {})
            a3 = resultats.get("agent3", {})
            logger.info(
                f"✅ [{declencheur}] Batch #{self.nb_batches_total} terminé en {duree:.1f}s | "
                f"Agent2 OK={a2.get('nb_ok', '?')} | "
                f"Agent3 OK={a3.get('total_ok', '?')} KO={a3.get('total_ko', '?')}"
            )
            logger.info("=" * 60)

        finally:
            self._batch_lock.release()


    def _afficher_distribution_horizons(self) -> None:
        """
        Lit les prédictions en base et affiche leur distribution
        par horizon temporel (Aujourd'hui / Demain / Semaine / Mois…).
        """
        try:
            import mysql.connector

            conn = mysql.connector.connect(
                host=os.getenv("DB_HOST", "localhost"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "attijari_predict_db"),
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT client_id, date_prevue, score_probabilite_global, "
                "operation_prevue, niveau_risque "
                "FROM prediction_visite "
                "WHERE date_prevue IS NOT NULL "
                "ORDER BY score_probabilite_global DESC"
            )
            predictions = cursor.fetchall()
            cursor.close()
            conn.close()

        except Exception as e:
            logger.warning(f"⚠️  Impossible de lire les prédictions pour les horizons : {e}")
            return

        if not predictions:
            logger.info("📭 Aucune prédiction en base pour l'analyse des horizons.")
            return

        compteurs = {k: 0 for k in ICONES_HORIZON}
        clients_par_horizon = {k: [] for k in ICONES_HORIZON}

        for pred in predictions:
            horizon = classifier_horizon(pred.get("date_prevue"))
            compteurs[horizon] = compteurs.get(horizon, 0) + 1
            clients_par_horizon[horizon].append({
                "client_id": pred["client_id"],
                "date_prevue": str(pred.get("date_prevue", ""))[:10],
                "score": float(pred.get("score_probabilite_global", 0)),
                "operation": pred.get("operation_prevue", "?"),
                "risque": pred.get("niveau_risque", "?"),
            })

        total = len(predictions)
        logger.info(f"\n📊 DISTRIBUTION DES PRÉDICTIONS PAR HORIZON — {total} clients")
        logger.info("─" * 60)

        for horizon_code, label in LABELS_HORIZON.items():
            nb = compteurs.get(horizon_code, 0)
            if nb == 0:
                continue
            icone = ICONES_HORIZON[horizon_code]
            pct   = nb / total * 100
            barre = "█" * int(pct / 3)
            logger.info(f"   {icone} {label:<25s} : {nb:4d} clients ({pct:5.1f}%) {barre}")

        for prioritaire in ["AUJOURD_HUI", "DEMAIN"]:
            liste = clients_par_horizon.get(prioritaire, [])
            if not liste:
                continue
            icone = ICONES_HORIZON[prioritaire]
            label = LABELS_HORIZON[prioritaire]
            logger.info(f"\n   {icone} PRIORITÉ — Clients prévus {label.upper()} :")
            for c in liste[:10]:
                logger.info(
                    f"      • Client {c['client_id']:>5} | "
                    f"Score: {c['score']:5.1f}% | "
                    f"Op: {c['operation']:<25s} | "
                    f"Date: {c['date_prevue']} | "
                    f"Risque: {c['risque']}"
                )
            if len(liste) > 10:
                logger.info(f"      … et {len(liste) - 10} autres.")

        logger.info("─" * 60)


    @staticmethod
    def _heure_maroc_actuelle() -> str:
        """Retourne l'heure actuelle côté Maroc (UTC+1) au format lisible."""
        now_maroc = datetime.datetime.utcnow() + datetime.timedelta(hours=MAROC_UTC_OFFSET_HEURES)
        return now_maroc.strftime("%H:%M:%S")

    @staticmethod
    def _secondes_avant_prochain_minuit() -> float:
        """
        Calcule le nombre de secondes avant le prochain minuit (heure Maroc).

        Le calcul est basé sur UTC+1 (heure marocaine fixe) et non sur
        le fuseau local pour garantir la cohérence en cas de déploiement
        sur un serveur configuré en UTC.
        """
        now_maroc      = datetime.datetime.utcnow() + datetime.timedelta(hours=MAROC_UTC_OFFSET_HEURES)
        prochain_minuit = (now_maroc + datetime.timedelta(days=1)).replace(
            hour=HEURE_DECLENCHEMENT,
            minute=MINUTE_DECLENCHEMENT,
            second=5,
            microsecond=0,
        )
        return max(1.0, (prochain_minuit - now_maroc).total_seconds())



_SCHEDULER_INSTANCE: PredictionScheduler = None


def get_scheduler() -> PredictionScheduler:
    """Retourne l'instance singleton du scheduler (crée si inexistante)."""
    global _SCHEDULER_INSTANCE
    if _SCHEDULER_INSTANCE is None:
        _SCHEDULER_INSTANCE = PredictionScheduler()
    return _SCHEDULER_INSTANCE


def demarrer_scheduler_background(executer_maintenant: bool = False) -> PredictionScheduler:
    """
    Point d'entrée principal — à appeler depuis main.py ou tout script de démarrage.

    Lance le scheduler en tâche de fond. Si le scheduler est déjà actif,
    ne fait rien (idempotent).

    Paramètres
    ----------
    executer_maintenant : bool
        Si True, un batch initial tourne immédiatement au démarrage. Défaut : False.

    Retourne
    -------
    PredictionScheduler : L'instance active du scheduler.

    Exemple
    -------
    >>> from scheduler import demarrer_scheduler_background
    >>> sched = demarrer_scheduler_background()
    """
    scheduler = get_scheduler()
    scheduler.demarrer(executer_maintenant=executer_maintenant)
    return scheduler



def _handler_signal(sig, frame):
    """Gestion propre des signaux SIGINT (Ctrl+C) et SIGTERM."""
    logger.info("\n🛑 Signal d'arrêt reçu — arrêt du scheduler...")
    get_scheduler().arreter()
    sys.exit(0)


if __name__ == "__main__":
    """
    Mode daemon autonome.
    Lance le scheduler comme un service long-running.

    Démarrage :
        python scheduler.py

    Arrêt :
        Ctrl+C  ou  kill <PID>
    """
    signal.signal(signal.SIGINT,  _handler_signal)
    signal.signal(signal.SIGTERM, _handler_signal)

    logger.info("═" * 60)
    logger.info("🤖  AWB — SCHEDULER DE PRÉDICTIONS NOCTURNES")
    logger.info(f"   Déclenchement : chaque nuit à 00h00 (Maroc UTC+1)")
    logger.info(f"   PID           : {os.getpid()}")
    logger.info("═" * 60)

    sched = demarrer_scheduler_background(executer_maintenant=False)

    try:
        while True:
            time.sleep(1800)
            statut = sched.statut()
            logger.info(
                f"📌 STATUT | Actif: {statut['actif']} | "
                f"Batches: {statut['nb_batches_total']} | "
                f"Dernier: {statut['heure_dernier_run']} | "
                f"{statut['prochain_batch']}"
            )
    except KeyboardInterrupt:
        _handler_signal(None, None)
