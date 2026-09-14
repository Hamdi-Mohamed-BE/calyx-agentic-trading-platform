from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from news_pulse_macro_audit import TARGET_INDICATORS, TARGET_RELEASES, _macro_events, _mcp_call


GENERATOR_VERSION = "1.0"


class CalendarCoverageError(RuntimeError):
    """Raised when FXMacroData cannot prove the entire requested tester window."""


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarCoverageError(f"Invalid ISO date: {value}") from exc


def _date_epoch(day: date, *, end_of_day: bool = False) -> int:
    clock = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return int(datetime.combine(day, clock, tzinfo=timezone.utc).timestamp())


def _quality_errors(label: str, payload: dict[str, Any], *, require_point_in_time_values: bool) -> list[str]:
    quality = payload.get("data_quality", {})
    errors = []
    required_true = ["is_official", "has_announcement_datetime"]
    if require_point_in_time_values:
        required_true.append("point_in_time_safe")
    for field in required_true:
        if quality.get(field) is not True:
            errors.append(f"{label}: data_quality.{field} is not true")
    for field in ("is_proxy", "is_fallback", "is_stale"):
        if quality.get(field) is True:
            errors.append(f"{label}: data_quality.{field} is true")
    if quality.get("missing_announcement_datetime_count", 0) not in (0, None):
        errors.append(f"{label}: release timestamps are missing")
    return errors


def _assert_complete_coverage(
    start_day: date,
    end_day: date,
    calendar: dict[str, Any],
    indicators: dict[str, dict[str, Any]],
) -> None:
    if start_day > end_day:
        raise CalendarCoverageError("Calendar start must not be after calendar end")
    errors = _quality_errors("release_calendar", calendar, require_point_in_time_values=True)
    latest_calendar = calendar.get("data_quality", {}).get("latest_available_date")
    if latest_calendar and _parse_date(str(latest_calendar)) < end_day:
        errors.append(
            f"release_calendar: latest verified date {latest_calendar} is before requested end {end_day.isoformat()}"
        )

    for kind, payload in indicators.items():
        # News Pulse consumes only the official release timestamp. It never
        # consumes the published value, so a revision-sensitive value series
        # does not invalidate an exact, non-assumed announcement timestamp.
        errors.extend(_quality_errors(kind, payload, require_point_in_time_values=False))
        freemium = payload.get("freemium_window")
        if isinstance(freemium, dict) and freemium.get("applied") is True:
            cutoff = _parse_date(str(freemium.get("cutoff_date")))
            if start_day < cutoff:
                errors.append(
                    f"{kind}: requested start {start_day.isoformat()} predates anonymous cutoff {cutoff.isoformat()}"
                )
        if payload.get("requested_window_has_data") is False:
            errors.append(f"{kind}: provider reports no data in the requested window")

    if errors:
        raise CalendarCoverageError("FXMacroData coverage validation failed:\n- " + "\n- ".join(errors))


def _assert_official_event_times(start_day: date, end_day: date, calendar: dict[str, Any]) -> None:
    """Validate the only data News Pulse consumes: confirmed official release times."""
    if start_day > end_day:
        raise CalendarCoverageError("Calendar start must not be after calendar end")
    quality = calendar.get("data_quality", {})
    errors: list[str] = []
    for field in ("is_official", "has_announcement_datetime"):
        if quality.get(field) is not True:
            errors.append(f"release_calendar: data_quality.{field} is not true")
    for field in ("is_proxy", "is_fallback", "is_stale", "has_assumed_release_times"):
        if quality.get(field) is True:
            errors.append(f"release_calendar: data_quality.{field} is true")
    if quality.get("missing_announcement_datetime_count", 0) not in (0, None):
        errors.append("release_calendar: release timestamps are missing")
    latest_calendar = quality.get("latest_available_date")
    if latest_calendar and _parse_date(str(latest_calendar)) < end_day:
        errors.append(
            f"release_calendar: latest verified date {latest_calendar} is before requested end {end_day.isoformat()}"
        )
    target_rows = [row for row in calendar.get("data", []) if str(row.get("release", "")) in TARGET_RELEASES]
    if not target_rows:
        errors.append("release_calendar: no NFP, CPI or FOMC rows were returned")
    for row in target_rows:
        if row.get("release_date_confirmed") is not True:
            errors.append(f"release_calendar: {row.get('release')} does not have a confirmed release date")
        if not isinstance(row.get("announcement_datetime"), int):
            errors.append(f"release_calendar: {row.get('release')} has no exact announcement timestamp")
    if errors:
        raise CalendarCoverageError("FXMacroData event-time validation failed:\n- " + "\n- ".join(errors))


