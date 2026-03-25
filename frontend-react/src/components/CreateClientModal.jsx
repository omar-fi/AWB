import { useState } from 'react';
import axios from 'axios';
import { X, UserPlus, Save, Building } from 'lucide-react';

export default function CreateClientModal({ isOpen, onClose, onClientCreated }) {
  const [nomComplet, setNomComplet] = useState('');
  const [cin, setCin] = useState('');
  const [email, setEmail] = useState('');
  const [segmentMetier, setSegmentMetier] = useState('PARTICULIER');

  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);

  // 1. On récupère automatiquement les données du banquier connecté
  const banquierData = JSON.parse(localStorage.getItem('banquierConnecte') || '{}');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setChargement(true);
    setErreur(null);

    if (!banquierData.agenceId) {
      setErreur("Erreur : aucune agence associée. Veuillez vous reconnecter.");
      setChargement(false);
      return;
    }

    // 2. On affecte le client à l'agence du banquier de manière invisible
    const nouveauClient = {
      nomComplet,
      cin,
      email,
      segmentMetier,
      agence: { id: banquierData.agenceId } // <-- L'association automatique est ici
    };

    axios.post('http://localhost:8080/api/v1/clients', nouveauClient)
      .then(() => {
        setChargement(false);
        setNomComplet('');
        setCin('');
        setEmail('');
        setSegmentMetier('PARTICULIER');

        onClientCreated();
        onClose();
      })
      .catch(err => {
        console.error(err);
        setErreur("Erreur lors de la création du client.");
        setChargement(false);
      });
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">

        <div className="bg-[#E74C3C] p-4 flex justify-between items-center text-white">
          <div className="flex items-center gap-2 font-bold text-lg">
            <UserPlus size={20} className="text-[#FDB913]" />
            Nouveau Client
          </div>
          <button onClick={onClose} className="hover:bg-[#C0392B] p-1 rounded-md transition-colors"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {erreur && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">{erreur}</div>}

          {/* Affichage informatif de l'agence (Non modifiable) */}
          <div className="bg-gray-50 p-3 rounded-lg flex items-center gap-3 border border-gray-100">
            <Building size={18} className="text-gray-400" />
            <div className="text-sm">
              <span className="text-gray-500">Affectation automatique : </span>
              <strong className="text-gray-800">{banquierData.agenceNom}</strong>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nom Complet</label>
            <input
              type="text" required placeholder="Ex: Omar Filali"
              value={nomComplet} onChange={(e) => setNomComplet(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CIN</label>
              <input
                type="text" required placeholder="Ex: AB123456"
                value={cin} onChange={(e) => setCin(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Segment</label>
              <select
                value={segmentMetier} onChange={(e) => setSegmentMetier(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
              >
                <option value="PARTICULIER">Particulier</option>
                <option value="PROFESSIONNEL">Professionnel</option>
                <option value="VIP">VIP</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email" required placeholder="Ex: omar@email.com"
              value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#E74C3C] outline-none"
            />
          </div>

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-gray-100">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium">Annuler</button>
            <button type="submit" disabled={chargement} className="px-4 py-2 bg-[#E74C3C] hover:bg-[#C0392B] text-white rounded-lg font-medium flex items-center gap-2">
              {chargement ? 'Création...' : <><Save size={18} /> Enregistrer</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}