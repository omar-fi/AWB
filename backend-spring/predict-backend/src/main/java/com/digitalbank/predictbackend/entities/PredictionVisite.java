package com.digitalbank.predictbackend.entities;


import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PredictionVisite {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private LocalDate datePrevue;
    
    private LocalDate datePrevueAjustee;
    
    private String motifAjustement;

    private String plageHorairePrevue;

    private String operationPrevue;

    private Double scoreProbabiliteGlobal;
    @Column(columnDefinition = "TEXT")
    private String insightGenai;

    @Column(columnDefinition = "TEXT")
    private String strategiePrescrite;

    private LocalDateTime dateDernierCalcul;

    @OneToOne
    @JoinColumn(name = "client_id")
    @JsonIgnoreProperties({"prediction", "comptes", "agence"})
    private Client client;

    @Column(name = "score_churn")
    private Double scoreChurn;

    @Column(name = "niveau_risque")
    private String niveauRisque;

    /**
     * Mécontentement du client, de 0 à 100 (100 = au bord de la rupture).
     *
     * Distinct du score de churn, et volontairement pas son complément : le
     * risque de départ intègre la tension financière, or un client à découvert
     * n'est pas mécontent de sa banque. Ce score ne retient que le litige
     * (réclamations non traitées) et le retrait relationnel (fréquentation de
     * l'agence en baisse), c'est-à-dire ce sur quoi un conseiller peut agir.
     */
    @Column(name = "score_insatisfaction")
    private Integer scoreInsatisfaction;

    @Column(name = "niveau_satisfaction")
    private String niveauSatisfaction;

    private Double fiabilite;
}