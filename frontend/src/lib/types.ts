export interface PriceResponse {
  token: string;
  price: number | null;
  block: number;
  chain: string;
  block_timestamp: number | null;
  cached: boolean;
  trade_path: TradeStep[] | null;
}
export interface BatchPriceItem {
  token: string;
  price: number | null;
  block: number;
  timestamp: number;
  cached: boolean;
}

export interface BatchPriceResponse {
  prices: BatchPriceItem[];
  chain: string;
}

export interface TradeStep {
  token: string;
  price: number;
  source: string;
}



export interface BucketResponse {
  bucket: string | null;
  token: string;
  chain: string;
  /** ERC-20 token symbol, present when backend metadata fetch succeeds */
  symbol?: string;
  /** ERC-20 token name, present when backend metadata fetch succeeds */
  name?: string;
  /** ERC-20 token decimals, present when backend metadata fetch succeeds */
  decimals?: number;
}

export interface HealthResponse {
  status: string;
  chain: string;
  block?: number;
  synced?: boolean | null;
  error?: string;
}

export interface TokenlistToken {
  chainId: number;
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  logoURI?: string;
}

export interface Tokenlist {
  name: string;
  tokens: TokenlistToken[];
  url?: string;
  timestamp?: string;
  version?: { major: number; minor: number; patch: number };
}
