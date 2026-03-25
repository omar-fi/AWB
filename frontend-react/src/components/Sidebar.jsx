import { Users, CreditCard, LayoutList, PlusCircle } from 'lucide-react'
import logoAttijari from '../assets/react.jpeg'

export default function Sidebar({ onOpenCreateCompte, vueActive, setVueActive }) {
  return (
    <aside className="w-64 bg-[#E74C3C] text-white flex flex-col shadow-2xl relative overflow-hidden shrink-0">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent to-[#C0392B] opacity-20 pointer-events-none"></div>
      
      <div className="p-6 border-b border-[#C0392B] flex items-center gap-3 relative z-10">
        <img src={logoAttijari} alt="Logo" className="h-10 w-auto object-contain bg-white rounded-md p-0.5 shadow-sm" />
        <span className="text-xl font-bold tracking-tight text-white">Attijari Predict</span>
      </div>

      <nav className="flex-1 p-4 space-y-2 mt-4 relative z-10">
        
    
        <button 
          onClick={() => setVueActive('CLIENTS')}
          className={`w-full flex items-center gap-3 p-3 rounded-lg font-medium transition-all text-left ${vueActive === 'CLIENTS' ? 'bg-[#C0392B] shadow-inner text-white' : 'text-white/80 hover:bg-[#C0392B] hover:text-white'}`}
        >
          <Users size={20} className={vueActive === 'CLIENTS' ? 'text-[#FDB913]' : ''} /> 
          <span>Liste des Clients</span>
        </button>

        {/* NOUVEAU MENU : COMPTES */}
        <button 
          onClick={() => setVueActive('COMPTES')}
          className={`w-full flex items-center gap-3 p-3 rounded-lg font-medium transition-all text-left ${vueActive === 'COMPTES' ? 'bg-[#C0392B] shadow-inner text-white' : 'text-white/80 hover:bg-[#C0392B] hover:text-white'}`}
        >
          <LayoutList size={20} className={vueActive === 'COMPTES' ? 'text-[#FDB913]' : ''} /> 
          <span>Liste des Comptes</span>
        </button>
        
        <div className="my-4 border-t border-[#C0392B]/50"></div>

        <button 
          onClick={onOpenCreateCompte}
          className="w-full flex items-center gap-3 p-3 border border-[#FDB913]/30 hover:bg-[#FDB913]/10 rounded-lg text-white transition-all text-left mt-4"
        >
          <PlusCircle size={20} className="text-[#FDB913]" /> 
          <span>Ouvrir un Compte</span>
        </button>
      </nav>
    </aside>
  )
}