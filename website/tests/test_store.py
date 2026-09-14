from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
import re
from urllib.parse import parse_qs, urlparse
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.catalog import (
    PACKAGE_ROOT,
    WHATSAPP_NUMBER,
    get_catalog,
    get_development_catalog,
    get_product,
    get_sellable_catalog,
    parse_installer_items,
)
from app.main import _display_catalog, app
from app.mt5_evidence_jobs import MAX_DAYS, _materialized_values, _native_trades, _same_setting, _set_values
from app.mt5_live import live_mt5, reconstruct_balance_history, reconstruct_trades
from app.trade_metrics import enrich_trades, outcome_streaks, pip_spec


client = TestClient(app)
STORE_ROOT = Path(__file__).resolve().parents[1]


def test_news_pulse_live_calendar_rejects_secondary_cpi_events() -> None:
    path = PACKAGE_ROOT / "AAA Final EAs/AAA Final News Pulse EA/AAA Final News Pulse EA.mq5"
    source = path.read_text(encoding="utf-8-sig")
    assert '#property version   "2.15"' in source
    assert 'if(event.importance!=CALENDAR_IMPORTANCE_HIGH) continue;' in source
    assert 'StringFind(normalized_name,"cpi")==0' in source
    assert 'StringFind(normalized_name,"core cpi")==0' in source
    assert 'StringFind(name,"cpi")>=0' not in source


def test_catalogue_is_synchronized_with_active_installer() -> None:
    installer_items = parse_installer_items()
    products = get_catalog()

    assert len(products) == len(installer_items)
    assert [product.installer_label for product in products] == [item["label"] for item in installer_items]
    assert len({product.slug for product in products}) == len(products)
    assert all("aaa" not in product.label.lower() for product in products)
    assert len(get_sellable_catalog()) == len(installer_items)
    assert len(get_development_catalog()) == 0


def test_every_active_entry_has_local_ea_and_set_files() -> None:
    missing: list[str] = []
    for product in get_catalog():
        for relative_path in (product.expert_source, product.set_source):
            if not relative_path or not (PACKAGE_ROOT / relative_path).is_file():
                missing.append(f"{product.label}: {relative_path or '<empty>'}")
    assert missing == []


def test_portfolio_risk_policy_has_only_news_exception() -> None:
    installer = (PACKAGE_ROOT / "_Auto Deploy" / "Install-BMTradingPortfolio.ps1").read_text(encoding="utf-8-sig")
    assert installer.count("LockRisk = $true") == 4
    assert installer.count("PercentRisk = $false") == 3

    risk_keys = {
        "InpRiskPercent",
        "InpMomentumRiskPercent",
        "InpContrarianRiskPercent",
        "InpAbsoluteRiskCapPercent",
        "RiskPercent",
    }
    for item in parse_installer_items():
        values = _materialized_values(_set_values(PACKAGE_ROOT / item["set_source"], safe=False))
        present = risk_keys & values.keys()
        assert present, item["label"]
        is_news = item["label"].startswith("News Pulse ") or item["label"] == "Gold News V9 Direction"
        expected = 0.75 if is_news else 1.0
        assert all(abs(float(values[key]) - expected) < 1e-9 for key in present), item["label"]

        if is_news:
            continue
        source = (PACKAGE_ROOT / item["expert_source"]).with_suffix(".mq5").read_text(
            encoding="utf-8-sig", errors="ignore"
        )
        lower_limits = re.findall(
            r"(?:InpRiskPercent|InpMomentumRiskPercent|InpContrarianRiskPercent)\s*>\s*([0-9.]+)",
            source,
        )
        assert all(float(value) >= 10.0 for value in lower_limits), item["label"]
        positive_floors = re.findall(
            r"(?:InpRiskPercent|InpMomentumRiskPercent|InpContrarianRiskPercent)\s*<\s*([0-9.]+)",
            source,
        )
        assert all(float(value) <= 0.0 for value in positive_floors), item["label"]


