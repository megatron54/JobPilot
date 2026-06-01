import { useState, useEffect } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import {
  getProfile, saveProfile, resetProfile,
  uploadCv, listCvs, deleteCv, extractProfileFromCv, extractProfileFromLinkedin,
  type Profile, type CvInfo
} from '../services/api';
import { Save, Loader2, Upload, Sparkles, User, Trash2, FileText, X, AlertTriangle, Linkedin } from 'lucide-react';

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cvs, setCvs] = useState<CvInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [skillInput, setSkillInput] = useState('');
  const [message, setMessage] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [linkedinLoading, setLinkedinLoading] = useState(false);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
    listCvs().then(setCvs).catch(() => {});
  }, []);

  async function handleSave() {
    if (!profile) return;
    setSaving(true);
    try {
      const updated = await saveProfile(profile);
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  async function handleResetProfile() {
    try {
      await resetProfile();
      setProfile({
        name: '', email: '', phone: '', linkedin_url: '', location: '',
        title: '', summary: '', key_skills: [], years_experience: 0,
        languages: [], preferred_language: 'es', tone: 'professional',
      });
      setShowResetConfirm(false);
      setMessage('Profile cleared.');
      setTimeout(() => setMessage(''), 3000);
    } catch (e) {
      setMessage(`Error: ${e}`);
    }
  }

  async function handleUploadDoc() {
    const selected = await open({
      multiple: true,
      filters: [{ name: 'Documents', extensions: ['pdf', 'docx', 'doc', 'txt', 'md'] }],
    });
    if (!selected) return;

    const files = Array.isArray(selected) ? selected : [selected];
    for (const file of files) {
      try {
        await uploadCv(file as string);
      } catch (e) {
        setMessage(`Error uploading: ${e}`);
      }
    }
    setCvs(await listCvs());
    setMessage(`${files.length} document(s) uploaded.`);
    setTimeout(() => setMessage(''), 3000);
  }

  async function handleDeleteCv(filename: string) {
    try {
      await deleteCv(filename);
      setCvs(await listCvs());
    } catch (e) {
      setMessage(`Error: ${e}`);
    }
  }

  async function handleExtract(filename: string) {
    setExtracting(true);
    setMessage('Extracting profile with AI...');
    try {
      const extracted = await extractProfileFromCv(filename);
      setProfile(extracted);
      setMessage('Profile auto-filled from CV!');
      setTimeout(() => setMessage(''), 4000);
    } catch (e) {
      setMessage(`Extraction error: ${e}`);
    } finally {
      setExtracting(false);
    }
  }

  async function handleLinkedinExtract() {
    if (!linkedinUrl.trim()) return;
    setLinkedinLoading(true);
    setMessage('Extracting profile info with AI...');
    try {
      const extracted = await extractProfileFromLinkedin(linkedinUrl.trim());
      setProfile(extracted);
      setMessage('Profile updated from LinkedIn text!');
      setLinkedinUrl('');
      setTimeout(() => setMessage(''), 4000);
    } catch (e) {
      setMessage(`Extraction error: ${e}`);
    } finally {
      setLinkedinLoading(false);
    }
  }

  function addSkill() {
    if (!profile || !skillInput.trim()) return;
    setProfile({ ...profile, key_skills: [...profile.key_skills, skillInput.trim()] });
    setSkillInput('');
  }

  function removeSkill(index: number) {
    if (!profile) return;
    setProfile({ ...profile, key_skills: profile.key_skills.filter((_, i) => i !== index) });
  }

  if (!profile) return <div className="p-8 text-gray-400">Loading...</div>;

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Profile & Documents</h1>
          <p className="text-sm text-gray-400">
            Upload CVs and relevant documents to give the AI context about you.
          </p>
        </div>
        <button
          onClick={() => setShowResetConfirm(true)}
          className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-400 border border-navy-600 px-3 py-1.5 rounded-lg hover:border-red-500/30 transition-colors"
        >
          <Trash2 size={12} />
          Reset Profile
        </button>
      </div>

      {/* Reset confirmation */}
      {showResetConfirm && (
        <div className="mb-4 bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertTriangle size={16} />
            Are you sure? This will delete all profile data.
          </div>
          <div className="flex gap-2">
            <button onClick={handleResetProfile} className="bg-red-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-red-700">
              Yes, delete
            </button>
            <button onClick={() => setShowResetConfirm(false)} className="text-gray-400 text-xs px-3 py-1.5 rounded-lg hover:text-white border border-navy-600">
              Cancel
            </button>
          </div>
        </div>
      )}

      {message && (
        <div className="mb-4 bg-blue-500/10 border border-blue-500/30 text-blue-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          {extracting && <Loader2 size={14} className="animate-spin" />}
          {message}
        </div>
      )}

      {/* ─── Documents Section ─── */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-white">My Documents</h2>
            <span className="text-xs text-gray-500">({cvs.length})</span>
          </div>
          <button
            onClick={handleUploadDoc}
            className="flex items-center gap-2 bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 text-xs font-medium transition-colors"
          >
            <Upload size={13} />
            Upload Documents
          </button>
        </div>

        <p className="text-xs text-gray-500 mb-3">
          Upload CVs, cover letter examples, portfolio descriptions, certifications — anything that gives context about you.
        </p>

        {cvs.length > 0 ? (
          <div className="space-y-2">
            {cvs.map(cv => (
              <div key={cv.filename} className="flex items-center justify-between bg-navy-900 border border-navy-700 rounded-lg px-4 py-2.5 group">
                <div className="flex items-center gap-3">
                  <FileText size={15} className="text-blue-400/70" />
                  <div>
                    <p className="text-sm text-gray-200">{cv.filename}</p>
                    <p className="text-[11px] text-gray-500">{Math.round(cv.char_count / 1000)}k characters extracted</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleExtract(cv.filename)}
                    disabled={extracting}
                    className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 px-2 py-1 rounded border border-blue-500/30 hover:bg-blue-600/10 disabled:opacity-50"
                    title="Extract profile from this document"
                  >
                    <Sparkles size={11} />
                    Extract
                  </button>
                  <button
                    onClick={() => handleDeleteCv(cv.filename)}
                    className="text-gray-600 hover:text-red-400 p-1 rounded hover:bg-red-500/10 transition-colors"
                    title="Delete document"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 border border-dashed border-navy-600 rounded-lg">
            <Upload size={24} className="mx-auto mb-2 text-gray-600" />
            <p className="text-sm text-gray-500">No documents yet</p>
            <p className="text-xs text-gray-600 mt-1">PDF, DOCX, TXT, MD supported</p>
          </div>
        )}
      </div>

      {/* ─── LinkedIn Import ─── */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Linkedin size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Import from LinkedIn</h2>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          Go to your LinkedIn profile, select all text (Ctrl+A), copy it (Ctrl+C), and paste it below. Or use LinkedIn's "Save to PDF" and upload it as a document above.
        </p>
        <textarea
          value={linkedinUrl}
          onChange={e => setLinkedinUrl(e.target.value)}
          placeholder="Paste your LinkedIn profile text here... (go to your profile page, Ctrl+A, Ctrl+C, then paste here)"
          rows={4}
          className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 mb-3"
        />
        <button
          onClick={handleLinkedinExtract}
          disabled={linkedinLoading || !linkedinUrl.trim()}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-xs font-medium transition-colors"
        >
          {linkedinLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {linkedinLoading ? 'Extracting...' : 'Extract Profile from Text'}
        </button>
      </div>

      {/* ─── Profile Form ─── */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <User size={16} className="text-gray-400" />
          <h2 className="text-sm font-medium text-gray-300">Personal Information</h2>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Full name" value={profile.name} onChange={v => setProfile({ ...profile, name: v })} />
          <Field label="Professional title" value={profile.title} onChange={v => setProfile({ ...profile, title: v })} placeholder="e.g. Senior Frontend Developer" />
          <Field label="Email" value={profile.email} onChange={v => setProfile({ ...profile, email: v })} />
          <Field label="Phone" value={profile.phone} onChange={v => setProfile({ ...profile, phone: v })} />
          <Field label="Location" value={profile.location} onChange={v => setProfile({ ...profile, location: v })} placeholder="e.g. Madrid, Spain" />
          <Field label="LinkedIn URL" value={profile.linkedin_url} onChange={v => setProfile({ ...profile, linkedin_url: v })} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Years of experience</label>
          <input
            type="number"
            step="0.5"
            min="0"
            value={profile.years_experience}
            onChange={e => setProfile({ ...profile, years_experience: parseFloat(e.target.value) || 0 })}
            className="w-32 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Professional summary</label>
          <textarea
            value={profile.summary}
            onChange={e => setProfile({ ...profile, summary: e.target.value })}
            rows={3}
            placeholder="Brief description of your experience and what you're looking for..."
            className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
          />
        </div>

        {/* Skills */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Key skills</label>
          <div className="flex flex-wrap gap-2 mb-3">
            {profile.key_skills.map((skill, i) => (
              <span key={i} className="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5">
                {skill}
                <button onClick={() => removeSkill(i)} className="hover:text-red-400 transition-colors">&times;</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={skillInput}
              onChange={e => setSkillInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addSkill())}
              placeholder="Add a skill..."
              className="flex-1 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500"
            />
            <button onClick={addSkill} className="bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg text-sm hover:bg-navy-600 transition-colors">Add</button>
          </div>
        </div>

        {/* Preferences */}
        <div className="pt-4 border-t border-navy-700">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Generation Preferences</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Preferred tone</label>
              <select
                value={profile.tone}
                onChange={e => setProfile({ ...profile, tone: e.target.value })}
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white"
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Default language</label>
              <select
                value={profile.preferred_language}
                onChange={e => setProfile({ ...profile, preferred_language: e.target.value })}
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white"
              >
                <option value="es">Spanish</option>
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="pt">Portuguese</option>
              </select>
            </div>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          {saved ? 'Saved!' : 'Save Profile'}
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
      />
    </div>
  );
}
