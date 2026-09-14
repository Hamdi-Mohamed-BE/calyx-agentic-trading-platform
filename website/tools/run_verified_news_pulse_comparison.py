from __future__ import annotations

import argparse
import json
import os
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
from tools.precompute_evidence_cache import news_pulse_calendar_window  # noqa: E402


SLUGS = ("news-pulse-xau", "news-pulse-xag", "news-pulse-btc")
OLD_RESULTS = (
    PACKAGE_ROOT
    / "News Pulse FXMacroData Audit 2026-09-10"
    / "schedule-replay-results.json"
)
CRYPTO_RESULTS = PACKAGE_ROOT / "News Pulse Crypto Extension 2026-09-11" / "VERIFIED RESULTS.json"


def _costs(trades: list[dict[str, Any]]) -> dict[str, float]:
    commission = round(sum(float(row.get("commission") or 0.0) for row in trades), 2)
    swap = round(sum(float(row.get("swap") or 0.0) for row in trades), 2)
    return {"commission": commission, "swap": swap, "total_costs": round(commission + swap, 2)}


def _on_tester_result(report: Path) -> float | None:
    raw = report.read_bytes()
    text = raw.decode("utf-16", errors="ignore") if raw[:200].count(b"\x00") > 20 else raw.decode("utf-8", errors="ignore")
    match = re.search(r"OnTester result:</td>\s*<td[^>]*><b>([-+0-9.,]+)</b>", text, re.IGNORECASE)
    return float(match.group(1).replace(",", "")) if match else None


def _run(slug: str, start: date, end: date) -> dict[str, Any]:
    product = get_product(slug)
    if product is None:
        raise RuntimeError(f"Unknown product: {slug}")
    suffix = os.getenv("EA_STORE_TESTER_SYMBOL_SUFFIX", "")
    overrides = {
        "InpTesterFromDateUTC": start.strftime("%Y%m%d"),
        "InpTesterToDateUTC": end.strftime("%Y%m%d"),
    }
    job = mt5_evidence_jobs.start(
        slug,
        "standard",
        start,
        end,
        f"{product.canonical}{suffix}",
        input_overrides=overrides,
    )
    while job["status"] in {"queued", "running"}:
        time.sleep(1)
        job = mt5_evidence_jobs.get(str(job["id"])) or job
    if job["status"] != "completed":
        raise RuntimeError(str(job.get("error") or f"News Pulse run failed: {slug}"))
    result = dict(job["result"])
    result["stats"] = {**result["stats"], **_costs(result.get("trades", []))}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare News Pulse on the connected account over its verified FXMacroData window")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retain-reports", action="store_true", help="Also retain the large native MT5 HTML reports")
    args = parser.parse_args()

    first_product = get_product(SLUGS[0])
    if first_product is None:
        raise RuntimeError("News Pulse XAU is missing from the catalog")
    start, end = news_pulse_calendar_window(first_product)
    old_payload = json.loads(OLD_RESULTS.read_text(encoding="utf-8-sig"))
    old_by_asset = {row["asset"]: row["fxmacrodata_schedule"] for row in old_payload["results"]}
    crypto_payload = json.loads(CRYPTO_RESULTS.read_text(encoding="utf-8-sig"))
    crypto_by_asset = {row["asset"]: row for row in crypto_payload}
    asset_by_slug = {
        "news-pulse-xau": "xauusd",
        "news-pulse-xag": "xagusd",
        "news-pulse-btc": "btcusd",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    report_root = args.output / "reports"
    if args.retain_reports:
        report_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for slug in SLUGS:
        print(f"RUN {slug} | verified calendar {start} to {end}", flush=True)
        result = _run(slug, start, end)
        retained = mt5_evidence_jobs.output_root / slug / "latest.htm"
        if retained.is_file():
            processed = _on_tester_result(retained)
            if processed != float(old_payload["expected_events"]):
                raise RuntimeError(
                    f"{slug} processed {processed} events; verified calendar requires {old_payload['expected_events']}"
                )
            if args.retain_reports:
                shutil.copy2(retained, report_root / f"{slug}.htm")
        raw_stats = result["stats"]
        asset = asset_by_slug[slug]
        if asset in crypto_by_asset:
            old = crypto_by_asset[asset]
            old_stats = {
                "return_pct": round(float(old["return_pct"]), 2),
                "profit_factor": float(old["profit_factor"]),
                "win_rate_pct": float(old["win_rate_pct"]),
                "max_drawdown_pct": float(old["max_drawdown_pct"]),
                "trades": int(old["trades"]),
            }
        else:
            old = old_by_asset[asset]["metrics"]
            old_stats = {
                "return_pct": round(float(old["reported_net_profit"]) / float(old["initial_balance"]) * 100, 2),
                "profit_factor": float(old["reported_profit_factor"]),
                "win_rate_pct": float(old["reported_win_rate_pct"]),
                "max_drawdown_pct": float(old["reported_max_drawdown_pct"]),
                "trades": int(old["reported_trades"]),
            }
        rows.append(
            {
                "slug": slug,
                "label": result["label"].split(" — fresh", 1)[0],
                "period": f"{start.isoformat()} to {end.isoformat()}",
                "standard_account": old_stats,
                "raw_spread_account": raw_stats,
                "delta": {
                    "return_pct": round(float(raw_stats["return_pct"]) - old_stats["return_pct"], 2),
                    "profit_factor": round(float(raw_stats["profit_factor"]) - old_stats["profit_factor"], 2),
                    "win_rate_pct": round(float(raw_stats["win_rate_pct"]) - old_stats["win_rate_pct"], 2),
                    "max_drawdown_pct": round(float(raw_stats["max_drawdown_pct"]) - old_stats["max_drawdown_pct"], 2),
                    "trades": int(raw_stats["trades"]) - old_stats["trades"],
                },
                "raw_trade_details": result.get("trades", []),
            }
        )
        print(
            f"DONE {slug}: {raw_stats['return_pct']}% | PF {raw_stats['profit_factor']} | "
            f"WR {raw_stats['win_rate_pct']}% | DD {raw_stats['max_drawdown_pct']}% | {raw_stats['trades']} trades",
            flush=True,
        )
        time.sleep(10)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "account": {
            "name": "Raw Spread",
            "login": os.getenv("EA_STORE_TESTER_LOGIN", ""),
            "server": os.getenv("EA_STORE_TESTER_SERVER", ""),
        },
        "calendar": {
            "provider": "FXMacroData MCP",
            "verified_from": start.isoformat(),
            "verified_to": end.isoformat(),
            "event_count": old_payload["expected_events"],
        },
        "rows": rows,
    }
    (args.output / "news-pulse-verified-window.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
