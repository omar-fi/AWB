import Keycloak from 'keycloak-js';

/**
 * Instance Keycloak unique (singleton).
 *
 * On exporte une seule instance partagée dans toute l'application
 * pour éviter les doubles initialisations et les conflits de token.
 *
 * Serveur : http://localhost:8080
 * Realm   : digitalbank-realm
 * Client  : react-frontend (Public client, PKCE activé dans Keycloak)
 */
const keycloak = new Keycloak({
  url:      'http://localhost:8081',
  realm:    'digitalbank-realm',
  clientId: 'react-frontend',
});

export default keycloak;
