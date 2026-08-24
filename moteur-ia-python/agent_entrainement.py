
"""
Agent d'Entraînement Autonome — AWB IA
========================================
Cet agent réentraîne les deux modèles XGBoost à partir de l'historique
réel des clients et de leurs comptes (including PLACEMENT & RETRAIT_EPARGNE).

Usage :
    python agent_entrainement.py

Les modèles sauvegardés :
    - xgboost_optimise.pkl  → prédit SI le client va venir (classification binaire)
    - xgboost_model.pkl     → prédit QUELLE opération le client va faire (multi-classe)
    - encoder_segment.pkl   → LabelEncoder pour segment_metier
    - encoder_motif.pkl     → LabelEncoder pour le type d'opération cible
"""

import os
import sys
import json
import asyncio
import datetime
import holidays
import joblib
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
from sqlalchemy import create_engine
from dotenv import load_dotenv
from collections import Counter
from features_visite import (colonnes_features,
                             construire_features as construire_features_visite,
                             MIN_VISITES_HISTORIQUE)

load_dotenv()

USE_MCP = os.getenv("AGENT1_USE_MCP", "1") != "0"
_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVER_SCRIPT = os.path.join(_MCP_DIR, "mcp_ia_server.py")


async def _call_mcp_tool_async(tool_name: str, args: dict) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_MCP_SERVER_SCRIPT],
        env=os.environ.copy(),
        cwd=_MCP_DIR,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result  = await session.call_tool(tool_name, args)
            content = result.content[0].text if result.content else ""
            return json.loads(content) if isinstance(content, str) else content


def _call_mcp_tool(tool_name: str, args: dict):
    try:
        return asyncio.run(_call_mcp_tool_async(tool_name, args))
    except Exception as exc:
        print(f"⚠️ [MCP] Appel '{tool_name}' échoué ({exc}). Fallback SQL direct.")
        return None

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "attijari_predict_db")

ENGINE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

ALL_OP_TYPES = [
    "RETRAIT", "VERSEMENT", "VIREMENT_EMIS", "VIREMENT_RECU",
    "PAIEMENT_FACTURE", "PAIEMENT_CARTE", "REMISE_CHEQUE",
    "Paiement TPE", "Demande de Crédit", "Retrait Guichet",
    "Versement Espèces", "Remise de Chèque", "Virement Reçu",
    "PLACEMENT", "RETRAIT_EPARGNE"
]

# Seul le canal AGENCE correspond à un déplacement du client au guichet, et
# donc à une visite. Les modèles de visite ne doivent voir que celui-là :
# entraînés sur l'ensemble des canaux, ils apprenaient le rythme transactionnel
# (1,7 jour) au lieu du rythme de passage en agence (20,9 jours) — d'où des
# visites prédites le même jour pour la moitié du portefeuille, et une
# « opération prévue » systématiquement PAIEMENT_CARTE.
CANAL_AGENCE = "AGENCE"
OPERATION_AGENCE_DEFAUT = "Retrait Guichet"

# Modèle « motif de la prochaine visite ».
MODELE_OP_VISITE_FILE   = "xgboost_operation_visite.pkl"
ENCODER_OP_VISITE_FILE  = "encoder_operation_visite.pkl"
FEATURES_OP_VISITE_FILE = "operation_visite_features.pkl"
TYPES_OP_VISITE_FILE    = "types_operation_visite.pkl"

VISITE_FEATURES_FILE = "xgboost_visite_features.pkl"

HEURE_OUVERTURE_SEMAINE = 8.0
HEURE_FERMETURE_SEMAINE = 16.5
HEURE_FERMETURE_SAMEDI = 13.0
HEURE_POINTE_DEBUT = 11.0
HEURE_POINTE_FIN = 14.0

NEXT_DATE_MODEL_FILE = "xgboost_next_date.pkl"
NEXT_TIME_MODEL_FILE = "xgboost_next_time.pkl"
NEXT_OP_MODEL_FILE = "xgboost_next_operation.pkl"
ENCODER_SEGMENT_NEXT_FILE = "encoder_segment_next.pkl"
ENCODER_TYPE_COMPTE_FILE = "encoder_type_compte.pkl"
ENCODER_NEXT_OPERATION_FILE = "encoder_next_operation.pkl"
NEXT_FEATURES_FILE = "xgboost_next_features.pkl"


