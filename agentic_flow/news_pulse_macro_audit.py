from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


MCP_URL = "https://mcp.fxmacrodata.com"
TARGET_INDICATORS = {
    "NFP": "non_farm_payrolls",
    "CPI": "inflation",
    "FOMC": "policy_rate",
}
TARGET_RELEASES = {value: key for key, value in TARGET_INDICATORS.items()}
COMMENT_PATTERN = re.compile(r"NP\|(\d+)\|(NFP|CPI|FOMC)\|[BS]")


def _mcp_call(name: str, arguments: dict[str, Any], request_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "CalyxResearchPipeline/1.0",
    }
    api_key = os.getenv("FXMD_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        MCP_URL,
        data=body,
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        envelope = json.loads(raw.decode("utf-8"))
        receipt = {
            "source": "FXMacroData MCP",
            "tool": name,
            "endpoint": MCP_URL,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "http_status": response.status,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "authenticated": bool(api_key),
        }

    tool_result = envelope.get("result", {})
    if tool_result.get("isError"):
        raise RuntimeError(f"FXMacroData MCP tool {name} returned an error")
    value: Any = tool_result.get("structuredContent", {})
    for _ in range(3):
        if isinstance(value, dict) and isinstance(value.get("result"), dict) and "data" not in value:
            value = value["result"]
        else:
            break
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise RuntimeError(f"FXMacroData MCP tool {name} did not return a data array")
    return value, receipt, envelope


def _parse_tester_schedule(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ny = ZoneInfo("America/New_York")
    definitions = {
        "NFP": ("nfp_dates", 8, 30),
        "CPI": ("cpi_dates", 8, 30),
        "FOMC": ("fomc_dates", 14, 0),
    }
    for kind, (array_name, hour, minute) in definitions.items():
        match = re.search(rf"int\s+{array_name}\[\]\s*=\s*\{{([^}}]+)\}}", source, re.DOTALL)
        if not match:
            raise RuntimeError(f"Could not find {array_name} in the News Pulse source")
        for token in re.findall(r"\d{8}", match.group(1)):
            local = datetime.strptime(token, "%Y%m%d").replace(hour=hour, minute=minute, tzinfo=ny)
            utc = local.astimezone(timezone.utc)
            rows.append(
                {
                    "kind": kind,
                    "date_key": token,
                    "new_york_time": local.isoformat(),
                    "utc_time": utc.isoformat(),
                    "epoch": int(utc.timestamp()),
                }
            )
    return sorted(rows, key=lambda row: row["epoch"])


def _macro_events(calendar: dict[str, Any], indicators: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    events: dict[tuple[str, int], dict[str, Any]] = {}
    for row in calendar["data"]:
        kind = TARGET_RELEASES.get(str(row.get("release", "")))
        epoch = row.get("announcement_datetime")
        if not kind or not isinstance(epoch, int):
            continue
        events[(kind, epoch)] = {
            "kind": kind,
            "epoch": epoch,
            "utc_time": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
            "source": row.get("source"),
            "source_url": row.get("source_url"),
            "release_date_confirmed": row.get("release_date_confirmed"),
            "calendar_point_in_time_safe": calendar.get("data_quality", {}).get("point_in_time_safe"),
            "actual_value": None,
            "actual_point_in_time_safe": None,
        }
    for kind, payload in indicators.items():
        quality = payload.get("data_quality", {})
        for row in payload["data"]:
            epoch = row.get("announcement_datetime")
            if not isinstance(epoch, int):
                continue
            event = events.setdefault(
                (kind, epoch),
                {
                    "kind": kind,
                    "epoch": epoch,
                    "utc_time": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
                    "source": row.get("source"),
                    "source_url": row.get("source_url"),
                    "release_date_confirmed": None,
                    "calendar_point_in_time_safe": None,
                    "actual_value": None,
                    "actual_point_in_time_safe": None,
                },
            )
            event["actual_value"] = row.get("val")
            event["actual_point_in_time_safe"] = quality.get("point_in_time_safe")
            event["source"] = row.get("source") or event.get("source")
            event["source_url"] = row.get("source_url") or event.get("source_url")
    return sorted(events.values(), key=lambda row: (row["epoch"], row["kind"]))


def _metrics(profits: list[float]) -> dict[str, Any]:
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = -sum(value for value in profits if value < 0)
    return {
        "trades": len(profits),
        "net_profit": round(sum(profits), 2),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "win_rate_pct": round(100 * sum(value > 0 for value in profits) / len(profits), 2) if profits else None,
    }


def _audit_job(path: Path, macro_lookup: set[tuple[str, int]], coverage_start: int, coverage_end: int) -> dict[str, Any]:
    job = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for trade in job.get("trades", []):
        match = COMMENT_PATTERN.search(str(trade.get("entry_comment", "")))
        if not match:
            continue
        grouped[(match.group(2), int(match.group(1)))].append(float(trade.get("net_profit", 0.0)))

    event_rows = []
    all_profits: list[float] = []
    overlap_profits: list[float] = []
    matched = 0
    mismatched = 0
    for (kind, epoch), profits in sorted(grouped.items(), key=lambda item: item[0][1]):
        all_profits.extend(profits)
        in_window = coverage_start <= epoch <= coverage_end
        exact = (kind, epoch) in macro_lookup
        if in_window:
            overlap_profits.extend(profits)
            if exact:
                matched += 1
            else:
                mismatched += 1
        event_rows.append(
            {
                "kind": kind,
                "event_epoch": epoch,
                "event_time_utc": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
                "trades": len(profits),
                "net_profit": round(sum(profits), 2),
                "inside_fxmacrodata_verified_window": in_window,
                "exact_fxmacrodata_timestamp_match": exact if in_window else None,
            }
        )

    return {
        "ea": job.get("label"),
        "evidence_file": str(path),
        "period": job.get("period"),
        "published_stats": job.get("stats", {}),
        "comment_parsed_all_events": _metrics(all_profits),
        "fxmacrodata_overlap": _metrics(overlap_profits),
        "verified_event_occurrences": matched,
        "mismatched_event_occurrences": mismatched,
        "effect_of_timestamp_replacement_in_verified_window": {
            "events_changed": mismatched,
            "trades_changed": 0 if mismatched == 0 else None,
            "net_profit_change": 0.0 if mismatched == 0 else None,
            "note": "A zero is valid only for the FXMacroData-covered window; anonymous history cannot validate the full report period.",
        },
        "events": event_rows,
    }


def _money(value: Any) -> str:
    return "n/a" if value is None else f"${float(value):,.2f}"


def _number(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def _write_report(path: Path, audit: dict[str, Any]) -> None:
    coverage = audit["fxmacrodata_coverage"]
    schedule = audit["tester_schedule_comparison"]
    lines = [
        "# News Pulse — FXMacroData MCP timing audit",
        "",
        "## Decision",
        "",
        audit["decision"],
        "",
        "No live EA, BAT installer, website evidence, or risk setting was changed by this audit.",
        "",
        "## Verified overlap",
        "",
        f"FXMacroData anonymous coverage used here: **{coverage['start_utc']} through {coverage['end_utc']}**. "
        "The provider returned official timestamps, but the anonymous tier does not cover the full historical backtests.",
        "",
        f"The tester list contains **{schedule['matched_events']}** of the **{schedule['macro_events']}** available NFP/CPI/FOMC releases. "
        f"It is missing **{schedule['missing_events']}**: "
        + ", ".join(f"{row['kind']} {row['utc_time']}" for row in schedule["missing_event_rows"]),
        "",
        "| EA | Matched events | Timestamp mismatches | Overlap trades | Overlap net | Overlap PF | Overlap WR | Result change |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for job in audit["jobs"]:
        overlap = job["fxmacrodata_overlap"]
        effect = job["effect_of_timestamp_replacement_in_verified_window"]
        lines.append(
            f"| {job['ea']} | {job['verified_event_occurrences']} | {job['mismatched_event_occurrences']} | "
            f"{overlap['trades']} | {_money(overlap['net_profit'])} | {_number(overlap['profit_factor'])} | "
            f"{_number(overlap['win_rate_pct'])}% | {_money(effect['net_profit_change'])} |"
        )
    lines.extend(
        [
            "",
            "## What the current EA does",
            "",
            "- **Live:** MT5's built-in USD economic calendar supplies the broker-server release timestamp. The EA refreshes an eight-day cache every five minutes and recognizes NFP, CPI and FOMC by event name.",
            "- **Placement clock:** a fresh broker-stamped tick is required. The VPS clock and VPS timezone are ignored. Orders are accepted only inside the configured pre-release lead window.",
            "- **Tester:** MT5 does not expose its economic calendar in Strategy Tester, so the EA uses hard-coded official dates, assumes NFP/CPI at 08:30 New York and FOMC at 14:00 New York, converts New York time to tester server time with DST handling, then uses the release epoch as the event ID.",
            "",
            "## What FXMacroData changed",
            "",
            "Every event that was already present in the tester used the same timestamp as FXMacroData. However, the tester omitted the event listed above, so a corrected replay is required to measure its P&L effect.",
            "",
            "FXMacroData still improves the process by replacing manually maintained future tester dates with a reproducible official-source calendar and source receipts. It does **not** prove the full-period result until historical access covers every event.",
            "",
            "## Important constraint",
            "",
            "The actual CPI/NFP/rate value is published at the release. News Pulse places its pending orders before the release, so filtering those orders using the actual value would introduce look-ahead bias. A legitimate actual-versus-consensus reaction rule would need a separate post-release strategy, paid consensus data, latency assumptions and a new MT5 backtest.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit News Pulse tester timestamps against FXMacroData MCP")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--start", default="2025-08-01")
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    schedule = _parse_tester_schedule(args.source.read_text(encoding="utf-8-sig"))
    calendar, calendar_receipt, calendar_envelope = _mcp_call(
        "release_calendar",
        {"currency": "usd", "start_date": args.start, "end_date": args.end, "timezone": "UTC"},
        1,
    )
    indicator_payloads: dict[str, dict[str, Any]] = {}
    receipts = [calendar_receipt]
    raw_envelopes = {"release_calendar": calendar_envelope}
    for request_id, (kind, indicator) in enumerate(TARGET_INDICATORS.items(), start=2):
        payload, receipt, envelope = _mcp_call(
            "indicator_query",
            {
                "currency": "usd",
                "indicator": indicator,
                "start_date": args.start,
                "end_date": args.end,
                "limit": 100,
                "official_only": True,
            },
            request_id,
        )
        indicator_payloads[kind] = payload
        receipts.append(receipt)
        raw_envelopes[indicator] = envelope

    macro_events = _macro_events(calendar, indicator_payloads)
    if not macro_events:
        raise RuntimeError("FXMacroData returned no NFP, CPI or FOMC events")
    coverage_start = min(row["epoch"] for row in macro_events)
    coverage_end = max(row["epoch"] for row in macro_events)
    macro_lookup = {(row["kind"], row["epoch"]) for row in macro_events}
    tester_lookup = {(row["kind"], row["epoch"]) for row in schedule}
    missing_schedule_rows = [row for row in macro_events if (row["kind"], row["epoch"]) not in tester_lookup]
    jobs = [_audit_job(path, macro_lookup, coverage_start, coverage_end) for path in args.evidence]
    mismatch_total = sum(job["mismatched_event_occurrences"] for job in jobs)

    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": (
            f"FXMacroData found {len(missing_schedule_rows)} release missing from the tester calendar. "
            "A research-only corrected MT5 replay is required before any production decision."
            if missing_schedule_rows
            else "No tester-calendar change is justified from the currently available evidence."
        ),
        "scope": "Research-only timestamp validation; no production mutation",
        "source_file": str(args.source),
        "tester_schedule": schedule,
        "tester_schedule_comparison": {
            "macro_events": len(macro_events),
            "matched_events": len(macro_events) - len(missing_schedule_rows),
            "missing_events": len(missing_schedule_rows),
            "missing_event_rows": missing_schedule_rows,
            "existing_trade_timestamp_mismatches": mismatch_total,
        },
        "fxmacrodata_coverage": {
            "start_epoch": coverage_start,
            "end_epoch": coverage_end,
            "start_utc": datetime.fromtimestamp(coverage_start, timezone.utc).isoformat(),
            "end_utc": datetime.fromtimestamp(coverage_end, timezone.utc).isoformat(),
            "anonymous_tier": True,
            "full_backtest_coverage": False,
        },
        "fxmacrodata_events": macro_events,
        "receipts": receipts,
        "jobs": jobs,
    }
    (args.output / "fxmacrodata-mcp-raw.json").write_text(
        json.dumps(raw_envelopes, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.output / "news-pulse-fxmacrodata-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (args.output / "event-comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ea",
                "kind",
                "event_epoch",
                "event_time_utc",
                "trades",
                "net_profit",
                "inside_fxmacrodata_verified_window",
                "exact_fxmacrodata_timestamp_match",
            ],
        )
        writer.writeheader()
        for job in jobs:
            for row in job["events"]:
                writer.writerow({"ea": job["ea"], **row})
    _write_report(args.output / "NEWS PULSE FXMACRODATA AUDIT.md", audit)
    print(f"Saved News Pulse FXMacroData audit to {args.output}")


if __name__ == "__main__":
    main()
