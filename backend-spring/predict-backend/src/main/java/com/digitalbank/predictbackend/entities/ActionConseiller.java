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
public class ActionConseiller {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private LocalDateTime dateAction;

    private String categorieAction;

    private String statut;

    @Column(columnDefinition = "TEXT")
    private String commentaire;

    private String priorite; // URGENT, MOYEN, BAS

    private String typeDelegation; // APPEL, RDV, RECOUVREMENT, DOSSIER

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "banquier_id")
    @JsonIgnoreProperties({"actions", "hibernateLazyInitializer", "handler"})
    private Banquier banquier;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id")
    @JsonIgnoreProperties({"actions", "comptes", "prediction", "hibernateLazyInitializer", "handler"})
    private Client client;
}