def extraire_dataset(engine):
    """
    Joint historique_operation + compte + client pour construire
    un dataset par client avec des features riches.
    """
    print("📥 Extraction des données depuis MySQL...")

    if USE_MCP:
        data = _call_mcp_tool("get_training_data", {})
        if data and not data.get("error") and data.get("operations") is not None:
            df_hist = pd.DataFrame(data["operations"])
            df_client = pd.DataFrame(data["clients"])
            if "montant" in df_hist.columns:
                df_hist["montant"] = pd.to_numeric(df_hist["montant"], errors="coerce")
            for col in ["solde_total", "solde_moyen_compte", "has_compte_epargne",
                        "nb_comptes", "nb_comptes_courant", "nb_comptes_epargne", "nb_comptes_credit"]:
                if col in df_client.columns:
                    df_client[col] = pd.to_numeric(df_client[col], errors="coerce")
            print(f"   → {len(df_hist)} opérations brutes (via MCP)")
            print(f"   → {len(df_client)} clients (via MCP)")
            return df_hist, df_client
        print("   ⚠️ MCP indisponible — bascule sur l'accès SQL direct (engine).")

    df_hist = pd.read_sql("SELECT * FROM historique_operation", con=engine)
    print(f"   → {len(df_hist)} opérations brutes")

    df_client = pd.read_sql("""
        SELECT
            cl.id                                                        AS client_id,
            cl.segment_metier,
            COALESCE(SUM(co.solde), 0)                                   AS solde_total,
            MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_compte_epargne,
            AVG(co.solde)                                                AS solde_moyen_compte,
            COUNT(co.id)                                                 AS nb_comptes,
            SUM(CASE WHEN co.type_compte = 'COURANT' THEN 1 ELSE 0 END)  AS nb_comptes_courant,
            SUM(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END)  AS nb_comptes_epargne,
            SUM(CASE WHEN co.type_compte = 'CREDIT' THEN 1 ELSE 0 END)   AS nb_comptes_credit
        FROM client cl
        LEFT JOIN compte co ON cl.id = co.client_id
        GROUP BY cl.id, cl.segment_metier
    """, con=engine)
    print(f"   → {len(df_client)} clients")

    return df_hist, df_client


def _ajouter_features_calendrier_operation(df_hist):
    """
    Ajoute les signaux calendrier/agence sur chaque opération.
    On ne supprime pas les week-ends ni les jours fériés : ils deviennent
    des signaux appris par XGBoost.
    """
    df = df_hist.copy()
    df["date_heure_operation"] = pd.to_datetime(df["date_heure_operation"], errors="coerce")
    df = df.dropna(subset=["date_heure_operation"])

    annees = sorted(df["date_heure_operation"].dt.year.dropna().astype(int).unique().tolist())
    feries_ma = holidays.Morocco(years=annees) if annees else holidays.Morocco()

    dt = df["date_heure_operation"]
    heure = dt.dt.hour + dt.dt.minute / 60.0
    jour = dt.dt.dayofweek

    df["heure_decimale"] = heure
    df["jour_semaine"] = jour
    df["est_samedi"] = (jour == 5).astype(int)
    df["est_dimanche"] = (jour == 6).astype(int)
    df["est_weekend"] = (jour >= 5).astype(int)
    df["est_jour_ferie"] = dt.dt.date.map(lambda d: int(d in feries_ma))
    df["dans_horaires_agence"] = np.where(
        df["est_samedi"].eq(1) | df["est_dimanche"].eq(1) | df["est_jour_ferie"].eq(1),
        0,
        ((heure >= HEURE_OUVERTURE_SEMAINE) & (heure <= HEURE_FERMETURE_SEMAINE)).astype(int)
    )
    df["est_heure_pointe"] = ((heure >= HEURE_POINTE_DEBUT) & (heure <= HEURE_POINTE_FIN)).astype(int)
    return df


