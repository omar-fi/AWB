import React, { useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Lock, Mail, Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react';
import awbLogo from '../assets/react.jpeg';

const Login = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPassword, setShowPassword] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // Requête Direct Access Grant (ROPC) vers Keycloak
            const response = await axios.post(
                'http://localhost:8081/realms/digitalbank-realm/protocol/openid-connect/token',
                new URLSearchParams({
                    client_id: 'react-frontend',
                    grant_type: 'password',
                    username: formData.email,
                    password: formData.password
                }),
                {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                }
            );
            
            // La réponse contient access_token, refresh_token, etc.
            const tokenData = response.data;
            
            // Await login() : il est async car il charge les permissions depuis l'API
            await login(tokenData);
            
            // Redirection après que le user et ses permissions soient chargés
            navigate('/');
        } catch (err) {
            console.error('Login Error:', err);
            const status = err?.response?.status;
            if (status === 400 || status === 401) {
                setError('Identifiants incorrects. Vérifiez votre email et mot de passe.');
            } else if (!err?.response) {
                setError('Serveur Keycloak injoignable (port 8081). Vérifiez que Keycloak est démarré.');
            } else {
                setError('Erreur de connexion. Veuillez réessayer.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex" style={{ fontFamily: "'Inter', sans-serif" }}>
            {/* Panneau gauche — Branding AWB */}
            <div
                className="hidden lg:flex flex-col justify-between w-1/2 p-12 relative overflow-hidden"
                style={{ background: 'linear-gradient(160deg, #FFC000 0%, #E8391D 60%, #1A1A1A 100%)' }}
            >
                {/* Motif décoratif (zigzag inspiré du logo) */}
                <div className="absolute inset-0 pointer-events-none opacity-10">
                    <svg viewBox="0 0 600 600" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
                        <polyline points="0,200 100,120 200,200 300,120 400,200 500,120 600,200" fill="none" stroke="black" strokeWidth="40"/>
                        <polyline points="0,300 100,220 200,300 300,220 400,300 500,220 600,300" fill="none" stroke="black" strokeWidth="40"/>
                        <polyline points="0,400 100,320 200,400 300,320 400,400 500,320 600,400" fill="none" stroke="black" strokeWidth="40"/>
                    </svg>
                </div>

                {/* Logo */}
                <div className="relative z-10">
                    <img src={awbLogo} alt="AWB Logo" className="w-20 h-20 rounded-2xl shadow-2xl object-contain bg-white p-1" />
                </div>

                {/* Texte central */}
                <div className="relative z-10">
                    <h2 className="text-4xl font-black text-white leading-tight mb-4">
                        Intelligence Artificielle<br/>au service de la<br/>banque de demain.
                    </h2>
                    <p className="text-white/70 text-base font-medium leading-relaxed">
                        Prédictions XGBoost · Insights GenAI · Pilotage en temps réel
                    </p>
                </div>

                {/* Footer branding */}
                <div className="relative z-10">
                    <p className="text-white/40 text-xs font-bold tracking-widest uppercase">
                        © Attijariwafa Bank · Front Office AI 2026
                    </p>
                </div>
            </div>

            {/* Panneau droit — Formulaire */}
            <div className="flex-1 flex items-center justify-center bg-[#F5F5F5] px-6 py-12">
                <div className="w-full max-w-md">
                    {/* Logo mobile */}
                    <div className="flex justify-center mb-8 lg:hidden">
                        <img src={awbLogo} alt="AWB Logo" className="w-16 h-16 rounded-xl object-contain bg-white p-1 shadow-md" />
                    </div>

                    {/* Card */}
                    <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8">
                        <div className="mb-8">
                            <h1 className="text-2xl font-black text-[#1A1A1A] tracking-tight">Espace Collaborateur</h1>
                            <p className="text-gray-500 text-sm mt-1.5">Connectez-vous à votre interface interne AWB</p>
                        </div>

                        {error && (
                            <div className="mb-6 bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start gap-3">
                                <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={18} />
                                <p className="text-sm text-red-700 font-medium">{error}</p>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-5">
                            {/* Email */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">Email Professionnel</label>
                                <div className="relative">
                                    <input
                                        type="email"
                                        required
                                        className="w-full pl-11 pr-4 py-3 rounded-xl border border-gray-200 bg-gray-50 focus:bg-white focus:border-[#E8391D] focus:ring-2 focus:ring-[#E8391D]/15 transition-all outline-none text-sm font-medium"
                                        placeholder="nom@attijariwafa.ma"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    />
                                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={17} />
                                </div>
                            </div>

                            {/* Password */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">Mot de passe</label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        required
                                        className="w-full pl-11 pr-11 py-3 rounded-xl border border-gray-200 bg-gray-50 focus:bg-white focus:border-[#E8391D] focus:ring-2 focus:ring-[#E8391D]/15 transition-all outline-none text-sm font-medium"
                                        placeholder="••••••••"
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    />
                                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={17} />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(v => !v)}
                                        className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                                    >
                                        {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                                    </button>
                                </div>
                            </div>

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-black text-sm text-white shadow-lg transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                                style={{ background: loading ? '#ccc' : 'linear-gradient(135deg, #E8391D 0%, #FFC000 100%)' }}
                            >
                                {loading ? <Loader2 className="animate-spin" size={20} /> : 'Se connecter →'}
                            </button>
                        </form>

                        {/* Footer */}
                        <p className="text-center text-xs text-gray-300 mt-6 font-bold uppercase tracking-widest">
                            Attijariwafa Bank · Accès Sécurisé
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;