def test_purchase_links_use_store_whatsapp_number() -> None:
    for product in get_sellable_catalog():
        parsed = urlparse(product.buy_url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "wa.me"
        assert parsed.path == f"/{WHATSAPP_NUMBER}"
        assert product.label in parse_qs(parsed.query)["text"][0]


def test_public_pages_render() -> None:
    for route in ("/", "/store", "/eas", "/portfolio", "/live", "/pricing", "/risk"):
        response = client.get(route)
        assert response.status_code == 200
        assert "Calyx" in response.text


def test_calyx_dns_installer_defaults_are_safe_and_complete() -> None:
    batch = (STORE_ROOT / "configDns.bat").read_text(encoding="utf-8")
    installer = (STORE_ROOT / "tools" / "Configure-DnsHttps.ps1").read_text(encoding="utf-8")

    assert "example.duckdns.org" in batch
    assert "203.0.113.10" in batch
    assert "RunAs" in batch
    assert "example.duckdns.org" in installer
    assert "1.1.1.1" in installer and "8.8.8.8" in installer
    assert "reverse_proxy 127.0.0.1:8080" in installer
    assert "Get-FileHash -Algorithm SHA512" in installer
    assert "FINAL LINK:" in installer
    assert "Calyx Caddy HTTPS" in installer
    assert "Calyx EA Store" in installer


def test_calyx_logo_is_used_for_branding_and_favicon() -> None:
    logo = STORE_ROOT / "static" / "images" / "calyx-logo.jpg"
    response = client.get("/eas")

    assert logo.is_file() and logo.stat().st_size > 0
    assert response.status_code == 200
    assert 'rel="icon" type="image/jpeg"' in response.text
    assert response.text.count("images/calyx-logo.jpg") >= 5
    assert "Calyx trading systems logo" in response.text


def test_live_installer_uses_simple_account_confirmation() -> None:
    installer_path = PACKAGE_ROOT / "_Auto Deploy" / "Install-BMTradingPortfolio.ps1"
    installer = installer_path.read_text(encoding="utf-8")

    assert '$expected = "RUN $login"' in installer
    assert "$confirmation = $confirmation.Trim()" in installer
    assert "$confirmation -ine $expected" in installer
    assert "MODE: STANDARD - current default/selective configuration." in installer
    assert "MODE: BEST RECOMMENDED - each EA uses its evidence-selected Standard, Safe or Dynamic input preset." in installer
    assert "â€”" not in installer


def test_every_product_detail_page_renders() -> None:
    for product in get_sellable_catalog():
        response = client.get(f"/eas/{product.slug}")
        assert response.status_code == 200
        assert product.label in response.text
        assert product.buy_url.replace("&", "&amp;") in response.text


def test_recommended_safe_eas_default_to_safe_evidence_and_are_tagged() -> None:
    expected = {"lta-volume-profile", "ema3", "xau-weakness", "xau-squeeze-momentum-standard"}
    products = {product.slug: product for product in _display_catalog()}
    assert {slug for slug, product in products.items() if product.recommended_safe_mode} == expected

    catalogue = client.get("/eas")
    assert catalogue.status_code == 200
    assert catalogue.text.count("Running in Safe mode</span>") == len(expected)
    assert catalogue.text.count('class="product-card group"') == len(_display_catalog())
    assert catalogue.text.count('aria-label="View ') >= len(_display_catalog())

    for slug in expected:
        detail = client.get(f"/eas/{slug}")
        assert detail.status_code == 200
        assert "Running in Safe mode" in detail.text
        assert f'/api/evidence/{slug}/series?mode=compare' in detail.text
        assert "Both cached equity curves are shown together" in detail.text
        assert "This is the Best Recommended BAT default." in detail.text

    standard = client.get("/eas/lta-volume-profile", params={"mode": "standard"})
    assert standard.status_code == 200
    assert "/api/evidence/lta-volume-profile/series?mode=compare" in standard.text

    comparison = client.get("/api/evidence/lta-volume-profile/series", params={"mode": "compare", "period": "3y"})
    assert comparison.status_code == 200
    datasets = comparison.json()["datasets"]
    assert [dataset["label"] for dataset in datasets] == ["Standard", "Full Safe"]
    assert all(len(dataset["series"]) >= 2 for dataset in datasets)

    dynamic_detail = client.get("/eas/sell-nasdaq-15min", params={"mode": "dynamic", "period": "3y"})
    assert dynamic_detail.status_code == 200
    assert "Dynamic London" in dynamic_detail.text
    assert "ATR(14) × 2.5 stop and 3R target" in dynamic_detail.text
    assert 'data-selected-dataset="Dynamic London"' in dynamic_detail.text
    dynamic_comparison = client.get(
        "/api/evidence/sell-nasdaq-15min/series",
        params={"mode": "compare", "period": "3y"},
    )
    assert dynamic_comparison.status_code == 200
    dynamic_datasets = dynamic_comparison.json()["datasets"]
    assert [dataset["label"] for dataset in dynamic_datasets] == ["Standard", "London Safe", "Dynamic London"]
    assert all(len(dataset["series"]) >= 2 for dataset in dynamic_datasets)
    for period in ("6m", "1y", "3y", "5y"):
        dynamic = client.get(
            "/api/evidence/sell-nasdaq-15min/series",
            params={"mode": "dynamic", "period": period},
        )
        assert dynamic.status_code == 200
        assert dynamic.json()["mode"] == "dynamic"

    lta_source = (PACKAGE_ROOT / "LTA volume profile" / "EA" / "LTA_Concepts_EA.mq5").read_text(encoding="utf-8")
    ema3_source = (PACKAGE_ROOT / "AAA Final EAs" / "AAA Final EMA3 EA" / "AAA_Final_Strategy_Engine.mqh").read_text(encoding="utf-8")
    weakness_source = (PACKAGE_ROOT / "AAA Final EAs" / "AAA Final XAU Weakness EA" / "AAA_Final_Strategy_Engine.mqh").read_text(encoding="utf-8")
    assert 'comment = "Safe " + comment;' in lta_source
    assert '"Safe AAA EMA3"' in ema3_source
    assert '"Safe AAA XAU weakness breakout"' in weakness_source


def test_sellable_logic_is_specific_and_audit_labeled() -> None:
    products = get_sellable_catalog()
    runtime_only = {"Gold News V9 Direction"}
    assert all(len(product.logic) == 6 for product in products if product.label not in runtime_only)
    assert all(step.title and len(step.detail) >= 80 for product in products if product.label not in runtime_only for step in product.logic)

    compiled_only: set[str] = set()
    assert {product.label for product in products if product.logic_audit == "Input-audited binary"} == compiled_only
    assert {product.label for product in products if product.logic_audit == "Preset summary"} == runtime_only
    assert all(
        product.logic_audit == "Source-code verified"
        for product in products
        if product.label not in compiled_only | runtime_only
    )

    by_name = {product.label: product for product in products}
    assert {"DMC Current XAU", "DMC Fresh Reaction XAU", "DMC Fresh Reaction US100"} <= set(by_name)
    assert by_name["DMC Current XAU"].evidence.win_rate_pct == 40.8
    assert by_name["DMC Fresh Reaction XAU"].evidence.win_rate_pct == 60.0
    assert by_name["DMC Fresh Reaction US100"].evidence.win_rate_pct == 65.22
    assert "display" in by_name["ORB Volume Profile"].logic[2].title.lower()
    assert "all three profile entry filters are OFF" in by_name["ORB Volume Profile"].logic[2].detail
    assert "four times" in by_name["Nasdaq 5M Candle Momentum"].logic[2].detail
    assert "2.5 times" in by_name["Nasdaq 5M Candle Momentum"].logic[3].detail
    assert "15:55" in by_name["Nasdaq 5M Candle Momentum"].logic[5].detail
    assert "buy stop" in by_name["News Pulse XAU"].logic[2].detail
    assert "sell stop" in by_name["News Pulse XAU"].logic[2].detail
    assert "maximum base risk of 0.75%" in by_name["News Pulse XAU"].logic[3].detail
    assert "preceding twelve M15 bars" in by_name["BTC Top Down FVG Liquidity"].logic[1].detail
    assert "target is 4R" in by_name["ETH Top Down FVG Liquidity"].logic[5].detail
    assert "09:30-09:45" in by_name["Sell Nasdaq 15min"].logic[0].detail
    assert "three times" in by_name["Sell Nasdaq 15min"].logic[5].detail
    assert "2.5 times M15 ATR(14)" in by_name["Sell Nasdaq 15min"].logic[4].detail
    assert "08:00-09:00" in by_name["USDJPY London Open Momentum"].logic[0].detail
    assert "0.75R" in by_name["USDJPY London Open Momentum"].logic[5].detail


def test_recommended_exit_settings_are_synced_per_ea() -> None:
    products = get_sellable_catalog()
    assert len(products) == 32
    assert sum(product.exit_mode == "Dynamic 50/20" for product in products) == 8
    assert sum(product.exit_mode == "Dynamic 60/20 only" for product in products) == 1
    assert sum(product.exit_mode == "Current EA exits" for product in products) == 6
    assert sum(product.exit_mode == "Native 60-second exit" for product in products) == 3
    assert sum(product.exit_mode == "Fixed 5R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "Native 1.5R / BE at 0.5R" for product in products) == 1
    assert sum(product.exit_mode == "Native 1R / BE at 0.5R" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 4R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "Nominal 6R / timed flat" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 2R / BE at 1R" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 3R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 6R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 1R / no trailing" for product in products) == 0
    assert sum(product.exit_mode == "Fixed 2.5R / six-hour exit" for product in products) == 1
    assert sum(product.exit_mode == "Fixed 2.5R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "ATR 2.5 stop / fixed 3R / no trailing" for product in products) == 1
    assert sum(product.exit_mode == "Time exit / BE at 0.75R" for product in products) == 1
    assert sum(product.exit_mode == "3.5 ATR stop / 1.5R / ATR ratchet" for product in products) == 1
    assert sum(product.exit_mode == "3 ATR stop / 0.75R / ATR ratchet" for product in products) == 0
    safe_defaults = {product.label for product in products if product.recommended_safe_mode}
    assert safe_defaults == {"LTA Volume Profile", "EMA3", "XAU Weakness", "XAU Squeeze Momentum Standard"}
    standalone_orbs = {
        "XAU ORB New York M30",
        "XAU ORB London NY Overlap M30",
        "US100 ORB New York M30",
        "US100 H1 ORB 13UTC",
        "US100 Selective ORB V3",
        "Sell Nasdaq 15min",
    }
    assert all(
        product.deployment_session == "All day / native strategy window"
        for product in products
            if product.label not in {"BTC POC Fibonacci", "XAU Regime Switch", "US100 Month End Flow", "USDJPY London Open Momentum", "DMC Current XAU", "DMC Fresh Reaction XAU", "DMC Fresh Reaction US100"} and product.label not in standalone_orbs
    )
    london_open = next(product for product in products if product.label == "USDJPY London Open Momentum")
    assert london_open.deployment_session == "08:00-16:00 Europe/London / M15"
    assert london_open.evidence is not None
    assert london_open.evidence.win_rate_pct == 51.85
    ema3 = next(product for product in products if product.label == "EMA3")
    assert ema3.exit_mode == "Dynamic 60/20 only"
    assert "Native R-trailing is disabled" in ema3.logic[-1].detail
    weakness = next(product for product in products if product.label == "XAU Weakness")
    assert weakness.timeframe == "M30"
    assert weakness.exit_mode == "Dynamic 50/20"
    assert weakness.evidence is not None
    assert weakness.evidence.return_pct == 235.67
    assert weakness.evidence.profit_factor == 1.58
    assert weakness.evidence.win_rate_pct == 38.97
    overnight = next(product for product in products if product.label == "Nasdaq Overnight")
    assert not overnight.safe_filter_supported
    assert overnight.evidence is not None
    assert overnight.evidence.return_pct == 8.6671
    assert overnight.evidence.win_rate_pct == 63.89
    assert weakness.evidence.drawdown_pct == 13.25
    assert weakness.evidence.trades == 390
    assert weakness.safe_evidence is not None
    assert weakness.safe_evidence.return_pct == 134.07
    assert weakness.safe_evidence.profit_factor == 1.95
    poc_fib = next(product for product in products if product.label == "BTC POC Fibonacci")
    assert poc_fib.deployment_session == "New York broker-session window"
    assert poc_fib.safe_filter_supported is False
    assert poc_fib.evidence is not None
    assert poc_fib.evidence.status == "Demo watch"
    assert all("Applied BAT overlay" in product.logic[-1].detail for product in products if product.exit_mode == "Dynamic 50/20")
    assert all("Dynamic 50/20 overlay is disabled" in product.logic[-1].detail for product in products if product.exit_mode == "Current EA exits")
    assert all("Dynamic 50/20 overlay is disabled" in product.logic[-1].detail for product in products if product.exit_mode == "Native 60-second exit")
    news_products = [product for product in products if product.label.startswith("News Pulse ")]
    assert {product.label for product in news_products} == {"News Pulse XAU", "News Pulse XAG", "News Pulse BTC"}
    assert all(product.safe_filter_supported is False for product in news_products)
    assert all(product.evidence is not None for product in news_products)
    assert all(
        product.evidence.status == "Watch only — full calendar coverage"
        for product in news_products
    )
    assert all(product.evidence.trades > 30 for product in news_products)
    assert all("v2.15" in product.logic_audit_note for product in news_products)
    xau_ny = next(product for product in products if product.label == "XAU ORB New York M30")
    assert xau_ny.deployment_session == "09:30 New York / M30"
    assert xau_ny.exit_mode == "Native 1.5R / BE at 0.5R"
    assert xau_ny.safe_filter_supported is False
    assert xau_ny.evidence is not None
    assert round(xau_ny.evidence.return_pct, 4) == 2.4405
    assert xau_ny.evidence.profit_factor == 3.04
    assert xau_ny.evidence.trades == 11

    xau_overlap = next(product for product in products if product.label == "XAU ORB London NY Overlap M30")
    assert xau_overlap.deployment_session == "13:00-16:00 UTC overlap / M30"
    assert xau_overlap.exit_mode == "Native 1R / BE at 0.5R"
    assert xau_overlap.safe_filter_supported is False
    assert xau_overlap.evidence is not None
    assert round(xau_overlap.evidence.return_pct, 4) == 5.2103
    assert xau_overlap.evidence.profit_factor == 2.16
    assert xau_overlap.evidence.trades == 24

    us100_ny = next(product for product in products if product.label == "US100 ORB New York M30")
    assert us100_ny.deployment_session == "09:30 New York / M30"
    assert us100_ny.exit_mode == "Fixed 4R / no trailing"
    assert us100_ny.safe_filter_supported is False
    assert us100_ny.evidence is not None
    assert round(us100_ny.evidence.return_pct, 4) == 9.6588
    assert us100_ny.evidence.profit_factor == 1.68
    assert us100_ny.evidence.trades == 27

    us100_h1 = next(product for product in products if product.label == "US100 H1 ORB 13UTC")
    assert us100_h1.deployment_session == "13:00-20:00 UTC / M15"
    assert us100_h1.exit_mode == "Nominal 6R / timed flat"
    assert us100_h1.safe_filter_supported is False
    assert us100_h1.evidence is not None
    assert round(us100_h1.evidence.return_pct, 4) == 22.9981
    assert us100_h1.evidence.profit_factor == 1.72
    assert us100_h1.evidence.trades == 71

    selective_v3 = next(product for product in products if product.label == "US100 Selective ORB V3")
    assert selective_v3.deployment_session == "09:30-15:55 New York / M5"
    assert selective_v3.exit_mode == "Fixed 2R / BE at 1R"
    assert selective_v3.safe_filter_supported is False
    assert selective_v3.evidence is not None
    assert round(selective_v3.evidence.return_pct, 4) == 1.5376
    assert selective_v3.evidence.profit_factor == 1.53
    assert selective_v3.evidence.trades == 5
    sell_nasdaq = next(product for product in products if product.label == "Sell Nasdaq 15min")
    assert sell_nasdaq.timeframe == "M15"
    assert sell_nasdaq.deployment_session == "09:30-15:55 New York / M15"
    assert sell_nasdaq.exit_mode == "ATR 2.5 stop / fixed 3R / no trailing"
    assert sell_nasdaq.safe_filter_supported is True
    assert sell_nasdaq.safe_mode_label == "London Safe"
    assert sell_nasdaq.recommended_safe_mode is False
    assert sell_nasdaq.recommended_dynamic_mode is True
    assert sell_nasdaq.evidence is not None
    assert round(sell_nasdaq.evidence.return_pct, 4) == 90.1637
    assert sell_nasdaq.evidence.profit_factor == 1.42
    assert sell_nasdaq.evidence.win_rate_pct == 42.22
    assert sell_nasdaq.evidence.drawdown_pct == 11.57
    assert sell_nasdaq.evidence.trades == 225
    assert sell_nasdaq.safe_evidence is not None
    assert round(sell_nasdaq.safe_evidence.return_pct, 4) == 32.6238
    assert sell_nasdaq.safe_evidence.profit_factor == 1.33
    assert sell_nasdaq.safe_evidence.win_rate_pct == 45.62
    assert sell_nasdaq.safe_evidence.drawdown_pct == 6.07
    assert sell_nasdaq.dynamic_mode_supported is True
    assert sell_nasdaq.dynamic_mode_label == "Dynamic London"
    assert sell_nasdaq.dynamic_evidence is not None
    assert round(sell_nasdaq.dynamic_evidence.return_pct, 3) == 95.359
    assert sell_nasdaq.dynamic_evidence.profit_factor == 1.78
    assert sell_nasdaq.dynamic_evidence.win_rate_pct == 44.38
    assert sell_nasdaq.dynamic_evidence.drawdown_pct == 7.82
    sell_nasdaq_set = (PACKAGE_ROOT / sell_nasdaq.set_source).read_text(encoding="utf-8-sig")
    assert "InpRiskPercent=1.0" in sell_nasdaq_set
    assert "InpStopPips=450.0" in sell_nasdaq_set
    assert "InpTargetPips=1000.0" in sell_nasdaq_set
    safe_set = (PACKAGE_ROOT / str(sell_nasdaq.safe_set_source)).read_text(encoding="utf-8-sig")
    assert "InpRequirePriorLondonBearish=true" in safe_set
    assert "InpStopPips=600.0" in safe_set
    assert "InpTargetPips=1000.0" in safe_set
    dynamic_set = (PACKAGE_ROOT / str(sell_nasdaq.dynamic_set_source)).read_text(encoding="utf-8-sig")
    assert (PACKAGE_ROOT / str(sell_nasdaq.dynamic_expert_source)).is_file()
    assert "InpRequirePriorLondonBearish=true" in dynamic_set
    assert "InpStopMode=3" in dynamic_set
    assert "InpAtrPeriod=14" in dynamic_set
    assert "InpStopAtrMultiple=2.5" in dynamic_set
    assert "InpTargetMode=1" in dynamic_set
    assert "InpTargetRMultiple=3.0" in dynamic_set
    sell_detail = client.get("/eas/sell-nasdaq-15min")
    assert sell_detail.status_code == 200
    assert 'data-selected-dataset="Dynamic London"' in sell_detail.text
    assert "Running in Dynamic mode" in sell_detail.text
    assert "This is the Best Recommended BAT default." in sell_detail.text
    recommended_bat = PACKAGE_ROOT / "BEST RECOMMENDED 2026-09-01.bat"
    assert recommended_bat.is_file()
    bat_text = recommended_bat.read_text(encoding="utf-8")
    assert "-SafetyMode STANDARD" in bat_text
    assert "-UseRecommendedSelections" in bat_text
    adaptive_bat = PACKAGE_ROOT / "RECOMMENDED ADAPTIVE.bat"
    assert adaptive_bat.is_file()
    adaptive_bat_text = adaptive_bat.read_text(encoding="utf-8")
    assert "-UseRecommendedSelections" in adaptive_bat_text
    assert "-UseAdaptiveProfile" in adaptive_bat_text
    installer_text = (PACKAGE_ROOT / "_Auto Deploy" / "Install-BMTradingPortfolio.ps1").read_text(encoding="utf-8")
    assert "RecommendedDynamic = $true" in installer_text
    assert "$inputs['InpAdaptivePortfolioControls'] = 'true'" in installer_text
    adaptive_header = (PACKAGE_ROOT / "_Shared" / "CalyxAdaptivePortfolio.mqh").read_text(encoding="utf-8")
    assert "CALYX_DAILY_STOP_PERCENT=5.0" in adaptive_header
    assert "CALYX_SOFT_DRAWDOWN_PERCENT=4.0" in adaptive_header
    assert "CALYX_HARD_DRAWDOWN_PERCENT=7.0" in adaptive_header
    assert "CALYX_SOFT_LOSS_STREAK=3" in adaptive_header
    assert "CALYX_HARD_LOSS_STREAK=5" in adaptive_header

    btc_fvg = next(product for product in products if product.label == "BTC Top Down FVG Liquidity")
    assert btc_fvg.deployment_session == "All day / native strategy window"
    assert btc_fvg.safe_set_source is None
    assert btc_fvg.safe_mode_label == "Full Safe"
    assert btc_fvg.safe_evidence is not None

    rsi_vwap = next(product for product in products if product.label == "XAU RSI VWAP")
    assert rsi_vwap.timeframe == "H1"
    assert rsi_vwap.exit_mode == "Current EA exits"
    assert rsi_vwap.safe_filter_supported is False
    assert "0.5 times initial risk" in rsi_vwap.logic[-1].detail

    slow_trend = next(product for product in products if product.label == "XAU Slow Trend")
    assert slow_trend.timeframe == "H4"
    assert slow_trend.exit_mode == "Fixed 6R / no trailing"
    assert slow_trend.safe_filter_supported is False
    assert slow_trend.evidence is not None
    assert slow_trend.evidence.return_pct == 28.6246
    assert slow_trend.evidence.profit_factor == 2.17
    assert slow_trend.evidence.win_rate_pct == 31.43
    assert slow_trend.evidence.trades == 35
    slow_set = (PACKAGE_ROOT / slow_trend.set_source).read_text(encoding="utf-8-sig")
    assert "InpRiskPercent=1.0" in slow_set
    assert "InpMagic=969060311" in slow_set
    assert "InpTesterOnly=false" in slow_set

    regime_switch = next(product for product in products if product.label == "XAU Regime Switch")
    assert regime_switch.timeframe == "M5"
    assert regime_switch.deployment_session == "H4 trend all day / M5 VWAP 10:00-11:45 New York"
    assert regime_switch.exit_mode == "6R trend / 3R VWAP regime switch"
    assert regime_switch.safe_filter_supported is False
    assert regime_switch.evidence is not None
    assert regime_switch.evidence.status == "Validated demo-forward evidence"
    assert regime_switch.evidence.return_pct == 29.28
    assert regime_switch.evidence.profit_factor == 2.09
    assert regime_switch.evidence.win_rate_pct == 30.56
    assert regime_switch.evidence.drawdown_pct == 8.43
    assert regime_switch.evidence.trades == 36
    regime_set = (PACKAGE_ROOT / regime_switch.set_source).read_text(encoding="utf-8-sig")
    assert "InpRiskPercent=1.0" in regime_set
    assert "InpMagic=969070101" in regime_set
    assert "InpTesterOnly=false" in regime_set
    assert "InpDemoOnly=true" in regime_set

    month_end = next(product for product in products if product.label == "US100 Month End Flow")
    assert month_end.timeframe == "M30"
    assert month_end.deployment_session == "First three business days, after 10:30 New York / M30"
    assert month_end.exit_mode == "Fixed 2.5R / six-hour exit"
    assert month_end.safe_filter_supported is False
    assert month_end.evidence is not None
    assert round(month_end.evidence.return_pct, 4) == 5.5281
    assert month_end.evidence.profit_factor == 1.34
    assert month_end.evidence.win_rate_pct == 47.06
    assert month_end.evidence.drawdown_pct == 5.74
    assert month_end.evidence.trades == 34
    month_end_set = (PACKAGE_ROOT / month_end.set_source).read_text(encoding="utf-8-sig")
    assert "InpRiskPercent=1.0" in month_end_set
    assert "InpTesterOnly=false" in month_end_set
    assert "InpCalendarWindow=5" in month_end_set
    assert "InpRewardRisk=2.5" in month_end_set

    trend = next(product for product in products if product.label == "XAU Trend Progression")
    assert trend.timeframe == "H4"
    assert trend.exit_mode == "Current EA exits"
    assert trend.safe_filter_supported is False
    assert trend.evidence is not None
    assert trend.evidence.return_pct == 16.1025
    assert trend.evidence.profit_factor == 2.74
    assert trend.evidence.trades == 25
    assert "default and validated value is 1%" in trend.logic[4].detail

    elliott = next(product for product in products if product.label == "XAU Elliott Wave 1-2-3")
    assert elliott.timeframe == "H4"
    assert elliott.exit_mode == "Fixed 3R / no trailing"
    assert elliott.safe_filter_supported is False
    assert elliott.evidence is not None
    assert elliott.evidence.return_pct == 23.8231
    assert elliott.evidence.profit_factor == 3.15
    assert elliott.evidence.win_rate_pct == 54.17
    assert elliott.evidence.drawdown_pct == 3.77
    assert elliott.evidence.trades == 24
    assert "default and validated value is 1%" in elliott.logic[4].detail

    overnight = next(product for product in products if product.label == "Nasdaq Overnight")
    assert overnight.exit_mode == "Current EA exits"
    assert overnight.evidence is not None
    assert overnight.evidence.return_pct == 8.6671
    assert overnight.evidence.profit_factor == 1.84
    assert overnight.evidence.win_rate_pct == 63.89
    assert overnight.evidence.drawdown_pct == 2.36
    assert overnight.evidence.trades == 72
    assert "16:00-to-09:29" in overnight.evidence.source_note


def test_news_pulse_cards_details_and_series_use_the_same_verified_evidence() -> None:
    for slug in ("news-pulse-xau", "news-pulse-xag", "news-pulse-btc"):
        result_path = PACKAGE_ROOT / 'News Pulse Full Coverage 2026-09-12' / f'{slug}-3y-model4.json'
        result = json.loads(result_path.read_text())
        stats = result['stats']
        return_pct, profit_factor = stats['return_pct'], stats['profit_factor']
        win_rate, drawdown, trades = stats['win_rate_pct'], stats['max_drawdown_pct'], stats['trades']
        evidence_period = '2023-09-05 to 2026-09-05'
        product = get_product(slug)
        assert product is not None
        card = client.get("/eas", params={"q": product.label})
        detail = client.get(f"/eas/{slug}")
        series = client.get(f"/api/evidence/{slug}/series", params={"period": "3y"})
        assert card.status_code == detail.status_code == series.status_code == 200
        for page in (card.text, detail.text):
            assert f"{return_pct:+,.2f}%" in page
            assert f"{profit_factor:.2f}" in page
            assert f"{win_rate:.2f}%" in page
            assert f"{drawdown:.2f}%" in page
            assert evidence_period in page
        assert "Watch only" in card.text
        assert "Older pre-calendar-fix results are excluded" in detail.text
        assert "Historical pre-v2.13 calendar replay" not in detail.text
        payload = series.json()
        assert payload["period"] == evidence_period
        assert payload["period_key"] == "3y"
        assert payload["independent_native_run"] is True
        assert 'data-chart-period' in detail.text
        assert payload["stats"]["trades"] == trades
        assert len(payload["trades"]) == trades
        assert len(payload["series"]) >= 2
        assert all(trade["cache_slug"] == slug and trade['cache_period']=='3y' for trade in payload["trades"])
        assert payload['stats']['commission'] == stats['commission']
        assert payload['stats']['swap'] == stats['swap']
        assert payload['stats']['max_win_streak'] == stats['max_win_streak']
        assert payload['stats']['max_loss_streak'] == stats['max_loss_streak']


def test_period_matched_news_trade_chart_is_available(monkeypatch) -> None:
    series = client.get("/api/evidence/news-pulse-xau/series").json()
    trade = series["trades"][0]

    def fake_price_bars(symbol, timeframe, start, end):
        assert symbol == trade["symbol"]
        assert timeframe in {"M1", "M5", "M15"}
        assert start < end
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": [
                {"time": start.isoformat(), "open": 1, "high": 2, "low": 0.5, "close": 1.5, "tick_volume": 1},
                {"time": end.isoformat(), "open": 1.5, "high": 2.5, "low": 1, "close": 2, "tick_volume": 1},
            ],
        }

    monkeypatch.setattr(live_mt5, "price_bars", fake_price_bars)
    response = client.get(
        f"/api/evidence/news-pulse-xau/cached-trades/3y/{trade['number']}/chart"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trade"]["number"] == trade["number"]
    assert len(payload["bars"]) == 2
    assert response.headers["cache-control"].startswith("no-store")

    missing = client.get("/api/evidence/news-pulse-xau/cached-trades/3y/999999/chart")
    assert missing.status_code == 404

    evidence_js = (Path(__file__).resolve().parents[1] / "static" / "evidence.js").read_text(encoding="utf-8")
    assert "data-trade-chart-verified-news" in evidence_js
    assert "[data-trade-chart-job],[data-trade-chart-cache],[data-trade-chart-verified-news]" in evidence_js
    assert "/verified-trades/" in evidence_js


def test_nasdaq_overnight_uses_fresh_native_curve_and_active_inputs() -> None:
    product = next(product for product in get_sellable_catalog() if product.label == "Nasdaq Overnight")
    response = client.get(f"/api/evidence/{product.slug}/series")
    assert response.status_code == 200
    payload = response.json()
    assert payload["period_key"] == "3y"
    assert payload["available_from"] == "2023-09-05"
    assert payload["available_to"] == "2026-09-05"
    assert payload["source"] == "precomputed-native-mt5-cache"
    assert payload["stats"]["trades"] == payload["cached_trade_count"]

    active_set = (PACKAGE_ROOT / product.set_source).read_text(encoding="utf-8-sig")
    for setting in (
        "InpRequireNegativeDay=true",
        "InpEntryHour=16",
        "InpEntryMinute=0",
        "InpExitHour=9",
        "InpExitMinute=29",
        "InpEmergencyStopPercent=2",
        "InpRewardRisk=0",
        "InpUseDynamicTrailingSL=false",
    ):
        assert setting in active_set


def test_removed_dmc_detail_is_not_available() -> None:
    response = client.get("/eas/dmc-xau")
    assert response.status_code == 404


def test_api_and_evidence_chart() -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    expected = len(get_catalog())
    assert health.json()["active_entries"] == expected
    assert health.json()["available_entries"] == expected
    assert health.json()["development_entries"] == 0

    payload = client.get("/api/eas")
    assert payload.status_code == 200
    assert len(payload.json()) == expected
    assert all(not item["development"] for item in payload.json())

    product = next(item for item in get_catalog() if item.evidence and item.evidence.chart_path)
    chart = client.get(f"/evidence/{product.slug}.png")
    assert chart.status_code == 200
    assert chart.headers["content-type"] == "image/png"
    assert chart.headers["cache-control"].startswith("no-store")

    for item in get_sellable_catalog():
        series = client.get(f"/api/evidence/{item.slug}/series")
        if item.evidence is None:
            assert series.status_code == 404, item.label
            continue
        assert series.status_code == 200, item.label
        payload = series.json()
        assert payload["label"] == item.label
        assert len(payload["series"]) >= 2
        assert all(set(point) >= {"time", "balance"} for point in payload["series"])
        assert series.headers["cache-control"].startswith("public")
        assert series.headers["x-evidence-cache"] == "HIT"

    detail = client.get(f"/eas/{product.slug}")
    assert f'/api/evidence/{product.slug}/series' in detail.text
    assert f'/evidence/{product.slug}.png' not in detail.text
    assert "/static/evidence.js" in detail.text


def test_portfolio_page_shows_fixed_cached_periods() -> None:
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert "Precomputed recommended-portfolio evidence" in response.text
    assert "32 EAs with the approved adaptive risk controls" in response.text
    assert "CACHED NATIVE MT5 DATA" in response.text
    assert "Dynamic 50/20" in response.text
    assert "Recommended Adaptive is the active website profile" in response.text
    assert "+2,288.14%" in response.text
    assert "9.54%" in response.text
    assert "All four news EAs are exempt" in response.text
    assert "Gold News V9 remains evidence pending" in response.text
    assert "Current · 5Y return" not in response.text
    assert "Current → adaptive PF" not in response.text
    assert "Approved removals" in response.text
    assert "DMC Current XAU was reviewed separately and remains active" in response.text
    for value in ("6m", "1y", "3y", "5y"):
        assert f'value="{value}"' in response.text
    assert 'value="10y"' not in response.text
    assert 'data-chart-from' not in response.text
    assert 'data-chart-to' not in response.text
    chart = client.get("/portfolio/equity.png?period=1y")
    assert chart.status_code == 404
    series = client.get("/api/portfolio/equity-series")
    assert series.status_code == 200
    assert len(series.json()["series"]) >= 2
    assert series.json()["included_ea_count"] == 32
    assert series.json()["tested_ea_count"] == 31
    assert series.json()["mode"] == "recommended-adaptive"
    assert series.json()["stats"]["return_pct"] == 2288.14
    assert series.json()["stats"]["profit_factor"] == 2.09
    assert series.json()["stats"]["max_drawdown_pct"] == 8.57
    assert series.headers["x-evidence-cache"] == "HIT"
    assert "/api/portfolio/equity-series" in response.text
    assert "/portfolio/equity.png" not in response.text
    assert "/static/evidence.js" in response.text


def test_every_public_ea_uses_supported_evidence_period() -> None:
    products = get_sellable_catalog()
    runtime_only = [product for product in products if product.evidence is None]
    assert [product.label for product in runtime_only] == ["Gold News V9 Direction"]
    for product in (product for product in products if product.evidence is not None):
        start_text, end_text = product.evidence.period.split(" to ")
        duration = (date.fromisoformat(end_text) - date.fromisoformat(start_text)).days
        assert 364 <= duration <= 3660
    assert all(product.one_year_evidence == product.evidence for product in products if product.evidence is not None)
    for route in ("/", "/eas", "/portfolio", "/risk", *(f"/eas/{product.slug}" for product in products)):
        response = client.get(route)
        assert "five-year" not in response.text.lower()
        assert "2021-08-11" not in response.text


def test_missing_product_returns_branded_404() -> None:
    response = client.get("/eas/not-a-real-ea")
    assert response.status_code == 404
    assert "This setup is not in the active catalogue" in response.text


def test_home_ranks_all_available_eas_by_default_three_year_return() -> None:
    products = _display_catalog()
    returns = [product.one_year_return_pct for product in products]
    assert sum(value is None for value in returns) == 1

    ranked = sorted(products, key=lambda product: product.one_year_return_pct or float("-inf"), reverse=True)
    response = client.get("/store")
    assert response.status_code == 200
    assert response.text.count("Three-year return") == len(products)
    positions = [response.text.index(f">{product.label}</h3>") for product in ranked]
    assert positions == sorted(positions)
    assert "Auction Market research engine" not in response.text
    assert "NOT FOR SALE" not in response.text
    assert "Auction Market XAU" not in response.text


def test_ea_catalogue_supports_metric_sorting_and_symbol_filtering() -> None:
    page = client.get("/eas")
    assert page.status_code == 200
    assert 'id="sort-filter"' in page.text
    assert "Highest profit factor" in page.text
    assert "Highest win rate" in page.text
    assert "Lowest drawdown" in page.text
    assert "Highest return" in page.text
    assert 'id="asset-filter"' in page.text
    assert "XAUUSD (18)" in page.text
    assert 'data-pf=' in page.text
    assert 'data-win=' in page.text
    assert 'data-dd=' in page.text

    xag = client.get("/eas", params={"symbol": "xagusd"})
    assert xag.status_code == 200
    assert "News Pulse XAG" in xag.text
    assert 'id="visible-count" class="text-white">1<' in xag.text

    pf_sorted = client.get("/eas", params={"sort": "pf-desc"})
    products = sorted(
        _display_catalog(),
        key=lambda product: product.evidence.profit_factor if product.evidence else float("-inf"),
        reverse=True,
    )
    positions = [pf_sorted.text.index(f">{product.label}</h3>") for product in products]
    assert positions == sorted(positions)


def test_development_builds_are_not_public_products() -> None:
    assert get_development_catalog() == []


def test_live_dashboard_and_read_only_api_render() -> None:
    for route in ("/", "/live"):
        page = client.get(route)
        assert page.status_code == 200
        assert "The account, as it trades" in page.text
        assert "Every reconstructed closed trade" in page.text
    store = client.get("/store")
    assert "Ranked by three-year return" in store.text
    api = client.get("/api/live/portfolio")
    assert api.status_code == 200
    assert api.headers["cache-control"].startswith("no-store")
    assert set(api.json()) >= {"connected", "account", "positions", "orders", "trades", "ea_summary", "equity_series"}
    assert "Balance history since first reaching $10,000" in client.get("/").text
    live_script = client.get("/static/live.js")
    assert live_script.status_code == 200
    assert "2026-08-01T00:00:00Z" in live_script.text
    assert "curveSinceFirstTenK" in live_script.text


def test_fixed_cached_evidence_periods_and_pricing_bundle() -> None:
    product = next(item for item in get_sellable_catalog() if item.evidence and item.evidence.trades > 20)
    response = client.get(
        f"/api/evidence/{product.slug}/series",
        params={"period": "6m"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["period_key"] == "6m"
    assert set(payload["stats"]) >= {"return_pct", "profit_factor", "win_rate_pct", "max_drawdown_pct", "trades", "sharpe_ratio", "recovery_factor", "max_win_streak", "max_loss_streak"}
    assert all(set(trade) >= {"source", "commission", "swap", "gross_profit"} for trade in payload["trades"])

    portfolio = client.get(
        "/api/portfolio/equity-series",
        params={"mode": "standard", "period": "6m"},
    )
    assert portfolio.status_code == 200
    assert portfolio.json()["included_ea_count"] == len(get_sellable_catalog())
    assert portfolio.json()["tested_ea_count"] == len(get_sellable_catalog()) - 1
    assert portfolio.json()["mode"] == "recommended-adaptive"
    assert set(portfolio.json()["stats"]) >= {"commission", "swap", "total_costs", "gross_profit_before_costs"}
    assert "datasets" not in portfolio.json()
    assert all("current" not in row for row in portfolio.json()["included_eas"])
    assert all(set(row) >= {"recommended", "skipped_trades"} for row in portfolio.json()["included_eas"])
    assert set(portfolio.json()["analytics"]) >= {"trade_stats", "drawdown_series", "assets", "monthly_pnl", "directions"}

    detail = client.get(f"/eas/{product.slug}")
    assert 'data-chart-period' in detail.text
    assert 'data-backtest-trades-body' in detail.text
    assert detail.text.index('How the installed version actually works.') < detail.text.index('data-trade-history-section')
    assert 'data-trade-pagination' in detail.text
    assert 'data-trade-page-size' in detail.text
    assert 'data-trade-page-prev' in detail.text
    assert 'data-trade-page-next' in detail.text
    assert '<option value="10" selected>10</option>' in detail.text
    assert 'Show cached period' in detail.text
    assert 'data-trade-chart-panel' in detail.text
    assert 'Price chart' in detail.text
    assert 'Max win streak' in detail.text
    assert 'Max losing streak' in detail.text
    assert 'changing periods does not launch a tester job' in detail.text
    assert all(label in detail.text for label in ("Last 6 months", "Last 1 year", "Last 3 years", "Last 5 years"))
    assert 'value="3y" selected' in detail.text
    portfolio_page = client.get("/portfolio")
    assert all(label in portfolio_page.text for label in ("Last 6 months", "Last 1 year", "Last 3 years", "Last 5 years"))
    assert 'value="3y" selected' in portfolio_page.text
    assert MAX_DAYS == 366 * 5
    pricing = client.get("/pricing")
    assert "Choose 3 + bonus EA" in pricing.text
    assert "$499" in pricing.text


def test_cached_trades_include_price_move_and_estimated_r_without_mt5_rerun() -> None:
    rows = enrich_trades(
        [
            {
                "symbol": "XAUUSD",
                "side": "Long",
                "open_time": "2026-01-01T10:00:00",
                "close_time": "2026-01-01T11:00:00",
                "open_price": 2000.0,
                "close_price": 2001.0,
                "net_profit": 100.0,
            }
        ],
        "xau-test",
    )
    assert pip_spec("XAUUSD") == (0.1, "pips")
    assert pip_spec("BTCUSD") == (1.0, "points")
    assert rows[0]["price_move"] == 10.0
    assert rows[0]["estimated_r"] == 1.0
    assert rows[0]["r_is_estimate"] is True

    product = next(item for item in get_sellable_catalog() if item.label == "LTA Volume Profile")
    payload = client.get(f"/api/evidence/{product.slug}/series", params={"period": "3y"}).json()
    assert payload["trades"]
    assert all(set(trade) >= {"price_move", "price_move_unit", "estimated_r", "configured_risk_pct"} for trade in payload["trades"])

    evidence_js = (Path(__file__).resolve().parents[1] / "static" / "evidence.js").read_text(encoding="utf-8")
    assert "addEquityHover" in evidence_js
    assert "Hover or tap the equity curve" in evidence_js


def test_outcome_streaks_are_ordered_and_break_even_is_neutral() -> None:
    trades = [
        {"number": 4, "close_time": "2026-01-04T00:00:00", "net_profit": -1},
        {"number": 2, "close_time": "2026-01-02T00:00:00", "net_profit": 2},
        {"number": 1, "close_time": "2026-01-01T00:00:00", "net_profit": 1},
        {"number": 3, "close_time": "2026-01-03T00:00:00", "net_profit": 0},
        {"number": 5, "close_time": "2026-01-05T00:00:00", "net_profit": -2},
    ]
    assert outcome_streaks(trades) == {"max_win_streak": 2, "max_loss_streak": 2}


def test_all_recommended_eas_and_portfolio_have_every_fixed_cache() -> None:
    products = get_sellable_catalog()
    assert len(products) == 32
    periods = ("6m", "1y", "3y", "5y")
    for period in periods:
        portfolio = client.get("/api/portfolio/equity-series", params={"period": period})
        assert portfolio.status_code == 200, period
        assert portfolio.json()["included_ea_count"] == len(products)
        assert portfolio.json()["stats"]["trades"] == portfolio.json()["cached_trade_count"]
    for product in (product for product in products if product.evidence is not None):
        for period in periods:
            response = client.get(f"/api/evidence/{product.slug}/series", params={"period": period})
            assert response.status_code == 200, f"{product.label} {period}"
            payload = response.json()
            assert payload["period_key"] == period
            assert payload["stats"]["trades"] == payload["cached_trade_count"]

    manifest = client.get("/api/evidence-cache/manifest")
    assert manifest.status_code == 200
    assert manifest.json()["recommended_ea_count"] == len(products)
    assert manifest.json()["failures"] == []


def test_balance_history_is_reconstructed_from_august_cash_flows() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 5, tzinfo=timezone.utc)
    deals = [
        SimpleNamespace(time_msc=datetime(2026, 8, 2, tzinfo=timezone.utc).timestamp() * 1000, profit=100, commission=-2, swap=0, fee=0),
        SimpleNamespace(time_msc=datetime(2026, 8, 3, tzinfo=timezone.utc).timestamp() * 1000, profit=-50, commission=-1, swap=0, fee=0),
    ]
    series = reconstruct_balance_history(deals, 1047, start, end)
    assert series[0]["balance"] == 1000
    assert series[-1]["balance"] == 1047
    assert all(point["equity"] is None for point in series)


def test_mt5_deals_are_reconstructed_and_attributed() -> None:
    entry = SimpleNamespace(
        ticket=1, position_id=77, time_msc=1_000_000, time=1000, type=0, entry=0,
        magic=123, volume=0.2, price=100.0, profit=0.0, commission=-1.0,
        swap=0.0, fee=0.0, symbol="XAUUSD", comment="entry signal",
    )
    exit_deal = SimpleNamespace(
        ticket=2, position_id=77, time_msc=1_060_000, time=1060, type=1, entry=1,
        magic=123, volume=0.2, price=110.0, profit=200.0, commission=-1.0,
        swap=-0.5, fee=0.0, symbol="XAUUSD", comment="[tp]",
    )
    trades = reconstruct_trades([entry, exit_deal], {123: "Test EA"})
    assert len(trades) == 1
    assert trades[0]["ea"] == "Test EA"
    assert trades[0]["side"] == "Buy"
    assert trades[0]["net_profit"] == 197.5
    assert trades[0]["duration_seconds"] == 60


def test_custom_mt5_refresh_api_is_retired() -> None:
    product = next(item for item in get_sellable_catalog() if item.evidence)
    started = client.post(
        f"/api/evidence/{product.slug}/refresh",
    )
    assert started.status_code == 410
    assert "fixed 6m, 1y, 3y or 5y" in started.json()["detail"]


def test_native_deal_parser_includes_chart_coordinates() -> None:
    report = (
        PACKAGE_ROOT / "RSI VWAP Research 2026-09-02" / "Backtest Reports"
        / "Locked Last Year Every Tick 2025-2026" / "btcusd--h4--optimized--locked.htm"
    )
    if not report.is_file():
        return
    trades = _native_trades(report, "BTC Test")
    assert trades
    assert set(trades[0]) >= {"symbol", "side", "open_time", "close_time", "open_price", "close_price"}
    assert round(sum(row["net_profit"] for row in trades), 2) == -654.60


def test_mt5_set_materialization_preserves_selected_lta_inputs_and_windows_newlines() -> None:
    source = (
        PACKAGE_ROOT / "Selected Portfolio Settings 2026-09-01"
        / "01 LTA Volume Profile - CURRENT - ALL DAY.set"
    )
    materialized = _set_values(source, safe=False)
    values = _materialized_values(materialized)

    assert "\r" not in materialized
    assert materialized.endswith("\n")
    assert values["InpUseSwingProfile"] == "false"
    assert values["InpUsePOCFirstRetestConfirmation"] == "false"
    assert values["InpUseEM2InternalSwing"] == "false"
    assert values["InpUseEM3CME"] == "false"
    assert values["InpUseDynamicTrailingSL"] == "false"


def test_btc_defaults_all_day_and_safe_is_a_per_ea_markov_input() -> None:
    product = next(item for item in get_sellable_catalog() if item.label == "BTC Top Down FVG Liquidity")
    source = PACKAGE_ROOT / product.set_source
    materialized = _set_values(source, safe=True)
    values = _materialized_values(materialized)

    assert values["InpResearchSession"] == "0"
    assert values["InpRewardRisk"] == "2"
    assert values["InpBreakEvenAtR"] == "0"
    assert values["InpUseDynamicTrailingSL"] == "false"
    assert values["InpRiskPercent"] == "1.00"
    assert values["InpUseMarkovRegimeFilter"] == "true"

    response = client.get(f"/api/evidence/{product.slug}/series", params={"mode": "compare", "period": "1y"})
    assert response.status_code == 200
    datasets = response.json()["datasets"]
    assert datasets[1]["label"] == "Full Safe"


def test_eth_approved_four_r_dynamic_configuration_is_shared_by_standard_and_safe() -> None:
    product = next(item for item in get_sellable_catalog() if item.label == "ETH Top Down FVG Liquidity")
    source = PACKAGE_ROOT / product.set_source
    standard = _materialized_values(_set_values(source, safe=False))
    safe = _materialized_values(_set_values(source, safe=True))

    assert standard["InpRewardRisk"] == "4"
    assert standard["InpUseDynamicTrailingSL"] == "true"
    assert standard["InpDynamicTriggerFraction"] == "0.50"
    assert standard["InpDynamicLockFraction"] == "0.20"
    assert standard["InpResearchSession"] == "0"
    assert standard["InpRiskPercent"] == "1.00"
    assert safe["InpRewardRisk"] == "4"
    assert safe["InpUseDynamicTrailingSL"] == "true"
    assert safe["InpUseMarkovRegimeFilter"] == "true"


def test_mt5_setting_comparison_handles_numeric_formatting_but_not_changed_inputs() -> None:
    assert _same_setting("0.50", "0.5")
    assert _same_setting("false", "FALSE")
    assert not _same_setting("false", "true")
    assert not _same_setting("0.50", "0.65")


def test_xau_squeeze_modes_are_saved_isolated_and_evidence_backed() -> None:
    products = {product.label: product for product in get_sellable_catalog()}
    standard = products["XAU Squeeze Momentum Standard"]

    standard_values = _materialized_values(_set_values(PACKAGE_ROOT / standard.set_source, safe=False))
    safe_values = _materialized_values((PACKAGE_ROOT / str(standard.safe_set_source)).read_text(encoding="utf-8-sig"))

    assert standard.recommended_safe_mode is True
    assert standard.evidence is not None and round(standard.evidence.return_pct, 2) == 22.75
    assert standard.safe_evidence is not None and round(standard.safe_evidence.profit_factor, 2) == 3.89
    assert standard_values["InpRiskPercent"] == safe_values["InpRiskPercent"] == "1.0"
    assert standard_values["InpStopATR"] == "3.5" and standard_values["InpTargetR"] == "1.5"
    assert safe_values["InpUseMarkovRegimeFilter"] == "true"
    assert safe_values["InpTradeComment"].startswith("Safe ")