def entrainer_modele_operation_visite(engine):
    """
    Modèle « motif de la prochaine visite en agence ».

    Remplace la prédiction par mode (l'opération la plus fréquente du client),
    qui ne prédit rien : elle renvoyait le même motif à chaque passage.

    Unité d'observation : une visite, pas un client. Les features ne décrivent
    que le passé du client plus le calendrier de la visite ciblée — la date est
    prédite en amont par le modèle next-date, la question ici est « pour quoi ».

    Évaluation sur découpage TEMPOREL (apprentissage sur le passé, test sur le
    futur). Un découpage aléatoire mélangerait des visites postérieures du même
    client à l'apprentissage et surestimerait franchement le résultat.
    """
    print("\n🎯 Entraînement Modèle — Motif de la prochaine visite")

    df = pd.read_sql(f"""
        SELECT h.client_id, h.date_heure_operation, h.type_operation, h.montant,
               cl.segment_metier
        FROM historique_operation h
        JOIN client cl ON cl.id = h.client_id
        WHERE h.canal = '{CANAL_AGENCE}'
        ORDER BY h.client_id, h.date_heure_operation
    """, con=engine)
    if len(df) < 200:
        print(f"   ⚠️ Trop peu de visites en agence ({len(df)}) — modèle ignoré.")
        return

    df["date_heure_operation"] = pd.to_datetime(df["date_heure_operation"])
    types = sorted(df["type_operation"].dropna().unique())
    enc_op = LabelEncoder().fit(types)
    enc_seg = LabelEncoder().fit(df["segment_metier"].fillna("Particulier"))
    colonnes = colonnes_features(types)

    lignes, cibles, dates, modes_glissants = [], [], [], []
    for _, ops in df.groupby("client_id"):
        ops = ops.sort_values("date_heure_operation").reset_index(drop=True)
        if len(ops) < MIN_VISITES_HISTORIQUE + 2:
            continue
        seg = int(enc_seg.transform([ops.iloc[0]["segment_metier"] or "Particulier"])[0])
        compteurs, historique = Counter(), []

        for i in range(len(ops) - 1):
            courante, suivante = ops.iloc[i], ops.iloc[i + 1]
            compteurs[courante["type_operation"]] += 1
            historique.append((courante["date_heure_operation"], courante["type_operation"]))

            f = construire_features_visite(seg, suivante["date_heure_operation"],
                                           historique, compteurs, enc_op, types)
            if f is None:
                continue
            f["montant_precedent"] = float(courante["montant"] or 0)
            lignes.append([f[c] for c in colonnes])
            cibles.append(int(enc_op.transform([suivante["type_operation"]])[0]))
            dates.append(suivante["date_heure_operation"])
            modes_glissants.append(int(enc_op.transform([compteurs.most_common(1)[0][0]])[0]))

    X = pd.DataFrame(lignes, columns=colonnes)
    y = pd.Series(cibles)
    dates = pd.Series(dates)
    modes_glissants = pd.Series(modes_glissants)
    print(f"   {len(X):,} visites exploitables — {y.nunique()} motifs distincts")

    seuil = dates.quantile(0.80)
    train, test = dates <= seuil, dates > seuil
    if test.sum() < 50 or y[train].nunique() < y.nunique():
        print("   ⚠️ Découpage temporel insuffisant — apprentissage sur tout l'historique.")
        train, test = pd.Series(True, index=y.index), pd.Series(False, index=y.index)

    modele = xgb.XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.8,
        objective="multi:softprob", eval_metric="mlogloss", random_state=42,
    )
    modele.fit(X[train], y[train])

    if test.sum() > 0:
        pred = modele.predict(X[test])
        acc = float((pred == y[test]).mean())
        proba = modele.predict_proba(X[test])
        top3 = modele.classes_[np.argsort(-proba, axis=1)[:, :3]]
        acc3 = float(np.mean([v in ligne for v, ligne in zip(y[test], top3)]))
        base_maj = float((y[test] == y[train].value_counts().idxmax()).mean())
        base_mode = float((modes_glissants[test] == y[test]).mean())
        meilleure = max(base_maj, base_mode)
        print(f"   Test sur {int(test.sum()):,} visites postérieures au {seuil.date()}")
        print(f"      base « classe majoritaire »   : {100*base_maj:5.1f} %")
        print(f"      base « mode du client »       : {100*base_mode:5.1f} %")
        print(f"      ✅ modèle                      : {100*acc:5.1f} %  "
              f"({100*(acc-meilleure):+.1f} pts)  |  top-3 : {100*acc3:5.1f} %")
        if acc <= meilleure:
            print("      ⚠️ Le modèle n'apporte rien face aux règles simples.")

    joblib.dump(modele, MODELE_OP_VISITE_FILE)
    joblib.dump(enc_op, ENCODER_OP_VISITE_FILE)
    joblib.dump(colonnes, FEATURES_OP_VISITE_FILE)
    joblib.dump({"types": types, "encoder_segment": enc_seg}, TYPES_OP_VISITE_FILE)
    print(f"   💾 Sauvegardés : {MODELE_OP_VISITE_FILE} + encodeurs + features")


