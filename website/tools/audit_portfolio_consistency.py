from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any


STORE = Path(__file__).resolve().parents[1]
CACHE = STORE / "data" / "evidence-cache" / "v1"
PRODUCTS = CACHE / "products"
MANIFEST = CACHE / "manifest.json"
PACKAGE = STORE.parent / "BM Trading Robust Sets 2026-08-04"
OUTPUT = PACKAGE / "Portfolio Consistency Audit 2026-09-11"
STORE_AUDIT = STORE / "data" / "portfolio-consistency-audit.json"
PERIODS = ("6m", "1y", "3y", "5y")

# These are mode changes only. No EA is removed by this audit without review.
PROPOSED_MODE_OVERRIDES = {
    "sell-nasdaq-15min": "dynamic",
}

PRE_AUDIT_MODE_OVERRIDES = {
    "sell-nasdaq-15min": "standard",
}

# The user approved these removals on 2026-09-10. Research files and cached
# single-EA evidence remain archived, but they are no longer active products.
APPROVED_EXCLUSIONS = {
    "engineered-liquidity-xau": {
        "label": "Engineered Liquidity XAU",
        "reason": "Weak consistency: 5Y PF 1.17 with 39.68% drawdown.",
    },
    "orb-volume-profile-high-win-0-75r": {
        "label": "ORB Volume Profile High Win 0.75R",
        "reason": "Duplicate core ORB entries with materially weaker 5Y PF and return.",
    },
    "xag-session-vwap-snapback": {
        "label": "XAG Session VWAP Snapback",
        "reason": "No demonstrated long-window edge: 5Y return +0.04% with PF 1.00.",
    },
    "xau-squeeze-momentum-high-win-0-75r": {
        "label": "XAU Squeeze Momentum High Win 0.75R",
        "reason": "Near-duplicate squeeze exposure with weaker evidence than Standard Safe.",
    },
}

WATCHLIST = {
    "btc-top-down-fvg-liquidity": "5Y PF is only 1.21, although recent performance improved.",
    "nasdaq-5m-candle-momentum": "Large historical return but thin edge: PF 1.12 over 5Y and 1.18 over 3Y.",
    "xau-regime-switch": "Strong long history but last six months are -4.95% with PF 0.43.",
    "xau-slow-trend": "Strong 3Y/5Y evidence but last six months are -7.13% with PF 0.48.",
    "news-pulse-xau": "Required News Pulse exposure retained at fixed risk. Review the independent period's trade count and real-tick coverage; older generated ticks and live news slippage remain limitations.",
    "news-pulse-xag": "Required News Pulse exposure retained at fixed risk. Review the independent period's trade count and real-tick coverage; older generated ticks and live news slippage remain limitations.",
    "news-pulse-btc": "Required News Pulse exposure retained at fixed risk. Review the independent period's trade count and real-tick coverage; older generated ticks and live news slippage remain limitations.",
    "us100-selective-orb-v3": "Only 34 trades exist in the 5Y view; retain as low-frequency evidence, not as a high-capacity core.",
    "xau-squeeze-momentum-standard": "Safe mode has strong PF/DD but only 48 trades in 5Y and no trades in the latest six months.",
}

