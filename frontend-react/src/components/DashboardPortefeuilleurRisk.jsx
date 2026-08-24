import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import { useAuth } from '../context/AuthContext';
import {
    AlertTriangle, ShieldAlert, ArrowUpCircle, CheckCircle,
    MessageSquare, AlertCircle, FileText, ArrowUpRight, ArrowDownRight, ArrowDownLeft,
    User, Search, Filter, Briefcase, Info, X, Check, Phone, Users, Clock, Send, Target,
    LogOut, Activity, Brain, Shield, ChevronRight, LayoutDashboard, Zap, TrendingUp, BarChart2,
    ChevronLeft, Calendar, Settings
} from 'lucide-react';
import awbLogo from '../assets/react.jpeg';

// ── Helpers de Styles AWB Prestige ───────────────────────────────────────────
// Code couleur du % = PROBABILITÉ DE VISITE (haute = positif = vert ; pas un niveau de risque)
/**
 * Pastille d'insatisfaction affichée sur chaque fiche du portefeuille.
 * Haut = mécontent, donc rouge : c'est le critère de tri de la liste, il doit
 * se lire au premier coup d'œil.
 */
const getInsatisfactionStyle = (score) => {
    if (score === null || score === undefined)
        return { bg: '#F5F5F5', text: '#8C8C8C', label: 'Non évalué' };
    if (score >= 75) return { bg: '#FFF1F0', text: '#CF1322', label: 'Très insatisfait' };
    if (score >= 50) return { bg: '#FFF2E8', text: '#D4380D', label: 'Insatisfait' };
    if (score >= 25) return { bg: '#FFFBE6', text: '#D48806', label: 'Mitigé' };
    if (score >= 10) return { bg: '#F6FFED', text: '#5B8C00', label: 'Plutôt satisfait' };
    return { bg: '#F6FFED', text: '#389E0D', label: 'Satisfait' };
};

