import React, { useState, useEffect } from 'react';
import api from '../api/axiosConfig';
import { 
    AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
    PieChart, Pie, Cell
} from 'recharts';
import { 
    LayoutDashboard, TrendingUp, ShieldCheck, 
    ArrowUpRight, ArrowDownRight, Briefcase, Activity,
    Download, Filter, ShieldAlert, Cpu, Users, Wallet, 
    Diamond, ChevronRight, LogOut, Globe, RefreshCcw, Bell,
    Shield, ToggleLeft, ToggleRight, UserCog
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import awbLogo from '../assets/react.jpeg';

// ── UTILS ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) => {
    return new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD', maximumFractionDigits: 0 }).format(val);
};

// ── PRESTIGE COMPONENTS ────────────────────────────────────────────────────

const ExecutiveBranding = () => (
    <div className="flex items-center gap-5 p-2 pr-6 bg-[#f1f5f9] rounded-full border border-slate-300 backdrop-blur-md shadow-[0_4px_24px_rgba(0,0,0,0.04)] relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-r from-[#E8391D]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <div className="relative">
            <img 
                src={awbLogo} 
                alt="AWB" 
                className="w-12 h-12 rounded-full border-2 border-slate-300 group-hover:border-[#E8391D]/50 transition-all duration-700 object-cover" 
            />
            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-[#FFC000] rounded-full border-2 border-[#111] animate-pulse" />
        </div>
        <div className="flex flex-col">
            <span className="text-slate-900 font-black text-xl tracking-tighter uppercase italic leading-none">Attijariwafa</span>
            <span className="text-[#FFC000] font-black text-[9px] tracking-[0.4em] uppercase opacity-70">Prestige Pilotage</span>
        </div>
    </div>
);

const ExecutiveKPI = ({ label, value, trend, isUp, icon: Icon, color = "#E8391D" }) => (
    <div className="relative group perspective-1000">
        <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent rounded-[32px] blur-2xl opacity-0 group-hover:opacity-100 transition-all duration-500" />
        
        <div className="relative bg-[#151515]/80 backdrop-blur-2xl border border-slate-200 p-8 rounded-[38px] transition-all duration-500 group-hover:-translate-y-2 group-hover:border-slate-300 shadow-[0_4px_24px_rgba(0,0,0,0.04)] overflow-hidden">
            {/* Ambient Background Diamond */}
            <div className="absolute -right-8 -top-8 w-32 h-32 rotate-45 bg-[#E8391D] opacity-[0.02] group-hover:opacity-[0.08] transition-opacity" />
            
            <div className="flex justify-between items-start mb-10">
                <div className="p-4 rounded-2xl bg-slate-100 border border-slate-200 text-slate-900/40 group-hover:text-slate-900 transition-colors shadow-inner" style={{color: isUp ? color : '#999'}}>
                    <Icon size={24} strokeWidth={2.5} />
                </div>
                <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black tracking-widest ${isUp ? 'text-emerald-400 bg-emerald-400/5' : 'text-[#E8391D] bg-[#E8391D]/5'}`}>
                    {isUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                    {trend}
                </div>
            </div>
            
            <div className="space-y-1">
                <p className="text-sm font-black text-slate-500 uppercase tracking-[0.2em]">{label}</p>
                <h3 className="text-4xl font-black text-slate-900 tracking-tighter italic">{value}</h3>
            </div>

            {/* Micro-sparkline Decorative SVG */}
            <div className="mt-8 h-8 w-full opacity-20 group-hover:opacity-40 transition-opacity">
                <svg width="100%" height="100%" viewBox="0 0 100 20" preserveAspectRatio="none">
                    <path 
                        d="M0 10 Q 25 5, 50 15 T 100 10" 
                        fill="none" 
                        stroke={color} 
                        strokeWidth="2" 
                        className="animate-pulse"
                    />
                </svg>
            </div>
        </div>
    </div>
);

const NavItem = ({ tab, icon: Icon, label, count, accent, activeTab, setActiveTab }) => (
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

export default function DashboardDirecteur() {
    const { user, logout } = useAuth();
    const [loading, setLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [chartsReady, setChartsReady] = useState(false);
    const [activeTab, setActiveTab] = useState('COCKPIT');
    
    const [page, setPage] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    
    const [clientsPage, setClientsPage] = useState(0);
    const [clientsTotalPages, setClientsTotalPages] = useState(0);
    const [agencyClients, setAgencyClients] = useState([]);

    const [stats, setStats] = useState({
        totalVentes: 0,
        caSimule: 0,
        tauxAdoption: 0,
        totalClients: 0,
        trends: {},
        conversionByAdvisor: [],
        distributionStatuts: [],
        recentActions: []
    });

    const [banquiers, setBanquiers] = useState([]);
    const [updatingPerms, setUpdatingPerms] = useState(null); // id du banquier en cours de maj

    const ALL_PERMISSIONS = [
        { key: 'CAN_CREATE_ACCOUNT',       label: 'Créer un client',          desc: 'Enregistrer un nouveau profil client' },
        { key: 'CAN_EDIT_CLIENT',          label: 'Modifier un client',         desc: 'Modifier les informations personnelles d’un client' },
        { key: 'CAN_DELETE_ACCOUNT',       label: 'Supprimer un client',        desc: 'Supprimer un client existant' },
        { key: 'CAN_CREATE_BANK_ACCOUNT',  label: 'Créer un compte',          desc: 'Ouvrir un nouveau compte bancaire' },
        { key: 'CAN_EDIT_BANK_ACCOUNT',    label: 'Modifier un compte',       desc: 'Modifier un compte bancaire existant' },
        { key: 'CAN_DELETE_BANK_ACCOUNT',  label: 'Supprimer un compte',      desc: 'Clôturer et supprimer un compte bancaire' },
        { key: 'CAN_ANALYZE_CLIENTS',      label: 'Analyser les clients (IA)',   desc: 'Accéder aux diagnostics de santé et stratégies IA' },
        { key: 'CAN_VIEW_ALL_PREDICTIONS', label: 'Voir tout le portefeuille',   desc: 'Consulter l’ensemble du portefeuille clients' },
    ];

    const fetchBanquiers = async () => {
        try {
            const agenceId = user?.agence?.id || 1;
            const res = await api.get(`/banquiers/agence/${agenceId}`);
            setBanquiers(res.data);
        } catch (err) { console.error('fetchBanquiers:', err); }
    };

    const togglePermission = async (banquier, permKey) => {
        const current = banquier.permissions || [];
        const newPerms = current.includes(permKey)
            ? current.filter(p => p !== permKey)
            : [...current, permKey];
        setUpdatingPerms(banquier.id);
        try {
            await api.put(`/banquiers/${banquier.id}/permissions`, { permissions: newPerms });
            setBanquiers(prev => prev.map(b =>
                b.id === banquier.id ? { ...b, permissions: newPerms } : b
            ));
        } catch (err) {
            console.error('Erreur mise à jour permissions:', err);
        } finally {
            setUpdatingPerms(null);
        }
    };

    const fetchStats = async () => {
        try {
            const agenceId = user?.agence?.id || 1;
            const res = await api.get(`/actions/stats/directeur/${agenceId}`);
            setStats(prev => ({ ...prev, ...res.data }));
        } catch (err) { console.error('fetchStats:', err); }
    };

    const fetchJournal = async (pageNum) => {
        try {
            const agenceId = user?.agence?.id || 1;
            const res = await api.get(`/actions/agence/${agenceId}/journal?page=${pageNum}&size=10`);
            setStats(prev => ({ ...prev, recentActions: res.data.content || [] }));
            setTotalPages(res.data.totalPages || 0);
            setPage(pageNum);
        } catch (err) { console.error('fetchJournal:', err); }
    };

    const fetchAgencyClients = async (pageNum) => {
        try {
            const agenceId = user?.agence?.id || 1;
            const res = await api.get(`/clients/agence/${agenceId}?page=${pageNum}&size=10`);
            setAgencyClients(res.data.content || []);
            setClientsTotalPages(res.data.totalPages || 0);
            setClientsPage(pageNum);
        } catch (err) { console.error('fetchAgencyClients:', err); }
    };

    const handleGlobalRefresh = async () => {
        setIsRefreshing(true);
        await Promise.all([fetchStats(), fetchJournal(page), fetchAgencyClients(clientsPage)]);
        setTimeout(() => setIsRefreshing(false), 800);
    };

    const handleExportCSV = () => {
        const dataToExport = activeTab === 'JOURNAL' ? stats.recentActions : agencyClients;
        if (!dataToExport || dataToExport.length === 0) return;
        let csvContent = "data:text/csv;charset=utf-8,";
        if (activeTab === 'JOURNAL') {
            csvContent += "Banquier,Client,Operation,Statut\n";
            dataToExport.forEach(row => csvContent += `${row.banquier.nomComplet},${row.client.nomComplet},${row.categorieAction},${row.statut}\n`);
        } else {
            csvContent += "Nom Complet,CIN,Segment,Risque\n";
            dataToExport.forEach(c => csvContent += `${c.nomComplet},${c.cin},${c.segmentMetier},${c.prediction?.niveauRisque}\n`);
        }
        const link = document.createElement("a");
        link.setAttribute("href", encodeURI(csvContent));
        link.setAttribute("download", `AWB_PILOTAGE_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const handlePageChange = (newP) => {
        if (activeTab === 'JOURNAL') {
            if (newP >= 0 && newP < totalPages) fetchJournal(newP);
        } else {
            if (newP >= 0 && newP < clientsTotalPages) fetchAgencyClients(newP);
        }
    };

    useEffect(() => {
        const init = async () => {
            setLoading(true);
            await Promise.all([fetchStats(), fetchJournal(0), fetchAgencyClients(0), fetchBanquiers()]);
            setLoading(false);
            setTimeout(() => setChartsReady(true), 300);
        };
        init();
    }, []);

    const COLORS = ['#E8391D', '#FFC000', '#262626', '#4F46E5', '#10B981'];

    if (loading) {
    


    return (
            <div className="min-h-screen bg-[#f8fafc] flex items-center justify-center overflow-hidden">
                <div className="relative w-32 h-32 flex items-center justify-center">
                    <div className="absolute inset-0 border-b-2 border-[#E8391D] rounded-full animate-spin duration-1000" />
                    <div className="absolute inset-4 border-t-2 border-[#FFC000] rounded-full animate-spin-reverse duration-700" />
                    <Diamond size={32} className="text-slate-900 animate-pulse" />
                </div>
            </div>
        );
    }




    return (

        <div className="flex h-screen overflow-hidden" style={{ background: '#F5F5F5', fontFamily: "'Inter', sans-serif" }}>
            
            {/* ── SIDEBAR ── */}
            <aside
                className="flex flex-col shadow-2xl flex-shrink-0"
                style={{ width: '270px', background: 'linear-gradient(185deg, #1A1A1A 0%, #2C1A14 60%, #1A0A04 100%)' }}
            >
                <div className="p-6 pb-4">
                    <div className="flex items-center gap-3 mb-8">
                        <img src={awbLogo} alt="AWB" className="w-10 h-10 rounded-xl object-contain bg-white p-0.5 shadow-lg" />
                        <div>
                            <p className="text-white font-black text-sm tracking-tight">AWB Front Office</p>
                            <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color: '#FFC000' }}>Cockpit Pilotage</p>
                        </div>
                    </div>

                    <nav className="space-y-1">
                        <NavItem tab="COCKPIT" icon={LayoutDashboard} label="Cockpit Pilotage" accent activeTab={activeTab} setActiveTab={setActiveTab} />
                        <NavItem tab="JOURNAL" icon={Activity} label="Flux d'activité" activeTab={activeTab} setActiveTab={setActiveTab} />
                        <NavItem tab="CLIENTS" icon={Users} label="Base Clients" count={agencyClients.length} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <NavItem tab="DROITS" icon={ShieldAlert} label="Gestion des Droits" activeTab={activeTab} setActiveTab={setActiveTab} />
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

            {/* ── MAIN CONTENT ── */}
            <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
                
                {/* Sticky Header */}
                <header
                    className="flex-shrink-0 px-8 py-5 flex justify-between items-center z-10 border-b shadow-sm"
                    style={{ background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(12px)', borderColor: '#E5E7EB' }}
                >
                    <div>
                        <h1 className="text-lg font-black tracking-tight" style={{ color: '#1A1A1A' }}>
                            {activeTab === 'COCKPIT' ? '📊 Cockpit Pilotage' 
                             : activeTab === 'JOURNAL' ? '📋 Flux d\'activité de l\'agence' 
                             : activeTab === 'CLIENTS' ? '👥 Base Clients Globale' 
                             : '🔐 Gestion des Droits et Habilitations'}
                        </h1>
                        <p className="text-xs mt-0.5" style={{ color: '#9CA3AF' }}>
                             Agence {user.agenceNom || 'Centrale'} — Supervision {user.nomComplet}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={handleExportCSV}
                            className="p-2.5 bg-white border border-slate-200 rounded-xl text-slate-500 hover:text-[#FFC000] hover:border-[#FFC000]/30 transition-all shadow-sm"
                            title="Exporter en CSV"
                        >
                            <Download size={16} />
                        </button>
                        <button
                            onClick={handleGlobalRefresh}
                            className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-xs border transition-all shadow-sm"
                            style={{ background: 'white', borderColor: '#E5E7EB', color: '#1A1A1A' }}
                        >
                            <RefreshCcw size={14} className={isRefreshing ? 'animate-spin text-[#E8391D]' : ''} /> 
                            {isRefreshing ? 'Actualisation...' : 'Actualiser'}
                        </button>
                    </div>
                </header>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-8 bg-[#F8FAFC]">
                    <div className="max-w-[1700px] mx-auto space-y-8 pb-10">
                        {activeTab === 'COCKPIT' && (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-10">
                                {/* ── KPI GRID ── */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                    <ExecutiveKPI 
                        label="Flux IA Global" 
                        value={formatCurrency(stats.caSimule)} 
                        trend={stats.trends?.caSimule?.value || "..."} 
                        isUp={stats.trends?.caSimule?.isUp ?? true} 
                        icon={Wallet} 
                        color="#FFC000" 
                    />
                    <ExecutiveKPI 
                        label="Indice de Captation" 
                        value={`${Math.round(stats.tauxAdoption)}%`} 
                        trend={stats.trends?.tauxAdoption?.value || "..."} 
                        isUp={stats.trends?.tauxAdoption?.isUp ?? true} 
                        icon={TrendingUp} 
                        color="#E8391D" 
                    />
                    <ExecutiveKPI 
                        label="Actifs Signés" 
                        value={stats.totalVentes} 
                        trend={stats.trends?.totalVentes?.value || "..."} 
                        isUp={stats.trends?.totalVentes?.isUp ?? true} 
                        icon={ShieldCheck} 
                        color="#10B981" 
                    />
                    <ExecutiveKPI 
                        label="Base Engagée" 
                        value={stats.totalClients} 
                        trend={stats.trends?.totalClients?.value || "Stable"} 
                        isUp={stats.trends?.totalClients?.isUp ?? true} 
                        icon={Users} 
                        color="#4F46E5" 
                    />
                </div>

                
                                {/* ── ANALYTICS CORE ── */}
                <div className="grid grid-cols-1 xl:grid-cols-12 gap-10">
                    
                    {/* Performance Canvas */}
                    <div className="xl:col-span-8 bg-white border border-slate-200 rounded-[48px] p-10 shadow-[0_4px_24px_rgba(0,0,0,0.04)] relative overflow-hidden group">
                        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-12">
                            <div className="flex items-center gap-5">
                                <div className="w-2 h-12 bg-gradient-to-b from-[#FFC000] via-[#06b6d4] to-transparent rounded-full" />
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 uppercase tracking-widest italic">Baromètre de Force</h3>
                                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mt-1">Productivité Réelle : Conseillers vs Portefeuilleurs</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-6 bg-slate-50 px-5 py-2.5 rounded-2xl border border-slate-200">
                                <div className="flex items-center gap-3">
                                    <div className="w-2.5 h-2.5 rounded-full bg-[#06b6d4] shadow-sm" />
                                    <span className="text-[10px] font-black text-slate-700 uppercase tracking-widest">Conseiller</span>
                                </div>
                                <div className="w-px h-4 bg-slate-300" />
                                <div className="flex items-center gap-3">
                                    <div className="w-2.5 h-2.5 rounded-full bg-[#FFC000] shadow-sm" />
                                    <span className="text-[10px] font-black text-slate-700 uppercase tracking-widest">Portefeuilleur</span>
                                </div>
                            </div>
                        </div>

                        <div className="h-[400px] w-full">
                            {chartsReady && stats.conversionByAdvisor?.length > 0 && (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={stats.conversionByAdvisor} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="colorConseiller" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.9}/>
                                                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.2}/>
                                            </linearGradient>
                                            <linearGradient id="colorPortefeuilleur" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#FFC000" stopOpacity={0.9}/>
                                                <stop offset="95%" stopColor="#FFC000" stopOpacity={0.2}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10, fontWeight: '900'}} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10, fontWeight: '900'}} />
                                        <Tooltip 
                                            cursor={{fill: '#f1f5f9'}}
                                            content={({ active, payload, label }) => {
                                                if (active && payload && payload.length) {
                                                    const item = payload[0].payload;
                                                    const isPortefeuilleur = item.role === 'PORTEFEUILLEUR';
                                                


    return (
                                                        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-lg backdrop-blur-xl">
                                                            <p className="text-slate-900 font-black text-sm">{label}</p>
                                                            <div className="flex items-center gap-2 mt-2 mb-3">
                                                                <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md" style={{backgroundColor: isPortefeuilleur ? '#FFC00020' : '#06b6d420', color: isPortefeuilleur ? '#FFC000' : '#06b6d4'}}>
                                                                    {item.role || 'CONSEILLER'}
                                                                </span>
                                                            </div>
                                                            <div className="space-y-1">
                                                                <div className="flex items-end justify-between gap-6">
                                                                    <span className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Actions Enregistrées</span>
                                                                    <span className="text-xl font-black italic" style={{color: isPortefeuilleur ? '#FFC000' : '#06b6d4'}}>{item.ventes}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                }
                                                return null;
                                            }}
                                        />
                                        <Bar dataKey="ventes" radius={[8, 8, 0, 0]} maxBarSize={60}>
                                            {stats.conversionByAdvisor.map((entry, index) => (
                                                <Cell 
                                                    key={`cell-${index}`} 
                                                    fill={entry.role === 'PORTEFEUILLEUR' ? 'url(#colorPortefeuilleur)' : 'url(#colorConseiller)'} 
                                                />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </div>

                    {/* Arbitrage Mix */}
                    <div className="xl:col-span-4 bg-white border border-slate-200 rounded-[48px] p-10 flex flex-col items-center shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
                        <h3 className="text-xl font-black text-slate-900 uppercase tracking-widest text-center italic mb-10">Mix Arbitrage</h3>
                        
                        <div className="h-[300px] w-full relative mb-10">
                            {chartsReady && stats.distributionStatuts?.length > 0 && (
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={stats.distributionStatuts}
                                            innerRadius={80}
                                            outerRadius={110}
                                            paddingAngle={8}
                                            dataKey="value"
                                        >
                                            {stats.distributionStatuts.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{backgroundColor: '#000', border: 'none', borderRadius: '12px'}} />
                                    </PieChart>
                                </ResponsiveContainer>
                            )}
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
                                <Diamond size={24} className="text-[#FFC000] rotate-45 mb-2 mx-auto" />
                                <span className="text-[10px] font-black text-slate-900 uppercase tracking-[0.3em]">IA Hub</span>
                            </div>
                        </div>

                        <div className="w-full space-y-3">
                            {stats.distributionStatuts.map((item, idx) => (
                                <div key={idx} className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-2xl hover:bg-white/[0.05] transition-colors group">
                                    <div className="flex items-center gap-3">
                                        <div className="w-2 h-2 rounded-full" style={{backgroundColor: COLORS[idx % COLORS.length]}} />
                                        <span className="text-[10px] font-black uppercase text-slate-500 group-hover:text-slate-900 transition-colors">{item.name}</span>
                                    </div>
                                    <span className="text-xs font-black text-slate-900">{item.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                
                            </div>
                        )}
                        
                        {activeTab === 'JOURNAL' && (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="bg-white border border-slate-200 rounded-3xl shadow-sm overflow-hidden">
                                    <div className="overflow-x-auto min-h-[500px]">
                                        <table className="w-full text-left">
                                <thead className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-600 bg-slate-50">
                                    <tr>
                                        <th className="px-10 py-6">Banquier</th>
                                        <th className="px-10 py-6">Client Cible</th>
                                        <th className="px-10 py-6">Arbitrage</th>
                                        <th className="px-10 py-6">Validation</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                    {stats.recentActions.map((row) => (
                                        <tr key={row.id} className="hover:bg-white transition-colors group">
                                            <td className="px-10 py-8">
                                                <div className="flex items-center gap-4">
                                                    <div className="w-10 h-10 bg-[#FFC000]/10 border border-[#FFC000]/20 rounded-xl flex items-center justify-center text-[#FFC000] font-black text-sm">
                                                        {row.banquier.nomComplet.charAt(0)}
                                                    </div>
                                                    <span className="text-sm font-black text-slate-900 italic">{row.banquier.nomComplet}</span>
                                                </div>
                                            </td>
                                            <td className="px-10 py-8 text-sm font-black text-slate-600">
                                                <span className="text-slate-900 group-hover:text-[#FFC000] transition-colors">{row.client.nomComplet}</span>
                                                <p className="text-[9px] font-bold text-slate-600 mt-1 uppercase tracking-widest">{row.client.cin}</p>
                                            </td>
                                            <td className="px-10 py-8">
                                                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-lg text-[10px] font-black text-slate-500 uppercase tracking-widest">
                                                    <Briefcase size={12} /> {row.categorieAction}
                                                </div>
                                            </td>
                                            <td className="px-10 py-8">
                                                <div className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border ${
                                                    row.statut === 'VENDU' ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' :
                                                    row.statut === 'DELEGUE_COMMERCIAL' ? 'bg-[#FFC000]/5 border-[#FFC000]/20 text-[#FFC000]' :
                                                    'bg-[#E8391D]/5 border-[#E8391D]/20 text-[#E8391D]'
                                                }`}>
                                                    <Activity size={12} /> {
                                                        row.statut === 'VENDU' ? 'SIGNÉ' : 
                                                        row.statut === 'DELEGUE_COMMERCIAL' ? 'DÉLÉGUÉ' : 'NON CONCLU'
                                                    }
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                                    </div>
                                    {/* 🧭 NAVIGATION COCKPIT */}
                    <div className="p-10 bg-slate-100 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-6">
                        <div className="flex flex-col gap-1">
                            <p className="text-[10px] font-black uppercase text-slate-600 tracking-[0.6em] italic">
                                Page <span className="text-slate-900">{(activeTab === 'JOURNAL' ? page : clientsPage) + 1}</span> / {(activeTab === 'JOURNAL' ? totalPages : clientsTotalPages) || 1}
                            </p>
                            <div className="h-0.5 w-8 bg-[#E8391D] rounded-full" />
                        </div>

                        <div className="flex items-center gap-2">
                            <button 
                                onClick={() => handlePageChange((activeTab === 'JOURNAL' ? page : clientsPage) - 1)}
                                disabled={(activeTab === 'JOURNAL' ? page : clientsPage) === 0}
                                className="p-3 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-900 disabled:opacity-20 transition-all"
                            >
                                <ChevronRight size={18} className="rotate-180" />
                            </button>
                            <button 
                                onClick={() => handlePageChange((activeTab === 'JOURNAL' ? page : clientsPage) + 1)}
                                disabled={(activeTab === 'JOURNAL' ? page : clientsPage) >= (activeTab === 'JOURNAL' ? totalPages : clientsTotalPages) - 1}
                                className="p-3 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-900 disabled:opacity-20 transition-all"
                            >
                                <ChevronRight size={18} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        )}

                        {activeTab === 'CLIENTS' && (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="bg-white border border-slate-200 rounded-3xl shadow-sm overflow-hidden">
                                    <div className="overflow-x-auto min-h-[500px]">
                                        <table className="w-full text-left">
                                        <thead className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-600 bg-slate-50">
                                            <tr>
                                                <th className="px-10 py-6">Titulaire</th>
                                                <th className="px-10 py-6">Contact & Identification</th>
                                                <th className="px-10 py-6">Comptes (RIB)</th>
                                                <th className="px-10 py-6">Classification</th>
                                                <th className="px-10 py-6">Niveau de Risque</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-200">
                                            {agencyClients.map((client) => (
                                                <tr key={client.id} className="hover:bg-white transition-colors">
                                                    <td className="px-10 py-8 text-sm font-black text-slate-900 italic">{client.nomComplet}</td>
                                                    <td className="px-10 py-8">
                                                        <p className="text-xs font-black text-slate-600 tracking-widest uppercase">{client.cin}</p>
                                                        <div className="flex flex-col gap-1 mt-1">
                                                            {client.email && <span className="text-[9px] text-slate-600 lowercase">{client.email}</span>}
                                                            {client.telephone && <span className="text-[9px] text-[#E8391D]/70 font-mono">{client.telephone}</span>}
                                                        </div>
                                                    </td>
                                                    <td className="px-10 py-8">
                                                        {client.comptes && client.comptes.length > 0 ? (
                                                            <div className="flex flex-col gap-1.5">
                                                                {client.comptes.map(compte => (
                                                                    <span key={compte.id} className="text-[10px] font-mono font-bold text-gray-500 bg-gray-100 px-2 py-1 rounded border border-gray-200 w-max">
                                                                        {compte.numeroCompte}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <span className="text-[10px] text-gray-400 italic">Aucun compte</span>
                                                        )}
                                                    </td>
                                            <td className="px-10 py-8">
                                                <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full">
                                                    {client.segmentMetier || 'FIRST BUSINESS'}
                                                </span>
                                            </td>
                                            <td className="px-10 py-8">
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-2.5 h-2.5 rounded-full ${
                                                        client.prediction?.niveauRisque === 'CRITIQUE' ? 'bg-[#E8391D] shadow-[0_0_10px_#E8391D]' :
                                                        client.prediction?.niveauRisque === 'ALERTE' ? 'bg-[#FFC000] shadow-[0_0_10px_#FFC000]' :
                                                        'bg-emerald-500 shadow-[0_0_10px_#10B981]'
                                                    }`} />
                                                    <span className={`text-[10px] font-black uppercase tracking-widest italic ${
                                                        client.prediction?.niveauRisque === 'CRITIQUE' ? 'text-[#E8391D]' :
                                                        client.prediction?.niveauRisque === 'ALERTE' ? 'text-[#FFC000]' :
                                                        'text-emerald-500'
                                                    }`}>
                                                        {client.prediction?.niveauRisque === 'SOUS SURVEILLANCE' ? 'SURVEILLANCE' : (client.prediction?.niveauRisque || 'REGULIER')}
                                                    </span>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                                    </div>
                                    {/* 🧭 NAVIGATION COCKPIT */}
                    <div className="p-10 bg-slate-100 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-6">
                        <div className="flex flex-col gap-1">
                            <p className="text-[10px] font-black uppercase text-slate-600 tracking-[0.6em] italic">
                                Page <span className="text-slate-900">{(activeTab === 'JOURNAL' ? page : clientsPage) + 1}</span> / {(activeTab === 'JOURNAL' ? totalPages : clientsTotalPages) || 1}
                            </p>
                            <div className="h-0.5 w-8 bg-[#E8391D] rounded-full" />
                        </div>

                        <div className="flex items-center gap-2">
                            <button 
                                onClick={() => handlePageChange((activeTab === 'JOURNAL' ? page : clientsPage) - 1)}
                                disabled={(activeTab === 'JOURNAL' ? page : clientsPage) === 0}
                                className="p-3 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-900 disabled:opacity-20 transition-all"
                            >
                                <ChevronRight size={18} className="rotate-180" />
                            </button>
                            <button 
                                onClick={() => handlePageChange((activeTab === 'JOURNAL' ? page : clientsPage) + 1)}
                                disabled={(activeTab === 'JOURNAL' ? page : clientsPage) >= (activeTab === 'JOURNAL' ? totalPages : clientsTotalPages) - 1}
                                className="p-3 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-900 disabled:opacity-20 transition-all"
                            >
                                <ChevronRight size={18} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        )}

                        {activeTab === 'DROITS' && (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="bg-white border border-slate-200 rounded-3xl shadow-sm overflow-hidden">
                                    {/* ── GESTION DES DROITS ───────────────────────────────── */}
                            <div className="p-10 space-y-6">
                                <div className="flex items-center gap-4 mb-8">
                                    <div className="p-3 bg-[#FFC000]/10 rounded-2xl">
                                        <UserCog size={24} className="text-[#FFC000]" />
                                    </div>
                                    <div>
                                        <h3 className="text-xl font-black text-slate-900 uppercase tracking-widest italic">Gestion des Droits</h3>
                                        <p className="text-xs text-slate-500 mt-1">Accordez des permissions supplémentaires à vos collaborateurs</p>
                                    </div>
                                </div>

                                {banquiers.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                                        <Users size={48} className="mb-4 opacity-30" />
                                        <p className="font-bold">Aucun banquier trouvé</p>
                                    </div>
                                ) : banquiers.map(banquier => (
                                    <div key={banquier.id} className="bg-white border border-slate-200 rounded-[32px] p-8 shadow-sm hover:shadow-md transition-all">
                                        {/* En-tête banquier */}
                                        <div className="flex items-center gap-5 mb-6">
                                            <div className="w-14 h-14 rounded-2xl flex items-center justify-center font-black text-xl text-white flex-shrink-0"
                                                style={{ background: banquier.role === 'PORTEFEUILLEUR' ? 'linear-gradient(135deg,#FFC000,#E8391D)' : 'linear-gradient(135deg,#1A1A1A,#3A3A3A)' }}>
                                                {banquier.nomComplet?.charAt(0)}
                                            </div>
                                            <div className="flex-1">
                                                <p className="font-black text-slate-900 text-lg italic">{banquier.nomComplet}</p>
                                                <div className="flex items-center gap-3 mt-1">
                                                    <span className="text-[9px] font-black uppercase tracking-[0.3em] px-3 py-1 rounded-full"
                                                        style={{ background: banquier.role === 'PORTEFEUILLEUR' ? '#FFF7E6' : '#F1F5F9', color: banquier.role === 'PORTEFEUILLEUR' ? '#B45309' : '#475569' }}>
                                                        {banquier.role}
                                                    </span>
                                                    <span className="text-xs text-slate-400">{banquier.email}</span>
                                                </div>
                                            </div>
                                            {updatingPerms === banquier.id && (
                                                <div className="w-5 h-5 border-2 border-[#FFC000] border-t-transparent rounded-full animate-spin" />
                                            )}
                                        </div>

                                        {/* Grille de permissions */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                            {ALL_PERMISSIONS.map(perm => {
                                                const active = (banquier.permissions || []).includes(perm.key);
                                            


    return (
                                                    <button
                                                        key={perm.key}
                                                        onClick={() => togglePermission(banquier, perm.key)}
                                                        disabled={updatingPerms === banquier.id}
                                                        className={`flex items-start gap-3 p-4 rounded-2xl border-2 text-left transition-all duration-200 ${
                                                            active
                                                                ? 'border-[#FFC000] bg-[#FFF7E6]'
                                                                : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                                                        }`}
                                                    >
                                                        <div className={`mt-0.5 flex-shrink-0 transition-colors ${
                                                            active ? 'text-[#FFC000]' : 'text-slate-300'
                                                        }`}>
                                                            {active 
                                                                ? <ToggleRight size={22} strokeWidth={2.5} />
                                                                : <ToggleLeft size={22} strokeWidth={2.5} />
                                                            }
                                                        </div>
                                                        <div>
                                                            <p className={`text-xs font-black uppercase tracking-wider ${
                                                                active ? 'text-[#B45309]' : 'text-slate-500'
                                                            }`}>{perm.label}</p>
                                                            <p className="text-[10px] text-slate-400 mt-0.5 leading-snug">{perm.desc}</p>
                                                        </div>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
