from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

from app.catalog import PACKAGE_ROOT, Product, get_sellable_catalog  # noqa: E402
from app.adaptive_portfolio import RULES as ADAPTIVE_RULES, simulate_adaptive_portfolio  # noqa: E402
from app.evidence_cache import (  # noqa: E402
    CACHE_ROOT as DEFAULT_CACHE_ROOT,
    PERIOD_OPTIONS,
    write_json,
)
from app.evidence_series import parse_mt5_balance_series  # noqa: E402
from app.mt5_evidence_jobs import _native_metrics, _native_trades, mt5_evidence_jobs  # noqa: E402
from app.mt5_live import live_mt5  # noqa: E402
from app.trade_metrics import enrich_trades, outcome_streaks  # noqa: E402
from app.news_evidence import news_payload_from_result  # noqa: E402


PERIOD_MONTHS = {"6m": 6, "1y": 12, "3y": 36, "5y": 60}
CACHE_ROOT = Path(os.getenv("EA_STORE_CACHE_ROOT", str(DEFAULT_CACHE_ROOT))).resolve()
NEWS_PULSE_SLUGS = {"news-pulse-xau", "news-pulse-xag", "news-pulse-btc"}
NEWS_RESEARCH_ROOT = PACKAGE_ROOT / "News Pulse Full Coverage 2026-09-12"


def product_cache_path(slug: str, mode: str, period: str) -> Path:
    return CACHE_ROOT / "products" / slug / mode / f"{period}.json"


def product_trades_path(slug: str, mode: str, period: str) -> Path:
    return CACHE_ROOT / "products" / slug / mode / f"{period}.trades.json"


def portfolio_cache_path(mode: str, period: str) -> Path:
    return CACHE_ROOT / "portfolio" / mode / f"{period}.json"


def portfolio_trades_path(mode: str, period: str) -> Path:
    return CACHE_ROOT / "portfolio" / mode / f"{period}.trades.json"


def recommended_mode(product: Product) -> str:
    if product.recommended_dynamic_mode and product.dynamic_mode_supported:
        return "dynamic"
    if product.recommended_safe_mode and product.safe_filter_supported:
        return "safe"
    return "standard"


def subtract_months(value: date, months: int) -> date:
    total = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(total, 12)
    month = month_zero + 1
    month_lengths = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(value.day, month_lengths[month - 1]))


def sample_series(series: list[dict[str, Any]], maximum: int = 5_000) -> list[dict[str, Any]]:
    if len(series) <= maximum:
        return series
    step = (len(series) - 1) / (maximum - 1)
    indexes = sorted({round(index * step) for index in range(maximum)} | {0, len(series) - 1})
    return [series[index] for index in indexes]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def independent_news_result(product: Product, mode: str, period: str, start: date, end: date) -> tuple[dict[str, Any], Path]:
    """Never substitute or rebase another News Pulse window during a refresh."""
    from app.mt5_evidence_jobs import _set_values

    path = NEWS_RESEARCH_ROOT / f"{product.slug}-{period}-model4.json"
    if mode != "standard" or not path.is_file():
        raise RuntimeError(f"Run the audited News Pulse coverage runner for {product.slug} {period} first.")
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if (result['slug'] != product.slug or result['period_key'] != period
            or result['from_date'] != start.isoformat() or result['to_exclusive'] != end.isoformat()):
        raise RuntimeError('News Pulse source dates differ from the requested window; an independent run is required.')
    report = (NEWS_RESEARCH_ROOT / result['source_report']).resolve()
    if NEWS_RESEARCH_ROOT.resolve() not in report.parents or file_hash(report) != result['source_report_sha256']:
        raise RuntimeError('News Pulse native report identity failed validation.')
    manifest = result.get('build') or json.loads((NEWS_RESEARCH_ROOT / 'BUILD MANIFEST.json').read_text())
    original_source = (PACKAGE_ROOT / product.expert_source).with_suffix('.mq5')
    if file_hash(original_source) != manifest['source_sha256']:
        raise RuntimeError('News Pulse source changed after the audited runs; rerun before publishing.')
    for name,digest in manifest['dependencies'].items():
        dependency = (NEWS_RESEARCH_ROOT / name if name=='NewsPulseTesterCalendar.mqh'
                      else PACKAGE_ROOT / '_Shared' / name if name=='CalyxAdaptivePortfolio.mqh'
                      else original_source.parent / name)
        if not dependency.is_file() or file_hash(dependency)!=digest:
            raise RuntimeError(f'News Pulse dependency {name} changed after the audited run.')
    if manifest.get('indexed_lookup') and not (NEWS_RESEARCH_ROOT/'LOOKUP PARITY.json').is_file():
        raise RuntimeError('The faster historical lookup has not passed native control-run parity.')
    expected_settings = _set_values(PACKAGE_ROOT / product.set_source, False, {
        'InpAdaptivePortfolioControls': 'false', 'InpTesterFromDateUTC': start.strftime('%Y%m%d'),
        'InpTesterToDateUTC': end.strftime('%Y%m%d'),
    })
    for line in expected_settings.splitlines():
        if not line.strip() or line.lstrip().startswith(';') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if result['settings'].get(key.strip()) != value.split('||')[0].strip():
            raise RuntimeError(f'News Pulse audited input {key} no longer matches the current preset.')
    news_payload_from_result(result)  # Reconcile dates, fees and ledger before reuse.
    return result, report


