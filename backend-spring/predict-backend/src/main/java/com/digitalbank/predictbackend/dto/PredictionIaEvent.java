package com.digitalbank.predictbackend.dto;


import lombok.Data;
import lombok.ToString;

@Data
@ToString
public class PredictionIaEvent {
    private Long clientId;
    private Double probabilite;
    private String statut;
    private String explication;
    private String operationPrevue; // ex: "Retrait Espèces"
    private String datePrevue;      // ex: "2026-03-27"
    private String plageHorairePrevue; // ex: "09h00 - 10h00"
}