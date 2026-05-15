package com.digitalbank.predictbackend;

import com.digitalbank.predictbackend.entities.Client;
import com.digitalbank.predictbackend.entities.Compte;
import com.digitalbank.predictbackend.repository.ClientRepository;
import com.digitalbank.predictbackend.repository.CompteRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import java.util.List;

@Component
public class DatabaseCheckRunner implements CommandLineRunner {
    private final ClientRepository clientRepository;
    private final CompteRepository compteRepository;

    public DatabaseCheckRunner(ClientRepository clientRepository, CompteRepository compteRepository) {
        this.clientRepository = clientRepository;
        this.compteRepository = compteRepository;
    }

    @Override
    public void run(String... args) throws Exception {
        System.out.println("🔍 CHECKING DATABASE STATE...");
        long clientCount = clientRepository.count();
        long compteCount = compteRepository.count();
        System.out.println("Total Clients: " + clientCount);
        System.out.println("Total Comptes: " + compteCount);
        
        if (clientCount > 0) {
            List<Client> clients = clientRepository.findAll().subList(0, (int)Math.min(5, clientCount));
            for (Client c : clients) {
                System.out.println("Client: " + c.getNomComplet() + " (ID: " + c.getId() + ")");
                if (c.getComptes() != null) {
                    System.out.println("  - Comptes count: " + c.getComptes().size());
                    for (Compte comp : c.getComptes()) {
                        System.out.println("    - Account: " + comp.getNumeroCompte());
                    }
                } else {
                    System.out.println("  - Comptes is NULL");
                }
            }
        }
    }
}
