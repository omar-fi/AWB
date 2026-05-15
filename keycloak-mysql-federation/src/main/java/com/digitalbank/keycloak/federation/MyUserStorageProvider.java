package com.digitalbank.keycloak.federation;

import org.keycloak.component.ComponentModel;
import org.keycloak.credential.CredentialInput;
import org.keycloak.credential.CredentialInputValidator;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.credential.PasswordCredentialModel;
import org.keycloak.storage.UserStorageProvider;
import org.keycloak.storage.user.UserLookupProvider;
import org.keycloak.storage.user.UserQueryProvider;
import org.mindrot.jbcrypt.BCrypt;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import java.util.logging.Logger;

/**
 * Provider SPI compatible Keycloak 24+ (Quarkus).
 * Fédère les utilisateurs depuis la table MySQL 'banquier'.
 */
public class MyUserStorageProvider implements 
        UserStorageProvider, 
        UserLookupProvider, 
        UserQueryProvider,
        CredentialInputValidator {

    private static final Logger logger = Logger.getLogger(MyUserStorageProvider.class.getName());

    private final KeycloakSession session;
    private final ComponentModel model;

    // Config Host Docker (depuis host.docker.internal pour atteindre XAMPP)
    private static final String DB_URL  = "jdbc:mysql://host.docker.internal:3306/attijari_predict_db";
    private static final String DB_USER = "root";
    private static final String DB_PASS = "";

    public MyUserStorageProvider(KeycloakSession session, ComponentModel model) {
        this.session = session;
        this.model   = model;
    }

    @Override
    public void close() {
        // Rien à fermer ici (on utilise try-with-resources)
    }

    // ─── RECHERCHE UTILISATEUR ──────────────────────────────────────────────

    @Override
    public UserModel getUserByUsername(RealmModel realm, String username) {
        try (Connection conn = getConnection()) {
            PreparedStatement st = conn.prepareStatement(
                "SELECT email, nom_complet, role, agence_id FROM banquier WHERE nom_complet = ? OR email = ?"
            );
            st.setString(1, username);
            st.setString(2, username);
            ResultSet rs = st.executeQuery();

            if (rs.next()) {
                return new MyUserAdapter(
                    session, realm, model,
                    rs.getString("email"),
                    rs.getString("nom_complet"),
                    rs.getString("role"),
                    rs.getString("agence_id")
                );
            }
        } catch (SQLException e) {
            logger.severe("Erreur SQL recherche par username: " + e.getMessage());
        }
        return null;
    }

    @Override
    public UserModel getUserById(RealmModel realm, String id) {
        // Format ID fédéré Keycloak → f:{componentId}:{username}
        String[] parts = id.split(":");
        if (parts.length < 3) return null;
        // parts[2] représente le username de Keycloak (qui est mappé sur le nom_complet)
        return getUserByUsername(realm, parts[2]);
    }

    @Override
    public UserModel getUserByEmail(RealmModel realm, String email) {
        try (Connection conn = getConnection()) {
            PreparedStatement st = conn.prepareStatement(
                "SELECT email, nom_complet, role, agence_id FROM banquier WHERE email = ?"
            );
            st.setString(1, email);
            ResultSet rs = st.executeQuery();

            if (rs.next()) {
                return new MyUserAdapter(
                    session, realm, model,
                    rs.getString("email"),
                    rs.getString("nom_complet"),
                    rs.getString("role"),
                    rs.getString("agence_id")
                );
            }
        } catch (SQLException e) {
            logger.severe("Erreur lors de la recherche MySQL: " + e.getMessage());
        }
        return null;
    }

    // ─── VALIDATION MOT DE PASSE (BCRYPT) ───────────────────────────────────

    @Override
    public boolean supportsCredentialType(String credentialType) {
        return PasswordCredentialModel.TYPE.equals(credentialType);
    }

    @Override
    public boolean isConfiguredFor(RealmModel realm, UserModel user, String credentialType) {
        return supportsCredentialType(credentialType);
    }

    @Override
    public boolean isValid(RealmModel realm, UserModel user, CredentialInput input) {
        if (!supportsCredentialType(input.getType())) return false;

        String passwordInput = input.getChallengeResponse();
        
        try (Connection conn = getConnection()) {
            PreparedStatement st = conn.prepareStatement(
                "SELECT mot_de_passe FROM banquier WHERE email = ?"
            );
            st.setString(1, user.getEmail());
            ResultSet rs = st.executeQuery();

            if (rs.next()) {
                String hashedPwInDb = rs.getString("mot_de_passe");
                // Vérification professionnelle via BCrypt
                return BCrypt.checkpw(passwordInput, hashedPwInDb);
            }
        } catch (SQLException e) {
            logger.severe("Erreur lors de la validation JDBC: " + e.getMessage());
        }
        return false;
    }

    private Connection getConnection() throws SQLException {
        try {
            Class.forName("com.mysql.cj.jdbc.Driver");
        } catch (ClassNotFoundException e) {
            throw new SQLException("Chargement du Driver MySQL échoué", e);
        }
        return DriverManager.getConnection(DB_URL, DB_USER, DB_PASS);
    }

    // ─── RECHERCHE MULTIPLE (USER QUERY PROVIDER) ──────────────────────────

    @Override
    public Stream<UserModel> searchForUserStream(RealmModel realm, Map<String, String> params, Integer firstResult, Integer maxResults) {
        String search = params.get(UserModel.SEARCH);
        if (search == null || search.isEmpty() || search.equals("*")) {
            search = "%";
        } else {
            search = "%" + search + "%";
        }
        
        List<UserModel> users = new ArrayList<>();
        try (Connection conn = getConnection()) {
            PreparedStatement st = conn.prepareStatement(
                "SELECT email, nom_complet, role, agence_id FROM banquier WHERE email LIKE ? OR nom_complet LIKE ?"
            );
            st.setString(1, search);
            st.setString(2, search);
            ResultSet rs = st.executeQuery();

            // Note: On pourrait gérer firstResult/maxResults avec LIMIT/OFFSET en vrai
            while (rs.next()) {
                users.add(new MyUserAdapter(
                    session, realm, model,
                    rs.getString("email"),
                    rs.getString("nom_complet"),
                    rs.getString("role"),
                    rs.getString("agence_id")
                ));
            }
        } catch (SQLException e) {
            logger.severe("Erreur lors de la recherche globale MySQL: " + e.getMessage());
        }
        return users.stream();
    }

    @Override
    public Stream<UserModel> searchForUserStream(RealmModel realm, String search, Integer firstResult, Integer maxResults) {
        return searchForUserStream(realm, Map.of(UserModel.SEARCH, search != null ? search : "*"), firstResult, maxResults);
    }

    @Override
    public Stream<UserModel> searchForUserByUserAttributeStream(RealmModel realm, String attrName, String attrValue) {
        return Stream.empty();
    }

    @Override
    public Stream<UserModel> getGroupMembersStream(RealmModel realm, org.keycloak.models.GroupModel group, Integer firstResult, Integer maxResults) {
        return Stream.empty();
    }
}
