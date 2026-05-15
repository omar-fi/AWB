package com.digitalbank.predictbackend.controllers;

import com.digitalbank.predictbackend.entities.Banquier;
import com.digitalbank.predictbackend.repository.BanquierRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/banquiers")
@CrossOrigin(origins = "http://localhost:5173")
public class BanquierController {

    @Autowired
    private BanquierRepository banquierRepository;

    private static final List<String> ALL_PERMISSIONS = Arrays.asList(
        "CAN_CREATE_ACCOUNT",
        "CAN_DELETE_ACCOUNT",
        "CAN_EDIT_CLIENT",
        "CAN_CREATE_BANK_ACCOUNT",
        "CAN_EDIT_BANK_ACCOUNT",
        "CAN_DELETE_BANK_ACCOUNT",
        "CAN_ANALYZE_CLIENTS",
        "CAN_VIEW_ALL_PREDICTIONS"
    );

    @GetMapping("/agence/{agenceId}")
    public ResponseEntity<List<Map<String, Object>>> getBanquiersAgence(@PathVariable Long agenceId) {
        List<Banquier> banquiers = banquierRepository.findByAgenceId(agenceId);
        List<Map<String, Object>> response = banquiers.stream().map(b -> {
            Map<String, Object> map = new HashMap<>();
            map.put("id", b.getId());
            map.put("nomComplet", b.getNomComplet());
            map.put("email", b.getEmail());
            map.put("role", b.getRole().name());
            map.put("permissions", b.getPermissions());
            return map;
        }).collect(Collectors.toList());
        return ResponseEntity.ok(response);
    }

    @PutMapping("/{id}/permissions")
    public ResponseEntity<?> updatePermissions(@PathVariable Long id, @RequestBody Map<String, List<String>> body) {
        List<String> perms = body.getOrDefault("permissions", List.of());
        List<String> invalid = perms.stream().filter(p -> !ALL_PERMISSIONS.contains(p)).collect(Collectors.toList());
        if (!invalid.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("detail", "Permissions inconnues : " + invalid));
        }
        
        return banquierRepository.findById(id).map(banquier -> {
            banquier.setPermissions(perms);
            banquierRepository.save(banquier);
            Map<String, Object> res = new HashMap<>();
            res.put("success", true);
            res.put("banquierId", id);
            res.put("permissions", perms);
            return ResponseEntity.ok(res);
        }).orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/me/permissions")
    public ResponseEntity<?> getMyPermissions(org.springframework.security.core.Authentication authentication) {
        String email = null;
        if (authentication instanceof org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken jwtAuth) {
            email = jwtAuth.getToken().getClaimAsString("email");
            if (email == null) {
                email = jwtAuth.getToken().getSubject(); // Fallback on 'sub' (username/id)
            }
        } else if (authentication != null) {
            email = authentication.getName();
        }

        if (email == null) {
            return ResponseEntity.status(401).body("Utilisateur non identifié");
        }

        return banquierRepository.findByEmail(email).map(b -> {
            Map<String, Object> res = new HashMap<>();
            res.put("permissions", b.getPermissions());
            res.put("allPermissions", ALL_PERMISSIONS);
            res.put("banquierId", b.getId());
            return ResponseEntity.ok(res);
        }).orElseGet(() -> {
            Map<String, Object> res = new HashMap<>();
            res.put("permissions", List.of());
            res.put("allPermissions", ALL_PERMISSIONS);
            return ResponseEntity.ok(res);
        });
    }

    @GetMapping("/{id}/permissions")
    public ResponseEntity<?> getPermissions(@PathVariable Long id) {
        return banquierRepository.findById(id).map(b -> {
            Map<String, Object> res = new HashMap<>();
            res.put("permissions", b.getPermissions());
            res.put("allPermissions", ALL_PERMISSIONS);
            res.put("banquierId", b.getId());
            return ResponseEntity.ok(res);
        }).orElseGet(() -> {
            Map<String, Object> res = new HashMap<>();
            res.put("permissions", List.of());
            res.put("allPermissions", ALL_PERMISSIONS);
            return ResponseEntity.ok(res);
        });
    }
}
