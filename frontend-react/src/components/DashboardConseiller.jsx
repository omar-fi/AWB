import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import { useAuth } from '../context/AuthContext';
import ActionModal from './ActionModal';
import ClientTable from './ClientTable';
import ClientDetailsModal from './ClientDetailsModal';
import CreateClientModal from './CreateClientModal';
import EditClientModal from './EditClientModal';
import {
    Users, TrendingUp, Bell, LogOut, Search, Calendar,
    ChevronRight, LayoutDashboard, UserCheck, Loader2,
    RefreshCw, MessageCircle, Clock, CreditCard, AlertTriangle,
    Brain, Target, Zap, Shield, Activity, Eye,
    ChevronDown, ChevronUp, Phone, Mail, Trash2, Edit, UserPlus
} from 'lucide-react';
import awbLogo from '../assets/react.jpeg';

// ── Palette AWB ──────────────────────────────────────────────────────────────
// Rouge : #E8391D | Jaune : #FFC000 | Noir : #1A1A1A | Blanc fond : #F5F5F5

const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
};

const isToday = (dateStr) => {
    if (!dateStr) return false;
    const d = new Date(dateStr);
    return d.toDateString() === new Date().toDateString();
};

const isFuture = (dateStr) => {
    if (!dateStr) return false;
    const d = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return d > today;
};

const getScoreStyle = (score) => {
    if (!score) return { bg: '#F5F5F5', text: '#999', bar: '#DDD', label: 'N/A' };
    if (score >= 85) return { bg: '#FFF1F0', text: '#CF1322', bar: '#F5222D', label: 'Très probable' };
    if (score >= 70) return { bg: '#FFF7E6', text: '#D46B08', bar: '#FA8C16', label: 'Probable' };
    if (score >= 50) return { bg: '#FFFBE6', text: '#B45309', bar: '#FFC000', label: 'À suivre' };
    return { bg: '#F6FFED', text: '#389E0D', bar: '#52C41A', label: 'Faible' };
};

const getRiskBadge = (niveau) => {
    const n = (niveau || '').toUpperCase();
    if (n === 'CRITIQUE' || n === 'ÉLEVÉ' || n === 'HIGH') {
        return { cls: 'bg-red-50 text-red-700 border-red-200', icon: '🔴', label: 'Risque critique' };
    }
    if (n === 'ALERTE' || n === 'MOYEN' || n === 'MEDIUM') {
        return { cls: 'bg-amber-50 text-amber-700 border-amber-200', icon: '🟡', label: 'Alerte Risque' };
    }
    if (n === 'SOUS SURVEILLANCE' || n === 'FAIBLE' || n === 'LOW') {
        return { cls: 'bg-blue-50 text-blue-700 border-blue-200', icon: '🔵', label: 'Surveillance' };
    }
    return { cls: 'bg-gray-100 text-gray-500 border-gray-200', icon: '⚪', label: 'Non évalué' };
};

const getDiagnosticText = (text) => {
    if (!text) return 'Analyse comportementale en cours...';
    const beforeStrategy = String(text).split(/Strategie\s*:|Stratégie\s*:/i)[0].trim();
    return beforeStrategy.replace(/^Sante\s*:|^Santé\s*:/i, '').trim() || 'Analyse comportementale en cours...';
};


