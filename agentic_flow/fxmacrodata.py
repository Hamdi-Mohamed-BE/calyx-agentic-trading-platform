from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_URL = "https://api.fxmacrodata.com/v1"
API_KEY_ENV = "FXMD_API_KEY"


class FXMacroDataError(RuntimeError):
    pass


def _redacted_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe = [(key, "REDACTED" if key.lower() == "api_key" else value) for key, value in query]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(safe), parsed.fragment))


class Client:
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv(API_KEY_ENV)
        self.timeout = timeout

    def get(self, path: str, **params: object) -> tuple[dict[str, Any], dict[str, Any]]:
        query = {key: value for key, value in params.items() if value is not None}
        headers = {"Accept": "application/json", "User-Agent": "CalyxResearchPipeline/1.0"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        url = f"{BASE_URL}/{path.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                receipt = {
                    "source": "FXMacroData",
                    "source_url": _redacted_url(url),
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "http_status": response.status,
                    "authenticated": bool(self.api_key),
                }
                return payload, receipt
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise FXMacroDataError(f"FXMacroData HTTP {exc.code}: {body[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise FXMacroDataError(f"FXMacroData request failed: {exc}") from exc

    def health(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.get("health")

    def catalogue(self, currency: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.get(f"data_catalogue/{currency.lower()}", include_coverage="true", include_capabilities="true")

    def calendar(self, currency: str, start: str, end: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.get(f"calendar/{currency.lower()}", start_date=start, end_date=end, timezone="UTC")

    def indicator(self, currency: str, indicator: str, start: str, end: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.get(
            f"announcements/{currency.lower()}/{indicator.lower()}",
            start_date=start,
            end_date=end,
            limit=100,
            official_only="true",
        )


def _quality(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    quality = result.get("data_quality", {}) if isinstance(result, dict) else {}
    metadata = payload.get("mcp_metadata", {}) if isinstance(payload.get("mcp_metadata"), dict) else {}
    return {
        "point_in_time_safe": quality.get("point_in_time_safe", metadata.get("point_in_time_safe")),
        "has_announcement_datetime": quality.get("has_announcement_datetime", metadata.get("has_announcement_datetime")),
        "is_official": quality.get("is_official"),
        "is_proxy": quality.get("is_proxy", metadata.get("is_proxy")),
        "is_fallback": quality.get("is_fallback", metadata.get("is_fallback")),
        "is_stale": quality.get("is_stale", metadata.get("is_stale")),
        "latest_available_date": quality.get("latest_available_date", metadata.get("latest_available_date")),
    }


def _write_snapshot(path: Path, payload: dict[str, Any], receipt: dict[str, Any], audit: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"receipt": receipt, "quality_audit": audit or _quality(payload), "payload": payload}
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")


def coverage_audit(client: Client, currency: str, indicators: list[str], start: str, end: str) -> dict[str, Any]:
    rows = []
    for indicator in indicators:
        try:
            payload, receipt = client.indicator(currency, indicator, start, end)
            data = payload.get("data", [])
            quality = _quality(payload)
            timestamps_present = bool(data) and all(row.get("announcement_datetime") for row in data)
            freemium = payload.get("freemium_window")
            analysis_ready = (
                bool(data)
                and timestamps_present
                and quality.get("point_in_time_safe") is True
                and quality.get("is_fallback") is not True
                and quality.get("is_stale") is not True
                and not (isinstance(freemium, dict) and freemium.get("applied") is True)
            )
            rows.append(
                {
                    "indicator": indicator,
                    "status": "usable" if analysis_ready else "exploratory_only",
                    "rows": len(data),
                    "requested_start": start,
                    "requested_end": end,
                    "earliest_returned_release": min((row.get("announcement_datetime") for row in data if row.get("announcement_datetime")), default=None),
                    "latest_returned_release": max((row.get("announcement_datetime") for row in data if row.get("announcement_datetime")), default=None),
                    "freemium_window": freemium,
                    "quality": quality,
                    "all_rows_have_announcement_datetime": timestamps_present,
                    "receipt": receipt,
                }
            )
        except FXMacroDataError as exc:
            rows.append({"indicator": indicator, "status": "blocked", "error": str(exc)})

    historical_window_requested = (datetime.now(timezone.utc).date() - datetime.fromisoformat(start).date()).days > 90
    fully_usable = all(row.get("status") == "usable" for row in rows)
    no_key_limit = currency.lower() == "usd" and not client.api_key and historical_window_requested
    if no_key_limit:
        verdict = "NOT_READY_FOR_MULTIYEAR_BACKTEST_FREE_KEY_LIMIT"
    elif fully_usable:
        verdict = "READY_FOR_POINT_IN_TIME_JOIN"
    else:
        verdict = "NOT_READY"
    return {
        "currency": currency.upper(),
        "start": start,
        "end": end,
        "authenticated": bool(client.api_key),
        "verdict": verdict,
        "rule": "Only announcement_datetime may release a value to a strategy. Observation dates never authorize availability.",
        "indicators": rows,
    }


def high_impact_calendar(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", [])
    selected = [
        row
        for row in data
        if row.get("top_tier_for_currency") is True or row.get("event_importance") == "high" or row.get("market_tier") == 1
    ]
    return {
        "currency": payload.get("currency"),
        "timezone": payload.get("requested_timezone", "UTC"),
        "data_quality": payload.get("data_quality", {}),
        "data": selected,
    }


def known_at_rows(rows: list[dict[str, Any]], decision_time: datetime) -> list[dict[str, Any]]:
    """Return only macro rows whose release timestamp was known at the decision time."""
    if decision_time.tzinfo is None:
        decision_time = decision_time.replace(tzinfo=timezone.utc)
    cutoff = decision_time.astimezone(timezone.utc).timestamp()
    return [row for row in rows if row.get("announcement_datetime") is not None and float(row["announcement_datetime"]) <= cutoff]


def main() -> None:
    parser = argparse.ArgumentParser(description="Point-in-time-safe FXMacroData connector for the Calyx research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")

    catalogue_parser = sub.add_parser("catalogue")
    catalogue_parser.add_argument("--currency", default="USD")
    catalogue_parser.add_argument("--output", type=Path, required=True)

    calendar_parser = sub.add_parser("calendar")
    calendar_parser.add_argument("--currency", default="USD")
    calendar_parser.add_argument("--start", required=True)
    calendar_parser.add_argument("--end", required=True)
    calendar_parser.add_argument("--high-impact-only", action="store_true")
    calendar_parser.add_argument("--output", type=Path, required=True)

    coverage_parser = sub.add_parser("audit-coverage")
    coverage_parser.add_argument("--currency", default="USD")
    coverage_parser.add_argument("--start", required=True)
    coverage_parser.add_argument("--end", required=True)
    coverage_parser.add_argument("--indicators", default="inflation,employment,non_farm_payrolls,policy_rate")
    coverage_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    client = Client()
    if args.command == "health":
        payload, receipt = client.health()
        print(json.dumps({"receipt": receipt, "payload": payload}, indent=2))
        return
    if args.command == "catalogue":
        payload, receipt = client.catalogue(args.currency)
        _write_snapshot(args.output, payload, receipt)
        print(f"Saved {args.currency.upper()} catalogue to {args.output}")
        return
    if args.command == "calendar":
        payload, receipt = client.calendar(args.currency, args.start, args.end)
        if args.high_impact_only:
            payload = high_impact_calendar(payload)
        _write_snapshot(args.output, payload, receipt)
        print(f"Saved {len(payload.get('data', []))} events to {args.output}")
        return
    if args.command == "audit-coverage":
        indicators = [item.strip() for item in args.indicators.split(",") if item.strip()]
        audit = coverage_audit(client, args.currency, indicators, args.start, args.end)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(f"{audit['verdict']}: {args.currency.upper()} {args.start} to {args.end}")


if __name__ == "__main__":
    main()
