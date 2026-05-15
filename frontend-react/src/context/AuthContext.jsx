import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import axios from 'axios';

/**
 * AuthContext — Authentification avec Token JWT personnalisé.
 * Gère manuellement le token récupéré via notre page de Login custom.
 * Inclut les permissions supplémentaires accordées par le Directeur.
 */
const AuthContext = createContext(null);

const ROLE_PRIORITY = ['DIRECTEUR', 'PORTEFEUILLEUR', 'COMMERCIAL', 'CONSEILLER'];

const extractPrimaryRole = (tokenParsed) => {
  const kcRoles = tokenParsed?.realm_access?.roles ?? [];
  const customRole = tokenParsed?.user_role;
  const allRoles = [...kcRoles];
  if (customRole) allRoles.push(customRole);
  return ROLE_PRIORITY.find((r) => allRoles.includes(r)) ?? null;
};

const buildUserFromToken = (tokenParsed, apiData = {}) => {
  if (!tokenParsed) return null;
  
  const perms = Array.isArray(apiData) ? apiData : (apiData?.permissions || []);
  const dbId = (!Array.isArray(apiData) && apiData?.banquierId) ? apiData.banquierId : tokenParsed.sub;

  return {
    id:          dbId, // ID numerique de la base de données
    keycloakId:  tokenParsed.sub,
    nomComplet:  tokenParsed.name               ?? tokenParsed.preferred_username,
    username:    tokenParsed.preferred_username ?? '',
    email:       tokenParsed.email              ?? '',
    role:        extractPrimaryRole(tokenParsed),
    agenceId:    tokenParsed.agence_id          ?? null,
    agenceNom:   tokenParsed.agence_nom         ?? '',
    permissions: perms,   // ← droits supplémentaires accordés par le Directeur
  };
};

/** Récupère les permissions et l'ID BD depuis l'API backend (via /me, résolution par email JWT) */
const fetchApiData = async (token) => {
  try {
    const res = await axios.get(
      `http://localhost:8080/api/v1/banquiers/me/permissions`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return {
      permissions: res.data?.permissions ?? [],
      banquierId: res.data?.banquierId ?? null
    };
  } catch {
    return { permissions: [], banquierId: null };
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialisation à partir du localStorage au démarrage
  useEffect(() => {
    const init = async () => {
      const token = localStorage.getItem('kc_access_token');
      if (token) {
        try {
          const decoded = jwtDecode(token);
          if (decoded.exp * 1000 > Date.now()) {
            const savedData = JSON.parse(localStorage.getItem('user_api_data') || '{"permissions":[]}');
            setUser(buildUserFromToken(decoded, savedData));
            // Rafraîchir les données depuis l'API en arrière-plan
            const apiData = await fetchApiData(token);
            localStorage.setItem('user_api_data', JSON.stringify(apiData));
            setUser(buildUserFromToken(decoded, apiData));
          } else {
            localStorage.removeItem('kc_access_token');
            localStorage.removeItem('kc_refresh_token');
            localStorage.removeItem('user_permissions');
          }
        } catch (err) {
          console.error('Erreur décodage token', err);
          localStorage.removeItem('kc_access_token');
          localStorage.removeItem('kc_refresh_token');
          localStorage.removeItem('user_permissions');
        }
      }
      setLoading(false);
    };
    init();
  }, []);

  const login = async (tokenData) => {
    if (tokenData.access_token) {
      localStorage.setItem('kc_access_token', tokenData.access_token);
      if (tokenData.refresh_token) {
        localStorage.setItem('kc_refresh_token', tokenData.refresh_token);
      }
      const decoded = jwtDecode(tokenData.access_token);
      // Charger les données depuis l'API
      const apiData = await fetchApiData(tokenData.access_token);
      localStorage.setItem('user_api_data', JSON.stringify(apiData));
      setUser(buildUserFromToken(decoded, apiData));
    }
  };

  const logout = () => {
    localStorage.removeItem('kc_access_token');
    localStorage.removeItem('kc_refresh_token');
    localStorage.removeItem('user_permissions');
    localStorage.removeItem('user_api_data');
    setUser(null);
    window.location.href = '/login';
  };

  const getToken = () => localStorage.getItem('kc_access_token');

  /** Vérifie si l'utilisateur a une permission spécifique */
  const hasPermission = (perm) => {
    if (!user) return false;
    if (user.role === 'DIRECTEUR') return true; // Le directeur a tous les droits
    return (user.permissions ?? []).includes(perm);
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      getToken,
      hasPermission,
    }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth doit être utilisé à l\'intérieur d\'un <AuthProvider>');
  }
  return context;
};
