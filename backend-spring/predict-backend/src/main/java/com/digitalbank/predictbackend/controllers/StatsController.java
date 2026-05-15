package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.service.DashboardService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@CrossOrigin(origins = "http://localhost:5173")
public class StatsController {

    @Autowired
    private DashboardService dashboardService;

    // PHASE 3 : Consulter "Santé du Portefeuille"
    @GetMapping("/stats/risques")
    public ResponseEntity<Map<String, Object>> getStatsRisques(@RequestParam Long agenceId) {
        return ResponseEntity.ok(dashboardService.obtenirStatsRisques(agenceId));
    }

    // PHASE 3 : Consulter "Performance Agence" (Graphiques de conversion)
    @GetMapping("/admin/kpi")
    public ResponseEntity<Map<String, Object>> getAdminKpi(@RequestParam Long agenceId) {
        return ResponseEntity.ok(dashboardService.obtenirAdminKpi(agenceId));
    }
}
