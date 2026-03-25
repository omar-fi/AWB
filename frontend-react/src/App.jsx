import { useState, useEffect } from 'react'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import FilterBar from './components/FilterBar'
import ClientTable from './components/ClientTable'
import CompteTable from './components/CompteTable'
import CreateClientModal from './components/CreateClientModal'
import CreateCompteModal from './components/CreateCompteModal'
import ClientDetailsModal from './components/ClientDetailsModal'
import Login from './components/Login' // NOUVEAU : Import du composant de connexion

function App() {
  // --- ÉTATS D'AUTHENTIFICATION ---
  const [banquier, setBanquier] = useState(null)

  // --- ÉTATS GLOBAUX ---
  const [vueActive, setVueActive] = useState('CLIENTS')
  const [clientSelectionne, setClientSelectionne] = useState(null)
  const [tousLesClients, setTousLesClients] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isCompteModalOpen, setIsCompteModalOpen] = useState(false)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [pageActive, setPageActive] = useState(0)
  const ITEMS_PER_PAGE = 10;

  // --- ÉTATS DE FILTRAGE ---
  const [recherche, setRecherche] = useState('')
  const [filtreStatut, setFiltreStatut] = useState('TOUS')
  const [filtreSegment, setFiltreSegment] = useState('TOUS')
  const [filtreDate, setFiltreDate] = useState('')

  // 1. Vérifier si le banquier est déjà connecté au lancement de l'app
  useEffect(() => {
    const savedBanquier = localStorage.getItem('banquierConnecte');
    if (savedBanquier) {
      setBanquier(JSON.parse(savedBanquier));
    }
  }, []);

  // 2. Charger les clients (Uniquement ceux de l'agence du banquier connecté)
  useEffect(() => {
    // Si pas de banquier connecté, on arrête l'exécution ici
    if (!banquier) return;

    const fetchClients = () => {
      // L'URL cible maintenant spécifiquement l'agence du banquier
      axios.get(`http://localhost:8080/api/v1/clients/agence/${banquier.agenceId}?size=1000&sort=id,desc&t=${Date.now()}`)
        .then(response => {
          const data = response.data.content || (Array.isArray(response.data) ? response.data : []);
          setTousLesClients(data);
          setChargement(false);
        })
        .catch(err => {
          console.error("Erreur API :", err);
          setErreur("Erreur de connexion au serveur");
          setChargement(false);
        });
    };

    fetchClients();
    const intervalId = setInterval(fetchClients, 3000); // Polling toutes les 3s

    return () => clearInterval(intervalId);
  }, [refreshTrigger, banquier]); // On relance si refreshTrigger OU banquier change

  // --- LOGIQUE DE DÉCONNEXION ---
  const handleLogout = () => {
    localStorage.removeItem('banquierConnecte');
    setBanquier(null);
    setTousLesClients([]); // On vide la liste par sécurité
  };

  // --- LOGIQUE DE FILTRAGE ET TRI ---
  const clientsFiltres = (Array.isArray(tousLesClients) ? tousLesClients : [])
    .filter(client => {
      const terme = recherche.toLowerCase();
      const cinClient = client.cin?.toLowerCase() || '';
      const nomClient = client.nomComplet?.toLowerCase() || '';

      const correspondRecherche = 
        cinClient.includes(terme) || 
        nomClient.includes(terme) ||
        (client.comptes?.some(compte => 
          compte.numeroCompte?.toLowerCase().includes(terme)
        ));
      
      let correspondStatut = true;
      if (filtreStatut === 'PREDITS') correspondStatut = !!client.prediction;
      else if (filtreStatut === 'EN_ATTENTE') correspondStatut = !client.prediction;

      let correspondSegment = true;
      if (filtreSegment !== 'TOUS') correspondSegment = client.segmentMetier === filtreSegment;

      let correspondDate = true;
      if (filtreDate !== '') {
        correspondDate = client.prediction?.datePrevue === filtreDate;
      }

      return correspondRecherche && correspondStatut && correspondSegment && correspondDate;
    })
    .sort((a, b) => {
      const dateA = a.prediction?.dateDernierCalcul ? new Date(a.prediction.dateDernierCalcul) : new Date(0);
      const dateB = b.prediction?.dateDernierCalcul ? new Date(b.prediction.dateDernierCalcul) : new Date(0);
      return dateB - dateA;
    });

  const totalElements = clientsFiltres.length;
  const totalPagesCalculated = Math.ceil(totalElements / ITEMS_PER_PAGE);
  const currentPageActive = (pageActive >= totalPagesCalculated && totalPagesCalculated > 0) ? 0 : pageActive;

  const clientsAffiches = clientsFiltres.slice(
    currentPageActive * ITEMS_PER_PAGE,
    (currentPageActive + 1) * ITEMS_PER_PAGE
  );

  // --- RENDU CONDITIONNEL (CRUCIAL) ---
  // Si le banquier n'est pas connecté, on affiche UNIQUEMENT la page de Login
  if (!banquier) {
    return <Login onLoginSuccess={(data) => setBanquier(data)} />;
  }

  // Si connecté, on affiche l'application normale
  return (
    <div className="flex h-screen bg-[#FFF8F5]">
      <Sidebar
        onOpenCreateCompte={() => setIsCompteModalOpen(true)}
        vueActive={vueActive}
        setVueActive={setVueActive}
      />

      <main className="flex-1 p-8 overflow-y-auto">
        {vueActive === 'CLIENTS' ? (
          <>
            <header className="mb-8 flex flex-col gap-4">
              {/* En-tête mis à jour avec les infos du banquier */}
              <div className="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-gray-100">
                <div>
                  <h1 className="text-2xl font-bold text-gray-800">
                    Tableau de Bord - <span className="text-[#E74C3C]">{banquier.agenceNom}</span>
                  </h1>
                  <p className="text-gray-500 mt-1">
                    Bonjour <strong className="text-gray-700">{banquier.nomComplet}</strong> | Prédictions en temps réel
                  </p>
                </div>
                
                <div className="flex items-center gap-6">
                  <button 
                    onClick={handleLogout} 
                    className="text-sm font-medium text-gray-500 hover:text-red-600 transition-colors"
                  >
                    Déconnexion
                  </button>
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="bg-[#E74C3C] hover:bg-[#C0392B] text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 shadow-sm transition-all"
                  >
                    Nouveau Client
                  </button>
                </div>
              </div>

              <FilterBar
                filtreStatut={filtreStatut} setFiltreStatut={(v) => { setFiltreStatut(v); setPageActive(0); }}
                filtreSegment={filtreSegment} setFiltreSegment={(v) => { setFiltreSegment(v); setPageActive(0); }}
                filtreDate={filtreDate} setFiltreDate={(v) => { setFiltreDate(v); setPageActive(0); }}
                recherche={recherche} setRecherche={(v) => { setRecherche(v); setPageActive(0); }}
              />
            </header>

            <ClientTable
              clientsFiltres={clientsAffiches}
              chargement={chargement}
              erreur={erreur}
              pageActive={currentPageActive} setPageActive={setPageActive}
              totalPages={totalPagesCalculated} totalElements={totalElements}
              onClientDeleted={() => setRefreshTrigger(prev => prev + 1)}
              onViewDetails={(client) => setClientSelectionne(client)}
            />
          </>
        ) : (
          <CompteTable />
        )}
      </main>

      <CreateClientModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onClientCreated={() => setRefreshTrigger(prev => prev + 1)} />
      <CreateCompteModal isOpen={isCompteModalOpen} onClose={() => setIsCompteModalOpen(false)} onCompteCreated={() => setRefreshTrigger(prev => prev + 1)} />
      <ClientDetailsModal isOpen={!!clientSelectionne} onClose={() => setClientSelectionne(null)} client={clientSelectionne} />
    </div>
  )
}

export default App