package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.entities.ActionConseiller;
import com.digitalbank.predictbackend.repository.ActionConseillerRepository;
import com.digitalbank.predictbackend.repository.BanquierRepository;
import com.digitalbank.predictbackend.repository.ClientRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class DashboardService {

    @Autowired
    private ActionConseillerRepository actionRepository;

    @Autowired
    private BanquierRepository banquierRepository;

    @Autowired
    private ClientRepository clientRepository;

    @Transactional
    public ActionConseiller enregistrerActionCommerciale(Long banquierId, Long clientId, String statut, String commentaire, String priorite, String typeDelegation, String categorie) {
        ActionConseiller action = new ActionConseiller();
        action.setDateAction(LocalDateTime.now());
        action.setCategorieAction(categorie != null ? categorie : "VENTE");
        action.setStatut(statut);
        action.setCommentaire(commentaire);
        action.setPriorite(priorite);
        action.setTypeDelegation(typeDelegation);

        action.setBanquier(banquierRepository.findById(banquierId).orElseThrow(() -> new RuntimeException("Banquier introuvable")));
        action.setClient(clientRepository.findById(clientId).orElseThrow(() -> new RuntimeException("Client introuvable")));

        return actionRepository.save(action);
    }

    public long obtenirKpiVentesAgence(Long agenceId) {
        return actionRepository.countVentesReussiesByAgence(agenceId);
    }

    public Optional<ActionConseiller> obtenirDerniereInstruction(Long clientId) {
        List<ActionConseiller> list = actionRepository.findInstructions(clientId, "DELEGUE_COMMERCIAL");
        if (!list.isEmpty()) {
            return Optional.of(list.get(0));
        }
        return Optional.empty();
    }

    public Optional<ActionConseiller> obtenirDernierExamen(Long clientId) {
        return actionRepository.findFirstByClientIdOrderByDateActionDesc(clientId);
    }

    // PHASE 3 : Santé du Portefeuille (Alertes Churn et Segments VIP)
    public Map<String, Object> obtenirStatsRisques(Long agenceId) {
        Map<String, Object> stats = new HashMap<>();
        stats.put("churnAlerts", 5); // Mock
        stats.put("vipSegments", 12); // Mock
        stats.put("message", "Santé du portefeuille analysée.");
        return stats;
    }

    // PHASE 3 : Performance Agence (Graphiques de conversion)
    public Map<String, Object> obtenirAdminKpi(Long agenceId) {
        Map<String, Object> kpi = new HashMap<>();
        kpi.put("conversionRate", 65.5); // Mock
        kpi.put("totalPredictions", 450); // Mock
        kpi.put("totalActions", 295); // Mock
        return kpi;
    }

    // PHASE 6 : Statistiques de Traitement Réelles
    public Map<String, Object> obtenirStatsTraitement() {
        long clientsTraites = actionRepository.countUniqueClientsTreated();
        long totalClients = clientRepository.count();
        double taux = (totalClients > 0) ? ((double) clientsTraites / totalClients) * 100 : 0;

        Map<String, Object> stats = new HashMap<>();
        stats.put("clientsTraites", clientsTraites);
        stats.put("totalClients", totalClients);
        stats.put("tauxTraitement", Math.round(taux * 10) / 10.0); // 1 décimale
        return stats;
    }

    // PHASE 8 : Statistiques Consolidées pour le Directeur
    public Map<String, Object> obtenirStatsDirecteur(Long agenceId) {
        Map<String, Object> response = new HashMap<>();

        // 1. KPIs de base
        long totalActions = actionRepository.count();
        long totalClients = clientRepository.count();
        long totalVentes = actionRepository.countVentesReussiesByAgence(agenceId);
        
        response.put("totalVentes", totalVentes);
        response.put("caSimule", totalVentes * 15000); // 15k MAD par vente en moyenne pour la démo
        response.put("tauxAdoption", totalActions > 0 ? (double) totalVentes / totalActions * 100 : 0);
        response.put("totalClients", totalClients);

        // 2. Performance par Banquier (BarChart : Conseillers & Portefeuilleurs)
        List<Object[]> conversionRaw = actionRepository.countPerformanceByBanquier(agenceId);
        List<Map<String, Object>> conversionList = conversionRaw.stream().map(row -> {
            Map<String, Object> map = new HashMap<>();
            map.put("name", row[0]);
            map.put("ventes", row[1]); // On garde la clé "ventes" pour la compatibilité frontend (total actions)
            map.put("role", row[2].toString());
            map.put("obj", row[3] != null ? row[3] : 20.0);
            return map;
        }).toList();
        response.put("conversionByAdvisor", conversionList);

        // 3. Distribution Statuts (PieChart)
        List<Object[]> statutRaw = actionRepository.countActionsByStatut(agenceId);
        List<Map<String, Object>> statutList = statutRaw.stream().map(row -> {
            Map<String, Object> map = new HashMap<>();
            map.put("name", row[0]);
            map.put("value", row[1]);
            return map;
        }).toList();
        response.put("distributionStatuts", statutList);

        // 4. Dernières Actions (Table)
        List<ActionConseiller> recentActions = actionRepository.findTop5RecentActionsByAgence(agenceId);
        response.put("recentActions", recentActions);

        return response;
    }
}
