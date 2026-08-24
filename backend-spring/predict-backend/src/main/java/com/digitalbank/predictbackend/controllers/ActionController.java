package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.dto.ActionRequest;
import com.digitalbank.predictbackend.entities.ActionConseiller;
import com.digitalbank.predictbackend.repository.ActionConseillerRepository;
import com.digitalbank.predictbackend.service.DashboardService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/actions")
@CrossOrigin(origins = "http://localhost:5173")
public class ActionController {

    @Autowired
    private DashboardService dashboardService;

    @Autowired
    private ActionConseillerRepository actionRepository;

    @Autowired
    private com.digitalbank.predictbackend.service.FluxAgenceService fluxAgenceService;

    @PostMapping
    public ResponseEntity<ActionConseiller> enregistrerAction(@RequestBody ActionRequest request) {
        ActionConseiller action = dashboardService.enregistrerActionCommerciale(
                request.getBanquierId(),
                request.getClientId(),
                request.getStatut(),
                request.getCommentaire(),
                request.getPriorite(),
                request.getTypeDelegation(),
                request.getCategorie()
        );
        return ResponseEntity.ok(action);
    }

    @PostMapping("/log")
    public ResponseEntity<ActionConseiller> logAction(@RequestBody ActionRequest request) {
        return enregistrerAction(request);
    }

    @GetMapping("/kpi/agence/{agenceId}")
    public ResponseEntity<Map<String, Object>> getKpiAgence(@PathVariable Long agenceId) {
        long totalVentes = dashboardService.obtenirKpiVentesAgence(agenceId);
        Map<String, Object> kpi = new HashMap<>();
        kpi.put("ventesReussies", totalVentes);
        kpi.put("message", "Statistiques générées avec succès");
        return ResponseEntity.ok(kpi);
    }

    @GetMapping("/client/{clientId}/instruction")
    public ResponseEntity<ActionConseiller> getDerniereInstruction(@PathVariable Long clientId) {
        return dashboardService.obtenirDerniereInstruction(clientId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.noContent().build());
    }

    @GetMapping("/client/{clientId}/dernier-examen")
    public ResponseEntity<ActionConseiller> getDernierExamen(@PathVariable Long clientId) {
        return dashboardService.obtenirDernierExamen(clientId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.noContent().build());
    }

    @GetMapping("/stats/taux-traitement")
    public ResponseEntity<Map<String, Object>> getStatsTraitement() {
        return ResponseEntity.ok(dashboardService.obtenirStatsTraitement());
    }

    @GetMapping("/stats/directeur/{agenceId}")
    public ResponseEntity<Map<String, Object>> getStatsDirecteur(@PathVariable Long agenceId) {
        return ResponseEntity.ok(dashboardService.obtenirStatsDirecteur(agenceId));
    }

    @GetMapping("/agence/{agenceId}/journal")
    public ResponseEntity<Page<ActionConseiller>> getJournalAgence(
            @PathVariable Long agenceId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ResponseEntity.ok(actionRepository.findAllByBanquierAgenceIdOrderByDateActionDesc(agenceId, PageRequest.of(page, size)));
    }

    // DIRECTEUR : services proposés sur la période (JOUR, SEMAINE, MOIS) et clients concernés
    @GetMapping("/agence/{agenceId}/services")
    public ResponseEntity<Map<String, Object>> getServicesProposes(
            @PathVariable Long agenceId,
            @RequestParam(defaultValue = "SEMAINE") String periode) {
        return ResponseEntity.ok(fluxAgenceService.obtenirServicesProposes(agenceId, periode));
    }

    @GetMapping("/agence/{agenceId}/delegations")
    public ResponseEntity<java.util.List<ActionConseiller>> getDelegations(@PathVariable Long agenceId) {
        return ResponseEntity.ok(actionRepository.findDelegationsByAgence(agenceId));
    }
}