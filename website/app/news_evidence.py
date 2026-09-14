"""Only independently verified, period-matched News Pulse evidence is public."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from calendar import monthrange
from pathlib import Path
from typing import Any

NEWS_SLUGS=frozenset({'news-pulse-xau','news-pulse-xag','news-pulse-btc'})
NEWS_EVIDENCE_VERSION=1
CACHE_ROOT=Path(__file__).resolve().parents[1]/'data'/'evidence-cache'/'v1'

def load_news_summary(slug: str, period: str='3y') -> dict[str, Any] | None:
    if slug not in NEWS_SLUGS or period not in {'6m','1y','3y','5y'}:
        return None
    path=CACHE_ROOT/'products'/slug/'standard'/f'{period}.json'
    if not path.is_file():
        return None
    try:
        payload=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None
    if (not isinstance(payload, dict) or payload.get('news_evidence_version')!=NEWS_EVIDENCE_VERSION
            or payload.get('period_key')!=period
            or not payload.get('independent_native_run')
            or not payload.get('calendar_verified')):
        return None
    try:
        start=date.fromisoformat(payload['available_from'])
        end=date.fromisoformat(payload['available_to'])
        months={'6m':6,'1y':12,'3y':36,'5y':60}[period]
        year,month=divmod(end.year*12+end.month-1-months,12)
        expected_start=date(year,month+1,min(end.day,monthrange(year,month+1)[1]))
        if start!=expected_start or payload['stats']['from']!=str(start) or payload['stats']['to']!=str(end):
            return None
    except (KeyError,TypeError,ValueError):
        return None
    return payload


def news_payload_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Build public evidence only from an audited independent native window."""
    start, end = result['from_date'], result['to_exclusive']
    stats = {**result['stats'], 'from': start, 'to': end}
    trades = result['trades']
    if not result['calendar_complete'] or result['model'] != 4:
        raise ValueError('News coverage requires an audited Model 4 run.')
    if len(trades) != stats['trades'] or abs(sum(t['net_profit'] for t in trades) - stats['net_profit']) >= .05:
        raise ValueError('News trade ledger does not reconcile with the native report.')
    if any(not start <= t['open_time'][:10] < end for t in trades):
        raise ValueError('News trade falls outside the independent test window.')
    series = [dict(point) for point in result['series']]
    if not series or series[0]['time'][:10] > start:
        series.insert(0, {'time': start+'T00:00:00', 'balance': stats['initial_balance']})
    series.append({'time': end+'T00:00:00', 'balance': stats['final_balance']})
    notice = (
        f"Independent native MT5 run of current News Pulse v2.15, {start} to {end} (end exclusive), "
        f"starting from $10,000. Official BLS/Federal Reserve calendar: {result['calendar_expected']} releases; "
        f"{result['calendar_attempted']} attempted and {result['calendar_placed']} event straddles placed. "
        f"{len(result['events_without_closed_trades'])} scheduled events produced no closed trade. "
        f"MT5 reports {stats['history_quality']}; real-tick mode was requested, but older missing ticks may be generated. "
        "Original Exness XAUUSD/XAGUSD/BTCUSD evidence account; broker spread and recorded commission/swap included. "
        "Fixed 1 ms simulated delay, not a live-slippage guarantee. Settings are unchanged: 0.75% planned risk "
        "per pending stop / 1.50% combined; rounding, gaps and costs can exceed that budget. "
        "PF and win rate are calculated after recorded fees; drawdown is native relative equity drawdown. "
        "No multi-year slicing or window rebasing; portfolio adaptive scaling is calculated separately."
    )
    return {
        'label': result['label'], 'period': f'{start} to {end}', 'period_key': result['period_key'],
        'mode': 'standard', 'currency': 'USD', 'series': series, 'stats': stats,
        'available_from': start, 'available_to': end, 'cached_trade_count': len(trades),
        'trade_coverage_from': min((t['open_time'] for t in trades), default=None),
        'trade_coverage_to': max((t['close_time'] for t in trades), default=None),
        'source': 'precomputed-native-mt5-cache', 'notice': notice, 'history_quality': stats['history_quality'],
        'generated_at': datetime.now(timezone.utc).isoformat(), 'news_evidence_version': NEWS_EVIDENCE_VERSION,
        'independent_native_run': True, 'calendar_verified': True,
        **{key: result[key] for key in ('calendar_sha256', 'calendar_expected', 'calendar_attempted', 'calendar_placed',
                                      'events_without_closed_trades', 'source_report_sha256', 'source_report')},
        'data_model': 'MT5 Model 4; real-tick percentage disclosed', 'execution_delay_ms': 1,
        'equity_drawdown_basis': 'Native maximum relative equity drawdown; includes floating P/L',
    }
