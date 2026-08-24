"""
Features du modèle « opération de la prochaine visite en agence ».

Ce module est la SEULE définition de ces features. L'entraînement
(agent_entrainement) et l'inférence (agent_prediction) l'importent tous les
deux : dupliquer la construction des features des deux côtés est la façon la
plus sûre de faire dériver silencieusement un modèle de sa production.

Principe : ne décrire que ce qui est connu AVANT la visite à prédire.
Le calendrier de la visite cible (jour, mois, jour de semaine) en fait partie —
on sait quand on projette le passage, la question est de savoir pour quoi.
"""
from collections import Counter

# Démarches qui en appellent une autre à quelques jours (opposition → code PIN,
# ouverture de compte → chéquier, crédit → assurance emprunteur). Savoir qu'une
# de ces démarches est récente est le signal le plus fort dont dispose le
# modèle.
DECLENCHEURS = ["Opposition Carte", "Ouverture de Compte", "Demande de Crédit",
                "Renouvellement Carte", "Réclamation"]

FENETRE_DECLENCHEUR_JOURS = 15
MIN_VISITES_HISTORIQUE = 3


def colonnes_features(types_operations: list) -> list:
    """Ordre canonique des colonnes. Doit être identique train / inférence."""
    return (["segment", "jour_du_mois", "jour_semaine", "mois",
             "op_precedente", "op_avant_precedente", "jours_depuis_derniere",
             "nb_visites", "montant_precedent"]
            + [f"part_{t}" for t in types_operations]
            + [f"recent_{t}" for t in DECLENCHEURS])


def construire_features(segment_enc, date_cible, historique, compteurs,
                        encoder_operation, types_operations):
    """
    Construit une ligne de features.

    Args:
        segment_enc:  segment client encodé.
        date_cible:   datetime de la visite dont on veut prédire le motif.
        historique:   liste [(datetime, type_operation)] des visites PASSÉES,
                      ordonnée du plus ancien au plus récent.
        compteurs:    Counter des types déjà observés (= mêmes visites).
        encoder_operation: LabelEncoder ajusté sur types_operations.
        types_operations:  catalogue ordonné des opérations d'agence.

    Returns:
        dict {colonne: valeur}, ou None si l'historique est trop court.
    """
    if len(historique) < MIN_VISITES_HISTORIQUE:
        return None

    date_prec, type_prec = historique[-1]
    _, type_avant = historique[-2]
    total = max(1, sum(compteurs.values()))

    def encoder(nom):
        try:
            return int(encoder_operation.transform([nom])[0])
        except (ValueError, KeyError):
            return -1

    f = {
        "segment":               segment_enc,
        "jour_du_mois":          date_cible.day,
        "jour_semaine":          date_cible.weekday(),
        "mois":                  date_cible.month,
        "op_precedente":         encoder(type_prec),
        "op_avant_precedente":   encoder(type_avant),
        "jours_depuis_derniere": max(0, (date_cible - date_prec).days),
        "nb_visites":            total,
        "montant_precedent":     0.0,
    }
    for t in types_operations:
        f[f"part_{t}"] = compteurs[t] / total
    # Les douze dernières visites suffisent à couvrir une fenêtre de 15 jours.
    recentes = historique[-12:]
    for t in DECLENCHEURS:
        f[f"recent_{t}"] = int(any(
            nom == t and (date_cible - dt).days <= FENETRE_DECLENCHEUR_JOURS
            for dt, nom in recentes))
    return f
