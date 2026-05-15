package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.PredictionVisite;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import com.digitalbank.predictbackend.service.EmailService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/v1/predictions")
@CrossOrigin(origins = "http://localhost:5173")
public class PredictionVisiteController {

    private final PredictionVisiteRepository predictionRepository;
    private final ClientRepository clientRepository;
    private final EmailService emailService;
    private final com.digitalbank.predictbackend.service.BatchIaService batchIaService;

    public PredictionVisiteController(PredictionVisiteRepository predictionRepository,
                                      ClientRepository clientRepository,
                                      EmailService emailService,
                                      com.digitalbank.predictbackend.service.BatchIaService batchIaService) {
        this.predictionRepository = predictionRepository;
        this.clientRepository     = clientRepository;
        this.emailService         = emailService;
        this.batchIaService      = batchIaService;
    }

    @GetMapping("/client/{clientId}")
    public ResponseEntity<PredictionVisite> getPredictionByClient(@PathVariable Long clientId) {
        return predictionRepository.findByClientId(clientId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public PredictionVisite saveOrUpdatePrediction(@RequestBody PredictionVisite nouvellePrediction) {
        nouvellePrediction.setDateDernierCalcul(LocalDateTime.now());
        PredictionVisite saved = predictionRepository.save(nouvellePrediction);

        if (saved.getClient() != null) {
            Long clientId = saved.getClient().getId();
            clientRepository.findById(clientId).ifPresent((Client client) -> {
                if (client.getEmail() != null && !client.getEmail().isBlank()) {
                    emailService.envoyerEmailPrediction(
                            client.getEmail(),
                            client.getNomComplet(),
                            saved
                    );
                }
            });
        }
        return saved;
    }

    // ROUTE COMMERCIAL : Récupérer les clients à contacter aujourd'hui
    @GetMapping("/agence/{agenceId}/aujourdhui")
    public ResponseEntity<List<PredictionVisite>> getPredictionsDuJour(@PathVariable Long agenceId) {
        LocalDate aujourdhui = LocalDate.now();
        List<PredictionVisite> opportunites = predictionRepository.findPredictionsDuJourByAgence(agenceId, aujourdhui);

        if (opportunites.isEmpty()) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.ok(opportunites);
    }

    // ALIAS PHASE 2 : Consulter "Clients attendus aujourd'hui"
    @GetMapping("/opportunites")
    public ResponseEntity<List<PredictionVisite>> getOpportunitesDirect(@RequestParam Long agenceId) {
        LocalDate aujourdhui = LocalDate.now();
        List<PredictionVisite> opportunites = predictionRepository.findHighProbabilityPredictionsDuJourByAgence(agenceId, aujourdhui);
        
        if (opportunites.isEmpty()) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.ok(opportunites);
    }

    // COMMERCIAL : Toutes les prédictions de l'agence (planning complet)
    @GetMapping("/agence/{agenceId}")
    public ResponseEntity<List<PredictionVisite>> getAllPredictionsByAgence(@PathVariable Long agenceId) {
        List<PredictionVisite> predictions = predictionRepository.findAllByAgenceId(agenceId);
        if (predictions.isEmpty()) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.ok(predictions);
    }

    @PostMapping("/batch-refresh")
    public ResponseEntity<String> runBatchIa() {
        String result = batchIaService.runBatchProcess();
        if (result.startsWith("SUCCÈS")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.status(500).body(result);
        }
    }
}