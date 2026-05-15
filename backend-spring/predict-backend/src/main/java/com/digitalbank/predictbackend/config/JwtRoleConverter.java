package com.digitalbank.predictbackend.config;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Convertisseur de rôles Keycloak → Spring Security GrantedAuthority.
 *
 * Structure du claim Keycloak ciblée :
 * {
 *   "realm_access": {
 *     "roles": ["DIRECTEUR", "COMMERCIAL", "PORTEFEUILLEUR", ...]
 *   }
 * }
 *
 * Chaque rôle est préfixé par "ROLE_" pour être compatible avec
 * les expressions hasRole() / hasAnyRole() de Spring Security.
 * Ex : "DIRECTEUR" → SimpleGrantedAuthority("ROLE_DIRECTEUR")
 */
public class JwtRoleConverter implements Converter<Jwt, Collection<GrantedAuthority>> {

    private static final String CLAIM_REALM_ACCESS = "realm_access";
    private static final String CLAIM_ROLES        = "roles";
    private static final String CLAIM_USER_ROLE    = "user_role";
    private static final String ROLE_PREFIX        = "ROLE_";

    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        List<String> allRoles = new ArrayList<>();

        // 1. Récupérer le claim "realm_access"
        Map<String, Object> realmAccess = jwt.getClaimAsMap(CLAIM_REALM_ACCESS);
        if (realmAccess != null && realmAccess.containsKey(CLAIM_ROLES)) {
            @SuppressWarnings("unchecked")
            List<String> realmRoles = (List<String>) realmAccess.get(CLAIM_ROLES);
            if (realmRoles != null) {
                allRoles.addAll(realmRoles);
            }
        }

        // 2. Récupérer le claim "user_role" (peut être une String ou une List selon Keycloak)
        Object userRoleObj = jwt.getClaim("user_role");
        if (userRoleObj instanceof String) {
            allRoles.add((String) userRoleObj);
        } else if (userRoleObj instanceof List) {
            @SuppressWarnings("unchecked")
            List<String> list = (List<String>) userRoleObj;
            allRoles.addAll(list);
        }

        if (allRoles.isEmpty()) {
            return Collections.emptyList();
        }

        // 3. Mapper chaque rôle en SimpleGrantedAuthority avec le préfixe "ROLE_"
        return allRoles.stream()
                .filter(role -> role != null && !role.isBlank())
                .map(role -> {
                    String formattedRole = role.toUpperCase();
                    if (!formattedRole.startsWith(ROLE_PREFIX)) {
                        formattedRole = ROLE_PREFIX + formattedRole;
                    }
                    return new SimpleGrantedAuthority(formattedRole);
                })
                .collect(Collectors.toList());
    }
}
