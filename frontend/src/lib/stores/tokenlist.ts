import { writable } from 'svelte/store';
import type { TokenlistToken } from '../types';
import { DEFAULT_TOKENS } from './default-tokens';

// Re-export TokenlistToken for convenience
export type { TokenlistToken };

export type Chain = 'ethereum' | 'arbitrum' | 'optimism' | 'base';

export const CHAIN_IDS: Record<Chain, number> = {
  ethereum: 1,
  arbitrum: 42161,
  optimism: 10,
  base: 8453,
};

export interface TokenlistEntry {
  name: string;
  tokens: TokenlistToken[];
  url?: string;
  isDefault?: boolean;
  isLocal?: boolean;
  enabled: boolean;
  error?: string;
  timestamp?: string;
  version?: { major: number; minor: number; patch: number };
}

export const DEFAULT_PAIRS: Record<Chain, { from: string; to: string }> = {
  ethereum: {
    from: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    to: '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E',
  },
  arbitrum: {
    from: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
    to: '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
  },
  optimism: {
    from: '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85',
    to: '0x4200000000000000000000000000000000000006',
  },
  base: {
    from: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    to: '0x4200000000000000000000000000000000000006',
  },
};

// Built-in default pair tokens (always available in index)
const DEFAULT_PAIR_TOKENS: TokenlistToken[] = [
  {
    chainId: 1,
    address: '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E',
    symbol: 'crvUSD',
    name: 'Curve USD',
    decimals: 18,
  },
  {
    chainId: 1,
    address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6,
  },
  {
    chainId: 42161,
    address: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6,
  },
  {
    chainId: 42161,
    address: '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
    symbol: 'WETH',
    name: 'Wrapped Ether',
    decimals: 18,
  },
  {
    chainId: 10,
    address: '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85',
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6,
  },
  {
    chainId: 10,
    address: '0x4200000000000000000000000000000000000006',
    symbol: 'WETH',
    name: 'Wrapped Ether',
    decimals: 18,
  },
  {
    chainId: 8453,
    address: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6,
  },
  {
    chainId: 8453,
    address: '0x4200000000000000000000000000000000000006',
    symbol: 'WETH',
    name: 'Wrapped Ether',
    decimals: 18,
  },
];

// ---------------------------------------------------------------------------
// Internal module state
// ---------------------------------------------------------------------------

let _lists: TokenlistEntry[] = [];
let _tokenIndex: Map<number, Map<string, TokenlistToken & { sourceList: string }>> = new Map();
// User-added lists (persisted to localStorage)
let _userLists: TokenlistEntry[] = [];
// Local tokens (persisted to localStorage)
let _localTokens: TokenlistToken[] = [];

// ---------------------------------------------------------------------------
// Svelte stores for reactive subscribers
// ---------------------------------------------------------------------------

export const tokenIndex = writable(_tokenIndex);
export const allLists = writable<TokenlistEntry[]>([]);

// ---------------------------------------------------------------------------
// Pure logic helpers (no DOM / Svelte dependencies)
// ---------------------------------------------------------------------------

/**
 * Returns the stable key used to identify a list in persisted state.
 * Built-in / default lists use 'default'; user lists use url or name.
 */
export function getListKey(list: TokenlistEntry): string {
  if (list.isDefault || list.isLocal) return 'default';
  return list.url ?? list.name;
}

/**
 * Builds a chainId → (lowercaseAddress → token) index from all enabled lists.
 * First-list-wins deduplication.
 */
export function buildTokenIndex(
  lists: TokenlistEntry[]
): Map<number, Map<string, TokenlistToken & { sourceList: string }>> {
  const index = new Map<number, Map<string, TokenlistToken & { sourceList: string }>>();

  for (const list of lists) {
    if (!list.enabled) continue;
    const key = getListKey(list);
    for (const token of list.tokens) {
      const addrLower = token.address.toLowerCase();
      if (!index.has(token.chainId)) {
        index.set(token.chainId, new Map());
      }
      const chainMap = index.get(token.chainId)!;
      if (!chainMap.has(addrLower)) {
        chainMap.set(addrLower, { ...token, sourceList: key });
      }
    }
  }

  return index;
}

/**
 * Searches the token index for tokens matching `query` on a given chainId.
 * Returns at most 20 results ordered by relevance:
 *   exact symbol > symbol prefix > symbol contains > name contains > address prefix
 */
