import { useEffect, useState } from 'react';
import { getHealth, listCvs, listJobs, type HealthResponse, type CvInfo, type JobOffer } from '../services/api';
import { CheckCircle, XCircle, FileText, Briefcase, Zap, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [cvs, setCvs] = useState<CvInfo[]>([]);
  const [jobs, setJobs] = useState<JobOffer[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
    listCvs().then(setCvs).catch(() => {});
    listJobs().then(setJobs).catch(() => {});
  }, []);

  const ollamaConnected = health?.ollama_status === 'connected';

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-1">Dashboard</h1>
        <p className="text-sm text-gray-400">Overview of your job application toolkit</p>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <StatusCard
          icon={ollamaConnected ? <CheckCircle size={20} className="text-green-400" /> : <XCircle size={20} className="text-red-400" />}
          title="Ollama"
          value={ollamaConnected ? `Connected` : 'Disconnected'}
          subtitle={ollamaConnected ? `Model: ${health?.llm_model}` : 'Start Ollama to begin'}
          accent={ollamaConnected ? 'green' : 'red'}
        />
        <StatusCard
          icon={<FileText size={20} className="text-blue-400" />}
          title="CVs Uploaded"
          value={`${cvs.length}`}
          subtitle="PDF, DOCX, TXT supported"
          accent="blue"
        />
        <StatusCard
          icon={<Briefcase size={20} className="text-purple-400" />}
          title="Job Offers"
          value={`${jobs.length}`}
          subtitle="Paste URL or text to add"
          accent="purple"
        />
      </div>

      {/* Quick start */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6">
        <div className="flex items-center gap-2 mb-5">
          <Zap size={18} className="text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Quick Start</h2>
        </div>
        <div className="space-y-4">
          <Step num={1} text="Upload your CV and let AI auto-fill your profile" action="Go to Profile" onClick={() => navigate('/profile')} />
          <Step num={2} text="Add job offers by pasting a URL or the description text" action="Add Jobs" onClick={() => navigate('/jobs')} />
          <Step num={3} text="Generate cover letters, recruiter DMs, or interview prep" action="Generate" onClick={() => navigate('/generate')} />
        </div>
      </div>
    </div>
  );
}

function StatusCard({ icon, title, value, subtitle, accent }: {
  icon: React.ReactNode;
  title: string;
  value: string;
  subtitle: string;
  accent: string;
}) {
  const borderColor = accent === 'green' ? 'border-green-500/30' : accent === 'blue' ? 'border-blue-500/30' : accent === 'purple' ? 'border-purple-500/30' : 'border-red-500/30';
  return (
    <div className={`bg-navy-800 rounded-xl border border-navy-700 p-5 hover:${borderColor} transition-colors`}>
      <div className="flex items-center gap-3 mb-3">
        {icon}
        <span className="text-sm font-medium text-gray-400">{title}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
    </div>
  );
}

function Step({ num, text, action, onClick }: { num: number; text: string; action: string; onClick: () => void }) {
  return (
    <div className="flex items-center gap-4 group">
      <span className="bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold shrink-0">
        {num}
      </span>
      <span className="text-sm text-gray-300 flex-1">{text}</span>
      <button
        onClick={onClick}
        className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {action} <ArrowRight size={12} />
      </button>
    </div>
  );
}
