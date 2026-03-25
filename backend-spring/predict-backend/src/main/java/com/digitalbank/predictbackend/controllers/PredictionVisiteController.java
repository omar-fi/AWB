package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.PredictionVisite;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import com.digitalbank.predictbackend.service.EmailService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;

@RestController
@RequestMapping("/api/v1/predictions")
@CrossOrigin(origins = "http://localhost:5173")
public class PredictionVisiteController {

    private final PredictionVisiteRepository predictionRepository;
    private final ClientRepository clientRepository;
    private final EmailService emailService;

    public PredictionVisiteController(PredictionVisiteRepository predictionRepository,
                                      ClientRepository clientRepository,
                                      EmailService emailService) {
        this.predictionRepository = predictionRepository;
        this.clientRepository     = clientRepository;
        this.emailService         = emailService;
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
}