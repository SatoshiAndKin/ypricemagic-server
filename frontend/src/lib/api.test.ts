import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchPrice, fetchQuote, fetchBatchPrices, fetchBucket, fetchHealth } from './api';

// Mock fetch globally
global.fetch = vi.fn();

beforeEach(() => {
  vi.mocked(fetch).mockReset();
});

// ---------------------------------------------------------------------------
// parseResponse error handling
// ---------------------------------------------------------------------------

describe('API client error handling', () => {
  it('throws with HTTP status message for non-JSON 500 response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('Internal Server Error', { status: 500 })
    );
    await expect(fetchPrice('ethereum', '0xSomeToken')).rejects.toThrow('HTTP 500');
  });

  it('throws with HTTP status message for non-JSON 404 response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('Not Found', { status: 404 })
    );
    await expect(fetchPrice('ethereum', '0xSomeToken')).rejects.toThrow('HTTP 404');
  });

  it('throws with detail field from JSON error body when present', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'token not found' }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    await expect(fetchPrice('ethereum', '0xSomeToken')).rejects.toThrow('token not found');
  });

  it('throws with error field from JSON error body when detail is absent', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'bad request' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    await expect(fetchPrice('ethereum', '0xSomeToken')).rejects.toThrow('bad request');
  });

  it('returns parsed JSON on successful 200 response', async () => {
    const mockData = { price: 1.23, token: '0xSomeToken' };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const result = await fetchPrice('ethereum', '0xSomeToken');
    expect(result).toEqual(mockData);
  });
});

// ---------------------------------------------------------------------------
// fetchQuote
// ---------------------------------------------------------------------------

describe('fetchQuote', () => {
  it('throws on non-OK response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('error', { status: 503 }));
    await expect(fetchQuote('ethereum', '0xFrom', '0xTo')).rejects.toThrow('HTTP 503');
  });

  it('returns parsed quote on success', async () => {
    const mockQuote = { price: 0.5, amount_out: '1000' };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockQuote), { status: 200 })
    );
    const result = await fetchQuote('ethereum', '0xFrom', '0xTo');
    expect(result).toEqual(mockQuote);
  });
});

// ---------------------------------------------------------------------------
// fetchBatchPrices
// ---------------------------------------------------------------------------

describe('fetchBatchPrices', () => {
  it('throws on non-OK response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('error', { status: 500 }));
    await expect(fetchBatchPrices('ethereum', ['0xA', '0xB'])).rejects.toThrow('HTTP 500');
  });

  it('returns parsed batch result on success', async () => {
    const mockBatch = { prices: { '0xa': 1.0, '0xb': 2.0 } };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockBatch), { status: 200 })
    );
    const result = await fetchBatchPrices('ethereum', ['0xA', '0xB']);
    expect(result).toEqual(mockBatch);
  });
});

// ---------------------------------------------------------------------------
// fetchBucket
// ---------------------------------------------------------------------------

describe('fetchBucket', () => {
  it('throws on non-OK response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('error', { status: 500 }));
    await expect(fetchBucket('ethereum', '0xToken')).rejects.toThrow('HTTP 500');
  });
});

// ---------------------------------------------------------------------------
// fetchHealth
// ---------------------------------------------------------------------------

describe('fetchHealth', () => {
  it('throws on non-OK response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('error', { status: 503 }));
    await expect(fetchHealth('ethereum')).rejects.toThrow('HTTP 503');
  });

  it('returns health data on success', async () => {
    const mockHealth = { status: 'ok', block: 12345678 };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockHealth), { status: 200 })
    );
    const result = await fetchHealth('ethereum');
    expect(result).toEqual(mockHealth);
  });
});
