import { useEffect, useState } from 'react';
import { getHealth, listCvs, listJobs } from '../services/api';
import { CheckCircle, XCircle, FileText, Briefcase } from 'lucide-react';

export default function Dashboard() {
  const [health, setHealth] = useState<{ ollama_status: string; llm_model: string } | null>(null);
  const [cvCount, setCvCount] = useState(0);
  const [jobCount, setJobCount] = useState(0);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
    listCvs().then(d => setCvCount(d.cvs.length)).catch(() => {});
    listJobs().then(d => setJobCount(d.jobs.length)).catch(() => {});
  }, []);

  const ollamaConnected = health?.ollama_status === 'connected';

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

      {/* Status cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatusCard
          icon={ollamaConnected ? <CheckCircle className="text-green-500" /> : <XCircle className="text-red-500" />}
          title="Ollama"
          value={ollamaConnected ? `Connected (${health?.llm_model})` : 'Disconnected'}
          subtitle={ollamaConnected ? 'Ready to generate' : 'Start Ollama to begin'}
          color={ollamaConnected ? 'green' : 'red'}
        />
        <StatusCard
          icon={<FileText className="text-blue-500" />}
          title="CVs"
          value={`${cvCount} uploaded`}
          subtitle="PDF, DOCX, TXT supported"
          color="blue"
        />
        <StatusCard
          icon={<Briefcase className="text-purple-500" />}
          title="Job Offers"
          value={`${jobCount} saved`}
          subtitle="Paste URL or text to add"
          color="purple"
        />
      </div>

      {/* Quick start */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Quick Start</h2>
        <ol className="space-y-3 text-sm text-gray-600">
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0">1</span>
            <span>Configure your <strong>Profile</strong> with your personal info, skills, and preferred tone</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span>Upload your <strong>CV</strong> (PDF or DOCX)</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0">3</span>
            <span>Add <strong>Job Offers</strong> - paste a LinkedIn URL or the job description text</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="bg-blue-100 text-blue-700 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0">4</span>
            <span>Go to <strong>Generate</strong> and create cover letters, recruiter messages, or interview prep</span>
          </li>
        </ol>
      </div>
    </div>
  );
}

function StatusCard({ icon, title, value, subtitle, color }: {
  icon: React.ReactNode;
  title: string;
  value: string;
  subtitle: string;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm font-medium text-gray-500">{title}</span>
      </div>
      <p className="text-lg font-semibold text-gray-800">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
    </div>
  );
}
