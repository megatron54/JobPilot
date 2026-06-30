import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Rocket, Sparkles, Play, Square, Power, RefreshCw, Loader2,
  AlertCircle, Settings,
} from 'lucide-react';
import {
  autopilotStatus, autopilotStart, autopilotRefreshCookies,
  runPipeline, cancelPipeline, getPipelineStatus, getDiscoveredJobs,
  type AutopilotStatus, type PipelineStatusInfo, type DiscoveredJobRow,
} from '../services/api';
import JobMatchCard from '../components/autopilot/JobMatchCard';

const TERMINAL = ['completed', 'failed', 'cancelled'];

function isRecommended(job: DiscoveredJobRow): boolean {
  return (job.score ?? 0) >= 70;
}

export default function AutopilotPage() {
  const [status, setStatus] = useState<AutopilotStatus | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatusInfo | null>(null);
  const [jobs, setJobs] = useState<DiscoveredJobRow[]>([]);
  const [total, setTotal] = useState(0);

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inFlightRef = useRef(false);

  function stopPolling() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function loadJobs() {
    const res = await getDiscoveredJobs(50, true);
    const sorted = [...res.jobs].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    setJobs(sorted);
    setTotal(res.total);
  }

  async function loadStatus() {
    const st = await autopilotStatus();
    setStatus(st);
  }

  async function pollStatus() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const s = await getPipelineStatus();
      setPipeline(s);
      if (TERMINAL.includes(s.status)) {
        stopPolling();
        setRunning(false);
        try {
          await loadJobs();
        } catch {
          /* keep last results */
        }
      }
    } catch (e) {
      stopPolling();
      setRunning(false);
      setError(`Pipeline status error: ${String(e)}`);
    } finally {
      inFlightRef.current = false;
    }
  }

  function startPolling() {
    stopPolling();
    pollRef.current = setInterval(() => { void pollStatus(); }, 1000);
  }

  // Initial load: service status, any in-flight pipeline, and existing matches.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [st, ps] = await Promise.all([autopilotStatus(), getPipelineStatus()]);
        if (cancelled) return;
        setStatus(st);
        setPipeline(ps);
        if (ps.status === 'running') {
          setRunning(true);
          startPolling();
        }
      } catch {
        /* service may be offline — banner will prompt to start it */
      }
      try {
        await loadJobs();
      } catch {
        /* no jobs yet / service offline */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleStart() {
    setStarting(true);
    setError('');
    try {
      await autopilotStart();
      await loadStatus();
    } catch (e) {
      setError(`Failed to start service: ${String(e)}`);
    } finally {
      setStarting(false);
    }
  }

  async function handleRefreshCookies() {
    setRefreshing(true);
    setError('');
    try {
      await autopilotRefreshCookies();
      await loadStatus();
    } catch (e) {
      setError(`Failed to refresh cookies: ${String(e)}`);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleRunDiscovery() {
    if (!status?.healthy) {
      setError('Start the autopilot service before running discovery.');
      return;
    }
    setError('');
    setRunning(true);
    try {
      const res = await runPipeline();
      setPipeline(res.status);
      if (TERMINAL.includes(res.status.status)) {
        setRunning(false);
        await loadJobs();
      } else {
        startPolling();
      }
    } catch (e) {
      setError(`Failed to start discovery: ${String(e)}`);
      setRunning(false);
    }
  }

  async function handleCancel() {
    setError('');
    try {
      await cancelPipeline();
      void pollStatus();
    } catch (e) {
      setError(`Failed to cancel: ${String(e)}`);
    }
  }

  const sessionActive = status?.session?.has_session ?? false;
  const recommendedCount = jobs.filter(isRecommended).length;

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Autopilot</h1>
          <p className="text-sm text-gray-400">Daily AI-powered job discovery</p>
        </div>
        <Link
          to="/autopilot/settings"
          className="flex items-center gap-2 text-xs text-gray-400 border border-navy-600 px-3 py-2 rounded-lg hover:text-white hover:border-navy-500 transition-colors"
        >
          <Settings size={14} />
          Settings
        </Link>
      </div>

      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Service status banner */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className={`w-2 h-2 rounded-full shrink-0 ${status?.healthy ? 'bg-emerald-400' : status?.spawned ? 'bg-amber-400 animate-pulse' : 'bg-gray-500'}`} />
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">
                {status?.healthy ? 'Service running' : status?.spawned ? 'Service starting…' : 'Service not running'}
              </p>
              <p className="text-xs text-gray-500">
                {status?.healthy ? `Listening on port ${status.port}` : 'Start the local autopilot service to begin'}
              </p>
            </div>
          </div>
          {!status?.healthy && (
            <button
              onClick={handleStart}
              disabled={starting}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-xs font-medium transition-colors shrink-0"
            >
              {starting ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
              {starting ? 'Starting…' : 'Start Service'}
            </button>
          )}
        </div>

        {/* Session row */}
        <div className="mt-4 pt-4 border-t border-navy-700 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className={`w-2 h-2 rounded-full shrink-0 ${sessionActive ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">
                LinkedIn session {sessionActive ? 'active' : 'inactive'}
              </p>
              {!sessionActive && (
                <p className="text-xs text-gray-500">Log into LinkedIn in your browser, then refresh cookies.</p>
              )}
            </div>
          </div>
          <button
            onClick={handleRefreshCookies}
            disabled={refreshing}
            className="flex items-center gap-2 bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg hover:bg-navy-600 hover:text-white disabled:opacity-50 text-xs font-medium transition-colors shrink-0"
          >
            {refreshing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Refresh cookies
          </button>
        </div>
      </div>

      {/* Discovery */}
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 mb-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Discovery</h2>
          </div>
          {running ? (
            <button
              onClick={handleCancel}
              className="flex items-center gap-2 bg-navy-700 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg hover:bg-red-500/10 text-sm font-medium transition-colors"
            >
              <Square size={14} />
              Cancel
            </button>
          ) : (
            <button
              onClick={handleRunDiscovery}
              disabled={!status?.healthy}
              className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm transition-colors"
              title={status?.healthy ? 'Run discovery now' : 'Start the service first'}
            >
              <Play size={16} />
              Run Discovery
            </button>
          )}
        </div>

        {pipeline && pipeline.status !== 'idle' && (
          <PipelineProgress pipeline={pipeline} />
        )}
      </div>

      {/* Results */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Matches</h2>
          {!loading && jobs.length > 0 && (
            <p className="text-sm text-gray-400">
              {total} job{total === 1 ? '' : 's'} found, {recommendedCount} recommended
            </p>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-gray-500 text-sm">
            <Loader2 size={16} className="animate-spin" />
            Loading matches…
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-navy-700 rounded-xl">
            <Rocket size={40} className="mx-auto mb-3 text-gray-700" />
            <p className="text-gray-400">No matches yet</p>
            <p className="text-xs text-gray-600 mt-1">
              Run discovery to find and score jobs from LinkedIn.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map(job => (
              <JobMatchCard key={job.job_id} job={job} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PipelineProgress({ pipeline }: { pipeline: PipelineStatusInfo }) {
  const pct = pipeline.total > 0
    ? Math.min(100, Math.round((pipeline.progress / pipeline.total) * 100))
    : 0;
  const indeterminate = pipeline.status === 'running' && pipeline.total === 0;
  const barWidth = pipeline.status === 'completed'
    ? 100
    : indeterminate
      ? 100
      : pct;
  const barColor =
    pipeline.status === 'completed' ? 'bg-emerald-500'
      : pipeline.status === 'failed' ? 'bg-red-500'
        : pipeline.status === 'cancelled' ? 'bg-amber-500'
          : 'bg-blue-500';

  return (
    <div className="mt-5">
      <div className="flex items-center justify-between text-xs mb-2">
        <span className="text-gray-300 font-medium capitalize">
          {pipeline.stage || pipeline.status}
        </span>
        {pipeline.total > 0 && (
          <span className="text-gray-500">{pipeline.progress}/{pipeline.total}</span>
        )}
      </div>

      <div className="h-2 bg-navy-900 rounded-full overflow-hidden border border-navy-700">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor} ${indeterminate ? 'animate-pulse' : ''}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>

      {pipeline.message && (
        <p className="text-xs text-gray-500 mt-2">{pipeline.message}</p>
      )}

      <div className="grid grid-cols-4 gap-3 mt-4">
        <Counter label="Fetched" value={pipeline.jobs_fetched} />
        <Counter label="Filtered" value={pipeline.jobs_filtered} />
        <Counter label="Scored" value={pipeline.jobs_scored} />
        <Counter label="Queued" value={pipeline.jobs_queued} />
      </div>
    </div>
  );
}

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-center">
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-[11px] text-gray-500">{label}</p>
    </div>
  );
}
