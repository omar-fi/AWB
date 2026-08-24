"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         SCRIPT D'ENTRAÎNEMENT XGBOOST — CHURN / PROBABILITÉ DE VISITE       ║
║         Secteur Bancaire Maroc — AWB IA                    v2.0.0           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Auteur     : Data Science Team — AWB                                       ║
║  Objectif   : Prédire le CHURN ou la probabilité de visite d'un client      ║
║               avec les contraintes réelles du secteur bancaire marocain.    ║
║                                                                              ║
║  Nouveautés v2 :                                                             ║
║    • Features WEEKEND (est_weekend, est_samedi, est_dimanche)               ║
║    • Features HORAIRES BANCAIRES (8h–16h30) : dans_horaires_banque,         ║
║      heure_decimale, decalage_ouverture, decalage_fermeture,                ║
║      est_heure_pointe, est_fin_journee                                      ║
║    • Score de confiance minimum de 80 % (seuil sur predict_proba)           ║
║    • Validation automatique du score — alerte si < 80 %                     ║
║                                                                              ║
║  Sorties    : modele_churn_maroc.pkl (XGBClassifier sérialisé)              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Librairies : pandas, numpy, xgboost, scikit-learn, joblib, holidays        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python train_xgboost.py

Import dans un pipeline existant :
    from train_xgboost import preprocess_donnees
