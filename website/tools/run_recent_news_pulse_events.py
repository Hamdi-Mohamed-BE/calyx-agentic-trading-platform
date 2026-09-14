from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

from app.catalog import PACKAGE_ROOT, get_product  # noqa: E402
from app.mt5_evidence_jobs import mt5_evidence_jobs  # noqa: E402


OUTPUT_ROOT = PACKAGE_ROOT / "News Pulse Event Replay 2026-09-11"
TOP_THREE = ("news-pulse-xag", "news-pulse-btc", "news-pulse-xau")
EVENTS = (
    {
        "id": "nfp-2026-09-04",
        "label": "NFP — 2026-09-04 12:30 UTC",
        "kind": "NFP",
        "event_epoch": 1788525000,
        "start": date(2026, 9, 1),
        "tester_end": date(2026, 9, 7),
        "calendar_end": date(2026, 9, 7),
    },
    {
        "id": "cpi-2026-09-11",
        "label": "CPI — 2026-09-11 12:30 UTC",
        "kind": "CPI",
        "event_epoch": 1789129800,
        "start": date(2026, 9, 5),
        # MT5's tester end date is exclusive.  Use the following midnight so
        # the release day can be replayed, while keeping the EA's generated
        # calendar gate on the actual inclusive coverage date.
        "tester_end": date(2026, 9, 12),
        "calendar_end": date(2026, 9, 11),
    },
)


def _on_tester_result(report: Path) -> float | None:
    raw = report.read_bytes()
    text = raw.decode("utf-16", errors="ignore") if raw[:200].count(b"\x00") > 20 else raw.decode("utf-8", errors="ignore")
    match = re.search(r"OnTester result:</td>\s*<td[^>]*><b>([-+0-9.,]+)</b>", text, re.IGNORECASE)
    return float(match.group(1).replace(",", "")) if match else None


def _run(slug: str, event: dict[str, Any]) -> dict[str, Any]:
    product = get_product(slug)
    if product is None:
        raise RuntimeError(f"Unknown product: {slug}")
    overrides = {
        "InpTesterFromDateUTC": event["start"].strftime("%Y%m%d"),
        "InpTesterToDateUTC": event["calendar_end"].strftime("%Y%m%d"),
    }
    job = mt5_evidence_jobs.start(
        slug,
        "standard",
        event["start"],
        event["tester_end"],
        product.canonical,
        input_overrides=overrides,
    )
    while job["status"] in {"queued", "running"}:
        time.sleep(1)
        job = mt5_evidence_jobs.get(str(job["id"])) or job
    if job["status"] != "completed":
        raise RuntimeError(str(job.get("error") or f"Recent event run failed: {slug}"))
    result = dict(job["result"])
    report = mt5_evidence_jobs.output_root / slug / "latest.htm"
    processed_events = _on_tester_result(report) if report.is_file() else None
    if processed_events != 1.0:
        raise RuntimeError(f"{product.label} processed {processed_events} target events; expected exactly 1")
    reports = OUTPUT_ROOT / "reports" / str(event["id"])
    reports.mkdir(parents=True, exist_ok=True)
    retained = reports / f"{slug}.htm"
    shutil.copy2(report, retained)
    trades = list(result.get("trades", []))
    commission = round(sum(float(row.get("commission") or 0.0) for row in trades), 2)
    swap = round(sum(float(row.get("swap") or 0.0) for row in trades), 2)
    return {
        "event": event["id"],
        "event_label": event["label"],
        "event_kind": event["kind"],
        "event_epoch": event["event_epoch"],
        "slug": slug,
        "label": product.label,
        "symbol": product.canonical,
        "period": f"{event['start'].isoformat()} to {event['calendar_end'].isoformat()}",
        "processed_events": int(processed_events),
        "stats": {
            **result["stats"],
            "commission": commission,
            "swap": swap,
            "total_costs": round(commission + swap, 2),
        },
        "trades": trades,
        "report": str(retained),
    }


def _unavailable_row(slug: str, event: dict[str, Any], error: Exception) -> dict[str, Any]:
    product = get_product(slug)
    return {
        "event": event["id"],
        "event_label": event["label"],
        "event_kind": event["kind"],
        "event_epoch": event["event_epoch"],
        "slug": slug,
        "label": product.label if product else slug,
        "symbol": product.canonical if product else "",
        "period": f"{event['start'].isoformat()} to {event['calendar_end'].isoformat()}",
        "status": "unavailable",
        "reason": str(error),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay the two most recent official News Pulse events")
    parser.add_argument("--event", choices=("all", "nfp", "cpi"), default="all")
    args = parser.parse_args()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    selected_events = [event for event in EVENTS if args.event == "all" or event["kind"].lower() == args.event]
    for event in selected_events:
        for slug in TOP_THREE:
            print(f"RUN {event['label']} | {slug}", flush=True)
            try:
                row = _run(slug, event)
            except Exception as exc:  # preserve successful markets and make archive gaps explicit
                row = _unavailable_row(slug, event, exc)
                rows.append(row)
                print(f"UNAVAILABLE {row['label']}: {row['reason']}", flush=True)
                continue
            rows.append(row)
            stats = row["stats"]
            print(
                f"DONE {row['label']}: {stats['return_pct']}% | PF {stats['profit_factor']} | "
                f"WR {stats['win_rate_pct']}% | DD {stats['max_drawdown_pct']}% | {stats['trades']} trades",
                flush=True,
            )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "MT5 Every Tick generated-tick replay on the isolated Exness tester",
        "risk": "0.75% per pending stop / 1.50% maximum planned two-sided event exposure",
        "calendar": "Official confirmed BLS release times supplied through FXMacroData MCP",
        "rows": rows,
    }
    (OUTPUT_ROOT / "recent-event-results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# News Pulse recent-event replay — 2026-09-11",
        "",
        "Fresh MT5 Every Tick simulations of the active top-three News Pulse markets. Net results include the broker-reported commission and swap contained in the deal ledger.",
        "",
        "| Event | Market | Return | Net P/L | PF | Win rate | Max DD | Trades | Commission | Swap |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row.get("status") == "unavailable":
            lines.append(f"| {row['event_label']} | {row['symbol']} | unavailable | — | — | — | — | — | — | — |")
            continue
        stats = row["stats"]
        lines.append(
            f"| {row['event_label']} | {row['symbol']} | {stats['return_pct']:+.2f}% | "
            f"${stats['net_profit']:+,.2f} | {stats['profit_factor']:.2f} | {stats['win_rate_pct']:.2f}% | "
            f"{stats['max_drawdown_pct']:.2f}% | {stats['trades']} | ${stats['commission']:+,.2f} | ${stats['swap']:+,.2f} |"
        )
    lines.extend(
        [
            "",
            "A row is marked unavailable when the broker has not yet archived the release-day tick history needed by Strategy Tester; no result is estimated or fabricated.",
            "",
            "These are single-event historical replays, not independent statistical samples and not guarantees of live fills. News gaps, spread expansion, slippage and rejection can exceed the planned stop risk.",
        ]
    )
    (OUTPUT_ROOT / "RECENT EVENT RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
