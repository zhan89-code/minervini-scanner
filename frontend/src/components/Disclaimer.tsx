// components/Disclaimer.tsx (CODE_BLUEPRINT.md §4/§7) -- persistent banner.
// Disclaimers are static UI copy, not API fields (§3).
export default function Disclaimer() {
  return (
    <p className="disclaimer">
      Screening tool based on one methodology, not financial advice. Data is
      end-of-day, refreshed nightly -- not an intraday trading tool. Stage
      and VCP detections are heuristic approximations; confirm visually
      against the chart before trusting them.
    </p>
  );
}
