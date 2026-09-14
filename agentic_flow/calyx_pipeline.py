from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Iterable


DEFAULT_SEED = 20260910
DEFAULT_PATHS = 10_000


@dataclass(frozen=True)
class TradeOutcome:
    closed_at: datetime
    pnl: float
    commission: float = 0.0
    swap: float = 0.0


def _number(value: object) -> float:
    match = re.search(r"[-+]?\d[\d\s,.]*", str(value or ""))
    if not match:
        return 0.0
    text = match.group(0).replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _percent(value: object) -> float:
    matches = re.findall(r"([-+]?\d+(?:[.,]\d+)?)%", str(value or ""))
    return float(matches[-1].replace(",", ".")) if matches else _number(value)


def _read_html(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw[:200].count(b"\x00") > 20:
        return raw.decode("utf-16", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def parse_mt5_report(path: Path) -> tuple[dict, list[TradeOutcome]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("BeautifulSoup is required: install beautifulsoup4") from exc

    soup = BeautifulSoup(_read_html(path), "html.parser")
    values: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all(["td", "th"], recursive=False)]
        for index, cell in enumerate(cells[:-1]):
            if cell.endswith(":"):
                values[cell[:-1]] = cells[index + 1]

    deal_rows: list[dict] = []
    inside_deals = False
    for row in soup.find_all("tr"):
        if " ".join(row.get_text(" ", strip=True).split()) == "Deals":
            inside_deals = True
            continue
        if not inside_deals:
            continue
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all("td", recursive=False)]
        if len(cells) != 13 or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", cells[0]):
            continue
        if cells[3].lower() == "balance":
            continue
        deal_rows.append(
            {
                "time": datetime.strptime(cells[0], "%Y.%m.%d %H:%M:%S"),
                "entry": cells[4].lower(),
                "commission": _number(cells[8]),
                "swap": _number(cells[9]),
                "profit": _number(cells[10]),
            }
        )

    outcomes: list[TradeOutcome] = []
    pending_pnl = pending_commission = pending_swap = 0.0
    for deal in deal_rows:
        cashflow = deal["commission"] + deal["swap"] + deal["profit"]
        pending_pnl += cashflow
        pending_commission += deal["commission"]
        pending_swap += deal["swap"]
        if deal["entry"] in {"out", "out by"}:
            outcomes.append(
                TradeOutcome(
                    closed_at=deal["time"],
                    pnl=pending_pnl,
                    commission=pending_commission,
                    swap=pending_swap,
                )
            )
            pending_pnl = pending_commission = pending_swap = 0.0

    initial = _number(values.get("Initial Deposit")) or 10_000.0
    metadata = {
        "source_report": str(path.resolve()),
        "initial_balance": initial,
        "reported_net_profit": _number(values.get("Total Net Profit")),
        "reported_profit_factor": _number(values.get("Profit Factor")),
        "reported_win_rate_pct": _percent(values.get("Profit Trades (% of total)", "")),
        "reported_max_drawdown_pct": _percent(values.get("Equity Drawdown Maximal", "")),
        "reported_trades": int(_number(values.get("Total Trades"))),
        "reported_sharpe": _number(values.get("Sharpe Ratio")),
        "reported_recovery": _number(values.get("Recovery Factor")),
        "history_quality": values.get("History Quality", ""),
    }
    return metadata, outcomes


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def json_safe(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def profit_factor(values: Iterable[float]) -> float:
    values = list(values)
    gross_profit = sum(value for value in values if value > 0.0)
    gross_loss = -sum(value for value in values if value < 0.0)
    if gross_loss <= 0.0:
        return float("inf") if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def wilson_interval(wins: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    proportion = wins / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def streaks(values: list[float]) -> tuple[int, int]:
    maximum_wins = maximum_losses = current_wins = current_losses = 0
    for value in values:
        if value > 0:
            current_wins += 1
            current_losses = 0
            maximum_wins = max(maximum_wins, current_wins)
        elif value < 0:
            current_losses += 1
            current_wins = 0
            maximum_losses = max(maximum_losses, current_losses)
        else:
            current_wins = current_losses = 0
    return maximum_wins, maximum_losses


def daily_returns(outcomes: list[TradeOutcome], initial: float) -> tuple[list[date], list[float], list[float]]:
    grouped: defaultdict[date, float] = defaultdict(float)
    for outcome in outcomes:
        grouped[outcome.closed_at.date()] += outcome.pnl
    if not grouped:
        return [], [], []
    first, last = min(grouped), max(grouped)
    crypto_calendar = any(day.weekday() >= 5 for day in grouped)
    days: list[date] = []
    cursor = first
    while cursor <= last:
        if crypto_calendar or cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    equity = initial
    returns: list[float] = []
    pnl: list[float] = []
    for day in days:
        result = grouped.get(day, 0.0)
        returns.append(result / equity if equity > 0.0 else -1.0)
        pnl.append(result)
        equity += result
    return days, returns, pnl


def expected_shortfall(returns: list[float], confidence: float = 0.95) -> float:
    if not returns:
        return 0.0
    cutoff = quantile(returns, 1.0 - confidence)
    tail = [value for value in returns if value <= cutoff]
    return -statistics.fmean(tail) if tail else 0.0


def moments(values: list[float]) -> tuple[float, float]:
    if len(values) < 3:
        return 0.0, 3.0
    mean = statistics.fmean(values)
    centred = [value - mean for value in values]
    m2 = statistics.fmean(value * value for value in centred)
    if m2 <= 0.0:
        return 0.0, 3.0
    skewness = statistics.fmean(value**3 for value in centred) / (m2**1.5)
    kurtosis = statistics.fmean(value**4 for value in centred) / (m2 * m2)
    return skewness, kurtosis


def sharpe_statistics(returns: list[float], tested_configurations: int, periods_per_year: float) -> dict:
    if len(returns) < 3:
        return {
            "annualized_sharpe": 0.0,
            "probabilistic_sharpe_pct": 0.0,
            "deflated_sharpe_pct": 0.0,
            "multiple_test_benchmark_sharpe": 0.0,
        }
    mean = statistics.fmean(returns)
    deviation = statistics.stdev(returns)
    if deviation <= 0.0:
        return {
            "annualized_sharpe": 0.0,
            "probabilistic_sharpe_pct": 0.0,
            "deflated_sharpe_pct": 0.0,
            "multiple_test_benchmark_sharpe": 0.0,
        }
    sr = mean / deviation
    skewness, kurtosis = moments(returns)
    variance_term = max(1e-12, 1.0 - skewness * sr + ((kurtosis - 1.0) / 4.0) * sr * sr)
    standard_error = math.sqrt(variance_term / (len(returns) - 1))
    normal = NormalDist()
    psr = normal.cdf(sr / standard_error)
    trials = max(1, tested_configurations)
    benchmark = 0.0
    if trials > 1:
        euler_gamma = 0.5772156649015329
        benchmark = standard_error * (
            (1.0 - euler_gamma) * normal.inv_cdf(1.0 - 1.0 / trials)
            + euler_gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
        )
    dsr = normal.cdf((sr - benchmark) / standard_error)
    return {
        "annualized_sharpe": sr * math.sqrt(periods_per_year),
        "probabilistic_sharpe_pct": psr * 100.0,
        "deflated_sharpe_pct": dsr * 100.0,
        "multiple_test_benchmark_sharpe": benchmark * math.sqrt(periods_per_year),
        "daily_skewness": skewness,
        "daily_kurtosis": kurtosis,
    }


def _block_sample(values: list[float], length: int, block: int, rng: random.Random) -> list[float]:
    if not values:
        return []
    sample: list[float] = []
    width = max(1, min(block, len(values)))
    while len(sample) < length:
        start = rng.randrange(len(values))
        sample.extend(values[(start + offset) % len(values)] for offset in range(width))
    return sample[:length]


def bootstrap(
    trade_pnl: list[float],
    returns: list[float],
    *,
    paths: int,
    block: int,
    daily_loss_limit_pct: float,
    total_loss_limit_pct: float,
    seed: int,
) -> dict:
    if not trade_pnl or not returns:
        return {"paths": paths, "status": "insufficient_data"}
    rng = random.Random(seed)
    final_returns: list[float] = []
    maximum_drawdowns: list[float] = []
    profit_factors: list[float] = []
    daily_breaches = total_breaches = 0
    daily_limit = daily_loss_limit_pct / 100.0
    total_limit = total_loss_limit_pct / 100.0
    for _ in range(paths):
        sampled_returns = _block_sample(returns, len(returns), block, rng)
        sampled_trades = _block_sample(trade_pnl, len(trade_pnl), block, rng)
        equity = peak = 1.0
        maximum_drawdown = 0.0
        breached_total = False
        breached_daily = False
        for result in sampled_returns:
            breached_daily = breached_daily or result <= -daily_limit
            equity *= max(0.0, 1.0 + result)
            peak = max(peak, equity)
            if peak > 0.0:
                maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak)
            breached_total = breached_total or equity <= 1.0 - total_limit
        final_returns.append((equity - 1.0) * 100.0)
        maximum_drawdowns.append(maximum_drawdown * 100.0)
        profit_factors.append(profit_factor(sampled_trades))
        daily_breaches += int(breached_daily)
        total_breaches += int(breached_total)
    return {
        "paths": paths,
        "block_length": block,
        "probability_profit_pct": sum(value > 0.0 for value in final_returns) / paths * 100.0,
        "return_p05_pct": quantile(final_returns, 0.05),
        "return_p50_pct": quantile(final_returns, 0.50),
        "return_p95_pct": quantile(final_returns, 0.95),
        "max_drawdown_p50_pct": quantile(maximum_drawdowns, 0.50),
        "max_drawdown_p95_pct": quantile(maximum_drawdowns, 0.95),
        "profit_factor_p05": quantile(profit_factors, 0.05),
        "profit_factor_p50": quantile(profit_factors, 0.50),
        "profit_factor_p95": quantile(profit_factors, 0.95),
        "closed_pnl_daily_limit_breach_pct": daily_breaches / paths * 100.0,
        "closed_pnl_total_limit_breach_pct": total_breaches / paths * 100.0,
        "breach_scope": "closed-trade P&L proxy; floating drawdown is not recoverable from an MT5 summary report",
    }


def subperiods(outcomes: list[TradeOutcome], parts: int = 3) -> list[dict]:
    if not outcomes:
        return []
    ordered = sorted(outcomes, key=lambda item: item.closed_at)
    groups: list[list[TradeOutcome]] = []
    for index in range(parts):
        start = round(len(ordered) * index / parts)
        end = round(len(ordered) * (index + 1) / parts)
        groups.append(ordered[start:end])
    rows = []
    for index, group in enumerate(groups, 1):
        pnl = [item.pnl for item in group]
        rows.append(
            {
                "part": index,
                "start": group[0].closed_at.isoformat() if group else None,
                "end": group[-1].closed_at.isoformat() if group else None,
                "trades": len(group),
                "net_profit": sum(pnl),
                "profit_factor": profit_factor(pnl),
                "win_rate_pct": sum(value > 0.0 for value in pnl) / len(pnl) * 100.0 if pnl else 0.0,
            }
        )
    return rows


def audit_report(
    path: Path,
    *,
    label: str,
    paths: int,
    block: int,
    tested_configurations: int,
    daily_loss_limit_pct: float,
    total_loss_limit_pct: float,
    extra_cost_per_trade: float | None,
    seed: int,
) -> dict:
    metadata, outcomes = parse_mt5_report(path)
    pnl = [item.pnl for item in outcomes]
    initial = metadata["initial_balance"]
    days, returns, _ = daily_returns(outcomes, initial)
    years = max(1.0 / 365.25, ((days[-1] - days[0]).days + 1) / 365.25) if days else 1.0
    periods_per_year = min(365.0, max(1.0, len(returns) / years))
    wins = sum(value > 0.0 for value in pnl)
    lower, upper = wilson_interval(wins, len(pnl))
    maximum_wins, maximum_losses = streaks(pnl)
    boot = bootstrap(
        pnl,
        returns,
        paths=paths,
        block=block,
        daily_loss_limit_pct=daily_loss_limit_pct,
        total_loss_limit_pct=total_loss_limit_pct,
        seed=seed,
    )
    sharpe = sharpe_statistics(returns, tested_configurations, periods_per_year)
    thirds = subperiods(outcomes)
    recent = pnl[len(pnl) // 2 :]
    stressed = None
    if extra_cost_per_trade is not None:
        stressed_pnl = [value - extra_cost_per_trade for value in pnl]
        stressed = {
            "extra_cost_per_trade": extra_cost_per_trade,
            "net_profit": sum(stressed_pnl),
            "return_pct": sum(stressed_pnl) / initial * 100.0,
            "profit_factor": profit_factor(stressed_pnl),
        }

    metrics = {
        "trades": len(pnl),
        "wins": wins,
        "losses": sum(value < 0.0 for value in pnl),
        "win_rate_pct": wins / len(pnl) * 100.0 if pnl else 0.0,
        "win_rate_wilson_95_pct": [lower * 100.0, upper * 100.0],
        "net_profit": sum(pnl),
        "return_pct": sum(pnl) / initial * 100.0,
        "profit_factor": profit_factor(pnl),
        "expected_payoff": statistics.fmean(pnl) if pnl else 0.0,
        "max_win_streak": maximum_wins,
        "max_loss_streak": maximum_losses,
        "daily_expected_shortfall_95_pct": expected_shortfall(returns) * 100.0,
        "recent_half_profit_factor": profit_factor(recent),
        "profitable_thirds": sum(row["net_profit"] > 0.0 for row in thirds),
        "tested_configurations": tested_configurations,
        **sharpe,
    }

    gates = {
        "minimum_30_closed_trades": metrics["trades"] >= 30,
        "positive_locked_return": metrics["return_pct"] > 0.0,
        "profit_factor_above_1": metrics["profit_factor"] > 1.0,
        "bootstrap_return_p05_positive": boot.get("return_p05_pct", -math.inf) > 0.0,
        "bootstrap_pf_p05_above_1": boot.get("profit_factor_p05", 0.0) > 1.0,
        "deflated_sharpe_95pct": metrics["deflated_sharpe_pct"] >= 95.0,
        "recent_half_pf_above_1": metrics["recent_half_profit_factor"] > 1.0,
        "two_of_three_subperiods_profitable": metrics["profitable_thirds"] >= 2,
        "closed_pnl_total_breach_below_5pct": boot.get("closed_pnl_total_limit_breach_pct", 100.0) < 5.0,
        "cost_stress_supplied": extra_cost_per_trade is not None,
        "cost_stress_pf_above_1": stressed is not None and stressed["profit_factor"] > 1.0,
    }
    mandatory = [value for key, value in gates.items() if key != "cost_stress_supplied"]
    if all(mandatory):
        verdict = "PASS_FOR_FORWARD_TEST"
    elif metrics["return_pct"] > 0.0 and metrics["profit_factor"] > 1.0:
        verdict = "WATCH_ONLY"
    else:
        verdict = "REJECT"
    return {
        "label": label,
        "verdict": verdict,
        "metadata": metadata,
        "metrics": metrics,
        "bootstrap": boot,
        "subperiods": thirds,
        "cost_stress": stressed or {"status": "not_run", "reason": "supply --extra-cost-per-trade from broker evidence"},
        "gates": gates,
        "trades": [asdict(item) | {"closed_at": item.closed_at.isoformat()} for item in outcomes],
    }


def markdown(payload: dict) -> str:
    m = payload["metrics"]
    b = payload["bootstrap"]
    lines = [
        f"# Calyx evidence audit — {payload['label']}",
        "",
        f"**Verdict: {payload['verdict'].replace('_', ' ')}**",
        "",
        "This is an evidence-quality decision, not a profit guarantee.",
        "",
        "## Observed and uncertainty metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Closed trades | {m['trades']} |",
        f"| Return | {m['return_pct']:+.2f}% |",
        f"| Profit factor | {m['profit_factor']:.2f} |",
        f"| Win rate | {m['win_rate_pct']:.2f}% |",
        f"| Win-rate 95% interval | {m['win_rate_wilson_95_pct'][0]:.2f}% – {m['win_rate_wilson_95_pct'][1]:.2f}% |",
        f"| Annualized Sharpe | {m['annualized_sharpe']:.2f} |",
        f"| Deflated Sharpe probability | {m['deflated_sharpe_pct']:.2f}% |",
        f"| Daily expected shortfall (95%) | {m['daily_expected_shortfall_95_pct']:.2f}% |",
        f"| Recent-half PF | {m['recent_half_profit_factor']:.2f} |",
        f"| Max win / loss streak | {m['max_win_streak']} / {m['max_loss_streak']} |",
        "",
        f"## {b.get('paths', 0):,}-path block bootstrap",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Probability profitable | {b.get('probability_profit_pct', 0.0):.2f}% |",
        f"| Return P5 / median / P95 | {b.get('return_p05_pct', 0.0):+.2f}% / {b.get('return_p50_pct', 0.0):+.2f}% / {b.get('return_p95_pct', 0.0):+.2f}% |",
        f"| PF P5 / median / P95 | {b.get('profit_factor_p05', 0.0):.2f} / {b.get('profit_factor_p50', 0.0):.2f} / {b.get('profit_factor_p95', 0.0):.2f} |",
        f"| Max DD median / P95 | {b.get('max_drawdown_p50_pct', 0.0):.2f}% / {b.get('max_drawdown_p95_pct', 0.0):.2f}% |",
        f"| Closed-P&L daily / total rule breach | {b.get('closed_pnl_daily_limit_breach_pct', 0.0):.2f}% / {b.get('closed_pnl_total_limit_breach_pct', 0.0):.2f}% |",
        "",
        "## Chronological stability",
        "",
        "| Third | Dates | Trades | Net | PF | Win rate |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["subperiods"]:
        lines.append(
            f"| {row['part']} | {row['start'][:10]} to {row['end'][:10]} | {row['trades']} | "
            f"{row['net_profit']:+.2f} | {row['profit_factor']:.2f} | {row['win_rate_pct']:.2f}% |"
        )
    lines += ["", "## Gates", ""]
    for name, passed in payload["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {name.replace('_', ' ')}")
    lines += [
        "",
        "The prop-rule probabilities use closed trades only. Final promotion still requires MT5 equity-path/floating-drawdown evidence and a broker-specific cost-stress value.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Calyx post-backtest evidence and robustness audit")
    parser.add_argument("--report", type=Path, action="append", required=True, help="Native MT5 HTML report; repeat for several reports")
    parser.add_argument("--label", action="append", help="Label matching each --report")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paths", type=int, default=DEFAULT_PATHS)
    parser.add_argument("--block", type=int, default=5)
    parser.add_argument("--tested-configurations", type=int, default=1, help="All configurations tried, including rejected ones")
    parser.add_argument("--daily-loss-limit", type=float, default=5.0)
    parser.add_argument("--total-loss-limit", type=float, default=10.0)
    parser.add_argument("--extra-cost-per-trade", type=float)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    labels = args.label or []
    if labels and len(labels) != len(args.report):
        parser.error("Provide one --label for every --report, or omit all labels")
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for index, report in enumerate(args.report):
        label = labels[index] if labels else report.stem
        payload = audit_report(
            report,
            label=label,
            paths=args.paths,
            block=args.block,
            tested_configurations=args.tested_configurations,
            daily_loss_limit_pct=args.daily_loss_limit,
            total_loss_limit_pct=args.total_loss_limit,
            extra_cost_per_trade=args.extra_cost_per_trade,
            seed=args.seed + index,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"audit-{index + 1}"
        (args.output / f"{slug}.json").write_text(json.dumps(json_safe(payload), indent=2, default=str, allow_nan=False), encoding="utf-8")
        (args.output / f"{slug}.md").write_text(markdown(payload), encoding="utf-8")
        summaries.append({"label": label, "verdict": payload["verdict"], **payload["metrics"]})
        print(f"{label}: {payload['verdict']} | PF {payload['metrics']['profit_factor']:.2f} | return {payload['metrics']['return_pct']:+.2f}% | n={payload['metrics']['trades']}")
    (args.output / "summary.json").write_text(json.dumps(json_safe(summaries), indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
