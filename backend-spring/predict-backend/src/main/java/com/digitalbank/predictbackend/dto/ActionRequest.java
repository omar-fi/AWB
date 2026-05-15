package com.digitalbank.predictbackend.dto;

import lombok.Data;

@Data
public class ActionRequest {
    private Long banquierId;
    private Long clientId;
    private String statut;
    private String commentaire;
    private String priorite;
    private String typeDelegation;
    private String categorie;
}