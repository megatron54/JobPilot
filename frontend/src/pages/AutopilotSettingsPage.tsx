import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, SlidersHorizontal, Save, Loader2, CheckCircle2,
  AlertCircle, ArrowLeft,
} from 'lucide-react';
import {
  getSearchCriteria, saveSearchCriteria,
  getAutopilotConfig, saveAutopilotConfig,
  type SearchCriteria, type AutopilotConfig,
} from '../services/api';

const EXPERIENCE_LEVELS: { value: string; label: string }[] = [
  { value: '1', label: 'Internship' },
  { value: '2', label: 'Entry' },
  { value: '3', label: 'Associate' },
  { value: '4', label: 'Mid-Senior' },
  { value: '5', label: 'Director' },
  { value: '6', label: 'Executive' },
];

const JOB_TYPES: { value: string; label: string }[] = [
  { value: 'F', label: 'Full-time' },
  { value: 'C', label: 'Contract' },
  { value: 'P', label: 'Part-time' },
  { value: 'T', label: 'Temporary' },
  { value: 'I', label: 'Internship' },
];

const WEEKDAYS: { value: number; label: string }[] = [
  { value: 0, label: 'Mon' },
  { value: 1, label: 'Tue' },
  { value: 2, label: 'Wed' },
  { value: 3, label: 'Thu' },
  { value: 4, label: 'Fri' },
  { value: 5, label: 'Sat' },
  { value: 6, label: 'Sun' },
];

export function toggleStr(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val];
}

export function toggleNum(arr: number[], val: number): number[] {
  return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val];
}

export function clampNum(n: number, min?: number, max?: number): number {
  if (Number.isNaN(n)) return min ?? 0;
  if (min !== undefined && n < min) return min;
  if (max !== undefined && n > max) return max;
  return n;
}

