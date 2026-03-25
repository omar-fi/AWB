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

    private LocalDateTime dateDernierCalcul;

    @OneToOne
    @JoinColumn(name = "client_id")
    @JsonIgnoreProperties({"prediction", "comptes"})
    private Client client;
}