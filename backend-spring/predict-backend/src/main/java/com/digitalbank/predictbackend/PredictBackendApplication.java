package com.digitalbank.predictbackend;

import com.digitalbank.predictbackend.entities.Agence;
import com.digitalbank.predictbackend.entities.Banquier;
import com.digitalbank.predictbackend.repository.AgenceRepository;
import com.digitalbank.predictbackend.repository.BanquierRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@EnableAsync
public class PredictBackendApplication {
    public static void main(String[] args) {
        SpringApplication.run(PredictBackendApplication.class, args);
    }

    @Bean
    CommandLineRunner start(AgenceRepository agenceRepository, BanquierRepository banquierRepository) {
        return args -> {
            // Création d'une agence par défaut si elle n'existe pas
            Agence agence = agenceRepository.findById(1L).orElseGet(() -> {
                Agence a = new Agence();
                a.setNomAgence("Agence Principale");
                a.setVille("Casablanca");
                return agenceRepository.save(a);
            });

            // Création du compte Commercial (CONSEILLER)
            if (banquierRepository.findByEmail("conseiller@awb.ma").isEmpty()) {
                Banquier b = new Banquier();
                b.setNomComplet("Commercial Test");
                b.setEmail("conseiller@awb.ma");
                b.setMotDePasse("admin");
                b.setRole(com.digitalbank.predictbackend.entities.RoleBanquier.CONSEILLER);
                b.setAgence(agence);
                b.setObjectifMensuel(50.0);
                banquierRepository.save(b);
            }

            // Création du compte Portefeuilleur
            if (banquierRepository.findByEmail("portefeuilleur@awb.ma").isEmpty()) {
                Banquier p = new Banquier();
                p.setNomComplet("Portefeuilleur Test");
                p.setEmail("portefeuilleur@awb.ma");
                p.setMotDePasse("admin");
                p.setRole(com.digitalbank.predictbackend.entities.RoleBanquier.PORTEFEUILLEUR);
                p.setAgence(agence);
                p.setObjectifMensuel(30.0);
                banquierRepository.save(p);
            }

            // Création du compte Directeur
            if (banquierRepository.findByEmail("directeur@awb.ma").isEmpty()) {
                Banquier b = new Banquier();
                b.setNomComplet("Directeur Test");
                b.setEmail("directeur@awb.ma");
                b.setMotDePasse("admin");
                b.setRole(com.digitalbank.predictbackend.entities.RoleBanquier.DIRECTEUR);
                b.setAgence(agence);
                b.setObjectifMensuel(100.0);
                banquierRepository.save(b);
            }

            System.out.println("✅ Données de test initialisées !");
        };
    }
}
