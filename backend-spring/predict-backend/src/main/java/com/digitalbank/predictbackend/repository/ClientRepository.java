package com.digitalbank.predictbackend.repository;



import com.digitalbank.predictbackend.entities.Client;
import org.springframework.data.domain.Page;
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
    Page<Client> findByAgenceId(Long agenceId, Pageable pageable);
    @Query("SELECT c FROM Client c JOIN c.prediction p WHERE p.datePrevue < :aujourdHui")
    List<Client> findClientsWithExpiredPredictions(@Param("aujourdHui") LocalDate aujourdHui);
}