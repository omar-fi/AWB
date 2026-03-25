package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.dto.OperationRequest;
import com.digitalbank.predictbackend.entities.Compte;
import com.digitalbank.predictbackend.entities.HistoriqueOperation;
import com.digitalbank.predictbackend.repository.CompteRepository;
import com.digitalbank.predictbackend.repository.HistoriqueOperationRepository;
import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

@Service
public class CompteService {

    @Autowired
    private CompteRepository compteRepository;

    @Autowired
    private HistoriqueOperationRepository historiqueRepository;

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    private static final String TOPIC_KAFKA = "transactions-client-topic";
    @Autowired
    private PredictionVisiteRepository predictionVisiteRepository;

    @Transactional
    public Compte effectuerOperation(Long compteId, OperationRequest request) {
        String typeOp = request.getTypeOperation().toUpperCase();
        List<String> operationsDebit = Arrays.asList("RETRAIT", "VIREMENT_EMIS", "PAIEMENT_FACTURE", "PAIEMENT_CARTE",
                "FRAIS_BANCAIRES");
        List<String> operationsCredit = Arrays.asList("VERSEMENT", "VIREMENT_RECU", "REMISE_CHEQUE");
        Compte compte = compteRepository.findById(compteId)
                .orElseThrow(() -> new RuntimeException("Compte introuvable"));

        if (operationsDebit.contains(typeOp)) {
            compte.setSolde(compte.getSolde().subtract(request.getMontant()));
        } else if (operationsCredit.contains(typeOp)) {
            compte.setSolde(compte.getSolde().add(request.getMontant()));
        } else {
            throw new RuntimeException("Type d'opération non reconnu : " + typeOp);
        }

        Compte compteMaj = compteRepository.save(compte);

        HistoriqueOperation historique = new HistoriqueOperation();
        historique.setDateHeureOperation(LocalDateTime.now());
        historique.setTypeOperation(request.getTypeOperation().toUpperCase());
        historique.setMontant(request.getMontant());
        historique.setClient(compte.getClient());

        historiqueRepository.save(historique);

        // Envoi d'un message Kafka enrichi (JSON) avec les détails de l'opération
        String clientIdStr = String.valueOf(compte.getClient().getId());
        String kafkaPayload = String.format(java.util.Locale.US,
                "{\"clientId\":%s,\"typeOperation\":\"%s\",\"montant\":%.2f}",
                clientIdStr, request.getTypeOperation().toUpperCase(), request.getMontant());
        kafkaTemplate.send(TOPIC_KAFKA, kafkaPayload);
        System.out.println("🚀 Événement Kafka envoyé : " + kafkaPayload);

        return compteMaj;
    }

}