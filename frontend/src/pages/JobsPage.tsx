import { useState, useEffect } from 'react';
import { listJobs, createJob, scrapeJob, deleteJob, type JobOffer } from '../services/api';
import { Plus, Trash2, Globe, FileText, Loader2 } from 'lucide-react';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobOffer[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [inputMode, setInputMode] = useState<'url' | 'manual'>('url');
  const [url, setUrl] = useState('');
  const [rawDescription, setRawDescription] = useState('');
  const [company, setCompany] = useState('');
  const [position, setPosition] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      const data = await listJobs();
      setJobs(data.jobs);
    } catch {
      // ignore
    }
  }

  async function handleAdd() {
    setLoading(true);
    setError('');
    try {
      if (inputMode === 'url') {
        await createJob({ url });
      } else {
        await createJob({ raw_description: rawDescription, company, position });
      }
      setShowAdd(false);
      setUrl('');
      setRawDescription('');
      setCompany('');
      setPosition('');
      await loadJobs();
    } catch (e: any) {
      setError(e.message || 'Error adding job');
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(jobId: string) {
    await deleteJob(jobId);
    await loadJobs();
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Job Offers</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={18} />
          Add Job
        </button>
      </div>

      {/* Add job form */}
      {showAdd && (
        <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
          <div className="flex gap-4 mb-4">
            <button
              onClick={() => setInputMode('url')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                inputMode === 'url' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              <Globe size={16} />
              From URL
            </button>
            <button
              onClick={() => setInputMode('manual')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                inputMode === 'manual' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              <FileText size={16} />
              Manual
            </button>
          </div>

          {inputMode === 'url' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job posting URL</label>
              <input
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://www.linkedin.com/jobs/view/..."
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-400 mt-1">
                Supports LinkedIn, InfoJobs, Indeed, and any job posting page
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company</label>
                  <input
                    type="text"
                    value={company}
                    onChange={e => setCompany(e.target.value)}
                    placeholder="ACME Corp"
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Position</label>
                  <input
                    type="text"
                    value={position}
                    onChange={e => setPosition(e.target.value)}
                    placeholder="Senior Developer"
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job description</label>
                <textarea
                  value={rawDescription}
                  onChange={e => setRawDescription(e.target.value)}
                  placeholder="Paste the full job description here..."
                  rows={8}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
          )}

          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}

          <button
            onClick={handleAdd}
            disabled={loading}
            className="mt-4 flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            {loading ? 'Processing...' : 'Save Job Offer'}
          </button>
        </div>
      )}

      {/* Job list */}
      <div className="space-y-3">
        {jobs.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Briefcase size={48} className="mx-auto mb-3 opacity-50" />
            <p>No job offers yet. Add one to get started.</p>
          </div>
        ) : (
          jobs.map(job => (
            <div key={job.id} className="bg-white rounded-xl shadow-sm border p-5 flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-gray-800">{job.position || 'Unknown Position'}</h3>
                <p className="text-sm text-gray-500">{job.company || 'Unknown Company'}</p>
                <div className="flex gap-3 mt-2 text-xs text-gray-400">
                  {job.location && <span>{job.location}</span>}
                  {job.source && <span className="bg-gray-100 px-2 py-0.5 rounded">{job.source}</span>}
                  <span>{new Date(job.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <button
                onClick={() => handleDelete(job.id)}
                className="text-gray-400 hover:text-red-500 transition-colors"
              >
                <Trash2 size={18} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function Briefcase({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" strokeWidth="2"/>
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" strokeWidth="2"/>
    </svg>
  );
}
