package com.digitalbank.predictbackend.repository;



import com.digitalbank.predictbackend.entities.HistoriqueOperation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HistoriqueOperationRepository extends JpaRepository<HistoriqueOperation, Long> {
    List<HistoriqueOperation> findByClientId(Long clientId);
}