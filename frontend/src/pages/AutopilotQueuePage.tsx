import { useEffect, useState } from 'react';
import {
  AlertCircle, Loader2, Inbox, RefreshCw, Play, CheckCheck, X, Check,
  CheckCircle2, ExternalLink, UserRound, Save, Info,
  Zap, Globe, UserPlus, MessageSquare,
} from 'lucide-react';
import {
  getQueue, updateQueueAction, approveAllQueue, rejectAllQueue,
  executeQueue, executeApply, getDailyUsage,
  type QueueAction, type DailyUsage, type ExecutionResult,
} from '../services/api';

type ExecSummary = { connected: number; messaged: number; skipped: number; failed: number };

/** Chip styling + icon + label per action type. */
function actionTypeMeta(type: QueueAction['action_type']) {
  switch (type) {
    case 'apply_easy':
      return { label: 'Easy Apply', Icon: Zap, className: 'bg-blue-500/10 text-blue-400 border-blue-500/30' };
    case 'apply_external':
      return { label: 'External Apply', Icon: Globe, className: 'bg-purple-500/10 text-purple-400 border-purple-500/30' };
    case 'connect':
      return { label: 'Connect', Icon: UserPlus, className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' };
    case 'message':
      return { label: 'Message', Icon: MessageSquare, className: 'bg-blue-500/10 text-blue-400 border-blue-500/30' };
    default:
      return { label: String(type), Icon: Inbox, className: 'bg-navy-700 text-gray-400 border-navy-600' };
  }
}

/** Chip color for a queue-action status. */
function statusChipClass(status: string): string {
  switch (status) {
    case 'approved':
    case 'completed':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    case 'rejected':
    case 'failed':
      return 'bg-red-500/10 text-red-400 border-red-500/30';
    case 'edited':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    case 'skipped':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    case 'pending_review':
    default:
      return 'bg-navy-700 text-gray-400 border-navy-600';
  }
}

function formatStatus(status: string): string {
  if (!status) return 'Unknown';
  const spaced = status.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Color the inline execute-apply result banner by outcome. */
function execResultClass(status: string): string {
  const s = status.toLowerCase();
  if (s.includes('fail') || s.includes('error')) return 'bg-red-500/10 text-red-400 border-red-500/30';
  if (s.includes('success') || s.includes('applied') || s.includes('submitted') || s.includes('complete')) {
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  }
  return 'bg-navy-700 text-gray-300 border-navy-600';
}

export default function AutopilotQueuePage() {
  const [actions, setActions] = useState<QueueAction[]>([]);
  const [usage, setUsage] = useState<DailyUsage | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [bulkBusy, setBulkBusy] = useState<'approve' | 'reject' | null>(null);
  const [executing, setExecuting] = useState(false);
  const [execSummary, setExecSummary] = useState<ExecSummary | null>(null);
  const [error, setError] = useState('');

  async function loadQueue() {
    const res = await getQueue();
    setActions(res.actions ?? []);
  }

  async function loadUsage() {
    const u = await getDailyUsage();
    setUsage(u);
  }

  /** Safe queue reload used after per-action mutations (never throws). */
  async function reloadQueue() {
    try {
      await loadQueue();
    } catch (e) {
      setError(`Failed to reload queue: ${String(e)}`);
    }
  }

  // Initial load: queue (critical) + daily usage (best-effort).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      await Promise.all([
        loadQueue().catch(e => { if (!cancelled) setError(`Failed to load action queue: ${String(e)}`); }),
        loadUsage().catch(() => { /* usage is optional — service may not expose it */ }),
      ]);
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    setError('');
    await Promise.all([
      loadQueue().catch(e => setError(`Failed to load queue: ${String(e)}`)),
      loadUsage().catch(() => { /* optional */ }),
    ]);
    setRefreshing(false);
  }

  async function handleApproveAll() {
    setBulkBusy('approve');
    setError('');
    try {
      await approveAllQueue();
      await loadQueue();
    } catch (e) {
      setError(`Failed to approve all: ${String(e)}`);
    } finally {
      setBulkBusy(null);
    }
  }

  async function handleRejectAll() {
    setBulkBusy('reject');
    setError('');
    try {
      await rejectAllQueue();
      await loadQueue();
    } catch (e) {
      setError(`Failed to reject all: ${String(e)}`);
    } finally {
      setBulkBusy(null);
    }
  }

  async function handleExecute() {
    setExecuting(true);
    setError('');
    setExecSummary(null);
    try {
      const res = await executeQueue();
      setExecSummary(res);
      await Promise.all([
        loadQueue().catch(() => { /* keep last results */ }),
        loadUsage().catch(() => { /* optional */ }),
      ]);
    } catch (e) {
      setError(`Failed to execute queue: ${String(e)}`);
    } finally {
      setExecuting(false);
    }
  }

  const approvedCount = actions.filter(a => a.status === 'approved').length;
  const busy = bulkBusy !== null || executing;

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Action Queue</h1>
          <p className="text-sm text-gray-400">Review and approve prepared actions</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing || loading}
          className="flex items-center gap-2 text-xs text-gray-400 border border-navy-600 px-3 py-2 rounded-lg hover:text-white hover:border-navy-500 disabled:opacity-50 transition-colors"
        >
          {refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Daily usage */}
      {usage && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <UsageChip label="Connections" used={usage.connections.used} limit={usage.connections.limit} />
          <UsageChip label="Messages" used={usage.messages.used} limit={usage.messages.limit} />
          <UsageChip label="Applies" used={usage.applies.used} limit={usage.applies.limit} />
        </div>
      )}

      {/* Bulk actions toolbar */}
      {!loading && actions.length > 0 && (
        <div className="bg-navy-800 rounded-xl border border-navy-700 p-4 mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={handleApproveAll}
              disabled={busy}
              className="flex items-center gap-2 bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg hover:bg-navy-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed text-xs font-medium transition-colors"
            >
              {bulkBusy === 'approve' ? <Loader2 size={14} className="animate-spin" /> : <CheckCheck size={14} />}
              Approve all
            </button>
            <button
              onClick={handleRejectAll}
              disabled={busy}
              className="flex items-center gap-2 bg-navy-700 border border-navy-600 text-gray-300 px-3 py-2 rounded-lg hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-medium transition-colors"
            >
              {bulkBusy === 'reject' ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
              Reject all
            </button>
          </div>
          <button
            onClick={handleExecute}
            disabled={busy || approvedCount === 0}
            title={approvedCount === 0 ? 'Approve at least one action first' : 'Execute all approved actions'}
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm transition-colors"
          >
            {executing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {executing ? 'Executing…' : `Execute approved${approvedCount > 0 ? ` (${approvedCount})` : ''}`}
          </button>
        </div>
      )}

      {/* Execute result summary */}
      {execSummary && (
        <div
          className={`mb-6 px-4 py-3 rounded-lg text-sm flex items-center gap-2 border ${
            execSummary.failed === 0
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
          }`}
        >
          <CheckCircle2 size={15} className="shrink-0" />
          <span>
            {execSummary.connected} connected, {execSummary.messaged} messaged, {execSummary.skipped} skipped, {execSummary.failed} failed
          </span>
        </div>
      )}

      {/* Action list */}
      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-gray-500 text-sm">
          <Loader2 size={16} className="animate-spin" />
          Loading action queue…
        </div>
      ) : actions.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy-700 rounded-xl">
          <Inbox size={40} className="mx-auto mb-3 text-gray-700" />
          <p className="text-gray-400">No actions pending</p>
          <p className="text-xs text-gray-600 mt-1">Run discovery to prepare applications.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {actions.map(action => (
            <QueueActionCard
              key={action.id}
              action={action}
              disabled={busy}
              onChanged={reloadQueue}
              onError={setError}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function UsageChip({ label, used, limit }: { label: string; used: number; limit: number }) {
  const atLimit = used >= limit;
  return (
    <div className="bg-navy-800 border border-navy-700 rounded-lg px-4 py-3">
      <p className="text-[11px] text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-semibold">
        <span className={atLimit ? 'text-amber-400' : 'text-white'}>{used}</span>
        <span className="text-gray-500"> / {limit}</span>
      </p>
    </div>
  );
}

function QueueActionCard({
  action, disabled, onChanged, onError,
}: {
  action: QueueAction;
  disabled: boolean;
  onChanged: () => Promise<void> | void;
  onError: (msg: string) => void;
}) {
  const original = action.content_final || action.content_draft;
  const [text, setText] = useState(original);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [applying, setApplying] = useState(false);
  const [execResult, setExecResult] = useState<ExecutionResult | null>(null);

  const meta = actionTypeMeta(action.action_type);
  const TypeIcon = meta.Icon;
  const isApply = action.action_type === 'apply_easy' || action.action_type === 'apply_external';
  const linkedinUrl = `https://www.linkedin.com/jobs/view/${action.job_id}/`;
  const dirty = text !== original;
  const localBusy = saving || approving || rejecting || applying;
  const anyBusy = localBusy || disabled;

  async function handleSave() {
    setSaving(true);
    onError('');
    try {
      await updateQueueAction(action.id, { status: 'edited', content_final: text });
      await onChanged();
    } catch (e) {
      onError(`Failed to save action #${action.id}: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    setApproving(true);
    onError('');
    try {
      await updateQueueAction(action.id, { status: 'approved' });
      await onChanged();
    } catch (e) {
      onError(`Failed to approve action #${action.id}: ${String(e)}`);
    } finally {
      setApproving(false);
    }
  }

  async function handleReject() {
    setRejecting(true);
    onError('');
    try {
      await updateQueueAction(action.id, { status: 'rejected' });
      await onChanged();
    } catch (e) {
      onError(`Failed to reject action #${action.id}: ${String(e)}`);
    } finally {
      setRejecting(false);
    }
  }

  async function handleApply() {
    setApplying(true);
    onError('');
    try {
      const res = await executeApply(action.job_id);
      setExecResult(res);
      await onChanged();
    } catch (e) {
      onError(`Failed to apply for ${action.job_id}: ${String(e)}`);
    } finally {
      setApplying(false);
    }
  }

  const btnBase = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

  return (
    <div className="bg-navy-800 rounded-xl border border-navy-700 p-5">
      {/* Top row: type + status chips, job link */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-[11px] border flex items-center gap-1 ${meta.className}`}>
            <TypeIcon size={11} />
            {meta.label}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[11px] border ${statusChipClass(action.status)}`}>
            {formatStatus(action.status)}
          </span>
        </div>
        <a
          href={linkedinUrl}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-blue-400 transition-colors shrink-0"
          title="View job on LinkedIn"
        >
          <ExternalLink size={13} />
          Job
        </a>
      </div>

      {/* Meta row: job id + recruiter */}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-500">
        <span className="font-mono truncate">job #{action.job_id}</span>
        {action.target_profile_url && (
          <a
            href={action.target_profile_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-blue-400 hover:underline"
          >
            <UserRound size={11} />
            Recruiter profile
          </a>
        )}
      </div>

      {/* Editable content */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-[11px] text-gray-500">Message / cover letter</label>
          {dirty && <span className="text-[11px] text-amber-400">Unsaved changes</span>}
        </div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={5}
          spellCheck={false}
          placeholder="No content drafted yet…"
          className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 resize-y"
        />
        <div className="mt-2">
          <button
            onClick={handleSave}
            disabled={anyBusy || !dirty}
            className={`${btnBase} bg-navy-700 border border-navy-600 text-gray-300 hover:bg-navy-600 hover:text-white`}
          >
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            Save
          </button>
        </div>
      </div>

      {/* Per-action buttons */}
      <div className="mt-4 pt-4 border-t border-navy-700 flex flex-wrap items-center gap-2">
        <button
          onClick={handleApprove}
          disabled={anyBusy}
          className={`${btnBase} bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20`}
        >
          {approving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
          Approve
        </button>
        <button
          onClick={handleReject}
          disabled={anyBusy}
          className={`${btnBase} bg-navy-700 border border-red-500/30 text-red-400 hover:bg-red-500/10`}
        >
          {rejecting ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
          Reject
        </button>
        {isApply && (
          <>
            <button
              onClick={handleApply}
              disabled={anyBusy}
              className={`${btnBase} bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20`}
            >
              {applying ? <Loader2 size={13} className="animate-spin" /> : <ExternalLink size={13} />}
              Open & Apply
            </button>
            <span className="text-[11px] text-gray-500">Opens a browser window</span>
          </>
        )}
      </div>

      {/* Execute-apply inline result */}
      {execResult && (
        <div className={`mt-3 px-3 py-2 rounded-lg border text-xs flex items-start gap-2 ${execResultClass(execResult.status)}`}>
          <Info size={13} className="shrink-0 mt-0.5" />
          <div className="min-w-0">
            <span className="font-medium capitalize">{execResult.status || 'done'}</span>
            {execResult.detail && <span className="break-words"> — {execResult.detail}</span>}
            {execResult.ats && <span className="opacity-70"> · {execResult.ats}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
