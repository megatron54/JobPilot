import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Briefcase, FileText, MessageSquare, User, Home, Loader2 } from 'lucide-react';
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
      <div className="flex items-center justify-center h-screen bg-gray-900">
        <div className="text-center">
          <Loader2 size={48} className="animate-spin text-blue-400 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-white">JobPilot</h1>
          <p className="text-gray-400 text-sm mt-2">Starting Ollama and checking model...</p>
        </div>
      </div>
    );
  }

  if (setupStatus && !setupStatus.ollama_running) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900">
        <div className="text-center max-w-md p-8">
          <div className="text-red-400 text-4xl mb-4">!</div>
          <h1 className="text-xl font-bold text-white mb-2">Ollama Not Available</h1>
          <p className="text-gray-400 text-sm mb-4">
            {setupStatus.error || 'Could not connect to Ollama.'}
          </p>
          <a
            href="https://ollama.com"
            target="_blank"
            className="inline-block bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Download Ollama
          </a>
          <button
            onClick={() => { setLoading(true); setup().then(setSetupStatus).finally(() => setLoading(false)); }}
            className="block mx-auto mt-3 text-sm text-gray-400 hover:text-white"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="flex h-screen">
        {/* Sidebar */}
        <nav className="w-64 bg-gray-900 text-white flex flex-col">
          <div className="p-6 border-b border-gray-700">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Briefcase size={24} className="text-blue-400" />
              JobPilot
            </h1>
            <p className="text-xs text-gray-400 mt-1">AI Job Application Assistant</p>
          </div>
          
          <div className="flex-1 p-4 space-y-1">
            <NavItem to="/" icon={<Home size={18} />} label="Dashboard" />
            <NavItem to="/jobs" icon={<Briefcase size={18} />} label="Job Offers" />
            <NavItem to="/generate" icon={<FileText size={18} />} label="Generate" />
            <NavItem to="/profile" icon={<User size={18} />} label="Profile" />
          </div>

          <div className="p-4 border-t border-gray-700">
            <div className="flex items-center gap-2 text-xs">
              <div className={`w-2 h-2 rounded-full ${setupStatus?.llm_ready ? 'bg-green-400' : 'bg-yellow-400'}`} />
              <span className="text-gray-400">
                {setupStatus?.llm_ready ? 'Model ready' : 'Model loading...'}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">Powered by Ollama (local AI)</p>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto bg-gray-50">
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
        `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
          isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'
        }`
      }
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </NavLink>
  );
}

export default App;
