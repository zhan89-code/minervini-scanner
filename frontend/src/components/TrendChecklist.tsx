// components/TrendChecklist.tsx (CODE_BLUEPRINT.md §4) -- renders the 8-point
// Trend Template as pass/fail/unknown per line, with the "why" detail string.
import type { Criterion } from "../api";
import Badge from "./Badge";

const LABELS: Record<string, string> = {
  "1": "Close > SMA150 and SMA200",
  "2": "SMA150 > SMA200",
  "3": "SMA200 trending up (1mo+)",
  "4": "SMA50 > SMA150 and SMA200",
  "5": "Close > SMA50",
  "6": "Close >= 1.30x 52-week low",
  "7": "Close >= 0.75x 52-week high",
  "8": "RS percentile >= threshold (proxy, not official IBD rating)",
};

export default function TrendChecklist({ criteria }: { criteria: Record<string, Criterion> }) {
  const keys = Object.keys(criteria).sort((a, b) => Number(a) - Number(b));
  return (
    <table className="trend-checklist">
      <tbody>
        {keys.map((key) => {
          const c = criteria[key];
          return (
            <tr key={key}>
              <td className="tc-index">{key}</td>
              <td>{LABELS[key] ?? key}</td>
              <td><Badge state={c.state}>{c.state.toUpperCase()}</Badge></td>
              <td className="detail">{c.detail}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
