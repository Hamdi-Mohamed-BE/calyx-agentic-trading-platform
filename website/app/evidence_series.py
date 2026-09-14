from __future__ import annotations

import json
import math
import re
import statistics
from datetime import date, datetime, time
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import Any

from .catalog import (
    BOOKMAPER_ROOT,
    FILTERED_AUDIT_ROOT,
    PACKAGE_ROOT,
    REGIME_SWITCH_ROOT,
    SELECTED_CONFIGS,
    SELECTED_PORTFOLIO_ROOT,
    Product,
)


ACTIVE_AUDIT_ROOT = PACKAGE_ROOT / "Active BAT Backtest 2026-08-12"
ACTIVE_REPORTS_ROOT = ACTIVE_AUDIT_ROOT / "MT5 Reports"
ACTIVE_RESULTS_PATH = ACTIVE_AUDIT_ROOT / "portfolio-results.json"
DEPLOYMENT_MODES_PATH = FILTERED_AUDIT_ROOT / "deployment-mode-results.json"
REGIME_FILTER_PATH = BOOKMAPER_ROOT / "artifacts" / "active-ea-regime-filter.json"
SELECTED_RESULTS_PATH = SELECTED_PORTFOLIO_ROOT / "locked-results.json"

CUSTOM_SERIES: dict[str, tuple[Path, str]] = {
    "US100 ORB 0.5R": (
        PACKAGE_ROOT
        / "US100 Selective ORB Research 2026-08-21"
        / "native-rr05-bat-one-year-results.json",
        "one-year-2025-2026",
    ),
    "US100 ORB 2R": (
        PACKAGE_ROOT
        / "US100 Selective ORB Research 2026-08-21"
        / "native-v3-time-direction-results.json",
        "one-year-2025-2026",
    ),
    "US100 Selective ORB V3": (
        PACKAGE_ROOT
        / "US100 Selective ORB Research 2026-08-21"
        / "native-v3-time-direction-results.json",
        "one-year-2025-2026",
    ),
    "Nasdaq 5M Candle Momentum": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "11 Nasdaq 5M Candle Momentum"
        / "all-results.json",
        "ustec-full-fixed-rr2.5",
    ),
    "EMA3": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "08 EMA3"
        / "Backtest Reports"
        / "ThreeYear"
        / "results.json",
        "manage-dynamic6020-only",
    ),
    "XAU Weakness": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "09 XAU Weakness"
        / "Backtest Reports"
        / "ThreeYear"
        / "results.json",
        "selected-m30-rr400-dynamic5020",
    ),
}

SAFE_CUSTOM_SERIES: dict[str, tuple[Path, str]] = {
    "Nasdaq 5M Candle Momentum": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "11 Nasdaq 5M Candle Momentum"
        / "Reports"
        / "full"
        / "ustec-full-fixed-rr2.5-safe.json",
        "ustec-full-fixed-rr2.5-safe",
    ),
    "EMA3": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "08 EMA3"
        / "Backtest Reports"
        / "ThreeYear"
        / "results.json",
        "manage-dynamic6020-only-safe",
    ),
    "XAU Weakness": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "09 XAU Weakness"
        / "Backtest Reports"
        / "ThreeYear"
        / "results.json",
        "selected-m30-rr400-safe5020",
    ),
}

SAFE_CUSTOM_REPORTS: dict[str, Path] = {
    "ETH Top Down FVG Liquidity": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "03 ETH Top Down FVG"
        / "Backtest Reports"
        / "Locked"
        / "eth-locked-combo-rr4-dynamic5020-safe.htm"
    ),
    "Engineered Liquidity XAU": (
        PACKAGE_ROOT
        / "Engineered Liquidity Sweep Research 2026-08-30"
        / "Improvement Reports"
        / "xauusd--safe-rr2--locked.htm"
    ),
    "Engineered Liquidity BTC": (
        PACKAGE_ROOT
        / "Engineered Liquidity Sweep Research 2026-08-30"
        / "Improvement Reports"
        / "btcusd--safe-displacement--locked.htm"
    ),
}