# Only individually viable alternatives enter the small portfolio interaction
# grid. Modes with PF <= 1 over a long horizon are never rescued merely because
# their loss timing happens to offset another EA in this one historical path.
INTERACTION_GRID = {
    "eth-top-down-fvg-liquidity": ("standard", "safe"),
    "sell-nasdaq-15min": ("standard", "safe", "dynamic"),
    "xau-squeeze-momentum-standard": ("safe", "standard"),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def payload(slug: str, mode: str, period: str) -> dict[str, Any]:
    path = PRODUCTS / slug / mode / f"{period}.json"
    return read_json(path) if path.is_file() else {}


def trades(slug: str, mode: str, period: str) -> list[dict[str, Any]]:
    path = PRODUCTS / slug / mode / f"{period}.trades.json"
    return read_json(path) if path.is_file() else []


def summarize_trade_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row.get("close_time", ""), row.get("open_time", "")))
    pnl = [finite(row.get("net_profit")) for row in ordered]
    wins = [value for value in pnl if value > 0]
    losses = [-value for value in pnl if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    pf = gross_profit / gross_loss if gross_loss else (99.0 if gross_profit else 0.0)
    balance = 10_000.0
    peak = balance
    max_dd = 0.0
    for value in pnl:
        balance += value
        peak = max(peak, balance)
        if peak > 0:
            max_dd = max(max_dd, (peak - balance) / peak * 100.0)
    return {
        "return_pct": round((balance / 10_000.0 - 1.0) * 100.0, 2),
        "profit_factor": round(pf, 2),
        "win_rate_pct": round(len(wins) / len(pnl) * 100.0, 2) if pnl else 0.0,
        "max_drawdown_pct": round(max_dd, 2),
        "trades": len(pnl),
        "net_profit": round(sum(pnl), 2),
    }


def combine(selection: list[dict[str, Any]], period: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in selection:
        for row in trades(item["slug"], item["mode"], period):
            rows.append({**row, "portfolio_slug": item["slug"], "portfolio_mode": item["mode"]})
    return summarize_trade_rows(rows)


def normalized_period_stats(slug: str, mode: str, period: str) -> dict[str, Any]:
    data = payload(slug, mode, period)
    stats = data.get("stats", {})
    return {
        "return_pct": finite(stats.get("return_pct")),
        "profit_factor": finite(stats.get("profit_factor")),
        "win_rate_pct": finite(stats.get("win_rate_pct")),
        "max_drawdown_pct": finite(stats.get("max_drawdown_pct")),
        "trades": int(finite(stats.get("trades"))),
        "available_from": data.get("available_from"),
        "available_to": data.get("available_to"),
        "trade_coverage_from": data.get("trade_coverage_from"),
        "trade_coverage_to": data.get("trade_coverage_to"),
        "history_quality": data.get("history_quality") or stats.get("history_quality"),
    }


def cached_portfolio_comparison() -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for period in PERIODS:
        current = read_json(CACHE / "portfolio" / "current" / f"{period}.json").get("stats", {})
        adaptive = read_json(CACHE / "portfolio" / "recommended-adaptive" / f"{period}.json").get("stats", {})
        fields = (
            "return_pct",
            "profit_factor",
            "win_rate_pct",
            "max_drawdown_pct",
            "trades",
            "commission",
            "swap",
            "total_costs",
        )
        comparison[period] = {
            "current": {key: current.get(key) for key in fields},
            "recommended_adaptive": {key: adaptive.get(key) for key in fields},
        }
    return comparison


def open_minute(row: dict[str, Any]) -> str:
    text = str(row.get("open_time", ""))
    return text[:16]


def overlap_and_correlation(selection: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledgers: dict[str, list[dict[str, Any]]] = {}
    daily: dict[str, dict[str, float]] = {}
    for item in selection:
        slug = item["slug"]
        rows = trades(slug, item["mode"], "5y")
        ledgers[slug] = rows
        day_map: dict[str, float] = defaultdict(float)
        for row in rows:
            day_map[str(row.get("close_time", ""))[:10]] += finite(row.get("net_profit"))
        daily[slug] = dict(day_map)

    overlaps: list[dict[str, Any]] = []
    correlations: list[dict[str, Any]] = []
    slugs = [item["slug"] for item in selection]
    for index, left in enumerate(slugs):
        left_rows = ledgers[left]
        left_entries = {(str(r.get("symbol", "")).upper(), open_minute(r), str(r.get("side", ""))) for r in left_rows}
        for right in slugs[index + 1 :]:
            right_rows = ledgers[right]
            right_entries = {(str(r.get("symbol", "")).upper(), open_minute(r), str(r.get("side", ""))) for r in right_rows}
            denominator = min(len(left_entries), len(right_entries))
            exact = len(left_entries & right_entries)
            overlap = exact / denominator if denominator else 0.0
            if overlap >= 0.10:
                overlaps.append(
                    {
                        "left": left,
                        "right": right,
                        "exact_same_minute_side": exact,
                        "overlap_of_smaller_pct": round(overlap * 100.0, 2),
                    }
                )

            days = sorted(set(daily[left]) | set(daily[right]))
            if len(days) < 2:
                continue
            xs = [daily[left].get(day, 0.0) for day in days]
            ys = [daily[right].get(day, 0.0) for day in days]
            xmean = sum(xs) / len(xs)
            ymean = sum(ys) / len(ys)
            numerator = sum((x - xmean) * (y - ymean) for x, y in zip(xs, ys))
            xvar = sum((x - xmean) ** 2 for x in xs)
            yvar = sum((y - ymean) ** 2 for y in ys)
            corr = numerator / math.sqrt(xvar * yvar) if xvar > 0 and yvar > 0 else 0.0
            if abs(corr) >= 0.15:
                correlations.append({"left": left, "right": right, "daily_pnl_correlation": round(corr, 4)})

    overlaps.sort(key=lambda row: row["overlap_of_smaller_pct"], reverse=True)
    correlations.sort(key=lambda row: abs(row["daily_pnl_correlation"]), reverse=True)
    return overlaps, correlations


def exposure(selection: list[dict[str, Any]]) -> dict[str, Any]:
    events: list[tuple[str, int, float, str]] = []
    for item in selection:
        risk = 1.5 if item["slug"].startswith("news-pulse-") else 1.0
        for row in trades(item["slug"], item["mode"], "5y"):
            symbol = str(row.get("symbol", "")).upper()
            events.append((str(row.get("open_time", "")), 1, risk, symbol))
            events.append((str(row.get("close_time", "")), 0, risk, symbol))
    # Close before open at the same timestamp.
    events.sort(key=lambda event: (event[0], event[1]))
    total = 0.0
    by_symbol: dict[str, float] = defaultdict(float)
    max_total = 0.0
    max_symbol: dict[str, float] = defaultdict(float)
    for _, kind, risk, symbol in events:
        if kind == 0:
            total = max(0.0, total - risk)
            by_symbol[symbol] = max(0.0, by_symbol[symbol] - risk)
        else:
            total += risk
            by_symbol[symbol] += risk
            max_total = max(max_total, total)
            max_symbol[symbol] = max(max_symbol[symbol], by_symbol[symbol])
    return {
        "max_reserved_risk_pct": round(max_total, 2),
        "max_reserved_risk_by_symbol_pct": dict(sorted((key, round(value, 2)) for key, value in max_symbol.items())),
        "warning": "Conservative: risk remains reserved until close; floating P/L and shared-margin effects are unavailable.",
    }


def main() -> None:
    manifest = read_json(MANIFEST)
    manifest_selection = [dict(item) for item in manifest["recommended_eas"]]
    current = [
        {**item, "mode": PRE_AUDIT_MODE_OVERRIDES.get(item["slug"], item["mode"])}
        for item in manifest_selection
    ]
    proposed = [dict(item) for item in manifest_selection]
    labels = {item["slug"]: item["label"] for item in current}
    for item in proposed:
        item["mode"] = PROPOSED_MODE_OVERRIDES.get(item["slug"], item["mode"])

    active_count = len(proposed)
    scenarios = {
        "pre_mode_active": {period: combine(current, period) for period in PERIODS},
        "recommended_active": {period: combine(proposed, period) for period in PERIODS},
    }

    interaction_grid: list[dict[str, Any]] = []
    grid_slugs = list(INTERACTION_GRID)
    for modes in product(*(INTERACTION_GRID[slug] for slug in grid_slugs)):
        overrides = dict(zip(grid_slugs, modes))
        candidate = [{**row, "mode": overrides.get(row["slug"], row["mode"])} for row in current]
        result = {period: combine(candidate, period) for period in PERIODS}
        # A transparent robustness rank: all windows retain at least 95% of the
        # current return, then prefer higher mean PF and lower mean/max DD.
        retention = min(
            result[period]["return_pct"] / scenarios["pre_mode_active"][period]["return_pct"]
            for period in PERIODS
        )
        mean_pf = sum(result[period]["profit_factor"] for period in PERIODS) / len(PERIODS)
        mean_dd = sum(result[period]["max_drawdown_pct"] for period in PERIODS) / len(PERIODS)
        interaction_grid.append(
            {
                "modes": overrides,
                "return_retention_min": round(retention, 4),
                "mean_profit_factor": round(mean_pf, 4),
                "mean_drawdown_pct": round(mean_dd, 4),
                "robust_rank_score": round((min(retention, 1.05) * 10.0) + mean_pf * 5.0 - mean_dd * 0.15, 4),
                "portfolio": result,
            }
        )
    interaction_grid.sort(key=lambda row: (row["return_retention_min"] >= 0.95, row["robust_rank_score"]), reverse=True)

    # One-at-a-time mode replacement table. This makes the portfolio interaction
    # visible and prevents a lower standalone drawdown from being accepted when
    # it worsens the combined chronology.
    one_at_a_time: list[dict[str, Any]] = []
    for item in current:
        slug = item["slug"]
        product_root = PRODUCTS / slug
        folders = sorted(path.name for path in product_root.iterdir() if path.is_dir()) if product_root.is_dir() else []
        if len(folders) < 2:
            continue
        for mode in folders:
            if mode == item["mode"]:
                continue
            candidate = [{**row, "mode": mode if row["slug"] == slug else row["mode"]} for row in current]
            one_at_a_time.append(
                {
                    "slug": slug,
                    "label": item["label"],
                    "from": item["mode"],
                    "to": mode,
                    "portfolio": {period: combine(candidate, period) for period in PERIODS},
                }
            )

    rows: list[dict[str, Any]] = []
    for item in proposed:
        slug = item["slug"]
        mode = item["mode"]
        row: dict[str, Any] = {
            "slug": slug,
            "label": item["label"],
            "symbol": item["symbol"],
            "current_mode": next(source["mode"] for source in current if source["slug"] == slug),
            "recommended_mode": mode,
            "decision": "retained by user" if slug == "dmc-current-xau" else "watch" if slug in WATCHLIST else "keep",
            "reason": (
                "Explicitly retained by the user after the portfolio audit; continue monitoring its weak 5Y PF and drawdown."
                if slug == "dmc-current-xau"
                else WATCHLIST.get(slug) or "Passes the current consistency review."
            ),
        }
        for period in PERIODS:
            stats = normalized_period_stats(slug, mode, period)
            for key in ("return_pct", "profit_factor", "win_rate_pct", "max_drawdown_pct", "trades"):
                row[f"{period}_{key}"] = stats[key]
        rows.append(row)

    mode_comparisons: list[dict[str, Any]] = []
    for item in current:
        slug = item["slug"]
        product_root = PRODUCTS / slug
        folders = sorted(path.name for path in product_root.iterdir() if path.is_dir()) if product_root.is_dir() else []
        if len(folders) < 2:
            continue
        for mode in folders:
            record: dict[str, Any] = {
                "slug": slug,
                "label": labels[slug],
                "mode": mode,
                "current": mode == item["mode"],
                "recommended": mode == next(row["mode"] for row in proposed if row["slug"] == slug),
            }
            for period in PERIODS:
                stats = normalized_period_stats(slug, mode, period)
                record[period] = {key: stats[key] for key in ("return_pct", "profit_factor", "max_drawdown_pct", "trades")}
            mode_comparisons.append(record)

    overlaps, correlations = overlap_and_correlation(proposed)
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_end": manifest.get("end_date"),
        "method": (
            "All saved native MT5 evidence modes were compared over 6m, 1y, 3y and 5y. "
            "Portfolio curves are chronological closed-deal cash-flow overlays on a $10,000 reference balance."
        ),
        "applied_mode_changes": [
            {
                "slug": slug,
                "label": labels[slug],
                "from": next(item["mode"] for item in current if item["slug"] == slug),
                "to": mode,
            }
            for slug, mode in PROPOSED_MODE_OVERRIDES.items()
        ],
        "active_ea_count": active_count,
        "applied_exclusions": [
            {"slug": slug, **details}
            for slug, details in APPROVED_EXCLUSIONS.items()
        ],
        "exclusions_require_user_approval": [],
        "retained_by_user": [
            {
                "slug": "dmc-current-xau",
                "label": labels["dmc-current-xau"],
                "reason": "Explicit user decision: keep DMC Current XAU active.",
            }
        ],
        "watchlist": [
            {"slug": slug, "label": labels[slug], "reason": reason}
            for slug, reason in WATCHLIST.items()
            if slug in labels
        ],
        "scenarios": scenarios,
        "adaptive_overlay_comparison": cached_portfolio_comparison(),
        "one_at_a_time_mode_replacements": one_at_a_time,
        "eligible_mode_interaction_grid": interaction_grid,
        "mode_comparisons": mode_comparisons,
        "per_ea_recommendations": rows,
        "top_entry_overlaps": overlaps[:20],
        "top_daily_pnl_correlations": correlations[:20],
        "recommended_mode_exposure": exposure(proposed),
        "limitations": [
            "No historical result guarantees future profitability.",
            "The component tests used separate balances; the combined curve is not a shared-margin MT5 simulation.",
            "Closed-deal drawdown can understate live equity drawdown and gap/slippage risk.",
            "Nested 6m/1y/3y/5y windows are evidence views, not four independent out-of-sample tests.",
            "News Pulse XAU and XAG have short release-verified ledgers; BTC has complete native three-year coverage. Every News Pulse chart remains fixed at 0.75% per triggered stop / 1.50% event cap before adaptive tapering.",
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "portfolio-consistency-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    STORE_AUDIT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    with (OUTPUT / "per-ea-recommendations.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Portfolio consistency audit — 2026-09-12",
        "",
        f"Evidence cutoff: **{manifest.get('end_date')}**. Four removals were applied after explicit user approval; DMC Current XAU was retained.",
        "",
        "## Portfolio scenario comparison",
        "",
        "| Scenario | Horizon | Return | PF | Win rate | Max DD | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    scenario_names = {
        "pre_mode_active": f"Active {active_count} before Sell Nasdaq mode change",
        "recommended_active": f"Recommended active {active_count}",
    }
    for scenario_key, period_map in scenarios.items():
        for period, stats in period_map.items():
            lines.append(
                f"| {scenario_names[scenario_key]} | {period} | {stats['return_pct']:+.2f}% | "
                f"{stats['profit_factor']:.2f} | {stats['win_rate_pct']:.2f}% | "
                f"{stats['max_drawdown_pct']:.2f}% | {stats['trades']} |"
            )

    lines += [
        "",
        "## Applied mode recommendations",
        "",
        "| EA | Current | Recommended | Reason |",
        "|---|---|---|---|",
        "| Sell Nasdaq 15min | Standard | Dynamic London | Better 1y/3y/5y return and PF with lower 3y/5y drawdown; last six months remain slightly negative. |",
        "",
        "All other mode choices remain unchanged. Existing Safe defaults remain on LTA Volume Profile, EMA3, XAU Weakness and XAU Squeeze Momentum Standard.",
        "",
        "## Approved removals",
        "",
        "| EA | Reason |",
        "|---|---|",
    ]
    for details in APPROVED_EXCLUSIONS.values():
        lines.append(f"| {details['label']} | {details['reason']} |")
    lines += [
        "",
        "DMC Current XAU remains active by explicit user decision.",
    ]
    lines += [
        "",
        "## Watchlist — retained",
        "",
        "| EA | Reason |",
        "|---|---|",
    ]
    for slug, reason in WATCHLIST.items():
        lines.append(f"| {labels[slug]} | {reason} |")
    lines += [
        "",
        "## Important limitation",
        "",
        "The combined figures merge independently sized MT5 deal ledgers. They are useful for relative portfolio decisions, but they are not proof of future returns or an exact shared-margin equity simulation. Concurrent positions can create materially more account risk than any one EA's displayed drawdown.",
        "",
    ]
    (OUTPUT / "PORTFOLIO CONSISTENCY AUDIT.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"output": str(OUTPUT), "scenarios": scenarios, "mode_changes": audit["applied_mode_changes"], "applied_exclusions": audit["applied_exclusions"], "top_overlaps": overlaps[:8], "exposure": audit["recommended_mode_exposure"]}, indent=2))


if __name__ == "__main__":
    main()
