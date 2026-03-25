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
public class Client {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String cin;
    private String nomComplet;
    private String email;
    private String segmentMetier;
    private LocalDateTime dateCreation;
    @OneToMany(mappedBy = "client", cascade = CascadeType.ALL, fetch = FetchType.EAGER)
    @JsonIgnoreProperties("client")
    private java.util.List<Compte> comptes;
    @OneToOne(mappedBy = "client", cascade = CascadeType.ALL, orphanRemoval = true)
    @JsonIgnoreProperties("client")
    private PredictionVisite prediction;
    @ManyToOne
    @JoinColumn(name = "agence_id")
    @JsonIgnoreProperties("clients")
    private Agence agence;
}