CUSTOM_REPORTS: dict[str, Path] = {
    "BTC Top Down FVG Liquidity": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "02 BTC Top Down FVG"
        / "Backtest Reports"
        / "Locked"
        / "btc-locked-rr-200.htm"
    ),
    "News Pulse XAU": (
        PACKAGE_ROOT
        / "News Pulse Direction Research 2026-09-05"
        / "Backtest Reports"
        / "Hard 1.5 Full"
        / "xauusd__two-sided__hard1p5__native60.htm"
    ),
    "News Pulse XAG": (
        PACKAGE_ROOT
        / "News Pulse Direction Research 2026-09-05"
        / "Backtest Reports"
        / "Hard 1.5 Full"
        / "xagusd__two-sided__hard1p5__native60.htm"
    ),
    "News Pulse BTC": (
        PACKAGE_ROOT
        / "News Pulse BTC Official 3Y Research 2026-09-11"
        / "Backtest Reports"
        / "btcusd__official-3y.htm"
    ),
    "XAU ORB New York M30": (
        PACKAGE_ROOT
        / "ORB Session Matrix Research 2026-09-05"
        / "Backtest Reports"
        / "locked"
        / "xauusd--new-york--development-selected--locked.htm"
    ),
    "XAU ORB London NY Overlap M30": (
        PACKAGE_ROOT
        / "ORB Session Matrix Research 2026-09-05"
        / "Backtest Reports"
        / "locked"
        / "xauusd--overlap--development-selected--locked.htm"
    ),
    "US100 ORB New York M30": (
        PACKAGE_ROOT
        / "ORB Session Matrix Research 2026-09-05"
        / "Backtest Reports"
        / "locked"
        / "ustec--new-york--development-selected--locked.htm"
    ),
    "US100 H1 ORB 13UTC": (
        PACKAGE_ROOT
        / "ORB H1 Range Research 2026-09-05"
        / "Backtest Reports"
        / "locked-rr-extension"
        / "ustec--overlap-1300--rr6--locked-rr-extension.htm"
    ),
    "US100 Selective ORB V3": (
        PACKAGE_ROOT
        / "US100 Selective ORB Research 2026-08-21"
        / "Backtest Reports"
        / "v3-time-direction"
        / "One Year"
        / "one-year-2025-2026.htm"
    ),
    "BTC POC Fibonacci": (
        PACKAGE_ROOT
        / "POC Fibonacci Volume Profile Research 2026-09-04"
        / "Backtest Reports"
        / "locked"
        / "btcusd--optimized--locked.htm"
    ),
    "XAU Trend Progression": (
        PACKAGE_ROOT
        / "Trend Progression Research 2026-09-02"
        / "Backtest Reports"
        / "locked"
        / "xauusd--h4--optimized--locked.htm"
    ),
    "XAU Elliott Wave 1-2-3": (
        PACKAGE_ROOT
        / "Elliott Wave Research 2026-09-05"
        / "Backtest Reports"
        / "locked"
        / "xauusd--h4--optimized--locked.htm"
    ),
    "XAU Slow Trend": (
        PACKAGE_ROOT
        / "Slow Multi Asset Trend Research 2026-09-06"
        / "Native"
        / "xauusd-selected-test-model0"
        / "xauusd-selected-test-model0.htm"
    ),
    "XAG Session VWAP Snapback": (
        PACKAGE_ROOT
        / "Session VWAP Snapback Research 2026-09-06"
        / "Native"
        / "xagusd-frozen-locked-model0"
        / "xagusd-frozen-locked-model0.htm"
    ),
    "US100 Month End Flow": (
        PACKAGE_ROOT
        / "Month End Institutional Flow Research 2026-09-06"
        / "Native"
        / "ustec-frozen-locked-model0"
        / "ustec-frozen-locked-model0.htm"
    ),
    "XAU RSI VWAP": (
        PACKAGE_ROOT
        / "RSI VWAP Research 2026-09-02"
        / "Backtest Reports"
        / "Locked Last Year Every Tick 2025-2026"
        / "xauusd--h1--optimized--locked.htm"
    ),
    "Engineered Liquidity XAU": (
        PACKAGE_ROOT
        / "Engineered Liquidity Sweep Research 2026-08-30"
        / "Improvement Reports"
        / "xauusd--rr2--locked.htm"
    ),
    "Engineered Liquidity BTC": (
        PACKAGE_ROOT
        / "Engineered Liquidity Sweep Research 2026-08-30"
        / "Improvement Reports"
        / "btcusd--displacement--locked.htm"
    ),
    "US100 Fabio ORB 1R": (
        PACKAGE_ROOT
        / "US100 Fabio ORB Volatility Target Research 2026-08-26"
        / "Backtest Reports"
        / "literal-one-year-every-tick.htm"
    ),
    "BTC Top Down FVG Liquidity": (
        PACKAGE_ROOT
        / "Top Down FVG Liquidity Research 2026-08-27"
        / "Backtest Reports"
        / "btcusd-locked-year.htm"
    ),
    "ETH Top Down FVG Liquidity": (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "03 ETH Top Down FVG"
        / "Backtest Reports"
        / "Locked"
        / "eth-locked-combo-rr4-dynamic5020.htm"
    ),
    "Nasdaq Overnight": (
        PACKAGE_ROOT
        / "US100 Overnight Optimization 2026-09-04"
        / "Backtest Reports"
        / "locked"
        / "locked--current-negative-close-open.htm"
    ),
    "USDJPY London Open Momentum": (
        PACKAGE_ROOT
        / "London Open FX Momentum Research 2026-09-08"
        / "Pipeline"
        / "Backtest Reports"
        / "USDJPY"
        / "final"
        / "usdjpy--final--selected-latest--m0--20250901-20260901--46e01de1e9.htm"
    ),
}

