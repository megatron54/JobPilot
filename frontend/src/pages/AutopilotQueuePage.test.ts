import { describe, expect, it } from 'vitest';
import { actionTypeMeta, execResultClass, formatStatus, statusChipClass } from './AutopilotQueuePage';

describe('actionTypeMeta', () => {
  it('returns the expected label for each known action type', () => {
    expect(actionTypeMeta('apply_easy').label).toBe('Easy Apply');
    expect(actionTypeMeta('apply_external').label).toBe('External Apply');
    expect(actionTypeMeta('connect').label).toBe('Connect');
    expect(actionTypeMeta('message').label).toBe('Message');
  });

  it('falls back to the raw type for unknown values', () => {
    // @ts-expect-error - intentionally passing an unknown value to test the fallback branch
    expect(actionTypeMeta('something_else').label).toBe('something_else');
  });
});

describe('statusChipClass', () => {
  it('returns a green-ish class for approved/completed', () => {
    expect(statusChipClass('approved')).toContain('emerald');
    expect(statusChipClass('completed')).toContain('emerald');
  });

  it('returns a red-ish class for rejected/failed', () => {
    expect(statusChipClass('rejected')).toContain('red');
    expect(statusChipClass('failed')).toContain('red');
  });

  it('falls back to the neutral class for unknown/pending statuses', () => {
    expect(statusChipClass('pending_review')).toContain('navy-700');
    expect(statusChipClass('anything_else')).toContain('navy-700');
  });
});

describe('formatStatus', () => {
  it('replaces underscores with spaces and capitalizes the first letter', () => {
    expect(formatStatus('pending_review')).toBe('Pending review');
  });

  it('returns "Unknown" for an empty status', () => {
    expect(formatStatus('')).toBe('Unknown');
  });
});

describe('execResultClass', () => {
  it('flags failure/error keywords as red regardless of case', () => {
    expect(execResultClass('FAILED')).toContain('red');
    expect(execResultClass('error: timeout')).toContain('red');
  });

  it('flags success/applied/submitted/complete keywords as green', () => {
    expect(execResultClass('submitted')).toContain('emerald');
    expect(execResultClass('Application completed')).toContain('emerald');
  });

  it('falls back to the neutral class otherwise', () => {
    expect(execResultClass('queued')).toContain('navy-700');
  });
});
