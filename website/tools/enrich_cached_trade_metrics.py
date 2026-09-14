from __future__ import annotations

import json
import sys
from pathlib import Path


STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

from app.catalog import get_sellable_catalog  # noqa: E402
from app.evidence_cache import (  # noqa: E402
    PERIOD_OPTIONS,
    product_cache_path,
    product_trades_path,
    write_json,
)
from app.trade_metrics import enrich_trades, outcome_streaks  # noqa: E402


def main() -> int:
    updated = 0
    for product in get_sellable_catalog():
        modes = ["standard"] + (["safe"] if product.safe_filter_supported else [])
        for mode in modes:
            for option in PERIOD_OPTIONS:
                path = product_trades_path(product.slug, mode, option["value"])
                if not path.is_file():
                    continue
                trades = json.loads(path.read_text(encoding="utf-8-sig"))
                enriched = enrich_trades(trades, product.slug)
                write_json(path, enriched)
                summary_path = product_cache_path(product.slug, mode, option["value"])
                if summary_path.is_file():
                    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
                    summary.setdefault("stats", {}).update(outcome_streaks(enriched))
                    write_json(summary_path, summary)
                updated += 1
                print(f"ENRICHED {product.label} | {mode} | {option['value']} | {len(trades)} trades + streaks")
    print(f"DONE {updated} cached trade ledgers and summaries enriched; no MT5 backtest was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
