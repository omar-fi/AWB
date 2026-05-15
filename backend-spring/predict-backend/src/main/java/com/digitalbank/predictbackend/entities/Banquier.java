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

    @Enumerated(EnumType.STRING)
    private RoleBanquier role;

    @ManyToOne
    @JoinColumn(name = "agence_id")
    private Agence agence;

    private Double objectifMensuel;

    @Convert(converter = com.digitalbank.predictbackend.config.StringListConverter.class)
    @Column(columnDefinition = "TEXT")
    private java.util.List<String> permissions = new java.util.ArrayList<>();
}