def _operation_agence_dominante(df_hist):
    """
    Opération de guichet la plus fréquente, par client.

    Ne considère que le canal AGENCE : c'est ce que le client vient faire au
    guichet, et donc la seule chose qu'on puisse annoncer au conseiller comme
    motif de sa prochaine visite.

    Repli sur « Retrait Guichet » pour les clients sans aucun passage en
    agence — motif de visite le plus courant, et surtout plausible.
    """
    if "canal" not in df_hist.columns:
        raise KeyError(
            "historique_operation.canal est absent : impossible de distinguer "
            "les visites en agence des opérations à distance."
        )
    en_agence = df_hist[df_hist["canal"] == CANAL_AGENCE]
    return (en_agence.groupby("client_id")["type_operation"]
            .agg(lambda x: x.mode()[0] if len(x) > 0 else OPERATION_AGENCE_DEFAUT)
            .rename("operation_plus_frequente")
            .reset_index())


def construire_features(df_hist, df_client):
    """
    Feature Engineering :
      - Statistiques agrégées par client (nb ops, montant, moyenne)
      - Pivot sur les types d'opération (dont PLACEMENT & RETRAIT_EPARGNE)
      - Jointure avec le profil client (segment, solde, has_epargne)
    """
    print("⚙️  Feature Engineering...")
    df_hist = _ajouter_features_calendrier_operation(df_hist)

    df_agg = df_hist.groupby("client_id").agg(
        nombre_operations=("id", "count"),
        montant_total=("montant", "sum"),
        montant_moyen=("montant", "mean"),
        moy_retrait=("montant", lambda x: x[df_hist.loc[x.index, "type_operation"] == "RETRAIT"].mean()),
        nb_ops_30j=("date_heure_operation",
                    lambda x: (pd.to_datetime(x) >= pd.Timestamp.now() - pd.Timedelta(days=30)).sum()),
        nb_ops_weekend=("est_weekend", "sum"),
        nb_ops_samedi=("est_samedi", "sum"),
        nb_ops_dimanche=("est_dimanche", "sum"),
        nb_ops_ferie=("est_jour_ferie", "sum"),
        nb_ops_hors_horaires=("dans_horaires_agence", lambda x: (x == 0).sum()),
        nb_ops_heure_pointe=("est_heure_pointe", "sum"),
        heure_moyenne_operation=("heure_decimale", "mean"),
        heure_derniere_operation=("heure_decimale", "last"),
        dernier_jour_semaine=("jour_semaine", "last"),
        derniere_est_weekend=("est_weekend", "last"),
        derniere_est_ferie=("est_jour_ferie", "last"),
        derniere_dans_horaires_agence=("dans_horaires_agence", "last"),
        derniere_operation_at=("date_heure_operation", "max"),
    ).reset_index()

    # L'opération annoncée au conseiller est celle que le client vient faire AU
    # GUICHET — calculée à part, sur le seul canal AGENCE.
    df_agg = df_agg.merge(_operation_agence_dominante(df_hist), on="client_id", how="left")
    df_agg["operation_plus_frequente"] = (
        df_agg["operation_plus_frequente"].fillna(OPERATION_AGENCE_DEFAUT))
    df_agg["moy_retrait"] = df_agg["moy_retrait"].fillna(0)
    df_agg["jours_depuis_derniere_operation"] = (
        pd.Timestamp.now() - pd.to_datetime(df_agg["derniere_operation_at"])
    ).dt.total_seconds().div(86400).clip(lower=0).fillna(999)
    df_agg = df_agg.drop(columns=["derniere_operation_at"])

    pivot = pd.crosstab(df_hist["client_id"], df_hist["type_operation"]).reset_index()
    for col in ALL_OP_TYPES:
        if col not in pivot.columns:
            pivot[col] = 0

    df = df_agg.merge(pivot, on="client_id", how="left")
    df = df.merge(df_client, on="client_id", how="left")

    df["segment_metier"] = df["segment_metier"].fillna("Particulier")
    df["has_compte_epargne"] = df["has_compte_epargne"].fillna(0).astype(int)
    df["solde_total"] = df["solde_total"].fillna(0)
    df["ratio_solde_habitude"] = df["solde_total"] / (df["moy_retrait"] + 1)
    df["ratio_ops_weekend"] = df["nb_ops_weekend"] / df["nombre_operations"].clip(lower=1)
    df["ratio_ops_ferie"] = df["nb_ops_ferie"] / df["nombre_operations"].clip(lower=1)
    df["ratio_ops_hors_horaires"] = df["nb_ops_hors_horaires"] / df["nombre_operations"].clip(lower=1)
    for col in ["nb_comptes", "nb_comptes_courant", "nb_comptes_epargne", "nb_comptes_credit"]:
        df[col] = df[col].fillna(0)

    print(f"   → Dataset final : {df.shape[0]} lignes × {df.shape[1]} colonnes")
    return df