"""

import sys
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import holidays

from datetime import date, timedelta, datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    roc_auc_score,
)



HORIZON_FERIE_JOURS = 30     
HEURE_OUVERTURE     = 8.0      
HEURE_FERMETURE     = 16.5     
HEURE_POINTE_DEBUT  = 11.0     
HEURE_POINTE_FIN    = 14.0     
HEURE_FIN_JOURNEE   = 15.5    
SEUIL_CONFIANCE_MIN = 0.80    

VERSION_MODELE = "2.0.0-maroc-horaires-weekend"


def _log(verbose: bool, *args, **kwargs) -> None:
    """print() conditionnel : l'entraînement trace, l'inférence reste silencieuse."""
    if verbose:
        print(*args, **kwargs)


def preprocess_donnees(
    df: pd.DataFrame,
    date_col: str = "date_operation",
    heure_col: str = "heure_operation",
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Applique un Feature Engineering complet orienté calendrier et horaires
    bancaires marocains.

    La fonction enrichit le DataFrame avec 3 blocs de features :

    ┌─ BLOC A : Jours Fériés Maroc ──────────────────────────────────────────┐
    │  • est_jour_ferie             → 1 si le jour est férié (OFF)           │
    │  • jours_avant_prochain_ferie → nb jours avant prochain férié (≤30)    │
    │  • est_veille_aid             → 1 si demain = Eid al-Fitr/al-Adha      │
    └────────────────────────────────────────────────────────────────────────┘

    ┌─ BLOC B : Weekend ─────────────────────────────────────────────────────┐
    │  • est_weekend   → 1 si Samedi (5) ou Dimanche (6)                     │
    │  • est_samedi    → 1 si Samedi (les banques MA ferment à 13h le sam)   │
    │  • est_dimanche  → 1 si Dimanche (fermeture totale)                    │
    │  • jour_semaine  → 0=Lundi … 6=Dimanche (encodage ordinal)             │
    └────────────────────────────────────────────────────────────────────────┘

    ┌─ BLOC C : Horaires Bancaires (8h00 – 16h30) ───────────────────────────┐
    │  • heure_decimale        → heure en format décimal (ex: 14.5 = 14h30)  │
    │  • dans_horaires_banque  → 1 si l'opération est en horaires ouverts    │
    │  • decalage_ouverture    → nb heures depuis l'ouverture (8h00)         │
    │  • decalage_fermeture    → nb heures avant la fermeture (16h30)        │
    │  • est_heure_pointe      → 1 si entre 11h et 14h (pic d'affluence)     │
    │  • est_fin_journee       → 1 si après 15h30 (flux ralenti)             │
    └────────────────────────────────────────────────────────────────────────┘

    Paramètres
    ----------
    df : pd.DataFrame
        DataFrame d'entrée avec au minimum une colonne de dates.
    date_col : str
        Nom de la colonne de dates (défaut : 'date_operation').
    heure_col : str
        Nom de la colonne d'heures décimales (défaut : 'heure_operation').
        Si la colonne est absente, les features horaires sont mises à 0.

    Retourne
    -------
    pd.DataFrame
        DataFrame enrichi des 3 blocs de features (12 nouvelles colonnes).
    """

    if date_col not in df.columns:
        raise ValueError(
            f"Colonne '{date_col}' introuvable. "
            f"Colonnes disponibles : {list(df.columns)}"
        )

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    _log(verbose, "   📅 Bloc A : Calcul des features jours fériés Maroc...")

    annees = df[date_col].dt.year.unique().tolist()
    annees_elargi = sorted(set(annees + [a + 1 for a in annees]))
    feries_ma = holidays.Morocco(years=annees_elargi)

    mots_clefs_aid = ["eid al-fitr", "eid al-adha", "rupture", "sacrifice", "الفطر", "الأضحى"]

    def _features_feries(dt: pd.Timestamp) -> dict:
        d = dt.date()

        est_ferie = int(d in feries_ma)

        jours_avant = HORIZON_FERIE_JOURS
        for delta in range(1, HORIZON_FERIE_JOURS + 1):
            if (d + timedelta(days=delta)) in feries_ma:
                jours_avant = delta
                break

        nom_lendemain = feries_ma.get(d + timedelta(days=1), "").lower()
        est_veille = int(any(mot in nom_lendemain for mot in mots_clefs_aid))

        return {
            "est_jour_ferie": est_ferie,
            "jours_avant_prochain_ferie": jours_avant,
            "est_veille_aid": est_veille,
        }

    feats_feries = pd.DataFrame(
        df[date_col].apply(_features_feries).tolist(), index=df.index
    )

    _log(verbose, "   📅 Bloc B : Calcul des features weekend...")

    jour_semaine = df[date_col].dt.dayofweek

    feats_weekend = pd.DataFrame({
        "est_weekend": (jour_semaine >= 5).astype(int),
        "est_samedi": (jour_semaine == 5).astype(int),
        "est_dimanche": (jour_semaine == 6).astype(int),
        "jour_semaine": jour_semaine.values,
    }, index=df.index)

    _log(verbose, "   ⏰ Bloc C : Calcul des features horaires bancaires (8h–16h30)...")

    if heure_col in df.columns:
        heure_dec = df[heure_col].fillna(HEURE_OUVERTURE)
    else:
        _log(verbose, f"   ⚠️  Colonne '{heure_col}' absente → features horaires à valeurs neutres.")
        heure_dec = pd.Series(
            np.full(len(df), (HEURE_OUVERTURE + HEURE_FERMETURE) / 2.0),
            index=df.index
        )

    feats_horaires = pd.DataFrame({
        "heure_decimale": heure_dec.values,

        "dans_horaires_banque": np.where(
            feats_weekend["est_samedi"].values == 1,
            ((heure_dec >= HEURE_OUVERTURE) & (heure_dec <= 13.0)).astype(int),
            np.where(
                feats_weekend["est_dimanche"].values == 1,
                0,
                ((heure_dec >= HEURE_OUVERTURE) & (heure_dec <= HEURE_FERMETURE)).astype(int),
            )
        ),

        "decalage_ouverture": np.clip(heure_dec - HEURE_OUVERTURE, 0, None).values,

        "decalage_fermeture": np.clip(HEURE_FERMETURE - heure_dec, 0, None).values,

        "est_heure_pointe": (
            (heure_dec >= HEURE_POINTE_DEBUT) & (heure_dec <= HEURE_POINTE_FIN)
        ).astype(int),

        "est_fin_journee": (heure_dec >= HEURE_FIN_JOURNEE).astype(int),
    }, index=df.index)

    df = pd.concat([df, feats_feries, feats_weekend, feats_horaires], axis=1)

    nb_feries    = df["est_jour_ferie"].sum()
    nb_weekends  = df["est_weekend"].sum()
    nb_en_heures = df["dans_horaires_banque"].sum()
    nb_pointe    = df["est_heure_pointe"].sum()

    _log(verbose, 
        f"   ✅ Features générées :\n"
        f"      • Jours fériés       : {nb_feries}\n"
        f"      • Weekends           : {nb_weekends}\n"
        f"      • Dans horaires      : {nb_en_heures}/{len(df)}\n"
        f"      • Heures de pointe   : {nb_pointe}\n"
        f"      • Veilles d'Aïd      : {df['est_veille_aid'].sum()}"
    )
    return df



