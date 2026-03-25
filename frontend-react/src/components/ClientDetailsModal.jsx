import React, { useState, useEffect } from 'react';
import { X, User, CreditCard, BrainCircuit, CalendarClock, Target, AlertTriangle, Trash2, History, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import axios from 'axios';

export default function ClientDetailsModal({ isOpen, onClose, client }) {
  const [historique, setHistorique] = useState([]);
  const [loadingHistorique, setLoadingHistorique] = useState(false);

  useEffect(() => {
    if (isOpen && client?.id) {
      setLoadingHistorique(true);
      axios.get(`http://localhost:8080/api/v1/operations/client/${client.id}`)
        .then(response => {
          const ops = response.data || [];
          ops.sort((a, b) => new Date(b.dateHeureOperation) - new Date(a.dateHeureOperation));
          setHistorique(ops.slice(0, 10));
          setLoadingHistorique(false);
        })
        .catch(err => {
          console.error("Erreur chargement historique:", err);
          setLoadingHistorique(false);
        });
    }
  }, [isOpen, client]);

  if (!isOpen || !client) return null;

  // ==========================================
  // FONCTION DE SUPPRESSION D'UN COMPTE
  // ==========================================
  const handleSupprimerCompte = async (compteId, numeroCompte) => {
    const confirmation = window.confirm(
      `⚠️ ATTENTION\n\nSouhaitez-vous vraiment supprimer le compte n° ${numeroCompte} ?\nCette action est irréversible.`
    );

    if (confirmation) {
      try {
        // Remplace l'URL par ton endpoint Spring Boot exact
        await axios.delete(`http://localhost:8080/api/v1/comptes/${compteId}`);
        alert("✅ Compte supprimé avec succès.");

        // On ferme le modal pour forcer le rafraîchissement de la liste parente
        onClose();
      } catch (err) {
        console.error("Erreur lors de la suppression du compte:", err);
        alert("❌ Erreur : Impossible de supprimer ce compte. Vérifiez les dépendances (transactions) dans la base de données.");
      }
    }
  };

  // Calcul du solde total du client
  const soldeTotal = client.comptes
    ? client.comptes.reduce((somme, compte) => somme + compte.solde, 0)
    : 0;

  // Formatage des données de l'IA
  const hasPrediction = !!client.prediction;
  // Le score XGBoost est entre 0 et 1 (predict_proba). On le convertit en pourcentage.
  // Si le score est > 1, c'est déjà en pourcentage (ancien format).
  const rawScore = hasPrediction ? client.prediction.scoreProbabiliteGlobal : 0;
  const score = rawScore <= 1 ? Math.round(rawScore * 100) : Math.round(rawScore);

  // Couleurs dynamiques pour la jauge
  let scoreColor = "bg-gray-200";
  let textColor = "text-gray-500";
  if (score >= 80) { scoreColor = "bg-green-500"; textColor = "text-green-600"; }
  else if (score >= 50) { scoreColor = "bg-orange-500"; textColor = "text-orange-600"; }
  else if (score > 0) { scoreColor = "bg-red-500"; textColor = "text-red-600"; }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-center items-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">

        {/* HEADER */}
        <div className="bg-[#E74C3C] p-6 text-white flex justify-between items-center shrink-0">
          <div className="flex items-center gap-4">
            <div className="bg-white/20 p-3 rounded-full shadow-inner">
              <User size={32} />
            </div>
            <div>
              <h2 className="text-2xl font-bold tracking-wide">{client.nomComplet}</h2>
              <p className="text-white/80 text-sm font-medium mt-1">
                CIN: {client.cin} • Segment: {client.segmentMetier}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="hover:bg-white/20 p-2 rounded-full transition-colors">
            <X size={24} />
          </button>
        </div>

        {/* CORPS DE LA FICHE */}
        <div className="p-6 overflow-y-auto flex-1 bg-gray-50 flex flex-col gap-6">

          <div className="flex flex-col md:flex-row gap-6">
            {/* COLONNE GAUCHE : COMPTES */}
            <div className="flex-1 space-y-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <CreditCard className="text-[#E74C3C]" size={20} />
                Portefeuille de Comptes
              </h3>

              {client.comptes && client.comptes.length > 0 ? (
                <div className="space-y-3">
                  {client.comptes.map(compte => (
                    <div key={compte.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-100 hover:border-[#E74C3C]/30 transition-all group">
                      <div className="flex items-center gap-3">
                        {/* BOUTON SUPPRIMER LE COMPTE */}
                        <button
                          onClick={() => handleSupprimerCompte(compte.id, compte.numeroCompte)}
                          className="text-gray-300 hover:text-red-500 transition-colors p-1.5 hover:bg-red-50 rounded-md"
                          title="Supprimer ce compte"
                        >
                          <Trash2 size={18} />
                        </button>

                        <div>
                          <p className="font-mono text-sm font-bold text-gray-700">{compte.numeroCompte}</p>
                          <p className="text-xs text-gray-500 mt-0.5">{compte.typeCompte}</p>
                        </div>
                      </div>
                      <span className={`font-bold ${compte.solde < 0 ? 'text-red-600 bg-red-50 px-2 py-1 rounded' : 'text-green-600'}`}>
                        {new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD' }).format(compte.solde)}
                      </span>
                    </div>
                  ))}

                  <div className="mt-5 pt-4 border-t border-gray-200 flex justify-between items-center">
                    <span className="font-bold text-gray-600 uppercase text-sm tracking-wider">Solde Global Consolidé</span>
                    <span className={`text-xl font-black ${soldeTotal < 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD' }).format(soldeTotal)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                  <p className="text-gray-500 italic text-sm">Ce profil n'a aucun compte rattaché.</p>
                </div>
              )}
            </div>
          </div>

          {/* COLONNE DROITE : IA XGBOOST */}
          <div className="flex-1">
            <div className="bg-gradient-to-br from-[#FFF8F5] to-white p-6 rounded-xl border border-[#E74C3C]/20 shadow-sm h-full relative overflow-hidden flex flex-col">
              <BrainCircuit className="absolute -right-6 -bottom-6 text-[#E74C3C]/5" size={180} />

              <h3 className="text-xl font-black text-gray-800 mb-6 flex items-center gap-2 relative z-10">
                <BrainCircuit className="text-[#E74C3C]" size={24} />
                Diagnostic IA (XGBoost)
              </h3>

              {hasPrediction ? (
                <div className="space-y-6 relative z-10 flex-1 flex flex-col">

                  {/* Opération prévue */}
                  <div className="bg-white p-4 rounded-lg border border-[#E74C3C]/10 shadow-sm">
                    <div className="text-sm text-gray-500 mb-2 flex items-center gap-1.5 font-medium">
                      <Target size={16} className="text-[#E74C3C]" /> Motif probable de la visite
                    </div>
                    <div className="text-lg font-bold text-[#E74C3C] bg-[#FFF0E6] inline-block px-4 py-1.5 rounded-md border border-[#E74C3C]/20">
                      {client.prediction.operationPrevue}
                    </div>
                  </div>

                  {/* Dates */}
                  <div className="bg-white p-4 rounded-lg border border-gray-100 shadow-sm flex gap-4">
                    <div className="flex-1">
                      <div className="text-sm text-gray-500 mb-1 font-medium">Date ciblée</div>
                      <div className="font-bold text-gray-800">
                        {new Date(client.prediction.datePrevue).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}
                      </div>
                    </div>
                    <div className="w-px bg-gray-100"></div>
                    <div className="flex-1">
                      <div className="text-sm text-gray-500 mb-1 font-medium">Plage horaire</div>
                      <div className="font-bold text-gray-800">{client.prediction.plageHorairePrevue}</div>
                    </div>
                  </div>

                  {/* Certitude */}
                  <div className="mt-auto pt-4">
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-sm font-bold text-gray-700 uppercase tracking-wider">Confiance IA</span>
                      <span className={`text-3xl font-black ${textColor}`}>{score}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden shadow-inner">
                      <div className={`h-full ${scoreColor} transition-all duration-1000`} style={{ width: `${score}%` }}></div>
                    </div>
                  </div>

                </div>
              ) : (
                <div className="flex flex-col items-center justify-center flex-1 text-center relative z-10 opacity-70">
                  <AlertTriangle className="text-orange-400 mb-4" size={48} />
                  <p className="font-bold text-gray-700">Aucune analyse disponible</p>
                </div>
              )}
            </div>
          </div>
        </div>
          {/* NOUVELLE SECTION : HORIZONTAL POUR HISTORIQUE RECENT */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm mt-2">
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <History className="text-[#E74C3C]" size={20} />
              Historique Récent (10 dernières opérations)
            </h3>
            {loadingHistorique ? (
              <div className="text-center py-6 text-gray-500 italic text-sm animate-pulse font-medium">
                Chargement de l'historique...
              </div>
            ) : historique.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-gray-100">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100 text-gray-600 uppercase text-xs tracking-wider font-semibold">
                      <th className="p-3 pl-4">Date & Heure</th>
                      <th className="p-3">Type Statistique</th>
                      <th className="p-3 text-right pr-4">Montant MAD</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {historique.map((op, index) => {
                      const estDebit = op.typeOperation.includes('RETRAIT') || op.typeOperation.includes('PAIEMENT') || op.typeOperation.includes('VIREMENT_EMIS');
                      return (
                        <tr key={index} className="hover:bg-gray-50/50 transition-colors">
                          <td className="p-3 pl-4 text-gray-600 font-medium">
                            {new Date(op.dateHeureOperation).toLocaleString('fr-FR', {
                              day: '2-digit', month: '2-digit', year: 'numeric',
                              hour: '2-digit', minute: '2-digit'
                            })}
                          </td>
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              {estDebit ? (
                                <ArrowUpRight size={16} className="text-red-500" />
                              ) : (
                                <ArrowDownRight size={16} className="text-green-500" />
                              )}
                              <span className="font-bold text-gray-800">{op.typeOperation.replace(/_/g, ' ')}</span>
                            </div>
                          </td>
                          <td className="p-3 text-right pr-4">
                            <span className={`font-bold ${estDebit ? 'text-red-600' : 'text-green-600'}`}>
                              {estDebit ? '-' : '+'}{new Intl.NumberFormat('fr-MA', { style: 'decimal', minimumFractionDigits: 2 }).format(op.montant)} MAD
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-6 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                <p className="text-gray-500 italic text-sm">Aucune opération trouvée pour ce client.</p>
              </div>
            )}
          </div>
        </div>

        {/* FOOTER */}
        <div className="bg-gray-50 border-t border-gray-100 p-4 flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold rounded-lg transition-colors shadow-sm"
          >
            Fermer le dossier
          </button>
        </div>
      </div>
    </div>
  );
}