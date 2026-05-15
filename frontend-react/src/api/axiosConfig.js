import axios from 'axios';

/**
 * Instance Axios sécurisée — Backend Spring Boot.
 * Configuration centralisée pour l'injection du token JWT Keycloak.
 */
const api = axios.create({
  baseURL: 'http://localhost:8080/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercepteur de requête : injecte le token Bearer avant chaque appel
api.interceptors.request.use(
  async (config) => {
    // Récupérer le token depuis le stockage local (géré par AuthContext)
    const token = localStorage.getItem('kc_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Intercepteur de réponse : gestion des erreurs 401 et 403
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('🔴 Erreur 401 : Non autorisé. Déconnexion automatique.');
      localStorage.removeItem('kc_access_token');
      localStorage.removeItem('kc_refresh_token');
      window.location.href = '/login';
    }
    if (error.response?.status === 403) {
      console.error('🟠 Erreur 403 : Accès interdit. Vérifiez vos rôles. (Axios)');
    }
    return Promise.reject(error);
  }
);

export default api;
