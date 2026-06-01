import { useState, useEffect } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { listJobs, addJob, deleteJob, uploadCv, listCvs, extractProfileFromCv, type JobOffer, type CvInfo } from '../services/api';
import { Plus, Trash2, Globe, FileText, Loader2, Upload, Briefcase, Sparkles } from 'lucide-react';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobOffer[]>([]);
  const [cvs, setCvs] = useState<CvInfo[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [inputMode, setInputMode] = useState<'url' | 'manual'>('url');
  const [url, setUrl] = useState('');
  const [rawDescription, setRawDescription] = useState('');
  const [company, setCompany] = useState('');
  const [position, setPosition] = useState('');
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadJobs();
    listCvs().then(setCvs).catch(() => {});
  }, []);

  async function loadJobs() {
    try {
      const data = await listJobs();
      setJobs(data);
    } catch {
      // ignore
    }
  }

  async function handleAdd() {
    setLoading(true);
    setError('');
    try {
      if (inputMode === 'url') {
        await addJob({ url });
      } else {
        await addJob({ raw_description: rawDescription, company, position });
      }
      setShowAdd(false);
      setUrl('');
      setRawDescription('');
      setCompany('');
      setPosition('');
      await loadJobs();
    } catch (e: any) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(jobId: string) {
    await deleteJob(jobId);
    await loadJobs();
  }

  async function handleUploadCv() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'CV Files', extensions: ['pdf', 'docx', 'doc', 'txt', 'md'] }],
    });
    if (selected) {
      try {
        const cv = await uploadCv(selected as string);
        const updated = await listCvs();
        setCvs(updated);
        setSuccess(`CV "${cv.filename}" uploaded! Extracting profile with AI...`);
        
        // Auto-extract profile from CV
        setExtracting(true);
        try {
          await extractProfileFromCv(cv.filename);
          setSuccess(`Profile auto-filled from "${cv.filename}"!`);
        } catch (e) {
          setSuccess(`CV uploaded. Profile extraction failed: ${e}`);
        } finally {
          setExtracting(false);
          setTimeout(() => setSuccess(''), 5000);
        }
      } catch (e) {
        setError(String(e));
      }
    }
  }

  return (
    <div className="p-8">
      {/* Success/error banners */}
      {success && (
        <div className="mb-4 bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          {extracting && <Loader2 size={14} className="animate-spin" />}
          <Sparkles size={14} />
          {success}
        </div>
      )}
      {error && (
        <div className="mb-4 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* CVs section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Your CVs</h2>
          <button
            onClick={handleUploadCv}
            className="flex items-center gap-2 bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg hover:bg-navy-600 hover:text-white text-sm transition-colors"
          >
            <Upload size={16} />
            Upload CV
          </button>
        </div>
        {cvs.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {cvs.map(cv => (
              <div key={cv.filename} className="bg-navy-800 border border-navy-700 rounded-lg px-3 py-2 text-sm flex items-center gap-2 text-gray-300">
                <FileText size={14} className="text-blue-400" />
                {cv.filename}
                <span className="text-xs text-gray-500">({Math.round(cv.char_count / 1000)}k chars)</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-navy-800 border border-navy-700 rounded-lg p-8 text-center">
            <FileText size={32} className="mx-auto mb-2 text-gray-600" />
            <p className="text-sm text-gray-400">No CVs uploaded yet.</p>
            <p className="text-xs text-gray-500 mt-1">Upload a PDF or DOCX to auto-fill your profile with AI.</p>
          </div>
        )}
      </div>

      {/* Jobs section */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Job Offers</h1>
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
        <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 mb-6">
          <div className="flex gap-3 mb-4">
            <button
              onClick={() => setInputMode('url')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                inputMode === 'url' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' : 'text-gray-400 border border-navy-600 hover:bg-navy-700'
              }`}
            >
              <Globe size={16} />
              From URL
            </button>
            <button
              onClick={() => setInputMode('manual')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                inputMode === 'manual' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' : 'text-gray-400 border border-navy-600 hover:bg-navy-700'
              }`}
            >
              <FileText size={16} />
              Manual
            </button>
          </div>

          {inputMode === 'url' ? (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Job posting URL</label>
              <input
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://www.linkedin.com/jobs/view/..."
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1.5">
                Supports LinkedIn, InfoJobs, Indeed, and any job posting page.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Company</label>
                  <input
                    type="text"
                    value={company}
                    onChange={e => setCompany(e.target.value)}
                    placeholder="ACME Corp"
                    className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Position</label>
                  <input
                    type="text"
                    value={position}
                    onChange={e => setPosition(e.target.value)}
                    placeholder="Senior Developer"
                    className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Job description</label>
                <textarea
                  value={rawDescription}
                  onChange={e => setRawDescription(e.target.value)}
                  placeholder="Paste the full job description here..."
                  rows={8}
                  className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
                />
              </div>
            </div>
          )}

          <button
            onClick={handleAdd}
            disabled={loading}
            className="mt-4 flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            {loading ? 'Processing...' : 'Save Job Offer'}
          </button>
        </div>
      )}

      {/* Job list */}
      <div className="space-y-3">
        {jobs.length === 0 ? (
          <div className="text-center py-16">
            <Briefcase size={48} className="mx-auto mb-3 text-gray-700" />
            <p className="text-gray-400">No job offers yet. Add one to get started.</p>
          </div>
        ) : (
          jobs.map(job => (
            <div key={job.id} className="bg-navy-800 rounded-xl border border-navy-700 p-5 flex items-start justify-between hover:border-navy-600 transition-colors">
              <div>
                <h3 className="font-semibold text-white">{job.position || 'Unknown Position'}</h3>
                <p className="text-sm text-gray-400">{job.company || 'Unknown Company'}</p>
                <div className="flex gap-3 mt-2 text-xs text-gray-500">
                  {job.location && <span>{job.location}</span>}
                  {job.source && <span className="bg-navy-700 px-2 py-0.5 rounded text-gray-400">{job.source}</span>}
                  {job.url && (
                    <a href={job.url} target="_blank" className="text-blue-400 hover:underline">view posting</a>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleDelete(job.id)}
                className="text-gray-600 hover:text-red-400 transition-colors"
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
