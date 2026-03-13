import type {
  QuoteResponse,
  BatchPriceResponse,
  BucketResponse,
  HealthResponse,
  Tokenlist,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const FETCH_TIMEOUT_MS = 300_000;

function fetchWithTimeout(
  url: string,
  timeoutMs = FETCH_TIMEOUT_MS,
  signal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }
  return fetch(url, { signal: controller.signal }).finally(() => clearTimeout(id));
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message: string;
    try {
      const body = await res.json();
      message = body?.detail ?? body?.error ?? JSON.stringify(body);
    } catch {
      message = await res.text().catch(() => res.statusText);
    }
    throw new Error(`HTTP ${res.status}: ${message}`);
  }
  try {
    return await res.json() as T;
  } catch {
    const text = await res.text().catch(() => '');
    throw new Error(`Expected JSON response but got: ${text.slice(0, 100)}`);
  }
}

export async function fetchQuote(
  chain: string,
  from: string,
  to: string,
  block?: string,
  amount?: string,
  signal?: AbortSignal,
): Promise<QuoteResponse> {
  const params = new URLSearchParams({ token: from, to });
  if (block) params.set('block', block);
  if (amount) params.set('amount', amount);
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/price?${params}`, FETCH_TIMEOUT_MS, signal);
  return parseResponse<QuoteResponse>(res);
}

export async function fetchPrice(
  chain: string,
  token: string,
  block?: string,
  signal?: AbortSignal,
  amount?: string,
): Promise<QuoteResponse> {
  const params = new URLSearchParams({ token });
  if (block) params.set('block', block);
  if (amount) params.set('amount', amount);
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/price?${params}`, FETCH_TIMEOUT_MS, signal);
  return parseResponse<QuoteResponse>(res);
}

export async function fetchBatchPrices(
  chain: string,
  tokens: string[],
  block?: string,
  amounts?: string[],
  signal?: AbortSignal,
): Promise<BatchPriceResponse> {
  const params = new URLSearchParams();
  for (const t of tokens) params.append('token', t);
  if (block) params.set('block', block);
  if (amounts) {
    for (const a of amounts) params.append('amount', a);
  }
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/prices?${params}`, FETCH_TIMEOUT_MS, signal);
  return parseResponse<BatchPriceResponse>(res);
}

export async function fetchBucket(
  chain: string,
  token: string,
  signal?: AbortSignal,
): Promise<BucketResponse> {
  const params = new URLSearchParams({ token });
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/bucket?${params}`, FETCH_TIMEOUT_MS, signal);
  return parseResponse<BucketResponse>(res);
}

export async function fetchHealth(
  chain: string,
  signal?: AbortSignal,
): Promise<HealthResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/health`, FETCH_TIMEOUT_MS, signal);
  return parseResponse<HealthResponse>(res);
}

export async function fetchTokenlist(_chain: string, url: string): Promise<Tokenlist> {
  const res = await fetchWithTimeout(url);
  return parseResponse<Tokenlist>(res);
}
