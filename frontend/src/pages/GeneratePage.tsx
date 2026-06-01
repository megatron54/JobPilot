import { useState, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';
import { 
  listCvs, listJobs, 
  generateCoverLetter, generateRecruiterMessage, 
  generateInterviewAnswer, generateInterviewQuestions,
  type CvInfo, type JobOffer 
} from '../services/api';
import { FileText, MessageSquare, HelpCircle, Loader2, Copy, Check } from 'lucide-react';

type GenerationType = 'cover_letter' | 'recruiter_message' | 'interview_answer' | 'interview_questions';

export default function GeneratePage() {
  const [cvs, setCvs] = useState<CvInfo[]>([]);
  const [jobs, setJobs] = useState<JobOffer[]>([]);
  const [selectedCv, setSelectedCv] = useState('');
  const [selectedJob, setSelectedJob] = useState('');
  const [genType, setGenType] = useState<GenerationType>('cover_letter');
  const [language, setLanguage] = useState('es');
  const [recruiterName, setRecruiterName] = useState('');
  const [messageType, setMessageType] = useState('first_contact');
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    listCvs().then(setCvs).catch(() => {});
    listJobs().then(setJobs).catch(() => {});
  }, []);

  async function handleGenerate() {
    if (!selectedCv || !selectedJob) return;
    setLoading(true);
    setResult('');

    // Listen for streaming tokens
    let accumulated = '';
    const unlisten = await listen<string>('generate-token', (event) => {
      accumulated += event.payload;
      setResult(accumulated);
    });

    const unlistenDone = await listen('generate-token-done', () => {
      setLoading(false);
      unlisten();
      unlistenDone();
    });

    try {
      switch (genType) {
        case 'cover_letter':
          await generateCoverLetter({
            cv_filename: selectedCv,
            job_id: selectedJob,
            language,
            recruiter_name: recruiterName || undefined,
          });
          break;
        case 'recruiter_message':
          await generateRecruiterMessage({
            cv_filename: selectedCv,
            job_id: selectedJob,
            message_type: messageType,
            language,
            recruiter_name: recruiterName || undefined,
          });
          break;
        case 'interview_answer':
          await generateInterviewAnswer({
            question,
            cv_filename: selectedCv,
            job_id: selectedJob,
            language,
          });
          break;
        case 'interview_questions':
          const questionsResult = await generateInterviewQuestions();
          setResult(questionsResult.content);
          setLoading(false);
          unlisten();
          unlistenDone();
          break;
      }
    } catch (e: any) {
      setResult(`Error: ${String(e)}`);
      setLoading(false);
      unlisten();
      unlistenDone();
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Generate Content</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Config panel */}
        <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
          {/* Generation type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">What to generate</label>
            <div className="grid grid-cols-2 gap-2">
              <TypeButton active={genType === 'cover_letter'} onClick={() => setGenType('cover_letter')} icon={<FileText size={16} />} label="Cover Letter" />
              <TypeButton active={genType === 'recruiter_message'} onClick={() => setGenType('recruiter_message')} icon={<MessageSquare size={16} />} label="Recruiter DM" />
              <TypeButton active={genType === 'interview_answer'} onClick={() => setGenType('interview_answer')} icon={<HelpCircle size={16} />} label="Interview Answer" />
              <TypeButton active={genType === 'interview_questions'} onClick={() => setGenType('interview_questions')} icon={<HelpCircle size={16} />} label="Likely Questions" />
            </div>
          </div>

          {/* CV selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CV</label>
            <select value={selectedCv} onChange={e => setSelectedCv(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="">Select a CV...</option>
              {cvs.map(cv => <option key={cv.filename} value={cv.filename}>{cv.filename}</option>)}
            </select>
          </div>

          {/* Job selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Job Offer</label>
            <select value={selectedJob} onChange={e => setSelectedJob(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="">Select a job offer...</option>
              {jobs.map(job => <option key={job.id} value={job.id}>{job.position} - {job.company}</option>)}
            </select>
          </div>

          {/* Language */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
            <select value={language} onChange={e => setLanguage(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="es">Spanish</option>
              <option value="en">English</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="pt">Portuguese</option>
            </select>
          </div>

          {/* Recruiter name */}
          {(genType === 'cover_letter' || genType === 'recruiter_message') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recruiter name (optional)</label>
              <input
                type="text"
                value={recruiterName}
                onChange={e => setRecruiterName(e.target.value)}
                placeholder="e.g. Rafael Fuentes"
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          )}

          {/* Message type */}
          {genType === 'recruiter_message' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Message type</label>
              <select value={messageType} onChange={e => setMessageType(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="first_contact">First contact</option>
                <option value="follow_up">Follow-up</option>
                <option value="networking">Networking</option>
              </select>
            </div>
          )}

          {/* Question */}
          {genType === 'interview_answer' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Interview question</label>
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="e.g. Tell me about a time you led a difficult project..."
                rows={3}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={loading || !selectedCv || !selectedJob}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <FileText size={18} />}
            {loading ? 'Generating with AI...' : 'Generate'}
          </button>
        </div>

        {/* Result panel */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-700">Generated Content</h2>
            {result && (
              <button onClick={handleCopy} className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600">
                {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          
          {result ? (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap text-gray-700 bg-gray-50 rounded-lg p-4 min-h-[400px] max-h-[600px] overflow-y-auto">
              {result}
              {loading && <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-0.5" />}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
              {loading ? 'Generating with AI...' : 'Select options and click Generate'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TypeButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
        active ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'text-gray-500 border border-gray-200 hover:bg-gray-50'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
