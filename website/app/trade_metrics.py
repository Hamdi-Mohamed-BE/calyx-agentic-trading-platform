from __future__ import annotations

from datetime import datetime
from typing import Any


NEWS_PULSE_PREFIX = "news-pulse-"


def configured_risk_percent(slug: str) -> float:
    # News Pulse splits its hard 1.50% event budget across two pending directions.
    return 0.75 if slug.startswith(NEWS_PULSE_PREFIX) else 1.0


def pip_spec(symbol: str) -> tuple[float, str]:
    normalized = symbol.upper().replace(".", "")
    if normalized.startswith("XAU"):
        return 0.1, "pips"
    if normalized.startswith("XAG"):
        return 0.01, "pips"
    if normalized.startswith(("BTC", "ETH")):
        return 1.0, "points"
    if len(normalized) >= 6 and normalized[:6].isalpha():
        return (0.1, "pips") if normalized[3:6] == "JPY" else (0.001, "pips")
    return 1.0, "points"


def _timestamp(value: Any) -> datetime:
    text = str(value or "1970-01-01T00:00:00").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def outcome_streaks(trades: list[dict[str, Any]]) -> dict[str, int]:
    """Return the longest consecutive winning and losing runs by close time.

    Break-even rows are neutral: they end either active streak and are not
    counted as wins or losses.
    """
    ordered = sorted(
        enumerate(trades),
        key=lambda item: (
            _timestamp(item[1].get("close_time")),
            int(item[1].get("number") or item[0]),
        ),
    )
    current_wins = 0
    current_losses = 0
    maximum_wins = 0
    maximum_losses = 0
    for _, trade in ordered:
        outcome = float(trade.get("net_profit") or 0.0)
        if outcome > 0:
            current_wins += 1
            current_losses = 0
            maximum_wins = max(maximum_wins, current_wins)
        elif outcome < 0:
            current_losses += 1
            current_wins = 0
            maximum_losses = max(maximum_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0
    return {
        "max_win_streak": maximum_wins,
        "max_loss_streak": maximum_losses,
    }


def enrich_trades(
    trades: list[dict[str, Any]],
    slug: str,
    *,
    starting_balance: float = 10_000.0,
) -> list[dict[str, Any]]:
    """Add exact price movement and estimated realized R to cached MT5 deals."""
    risk_percent = configured_risk_percent(slug)
    indexed = list(enumerate(trades))
    closed = sorted(
        ((_timestamp(row.get("close_time")), index, float(row.get("net_profit") or 0.0)) for index, row in indexed),
        key=lambda item: (item[0], item[1]),
    )
    balance = float(starting_balance)
    closed_index = 0
    risk_at_entry: dict[int, float] = {}
    for index, row in sorted(indexed, key=lambda item: (_timestamp(item[1].get("open_time")), item[0])):
        opened_at = _timestamp(row.get("open_time"))
        while closed_index < len(closed) and closed[closed_index][0] < opened_at:
            balance += closed[closed_index][2]
            closed_index += 1
        risk_at_entry[index] = max(abs(balance) * risk_percent / 100.0, 0.01)

    enriched: list[dict[str, Any]] = []
    for index, row in indexed:
        open_price = float(row.get("open_price") or 0.0)
        close_price = float(row.get("close_price") or 0.0)
        side = str(row.get("side") or "").lower()
        direction = 1.0 if "buy" in side or "long" in side else -1.0
        pip_size, move_unit = pip_spec(str(row.get("symbol") or ""))
        price_move = (close_price - open_price) * direction / pip_size if pip_size else 0.0
        risk_cash = risk_at_entry[index]
        net_profit = float(row.get("net_profit") or 0.0)
        enriched.append(
            {
                **row,
                "price_move": round(price_move, 2),
                "price_move_unit": move_unit,
                "pip_size": pip_size,
                "estimated_r": round(net_profit / risk_cash, 2),
                "estimated_risk_cash": round(risk_cash, 2),
                "configured_risk_pct": risk_percent,
                "r_is_estimate": True,
            }
        )
    return enriched
