export interface PriceResponse {
  price: number | null;
  block: number;
  timestamp: number;
  cached: boolean;
  chain: string;
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
  source: string;
  input_token: string;
  output_token: string;
  pool: string;
  price: number;
}

export interface QuoteResponse {
  from: string;
  to: string;
  amount: number;
  output_amount: number;
  block: number;
  chain: string;
  block_timestamp: number | null;
  route: string;
  from_price: number;
  to_price: number;
  from_trade_path: TradeStep[] | null;
  to_trade_path: TradeStep[] | null;
}

export interface BucketResponse {
  bucket: string | null;
  token: string;
  chain: string;
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
