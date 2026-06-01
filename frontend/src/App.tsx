import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Briefcase, FileText, User, Home } from 'lucide-react';
import { setup, type SetupStatus } from './services/api';
import Dashboard from './pages/Dashboard';
import JobsPage from './pages/JobsPage';
import GeneratePage from './pages/GeneratePage';
import ProfilePage from './pages/ProfilePage';

/** The JP speed-mark as inline SVG — derived from Logo.png monogram colors */
function JPMark({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 510 510" fill="none" className={className}>
      {/* Speed lines */}
      <rect x="48" y="195" width="155" height="22" rx="11" fill="#1e2a3a"/>
      <rect x="28" y="238" width="175" height="22" rx="11" fill="#1e2a3a"/>
      <rect x="48" y="281" width="155" height="22" rx="11" fill="#1e2a3a"/>
      {/* J stroke */}
      <path d="M150 100 L150 100 Q150 100 150 100" fill="none"/>
      <path d="M195 320 C195 390 165 420 130 435 C100 448 70 440 55 425 C40 410 38 385 50 365 C62 345 85 340 120 340 L245 340 L245 100 L195 100 L195 320Z" fill="#1e2a3a"/>
      {/* P stroke */}
      <path d="M245 100 L245 340 M245 100 L360 100 C420 100 460 140 460 195 C460 250 420 285 360 285 L245 285" stroke="#1e2a3a" strokeWidth="50" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    </svg>
  );
}

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
          <div className="relative mx-auto w-20 h-20 mb-6">
            <img src="/icon.png" alt="" className="w-20 h-20 object-contain" />
            <div className="absolute inset-0 rounded-full border-2 border-blue-500/30 animate-ping" />
          </div>
          <h1 className="text-xl font-semibold text-white tracking-tight mb-1">
            Job<span className="text-blue-500">Pilot</span>
          </h1>
          <p className="text-gray-500 text-xs tracking-wide">Initializing local AI...</p>
        </div>
      </div>
    );
  }

  if (setupStatus && !setupStatus.ollama_running) {
    return (
      <div className="flex items-center justify-center h-screen bg-navy-900">
        <div className="text-center max-w-sm p-8">
          <img src="/icon.png" alt="" className="w-16 h-16 mx-auto mb-5 opacity-60" />
          <h1 className="text-lg font-bold text-white mb-2">Ollama Not Available</h1>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">
            {setupStatus.error || 'JobPilot needs Ollama running locally to generate content.'}
          </p>
          <a
            href="https://ollama.com"
            target="_blank"
            className="inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 font-medium text-sm transition-colors"
          >
            Download Ollama
          </a>
          <button
            onClick={() => { setLoading(true); setup().then(setSetupStatus).finally(() => setLoading(false)); }}
            className="block mx-auto mt-4 text-xs text-gray-500 hover:text-white transition-colors"
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
        <nav className="w-60 bg-navy-800 text-white flex flex-col border-r border-navy-700/50">
          {/* Brand */}
          <div className="px-5 py-4 border-b border-navy-700/50">
            <div className="flex items-center gap-3">
              <img src="/icon.png" alt="" className="w-8 h-8 object-contain" />
              <h1 className="text-[15px] font-bold tracking-tight">
                Job<span className="text-blue-500">Pilot</span>
              </h1>
            </div>
          </div>
          
          {/* Navigation */}
          <div className="flex-1 px-3 py-4 space-y-0.5">
            <NavItem to="/" icon={<Home size={17} />} label="Dashboard" />
            <NavItem to="/jobs" icon={<Briefcase size={17} />} label="Job Offers" />
            <NavItem to="/generate" icon={<FileText size={17} />} label="Generate" />
            <NavItem to="/profile" icon={<User size={17} />} label="Profile & CV" />
          </div>

          {/* Status footer */}
          <div className="px-5 py-3 border-t border-navy-700/50">
            <div className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${setupStatus?.llm_ready ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
              <span className="text-[11px] text-gray-500">
                {setupStatus?.llm_ready ? 'AI Ready' : 'Loading model...'}
              </span>
            </div>
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
        `flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-[13px] font-medium ${
          isActive 
            ? 'bg-blue-600/15 text-blue-400' 
            : 'text-gray-400 hover:bg-white/[0.04] hover:text-gray-200'
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}

export default App;