def entrainer_modele_visite(df):
    """
    Modèle 1 : Classification binaire — le client va-t-il venir ? (xgboost_optimise.pkl)
    Cible : 1 si le client a > médiane d'opérations ET > médiane de montant total
    """
    print("\n🎯 Entraînement Modèle 1 — Prédiction de Visite (xgboost_optimise.pkl)")

    composite = (
        0.35 * df["nb_ops_30j"].rank(pct=True)
        + 0.25 * (-df["jours_depuis_derniere_operation"]).rank(pct=True)
        + 0.20 * df["nombre_operations"].rank(pct=True)
        + 0.20 * df["montant_total"].rank(pct=True)
    )
    propension = composite.rank(pct=True)
    _rng = np.random.default_rng(42)
    df["cible_visite"] = np.clip(propension + _rng.normal(0, 0.02, len(df)), 0.02, 0.98)
    print(f"   Propension visite — min={df['cible_visite'].min():.2f} "
          f"moy={df['cible_visite'].mean():.2f} max={df['cible_visite'].max():.2f}")

    exclude = ["client_id", "cible_visite", "operation_plus_frequente", "segment_metier"]
    feature_cols = [c for c in df.columns if c not in exclude]

    X = df[feature_cols].fillna(0)
    y = df["cible_visite"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        objective="reg:logistic",
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.9, colsample_bytree=0.9,
        min_child_weight=2, reg_lambda=1.0, random_state=42
    )
    model.fit(X_train, y_train)

    pred_test = model.predict(X_test)
    mae = float(np.mean(np.abs(pred_test - y_test)))
    print(f"   ✅ MAE (test) : {mae:.3f}  |  étendue prédite : "
          f"[{pred_test.min():.2f}, {pred_test.max():.2f}]")

    joblib.dump(model, "xgboost_optimise.pkl")
    joblib.dump(feature_cols, VISITE_FEATURES_FILE)
    print(f"   💾 Sauvegardés : xgboost_optimise.pkl + {VISITE_FEATURES_FILE}")
    return feature_cols


