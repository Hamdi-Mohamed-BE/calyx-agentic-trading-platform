from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import PACKAGE_ROOT, STORE_ROOT, Product, get_product
from .evidence_series import analyse_equity_series, parse_mt5_balance_series


TAG_RE = re.compile(r"<[^>]+>")
MAX_DAYS = 366 * 5


def _clean(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value)).replace("\xa0", " ").strip()


def _number(value: str) -> float:
    match = re.search(r"[-+]?\d[\d ]*(?:\.\d+)?", value.replace("%", ""))
    return float(match.group(0).replace(" ", "")) if match else 0.0


def _percent_in_parentheses(value: str) -> float:
    match = re.search(r"\(([-+]?\d+(?:\.\d+)?)%\)", value)
    return float(match.group(1)) if match else 0.0


def _read_report(path: Path) -> str:
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeError:
            continue
        if "Initial Deposit" in text:
            return text
    return path.read_text(encoding="utf-8", errors="ignore")


def _metric(text: str, label: str) -> str:
    match = re.search(
        rf">\s*{re.escape(label)}:\s*</td>\s*<td[^>]*>\s*<b>(.*?)</b>",
        text,
        flags=re.I | re.S,
    )
    return _clean(match.group(1)) if match else ""


def _native_metrics(path: Path) -> dict[str, Any]:
    text = _read_report(path)
    initial = _number(_metric(text, "Initial Deposit"))
    net = _number(_metric(text, "Total Net Profit"))
    return {
        "initial_balance": round(initial, 2),
        "final_balance": round(initial + net, 2),
        "net_profit": round(net, 2),
        "return_pct": round(net / initial * 100, 2) if initial else 0.0,
        "profit_factor": round(_number(_metric(text, "Profit Factor")), 2),
        "win_rate_pct": round(_percent_in_parentheses(_metric(text, "Profit Trades (% of total)")), 2),
        "max_drawdown_pct": round(_percent_in_parentheses(_metric(text, "Equity Drawdown Maximal")), 2),
        "trades": int(_number(_metric(text, "Total Trades"))),
        "sharpe_ratio": round(_number(_metric(text, "Sharpe Ratio")), 2),
        "recovery_factor": round(_number(_metric(text, "Recovery Factor")), 2),
        "history_quality": _metric(text, "History Quality"),
    }


def _native_trades(path: Path, label: str) -> list[dict[str, Any]]:
    """Read completed positions directly from the MT5 Deals table.

    Pair exits with the opposite deal side, not just the symbol. News Pulse
    can hold a long and a short simultaneously. Within each side, entries are
    matched FIFO; entry costs are apportioned for partial closes.
    """
    text = _read_report(path)
    marker = text.lower().find("<b>deals</b>")
    if marker < 0:
        return []
    row_re = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
    cell_re = re.compile(r"<td\b[^>]*>(.*?)</td>", re.I | re.S)
    entries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    trades: list[dict[str, Any]] = []
    for row_html in row_re.findall(text[marker:]):
        cells = [_clean(cell) for cell in cell_re.findall(row_html)]
        if len(cells) < 13 or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", cells[0]):
            continue
        symbol, deal_type, direction = cells[2], cells[3].lower(), cells[4].lower()
        if not symbol or deal_type not in {"buy", "sell"}:
            continue
        volume = _number(cells[5])
        price = _number(cells[6])
        commission = _number(cells[8])
        swap = _number(cells[9])
        profit = _number(cells[10])
        timestamp = cells[0].replace(".", "-", 2).replace(" ", "T", 1)
        if direction in {"in", "in/out"}:
            entries.setdefault((symbol, deal_type), []).append(
                {
                    "time": timestamp,
                    "type": deal_type,
                    "volume": volume,
                    "remaining": volume,
                    "price": price,
                    "commission": commission,
                    "swap": swap,
                    "profit": profit,
                    "comment": cells[12],
                }
            )
            if direction == "in":
                continue
        if direction not in {"out", "out by", "in/out"}:
            continue
        remaining_exit = volume
        entry_type = "sell" if deal_type == "buy" else "buy"
        queue = entries.get((symbol, entry_type), [])
        while remaining_exit > 1e-9 and queue:
            entry = queue[0]
            matched = min(remaining_exit, float(entry["remaining"]))
            share = matched / volume if volume > 0 else 1.0
            entry_share = matched / float(entry["volume"]) if float(entry["volume"]) > 0 else 1.0
            matched_commission = commission * share + float(entry["commission"]) * entry_share
            matched_swap = swap * share + float(entry["swap"]) * entry_share
            matched_gross_profit = profit * share + float(entry["profit"]) * entry_share
            net = matched_gross_profit + matched_commission + matched_swap
            trades.append(
                {
                    "number": len(trades) + 1,
                    "ea": label,
                    "symbol": symbol,
                    "side": "Long" if entry["type"] == "buy" else "Short",
                    "volume": round(matched, 4),
                    "open_time": entry["time"],
                    "close_time": timestamp,
                    "open_price": float(entry["price"]),
                    "close_price": price,
                    "gross_profit": round(matched_gross_profit, 2),
                    "commission": round(matched_commission, 2),
                    "swap": round(matched_swap, 2),
                    "total_costs": round(matched_commission + matched_swap, 2),
                    "net_profit": round(net, 2),
                    "result": "Win" if net > 0 else "Loss" if net < 0 else "Flat",
                    "source": "Native MT5 deals",
                    "entry_comment": entry["comment"],
                    "exit_comment": cells[12],
                }
            )
            entry["remaining"] = float(entry["remaining"]) - matched
            remaining_exit -= matched
            if float(entry["remaining"]) <= 1e-9:
                queue.pop(0)
    return trades


