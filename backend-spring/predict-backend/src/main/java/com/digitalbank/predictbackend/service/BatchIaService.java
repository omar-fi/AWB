package com.digitalbank.predictbackend.service;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class BatchIaService {

    private static final Logger logger = LoggerFactory.getLogger(BatchIaService.class);
    private final RestTemplate restTemplate = new RestTemplate();
    private final String IA_MICROSERVICE_URL = "http://localhost:8000/api/v1/ia/run-batch";

    public String runBatchProcess() {
        logger.info("🚀 Demande de lancement du batch IA via le Microservice Python...");
        try {
            String response = restTemplate.postForObject(IA_MICROSERVICE_URL, null, String.class);
            return "SUCCÈS : " + response;
        } catch (Exception e) {
            logger.error("❌ Échec de l'appel au Microservice IA : {}", e.getMessage());
            return "ERREUR : Impossible de joindre le moteur IA (" + e.getMessage() + ")";
        }
    }
}
