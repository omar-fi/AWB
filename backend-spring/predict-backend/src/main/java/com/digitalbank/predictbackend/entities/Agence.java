package com.digitalbank.predictbackend.entities;

import jakarta.persistence.*;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

@Entity
@Data
public class Agence {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String nomAgence;
    private String ville;
    private String adresse;

    @OneToMany(mappedBy = "agence")
    @JsonIgnore
    private List<Client> clients;

}