def _set_values(source: Path, safe: bool, overrides: dict[str, str] | None = None) -> str:
    lines = source.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    if safe:
        safe_values = {
            "InpUseMarkovRegimeFilter": "true",
            "InpMarkovReturnWindow": "40",
            "InpMarkovThreshold": "0.05",
            "InpMarkovSignalGate": "0.05",
            "InpMarkovMinLabels": "252",
            "InpMarkovHistoryBars": "2600",
        }
        for name, value in safe_values.items():
            found = False
            for index, line in enumerate(lines):
                if not line.strip().startswith(f"{name}="):
                    continue
                prefix, raw = line.split("=", 1)
                suffix = f"||{raw.split('||', 1)[1]}" if "||" in raw else ""
                lines[index] = f"{prefix}={value}{suffix}"
                found = True
                break
            if not found:
                lines.append(f"{name}={value}")
    for name, value in (overrides or {}).items():
        found = False
        for index, line in enumerate(lines):
            if not line.strip().startswith(f"{name}="):
                continue
            prefix, raw = line.split("=", 1)
            suffix = f"||{raw.split('||', 1)[1]}" if "||" in raw else ""
            lines[index] = f"{prefix}={value}{suffix}"
            found = True
            break
        if not found:
            lines.append(f"{name}={value}")
    return "\n".join(lines) + "\n"


def _materialized_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#")) or "=" not in stripped:
            continue
        name, raw = stripped.split("=", 1)
        if name.strip().startswith("Inp"):
            values[name.strip()] = raw.split("||", 1)[0].strip()
    return values


def _report_inputs(path: Path) -> dict[str, str]:
    text = _read_report(path)
    marker = text.lower().find("inputs:")
    if marker < 0:
        return {}
    end = text.lower().find("company:", marker)
    section = text[marker:end if end > marker else len(text)]
    values: dict[str, str] = {}
    for raw in re.findall(r"<b>(Inp[^<]+)</b>", section, flags=re.I | re.S):
        cleaned = _clean(raw).replace("\r", "").replace("\n", "")
        if "=" not in cleaned:
            continue
        name, value = cleaned.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def _same_setting(expected: str, actual: str) -> bool:
    if expected.strip().lower() in {"true", "false"} or actual.strip().lower() in {"true", "false"}:
        return expected.strip().lower() == actual.strip().lower()
    try:
        return abs(float(expected) - float(actual)) < 1e-9
    except ValueError:
        return expected.strip() == actual.strip()


