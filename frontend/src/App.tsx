import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Briefcase, FileText, MessageSquare, HelpCircle, User, Home } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import JobsPage from './pages/JobsPage';
import GeneratePage from './pages/GeneratePage';
import ProfilePage from './pages/ProfilePage';

function App() {
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

          <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
            Powered by Ollama (local AI)
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
