// pages/Watchlist.tsx (CODE_BLUEPRINT.md §4) -- list + change flags.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchWatchlist, removeFromWatchlist } from "../api";

export default function Watchlist() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["watchlist"],
    queryFn: fetchWatchlist,
  });

  const handleRemove = async (symbol: string) => {
    await removeFromWatchlist(symbol);
    queryClient.invalidateQueries({ queryKey: ["watchlist"] });
  };

  if (isLoading) return <p className="loading">Loading watchlist…</p>;
  if (isError || !data) return <p className="loading">Failed to load watchlist.</p>;

  return (
    <div>
      <h2>Watchlist</h2>
      {data.items.length === 0 ? (
        <p className="empty-state">
          No symbols on your watchlist yet. Add one from the scan table or a stock's detail page.
        </p>
      ) : (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Added</th>
                <th>Status change</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.symbol}>
                  <td>
                    <Link to={`/stock/${item.symbol}`} className="symbol">{item.symbol}</Link>
                  </td>
                  <td className="detail">{item.added_at.slice(0, 10)}</td>
                  <td className={item.changed ? "watchlist-changed" : "detail"}>
                    {item.changed ? item.change_note : "no change"}
                  </td>
                  <td>
                    <button type="button" className="btn-ghost" onClick={() => handleRemove(item.symbol)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
