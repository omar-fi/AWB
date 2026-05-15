package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.dto.OperationRequest;
import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.Compte;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.CompteRepository;
import com.digitalbank.predictbackend.service.CompteService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;

@RestController
@RequestMapping("/api/v1/comptes")
@CrossOrigin(origins = "http://localhost:5173")
public class CompteController {
    @Autowired
    private CompteService compteService;
    private final CompteRepository compteRepository;
    private final ClientRepository clientRepository;

    public CompteController(CompteRepository compteRepository, ClientRepository clientRepository) {
        this.compteRepository = compteRepository;
        this.clientRepository = clientRepository;
    }

    @GetMapping
    public ResponseEntity<Page<Compte>> getAllComptes(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "1000") int size) {
        return ResponseEntity.ok(compteRepository.findAll(PageRequest.of(page, size)));
    }

    @GetMapping("/client/{clientId}")
    public ResponseEntity<java.util.List<Compte>> getComptesByClient(@PathVariable Long clientId) {
        return ResponseEntity.ok(compteRepository.findByClientId(clientId));
    }

    @PostMapping("/client/{clientId}")
    public ResponseEntity<Compte> createCompte(@PathVariable Long clientId, @RequestBody Compte nouveauCompte) {

        Client client = clientRepository.findById(clientId)
                .orElseThrow(() -> new RuntimeException("Client introuvable avec l'ID : " + clientId));

        nouveauCompte.setClient(client);
        nouveauCompte.setDateOuverture(LocalDateTime.now());

        if (nouveauCompte.getNumeroCompte() == null || nouveauCompte.getNumeroCompte().isEmpty()) {
            String fauxRib = "RIB" + (long)(Math.random() * 100000000000000L);
            nouveauCompte.setNumeroCompte(fauxRib);
        }

        return ResponseEntity.ok(compteRepository.save(nouveauCompte));
    }
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> supprimerCompte(@PathVariable Long id) {
        compteRepository.deleteById(id);
        return ResponseEntity.noContent().build();
    }

    @PutMapping("/{id}")
    public ResponseEntity<Compte> updateCompte(@PathVariable Long id, @RequestBody Compte updatedData) {
        return compteRepository.findById(id).map(compte -> {
            if (updatedData.getNumeroCompte() != null) compte.setNumeroCompte(updatedData.getNumeroCompte());
            if (updatedData.getTypeCompte() != null) compte.setTypeCompte(updatedData.getTypeCompte());
            if (updatedData.getSolde() != null) compte.setSolde(updatedData.getSolde());
            return ResponseEntity.ok(compteRepository.save(compte));
        }).orElse(ResponseEntity.notFound().build());
    }
    @PostMapping("/{id}/operations")
    public ResponseEntity<?> effectuerOperation(@PathVariable Long id, @RequestBody OperationRequest request) {
        try {
            Compte compteMisAJour = compteService.effectuerOperation(id, request);
            return ResponseEntity.ok(compteMisAJour);
        } catch (Exception e) {
            e.printStackTrace(); // <-- AJOUTE CETTE LIGNE POUR LE DEBUG
            return ResponseEntity.badRequest().body("Erreur : " + e.getMessage());
        }
    }
}