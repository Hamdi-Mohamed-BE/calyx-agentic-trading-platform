from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .catalog import STORE_ROOT


CACHE_VERSION = "v1"
CACHE_ROOT = STORE_ROOT / "data" / "evidence-cache" / CACHE_VERSION
PERIOD_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "6m", "label": "Last 6 months"},
    {"value": "1y", "label": "Last 1 year"},
    {"value": "3y", "label": "Last 3 years"},
    {"value": "5y", "label": "Last 5 years"},
)
PERIOD_KEYS = frozenset(option["value"] for option in PERIOD_OPTIONS)
DEFAULT_PERIOD = "3y"


def validate_period(period: str) -> str:
    if period not in PERIOD_KEYS:
        raise ValueError(f"Unknown evidence period: {period}")
    return period


def product_cache_path(slug: str, mode: str, period: str) -> Path:
    validate_period(period)
    return CACHE_ROOT / "products" / slug / mode / f"{period}.json"


def product_trades_path(slug: str, mode: str, period: str) -> Path:
    validate_period(period)
    return CACHE_ROOT / "products" / slug / mode / f"{period}.trades.json"


def portfolio_cache_path(mode: str, period: str) -> Path:
    validate_period(period)
    return CACHE_ROOT / "portfolio" / mode / f"{period}.json"


def portfolio_trades_path(mode: str, period: str) -> Path:
    validate_period(period)
    return CACHE_ROOT / "portfolio" / mode / f"{period}.trades.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _with_cached_trades(payload_path: Path, trades_path: Path) -> dict[str, Any] | None:
    if not payload_path.is_file():
        return None
    payload = dict(_read_json(payload_path))
    if trades_path.is_file():
        all_trades = list(_read_json(trades_path))
        payload["trades"] = all_trades[-500:]
        payload["cached_trade_count"] = len(all_trades)
        payload["displayed_trade_count"] = min(len(all_trades), 500)
    return payload


def load_product_cache(slug: str, mode: str, period: str) -> dict[str, Any] | None:
    return _with_cached_trades(
        product_cache_path(slug, mode, period),
        product_trades_path(slug, mode, period),
    )


def load_product_summary(slug: str, mode: str, period: str) -> dict[str, Any] | None:
    path = product_cache_path(slug, mode, period)
    return dict(_read_json(path)) if path.is_file() else None


def load_portfolio_cache(mode: str, period: str) -> dict[str, Any] | None:
    return _with_cached_trades(
        portfolio_cache_path(mode, period),
        portfolio_trades_path(mode, period),
    )


def load_portfolio_summary(mode: str, period: str) -> dict[str, Any] | None:
    path = portfolio_cache_path(mode, period)
    return dict(_read_json(path)) if path.is_file() else None


def load_cached_trade(slug: str, mode: str, period: str, number: int) -> dict[str, Any] | None:
    path = product_trades_path(slug, mode, period)
    if not path.is_file():
        return None
    return next(
        (dict(row) for row in _read_json(path) if int(row.get("number", -1)) == number),
        None,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def cache_manifest() -> dict[str, Any] | None:
    path = CACHE_ROOT / "manifest.json"
    return dict(_read_json(path)) if path.is_file() else None


def available_product_periods(slug: str, mode: str = "standard") -> set[str]:
    return {
        period for period in PERIOD_KEYS
        if product_cache_path(slug, mode, period).is_file()
    }


def all_period_values() -> Iterable[str]:
    return (option["value"] for option in PERIOD_OPTIONS)
