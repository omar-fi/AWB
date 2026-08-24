package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.repository.PredictionVisiteRepository;
import jakarta.transaction.Transactional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDate;

@Service
public class PredictionScheduler {

    @Autowired
    private PredictionVisiteRepository predictionRepository;

    @Scheduled(fixedRate = 60000)
    @Transactional
    public void actualiserDatesPerimees() {
        predictionRepository.updateOldPredictions(LocalDate.now(), LocalDate.now());
    }
}