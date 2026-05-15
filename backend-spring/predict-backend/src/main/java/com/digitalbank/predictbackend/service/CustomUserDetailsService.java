package com.digitalbank.predictbackend.service;

import com.digitalbank.predictbackend.entities.Banquier;
import com.digitalbank.predictbackend.repository.BanquierRepository;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.ArrayList;

@Service
public class CustomUserDetailsService implements UserDetailsService {

    private final BanquierRepository banquierRepository;

    public CustomUserDetailsService(BanquierRepository banquierRepository) {
        this.banquierRepository = banquierRepository;
    }

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        Banquier banquier = banquierRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("Utilisateur non trouvé avec l'email: " + email));

        return new User(
                banquier.getEmail(),
                banquier.getMotDePasse(),
                new ArrayList<>() // On peut ajouter des rôles ici si nécessaire
        );
    }
}
