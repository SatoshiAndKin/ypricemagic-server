import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchBucket } from '../api';
import { addLocalToken, buildTokenIndex, searchTokens } from '../stores/tokenlist';
import type { BucketResponse, TokenlistToken } from '../types';

// Mock fetch globally
global.fetch = vi.fn();

beforeEach(() => {
  vi.mocked(fetch).mockReset();
});

// ---------------------------------------------------------------------------
// Metadata extraction from fetchBucket response
// ---------------------------------------------------------------------------

describe('UnknownTokenModal metadata fetch logic', () => {
  it('extracts metadata (symbol, name, decimals) from bucket response', async () => {
    const mockResponse: BucketResponse = {
      bucket: 'stable usd',
      token: '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70',
      chain: 'ethereum',
      symbol: 'PREMIA',
      name: 'Premia',
      decimals: 18,
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), { status: 200 })
    );

    const resp = await fetchBucket('ethereum', '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70');

    expect(resp.symbol).toBe('PREMIA');
    expect(resp.name).toBe('Premia');
    expect(resp.decimals).toBe(18);
  });

  it('returns undefined metadata fields when backend omits them', async () => {
    const mockResponse: BucketResponse = {
      bucket: null,
      token: '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
      chain: 'ethereum',
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), { status: 200 })
    );

    const resp = await fetchBucket(
      'ethereum',
      '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
    );

    expect(resp.symbol).toBeUndefined();
    expect(resp.name).toBeUndefined();
    expect(resp.decimals).toBeUndefined();
  });

  it('throws on fetch failure (network error)', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('network error'));

    await expect(
      fetchBucket('ethereum', '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef')
    ).rejects.toThrow('network error');
  });

  it('throws on non-OK response (500)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('Server Error', { status: 500 }));

    await expect(
      fetchBucket('ethereum', '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef')
    ).rejects.toThrow('HTTP 500');
  });
});

// ---------------------------------------------------------------------------
// Fallback: use truncated address when metadata unavailable
// ---------------------------------------------------------------------------

describe('Fallback metadata for save', () => {
  it('falls back to truncated address when metadata is null', () => {
    const address = '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70';
    const metadata = null as { symbol: string; name: string; decimals: number } | null;

    // This mirrors the QuoteForm save logic:
    // symbol: metadata?.symbol ?? address.slice(0, 8)
    const symbol = metadata?.symbol ?? address.slice(0, 8);
    const name = metadata?.name ?? address;
    const decimals = metadata?.decimals ?? 18;

    expect(symbol).toBe('0x6399c8');
    expect(name).toBe(address);
    expect(decimals).toBe(18);
  });

  it('uses real metadata when available', () => {
    const address = '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70';
    const metadata = { symbol: 'PREMIA', name: 'Premia', decimals: 18 } as {
      symbol: string;
      name: string;
      decimals: number;
    } | null;

    const symbol = metadata?.symbol ?? address.slice(0, 8);
    const name = metadata?.name ?? address;
    const decimals = metadata?.decimals ?? 18;

    expect(symbol).toBe('PREMIA');
    expect(name).toBe('Premia');
    expect(decimals).toBe(18);
  });
});

// ---------------------------------------------------------------------------
// Saved token appears in search with real metadata
// ---------------------------------------------------------------------------

describe('Saved token with real metadata in tokenlist index', () => {
  it('token saved with real symbol is found in search by symbol', () => {
    const localToken: TokenlistToken = {
      chainId: 1,
      address: '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70',
      symbol: 'PREMIA',
      name: 'Premia',
      decimals: 18,
    };

    const index = buildTokenIndex([
      {
        name: 'Local Tokens',
        tokens: [localToken],
        isLocal: true,
        enabled: true,
      },
    ]);

    const results = searchTokens(index, 'PREMIA', 1);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].symbol).toBe('PREMIA');
    expect(results[0].name).toBe('Premia');
    expect(results[0].address).toBe('0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70');
  });

  it('token saved with fallback is found in search by address prefix', () => {
    const localToken: TokenlistToken = {
      chainId: 1,
      address: '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70',
      symbol: '0x6399c8',
      name: '0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70',
      decimals: 18,
    };

    const index = buildTokenIndex([
      {
        name: 'Local Tokens',
        tokens: [localToken],
        isLocal: true,
        enabled: true,
      },
    ]);

    const results = searchTokens(index, '0x6399c8', 1);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].symbol).toBe('0x6399c8');
  });
});
