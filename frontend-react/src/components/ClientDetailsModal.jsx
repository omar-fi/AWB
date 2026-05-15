import React, { useState, useEffect } from 'react';
import { X, User, CreditCard, BrainCircuit, Target, AlertTriangle, Trash2, History, ArrowUpRight, ArrowDownRight, Activity, CalendarDays, Wallet, Send, ShieldAlert, Edit } from 'lucide-react';
import api from '../api/axiosConfig';
import { useAuth } from '../context/AuthContext';
import Swal from 'sweetalert2';

const getDiagnosticText = (text) => {
  if (!text) return '';
  const beforeStrategy = String(text).split(/Strategie\s*:|Stratégie\s*:/i)[0].trim();
  return beforeStrategy.replace(/^Sante\s*:|^Santé\s*:/i, '').trim();
};

export default function ClientDetailsModal({ isOpen, onClose, client }) {
  const { user, hasPermission } = useAuth();
  const [historique, setHistorique] = useState([]);
  const [comptes, setComptes] = useState([]);
  const [loadingHistorique, setLoadingHistorique] = useState(false);
  const [activeTab, setActiveTab] = useState('comptes'); // 'comptes', 'historique', 'ia', 'delegation'
  const [delegationForm, setDelegationForm] = useState({ 
    priorite: 'HAUTE', 
    commentaire: '', 
    servicePropose: '',
    mode: 'DELEGATION', // 'DELEGATION' or 'DIRECT_ACTION'
    statut: 'VENDU'
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleDelegationSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    const isDelegation = delegationForm.mode === 'DELEGATION';
    try {
        await api.post('/actions', {
            banquierId: user.id,
            clientId: client.id,
            statut: isDelegation ? 'A_TRAITER' : delegationForm.statut,
            commentaire: `[${delegationForm.servicePropose}] ${delegationForm.commentaire}`,
            priorite: delegationForm.priorite,
            typeDelegation: isDelegation ? 'ANALYSE_RISQUE' : 'ACTION_DIRECTE',
            categorie: isDelegation ? 'DELEGATION' : 'VENTE'
        });
        Swal.fire({ 
            icon: 'success', 
            title: isDelegation ? 'Délégation envoyée' : 'Action enregistrée', 
            text: isDelegation ? 'Le conseiller a reçu vos instructions.' : 'Votre proposition a été enregistrée pour le pilotage admin.', 
            confirmButtonColor: '#E8391D' 
        });
        setActiveTab('comptes');
        setDelegationForm({ priorite: 'HAUTE', commentaire: '', servicePropose: '', mode: 'DELEGATION', statut: 'VENDU' });
    } catch (err) {
        console.error(err);
        Swal.fire({ icon: 'error', title: 'Erreur', text: 'Impossible d\'enregistrer l\'action.', confirmButtonColor: '#E8391D' });
    } finally {
        setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (isOpen && client?.id) {
      setLoadingHistorique(true);
      setActiveTab('comptes');
      api.get(`/operations/client/${client.id}`)
        .then(response => {
          const ops = response.data || [];
          ops.sort((a, b) => new Date(b.dateHeureOperation) - new Date(a.dateHeureOperation));
          setHistorique(ops.slice(0, 10)); // keep last 10
        })
        .catch(err => {
          console.error("Erreur chargement historique:", err);
        })
        .finally(() => setLoadingHistorique(false));

      // Fetch comptes
      api.get(`/comptes/client/${client.id}`)
        .then(response => {
          setComptes(response.data || []);
        })
        .catch(err => console.error("Erreur comptes:", err));
    }
  }, [isOpen, client]);

  if (!isOpen || !client) return null;

  const canAnalyzeClient = user.role === 'PORTEFEUILLEUR' || user.role === 'DIRECTEUR' || hasPermission('CAN_ANALYZE_CLIENTS');
  const tabs = [
    { id: 'comptes', label: 'Portefeuille & Comptes', icon: Wallet },
    { id: 'historique', label: 'Historique des Opérations', icon: History },
    ...(canAnalyzeClient ? [{ id: 'ia', label: 'Diagnostic IA XGBoost', icon: BrainCircuit }] : []),
    { id: 'delegation', label: canAnalyzeClient ? 'Délégation & Services' : 'Visite & Vente', icon: Send }
  ];

  const handleSupprimerCompte = async (compteId, numeroCompte) => {
    const confirmation = window.confirm(
      `⚠️ AVERTISSEMENT CRITIQUE\n\nVous êtes sur le point de supprimer DÉFINITIVEMENT le compte N° ${numeroCompte}.\nConfirmez-vous cette action ?`
    );
    if (confirmation) {
      try {
        await api.delete(`/comptes/${compteId}`);
        alert("✅ Succès: Compte supprimé.");
        onClose();
      } catch (err) {
        console.error("Erreur lors de la suppression:", err);
        alert("❌ Erreur: Impossible de supprimer le compte en raison de dépendances système.");
      }
    }
  };

  const handleAjouterCompte = async () => {
    const { value: formValues } = await Swal.fire({
      title: 'Ajouter un nouveau compte',
      background: '#141414',
      color: '#fff',
      html:
        '<input id="swal-input1" class="swal2-input" style="background:#262626; color:white; border:1px solid #444" placeholder="Type de compte (ex: Compte Chèque)">' +
        '<input id="swal-input2" class="swal2-input" style="background:#262626; color:white; border:1px solid #444" placeholder="Solde Initial">',
      focusConfirm: false,
      showCancelButton: true,
      confirmButtonText: 'Créer',
      confirmButtonColor: '#10B981',
      preConfirm: () => {
        return {
          typeCompte: document.getElementById('swal-input1').value,
          solde: document.getElementById('swal-input2').value
        }
      }
    });

    if (formValues) {
      try {
        await api.post(`/comptes/client/${client.id}`, {
          typeCompte: formValues.typeCompte || 'Compte Chèque',
          solde: parseFloat(formValues.solde) || 0
        });
        Swal.fire({ icon: 'success', title: 'Compte créé !', background: '#141414', color: '#fff' });
        // Re-fetch comptes
        const res = await api.get(`/comptes/client/${client.id}`);
        setComptes(res.data || []);
      } catch (err) {
        console.error(err);
        Swal.fire({ icon: 'error', title: 'Erreur', text: 'Impossible de créer le compte.', background: '#141414', color: '#fff' });
      }
    }
  };

  const handleModifierCompte = async (compte) => {
    const { value: formValues } = await Swal.fire({
      title: 'Modifier le compte',
      background: '#141414',
      color: '#fff',
      html:
        `<input id="swal-input1" class="swal2-input" style="background:#262626; color:white; border:1px solid #444" value="${compte.typeCompte}" placeholder="Type de compte">` +
        `<input id="swal-input2" class="swal2-input" style="background:#262626; color:white; border:1px solid #444" value="${compte.numeroCompte}" placeholder="Numéro de compte">`,
      focusConfirm: false,
      showCancelButton: true,
      confirmButtonText: 'Enregistrer',
      confirmButtonColor: '#F59E0B',
      preConfirm: () => {
        return {
          typeCompte: document.getElementById('swal-input1').value,
          numeroCompte: document.getElementById('swal-input2').value
        }
      }
    });

    if (formValues) {
      try {
        await api.put(`/comptes/${compte.id}`, formValues);
        Swal.fire({ icon: 'success', title: 'Compte mis à jour !', background: '#141414', color: '#fff' });
        // Re-fetch comptes
        const res = await api.get(`/comptes/client/${client.id}`);
        setComptes(res.data || []);
      } catch (err) {
        console.error(err);
        Swal.fire({ icon: 'error', title: 'Erreur', text: 'Impossible de modifier le compte.', background: '#141414', color: '#fff' });
      }
    }
  };

  const soldeTotal = comptes ? comptes.reduce((sum, c) => sum + c.solde, 0) : 0;
  const hasPrediction = !!client.prediction;
  const rawScore = hasPrediction ? client.prediction.scoreProbabiliteGlobal : 0;
  const chanceVisite = hasPrediction ? (rawScore <= 1 ? Math.round(rawScore * 100) : Math.round(rawScore)) : 0;
  const isVisite = chanceVisite > 50;
  const score = chanceVisite;

  const getScoreStyle = (s, isV) => {
      if (!hasPrediction) return { bg: '#374151', text: '#9CA3AF', dropShadow: 'none', label: 'N/A' };
      if (isV) {
          if (s >= 80) return { bg: 'linear-gradient(135deg, #FFC000 0%, #E8391D 100%)', text: '#FFC000', dropShadow: 'drop-shadow(0 0 10px rgba(232,57,29,0.5))', label: 'Élevé' };
          if (s >= 50) return { bg: 'linear-gradient(135deg, #F97316 0%, #EF4444 100%)', text: '#F97316', dropShadow: 'drop-shadow(0 0 10px rgba(249,115,22,0.5))', label: 'Moyen' };
      }
      return { bg: 'linear-gradient(135deg, #4ADE80 0%, #059669 100%)', text: '#4ADE80', dropShadow: 'drop-shadow(0 0 10px rgba(74,222,128,0.3))', label: 'Sûr' };
  };

  const scoreStyle = getScoreStyle(score, isVisite);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" style={{ background: 'rgba(10, 10, 10, 0.75)', backdropFilter: 'blur(12px)', fontFamily: "'Inter', sans-serif" }}>
      <div className="w-full max-w-5xl rounded-[20px] overflow-hidden shadow-2xl flex flex-col h-[85vh] animate-in fade-in zoom-in-95 duration-300 border" style={{ background: '#111111', borderColor: 'rgba(255,255,255,0.1)' }}>
        
        {/* HEADER GLASSMORPHISM */}
        <div className="relative shrink-0 border-b overflow-hidden" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
            {/* Background effects */}
            <div className="absolute top-0 left-0 w-full h-full opacity-30" style={{ background: 'linear-gradient(135deg, rgba(232,57,29,0.4) 0%, rgba(255,192,0,0.1) 100%)', mixBlendMode: 'overlay' }}></div>
            <div className="absolute -top-24 -right-24 w-64 h-64 rounded-full blur-[80px] opacity-20 pointer-events-none" style={{ background: '#E8391D' }}></div>
            <div className="absolute -bottom-12 -left-12 w-48 h-48 rounded-full blur-[60px] opacity-10 pointer-events-none" style={{ background: '#FFC000' }}></div>
            
            <div className="relative p-6 px-8 flex justify-between items-start gap-4">
                <div className="flex items-center gap-5">
                    <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-black text-white shadow-lg border relative group" 
                         style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(10px)' }}>
                         {client.nomComplet?.charAt(0).toUpperCase()}
                         <div className="absolute inset-0 bg-gradient-to-tr from-[#E8391D] to-[#FFC000] opacity-0 group-hover:opacity-20 transition-opacity duration-300 rounded-2xl"></div>
                    </div>
                    <div>
                        <h2 className="text-3xl font-black text-white tracking-tight leading-none mb-2">{client.nomComplet}</h2>
                        <div className="flex flex-wrap items-center gap-3">
                            <span className="px-3 py-1 text-xs font-bold rounded-full border tracking-widest uppercase flex items-center gap-1.5" style={{ background: 'rgba(255,255,255,0.05)', color: '#9CA3AF', borderColor: 'rgba(255,255,255,0.1)' }}>
                                CIN: <span className="text-white">{client.cin}</span>
                            </span>
                            {client.email && (
                                <span className="px-3 py-1 text-xs font-bold rounded-full border tracking-wider flex items-center gap-1.5" style={{ background: 'rgba(255,255,255,0.05)', color: '#9CA3AF', borderColor: 'rgba(255,255,255,0.1)' }}>
                                    📧 <span className="text-white">{client.email}</span>
                                </span>
                            )}
                            {client.telephone && (
                                <span className="px-3 py-1 text-xs font-bold rounded-full border tracking-wider flex items-center gap-1.5" style={{ background: 'rgba(255,255,255,0.05)', color: '#9CA3AF', borderColor: 'rgba(255,255,255,0.1)' }}>
                                    📞 <span className="text-white">{client.telephone}</span>
                                </span>
                            )}
                            {client.segmentMetier && (
                                <span className="px-3 py-1 text-xs font-black rounded-full uppercase tracking-wider shadow-sm" style={{ background: '#FFF7E6', color: '#B45309' }}>
                                    {client.segmentMetier}
                                </span>
                            )}
                            <span className={`px-3 py-1 text-xs font-bold rounded-full border flex items-center gap-1.5`} style={{ borderColor: 'rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)' }}>
                                <Activity size={12} style={{ color: scoreStyle.text }} />
                                <span style={{ color: '#E5E7EB' }}>Score:</span> 
                                <span style={{ color: scoreStyle.text }}>{hasPrediction ? `${score}%` : 'N/A'}</span>
                            </span>
                        </div>
                    </div>
                </div>
                <button onClick={onClose} className="p-2.5 rounded-xl border text-gray-400 hover:text-white transition-all bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.1)] focus:outline-none focus:ring-2 focus:ring-[#E8391D]" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
                    <X size={20} />
                </button>
            </div>

            {/* TAB NAVIGATION */}
            <div className="flex px-8 gap-6 mt-2 relative z-10">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-2 pb-4 text-sm font-bold transition-all relative ${activeTab === tab.id ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
                    >
                        <tab.icon size={16} className={activeTab === tab.id ? 'opacity-100' : 'opacity-70'} style={activeTab === tab.id && tab.id === 'ia' ? { color: '#FFC000', filter: 'drop-shadow(0 0 5px rgba(255,192,0,0.5))' } : {}} />
                        {tab.label}
                        {activeTab === tab.id && (
                            <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full" style={{ background: tab.id === 'ia' ? '#FFC000' : '#E8391D', boxShadow: `0 -2px 10px ${tab.id === 'ia' ? 'rgba(255,192,0,0.6)' : 'rgba(232,57,29,0.6)'}`}}></div>
                        )}
                    </button>
                ))}
            </div>
        </div>

        {/* CONTENT AREA */}
        <div className="flex-1 overflow-y-auto p-8 relative" style={{ background: '#0A0A0A' }}>
            
            {/* PORTFOLIO TAB */}
            {activeTab === 'comptes' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xl font-black text-white flex items-center gap-3">
                            <Wallet className="text-[#E8391D]" size={22} />
                            Aperçu des Comptes
                        </h3>
                        <div className="flex items-center gap-3">
                            {(user.role === 'DIRECTEUR' || hasPermission('CAN_CREATE_BANK_ACCOUNT')) && (
                                <button
                                    onClick={handleAjouterCompte}
                                    className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs shadow-sm transition-all text-white hover:bg-emerald-600 active:scale-95"
                                    style={{ background: '#10B981' }}
                                >
                                    <Wallet size={14} /> Ajouter un compte
                                </button>
                            )}
                            <div className="px-4 py-2 rounded-xl flex items-center gap-3 border shadow-sm" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)' }}>
                                <span className="text-xs uppercase tracking-widest text-gray-400 font-bold">Solde Global Net</span>
                                <span className={`text-lg font-black tracking-tight ${soldeTotal < 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                                    {new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD' }).format(soldeTotal)}
                                </span>
                            </div>
                        </div>
                    </div>

                    {comptes && comptes.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {comptes.map(compte => (
                                <div key={compte.id} className="p-5 rounded-2xl border relative overflow-hidden group transition-all duration-300 hover:border-gray-600 hover:-translate-y-1" style={{ background: '#141414', borderColor: '#262626' }}>
                                    <div className="absolute top-0 left-0 w-1 h-full" style={{ background: compte.solde < 0 ? '#EF4444' : '#10B981' }}></div>
                                    <div className="flex justify-between items-start mb-4 pl-2">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">{compte.typeCompte}</p>
                                            <p className="font-mono text-sm text-gray-200 tracking-wider bg-black/50 px-2 py-1 rounded inline-block border border-gray-800">{compte.numeroCompte}</p>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            {(user.role === 'DIRECTEUR' || hasPermission('CAN_EDIT_BANK_ACCOUNT')) && (
                                                <button
                                                    onClick={() => handleModifierCompte(compte)}
                                                    className="text-gray-600 hover:text-amber-500 transition-colors p-2 hover:bg-amber-500/10 rounded-lg group/btn relative"
                                                    title="Modifier ce compte"
                                                >
                                                    <Edit size={16} />
                                                    <div className="absolute -top-8 right-0 bg-amber-600 text-white text-[10px] font-bold px-2 py-1 rounded opacity-0 group-hover/btn:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">Modifier</div>
                                                </button>
                                            )}
                                            {(user.role === 'DIRECTEUR' || hasPermission('CAN_DELETE_BANK_ACCOUNT')) && (
                                                <button
                                                    onClick={() => handleSupprimerCompte(compte.id, compte.numeroCompte)}
                                                    className="text-gray-600 hover:text-red-500 transition-colors p-2 hover:bg-red-500/10 rounded-lg group/btn relative"
                                                    title="Supprimer ce compte"
                                                >
                                                    <Trash2 size={16} />
                                                    <div className="absolute -top-8 right-0 bg-red-600 text-white text-[10px] font-bold px-2 py-1 rounded opacity-0 group-hover/btn:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">Supprimer</div>
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                    <div className="pl-2 flex justify-between items-end">
                                        <span className="text-xs text-gray-500">Solde disponible</span>
                                        <span className={`text-2xl font-black ${compte.solde < 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                                            {new Intl.NumberFormat('fr-MA', { style: 'decimal', minimumFractionDigits: 2 }).format(compte.solde)} <span className="text-sm">MAD</span>
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-20 px-4 rounded-2xl border border-dashed" style={{ borderColor: '#333', background: 'rgba(255,255,255,0.01)' }}>
                            <Wallet size={48} className="text-gray-700 mb-4" />
                            <p className="text-sm font-bold text-gray-400 text-center">Aucun compte actif pour ce client.</p>
                            <p className="text-xs text-gray-600 mt-1">Le portefeuille est actuellement vide.</p>
                        </div>
                    )}
                </div>
            )}

            {/* HISTORY TAB */}
            {activeTab === 'historique' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
                    <h3 className="text-xl font-black text-white flex items-center gap-3 mb-6">
                        <History className="text-[#FFC000]" size={22} />
                        Dernières Interactions
                    </h3>
                    
                    {loadingHistorique ? (
                        <div className="flex flex-col items-center justify-center py-16">
                            <div className="w-10 h-10 border-4 border-gray-800 border-t-[#E8391D] rounded-full animate-spin mb-4"></div>
                            <p className="text-sm text-gray-500 font-medium animate-pulse">Extraction de l'historique sécurisé...</p>
                        </div>
                    ) : historique.length > 0 ? (
                        <div className="rounded-2xl border overflow-hidden shadow-2xl" style={{ borderColor: '#262626', background: '#111' }}>
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b text-xs font-bold uppercase tracking-widest text-gray-400" style={{ background: '#1A1A1A', borderColor: '#262626' }}>
                                        <th className="p-4 pl-6">Horodatage</th>
                                        <th className="p-4">Nature de l'opération</th>
                                        <th className="p-4 text-right pr-6">Montant MAD</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y" style={{ divideColor: '#1A1A1A' }}>
                                    {historique.map((op, index) => {
                                        const estDebit = op.typeOperation.includes('RETRAIT') || op.typeOperation.includes('PAIEMENT') || op.typeOperation.includes('VIREMENT_EMIS');
                                        return (
                                            <tr key={index} className="transition-colors hover:bg-[rgba(255,255,255,0.02)] group">
                                                <td className="p-4 pl-6">
                                                    <div className="font-mono text-sm text-gray-300">
                                                        {new Date(op.dateHeureOperation).toLocaleString('fr-FR', {
                                                            day: '2-digit', month: '2-digit', year: 'numeric'
                                                        })}
                                                    </div>
                                                    <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-1">
                                                        <CalendarDays size={10} />
                                                        {new Date(op.dateHeureOperation).toLocaleString('fr-FR', {
                                                            hour: '2-digit', minute: '2-digit'
                                                        })}
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${estDebit ? 'bg-red-500/10 text-red-500' : 'bg-emerald-500/10 text-emerald-500'}`}>
                                                            {estDebit ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                                                        </div>
                                                        <span className="font-bold text-sm text-white capitalize tracking-wide">{op.typeOperation.replace(/_/g, ' ').toLowerCase()}</span>
                                                    </div>
                                                </td>
                                                <td className="p-4 text-right pr-6">
                                                    <span className={`font-mono text-sm font-bold bg-transparent px-2 py-1 rounded ${estDebit ? 'text-red-400' : 'text-emerald-400'}`}>
                                                        {estDebit ? '-' : '+'}{new Intl.NumberFormat('fr-MA', { style: 'decimal', minimumFractionDigits: 2 }).format(op.montant)}
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-20 px-4 rounded-2xl border border-dashed text-center" style={{ borderColor: '#333', background: 'rgba(255,255,255,0.01)' }}>
                            <History size={48} className="text-gray-700 mb-4" />
                            <p className="text-sm font-bold text-gray-400">Aucune archive transactionnelle trouvée.</p>
                        </div>
                    )}
                </div>
            )}

            {/* AI DIAGNOSTICS TAB */}
            {activeTab === 'ia' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col items-center max-w-3xl mx-auto">
                    
                    {!hasPrediction ? (
                        <div className="w-full flex justify-center py-16">
                            <div className="p-8 rounded-3xl border text-center relative overflow-hidden max-w-md w-full" style={{ background: '#141414', borderColor: '#262626' }}>
                                <BrainCircuit className="absolute -right-6 -bottom-6 text-white opacity-5" size={120} />
                                <AlertTriangle className="mx-auto text-orange-500 mb-5" size={42} />
                                <h3 className="text-lg font-black text-white mb-2">Aucune donnée prédictive</h3>
                                <p className="text-xs text-gray-400">Le modèle XGBoost nécessitera davantage de données transactionnelles pour générer un profil prédictif de ce client.</p>
                            </div>
                        </div>
                    ) : (
                        <div className="w-full space-y-6">
                            
                            {/* Score Display */}
                            <div className="p-8 rounded-[24px] border relative overflow-hidden" style={{ background: '#161616', borderColor: '#333' }}>
                                {/* Decorative elements */}
                                <div className="absolute top-0 right-0 w-64 h-64 blur-[100px] opacity-20 pointer-events-none rounded-full" style={{ background: scoreStyle.text }}></div>
                                <Activity className="absolute -left-10 -bottom-10 opacity-5 pointer-events-none" style={{ color: scoreStyle.text }} size={240} />
                                
                                <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-10">
                                    <div className="text-center md:text-left flex-1">
                                        <div className="flex items-center gap-2 mb-2 text-gray-400 uppercase tracking-widest text-xs font-bold justify-center md:justify-start">
                                            <BrainCircuit size={14} style={{ color: '#FFC000' }} />
                                            Modèle XGBoost • Confiance
                                        </div>
                                        <h3 className="text-4xl text-white font-black tracking-tight mb-2">Probabilité de Visite</h3>
                                        <p className="text-sm text-gray-500 leading-relaxed font-medium">Probabilité estimée que ce client vienne à l'agence, calculée à partir de son historique bancaire.</p>
                                    </div>
                                    
                                    <div className="relative shrink-0 flex items-center justify-center" style={{ width: '160px', height: '160px' }}>
                                        {/* Outer glowing rings */}
                                        <div className="absolute inset-0 rounded-full border border-gray-800 animate-spin-slow" style={{ animationDuration: '15s' }}></div>
                                        <div className="absolute inset-2 rounded-full border border-dashed border-gray-700 animate-spin-slow-reverse" style={{ animationDuration: '20s' }}></div>
                                        
                                        <div className="relative z-10 flex flex-col items-center justify-center w-32 h-32 rounded-full shadow-2xl" 
                                             style={{ background: '#0A0A0A', border: `2px solid ${scoreStyle.text}`, boxShadow: `0 0 30px ${scoreStyle.text}30` }}>
                                            <span className="text-4xl font-black" style={{ color: scoreStyle.text, filter: scoreStyle.dropShadow }}>{score}%</span>
                                            <span className="text-[10px] uppercase font-bold tracking-widest mt-1 text-gray-400">Visite</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Details Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="p-6 rounded-2xl border" style={{ background: '#111', borderColor: '#262626' }}>
                                    <div className="flex items-center gap-2 mb-4 text-xs font-bold uppercase tracking-widest text-[#E8391D]">
                                        <Target size={14} /> Opération Prédite
                                    </div>
                                    <div className="text-xl font-black text-white capitalize break-words mb-2 leading-tight">
                                        {client.prediction.operationPrevue?.includes('Analyse') ? (isVisite ? 'Visite' : 'Pas de visite') : client.prediction.operationPrevue}
                                    </div>
                                    <p className="text-xs text-gray-500">Motif le plus probable pour la prochaine visite en agence.</p>
                                </div>
                                
                                <div className="p-6 rounded-2xl border" style={{ background: '#111', borderColor: '#262626' }}>
                                    <div className="flex items-center gap-2 mb-4 text-xs font-bold uppercase tracking-widest text-[#FFC000]">
                                        <CalendarDays size={14} /> Fenêtre Temporelle
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <div className="font-mono text-sm text-gray-300">
                                            <span className="text-gray-500 mr-2 uppercase text-[10px]">Date Prévue:</span> 
                                            <span className="font-bold text-white text-base">{new Date(client.prediction.datePrevue).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
                                        </div>
                                        <div className="font-mono text-sm text-gray-300 mt-2">
                                            <span className="text-gray-500 mr-2 uppercase text-[10px]">Créneau ciblé:</span> 
                                            <span className="font-bold text-white bg-white/5 px-2 py-0.5 rounded border border-white/10">{client.prediction.plageHorairePrevue || 'Horaire à confirmer'}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            


                            {/* DIAGNOSTIC FACTUEL IA (Réservé au Portefeuilleur/Directeur ou autorisé) */}
                            {(client.prediction.insightGenai || client.prediction.insightIa) && canAnalyzeClient && (
                                <details className="group mt-4 p-5 rounded-2xl border relative overflow-hidden cursor-pointer select-none" style={{ background: 'linear-gradient(135deg, #13110a, #0f0d07)', borderColor: '#FFC00030' }}>
                                    <summary className="flex items-center gap-2 outline-none">
                                        <div className="absolute top-0 left-0 w-1 h-full" style={{ background: '#FFC000' }}></div>
                                        <div className="absolute top-0 right-0 w-40 h-40 blur-[80px] opacity-10 pointer-events-none rounded-full" style={{ background: '#FFC000' }}></div>
                                        <BrainCircuit size={12} style={{ color: '#FFC000' }} />
                                        <span className="text-xs font-black uppercase tracking-widest" style={{ color: '#FFC000' }}>Diagnostic de l'Agent IA</span>
                                        <span className="ml-auto text-[10px] text-gray-500 transition-transform group-open:rotate-180">▼</span>
                                    </summary>
                                    <div className="mt-4 pt-4 border-t border-white/10 relative z-10">
                                        <p className="text-sm text-gray-300 italic leading-relaxed">
                                            "{getDiagnosticText(client.prediction.insightGenai || client.prediction.insightIa)}"
                                        </p>
                                        <p className="text-xs text-gray-600 mt-2 uppercase tracking-wide">Analyse comportementale — Décision de l'Agent IA</p>
                                    </div>
                                </details>
                            )}

                        </div>
                    )}
                </div>
            )}

            {/* DELEGATION TAB */}
            {activeTab === 'delegation' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pb-8 space-y-6">

                    {/* STRATÉGIE PRESCRITE (Réservé au Portefeuilleur/Directeur ou autorisé) */}
                    {(client.prediction?.strategiePrescrite || client.prediction?.strategie_prescrite) && canAnalyzeClient && (
                        <div className="p-6 rounded-3xl border relative overflow-hidden shadow-lg" style={{ background: 'linear-gradient(135deg, #1a0800, #120a00)', borderColor: '#E8391D40' }}>
                            <div className="absolute top-0 left-0 w-1 h-full" style={{ background: '#E8391D' }}></div>
                            <div className="absolute top-0 right-0 w-40 h-40 blur-[80px] opacity-10 pointer-events-none rounded-full" style={{ background: '#E8391D' }}></div>
                            <h4 className="text-xs font-black uppercase tracking-widest mb-3 flex items-center gap-2" style={{ color: '#E8391D' }}>
                                <Target size={14} /> Stratégie & Services Recommandés par l'Agent IA
                            </h4>
                            <p className="text-lg font-black text-white leading-snug relative z-10 italic">
                                "{client.prediction.strategiePrescrite || client.prediction.strategie_prescrite}"
                            </p>
                            <p className="text-[10px] text-gray-500 mt-3 uppercase tracking-widest">Décision de l'Agent IA — Vue Portefeuilleur</p>
                        </div>
                    )}

                    <div className="p-6 rounded-3xl border relative overflow-hidden" style={{ background: '#111', borderColor: '#262626' }}>
                        <div className="absolute top-0 right-0 w-40 h-40 blur-[80px] opacity-10 pointer-events-none rounded-full" style={{ background: '#E8391D' }}></div>
                        
                        <div className="flex items-center gap-3 mb-6 relative z-10">
                            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#E8391D]/10 text-[#E8391D]">
                                {delegationForm.mode === 'DELEGATION' ? <ShieldAlert size={20} /> : <Target size={20} />}
                            </div>
                            <div>
                                <h3 className="text-xl font-black text-white">
                                    {delegationForm.mode === 'DELEGATION' ? 'Instruire le Conseiller' : 'Enregistrer mon Action'}
                                </h3>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    {delegationForm.mode === 'DELEGATION' ? 'Déléguez une tâche spécifique' : 'Enregistrez le résultat de votre proposition directe'}
                                </p>
                            </div>
                        </div>

                        {/* MODE SELECTOR */}
                        <div className="flex p-1 bg-[#1A1A1A] border border-[#333] rounded-2xl mb-6 relative z-10">
                            <button 
                                type="button"
                                onClick={() => setDelegationForm({...delegationForm, mode: 'DELEGATION'})}
                                className={`flex-1 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${delegationForm.mode === 'DELEGATION' ? 'bg-[#E8391D] text-white' : 'text-gray-500 hover:text-gray-300'}`}
                            >
                                Délégation au Conseiller
                            </button>
                            <button 
                                type="button"
                                onClick={() => setDelegationForm({...delegationForm, mode: 'DIRECT_ACTION'})}
                                className={`flex-1 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${delegationForm.mode === 'DIRECT_ACTION' ? 'bg-[#FFC000] text-black' : 'text-gray-500 hover:text-gray-300'}`}
                            >
                                Enregistrer Action Directe
                            </button>
                        </div>

                        <form onSubmit={handleDelegationSubmit} className="space-y-5 relative z-10">
                            {delegationForm.mode === 'DIRECT_ACTION' && (
                                <div className="animate-in slide-in-from-top-2 duration-300">
                                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Résultat de la proposition</label>
                                    <div className="flex gap-3">
                                        {[
                                            {id: 'VENDU', label: 'VENDU', color: '#10B981'},
                                            {id: 'REFUSE', label: 'REFUSÉ', color: '#EF4444'},
                                            {id: 'A_RAPPELER', label: 'RAPPEL', color: '#F59E0B'}
                                        ].map(st => (
                                            <button 
                                                key={st.id} type="button"
                                                onClick={() => setDelegationForm({...delegationForm, statut: st.id})}
                                                className={`flex-1 py-2 rounded-xl text-[10px] font-black border transition-all ${delegationForm.statut === st.id ? 'text-white border-white' : 'text-gray-500 border-[#333] hover:border-gray-600'}`}
                                                style={{ backgroundColor: delegationForm.statut === st.id ? st.color : 'transparent' }}
                                            >
                                                {st.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Service de Rétention à proposer</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="Ex : Prêt immobilier, Pack Premium, Renforcement KYC..."
                                    className="w-full bg-[#1A1A1A] border border-[#333] text-white rounded-xl px-4 py-3 outline-none focus:border-[#E8391D] transition-colors text-sm placeholder-gray-600"
                                    value={delegationForm.servicePropose}
                                    onChange={e => setDelegationForm({...delegationForm, servicePropose: e.target.value})}
                                />
                                {/* Suggestions rapides cliquables */}
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {[
                                        'Entretien de Rétention',
                                        'Restructuration de Dette',
                                        'Geste Commercial',
                                        'Produit Premium Fidélité',
                                        'Ligne de Crédit',
                                        'Mise à jour KYC',
                                        'Assurance Vie',
                                        'Plan Épargne',
                                        'Carte Platinum',
                                        'Crédit Immobilier',
                                    ].map(suggestion => (
                                        <button
                                            key={suggestion}
                                            type="button"
                                            onClick={() => setDelegationForm({...delegationForm, servicePropose: suggestion})}
                                            className="text-[10px] font-bold px-2.5 py-1 rounded-full border transition-all hover:border-[#E8391D] hover:text-[#E8391D]"
                                            style={{
                                                background: delegationForm.servicePropose === suggestion ? 'rgba(232,57,29,0.15)' : 'rgba(255,255,255,0.03)',
                                                borderColor: delegationForm.servicePropose === suggestion ? '#E8391D' : '#333',
                                                color: delegationForm.servicePropose === suggestion ? '#E8391D' : '#6B7280',
                                            }}
                                        >
                                            {suggestion}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Niveau de Priorité</label>
                                <div className="flex gap-3">
                                    {['BASSE', 'MOYENNE', 'HAUTE', 'URGENTE'].map(prio => (
                                        <button 
                                            key={prio} type="button"
                                            onClick={() => setDelegationForm({...delegationForm, priorite: prio})}
                                            className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all ${delegationForm.priorite === prio ? 'bg-[#E8391D] text-white border-[#E8391D]' : 'bg-[#1A1A1A] text-gray-500 border-[#333] hover:border-gray-600'}`}
                                        >
                                            {prio}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Instructions pour le conseiller</label>
                                <textarea 
                                    required
                                    rows="4"
                                    placeholder={delegationForm.mode === 'DELEGATION' ? "Rédigez ici vos observations et directives pour le conseiller..." : "Détaillez ici le retour client et les conditions de la proposition..."}
                                    className="w-full bg-[#1A1A1A] border border-[#333] text-white rounded-xl px-4 py-3 outline-none focus:border-[#E8391D] transition-colors text-sm resize-none"
                                    value={delegationForm.commentaire}
                                    onChange={e => setDelegationForm({...delegationForm, commentaire: e.target.value})}
                                />
                            </div>

                            <div className="pt-2">
                                <button 
                                    type="submit" 
                                    disabled={isSubmitting}
                                    className="w-full py-3.5 rounded-xl text-sm font-black text-white flex items-center justify-center gap-2 transition-all hover:opacity-90 active:scale-[0.98]"
                                    style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)' }}
                                >
                                    {isSubmitting ? (
                                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                    ) : (
                                        <>
                                            <Send size={16} /> 
                                            {delegationForm.mode === 'DELEGATION' ? 'Envoyer la délégation au Conseiller' : 'Enregistrer mon action pour l\'Admin'}
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
      </div>
    </div>
  );
}
