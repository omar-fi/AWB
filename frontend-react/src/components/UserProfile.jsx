import React, { useState, useEffect } from 'react';
import keycloak from '../keycloak';
import api from '../api/axiosConfig';
import { LogOut, User, Shield, Loader2, AlertCircle } from 'lucide-react';

/**
 * UserProfile — Composant d'exemple d'intégration Keycloak.
 *
 * Démontre :
 *  - Lecture des infos utilisateur depuis keycloak.tokenParsed
 *  - Appel API sécurisé via l'instance Axios configurée
 *  - Déconnexion Keycloak (SSO logout — invalide la session sur le serveur)
 */
const UserProfile = () => {
  const [profile, setProfile]   = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error,   setError]     = useState(null);

  // ── Infos extraites directement du JWT Keycloak ──────────────────────────
  const tokenParsed    = keycloak.tokenParsed ?? {};
  const username       = tokenParsed.preferred_username ?? 'Utilisateur inconnu';
  const fullName       = tokenParsed.name              ?? username;
  const email          = tokenParsed.email             ?? '—';
  const roles          = tokenParsed.realm_access?.roles ?? [];

  // ── Appel API sécurisé au chargement ─────────────────────────────────────
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        // Le token JWT est injecté automatiquement par l'intercepteur Axios
        const response = await api.get('/users/profile');
        setProfile(response.data);
      } catch (err) {
        console.error('[UserProfile] Erreur chargement profil :', err);
        setError('Impossible de charger le profil depuis l\'API.');
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []);

  // ── Déconnexion Keycloak (SSO — invalide aussi la session Keycloak) ───────
  const handleLogout = () => {
    keycloak.logout({
      // Redirige vers la racine après déconnexion
      redirectUri: window.location.origin,
    });
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{ fontFamily: "'Inter', sans-serif" }}
      className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-6"
    >
      <div className="w-full max-w-md bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl">

        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)' }}
            >
              <User size={22} color="white" />
            </div>
            <div>
              <h1 className="text-white font-black text-lg leading-tight">Mon Profil</h1>
              <p className="text-white/40 text-xs font-medium">Session Keycloak active</p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all
                       bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 hover:text-red-300"
            title="Se déconnecter"
          >
            <LogOut size={15} />
            Déconnexion
          </button>
        </div>

        {/* Infos JWT (toujours disponibles côté client) */}
        <div className="space-y-3 mb-6">
          <InfoRow label="Utilisateur"  value={fullName}  />
          <InfoRow label="Login"        value={username}  />
          <InfoRow label="Email"        value={email}     />

          {/* Badge des rôles Keycloak */}
          <div className="flex items-start gap-3 py-3 border-b border-white/10">
            <span className="text-white/40 text-xs font-bold uppercase tracking-widest w-24 pt-0.5 flex-shrink-0">
              Rôles
            </span>
            <div className="flex flex-wrap gap-2">
              {roles.length > 0 ? roles.map((role) => (
                <span
                  key={role}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold"
                  style={{ background: 'rgba(232,57,29,0.15)', color: '#FFC000' }}
                >
                  <Shield size={11} />
                  {role}
                </span>
              )) : (
                <span className="text-white/30 text-xs italic">Aucun rôle</span>
              )}
            </div>
          </div>
        </div>

        {/* Données issues de l'API Spring Boot */}
        <div
          className="rounded-2xl p-4"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
        >
          <p className="text-white/40 text-xs font-bold uppercase tracking-widest mb-3">
            Données API Backend
          </p>

          {loading && (
            <div className="flex items-center gap-2 text-white/50 text-sm">
              <Loader2 size={16} className="animate-spin" />
              Chargement...
            </div>
          )}

          {error && !loading && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {profile && !loading && (
            <pre className="text-green-400 text-xs overflow-auto rounded-lg">
              {JSON.stringify(profile, null, 2)}
            </pre>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-white/20 text-xs font-bold uppercase tracking-widest mt-6">
          AWB · Sécurisé par Keycloak SSO
        </p>
      </div>
    </div>
  );
};

// ─── Sous-composant utilitaire ───────────────────────────────────────────────
const InfoRow = ({ label, value }) => (
  <div className="flex items-center gap-3 py-3 border-b border-white/10">
    <span className="text-white/40 text-xs font-bold uppercase tracking-widest w-24 flex-shrink-0">
      {label}
    </span>
    <span className="text-white font-semibold text-sm">{value}</span>
  </div>
);

export default UserProfile;
