import { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, ChevronLeft, ChevronRight, CreditCard, Trash2 } from 'lucide-react';
import Swal from 'sweetalert2';
import OperationModal from './OperationModal';
import { ArrowRightLeft } from 'lucide-react'; 

export default function CompteTable() {
  const [comptes, setComptes] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [pageActive, setPageActive] = useState(0);
  const ITEMS_PER_PAGE = 10;
  const [compteOperationSelectionne, setCompteOperationSelectionne] = useState(null);

  // Fonction de chargement isolée pour pouvoir rafraîchir après suppression
  const chargerComptes = () => {
    setChargement(true);
    axios.get('http://localhost:8080/api/v1/comptes?page=0&size=1000')
      .then(res => {
        let donnees = [];
        if (res.data && Array.isArray(res.data.content)) {
          donnees = res.data.content;
        } else if (Array.isArray(res.data)) {
          donnees = res.data;
        }
        setComptes(donnees);
        setChargement(false);
      })
      .catch(err => {
        console.error("Erreur API Comptes:", err);
        setChargement(false);
      });
  };

  useEffect(() => {
    chargerComptes();
  }, []);

  // NOUVELLE FONCTION : SUPPRESSION DU COMPTE
  const handleSupprimerCompte = async (compteId, numeroCompte) => {
    if (window.confirm(`Voulez-vous vraiment supprimer le compte ${numeroCompte} ?`)) {
      try {
        await axios.delete(`http://localhost:8080/api/v1/comptes/${compteId}`);
        
Swal.fire({
  title: "Good job!",
  text: "Compte supprimé avec succès !",
  icon: "success"
});
        chargerComptes(); // Rafraîchir la liste
      } catch (err) {
        console.error("Erreur suppression:", err);
        Swal.fire({
  icon: "error",
  title: "Oops...",
  text: "Something went wrong!",
});
      }
    }
  };

  useEffect(() => { 
    setPageActive(0); 
  }, [recherche]);

  const comptesFiltres = (Array.isArray(comptes) ? comptes : []).filter(c => {
    if (!c) return false;
    const terme = (recherche || '').toLowerCase();
    const nomClient = (c.client && c.client.nomComplet) ? c.client.nomComplet.toLowerCase() : '';
    const numCompte = c.numeroCompte ? c.numeroCompte.toLowerCase() : '';
    const typeCompte = c.typeCompte ? c.typeCompte.toLowerCase() : '';
    return numCompte.includes(terme) || nomClient.includes(terme) || typeCompte.includes(terme);
  });

  const totalElements = comptesFiltres.length;
  const totalPages = Math.ceil(totalElements / ITEMS_PER_PAGE);
  const currentPageActive = (pageActive >= totalPages && totalPages > 0) ? 0 : pageActive;
  
  const comptesAffiches = comptesFiltres.slice(
    currentPageActive * ITEMS_PER_PAGE, 
    (currentPageActive + 1) * ITEMS_PER_PAGE
  );

  return (
    <div className="flex flex-col h-full animate-in fade-in duration-500">
      <header className="mb-8 flex flex-col gap-4">
        <h1 className="text-3xl font-bold text-gray-800">Référentiel des Comptes</h1>
        <p className="text-gray-500 mt-1">Consultez l'ensemble des comptes bancaires et leurs propriétaires.</p>
        
        <div className="flex bg-white p-4 rounded-xl shadow-sm border border-[#E74C3C]/20 w-1/3 min-w-[350px]">
          <div className="relative w-full">
            <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
            <input 
              type="text" 
              placeholder="Chercher un RIB, Nom ou Type..." 
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#E74C3C] outline-none w-full bg-[#FFF8F5]" 
            />
          </div>
        </div>
      </header>

      <div className="bg-white rounded-xl shadow-sm border border-[#E74C3C]/10 overflow-hidden flex-1 flex flex-col">
        <div className="overflow-x-auto">
          {chargement ? (
            <div className="p-12 text-center text-gray-400 animate-pulse font-medium">Chargement des comptes...</div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#FFF8F5] border-b border-[#E74C3C]/10 text-gray-700 uppercase text-xs tracking-wider font-semibold">
                  <th className="p-4">Numéro de Compte (RIB)</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Client Titulaire</th>
                  <th className="p-4">Date d'ouverture</th>
                  <th className="p-4 text-right">Solde Actuel</th>
                  <th className="p-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E74C3C]/10">
                {comptesAffiches.length > 0 ? (
                  comptesAffiches.map(compte => (
                    <tr key={compte.id} className="hover:bg-[#FFF0E6]/50 transition-colors group">
                      <td className="p-4 font-mono font-bold text-gray-800 flex items-center gap-2">
                        <CreditCard size={16} className="text-[#E74C3C]" />
                        {compte.numeroCompte}
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-1 bg-[#FFF0E6] text-[#E74C3C] border border-[#E74C3C]/20 text-xs rounded font-bold">
                          {compte.typeCompte}
                        </span>
                      </td>
                      <td className="p-4 font-bold text-gray-800">
                        {compte.client ? compte.client.nomComplet : <span className="text-red-500 italic text-xs">Client introuvable</span>}
                      </td>
                      <td className="p-4 text-gray-500 text-sm">
                        {compte.dateOuverture ? new Date(compte.dateOuverture).toLocaleDateString('fr-FR') : '-'}
                      </td>
                      <td className="p-4 text-right">
                         <span className={`font-bold px-2 py-1 rounded-lg ${compte.solde < 0 ? 'text-red-600 bg-red-50' : 'text-green-600 bg-green-50'}`}>
                            {new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD' }).format(compte.solde)}
                         </span>
                      </td>
                      <td className="p-4 text-center">
                        <button 
                          onClick={() => setCompteOperationSelectionne(compte)}
                          className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-full transition-all opacity-0 group-hover:opacity-100"
                          title="Effectuer une opération"
                        >
                          <ArrowRightLeft size={18} />
                        </button>
                        <button 
                          onClick={() => handleSupprimerCompte(compte.id, compte.numeroCompte)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-all opacity-0 group-hover:opacity-100"
                        >
                          <Trash2 size={18} />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="p-12 text-center text-gray-500 font-medium">Aucun compte ne correspond à votre recherche.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <div className="p-4 border-t border-[#E74C3C]/10 flex justify-between bg-[#FFF8F5] mt-auto">
          <span className="text-sm text-gray-600 font-medium">Page {currentPageActive + 1} sur {totalPages > 0 ? totalPages : 1} ({totalElements} comptes)</span>
          <div className="flex gap-2">
            <button onClick={() => setPageActive(p => Math.max(0, p - 1))} disabled={currentPageActive === 0} className="px-3 py-1.5 border rounded-lg bg-white disabled:opacity-50 hover:bg-gray-50 shadow-sm transition-all"><ChevronLeft size={16}/></button>
            <button onClick={() => setPageActive(p => Math.min(totalPages - 1, p + 1))} disabled={currentPageActive >= totalPages - 1} className="px-3 py-1.5 border rounded-lg bg-white disabled:opacity-50 hover:bg-gray-50 shadow-sm transition-all"><ChevronRight size={16}/></button>
          </div>
        </div>
      </div>
      <OperationModal 
        isOpen={!!compteOperationSelectionne}
        onClose={() => setCompteOperationSelectionne(null)}
        compte={compteOperationSelectionne}
        onOperationSuccess={() => {
          chargerComptes(); 
          setCompteOperationSelectionne(null);
        }}
      />
    </div>
  );
}