export function searchTokens(
  index: Map<number, Map<string, TokenlistToken & { sourceList: string }>>,
  query: string,
  chainId: number
): (TokenlistToken & { sourceList: string })[] {
  const chainMap = index.get(chainId);
  if (!chainMap || !query) return [];

  const q = query.toLowerCase();
  const results: Array<{ token: TokenlistToken & { sourceList: string }; rank: number }> = [];

  for (const token of chainMap.values()) {
    const symLower = token.symbol.toLowerCase();
    const nameLower = token.name.toLowerCase();
    const addrLower = token.address.toLowerCase();

    let rank = -1;
    if (symLower === q) {
      rank = 0;
    } else if (symLower.startsWith(q)) {
      rank = 1;
    } else if (symLower.includes(q)) {
      rank = 2;
    } else if (nameLower.includes(q)) {
      rank = 3;
    } else if (addrLower.startsWith(q)) {
      rank = 4;
    }

    if (rank >= 0) {
      results.push({ token, rank });
    }
  }

  results.sort((a, b) => a.rank - b.rank || a.token.symbol.localeCompare(b.token.symbol));

  return results.slice(0, 20).map((r) => r.token);
}

/**
 * Counts how many tokens in a list belong to the given chainId.
 */
export function countTokensForChain(list: TokenlistEntry, chainId: number): number {
  return list.tokens.filter((t) => t.chainId === chainId).length;
}

// ---------------------------------------------------------------------------
// localStorage helpers (thin wrappers - safe to call in browser or test env)
// ---------------------------------------------------------------------------

function readLocalStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocalStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // no-op in environments without localStorage
  }
}

function removeLocalStorageKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // no-op
  }
}

// ---------------------------------------------------------------------------
// Custom default pair management
// ---------------------------------------------------------------------------

export function getCustomPairs(): Record<string, { from: string; to: string }> {
  const raw = readLocalStorage('defaultPairs');
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, { from: string; to: string }>;
  } catch {
    return {};
  }
}

export function saveCustomPair(chain: string, from: string, to: string): void {
  const pairs = getCustomPairs();
  pairs[chain] = { from, to };
  writeLocalStorage('defaultPairs', JSON.stringify(pairs));
}

export function resetCustomPair(chain: string): void {
  const pairs = getCustomPairs();
  delete pairs[chain];
  writeLocalStorage('defaultPairs', JSON.stringify(pairs));
}

export function getEffectivePair(chain: Chain): { from: string; to: string } {
  const custom = getCustomPairs();
  return custom[chain] ?? DEFAULT_PAIRS[chain];
}

// ---------------------------------------------------------------------------
// Internal helpers to sync Svelte stores
// ---------------------------------------------------------------------------

function rebuildAndSync(): void {
  _tokenIndex = buildTokenIndex(_lists);
  tokenIndex.set(_tokenIndex);
  allLists.set([..._lists]);
}

function saveUserLists(): void {
  // Persist only non-default, non-local lists
  const toSave = _userLists.map(({ tokens: _t, ...rest }) => rest);
  writeLocalStorage('tokenlists', JSON.stringify(toSave));
}

function saveLocalTokens(): void {
  writeLocalStorage('localTokens', JSON.stringify(_localTokens));
}

function saveTokenlistStates(): void {
  const states: Record<string, boolean> = {};
  for (const list of _lists) {
    const key = getListKey(list);
    states[key] = list.enabled;
  }
  writeLocalStorage('tokenlistStates', JSON.stringify(states));
}