export default function AutopilotSettingsPage() {
  const [criteria, setCriteria] = useState<SearchCriteria | null>(null);
  const [config, setConfig] = useState<AutopilotConfig | null>(null);

  const [savingCriteria, setSavingCriteria] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [criteriaMsg, setCriteriaMsg] = useState('');
  const [configMsg, setConfigMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getSearchCriteria().then(setCriteria).catch(e => setError(`Failed to load search criteria: ${String(e)}`));
    getAutopilotConfig().then(setConfig).catch(e => setError(`Failed to load config: ${String(e)}`));
  }, []);

  async function handleSaveCriteria() {
    if (!criteria) return;
    setSavingCriteria(true);
    setError('');
    try {
      await saveSearchCriteria(criteria);
      setCriteriaMsg('Search criteria saved');
      setTimeout(() => setCriteriaMsg(''), 2500);
    } catch (e) {
      setError(`Failed to save criteria: ${String(e)}`);
    } finally {
      setSavingCriteria(false);
    }
  }

  async function handleSaveConfig() {
    if (!config) return;
    setSavingConfig(true);
    setError('');
    try {
      await saveAutopilotConfig(config);
      setConfigMsg('Autopilot config saved');
      setTimeout(() => setConfigMsg(''), 2500);
    } catch (e) {
      setError(`Failed to save config: ${String(e)}`);
    } finally {
      setSavingConfig(false);
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Autopilot Settings</h1>
          <p className="text-sm text-gray-400">Configure what to search for and how Autopilot runs</p>
        </div>
        <Link
          to="/autopilot"
          className="flex items-center gap-2 text-xs text-gray-400 border border-navy-600 px-3 py-2 rounded-lg hover:text-white hover:border-navy-500 transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </Link>
      </div>

      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {/* ─── Search Criteria ─── */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Search size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Search Criteria</h2>
        </div>

        {!criteria ? (
          <div className="flex items-center gap-2 py-6 text-gray-500 text-sm">
            <Loader2 size={14} className="animate-spin" />
            Loading…
          </div>
        ) : (
          <div className="space-y-5">
            <TagInput
              label="Keywords"
              values={criteria.keywords}
              onChange={v => setCriteria({ ...criteria, keywords: v })}
              placeholder="e.g. React, TypeScript (comma or Enter)"
            />

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Location</label>
              <input
                type="text"
                value={criteria.location}
                onChange={e => setCriteria({ ...criteria, location: e.target.value })}
                placeholder="e.g. Madrid, Spain"
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Workplace</label>
              <div className="flex flex-wrap gap-4">
                <CheckRow label="Remote" checked={criteria.remote} onChange={() => setCriteria({ ...criteria, remote: !criteria.remote })} />
                <CheckRow label="Hybrid" checked={criteria.hybrid} onChange={() => setCriteria({ ...criteria, hybrid: !criteria.hybrid })} />
                <CheckRow label="On-site" checked={criteria.onsite} onChange={() => setCriteria({ ...criteria, onsite: !criteria.onsite })} />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Experience levels</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {EXPERIENCE_LEVELS.map(lvl => (
                  <CheckRow
                    key={lvl.value}
                    label={lvl.label}
                    checked={criteria.experience_levels.includes(lvl.value)}
                    onChange={() => setCriteria({ ...criteria, experience_levels: toggleStr(criteria.experience_levels, lvl.value) })}
                  />
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Job types</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {JOB_TYPES.map(jt => (
                  <CheckRow
                    key={jt.value}
                    label={jt.label}
                    checked={criteria.job_types.includes(jt.value)}
                    onChange={() => setCriteria({ ...criteria, job_types: toggleStr(criteria.job_types, jt.value) })}
                  />
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Posted within (hours)</label>
              <input
                type="number"
                min={1}
                value={criteria.posted_within_hours}
                onChange={e => setCriteria({ ...criteria, posted_within_hours: clampNum(parseInt(e.target.value, 10), 1) })}
                className="w-40 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2.5 text-sm text-white"
              />
              <p className="text-[11px] text-gray-600 mt-1">Default 168 (last 7 days).</p>
            </div>

            <TagInput
              label="Excluded companies"
              values={criteria.excluded_companies}
              onChange={v => setCriteria({ ...criteria, excluded_companies: v })}
              placeholder="Companies to skip"
            />
            <TagInput
              label="Required keywords"
              values={criteria.required_keywords}
              onChange={v => setCriteria({ ...criteria, required_keywords: v })}
              placeholder="Must appear in the posting"
            />
            <TagInput
              label="Excluded keywords"
              values={criteria.excluded_keywords}
              onChange={v => setCriteria({ ...criteria, excluded_keywords: v })}
              placeholder="Reject postings containing these"
            />

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleSaveCriteria}
                disabled={savingCriteria}
                className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm transition-colors"
              >
                {savingCriteria ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
                {savingCriteria ? 'Saving…' : 'Save Criteria'}
              </button>
              <SavedMessage text={criteriaMsg} />
            </div>
          </div>
        )}
      </div>

      {/* ─── Autopilot Config ─── */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6">
        <div className="flex items-center gap-2 mb-5">
          <SlidersHorizontal size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Autopilot Config</h2>
        </div>

        {!config ? (
          <div className="flex items-center gap-2 py-6 text-gray-500 text-sm">
            <Loader2 size={14} className="animate-spin" />
            Loading…
          </div>
        ) : (
          <div className="space-y-5">
            <Toggle
              label={config.enabled ? 'Autopilot enabled' : 'Autopilot disabled'}
              checked={config.enabled}
              onChange={() => setConfig({ ...config, enabled: !config.enabled })}
            />

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Discovery source</label>
              <select
                value={config.discovery_source}
                onChange={e => setConfig({ ...config, discovery_source: e.target.value as AutopilotConfig['discovery_source'] })}
                className="w-full bg-navy-700 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="guest">Guest — no login, safest (recommended)</option>
                <option value="hybrid">Hybrid — guest search + LinkedIn enrich (needs login)</option>
                <option value="voyager">Voyager — full LinkedIn API (needs login, higher risk)</option>
              </select>
              <p className="text-xs text-gray-500 mt-1.5">
                Guest uses LinkedIn's public endpoints (no cookies, minimal ban risk). Voyager/Hybrid
                use your logged-in session for richer data (Easy Apply, recruiters) but carry more risk.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Daily schedule</label>
              <div className="flex items-end gap-3">
                <NumberField
                  label="Hour (0–23)"
                  value={config.schedule_hour}
                  min={0}
                  max={23}
                  onChange={n => setConfig({ ...config, schedule_hour: n })}
                />
                <span className="text-gray-500 pb-2">:</span>
                <NumberField
                  label="Minute (0–59)"
                  value={config.schedule_minute}
                  min={0}
                  max={59}
                  onChange={n => setConfig({ ...config, schedule_minute: n })}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Run on days</label>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map(day => {
                  const active = config.schedule_days.includes(day.value);
                  return (
                    <button
                      key={day.value}
                      type="button"
                      onClick={() => setConfig({ ...config, schedule_days: toggleNum(config.schedule_days, day.value) })}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        active
                          ? 'bg-blue-600/20 text-blue-400 border-blue-500/30'
                          : 'text-gray-400 border-navy-600 hover:bg-navy-700'
                      }`}
                    >
                      {day.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <NumberField
                label="Max connections / day"
                value={config.max_connections_per_day}
                min={0}
                onChange={n => setConfig({ ...config, max_connections_per_day: n })}
              />
              <NumberField
                label="Max messages / day"
                value={config.max_messages_per_day}
                min={0}
                onChange={n => setConfig({ ...config, max_messages_per_day: n })}
              />
              <NumberField
                label="Max applies / day"
                value={config.max_applies_per_day}
                min={0}
                onChange={n => setConfig({ ...config, max_applies_per_day: n })}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-300">Score threshold</label>
                <span className="text-sm font-semibold text-blue-400">{config.score_threshold}</span>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={config.score_threshold}
                  onChange={e => setConfig({ ...config, score_threshold: clampNum(parseInt(e.target.value, 10), 0, 100) })}
                  className="flex-1 accent-blue-600"
                />
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={config.score_threshold}
                  onChange={e => setConfig({ ...config, score_threshold: clampNum(parseInt(e.target.value, 10), 0, 100) })}
                  className="w-20 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white"
                />
              </div>
              <p className="text-[11px] text-gray-600 mt-1">Only jobs scoring at or above this are queued.</p>
            </div>

            <div className="w-full sm:w-48">
              <NumberField
                label="Top N to generate"
                value={config.top_n_generate}
                min={0}
                onChange={n => setConfig({ ...config, top_n_generate: n })}
                hint="How many top matches get drafted content."
              />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm transition-colors"
              >
                {savingConfig ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
                {savingConfig ? 'Saving…' : 'Save Config'}
              </button>
              <SavedMessage text={configMsg} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TagInput({ label, values, onChange, placeholder }: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');

  function add() {
    const parts = input.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length === 0) return;
    const next = [...values];
    for (const p of parts) {
      if (!next.includes(p)) next.push(p);
    }
    onChange(next);
    setInput('');
  }

  function remove(index: number) {
    onChange(values.filter((_, i) => i !== index));
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-2">{label}</label>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {values.map((v, i) => (
            <span key={`${v}-${i}`} className="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5">
              {v}
              <button onClick={() => remove(i)} className="hover:text-red-400 transition-colors">&times;</button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          className="flex-1 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500"
        />
        <button
          onClick={add}
          className="bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg text-sm hover:bg-navy-600 transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  );
}

function CheckRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="w-4 h-4 accent-blue-600"
      />
      <span className="text-sm text-gray-300">{label}</span>
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <button type="button" onClick={onChange} className="flex items-center gap-3 group">
      <span className={`relative w-10 h-6 rounded-full transition-colors ${checked ? 'bg-blue-600' : 'bg-navy-600'}`}>
        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${checked ? 'translate-x-4' : ''}`} />
      </span>
      <span className="text-sm text-gray-300 group-hover:text-white transition-colors">{label}</span>
    </button>
  );
}

function NumberField({ label, value, onChange, min, max, step = 1, hint }: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  min?: number;
  max?: number;
  step?: number;
  hint?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={e => onChange(clampNum(parseInt(e.target.value, 10), min, max))}
        className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white"
      />
      {hint && <p className="text-[11px] text-gray-600 mt-1">{hint}</p>}
    </div>
  );
}

function SavedMessage({ text }: { text: string }) {
  if (!text) return null;
  return (
    <span className="flex items-center gap-1.5 text-xs text-emerald-400 transition-opacity">
      <CheckCircle2 size={14} />
      {text}
    </span>
  );
}