class MT5EvidenceJobs:
    def __init__(self) -> None:
        configured = os.getenv("EA_STORE_TESTER_TERMINAL")
        self.tester_terminal = Path(configured) if configured else PACKAGE_ROOT / "_Backtests" / "MT5-DMC-20260811" / "terminal64.exe"
        self.output_root = STORE_ROOT / "data" / "evidence-jobs"
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._active_job: str | None = None
        self._last_started: dict[str, float] = {}

    def _stop_stale_isolated_terminal(self) -> None:
        """Stop only this portable tester if MT5 left its GUI process behind."""
        environment = os.environ.copy()
        environment["EA_STORE_TESTER_TO_STOP"] = str(self.tester_terminal.resolve())
        script = (
            "$target=$env:EA_STORE_TESTER_TO_STOP; "
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match '^terminal(64)?\\.exe$' -and $_.ExecutablePath -ieq $target } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", script],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def start(
        self,
        slug: str,
        mode: str,
        start: date,
        end: date,
        broker_symbol: str | None = None,
        *,
        tester_start: date | None = None,
        input_overrides: dict[str, str] | None = None,
        expert_source_override: Path | None = None,
    ) -> dict[str, Any]:
        product = get_product(slug)
        if product is None or product.evidence is None:
            raise ValueError("Unknown EA evidence request.")
        if mode == "safe" and not product.safe_filter_supported:
            raise ValueError("This EA has no validated Safe-mode configuration.")
        if mode == "dynamic" and not product.dynamic_mode_supported:
            raise ValueError("This EA has no saved Dynamic London configuration.")
        if start > end:
            raise ValueError("The From date must be earlier than the To date.")
        if (end - start).days > MAX_DAYS:
            raise ValueError("Dynamic MT5 evidence is limited to five years per run.")
        if (end - start).days < 6:
            raise ValueError("Select at least seven calendar days for an MT5 test.")
        key = f"{slug}:{mode}"
        now = time.time()
        with self._lock:
            if self._active_job:
                active = self._jobs.get(self._active_job)
                if active and active["status"] in {"queued", "running"}:
                    if active["slug"] == slug and active["mode"] == mode and active["from"] == start.isoformat() and active["to"] == end.isoformat():
                        return self._public(active)
                    raise ValueError(f"Another MT5 evidence run is active for {active['label']}. Wait for it to finish.")
            if now - self._last_started.get(key, 0) < 10:
                raise ValueError("Please wait a few seconds before starting another MT5 run.")
            job_id = uuid.uuid4().hex
            job = {
                "id": job_id,
                "slug": slug,
                "label": product.label,
                "mode": mode,
                "symbol": broker_symbol or product.canonical,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "status": "queued",
                "stage": "Queued for the isolated MT5 tester",
                "progress": 2,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "result": None,
                "error": None,
            }
            self._jobs[job_id] = job
            self._active_job = job_id
            self._last_started[key] = now
        threading.Thread(
            target=self._run,
            args=(job_id, product, start, end, mode, broker_symbol or product.canonical, tester_start or start, input_overrides or {}, expert_source_override),
            name=f"mt5-evidence-{job_id[:8]}",
            daemon=True,
        ).start()
        return self._public(job)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public(job) if job else None

    def get_trade(self, job_id: str, trade_number: int) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("status") != "completed" or not job.get("result"):
                return None
            return next(
                (dict(row) for row in job["result"].get("trades", []) if int(row.get("number", -1)) == trade_number),
                None,
            )

    def _public(self, job: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(job))

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(changes)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()

    def _run(
        self,
        job_id: str,
        product: Product,
        start: date,
        end: date,
        mode: str,
        broker_symbol: str,
        tester_start: date,
        input_overrides: dict[str, str],
        expert_source_override: Path | None,
    ) -> None:
        process: subprocess.Popen[Any] | None = None
        cleanup_files: list[Path] = []
        cleanup_report_prefix: tuple[Path, str] | None = None
        try:
            self._update(job_id, status="running", stage="Preparing EA and selected settings", progress=8)
            tester_root = self.tester_terminal.parent
            if not self.tester_terminal.is_file():
                raise RuntimeError(f"Isolated MT5 tester not found: {self.tester_terminal}")
            dynamic_mode = mode == "dynamic"
            expert_relative = product.dynamic_expert_source if dynamic_mode else product.expert_source
            if not expert_relative:
                raise RuntimeError(f"No compiled EA is configured for {mode} mode.")
            expert_source = expert_source_override or (PACKAGE_ROOT / expert_relative)
            dedicated_safe = mode == "safe" and bool(product.safe_set_source)
            selected_set_source = (
                product.dynamic_set_source
                if dynamic_mode
                else product.safe_set_source
                if dedicated_safe
                else product.set_source
            )
            if not selected_set_source:
                raise RuntimeError(f"No settings file is configured for {mode} mode.")
            set_source = PACKAGE_ROOT / str(selected_set_source)
            if not expert_source.is_file():
                raise RuntimeError(f"Compiled EA is missing: {expert_source}")
            if not set_source.is_file():
                raise RuntimeError(f"Selected settings are missing: {set_source}")

            expert_folder = tester_root / "MQL5" / "Experts" / "EA Store Dynamic"
            tester_sets = tester_root / "MQL5" / "Profiles" / "Tester"
            report_folder = tester_root / "reports" / "ea-store-dynamic"
            config_folder = tester_root / "backtest-configs" / "ea-store-dynamic"
            saved_folder = self.output_root / product.slug
            for path in (expert_folder, tester_sets, report_folder, config_folder, saved_folder):
                path.mkdir(parents=True, exist_ok=True)

            self._stop_stale_isolated_terminal()

            expert_name = f"{product.slug}-{job_id[:8]}"
            copied_expert = expert_folder / f"{expert_name}.ex5"
            shutil.copy2(expert_source, copied_expert)
            cleanup_files.append(copied_expert)
            set_name = f"{product.slug}-{job_id[:8]}.set"
            materialized_set = _set_values(set_source, mode == "safe" and not dedicated_safe, input_overrides)
            # Write bytes directly. On Windows, write_text translated explicit
            # CRLF into CR-CR-LF, which made MT5 silently fall back to defaults.
            copied_set = tester_sets / set_name
            copied_set.write_bytes(materialized_set.encode("utf-8"))
            cleanup_files.append(copied_set)
            report_name = f"{product.slug}-{job_id}"
            report_path = report_folder / f"{report_name}.htm"
            for stale in report_folder.glob(f"{report_name}*"):
                stale.unlink(missing_ok=True)
            config_path = config_folder / f"{report_name}.ini"
            cleanup_files.append(config_path)
            cleanup_report_prefix = (report_folder, report_name)
            server = os.getenv("EA_STORE_TESTER_SERVER", "").strip()
            login = os.getenv("EA_STORE_TESTER_LOGIN", "").strip()
            if not server or not login:
                raise RuntimeError("EA_STORE_TESTER_SERVER and EA_STORE_TESTER_LOGIN must be configured privately.")
            deposit = os.getenv("EA_STORE_TESTER_DEPOSIT", "10000")
            leverage = os.getenv("EA_STORE_TESTER_LEVERAGE", "2000")
            config = (
                "[Common]\r\n"
                f"Login={login}\r\nServer={server}\r\n\r\n"
                "[Tester]\r\n"
                f"Expert=EA Store Dynamic\\{expert_name}\r\n"
                f"ExpertParameters={set_name}\r\n"
                f"Symbol={broker_symbol}\r\n"
                f"Period={product.timeframe}\r\n"
                f"Login={login}\r\nDeposit={deposit}\r\nCurrency=USD\r\nLeverage=1:{leverage}\r\n"
                "Model=0\r\nExecutionMode=1\r\nOptimization=0\r\n"
                f"FromDate={tester_start.strftime('%Y.%m.%d')}\r\n"
                f"ToDate={end.strftime('%Y.%m.%d')}\r\n"
                "ForwardMode=0\r\n"
                f"Report=reports\\ea-store-dynamic\\{report_name}.htm\r\n"
                "ReplaceReport=1\r\nShutdownTerminal=1\r\nUseCloud=0\r\nVisual=0\r\n"
            )
            config_path.write_text(config, encoding="utf-16")
            self._update(job_id, stage="Running MT5 Every Tick backtest", progress=18)
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                [str(self.tester_terminal), "/portable", f"/config:{config_path.relative_to(tester_root)}"],
                cwd=tester_root,
                creationflags=creation_flags,
            )
            started = time.monotonic()
            while process.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > 1800:
                    process.kill()
                    raise RuntimeError("MT5 evidence run exceeded the 30-minute safety limit.")
                progress = min(88, 18 + int(elapsed / 4))
                self._update(job_id, progress=progress, stage="MT5 is processing broker history and ticks")
                time.sleep(1)
            if process.returncode not in (0, None):
                raise RuntimeError(f"MT5 tester exited with code {process.returncode}.")
            if not report_path.is_file():
                raise RuntimeError("MT5 finished without creating a report. Check symbol history and tester login.")

            expected_inputs = _materialized_values(materialized_set)
            actual_inputs = _report_inputs(report_path)
            common = sorted(set(expected_inputs) & set(actual_inputs))
            mismatched = [name for name in common if not _same_setting(expected_inputs[name], actual_inputs[name])]
            minimum_coverage = max(1, int(len(expected_inputs) * 0.8))
            if len(common) < minimum_coverage or mismatched:
                sample = ", ".join(
                    f"{name}: wanted {expected_inputs[name]}, MT5 used {actual_inputs.get(name, '<missing>')}"
                    for name in mismatched[:5]
                )
                raise RuntimeError(
                    "MT5 did not apply the selected BAT settings"
                    + (f" ({sample})." if sample else ".")
                )

            self._update(job_id, stage="Parsing equity and closed trades", progress=92)
            parse_mt5_balance_series.cache_clear()
            raw_series = [dict(point) for point in parse_mt5_balance_series(report_path)]
            native = _native_metrics(report_path)
            if not raw_series and float(native["initial_balance"]) > 0:
                raw_series = [{"time": f"{start.isoformat()}T00:00:00", "balance": native["initial_balance"]}]
            if len(raw_series) == 1:
                raw_series.append({"time": f"{end.isoformat()}T23:59:59", "balance": raw_series[0]["balance"]})
            analysed = analyse_equity_series(
                raw_series,
                expected_trades=int(native["trades"]),
                label=f"{product.label} — fresh MT5 {mode.title()}",
            )
            if len(analysed["series"]) < 2:
                raise RuntimeError("The native MT5 report contained no usable balance history for this period.")
            trades = _native_trades(report_path, f"{product.label} — {mode.title()}")
            for trade in trades:
                trade["job_id"] = job_id
            native.update({"from": start.isoformat(), "to": end.isoformat()})
            result = {
                "job_id": job_id,
                "label": f"{product.label} — fresh MT5 {mode.title()} run",
                "period": f"{start.isoformat()} to {end.isoformat()}",
                "currency": "USD",
                "series": analysed["series"],
                "stats": native,
                "trades": trades[-500:],
                "available_from": start.isoformat(),
                "available_to": end.isoformat(),
                "notice": "Fresh native MT5 Every Tick result using the selected BAT preset and broker history.",
                "source": "native-mt5-background-job",
            }
            shutil.copy2(report_path, saved_folder / "latest.htm")
            (saved_folder / "latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            self._update(job_id, status="completed", stage="Fresh MT5 evidence is ready", progress=100, result=result)
        except Exception as exc:
            self._update(job_id, status="failed", stage="MT5 evidence refresh failed", progress=100, error=str(exc))
        finally:
            for path in cleanup_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            if cleanup_report_prefix is not None:
                folder, prefix = cleanup_report_prefix
                for path in folder.glob(f"{prefix}*"):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
            with self._lock:
                if self._active_job == job_id:
                    self._active_job = None


mt5_evidence_jobs = MT5EvidenceJobs()
