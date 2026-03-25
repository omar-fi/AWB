package com.digitalbank.predictbackend.repository;


import com.digitalbank.predictbackend.entities.PredictionVisite;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.Optional;

@Repository
public interface PredictionVisiteRepository extends JpaRepository<PredictionVisite, Long> {

    Optional<PredictionVisite> findByClientId(Long clientId);
    @Modifying
    @Query("UPDATE PredictionVisite p SET p.datePrevue = :demain WHERE p.datePrevue < :aujourdhui")
    void updateOldPredictions(LocalDate aujourdhui, LocalDate demain);
}