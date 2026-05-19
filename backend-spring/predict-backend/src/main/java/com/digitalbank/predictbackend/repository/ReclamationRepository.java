package com.digitalbank.predictbackend.repository;

import com.digitalbank.predictbackend.entities.Reclamation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ReclamationRepository extends JpaRepository<Reclamation, Long> {

    List<Reclamation> findByClientIdOrderByDateReclamationDesc(Long clientId);

    List<Reclamation> findByClientIdAndStatutOrderByDateReclamationDesc(Long clientId, String statut);

    long countByClientIdAndStatut(Long clientId, String statut);

    long countByClientId(Long clientId);
}
