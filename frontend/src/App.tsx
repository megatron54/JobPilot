import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Briefcase, FileText, User, Home, Loader2 } from 'lucide-react';
import { setup, type SetupStatus } from './services/api';
import Dashboard from './pages/Dashboard';
import JobsPage from './pages/JobsPage';
import GeneratePage from './pages/GeneratePage';
import ProfilePage from './pages/ProfilePage';

function App() {
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setup()
      .then(setSetupStatus)
      .catch(err => setSetupStatus({ ollama_running: false, llm_ready: false, error: String(err) }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-navy-900">
        <div className="text-center">
          <img src="/logo.png" alt="JobPilot" className="w-32 mx-auto mb-6 animate-pulse" />
          <p className="text-gray-400 text-sm">Starting Ollama and checking model...</p>
        </div>
      </div>
    );
  }

  if (setupStatus && !setupStatus.ollama_running) {
    return (
      <div className="flex items-center justify-center h-screen bg-navy-900">
        <div className="text-center max-w-md p-8">
          <img src="/logo.png" alt="JobPilot" className="w-24 mx-auto mb-6" />
          <h1 className="text-xl font-bold text-white mb-2">Ollama Not Available</h1>
          <p className="text-gray-400 text-sm mb-6">
            {setupStatus.error || 'Could not connect to Ollama.'}
          </p>
          <a
            href="https://ollama.com"
            target="_blank"
            className="inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 font-medium"
          >
            Download Ollama
          </a>
          <button
            onClick={() => { setLoading(true); setup().then(setSetupStatus).finally(() => setLoading(false)); }}
            className="block mx-auto mt-4 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Retry connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-navy-900">
        {/* Sidebar */}
        <nav className="w-64 bg-navy-800 text-white flex flex-col border-r border-navy-700">
          <div className="p-5 border-b border-navy-700">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="JobPilot" className="w-10 h-10 object-contain" />
              <div>
                <h1 className="text-lg font-bold">
                  <span className="text-white">Job</span>
                  <span className="text-blue-500">Pilot</span>
                </h1>
                <p className="text-[10px] text-gray-500 tracking-wider uppercase">Apply Smarter</p>
              </div>
            </div>
          </div>
          
          <div className="flex-1 p-3 space-y-1 mt-2">
            <NavItem to="/" icon={<Home size={18} />} label="Dashboard" />
            <NavItem to="/jobs" icon={<Briefcase size={18} />} label="Job Offers" />
            <NavItem to="/generate" icon={<FileText size={18} />} label="Generate" />
            <NavItem to="/profile" icon={<User size={18} />} label="Profile & CV" />
          </div>

          <div className="p-4 border-t border-navy-700">
            <div className="flex items-center gap-2 text-xs">
              <div className={`w-2 h-2 rounded-full ${setupStatus?.llm_ready ? 'bg-green-400' : 'bg-yellow-400'}`} />
              <span className="text-gray-400">
                {setupStatus?.llm_ready ? 'AI Ready' : 'Model loading...'}
              </span>
            </div>
            <p className="text-[10px] text-gray-600 mt-1">100% Local - Powered by Ollama</p>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/generate" element={<GeneratePage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
          isActive 
            ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' 
            : 'text-gray-400 hover:bg-navy-700 hover:text-white'
        }`
      }
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </NavLink>
  );
}

export default App;
