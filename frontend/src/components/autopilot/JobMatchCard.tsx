import { useState } from 'react';
import {
  ExternalLink, ChevronDown, ChevronUp, MapPin, Building2,
  UserRound, Zap, Globe,
} from 'lucide-react';
import type { DiscoveredJobRow } from '../../services/api';

/** Visual treatment for the /100 score badge, tiered by quality. */
export function scoreStyle(score: number | null): { text: string; bg: string; border: string } {
  if (score === null) return { text: 'text-gray-400', bg: 'bg-navy-700', border: 'border-navy-600' };
  if (score >= 80) return { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
  if (score >= 60) return { text: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
  if (score >= 40) return { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
  return { text: 'text-gray-400', bg: 'bg-navy-700', border: 'border-navy-600' };
}

export function workplaceChip(type: string): string {
  const t = type.toLowerCase();
  if (t.includes('remote')) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  if (t.includes('hybrid')) return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
  return 'bg-navy-700 text-gray-400 border-navy-600';
}

export function formatWorkplace(type: string): string {
  if (!type) return '';
  const t = type.toLowerCase();
  if (t.includes('remote')) return 'Remote';
  if (t.includes('hybrid')) return 'Hybrid';
  if (t.includes('site') || t.includes('office')) return 'On-site';
  return type;
}

export default function JobMatchCard({ job }: { job: DiscoveredJobRow }) {
  const [expanded, setExpanded] = useState(false);

  const badge = scoreStyle(job.score);
  const hasApplyMethod = job.apply_method.trim().length > 0;
  const isEasyApply = job.apply_method.toLowerCase().includes('easy');
  const linkedinUrl = `https://www.linkedin.com/jobs/view/${job.job_id}/`;
  const workplaceLabel = formatWorkplace(job.workplace_type);

  return (
    <div className="bg-navy-800 rounded-xl border border-navy-700 p-5 hover:border-navy-600 transition-colors">
      <div className="flex items-start justify-between gap-4">
        {/* Main info — clickable to expand */}
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex-1 min-w-0 text-left"
        >
          <h3 className="font-semibold text-white truncate">{job.title || 'Untitled role'}</h3>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-sm text-gray-400">
            {job.company && (
              <span className="flex items-center gap-1 truncate">
                <Building2 size={13} className="shrink-0 text-gray-500" />
                {job.company}
              </span>
            )}
            {job.location && (
              <span className="flex items-center gap-1 truncate">
                <MapPin size={13} className="shrink-0 text-gray-500" />
                {job.location}
              </span>
            )}
          </div>

          {/* Chips */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {workplaceLabel && (
              <span className={`px-2 py-0.5 rounded-full text-[11px] border ${workplaceChip(job.workplace_type)}`}>
                {workplaceLabel}
              </span>
            )}
            {hasApplyMethod && (
              <span
                className={`px-2 py-0.5 rounded-full text-[11px] border flex items-center gap-1 ${
                  isEasyApply
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    : 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                }`}
              >
                {isEasyApply ? <Zap size={10} /> : <Globe size={10} />}
                {isEasyApply ? 'Easy Apply' : 'External'}
              </span>
            )}
            {job.recommendation && (
              <span className="px-2 py-0.5 rounded-full text-[11px] border bg-navy-700 text-gray-300 border-navy-600">
                {job.recommendation}
              </span>
            )}
          </div>
        </button>

        {/* Score badge + external link */}
        <div className="flex flex-col items-center gap-2 shrink-0">
          <div className={`flex flex-col items-center justify-center w-16 h-16 rounded-xl border ${badge.bg} ${badge.border}`}>
            <span className={`text-xl font-bold leading-none ${badge.text}`}>
              {job.score === null ? '—' : Math.round(job.score)}
            </span>
            <span className="text-[10px] text-gray-500 mt-0.5">/ 100</span>
          </div>
          <a
            href={linkedinUrl}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="text-gray-500 hover:text-blue-400 transition-colors"
            title="View on LinkedIn"
          >
            <ExternalLink size={15} />
          </a>
        </div>
      </div>

      {/* Recruiter */}
      {job.recruiter_name && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-gray-400">
          <UserRound size={13} className="text-gray-500" />
          <span>Recruiter:</span>
          {job.recruiter_url ? (
            <a
              href={job.recruiter_url}
              target="_blank"
              rel="noreferrer"
              onClick={e => e.stopPropagation()}
              className="text-blue-400 hover:underline"
            >
              {job.recruiter_name}
            </a>
          ) : (
            <span className="text-gray-300">{job.recruiter_name}</span>
          )}
        </div>
      )}

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="mt-3 flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300 transition-colors"
      >
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {expanded ? 'Less details' : 'More details'}
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-navy-700 space-y-2 text-xs">
          <DetailRow label="Recommendation" value={job.recommendation || '—'} />
          <DetailRow label="Workplace" value={workplaceLabel || '—'} />
          <DetailRow
            label="Apply method"
            value={hasApplyMethod ? (isEasyApply ? 'Easy Apply' : 'External') : '—'}
          />
          <DetailRow label="Status" value={job.status || '—'} />
          {job.external_url && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-28 shrink-0">External URL</span>
              <a
                href={job.external_url}
                target="_blank"
                rel="noreferrer"
                onClick={e => e.stopPropagation()}
                className="text-blue-400 hover:underline truncate"
              >
                {job.external_url}
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 w-28 shrink-0">{label}</span>
      <span className="text-gray-300 break-words">{value}</span>
    </div>
  );
}
