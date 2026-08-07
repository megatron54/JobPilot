import { describe, expect, it } from 'vitest';
import { isRecommended } from './AutopilotPage';
import type { DiscoveredJobRow } from '../services/api';

function makeJob(score: number | null): DiscoveredJobRow {
  return { score } as DiscoveredJobRow;
}

describe('isRecommended', () => {
  it('is true for scores at or above the 70 threshold', () => {
    expect(isRecommended(makeJob(70))).toBe(true);
    expect(isRecommended(makeJob(95))).toBe(true);
  });

  it('is false for scores below the threshold', () => {
    expect(isRecommended(makeJob(69))).toBe(false);
    expect(isRecommended(makeJob(0))).toBe(false);
  });

  it('treats a null score as 0 (not recommended)', () => {
    expect(isRecommended(makeJob(null))).toBe(false);
  });
});