def source_fingerprint(product: Product, mode: str, start: date, end: date) -> dict[str, Any]:
    set_relative = (
        product.dynamic_set_source
        if mode == "dynamic"
        else product.safe_set_source
        if mode == "safe" and product.safe_set_source
        else product.set_source
    )
    expert_relative = product.dynamic_expert_source if mode == "dynamic" else product.expert_source
    if not set_relative or not expert_relative:
        raise ValueError(f"Missing source files for {product.label} {mode} mode.")
    expert = PACKAGE_ROOT / expert_relative
    settings = PACKAGE_ROOT / str(set_relative)
    fingerprint = {
        "slug": product.slug,
        "mode": mode,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "canonical_symbol": product.canonical,
        "timeframe": product.timeframe,
        "expert_sha256": file_hash(expert),
        "settings_sha256": file_hash(settings),
    }
    return fingerprint


def source_paths(product: Product, mode: str, period: str) -> tuple[Path, Path]:
    folder = CACHE_ROOT / "source-runs" / product.slug / mode
    return folder / f"{period}.htm", folder / f"{period}.meta.json"


def resolve_symbol(product: Product) -> str:
    suffix = os.getenv("EA_STORE_TESTER_SYMBOL_SUFFIX", "")
    if suffix:
        return f"{product.canonical}{suffix}"
    try:
        return live_mt5.resolve_symbol(product.canonical)
    except RuntimeError:
        return product.canonical


def news_pulse_calendar_window(product: Product) -> tuple[date, date]:
    """Return the exact verified calendar window compiled into News Pulse."""
    if product.slug not in NEWS_PULSE_SLUGS or not product.expert_source:
        raise ValueError(f"{product.label} is not a News Pulse product.")
    include = (PACKAGE_ROOT / product.expert_source).parent / "NewsPulseTesterCalendar.mqh"
    text = include.read_text(encoding="utf-8-sig")
    values: dict[str, date] = {}
    for key, name in (
        ("NP_TESTER_CALENDAR_COVERAGE_START_DATE", "start"),
        ("NP_TESTER_CALENDAR_COVERAGE_END_DATE", "end"),
    ):
        match = re.search(rf"^#define\s+{key}\s+(\d{{8}})\s*$", text, flags=re.MULTILINE)
        if not match:
            raise RuntimeError(f"News Pulse calendar is missing {key}: {include}")
        values[name] = datetime.strptime(match.group(1), "%Y%m%d").date()
    return values["start"], values["end"]


def cleanup_stale_dynamic_artifacts() -> int:
    """Remove only files created by the website's isolated dynamic-test runner."""
    tester_root = mt5_evidence_jobs.tester_terminal.parent.resolve()
    locations = (
        (tester_root / "MQL5" / "Experts" / "EA Store Dynamic", "*.ex5"),
        (tester_root / "reports" / "ea-store-dynamic", "*"),
        (tester_root / "backtest-configs" / "ea-store-dynamic", "*.ini"),
    )
    removed = 0
    for folder, pattern in locations:
        if not folder.is_dir() or tester_root not in folder.resolve().parents:
            continue
        for path in folder.glob(pattern):
            if not path.is_file():
                continue
            path.unlink(missing_ok=True)
            removed += 1
    tester_sets = tester_root / "MQL5" / "Profiles" / "Tester"
    for product in get_sellable_catalog():
        for path in tester_sets.glob(f"{product.slug}-????????.set"):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
    return removed