def _calendar_include(manifest: dict[str, Any]) -> str:
    epochs = ",".join(str(row["epoch"]) for row in manifest["events"])
    kinds = ",".join(f'"{row["kind"]}"' for row in manifest["events"])
    return f'''// AUTO-GENERATED by Calyx news_pulse_calendar.py v{GENERATOR_VERSION}.
// Do not edit release timestamps by hand. Regenerate from the FXMacroData MCP.
#ifndef CALYX_NEWS_PULSE_TESTER_CALENDAR_MQH
#define CALYX_NEWS_PULSE_TESTER_CALENDAR_MQH

#define NP_TESTER_CALENDAR_COVERAGE_START_DATE {manifest["coverage"]["start_date_key"]}
#define NP_TESTER_CALENDAR_COVERAGE_END_DATE {manifest["coverage"]["end_date_key"]}
#define NP_TESTER_CALENDAR_EXPECTED_EVENTS {manifest["event_count"]}

long NP_GENERATED_EVENT_UTC_EPOCHS[]={{{epochs}}};
string NP_GENERATED_EVENT_KINDS[]={{{kinds}}};

string NP_GeneratedCalendarProvider() {{ return "FXMacroData MCP"; }}
string NP_GeneratedCalendarHash() {{ return "{manifest["calendar_sha256"]}"; }}
string NP_GeneratedCalendarFetchedAt() {{ return "{manifest["generated_at_utc"]}"; }}
int NP_GeneratedCalendarEventCount() {{ return ArraySize(NP_GENERATED_EVENT_UTC_EPOCHS); }}

#endif
'''


