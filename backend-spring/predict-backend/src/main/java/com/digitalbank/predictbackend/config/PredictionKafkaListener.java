package com.digitalbank.predictbackend.config;


import com.digitalbank.predictbackend.dto.PredictionIaEvent;
import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.PredictionVisite;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Service
@Slf4j
@RequiredArgsConstructor
public class PredictionKafkaListener {

    private final ObjectMapper objectMapper;
    private final ClientRepository clientRepository;
    private final PredictionVisiteRepository predictionVisiteRepository;

    @Transactional
    @KafkaListener(
            topics = "predictions-ia-topic",
            groupId = "pfe-predict-group",
            properties = {"auto.offset.reset=earliest"}
    )
    public void ecouterPredictionIA(String messageJson) {
        try {
            // 1. Désérialisation du JSON Python
            PredictionIaEvent event = objectMapper.readValue(messageJson, PredictionIaEvent.class);
            log.info("🤖 Prédiction reçue pour client ID: {} → {} le {}",
                    event.getClientId(), event.getOperationPrevue(), event.getDatePrevue());

            // 2. Recherche du client
            clientRepository.findById(event.getClientId()).ifPresent(client -> {

                // 3. Création ou récupération de la prédiction
                PredictionVisite prediction = client.getPrediction();
                if (prediction == null) {
                    prediction = new PredictionVisite();
                    prediction.setClient(client);
                }

                // 4. Mise à jour complète : QUAND + QUELLE OPÉRATION + SCORE
                prediction.setScoreProbabiliteGlobal(event.getProbabilite());
                prediction.setInsightGenai(event.getExplication());
                prediction.setDateDernierCalcul(LocalDateTime.now());

                // Opération future prévue (ex: "Retrait Espèces")
                if (event.getOperationPrevue() != null && !event.getOperationPrevue().isBlank()) {
                    prediction.setOperationPrevue(event.getOperationPrevue());
                }

                // Plage horaire
                if (event.getPlageHorairePrevue() != null && !event.getPlageHorairePrevue().isBlank()) {
                    prediction.setPlageHorairePrevue(event.getPlageHorairePrevue());
                }

                // Date de visite estimée (ex: "2026-03-27")
                if (event.getDatePrevue() != null && !event.getDatePrevue().isBlank()) {
                    try {
                        LocalDate dateBrute = LocalDate.parse(event.getDatePrevue());
                        prediction.setDatePrevue(dateBrute);
                        
                        // --- Filtre Déterministe (Business Rules) ---
                        if (dateBrute.getDayOfWeek() == java.time.DayOfWeek.SATURDAY) {
                            prediction.setDatePrevueAjustee(dateBrute.plusDays(2)); // Lundi
                            prediction.setMotifAjustement("AGENCY_CLOSED_WEEKEND");
                            log.info("⚠️ Ajustement métier: Samedi -> Lundi");
                        } else if (dateBrute.getDayOfWeek() == java.time.DayOfWeek.SUNDAY) {
                            prediction.setDatePrevueAjustee(dateBrute.plusDays(1)); // Lundi
                            prediction.setMotifAjustement("AGENCY_CLOSED_WEEKEND");
                            log.info("⚠️ Ajustement métier: Dimanche -> Lundi");
                        } else {
                            prediction.setDatePrevueAjustee(dateBrute);
                            prediction.setMotifAjustement(null);
                        }
                    } catch (Exception e) {
                        log.warn("Date invalide ignorée : {}", event.getDatePrevue());
                    }
                }

                // 5. Sauvegarde MySQL
                predictionVisiteRepository.save(prediction);

                log.info("✅ Prédiction sauvegardée : {} viendra le {} pour «{}» ({}%)",
                        client.getNomComplet(),
                        event.getDatePrevue(),
                        event.getOperationPrevue(),
                        String.format("%.1f", event.getProbabilite()));
            });

        } catch (Exception e) {
            log.error("❌ Erreur persistance prédiction : ", e);
        }
    }
}