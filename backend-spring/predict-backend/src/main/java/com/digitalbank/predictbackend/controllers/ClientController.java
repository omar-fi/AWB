package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.service.EmailService;
import jakarta.transaction.Transactional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable; // Le SEUL bon import pour la pagination
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDateTime;

@RestController
@RequestMapping("/api/v1/clients")
@CrossOrigin(origins = "http://localhost:5173")
public class ClientController {
    private final EmailService emailService;
    private final ClientRepository clientRepository;

    public ClientController(ClientRepository clientRepository, EmailService emailService) {
        this.clientRepository = clientRepository;
        this.emailService = emailService;
    }

    @GetMapping
    public Page<Client> getAllClients(Pageable pageable) {
        return clientRepository.findAll(pageable);
    }

    @GetMapping("/cin/{cin}")
    public Client getClientByCin(@PathVariable String cin) {
        return clientRepository.findByCin(cin)
                .orElseThrow(() -> new RuntimeException("Client introuvable avec le CIN : " + cin));
    }

    @PostMapping
    public ResponseEntity<Client> createClient(@RequestBody Client nouveauClient) {
        nouveauClient.setDateCreation(LocalDateTime.now());
        Client clientSauvegarde = clientRepository.save(nouveauClient);
        if (clientSauvegarde.getEmail() != null && !clientSauvegarde.getEmail().isEmpty()) {
            emailService.envoyerEmailBienvenue(clientSauvegarde.getEmail(), clientSauvegarde.getNomComplet());
        }
        return ResponseEntity.ok(clientSauvegarde);
    }

    @DeleteMapping("/{id}")
    @Transactional
    public ResponseEntity<?> deleteClient(@PathVariable Long id) {
        return clientRepository.findById(id).map(client -> {
            if (client.getPrediction() != null) {
                client.getPrediction().setClient(null);
            }
            clientRepository.delete(client);
            return ResponseEntity.ok().build();
        }).orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/agence/{agenceId}")
    public ResponseEntity<Page<Client>> getClientsByAgence(
            @PathVariable Long agenceId,
            Pageable pageable) {

        Page<Client> clients = clientRepository.findByAgenceId(agenceId, pageable);
        return ResponseEntity.ok(clients);
    }
}