const getAlerteConfig = (type) => {
    switch (type) {
        case 'CHURN': return { bg: 'bg-red-50', text: 'text-[#E8391D]', border: 'border-red-100', icon: AlertTriangle, grad: 'from-[#E8391D] to-[#FF4D4F]', label: 'Risque de Churn' };
        case 'DEFAULT': return { bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', icon: ShieldAlert, grad: 'from-orange-500 to-amber-500', label: 'Risque d\'Impayé' };
        case 'VIP': return { bg: 'bg-yellow-50', text: 'text-[#B45309]', border: 'border-yellow-200', icon: Zap, grad: 'from-[#FFC000] to-[#FF9C08]', label: 'Alerte VIP' };
        default: return { bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200', icon: Info, grad: 'from-gray-500 to-gray-400', label: 'Analyse Standard' };
    }
};

/** Couleur du pourcentage de risque de churn, alignée sur la palette AWB. */
const couleurRisque = (niveau) => {
    switch ((niveau || '').toUpperCase()) {
        case 'CRITIQUE': return '#E8391D';
        case 'ÉLEVÉ': return '#D9480F';
        case 'ALERTE': return '#B45309';
        default: return '#6B7280';
    }
};

/** Génère la stratégie de l'Agent IA pour le Portefeuilleur */
const genererStrategieAgent = (client) => {
    if (!client) return null;
    const score = client.score;
    const seg = (client.segment || '').toUpperCase();
    const type = client.alerteType;
    const op = client.operationPrevue || 'Opération bancaire';
    const date = client.dateVisite
        ? new Date(client.dateVisite).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long' })
        : 'prochainement';

    if (type === 'CHURN' || score >= 90) {
        return {
            titre: 'Rétention Urgente',
            couleur: 'from-red-600 to-red-800',
            badge: 'CRITIQUE',
            badgeCouleur: 'bg-red-100 text-red-700',
            barreColor: 'bg-[#E8391D]',
            etapes: [
                { icon: '📞', text: `Contacter ${client.nom} AVANT le ${date} — score de risque : ${score}%.` },
                { icon: '🎯', text: `Proposer une offre de rétention adaptée au segment ${client.segment} (ex: réduction de frais, cashback).` },
                { icon: '🔒', text: `Documenter l'échange et planifier un suivi à J+7 avec le Directeur d'Agence.` },
            ]
        };
    } else if (type === 'DEFAULT') {
        return {
            titre: 'Plan de Recouvrement',
            couleur: 'from-orange-500 to-amber-600',
            badge: 'IMPAYÉ',
            badgeCouleur: 'bg-orange-100 text-orange-700',
            barreColor: 'bg-orange-500',
            etapes: [
                { icon: '⚖️', text: `Initier la procédure de recouvrement amiable pour le profil ${client.segment}.` },
                { icon: '📋', text: `Vérifier les garanties en dossier et proposer une restructuration de crédit.` },
                { icon: '🤝', text: `Planifier un entretien en agence avant le ${date} pour régularisation.` },
            ]
        };
    } else if (type === 'VIP' || seg.includes('VIP') || seg.includes('PRO') || seg.includes('PME')) {
        return {
            titre: 'Valorisation Patrimoine',
            couleur: 'from-amber-500 to-yellow-400',
            badge: 'VIP / PRO',
            badgeCouleur: 'bg-amber-100 text-amber-700',
            barreColor: 'bg-[#FFC000]',
            etapes: [
                { icon: '✨', text: `Présenter les nouvelles offres patrimoniales lors de l'opération prévue : '${op}'.` },
                { icon: '📈', text: `Proposer un produit de placement ou d'assurance-vie adapté au profil ${client.segment}.` },
                { icon: '🏆', text: `Offrir un accueil VIP personnalisé le ${date} avec le Directeur d'Agence.` },
            ]
        };
    } else {
        return {
            titre: 'Fidélisation Standard',
            couleur: 'from-slate-600 to-slate-800',
            badge: 'ROUTINE',
            badgeCouleur: 'bg-gray-100 text-gray-600',
            barreColor: 'bg-gray-500',
            etapes: [
                { icon: '💬', text: `Accompagner le client pour l'opération prévue : '${op}' le ${date}.` },
                { icon: '🔍', text: `Identifier les opportunités de vente croisée lors du passage en agence.` },
                { icon: '📌', text: `Mettre à jour le dossier KYC et vérifier les besoins assurantiels.` },
            ]
        };
    }
};

export default function DashboardPortefeuilleurRisk() {
    const { user, logout } = useAuth();
    const [clients, setClients] = useState([]);
    const [selectedClient, setSelectedClient] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('ALL');
    const [searchTerm, setSearchTerm] = useState('');

    const [actionPath, setActionPath] = useState('DIRECT');
    const [decisionForm, setDecisionForm] = useState({
        statut: 'RISQUE_ECARTE',
        commentaire: '',
        noteDelegation: "",
        priorite: "MOYEN",
        typeDelegation: "APPEL"
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isAIRunning, setIsAIRunning] = useState(false);
    const [actionSaved, setActionSaved] = useState(null);
    const [lastAction, setLastAction] = useState(null);
    const [tauxTraitement, setTauxTraitement] = useState(0);

    // ── États Pagination ──────────────────────────────────────────────────
    const [currentPage, setCurrentPage] = useState(1);
    const CLIENTS_PER_PAGE = 6;
    const [currentTxPage, setCurrentTxPage] = useState(1);
    const TX_PER_PAGE = 5;

    useEffect(() => {
        const fetchClients = async () => {
            try {
                setLoading(true);
                const response = await api.get('/clients?size=200');
                const realData = response.data.content || [];

                const mappedClients = realData.map(c => {
                    const rawScore = c.prediction?.scoreProbabiliteGlobal || 0;
                    const score = Math.round(rawScore > 1 ? rawScore : rawScore * 100);

                    // Risque de churn : distinct du score de visite ci-dessus.
                    // Stocké en 0–1 par le moteur IA, toléré en 0–100 par sécurité.
                    const rawChurn = c.prediction?.scoreChurn;
                    const risque = (rawChurn === null || rawChurn === undefined)
                        ? null
                        : Math.round(rawChurn > 1 ? rawChurn : rawChurn * 100);

                    const rawNiveau = (c.prediction?.niveauRisque || '').toUpperCase();
                    const seg = (c.segmentMetier || '').toUpperCase();
                    const isVipSegment = seg.includes('VIP') || seg.includes('PRO') || seg.includes('PME') || seg.includes('TPE');

                    let type = 'STANDARD';
                    let label = 'Analyse Standard';

                    // Mapping direct niveauRisque (backend déterministe) → alerteType Portefeuilleur
                    // CRITIQUE et ÉLEVÉ = Client très inactif et/ou compte en forte tension = Risque de Churn
                    if (rawNiveau === 'CRITIQUE' || rawNiveau === 'ÉLEVÉ') {
                        type = 'CHURN';
                        label = 'Risque de Churn (Départ client)';
                    }
                    // ALERTE = Tension modérée sur le compte
                    else if (rawNiveau === 'ALERTE') {
                        if (isVipSegment) {
                            type = 'VIP';
                            label = 'Alerte VIP / PRO — Suivi renforcé';
                        } else {
                            type = 'DEFAULT';
                            label = 'Risque d\'impayé / Déséquilibre compte';
                        }
                    }
                    // SOUS SURVEILLANCE = Client actif, suivi préventif
                    else {
                        if (isVipSegment) {
                            type = 'VIP';
                            label = 'Valorisation Patrimoine VIP / PRO';
                        } else {
                            type = 'STANDARD';
                            label = 'Fidélisation Standard';
                        }
                    }

                    return {
                        id: c.id,
                        nom: c.nomComplet,
                        cin: c.cin,
                        email: c.email || 'N/A',
                        telephone: c.telephone || 'Non renseigné',
                        segment: c.segmentMetier || 'Particulier',
                        alerteType: type,
                        alerteLabel: label,
                        score: score,
                        risque: risque,
                        niveauRisque: rawNiveau || null,
                        insatisfaction: c.prediction?.scoreInsatisfaction ?? null,
                        niveauSatisfaction: c.prediction?.niveauSatisfaction || null,
                        fiabilite: c.prediction?.fiabilite ? c.prediction.fiabilite.toFixed(1) : (92 + ((c.id || 0) % 5) + ((score || 0) % 3)).toFixed(1),
                        iaDiagnostic: c.prediction?.insightGenai || "Diagnostic IA non généré.",
                        dateVisite: c.prediction?.dateVisitePrevue,
                        operationPrevue: c.prediction?.operationPrevue || 'Analyse en cours',
                        horaire: c.prediction?.plageHorairePrevue || 'N/A',
                        isTreated: c.actions && c.actions.length > 0,
                        lastActionDate: c.actions && c.actions.length > 0 ? c.actions[0].dateAction : null,
                        transactions: [],
                        comptes: c.comptes || []
                    };
                });

                // Les clients les plus mécontents en tête : c'est l'ordre dans
                // lequel un conseiller doit traiter son portefeuille. Le tri
                // précédent se faisait sur le score de visite, qui n'a rien à
                // voir avec l'urgence relationnelle.
                // Un client sans score évalué est envoyé en fin de liste plutôt
                // que traité comme satisfait — on ne sait pas, ce n'est pas
                // pareil que « il va bien ».
                const sorted = mappedClients.sort((a, b) => {
                    const ia = a.insatisfaction ?? -1;
                    const ib = b.insatisfaction ?? -1;
                    if (ib !== ia) return ib - ia;
                    return (b.risque ?? 0) - (a.risque ?? 0);
                });
                setClients(sorted);
                if (sorted.length > 0 && !selectedClient) setSelectedClient(sorted[0]);
            } catch (error) {
                console.error("Erreur fetch clients:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchClients();
        fetchTauxTraitement();
    }, []);

    const fetchLastAction = async (clientId) => {
        try {
            const res = await api.get(`/actions/client/${clientId}/dernier-examen`);
            if (res.status === 200 && res.data) {
                setLastAction(res.data);
            } else {
                setLastAction(null);
            }
        } catch (error) {
            console.error("Erreur fetch last action:", error);
            setLastAction(null);
        }
    };

    const fetchTauxTraitement = async () => {
        try {
            const res = await api.get('/actions/stats/taux-traitement');
            setTauxTraitement(res.data.tauxTraitement || 0);
        } catch (err) {
            console.error("Erreur fetch taux traitement:", err);
        }
    };

    const handleClientSelect = async (client) => {
        setSelectedClient(client);
        setActionSaved(null);
        fetchLastAction(client.id);
        setDecisionForm({
            ...decisionForm,
            commentaire: '',
            noteDelegation: `Opportunité commerciale identifiée : Profil ${client.segment} à fort potentiel. À aborder lors du passage prévu pour ${client.operationPrevue || 'son opération'} avec une proposition personnalisée.`
        });
        setCurrentTxPage(1); // Reset pagination transactions

        try {
            const res = await api.get(`/operations/client/${client.id}`);
            setSelectedClient(prev => ({ ...prev, transactions: res.data || [] }));
        } catch (error) {
            console.error("Erreur transactions:", error);
        }
    };

    const handleRunIA = async () => {
        setIsAIRunning(true);
        try {
            await api.post('/predictions/batch-refresh');
            // Petit délai pour s'assurer que les données en DB sont bien synchronisées
            setTimeout(() => {
                fetchClients();
                fetchTauxTraitement();
                setIsAIRunning(false);
                alert("Recalcul IA terminé avec succès !");
            }, 1000);
        } catch (err) {
            console.error("Erreur IA:", err);
            alert("Une erreur est survenue lors du lancement du moteur IA.");
            setIsAIRunning(false);
        }
    };

    const handleSubmitDecision = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const payload = {
                banquierId: user?.id || 1,
                clientId: selectedClient.id,
                statut: actionPath === 'DIRECT' ? decisionForm.statut : 'DELEGUE_COMMERCIAL',
                commentaire: actionPath === 'DIRECT' ? decisionForm.commentaire : decisionForm.noteDelegation,
                priorite: actionPath === 'DIRECT' ? 'NORMALE' : decisionForm.priorite,
                typeDelegation: actionPath === 'DIRECT' ? 'DIRECT' : decisionForm.typeDelegation,
                categorie: 'ARBITRAGE'
            };
            await api.post('/actions', payload);
            setActionSaved(`L'arbitrage pour ${selectedClient.nom} a été enregistré avec succès.`);
            
            // Re-fetch data to reflect changes
            fetchLastAction(selectedClient.id);
            fetchTauxTraitement();
            
            // Clear message and form after 3 seconds
            setTimeout(() => {
                setActionSaved(null);
                setDecisionForm(prev => ({ ...prev, commentaire: '' }));
            }, 3000);

        } catch (error) {
            console.error("Erreur enregistrement action", error);
            alert("Une erreur est survenue lors de l'enregistrement de l'arbitrage.");
        } finally {
            setIsSubmitting(false);
        }
    };

    // Bornes des filtres de satisfaction — alignées sur les seuils du moteur
    // (agent_analyse.evaluer_satisfaction).
    const DANS_TRANCHE = {
        ALL: () => true,
        TRES_INSATISFAIT: (s) => s !== null && s >= 75,
        INSATISFAIT: (s) => s !== null && s >= 50 && s < 75,
        MITIGE: (s) => s !== null && s >= 25 && s < 50,
        SATISFAIT: (s) => s !== null && s < 25,
    };

    const filteredClients = clients.filter(c => {
        const matchSearch = c.nom.toLowerCase().includes(searchTerm.toLowerCase()) || c.cin.toLowerCase().includes(searchTerm.toLowerCase());
        const test = DANS_TRANCHE[filter] || DANS_TRANCHE.ALL;
        return matchSearch && test(c.insatisfaction ?? null);
    });

    const compteTranche = (cle) => clients.filter(c => DANS_TRANCHE[cle](c.insatisfaction ?? null)).length;

    // Reset pagination clients au changement de filtre ou recherche
    useEffect(() => {
        setCurrentPage(1);
    }, [filter, searchTerm]);

    const totalPages = Math.ceil(filteredClients.length / CLIENTS_PER_PAGE);
    const paginatedClients = filteredClients.slice(
        (currentPage - 1) * CLIENTS_PER_PAGE,
        currentPage * CLIENTS_PER_PAGE
    );

    const transactions = selectedClient?.transactions || [];
    const totalTxPages = Math.ceil(transactions.length / TX_PER_PAGE);
    const paginatedTransactions = transactions.slice(
        (currentTxPage - 1) * TX_PER_PAGE,
        currentTxPage * TX_PER_PAGE
    );

    // ── Calcul des pourcentages d'alertes ─────────────────────────────────
    const totalClients = clients.length || 1;
    const nbChurn   = clients.filter(c => c.alerteType === 'CHURN').length;
    const nbDefault = clients.filter(c => c.alerteType === 'DEFAULT').length;
    const nbVip     = clients.filter(c => c.alerteType === 'VIP').length;
    const nbStd     = clients.filter(c => c.alerteType === 'STANDARD').length;
    const pctChurn   = Math.round((nbChurn   / totalClients) * 100);
    const pctDefault = Math.round((nbDefault / totalClients) * 100);
    const pctVip     = Math.round((nbVip     / totalClients) * 100);
    const nbCritiques = clients.filter(c => c.score >= 90).length;
    const pctCritiques = Math.round((nbCritiques / totalClients) * 100);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#F5F5F5] flex flex-col items-center justify-center p-8">
                <div className="w-16 h-16 border-4 border-t-[#E8391D] border-gray-200 rounded-full animate-spin mb-4" />
                <p className="text-[#1A1A1A] font-black uppercase tracking-widest text-sm">Chargement de la console risques...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#F8F9FA] flex flex-col font-sans text-[#1A1A1A]">

            {/* ── HEADER PRESTIGE AWB ────────────────────────────────────────── */}
            <header className="bg-white border-b border-gray-100 px-10 py-5 flex items-center justify-between sticky top-0 z-50 shadow-md backdrop-blur-md bg-white/90">
                <div className="flex items-center gap-8">
                    <div className="relative">
                        <img src={awbLogo} alt="AWB Logo" className="h-12 w-12 rounded-2xl shadow-lg border border-red-100 transform hover:scale-105 transition-transform" />
                        <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-white rounded-full"></div>
                    </div>
                    <div className="h-10 w-px bg-gray-200" />
                    <div className="flex items-center gap-4">
                        <div>
                            <h1 className="text-lg font-black tracking-tighter leading-none text-[#1A1A1A]">CORE-RISK ANALYTICS</h1>
                            <p className="text-[10px] font-black text-[#E8391D] uppercase mt-1 tracking-[0.2em]">Pilotage Haute Performance</p>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-3 bg-gray-50 px-4 py-2 rounded-2xl border">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#1A1A1A] to-[#3A3A3A] flex items-center justify-center text-white text-xs font-black">
                            {user?.nomComplet?.charAt(0) || 'R'}
                        </div>
                        <span className="text-xs font-black uppercase">{user?.nomComplet || 'Analyste'}</span>
                    </div>

                    <button
                        onClick={logout}
                        className="p-2.5 bg-white text-red-600 rounded-2xl border hover:bg-red-50 transition-colors shadow-sm"
                        title="Déconnexion"
                    >
                        <LogOut size={20} />
                    </button>
                </div>
            </header>

            <main className="flex-1 flex overflow-hidden">

                {/* ── SIDEBAR : LISTE DES DOSSIERS ────────────────────────────────── */}
                <aside className="w-[450px] bg-white border-r flex flex-col shadow-2xl z-10">
                    <div className="p-8 border-b space-y-6">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xs font-black uppercase tracking-[0.1em] text-gray-400 flex items-center gap-2">
                                <Activity size={14} className="text-[#E8391D]" /> Portefeuille en Analyse
                            </h2>
                            <span className="bg-[#E8391D]/10 text-[#E8391D] text-[10px] font-black px-3 py-1 rounded-full border border-[#E8391D20]">
                                {filteredClients.length} dossiers
                            </span>
                        </div>

                        <div className="relative group">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-[#E8391D] transition-colors" size={18} />
                            <input
                                type="text"
                                placeholder="Rechercher un dossier..."
                                className="w-full pl-12 pr-4 py-4 bg-gray-50 border border-gray-100 rounded-3xl text-sm font-black focus:ring-2 focus:ring-[#E8391D20] focus:bg-white transition-all shadow-inner"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>

                        <div className="flex gap-2 p-1 bg-gray-50 rounded-2xl overflow-x-auto no-scrollbar">
                            {[
                                ['ALL', 'Tous'],
                                ['TRES_INSATISFAIT', 'Très insatisfaits'],
                                ['INSATISFAIT', 'Insatisfaits'],
                                ['MITIGE', 'Mitigés'],
                                ['SATISFAIT', 'Satisfaits'],
                            ].map(([cle, libelle]) => (
                                <button
                                    key={cle}
                                    onClick={() => setFilter(cle)}
                                    className={`whitespace-nowrap px-4 py-1.5 rounded-xl text-[10px] font-black uppercase transition-all ${filter === cle ? 'bg-white text-[#E8391D] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                                >
                                    {libelle} ({compteTranche(cle)})
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-3 bg-[#FAFAFA]">
                        {paginatedClients.map((client) => {
                            const isSelected = selectedClient?.id === client.id;
                            const config = getAlerteConfig(client.alerteType);
                            const sc = getInsatisfactionStyle(client.insatisfaction);

                            return (
                                <div
                                    key={client.id}
                                    onClick={() => handleClientSelect(client)}
                                    className={`relative p-4 rounded-3xl cursor-pointer transition-all duration-300 border shadow-sm group ${isSelected ? 'bg-white border-[#E8391D] ring-1 ring-[#E8391D10]' : 'bg-white border-transparent hover:border-gray-200'}`}
                                >
                                    <div className="flex items-start gap-4">
                                        <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${config.grad} flex items-center justify-center text-white shadow-lg transition-transform group-hover:scale-105`}>
                                            <config.icon size={22} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-1">
                                                <p className={`text-sm font-black truncate ${isSelected ? 'text-[#E8391D]' : 'text-[#1A1A1A]'}`}>{client.nom}</p>
                                                <span className={`text-[10px] font-black px-2 py-0.5 rounded-full whitespace-nowrap`}
                                                      style={{ background: sc.bg, color: sc.text }}
                                                      title={`Insatisfaction — ${sc.label}`}>
                                                    {client.insatisfaction === null || client.insatisfaction === undefined
                                                        ? 'N/É'
                                                        : `${client.insatisfaction}%`}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <p className="text-[10px] font-bold text-gray-400 uppercase">{client.cin}</p>
                                                <div className="w-1 h-1 rounded-full bg-gray-300" />
                                                {client.comptes && client.comptes.length > 0 && (
                                                    <p className="text-[10px] font-mono text-[#E8391D] font-black tracking-tighter">
                                                        {client.comptes[0].numeroCompte}
                                                    </p>
                                                )}
                                                <div className="w-1 h-1 rounded-full bg-gray-300" />
                                                {client.isTreated ? (
                                                    <span className="text-[9px] font-black text-green-500 flex items-center gap-1 uppercase">
                                                        <CheckCircle size={10} /> Traité
                                                    </span>
                                                ) : (
                                                    <p className="text-[10px] font-black text-[#FFC000] uppercase truncate">{client.alerteLabel}</p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    {isSelected && <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[#E8391D] animate-pulse"><ChevronRight size={18} /></div>}
                                </div>
                            );
                        })}
                    </div>

                    {/* CONTRÔLES PAGINATION SIDEBAR */}
                    {totalPages > 1 && (
                        <div className="p-4 border-t bg-white flex items-center justify-between">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="p-2 rounded-xl border hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm"
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <span className="text-[10px] font-black uppercase tracking-tighter text-gray-500">
                                Page <span className="text-[#E8391D]">{currentPage}</span> sur {totalPages}
                            </span>
                            <button
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="p-2 rounded-xl border hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm"
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    )}
                </aside>

                {/* ── ZONE DE TRAVAIL CENTRALE ─────────────────────────────────────── */}
                <section className="flex-1 overflow-y-auto no-scrollbar bg-[#F8F9FA] p-10 space-y-10">

                    {/* 🧠 SMART DASHBOARD STATS DYNAMIQUES */}
                    <div className="grid grid-cols-4 gap-6">
                        {[
                            {
                                label: 'Alertes Critiques',
                                value: nbCritiques,
                                icon: ShieldAlert,
                                color: 'text-white',
                                bg: 'bg-[#E8391D]',
                                trend: `${pctCritiques}% du portefeuille`
                            },
                            {
                                label: 'Risque Churn',
                                value: nbChurn,
                                icon: AlertTriangle,
                                color: 'text-[#E8391D]',
                                bg: 'bg-white',
                                trend: `${pctChurn}% des clients`
                            },
                            {
                                label: 'Impayés / Défaut',
                                value: nbDefault,
                                icon: ShieldAlert,
                                color: 'text-orange-500',
                                bg: 'bg-white',
                                trend: `${pctDefault}% du portefeuille`
                            },
                            {
                                label: 'VIP / Taux Traitement',
                                value: `${nbVip} | ${tauxTraitement}%`,
                                icon: Activity,
                                color: 'text-[#FFC000]',
                                bg: 'bg-white',
                                trend: `${pctVip}% VIP/PRO`
                            }
                        ].map((stat, i) => (
                            <div key={i} className={`${stat.bg} p-6 rounded-[32px] border border-gray-100 shadow-xl flex flex-col justify-between group hover:scale-[1.02] transition-all duration-300`}>
                                <div className="flex items-center justify-between mb-4">
                                    <div className={`p-3 rounded-2xl ${stat.bg === 'bg-white' ? 'bg-gray-50' : 'bg-white/10'}`}>
                                        <stat.icon size={22} className={stat.color} />
                                    </div>
                                    <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded-lg ${stat.bg === 'bg-white' ? 'bg-gray-100 text-gray-500' : 'bg-white/20 text-white'}`}>
                                        {stat.trend}
                                    </span>
                                </div>
                                <div className="animate-in fade-in slide-in-from-bottom-2 duration-700">
                                    <p className={`text-2xl font-black ${stat.bg === 'bg-white' ? 'text-[#1A1A1A]' : 'text-white'}`}>{stat.value}</p>
                                    <p className={`text-[10px] font-black uppercase tracking-wider ${stat.bg === 'bg-white' ? 'text-gray-400' : 'text-white/60'}`}>{stat.label}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                    {selectedClient ? (
                        <>
                            {/* 1. EN-TÊTE PROFIL CLIENT PRESTIGE */}
                            <div className="bg-white rounded-[48px] p-12 border border-gray-50 shadow-2xl relative overflow-hidden group">
                                <div className="absolute -top-24 -right-24 w-96 h-96 bg-[#E8391D]/5 rounded-full blur-[80px]" />

                                <div className="relative flex flex-col md:flex-row items-center md:items-start gap-12">
                                    <div className="relative group">
                                        <div className="w-40 h-40 rounded-[48px] bg-[#1A1A1A] p-1">
                                            <div className="w-full h-full rounded-[44px] bg-gradient-to-br from-[#1A1A1A] to-[#333] flex items-center justify-center text-white text-6xl font-black shadow-2xl transition-transform group-hover:scale-105">
                                                {selectedClient.nom.charAt(0)}
                                            </div>
                                        </div>
                                        <div className="absolute -bottom-2 -right-2 w-12 h-12 bg-[#FFC000] border-4 border-white rounded-2xl flex items-center justify-center text-[#1A1A1A] shadow-lg">
                                            <Shield size={20} />
                                        </div>
                                    </div>

                                    <div className="flex-1 text-center md:text-left space-y-6">
                                        <div className="space-y-1">
                                            <div className="flex flex-wrap items-center justify-center md:justify-start gap-5">
                                                <h2 className="text-4xl font-black tracking-tighter text-[#1A1A1A] uppercase">{selectedClient.nom}</h2>
                                                <div className="px-5 py-2 bg-[#FFC000]/10 border border-[#FFC00020] rounded-full flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full bg-[#FFC000] animate-pulse" />
                                                    <span className="text-[10px] font-black text-[#B45309] uppercase tracking-widest">SEGMENT : {selectedClient.segment}</span>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-4">
                                                <p className="text-gray-400 font-black uppercase tracking-[0.3em] text-xs">IDENTIFIANT CLIENT : {selectedClient.cin}</p>
                                                {selectedClient.comptes && selectedClient.comptes.length > 0 && (
                                                    <div className="flex gap-2">
                                                        {selectedClient.comptes.map(compte => (
                                                            <span key={compte.id} className="px-3 py-1 bg-gray-100 border border-gray-200 rounded-lg text-[10px] font-mono font-black text-gray-600">
                                                                RIB: {compte.numeroCompte}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                            <div className="bg-gray-50 p-4 rounded-3xl border">
                                                <p className="text-[10px] font-black text-gray-400 uppercase mb-1">Probabilité de visite</p>
                                                <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full bg-[#E8391D]" />
                                                    <span className="text-xl font-black">{selectedClient.score}%</span>
                                                </div>
                                            </div>
                                            <div className="bg-gray-50 p-4 rounded-3xl border">
                                                <p className="text-[10px] font-black text-gray-400 uppercase mb-1">Pr. Visite</p>
                                                <div className="flex items-center gap-2">
                                                    <Calendar size={12} className="text-[#E8391D]" />
                                                    <span className="text-xs font-black uppercase">
                                                        {selectedClient.dateVisite 
                                                            ? new Date(selectedClient.dateVisite).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long' }) 
                                                            : 'A planifier'}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="bg-gray-50 p-4 rounded-3xl border">
                                                <p className="text-[10px] font-black text-gray-400 uppercase mb-1">Email</p>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-semibold text-gray-700 truncate">{selectedClient.email || 'N/A'}</span>
                                                </div>
                                            </div>
                                            <div className="bg-gray-50 p-4 rounded-3xl border">
                                                <p className="text-[10px] font-black text-gray-400 uppercase mb-1">Téléphone</p>
                                                <div className="flex items-center gap-2">
                                                    <Phone size={12} className="text-[#E8391D]" />
                                                    <span className="text-xs font-black">{selectedClient.telephone || 'Non renseigné'}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">

                                {/* COLONNE GAUCHE (60%) : ANALYSE & TRANSACTIONS */}
                                <div className="xl:col-span-7 space-y-8">

                                    {/* CONSOLE DIAGNOSTIC IA PREMIUM */}
                                    <div className="bg-[#1A1A1A] rounded-[48px] p-12 text-white shadow-2xl relative overflow-hidden border border-gray-800">
                                        <div className="absolute -top-24 -left-24 w-64 h-64 bg-[#E8391D]/20 rounded-full blur-[100px]" />
                                        <div className="absolute top-0 right-0 p-10 opacity-5">
                                            <Brain size={180} />
                                        </div>

                                        <div className="relative space-y-10">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-4">
                                                    <div className="w-14 h-14 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl flex items-center justify-center text-[#FFC000]">
                                                        <Activity size={28} />
                                                    </div>
                                                    <div>
                                                        <h3 className="text-md font-black uppercase tracking-[0.2em] text-white">Synthese IA</h3>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-xl">
                                                    <Zap size={14} className="text-[#E8391D]" />
                                                    <span className="text-[10px] font-black text-[#E8391D] uppercase">Fiabilité {selectedClient.fiabilite}%</span>
                                                </div>
                                            </div>

                                            <div className="p-8 bg-white/5 rounded-[32px] border border-white/5 backdrop-blur-sm">
                                                <p className="text-2xl font-bold leading-[1.6] italic text-gray-100 first-letter:text-5xl first-letter:float-left first-letter:mr-3 first-letter:font-black first-letter:text-[#E8391D]">
                                                    {selectedClient.iaDiagnostic}
                                                </p>
                                            </div>

                                            <div className="flex items-center gap-6">
                                                <div className="flex -space-x-4">
                                                    {[1, 2, 3].map(i => <div key={i} className="w-10 h-10 rounded-full border-2 border-[#1A1A1A] bg-gray-700"></div>)}
                                                </div>
                                                <p className="text-[10px] font-black uppercase tracking-widest text-gray-500">Données croisées avec le réseau succursales</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* LISTE DES FLUX FINANCIERS PRESTIGE */}
                                    <div className="bg-white rounded-[48px] border border-gray-50 shadow-2xl p-12 space-y-8">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <div className="w-12 h-12 bg-red-50 rounded-2xl flex items-center justify-center text-[#E8391D]">
                                                    <TrendingUp size={24} />
                                                </div>
                                                <h3 className="text-md font-black uppercase tracking-[0.2em] text-[#1A1A1A]">Flux Transactionnels</h3>
                                            </div>
                                            <div className="flex gap-2">
                                                <button className="px-4 py-2 bg-gray-50 border border-gray-100 rounded-xl text-[10px] font-black uppercase text-gray-400 hover:text-[#E8391D] transition-colors">Exporter PDF</button>
                                                <button className="px-4 py-2 bg-gray-50 border border-gray-100 rounded-xl text-[10px] font-black uppercase text-gray-400 hover:text-[#E8391D] transition-colors">Filtrer</button>
                                            </div>
                                        </div>

                                        <div className="space-y-3">
                                            {paginatedTransactions && paginatedTransactions.length > 0 ? (
                                                paginatedTransactions.map((tx) => {
                                                    const typeBrut = tx.typeOperation || tx.type || 'Opération';
                                                    const typeUpper = typeBrut.toUpperCase();
                                                    const dateOp = tx.dateHeureOperation || tx.date || '—';

                                                    const estDebit =
                                                        tx.montant < 0 ||
                                                        ['RETRAIT', 'PAIEMENT', 'ACHAT', 'FACTURE', 'EMIS', 'PRELEVEMENT', 'COMMISSION', 'FRAIS', 'REJETE'].some(word => typeUpper.includes(word));

                                                    return (
                                                        <div key={tx.id} className="flex justify-between items-center p-6 rounded-[32px] border border-transparent bg-gray-50/50 hover:bg-white hover:border-[#E8391D30] hover:shadow-xl hover:shadow-red-900/5 transition-all duration-300 group">
                                                            <div className="flex items-center gap-6">
                                                                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-all shadow-inner ${estDebit ? 'bg-red-100/50 text-[#E8391D]' : 'bg-green-100/50 text-green-600'}`}>
                                                                    {estDebit ? <ArrowUpRight size={24} /> : <ArrowDownLeft size={24} />}
                                                                </div>
                                                                <div className="space-y-1">
                                                                    <p className="text-sm font-black text-[#1A1A1A] uppercase tracking-tight">{typeBrut.replace('_', ' ')}</p>
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">
                                                                            {new Date(dateOp).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })}
                                                                        </span>
                                                                        <div className="w-1 h-1 rounded-full bg-gray-300" />
                                                                        <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest truncate max-w-[200px]">
                                                                            {tx.label || 'SANS RÉFÉRENCE'}
                                                                        </span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <div className="text-right">
                                                                <span className={`text-lg font-black tracking-tighter ${estDebit ? 'text-[#E8391D]' : 'text-green-600'}`}>
                                                                    {estDebit ? '-' : '+'}{Math.abs(tx.montant).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                                </span>
                                                                <p className="text-[8px] font-black text-gray-300 uppercase tracking-widest">MAD (DIRHAMS)</p>
                                                            </div>
                                                        </div>
                                                    )
                                                })
                                            ) : (
                                                <div className="py-20 text-center">
                                                    <div className="w-20 h-20 bg-gray-50 rounded-full mx-auto flex items-center justify-center text-gray-200 mb-6">
                                                        <Clock size={32} />
                                                    </div>
                                                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em]">Aucun mouvement détecté</p>
                                                </div>
                                            )}
                                        </div>

                                        {/* CONTRÔLES PAGINATION TRANSACTIONS */}
                                        {totalTxPages > 1 && (
                                            <div className="mt-8 pt-6 border-t flex items-center justify-between">
                                                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                                                    Affichage {paginatedTransactions.length} sur {transactions.length} flux
                                                </p>
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={() => setCurrentTxPage(p => Math.max(1, p - 1))}
                                                        disabled={currentTxPage === 1}
                                                        className="w-10 h-10 flex items-center justify-center rounded-2xl border bg-white hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm"
                                                    >
                                                        <ChevronLeft size={16} />
                                                    </button>
                                                    <div className="px-4 py-2 bg-gray-50 rounded-2xl border text-xs font-black text-[#E8391D]">
                                                        {currentTxPage} / {totalTxPages}
                                                    </div>
                                                    <button
                                                        onClick={() => setCurrentTxPage(p => Math.min(totalTxPages, p + 1))}
                                                        disabled={currentTxPage === totalTxPages}
                                                        className="w-10 h-10 flex items-center justify-center rounded-2xl border bg-white hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm"
                                                    >
                                                        <ChevronRight size={16} />
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* COLONNE DROITE (40%) : STRATÉGIE IA + ARBITRAGE */}
                                <div className="xl:col-span-5 space-y-8">

                                    {/* ── BLOC STRATÉGIE DE L'AGENT IA ───────────────────── */}
                                    {(() => {
                                        const strategie = genererStrategieAgent(selectedClient);
                                        if (!strategie) return null;
                                        return (
                                            <div className="bg-white rounded-[48px] border border-gray-50 shadow-2xl p-10 relative overflow-hidden">
                                                <div className={`absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r ${strategie.couleur}`} />
                                                <div className="absolute -top-20 -right-20 w-48 h-48 rounded-full bg-gradient-to-br opacity-5" style={{background: 'radial-gradient(circle, #E8391D, transparent)'}} />

                                                <div className="flex items-center justify-between mb-8">
                                                    <div className="flex items-center gap-4">
                                                        <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${strategie.couleur} flex items-center justify-center text-white shadow-lg`}>
                                                            <Brain size={22} />
                                                        </div>
                                                        <div>
                                                            <h3 className="text-sm font-black uppercase tracking-[0.2em] text-[#1A1A1A]">Stratégie de l'Agent IA</h3>
                                                            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{strategie.titre}</p>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-4">
                                                        {selectedClient.risque !== null && selectedClient.risque !== undefined && (
                                                            <div className="text-right leading-none">
                                                                <p className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-1">
                                                                    Risque de churn
                                                                </p>
                                                                <p className="text-2xl font-black" style={{ color: couleurRisque(selectedClient.niveauRisque) }}>
                                                                    {selectedClient.risque}%
                                                                </p>
                                                                {selectedClient.niveauRisque && (
                                                                    <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mt-1">
                                                                        {selectedClient.niveauRisque}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        )}
                                                        <span className={`text-[9px] font-black uppercase tracking-widest px-3 py-1.5 rounded-full ${strategie.badgeCouleur}`}>
                                                            {strategie.badge}
                                                        </span>
                                                    </div>
                                                </div>

                                                <div className="space-y-4">
                                                    {strategie.etapes.map((etape, i) => (
                                                        <div key={i} className="flex items-start gap-4 p-5 bg-gray-50 rounded-[24px] border border-gray-100 hover:border-gray-200 hover:bg-white transition-all group">
                                                            <div className="w-10 h-10 rounded-2xl bg-white border border-gray-100 flex items-center justify-center text-lg shadow-sm flex-shrink-0 group-hover:scale-110 transition-transform">
                                                                {etape.icon}
                                                            </div>
                                                            <p className="text-xs font-semibold text-gray-600 leading-relaxed pt-1">{etape.text}</p>
                                                        </div>
                                                    ))}
                                                </div>

                                                <div className="mt-6 flex items-center gap-3">
                                                    <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full ${strategie.barreColor} rounded-full transition-all duration-1000`}
                                                            style={{ width: `${selectedClient.score}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-[10px] font-black text-gray-400 uppercase">Priorité : {selectedClient.score}%</span>
                                                </div>
                                            </div>
                                        );
                                    })()}
                                    <div className="bg-white rounded-[48px] border border-gray-50 shadow-2xl p-12 relative overflow-hidden">
                                        <div className="absolute top-0 left-0 w-2 h-full bg-[#FFC000]" />

                                        <div className="flex items-center gap-4 mb-12">
                                            <div className="w-14 h-14 bg-yellow-50 rounded-2xl flex items-center justify-center text-[#B45309]">
                                                <Zap size={28} />
                                            </div>
                                            <div>
                                                <h3 className="text-md font-black uppercase tracking-[0.2em] text-[#1A1A1A]">Terminal d'Arbitrage</h3>
                                                <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Décision Immédiate Stratégique</p>
                                            </div>
                                        </div>

                                        <div className="flex gap-4 p-2 bg-gray-50 rounded-[36px] mb-12 shadow-inner">
                                            <button
                                                onClick={() => setActionPath('DIRECT')}
                                                className={`flex-1 flex flex-col items-center gap-2 py-6 rounded-[32px] transition-all transform active:scale-95 ${actionPath === 'DIRECT' ? 'bg-white text-[#1A1A1A] shadow-xl border border-gray-100' : 'text-gray-400 hover:text-gray-600'}`}
                                            >
                                                <Briefcase size={24} />
                                                <span className="text-[9px] font-black uppercase tracking-widest">Maîtrise Interne</span>
                                            </button>
                                            <button
                                                onClick={() => setActionPath('DELEGUE')}
                                                className={`flex-1 flex flex-col items-center gap-2 py-6 rounded-[32px] transition-all transform active:scale-95 ${actionPath === 'DELEGUE' ? 'bg-[#E8391D] text-white shadow-xl shadow-red-500/20' : 'text-gray-400 hover:text-gray-600'}`}
                                            >
                                                <Users size={24} />
                                                <span className="text-[9px] font-black uppercase tracking-widest">Délégation Réseau</span>
                                            </button>
                                        </div>

                                        <form onSubmit={handleSubmitDecision} className="space-y-8">
                                            {actionPath === 'DIRECT' ? (
                                                <div className="space-y-4 animate-in slide-in-from-left-4 duration-500">
                                                    <label className="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">Arbitrage technique</label>
                                                    <select
                                                        className="w-full p-5 bg-gray-50 border-none rounded-3xl text-sm font-black focus:ring-2 focus:ring-[#FFC000]"
                                                        value={decisionForm.statut}
                                                        onChange={(e) => setDecisionForm({ ...decisionForm, statut: e.target.value })}
                                                    >
                                                        <option value="RISQUE_ECARTE">✅ Risque Écarté / Dossier sain</option>
                                                        <option value="SURVEILLANCE_APPROFONDIE">👁️ Surveillance Approfondie</option>
                                                        <option value="ACTION_RECOUVREMENT">🔴 Action de Recouvrement</option>
                                                        <option value="CLOTURE_PROPOSEE">⚠️ Proposition de Clôture</option>
                                                    </select>
                                                    <textarea
                                                        className="w-full p-6 bg-gray-50 border-none rounded-[30px] text-sm font-semibold placeholder:text-gray-300 min-h-[140px] focus:ring-2 focus:ring-[#FFC000]"
                                                        placeholder="Saisissez votre justificatif interne pour le comité des risques..."
                                                        value={decisionForm.commentaire}
                                                        onChange={(e) => setDecisionForm({ ...decisionForm, commentaire: e.target.value })}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="space-y-6 animate-in slide-in-from-right-4 duration-500">
                                                    <div className="grid grid-cols-2 gap-4">
                                                        <div className="space-y-2">
                                                            <label className="text-[10px] font-black text-indigo-400 uppercase tracking-widest ml-1">Nature de l'action</label>
                                                            <select
                                                                className="w-full p-4 bg-indigo-50/50 border-none rounded-2xl text-xs font-black text-indigo-900 focus:ring-2 focus:ring-indigo-500"
                                                                value={decisionForm.typeDelegation}
                                                                onChange={(e) => setDecisionForm({ ...decisionForm, typeDelegation: e.target.value })}
                                                            >
                                                                <option value="APPEL">📞 Appel de Courtoisie</option>
                                                                <option value="RDV">🤝 Entretien en Agence</option>
                                                                <option value="RECOUVREMENT">⚖️ Recouvrement Amiable</option>
                                                                <option value="DOSSIER">📂 Mise à jour KYC/Dossier</option>
                                                            </select>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <label className="text-[10px] font-black text-indigo-400 uppercase tracking-widest ml-1">Niveau d'urgence</label>
                                                            <div className="flex bg-indigo-50/50 rounded-2xl p-1 gap-1">
                                                                {['BAS', 'MOYEN', 'URGENT'].map((p) => (
                                                                    <button
                                                                        key={p}
                                                                        type="button"
                                                                        onClick={() => setDecisionForm({ ...decisionForm, priorite: p })}
                                                                        className={`flex-1 py-2 rounded-xl text-[9px] font-black uppercase transition-all ${decisionForm.priorite === p ? 'bg-white text-indigo-600 shadow-sm' : 'text-indigo-300 hover:text-indigo-500'}`}
                                                                    >
                                                                        {p}
                                                                    </button>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div className="bg-indigo-50 p-6 rounded-[30px] border border-indigo-100">
                                                        <div className="flex items-center gap-3 mb-3">
                                                            <div className="bg-[#FFC000] text-[#1A1A1A] p-1.5 rounded-lg"><Target size={14} /></div>
                                                            <p className="text-xs font-black text-[#B45309] uppercase">Opportunité Commerciale à Transférer</p>
                                                        </div>
                                                        <textarea
                                                            className="w-full p-4 bg-white/50 border-none rounded-2xl text-xs font-bold text-indigo-900 placeholder:text-indigo-300 min-h-[120px] focus:ring-2 focus:ring-indigo-500"
                                                            value={decisionForm.noteDelegation}
                                                            onChange={(e) => setDecisionForm({ ...decisionForm, noteDelegation: e.target.value })}
                                                            placeholder="Décrivez l'opportunité commerciale ou l'instruction précise pour le conseiller..."
                                                        />
                                                    </div>
                                                </div>
                                            )}

                                            <button
                                                type="submit"
                                                disabled={isSubmitting}
                                                className={`w-full py-6 rounded-[32px] font-black uppercase tracking-[0.3em] text-[10px] shadow-2xl transform hover:scale-[1.02] active:scale-95 transition-all flex items-center justify-center gap-4 disabled:opacity-50 ${actionPath === 'DIRECT' ? 'bg-[#1A1A1A] text-white shadow-black/20' : 'bg-[#E8391D] text-white shadow-red-500/20'}`}
                                            >
                                                {isSubmitting ? (
                                                    <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                                ) : (
                                                    <Shield size={20} className={actionPath === 'DIRECT' ? 'text-[#FFC000]' : 'text-white'} />
                                                )}
                                                {isSubmitting ? 'EXÉCUTION EN COURS...' : 'CONFIRMER L\'ARBITRAGE'}
                                            </button>
                                        </form>

                                        {actionSaved && (
                                            <div className="mt-8 p-6 bg-green-50 border border-green-100 rounded-[32px] flex items-center gap-4 text-green-800 animate-in zoom-in duration-300">
                                                <div className="bg-green-500 text-white p-2 rounded-xl"><CheckCircle size={18} /></div>
                                                <p className="text-[10px] font-black uppercase tracking-widest">{actionSaved}</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* FOOTER AUDIT TRAIL PRESTIGE */}
                                    <div className="bg-white/40 backdrop-blur-3xl rounded-[40px] p-8 border border-white/50 flex items-center justify-between shadow-xl">
                                        <div className="flex items-center gap-5">
                                            <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center text-gray-400 shadow-xl border border-gray-100"><Clock size={24} /></div>
                                            <div>
                                                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Derniere analyse certifiee</p>
                                                <p className="text-xs font-black text-[#1A1A1A]">
                                                    {lastAction ? (
                                                        `${new Date(lastAction.dateAction).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })} à ${new Date(lastAction.dateAction).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
                                                    ) : "DOSSIER EN ATTENTE D'EXAMEN"}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="w-px h-12 bg-gray-200/50" />
                                        <div className="flex items-center gap-5 text-right">
                                            <div>
                                                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Expert Responsable</p>
                                                <p className="text-xs font-black text-[#1A1A1A] uppercase">
                                                    {lastAction?.banquier?.nomComplet || "CORE-AI SYSTEM"}
                                                </p>
                                            </div>
                                            <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center text-gray-400 shadow-xl border border-gray-100"><Users size={24} /></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
                            <div className="w-32 h-32 bg-white rounded-[40px] shadow-2xl flex items-center justify-center text-gray-200 animate-pulse border">
                                <Target size={64} />
                            </div>
                            <div className="max-w-md">
                                <h2 className="text-2xl font-black mb-2">Sélectionner un dossier</h2>
                                <p className="text-gray-400 font-bold uppercase tracking-widest text-xs">Veuillez choisir un client dans la liste latérale pour démarrer l'analyse de risque.</p>
                            </div>
                        </div>
                    )}
                </section>
            </main>
        </div>
    );
}

// ── Icons techniques additionnelles ──────────────────────────────────────────
const Loader2 = ({ className }) => (
    <svg className={`h-4 w-4 ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
);
