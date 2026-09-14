from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import news_evidence
from app.catalog import PACKAGE_ROOT, get_product
from app.main import app
from app.mt5_evidence_jobs import _native_trades
from tools.precompute_evidence_cache import independent_news_result

WINDOWS={'6m':'2026-03-05','1y':'2025-09-05','3y':'2023-09-05','5y':'2021-09-05'}
ROOT=PACKAGE_ROOT/'News Pulse Full Coverage 2026-09-12'
client=TestClient(app)


def test_native_deals_pair_hedged_news_by_direction(tmp_path):
    rows=[
        ['2026.03.06 13:30:01','1','XAUUSD','sell','in','1','100','1','-3','0','0','9997','NP|1|NFP|S'],
        ['2026.03.06 13:30:02','2','XAUUSD','buy','in','.5','101','2','-1.5','0','0','9995.5','NP|1|NFP|B'],
        ['2026.03.06 13:30:03','3','XAUUSD','sell','out','.5','105','3','-1.5','0','200','10194','sl 105'],
        ['2026.03.06 13:30:04','4','XAUUSD','buy','out','1','102','4','-3','0','-200','9991','sl 102'],
    ]
    report=tmp_path/'hedged.htm'
    report.write_text('<html>Initial Deposit<b>Deals</b><table>'+''.join(
        '<tr>'+''.join(f'<td>{value}</td>' for value in row)+'</tr>' for row in rows
    )+'</table></html>')
    trades=_native_trades(report,'News test')
    assert len(trades)==2
    assert [(t['side'],t['open_price'],t['net_profit']) for t in trades]==[('Long',101,197),('Short',100,-206)]
    assert trades[0]['entry_comment'].endswith('|B')
    assert trades[1]['entry_comment'].endswith('|S')
    assert sum(t['commission'] for t in trades)==-9


def test_old_or_mismatched_news_summary_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(news_evidence,'CACHE_ROOT',tmp_path)
    path=tmp_path/'products'/'news-pulse-xau'/'standard'/'5y.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'period_key':'5y','stats':{'trades':9}}))
    assert news_evidence.load_news_summary('news-pulse-xau','5y') is None
    path.write_text(json.dumps({'period_key':'3y','news_evidence_version':1,'calendar_verified':True,'independent_native_run':True}))
    assert news_evidence.load_news_summary('news-pulse-xau','5y') is None


@pytest.mark.parametrize('slug',sorted(news_evidence.NEWS_SLUGS))
def test_every_news_period_has_independent_complete_evidence(slug):
    calendar=json.loads((ROOT/'OFFICIAL CALENDAR.json').read_text())
    hashes=[]
    for period,start in WINDOWS.items():
        result,report=independent_news_result(get_product(slug),'standard',period,date.fromisoformat(start),date(2026,9,5))
        response=client.get(f'/api/evidence/{slug}/series',params={'period':period})
        assert response.status_code==200
        payload=response.json()
        assert payload['available_from']==start and payload['available_to']=='2026-09-05'
        assert payload['calendar_sha256']==calendar['sha256']
        assert payload['calendar_expected']==sum(start<=e['release_utc'][:10]<'2026-09-05' for e in calendar['events'])
        assert payload['stats']['initial_balance']==10000
        assert payload['stats']['trades']==len(payload['trades'])==len(result['trades'])
        for field in ('net_profit','commission','swap'):
            assert sum(t[field] for t in payload['trades'])==pytest.approx(payload['stats'][field],abs=.05)
        assert all(t['cache_period']==period and start<=t['open_time'][:10]<'2026-09-05' for t in payload['trades'])
        assert all('window_rebase_multiplier' not in t for t in payload['trades'])
        for trade in payload['trades']:
            direction=1 if trade['side']=='Long' else -1
            assert (trade['close_price']-trade['open_price'])*direction*trade['gross_profit']>=-.01
        hashes.append(payload['source_report_sha256'])
        detail=client.get(f'/eas/{slug}',params={'period':period})
        assert f"{payload['stats']['return_pct']:+,.2f}%" in detail.text
        assert payload['history_quality'] in detail.text
        assert 'data-chart-period' in detail.text
    assert len(set(hashes))==4, 'A source report was reused across different windows'


def test_news_reparse_refuses_wrong_window():
    with pytest.raises(RuntimeError,match='source dates differ'):
        independent_news_result(get_product('news-pulse-btc'),'standard','1y',date(2023,9,5),date(2026,9,5))


def test_news_calendar_does_not_invent_monthly_release_dates():
    calendar=json.loads((ROOT/'OFFICIAL CALENDAR.json').read_text())
    events=calendar['events']
    assert len(events)==158 and len({e['epoch'] for e in events})==158
    assert events==sorted(events,key=lambda e:e['epoch'])
    assert all(e['source'].startswith(('https://www.bls.gov/','https://www.federalreserve.gov/')) for e in events)
