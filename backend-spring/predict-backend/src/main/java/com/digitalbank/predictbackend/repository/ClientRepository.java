package com.digitalbank.predictbackend.repository;

import com.digitalbank.predictbackend.entities.Client;
import org.springframework.data.domain.Page;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import org.springframework.data.domain.Pageable;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface ClientRepository extends JpaRepository<Client, Long> {

    Optional<Client> findByCin(String cin);
    
    /**
     * Portefeuille d'une agence, les clients les plus mécontents en premier.
     *
     * Le tri doit être fait ici et non dans le navigateur : la page ne contient
     * que 10 clients sur 100, un tri côté front ne réordonnerait donc que la
     * page affichée et laisserait un client à 90 % d'insatisfaction en page 7.
     *
     * NULLS LAST : un client sans score évalué part en fin de liste. Ne pas
     * savoir n'est pas la même chose qu'aller bien, et le traiter comme
     * satisfait le rendrait invisible.
     */
    @Query(value = "SELECT DISTINCT c FROM Client c "
                 + "LEFT JOIN FETCH c.comptes LEFT JOIN FETCH c.prediction p "
                 + "WHERE c.agence.id = :agenceId "
                 + "ORDER BY CASE WHEN p.scoreInsatisfaction IS NULL THEN 1 ELSE 0 END, "
                 + "p.scoreInsatisfaction DESC",
           countQuery = "SELECT COUNT(c) FROM Client c WHERE c.agence.id = :agenceId")
    Page<Client> findByAgenceId(@Param("agenceId") Long agenceId, Pageable pageable);
    
    @EntityGraph(attributePaths = {"comptes", "prediction"})
    @Query("SELECT c FROM Client c")
    Page<Client> findAllClients(Pageable pageable);
    
    @Query("SELECT c FROM Client c JOIN c.prediction p WHERE p.datePrevue < :aujourdHui")
    List<Client> findClientsWithExpiredPredictions(@Param("aujourdHui") LocalDate aujourdHui);
    
    // ALIGNEMENT PHASE 3 : Alertes Churn
    @Query("SELECT c FROM Client c JOIN c.prediction p WHERE c.agence.id = :agenceId AND p.scoreChurn > 0.8")
    List<Client> findClientsARisqueByAgence(@Param("agenceId") Long agenceId);
}