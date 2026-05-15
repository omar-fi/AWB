import { useState } from 'react';
import api from '../api/axiosConfig';
import { X, UserPlus, Save, Building, CreditCard } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function CreateClientModal({ isOpen, onClose, onClientCreated }) {
  const { user } = useAuth();
  const [nomComplet, setNomComplet] = useState('');
  const [cin, setCin] = useState('');
  const [email, setEmail] = useState('');
  const [telephone, setTelephone] = useState('');
  const [segmentMetier, setSegmentMetier] = useState('PARTICULIER');

  const [numeroCompte, setNumeroCompte] = useState('');
  const [typeCompte, setTypeCompte] = useState('COURANT');
  const [solde, setSolde] = useState('');

  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setChargement(true);
    setErreur(null);

    const agenceId = user?.agence?.id || 1;

    const nouveauClient = {
      nomComplet,
      cin,
      email,
      telephone,
      segmentMetier,
      agence: { id: agenceId },
      comptes: [
        {
          numeroCompte,
          typeCompte,
          solde: solde ? parseFloat(solde) : 0,
        }
      ]
    };

    api.post('/clients', nouveauClient)
      .then(() => {
        setChargement(false);
        setNomComplet('');
        setCin('');
        setEmail('');
        setTelephone('');
        setSegmentMetier('PARTICULIER');
        setNumeroCompte('');
        setTypeCompte('COURANT');
        setSolde('');

        onClientCreated();
        onClose();
      })
      .catch(err => {
        console.error(err);
        setErreur("Erreur lors de la création du client. Vérifiez que le CIN n'existe pas déjà.");
        setChargement(false);
      });
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200 border border-white/20">

        <div className="bg-gradient-to-r from-[#E8391D] to-[#FFC000] p-5 flex justify-between items-center text-white">
          <div className="flex items-center gap-2 font-black text-lg uppercase tracking-tighter">
            <UserPlus size={22} />
            Nouveau Client
          </div>
          <button onClick={onClose} className="hover:bg-black/10 p-1.5 rounded-lg transition-colors"><X size={20} /></button>
        </div> 
        
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
          {erreur && <div className="p-3 bg-red-50 text-red-600 text-xs font-bold rounded-xl border border-red-100">{erreur}</div>}

          <div className="bg-slate-50 p-4 rounded-xl flex items-center gap-3 border border-slate-100">
            <Building size={18} className="text-[#E8391D]" />
            <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">
              Agence d'affectation : <span className="text-slate-900 ml-1">{user?.agence?.nomAgence || 'Principale'}</span>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Nom Complet</label>
            <input
              type="text" required placeholder="Ex: Omar Filali"
              value={nomComplet} onChange={(e) => setNomComplet(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">CIN</label>
              <input
                type="text" required placeholder="AB123456"
                value={cin} onChange={(e) => setCin(e.target.value)}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
              />
            </div>
            <div>
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Segment</label>
              <select
                value={segmentMetier} onChange={(e) => setSegmentMetier(e.target.value)}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
              >
                <option value="PARTICULIER">Particulier</option>
                <option value="PROFESSIONNEL">Professionnel</option>
                <option value="VIP">VIP</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Email</label>
            <input
              type="email" required placeholder="client@email.com"
              value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Téléphone</label>
            <input
              type="tel" required placeholder="0612345678"
              value={telephone} onChange={(e) => setTelephone(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
            />
          </div>

          <div className="mt-2 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 mb-4 text-[#E8391D]">
              <CreditCard size={18} />
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-800">Détails du Compte</h3>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Numéro de Compte</label>
                <input
                  type="text" required placeholder="RIB ou Numéro..."
                  value={numeroCompte} onChange={(e) => setNumeroCompte(e.target.value)}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
                />
              </div>
              <div>
                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Type de Compte</label>
                <select
                  value={typeCompte} onChange={(e) => setTypeCompte(e.target.value)}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
                >
                  <option value="COURANT">Courant</option>
                  <option value="EPARGNE">Épargne</option>
                  <option value="DEVISE">Devise</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Solde Initial (MAD)</label>
              <input
                type="number" required placeholder="Ex: 5000" min="0" step="0.01"
                value={solde} onChange={(e) => setSolde(e.target.value)}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#E8391D]/20 focus:border-[#E8391D] outline-none font-bold text-slate-900 transition-all"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
            <button type="button" onClick={onClose} className="px-5 py-2.5 text-slate-500 hover:bg-slate-100 rounded-xl font-black text-xs uppercase tracking-widest transition-all">Annuler</button>
            <button type="submit" disabled={chargement} className="px-6 py-2.5 bg-[#1A1A1A] text-white rounded-xl font-black text-xs uppercase tracking-widest shadow-lg hover:shadow-xl active:scale-95 transition-all flex items-center gap-2">
              {chargement ? 'Traitement...' : <><Save size={16} className="text-[#FFC000]" /> Créer le profil</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}