// ── Carte Prédiction Conseiller (vue simplifiée vente) ───────────────────────
const ConseillerPredictionCard = ({ prediction, onAction, onEdit }) => {
    const { user, hasPermission } = useAuth();
    const [instruction, setInstruction] = useState(null);
    const client = prediction.client || {};
    const nomComplet = client.nomComplet || prediction.nomComplet || 'Client inconnu';
    const cin = client.cin || prediction.cin || '—';
    const dateAff = prediction.datePrevueAjustee || prediction.datePrevue;
    const todayCard = isToday(dateAff);
    const rawScore = prediction.scoreProbabiliteGlobal || 0;
    const score = rawScore <= 1 ? rawScore * 100 : rawScore;
    const sc = getScoreStyle(score);

    useEffect(() => {
        const fetchInstruction = async () => {
            const cid = client.id || prediction.clientId || prediction.client_id;
            if (!cid) return;
            try {
                const res = await api.get(`/actions/client/${cid}/dernier-examen`);
                if (res.status === 200 && res.data) setInstruction(res.data);
            } catch { }
        };
        fetchInstruction();
    }, [client.id]);

    const handleSupprimerLocal = async (e) => {
        e.stopPropagation();
        const confirmation = window.confirm(`Supprimer le client ${nomComplet} ?`);
        if (confirmation) {
            try {
                await api.delete(`/clients/${client.id || prediction.clientId || prediction.client_id}`);
                alert("Client supprimé.");
                window.location.reload();
            } catch (err) {
                console.error(err);
                alert("Erreur suppression.");
            }
        }
    };

    return (
        <div
            className="relative bg-white rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden"
            style={{ borderColor: todayCard ? '#E8391D' : '#E5E7EB', borderWidth: todayCard ? '1.5px' : '1px' }}
        >
            <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl"
                style={{ background: todayCard ? '#E8391D' : '#E5E7EB' }} />

            <div className="pl-5 pr-5 pt-4 pb-4">
                {/* En-tête client */}
                <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-sm text-white flex-shrink-0"
                            style={{ background: todayCard ? 'linear-gradient(135deg,#E8391D,#FFC000)' : '#1A1A1A' }}>
                            {nomComplet.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <p className="font-black text-[#1A1A1A] text-sm">{nomComplet}</p>
                            <p className="text-[10px] text-gray-400 font-mono">{cin}</p>
                        </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5">
                        {score > 0 && (
                            <span
                                className="text-[11px] font-bold px-2.5 py-1 rounded-full flex items-center gap-1"
                                style={{ background: sc.bg, color: sc.text }}
                            >
                                <Activity size={11} />
                                Prob. visite {Math.round(score)}%
                            </span>
                        )}
                        <span className="text-xs font-semibold flex items-center gap-1 px-2 py-0.5 rounded-full"
                            style={{ background: todayCard ? '#FEF3F0' : '#F5F5F5', color: todayCard ? '#E8391D' : '#6B7280' }}>
                            <Calendar size={10} />
                            {todayCard ? '📍 Aujourd\'hui' : formatDate(dateAff)}
                        </span>
                    </div>
                </div>

                {/* Opération prévue */}
                <div className="mt-3 flex items-center gap-2 p-3 rounded-xl bg-gray-50 border border-gray-100">
                    <CreditCard size={14} className="text-gray-400 flex-shrink-0" />
                    <div>
                        <p className="text-[9px] text-gray-400 uppercase tracking-widest font-bold">Opération prévue</p>
                        <p className="text-xs font-black text-[#1A1A1A]">
                            {prediction.operationPrevue || 'Opération Bancaire'}
                        </p>
                    </div>
                    {prediction.plageHorairePrevue && (
                        <span className="ml-auto text-[10px] text-gray-400 flex items-center gap-1">
                            <Clock size={10} /> {prediction.plageHorairePrevue}
                        </span>
                    )}
                </div>

                {/* Opportunité Commerciale (Uniquement si transférée par l'expert) */}
                {instruction && (instruction.statut === 'DELEGUE_COMMERCIAL' || instruction.typeDelegation === 'ACTION_DELEGUE') && (
                    <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-xl shadow-sm animate-in zoom-in duration-300">
                        <div className="flex items-center gap-2 mb-1">
                            <Target size={12} className="text-[#B45309]" />
                            <span className="text-[9px] font-black text-[#B45309] uppercase tracking-widest">Opportunité Commerciale</span>
                        </div>
                        <p className="text-xs font-bold text-[#78350F] italic">"{instruction.commentaire}"</p>
                    </div>
                )}

                {/* Boutons actions */}
                <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-1">
                        {(user.role === 'DIRECTEUR' || hasPermission('CAN_EDIT_CLIENT')) && (
                            <button
                                onClick={(e) => { e.stopPropagation(); onEdit(prediction.client || prediction); }}
                                className="p-2 text-amber-600 hover:bg-amber-50 rounded-lg transition-all"
                                title="Modifier"
                            >
                                <Edit size={14} />
                            </button>
                        )}
                        {(user.role === 'DIRECTEUR' || hasPermission('CAN_DELETE_ACCOUNT')) && (
                            <button
                                onClick={handleSupprimerLocal}
                                className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-all"
                                title="Supprimer"
                            >
                                <Trash2 size={14} />
                            </button>
                        )}
                    </div>
                    <button
                        onClick={() => onAction(prediction)}
                        className="inline-flex items-center gap-2 px-4 py-2 text-white text-xs font-black rounded-xl shadow-sm transition-all duration-200 active:scale-95 hover:shadow-md"
                        style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)' }}
                    >
                        Enregistrer vente <ChevronRight size={13} />
                    </button>
                </div>
            </div>
        </div>
    );
};

