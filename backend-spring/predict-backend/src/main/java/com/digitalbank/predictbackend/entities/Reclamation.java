package com.digitalbank.predictbackend.entities;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Reclamation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * Catégorie de la réclamation.
     * Valeurs : FRAIS, DELAI, ERREUR_OPERATION, COMPORTEMENT, SERVICE, AUTRE
     */
    @Column(nullable = false, length = 100)
    private String typeReclamation;

    @Column(columnDefinition = "TEXT")
    private String description;

    /**
     * Statut du traitement : OUVERTE / EN_COURS / RESOLUE
     */
    @Column(nullable = false, length = 50)
    private String statut;

    @Column(nullable = false)
    private LocalDateTime dateReclamation;

    private LocalDateTime dateResolution;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id", nullable = false)
    @JsonIgnoreProperties({"reclamations", "comptes", "prediction", "actions"})
    private Client client;
}