INSTALLER_LABEL_ALIASES: dict[str, str] = {}

ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
TIME_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _clean_cell(value: str) -> str:
    return " ".join(unescape(TAG_RE.sub("", value)).replace("\xa0", " ").split())


def _number(value: str) -> float:
    return float(value.replace(" ", "").replace(",", ""))


def _sample(series: list[dict[str, Any]], maximum: int = 900) -> list[dict[str, Any]]:
    if len(series) <= maximum:
        return series
    step = (len(series) - 1) / (maximum - 1)
    indexes = sorted({round(index * step) for index in range(maximum)} | {0, len(series) - 1})
    return [series[index] for index in indexes]


@lru_cache(maxsize=32)
def parse_mt5_balance_series(report_path: Path) -> tuple[dict[str, Any], ...]:
    raw: str | None = None
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            raw = report_path.read_text(encoding=encoding)
            break
        except UnicodeError:
            continue
    if raw is None:
        return ()

    marker = raw.lower().find("<b>deals</b>")
    if marker < 0:
        return ()

    series: list[dict[str, Any]] = []
    for row_html in ROW_RE.findall(raw[marker:]):
        cells = [_clean_cell(cell) for cell in CELL_RE.findall(row_html)]
        if len(cells) < 12 or not TIME_RE.match(cells[0]):
            continue
        try:
            balance = _number(cells[11])
        except ValueError:
            continue
        series.append(
            {
                "time": cells[0].replace(".", "-", 2).replace(" ", "T", 1),
                "balance": round(balance, 2),
            }
        )
    return tuple(_sample(series))


