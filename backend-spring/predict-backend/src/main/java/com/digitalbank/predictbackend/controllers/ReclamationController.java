package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.Reclamation;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.ReclamationRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/reclamations")
@CrossOrigin(origins = "http://localhost:5173")
public class ReclamationController {

    private final ReclamationRepository reclamationRepository;
    private final ClientRepository clientRepository;

    public ReclamationController(ReclamationRepository reclamationRepository,
                                 ClientRepository clientRepository) {
        this.reclamationRepository = reclamationRepository;
        this.clientRepository = clientRepository;
    }

    /** Liste toutes les réclamations d'un client */
    @GetMapping("/client/{clientId}")
    public ResponseEntity<List<Reclamation>> getByClient(@PathVariable Long clientId) {
        List<Reclamation> list = reclamationRepository.findByClientIdOrderByDateReclamationDesc(clientId);
        return ResponseEntity.ok(list);
    }

    /** Crée une nouvelle réclamation pour un client */
    @PostMapping
    public ResponseEntity<Reclamation> creerReclamation(@RequestBody Map<String, Object> body) {
        Long clientId = Long.parseLong(body.get("clientId").toString());
        Client client = clientRepository.findById(clientId)
                .orElseThrow(() -> new RuntimeException("Client introuvable : " + clientId));

        Reclamation r = new Reclamation();
        r.setClient(client);
        r.setTypeReclamation(body.getOrDefault("typeReclamation", "AUTRE").toString());
        r.setDescription(body.getOrDefault("description", "").toString());
        r.setStatut("OUVERTE");
        r.setDateReclamation(LocalDateTime.now());

        return ResponseEntity.ok(reclamationRepository.save(r));
    }

    /** Met à jour le statut d'une réclamation (EN_COURS, RESOLUE) */
    @PutMapping("/{id}/statut")
    public ResponseEntity<Reclamation> mettreAJourStatut(
            @PathVariable Long id,
            @RequestBody Map<String, String> body) {

        return reclamationRepository.findById(id).map(r -> {
            String newStatut = body.getOrDefault("statut", r.getStatut());
            r.setStatut(newStatut);
            if ("RESOLUE".equals(newStatut) && r.getDateResolution() == null) {
                r.setDateResolution(LocalDateTime.now());
            }
            return ResponseEntity.ok(reclamationRepository.save(r));
        }).orElse(ResponseEntity.notFound().build());
    }

    /** Supprime une réclamation */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        if (!reclamationRepository.existsById(id)) return ResponseEntity.notFound().build();
        reclamationRepository.deleteById(id);
        return ResponseEntity.ok().build();
    }

    /** Résumé des réclamations d'un client (pour l'Agent IA) */
    @GetMapping("/client/{clientId}/resume")
    public ResponseEntity<Map<String, Object>> getResume(@PathVariable Long clientId) {
        long total    = reclamationRepository.countByClientId(clientId);
        long ouvertes = reclamationRepository.countByClientIdAndStatut(clientId, "OUVERTE");
        long enCours  = reclamationRepository.countByClientIdAndStatut(clientId, "EN_COURS");
        long resolues = reclamationRepository.countByClientIdAndStatut(clientId, "RESOLUE");
        return ResponseEntity.ok(Map.of(
                "total", total,
                "ouvertes", ouvertes,
                "enCours", enCours,
                "resolues", resolues
        ));
    }
}
