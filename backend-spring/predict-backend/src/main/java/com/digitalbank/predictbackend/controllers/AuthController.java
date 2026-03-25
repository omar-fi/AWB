package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Banquier;
import com.digitalbank.predictbackend.repository.BanquierRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/auth")
@CrossOrigin("*")
public class AuthController {

    @Autowired
    private BanquierRepository banquierRepository;

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> request) {
        String email = request.get("email");
        String password = request.get("password");

        Optional<Banquier> banquierOpt = banquierRepository.findByEmail(email);


        if (banquierOpt.isPresent() && banquierOpt.get().getMotDePasse().equals(password)) {
            Banquier banquier = banquierOpt.get();

            Map<String, Object> response = new HashMap<>();
            response.put("id", banquier.getId());
            response.put("nomComplet", banquier.getNomComplet());
            response.put("agenceId", banquier.getAgence().getId());
            response.put("agenceNom", banquier.getAgence().getNomAgence());

            return ResponseEntity.ok(response);
        }

        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("Email ou mot de passe incorrect");
    }
}