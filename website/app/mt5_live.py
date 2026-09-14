from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - exercised only on unsupported hosts
    mt5 = None  # type: ignore[assignment]

from .catalog import PACKAGE_ROOT, STORE_ROOT, get_catalog


DEFAULT_TERMINAL = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
POLL_SECONDS = 5.0
HISTORY_FROM = datetime(2000, 1, 1, tzinfo=timezone.utc)
CURVE_FROM = datetime(2026, 8, 1, tzinfo=timezone.utc)
MAGIC_PATTERN = re.compile(r"(?im)^(?:Inp)?Magic(?:Number)?\s*=\s*(\d+)")


def _iso(timestamp: float | int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mask_login(login: Any) -> str:
    text = str(login or "")
    return f"••••{text[-4:]}" if text else "Unavailable"


def load_magic_map() -> dict[int, str]:
    mapping: dict[int, str] = {0: "Manual / unassigned"}
    for product in get_catalog():
        path = PACKAGE_ROOT / product.set_source
        if not path.is_file():
            continue
        try:
            match = MAGIC_PATTERN.search(path.read_text(encoding="utf-8-sig", errors="ignore"))
        except OSError:
            continue
        if match:
            suffix = " (Development)" if product.development else ""
            mapping[int(match.group(1))] = f"{product.label}{suffix}"
    return mapping


def _ea_name(magic: int, magic_map: dict[int, str]) -> str:
    if magic in magic_map:
        return magic_map[magic]
    return f"External EA · magic {magic}" if magic else "Manual / unassigned"


def _trade_direction(deal_type: int) -> str:
    return "Buy" if deal_type == 0 else "Sell" if deal_type == 1 else "Other"


def _weighted_price(rows: list[Any]) -> float | None:
    volume = sum(_float(row.volume) for row in rows)
    if volume <= 0:
        return None
    return sum(_float(row.price) * _float(row.volume) for row in rows) / volume


def reconstruct_trades(deals: list[Any], magic_map: dict[int, str]) -> list[dict[str, Any]]:
    groups: dict[int, list[Any]] = defaultdict(list)
    for deal in deals:
        if not getattr(deal, "symbol", "") or int(getattr(deal, "type", -1)) not in (0, 1):
            continue
        position_id = int(getattr(deal, "position_id", 0) or 0)
        if position_id:
            groups[position_id].append(deal)

    trades: list[dict[str, Any]] = []
    for position_id, rows in groups.items():
        rows.sort(key=lambda row: (int(row.time_msc), int(row.ticket)))
        entries = [row for row in rows if int(row.entry) in (0, 2)]
        exits = [row for row in rows if int(row.entry) in (1, 2, 3)]
        if not entries or not exits:
            continue
        first = entries[0]
        last = exits[-1]
        magic = next((int(row.magic) for row in entries if int(row.magic)), int(first.magic))
        entry_comment = next((str(row.comment) for row in entries if str(row.comment).strip()), "")
        exit_comment = next((str(row.comment) for row in reversed(exits) if str(row.comment).strip()), "")
        gross_profit = sum(_float(row.profit) for row in rows)
        costs = sum(_float(row.commission) + _float(row.swap) + _float(row.fee) for row in rows)
        trades.append(
            {
                "position_id": position_id,
                "ea": _ea_name(magic, magic_map),
                "magic": magic,
                "symbol": str(first.symbol),
                "side": _trade_direction(int(first.type)),
                "volume": round(sum(_float(row.volume) for row in entries), 4),
                "open_time": _iso(first.time_msc / 1000),
                "close_time": _iso(last.time_msc / 1000),
                "open_price": _weighted_price(entries),
                "close_price": _weighted_price(exits),
                "gross_profit": round(gross_profit, 2),
                "costs": round(costs, 2),
                "net_profit": round(gross_profit + costs, 2),
                "duration_seconds": max(0, int((last.time_msc - first.time_msc) / 1000)),
                "entry_comment": entry_comment,
                "exit_comment": exit_comment,
            }
        )
    trades.sort(key=lambda trade: trade["close_time"] or "", reverse=True)
    return trades


def serialize_positions(positions: list[Any], magic_map: dict[int, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in positions:
        magic = int(row.magic)
        result.append(
            {
                "ticket": int(row.ticket),
                "ea": _ea_name(magic, magic_map),
                "magic": magic,
                "symbol": str(row.symbol),
                "side": "Buy" if int(row.type) == 0 else "Sell",
                "volume": _float(row.volume),
                "open_time": _iso(row.time_msc / 1000),
                "open_price": _float(row.price_open),
                "current_price": _float(row.price_current),
                "stop_loss": _float(row.sl) or None,
                "take_profit": _float(row.tp) or None,
                "profit": round(_float(row.profit) + _float(row.swap), 2),
                "comment": str(row.comment or ""),
            }
        )
    result.sort(key=lambda position: position["open_time"] or "", reverse=True)
    return result


def serialize_orders(orders: list[Any], magic_map: dict[int, str]) -> list[dict[str, Any]]:
    order_types = {2: "Buy limit", 3: "Sell limit", 4: "Buy stop", 5: "Sell stop", 6: "Buy stop limit", 7: "Sell stop limit"}
    result: list[dict[str, Any]] = []
    for row in orders:
        magic = int(row.magic)
        result.append(
            {
                "ticket": int(row.ticket),
                "ea": _ea_name(magic, magic_map),
                "magic": magic,
                "symbol": str(row.symbol),
                "type": order_types.get(int(row.type), f"Order {int(row.type)}"),
                "volume": _float(row.volume_initial),
                "placed_time": _iso(row.time_setup_msc / 1000),
                "price": _float(row.price_open),
                "stop_loss": _float(row.sl) or None,
                "take_profit": _float(row.tp) or None,
                "comment": str(row.comment or ""),
            }
        )
    return result


def summarize_eas(trades: list[dict[str, Any]], positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: dict[tuple[str, int], dict[str, Any]] = {}
    for trade in trades:
        key = (trade["ea"], int(trade["magic"]))
        item = summaries.setdefault(
            key,
            {"ea": key[0], "magic": key[1], "closed_trades": 0, "wins": 0, "net_profit": 0.0, "open_positions": 0, "floating_profit": 0.0, "symbols": set()},
        )
        item["closed_trades"] += 1
        item["wins"] += int(trade["net_profit"] > 0)
        item["net_profit"] += trade["net_profit"]
        item["symbols"].add(trade["symbol"])
    for position in positions:
        key = (position["ea"], int(position["magic"]))
        item = summaries.setdefault(
            key,
            {"ea": key[0], "magic": key[1], "closed_trades": 0, "wins": 0, "net_profit": 0.0, "open_positions": 0, "floating_profit": 0.0, "symbols": set()},
        )
        item["open_positions"] += 1
        item["floating_profit"] += position["profit"]
        item["symbols"].add(position["symbol"])

    result: list[dict[str, Any]] = []
    for item in summaries.values():
        closed = int(item["closed_trades"])
        result.append(
            {
                **item,
                "net_profit": round(item["net_profit"], 2),
                "floating_profit": round(item["floating_profit"], 2),
                "win_rate": round(item["wins"] / closed * 100, 2) if closed else None,
                "symbols": sorted(item["symbols"]),
            }
        )
    result.sort(key=lambda item: (item["net_profit"] + item["floating_profit"]), reverse=True)
    return result


def reconstruct_balance_history(
    deals: list[Any], current_balance: float, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Rebuild the balance ledger from a known current balance and MT5 deal cash flows."""
    start_timestamp = start.timestamp()
    end_timestamp = end.timestamp()
    changes: list[tuple[float, float]] = []
    for deal in deals:
        timestamp = _float(getattr(deal, "time_msc", 0)) / 1000.0
        if timestamp <= 0:
            timestamp = _float(getattr(deal, "time", 0))
        if timestamp < start_timestamp or timestamp > end_timestamp:
            continue
        delta = sum(
            _float(getattr(deal, field, 0.0))
            for field in ("profit", "commission", "swap", "fee")
        )
        if abs(delta) > 1e-9:
            changes.append((timestamp, delta))

    changes.sort(key=lambda item: item[0])
    balance = current_balance - sum(delta for _, delta in changes)
    series = [
        {
            "time": start.isoformat(),
            "balance": round(balance, 2),
            "equity": None,
            "floating": None,
            "source": "reconstructed-ledger",
        }
    ]
    for timestamp, delta in changes:
        balance += delta
        series.append(
            {
                "time": _iso(timestamp),
                "balance": round(balance, 2),
                "equity": None,
                "floating": None,
                "source": "reconstructed-ledger",
            }
        )
    series.append(
        {
            "time": end.isoformat(),
            "balance": round(current_balance, 2),
            "equity": None,
            "floating": None,
            "source": "reconstructed-ledger",
        }
    )
    return series


def merge_account_curve(
    balance_history: list[dict[str, Any]], recorded_equity: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    combined = [*balance_history, *recorded_equity]
    combined.sort(key=lambda point: str(point["time"]))
    return combined


class LiveMT5Service:
    def __init__(self, terminal_path: Path | None = None, database_path: Path | None = None) -> None:
        configured = os.getenv("EA_STORE_MT5_TERMINAL")
        self.terminal_path = Path(configured) if configured else terminal_path or DEFAULT_TERMINAL
        self.database_path = database_path or STORE_ROOT / "data" / "live-telemetry.sqlite3"
        live_enabled = os.getenv("CALYX_ENABLE_LIVE_MT5", "").lower() in {"1", "true", "yes"}
        self.magic_map = load_magic_map() if live_enabled else {0: "Manual / unassigned"}
        self._lock = threading.RLock()
        self._connector_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: str | None = None
        self._state: dict[str, Any] = self._empty_state("Live monitoring has not started.")

    def _empty_state(self, message: str) -> dict[str, Any]:
        return {
            "connected": False,
            "message": message,
            "last_update": None,
            "monitoring_started": self._started_at if hasattr(self, "_started_at") else None,
            "account": None,
            "positions": [],
            "orders": [],
            "trades": [],
            "ea_summary": [],
            "equity_series": [],
            "curve_started": CURVE_FROM.isoformat(),
            "equity_recorded_from": None,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._stop.clear()
        self._initialize_database()
        self._thread = threading.Thread(target=self._run, name="ea-store-mt5-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        if mt5 is not None:
            try:
                with self._connector_lock:
                    mt5.shutdown()
            except Exception:
                pass

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._state,
                "positions": [dict(item) for item in self._state["positions"]],
                "orders": [dict(item) for item in self._state["orders"]],
                "trades": [dict(item) for item in self._state["trades"]],
                "ea_summary": [dict(item) for item in self._state["ea_summary"]],
                "equity_series": [dict(item) for item in self._state["equity_series"]],
            }

    def price_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Load broker candles from the currently connected read-only MT5 terminal."""
        if mt5 is None:
            raise RuntimeError("The MetaTrader 5 Python connector is unavailable.")
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        selected_timeframe = timeframe_map.get(timeframe.upper(), mt5.TIMEFRAME_M5)
        with self._connector_lock:
            terminal = mt5.terminal_info()
            if terminal is None or not terminal.connected:
                raise RuntimeError("The website is not connected to an active MT5 terminal.")
            resolved = self._resolve_symbol_locked(symbol)
            mt5.symbol_select(resolved, True)
            rates = mt5.copy_rates_range(resolved, selected_timeframe, start, end)
            if rates is None or len(rates) == 0:
                raise RuntimeError(f"No {timeframe} broker candles were returned for {resolved}.")
            bars = [
                {
                    "time": _iso(int(row["time"])),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "tick_volume": int(row["tick_volume"]),
                }
                for row in rates
            ]
        maximum = 500
        if len(bars) > maximum:
            step = max(1, len(bars) // maximum)
            bars = bars[::step]
            if bars[-1]["time"] != _iso(int(rates[-1]["time"])):
                row = rates[-1]
                bars.append(
                    {
                        "time": _iso(int(row["time"])),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "tick_volume": int(row["tick_volume"]),
                    }
                )
        return {"symbol": str(resolved), "timeframe": timeframe.upper(), "bars": bars}

    def _resolve_symbol_locked(self, symbol: str) -> str:
        available = list(mt5.symbols_get() or [])
        wanted = symbol.upper()
        exact = next((str(row.name) for row in available if str(row.name).upper() == wanted), None)
        resolved = exact or next(
            (str(row.name) for row in available if str(row.name).upper().startswith(wanted)),
            None,
        )
        if not resolved:
            raise RuntimeError(f"MT5 has no compatible symbol for {symbol}.")
        return resolved

    def resolve_symbol(self, symbol: str) -> str:
        if mt5 is None:
            raise RuntimeError("The MetaTrader 5 Python connector is unavailable.")
        with self._connector_lock:
            terminal = mt5.terminal_info()
            if terminal is None or not terminal.connected:
                raise RuntimeError("The website is not connected to an active MT5 terminal.")
            return self._resolve_symbol_locked(symbol)

    def _initialize_database(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    account_key TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    floating REAL NOT NULL,
                    margin REAL NOT NULL,
                    margin_free REAL NOT NULL,
                    margin_level REAL NOT NULL,
                    PRIMARY KEY (account_key, timestamp)
                )
                """
            )

    def _save_equity(self, account_key: str, timestamp: float, account: Any) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO equity_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_key,
                    timestamp,
                    _float(account.balance),
                    _float(account.equity),
                    _float(account.profit),
                    _float(account.margin),
                    _float(account.margin_free),
                    _float(account.margin_level),
                ),
            )

    def _load_equity(
        self, account_key: str, from_timestamp: float, maximum: int = 620
    ) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT timestamp, balance, equity, floating FROM equity_snapshots WHERE account_key=? AND timestamp>=? ORDER BY timestamp",
                (account_key, from_timestamp),
            ).fetchall()
        if len(rows) > maximum:
            step = max(1, len(rows) // (maximum - 1))
            sampled = rows[::step]
            if sampled[-1] != rows[-1]:
                sampled.append(rows[-1])
            rows = sampled
        return [
            {
                "time": _iso(row[0]),
                "balance": row[1],
                "equity": row[2],
                "floating": row[3],
                "source": "recorded-equity",
            }
            for row in rows
        ]

    def _run(self) -> None:
        if os.getenv("EA_STORE_DISABLE_MT5") == "1":
            with self._lock:
                self._state = self._empty_state("Live MT5 monitoring is disabled by configuration.")
            return
        if mt5 is None:
            with self._lock:
                self._state = self._empty_state("The MetaTrader 5 Python connector is unavailable.")
            return
        initialized = False
        while not self._stop.is_set():
            try:
                if not initialized:
                    with self._connector_lock:
                        initialized = bool(mt5.initialize(path=str(self.terminal_path), timeout=60_000))
                    if not initialized:
                        raise RuntimeError(f"MT5 connection failed: {mt5.last_error()}")
                self._poll()
            except Exception as exc:
                initialized = False
                try:
                    with self._connector_lock:
                        mt5.shutdown()
                except Exception:
                    pass
                with self._lock:
                    stale = self._state
                    self._state = {
                        **stale,
                        "connected": False,
                        "message": str(exc),
                        "last_update": datetime.now(timezone.utc).isoformat(),
                    }
            self._stop.wait(POLL_SECONDS)

    def _poll(self) -> None:
        now = datetime.now(timezone.utc)
        with self._connector_lock:
            account = mt5.account_info()
            terminal = mt5.terminal_info()
            if account is None or terminal is None or not terminal.connected:
                raise RuntimeError("MT5 is not connected to an active account.")
            positions_raw = list(mt5.positions_get() or [])
            orders_raw = list(mt5.orders_get() or [])
            deals_raw = list(mt5.history_deals_get(HISTORY_FROM, now) or [])
        positions = serialize_positions(positions_raw, self.magic_map)
        orders = serialize_orders(orders_raw, self.magic_map)
        trades = reconstruct_trades(deals_raw, self.magic_map)
        account_key = hashlib.sha256(str(account.login).encode("utf-8")).hexdigest()[:16]
        self._save_equity(account_key, now.timestamp(), account)
        recorded_equity = self._load_equity(account_key, CURVE_FROM.timestamp())
        balance_history = reconstruct_balance_history(
            deals_raw, _float(account.balance), CURVE_FROM, now
        )
        equity_series = merge_account_curve(balance_history, recorded_equity)
        first_deal = min((int(deal.time) for deal in deals_raw), default=None)
        account_payload = {
            "login": _mask_login(account.login),
            "server": str(account.server),
            "company": str(account.company),
            "currency": str(account.currency),
            "balance": _float(account.balance),
            "equity": _float(account.equity),
            "floating_profit": _float(account.profit),
            "margin": _float(account.margin),
            "margin_free": _float(account.margin_free),
            "margin_level": _float(account.margin_level),
            "leverage": int(account.leverage),
            "history_started": _iso(first_deal),
            "closed_net_profit": round(sum(trade["net_profit"] for trade in trades), 2),
        }
        state = {
            "connected": True,
            "message": "Live read-only MT5 connection",
            "last_update": now.isoformat(),
            "monitoring_started": self._started_at,
            "curve_started": CURVE_FROM.isoformat(),
            "equity_recorded_from": recorded_equity[0]["time"] if recorded_equity else None,
            "account": account_payload,
            "positions": positions,
            "orders": orders,
            "trades": trades,
            "ea_summary": summarize_eas(trades, positions),
            "equity_series": equity_series,
        }
        with self._lock:
            self._state = state


live_mt5 = LiveMT5Service()
