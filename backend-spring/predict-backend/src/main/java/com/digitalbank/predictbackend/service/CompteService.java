package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.dto.OperationRequest;
import com.digitalbank.predictbackend.entities.Compte;
import com.digitalbank.predictbackend.entities.HistoriqueOperation;
import com.digitalbank.predictbackend.repository.CompteRepository;
import com.digitalbank.predictbackend.repository.HistoriqueOperationRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

@Service
public class CompteService {

    @Autowired
    private CompteRepository compteRepository;

    @Autowired
    private HistoriqueOperationRepository historiqueRepository;

    @Transactional
    public Compte effectuerOperation(Long compteId, OperationRequest request) {
        String typeOp = request.getTypeOperation().toUpperCase();

        // Opérations débitrices : diminuent le solde
        List<String> operationsDebit = Arrays.asList(
                "RETRAIT", "VIREMENT_EMIS", "PAIEMENT_FACTURE", "PAIEMENT_CARTE",
                "FRAIS_BANCAIRES", "RETRAIT_EPARGNE"
        );
        // Opérations créditrices : augmentent le solde
        List<String> operationsCredit = Arrays.asList(
                "VERSEMENT", "VIREMENT_RECU", "REMISE_CHEQUE", "PLACEMENT"
        );

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

        // Enregistrement dans l'historique (sera exploité par le batch nocturne Python)
        LocalDateTime eventTime = LocalDateTime.now();
        HistoriqueOperation historique = new HistoriqueOperation();
        historique.setDateHeureOperation(eventTime);
        historique.setTypeOperation(typeOp);
        historique.setMontant(request.getMontant());
        historique.setClient(compte.getClient());
        historique.setCompte(compte);
        historiqueRepository.save(historique);

        System.out.println("✅ Opération enregistrée : " + typeOp + " pour le client " + compte.getClient().getId()
                + " — sera prise en compte par le prochain batch nocturne.");

        return compteMaj;
    }
}