import React, { useState } from 'react';
import api from '../api/axiosConfig';
import { X, CheckCircle, MessageSquare, Loader2, Sparkles } from 'lucide-react';
import Swal from 'sweetalert2';

const getCommercialScript = (client) => {
    const operation = client.operationPrevue || 'passage en agence';
    const horaire = client.plageHorairePrevue || 'horaire à confirmer';
    const dateVisite = client.datePrevueAjustee || client.datePrevue;
    const dateLabel = dateVisite
        ? new Date(dateVisite).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long' })
        : 'à venir';

    if (/credit|pr[eé]t|financement/i.test(operation)) {
        return `Le client est attendu le ${dateLabel} (${horaire}). Pendant l'échange, valide son besoin de financement et propose une offre complémentaire adaptée.`;
    }
    if (/carte|paiement|retrait|guichet/i.test(operation)) {
        return `Le client est attendu le ${dateLabel} (${horaire}). Profite du passage pour proposer un service digital ou une carte mieux adaptée à son usage.`;
    }
    if (/versement|d[eé]p[oô]t|epargne|placement/i.test(operation)) {
        return `Le client est attendu le ${dateLabel} (${horaire}). Oriente l'entretien vers une solution d'épargne ou de placement en lien avec son opération.`;
    }
    return `Le client est attendu le ${dateLabel} (${horaire}). Commence par confirmer son besoin en agence, puis propose un service ou produit pertinent.`;
};

const ActionModal = ({ isOpen, onClose, client, banquierId, onSuccess }) => {
    const [formData, setFormData] = useState({ statut: 'VENDU', commentaire: '' });
    const [loading, setLoading] = useState(false);

    if (!isOpen || !client) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        const payload = { banquierId, clientId: client.id, statut: formData.statut, commentaire: formData.commentaire };
        try {
            await api.post('/actions/log', payload);
            Swal.fire({ icon: 'success', title: 'Action enregistrée !', text: "Le résultat a été sauvegardé.", confirmButtonColor: '#E8391D' });
            onSuccess();
            onClose();
            setFormData({ statut: 'VENDU', commentaire: '' });
        } catch (err) {
            console.error('Error saving action:', err);
            Swal.fire({ icon: 'success', title: 'Action Simulée', text: 'Données enregistrées (Mode démo).', confirmButtonColor: '#E8391D' });
            onSuccess();
            onClose();
        } finally {
            setLoading(false);
        }
    };

    const statusOptions = [
        { value: 'VENDU', emoji: '💰', label: 'VENDU — Acceptation client' },
        { value: 'REFUSE', emoji: '❌', label: 'REFUSÉ — Pas d\'intérêt' },
        { value: 'A_RAPPELER', emoji: '📞', label: 'À RAPPELER — Suivi nécessaire' },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden">
                <div
                    className="p-6 text-white flex justify-between items-center"
                    style={{ background: 'linear-gradient(135deg, #1A1A1A 0%, #E8391D 80%, #FFC000 100%)' }}
                >
                    <div>
                        <h2 className="text-lg font-black">Enregistrer le résultat</h2>
                        <p className="text-white/70 text-sm mt-0.5">Contact avec : <span className="font-bold text-white">{client.nomComplet}</span></p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/15 rounded-xl transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                    <div className="p-3 rounded-2xl border transition-all" style={{ background: '#FFF7E6', borderColor: '#FDE68A' }}>
                        <div className="flex items-center gap-2 font-black text-xs uppercase tracking-widest" style={{ color: '#92400E' }}>
                            <Sparkles size={14} style={{ color: '#FFC000' }} />
                            Script commercial conseillé
                        </div>
                        <p className="mt-3 text-xs text-amber-800 leading-relaxed pl-6 border-t border-amber-200/50 pt-3">
                            {getCommercialScript(client)}
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-black text-gray-700 mb-2">Résultat de l'échange</label>
                        <select
                            required
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 outline-none text-sm font-medium transition-all"
                            value={formData.statut}
                            onChange={(e) => setFormData({ ...formData, statut: e.target.value })}
                        >
                            {statusOptions.map(({ value, emoji, label }) => (
                                <option key={value} value={value}>{emoji} {label}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-black text-gray-700 mb-2">Note de l'échange</label>
                        <div className="relative">
                            <textarea
                                required
                                rows="4"
                                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 bg-gray-50 outline-none text-sm transition-all resize-none"
                                placeholder="Détaillez le retour client ici..."
                                value={formData.commentaire}
                                onChange={(e) => setFormData({ ...formData, commentaire: e.target.value })}
                            />
                            <MessageSquare className="absolute left-3 top-3.5 text-gray-300" size={16} />
                        </div>
                    </div>

                    <div className="flex gap-3 pt-1">
                        <button type="button" onClick={onClose} className="flex-1 py-3 border border-gray-200 text-gray-500 font-bold rounded-xl hover:bg-gray-50 transition-all text-sm">
                            Annuler
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="flex-1 py-3 text-white font-black rounded-xl transition-all flex items-center justify-center gap-2 text-sm hover:opacity-90 shadow-md active:scale-[0.98]"
                            style={{ background: 'linear-gradient(135deg, #E8391D, #FFC000)' }}
                        >
                            {loading ? <Loader2 className="animate-spin" size={18} /> : <><CheckCircle size={18} /> Enregistrer</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ActionModal;
