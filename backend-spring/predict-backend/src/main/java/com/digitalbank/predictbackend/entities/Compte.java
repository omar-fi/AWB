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
public class Compte {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "numero_compte", unique = true, nullable = false, length = 30)
    private String numeroCompte;
    @Column(name = "type_compte", nullable = false, length = 20)
    private String typeCompte;
    @Column(nullable = false, precision = 15, scale = 2)
    private BigDecimal solde;
    @Column(name = "date_ouverture")
    private LocalDateTime dateOuverture;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id")
    @JsonIgnoreProperties("comptes")
    private Client client;
}