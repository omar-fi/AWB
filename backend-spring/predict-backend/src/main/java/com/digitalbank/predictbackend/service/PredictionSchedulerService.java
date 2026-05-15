package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.repository.ClientRepository;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import jakarta.transaction.Transactional;
import java.time.LocalDate;
import java.util.List;

/**
 * Service de surveillance des prédictions expirées.
 * Pas de recalcul en temps réel : le batch nocturne Python (nightly_batch.py)
 * se charge de régénérer toutes les prédictions chaque nuit.
 * Ce service se contente de logger les prédictions dont la date est passée.
 */
@Service
public class PredictionSchedulerService {

    private final ClientRepository clientRepository;

    public PredictionSchedulerService(ClientRepository clientRepository) {
        this.clientRepository = clientRepository;
    }

    /**
     * Vérifie toutes les heures les prédictions expirées et les signale.
     * Le vrai recalcul est délégué au batch nocturne Python.
     */
    @Scheduled(fixedRate = 3600000) // toutes les heures
    @Transactional
    public void signalerPredictionsExpirees() {
        LocalDate aujourdHui = LocalDate.now();
        List<Client> clientsExpires = clientRepository.findClientsWithExpiredPredictions(aujourdHui);

        if (!clientsExpires.isEmpty()) {
            System.out.println("⚠️ [Batch Monitor] " + clientsExpires.size()
                    + " prédictions expirées détectées. Elles seront recalculées par le prochain batch nocturne (nightly_batch.py).");
        } else {
            System.out.println("✅ [Batch Monitor] Toutes les prédictions sont à jour.");
        }
    }
}