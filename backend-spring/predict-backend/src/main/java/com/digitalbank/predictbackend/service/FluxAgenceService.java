package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.entities.ActionConseiller;
import com.digitalbank.predictbackend.entities.Banquier;
import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.PredictionVisite;
import com.digitalbank.predictbackend.repository.ActionConseillerRepository;
import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Flux d'agence — la lecture du directeur : qui pousse la porte, quand, et
 * pourquoi ; puis ce que l'agence a proposé à ces clients.
 *
 * Deux services distincts et volontairement séparés :
 *  - {@link #obtenirFluxAttendu(Long, int)} projette l'affluence jour par jour
 *    à partir des prédictions de visite, et déclare le contexte qui l'explique
 *    (fin de mois, veille de week-end…) ;
 *  - {@link #obtenirServicesProposes(Long, String)} compte les services
 *    proposés sur une période et nomme les clients concernés.
 *
 * Le contexte calendaire est une lecture du calendrier, pas une sortie du
 * modèle : il est affiché comme tel, avec le nombre de clients réellement
 * attendus ce jour-là et le détail de ce qu'ils viennent faire. Le directeur
 * doit pouvoir distinguer ce que la machine a prédit de ce que le calendrier
 * suggère.
 */
@Service
public class FluxAgenceService {

    private static final Locale FR = Locale.FRENCH;
    private static final DateTimeFormatter LIBELLE_JOUR = DateTimeFormatter.ofPattern("EEEE d MMMM", FR);
    private static final DateTimeFormatter HORODATAGE = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    /** Libellés lisibles des opérations prédites par le moteur IA. */
    private static final Map<String, String> LIBELLES_OPERATION = Map.ofEntries(
            Map.entry("RETRAIT", "Retrait d'espèces"),
            Map.entry("RETRAIT GUICHET", "Retrait au guichet"),
            Map.entry("RETRAIT_EPARGNE", "Retrait sur épargne"),
            Map.entry("VIREMENT", "Virement"),
            Map.entry("DEPOT", "Dépôt d'espèces"),
            Map.entry("REMISE_CHEQUE", "Remise de chèque"),
            Map.entry("PAIEMENT_FACTURE", "Paiement de facture"),
            Map.entry("PAIEMENT DE FACTURE", "Paiement de facture"),
            Map.entry("PAIEMENT_CARTE", "Paiement par carte"),
            Map.entry("PAIEMENT TPE", "Paiement TPE"),
            Map.entry("PLACEMENT", "Placement / épargne"),
            Map.entry("PLACEMENT ÉPARGNE", "Placement / épargne"),
            Map.entry("DEMANDE DE CRÉDIT", "Demande de crédit"),
            Map.entry("DEMANDE DE CREDIT", "Demande de crédit")
    );

    /**
     * Opérations qui obligent le client à se déplacer au guichet : ce sont
     * celles qui portent les pics de fin et de début de mois.
     */
    private static final Set<String> OPERATIONS_CAISSE = Set.of(
            "RETRAIT", "RETRAIT GUICHET", "RETRAIT_EPARGNE", "VIREMENT",
            "DEPOT", "REMISE_CHEQUE"
    );

    private static final Set<String> RISQUES_ELEVES = Set.of("CRITIQUE", "ÉLEVÉ", "ELEVE", "HIGH");

    private final PredictionVisiteRepository predictionRepository;
    private final ActionConseillerRepository actionRepository;

    public FluxAgenceService(PredictionVisiteRepository predictionRepository,
                             ActionConseillerRepository actionRepository) {
        this.predictionRepository = predictionRepository;
        this.actionRepository = actionRepository;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 1. AFFLUENCE ATTENDUE — combien de clients, qui, et pourquoi
    // ──────────────────────────────────────────────────────────────────────────

    @Transactional(readOnly = true)
    public Map<String, Object> obtenirFluxAttendu(Long agenceId, int jours) {
        int horizon = Math.max(1, Math.min(jours, 31));
        LocalDate debut = LocalDate.now();
        LocalDate fin = debut.plusDays(horizon - 1L);

        List<PredictionVisite> predictions =
                predictionRepository.findFluxByAgenceEntre(agenceId, debut, fin);

        // Regroupement par date effective (la date ajustée prime sur la prédite).
        Map<LocalDate, List<PredictionVisite>> parJour = predictions.stream()
                .filter(p -> dateEffective(p) != null)
                .collect(Collectors.groupingBy(FluxAgenceService::dateEffective));

        double moyenne = (double) predictions.size() / horizon;

        List<Map<String, Object>> jourList = new ArrayList<>();
        for (int i = 0; i < horizon; i++) {
            LocalDate jour = debut.plusDays(i);
            jourList.add(construireJour(jour, parJour.getOrDefault(jour, List.of()), moyenne));
        }

        Map<String, Object> pic = jourList.stream()
                .max(Comparator.comparingInt((Map<String, Object> j) -> (int) j.get("nbClients")))
                .orElse(null);

        Map<String, Object> reponse = new LinkedHashMap<>();
        reponse.put("horizonJours", horizon);
        reponse.put("dateDebut", debut.toString());
        reponse.put("dateFin", fin.toString());
        reponse.put("totalClients", predictions.size());
        reponse.put("moyenneParJour", arrondir(moyenne));
        reponse.put("nbClientsAujourdhui", jourList.isEmpty() ? 0 : jourList.get(0).get("nbClients"));
        if (pic != null && (int) pic.get("nbClients") > 0) {
            Map<String, Object> resumePic = new LinkedHashMap<>();
            resumePic.put("date", pic.get("date"));
            resumePic.put("libelle", pic.get("libelle"));
            resumePic.put("nbClients", pic.get("nbClients"));
            resumePic.put("contexte", pic.get("contexte"));
            reponse.put("picAffluence", resumePic);
        } else {
            reponse.put("picAffluence", null);
        }
        reponse.put("jours", jourList);
        return reponse;
    }

    private Map<String, Object> construireJour(LocalDate jour, List<PredictionVisite> visites, double moyenne) {
        List<Map<String, Object>> clients = visites.stream()
                .sorted(Comparator
                        .comparing((PredictionVisite p) -> p.getPlageHorairePrevue() == null ? "~" : p.getPlageHorairePrevue())
                        .thenComparing(Comparator.comparingDouble(FluxAgenceService::scoreNormalise).reversed()))
                .map(this::decrireClientAttendu)
                .toList();

        // Motifs : ce que ces clients viennent faire. La somme des motifs vaut
        // le nombre de clients attendus — c'est la seule attribution que le
        // modèle autorise, client par client.
        Map<String, Long> motifsBruts = visites.stream()
                .collect(Collectors.groupingBy(p -> libelleOperation(p.getOperationPrevue()),
                        LinkedHashMap::new, Collectors.counting()));
        List<Map<String, Object>> motifs = motifsBruts.entrySet().stream()
                .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                .map(e -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("operation", e.getKey());
                    m.put("nbClients", e.getValue());
                    m.put("part", visites.isEmpty() ? 0.0 : arrondir(e.getValue() * 100.0 / visites.size()));
                    return m;
                })
                .toList();

        Map<String, Long> plagesBrutes = visites.stream()
                .collect(Collectors.groupingBy(p -> p.getPlageHorairePrevue() == null || p.getPlageHorairePrevue().isBlank()
                                ? "Heure non déterminée" : p.getPlageHorairePrevue(),
                        LinkedHashMap::new, Collectors.counting()));
        List<Map<String, Object>> plages = plagesBrutes.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(e -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("plage", e.getKey());
                    m.put("nbClients", e.getValue());
                    return m;
                })
                .toList();

        long nbCaisse = visites.stream()
                .filter(p -> OPERATIONS_CAISSE.contains(normaliser(p.getOperationPrevue())))
                .count();
        long nbRisque = visites.stream()
                .filter(p -> RISQUES_ELEVES.contains(normaliser(p.getNiveauRisque())))
                .count();
        long nbMecontents = visites.stream()
                .filter(p -> p.getScoreInsatisfaction() != null && p.getScoreInsatisfaction() >= 50)
                .count();

        double ecart = moyenne > 0 ? (visites.size() - moyenne) / moyenne * 100.0 : 0.0;

        Map<String, Object> j = new LinkedHashMap<>();
        j.put("date", jour.toString());
        j.put("libelle", capitaliser(jour.format(LIBELLE_JOUR)));
        j.put("jourSemaine", capitaliser(jour.getDayOfWeek().getDisplayName(java.time.format.TextStyle.FULL, FR)));
        j.put("estAujourdhui", jour.equals(LocalDate.now()));
        j.put("nbClients", visites.size());
        j.put("ecartMoyennePct", moyenne > 0 ? (int) Math.round(ecart) : 0);
        j.put("affluence", niveauAffluence(visites.size(), moyenne));
        j.put("contexte", contexteCalendaire(jour, visites.size(), nbCaisse));
        j.put("motifs", motifs);
        j.put("plagesHoraires", plages);
        j.put("nbOperationsCaisse", nbCaisse);
        j.put("nbRisqueEleve", nbRisque);
        j.put("nbMecontents", nbMecontents);
        j.put("clients", clients);
        return j;
    }

    /**
     * Le « pourquoi » du jour, lu dans le calendrier et chiffré avec les
     * clients réellement attendus.
     *
     * Chaque cause porte le nombre de clients du jour concernés par une
     * opération de caisse : dire « c'est la fin du mois » sans dire combien de
     * clients viennent retirer ou virer ne renseigne personne.
     */
    private List<Map<String, Object>> contexteCalendaire(LocalDate jour, int nbClients, long nbCaisse) {
        List<Map<String, Object>> contexte = new ArrayList<>();
        // Un jour sans visite attendue n'a pas de cause à déclarer : afficher
        // « fin de mois » sur une journée vide brouillerait la lecture.
        if (nbClients == 0) return contexte;

        int quantieme = jour.getDayOfMonth();
        int dernierJour = jour.lengthOfMonth();
        DayOfWeek jourSemaine = jour.getDayOfWeek();

        if (quantieme >= dernierJour - 2) {
            contexte.add(cause("FIN_DE_MOIS", "Fin de mois",
                    "Virements de salaire et échéances de prélèvements : "
                            + nbCaisse + " client(s) attendu(s) pour une opération de caisse sur "
                            + nbClients + " au total."));
        } else if (quantieme <= 5) {
            contexte.add(cause("DEBUT_DE_MOIS", "Début de mois",
                    "Retraits sur salaire et règlement des charges : "
                            + nbCaisse + " client(s) attendu(s) pour une opération de caisse sur "
                            + nbClients + " au total."));
        }

        if (jourSemaine == DayOfWeek.FRIDAY) {
            contexte.add(cause("VEILLE_WEEKEND", "Veille de week-end",
                    "Dernier jour ouvré : les retraits d'espèces se concentrent avant la fermeture."));
        } else if (jourSemaine == DayOfWeek.MONDAY) {
            contexte.add(cause("REOUVERTURE", "Réouverture après week-end",
                    "Les opérations guichet reportées du samedi et du dimanche se présentent ce jour."));
        } else if (jourSemaine == DayOfWeek.SATURDAY || jourSemaine == DayOfWeek.SUNDAY) {
            contexte.add(cause("WEEK_END", "Week-end",
                    "Guichet fermé ou en service réduit : ces visites sont à replanifier."));
        }

        if (contexte.isEmpty() && nbClients > 0) {
            contexte.add(cause("RYTHME_HABITUEL", "Jour ordinaire",
                    "Aucun effet de calendrier : l'affluence vient du rythme habituel des clients."));
        }
        return contexte;
    }

    private Map<String, Object> cause(String code, String libelle, String detail) {
        Map<String, Object> c = new LinkedHashMap<>();
        c.put("code", code);
        c.put("libelle", libelle);
        c.put("detail", detail);
        return c;
    }

    private Map<String, Object> decrireClientAttendu(PredictionVisite p) {
        Client client = p.getClient();
        Map<String, Object> c = new LinkedHashMap<>();
        c.put("predictionId", p.getId());
        c.put("clientId", client != null ? client.getId() : null);
        c.put("nomComplet", client != null ? client.getNomComplet() : "Client inconnu");
        c.put("cin", client != null ? client.getCin() : null);
        c.put("telephone", client != null ? client.getTelephone() : null);
        c.put("segment", client != null ? client.getSegmentMetier() : null);
        c.put("plageHoraire", p.getPlageHorairePrevue());
        c.put("operationPrevue", libelleOperation(p.getOperationPrevue()));
        c.put("score", scoreNormalise(p));
        c.put("niveauRisque", p.getNiveauRisque());
        c.put("scoreInsatisfaction", p.getScoreInsatisfaction());
        c.put("niveauSatisfaction", p.getNiveauSatisfaction());
        c.put("dateAjustee", p.getDatePrevueAjustee() != null);
        c.put("motifAjustement", p.getMotifAjustement());
        return c;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 2. SERVICES PROPOSÉS — combien, lesquels, à quels clients
    // ──────────────────────────────────────────────────────────────────────────

    @Transactional(readOnly = true)
    public Map<String, Object> obtenirServicesProposes(Long agenceId, String periode) {
        String choix = periode == null ? "SEMAINE" : periode.toUpperCase(FR);
        if (!Set.of("JOUR", "SEMAINE", "MOIS").contains(choix)) {
            choix = "SEMAINE";
        }

        LocalDate aujourdhui = LocalDate.now();
        LocalDateTime debutJour = aujourdhui.atStartOfDay();
        LocalDateTime debutSemaine = aujourdhui.with(DayOfWeek.MONDAY).atStartOfDay();
        LocalDateTime debutMois = aujourdhui.withDayOfMonth(1).atStartOfDay();

        // Une seule lecture, sur la plus ancienne des trois bornes : la semaine
        // en cours peut commencer le mois précédent.
        LocalDateTime borne = debutSemaine.isBefore(debutMois) ? debutSemaine : debutMois;
        List<ActionConseiller> actions = actionRepository.findServicesByAgenceDepuis(agenceId, borne);

        LocalDateTime debutPeriode = switch (choix) {
            case "JOUR" -> debutJour;
            case "MOIS" -> debutMois;
            default -> debutSemaine;
        };
        List<ActionConseiller> selection = actions.stream()
                .filter(a -> a.getDateAction() != null && !a.getDateAction().isBefore(debutPeriode))
                .toList();

        Map<String, Object> totaux = new LinkedHashMap<>();
        totaux.put("jour", compter(actions, debutJour));
        totaux.put("semaine", compter(actions, debutSemaine));
        totaux.put("mois", compter(actions, debutMois));

        long vendus = selection.stream()
                .filter(a -> "VENDU".equalsIgnoreCase(a.getStatut()))
                .count();

        Map<String, Object> reponse = new LinkedHashMap<>();
        reponse.put("periode", choix);
        reponse.put("debutPeriode", debutPeriode.format(HORODATAGE));
        reponse.put("total", selection.size());
        reponse.put("totaux", totaux);
        reponse.put("clientsUniques", selection.stream()
                .map(a -> a.getClient() != null ? a.getClient().getId() : null)
                .filter(java.util.Objects::nonNull)
                .distinct().count());
        reponse.put("nbVendus", vendus);
        reponse.put("tauxConversion", selection.isEmpty() ? 0.0 : arrondir(vendus * 100.0 / selection.size()));
        reponse.put("parCategorie", agreger(selection, a -> libelleService(a.getCategorieAction())));
        reponse.put("parStatut", agreger(selection, a -> a.getStatut() == null ? "NON RENSEIGNÉ" : a.getStatut()));
        reponse.put("parBanquier", agregerBanquiers(selection));
        reponse.put("propositions", selection.stream().map(this::decrireProposition).toList());
        return reponse;
    }

    private long compter(List<ActionConseiller> actions, LocalDateTime depuis) {
        return actions.stream()
                .filter(a -> a.getDateAction() != null && !a.getDateAction().isBefore(depuis))
                .count();
    }

    private List<Map<String, Object>> agreger(List<ActionConseiller> actions,
                                              java.util.function.Function<ActionConseiller, String> cle) {
        return actions.stream()
                .collect(Collectors.groupingBy(cle, LinkedHashMap::new, Collectors.counting()))
                .entrySet().stream()
                .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                .map(e -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("name", e.getKey());
                    m.put("value", e.getValue());
                    return m;
                })
                .toList();
    }

    private List<Map<String, Object>> agregerBanquiers(List<ActionConseiller> actions) {
        Map<String, long[]> parBanquier = new LinkedHashMap<>();
        Map<String, String> roles = new HashMap<>();
        for (ActionConseiller a : actions) {
            Banquier b = a.getBanquier();
            String nom = b != null && b.getNomComplet() != null ? b.getNomComplet() : "Non attribué";
            roles.putIfAbsent(nom, b != null && b.getRole() != null ? b.getRole().name() : "—");
            long[] compteurs = parBanquier.computeIfAbsent(nom, k -> new long[2]);
            compteurs[0]++;
            if ("VENDU".equalsIgnoreCase(a.getStatut())) compteurs[1]++;
        }
        return parBanquier.entrySet().stream()
                .sorted((x, y) -> Long.compare(y.getValue()[0], x.getValue()[0]))
                .map(e -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("name", e.getKey());
                    m.put("role", roles.get(e.getKey()));
                    m.put("value", e.getValue()[0]);
                    m.put("vendus", e.getValue()[1]);
                    return m;
                })
                .toList();
    }

    private Map<String, Object> decrireProposition(ActionConseiller a) {
        Client client = a.getClient();
        Banquier banquier = a.getBanquier();
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", a.getId());
        m.put("dateAction", a.getDateAction() == null ? null : a.getDateAction().format(HORODATAGE));
        m.put("service", libelleService(a.getCategorieAction()));
        m.put("statut", a.getStatut());
        m.put("priorite", a.getPriorite());
        m.put("typeDelegation", a.getTypeDelegation());
        m.put("commentaire", a.getCommentaire());
        m.put("clientId", client != null ? client.getId() : null);
        m.put("clientNom", client != null ? client.getNomComplet() : "Client inconnu");
        m.put("clientCin", client != null ? client.getCin() : null);
        m.put("clientSegment", client != null ? client.getSegmentMetier() : null);
        m.put("clientTelephone", client != null ? client.getTelephone() : null);
        m.put("banquierNom", banquier != null ? banquier.getNomComplet() : "Non attribué");
        m.put("banquierRole", banquier != null && banquier.getRole() != null ? banquier.getRole().name() : "—");
        return m;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Utilitaires
    // ──────────────────────────────────────────────────────────────────────────

    private static LocalDate dateEffective(PredictionVisite p) {
        return p.getDatePrevueAjustee() != null ? p.getDatePrevueAjustee() : p.getDatePrevue();
    }

    /**
     * Le moteur IA écrit tantôt une probabilité (0–1), tantôt un pourcentage
     * (0–100) : on ramène tout sur 100 pour que l'affichage ne mente pas.
     */
    private static double scoreNormalise(PredictionVisite p) {
        Double brut = p.getScoreProbabiliteGlobal();
        if (brut == null) return 0.0;
        double valeur = brut <= 1.0 ? brut * 100.0 : brut;
        return Math.round(valeur * 10.0) / 10.0;
    }

    private static String normaliser(String valeur) {
        return valeur == null ? "" : valeur.trim().toUpperCase(FR);
    }

    private static String libelleOperation(String operation) {
        if (operation == null || operation.isBlank()) return "Opération non déterminée";
        String cle = normaliser(operation);
        String libelle = LIBELLES_OPERATION.get(cle);
        if (libelle != null) return libelle;
        return capitaliser(cle.replace('_', ' ').toLowerCase(FR));
    }

    private static String libelleService(String categorie) {
        if (categorie == null || categorie.isBlank()) return "Service non renseigné";
        return capitaliser(categorie.replace('_', ' ').toLowerCase(FR));
    }

    private static String capitaliser(String texte) {
        if (texte == null || texte.isEmpty()) return texte;
        return texte.substring(0, 1).toUpperCase(FR) + texte.substring(1);
    }

    private static double arrondir(double valeur) {
        return Math.round(valeur * 10.0) / 10.0;
    }

    private static String niveauAffluence(int nbClients, double moyenne) {
        if (nbClients == 0) return "AUCUNE";
        if (moyenne <= 0) return "NORMALE";
        if (nbClients >= moyenne * 1.25) return "FORTE";
        if (nbClients <= moyenne * 0.75) return "FAIBLE";
        return "NORMALE";
    }
}
