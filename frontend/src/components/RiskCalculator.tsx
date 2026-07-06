// components/RiskCalculator.tsx (CODE_BLUEPRINT.md §4/§5) -- pure client-side,
// no backend calls. Inputs: entry, shares, target?. Outputs: stop price, $
// risk, % risk, reward/risk. A calculator, not a recommendation.
//
// stopLossPct/stopLossCapPct default to the same values seeded in
// app/config.py (§7 stop_loss_pct=0.08, stop_loss_cap_pct=0.10). There's no
// GET /api/settings yet (that's Phase 5), so these are editable defaults
// rather than values read live from the backend -- once Phase 5 ships,
// wire these two inputs to the settings API instead of a hardcoded default.
import { useState } from "react";

const DEFAULT_STOP_LOSS_PCT = 0.08;
const DEFAULT_STOP_LOSS_CAP_PCT = 0.10;

interface Props {
  defaultEntry?: number | null;
}

export default function RiskCalculator({ defaultEntry }: Props) {
  const [entry, setEntry] = useState(defaultEntry ?? 0);
  const [shares, setShares] = useState(100);
  const [target, setTarget] = useState<number | "">("");
  const [stopLossPct, setStopLossPct] = useState(DEFAULT_STOP_LOSS_PCT);
  const [stopLossCapPct, setStopLossCapPct] = useState(DEFAULT_STOP_LOSS_CAP_PCT);

  const effectivePct = Math.min(stopLossPct, stopLossCapPct);
  const stopPrice = entry * (1 - effectivePct);
  const dollarRisk = (entry - stopPrice) * shares;
  const percentRisk = effectivePct * 100;
  const rewardRisk =
    target !== "" && entry > stopPrice ? (Number(target) - entry) / (entry - stopPrice) : null;

  return (
    <div className="risk-calculator">
      <p className="detail">Calculator, not a recommendation.</p>
      <label>
        Entry price
        <input
          type="number"
          value={entry}
          onChange={(e) => setEntry(Number(e.target.value))}
        />
      </label>
      <label>
        Shares
        <input
          type="number"
          value={shares}
          onChange={(e) => setShares(Number(e.target.value))}
        />
      </label>
      <label>
        Target price (optional)
        <input
          type="number"
          value={target}
          onChange={(e) => setTarget(e.target.value === "" ? "" : Number(e.target.value))}
        />
      </label>
      <label>
        Stop-loss %
        <input
          type="number"
          step="0.01"
          value={stopLossPct}
          onChange={(e) => setStopLossPct(Number(e.target.value))}
        />
      </label>
      <label>
        Stop-loss cap %
        <input
          type="number"
          step="0.01"
          value={stopLossCapPct}
          onChange={(e) => setStopLossCapPct(Number(e.target.value))}
        />
      </label>

      <table className="risk-output">
        <tbody>
          <tr>
            <td>Stop price</td>
            <td>{stopPrice.toFixed(2)}</td>
          </tr>
          <tr>
            <td>$ risk</td>
            <td>{dollarRisk.toFixed(2)}</td>
          </tr>
          <tr>
            <td>% risk</td>
            <td>{percentRisk.toFixed(2)}%</td>
          </tr>
          <tr>
            <td>Reward/risk</td>
            <td>{rewardRisk !== null ? rewardRisk.toFixed(2) : "—"}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
