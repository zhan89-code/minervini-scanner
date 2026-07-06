// components/TrendHistory.tsx (CODE_BLUEPRINT.md §4/§2) -- dated timeline of
// whether/when a stock passed the Trend Template. Embedded in StockDetail.
import { useQuery } from "@tanstack/react-query";
import { fetchStockHistory } from "../api";

export default function TrendHistory({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stock-history", symbol],
    queryFn: () => fetchStockHistory(symbol),
  });

  if (isLoading) return <p className="loading">Loading history…</p>;
  if (isError || !data) return <p className="loading">Failed to load history.</p>;
  if (data.rows.length === 0) return <p className="empty-state">No scan history yet for {symbol}.</p>;

  return (
    <div className="table-card">
      <table className="trend-history">
        <thead>
          <tr>
            <th>Date</th>
            <th>TT Pass</th>
            <th>Stage 2</th>
            <th>RS %ile</th>
            <th>Stage</th>
            <th>VCP</th>
            <th>Composite</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.scan_date}>
              <td className="detail">{row.scan_date}</td>
              <td>{row.tt_pass_count ?? "—"}/8</td>
              <td>{row.tt_all_pass ? "Yes" : "No"}</td>
              <td>{row.rs_percentile ?? "—"}</td>
              <td>{row.stage_est ?? "—"}</td>
              <td>{row.vcp_detected === null ? "—" : row.vcp_detected ? "Yes" : "No"}</td>
              <td>{row.composite?.toFixed(1) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
