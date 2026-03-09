import type {
  QuoteResponse,
  PriceResponse,
  BatchPriceResponse,
  BucketResponse,
  HealthResponse,
  Tokenlist,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const FETCH_TIMEOUT_MS = 30_000;

function fetchWithTimeout(url: string, timeoutMs = FETCH_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
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
  return res.json() as Promise<T>;
}

export async function fetchQuote(
  chain: string,
  from: string,
  to: string,
  block?: string,
  amount?: string,
): Promise<QuoteResponse> {
  const params = new URLSearchParams({ token: from, to });
  if (block) params.set('block', block);
  if (amount) params.set('amount', amount);
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/price?${params}`);
  return parseResponse<QuoteResponse>(res);
}

export async function fetchPrice(
  chain: string,
  token: string,
  block?: string,
): Promise<PriceResponse> {
  const params = new URLSearchParams({ token });
  if (block) params.set('block', block);
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/price?${params}`);
  return parseResponse<PriceResponse>(res);
}

export async function fetchBatchPrices(
  chain: string,
  tokens: string[],
  block?: string,
  amounts?: string[],
): Promise<BatchPriceResponse> {
  const params = new URLSearchParams();
  for (const t of tokens) params.append('token', t);
  if (block) params.set('block', block);
  if (amounts) {
    for (const a of amounts) params.append('amount', a);
  }
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/prices?${params}`);
  return parseResponse<BatchPriceResponse>(res);
}

export async function fetchBucket(chain: string, token: string): Promise<BucketResponse> {
  const params = new URLSearchParams({ token });
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/bucket?${params}`);
  return parseResponse<BucketResponse>(res);
}

export async function fetchHealth(chain: string): Promise<HealthResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/health`);
  return parseResponse<HealthResponse>(res);
}

export async function fetchTokenlistProxy(chain: string, url: string): Promise<Tokenlist> {
  const params = new URLSearchParams({ url });
  const res = await fetchWithTimeout(`${BASE_URL}/${chain}/tokenlist/proxy?${params}`);
  return parseResponse<Tokenlist>(res);
}
