package com.digitalbank.predictbackend.entities;

import jakarta.persistence.*;
import lombok.Data;

@Entity
@Data
public class Banquier {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String nomComplet;

    @Column(unique = true)
    private String email;

    private String motDePasse;

    @ManyToOne
    @JoinColumn(name = "agence_id")
    private Agence agence;

}