function loadTokenlistStates(): Record<string, boolean> {
  const raw = readLocalStorage('tokenlistStates');
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, boolean>;
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Async initialisation
// ---------------------------------------------------------------------------

export async function initTokenlists(): Promise<void> {
  const states = loadTokenlistStates();

  // 1. Hardcoded default tokenlist (common tokens per chain)
  const defaultList: TokenlistEntry = {
    name: 'Default Token List',
    tokens: DEFAULT_TOKENS,
    isDefault: true,
    enabled: states['default'] !== false, // default on unless explicitly disabled
  };

  // 2. Built-in default pair tokens list
  const builtinList: TokenlistEntry = {
    name: 'Default Pair Tokens',
    tokens: DEFAULT_PAIR_TOKENS,
    isLocal: true,
    enabled: true, // always enabled
  };

  // 3. Load user lists from localStorage
  const rawUserLists = readLocalStorage('tokenlists');
  let savedUserListMeta: Array<Omit<TokenlistEntry, 'tokens'>> = [];
  if (rawUserLists) {
    try {
      savedUserListMeta = JSON.parse(rawUserLists) as Array<Omit<TokenlistEntry, 'tokens'>>;
    } catch {
      savedUserListMeta = [];
    }
  }

  // Fetch each user list
  const userLists: TokenlistEntry[] = await Promise.all(
    savedUserListMeta.map(async (meta) => {
      if (!meta.url) {
        return { ...meta, tokens: [], enabled: states[meta.url ?? meta.name] ?? meta.enabled };
      }
      try {
        const resp = await fetch(meta.url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = (await resp.json()) as {
          name?: string;
          tokens: TokenlistToken[];
          timestamp?: string;
          version?: { major: number; minor: number; patch: number };
        };
        return {
          ...meta,
          name: data.name ?? meta.name,
          tokens: data.tokens ?? [],
          timestamp: data.timestamp,
          version: data.version,
          enabled: states[meta.url] !== undefined ? states[meta.url] : meta.enabled,
          error: undefined,
        };
      } catch (err) {
        return {
          ...meta,
          tokens: [],
          error: err instanceof Error ? err.message : 'Failed to fetch',
          enabled: states[meta.url ?? meta.name] !== undefined
            ? (states[meta.url ?? meta.name] ?? meta.enabled)
            : meta.enabled,
        };
      }
    })
  );
  _userLists = userLists;

  // 4. Load local tokens from localStorage
  const rawLocal = readLocalStorage('localTokens');
  if (rawLocal) {
    try {
      _localTokens = JSON.parse(rawLocal) as TokenlistToken[];
    } catch {
      _localTokens = [];
    }
  }

  const localTokensList: TokenlistEntry = {
    name: 'Local Tokens',
    tokens: _localTokens,
    isLocal: true,
    enabled: true,
  };

  // Assemble full list (default first for first-list-wins dedup)
  _lists = [defaultList, builtinList, ...userLists, localTokensList];

  rebuildAndSync();
}

// ---------------------------------------------------------------------------
// Mutation functions
// ---------------------------------------------------------------------------

export function toggleList(key: string): void {
  for (const list of _lists) {
    if (getListKey(list) === key) {
      list.enabled = !list.enabled;
      break;
    }
  }
  saveTokenlistStates();
  rebuildAndSync();
}

export function addList(list: TokenlistEntry): void {
  _userLists.push(list);
  // Insert before the local tokens list (last item)
  _lists.splice(_lists.length - 1, 0, list);
  saveUserLists();
  rebuildAndSync();
}

export function removeList(index: number): void {
  if (index < 0 || index >= _lists.length) return;
  const removed = _lists[index];
  _lists.splice(index, 1);

  // Remove from _userLists if present
  const userIdx = _userLists.indexOf(removed);
  if (userIdx >= 0) {
    _userLists.splice(userIdx, 1);
  }
  saveUserLists();

  // If the removed list was the source of a custom pair, revert those pairs
  const removedKey = getListKey(removed);
  if (removedKey !== 'default') {
    const chains = Object.keys(CHAIN_IDS) as Chain[];
    for (const chain of chains) {
      const custom = getCustomPairs();
      if (custom[chain]) {
        // Check if either token in the custom pair came solely from this list
        const fromAddr = custom[chain].from.toLowerCase();
        const toAddr = custom[chain].to.toLowerCase();
        const chainId = CHAIN_IDS[chain];

        // Build a temporary index without the removed list
        const tempIndex = buildTokenIndex(_lists);
        const chainMap = tempIndex.get(chainId);
        const fromPresent = chainMap?.has(fromAddr);
        const toPresent = chainMap?.has(toAddr);

        if (!fromPresent || !toPresent) {
          resetCustomPair(chain);
        }
      }
    }
  }

  rebuildAndSync();
}

export function addLocalToken(token: TokenlistToken): void {
  _localTokens.push(token);
  // Update the local tokens list entry (last item in _lists is localTokensList)
  const localEntry = _lists.find((l) => l.isLocal && l.name === 'Local Tokens');
  if (localEntry) {
    localEntry.tokens = [..._localTokens];
  }
  saveLocalTokens();
  rebuildAndSync();
}

export function isTokenInIndex(address: string, chainId: number): boolean {
  const chainMap = _tokenIndex.get(chainId);
  return chainMap?.has(address.toLowerCase()) ?? false;
}

export function getTokenFromIndex(
  address: string,
  chainId: number
): (TokenlistToken & { sourceList: string }) | undefined {
  const chainMap = _tokenIndex.get(chainId);
  return chainMap?.get(address.toLowerCase());
}
