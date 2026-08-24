package com.digitalbank.predictbackend.entities;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;
import java.util.List;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class Client {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String cin;
    private String nomComplet;
    private String email;
    private String telephone;
    private String segmentMetier;
    private LocalDateTime dateCreation;
    
    @OneToMany(mappedBy = "client", cascade = CascadeType.ALL, fetch = FetchType.EAGER)
    @JsonIgnoreProperties("client")
    private List<Compte> comptes;
    
    @OneToOne(mappedBy = "client", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    @JsonIgnoreProperties("client")
    private PredictionVisite prediction;

    @OneToMany(mappedBy = "client", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @JsonIgnoreProperties("client")
    private List<Reclamation> reclamations;
    
    @ManyToOne
    @JoinColumn(name = "agence_id")
    @JsonIgnoreProperties("clients")
    private Agence agence;

    // ALIGNEMENT PHASE 3 : Alertes Churn & Risques
    private Double scoreChurn;
    private String niveauRisque;
}