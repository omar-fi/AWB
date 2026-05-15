import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import DashboardConseiller from './components/DashboardConseiller';
import DashboardDirecteur from './components/DashboardDirecteur';
import Login from './components/Login';
import './App.css';

/**
 * ProtectedRoute — Garde de route basée sur le rôle Keycloak.
 *
 * Avec Keycloak + onLoad:'login-required', l'utilisateur est TOUJOURS
 * authentifié quand React se monte. On vérifie uniquement le rôle.
 *
 * allowedRole : string | string[]
 */
const ProtectedRoute = ({ children, allowedRole }) => {
  const { user } = useAuth();

  // Redirection vers le login si l'utilisateur n'est pas connecté
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Sécurité défensive : s'il s'est connecté mais n'a pas de rôle valide
  if (!user.role) {
    return <RoleErrorScreen message="Aucun rôle métier trouvé dans votre compte Keycloak." />;
  }

  // Vérification du rôle autorisé
  const allowed = Array.isArray(allowedRole)
    ? allowedRole.includes(user.role)
    : user.role === allowedRole;

  if (!allowed) {
    // Redirige vers le dashboard du rôle réel de l'utilisateur
    return <Navigate to={getRolePath(user.role)} replace />;
  }

  return children;
};

/** Retourne le chemin de dashboard pour un rôle donné */
const getRolePath = (role) => {
  switch (role) {
    case 'DIRECTEUR':      return '/dashboard/directeur';
    case 'PORTEFEUILLEUR': 
    case 'COMMERCIAL':
    case 'CONSEILLER':
    default:               return '/dashboard/conseiller';
  }
};

/**
 * Redirection intelligente depuis "/" vers le dashboard du rôle connecté.
 * Keycloak garantit qu'un user est toujours connecté ici.
 */
const RootRedirect = () => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={getRolePath(user.role)} replace />;
};

/** Écran d'erreur de rôle — affiché si aucun rôle métier n'est configuré */
const RoleErrorScreen = ({ message }) => (
  <div style={{
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100vh',
    fontFamily: "'Inter', sans-serif", background: '#0F172A', color: 'white',
  }}>
    <div style={{
      background: 'rgba(232,57,29,0.1)', border: '1px solid rgba(232,57,29,0.3)',
      borderRadius: '1.5rem', padding: '2.5rem', maxWidth: '420px', textAlign: 'center',
    }}>
      <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🔐</div>
      <h2 style={{ fontWeight: 800, fontSize: '1.1rem', marginBottom: '0.75rem' }}>
        Accès non autorisé
      </h2>
      <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.875rem', lineHeight: 1.6 }}>
        {message}
        <br />
        Contactez votre administrateur Keycloak pour qu'un rôle vous soit assigné
        (<strong>CONSEILLER</strong>, <strong>PORTEFEUILLEUR</strong> ou <strong>DIRECTEUR</strong>).
      </p>
      <button
        onClick={() => {
          import('./keycloak').then(module => {
            module.default.logout({ redirectUri: window.location.origin });
          });
        }}
        style={{
          marginTop: '1.5rem', padding: '0.6rem 1.5rem',
          background: 'linear-gradient(135deg, #E8391D, #FFC000)',
          border: 'none', borderRadius: '10px', color: 'white',
          fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer',
        }}
      >
        Se déconnecter
      </button>
    </div>
  </div>
);

// ─── Application principale ──────────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Redirection racine → dashboard selon rôle Keycloak */}
          <Route path="/" element={<RootRedirect />} />

          {/* Page de connexion personnalisée */}
          <Route path="/login" element={<Login />} />

          {/* Dashboard Unifié (Conseiller / Commercial / Portefeuilleur) */}
          <Route
            path="/dashboard/conseiller"
            element={
              <ProtectedRoute allowedRole={['CONSEILLER', 'COMMERCIAL', 'PORTEFEUILLEUR']}>
                <DashboardConseiller />
              </ProtectedRoute>
            }
          />

          {/* Dashboard Directeur */}
          <Route
            path="/dashboard/directeur"
            element={
              <ProtectedRoute allowedRole="DIRECTEUR">
                <DashboardDirecteur />
              </ProtectedRoute>
            }
          />

          {/* Toute route inconnue → redirection intelligente */}
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;