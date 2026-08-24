package com.digitalbank.predictbackend.entities;


import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
public class HistoriqueOperation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private LocalDateTime dateHeureOperation;

    private String typeOperation;

    /**
     * Canal par lequel l'opération a été réalisée : AGENCE, DAB, TPE,
     * EN_LIGNE ou AUTOMATIQUE.
     *
     * Seul AGENCE correspond à un déplacement du client au guichet. Sans cette
     * colonne, le canal ne pouvait être que deviné à partir du libellé, et les
     * modèles de prédiction de visite s'entraînaient sur des paiements par
     * carte — qui ne se font évidemment pas en agence.
     */
    private String canal;

    private BigDecimal montant;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id", nullable = false)
    @JsonIgnoreProperties({"reclamations", "comptes", "prediction", "actions", "hibernateLazyInitializer", "handler"})
    private Client client;

    // Permet de stocker le type de compte au moment de l'opération.
    // Utile pour prédire la prochaine visite (date/heure/opération).
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "compte_id")
    @JsonIgnoreProperties({"client", "prediction", "hibernateLazyInitializer", "handler"})
    private Compte compte;
}