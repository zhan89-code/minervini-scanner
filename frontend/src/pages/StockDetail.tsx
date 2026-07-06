// pages/StockDetail.tsx (CODE_BLUEPRINT.md §4) -- GET /api/stock/:symbol.
// Shows a near-earnings warning badge when earnings_risk_state == "fail"
// ("don't buy right before earnings", §3.3/§5).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { addToWatchlist, fetchStock, fetchWatchlist, removeFromWatchlist } from "../api";
import Badge from "../components/Badge";
import PriceChart from "../components/PriceChart";
import RiskCalculator from "../components/RiskCalculator";
import TrendChecklist from "../components/TrendChecklist";
import TrendHistory from "../components/TrendHistory";

const FUND_LABELS: Record<string, string> = {
  eps_yoy: "EPS growth YoY",
  eps_accel: "EPS growth accelerating",
  rev_yoy: "Revenue growth YoY",
  rev_accel: "Revenue growth accelerating",
  margin_trend: "Margin trend",
  catalyst: "Catalyst",
  industry_strength: "Industry group strength",
};

export default function StockDetail() {
  const { symbol = "" } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["stock", symbol],
    queryFn: () => fetchStock(symbol),
  });
  const watchlistQuery = useQuery({ queryKey: ["watchlist"], queryFn: fetchWatchlist });

  if (isLoading) return <p className="loading">Loading {symbol}…</p>;
  if (isError || !data) return <p className="loading">{(error as Error)?.message ?? `Failed to load ${symbol}.`}</p>;

  const onWatchlist = watchlistQuery.data?.items.some((item) => item.symbol === symbol) ?? false;
  const lastClose = data.prices.at(-1)?.c ?? null;
  const ttPassCount = Object.values(data.trend_template).filter((c) => c.state === "pass").length;

  const toggleWatchlist = async () => {
    if (onWatchlist) {
      await removeFromWatchlist(symbol);
    } else {
      await addToWatchlist(symbol);
    }
    queryClient.invalidateQueries({ queryKey: ["watchlist"] });
  };

  return (
    <div>
      <p><Link to="/">&larr; back to scan</Link></p>

      <div className="detail-header">
        <div>
          <h2>{data.symbol}</h2>
          <p className="data-as-of">Data as of: {data.as_of ?? "no scan run yet"}</p>
        </div>
        <div className="detail-header-right">
          {lastClose !== null && <span className="last-price">{lastClose.toFixed(2)}</span>}
          <button type="button" onClick={toggleWatchlist}>
            {onWatchlist ? "Remove from watchlist" : "+ Add to watchlist"}
          </button>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-label">Trend Template</span>
          <span className="stat-value">{ttPassCount}/8</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">RS percentile</span>
          <span className="stat-value">{data.rs_percentile ?? "—"}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Stage</span>
          <span className="stat-value">{data.stage.est ?? "—"}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">VCP</span>
          <span className="stat-value">{data.vcp.detected ? "Yes" : "No"}</span>
        </div>
      </div>

      {data.earnings_risk_state === "fail" && (
        <p className="earnings-warning">
          Next earnings {data.next_earnings_date} -- inside the blackout window.
          Don't buy right before earnings.
        </p>
      )}

      <h3>Trend Template</h3>
      <div className="table-card">
        <TrendChecklist criteria={data.trend_template} />
      </div>

      <h3>Stage</h3>
      <p className="detail">
        {data.stage.est ? `Stage ${data.stage.est}` : "Unknown"}
        {data.stage.conf ? ` (${data.stage.conf})` : ""}
        {" -- heuristic, confirm visually against the chart below."}
      </p>

      <h3>Fundamentals</h3>
      <div className="table-card">
        <table className="fundamentals">
          <tbody>
            {Object.entries(FUND_LABELS).map(([key, label]) => {
              const c = data.fundamentals[key];
              return (
                <tr key={key}>
                  <td>{label}</td>
                  <td><Badge state={c?.state ?? "unknown"}>{(c?.state ?? "unknown").toUpperCase()}</Badge></td>
                  <td className="detail">{c?.detail ?? ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h3>VCP / base</h3>
      <p className="detail">
        {data.vcp.detected
          ? `${data.vcp.footprint} -- pivot ${data.vcp.pivot?.toFixed(2)}${
              data.vcp.breakout ? " (breakout confirmed)" : ""
            }`
          : "No base detected"}
        {" -- heuristic, expect false positives/negatives; confirm visually."}
      </p>

      <h3>Price</h3>
      <div className="chart-card">
        <PriceChart prices={data.prices} pivot={data.vcp.pivot} legs={data.vcp.legs} />
      </div>

      <h3>Risk calculator</h3>
      <RiskCalculator defaultEntry={lastClose} />

      <h3>Trend Template history</h3>
      <TrendHistory symbol={data.symbol} />
    </div>
  );
}
