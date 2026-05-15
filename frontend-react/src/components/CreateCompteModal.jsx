import { useState, useEffect } from 'react';
import axios from 'axios';
import { X, CreditCard, Save } from 'lucide-react';

export default function CreateCompteModal({ isOpen, onClose, onCompteCreated }) {
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [typeCompte, setTypeCompte] = useState('COURANT'); 
  const [solde, setSolde] = useState('');

  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    if (isOpen) {
      axios.get('http://localhost:8080/api/v1/clients?page=0&size=1000')
        .then(res => {
          const content = res.data.content || [];
          setClients(content);
          if (content.length > 0) {
            setClientId(content[0].id);
          }
        })
        .catch(err => console.error("Erreur de chargement des clients", err));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setChargement(true);
    setErreur(null);

    const nouveauCompte = {
      typeCompte: typeCompte,
      solde: parseFloat(solde),
    };

    axios.post(`http://localhost:8080/api/v1/comptes/client/${clientId}`, nouveauCompte)
      .then(() => {
        setChargement(false);
        setSolde('');
        setTypeCompte('COURANT');
        onCompteCreated(); 
        onClose(); 
      })
      .catch(err => { 
        console.error(err);
        setErreur("Erreur lors de la création du compte.");
        setChargement(false);
      });
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">

        <div className="bg-[#E74C3C] p-4 flex justify-between items-center text-white">
          <div className="flex items-center gap-2 font-bold text-lg">
            <CreditCard size={20} className="text-[#FDB913]" />
            Ouvrir un Compte Bancaire
          </div>
          <button onClick={onClose} className="hover:bg-[#C0392B] p-1 rounded-md transition-colors"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {erreur && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">{erreur}</div>}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Client Titulaire</label>
            <select
              required
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            >
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.cin} - {c.nomComplet}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type de Compte</label>
            <select 
              className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
              value={typeCompte}
              onChange={(e) => setTypeCompte(e.target.value)}
            >
              <option value="COURANT">Compte Courant (CHE)</option>
              <option value="EPARGNE">Compte d'Épargne (EPA)</option>
              <option value="DEVISE">Compte Devise (DEV)</option>
              <option value="ENTREPRISE">Compte Entreprise (ENT)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Solde Initial (MAD)</label>
            <input
              type="number"
              step="0.01"
              required
              placeholder="Ex: 5000"
              value={solde}
              onChange={(e) => setSolde(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            />
          </div>

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-gray-100">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium">Annuler</button>
            <button type="submit" disabled={chargement} className="px-4 py-2 bg-[#E74C3C] hover:bg-[#C0392B] text-white rounded-lg font-medium flex items-center gap-2">
              {chargement ? 'Création...' : <><Save size={18} /> Valider</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}