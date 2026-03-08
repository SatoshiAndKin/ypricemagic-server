import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { escapeHtml, formatRelativeAge, formatTimestamp } from './utils';

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------

describe('escapeHtml', () => {
  it('escapes ampersand', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  it('escapes less-than', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes greater-than', () => {
    expect(escapeHtml('a > b')).toBe('a &gt; b');
  });

  it('escapes double quote', () => {
    expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;');
  });

  it('escapes single quote', () => {
    expect(escapeHtml("it's")).toBe('it&#039;s');
  });

  it('escapes all special chars in one string', () => {
    expect(escapeHtml('<a href="x&y">it\'s</a>')).toBe(
      '&lt;a href=&quot;x&amp;y&quot;&gt;it&#039;s&lt;/a&gt;'
    );
  });

  it('returns empty string for null', () => {
    expect(escapeHtml(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(escapeHtml(undefined)).toBe('');
  });

  it('returns unchanged string when no special chars', () => {
    expect(escapeHtml('hello world')).toBe('hello world');
  });

  it('returns empty string for empty input', () => {
    expect(escapeHtml('')).toBe('');
  });
});

// ---------------------------------------------------------------------------
// formatRelativeAge
// ---------------------------------------------------------------------------

describe('formatRelativeAge', () => {
  beforeEach(() => {
    // Fix Date.now() to a known value: 1_000_000 seconds since epoch
    vi.spyOn(Date, 'now').mockReturnValue(1_000_000 * 1000);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns "unknown" for null', () => {
    expect(formatRelativeAge(null)).toBe('unknown');
  });

  it('returns "just now" for a future timestamp', () => {
    expect(formatRelativeAge(1_000_001)).toBe('just now');
  });

  it('returns seconds for diff < 60s', () => {
    expect(formatRelativeAge(1_000_000 - 30)).toBe('30s ago');
  });

  it('returns 0s for the exact current second', () => {
    expect(formatRelativeAge(1_000_000)).toBe('0s ago');
  });

  it('returns minutes for diff 60s–3599s', () => {
    expect(formatRelativeAge(1_000_000 - 90)).toBe('1m ago');
    expect(formatRelativeAge(1_000_000 - 3599)).toBe('59m ago');
  });

  it('returns hours for diff 3600s–86399s', () => {
    expect(formatRelativeAge(1_000_000 - 3600)).toBe('1h ago');
    expect(formatRelativeAge(1_000_000 - 7200)).toBe('2h ago');
  });

  it('returns days for diff >= 86400s', () => {
    expect(formatRelativeAge(1_000_000 - 86400)).toBe('1d ago');
    expect(formatRelativeAge(1_000_000 - 172800)).toBe('2d ago');
  });
});

// ---------------------------------------------------------------------------
// formatTimestamp
// ---------------------------------------------------------------------------

describe('formatTimestamp', () => {
  it('returns "unknown" for null', () => {
    expect(formatTimestamp(null)).toBe('unknown');
  });

  it('formats a known Unix timestamp to ISO-like UTC string', () => {
    // 0 = 1970-01-01T00:00:00Z
    expect(formatTimestamp(0)).toBe('1970-01-01 00:00:00 UTC');
  });

  it('formats a non-zero timestamp', () => {
    // 1609459200 = 2021-01-01 00:00:00 UTC
    expect(formatTimestamp(1609459200)).toBe('2021-01-01 00:00:00 UTC');
  });

  it('always appends " UTC" suffix', () => {
    expect(formatTimestamp(1000000)).toMatch(/ UTC$/);
  });

  it('result has exactly 19 chars before the UTC suffix', () => {
    const result = formatTimestamp(1000000);
    // format: "YYYY-MM-DD HH:MM:SS UTC"
    expect(result.slice(0, 19)).toHaveLength(19);
  });
});
