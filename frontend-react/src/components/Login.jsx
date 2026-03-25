import { useState } from 'react';
import axios from 'axios';

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [erreur, setErreur] = useState('');
  const [chargement, setChargement] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    setChargement(true);
    setErreur('');

    axios.post('http://localhost:8080/api/v1/auth/login', { email, password })
      .then(res => {
        // 1. On stocke les infos du banquier dans le navigateur
        localStorage.setItem('banquierConnecte', JSON.stringify(res.data));
        
        // 2. On informe l'application que la connexion a réussi
        onLoginSuccess(res.data);
      })
      .catch(err => {
        setErreur('Identifiants incorrects. Veuillez réessayer.');
        setChargement(false);
      });
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
        <h2 className="text-2xl font-bold text-center text-[#E74C3C] mb-6">Connexion Banquier</h2>
        
        {erreur && <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">{erreur}</div>}
        
        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input 
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className="w-full p-2 border rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mot de passe</label>
            <input 
              type="password" required value={password} onChange={e => setPassword(e.target.value)}
              className="w-full p-2 border rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            />
          </div>
          <button 
            type="submit" disabled={chargement}
            className="w-full py-2 bg-[#E74C3C] hover:bg-[#C0392B] text-white font-bold rounded-lg transition-colors mt-2"
          >
            {chargement ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>
      </div>
    </div>
  );
}