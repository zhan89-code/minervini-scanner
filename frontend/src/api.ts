// Phase 1 API client (CODE_BLUEPRINT.md §3). Later-phase fields on ScanRow
// come back as null until their phase lands -- see the §3 Phase note.
//
// VITE_API_BASE lets a deployed build (e.g. on Vercel) point at a hosted
// backend instead of localhost -- set it in the deployment's env vars.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface MetaResponse {
  last_run: string | null;
  status: "ok" | "partial" | "failed" | "unknown";
  universe_size: number;
}

export interface ScanRow {
  symbol: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  tt_pass_count: number | null;
  tt_all_pass: boolean;
  rs_percentile: number | null;
  stage_est: number | null;
  stage_conf: string | null;
  eps_yoy: number | null;
  rev_yoy: number | null;
  industry_strength: string | null;
  catalyst: string | null;
  catalyst_state: string | null;
  near_earnings: boolean | null;
  earnings_risk_state: string | null;
  vcp_detected: boolean | null;
  vcp_footprint: string | null;
  vcp_breakout: boolean | null;
  composite: number | null;
}

export interface ScanResponse {
  as_of: string | null;
  rows: ScanRow[];
}

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await fetch(`${API_BASE}/api/meta`);
  if (!res.ok) throw new Error(`GET /api/meta failed: ${res.status}`);
  return res.json();
}

export async function fetchScan(): Promise<ScanResponse> {
  const res = await fetch(`${API_BASE}/api/scan`);
  if (!res.ok) throw new Error(`GET /api/scan failed: ${res.status}`);
  return res.json();
}

// Phase 2 additions (CODE_BLUEPRINT.md §3): stock detail + historical check.

export interface Criterion {
  state: "pass" | "fail" | "unknown";
  value: number | null;
  detail: string;
}

export interface PricePoint {
  date: string;
  o: number | null;
  h: number | null;
  l: number | null;
  c: number | null;
  v: number | null;
}

export interface VcpLeg {
  depth_pct: number;
  avg_vol: number;
  hi: number;
  lo: number;
  start: string;
  end: string;
}

export interface StockDetailResponse {
  symbol: string;
  as_of: string | null;
  trend_template: Record<string, Criterion>;
  stage: { est: number | null; conf: string | null };
  rs_percentile: number | null;
  fundamentals: Record<string, Criterion>;
  vcp: {
    detected: boolean | null;
    footprint: string | null;
    pivot: number | null;
    legs: VcpLeg[] | null;
    breakout: boolean | null;
  };
  prices: PricePoint[];
  next_earnings_date: string | null;
  near_earnings: boolean | null;
  earnings_risk_state: string | null;
}

export interface StockHistoryRow {
  scan_date: string;
  tt_pass_count: number | null;
  tt_all_pass: boolean;
  rs_percentile: number | null;
  stage_est: number | null;
  vcp_detected: boolean | null;
  vcp_breakout: boolean | null;
  composite: number | null;
}

export interface StockHistoryResponse {
  symbol: string;
  rows: StockHistoryRow[];
}

export async function fetchStock(symbol: string): Promise<StockDetailResponse> {
  const res = await fetch(`${API_BASE}/api/stock/${symbol}`);
  if (!res.ok) throw new Error(`GET /api/stock/${symbol} failed: ${res.status}`);
  return res.json();
}

export async function fetchStockHistory(symbol: string): Promise<StockHistoryResponse> {
  const res = await fetch(`${API_BASE}/api/stock/${symbol}/history`);
  if (!res.ok) throw new Error(`GET /api/stock/${symbol}/history failed: ${res.status}`);
  return res.json();
}

// Phase 5 additions (CODE_BLUEPRINT.md §3): watchlist + settings.

export interface WatchlistItem {
  symbol: string;
  added_at: string;
  changed: boolean;
  change_note: string;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
}

export async function fetchWatchlist(): Promise<WatchlistResponse> {
  const res = await fetch(`${API_BASE}/api/watchlist`);
  if (!res.ok) throw new Error(`GET /api/watchlist failed: ${res.status}`);
  return res.json();
}

export async function addToWatchlist(symbol: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  if (!res.ok) throw new Error(`POST /api/watchlist failed: ${res.status}`);
}

export async function removeFromWatchlist(symbol: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/watchlist/${symbol}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /api/watchlist/${symbol} failed: ${res.status}`);
}

export interface SettingValue {
  value: unknown;
  type: "float" | "int" | "str" | "list" | "object";
}

export type SettingsResponse = Record<string, SettingValue>;

export async function fetchSettings(): Promise<SettingsResponse> {
  const res = await fetch(`${API_BASE}/api/settings`);
  if (!res.ok) throw new Error(`GET /api/settings failed: ${res.status}`);
  return res.json();
}

export async function updateSettings(
  changes: Record<string, unknown>
): Promise<SettingsResponse> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `PUT /api/settings failed: ${res.status}`);
  }
  return res.json();
}
