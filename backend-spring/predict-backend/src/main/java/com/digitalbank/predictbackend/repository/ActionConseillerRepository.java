package com.digitalbank.predictbackend.repository;

import com.digitalbank.predictbackend.entities.ActionConseiller;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ActionConseillerRepository extends JpaRepository<ActionConseiller, Long> {

    List<ActionConseiller> findByBanquierId(Long banquierId);

    @Query("SELECT COUNT(a) FROM ActionConseiller a JOIN a.banquier b WHERE b.agence.id = :agenceId AND a.statut = 'VENDU'")
    long countVentesReussiesByAgence(@Param("agenceId") Long agenceId);

    @Query("SELECT a FROM ActionConseiller a WHERE a.client.id = :clientId AND a.statut = :statut ORDER BY a.dateAction DESC")
    List<ActionConseiller> findInstructions(@Param("clientId") Long clientId, @Param("statut") String statut);

    Optional<ActionConseiller> findFirstByClientIdAndStatutOrderByDateActionDesc(Long clientId, String statut);

    Optional<ActionConseiller> findFirstByClientIdOrderByDateActionDesc(Long clientId);

    @Query("SELECT COUNT(DISTINCT a.client.id) FROM ActionConseiller a")
    long countUniqueClientsTreated();

    // PHASE 8: Aggregations for Executive Dashboard
    
    @Query("SELECT a.banquier.nomComplet as name, COUNT(a) as total, a.banquier.role as role, a.banquier.objectifMensuel as obj " +
           "FROM ActionConseiller a WHERE a.banquier.agence.id = :agenceId " +
           "GROUP BY a.banquier.id, a.banquier.nomComplet, a.banquier.role, a.banquier.objectifMensuel")
    List<Object[]> countPerformanceByBanquier(@Param("agenceId") Long agenceId);

    @Query("SELECT a.statut as name, COUNT(a) as value FROM ActionConseiller a WHERE a.banquier.agence.id = :agenceId GROUP BY a.statut")
    List<Object[]> countActionsByStatut(@Param("agenceId") Long agenceId);

    @Query("SELECT a FROM ActionConseiller a WHERE a.banquier.agence.id = :agenceId ORDER BY a.dateAction DESC")
    List<ActionConseiller> findTop5RecentActionsByAgence(@Param("agenceId") Long agenceId);

    // PHASE 9: Paginated Journal
    Page<ActionConseiller> findAllByBanquierAgenceIdOrderByDateActionDesc(Long agenceId, Pageable pageable);
}