def _normalise_json_series(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for point in values:
        timestamp = point.get("time") or point.get("date")
        balance = point.get("balance")
        if timestamp is None or balance is None:
            continue
        text_time = str(timestamp).replace(" ", "T", 1)
        series.append({"time": text_time, "balance": round(float(balance), 2)})
    return _sample(series)


def _summary_performance_series(product: Product, mode: str) -> list[dict[str, Any]]:
    """Honest two-point fallback when the detailed MT5 deal path is not deployed."""
    evidence = (
        product.safe_evidence
        if mode == "safe" and product.safe_evidence
        else product.dynamic_evidence
        if mode == "dynamic" and product.dynamic_evidence
        else product.evidence
    )
    if evidence is None:
        return []
    dates = DATE_RE.findall(evidence.period)
    if len(dates) < 2:
        return []
    initial = 10_000.0
    final = initial * (1.0 + float(evidence.return_pct) / 100.0)
    return [
        {"time": f"{dates[0]}T00:00:00", "balance": initial, "summary": True},
        {"time": f"{dates[-1]}T23:59:59", "balance": round(final, 2), "summary": True},
    ]


@lru_cache(maxsize=1)
def _active_bot_rows() -> tuple[dict[str, Any], ...]:
    if not ACTIVE_RESULTS_PATH.is_file():
        return ()
    data = _load_json(ACTIVE_RESULTS_PATH)
    return tuple(data.get("bots", []))


def _active_report_for(installer_label: str) -> Path | None:
    wanted = INSTALLER_LABEL_ALIASES.get(installer_label, installer_label)
    for row in _active_bot_rows():
        if row.get("label") == wanted and row.get("file"):
            path = ACTIVE_REPORTS_ROOT / str(row["file"])
            return path if path.is_file() else None
    return None


@lru_cache(maxsize=1)
def _selected_rows() -> dict[tuple[str, str], dict[str, Any]]:
    if not SELECTED_RESULTS_PATH.is_file():
        return {}
    return {
        (str(row.get("EaId")), str(row.get("Variant"))): row
        for row in _load_json(SELECTED_RESULTS_PATH)
        if row.get("Stage") == "Locked" and row.get("status") == "valid"
    }


def _selected_product_series(product: Product, use_current: bool = False) -> list[dict[str, Any]]:
    config = SELECTED_CONFIGS.get(product.installer_label)
    if config is None:
        return []
    ea_id, selected_variant, _exit_mode = config
    variant = "current" if use_current else selected_variant
    row = _selected_rows().get((ea_id, variant))
    if row is None:
        return []
    return _normalise_json_series(row.get("series", []))


@lru_cache(maxsize=2)
def _regime_switch_series(scope: str = "full") -> tuple[dict[str, Any], ...]:
    path = REGIME_SWITCH_ROOT / "true-switch-trades.json"
    if not path.is_file():
        return ()
    trades = _load_json(path).get("XAUUSD", {}).get(scope, [])
    if not trades:
        return ()
    balance = 10_000.0
    start = "2023-09-01T00:00:00+00:00" if scope == "full" else "2025-09-01T00:00:00+00:00"
    series = [{"time": start, "balance": balance}]
    for trade in sorted(trades, key=lambda row: str(row.get("exit_time", ""))):
        balance *= 1.0 + float(trade.get("return_fraction", 0.0))
        series.append({"time": str(trade["exit_time"]), "balance": round(balance, 2)})
    return tuple(series)


def _selected_portfolio_series(use_current: bool = False) -> tuple[dict[str, Any], ...]:
    events: list[tuple[str, float]] = []
    for installer_label, (ea_id, selected_variant, _exit_mode) in SELECTED_CONFIGS.items():
        # The public combined audit was locked before XAU RSI VWAP was added.
        # Keep its separate evidence out of this historical 12-EA overlay.
        if ea_id == "rsi-vwap-xau":
            continue
        if ea_id == "regime-switch-xau":
            series = [dict(point) for point in _regime_switch_series("full")]
            for previous, current in zip(series, series[1:]):
                events.append((str(current["time"]), float(current["balance"]) - float(previous["balance"])))
            continue
        if installer_label == "Nasdaq 5M Candle Momentum":
            # Step 11 supersedes the older selected-portfolio reconstruction
            # with the frozen fixed-2.5R native MT5 series.
            series = [dict(point) for point in _custom_series(installer_label)]
            for previous, current in zip(series, series[1:]):
                events.append((str(current["time"]), float(current["balance"]) - float(previous["balance"])))
            continue
        variant = "current" if use_current else selected_variant
        row = _selected_rows().get((ea_id, variant))
        if row is None:
            report = CUSTOM_REPORTS.get(installer_label)
            if report is not None and report.is_file():
                series = [dict(point) for point in parse_mt5_balance_series(report)]
                for previous, current in zip(series, series[1:]):
                    events.append(
                        (
                            str(current["time"]),
                            float(current["balance"]) - float(previous["balance"]),
                        )
                    )
            continue
        series = _normalise_json_series(row.get("series", []))
        for previous, current in zip(series, series[1:]):
            events.append(
                (
                    str(current["time"]),
                    float(current["balance"]) - float(previous["balance"]),
                )
            )
    if not events:
        return ()
    balance = 10_000.0
    combined = [{"time": "2025-09-01T00:00:00", "balance": balance}]
    for timestamp, delta in sorted(events, key=lambda item: item[0]):
        balance += delta
        combined.append({"time": timestamp, "balance": round(balance, 2)})
    return tuple(_sample(combined, maximum=5_000))


@lru_cache(maxsize=8)
def _custom_series(label: str) -> tuple[dict[str, Any], ...]:
    config = CUSTOM_SERIES.get(label)
    if config is None:
        return ()
    path, case_name = config
    if not path.is_file():
        return ()
    data = _load_json(path)
    rows = data if isinstance(data, list) else [data]
    selected = next((row for row in rows if row.get("case") == case_name), None)
    if selected is None:
        return ()
    return tuple(_normalise_json_series(selected.get("series", [])))


def _safe_overlay_series(product: Product) -> list[dict[str, Any]]:
    if not product.safe_filter_supported:
        return []
    native_report = SAFE_CUSTOM_REPORTS.get(product.label)
    if native_report is not None and native_report.is_file():
        return [dict(point) for point in parse_mt5_balance_series(native_report)]
    safe_custom = SAFE_CUSTOM_SERIES.get(product.label)
    if safe_custom is not None:
        path, case_name = safe_custom
        if path.is_file():
            data = _load_json(path)
            rows = data if isinstance(data, list) else [data]
            selected = next((row for row in rows if row.get("case") == case_name), None)
            if selected is not None:
                return _normalise_json_series(selected.get("series", []))
    if not REGIME_FILTER_PATH.is_file():
        return []
    if product.label in {"Asia Breakout", "XAU Weakness", "XAU Markov Regime"}:
        return product_equity_series(product, "standard")
    aliases = {
        "News Pulse": "News Pulse",
    }
    wanted = aliases.get(product.label, product.label)
    data = _load_json(REGIME_FILTER_PATH)
    events = [
        row for row in data.get("decisions", [])
        if row.get("bot") == wanted and row.get("accepted")
    ]
    events.sort(key=lambda row: (str(row.get("close_time")), str(row.get("open_time"))))
    if not events:
        return []
    balance = 10_000.0
    series = [{"time": "2025-08-11T00:00:00", "balance": balance}]
    for event in events:
        balance += float(event.get("base_net", 0.0))
        series.append({"time": str(event["close_time"]), "balance": round(balance, 2)})
    return _sample(series)


def product_equity_series(product: Product, mode: str = "standard") -> list[dict[str, Any]]:
    if mode == "safe":
        safe = _safe_overlay_series(product)
        if safe:
            return safe
    if product.label in {"EMA3", "XAU Weakness", "Nasdaq 5M Candle Momentum"} and mode != "safe":
        # Focused pipeline steps promoted independently audited configurations.
        # Prefer those exact three-year series over the older portfolio audit.
        custom = [dict(point) for point in _custom_series(product.label)]
        if custom:
            return custom
    if product.label == "XAU Regime Switch":
        return [dict(point) for point in _regime_switch_series("full")]
    if product.label == "Nasdaq Overnight" and mode != "safe":
        # The fresh optimization is newer than the selected-portfolio audit.
        # Load the exact active native report so the graph and trade table do
        # not fall back to the older archived portfolio curve.
        current_report = CUSTOM_REPORTS[product.label]
        if current_report.is_file():
            parsed = [dict(point) for point in parse_mt5_balance_series(current_report)]
            if parsed:
                return parsed
    selected = _selected_product_series(product, use_current=mode == "current")
    if selected:
        return selected
    if product.label == "XAU Markov Regime":
        path = BOOKMAPER_ROOT / "artifacts" / "standalone-results.json"
        if path.is_file():
            row = _load_json(path).get("xau", {}).get("optimized", {})
            return [
                {"time": str(point["date"]), "balance": round(float(point["equity"]), 2)}
                for point in row.get("equity", [])
            ]
    native_filtered = {
        "Asia Breakout": "asia.htm",
        "XAU Weakness": "xau-weakness.htm",
    }
    if product.label in native_filtered:
        path = PACKAGE_ROOT / "_Backtests" / "MT5-DMC-20260811" / "reports" / "selected-regime-20260828" / native_filtered[product.label]
        if path.is_file():
            parsed = [dict(point) for point in parse_mt5_balance_series(path)]
            if parsed:
                return parsed
    custom_report = CUSTOM_REPORTS.get(product.label)
    if custom_report is not None and custom_report.is_file():
        parsed = [dict(point) for point in parse_mt5_balance_series(custom_report)]
        if parsed:
            return parsed
    custom = _custom_series(product.label)
    if custom:
        return [dict(point) for point in custom]
    report = _active_report_for(product.installer_label)
    if report is None:
        return _summary_performance_series(product, mode)
    parsed = [dict(point) for point in parse_mt5_balance_series(report)]
    return parsed if parsed else _summary_performance_series(product, mode)


@lru_cache(maxsize=4)
def portfolio_equity_series(mode: str = "standard") -> tuple[dict[str, Any], ...]:
    if mode in {"standard", "current"}:
        selected = _selected_portfolio_series(use_current=mode == "current")
        if selected:
            return selected
    if DEPLOYMENT_MODES_PATH.is_file():
        data = _load_json(DEPLOYMENT_MODES_PATH)
        selected = data.get(mode, data.get("standard", {}))
        return tuple(_sample(selected.get("series", []), maximum=5_000))
    filtered_path = FILTERED_AUDIT_ROOT / "portfolio-results.json"
    if filtered_path.is_file():
        data = _load_json(filtered_path)
        return tuple(_sample(data.get("combined", {}).get("series", []), maximum=5_000))
    events: list[tuple[str, float]] = []
    for row in _active_bot_rows():
        filename = row.get("file")
        if not filename:
            continue
        series = parse_mt5_balance_series(ACTIVE_REPORTS_ROOT / str(filename))
        for previous, current in zip(series, series[1:]):
            events.append((str(current["time"]), float(current["balance"]) - float(previous["balance"])))

    balance = 10_000.0
    combined: list[dict[str, Any]] = []
    if events:
        combined.append({"time": min(timestamp for timestamp, _delta in events), "balance": balance})
    for timestamp, delta in sorted(events, key=lambda item: item[0]):
        balance += delta
        combined.append({"time": timestamp, "balance": round(balance, 2)})
    return tuple(_sample(combined, maximum=5_000))


def _point_datetime(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _date_bounds(from_date: date | None, to_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(from_date, time.min) if from_date else None
    end = datetime.combine(to_date, time.max) if to_date else None
    return start, end


def _trade_events(
    series: list[dict[str, Any]],
    expected_trades: int | None,
    label: str,
) -> list[dict[str, Any]]:
    """Reconstruct closed-trade cash flow from archived MT5 balance events.

    MT5 reports record a small entry commission balance event followed by the
    close event. Selecting the largest expected deltas identifies the closes;
    intervening costs are rolled into that trade's net outcome.
    """
    if len(series) < 2 or all(bool(point.get("summary")) for point in series):
        return []
    deltas = [
        {
            "index": index,
            "time": str(series[index]["time"]),
            "delta": float(series[index]["balance"]) - float(series[index - 1]["balance"]),
        }
        for index in range(1, len(series))
    ]
    nonzero = [item for item in deltas if abs(float(item["delta"])) > 1e-9]
    count = min(max(int(expected_trades or len(nonzero)), 0), len(nonzero))
    close_indexes = {
        int(item["index"])
        for item in sorted(nonzero, key=lambda item: abs(float(item["delta"])), reverse=True)[:count]
    }
    pending = 0.0
    trades: list[dict[str, Any]] = []
    for item in deltas:
        pending += float(item["delta"])
        if int(item["index"]) not in close_indexes:
            continue
        trades.append(
            {
                "number": len(trades) + 1,
                "close_time": str(item["time"]),
                "ea": label,
                "net_profit": round(pending, 2),
                "result": "Win" if pending > 0 else "Loss" if pending < 0 else "Flat",
                "source": "Reconstructed from archived MT5 balance events",
            }
        )
        pending = 0.0
    return trades


def analyse_equity_series(
    series: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    expected_trades: int | None,
    label: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    ordered = sorted((dict(point) for point in series), key=lambda point: _point_datetime(str(point["time"])))
    if len(ordered) < 2:
        return {"series": [], "trades": [], "stats": None}
    start, end = _date_bounds(from_date, to_date)
    available_start = _point_datetime(str(ordered[0]["time"]))
    available_end = _point_datetime(str(ordered[-1]["time"]))
    start = max(start or available_start, available_start)
    end = min(end or available_end, available_end)
    if start > end:
        return {"series": [], "trades": [], "stats": None}

    anchor = ordered[0]
    for point in ordered:
        if _point_datetime(str(point["time"])) < start:
            anchor = point
        else:
            break
    sliced = [{"time": start.isoformat(), "balance": round(float(anchor["balance"]), 2)}]
    sliced.extend(
        point for point in ordered
        if start < _point_datetime(str(point["time"])) <= end
    )
    if len(sliced) == 1:
        sliced.append({"time": end.isoformat(), "balance": sliced[0]["balance"]})

    all_trades = _trade_events(ordered, expected_trades, label)
    trades = [
        trade for trade in all_trades
        if start <= _point_datetime(str(trade["close_time"])) <= end
    ]
    initial = float(sliced[0]["balance"])
    final = float(sliced[-1]["balance"])
    peak = initial
    max_drawdown_cash = 0.0
    max_drawdown_pct = 0.0
    for point in sliced:
        balance = float(point["balance"])
        peak = max(peak, balance)
        drawdown_cash = peak - balance
        max_drawdown_cash = max(max_drawdown_cash, drawdown_cash)
        if peak:
            max_drawdown_pct = max(max_drawdown_pct, drawdown_cash / peak * 100.0)

    summary_only = all(bool(point.get("summary")) for point in ordered)
    outcomes = [float(trade["net_profit"]) for trade in trades]
    gross_profit = sum(value for value in outcomes if value > 0)
    gross_loss = -sum(value for value in outcomes if value < 0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else None)
    win_rate = (sum(value > 0 for value in outcomes) / len(outcomes) * 100.0) if outcomes else None
    sharpe = None
    if len(outcomes) > 1:
        deviation = statistics.pstdev(outcomes)
        if deviation > 0:
            sharpe = statistics.mean(outcomes) / deviation * math.sqrt(len(outcomes))
    net = final - initial
    stats = {
        "initial_balance": round(initial, 2),
        "final_balance": round(final, 2),
        "net_profit": round(net, 2),
        "return_pct": round((net / initial * 100.0) if initial else 0.0, 2),
        "profit_factor": None if summary_only or profit_factor is None else round(profit_factor, 2),
        "win_rate_pct": None if summary_only or win_rate is None else round(win_rate, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "max_drawdown_cash": round(max_drawdown_cash, 2),
        "trades": None if summary_only else len(trades),
        "sharpe_ratio": None if summary_only or sharpe is None else round(sharpe, 2),
        "recovery_factor": None if max_drawdown_cash <= 0 else round(net / max_drawdown_cash, 2),
        "from": start.date().isoformat(),
        "to": end.date().isoformat(),
    }
    return {"series": _sample(sliced), "trades": trades[-250:], "stats": stats}
