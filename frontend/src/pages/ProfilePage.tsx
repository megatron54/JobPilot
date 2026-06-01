import { useState, useEffect } from 'react';
import { getProfile, updateProfile, type Profile } from '../services/api';
import { Save, Loader2 } from 'lucide-react';

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [skillInput, setSkillInput] = useState('');

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
  }, []);

  async function handleSave() {
    if (!profile) return;
    setSaving(true);
    try {
      const updated = await updateProfile(profile);
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
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
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Your Profile</h1>
      <p className="text-sm text-gray-500 mb-6">
        This information is used to personalize all generated content. The more detail you provide, the better the results.
      </p>

      <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Full name" value={profile.name} onChange={v => setProfile({ ...profile, name: v })} />
          <Field label="Professional title" value={profile.title} onChange={v => setProfile({ ...profile, title: v })} placeholder="e.g. Senior Frontend Developer" />
          <Field label="Email" value={profile.email} onChange={v => setProfile({ ...profile, email: v })} />
          <Field label="Phone" value={profile.phone} onChange={v => setProfile({ ...profile, phone: v })} />
          <Field label="Location" value={profile.location} onChange={v => setProfile({ ...profile, location: v })} placeholder="e.g. Madrid, Spain" />
          <Field label="LinkedIn URL" value={profile.linkedin_url} onChange={v => setProfile({ ...profile, linkedin_url: v })} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Years of experience</label>
          <input
            type="number"
            value={profile.years_experience}
            onChange={e => setProfile({ ...profile, years_experience: parseInt(e.target.value) || 0 })}
            className="w-32 border rounded-lg px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Professional summary</label>
          <textarea
            value={profile.summary}
            onChange={e => setProfile({ ...profile, summary: e.target.value })}
            rows={3}
            placeholder="Brief description of your experience and what you're looking for..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
        </div>

        {/* Skills */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Key skills</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {profile.key_skills.map((skill, i) => (
              <span key={i} className="bg-blue-100 text-blue-700 px-2 py-1 rounded-full text-xs flex items-center gap-1">
                {skill}
                <button onClick={() => removeSkill(i)} className="hover:text-red-500">&times;</button>
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
              className="flex-1 border rounded-lg px-3 py-2 text-sm"
            />
            <button onClick={addSkill} className="bg-gray-100 px-3 py-2 rounded-lg text-sm hover:bg-gray-200">Add</button>
          </div>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Preferred tone</label>
          <select
            value={profile.tone}
            onChange={e => setProfile({ ...profile, tone: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          >
            <option value="professional">Professional</option>
            <option value="friendly">Friendly</option>
            <option value="formal">Formal</option>
          </select>
        </div>

        {/* Language */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Default language</label>
          <select
            value={profile.preferred_language}
            onChange={e => setProfile({ ...profile, preferred_language: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          >
            <option value="es">Spanish</option>
            <option value="en">English</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="pt">Portuguese</option>
          </select>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
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
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border rounded-lg px-3 py-2 text-sm"
      />
    </div>
  );
}
