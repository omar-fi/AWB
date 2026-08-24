package com.digitalbank.predictbackend.repository;


import com.digitalbank.predictbackend.entities.PredictionVisite;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface PredictionVisiteRepository extends JpaRepository<PredictionVisite, Long> {

    Optional<PredictionVisite> findByClientId(Long clientId);

    @Modifying
    @Query("UPDATE PredictionVisite p SET p.datePrevue = :demain WHERE p.datePrevue < :aujourdhui")
    void updateOldPredictions(@Param("aujourdhui") LocalDate aujourdhui, @Param("demain") LocalDate demain);
    
    @EntityGraph(attributePaths = {"client", "client.comptes"})
    @Query("SELECT p FROM PredictionVisite p JOIN p.client c WHERE c.agence.id = :agenceId AND p.datePrevue = :aujourdHui")
    List<PredictionVisite> findPredictionsDuJourByAgence(@Param("agenceId") Long agenceId, @Param("aujourdHui") LocalDate aujourdHui);

    @EntityGraph(attributePaths = {"client", "client.comptes"})
    @Query("SELECT p FROM PredictionVisite p JOIN p.client c WHERE c.agence.id = :agenceId AND p.datePrevue = :aujourdHui AND p.scoreProbabiliteGlobal >= 80")
    List<PredictionVisite> findHighProbabilityPredictionsDuJourByAgence(@Param("agenceId") Long agenceId, @Param("aujourdHui") LocalDate aujourdHui);

    @EntityGraph(attributePaths = {"client", "client.comptes"})
    @Query("SELECT p FROM PredictionVisite p JOIN p.client c WHERE c.agence.id = :agenceId ORDER BY p.datePrevue ASC")
    List<PredictionVisite> findAllByAgenceId(@Param("agenceId") Long agenceId);

    /**
     * Visites attendues sur une fenêtre de dates, pour le flux d'affluence du
     * directeur.
     *
     * La date retenue est la date ajustée quand elle existe : c'est celle que
     * le conseiller a corrigée à la main, donc celle qui fait foi sur le
     * planning de l'agence.
     */
    @EntityGraph(attributePaths = {"client"})
    @Query("SELECT p FROM PredictionVisite p JOIN p.client c WHERE c.agence.id = :agenceId " +
           "AND ((p.datePrevueAjustee IS NOT NULL AND p.datePrevueAjustee BETWEEN :debut AND :fin) " +
           "  OR (p.datePrevueAjustee IS NULL AND p.datePrevue BETWEEN :debut AND :fin))")
    List<PredictionVisite> findFluxByAgenceEntre(@Param("agenceId") Long agenceId,
                                                 @Param("debut") LocalDate debut,
                                                 @Param("fin") LocalDate fin);
}