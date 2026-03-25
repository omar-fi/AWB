import { Search, Filter, Briefcase, Calendar } from 'lucide-react'

export default function FilterBar({ 
  filtreStatut, setFiltreStatut, 
  filtreSegment, setFiltreSegment, 
  filtreDate, setFiltreDate, 
  recherche, setRecherche 
}) {
  return (
    <div className="flex flex-wrap gap-4 items-center p-4 bg-white rounded-xl shadow-sm border border-[#E74C3C]/20 mb-8">
      
      <div className="relative">
        <div className="absolute left-3 top-2.5 text-gray-400"><Filter size={18} /></div>
        <select value={filtreStatut} onChange={(e) => setFiltreStatut(e.target.value)} className="pl-9 pr-8 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#E74C3C] outline-none appearance-none bg-[#FFF8F5] text-gray-700 cursor-pointer hover:border-[#E74C3C]/50 transition-colors">
          <option value="TOUS">Tous les statuts</option>
          <option value="PREDITS">Prédiction prête</option>
          <option value="EN_ATTENTE">En attente d'IA</option>
        </select>
      </div>

      <div className="relative">
        <div className="absolute left-3 top-2.5 text-gray-400"><Briefcase size={18} /></div>
        <select value={filtreSegment} onChange={(e) => setFiltreSegment(e.target.value)} className="pl-9 pr-8 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#E74C3C] outline-none appearance-none bg-[#FFF8F5] text-gray-700 cursor-pointer hover:border-[#E74C3C]/50 transition-colors">
          <option value="TOUS">Tous les segments</option>
          <option value="Particulier">Particulier</option>
          <option value="Professionnel">Professionnel</option>
          <option value="TPE">TPE</option>
          <option value="PME">PME</option>
          <option value="VIP">VIP</option>
        </select>
      </div>

      <div className="relative flex items-center gap-2">
        <div className="absolute left-3 text-gray-400"><Calendar size={18} /></div>
        <input type="date" value={filtreDate} onChange={(e) => setFiltreDate(e.target.value)} className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#E74C3C] outline-none bg-[#FFF8F5] text-gray-700 hover:border-[#E74C3C]/50 transition-colors" />
        {filtreDate && (
          <button onClick={() => setFiltreDate('')} className="text-xs text-[#E74C3C] hover:text-[#C0392B] underline font-medium">Effacer</button>
        )}
      </div>

      <div className="relative ml-auto">
        <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
        <input type="text" placeholder="Chercher CIN ou Nom..." value={recherche} onChange={(e) => setRecherche(e.target.value)} className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-[#E74C3C] outline-none w-64 bg-[#FFF8F5] hover:border-[#E74C3C]/50 transition-colors" />
      </div>
    </div>
  )
}