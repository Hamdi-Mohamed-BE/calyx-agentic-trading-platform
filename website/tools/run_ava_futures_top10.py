from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

from app.catalog import PACKAGE_ROOT, get_product  # noqa: E402
from app.evidence_cache import load_product_summary  # noqa: E402
from app.mt5_evidence_jobs import MT5EvidenceJobs  # noqa: E402


TESTER = PACKAGE_ROOT / "_Backtests" / "MT5-Ava-Futures-20260909" / "terminal64.exe"
OUTPUT = PACKAGE_ROOT / "Ava Futures Portfolio Research 2026-09-09"
AVA_EA_ROOT = OUTPUT / "EA"

# Full continuous futures are used only for history. Deposits are scaled by the
# full-to-micro contract ratio so 1% risk has the same economics as a $10k
# micro-futures account. Installation targets the current tradable micro contract.
CASES = (
    ("news-pulse-xag", "standard", "SIEc1", "SILZ26", 50_000, date(2024, 2, 28)),
    ("news-pulse-xau", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("xau-trend-progression", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("dmc-fresh-reaction-xau", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("ema3", "safe", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("xau-orb-london-ny-overlap-m30", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("xau-elliott-wave-1-2-3", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("us100-h1-orb-13utc", "standard", "ENQc1", "MNQZ26", 100_000, date(2023, 9, 9)),
    ("xau-weakness", "safe", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("xau-rsi-vwap", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
)

AVA_EXPERTS = {
    "news-pulse-xag": AVA_EA_ROOT / "News Pulse" / "AAA Final News Pulse EA.ex5",
    "news-pulse-xau": AVA_EA_ROOT / "News Pulse" / "AAA Final News Pulse EA.ex5",
    "xau-trend-progression": AVA_EA_ROOT / "Trend Progression" / "Trend Progression EA.ex5",
    "dmc-fresh-reaction-xau": AVA_EA_ROOT / "DMC Fresh Reaction" / "Calyx DMC Fresh Reaction EA.ex5",
    "ema3": AVA_EA_ROOT / "EMA3" / "AAA Final EMA3 EA.ex5",
    "xau-orb-london-ny-overlap-m30": AVA_EA_ROOT / "ORB Volume Data" / "ORB Volume Data EA.ex5",
    "xau-elliott-wave-1-2-3": AVA_EA_ROOT / "Elliott Wave" / "Elliott Wave 123 EA.ex5",
    "us100-h1-orb-13utc": AVA_EA_ROOT / "ORB Volume Data" / "ORB Volume Data EA.ex5",
    "xau-weakness": AVA_EA_ROOT / "XAU Weakness" / "AAA Final XAU Weakness EA.ex5",
    "xau-rsi-vwap": AVA_EA_ROOT / "RSI VWAP" / "RSI VWAP Managed EA.ex5",
}


def evidence_payload(product: Any, mode: str) -> dict[str, Any]:
    if mode == "safe" and product.safe_evidence and "2023" in product.safe_evidence.period:
        evidence = product.safe_evidence
        return {
            "period": evidence.period,
            "return_pct": evidence.return_pct,
            "profit_factor": evidence.profit_factor,
            "win_rate_pct": evidence.win_rate_pct,
            "drawdown_pct": evidence.drawdown_pct,
            "trades": evidence.trades,
        }
    cached = load_product_summary(product.slug, mode, "3y")
    if cached:
        stats = cached.get("stats", cached)
        return {
            "period": cached.get("period", f"{cached.get('available_from', '')} to {cached.get('available_to', '')}"),
            "return_pct": stats.get("return_pct", 0.0),
            "profit_factor": stats.get("profit_factor", 0.0),
            "win_rate_pct": stats.get("win_rate_pct", 0.0),
            "drawdown_pct": stats.get("max_drawdown_pct", stats.get("drawdown_pct", 0.0)),
            "trades": stats.get("trades", 0),
        }
    evidence = product.safe_evidence if mode == "safe" and product.safe_evidence else product.evidence
    return {
        "period": evidence.period,
        "return_pct": evidence.return_pct,
        "profit_factor": evidence.profit_factor,
        "win_rate_pct": evidence.win_rate_pct,
        "drawdown_pct": evidence.drawdown_pct,
        "trades": evidence.trades,
    }


def tester_log_lines(job_id: str, slug: str) -> list[str]:
    pattern = f"{slug}-{job_id[:8]}"
    lines: list[str] = []
    for log in (TESTER.parent / "Tester").glob("Agent-*/logs/*.log"):
        try:
            lines.extend(line for line in log.read_text(encoding="utf-16", errors="ignore").splitlines() if pattern in line)
        except OSError:
            continue
    return lines


def save(payload: dict[str, Any]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "ava-futures-top10-results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def main() -> int:
    if not TESTER.is_file():
        raise FileNotFoundError(f"Ava isolated tester is missing: {TESTER}")
    os.environ["EA_STORE_TESTER_TERMINAL"] = str(TESTER)
    if not os.getenv("EA_STORE_TESTER_SERVER") or not os.getenv("EA_STORE_TESTER_LOGIN"):
        raise RuntimeError("Configure EA_STORE_TESTER_SERVER and EA_STORE_TESTER_LOGIN privately before running.")
    os.environ.setdefault("EA_STORE_TESTER_LEVERAGE", "2000")
    end = date(2026, 9, 8)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Ava continuous-futures Every Tick tests. NQ and Gold use a $100k tester balance "
            "to emulate one micro contract on a $10k account; Silver uses $50k for the same reason. "
            "Ava-only EA builds always use exactly one broker-minimum contract."
        ),
        "rows": [],
    }
    save(payload)
    for index, (slug, mode, history_symbol, install_symbol, deposit, start) in enumerate(CASES, 1):
        product = get_product(slug)
        if product is None:
            raise ValueError(f"Unknown product: {slug}")
        print(f"[{index}/10] {product.label} | {history_symbol} | {start} to {end}", flush=True)
        os.environ["EA_STORE_TESTER_DEPOSIT"] = str(deposit)
        jobs = MT5EvidenceJobs()
        job = jobs.start(
            slug,
            mode,
            start,
            end,
            history_symbol,
            expert_source_override=AVA_EXPERTS[slug],
        )
        last_stage = ""
        while job["status"] in {"queued", "running"}:
            stage = str(job.get("stage", ""))
            if stage != last_stage:
                last_stage = stage
                print(f"  {job.get('progress', 0)}% {stage}", flush=True)
            time.sleep(2)
            job = jobs.get(str(job["id"])) or job
        row: dict[str, Any] = {
            "rank": index,
            "label": product.label,
            "slug": slug,
            "mode": mode,
            "history_symbol": history_symbol,
            "install_symbol": install_symbol,
            "emulation_deposit": deposit,
            "history_period": f"{start.isoformat()} to {end.isoformat()}",
            "cfd_3y": evidence_payload(product, mode),
            "status": job["status"],
        }
        if job["status"] == "completed" and job.get("result"):
            stats = dict(job["result"].get("stats", {}))
            row["ava_futures"] = stats
            lines = tester_log_lines(str(job["id"]), slug)
            row["risk_skip_count"] = sum("risk size is below" in line.lower() for line in lines)
            report = jobs.output_root / slug / "latest.htm"
            if report.is_file():
                reports = OUTPUT / "Reports"
                reports.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report, reports / f"{index:02d}-{slug}.htm")
            print(
                "  RESULT "
                f"Return {stats.get('return_pct', 0):.2f}% | PF {stats.get('profit_factor', 0):.2f} | "
                f"WR {stats.get('win_rate_pct', 0):.2f}% | DD {stats.get('max_drawdown_pct', 0):.2f}% | "
                f"Trades {stats.get('trades', 0)}",
                flush=True,
            )
        else:
            row["error"] = job.get("error") or "Unknown MT5 test failure"
            print(f"  FAILED {row['error']}", flush=True)
        payload["rows"].append(row)
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        save(payload)
        time.sleep(4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
