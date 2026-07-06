// components/Badge.tsx -- shared pass/fail/unknown (and generic) badge used
// across TrendChecklist, ScanTable, StockDetail fundamentals, etc.
import type { ReactNode } from "react";

type BadgeState = "pass" | "fail" | "unknown" | "neutral";

const STATE_CLASS: Record<BadgeState, string> = {
  pass: "badge badge-pass",
  fail: "badge badge-fail",
  unknown: "badge badge-unknown",
  neutral: "badge badge-neutral",
};

export default function Badge({ state, children }: { state: BadgeState; children: ReactNode }) {
  return <span className={STATE_CLASS[state]}>{children}</span>;
}
