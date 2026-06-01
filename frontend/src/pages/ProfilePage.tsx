import { useState, useEffect } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { getProfile, saveProfile, uploadCv, listCvs, extractProfileFromCv, type Profile, type CvInfo } from '../services/api';
import { Save, Loader2, Upload, Sparkles, User } from 'lucide-react';

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cvs, setCvs] = useState<CvInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [skillInput, setSkillInput] = useState('');
  const [message, setMessage] = useState('');

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

  async function handleUploadAndExtract() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'CV Files', extensions: ['pdf', 'docx', 'doc', 'txt', 'md'] }],
    });
    if (!selected) return;
    
    try {
      setMessage('Uploading CV...');
      const cv = await uploadCv(selected as string);
      setCvs(await listCvs());
      
      setMessage('Extracting profile with AI... This may take a moment.');
      setExtracting(true);
      const extracted = await extractProfileFromCv(cv.filename);
      setProfile(extracted);
      setMessage('Profile auto-filled from your CV!');
      setTimeout(() => setMessage(''), 4000);
    } catch (e) {
      setMessage(`Error: ${e}`);
    } finally {
      setExtracting(false);
    }
  }

  async function handleExtractFromExisting(filename: string) {
    setExtracting(true);
    setMessage('Extracting profile with AI...');
    try {
      const extracted = await extractProfileFromCv(filename);
      setProfile(extracted);
      setMessage('Profile auto-filled!');
      setTimeout(() => setMessage(''), 4000);
    } catch (e) {
      setMessage(`Error: ${e}`);
    } finally {
      setExtracting(false);
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
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">Profile & CV</h1>
        <p className="text-sm text-gray-400">
          Upload your CV to auto-fill your profile, or edit manually. This info personalizes all generated content.
        </p>
      </div>

      {/* AI Extract section */}
      <div className="bg-gradient-to-r from-blue-600/10 to-purple-600/10 border border-blue-500/20 rounded-xl p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles size={16} className="text-blue-400" />
              <h3 className="font-semibold text-white text-sm">AI Profile Extraction</h3>
            </div>
            <p className="text-xs text-gray-400">Upload a CV and AI will automatically extract your name, skills, experience, and more.</p>
          </div>
          <button
            onClick={handleUploadAndExtract}
            disabled={extracting}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm shrink-0 transition-colors"
          >
            {extracting ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {extracting ? 'Extracting...' : 'Upload & Extract'}
          </button>
        </div>

        {cvs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-navy-700">
            <p className="text-xs text-gray-500 mb-2">Or extract from an existing CV:</p>
            <div className="flex flex-wrap gap-2">
              {cvs.map(cv => (
                <button
                  key={cv.filename}
                  onClick={() => handleExtractFromExisting(cv.filename)}
                  disabled={extracting}
                  className="text-xs bg-navy-800 border border-navy-600 text-gray-300 px-2.5 py-1.5 rounded-lg hover:border-blue-500/50 hover:text-blue-400 disabled:opacity-50 transition-colors"
                >
                  {cv.filename}
                </button>
              ))}
            </div>
          </div>
        )}

        {message && (
          <div className="mt-3 text-sm text-blue-400 flex items-center gap-2">
            {extracting && <Loader2 size={12} className="animate-spin" />}
            {message}
          </div>
        )}
      </div>

      {/* Profile form */}
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
            value={profile.years_experience}
            onChange={e => setProfile({ ...profile, years_experience: parseInt(e.target.value) || 0 })}
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
