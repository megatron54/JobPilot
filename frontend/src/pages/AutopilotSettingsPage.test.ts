import { describe, expect, it } from 'vitest';
import { clampNum, toggleNum, toggleStr } from './AutopilotSettingsPage';

describe('toggleStr', () => {
  it('adds a value that is not present', () => {
    expect(toggleStr(['a', 'b'], 'c')).toEqual(['a', 'b', 'c']);
  });

  it('removes a value that is already present', () => {
    expect(toggleStr(['a', 'b', 'c'], 'b')).toEqual(['a', 'c']);
  });

  it('does not mutate the input array', () => {
    const input = ['a'];
    toggleStr(input, 'b');
    expect(input).toEqual(['a']);
  });
});

describe('toggleNum', () => {
  it('adds a value that is not present', () => {
    expect(toggleNum([1, 2], 3)).toEqual([1, 2, 3]);
  });

  it('removes a value that is already present', () => {
    expect(toggleNum([1, 2, 3], 2)).toEqual([1, 3]);
  });
});

describe('clampNum', () => {
  it('clamps below the minimum', () => {
    expect(clampNum(-5, 0, 100)).toBe(0);
  });

  it('clamps above the maximum', () => {
    expect(clampNum(500, 0, 100)).toBe(100);
  });

  it('passes through values within range', () => {
    expect(clampNum(42, 0, 100)).toBe(42);
  });

  it('falls back to min (or 0) for NaN input', () => {
    expect(clampNum(NaN, 5, 100)).toBe(5);
    expect(clampNum(NaN)).toBe(0);
  });

  it('works with only a min or only a max bound', () => {
    expect(clampNum(-1, 0)).toBe(0);
    expect(clampNum(1000, undefined, 10)).toBe(10);
  });
});