def entrainer_modele_operation(df):
    """
    Modèle 2 : Multi-classe — quelle opération le client va-t-il faire ? (xgboost_model.pkl)
    Cible : l'opération la plus fréquente du client
    """
    print("\n🎯 Entraînement Modèle 2 — Prédiction Opération Future (xgboost_model.pkl)")

    enc_segment = LabelEncoder()
    df["seg_enc"] = enc_segment.fit_transform(df["segment_metier"].fillna("Particulier"))

    enc_motif = LabelEncoder()
    df["motif_enc"] = enc_motif.fit_transform(df["operation_plus_frequente"].fillna("RETRAIT"))

    print(f"   Classes d'opération détectées : {list(enc_motif.classes_)}")

    X = df[["seg_enc", "solde_total", "moy_retrait", "nb_ops_30j",
            "ratio_solde_habitude", "has_compte_epargne",
            "PLACEMENT", "RETRAIT_EPARGNE", "RETRAIT", "VERSEMENT"]].fillna(0)
    X = X.rename(columns={"solde_total": "solde_actuel",
                           "moy_retrait": "moyenne_retraits_30j"})

    y = df["motif_enc"]

    # Découpage stratifié. Sur 100 clients et une vingtaine de motifs de visite,
    # un tirage aléatoire simple envoie parfois toute une classe rare dans le
    # test : XGBoost reçoit alors des étiquettes non contiguës et refuse de
    # s'entraîner. Les classes à individu unique ne sont pas stratifiables et
    # restent côté apprentissage — on ne peut de toute façon rien apprendre
    # d'un seul exemple, mais leur présence garde les indices contigus.
    effectifs = y.value_counts()
    rares = y.isin(effectifs[effectifs < 2].index)
    X_str, y_str = X[~rares], y[~rares]
    X_train, X_test, y_train, y_test = train_test_split(
        X_str, y_str, test_size=0.2, random_state=42, stratify=y_str)
    if rares.any():
        X_train = pd.concat([X_train, X[rares]])
        y_train = pd.concat([y_train, y[rares]])
        print(f"   ℹ️  {int(rares.sum())} client(s) de classe unique gardés en apprentissage : "
              f"{', '.join(enc_motif.inverse_transform(sorted(y[rares].unique())))}")

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        use_label_encoder=False, eval_metric="mlogloss", random_state=42
    )
    model.fit(X_train, y_train)

    acc = accuracy_score(y_test, model.predict(X_test))
    print(f"   ✅ Accuracy : {acc*100:.1f}%")

    joblib.dump(model, "xgboost_model.pkl")  # noqa: E501 (modèle historique)
    joblib.dump(enc_segment, "encoder_segment.pkl")
    joblib.dump(enc_motif, "encoder_motif.pkl")
    print("   💾 Sauvegardés : xgboost_model.pkl + encoder_segment.pkl + encoder_motif.pkl")


def main():
    print("=" * 60)
    print("🤖 AGENT D'ENTRAÎNEMENT IA — AWB")
    print("=" * 60)

    try:
        engine = create_engine(ENGINE_URL)
        print(f"✅ Connexion MySQL OK ({DB_NAME})\n")
    except Exception as e:
        print(f"❌ Connexion échouée : {e}")
        return

    df_hist, df_client = extraire_dataset(engine)
    if df_hist.empty:
        print("⚠️  Pas de données dans historique_operation. Lance d'abord generate_mock_data.py")
        return

    df_features = construire_features(df_hist, df_client)

    print("🧪 Lancement entrainer_modele_visite()", flush=True)
    entrainer_modele_visite(df_features)
    print("🧪 Lancement entrainer_modele_operation()", flush=True)
    entrainer_modele_operation(df_features)
    print("🧪 Lancement entrainer_modele_operation_visite()", flush=True)
    entrainer_modele_operation_visite(engine)

    try:
        print("\n🎯 Entraînement Modèle Next — Date/Heure & Opération suivante", flush=True)
        entrainer_modele_next_visite(engine)
        print("   💾 Sauvegardés : next-time + next-operation + encodeurs")
    except Exception as e:
        print(f"   ⚠️ Entraînement next-visite ignoré (erreur): {e}")

    print("\n" + "=" * 60)
    print("✅ ENTRAÎNEMENT TERMINÉ — Les 2 modèles sont prêts !")
    print("   Redémarre consumer_ia.py pour utiliser les nouveaux modèles.")
    print("=" * 60)


