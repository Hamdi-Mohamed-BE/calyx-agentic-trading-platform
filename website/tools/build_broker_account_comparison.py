from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

from app.adaptive_portfolio import simulate_adaptive_portfolio  # noqa: E402
from tools.precompute_evidence_cache import portfolio_metrics  # noqa: E402


PERIOD_ORDER = {"6m": 0, "1y": 1, "3y": 2, "5y": 3}
METRICS = (
    "return_pct",
    "profit_factor",
    "win_rate_pct",
    "max_drawdown_pct",
    "trades",
    "commission",
    "swap",
    "total_costs",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _summary_files(root: Path) -> list[Path]:
    return [
        path
        for path in (root / "products").glob("*/*/*.json")
        if not path.name.endswith(".trades.json")
    ]


def _number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    return value


def build(old_root: Path, new_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for new_path in _summary_files(new_root):
        relative = new_path.relative_to(new_root)
        old_path = old_root / relative
        if not old_path.is_file():
            missing.append({"side": "old", "path": str(relative)})
            continue
        new_payload = _read(new_path)
        old_payload = _read(old_path)
        new_stats = new_payload.get("stats", {})
        old_stats = old_payload.get("stats", {})
        row: dict[str, Any] = {
            "slug": relative.parts[1],
            "label": new_payload.get("label") or old_payload.get("label") or relative.parts[1],
            "mode": relative.parts[2],
            "period": new_path.stem,
            "from": new_payload.get("available_from"),
            "to": new_payload.get("available_to"),
            "old_trade_coverage_from": old_payload.get("trade_coverage_from"),
            "old_trade_coverage_to": old_payload.get("trade_coverage_to"),
            "new_trade_coverage_from": new_payload.get("trade_coverage_from"),
            "new_trade_coverage_to": new_payload.get("trade_coverage_to"),
            "old_history_quality": old_stats.get("history_quality"),
            "new_history_quality": new_stats.get("history_quality"),
        }
        for metric in METRICS:
            old_value = _number(old_stats.get(metric))
            new_value = _number(new_stats.get(metric))
            row[f"old_{metric}"] = old_value
            row[f"new_{metric}"] = new_value
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                row[f"delta_{metric}"] = round(float(new_value) - float(old_value), 2)
            else:
                row[f"delta_{metric}"] = None
        rows.append(row)
    rows.sort(key=lambda row: (str(row["label"]), PERIOD_ORDER.get(str(row["period"]), 99)))
    portfolio_rows: list[dict[str, Any]] = []
    for period in PERIOD_ORDER:
        common_rows = [row for row in rows if row["period"] == period]
        if not common_rows:
            continue
        old_trades: list[dict[str, Any]] = []
        new_trades: list[dict[str, Any]] = []
        for common in common_rows:
            relative = Path("products") / str(common["slug"]) / str(common["mode"]) / f"{period}.trades.json"
            old_trade_path = old_root / relative
            new_trade_path = new_root / relative
            if old_trade_path.is_file() and new_trade_path.is_file():
                old_trades.extend(_read(old_trade_path))
                new_trades.extend(_read(new_trade_path))
        start = date.fromisoformat(str(common_rows[0]["from"]))
        end = date.fromisoformat(str(common_rows[0]["to"]))
        old_adaptive, _, _ = simulate_adaptive_portfolio(old_trades)
        new_adaptive, _, _ = simulate_adaptive_portfolio(new_trades)
        old_stats, _ = portfolio_metrics(old_adaptive, start, end)
        new_stats, _ = portfolio_metrics(new_adaptive, start, end)
        row: dict[str, Any] = {"period": period, "common_ea_count": len(common_rows)}
        for metric in METRICS:
            old_value = _number(old_stats.get(metric))
            new_value = _number(new_stats.get(metric))
            row[f"old_{metric}"] = old_value
            row[f"new_{metric}"] = new_value
            row[f"delta_{metric}"] = (
                round(float(new_value) - float(old_value), 2)
                if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float))
                else None
            )
        portfolio_rows.append(row)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "old_account": "Exness Standard (existing website evidence)",
        "new_account": "Configured comparison account (details kept private)",
        "execution_model": "Native MT5 Every Tick, broker Bid/Ask spread, commission, swap and random execution delay",
        "warning": "Treat rows with low MT5 history quality or short trade samples as provisional.",
        "portfolio_scope": "Like-for-like Recommended Adaptive replay of only the EAs with long-window evidence on both accounts. News Pulse is compared separately over its verified calendar.",
        "rows": rows,
        "portfolio": portfolio_rows,
        "missing": missing,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = [row for row in payload["rows"] if row["period"] == "5y"]
    lines = [
        "# Exness Standard vs Raw Spread — recommended EA modes",
        "",
        payload["execution_model"] + ".",
        "",
        f"## Recommended Adaptive portfolio ({payload['portfolio'][0]['common_ea_count']} common EAs)",
        "",
        "| Period | Return old / raw | PF old / raw | WR old / raw | DD old / raw | Trades old / raw | Raw costs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["portfolio"]:
        lines.append(
            "| {period} | {old_return_pct:.2f}% / {new_return_pct:.2f}% | {old_profit_factor:.2f} / {new_profit_factor:.2f} | "
            "{old_win_rate_pct:.2f}% / {new_win_rate_pct:.2f}% | {old_max_drawdown_pct:.2f}% / {new_max_drawdown_pct:.2f}% | "
            "{old_trades} / {new_trades} | ${new_total_costs:.2f} |".format(**row)
        )
    news = payload.get("news_pulse")
    if news:
        lines.extend(
            [
                "",
                "## News Pulse — verified FXMacroData window",
                "",
                f"Window: {news['calendar']['verified_from']} to {news['calendar']['verified_to']} ({news['calendar']['event_count']} events).",
                "",
                "| EA | Return old / raw | PF old / raw | WR old / raw | DD old / raw | Trades | Raw commission + swap |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in news["rows"]:
            old = row["standard_account"]
            new = row["raw_spread_account"]
            lines.append(
                f"| {row['label']} | {old['return_pct']:.2f}% / {new['return_pct']:.2f}% | "
                f"{old['profit_factor']:.2f} / {new['profit_factor']:.2f} | "
                f"{old['win_rate_pct']:.2f}% / {new['win_rate_pct']:.2f}% | "
                f"{old['max_drawdown_pct']:.2f}% / {new['max_drawdown_pct']:.2f}% | {new['trades']} | "
                f"${new['total_costs']:.2f} |"
            )
    lines.extend(
        [
            "",
            "## EA-by-EA 5-year view",
            "",
        "| EA | Mode | Return old / raw | PF old / raw | WR old / raw | DD old / raw | Trades old / raw | Raw costs | Quality old / raw | Raw first trade |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| {label} | {mode} | {old_return_pct:.2f}% / {new_return_pct:.2f}% | "
            "{old_profit_factor:.2f} / {new_profit_factor:.2f} | {old_win_rate_pct:.2f}% / {new_win_rate_pct:.2f}% | "
            "{old_max_drawdown_pct:.2f}% / {new_max_drawdown_pct:.2f}% | {old_trades} / {new_trades} | "
            "${new_total_costs:.2f} | {old_history_quality} / {new_history_quality} | {new_trade_coverage_from} |".format(**row)
        )
    lines.extend(
        [
            "",
            "The CSV and JSON beside this report contain every 6-month, 1-year, 3-year and 5-year row. "
            "News Pulse is reported separately because the unauthenticated FXMacroData calendar only proves a 90-day window.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an old-vs-new MT5 account comparison from two evidence caches")
    parser.add_argument("--old-root", type=Path, required=True)
    parser.add_argument("--new-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.old_root.resolve(), args.new_root.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    news_path = args.output / "news-pulse" / "news-pulse-verified-window.json"
    if news_path.is_file():
        payload["news_pulse"] = _read(news_path)
    (args.output / "comparison.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(args.output / "comparison.csv", payload["rows"])
    write_csv(args.output / "portfolio-comparison.csv", payload["portfolio"])
    write_markdown(args.output / "README.md", payload)
    print(f"Wrote {len(payload['rows'])} comparison rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
