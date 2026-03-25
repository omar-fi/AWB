package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.HistoriqueOperation;
import com.digitalbank.predictbackend.repository.HistoriqueOperationRepository;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/operations")
@CrossOrigin(origins = "http://localhost:5173")
public class HistoriqueOperationController {

    private final HistoriqueOperationRepository operationRepository;

    public HistoriqueOperationController(HistoriqueOperationRepository operationRepository) {
        this.operationRepository = operationRepository;
    }

    @GetMapping("/client/{clientId}")
    public List<HistoriqueOperation> getOperationsByClient(@PathVariable Long clientId) {
        return operationRepository.findByClientId(clientId);
    }
}