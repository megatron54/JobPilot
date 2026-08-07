import { describe, expect, it } from 'vitest';
import { formatWorkplace, scoreStyle, workplaceChip } from './JobMatchCard';

describe('scoreStyle', () => {
  it('returns the neutral style for a null score', () => {
    expect(scoreStyle(null).text).toContain('gray');
  });

  it('returns green for high scores (>= 80)', () => {
    expect(scoreStyle(85).text).toContain('emerald');
    expect(scoreStyle(80).text).toContain('emerald');
  });

  it('returns blue for medium-high scores (60-79)', () => {
    expect(scoreStyle(65).text).toContain('blue');
  });

  it('returns amber for medium-low scores (40-59)', () => {
    expect(scoreStyle(45).text).toContain('amber');
  });

  it('returns the neutral style for low scores (< 40)', () => {
    expect(scoreStyle(10).text).toContain('gray');
  });
});

describe('workplaceChip', () => {
  it('is case-insensitive and matches remote/hybrid', () => {
    expect(workplaceChip('REMOTE')).toContain('emerald');
    expect(workplaceChip('Hybrid')).toContain('blue');
  });

  it('falls back to the neutral chip for on-site/unknown', () => {
    expect(workplaceChip('on-site')).toContain('navy-700');
    expect(workplaceChip('')).toContain('navy-700');
  });
});

describe('formatWorkplace', () => {
  it('returns an empty string for empty input', () => {
    expect(formatWorkplace('')).toBe('');
  });

  it('normalizes known workplace types', () => {
    expect(formatWorkplace('REMOTE')).toBe('Remote');
    expect(formatWorkplace('hybrid')).toBe('Hybrid');
    expect(formatWorkplace('on-site')).toBe('On-site');
    expect(formatWorkplace('office')).toBe('On-site');
  });

  it('passes through unrecognized values unchanged', () => {
    expect(formatWorkplace('Contract')).toBe('Contract');
  });
});
