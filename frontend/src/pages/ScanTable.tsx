// pages/ScanTable.tsx (CODE_BLUEPRINT.md §4) -- TanStack Table over
// GET /api/scan; "data as of" from GET /api/meta. Row click -> /stock/:symbol.
// Later-phase columns render "—" until their phase populates them.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { addToWatchlist, fetchMeta, fetchScan, fetchWatchlist, type ScanRow } from "../api";
import Badge from "../components/Badge";

const columnHelper = createColumnHelper<ScanRow>();

const columns = [
  columnHelper.accessor("symbol", {
    header: "Symbol",
    cell: (info) => <span className="symbol">{info.getValue()}</span>,
  }),
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("sector", {
    header: "Sector",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("tt_pass_count", {
    header: "TT Pass",
    cell: (info) => (
      <span className="tt-pass-cell">
        <span className="tt-pass-bar">
          <span
            className="tt-pass-fill"
            style={{ width: `${((info.getValue() ?? 0) / 8) * 100}%` }}
          />
        </span>
        {info.getValue() ?? 0}/8
      </span>
    ),
  }),
  columnHelper.accessor("tt_all_pass", {
    header: "Stage 2 Candidate",
    cell: (info) => (
      <Badge state={info.getValue() ? "pass" : "neutral"}>{info.getValue() ? "Yes" : "No"}</Badge>
    ),
  }),
  columnHelper.accessor("rs_percentile", {
    header: "RS %ile",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("stage_est", {
    header: "Stage",
    cell: (info) => {
      const row = info.row.original;
      if (info.getValue() === null) return "—";
      return `${info.getValue()} (${row.stage_conf ?? "?"})`;
    },
  }),
  columnHelper.accessor("earnings_risk_state", {
    header: "Earnings Risk",
    cell: (info) => {
      const state = info.getValue();
      if (!state) return "—";
      return <Badge state={state === "pass" ? "pass" : state === "fail" ? "fail" : "unknown"}>{state.toUpperCase()}</Badge>;
    },
  }),
  columnHelper.accessor("composite", {
    header: "Composite",
    cell: (info) => info.getValue()?.toFixed(1) ?? "—",
  }),
];

export default function ScanTable() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([
    { id: "tt_pass_count", desc: true },
  ]);

  const metaQuery = useQuery({ queryKey: ["meta"], queryFn: fetchMeta });
  const scanQuery = useQuery({ queryKey: ["scan"], queryFn: fetchScan });
  const watchlistQuery = useQuery({ queryKey: ["watchlist"], queryFn: fetchWatchlist });

  const watchlistSymbols = new Set(watchlistQuery.data?.items.map((item) => item.symbol) ?? []);

  const handleAdd = async (e: React.MouseEvent, symbol: string) => {
    e.stopPropagation();
    await addToWatchlist(symbol);
    queryClient.invalidateQueries({ queryKey: ["watchlist"] });
  };

  const table = useReactTable({
    data: scanQuery.data?.rows ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (scanQuery.isLoading) return <p className="loading">Loading scan…</p>;
  if (scanQuery.isError) return <p className="loading">Failed to load scan results.</p>;

  return (
    <div>
      <div className="scan-toolbar">
        <p className="data-as-of">
          Data as of: {scanQuery.data?.as_of ?? "no scan run yet"}
          {" · "}
          Universe: {metaQuery.data?.universe_size ?? "—"}
          {" · "}
          Last run status:{" "}
          <Badge state={metaQuery.data?.status === "ok" ? "pass" : metaQuery.data?.status === "partial" ? "unknown" : "neutral"}>
            {metaQuery.data?.status ?? "—"}
          </Badge>
        </p>
      </div>
      <div className="table-card">
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  style={{ cursor: "pointer" }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {{ asc: " ▲", desc: " ▼" }[header.column.getIsSorted() as string] ?? ""}
                </th>
              ))}
              <th></th>
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              onClick={() => navigate(`/stock/${row.original.symbol}`)}
              style={{ cursor: "pointer" }}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
              <td>
                {watchlistSymbols.has(row.original.symbol) ? (
                  "On watchlist"
                ) : (
                  <button type="button" className="btn-ghost" onClick={(e) => handleAdd(e, row.original.symbol)}>
                    + Watchlist
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
