import React, { useState } from 'react'
import { Calendar, Filter, ChevronLeft, ChevronRight, Trash2, Sparkles } from 'lucide-react'
import axios from 'axios'

export default function ClientTable({
  clientsFiltres, chargement, erreur,
  pageActive, setPageActive, totalPages, totalElements,
  onClientDeleted,
  onViewDetails
}) {

  // NOUVEAU : État pour savoir quelle ligne d'explication IA est ouverte
  const [clientExplicationOuverte, setClientExplicationOuverte] = useState(null);

  const toggleExplication = (clientId) => {
    setClientExplicationOuverte(prev => prev === clientId ? null : clientId);
  };

  const handleSupprimer = (id, nom) => {
    const confirmation = window.confirm(`Êtes-vous sûr de vouloir supprimer le client ${nom} ainsi que tous ses comptes bancaires ? Cette action est irréversible.`);

    if (confirmation) {
      axios.delete(`http://localhost:8080/api/v1/clients/${id}`)
        .then(() => {
          alert("Client supprimé avec succès !");
          onClientDeleted();
        })
        .catch(err => {
          console.error(err);
          alert("Erreur lors de la suppression. Le client est peut-être lié à d'autres données.");
        });
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-[#E74C3C]/10 overflow-hidden">
      {chargement ? (
        <div className="p-12 text-center text-gray-400 animate-pulse flex flex-col items-center justify-center gap-3">
          <Calendar className="text-[#E74C3C]/50" size={40} />
          <span className="font-medium">Chargement des données bancaires...</span>
        </div>
      ) : erreur ? (
        <div className="p-12 text-center text-[#E74C3C] font-bold bg-[#FFF0E6]">{erreur}</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse whitespace-nowrap">
              <thead>
                <tr className="bg-[#FFF8F5] border-b border-[#E74C3C]/10 text-gray-700 uppercase text-xs tracking-wider font-semibold">
                  <th className="p-4">CIN</th>
                  <th className="p-4">Client</th>
                  <th className="p-4">Comptes (RIB)</th>
                  <th className="p-4">Prochaine Visite</th>
                  <th className="p-4">Opération Prévue</th>
                  <th className="p-4">Certitude</th>
                  <th className="p-4 text-right sticky right-0 bg-[#FFF8F5]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E74C3C]/10">
                {clientsFiltres.length > 0 ? (
                  clientsFiltres.map(client => {
                    return (
                      // NOUVEAU : On englobe les lignes dans un Fragment pour pouvoir afficher la ligne cachée juste en dessous
                      <React.Fragment key={client.id}>
                        <tr className="hover:bg-[#FFF0E6]/50 transition-colors">
                          <td className="p-4 font-bold text-gray-800">{client.cin}</td>
                          <td className="p-4">
                            <div className="font-medium text-gray-800">{client.nomComplet}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{client.segmentMetier}</div>
                          </td>

                          <td className="p-4">
                            {client.comptes && client.comptes.length > 0 ? (
                              <div className="flex flex-col gap-1.5">
                                {client.comptes.map(compte => (
                                  <span key={compte.id} className="text-xs font-mono text-gray-600 bg-gray-50 px-2 py-1 rounded-md border border-gray-200 w-max flex items-center gap-2">
                                    <span className="font-bold text-[#E74C3C] text-[10px] bg-[#FFF0E6] px-1.5 py-0.5 rounded">
                                      {compte.typeCompte.substring(0, 3)}
                                    </span>
                                    {compte.numeroCompte}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-xs text-gray-400 italic">Aucun compte</span>
                            )}
                          </td>

                          <td className="p-4">
                            {client.prediction ? (
                              <div className="flex flex-col gap-0.5">
                                {client.prediction.motifAjustement ? (
                                  <>
                                    <span className="font-bold text-[#E74C3C]">{client.prediction.datePrevueAjustee}</span>
                                    <span className="text-xs text-gray-400 line-through" title={`Ajustement métier: ${client.prediction.motifAjustement}`}>
                                      {client.prediction.datePrevue}
                                    </span>
                                  </>
                                ) : (
                                  <span className="font-bold text-[#E74C3C]">{client.prediction.datePrevueAjustee || client.prediction.datePrevue}</span>
                                )}
                                {/* NOUVEAU : Affichage de la plage horaire */}
                                {client.prediction.plageHorairePrevue && (
                                  <span className="text-xs text-gray-500">({client.prediction.plageHorairePrevue})</span>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400 italic text-sm">En attente d'IA...</span>
                            )}
                          </td>
                          <td className="p-4">
                            {client.prediction ? (() => {
                              const raw = client.prediction.scoreProbabiliteGlobal;
                              const pct = raw != null ? (raw <= 1 ? raw * 100 : raw) : 0;
                              const isVisite = pct > 50;
                              
                              // On récupère le vrai type d'opération prévu (nettoyage au cas où c'est l'ancien format)
                              let operation = client.prediction.operationPrevue || 'Opération';
                              if (operation.includes('Analyse')) {
                                  operation = isVisite ? 'Visite' : 'Pas de visite';
                              }

                              return (
                                <span className={`px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5 w-max ${
                                  isVisite
                                    ? 'bg-red-50 text-red-700 border-red-200'
                                    : 'bg-green-50 text-green-700 border-green-200'
                                }`}>
                                  {isVisite ? '🔴' : '🟢'} {operation}
                                </span>
                              );
                            })() : (
                              <span className="text-gray-300">-</span>
                            )}
                          </td>

                          <td className="p-4">
                            {client.prediction && client.prediction.scoreProbabiliteGlobal != null ? (() => {
                              const raw = client.prediction.scoreProbabiliteGlobal;
                              // La probabilité de visite est entre 0 et 100 (ou 0 et 1)
                              const chanceVisite = raw <= 1 ? raw * 100 : raw;
                              
                              // La prédiction est "Visite" si > 50%
                              const isVisite = chanceVisite > 50;
                              
                              // La "Certitude" de la prédiction est le pourcentage dans la classe prédite
                              const certitude = isVisite ? chanceVisite : (100 - chanceVisite);
                              
                              // Couleur correspondante
                              const textColor = isVisite ? 'text-red-600' : 'text-green-600';
                              
                              return (
                                <span className={`font-bold ${textColor}`}>
                                  {Math.round(certitude)}%
                                </span>
                              );
                            })() : (
                              <span className="text-gray-400">-</span>
                            )}
                          </td>

                          <td className="p-4 text-right flex justify-end gap-2 sticky right-0 bg-white/90 backdrop-blur-sm">
                            {/* NOUVEAU : Bouton Agent IA */}
                            {client.prediction?.insightGenai && (
                              <button
                                onClick={() => toggleExplication(client.id)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium text-sm transition-all border ${
                                  clientExplicationOuverte === client.id
                                    ? 'bg-purple-100 text-purple-800 border-purple-200 shadow-inner'
                                    : 'text-purple-600 hover:text-purple-800 hover:bg-purple-50 border-transparent hover:border-purple-100'
                                }`}
                                title="Voir l'analyse de l'Agent IA"
                              >
                                <Sparkles size={16} className={clientExplicationOuverte === client.id ? "text-purple-700" : ""} />
                                {clientExplicationOuverte === client.id ? 'Fermer' : 'Agent IA'}
                              </button>
                            )}

                            <button
                              onClick={() => onViewDetails(client)}
                              className="text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-3 py-1.5 rounded-md font-medium text-sm transition-all border border-transparent hover:border-blue-100"
                            >
                              Détails
                            </button>
                            <button
                              onClick={() => handleSupprimer(client.id, client.nomComplet)}
                              className="text-red-500 hover:text-white hover:bg-red-500 p-1.5 rounded-md transition-all border border-red-100"
                              title="Supprimer ce client"
                            >
                              <Trash2 size={18} />
                            </button>
                          </td>
                        </tr>

                        {/* NOUVEAU : Ligne déroulante qui s'affiche au clic (Agent IA) */}
                        {clientExplicationOuverte === client.id && client.prediction?.insightGenai && (
                          <tr className="bg-gradient-to-r from-purple-50 to-white border-b border-purple-100/50">
                            <td colSpan="7" className="p-4 pl-8">
                              <div className="flex items-start gap-3 animate-fade-in-down">
                                <div className="p-2 bg-purple-100 rounded-lg text-purple-600 shadow-sm mt-0.5">
                                  <Sparkles size={20} />
                                </div>
                                <div>
                                  <h4 className="text-xs font-bold text-purple-900 uppercase tracking-wider mb-1">
                                    Analyse prédictive de l'Agent
                                  </h4>
                                  <p className="text-sm text-gray-800 italic leading-relaxed whitespace-normal max-w-4xl">
                                    "{client.prediction.insightGenai}"
                                  </p>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="7" className="p-12 text-center text-gray-500 flex flex-col items-center justify-center gap-2">
                      <Filter className="text-gray-300" size={32} />
                      Aucun client ne correspond à vos critères.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-[#E74C3C]/10 flex items-center justify-between bg-[#FFF8F5]">
            <span className="text-sm text-gray-600 font-medium">Page {pageActive + 1} sur {totalPages > 0 ? totalPages : 1} ({totalElements} clients)</span>
            <div className="flex gap-2">
              <button onClick={() => setPageActive(p => Math.max(0, p - 1))} disabled={pageActive === 0} className="flex items-center gap-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-[#E74C3C] hover:text-white hover:border-[#E74C3C] disabled:opacity-50 transition-all shadow-sm">
                <ChevronLeft size={16} /> Précédent
              </button>
              <button onClick={() => setPageActive(p => Math.min(totalPages - 1, p + 1))} disabled={pageActive >= totalPages - 1} className="flex items-center gap-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-[#E74C3C] hover:text-white hover:border-[#E74C3C] disabled:opacity-50 transition-all shadow-sm">
                Suivant <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}