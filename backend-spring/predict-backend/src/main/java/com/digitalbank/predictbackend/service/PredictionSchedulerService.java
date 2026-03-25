package com.digitalbank.predictbackend.service;


import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.repository.ClientRepository;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import jakarta.transaction.Transactional;
import java.time.LocalDate;
import java.util.List;

@Service
public class PredictionSchedulerService {

    private final ClientRepository clientRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public PredictionSchedulerService(ClientRepository clientRepository, KafkaTemplate<String, String> kafkaTemplate) {
        this.clientRepository = clientRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedRate = 60000)
    @Transactional
    public void verifierEtRecalculerPredictionsExpirees() {

        LocalDate aujourdHui = LocalDate.now();

        List<Client> clientsAmettreAJour = clientRepository.findClientsWithExpiredPredictions(aujourdHui);

        if (!clientsAmettreAJour.isEmpty()) {
            System.out.println("⏳ Recalcul IA déclenché pour " + clientsAmettreAJour.size() + " prédictions expirées.");

            for (Client client : clientsAmettreAJour) {
                client.setPrediction(null);
                clientRepository.save(client);

                String message = "{\"clientId\": " + client.getId() + ", \"action\": \"RECALCUL_EXPIRATION\"}";
                kafkaTemplate.send("topic_prediction_ia", message);
            }
        }
    }
}