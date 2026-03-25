import React, { useState } from 'react';
import { X, ArrowRightLeft, DollarSign, CheckCircle, BrainCircuit } from 'lucide-react';
import axios from 'axios';

export default function OperationModal({ isOpen, onClose, compte, onOperationSuccess }) {
  const [typeOperation, setTypeOperation] = useState('RETRAIT');
  const [montant, setMontant] = useState('');
  const [chargement, setChargement] = useState(false);
  const [analyseIA, setAnalyseIA] = useState(false);

  if (!isOpen || !compte) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!montant || montant <= 0) {
      alert("Veuillez saisir un montant valide.");
      return;
    }

    setChargement(true);
    try {
      // Appel Spring Boot → déclenche l'événement Kafka → XGBoost → MySQL
      await axios.post(`http://localhost:8080/api/v1/comptes/${compte.id}/operations`, {
        typeOperation: typeOperation,
        montant: parseFloat(montant)
      });

      // Feedback visuel : XGBoost en train d'analyser
      setChargement(false);
      setAnalyseIA(true);
      onOperationSuccess(); // Rafraîchit la liste en arrière-plan

      // Ferme après 2,5s (polling va afficher la nouvelle prédiction)
      setTimeout(() => {
        setAnalyseIA(false);
        setMontant('');
        onClose();
      }, 2500);

    } catch (err) {
      console.error("Erreur d'opération:", err);
      alert("❌ Erreur lors de la transaction. Vérifiez le serveur.");
      setChargement(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-center items-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">

        {/* Header */}
        <div className="bg-[#E74C3C] p-5 text-white flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="bg-white/20 p-2 rounded-full">
              <ArrowRightLeft size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold">Nouvelle Opération</h2>
              <p className="text-white/80 text-xs font-mono mt-0.5">RIB: {compte.numeroCompte}</p>
            </div>
          </div>
          <button onClick={onClose} className="hover:bg-white/20 p-2 rounded-full transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Écran de feedback IA (après validation) */}
        {analyseIA ? (
          <div className="p-8 flex flex-col items-center gap-5 text-center">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
              <CheckCircle size={36} className="text-green-500" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-gray-800">Transaction validée !</h3>
              <p className="text-sm text-gray-500 mt-1">L'événement a été transmis via Kafka.</p>
            </div>
            <div className="w-full bg-purple-50 border border-purple-200 rounded-xl p-4 flex items-center gap-3">
              <div className="animate-spin text-purple-500">
                <BrainCircuit size={24} />
              </div>
              <div className="text-left">
                <p className="text-sm font-bold text-purple-800">XGBoost analyse le profil…</p>
                <p className="text-xs text-purple-600 mt-0.5">La prédiction sera mise à jour dans quelques secondes.</p>
              </div>
            </div>
          </div>
        ) : (
          /* Formulaire normal */
          <form onSubmit={handleSubmit} className="p-6 space-y-5">

            {/* Solde actuel */}
            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100 flex justify-between items-center">
              <span className="text-gray-500 font-medium text-sm">Solde actuel</span>
              <span className={`font-bold text-lg ${compte.solde < 0 ? 'text-red-600' : 'text-green-600'}`}>
                {new Intl.NumberFormat('fr-MA', { style: 'currency', currency: 'MAD' }).format(compte.solde)}
              </span>
            </div>

            {/* Type de transaction */}
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-2">Type de transaction</label>
              <div className="relative">
                <select
                  value={typeOperation}
                  onChange={(e) => setTypeOperation(e.target.value)}
                  className="w-full p-3 rounded-lg border border-gray-200 focus:border-[#E74C3C] outline-none font-bold text-gray-700 bg-white appearance-none cursor-pointer"
                >
                  <optgroup label="Opérations Débitrices (-) : Diminue le solde">
                    <option value="RETRAIT">Retrait Espèces</option>
                    <option value="VIREMENT_EMIS">Virement Émis</option>
                    <option value="PAIEMENT_FACTURE">Paiement de Facture (Eau/Élec...)</option>
                    <option value="PAIEMENT_CARTE">Paiement par Carte (TPE/E-com)</option>
                  </optgroup>
                  <optgroup label="Opérations Créditrices (+) : Augmente le solde">
                    <option value="VERSEMENT">Versement Espèces</option>
                    <option value="VIREMENT_RECU">Virement Reçu</option>
                    <option value="REMISE_CHEQUE">Remise de Chèque</option>
                  </optgroup>
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">▼</div>
              </div>
            </div>

            {/* Montant */}
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-2">Montant (MAD)</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="number"
                  min="1"
                  step="0.01"
                  required
                  value={montant}
                  onChange={(e) => setMontant(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-200 focus:border-[#E74C3C] focus:ring-2 focus:ring-[#E74C3C]/20 outline-none font-bold text-lg"
                  placeholder="0.00"
                />
              </div>
            </div>

            {/* Bouton */}
            <button
              type="submit"
              disabled={chargement}
              className="w-full bg-[#E74C3C] hover:bg-[#C0392B] text-white font-bold py-3 px-4 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-70 mt-4"
            >
              {chargement ? (
                <span className="animate-pulse">Traitement en cours...</span>
              ) : (
                <>
                  <CheckCircle size={20} />
                  Valider la transaction
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}