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

    private Double fiabilite;
}