// ── Carte Prédiction Portefeuilleur (vue complète analyse) ────────────────────
const PredictionCard = ({ prediction, onAction, onEdit, highlight = false }) => {
    const { user, hasPermission } = useAuth();
    const [instruction, setInstruction] = useState(null);
    const client = prediction.client || {};
    const nomComplet = client.nomComplet || prediction.nomComplet || 'Client inconnu';

    useEffect(() => {
        const fetchInstruction = async () => {
            const cid = client.id || prediction.clientId || prediction.client_id;
            if (!cid) return;
            try {
                const res = await api.get(`/actions/client/${cid}/dernier-examen`);
                if (res.status === 200 && res.data) {
                    setInstruction(res.data);
                }
            } catch (err) {
                console.error("❌ Erreur instruction:", err);
            }
        };
        fetchInstruction();
    }, [client.id, prediction.clientId, prediction.client_id]);

    const cin = client.cin || prediction.cin || '—';
    const rawScore = prediction.scoreProbabiliteGlobal || 0;
    const score = rawScore <= 1 ? rawScore * 100 : rawScore;
    const sc = getScoreStyle(score);
    const risk = getRiskBadge(prediction.niveauRisque || client.niveauRisque);
    const dateAff = prediction.datePrevueAjustee || prediction.datePrevue;
    const todayCard = isToday(dateAff);

    const handleSupprimerLocal = async (e) => {
        e.stopPropagation();
        const confirmation = window.confirm(`Supprimer le client ${nomComplet} ?`);
        if (confirmation) {
            try {
                await api.delete(`/clients/${client.id || prediction.clientId || prediction.client_id}`);
                alert("Client supprimé.");
                window.location.reload(); // Recharger pour rafraîchir la liste
            } catch (err) {
                console.error(err);
                alert("Erreur suppression.");
            }
        }
    };

    return (
        <div
            className="relative bg-white rounded-2xl border transition-all duration-300 shadow-sm hover:shadow-lg overflow-hidden"
            style={{
                borderColor: todayCard ? '#E8391D' : '#E5E7EB',
                borderWidth: todayCard ? '1.5px' : '1px'
            }}
        >
            <div
                className="absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl"
                style={{ background: todayCard ? '#E8391D' : score >= 80 ? '#FFC000' : score >= 60 ? '#E8391D80' : '#E5E7EB' }}
            />

            <div className="pl-5 pr-5 pt-4 pb-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                        <div
                            className="w-11 h-11 rounded-xl flex items-center justify-center font-black text-base flex-shrink-0"
                            style={{
                                background: todayCard
                                    ? 'linear-gradient(135deg, #E8391D, #FFC000)'
                                    : 'linear-gradient(135deg, #1A1A1A, #3A3A3A)',
                                color: 'white'
                            }}
                        >
                            {nomComplet.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                            <p className="font-black text-[#1A1A1A] text-sm truncate">{nomComplet}</p>
                            <div className="flex flex-col gap-0.5 mt-0.5">
                                <p className="text-[10px] text-gray-400 font-mono flex items-center gap-1">
                                    <span className="font-bold">ID:</span> {cin}
                                </p>
                                {client.email && (
                                    <p className="text-[10px] text-gray-500 flex items-center gap-1 truncate">
                                        <Mail size={10} className="text-gray-400" /> {client.email}
                                    </p>
                                )}
                                {client.telephone && (
                                    <p className="text-[10px] text-gray-500 flex items-center gap-1">
                                        <Phone size={10} className="text-[#E8391D]" /> {client.telephone}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                        {score > 0 && (
                            <span
                                className="text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1"
                                style={{ background: sc.bg, color: sc.text }}
                            >
                                <Activity size={11} />
                                {Math.round(score)}% {sc.label}
                            </span>
                        )}
                        <span
                            className="text-xs font-semibold flex items-center gap-1 px-2 py-0.5 rounded-full"
                            style={{
                                background: todayCard ? '#FEF3F0' : '#F5F5F5',
                                color: todayCard ? '#E8391D' : '#6B7280'
                            }}
                        >
                            <Calendar size={10} />
                            {todayCard ? '📍 Aujourd\'hui' : formatDate(dateAff)}
                        </span>
                    </div>
                </div>

                {/* Instruction Portefeuilleur (Opportunité Commerciale) */}
                {instruction && (instruction.statut === 'DELEGUE_COMMERCIAL' || instruction.typeDelegation === 'ACTION_DELEGUE') && (
                    <div className="mt-4 p-3.5 bg-amber-50 border border-amber-200 rounded-2xl shadow-md animate-in fade-in slide-in-from-top-2 duration-500">
                        <div className="flex items-center gap-2 mb-1.5">
                            <Target size={14} className="text-[#B45309]" />
                            <span className="text-[10px] font-black text-[#B45309] uppercase tracking-widest">Opportunité Commerciale à saisir</span>
                        </div>
                        <p className="text-xs font-bold text-[#78350F] leading-relaxed italic">
                            "{instruction.commentaire}"
                        </p>
                    </div>
                )}

                <div className="mt-3 flex flex-wrap gap-1.5">
                    {prediction.plageHorairePrevue && (
                        <span className="inline-flex items-center gap-1 text-xs bg-gray-50 text-gray-600 border border-gray-100 px-2.5 py-1 rounded-full font-medium">
                            <Clock size={10} /> {prediction.plageHorairePrevue}
                        </span>
                    )}
                    {prediction.operationPrevue && (
                        <span
                            className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium"
                            style={{ background: '#FFF7E6', color: '#92400E' }}
                        >
                            <CreditCard size={10} /> {prediction.operationPrevue}
                        </span>
                    )}
                    <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium border ${risk.cls}`}>
                        {risk.icon} {risk.label}
                    </span>
                </div>

                {score > 0 && (
                    <div className="mt-3">
                        <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className="h-full rounded-full transition-all duration-700"
                                style={{ width: `${Math.round(score)}%`, background: sc.bar }}
                            />
                        </div>
                    </div>
                )}

                <div className="mt-4 space-y-2">
                    {/* Analyse santé client - Réservé au Portefeuilleur/Directeur */}
                    {(user.role === 'PORTEFEUILLEUR' || user.role === 'DIRECTEUR' || hasPermission('CAN_ANALYZE_CLIENTS')) && (
                        <details
                            className="group p-3 rounded-xl border transition-all duration-300 cursor-pointer select-none"
                            style={{ background: '#F8FAFC', borderColor: '#E2E8F0' }}
                        >
                            <summary className="flex items-center gap-2 outline-none text-gray-400">
                                <Brain size={13} />
                                <span className="text-[9px] font-black uppercase tracking-widest">Analyse santé client</span>
                                <span className="ml-auto text-[8px] transition-transform group-open:rotate-180">▼</span>
                            </summary>
                            <div className="mt-2 pt-2 border-t border-slate-200">
                                <p className="text-[11px] text-[#475569] leading-relaxed font-medium italic">
                                    "{getDiagnosticText(prediction.insightGenai || prediction.insightIa)}"
                                </p>
                            </div>
                        </details>
                    )}
                </div>

                <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        {(user.role === 'DIRECTEUR' || hasPermission('CAN_EDIT_CLIENT')) && (
                            <button
                                onClick={(e) => { e.stopPropagation(); onEdit(prediction.client || prediction); }}
                                className="p-2 text-amber-600 hover:bg-amber-50 rounded-xl border border-transparent hover:border-amber-100 transition-all"
                                title="Modifier"
                            >
                                <Edit size={16} />
                            </button>
                        )}
                        {(user.role === 'DIRECTEUR' || hasPermission('CAN_DELETE_ACCOUNT')) && (
                            <button
                                onClick={handleSupprimerLocal}
                                className="p-2 text-red-600 hover:bg-red-50 rounded-xl border border-transparent hover:border-red-100 transition-all"
                                title="Supprimer"
                            >
                                <Trash2 size={16} />
                            </button>
                        )}
                    </div>
                    <button
                        onClick={() => onAction(prediction)}
                        className="inline-flex items-center gap-2 px-4 py-2 text-white text-xs font-black rounded-xl shadow-sm transition-all duration-200 active:scale-95 hover:shadow-md"
                        style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)' }}
                    >
                        Enregistrer résultat <ChevronRight size={13} />
                    </button>
                </div>
            </div>
        </div>
    );
};

// ── Vue Agenda ────────────────────────────────────────────────────────────────
const AgendaView = ({ predictions, onAction, onEdit }) => {
    const grouped = {};
    for (const p of predictions) {
        const d = p.datePrevueAjustee || p.datePrevue;
        if (!d) continue;
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(p);
    }

    const sortedDates = Object.keys(grouped).sort((a, b) => new Date(a) - new Date(b));

    if (sortedDates.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-24">
                <Calendar size={52} style={{ color: '#E5E7EB' }} />
                <p className="font-bold text-gray-400 mt-3">L'agenda est vide</p>
                <p className="text-xs text-gray-400 mt-1">Aucune visite IA n'est planifiée.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-fade-in-down">
            {sortedDates.map(date => {
                const preds = grouped[date];
                const dateObj = new Date(date);
                const isTdy = isToday(date);
                const isPast = !isTdy && dateObj < new Date(new Date().setHours(0, 0, 0, 0));

                return (
                    <section key={date} className="relative">
                        <div className="flex items-center gap-3 mb-4">
                            <div className={`w-11 h-11 rounded-xl flex flex-col items-center justify-center font-bold text-white shadow-sm ${isTdy ? 'bg-gradient-to-br from-[#E8391D] to-[#FFC000]' : isPast ? 'bg-gray-400' : 'bg-[#1A1A1A]'}`}>
                                <span className="text-[9px] uppercase tracking-wider opacity-90">{dateObj.toLocaleDateString('fr-FR', { weekday: 'short' })}</span>
                                <span className="text-sm leading-none">{dateObj.getDate()}</span>
                            </div>
                            <div>
                                <h2 className="text-sm font-black text-gray-800 flex items-center gap-2 capitalize">
                                    {dateObj.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                                    {isTdy && <span className="text-[9px] bg-[#FEF3F0] text-[#E8391D] px-2 py-0.5 rounded-full uppercase tracking-widest border border-[#FCA5A5] font-black">Aujourd'hui</span>}
                                </h2>
                                <p className="text-xs text-gray-500 font-medium">
                                    {preds.length} rendez-vous prévu{preds.length > 1 ? 's' : ''}
                                </p>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 border-l-[3px] border-gray-100 ml-5 pl-8 py-2 relative">
                            <div className="absolute top-0 bottom-0 left-[-3px] w-[3px] rounded-full" style={{ background: isTdy ? '#FFC000' : 'transparent' }} />
                            {preds.map(p => <PredictionCard key={p.id} prediction={p} onAction={onAction} onEdit={onEdit} />)}
                        </div>
                    </section>
                );
            })}
        </div>
    );
};

// ── Dashboard Conseiller ──────────────────────────────────────────────────────
const DashboardConseiller = () => {
    const { user, logout, hasPermission } = useAuth();
    const [allPredictions, setAllPredictions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedPrediction, setSelectedPrediction] = useState(null);
    const [isActionModalOpen, setIsActionModalOpen] = useState(false);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [selectedClientForEdit, setSelectedClientForEdit] = useState(null);
    const [selectedClientDetails, setSelectedClientDetails] = useState(null);
    const [isClientDetailsModalOpen, setIsClientDetailsModalOpen] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [activeTab, setActiveTab] = useState(user.role === 'PORTEFEUILLEUR' ? 'portefeuille' : 'today');
    const [error, setError] = useState(null);

    const [clientsPage, setClientsPage] = useState({ content: [], totalPages: 0, totalElements: 0 });
    const [clientPageActive, setClientPageActive] = useState(0);
    const [clientsLoading, setClientsLoading] = useState(false);

    const fetchAllData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [allRes, clientsRes] = await Promise.all([
                api.get(`/predictions/agence/${user.agenceId}`),
                api.get(`/clients/agence/${user.agenceId}?page=0&size=1000`),
            ]);

            const predictions = Array.isArray(allRes.data) ? allRes.data : [];
            const clients = Array.isArray(clientsRes.data?.content) ? clientsRes.data.content : [];

            const predictionsByClientId = new Map(
                predictions.map((p) => [
                    p?.client?.id || p?.clientId || p?.client_id,
                    p,
                ])
            );

            const merged = clients.map((client) => {
                const existing = predictionsByClientId.get(client.id);
                if (existing) return existing;
                const fallback = client.prediction || {};
                return {
                    id: `client-${client.id}`,
                    client,
                    clientId: client.id,
                    datePrevue: fallback.datePrevue || null,
                    datePrevueAjustee: fallback.datePrevueAjustee || null,
                    plageHorairePrevue: fallback.plageHorairePrevue || null,
                    operationPrevue: fallback.operationPrevue || null,
                    scoreProbabiliteGlobal: fallback.scoreProbabiliteGlobal ?? null,
                    insightGenai: fallback.insightGenai || null,
                    niveauRisque: fallback.niveauRisque || client.niveauRisque || null,
                    strategiePrescrite: fallback.strategiePrescrite || fallback.strategie_prescrite || null,
                };
            });

            setAllPredictions(merged);
        } catch (err) {
            console.error('Erreur:', err);
            setError('Impossible de contacter le serveur.');
        } finally {
            setLoading(false);
        }
    };

    const fetchClients = async (query = searchTerm) => {
        setClientsLoading(true);
        try {
            const searchParam = query ? `&search=${encodeURIComponent(query)}` : '';
            const res = await api.get(`/clients/agence/${user.agenceId}?page=${clientPageActive}&size=10${searchParam}`);
            setClientsPage(res.data);
        } catch (err) {
            console.error('Erreur clients:', err);
        } finally {
            setClientsLoading(false);
        }
    };

    useEffect(() => { fetchAllData(); }, [user.agenceId]);

    useEffect(() => {
        setClientPageActive(0);
    }, [searchTerm]);

    useEffect(() => {
        if (activeTab === 'portefeuille') fetchClients();
    }, [activeTab, clientPageActive, searchTerm, user.agenceId]);

    const filterFn = (p) => {
        const term = searchTerm.toLowerCase();
        const c = p.client || {};
        return (c.nomComplet || p.nomComplet || '').toLowerCase().includes(term)
            || (c.cin || p.cin || '').toLowerCase().includes(term)
            || (p.operationPrevue || '').toLowerCase().includes(term);
    };

    const baseToday = allPredictions.filter(p => isToday(p.datePrevueAjustee || p.datePrevue));
    const displayList = (activeTab === 'today' ? baseToday : allPredictions).filter(filterFn);
    const todayPreds = baseToday.filter(filterFn);

    const NavItem = ({ tab, icon: Icon, label, count, accent }) => (
        <button
            onClick={() => setActiveTab(tab)}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-bold transition-all"
            style={{
                background: activeTab === tab ? 'rgba(255,255,255,0.12)' : 'transparent',
                color: activeTab === tab ? 'white' : 'rgba(255,255,255,0.45)',
                border: activeTab === tab ? '1px solid rgba(255,255,255,0.15)' : '1px solid transparent',
            }}
        >
            <Icon size={17} />
            <span>{label}</span>
            {count > 0 && (
                <span
                    className="ml-auto text-xs font-black px-2 py-0.5 rounded-full"
                    style={{ background: accent ? '#FFC000' : 'rgba(255,255,255,0.15)', color: accent ? '#1A1A1A' : 'white' }}
                >
                    {count}
                </span>
            )}
        </button>
    );

    return (
        <div className="flex h-screen overflow-hidden" style={{ background: '#F5F5F5', fontFamily: "'Inter', sans-serif" }}>
            <aside
                className="flex flex-col shadow-2xl flex-shrink-0"
                style={{ width: '270px', background: 'linear-gradient(185deg, #1A1A1A 0%, #2C1A14 60%, #1A0A04 100%)' }}
            >
                <div className="p-6 pb-4">
                    <div className="flex items-center gap-3 mb-8">
                        <img src={awbLogo} alt="AWB" className="w-10 h-10 rounded-xl object-contain bg-white p-0.5 shadow-lg" />
                        <div>
                            <p className="text-white font-black text-sm tracking-tight">AWB Front Office</p>
                            <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color: '#FFC000' }}>IA Prédictive</p>
                        </div>
                    </div>

                    <nav className="space-y-1">
                        <NavItem tab="today" icon={Zap} label="Clients attendus" count={baseToday.length} accent />
                        <button
                            onClick={() => setActiveTab('agenda')}
                            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-bold transition-all"
                            style={{
                                background: activeTab === 'agenda' ? 'rgba(255,255,255,0.12)' : 'transparent',
                                color: activeTab === 'agenda' ? 'white' : 'rgba(255,255,255,0.45)',
                                border: activeTab === 'agenda' ? '1px solid rgba(255,255,255,0.15)' : '1px solid transparent',
                            }}
                        >
                            <Calendar size={17} /><span>Agenda IA</span>
                        </button>
                        {(user.role === 'PORTEFEUILLEUR' || user.role === 'DIRECTEUR' || hasPermission('CAN_VIEW_ALL_PREDICTIONS') || hasPermission('CAN_VIEW_PORTFOLIO')) && (
                            <NavItem tab="portefeuille" icon={Users} label="Portefeuille Clients" count={clientsPage.totalElements} />
                        )}
                    </nav>
                </div>

                <div className="mt-auto p-5 space-y-3">
                    <div className="p-4 rounded-2xl border" style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.08)' }}>
                        <div className="flex items-center gap-3">
                            <div
                                className="w-10 h-10 rounded-full flex items-center justify-center font-black text-sm"
                                style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)', color: 'white' }}
                            >
                                {user.nomComplet?.charAt(0)}
                            </div>
                            <div className="overflow-hidden">
                                <p className="text-sm font-bold text-white truncate">{user.nomComplet}</p>
                                <p className="text-[10px] font-bold tracking-widest uppercase flex items-center gap-1" style={{ color: '#FFC000' }}>
                                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                                    {user.role}
                                </p>
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={logout}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all"
                        style={{ background: 'rgba(232,57,29,0.1)', color: '#E8391D', border: '1px solid rgba(232,57,29,0.2)' }}
                    >
                        <LogOut size={15} /> Déconnexion
                    </button>
                </div>
            </aside>

            <main className="flex-1 overflow-y-auto">
                <header
                    className="sticky top-0 px-7 py-4 flex justify-between items-center z-10 border-b"
                    style={{ background: 'rgba(245,245,245,0.85)', backdropFilter: 'blur(12px)', borderColor: '#E5E7EB' }}
                >
                    <div>
                        <h1 className="text-lg font-black tracking-tight" style={{ color: '#1A1A1A' }}>
                            {activeTab === 'today' ? '⚡ Clients attendus aujourd\'hui'
                                : activeTab === 'agenda' ? ' Agenda IA des visites'
                                    : '👥 Gestion du Portefeuille Clients'}
                        </h1>
                        <p className="text-xs mt-0.5" style={{ color: '#9CA3AF' }}>
                            Agence {user.agenceNom}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {(user.role === 'DIRECTEUR' || hasPermission('CAN_CREATE_ACCOUNT')) && (
                            <button
                                onClick={() => setIsCreateModalOpen(true)}
                                className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs shadow-sm transition-all text-white hover:bg-green-700 active:scale-95"
                                style={{ background: '#10B981' }}
                            >
                                <UserPlus size={14} /> Ajouter client
                            </button>
                        )}
                        <button
                            onClick={fetchAllData}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs border transition-all hover:shadow-sm"
                            style={{ background: 'white', borderColor: '#E5E7EB', color: '#1A1A1A' }}
                        >
                            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Actualiser
                        </button>
                    </div>
                </header>

                <div className="p-6">
                    <div className="relative mb-6 max-w-sm">
                        <input
                            type="text"
                            placeholder="Rechercher..."
                            className="w-full pl-10 pr-4 py-2.5 rounded-xl border bg-white outline-none text-sm transition-all"
                            style={{ borderColor: '#E5E7EB' }}
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2" size={15} style={{ color: '#9CA3AF' }} />
                    </div>

                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-28">
                            <Loader2 className="animate-spin mb-4" size={44} style={{ color: '#E8391D' }} />
                            <p className="font-black text-sm" style={{ color: '#1A1A1A' }}>Chargement...</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center py-24 text-center">
                            <AlertTriangle className="mb-3" size={48} style={{ color: '#FFC000' }} />
                            <p className="font-bold text-gray-700">{error}</p>
                        </div>
                    ) : activeTab === 'today' ? (
                        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                            {displayList.map(p => {
                                const showFull = user.role === 'PORTEFEUILLEUR' || user.role === 'DIRECTEUR' || hasPermission('CAN_ANALYZE_CLIENTS');
                                return showFull
                                    ? <PredictionCard key={p.id} prediction={p} onAction={p2 => { setSelectedPrediction(p2); setIsActionModalOpen(true); }} onEdit={c => { setSelectedClientForEdit(c); setIsEditModalOpen(true); }} highlight />
                                    : <ConseillerPredictionCard key={p.id} prediction={p} onAction={p2 => { setSelectedPrediction(p2); setIsActionModalOpen(true); }} onEdit={c => { setSelectedClientForEdit(c); setIsEditModalOpen(true); }} />
                            })}
                        </div>
                    ) : activeTab === 'agenda' ? (
                        <AgendaView predictions={displayList} onAction={p2 => { setSelectedPrediction(p2); setIsActionModalOpen(true); }} onEdit={c => { setSelectedClientForEdit(c); setIsEditModalOpen(true); }} />
                    ) : activeTab === 'portefeuille' ? (
                        <ClientTable
                            clientsFiltres={clientsPage.content}
                            chargement={clientsLoading}
                            pageActive={clientPageActive}
                            setPageActive={setClientPageActive}
                            totalPages={clientsPage.totalPages}
                            totalElements={clientsPage.totalElements}
                            onClientDeleted={fetchClients}
                            roleGlobal={user.role === 'DIRECTEUR'}
                            rolePortefeuilleur={user.role === 'PORTEFEUILLEUR' || user.role === 'DIRECTEUR' || hasPermission('CAN_ANALYZE_CLIENTS')}
                            canDelete={user.role === 'DIRECTEUR' || hasPermission('CAN_DELETE_ACCOUNT')}
                            canEdit={user.role === 'DIRECTEUR' || hasPermission('CAN_EDIT_CLIENT')}
                            canCreate={user.role === 'DIRECTEUR' || hasPermission('CAN_CREATE_ACCOUNT')}
                            onViewDetails={(c) => { setSelectedClientDetails(c); setIsClientDetailsModalOpen(true); }}
                            onEditClient={(c) => { setSelectedClientForEdit(c); setIsEditModalOpen(true); }}
                            onCreateClient={() => setIsCreateModalOpen(true)}
                        />
                    ) : null}

                </div>
            </main>

            <ActionModal
                isOpen={isActionModalOpen}
                onClose={() => setIsActionModalOpen(false)}
                client={selectedPrediction?.client || selectedPrediction}
                banquierId={user.id}
                onSuccess={fetchAllData}
            />

            <ClientDetailsModal
                isOpen={isClientDetailsModalOpen}
                onClose={() => { setIsClientDetailsModalOpen(false); setSelectedClientDetails(null); }}
                client={selectedClientDetails}
            />

            {isCreateModalOpen && (
                <CreateClientModal
                    isOpen={isCreateModalOpen}
                    onClose={() => setIsCreateModalOpen(false)}
                    onClientCreated={fetchAllData}
                />
            )}

            {isEditModalOpen && (
                <EditClientModal
                    isOpen={isEditModalOpen}
                    onClose={() => setIsEditModalOpen(false)}
                    client={selectedClientForEdit}
                    onClientUpdated={fetchAllData}
                />
            )}
        </div>
    );
};

export default DashboardConseiller;
