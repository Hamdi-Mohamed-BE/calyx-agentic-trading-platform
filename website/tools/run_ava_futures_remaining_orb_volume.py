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
RESULT_PATH = OUTPUT / "ava-futures-remaining-orb-volume-results.json"

CASES = (
    ("lta-volume-profile", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("lta-volume-profile", "safe", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("orb-volume-profile", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("orb-volume-profile-volume-confirmed", "standard", "GCEc1", "MGCZ26", 100_000, date(2024, 2, 28)),
    ("us100-selective-orb-v3", "standard", "ENQc1", "MNQZ26", 100_000, date(2023, 9, 9)),
)

AVA_EXPERTS = {
    "lta-volume-profile": AVA_EA_ROOT / "LTA" / "LTA_Concepts_EA.ex5",
    "orb-volume-profile": AVA_EA_ROOT / "ORB Volume Data" / "ORB Volume Data EA.ex5",
    "orb-volume-profile-volume-confirmed": AVA_EA_ROOT / "ORB Volume Data" / "ORB Volume Data EA.ex5",
    "us100-selective-orb-v3": AVA_EA_ROOT / "Selective ORB" / "US100 Selective ORB Retest EA.ex5",
}


def cfd_payload(slug: str, mode: str) -> dict[str, Any]:
    product = get_product(slug)
    cached = load_product_summary(slug, mode, "3y")
    if cached:
        stats = cached.get("stats", cached)
        return {
            "return_pct": stats.get("return_pct", 0.0),
            "profit_factor": stats.get("profit_factor", 0.0),
            "win_rate_pct": stats.get("win_rate_pct", 0.0),
            "max_drawdown_pct": stats.get("max_drawdown_pct", stats.get("drawdown_pct", 0.0)),
            "trades": stats.get("trades", 0),
        }
    evidence = product.safe_evidence if mode == "safe" and product.safe_evidence else product.evidence
    return {
        "return_pct": evidence.return_pct,
        "profit_factor": evidence.profit_factor,
        "win_rate_pct": evidence.win_rate_pct,
        "max_drawdown_pct": evidence.drawdown_pct,
        "trades": evidence.trades,
    }


def save(payload: dict[str, Any]) -> None:
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    if not TESTER.is_file():
        raise FileNotFoundError(f"Ava isolated tester is missing: {TESTER}")
    for expert in AVA_EXPERTS.values():
        if not expert.is_file():
            raise FileNotFoundError(f"Ava EA build is missing: {expert}")

    os.environ["EA_STORE_TESTER_TERMINAL"] = str(TESTER)
    if not os.getenv("EA_STORE_TESTER_SERVER") or not os.getenv("EA_STORE_TESTER_LOGIN"):
        raise RuntimeError("Configure EA_STORE_TESTER_SERVER and EA_STORE_TESTER_LOGIN privately before running.")
    os.environ.setdefault("EA_STORE_TESTER_LEVERAGE", "2000")
    end = date(2026, 9, 8)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Ava Every Tick continuous-futures tests using one broker-minimum-contract EA builds.",
        "selection_rule": "Propose only PF >= 1.40. Do not mutate the active Ava profile during research.",
        "rows": [],
    }
    save(payload)

    for index, (slug, mode, history_symbol, install_symbol, deposit, start) in enumerate(CASES, 1):
        product = get_product(slug)
        if product is None:
            raise ValueError(f"Unknown product: {slug}")
        label = product.label + (" Safe" if mode == "safe" else "")
        print(f"[{index}/{len(CASES)}] {label} | {history_symbol} | {start} to {end}", flush=True)
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
            "label": product.label,
            "slug": slug,
            "mode": mode,
            "history_symbol": history_symbol,
            "install_symbol": install_symbol,
            "history_period": f"{start.isoformat()} to {end.isoformat()}",
            "cfd_3y": cfd_payload(slug, mode),
            "status": job["status"],
        }
        if job["status"] == "completed" and job.get("result"):
            stats = dict(job["result"].get("stats", {}))
            row["ava_futures"] = stats
            row["passes_pf_1_40"] = float(stats.get("profit_factor", 0.0)) >= 1.40
            report = jobs.output_root / slug / "latest.htm"
            if report.is_file():
                reports = OUTPUT / "Reports"
                reports.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report, reports / f"remaining-{slug}-{mode}.htm")
            print(
                f"  RESULT Return {stats.get('return_pct', 0):.2f}% | "
                f"PF {stats.get('profit_factor', 0):.2f} | WR {stats.get('win_rate_pct', 0):.2f}% | "
                f"DD {stats.get('max_drawdown_pct', 0):.2f}% | Trades {stats.get('trades', 0)}",
                flush=True,
            )
        else:
            row["error"] = job.get("error") or "Unknown MT5 test failure"
            row["passes_pf_1_40"] = False
            print(f"  FAILED {row['error']}", flush=True)
        payload["rows"].append(row)
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        save(payload)
        time.sleep(3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