def extraire_dataset_next_event(engine):
    """
    Extrait l'historique opérationnel avec:
    - segment_metier (client)
    - type_compte (compte lié à l'opération via compte_id)
    - date_heure_operation (timestamp)
    - type_operation (catégorie opération)
    - montant
    """
    query_ops_with_compte = """
        SELECT
            h.client_id,
            cl.segment_metier,
            COALESCE(co.type_compte, 'AUCUN') AS type_compte,
            h.date_heure_operation,
            h.type_operation,
            h.canal,
            h.montant
        FROM historique_operation h
        JOIN client cl ON h.client_id = cl.id
        LEFT JOIN compte co ON h.compte_id = co.id
        ORDER BY h.client_id, h.date_heure_operation
    """
    query_ops_fallback = """
        SELECT
            h.client_id,
            cl.segment_metier,
            'AUCUN' AS type_compte,
            h.date_heure_operation,
            h.type_operation,
            h.canal,
            h.montant
        FROM historique_operation h
        JOIN client cl ON h.client_id = cl.id
        ORDER BY h.client_id, h.date_heure_operation
    """

    try:
        df_ops = pd.read_sql(query_ops_with_compte, con=engine)
    except Exception as e:
        print(f"   ⚠️ Next-event: colonne compte_id introuvable (fallback). Détail: {e}")
        df_ops = pd.read_sql(query_ops_fallback, con=engine)

    # Les modèles next-date / next-time / next-operation prédisent la PROCHAINE
    # VISITE. Ils ne doivent donc voir que les passages au guichet : sur
    # l'ensemble des opérations, l'écart médian entre deux événements est de
    # 1,7 jour contre 20,9 jours entre deux visites réelles, et le modèle
    # concluait que chaque client repassait le lendemain.
    avant = len(df_ops)
    df_ops = df_ops[df_ops["canal"] == CANAL_AGENCE].reset_index(drop=True)
    print(f"   🏦 Next-event restreint au canal AGENCE : "
          f"{len(df_ops):,} / {avant:,} opérations")

    df_client = pd.read_sql(
        """
        SELECT
            cl.id AS client_id,
            cl.segment_metier,
            COALESCE(SUM(co.solde), 0) AS solde_actuel,
            MAX(CASE WHEN co.type_compte = 'EPARGNE' THEN 1 ELSE 0 END) AS has_compte_epargne,
            AVG(co.solde) AS solde_moyen_compte
        FROM client cl
        LEFT JOIN compte co ON cl.id = co.client_id
        GROUP BY cl.id, cl.segment_metier
        """,
        con=engine
    )

    df_ops["date_heure_operation"] = pd.to_datetime(df_ops["date_heure_operation"])
    df_client["solde_actuel"] = df_client["solde_actuel"].fillna(0)
    df_client["solde_moyen_compte"] = df_client["solde_moyen_compte"].fillna(0)
    df_client["has_compte_epargne"] = df_client["has_compte_epargne"].fillna(0).astype(int)

    return df_ops, df_client


