import { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import { X, Save, User } from 'lucide-react';

export default function EditClientModal({ isOpen, onClose, onClientUpdated, client }) {
  const [nomComplet, setNomComplet] = useState('');
  const [cin, setCin] = useState('');
  const [email, setEmail] = useState('');
  const [telephone, setTelephone] = useState('');
  const [segmentMetier, setSegmentMetier] = useState('PARTICULIER');

  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    if (client) {
      setNomComplet(client.nomComplet || '');
      setCin(client.cin || '');
      setEmail(client.email || '');
      setTelephone(client.telephone || '');
      setSegmentMetier(client.segmentMetier || 'PARTICULIER');
    }
  }, [client, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setChargement(true);
    setErreur(null);

    const updatedClient = {
      nomComplet,
      cin,
      email,
      telephone,
      segmentMetier
    };

    api.put(`/clients/${client.id}`, updatedClient)
      .then(() => {
        setChargement(false);
        onClientUpdated();
        onClose();
      })
      .catch(err => {
        console.error(err);
        setErreur("Erreur lors de la mise à jour du client.");
        setChargement(false);
      });
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">

        <div className="bg-[#FFC000] p-4 flex justify-between items-center text-slate-900">
          <div className="flex items-center gap-2 font-black text-lg uppercase tracking-tighter">
            <User size={20} />
            Modifier Client
          </div>
          <button onClick={onClose} className="hover:bg-black/10 p-1 rounded-md transition-colors"><X size={20} /></button>
        </div> 
        
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {erreur && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">{erreur}</div>}

          <div>
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Nom Complet</label>
            <input
              type="text" required
              value={nomComplet} onChange={(e) => setNomComplet(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#FFC000] outline-none font-bold text-slate-900"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">CIN</label>
              <input
                type="text" required
                value={cin} onChange={(e) => setCin(e.target.value)}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#FFC000] outline-none font-bold text-slate-900"
              />
            </div>
            <div>
              <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Segment</label>
              <select
                value={segmentMetier} onChange={(e) => setSegmentMetier(e.target.value)}
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#FFC000] outline-none font-bold text-slate-900"
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
              type="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#FFC000] outline-none font-bold text-slate-900"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5">Téléphone</label>
            <input
              type="tel" required
              value={telephone} onChange={(e) => setTelephone(e.target.value)}
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#FFC000] outline-none font-bold text-slate-900"
            />
          </div>

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
            <button type="button" onClick={onClose} className="px-5 py-2.5 text-slate-500 hover:bg-slate-100 rounded-xl font-black text-xs uppercase tracking-widest transition-all">Annuler</button>
            <button type="submit" disabled={chargement} className="px-6 py-2.5 bg-[#1A1A1A] text-white rounded-xl font-black text-xs uppercase tracking-widest shadow-lg hover:shadow-xl active:scale-95 transition-all flex items-center gap-2">
              {chargement ? 'Mise à jour...' : <><Save size={16} className="text-[#FFC000]" /> Enregistrer</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
