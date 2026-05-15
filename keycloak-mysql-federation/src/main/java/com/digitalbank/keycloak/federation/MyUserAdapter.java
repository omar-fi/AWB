package com.digitalbank.keycloak.federation;

import org.keycloak.component.ComponentModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.storage.adapter.AbstractUserAdapterFederatedStorage;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Adaptateur pour la table 'utilisateurs'.
 * Mappe l'email sur le username Keycloak.
 */
public class MyUserAdapter extends AbstractUserAdapterFederatedStorage {

    private final String email;
    private final String fullName;
    private final String role;
    private final String agenceId;

    public MyUserAdapter(KeycloakSession session, RealmModel realm, ComponentModel model, 
                         String email, String fullName, String role, String agenceId) {
        super(session, realm, model);
        this.email = email;
        this.fullName = fullName;
        this.role = role;
        this.agenceId = agenceId;
    }

    @Override
    public String getUsername() {
        return fullName;
    }

    @Override
    public void setUsername(String username) {
        // Lecture seule
    }

    @Override
    public String getEmail() {
        return email;
    }

    @Override
    public boolean isEmailVerified() {
        return true;
    }

    @Override
    public void setEmail(String email) {
        // Lecture seule
    }

    @Override
    public String getFirstName() {
        // Extraction simple du prénom depuis le nom complet
        return fullName != null && fullName.contains(" ") ? fullName.split(" ")[0] : fullName;
    }

    @Override
    public String getLastName() {
        // Extraction simple du nom depuis le nom complet
        return fullName != null && fullName.contains(" ") ? fullName.substring(fullName.indexOf(" ") + 1) : "";
    }

    @Override
    public Map<String, List<String>> getAttributes() {
        Map<String, List<String>> attrs = super.getAttributes();
        Map<String, List<String>> myAttrs = new org.keycloak.common.util.MultivaluedHashMap<>();
        if (attrs != null) {
            myAttrs.putAll(attrs);
        }
        
        if (email != null) {
            myAttrs.put("email", Collections.singletonList(email));
        }
        if (fullName != null) {
            myAttrs.put("full_name", Collections.singletonList(fullName));
        }
        if (role != null) {
            myAttrs.put("role", Collections.singletonList(role));
        }
        if (agenceId != null) {
            // Utilisé par le backend/frontend pour assigner l'agence
            myAttrs.put("agence_id", Collections.singletonList(agenceId));
        }
        return myAttrs;
    }

    @Override
    public String getFirstAttribute(String name) {
        if ("role".equals(name)) return role;
        if ("agence_id".equals(name)) return agenceId;
        if ("email".equals(name)) return email;
        if ("full_name".equals(name)) return fullName;
        return super.getFirstAttribute(name);
    }

    @Override
    public java.util.stream.Stream<String> getAttributeStream(String name) {
        String val = getFirstAttribute(name);
        if (val != null && ("role".equals(name) || "agence_id".equals(name) || "email".equals(name) || "full_name".equals(name))) {
            return java.util.stream.Stream.of(val);
        }
        return super.getAttributeStream(name);
    }

    @Override
    public java.util.stream.Stream<org.keycloak.models.RoleModel> getRoleMappingsStream() {
        if (role != null && !role.isEmpty()) {
            org.keycloak.models.RoleModel roleModel = realm.getRole(role);
            if (roleModel != null) {
                return java.util.stream.Stream.of(roleModel);
            }
        }
        return java.util.stream.Stream.empty();
    }
}
