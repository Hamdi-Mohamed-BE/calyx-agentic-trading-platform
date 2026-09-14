from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


STARTING_BALANCE = 10_000.0
NASDAQ_CANDLE_SLUG = "nasdaq-5m-candle-momentum"
DAILY_ENTRY_STOP_PERCENT = 5.0
SOFT_DRAWDOWN_PCT = 4.0
HARD_DRAWDOWN_PCT = 7.0
SOFT_LOSS_STREAK = 3
HARD_LOSS_STREAK = 5
NEWS_ADAPTIVE_EXEMPTIONS = {
    "news-pulse-xau": "News Pulse XAU",
    "news-pulse-xag": "News Pulse XAG",
    "news-pulse-btc": "News Pulse BTC",
    "gold-news-v9-direction": "Gold News V9 Direction",
}


def is_news_adaptive_exempt(row: dict[str, Any]) -> bool:
    slug = str(row.get("cache_slug") or "")
    label = str(row.get("ea") or "").split(" — ", 1)[0]
    return slug in NEWS_ADAPTIVE_EXEMPTIONS or (not slug and label in NEWS_ADAPTIVE_EXEMPTIONS.values())

RULES = (
    "Nasdaq 5M Candle Momentum uses 0.25x the selected non-News risk.",
    "Non-News entries stop after closed P/L reaches -5% for the current day (-$500 on the $10,000 reference balance).",
    "Non-News risk tapers to 0.5x beyond 4% closed-equity drawdown and 0.25x beyond 7%.",
    "A non-News EA tapers to 0.5x after three consecutive losses and 0.25x after five; its next win resets the taper.",
    "News Pulse XAU, XAG, BTC and Gold News V9 Direction bypass all adaptive entry stops and risk tapers. Their locked 0.75% planned risk per entry is unchanged (1.50% combined for two-sided News Pulse).",
    "News profits and losses still count toward account-wide daily P/L and drawdown for non-News controls. News signal filters, broker constraints and native exits remain unchanged.",
)


def _parse_time(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def simulate_adaptive_portfolio(
    source_trades: list[dict[str, Any]],
    *,
    starting_balance: float = STARTING_BALANCE,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Replay the approved adaptive risk rules on a cached MT5 trade ledger.

    Signals and fills remain the native MT5 evidence. Reduced position sizes are
    modelled linearly, so P/L, commission and swap scale with the risk multiplier.
    """
    candidates: list[dict[str, Any]] = []
    events: list[tuple[datetime, int, str, int]] = []
    for identifier, source in enumerate(source_trades):
        row = dict(source)
        row["_adaptive_id"] = identifier
        row["_open_dt"] = _parse_time(row["open_time"])
        row["_close_dt"] = _parse_time(row["close_time"])
        candidates.append(row)
        # Closing events execute before opening events at the same timestamp.
        events.append((row["_open_dt"], 1, "open", identifier))
        events.append((row["_close_dt"], 0, "close", identifier))
    events.sort(key=lambda item: (item[0], item[1], item[3]))

    daily_entry_stop_cash = float(starting_balance) * DAILY_ENTRY_STOP_PERCENT / 100.0
    accepted: dict[int, dict[str, Any]] = {}
    loss_streak: defaultdict[str, int] = defaultdict(int)
    daily_closed: defaultdict[object, float] = defaultdict(float)
    balance = peak = float(starting_balance)
    counters: defaultdict[str, int] = defaultdict(int)
    skipped_by_ea: defaultdict[str, int] = defaultdict(int)

    for at, _, event_kind, identifier in events:
        row = candidates[identifier]
        slug = str(row.get("cache_slug") or row.get("ea") or "unknown")
        if event_kind == "open":
            multiplier = 1.0
            reasons: list[str] = []
            news_exempt = is_news_adaptive_exempt(row)
            if news_exempt:
                counters["news_exempt_entries"] += 1
                reasons.append("News exemption: original locked risk; no adaptive controls")
            if slug == NASDAQ_CANDLE_SLUG:
                multiplier *= 0.25
                counters["nasdaq_scaled"] += 1
                reasons.append("Nasdaq 5M allocation 0.25x")

            if not news_exempt and daily_closed[at.date()] <= -daily_entry_stop_cash:
                counters["daily_stop_skips"] += 1
                skipped_by_ea[slug] += 1
                continue

            drawdown_pct = 100.0 * (peak - balance) / peak if peak else 0.0
            if not news_exempt and drawdown_pct >= HARD_DRAWDOWN_PCT:
                multiplier *= 0.25
                counters["hard_dd_taper"] += 1
                reasons.append("portfolio DD >= 7%")
            elif not news_exempt and drawdown_pct >= SOFT_DRAWDOWN_PCT:
                multiplier *= 0.5
                counters["soft_dd_taper"] += 1
                reasons.append("portfolio DD >= 4%")

            streak = loss_streak[slug]
            if not news_exempt and streak >= HARD_LOSS_STREAK:
                multiplier *= 0.25
                counters["hard_ea_taper"] += 1
                reasons.append("EA loss streak >= 5")
            elif not news_exempt and streak >= SOFT_LOSS_STREAK:
                multiplier *= 0.5
                counters["soft_ea_taper"] += 1
                reasons.append("EA loss streak >= 3")

            raw_net = float(row.get("net_profit") or 0.0)
            raw_commission = float(row.get("commission") or 0.0)
            raw_swap = float(row.get("swap") or 0.0)
            raw_gross = float(row.get("gross_profit") if row.get("gross_profit") is not None else raw_net - raw_commission - raw_swap)
            scaled = {
                **row,
                "raw_net_profit": round(raw_net, 2),
                "raw_gross_profit": round(raw_gross, 2),
                "raw_commission": round(raw_commission, 2),
                "raw_swap": round(raw_swap, 2),
                "risk_multiplier": round(multiplier, 6),
                "adaptive_reason": ", ".join(reasons) if reasons else "Base selected risk",
                "gross_profit": round(raw_gross * multiplier, 2),
                "commission": round(raw_commission * multiplier, 2),
                "swap": round(raw_swap * multiplier, 2),
                "total_costs": round((raw_commission + raw_swap) * multiplier, 2),
                "net_profit": round(raw_net * multiplier, 2),
                "cost_basis": "Linearly scaled from native MT5 deal costs",
            }
            scaled["result"] = "Win" if scaled["net_profit"] > 0 else "Loss" if scaled["net_profit"] < 0 else "Flat"
            accepted[identifier] = scaled
            if multiplier < 0.999999:
                counters["scaled_trades"] += 1
            continue

        accepted_row = accepted.get(identifier)
        if accepted_row is None:
            continue
        pnl = float(accepted_row["net_profit"])
        balance += pnl
        peak = max(peak, balance)
        daily_closed[at.date()] += pnl
        accepted_slug = str(accepted_row.get("cache_slug") or accepted_row.get("ea") or "unknown")
        if pnl < 0:
            loss_streak[accepted_slug] += 1
        elif pnl > 0:
            loss_streak[accepted_slug] = 0

    clean_rows: list[dict[str, Any]] = []
    for row in accepted.values():
        clean_rows.append({key: value for key, value in row.items() if not key.startswith("_")})
    clean_rows.sort(key=lambda row: (str(row["close_time"]), str(row.get("ea") or "")))
    return clean_rows, dict(counters), dict(skipped_by_ea)
