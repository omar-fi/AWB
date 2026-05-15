package com.digitalbank.keycloak.federation;

import org.keycloak.component.ComponentModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.storage.UserStorageProviderFactory;

/**
 * Factory pour enregistrer le bridge MySQL dans Keycloak.
 */
public class MyUserStorageProviderFactory implements UserStorageProviderFactory<MyUserStorageProvider> {

    public static final String PROVIDER_ID = "mysql-bridge";

    @Override
    public MyUserStorageProvider create(KeycloakSession session, ComponentModel model) {
        return new MyUserStorageProvider(session, model);
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getHelpText() {
        return "Fédération d'utilisateurs MySQL (Table: utilisateurs)";
    }
}