def generer_mock_data(n_clients: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Génère un DataFrame synthétique de profils clients bancaires marocains.

    La v2 ajoute une colonne `heure_operation` (format décimal) respectant
    la distribution réelle des flux en agence bancaire :
       • 70 % des opérations en horaires bancaires (8h–16h30)
       • 30 % en dehors des horaires (opérations digitales / ATM)
    Le Samedi, la borne de fermeture est ramenée à 13h.

    Colonnes générées
    -----------------
    client_id, montant_moyen, frequence_retrait, date_operation, heure_operation,
    solde_moyen, nb_operations_30j, nb_ops_hors_horaires, ratio_digital,
    anciennete_client_ans, segment_metier_enc, cible_churn

    Paramètres
    ----------
    n_clients : int   → Nombre de profils (défaut : 1000).
    seed      : int   → Reproductibilité (défaut : 42).
    """
    rng = np.random.default_rng(seed)

    date_debut = date(2023, 1, 1)
    date_fin   = date(2025, 6, 30)
    n_jours    = (date_fin - date_debut).days
    dates = [
        date_debut + timedelta(days=int(rng.integers(0, n_jours)))
        for _ in range(n_clients)
    ]

    heures_banque = rng.uniform(HEURE_OUVERTURE, HEURE_FERMETURE, size=n_clients)
    heures_hors   = rng.choice(
        np.concatenate([
            rng.uniform(0, HEURE_OUVERTURE, size=500),      
            rng.uniform(HEURE_FERMETURE, 24.0, size=500),   
        ]),
        size=n_clients,
    )
    masque_banque = rng.binomial(n=1, p=0.70, size=n_clients).astype(bool)
    heures = np.where(masque_banque, heures_banque, heures_hors).round(2)

    montant_moyen       = rng.normal(loc=6000, scale=4000, size=n_clients).clip(min=100)
    frequence_retrait   = rng.poisson(lam=6, size=n_clients).clip(min=0, max=30)
    solde_moyen         = rng.normal(loc=18000, scale=10000, size=n_clients).clip(min=0)
    nb_operations_30j   = rng.poisson(lam=5, size=n_clients).clip(min=0)
    anciennete          = rng.uniform(0.5, 15, size=n_clients).round(1)
    segment_metier_enc  = rng.choice([0, 1, 2], size=n_clients, p=[0.68, 0.22, 0.10])

    nb_ops_hors_horaires = (~masque_banque).astype(int)
    ratio_digital = (nb_ops_hors_horaires / (nb_operations_30j + 1)).round(4)

    score_churn = (
        (montant_moyen < 3500).astype(int)        
        + (frequence_retrait < 3).astype(int)      
        + (nb_operations_30j < 2).astype(int)      
        + (solde_moyen < 6000).astype(int)        
        + (anciennete < 2).astype(int)            
        + (ratio_digital > 0.5).astype(int)        
    )
    cible_churn = (score_churn >= 3).astype(int)
    bruit = rng.binomial(n=1, p=0.05, size=n_clients)
    cible_churn = np.abs(cible_churn - bruit).clip(0, 1)

    df = pd.DataFrame({
        "client_id":             [f"C{str(i+1).zfill(4)}" for i in range(n_clients)],
        "montant_moyen":         montant_moyen.round(2),
        "frequence_retrait":     frequence_retrait,
        "date_operation":        dates,
        "heure_operation":       heures,       
        "solde_moyen":           solde_moyen.round(2),
        "nb_operations_30j":     nb_operations_30j,
        "nb_ops_hors_horaires":  nb_ops_hors_horaires,
        "ratio_digital":         ratio_digital,       
        "anciennete_client_ans": anciennete,            
        "segment_metier_enc":    segment_metier_enc,
        "cible_churn":           cible_churn,
    })

    n_churn = cible_churn.sum()
    print(f"   📊 Mock data générée : {len(df)} clients")
    print(f"   🔴 Churners (1) : {n_churn}  |  🟢 Fidèles (0) : {len(df) - n_churn}")
    print(f"   ⚖️  Ratio churn : {n_churn/len(df)*100:.1f}%")
    return df


HYPERPARAMS_XGBOOST = {
    "n_estimators":     1000,
    "max_depth":        5,
    "learning_rate":    0.05,
    "subsample":        0.85,
    "colsample_bytree": 0.85,
    "min_child_weight": 5,
    "gamma":            0.05,
    "reg_alpha":        0.1,
    "reg_lambda":       1.5,
    "eval_metric":      "auc",
    "random_state":     42,
    "n_jobs":           -1,
}


def entrainer_modele(df: pd.DataFrame):
    """
    Pipeline complet pour l'entraînement XGBoost avec :
    - Feature Engineering (fériés Maroc + weekend + horaires bancaires)
    - Split stratifié 80/20
    - XGBClassifier optimisé (≥ 80 % d'accuracy visé)
    - Early stopping (50 rounds) pour éviter l'overfitting
    - Validation croisée 5-fold pour confirmer la robustesse
    - Blocage si accuracy < 80 % (exigence métier)

    Paramètres
    ----------
    df : pd.DataFrame
        DataFrame brut issu de `generer_mock_data` ou de la base réelle.

    Retourne
    -------
    tuple : (modele, X_test, y_test, feature_cols)
    """

    print("\n⚙️  Preprocessing des données...")
    df = preprocess_donnees(df, date_col="date_operation", heure_col="heure_operation")

    colonnes_a_exclure = ["client_id", "date_operation", "cible_churn"]
    feature_cols = [c for c in df.columns if c not in colonnes_a_exclure]

    print(f"\n   🧩 Features retenues ({len(feature_cols)}) :")
    for col in feature_cols:
        print(f"      • {col}")

    X = df[feature_cols].fillna(0)
    y = df["cible_churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )
    print(f"\n   ✂️  Split : {len(X_train)} train | {len(X_test)} test")
    print(f"   ⚖️  Déséquilibre train : {y_train.sum()} churners / {(y_train==0).sum()} fidèles")

    ratio_classes = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"   ⚖️  scale_pos_weight = {ratio_classes:.2f}")

    print("\n🚀 Entraînement du modèle XGBClassifier (Early Stopping activé)...")

    modele = xgb.XGBClassifier(
        **HYPERPARAMS_XGBOOST,
        scale_pos_weight=ratio_classes,
        early_stopping_rounds=50,      
    )

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train,
        test_size=0.15,
        random_state=42,
        stratify=y_train,
    )
    print(f"   ✂️  Validation interne (Early Stopping) : {len(X_val)} exemples")

    modele.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],   
        verbose=50,                 
    )

    nb_arbres_optimal = modele.best_iteration + 1
    print(f"\n   🌳 Early Stopping : meilleur arbre = #{nb_arbres_optimal}")
    print(f"      (sur {HYPERPARAMS_XGBOOST['n_estimators']} arbres max — "
          f"{HYPERPARAMS_XGBOOST['n_estimators'] - nb_arbres_optimal} arbres économisés)")

    print("\n🔁 Validation croisée 5-Fold...")
    modele_cv = xgb.XGBClassifier(
        **{k: v for k, v in HYPERPARAMS_XGBOOST.items() if k != "eval_metric"},
        scale_pos_weight=ratio_classes,
        eval_metric="logloss",
    )
    scores_cv = cross_val_score(modele_cv, X, y, cv=5, scoring="accuracy", n_jobs=-1)
    print(f"   📊 Scores CV (5 folds) : {[f'{s*100:.1f}%' for s in scores_cv]}")
    print(f"   📊 Moyenne CV          : {scores_cv.mean()*100:.2f}% ± {scores_cv.std()*100:.2f}%")

    accuracy_cv = scores_cv.mean()
    if accuracy_cv < SEUIL_CONFIANCE_MIN:
        print(
            f"\n⚠️  [AVERTISSEMENT] Accuracy CV = {accuracy_cv*100:.2f}% < {SEUIL_CONFIANCE_MIN*100:.0f}%\n"
            f"   → Le modèle ne satisfait pas le seuil de confiance métier.\n"
            f"   → Actions recommandées : augmenter n_clients, enrichir les features,\n"
            f"     affiner les hyperparamètres ou revoir la définition de la cible."
        )

    print("   ✅ Entraînement terminé.")
    return modele, X_test, y_test, feature_cols


def evaluer_modele(
    modele: xgb.XGBClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> float:
    """
    Évalue le modèle sur le jeu de test et retourne l'accuracy.

    Métriques calculées
    -------------------
    - Accuracy     : Taux de prédictions correctes
    - Precision    : Fiabilité des alertes churn
    - Recall       : Couverture des vrais churners (priorité métier)
    - F1-Score     : Compromis Precision/Recall
    - ROC-AUC      : Capacité discriminatoire globale
    - Classification Report : Détail par classe

    Bonus : affichage du seuil de confiance et prédictions incertaines filtrées.

    Retourne
    -------
    float : Accuracy sur le jeu de test (0.0 → 1.0)
    """
    y_pred  = modele.predict(X_test)
    y_proba = modele.predict_proba(X_test)[:, 1]

    accuracy  = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall    = recall_score(y_test, y_pred, zero_division=0)
    f1        = f1_score(y_test, y_pred, zero_division=0)
    auc       = roc_auc_score(y_test, y_proba)

    print("\n" + "═" * 62)
    print("📊  MÉTRIQUES D'ÉVALUATION — JEU DE TEST")
    print("═" * 62)
    status_acc = "✅" if accuracy >= SEUIL_CONFIANCE_MIN else "❌"
    print(f"   {status_acc} Accuracy  : {accuracy * 100:.2f}%  (seuil min : {SEUIL_CONFIANCE_MIN*100:.0f}%)")
    print(f"   🔍 Precision : {precision * 100:.2f}%")
    print(f"   📡 Recall    : {recall * 100:.2f}%")
    print(f"   ⚖️  F1-Score  : {f1 * 100:.2f}%")
    print(f"   📈 ROC-AUC   : {auc:.4f}")
    print("\n--- Rapport de Classification Détaillé ---")
    print(
        classification_report(
            y_test,
            y_pred,
            target_names=["Fidèle (0)", "Churner (1)"],
        )
    )
    print("═" * 62)

    masque_confiant = (y_proba >= SEUIL_CONFIANCE_MIN) | (y_proba <= (1 - SEUIL_CONFIANCE_MIN))
    nb_confiants = masque_confiant.sum()
    pct_confiants = nb_confiants / len(y_test) * 100

    if nb_confiants > 0:
        acc_confiante = accuracy_score(
            y_test[masque_confiant],
            y_pred[masque_confiant]
        )
        print(f"\n🎯 PRÉDICTIONS CONFIANTES (proba ≥ {SEUIL_CONFIANCE_MIN*100:.0f}% ou ≤ {(1-SEUIL_CONFIANCE_MIN)*100:.0f}%)")
        print(f"   → {nb_confiants}/{len(y_test)} prédictions ({pct_confiants:.1f}%)")
        print(f"   → Accuracy sur prédictions confiantes : {acc_confiante*100:.2f}%")
        status_conf = "✅" if acc_confiante >= SEUIL_CONFIANCE_MIN else "⚠️"
        print(f"   {status_conf} Seuil 80% {'ATTEINT' if acc_confiante >= SEUIL_CONFIANCE_MIN else 'NON ATTEINT'}")

    print("\n🔑 Top 8 Features les plus importantes :")
    importance_df = pd.DataFrame({
        "feature":    X_test.columns.tolist(),
        "importance": modele.feature_importances_,
    }).sort_values("importance", ascending=False).head(8)

    max_imp = importance_df["importance"].max()
    for _, row in importance_df.iterrows():
        largeur_barre = int((row["importance"] / max_imp) * 40)
        barre = "█" * largeur_barre
        print(f"   {row['feature']:35s} {barre} {row['importance']:.4f}")

    return accuracy



def sauvegarder_modele(
    modele: xgb.XGBClassifier,
    feature_cols: list,
    accuracy: float,
    chemin: str = "modele_churn_maroc.pkl",
) -> None:
    """
    Sérialise le modèle, ses métadonnées et le seuil de confiance avec joblib.

    Le payload sauvegardé contient :
        - modele              : XGBClassifier entraîné
        - feature_cols        : Liste ordonnée des features (ordre critique !)
        - seuil_confiance     : Seuil de probabilité minimum pour valider une prédiction
        - accuracy_entrainement : Score enregistré lors de l'entraînement
        - version             : Tag de version pour traçabilité
        - horaires_banque     : Dictionnaire des contraintes horaires utilisées
        - timestamp           : Horodatage de l'entraînement

    Paramètres
    ----------
    modele       : XGBClassifier entraîné
    feature_cols : Liste des colonnes features
    accuracy     : Accuracy observée sur le jeu de test
    chemin       : Chemin de sortie du fichier .pkl
    """
    payload = {
        "modele":                    modele,
        "feature_cols":              feature_cols,
        "seuil_confiance":           SEUIL_CONFIANCE_MIN,
        "accuracy_entrainement":     round(accuracy, 4),
        "version":                   VERSION_MODELE,
        "horaires_banque": {
            "ouverture":             HEURE_OUVERTURE,
            "fermeture":             HEURE_FERMETURE,
            "fermeture_samedi":      13.0,
            "dimanche_ferme":        True,
            "heure_pointe_debut":    HEURE_POINTE_DEBUT,
            "heure_pointe_fin":      HEURE_POINTE_FIN,
        },
        "timestamp": datetime.now().isoformat(),
    }

    joblib.dump(payload, chemin)
    print(f"\n💾 Modèle sauvegardé → {chemin}")
    print(f"   ├─ Accuracy enregistrée  : {accuracy * 100:.2f}%")
    print(f"   ├─ Seuil de confiance    : {SEUIL_CONFIANCE_MIN * 100:.0f}%")
    print(f"   ├─ Version               : {VERSION_MODELE}")
    print(f"   └─ Features ({len(feature_cols)})        : {feature_cols}")



def main():
    """
    Orchestre l'ensemble du pipeline d'entraînement v2.

    Étapes :
        1️⃣  Génération des données mock (profils clients bancaires marocains + heures).
        2️⃣  Feature Engineering : Fériés MA + Weekend + Horaires bancaires 8h–16h30.
        3️⃣  Split 80/20 stratifié + Entraînement XGBClassifier optimisé.
        4️⃣  Validation croisée 5-fold + Vérification seuil 80 %.
        5️⃣  Évaluation complète des métriques.
        6️⃣  Sauvegarde dans modele_churn_maroc.pkl.
    """
    print("=" * 62)
    print("🤖  PIPELINE CHURN / VISITE — AWB IA  (Maroc)  v2.0")
    print("=" * 62)
    print(f"   ⏰ Horaires bancaires : {HEURE_OUVERTURE}h → {HEURE_FERMETURE}h (Ven–Sam 8h→13h)")
    print(f"   🎯 Seuil de confiance minimum : {SEUIL_CONFIANCE_MIN*100:.0f}%")

    print("\n📦 Étape 1 — Génération des données mock...")
    df = generer_mock_data(n_clients=1200, seed=42)

    print("\n🔧 Étapes 2-4 — Feature Engineering + Entraînement + Validation...")
    modele, X_test, y_test, feature_cols = entrainer_modele(df)

    print("\n📈 Étape 5 — Évaluation complète du modèle...")
    accuracy = evaluer_modele(modele, X_test, y_test)

    print("\n" + "─" * 62)
    if accuracy >= SEUIL_CONFIANCE_MIN:
        print(f"✅  SEUIL MÉTIER ATTEINT : Accuracy = {accuracy*100:.2f}% ≥ {SEUIL_CONFIANCE_MIN*100:.0f}%")
    else:
        print(f"❌  SEUIL MÉTIER NON ATTEINT : Accuracy = {accuracy*100:.2f}% < {SEUIL_CONFIANCE_MIN*100:.0f}%")
        print("   → Le modèle NE SERA PAS sauvegardé. Revoyez la configuration.")
        sys.exit(1)  
    print("─" * 62)
    print("\n💾 Étape 6 — Sauvegarde du modèle...")
    sauvegarder_modele(modele, feature_cols, accuracy, chemin="modele_churn_maroc.pkl")

    print("\n" + "=" * 62)
    print("✅  PIPELINE TERMINÉ — Modèle prêt à l'emploi !")
    print("   → Chargement : payload = joblib.load('modele_churn_maroc.pkl')")
    print("   →              modele  = payload['modele']")
    print("   →              features = payload['feature_cols']")
    print("=" * 62)


if __name__ == "__main__":
    main()