def entrainer_modele_next_visite(engine):
    df_ops, df_client = extraire_dataset_next_event(engine)
    if df_ops.empty:
        print("   ⚠️ Dataset next-visite vide: historique_operation sans lignes.")
        return

    MAX_SAMPLES = int(os.getenv("NEXT_EVENT_MAX_SAMPLES", "50000"))
    MAX_PAIRS_PER_CLIENT = int(os.getenv("NEXT_EVENT_MAX_PAIRS_PER_CLIENT", "2000"))
    print(f"   ⏳ Limites next-event: MAX_SAMPLES={MAX_SAMPLES}, MAX_PAIRS_PER_CLIENT={MAX_PAIRS_PER_CLIENT}")

    enc_segment_next = LabelEncoder()
    enc_type_compte = LabelEncoder()
    enc_next_operation = LabelEncoder()

    enc_segment_next.fit(df_client["segment_metier"].fillna("Particulier").astype(str))
    enc_type_compte.fit(df_ops["type_compte"].fillna("AUCUN").astype(str))
    enc_next_operation.fit(df_ops["type_operation"].fillna("INCONNU").astype(str))

    client_map = df_client.set_index("client_id").to_dict(orient="index")

    feature_cols = [
        "seg_enc", "type_compte_enc", "nombre_operations", "montant_total",
        "montant_moyen", "moy_retrait", "nb_ops_30j", "ratio_solde_habitude",
        "has_compte_epargne", "solde_total", "solde_moyen_compte", "montant_courant"
    ] + ALL_OP_TYPES + [
        "current_heure_decimale", "current_jour_semaine", "current_est_weekend",
        "current_est_ferie", "current_dans_horaires_agence", "current_est_heure_pointe",
    ]

    X_rows, y_delta_days, y_hours, y_ops = [], [], [], []

    for client_id, ops in df_ops.groupby("client_id"):
        profile = client_map.get(client_id)
        if not profile: continue

        ops = ops.sort_values("date_heure_operation").reset_index(drop=True)
        if len(ops) < 2: continue

        start_i = max(0, len(ops) - 1 - MAX_PAIRS_PER_CLIENT)
        seg_enc = int(enc_segment_next.transform([str(profile.get("segment_metier", "Particulier"))])[0])
        
        counts = {op: 0 for op in ALL_OP_TYPES}
        nb_ops, total_m = 0, 0.0

        for i in range(len(ops) - 1):
            current, nxt = ops.iloc[i], ops.iloc[i+1]
            diff = nxt["date_heure_operation"] - current["date_heure_operation"]
            d_days = diff.total_seconds() / (24 * 3600)
            
            if i < start_i:
                nb_ops += 1
                total_m += float(current["montant"] or 0)
                if str(current["type_operation"]) in counts: counts[str(current["type_operation"])] += 1
                continue

            if len(X_rows) >= MAX_SAMPLES: break
            
            nb_ops += 1
            total_m += float(current["montant"] or 0)
            if str(current["type_operation"]) in counts: counts[str(current["type_operation"])] += 1

            type_compte_enc = int(enc_type_compte.transform([str(current["type_compte"])])[0])
            
            feat = {
                "seg_enc": seg_enc, "type_compte_enc": type_compte_enc,
                "nombre_operations": nb_ops, "montant_total": total_m,
                "montant_moyen": total_m / nb_ops, "montant_courant": float(current["montant"] or 0),
                "has_compte_epargne": int(profile.get("has_compte_epargne", 0)),
                "solde_total": float(profile.get("solde_actuel", 0)),
                "solde_moyen_compte": float(profile.get("solde_moyen_compte", 0)),
                "nb_ops_30j": nb_ops, "moy_retrait": total_m / nb_ops
            }
            feat["ratio_solde_habitude"] = feat["solde_total"] / (feat["moy_retrait"] + 1)
            
            for op in ALL_OP_TYPES: feat[op] = counts[op]
            cal = _ajouter_features_calendrier_operation(pd.DataFrame([{
                "id": 0,
                "client_id": client_id,
                "date_heure_operation": current["date_heure_operation"],
                "type_operation": current["type_operation"],
                "montant": current["montant"],
            }])).iloc[0]
            feat.update({
                "current_heure_decimale": float(cal["heure_decimale"]),
                "current_jour_semaine": int(cal["jour_semaine"]),
                "current_est_weekend": int(cal["est_weekend"]),
                "current_est_ferie": int(cal["est_jour_ferie"]),
                "current_dans_horaires_agence": int(cal["dans_horaires_agence"]),
                "current_est_heure_pointe": int(cal["est_heure_pointe"]),
            })

            X_rows.append([feat[c] for c in feature_cols])
            y_delta_days.append(max(0, d_days))
            y_hours.append(nxt["date_heure_operation"].hour + nxt["date_heure_operation"].minute / 60.0)
            y_ops.append(str(nxt["type_operation"]))

    if not X_rows:
        print("   ⚠️ Dataset next-visite vide après construction.")
        return

    X = pd.DataFrame(X_rows, columns=feature_cols)
    y_d = np.array(y_delta_days)
    y_h = np.array(y_hours)
    y_o = enc_next_operation.transform(y_ops)

    print(f"   🚀 Entraînement 3 modèles XGBoost sur {len(X)} lignes...")
    
    X_train, X_test, yd_train, yd_test, yh_train, yh_test, yo_train, yo_test = train_test_split(
        X, y_d, y_h, y_o, test_size=0.1, random_state=42
    )

    model_date = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_date.fit(X_train, yd_train)
    joblib.dump(model_date, NEXT_DATE_MODEL_FILE)

    model_hour = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_hour.fit(X_train, yh_train)
    joblib.dump(model_hour, NEXT_TIME_MODEL_FILE)

    model_op = xgb.XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1)
    model_op.fit(X_train, yo_train)
    joblib.dump(model_op, NEXT_OP_MODEL_FILE)

    joblib.dump(enc_segment_next, ENCODER_SEGMENT_NEXT_FILE)
    joblib.dump(enc_type_compte, ENCODER_TYPE_COMPTE_FILE)
    joblib.dump(enc_next_operation, ENCODER_NEXT_OPERATION_FILE)
    joblib.dump(feature_cols, NEXT_FEATURES_FILE)


if __name__ == "__main__":
    main()
