"""§2 watchlist status-change alerts.

status_snapshot/diff_status are pure (easy to unit test); apply_watchlist_diffs
is the only impure piece, reading/writing the `watchlist` table.
"""
import json
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

# The fields tracked for change detection -- exactly what gets stored as the
# "snapshot" half of watchlist.last_known_status.
SnapshotDict = dict


def status_snapshot(row: dict) -> SnapshotDict:
    """row carries whatever the caller has on hand for one symbol's latest
    scan: tt_all_pass, tt_pass_count, stage_est, vcp_detected, vcp_breakout,
    close, vcp_pivot. below_pivot is derived here rather than stored
    separately in scan_results."""
    close = row.get("close")
    pivot = row.get("vcp_pivot")
    below_pivot = (close is not None and pivot is not None and close < pivot)
    return {
        "tt_all_pass": row.get("tt_all_pass"),
        "tt_pass_count": row.get("tt_pass_count"),
        "stage_est": row.get("stage_est"),
        "vcp_detected": row.get("vcp_detected"),
        "vcp_breakout": row.get("vcp_breakout"),
        "below_pivot": below_pivot,
    }


def diff_status(prev: SnapshotDict | None, curr: SnapshotDict) -> tuple[bool, str]:
    """No baseline yet (first-ever scan for this watchlist symbol) -> no
    change to report. Otherwise emit one human-readable note per
    meaningful transition; multiple transitions are joined with "; "."""
    if prev is None:
        return False, ""

    notes: list[str] = []

    prev_pass, curr_pass = prev.get("tt_all_pass"), curr.get("tt_all_pass")
    if prev_pass and not curr_pass:
        notes.append(
            f"lost Trend Template ({prev.get('tt_pass_count')}->{curr.get('tt_pass_count')})"
        )
    elif not prev_pass and curr_pass:
        notes.append(f"gained Trend Template ({curr.get('tt_pass_count')}/8)")
    elif prev.get("tt_pass_count") != curr.get("tt_pass_count"):
        notes.append(f"TT pass count {prev.get('tt_pass_count')}->{curr.get('tt_pass_count')}")

    prev_stage, curr_stage = prev.get("stage_est"), curr.get("stage_est")
    if prev_stage != curr_stage:
        notes.append(f"stage {prev_stage} -> {curr_stage}")

    prev_breakout, curr_breakout = prev.get("vcp_breakout"), curr.get("vcp_breakout")
    if not prev_breakout and curr_breakout:
        notes.append("broke out above pivot")
    elif prev_breakout and not curr_breakout:
        notes.append("no longer above pivot")

    prev_below, curr_below = prev.get("below_pivot"), curr.get("below_pivot")
    if not prev_below and curr_below:
        notes.append("closed back below pivot")

    if not notes:
        return False, ""
    return True, "; ".join(notes)


def apply_watchlist_diffs(engine: Engine, scan_date: date) -> None:
    with engine.begin() as conn:
        watch_rows = conn.execute(text("SELECT symbol, last_known_status FROM watchlist")).fetchall()

        for symbol, last_known_status_raw in watch_rows:
            scan_row = conn.execute(
                text("""
                    SELECT tt_all_pass, tt_pass_count, stage_est, vcp_detected,
                           vcp_breakout, vcp_pivot
                    FROM scan_results WHERE symbol = :symbol AND scan_date = :scan_date
                """),
                {"symbol": symbol, "scan_date": scan_date.isoformat()},
            ).fetchone()
            if scan_row is None:
                continue  # no scan for this symbol today -- nothing to diff

            close = conn.execute(
                text("SELECT close FROM prices WHERE symbol = :symbol ORDER BY date DESC LIMIT 1"),
                {"symbol": symbol},
            ).scalar()

            curr = status_snapshot({
                "tt_all_pass": bool(scan_row.tt_all_pass), "tt_pass_count": scan_row.tt_pass_count,
                "stage_est": scan_row.stage_est,
                "vcp_detected": bool(scan_row.vcp_detected) if scan_row.vcp_detected is not None else None,
                "vcp_breakout": bool(scan_row.vcp_breakout) if scan_row.vcp_breakout is not None else None,
                "close": close, "vcp_pivot": scan_row.vcp_pivot,
            })

            prev_wrapper = json.loads(last_known_status_raw) if last_known_status_raw else None
            prev_snapshot = prev_wrapper.get("snapshot") if prev_wrapper else None
            changed, change_note = diff_status(prev_snapshot, curr)

            conn.execute(
                text("UPDATE watchlist SET last_known_status = :status WHERE symbol = :symbol"),
                {
                    "symbol": symbol,
                    "status": json.dumps({
                        "snapshot": curr, "changed": changed, "change_note": change_note,
                    }),
                },
            )
