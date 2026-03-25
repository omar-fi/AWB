package com.digitalbank.predictbackend.dto;


import lombok.Data;
import java.math.BigDecimal;

@Data
public class OperationRequest {
    private String typeOperation;
    private BigDecimal montant;
    // Constructeur par défaut obligatoire pour Spring (Jackson)
    public OperationRequest() {}

    public String getTypeOperation() {
        return typeOperation;
    }

    public void setTypeOperation(String typeOperation) {
        this.typeOperation = typeOperation;
    }

    public BigDecimal getMontant() {
        return montant;
    }

    public void setMontant(BigDecimal montant) {
        this.montant = montant;
    }
}
