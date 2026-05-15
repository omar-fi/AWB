package com.digitalbank.predictbackend.repository;

import com.digitalbank.predictbackend.entities.Banquier;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface BanquierRepository extends JpaRepository<Banquier, Long> {
    Optional<Banquier> findByEmail(String email);
    java.util.List<Banquier> findByAgenceId(Long agenceId);
}