def _merge_with_base(manifest: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Extend an earlier verified calendar without discarding its covered events."""
    if base.get("provider") != "FXMacroData MCP" or base.get("coverage", {}).get("complete_for_requested_window") is not True:
        raise CalendarCoverageError("Base calendar is not a complete FXMacroData manifest")
    events = {
        (str(row["kind"]), int(row["epoch"])): dict(row)
        for row in [*base.get("events", []), *manifest.get("events", [])]
    }
    ordered = sorted(events.values(), key=lambda row: (int(row["epoch"]), str(row["kind"])))
    canonical = json.dumps(
        [{"kind": row["kind"], "epoch": row["epoch"], "source": row.get("source")} for row in ordered],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    start = min(str(base["coverage"]["start_date"]), str(manifest["coverage"]["start_date"]))
    end = max(str(base["coverage"]["end_date"]), str(manifest["coverage"]["end_date"]))
    start_day = _parse_date(start)
    end_day = _parse_date(end)
    counts = Counter(str(row["kind"]) for row in ordered)
    return {
        **manifest,
        "base_calendar_sha256": base.get("calendar_sha256"),
        "coverage": {
            "start_date": start,
            "end_date": end,
            "start_date_key": int(start_day.strftime("%Y%m%d")),
            "end_date_key": int(end_day.strftime("%Y%m%d")),
            "start_epoch_utc": _date_epoch(start_day),
            "end_epoch_utc": _date_epoch(end_day, end_of_day=True),
            "complete_for_requested_window": True,
        },
        "event_count": len(ordered),
        "event_count_by_kind": dict(sorted(counts.items())),
        "calendar_sha256": hashlib.sha256(canonical).hexdigest(),
        "events": ordered,
        "receipts": [*base.get("receipts", []), *manifest.get("receipts", [])],
    }


def build_calendar(start: str, end: str, *, event_times_only: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    start_day = _parse_date(start)
    end_day = _parse_date(end)
    calendar, calendar_receipt, calendar_envelope = _mcp_call(
        "release_calendar",
        {"currency": "usd", "start_date": start, "end_date": end, "timezone": "UTC"},
        1,
    )
    indicator_payloads: dict[str, dict[str, Any]] = {}
    receipts = [calendar_receipt]
    raw = {"release_calendar": calendar_envelope}
    if event_times_only:
        _assert_official_event_times(start_day, end_day, calendar)
    else:
        for request_id, (kind, indicator) in enumerate(TARGET_INDICATORS.items(), start=2):
            payload, receipt, envelope = _mcp_call(
                "indicator_query",
                {
                    "currency": "usd",
                    "indicator": indicator,
                    "start_date": start,
                    "end_date": end,
                    "limit": 100,
                    "official_only": True,
                },
                request_id,
            )
            indicator_payloads[kind] = payload
            receipts.append(receipt)
            raw[indicator] = envelope
        _assert_complete_coverage(start_day, end_day, calendar, indicator_payloads)
    start_epoch = _date_epoch(start_day)
    end_epoch = _date_epoch(end_day, end_of_day=True)
    events = [
        row for row in _macro_events(calendar, indicator_payloads) if start_epoch <= int(row["epoch"]) <= end_epoch
    ]
    if not events:
        raise CalendarCoverageError("FXMacroData returned no NFP, CPI or FOMC events in the requested window")
    if len({(row["kind"], row["epoch"]) for row in events}) != len(events):
        raise CalendarCoverageError("FXMacroData returned duplicate target event timestamps")

    canonical = json.dumps(
        [{"kind": row["kind"], "epoch": row["epoch"], "source": row.get("source")} for row in events],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    counts = Counter(row["kind"] for row in events)
    manifest = {
        "schema_version": 1,
        "generator_version": GENERATOR_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "FXMacroData MCP",
        "validation_mode": "official-confirmed-event-times" if event_times_only else "full-point-in-time-join",
        "authenticated": any(bool(row.get("authenticated")) for row in receipts),
        "coverage": {
            "start_date": start,
            "end_date": end,
            "start_date_key": int(start_day.strftime("%Y%m%d")),
            "end_date_key": int(end_day.strftime("%Y%m%d")),
            "start_epoch_utc": start_epoch,
            "end_epoch_utc": end_epoch,
            "complete_for_requested_window": True,
        },
        "event_count": len(events),
        "event_count_by_kind": dict(sorted(counts.items())),
        "calendar_sha256": hashlib.sha256(canonical).hexdigest(),
        "events": events,
        "receipts": receipts,
        "quality": {
            "release_calendar": calendar.get("data_quality", {}),
            "indicators": {kind: payload.get("data_quality", {}) for kind, payload in indicator_payloads.items()},
        },
    }
    return manifest, raw


def generate_calendar(
    start: str,
    end: str,
    include_path: Path,
    manifest_path: Path,
    raw_path: Path,
    *,
    event_times_only: bool = False,
    base_manifest_path: Path | None = None,
) -> dict[str, Any]:
    manifest, raw = build_calendar(start, end, event_times_only=event_times_only)
    if base_manifest_path is not None:
        base = json.loads(base_manifest_path.read_text(encoding="utf-8-sig"))
        manifest = _merge_with_base(manifest, base)
        raw["base_manifest"] = base
    include_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    include_path.write_text(_calendar_include(manifest), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the fail-closed News Pulse Strategy Tester calendar from FXMacroData MCP"
    )
    parser.add_argument("--start", required=True, help="Required tester coverage start, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Required tester coverage end, YYYY-MM-DD")
    parser.add_argument("--include", type=Path, required=True, help="Generated MQL5 include path")
    parser.add_argument("--manifest", type=Path, required=True, help="Provenance manifest path")
    parser.add_argument("--raw", type=Path, required=True, help="Raw MCP receipt path")
    parser.add_argument(
        "--event-times-only",
        action="store_true",
        help="Validate confirmed official release timestamps only; News Pulse does not consume the released values.",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        help="Optional earlier verified manifest whose events are retained while extending the calendar.",
    )
    args = parser.parse_args()
    try:
        manifest = generate_calendar(
            args.start,
            args.end,
            args.include,
            args.manifest,
            args.raw,
            event_times_only=args.event_times_only,
            base_manifest_path=args.base_manifest,
        )
    except CalendarCoverageError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(
        f"Generated {manifest['event_count']} verified events for {args.start} through {args.end}; "
        f"calendar hash {manifest['calendar_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