def run_native(product: Product, mode: str, period: str, start: date, end: date, *, force: bool) -> Path:
    report_path, metadata_path = source_paths(product, mode, period)
    fingerprint = source_fingerprint(product, mode, start, end)
    if product.slug in NEWS_PULSE_SLUGS:
        if force:
            raise RuntimeError('Use the audited News Pulse coverage runner for fresh official-calendar tests; generic refresh cannot extend its calendar.')
        result, reviewed_report = independent_news_result(product, mode, period, start, end)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reviewed_report, report_path)
        write_json(metadata_path, {**fingerprint, 'source_report_sha256': result['source_report_sha256'],
                                  'source': 'independent-official-calendar-window'})
        print(f"IMPORT {product.label} {period}: exact independent window", flush=True)
        return report_path
    if not force and report_path.is_file() and metadata_path.is_file():
        try:
            if json.loads(metadata_path.read_text(encoding="utf-8-sig")) == fingerprint:
                print(f"CACHE SOURCE {product.label} {mode} {period}", flush=True)
                return report_path
        except (OSError, json.JSONDecodeError):
            pass

    input_overrides: dict[str, str] = {}
    if product.slug in NEWS_PULSE_SLUGS:
        coverage_start, coverage_end = news_pulse_calendar_window(product)
        if start < coverage_start or end > coverage_end:
            raise RuntimeError(
                "News Pulse cannot be backtested outside its verified FXMacroData calendar: "
                f"requested {start} to {end}, available {coverage_start} to {coverage_end}. "
                "Authenticate FXMacroData and regenerate the calendar for a longer window."
            )
        input_overrides = {
            "InpTesterFromDateUTC": start.strftime("%Y%m%d"),
            "InpTesterToDateUTC": end.strftime("%Y%m%d"),
        }

    symbol = resolve_symbol(product)
    print(f"RUN {product.label} | {mode} | {period} | {symbol} {product.timeframe} | {start} to {end}", flush=True)
    try:
        job = mt5_evidence_jobs.start(product.slug, mode, start, end, symbol, input_overrides=input_overrides)
    except ValueError as exc:
        if "wait a few seconds" not in str(exc).lower():
            raise
        time.sleep(10)
        job = mt5_evidence_jobs.start(product.slug, mode, start, end, symbol, input_overrides=input_overrides)
    last_stage = ""
    while job["status"] in {"queued", "running"}:
        if job.get("stage") != last_stage:
            last_stage = str(job.get("stage"))
            print(f"  {last_stage} ({job.get('progress', 0)}%)", flush=True)
        time.sleep(1)
        job = mt5_evidence_jobs.get(str(job["id"])) or job
    if job["status"] != "completed":
        raise RuntimeError(str(job.get("error") or f"Native MT5 run failed for {product.label}"))
    latest = mt5_evidence_jobs.output_root / product.slug / "latest.htm"
    if not latest.is_file():
        raise RuntimeError(f"Native report was not retained for {product.label}.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest, report_path)
    write_json(metadata_path, fingerprint)
    latest.unlink(missing_ok=True)
    (latest.parent / "latest.json").unlink(missing_ok=True)
    return report_path


def product_payload(product: Product, mode: str, period: str, start: date, end: date, report: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if product.slug in NEWS_PULSE_SLUGS:
        result, reviewed_report = independent_news_result(product, mode, period, start, end)
        if file_hash(report) != file_hash(reviewed_report):
            raise RuntimeError('Refusing to replace audited News Pulse evidence with a different report.')
        return news_payload_from_result(result), result['trades']
    parse_mt5_balance_series.cache_clear()
    series = [dict(point) for point in parse_mt5_balance_series(report)]
    native = _native_metrics(report)
    all_trades = _native_trades(report, f"{product.label} — {mode.title()}")
    all_trade_count = len(all_trades)
    trades = [
        trade
        for trade in all_trades
        if start.isoformat() <= str(trade.get("close_time") or "")[:10] <= end.isoformat()
    ]
    for number, trade in enumerate(trades, 1):
        trade["number"] = number
        trade["cache_slug"] = product.slug
        trade["cache_mode"] = mode
        trade["cache_period"] = period
        trade["source"] = "Precomputed native MT5 deals"
    trades = enrich_trades(trades, product.slug)
    if len(trades) != all_trade_count:
        native, series = portfolio_metrics(trades, start, end)
        native["history_quality"] = "100%"
    native.update(outcome_streaks(trades))
    native.update(
        {
            "gross_profit_before_costs": round(sum(float(trade.get("gross_profit") or 0.0) for trade in trades), 2),
            "commission": round(sum(float(trade.get("commission") or 0.0) for trade in trades), 2),
            "swap": round(sum(float(trade.get("swap") or 0.0) for trade in trades), 2),
            "total_costs": round(sum(float(trade.get("total_costs") or 0.0) for trade in trades), 2),
        }
    )
    initial = float(native.get("initial_balance", 10_000) or 10_000)
    if not series:
        series = [{"time": f"{start.isoformat()}T00:00:00", "balance": initial}]
    if str(series[0]["time"])[:10] > start.isoformat():
        series.insert(0, {"time": f"{start.isoformat()}T00:00:00", "balance": initial})
    final = float(native.get("final_balance", initial))
    if len(series) == 1 or str(series[-1]["time"])[:10] < end.isoformat():
        series.append({"time": f"{end.isoformat()}T23:59:59", "balance": final})
    native.update({"from": start.isoformat(), "to": end.isoformat()})
    first_trade_at = min((str(trade["open_time"]) for trade in trades), default=None)
    last_trade_at = max((str(trade["close_time"]) for trade in trades), default=None)
    payload = {
        "label": product.label,
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "period_key": period,
        "mode": mode,
        "currency": "USD",
        "series": sample_series(series),
        "stats": native,
        "available_from": start.isoformat(),
        "available_to": end.isoformat(),
        "cached_trade_count": len(trades),
        "trade_coverage_from": first_trade_at,
        "trade_coverage_to": last_trade_at,
        "notice": "Precomputed native MT5 Every Tick result using the exact active recommended EA and SET file.",
        "source": "precomputed-native-mt5-cache",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_quality": native.get("history_quality"),
    }
    return payload, trades


def portfolio_metrics(trades: list[dict[str, Any]], start: date, end: date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ordered = sorted(trades, key=lambda row: (str(row["close_time"]), str(row.get("ea", "")), int(row.get("number", 0))))
    balance = 10_000.0
    peak = balance
    maximum_drawdown_cash = 0.0
    maximum_drawdown_pct = 0.0
    series: list[dict[str, Any]] = [{"time": f"{start.isoformat()}T00:00:00", "balance": balance}]
    outcomes: list[float] = []
    normalized: list[dict[str, Any]] = []
    for number, row in enumerate(ordered, 1):
        outcome = float(row["net_profit"])
        outcomes.append(outcome)
        balance += outcome
        peak = max(peak, balance)
        drawdown = peak - balance
        maximum_drawdown_cash = max(maximum_drawdown_cash, drawdown)
        maximum_drawdown_pct = max(maximum_drawdown_pct, drawdown / peak * 100 if peak else 0.0)
        series.append({"time": str(row["close_time"]), "balance": round(balance, 2)})
        normalized.append({**row, "number": number})
    series.append({"time": f"{end.isoformat()}T23:59:59", "balance": round(balance, 2)})
    gross_profit = sum(value for value in outcomes if value > 0)
    gross_loss = -sum(value for value in outcomes if value < 0)
    profit_factor = gross_profit / gross_loss if gross_loss else (999.0 if gross_profit else None)
    win_rate = sum(value > 0 for value in outcomes) / len(outcomes) * 100 if outcomes else None
    sharpe = None
    if len(outcomes) > 1:
        deviation = statistics.pstdev(outcomes)
        if deviation:
            sharpe = statistics.mean(outcomes) / deviation * math.sqrt(len(outcomes))
    net = balance - 10_000.0
    stats = {
        "initial_balance": 10_000.0,
        "final_balance": round(balance, 2),
        "net_profit": round(net, 2),
        "return_pct": round(net / 10_000.0 * 100, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "win_rate_pct": round(win_rate, 2) if win_rate is not None else None,
        "max_drawdown_pct": round(maximum_drawdown_pct, 2),
        "max_drawdown_cash": round(maximum_drawdown_cash, 2),
        "trades": len(outcomes),
        "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,
        "recovery_factor": round(net / maximum_drawdown_cash, 2) if maximum_drawdown_cash else None,
        "gross_profit_before_costs": round(sum(float(row.get("gross_profit") if row.get("gross_profit") is not None else float(row.get("net_profit") or 0.0) - float(row.get("commission") or 0.0) - float(row.get("swap") or 0.0)) for row in ordered), 2),
        "commission": round(sum(float(row.get("commission") or 0.0) for row in ordered), 2),
        "swap": round(sum(float(row.get("swap") or 0.0) for row in ordered), 2),
        "total_costs": round(sum(float(row.get("commission") or 0.0) + float(row.get("swap") or 0.0) for row in ordered), 2),
        "from": start.isoformat(),
        "to": end.isoformat(),
    }
    return stats, series


def portfolio_analytics(
    trades: list[dict[str, Any]],
    series: list[dict[str, Any]],
    initial_balance: float = 10_000.0,
) -> dict[str, Any]:
    """Build deployable portfolio breakdowns from the complete cached MT5 ledger."""
    outcomes = [float(row.get("net_profit") or 0.0) for row in trades]
    wins = [value for value in outcomes if value > 0]
    losses = [value for value in outcomes if value < 0]

    assets: dict[str, dict[str, Any]] = {}
    directions: dict[str, dict[str, Any]] = {
        "Long": {"side": "Long", "trades": 0, "wins": 0, "net_profit": 0.0},
        "Short": {"side": "Short", "trades": 0, "wins": 0, "net_profit": 0.0},
    }
    monthly: dict[str, float] = {}
    for row in trades:
        net = float(row.get("net_profit") or 0.0)
        symbol = str(row.get("symbol") or "Unknown").upper()
        asset = assets.setdefault(symbol, {"symbol": symbol, "trades": 0, "wins": 0, "net_profit": 0.0})
        asset["trades"] += 1
        asset["wins"] += int(net > 0)
        asset["net_profit"] += net

        side_text = str(row.get("side") or "").lower()
        side = "Long" if "buy" in side_text or "long" in side_text else "Short"
        directions[side]["trades"] += 1
        directions[side]["wins"] += int(net > 0)
        directions[side]["net_profit"] += net

        closed = str(row.get("close_time") or "")
        month = closed[:7] if len(closed) >= 7 else "Unknown"
        monthly[month] = monthly.get(month, 0.0) + net

    asset_rows: list[dict[str, Any]] = []
    for asset in assets.values():
        trade_count = int(asset["trades"])
        net = float(asset["net_profit"])
        asset_rows.append(
            {
                **asset,
                "net_profit": round(net, 2),
                "return_contribution_pct": round(net / initial_balance * 100, 2),
                "win_rate_pct": round(float(asset["wins"]) / trade_count * 100, 2) if trade_count else None,
                "trade_share_pct": round(trade_count / len(trades) * 100, 2) if trades else 0.0,
            }
        )
    asset_rows.sort(key=lambda row: float(row["net_profit"]), reverse=True)

    direction_rows: list[dict[str, Any]] = []
    for direction in directions.values():
        trade_count = int(direction["trades"])
        net = float(direction["net_profit"])
        direction_rows.append(
            {
                **direction,
                "net_profit": round(net, 2),
                "win_rate_pct": round(float(direction["wins"]) / trade_count * 100, 2) if trade_count else None,
                "avg_pnl": round(net / trade_count, 2) if trade_count else None,
                "trade_share_pct": round(trade_count / len(trades) * 100, 2) if trades else 0.0,
            }
        )

    ordered_series = sorted(series, key=lambda point: str(point["time"]))
    peak = float(ordered_series[0]["balance"]) if ordered_series else initial_balance
    drawdown_series: list[dict[str, Any]] = []
    for point in ordered_series:
        balance = float(point["balance"])
        peak = max(peak, balance)
        drawdown = (balance - peak) / peak * 100 if peak else 0.0
        drawdown_series.append({"time": str(point["time"]), "drawdown_pct": round(drawdown, 4)})

    return {
        "trade_stats": {
            "average_win": round(statistics.mean(wins), 2) if wins else None,
            "average_loss": round(statistics.mean(losses), 2) if losses else None,
            "best_trade": round(max(outcomes), 2) if outcomes else None,
            "worst_trade": round(min(outcomes), 2) if outcomes else None,
            "payoff_ratio": round(statistics.mean(wins) / abs(statistics.mean(losses)), 2) if wins and losses else None,
        },
        "drawdown_series": sample_series(drawdown_series, maximum=2_000),
        "assets": asset_rows,
        "monthly_pnl": [
            {"month": month, "net_profit": round(net, 2)}
            for month, net in sorted(monthly.items())
            if month != "Unknown"
        ],
        "directions": direction_rows,
    }


def build_portfolio(products: list[Product], period: str, start: date, end: date) -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    included: list[dict[str, Any]] = []
    for product in products:
        selected_mode = (
            "dynamic"
            if product.recommended_dynamic_mode and product.dynamic_mode_supported
            else "safe"
            if product.recommended_safe_mode
            else "standard"
        )
        payload_path = product_cache_path(product.slug, selected_mode, period)
        trades_path = product_trades_path(product.slug, selected_mode, period)
        if not payload_path.is_file() or not trades_path.is_file():
            included.append(
                {
                    "slug": product.slug,
                    "label": product.label,
                    "symbol": product.canonical,
                    "timeframe": product.timeframe,
                    "mode": selected_mode,
                    "available": False,
                }
            )
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
        product_trades = [
            trade
            for trade in json.loads(trades_path.read_text(encoding="utf-8-sig"))
            if start.isoformat() <= str(trade.get("close_time") or "")[:10] <= end.isoformat()
        ]
        all_trades.extend(product_trades)
        included.append(
            {
                "slug": product.slug,
                "label": product.label,
                "symbol": product.canonical,
                "timeframe": product.timeframe,
                "mode": selected_mode,
                "available": True,
                "net_profit": payload["stats"].get("net_profit"),
                "return_pct": payload["stats"].get("return_pct"),
                "profit_factor": payload["stats"].get("profit_factor"),
                "win_rate_pct": payload["stats"].get("win_rate_pct"),
                "max_drawdown_pct": payload["stats"].get("max_drawdown_pct"),
                "trades": payload["stats"].get("trades"),
            }
        )
    current_stats, current_series = portfolio_metrics(all_trades, start, end)
    current_analytics = portfolio_analytics(all_trades, current_series, float(current_stats["initial_balance"]))
    adaptive_trades, activations, skipped_by_ea = simulate_adaptive_portfolio(all_trades)
    stats, series = portfolio_metrics(adaptive_trades, start, end)
    analytics = portfolio_analytics(adaptive_trades, series, float(stats["initial_balance"]))

    comparison_rows: list[dict[str, Any]] = []
    for row in included:
        slug = str(row["slug"])
        if not row.get("available"):
            comparison_rows.append({**row, "current": {}, "recommended": {}, "skipped_trades": 0})
            continue
        current_ea_trades = [trade for trade in all_trades if str(trade.get("cache_slug") or "") == slug]
        adaptive_ea_trades = [trade for trade in adaptive_trades if str(trade.get("cache_slug") or "") == slug]
        current_ea, _ = portfolio_metrics(current_ea_trades, start, end)
        recommended_ea, _ = portfolio_metrics(adaptive_ea_trades, start, end)
        comparison_rows.append(
            {
                **row,
                "net_profit": recommended_ea["net_profit"],
                "return_pct": recommended_ea["return_pct"],
                "profit_factor": recommended_ea["profit_factor"],
                "win_rate_pct": recommended_ea["win_rate_pct"],
                "max_drawdown_pct": recommended_ea["max_drawdown_pct"],
                "trades": recommended_ea["trades"],
                "current": current_ea,
                "recommended": recommended_ea,
                "skipped_trades": int(skipped_by_ea.get(slug, 0)),
            }
        )
    comparison_rows.sort(key=lambda row: float(row["recommended"].get("net_profit") or 0.0), reverse=True)
    first_trade_at = min((str(trade["open_time"]) for trade in all_trades), default=None)
    last_trade_at = max((str(trade["close_time"]) for trade in all_trades), default=None)
    tested_count = sum(bool(row.get("available")) for row in included)
    current_payload = {
        "label": f"Current {tested_count}-EA tested portfolio",
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "period_key": period,
        "mode": "current",
        "currency": "USD",
        "series": sample_series(current_series),
        "stats": current_stats,
        "available_from": start.isoformat(),
        "available_to": end.isoformat(),
        "cached_trade_count": len(all_trades),
        "trade_coverage_from": first_trade_at,
        "trade_coverage_to": last_trade_at,
        "included_eas": included,
        "analytics": current_analytics,
        "included_ea_count": len(included),
        "tested_ea_count": tested_count,
        "expected_ea_count": len(products),
        "notice": "Current chronological cash-flow overlay of separate native MT5 tests using each EA's selected mode. Commission and swap are included in every net result.",
        "source": "precomputed-native-mt5-cache",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = {
        "label": f"Recommended adaptive {tested_count}-EA tested portfolio",
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "period_key": period,
        "mode": "recommended-adaptive",
        "currency": "USD",
        "series": sample_series(series),
        "stats": stats,
        "datasets": [
            {"label": "Recommended adaptive", "color": "#7ef7c7", "series": sample_series(series), "stats": stats},
            {"label": "Current profile", "color": "#68a7ff", "series": sample_series(current_series), "stats": current_stats},
        ],
        "available_from": start.isoformat(),
        "available_to": end.isoformat(),
        "cached_trade_count": len(adaptive_trades),
        "trade_coverage_from": first_trade_at,
        "trade_coverage_to": last_trade_at,
        "included_eas": comparison_rows,
        "analytics": analytics,
        "included_ea_count": len(included),
        "tested_ea_count": tested_count,
        "expected_ea_count": len(products),
        "candidate_trade_count": len(all_trades),
        "skipped_trade_count": len(all_trades) - len(adaptive_trades),
        "adaptive_activations": activations,
        "adaptive_rules": list(ADAPTIVE_RULES),
        "notice": "Recommended adaptive replay of the existing native MT5 trade ledger. The four news EAs are exempt: no adaptive entry skips or risk scaling. Non-News controls are unchanged and still count news P/L in account-wide checks. Net P/L includes commission and swap; scaled non-News costs are proportional to modelled position size. Gold News V9 contributes only when evidence exists. This is not a simultaneous shared-margin MT5 run.",
        "source": "adaptive-replay-of-native-mt5-cache",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(portfolio_cache_path("current", period), current_payload)
    write_json(portfolio_trades_path("current", period), sorted(all_trades, key=lambda row: str(row["close_time"])))
    write_json(portfolio_cache_path("standard", period), payload)
    write_json(portfolio_trades_path("standard", period), adaptive_trades)
    write_json(portfolio_cache_path("recommended-adaptive", period), payload)
    write_json(portfolio_trades_path("recommended-adaptive", period), adaptive_trades)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Precompute fixed-period native MT5 evidence for the active recommended portfolio.")
    parser.add_argument("--period", choices=["all", *PERIOD_MONTHS], default="all")
    parser.add_argument("--slug", action="append", help="Limit generation to one or more EA slugs.")
    parser.add_argument("--safe", action="store_true", help="Also generate Safe mode for compatible EAs.")
    parser.add_argument("--dynamic", action="store_true", help="Also generate saved Dynamic London mode when available.")
    parser.add_argument("--recommended-only", action="store_true", help="Generate only each EA's selected recommended Standard, Safe or Dynamic mode.")
    parser.add_argument("--force", action="store_true", help="Ignore reusable native source reports.")
    parser.add_argument("--portfolio-only", action="store_true", help="Only rebuild portfolio caches from existing EA caches.")
    parser.add_argument("--reparse-cached-sources", action="store_true", help="Rebuild existing product caches from retained native reports without launching MT5.")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    products = get_sellable_catalog()
    if args.slug:
        wanted = set(args.slug)
        products = [product for product in products if product.slug in wanted]
        missing = wanted - {product.slug for product in products}
        if missing:
            raise SystemExit(f"Unknown EA slug(s): {', '.join(sorted(missing))}")
    periods = list(PERIOD_MONTHS) if args.period == "all" else [args.period]
    failures: list[dict[str, str]] = []
    generated: list[dict[str, Any]] = []

    if args.reparse_cached_sources:
        for product in products:
            modes = ["standard"] + (["safe"] if product.safe_filter_supported else []) + (["dynamic"] if product.dynamic_mode_supported else [])
            for mode in modes:
                for period in periods:
                    report, _ = source_paths(product, mode, period)
                    summary_path = product_cache_path(product.slug, mode, period)
                    if not report.is_file() or not summary_path.is_file():
                        continue
                    old_summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
                    start = date.fromisoformat(str(old_summary["available_from"]))
                    end = date.fromisoformat(str(old_summary["available_to"]))
                    payload, trades = product_payload(product, mode, period, start, end, report)
                    write_json(summary_path, payload)
                    write_json(product_trades_path(product.slug, mode, period), trades)
                    generated.append({"slug": product.slug, "mode": mode, "period": period, "stats": payload["stats"]})
                    print(f"REPARSED {product.label} {mode} {period}: {len(trades)} trades with broker costs", flush=True)
    elif not args.portfolio_only:
        removed = cleanup_stale_dynamic_artifacts()
        print(f"CLEANUP removed {removed} stale isolated-tester artifacts", flush=True)
        for product in products:
            modes = [recommended_mode(product)] if args.recommended_only else (
                ["standard"]
                + (["safe"] if args.safe and product.safe_filter_supported else [])
                + (["dynamic"] if args.dynamic and product.dynamic_mode_supported else [])
            )
            for mode in modes:
                for period in periods:
                    start = subtract_months(args.end, PERIOD_MONTHS[period])
                    try:
                        report = run_native(product, mode, period, start, args.end, force=args.force)
                        payload, trades = product_payload(product, mode, period, start, args.end, report)
                        write_json(product_cache_path(product.slug, mode, period), payload)
                        write_json(product_trades_path(product.slug, mode, period), trades)
                        generated.append({"slug": product.slug, "mode": mode, "period": period, "stats": payload["stats"]})
                        print(
                            f"DONE {product.label} {mode} {period}: "
                            f"{payload['stats'].get('return_pct')}% | PF {payload['stats'].get('profit_factor')} | "
                            f"WR {payload['stats'].get('win_rate_pct')}% | DD {payload['stats'].get('max_drawdown_pct')}% | "
                            f"{len(trades)} trades",
                            flush=True,
                        )
                    except Exception as exc:
                        failures.append({"slug": product.slug, "mode": mode, "period": period, "error": str(exc)})
                        print(f"FAILED {product.label} {mode} {period}: {exc}", flush=True)

    portfolio_rows: list[dict[str, Any]] = []
    full_catalog = get_sellable_catalog()
    for period in periods:
        start = subtract_months(args.end, PERIOD_MONTHS[period])
        portfolio_end = args.end
        if (args.portfolio_only or args.reparse_cached_sources) and full_catalog:
            reference_mode = (
                "dynamic"
                if full_catalog[0].recommended_dynamic_mode and full_catalog[0].dynamic_mode_supported
                else "safe"
                if full_catalog[0].recommended_safe_mode
                else "standard"
            )
            reference_path = product_cache_path(full_catalog[0].slug, reference_mode, period)
            if reference_path.is_file():
                reference = json.loads(reference_path.read_text(encoding="utf-8-sig"))
                start = date.fromisoformat(str(reference["available_from"]))
                portfolio_end = date.fromisoformat(str(reference["available_to"]))
        portfolio = build_portfolio(full_catalog, period, start, portfolio_end)
        portfolio_rows.append({"period": period, "stats": portfolio["stats"], "included_ea_count": portfolio["included_ea_count"], "tested_ea_count": portfolio["tested_ea_count"]})
        print(f"PORTFOLIO {period}: {portfolio['stats']}", flush=True)

    # Portfolio-only/partial refreshes must not erase the source-run inventory.
    manifest_path = CACHE_ROOT / "manifest.json"
    previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.is_file() else {}
    current_slugs = {product.slug for product in full_catalog}
    run_inventory = {
        (row["slug"], row["mode"], row["period"]): row
        for row in previous_manifest.get("generated_runs", [])
        if row.get("slug") in current_slugs
    }
    run_inventory.update({(row["slug"], row["mode"], row["period"]): row for row in generated})
    manifest = {
        "cache_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "end_date": str(portfolio_rows[-1]["stats"]["to"]) if portfolio_rows else args.end.isoformat(),
        "periods": PERIOD_OPTIONS,
        "recommended_eas": [
            {
                "slug": product.slug,
                "label": product.label,
                "symbol": product.canonical,
                "timeframe": product.timeframe,
                "mode": (
                    "dynamic"
                    if product.recommended_dynamic_mode and product.dynamic_mode_supported
                    else "safe"
                    if product.recommended_safe_mode
                    else "standard"
                ),
            }
            for product in full_catalog
        ],
        "recommended_ea_count": len(full_catalog),
        "tested_ea_count": portfolio_rows[-1]["tested_ea_count"] if portfolio_rows else 0,
        "active_portfolio_mode": "recommended-adaptive",
        "adaptive_rules": list(ADAPTIVE_RULES),
        "cost_accounting": "Commission and swap are parsed separately from native MT5 entry and exit deals and are included in net P/L. Adaptive costs scale linearly with the modelled position size.",
        "generated_runs": [run_inventory[key] for key in sorted(run_inventory)],
        "portfolio": portfolio_rows,
        "failures": failures,
        "methodology": "Each cached EA period is an independent native MT5 Every Tick run from a USD 10,000 starting balance using its exact active recommended EA, SET and evidence-selected Standard, Safe or Dynamic mode. The current portfolio chronologically overlays those realized cash flows; the website default applies the approved Recommended Adaptive rules to the same signals without claiming a shared-margin MT5 run.",
    }
    write_json(CACHE_ROOT / "manifest.json", manifest)
    print(f"MANIFEST {CACHE_ROOT / 'manifest.json'}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
