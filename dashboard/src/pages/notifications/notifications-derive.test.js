import { describe, it, expect } from 'vitest';
import * as d from './notifications-derive';

const NOW = new Date('2026-06-07T12:00:00');

describe('severityOf', () => {
  it('classifies failures as Error', () => {
    expect(d.severityOf({ type: 'Agent Job Failure' })).toBe('Error');
    expect(d.severityOf({ title: 'Site responding slowly', type: 'Downtime/Performance is down' })).toBe('Error');
  });
  it('classifies validation/pending as Warning', () => {
    expect(d.severityOf({ type: 'Pre Build Validation Warning' })).toBe('Warning');
    expect(d.severityOf({ type: 'Support Access', title: 'access requested' })).toBe('Warning');
  });
  it('classifies completions as Success', () => {
    expect(d.severityOf({ type: 'Version Upgrade', title: 'Upgrade complete' })).toBe('Success');
  });
  it('falls back to Info', () => {
    expect(d.severityOf({ type: 'Site Migrate' })).toBe('Info');
    expect(d.severityOf({})).toBe('Info');
  });
  it('lets Error win over Warning when both match', () => {
    expect(d.severityOf({ type: 'Validation', title: 'build failed' })).toBe('Error');
  });
});

describe('needsAttention', () => {
  it('is true only for actionable + unaddressed', () => {
    expect(d.needsAttention({ is_actionable: 1, is_addressed: 0 })).toBe(true);
    expect(d.needsAttention({ is_actionable: 1, is_addressed: 1 })).toBe(false);
    expect(d.needsAttention({ is_actionable: 0, is_addressed: 0 })).toBe(false);
  });
});

describe('bucketOf', () => {
  it('buckets by local day', () => {
    expect(d.bucketOf('2026-06-07 09:00:00', NOW)).toBe('Today');
    expect(d.bucketOf('2026-06-06 23:00:00', NOW)).toBe('Yesterday');
    expect(d.bucketOf('2026-06-01 10:00:00', NOW)).toBe('Earlier');
  });
  it('treats null/garbage creation as Earlier', () => {
    expect(d.bucketOf(null, NOW)).toBe('Earlier');
    expect(d.bucketOf('not-a-date', NOW)).toBe('Earlier');
  });
});

describe('timeAgo', () => {
  it('returns a relative string for a valid timestamp', () => {
    expect(d.timeAgo('2026-06-07 09:00:00', NOW)).toMatch(/ago/);
  });
  it('returns empty for null/garbage', () => {
    expect(d.timeAgo(null, NOW)).toBe('');
    expect(d.timeAgo('not-a-date', NOW)).toBe('');
  });
  it('clamps future timestamps (clock skew) to just now', () => {
    expect(d.timeAgo('2026-06-07 13:00:00', NOW)).toBe('just now');
  });
});

describe('cleanMessage / plainLength', () => {
  it('strips tags except <b>', () => {
    expect(d.cleanMessage('<p>Hello <b>world</b></p>')).toBe('Hello <b>world</b>');
  });
  it('handles empty message', () => {
    expect(d.cleanMessage(null)).toBe('');
    expect(d.cleanMessage('')).toBe('');
  });
  it('plainLength ignores all markup', () => {
    expect(d.plainLength('<b>abc</b>')).toBe(3);
  });
});

describe('summarize', () => {
  it('counts unread, attention, errors', () => {
    const items = [
      { read: 0, type: 'Agent Job Failure', is_actionable: 1, is_addressed: 0 },
      { read: 1, type: 'Site Migrate' },
      { read: 0, type: 'Pre Build Validation Warning' },
    ];
    expect(d.summarize(items)).toEqual({ unread: 2, attention: 1, errors: 1 });
  });
});

describe('applyFilters', () => {
  const items = [
    { read: 0, type: 'Agent Job Failure', is_actionable: 1, is_addressed: 0 }, // Error, unread, attention
    { read: 1, type: 'Site Migrate' },                                          // Info, read
    { read: 0, type: 'Version Upgrade', title: 'complete' },                    // Success, unread
  ];
  it('filters by unread tab', () => {
    expect(d.applyFilters(items, { tab: 'unread' })).toHaveLength(2);
  });
  it('filters by attention tab', () => {
    expect(d.applyFilters(items, { tab: 'attention' })).toHaveLength(1);
  });
  it('filters by severity', () => {
    expect(d.applyFilters(items, { tab: 'all', severity: 'Error' })).toHaveLength(1);
  });
  it('filters by type', () => {
    expect(d.applyFilters(items, { tab: 'all', type: 'Site Migrate' })).toHaveLength(1);
  });
});

describe('groupByBucket', () => {
  it('returns ordered, non-empty buckets only', () => {
    const items = [
      { creation: '2026-06-07 09:00:00' },
      { creation: '2026-06-01 10:00:00' },
    ];
    const groups = d.groupByBucket(items, NOW);
    expect(groups.map((g) => g.label)).toEqual(['Today', 'Earlier']);
    expect(groups[0].items).toHaveLength(1);
  });
});

describe('distinctTypes', () => {
  it('returns sorted unique types', () => {
    const items = [{ type: 'B' }, { type: 'A' }, { type: 'B' }, { type: null }];
    expect(d.distinctTypes(items)).toEqual(['A', 'B']);
  });
});
