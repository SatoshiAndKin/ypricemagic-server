import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  buildTokenIndex,
  searchTokens,
  DEFAULT_PAIRS,
  CHAIN_IDS,
  countTokensForChain,
  getListKey,
  getCustomPairs,
  saveCustomPair,
  resetCustomPair,
  getEffectivePair,
} from './tokenlist';
import type { TokenlistEntry } from './tokenlist';
import type { TokenlistToken } from '../types';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ETH = 1;
const ARB = 42161;

function makeToken(overrides: Partial<TokenlistToken> & Pick<TokenlistToken, 'address' | 'symbol'>): TokenlistToken {
  return {
    chainId: ETH,
    name: overrides.symbol,
    decimals: 18,
    ...overrides,
  };
}

function makeList(
  name: string,
  tokens: TokenlistToken[],
  enabled = true,
  opts: Partial<TokenlistEntry> = {}
): TokenlistEntry {
  return { name, tokens, enabled, ...opts };
}

// ---------------------------------------------------------------------------
// buildTokenIndex
// ---------------------------------------------------------------------------

describe('buildTokenIndex', () => {
  it('indexes tokens by chainId and lowercase address', () => {
    const usdc = makeToken({ address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', symbol: 'USDC' });
    const list = makeList('Test', [usdc]);
    const index = buildTokenIndex([list]);

    expect(index.has(ETH)).toBe(true);
    const chainMap = index.get(ETH)!;
    expect(chainMap.has('0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48')).toBe(true);
  });

  it('first-list-wins deduplication', () => {
    const addr = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48';
    const tokenA = makeToken({ address: addr, symbol: 'USDC-A', name: 'First List USDC' });
    const tokenB = makeToken({ address: addr, symbol: 'USDC-B', name: 'Second List USDC' });

    const listA = makeList('ListA', [tokenA]);
    const listB = makeList('ListB', [tokenB]);

    const index = buildTokenIndex([listA, listB]);
    const result = index.get(ETH)!.get(addr.toLowerCase())!;
    expect(result.symbol).toBe('USDC-A');
    expect(result.sourceList).toBe('ListA');
  });

  it('ignores disabled lists', () => {
    const token = makeToken({ address: '0xDeadBeef00000000000000000000000000000001', symbol: 'DEAD' });
    const list = makeList('Disabled', [token], false);
    const index = buildTokenIndex([list]);
    expect(index.has(ETH)).toBe(false);
  });

  it('separates tokens by chainId', () => {
    const ethToken = makeToken({ chainId: ETH, address: '0x0000000000000000000000000000000000000001', symbol: 'ETH1' });
    const arbToken = makeToken({ chainId: ARB, address: '0x0000000000000000000000000000000000000002', symbol: 'ARB1' });
    const list = makeList('Multi', [ethToken, arbToken]);
    const index = buildTokenIndex([list]);

    // +1 for synthetic USD entry injected into each chain
    expect(index.get(ETH)!.size).toBe(2);
    expect(index.get(ARB)!.size).toBe(2);
  });

  it('returns empty map for empty input', () => {
    const index = buildTokenIndex([]);
    expect(index.size).toBe(0);
  });

  it('returns empty map when all lists are disabled', () => {
    const token = makeToken({ address: '0x0000000000000000000000000000000000000001', symbol: 'A' });
    const index = buildTokenIndex([makeList('L', [token], false)]);
    expect(index.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// searchTokens
// ---------------------------------------------------------------------------

describe('searchTokens', () => {
  let index: ReturnType<typeof buildTokenIndex>;

  beforeEach(() => {
    const tokens: TokenlistToken[] = [
      makeToken({ address: '0x0000000000000000000000000000000000000001', symbol: 'USDC', name: 'USD Coin' }),
      makeToken({ address: '0x0000000000000000000000000000000000000002', symbol: 'USDT', name: 'Tether USD' }),
      makeToken({ address: '0x0000000000000000000000000000000000000003', symbol: 'DAI', name: 'Dai Stablecoin' }),
      makeToken({ address: '0x0000000000000000000000000000000000000004', symbol: 'WBTC', name: 'Wrapped Bitcoin' }),
      makeToken({ address: '0x0000000000000000000000000000000000000005', symbol: 'WETH', name: 'Wrapped Ether' }),
      // CUSD: symbol contains 'USD' but doesn't start with it — lower rank than USDC/USDT prefix
      makeToken({ address: '0x0000000000000000000000000000000000000006', symbol: 'CUSD', name: 'Celo Dollar' }),
    ];
    index = buildTokenIndex([makeList('Main', tokens)]);
  });

  it('returns empty array for empty query', () => {
    const results = searchTokens(index, '', ETH);
    expect(results).toEqual([]);
  });

  it('exact symbol match ranks first', () => {
    const results = searchTokens(index, 'USDC', ETH);
    expect(results[0].symbol).toBe('USDC');
  });

  it('USD sentinel ranks first, then prefix, then contains', () => {
    // 'USD' matches synthetic USD (exact, boosted), USDC and USDT as symbol prefix (rank 1),
    // 'CUSD' contains 'USD' but does not start with it (rank 2)
    const results = searchTokens(index, 'USD', ETH);
    const symbols = results.map((t) => t.symbol);
    const usdIdx = symbols.indexOf('USD');
    const usdcIdx = symbols.indexOf('USDC');
    const usdtIdx = symbols.indexOf('USDT');
    const cusdIdx = symbols.indexOf('CUSD');
    expect(usdIdx).toBe(0); // USD sentinel is first
    expect(usdcIdx).toBeGreaterThanOrEqual(0);
    expect(usdtIdx).toBeGreaterThanOrEqual(0);
    expect(cusdIdx).toBeGreaterThanOrEqual(0);
    // prefix matches come before contains matches
    expect(usdcIdx).toBeLessThan(cusdIdx);
    expect(usdtIdx).toBeLessThan(cusdIdx);
  });

  it('name match works', () => {
    const results = searchTokens(index, 'stablecoin', ETH);
    expect(results.map((t) => t.symbol)).toContain('DAI');
  });

  it('returns at most 20 results', () => {
    // Create 25 tokens all matching 'token'
    const manyTokens: TokenlistToken[] = Array.from({ length: 25 }, (_, i) =>
      makeToken({
        address: `0x${i.toString().padStart(40, '0')}`,
        symbol: `TOKEN${i}`,
        name: `Token ${i}`,
      })
    );
    const bigIndex = buildTokenIndex([makeList('Big', manyTokens)]);
    const results = searchTokens(bigIndex, 'token', ETH);
    expect(results.length).toBeLessThanOrEqual(20);
  });

  it('chain filtering: ETH tokens do not appear in ARB results', () => {
    const ethToken = makeToken({ chainId: ETH, address: '0x0000000000000000000000000000000000000001', symbol: 'ETHONLY' });
    const arbToken = makeToken({ chainId: ARB, address: '0x0000000000000000000000000000000000000002', symbol: 'ARBONLY' });
    const mixedIndex = buildTokenIndex([makeList('Mixed', [ethToken, arbToken])]);

    const ethResults = searchTokens(mixedIndex, 'only', ETH);
    const arbResults = searchTokens(mixedIndex, 'only', ARB);

    expect(ethResults.map((t) => t.symbol)).toContain('ETHONLY');
    expect(ethResults.map((t) => t.symbol)).not.toContain('ARBONLY');
    expect(arbResults.map((t) => t.symbol)).toContain('ARBONLY');
    expect(arbResults.map((t) => t.symbol)).not.toContain('ETHONLY');
  });

  it('returns empty for unknown chainId', () => {
    const results = searchTokens(index, 'USDC', 999999);
    expect(results).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// DEFAULT_PAIRS
// ---------------------------------------------------------------------------

describe('DEFAULT_PAIRS', () => {
  it('has correct Ethereum USDC address', () => {
    expect(DEFAULT_PAIRS.ethereum.from).toBe('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48');
  });

  it('defaults all chains to USD', () => {
    expect(DEFAULT_PAIRS.ethereum.to).toBe('USD');
    expect(DEFAULT_PAIRS.arbitrum.to).toBe('USD');
    expect(DEFAULT_PAIRS.optimism.to).toBe('USD');
    expect(DEFAULT_PAIRS.base.to).toBe('USD');
  });

  it('has correct Arbitrum USDC address', () => {
    expect(DEFAULT_PAIRS.arbitrum.from).toBe('0xaf88d065e77c8cC2239327C5EDb3A432268e5831');
  });

  it('has correct Optimism USDC address', () => {
    expect(DEFAULT_PAIRS.optimism.from).toBe('0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85');
  });

  it('has correct Base USDC address', () => {
    expect(DEFAULT_PAIRS.base.from).toBe('0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913');
  });

  it('covers all four chains', () => {
    const chains = Object.keys(DEFAULT_PAIRS);
    expect(chains).toContain('ethereum');
    expect(chains).toContain('arbitrum');
    expect(chains).toContain('optimism');
    expect(chains).toContain('base');
  });
});

// ---------------------------------------------------------------------------
// CHAIN_IDS
// ---------------------------------------------------------------------------

describe('CHAIN_IDS', () => {
  it('maps ethereum to 1', () => {
    expect(CHAIN_IDS.ethereum).toBe(1);
  });

  it('maps arbitrum to 42161', () => {
    expect(CHAIN_IDS.arbitrum).toBe(42161);
  });

  it('maps optimism to 10', () => {
    expect(CHAIN_IDS.optimism).toBe(10);
  });

  it('maps base to 8453', () => {
    expect(CHAIN_IDS.base).toBe(8453);
  });
});

// ---------------------------------------------------------------------------
// countTokensForChain
// ---------------------------------------------------------------------------

describe('countTokensForChain', () => {
  it('counts tokens for the given chainId', () => {
    const tokens: TokenlistToken[] = [
      makeToken({ chainId: ETH, address: '0x0000000000000000000000000000000000000001', symbol: 'A' }),
      makeToken({ chainId: ETH, address: '0x0000000000000000000000000000000000000002', symbol: 'B' }),
      makeToken({ chainId: ARB, address: '0x0000000000000000000000000000000000000003', symbol: 'C' }),
    ];
    const list = makeList('L', tokens);
    expect(countTokensForChain(list, ETH)).toBe(2);
    expect(countTokensForChain(list, ARB)).toBe(1);
    expect(countTokensForChain(list, 999)).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// getListKey
// ---------------------------------------------------------------------------

describe('getListKey', () => {
  it('returns "default" for isDefault lists', () => {
    const list = makeList('Uniswap Default', [], true, { isDefault: true });
    expect(getListKey(list)).toBe('default');
  });

  it('returns "default" for isLocal lists', () => {
    const list = makeList('Local Tokens', [], true, { isLocal: true });
    expect(getListKey(list)).toBe('default');
  });

  it('returns url for user lists with a url', () => {
    const list = makeList('My List', [], true, { url: 'https://example.com/tokenlist.json' });
    expect(getListKey(list)).toBe('https://example.com/tokenlist.json');
  });

  it('returns name for user lists without a url', () => {
    const list = makeList('Unnamed List', []);
    expect(getListKey(list)).toBe('Unnamed List');
  });
});

// ---------------------------------------------------------------------------
// Custom pair management (getCustomPairs / saveCustomPair / resetCustomPair)
// ---------------------------------------------------------------------------

describe('getCustomPairs / saveCustomPair / resetCustomPair', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('returns empty object when localStorage has no entry', () => {
    expect(getCustomPairs()).toEqual({});
  });

  it('saves a custom pair and retrieves it', () => {
    saveCustomPair('ethereum', '0xFromAddr', '0xToAddr');
    const pairs = getCustomPairs();
    expect(pairs['ethereum']).toEqual({ from: '0xFromAddr', to: '0xToAddr' });
  });

  it('saves multiple chains independently', () => {
    saveCustomPair('ethereum', '0xEthFrom', '0xEthTo');
    saveCustomPair('arbitrum', '0xArbFrom', '0xArbTo');
    const pairs = getCustomPairs();
    expect(pairs['ethereum']).toEqual({ from: '0xEthFrom', to: '0xEthTo' });
    expect(pairs['arbitrum']).toEqual({ from: '0xArbFrom', to: '0xArbTo' });
  });

  it('overwrites an existing custom pair for the same chain', () => {
    saveCustomPair('ethereum', '0xOldFrom', '0xOldTo');
    saveCustomPair('ethereum', '0xNewFrom', '0xNewTo');
    const pairs = getCustomPairs();
    expect(pairs['ethereum']).toEqual({ from: '0xNewFrom', to: '0xNewTo' });
  });

  it('saves swapped pairs as long as the final pair is not identity', () => {
    saveCustomPair('ethereum', '0xToAddr', '0xFromAddr');
    const pairs = getCustomPairs();
    expect(pairs['ethereum']).toEqual({ from: '0xToAddr', to: '0xFromAddr' });
  });

  it('does not save identity pairs', () => {
    saveCustomPair('arbitrum', '0xABCDEF', '0xabcdef');
    expect(getCustomPairs()).toEqual({});
    expect(localStorage.getItem('defaultPairs')).toBeNull();
  });

  it('resetCustomPair removes a chain entry', () => {
    saveCustomPair('ethereum', '0xFromAddr', '0xToAddr');
    resetCustomPair('ethereum');
    const pairs = getCustomPairs();
    expect(pairs['ethereum']).toBeUndefined();
  });

  it('resetCustomPair on a non-existent chain does not throw', () => {
    expect(() => resetCustomPair('optimism')).not.toThrow();
  });

  it('returns empty object if localStorage contains malformed JSON', () => {
    localStorage.setItem('defaultPairs', 'NOT_JSON');
    expect(getCustomPairs()).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// getEffectivePair
// ---------------------------------------------------------------------------

describe('getEffectivePair', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('returns DEFAULT_PAIRS value when no custom pair is set', () => {
    const pair = getEffectivePair('ethereum');
    expect(pair).toEqual(DEFAULT_PAIRS.ethereum);
  });

  it('returns DEFAULT_PAIRS for each chain when no custom pairs set', () => {
    const chains = ['ethereum', 'arbitrum', 'optimism', 'base'] as const;
    for (const chain of chains) {
      expect(getEffectivePair(chain)).toEqual(DEFAULT_PAIRS[chain]);
    }
  });

  it('returns custom pair when one has been saved', () => {
    const custom = { from: '0xCustomFrom', to: '0xCustomTo' };
    saveCustomPair('ethereum', custom.from, custom.to);
    expect(getEffectivePair('ethereum')).toEqual(custom);
  });

  it('returns custom pair for one chain while others still return defaults', () => {
    saveCustomPair('arbitrum', '0xArbFrom', '0xArbTo');
    expect(getEffectivePair('arbitrum')).toEqual({ from: '0xArbFrom', to: '0xArbTo' });
    expect(getEffectivePair('ethereum')).toEqual(DEFAULT_PAIRS.ethereum);
  });

  it('falls back to default pair when stored custom pair is an identity pair', () => {
    localStorage.setItem(
      'defaultPairs',
      JSON.stringify({
        arbitrum: {
          from: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
          to: '0xAF88D065E77C8CC2239327C5EDB3A432268E5831',
        },
      })
    );

    expect(getEffectivePair('arbitrum')).toEqual(DEFAULT_PAIRS.arbitrum);
  });

  it('keeps using normal custom pairs when from and to differ', () => {
    localStorage.setItem(
      'defaultPairs',
      JSON.stringify({
        arbitrum: {
          from: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
          to: '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
        },
      })
    );

    expect(getEffectivePair('arbitrum')).toEqual({
      from: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
      to: '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
    });
  });

  it('returns a swapped custom pair unchanged when addresses differ', () => {
    localStorage.setItem(
      'defaultPairs',
      JSON.stringify({
        base: {
          from: '0x4200000000000000000000000000000000000006',
          to: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        },
      })
    );

    expect(getEffectivePair('base')).toEqual({
      from: '0x4200000000000000000000000000000000000006',
      to: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    });
  });

  it('returns default again after custom pair is reset', () => {
    saveCustomPair('ethereum', '0xCustomFrom', '0xCustomTo');
    resetCustomPair('ethereum');
    expect(getEffectivePair('ethereum')).toEqual(DEFAULT_PAIRS.ethereum);
  });
});
