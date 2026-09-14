from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic import BaseModel, ConfigDict

from .news_evidence import load_news_summary


STORE_ROOT = Path(__file__).resolve().parents[1]
EAS_ROOT = STORE_ROOT.parent
PACKAGE_ROOT = EAS_ROOT / "BM Trading Robust Sets 2026-08-04"
BOOKMAPER_ROOT = EAS_ROOT / "BookMaper"
FILTERED_AUDIT_ROOT = PACKAGE_ROOT / "Selected Portfolio Audit 2026-08-28"
SELECTED_PORTFOLIO_ROOT = PACKAGE_ROOT / "Dynamic Trailing Session Research 2026-09-01"
RSI_VWAP_ROOT = PACKAGE_ROOT / "RSI VWAP Research 2026-09-02"
TREND_PROGRESSION_ROOT = PACKAGE_ROOT / "Trend Progression Research 2026-09-02"
ELLIOTT_WAVE_ROOT = PACKAGE_ROOT / "Elliott Wave Research 2026-09-05"
SLOW_TREND_ROOT = PACKAGE_ROOT / "Slow Multi Asset Trend Research 2026-09-06"
SESSION_VWAP_ROOT = PACKAGE_ROOT / "Session VWAP Snapback Research 2026-09-06"
MONTH_END_FLOW_ROOT = PACKAGE_ROOT / "Month End Institutional Flow Research 2026-09-06"
REGIME_SWITCH_ROOT = PACKAGE_ROOT / "Regime Switch Overlay Research 2026-09-06"
POC_FIB_ROOT = PACKAGE_ROOT / "POC Fibonacci Volume Profile Research 2026-09-04"
OVERNIGHT_OPTIMIZATION_ROOT = PACKAGE_ROOT / "US100 Overnight Optimization 2026-09-04"
ORB_SESSION_AUDIT_ROOT = PACKAGE_ROOT / "ORB Session Matrix Research 2026-09-05"
ORB_H1_AUDIT_ROOT = PACKAGE_ROOT / "ORB H1 Range Research 2026-09-05"
SELECTIVE_ORB_ROOT = PACKAGE_ROOT / "US100 Selective ORB Research 2026-08-21"
NEWS_PULSE_ROOT = PACKAGE_ROOT / "News Pulse Direction Research 2026-09-05"
NEWS_PULSE_CALENDAR_ROOT = PACKAGE_ROOT / "News Pulse FXMacroData Audit 2026-09-10"
NEWS_PULSE_CRYPTO_ROOT = PACKAGE_ROOT / "News Pulse Crypto Extension 2026-09-11"
NEWS_PULSE_BTC_3Y_ROOT = PACKAGE_ROOT / "News Pulse BTC Official 3Y Research 2026-09-11"
ACTIVE_PIPELINE_ROOT = PACKAGE_ROOT / "Active Portfolio Full Pipeline 2026-09-05"
SELL_NASDAQ_15M_ROOT = PACKAGE_ROOT / "Sell Nasdaq 15min Research 2026-09-08"
LONDON_OPEN_FX_MOMENTUM_ROOT = PACKAGE_ROOT / "London Open FX Momentum Research 2026-09-08"
DMC_FRESH_REACTION_ROOT = PACKAGE_ROOT / "DMC Fresh Reaction Research 2026-09-09"
XAU_SQUEEZE_MOMENTUM_ROOT = PACKAGE_ROOT / "XAU Squeeze Momentum Research 2026-09-10"
INSTALLER_PATH = PACKAGE_ROOT / "_Auto Deploy" / "Install-BMTradingPortfolio.ps1"
PUBLIC_CATALOG_MANIFEST = STORE_ROOT / "public_catalog_manifest.json"
WHATSAPP_NUMBER = os.getenv("CALYX_WHATSAPP_NUMBER", "").strip()
CONTACT_URL = os.getenv("CALYX_CONTACT_URL", "https://calyx.duckdns.org/").strip()

TIMEFRAMES = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 60: "H1", 240: "H4", 1440: "D1"}

ORB_SESSION_PRODUCTS: dict[str, tuple[str, str]] = {
    "XAU ORB New York M30": ("xauusd", "new-york"),
    "XAU ORB London NY Overlap M30": ("xauusd", "overlap"),
    "US100 ORB New York M30": ("ustec", "new-york"),
}

STANDALONE_ORB_LABELS = frozenset(
    {
        *ORB_SESSION_PRODUCTS,
        "US100 H1 ORB 13UTC",
        "US100 Selective ORB V3",
        "Sell Nasdaq 15min",
    }
)


class Evidence(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str
    period: str
    return_pct: float
    profit_factor: float
    drawdown_pct: float
    win_rate_pct: float
    trades: int
    sharpe_ratio: float | None = None
    recovery_factor: float | None = None
    max_win_streak: int | None = None
    max_loss_streak: int | None = None
    history_quality: str = "Not stated"
    source_note: str
    chart_path: Path | None = None
    status: str = "Research"
    caution: str | None = None


class LogicStep(BaseModel):
    title: str
    detail: str


class Product(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str
    installer_label: str
    slug: str
    canonical: str
    timeframe: str
    period_minutes: int
    expert: str
    expert_source: str
    set_source: str
    safe_set_source: str | None = None
    dynamic_expert_source: str | None = None
    dynamic_set_source: str | None = None
    optional_symbol: bool = False
    category: str
    asset_group: str
    strategy: str
    tagline: str
    description: str
    session: str
    exit_mode: str = "Current EA exits"
    deployment_session: str = "All day"
    risk_note: str
    logic_audit: str
    logic_audit_note: str
    logic: list[LogicStep]
    limitations: list[str]
    price: int
    accent: str
    featured: bool = False
    development: bool = False
    safe_filter_supported: bool = False
    recommended_safe_mode: bool = False
    safe_mode_label: str = "Full Safe"
    safe_mode_note: str = "Independent completed-D1 Markov gate enabled inside this EA."
    dynamic_mode_supported: bool = False
    recommended_dynamic_mode: bool = False
    dynamic_mode_label: str = "Dynamic London"
    dynamic_mode_note: str = "Research preset using volatility-scaled exits."
    evidence: Evidence | None = None
    safe_evidence: Evidence | None = None
    dynamic_evidence: Evidence | None = None
    one_year_evidence: Evidence | None = None
    one_year_return_pct: float | None = None
    one_year_note: str | None = None
    buy_url: str = ""


SELECTED_CONFIGS: dict[str, tuple[str, str, str]] = {
    "LTA Volume Profile": ("lta-xau", "current", "Current EA exits"),
    "BTC Top Down FVG Liquidity": ("topdown-btc", "current", "Current EA exits"),
    "ETH Top Down FVG Liquidity": ("topdown-eth", "dynamic-only", "Dynamic 50/20"),
    "Engineered Liquidity XAU": ("engineered-xau", "dynamic-only", "Dynamic 50/20"),
    "ORB Volume Profile": ("orb-volume-xau", "dynamic-only", "Dynamic 50/20"),
    "ORB Volume Profile High Win 0.75R": ("orb-volume-xau-high-win", "dynamic-only", "Dynamic 50/20"),
    "ORB Volume Profile Volume Confirmed": ("orb-volume-xau-volume-confirmed", "dynamic-only", "Dynamic 50/20"),
    "XAU ORB New York M30": ("orb-session-xau-new-york", "current", "Native 1.5R / BE at 0.5R"),
    "XAU ORB London NY Overlap M30": ("orb-session-xau-overlap", "current", "Native 1R / BE at 0.5R"),
    "US100 ORB New York M30": ("orb-session-us100-new-york", "current", "Fixed 4R / no trailing"),
    "US100 H1 ORB 13UTC": ("orb-h1-us100-13utc", "current", "Nominal 6R / timed flat"),
    "US100 Selective ORB V3": ("orb-selective-us100-v3", "current", "Fixed 2R / BE at 1R"),
    "AAA Final Asia Breakout": ("asia-xau", "dynamic-only", "Dynamic 50/20"),
    "DMC Current XAU": ("dmc-current-xau", "current", "Dynamic 50/20"),
    "DMC Fresh Reaction XAU": ("dmc-fresh-reaction-xau", "current", "Dynamic 50/20"),
    "DMC Fresh Reaction US100": ("dmc-fresh-reaction-us100", "current", "Dynamic 50/20"),
    "AAA Final EMA3": ("ema3-xau", "dynamic-only", "Dynamic 60/20 only"),
    "AAA Final XAU Weakness": ("weakness-xau", "dynamic-only", "Dynamic 50/20"),
    "Nasdaq Overnight": ("overnight-ustec", "current", "Current EA exits"),
    "Nasdaq 5M Candle Momentum": ("momentum-ustec", "current", "Fixed 2.5R / no trailing"),
    "Sell Nasdaq 15min": ("sell-nasdaq-15min", "current", "Fixed 2.22R / no trailing"),
    "USDJPY London Open Momentum": ("london-open-momentum-usdjpy", "current", "Time exit / BE at 0.75R"),
    "XAU Squeeze Momentum Standard": ("squeeze-momentum-xau-standard", "current", "3.5 ATR stop / 1.5R / ATR ratchet"),
    "XAU Squeeze Momentum High Win 0.75R": ("squeeze-momentum-xau-high-win", "current", "3 ATR stop / 0.75R / ATR ratchet"),
    "News Pulse XAU": ("news-xau-hard-1p5", "current", "Native 60-second exit"),
    "News Pulse XAG": ("news-xag-hard-1p5", "current", "Native 60-second exit"),
    "News Pulse BTC": ("news-btc-hard-1p5", "current", "Native 60-second exit"),
    "XAU RSI VWAP": ("rsi-vwap-xau", "current", "Current EA exits"),
    "BTC POC Fibonacci": ("pocfib-btc", "current", "Fixed 5R / no trailing"),
    "XAU Elliott Wave 1-2-3": ("elliott-xau", "current", "Fixed 3R / no trailing"),
    "XAU Slow Trend": ("slow-trend-xau", "current", "Fixed 6R / no trailing"),
    "XAU Regime Switch": ("regime-switch-xau", "current", "6R trend / 3R VWAP regime switch"),
    "XAG Session VWAP Snapback": ("session-vwap-xag", "current", "Fixed 1R / no trailing"),
    "US100 Month End Flow": ("month-end-flow-us100", "current", "Fixed 2.5R / six-hour exit"),
}


CORE_META: dict[str, dict[str, Any]] = {
    "DMC Current XAU": {
        "strategy": "Prior-day body rejection",
        "tagline": "The established XAUUSD DMC baseline, retained as a higher-frequency control beside the selective builds.",
        "description": "This original XAUUSD H1 DMC configuration trades rejection from the completed prior-day real-body high or low during Asia. It deliberately keeps the freshness and higher-timeframe proximity gates disabled, uses a fixed 22.5-price-unit stop, targets 3R and protects progress with Dynamic 50/20.",
        "session": "00:00-08:00 UTC Asia window / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The retained production source, exact selected SET and native MT5 Every Tick comparison reports were reviewed during the 100-case DMC fresh-reaction pipeline.",
        "logic": [
            {"title": "Map yesterday's real body", "detail": "After a new broker day begins, the EA stores the open and close of the last completed D1 candle and treats the higher and lower body prices as reaction boundaries."},
            {"title": "Wait for an H1 rejection", "detail": "A completed H1 candle must test beyond one mapped body boundary and close back on the accepted side with a directional candle body before an entry can qualify."},
            {"title": "Trade the established Asia window", "detail": "The production SET permits signals from 00:00 through 08:00 UTC after converting the configured broker offset; entries outside that window are rejected."},
            {"title": "Keep the baseline filters unchanged", "detail": "Fresh-touch counting and weekly or monthly proximity confirmation remain disabled, preserving the original signal population as the comparison control."},
            {"title": "Use fixed protection and chosen risk", "detail": "The initial protective distance is 22.5 XAU price units and volume is calculated from the percentage selected in the BAT; pressing Enter keeps the 1% default."},
            {"title": "Target 3R and apply Dynamic 50/20", "detail": "The initial objective is three times risk; after a completed M15 candle reaches halfway toward target, the stop can lock twenty percent of the original path."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage and defaults to the tested 1%. Its three-year result was +46.72%, PF 1.27, 40.80% wins and 12.49% drawdown over 250 trades; it overlaps strongly with the two selective DMC variants.",
        "price": 299,
        "accent": "gold",
        "featured": False,
    },
    "DMC Fresh Reaction XAU": {
        "strategy": "Fresh multi-timeframe body rejection",
        "tagline": "A selective XAUUSD DMC build that demands a fresh daily level aligned with weekly or monthly structure.",
        "description": "This pipeline-selected XAUUSD H1 version keeps the DMC rejection idea but admits no more than one earlier M15 touch of the daily-body level. It also requires a completed weekly or monthly body boundary nearby, uses a fixed 30-price-unit stop, targets 3R and applies Dynamic 50/20.",
        "session": "00:00-08:00 UTC Asia window / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable production MQ5, 100 native MT5 Every Tick pipeline cases, a locked year and an exact three-year validation were reviewed together.",
        "logic": [
            {"title": "Map the completed daily body", "detail": "The EA builds the candidate reaction levels from the open and close of the last completed D1 candle, never from the still-forming current daily bar."},
            {"title": "Require a fresh level", "detail": "Completed M15 candles since the day opened are scanned with a 0.05 D1-ATR tolerance, and the setup survives only when the boundary has no more than one prior touch."},
            {"title": "Demand higher-timeframe confluence", "detail": "A completed W1 or MN1 real-body boundary must lie within 0.25 of D1 ATR from the daily reaction price, giving the level independent structural support."},
            {"title": "Confirm rejection during Asia", "detail": "Inside 00:00-08:00 UTC, a completed H1 candle must sweep the selected boundary, close back through it and print the correct directional candle body."},
            {"title": "Use the selected fixed stop and risk", "detail": "The protective distance is fixed at 30 XAU price units while OrderCalcProfit sizes volume from the BAT-selected equity percentage, defaulting to the tested 1%."},
            {"title": "Target 3R and protect at 50/20", "detail": "The trade begins with a three-times-risk objective; a completed M15 close halfway toward target permits the stop to lock twenty percent of the original route."},
        ],
        "risk_note": "Every BAT follows the user's selected equity-risk percentage and defaults to the tested 1%. Three years returned +36.18%, PF 2.49, 60.00% wins and 4.08% drawdown over 55 trades; the locked year contained only 15 trades, so demo-forward confirmation remains important.",
        "price": 349,
        "accent": "teal",
        "featured": True,
    },
    "DMC Fresh Reaction US100": {
        "strategy": "Fresh multi-timeframe index rejection",
        "tagline": "The DMC fresh-reaction concept transferred to US100 with a New York window and volatility-scaled protection.",
        "description": "This selective USTEC H1 deployment requires a fresh prior-day body level plus nearby completed weekly or monthly body structure. It trades during New York, uses a 1.5 ATR stop, targets 2R and applies Dynamic 50/20.",
        "session": "13:00-21:00 UTC New York window / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable production MQ5, native MT5 transfer testing, locked-year validation and an exact three-year Every Tick report were reviewed together.",
        "logic": [
            {"title": "Map the completed daily body", "detail": "At each new broker day, the EA records the prior completed D1 open and close as the upper and lower body reaction levels for US100."},
            {"title": "Reject repeatedly tested levels", "detail": "It scans completed M15 history since the day opened and accepts only a boundary with no more than one earlier touch inside a 0.05 D1-ATR tolerance."},
            {"title": "Align with larger structure", "detail": "At least one completed weekly or monthly real-body boundary must be within 0.25 D1 ATR of the candidate daily level before the signal can proceed."},
            {"title": "Confirm in the New York window", "detail": "From 13:00 through 21:00 UTC, a completed H1 candle must sweep the chosen boundary, close back on the accepted side and agree directionally."},
            {"title": "Scale the stop to index volatility", "detail": "The initial stop is 1.5 times H1 ATR(14), and volume targets the risk percentage selected by the BAT; pressing Enter retains the tested 1% default."},
            {"title": "Target 2R and apply Dynamic 50/20", "detail": "The objective is two times initial risk, while a completed M15 close halfway to target can advance the stop to lock twenty percent of the original path."},
        ],
        "risk_note": "Every BAT follows the user's selected equity-risk percentage and defaults to the tested 1%. Three years returned +17.94%, PF 1.99, 65.22% wins and 4.39% drawdown over 46 trades; its locked year contained 12 trades, so it remains a selective demo-forward allocation.",
        "price": 349,
        "accent": "sky",
        "featured": True,
    },
    "USDJPY London Open Momentum": {
        "strategy": "London-open intraday momentum continuation",
        "tagline": "A selective USDJPY continuation model built from the first completed London trading hour.",
        "description": "This pipeline-selected USDJPY M15 deployment measures the completed 08:00-09:00 London move and follows its direction only on Wednesday through Friday. It requires a meaningful move and acceptable formation activity, uses a wide volatility-scaled protective stop, protects the trade at +0.75R and closes remaining exposure at 16:00 London.",
        "session": "08:00-16:00 Europe/London / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, 144 native MT5 pipeline cases, independent Every Tick validation windows and a 10,000-path latest-year Monte Carlo audit were reviewed together.",
        "logic": [
            {"title": "Measure the completed London opening hour", "detail": "The EA converts broker time to Europe/London with daylight-saving handling and builds the 08:00-09:00 range from completed M5 candles."},
            {"title": "Follow the opening direction", "detail": "A positive opening-hour return produces a long signal and a negative return produces a short signal. Both directions are enabled."},
            {"title": "Demand meaningful participation", "detail": "The absolute opening move must measure at least 0.20 of M15 ATR, and formation tick activity must reach at least 25% of the median activity from the previous twenty comparable windows."},
            {"title": "Trade only the selected weekdays", "detail": "The promoted configuration trades Wednesday, Thursday and Friday. Monday and Tuesday were removed during development selection and were not reintroduced after seeing the validation periods."},
            {"title": "Use volatility-scaled protection", "detail": "The initial stop is five times M15 ATR(14). OrderCalcProfit sizes volume from current equity using the percentage selected in the BAT; pressing Enter keeps the 1% default."},
            {"title": "Protect and close intraday", "detail": "At +0.75R the stop advances to breakeven. Fixed and adaptive profit targets remain disabled, and any surviving position is closed thirty seconds before 16:00 London."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage; pressing Enter defaults to the tested 1%. The latest unseen year returned +12.72% with PF 1.33, 51.85% wins and 10.13% drawdown, but the preceding validation year produced only PF 1.09. Treat it as a demo/watch allocation, not a proven core strategy.",
        "price": 249,
        "accent": "sky",
        "featured": False,
    },
    "XAU Squeeze Momentum Standard": {
        "strategy": "H1 volatility-compression breakout",
        "tagline": "The broad-evidence XAUUSD squeeze-release model with trend, momentum and volatility-scaled exits.",
        "description": "This optimized long-only H1 build waits for Bollinger Bands to leave a Keltner Channel squeeze, then requires positive strengthening regression momentum and a close above SMA200. Standard uses a 3.5 ATR stop, 1.5R target and a ratcheting 3.5 ATR trail; Safe adds the independently tested completed-D1 regime gate.",
        "session": "All UTC hours, Monday-Friday / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, 135 pipeline configurations, purged validation, an untouched real-tick year, long-window context, delay tests, spread stress and Monte Carlo analysis were reviewed.",
        "logic": [
            {"title": "Wait for volatility compression to release", "detail": "A completed H1 candle must be the first bar after Bollinger Bands with length 24 and multiplier 1.8 expand back outside Keltner Channels using length 24 and multiplier 1.3."},
            {"title": "Confirm positive strengthening momentum", "detail": "LazyBear-style linear-regression momentum over 28 completed H1 observations must be above zero and stronger than its immediately preceding completed value before a long can qualify."},
            {"title": "Align with the long-term trend", "detail": "The completed signal close must remain above the 200-hour simple moving average. The promoted configuration is deliberately long-only and trades Monday through Friday."},
            {"title": "Size from current equity and broker economics", "detail": "OrderCalcProfit measures the one-lot loss to the initial stop, then volume is rounded up to the broker step from the BAT-selected equity-risk percentage; pressing Enter keeps the tested 1% default. If the requested volume is below the broker minimum, the minimum lot is used, so actual risk can exceed the target."},
            {"title": "Use ATR-scaled protection and reward", "detail": "Standard places the initial stop 3.5 Wilder ATR(14) below entry and the take profit at 1.5 times initial risk, while maximum effective exposure is capped near 9.8 times equity."},
            {"title": "Rachet the stop and monitor momentum", "detail": "On each completed H1 bar, the stop trails 3.5 ATR below the highest completed high. The position exits early if momentum turns negative or loses more than half of its preceding strength."},
        ],
        "risk_note": "Every BAT defaults this EA to 1% of current equity and replaces that value with the user's input in dynamic-risk BATs. Safe produced +22.60%, PF 3.89, 65.79% wins and 3.36% drawdown over 38 three-year trades; Standard produced +22.75%, PF 1.87, 45.35% wins and 5.69% drawdown over 86 trades. Both remain watch-only historical evidence, not guaranteed profitability.",
        "price": 349,
        "accent": "sky",
        "featured": True,
    },
    "XAU Squeeze Momentum High Win 0.75R": {
        "strategy": "High-win squeeze-release breakout",
        "tagline": "A shorter-target XAUUSD variant using a 3 ATR stop and 0.75R objective.",
        "description": "This H1 variant retains the optimized squeeze, momentum and SMA200 signal but reduces the protective stop to 3 ATR and the hard target to 0.75R. It is installed separately with its own magic number and trade comment so it can coexist safely with Standard.",
        "session": "All UTC hours, Monday-Friday / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source and the exact native MT5 development-period management comparison were reviewed. Unlike Standard and Safe, this 0.75R variant has not yet completed a standalone untouched validation cycle.",
        "logic": [
            {"title": "Wait for the optimized squeeze release", "detail": "A completed H1 candle must be the first after Bollinger Bands at length 24 and multiplier 1.8 expand beyond Keltner Channels at length 24 and multiplier 1.3."},
            {"title": "Require rising positive regression momentum", "detail": "The 28-hour linear-regression projection of price deviation from the blended high-low and average-price midline must be positive and higher than on the previous completed H1 bar."},
            {"title": "Trade only with the primary uptrend", "detail": "The completed signal close must be above SMA200, only long entries are permitted, and weekend entries are blocked by the Monday-through-Friday weekday mask."},
            {"title": "Keep risk selectable without changing the signal", "detail": "Volume is calculated from broker tick value and the stop distance. It defaults to 1% equity in every static BAT and follows the exact user-entered percentage in dynamic-risk BATs."},
            {"title": "Use the saved 3 ATR and 0.75R geometry", "detail": "The initial stop is three Wilder ATR(14) below entry and the take profit is 0.75 times initial risk, producing the shorter target responsible for its higher development win rate."},
            {"title": "Retain the matching ATR and momentum exits", "detail": "The highest completed H1 high ratchets a three-ATR trailing stop upward, while negative momentum or a fade greater than fifty percent can liquidate the position before the hard target."},
        ],
        "risk_note": "Every BAT defaults to 1% equity and applies the user's selected percentage in dynamic-risk mode. A fresh three-year native run returned +10.10%, PF 1.40, 54.44% wins and 5.01% drawdown over 90 trades; its original development comparison reached 60.76% wins. It remains a research candidate because the exact preset was chosen before this post-selection long-window run and has not passed a new untouched validation.",
        "price": 299,
        "accent": "blue",
        "featured": False,
    },
    "BTC POC Fibonacci": {
        "strategy": "POC and 0.618 Fibonacci confluence",
        "tagline": "A selective BTCUSD M15 profile-retracement model retained as a demo-watch candidate.",
        "description": "This optimized BTCUSD M15 build forms a completed rolling activity profile, aligns its point of control with a 0.618 retracement, and trades a directional reclaim only during its selected New York broker-session window. It uses a 1.5 ATR stop, a fixed 5R target and no trailing stop.",
        "session": "New York broker-session window / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact optimized SET, native MT5 Every Tick reports and the 10,000-path Monte Carlo audit were reviewed together.",
        "logic": [
            {"title": "Build the completed profile", "detail": "The EA bins the last 192 completed M15 candles into 64 price buckets using broker tick activity, then identifies the rolling point of control without using the still-forming candle."},
            {"title": "Require Fibonacci confluence", "detail": "The profile POC must sit within 0.50 ATR of the 0.618 retracement of the completed profile range, and the completed signal candle must interact with the POC inside a 0.10 ATR touch tolerance."},
            {"title": "Confirm trend and departure", "detail": "Direction is aligned with a rising or falling H1 50 EMA. Price must first depart by at least 0.75 ATR during the prior sixteen bars and then produce the configured completed-candle reclaim confirmation."},
            {"title": "Restrict entries and size risk", "detail": "Longs and shorts are allowed, with no more than two entries per broker day and entries limited to the selected New York broker-session hours. Order size targets the risk chosen by the BAT; the default and validated value is 1% of current equity."},
            {"title": "Reject unsuitable execution conditions", "detail": "The completed profile must span at least two ATR and the live spread must remain at or below 0.20 ATR. Broker stop distance, volume steps and an 80-point maximum order deviation are enforced before submission."},
            {"title": "Use the locked native exit", "detail": "The initial stop is 1.5 ATR and the take profit is fixed at five times original risk. Break-even, ATR trailing and Dynamic 50/20 are disabled; a position may remain open for up to 96 M15 bars."},
        ],
        "risk_note": "Every BAT asks for risk before installation; the default and validated value is 1% of current equity. The locked year produced only 26 trades and the Monte Carlo return P5 was -14.32%, so this EA should remain on demo/watch rather than be treated as a dependable core system.",
        "price": 249,
        "accent": "orange",
        "featured": False,
    },
    "XAU Trend Progression": {
        "strategy": "H4 trend-pullback continuation",
        "tagline": "An optimized long-only XAUUSD H4 continuation model with structural risk and a 3R objective.",
        "description": "This locked optimized build follows established XAUUSD H4 uptrends, waits for price to pull back into the 20 EMA area, and enters only after the completed signal candle confirms continuation. It uses a five-bar structural stop, a 3R target and a small locked-profit break-even move after +1R.",
        "session": "All broker sessions / H4",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact optimized 1% SET and its locked MT5 Every Tick report were reviewed together.",
        "logic": [
            {"title": "Confirm the established H4 uptrend", "detail": "The completed signal candle must close above the 50 EMA, the 20 EMA must be above the 50 EMA, and the 50 EMA must be higher than it was three H4 bars earlier. Shorts are disabled in the promoted XAUUSD preset."},
            {"title": "Require genuine multi-bar momentum", "detail": "The close must be at least 0.50 ATR above the close from twenty-four H4 bars earlier. Signal bodies smaller than 0.05 ATR and total candle ranges larger than 2.50 ATR are rejected."},
            {"title": "Wait for the pullback to value", "detail": "The completed H4 signal candle must touch the 20 EMA within a tolerance of 0.25 ATR. The range-leadership filter is disabled, so the EA does not require price to finish in a fixed percentile of its 48-bar range."},
            {"title": "Accept objective bullish confirmation", "detail": "The optimized preset uses the EA's any-confirmation mode: a bullish body, bullish engulfing pattern or bullish pin-bar can confirm that the pullback is attempting to resume upward."},
            {"title": "Place the structural stop and size from chosen risk", "detail": "The stop goes below the lowest low of the latest five completed H4 candles with a 0.10 ATR buffer. OrderCalcProfit measures the one-lot loss to that stop, and volume is rounded up to the broker step from the risk selected when the BAT starts. The default and validated value is 1% of current equity; the broker minimum lot is used when necessary, even if that exceeds the target."},
            {"title": "Target 3R and protect after +1R", "detail": "Take profit is three times the original stop distance. Once price reaches +1R, the stop can advance to entry plus 0.05R. ATR trailing, Dynamic 50/20, maximum-hold exits, session filtering and the experimental regime gate are disabled."},
        ],
        "risk_note": "Every BAT asks for risk before installation; the default and validated value is 1% of current equity per trade. The selected model is long-only, so it can remain inactive during extended bearish or non-trending gold conditions.",
        "price": 349,
        "accent": "gold",
        "featured": True,
    },
    "XAU Elliott Wave 1-2-3": {
        "strategy": "Confirmed Wave 1-2-3 continuation",
        "tagline": "A non-repainting XAUUSD H4 continuation model built from confirmed pivots and a fixed 3R objective.",
        "description": "This optimized XAUUSD H4 build converts the Wave 1, Wave 2 and Wave 3 continuation idea into objective rules. It waits for confirmed alternating pivots, validates the Wave 2 retracement, aligns direction with a sloping 50 EMA, and enters only after a completed breakout candle clears the Wave 1 extreme.",
        "session": "All broker sessions / H4",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact optimized SET, 329 native MT5 reports and the 10,000-path locked-trade Monte Carlo audit were reviewed together.",
        "logic": [
            {"title": "Confirm pivots without repainting", "detail": "A swing is accepted only after three completed candles exist on both sides of the candidate high or low. The EA then requires the most recent three confirmed pivots to alternate as low-high-low for a long or high-low-high for a short."},
            {"title": "Validate Wave 1 and Wave 2", "detail": "Wave 1 must measure between 1.50 and 10.00 H4 ATR. Wave 2 must retrace between 38.2% and 78.6% of Wave 1 and may not cross the Wave 1 origin, which supplies an objective invalidation rule."},
            {"title": "Align with the H4 EMA50 trend", "detail": "Long setups require the completed signal close above the 50 EMA with the average rising over the previous three H4 bars. Shorts require the inverse relationship, while the unused EMA-stack and higher-timeframe alternatives remain disabled."},
            {"title": "Demand a completed Wave 3 breakout", "detail": "The completed signal candle must close at least 0.05 ATR beyond the Wave 1 extreme and its real body must measure at least 0.15 ATR. The live spread must remain at or below 0.15 ATR before an order can be submitted."},
            {"title": "Use signal-candle invalidation and equity risk", "detail": "The protective stop is placed beyond the completed breakout candle with a 0.10 ATR buffer and is rejected if wider than five ATR. OrderCalcProfit sizes the trade from current equity; every BAT asks for risk, and the default and validated value is 1%."},
            {"title": "Hold for the fixed 3R objective", "detail": "Take profit is three times the original entry-to-stop distance. Break-even, ATR trailing, Dynamic 50/20, maximum-holding exits and session restrictions are disabled, preserving the exact exit behavior used in the untouched locked-year validation."},
        ],
        "risk_note": "Every BAT asks for the desired risk before installation; the default and validated value is 1% of current equity per trade. The untouched year contains only 24 trades, so this remains a cautious demo-forward candidate despite its positive Monte Carlo downside.",
        "price": 349,
        "accent": "gold",
        "featured": True,
    },
    "XAU Slow Trend": {
        "strategy": "Slow multi-horizon time-series momentum",
        "tagline": "A selective XAUUSD H4 trend model combining one-, three- and six-month momentum.",
        "description": "The promoted XAUUSD build votes across completed one-, three- and six-month momentum horizons, aligns the result with EMA100, and trades the accepted direction from H4 data. It uses a 1.5 ATR stop, fixed 6R objective, no trailing and percentage-based equity risk.",
        "session": "All broker sessions / H4",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the frozen optimized SET, untouched locked-year native MT5 report, three-year context and rolling walk-forward audit were reviewed together.",
        "logic": [
            {"title": "Vote across three slow horizons", "detail": "The EA compares the latest completed H4 close with scaled 21-, 63- and 126-trading-day lookbacks. Their signs are averaged, and a trade requires a non-zero majority direction."},
            {"title": "Confirm direction with EMA100", "detail": "A long requires the completed H4 close above the scaled EMA100; a short requires it below. Both directions remain enabled in the locked XAU preset."},
            {"title": "Use completed data and avoid late attachment entries", "detail": "Signals use the last completed H4 candle. On a live attach or terminal restart, the EA records the existing signal and waits for the next completed H4 candle rather than entering an old setup late."},
            {"title": "Place the ATR stop", "detail": "The initial stop is 1.5 times H4 ATR(14) from entry. Volume is rounded up to the broker step from the calculated one-lot loss so the planned loss targets the percentage selected in the BAT. If the requested size is below the broker minimum, the minimum lot is used and the trade is not skipped for sizing."},
            {"title": "Leave the wide winner intact", "detail": "The target is fixed at six times original risk. Break-even, ATR trailing, chandelier trailing, Dynamic 50/20 and maximum-hold exits are disabled in the promoted configuration."},
            {"title": "Isolate this chart from other XAU EAs", "detail": "Magic number 969060311 uniquely identifies this strategy. On hedging accounts it scans all positions and manages only its own matching XAU position."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage to this EA; pressing Enter defaults to the validated 1%. The locked year had 35 trades, so it should begin on demo forward testing.",
        "price": 399,
        "accent": "emerald",
        "featured": True,
    },
    "XAG Session VWAP Snapback": {
        "strategy": "New York session VWAP liquidity snapback",
        "tagline": "A selective XAGUSD M30 mean-reversion model for stretched New York-session prices.",
        "description": "The promoted XAGUSD build reconstructs the active New York session VWAP and volume-weighted deviation from completed M30 candles. It waits for price to stretch 2.5 standard deviations from accepted value, requires a completed rejection candle, and trades the snapback only while ADX remains at or below 20.",
        "session": "09:30-16:00 New York / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the frozen SET, untouched locked-year native MT5 report, three-year context, sensitivity grids and 10,000-path block bootstrap were reviewed together.",
        "logic": [
            {"title": "Build the active New York session profile", "detail": "For every completed M30 signal candle, the EA rebuilds VWAP and its volume-weighted price deviation from the start of the current 09:30-16:00 New York session using broker tick volume."},
            {"title": "Wait for an exceptional stretch", "detail": "Price must reach at least 2.5 session standard deviations above or below VWAP. This keeps entries away from the middle of accepted value and avoids ordinary session noise."},
            {"title": "Require a completed rejection candle", "detail": "A stretched candle must close back toward VWAP with a directionally rejecting body and wick. Both long and short snapbacks are enabled, with no more than one entry per New York session."},
            {"title": "Trade only a quiet regime", "detail": "M30 ADX(14) must be at or below 20. This prevents the mean-reversion entry from fading stronger directional sessions, where a VWAP extension is more likely to continue."},
            {"title": "Use the locked ATR stop and 1R target", "detail": "The initial stop is 1.25 M30 ATR from entry and the target is exactly one original risk unit. Break-even, ATR trailing and Dynamic 50/20 are disabled because the no-management version was selected before the locked year."},
            {"title": "Apply the BAT-selected equity risk", "detail": "OrderCalcProfit measures the one-lot loss to the stop, and order volume is rounded up to the broker step to target the percentage selected in the BAT. Broker minimum-stop rules are enforced; if the requested volume is below the broker minimum, the minimum lot is used and actual risk can exceed the target."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage; pressing Enter defaults to the validated 1%. The untouched year returned +3.93% with PF 2.57 and 3.60% drawdown, but it produced only 15 trades; this is therefore a demo-forward/watch allocation, not a statistically mature core strategy.",
        "price": 299,
        "accent": "silver",
        "featured": False,
    },
    "US100 Month End Flow": {
        "strategy": "Turn-of-month institutional equity flow",
        "tagline": "A selective US100 M30 long-only model for the first three business days of each month.",
        "description": "The promoted USTEC build trades the documented turn-of-month equity-flow tendency without using future calendar information. It enters long after the first New York trading hour on each of the first three business days, protects the position with a 1.5 ATR stop, targets 2.5R and closes any survivor after six hours.",
        "session": "First three business days, after 10:30 New York / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the frozen production SET, untouched locked-year native MT5 report, three-year context, sensitivity grids, rolling audit and 10,000-path Monte Carlo simulation were reviewed together.",
        "logic": [
            {"title": "Identify the month window without look-ahead", "detail": "The EA derives business-day position from the known weekday calendar only. It activates on the first three Monday-to-Friday trading days of the month and does not inspect future prices or future bars."},
            {"title": "Wait through the New York opening hour", "detail": "On an eligible day, the strategy waits until the first completed M30 candle after the initial New York trading hour and submits at most one long entry for that calendar day."},
            {"title": "Keep the selected signal deliberately simple", "detail": "The frozen US100 configuration is long-only and does not add a moving-average, candle-pattern or trend confirmation. Those alternatives were tested before the locked year and were not selected."},
            {"title": "Use a volatility-scaled protective stop", "detail": "The initial stop is placed 1.5 times M30 ATR(14) below entry. A spread-to-risk ceiling and broker stop-distance checks reject trades whose execution cost or placement is unsuitable."},
            {"title": "Target 2.5R and time-limit exposure", "detail": "The take-profit objective is fixed at 2.5 times original risk. Break-even, ATR trailing and Dynamic 50/20 are disabled, while any position still open after six hours is closed."},
            {"title": "Apply the BAT-selected equity risk", "detail": "OrderCalcProfit measures the one-lot loss to the ATR stop and volume is rounded up to the broker step to target the percentage selected in the BAT. If the requested volume is below the broker minimum, the minimum lot is used and the trade is not skipped for sizing."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage; pressing Enter defaults to the validated 1%. The untouched year returned +5.53% with PF 1.34, 47.06% wins and 5.74% equity drawdown across 34 trades. Monte Carlo return P5 was -5.24%, so this is a demo-forward candidate rather than a proven live-capital core.",
        "price": 299,
        "accent": "indigo",
        "featured": False,
    },
    "Sell Nasdaq 15min": {
        "strategy": "New York M15 bearish opening-break continuation",
        "tagline": "A sell-only USTEC setup built from the completed 09:30 New York M15 candle.",
        "description": "The Best Recommended Dynamic London version requires both the 09:15-09:30 and 09:30-09:45 New York M15 candles to close bearish, then places a sell stop at the opening candle's low. It trades Monday through Friday without a fixed setup-range filter, keeps the pending order live for sixty minutes, uses a 2.5 ATR(14) stop and targets 3R. The older 450/1,000 Standard and 600/1,000 London Safe presets remain available on the comparison graph.",
        "session": "09:30-15:55 New York / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, 73 native MT5 pipeline cases, the exact selected SET, untouched locked-year Every Tick evidence, three-year Every Tick context and a 10,000-path block-bootstrap audit were reviewed together.",
        "logic": [
            {"title": "Anchor the setup to the Nasdaq cash open", "detail": "The EA converts broker time to New York time with automatic US daylight-saving handling and observes the completed 09:30-09:45 New York M15 candle on USTEC."},
            {"title": "Require two completed bearish candles", "detail": "The selected Dynamic London setup requires both the preceding 09:15-09:30 candle and the first 09:30-09:45 cash-session candle to close below their opens."},
            {"title": "Keep the dynamic setup broad", "detail": "Entries are permitted Monday through Friday. Fixed minimum/maximum opening-candle range filters and the setup-high cancellation rule are disabled in this selected preset."},
            {"title": "Place one sell stop below the setup", "detail": "Immediately after the qualifying candle closes, the EA places one sell stop exactly at its low with no extra entry buffer. The pending order has sixty minutes to trigger and only one setup is allowed per New York trading day."},
            {"title": "Scale the stop to current volatility", "detail": "The protective stop is 2.5 times M15 ATR(14) above entry. OrderCalcProfit measures the broker-specific one-lot loss and the installer applies the user's selected equity-risk percentage, defaulting to 1%."},
            {"title": "Hold for the fixed 3R objective", "detail": "Take profit is three times the original ATR-based risk below entry. Break-even, trailing and Dynamic 50/20 are disabled; any surviving position is closed at 15:55 New York."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage; pressing Enter defaults to 1%. This sell-only setup can cluster with other US100 systems. Its cached 5Y Dynamic London result is +106.38%, PF 1.52, 41.42% wins and 17.87% drawdown across 268 trades; the latest six months are negative, so forward monitoring remains necessary.",
        "price": 349,
        "accent": "sky",
        "featured": False,
    },
    "XAU RSI VWAP": {
        "strategy": "RSI-of-VWAP pullback continuation",
        "tagline": "A long-only XAUUSD H1 pullback model built from session VWAP momentum and a structural swing stop.",
        "description": "This locked XAUUSD build calculates a broker-volume VWAP that resets each broker day, applies Wilder RSI to that VWAP series, and buys only when the completed H1 signal crosses up from an unusually oversold reading. The selected setup uses a recent-swing stop and a compact 0.5R target.",
        "session": "All broker sessions / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact selected SET and its locked MT5 Every Tick report were reviewed together.",
        "logic": [
            {"title": "Rebuild the daily anchored VWAP", "detail": "On every new H1 bar, the EA reconstructs VWAP from completed chart bars and resets the cumulative price-volume calculation at each broker-day boundary. Real volume is used when available, otherwise broker tick volume is used."},
            {"title": "Measure momentum on VWAP rather than price", "detail": "A 16-period Wilder RSI is calculated from the reconstructed VWAP series. This deliberately smooths the input and asks whether accepted value, rather than one candle's close, is recovering from an extreme."},
            {"title": "Enter only the completed oversold cross", "detail": "The selected build is long-only. It requires the prior completed RSI-of-VWAP value to be at or below 18 and the newest completed value to cross above 18; the signal is evaluated once when the next H1 bar begins."},
            {"title": "Place the stop beyond recent structure", "detail": "The stop is placed below the lowest low of the preceding five completed H1 candles with an additional 0.10 ATR(14) buffer. Broker minimum stop distance is enforced before position size is calculated."},
            {"title": "Size the trade from current equity", "detail": "OrderCalcProfit measures the one-lot loss from entry to the structural stop, then volume is rounded up to the broker step to target 1% of current equity. The dynamic BAT can replace that percentage without changing the signal rules; the broker minimum lot is used when necessary."},
            {"title": "Take the compact continuation objective", "detail": "The locked target is 0.5 times initial risk. A break-even rule is configured at 0.75R, which is beyond the target and therefore does not activate in normal fills; ATR trailing and maximum-hold exits are disabled."},
        ],
        "risk_note": "Dynamic equity risk, default 1%, with no spread ceiling in the locked research preset. The 0.5R target needs a win rate above roughly 66.7% before costs; the locked year achieved 72.73% over only 44 trades.",
        "price": 249,
        "accent": "gold",
        "featured": False,
    },
    "BTC Top Down FVG Liquidity": {
        "strategy": "Liquidity sweep and fair-value-gap retest",
        "tagline": "BTCUSD M15 reversals aligned with the H4 trend and entered from a three-candle imbalance retest.",
        "description": "The BTCUSD build looks for a sweep beyond the prior 12-bar liquidity range, a decisive reversal candle, and a genuine three-candle fair-value gap. It waits for price to retrace to the gap midpoint before entering in the H4 trend direction, with a structural stop and a fixed 2R target. The installed default scans all day; the EA exposes its own session selector so All day, Asia, London, New York or the London-New York overlap can be chosen per chart.",
        "session": "All day by default; selectable per EA / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source and the exact locked BTCUSD BAT preset were reviewed together.",
        "logic": [
            {"title": "Align with the H4 trend", "detail": "A long requires the last completed H4 close above the 20 EMA while the 20 EMA is above the 50 EMA; a short requires the exact inverse. Both trade directions remain enabled."},
            {"title": "Sweep a 12-bar liquidity extreme", "detail": "The sweep candle must trade beyond the highest high or lowest low of the preceding twelve M15 bars by at least 0.02 ATR. It must then close back inside that prior range."},
            {"title": "Demand reversal displacement", "detail": "The next M15 candle must reverse away from the sweep, have a real body of at least 0.90 ATR, and close beyond the sweep candle's opposite extreme to establish directional displacement."},
            {"title": "Confirm a three-candle imbalance", "detail": "The completion candle must leave a fair-value gap between its low and the sweep high for longs, or its high and the sweep low for shorts. Gap width must remain between 0.03 and 1.00 ATR."},
            {"title": "Enter the midpoint retest", "detail": "The EA arms the gap for six M15 bars and enters only when live Ask or Bid retraces to the gap midpoint without first invalidating the structural stop or crossing through the far side of the zone."},
            {"title": "Risk 1% toward a 2R target", "detail": "Position size risks 1% of current equity to the sweep extreme plus a 0.10 ATR buffer. Stops outside 0.30 to 3.00 ATR are rejected, the target is 2R, and any survivor exits after 96 M15 bars. The default session input is All day and can be changed independently on this EA's chart."},
        ],
        "risk_note": "Default and validated risk is 1% of current equity per trade; every portfolio BAT still asks for the desired risk at launch. The EA allows up to two entries per broker day, rejects spread above 15% of M15 ATR and can trade weekends. Standard leaves the embedded Safe filter off; Full Safe enables that filter inside this EA without changing the all-day session input.",
        "price": 349,
        "accent": "orange",
        "featured": True,
    },
    "ETH Top Down FVG Liquidity": {
        "strategy": "Liquidity sweep and fair-value-gap retest",
        "tagline": "ETHUSD M15 imbalance retests filtered by the H4 trend, with a locked 4R objective and Dynamic 50/20 protection.",
        "description": "The approved ETHUSD build converts a liquidity sweep, reversal displacement and three-candle fair-value gap into a rules-based retest entry. It uses the H4 20/50 EMA regime for direction, waits only three M15 bars for the midpoint retrace, and targets four times the structural risk. Dynamic 50/20 was retained because it produced the stronger locked-year result and a better Monte Carlo drawdown tail than the raw 4R exit.",
        "session": "Continuous crypto market / M15 execution",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the approved BAT preset, 59 native MT5 comparison runs and the 10,000-path block-bootstrap audit were reviewed together.",
        "logic": [
            {"title": "Align with the H4 trend", "detail": "A long requires the last completed H4 close above the 20 EMA with the fast EMA above the 50 EMA; a short requires price below the fast EMA and the fast EMA below the slow EMA."},
            {"title": "Sweep a 24-bar liquidity extreme", "detail": "The setup begins only after an M15 candle trades at least 0.02 ATR beyond the prior twenty-four-bar high or low and then closes back inside the swept range."},
            {"title": "Confirm directional displacement", "detail": "The following candle must reverse from the sweep, form a body of at least 0.60 ATR, and close beyond the sweep candle's opposite extreme before the EA will recognize a setup."},
            {"title": "Require a valid fair-value gap", "detail": "A third candle must leave a non-overlapping three-candle gap measuring between 0.03 and 1.00 M15 ATR. The exact gap boundaries become the temporary entry zone."},
            {"title": "Wait three bars for a midpoint retest", "detail": "The setup expires after three M15 bars. Before expiry, live price must retrace to the gap midpoint without reaching the planned structural stop or invalidating the opposite boundary of the zone."},
            {"title": "Risk 1% toward the selected 4R target", "detail": "The stop sits beyond the swept extreme with a 0.10 ATR buffer, must measure 0.30 to 3.00 ATR, and sizes the order to 1% equity risk. The target is 4R and the maximum hold is 96 M15 bars. Dynamic 50/20 evaluates completed M15 candles and, after a close reaches halfway to target, advances the stop to lock 20% of the original target path."},
        ],
        "risk_note": "Every BAT asks for risk at launch; the default and validated value is 1% of current equity per trade. The preset permits at most two entries per broker day, rejects spread above 15% of M15 ATR and keeps weekend trading enabled. Three-year evidence contains only 44 trades, so demo forward-testing remains appropriate.",
        "price": 349,
        "accent": "violet",
        "featured": True,
    },
    "LTA Volume Profile": {
        "strategy": "Momentum at auction reference levels",
        "tagline": "D1/H1 trend momentum entered from H4 zones or prior-day and prior-week profile levels.",
        "description": "The active XAUUSD M15 preset is a momentum-only model. It first establishes direction, then requires price to revisit a qualified H4 supply/demand zone or a prior-day/prior-week POC, VAH or VAL before one of two enabled candle confirmations can trigger a market order. The compiled EA also contains an optional completed-profile POC first-retest gate, but the active BAT keeps it disabled because validation showed much lower drawdown at the cost of most of the return and trade count.",
        "session": "No session filter / M15 execution",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the full execution engine and the exact active BAT preset were reviewed together.",
        "logic": [
            {"title": "Establish the allowed direction", "detail": "Auto bias reads D1 first and falls back to H1. Direction is based on 20-versus-50 average closes plus recent structure. The active Momentum archetype rejects trades against the H1 trend."},
            {"title": "Build the reference map", "detail": "The EA calculates 64-bin, 70% value-area profiles for the previous day and previous week. It also finds H4 zones formed by a three-bar base followed by an ATR- and tick-volume-qualified expansion that breaks earlier structure. The optional rolling swing profile is disabled. A new completed-profile heavy-zone and first-retest calculation is available for research."},
            {"title": "Require a recent revisit", "detail": "A zone or profile level must have been touched and held within the last five M15 bars, using a 0.24 ATR proximity buffer. Supply/demand is checked first, followed by prior-week and then prior-day POC, VAH and VAL."},
            {"title": "Confirm with an enabled entry model", "detail": "Only EM1 Double Wick and EM4 Continuation are active. EM1 needs a level touch, a rejection wick of at least 25% of candle range and a directional flip. EM4 needs a touch in the first two bars and a third candle that closes through both. The confirmation bar must have at least its 20-bar average tick volume."},
            {"title": "Place a structural 3R trade", "detail": "Entry is at market. The stop sits beyond the confirming candles and, for a zone trade, beyond the zone, with a 0.12 ATR buffer. The take profit is three times the initial stop distance."},
            {"title": "Apply the active safety rules", "detail": "Each trade risks 1% of current equity, both directions are enabled and only one position is allowed per symbol. New entries pause after two consecutive losses while daily P/L is non-positive. Session, break-even and time-based dead-trade exits are disabled. The POC first-retest confirmation is explicitly OFF in every active BAT, preserving the stronger-return baseline; its safer H50/D0.50/3-bar preset remains optional research only."},
        ],
        "risk_note": "Dynamic 1% of current equity per trade, capped at 1% by the active preset. Position size is rounded up to the broker step; if the requested size is smaller, the broker minimum lot is used and actual risk can exceed the target.",
        "price": 399,
        "accent": "cyan",
    },
    "XAU Markov Regime": {
        "strategy": "No-lookahead Markov regime continuation",
        "tagline": "A long-only XAUUSD D1 regime model using transition persistence, ATR risk and a fixed 3R objective.",
        "description": "The locked XAU build converts forty-day returns into Bull, Sideways and Bear states, estimates transition probabilities from prior states only, and trades only when Bull persistence exceeds Bear persistence by more than five percentage points.",
        "session": "Daily / XAUUSD",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The Python no-lookahead research engine, locked proxy evidence, readable MQ5 port and exact BAT preset were reviewed together.",
        "logic": [
            {"title": "Label the completed D1 history", "detail": "Each completed daily close is compared with the close forty bars earlier. Returns above +5% are Bull, below -5% are Bear, and all values between those thresholds are Sideways."},
            {"title": "Build transitions without the newest outcome", "detail": "The EA counts historical state-to-state transitions in chronological order but deliberately excludes the transition into the newest state, matching the research engine's no-lookahead forecast."},
            {"title": "Demand a persistent bullish edge", "detail": "From the current state row, the EA calculates Bull probability minus Bear probability. A new long is permitted only when that signal is greater than the locked +0.05 gate."},
            {"title": "Enter once at the new daily bar", "detail": "The model evaluates only when a new broker D1 candle begins. It places no short positions and does not re-enter intraday after a stop or target has closed the day's position."},
            {"title": "Size from a four-ATR stop", "detail": "The initial stop is four times D1 ATR(14). Volume targets 1% of current equity while also capping notional exposure at two times equity. The broker minimum lot is used when the calculated size is smaller, so actual risk can exceed the target rather than skipping the trade for sizing."},
            {"title": "Target 3R and trail once per day", "detail": "Take profit is three times initial stop distance. On each later D1 close the stop may ratchet to four ATR below that close, and an invalid regime can close the surviving position."},
        ],
        "risk_note": "Dynamic 1% equity risk with a two-times-notional cap. The displayed PF 5.50 is based on only ten proxy trades and is not an MT5 tick result, so this remains a forward-test candidate.",
        "price": 399,
        "accent": "gold",
        "featured": True,
    },
    "ORB Volume Profile": {
        "strategy": "New York opening-range breakout",
        "tagline": "A direct 15-minute New York ORB filtered by range quality and broker quote activity.",
        "description": "The active XAUUSD M5 preset trades direct breaks of the 09:30-09:45 New York opening range. It does build and display a tick-activity profile, but POC, value-area and boundary-node filters are deliberately OFF in the validated preset; VWAP, EMA and Safe/Markov filters are also OFF. The retained configuration returned 49.38% over the exact three-year MT5 test with PF 1.68, a 46.75% win rate, 5.85% maximum drawdown and 169 trades.",
        "session": "09:30 New York / weekdays",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the active BAT preset, the development matrix, untouched locked year, exact three-year MT5 Every Tick evidence and 10,000-path Monte Carlo were reviewed. Display-only features are separated from entry filters below.",
        "logic": [
            {"title": "Build the 15-minute New York range", "detail": "At 09:45 New York time, the EA takes the high and low of 09:30-09:45 from M1 bars. The range must measure between 0.20 and 1.20 times M15 ATR(14). Server offset and US daylight saving are handled automatically."},
            {"title": "Confirm active opening activity", "detail": "Opening-window tick volume must be at least 0.60 times the median volume of the same window across the previous 20 valid weekdays. This is broker quote activity, not centralized exchange volume."},
            {"title": "Calculate profile levels for display", "detail": "Quote ticks from 08:00 through 09:45 are distributed into 48 price bins to draw POC, VAH and VAL for a 70% value area. In the active preset all three profile entry filters are OFF, so these lines are visual context only."},
            {"title": "Qualify a direct M5 breakout", "detail": "During the next 120 minutes, a closed M5 candle must have at least a 55% body, at least 0.80 relative tick volume versus its prior 20 bars, and close beyond the range by 0.03 ATR in its own direction. Retest mode, VWAP and EMA trend filtering are disabled."},
            {"title": "Use the opposite range boundary as the stop", "detail": "The EA enters at market. Stop loss is beyond the opposite side of the opening range by 0.10 ATR; signals needing more than 2.0 ATR of stop distance are rejected. Take profit is 2.5R and spread may not exceed 12% of the opening-range width."},
            {"title": "Manage one trade for the session", "detail": "Risk is 1% of current equity. The stop first moves to entry at +1R. Dynamic 50/20 then evaluates completed M15 candles and, after a close reaches halfway to the 2.5R target, advances the stop to lock 20% of the target path. Candle trailing is disabled, no second trade is allowed that New York date, and any open position is closed at 15:55 New York."},
        ],
        "risk_note": "Dynamic 1% of current equity, sized from entry to the opposite-range stop. The exact three-year test produced a 46.75% win rate over 169 trades; the 10,000-path Monte Carlo return P5 was +16.23% with 0% simulated ruin. Gap, spread and execution slippage can still make realized risk differ from the calculation.",
        "price": 449,
        "accent": "emerald",
        "featured": True,
    },
    "XAU ORB New York M30": {
        "strategy": "Standalone New York opening-range breakout",
        "tagline": "A low-frequency XAUUSD M30 breakout of the completed 09:30 New York range.",
        "description": "This standalone gold variant builds the first thirty minutes after 09:30 New York, then waits for a completed M30 candle to confirm a direct breakout. It was selected on the two years before the displayed locked year and retains its native 1.5R target and 0.5R break-even rule.",
        "session": "09:30 New York / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The current MQ5 source, exact promoted SET, development matrix and untouched native MT5 Every Tick report were verified together.",
        "logic": [
            {"title": "Build the standalone New York range", "detail": "The EA converts broker time to New York time with US daylight-saving support and measures the high, low and tick activity from 09:30 through 10:00 using completed M1 bars."},
            {"title": "Reject weak or distorted openings", "detail": "The thirty-minute range must measure between 0.20 and 1.80 times M15 ATR(14), while opening tick activity must reach at least 0.60 of the same window's twenty-session median."},
            {"title": "Demand a completed M30 breakout", "detail": "Within the next 180 minutes, a completed M30 candle needs a body of at least 55% of its range, 0.80 relative tick activity and a close at least 0.03 ATR beyond the opening boundary."},
            {"title": "Place the opposite-range stop", "detail": "A market entry uses the far side of the opening range plus a 0.10 ATR buffer as its structural stop. Signals requiring more than 2.00 ATR of stop distance are rejected."},
            {"title": "Target 1.5R and protect at 0.5R", "detail": "Take profit is fixed at 1.5 times original risk. At +0.5R the stop advances to entry; candle trailing and Dynamic 50/20 are disabled, and surviving exposure closes at 15:55 New York."},
            {"title": "Limit execution and size exact risk", "detail": "Only one trade is allowed per New York date, spread may not exceed 12% of the range, and order volume targets the percentage selected by the BAT, defaulting to the validated 1% of equity."},
        ],
        "risk_note": "The default and validated setting is 1% of current equity. The locked year returned 2.44% with PF 3.04 but contained only eleven trades, so this remains a low-confidence forward-test configuration.",
        "price": 449,
        "accent": "gold",
        "featured": False,
    },
    "XAU ORB London NY Overlap M30": {
        "strategy": "Standalone London/New York overlap breakout",
        "tagline": "A compact 13:00 UTC gold range traded only through the liquid London/New York overlap.",
        "description": "This XAUUSD variant builds a five-minute range from 13:00 UTC and evaluates direct breakout confirmation on completed M30 candles. It uses the overlap as the strategy's native clock rather than applying a generic session filter over the standard New York ORB.",
        "session": "13:00-16:00 UTC overlap / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The current MQ5 source, promoted SET and untouched locked-year native MT5 report were checked against the completed session matrix.",
        "logic": [
            {"title": "Build the five-minute overlap range", "detail": "At 13:00 UTC the EA measures the next five minutes of completed M1 bars, converting the live broker server clock automatically so the reference remains anchored to UTC."},
            {"title": "Validate range and opening activity", "detail": "The range must remain between 0.20 and 1.80 times M15 ATR(14), and its tick activity must reach at least 0.60 of the matching window's twenty-session median."},
            {"title": "Confirm the break on M30", "detail": "A completed M30 candle must close at least 0.03 ATR outside the range, print a body of at least 55% of total candle range and carry at least 0.80 relative tick activity."},
            {"title": "Use the tighter opposite boundary stop", "detail": "The initial stop sits beyond the far side of the five-minute range with a 0.05 ATR buffer. Setups requiring more than 1.50 ATR to that stop are rejected before sizing."},
            {"title": "Target 1R and break even at 0.5R", "detail": "The fixed objective equals original risk and the stop moves to entry after +0.5R. Dynamic 50/20 and candle trailing are disabled, and exposure is flattened at 16:00 UTC."},
            {"title": "Keep the overlap deployment isolated", "detail": "The EA permits one trade per session date, rejects spread above 12% of range width and sizes from the BAT-selected equity percentage, with 1% used in the locked validation."},
        ],
        "risk_note": "The locked year returned 5.21% with PF 2.16 over only twenty-four trades. Its Monte Carlo P5 was -1.17%, so the promoted configuration should be treated as a diversified research sleeve rather than a proven core EA.",
        "price": 449,
        "accent": "emerald",
        "featured": False,
    },
    "US100 ORB New York M30": {
        "strategy": "Standalone New York opening-range breakout",
        "tagline": "The strongest tested US100 session variant: a five-minute New York range with a wide 4R objective.",
        "description": "This USTEC configuration builds the first five minutes after the 09:30 New York cash open and waits for direct M30 breakout confirmation. It deliberately leaves break-even and trailing management off so the selected 4R objective can capture the full continuation.",
        "session": "09:30 New York / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The current MQ5 source, exact promoted SET, complete development matrix and untouched native MT5 Every Tick report were reviewed together.",
        "logic": [
            {"title": "Build the five-minute New York range", "detail": "The EA measures completed M1 highs, lows and broker tick activity from 09:30 through 09:35 New York, with automatic conversion for broker time and US daylight-saving changes."},
            {"title": "Screen opening conditions", "detail": "Range width must fall between 0.20 and 1.80 times M15 ATR(14), and five-minute opening activity must reach at least 0.60 of the same period's twenty-session median."},
            {"title": "Wait for M30 continuation evidence", "detail": "During the following 180 minutes, a completed M30 candle must close 0.03 ATR beyond the range with a body ratio of at least 55% and relative tick activity of at least 0.80."},
            {"title": "Risk against the opposite boundary", "detail": "The stop is placed beyond the far side of the opening range with a 0.10 ATR buffer. Any signal whose required stop exceeds 2.00 M15 ATR is rejected before order submission."},
            {"title": "Leave the selected 4R exit untouched", "detail": "Take profit is four times original risk. Break-even, candle trailing and Dynamic 50/20 are all disabled, allowing the trade to resolve at its structural stop, 4R target or 15:55 close."},
            {"title": "Apply one-trade execution controls", "detail": "Only one trade is permitted per New York date, spread may not exceed 12% of range width and volume targets the BAT-selected equity risk, defaulting to the tested 1%."},
        ],
        "risk_note": "The locked year returned 9.66% with PF 1.68 and 4.76% drawdown over twenty-seven trades. Monte Carlo P5 was -0.94%, so this is promoted for demo-forward observation before meaningful live capital.",
        "price": 449,
        "accent": "cyan",
        "featured": True,
    },
    "US100 H1 ORB 13UTC": {
        "strategy": "Fixed-UTC one-hour opening-range breakout",
        "tagline": "A USTEC M15 continuation model built around the completed 13:00-14:00 UTC range.",
        "description": "This standalone US100 configuration measures a fixed one-hour range from 13:00 UTC, then accepts a direct breakout confirmed by a completed M15 candle during the following hour. It uses the opposite range boundary as structural risk, a nominal 6R target and a 20:00 UTC timed close. The 6R objective is not the same as realized average reward because many survivors close at the time limit.",
        "session": "13:00-20:00 UTC / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The current ORB MQ5 source, exact RR6 SET, untouched one-year MT5 Every Tick report and 10,000-path Monte Carlo audit were reviewed together.",
        "logic": [
            {"title": "Build the fixed one-hour UTC range", "detail": "The EA converts broker-server time to UTC and measures completed M1 highs, lows and broker tick activity from 13:00 through 14:00 on weekdays only."},
            {"title": "Screen the opening conditions", "detail": "Range width must remain between 0.35 and 4.00 times H1 ATR(14), while opening quote activity must reach at least half of the matching window's twenty-session median."},
            {"title": "Confirm a direct M15 breakout", "detail": "During the sixty minutes after the range completes, a closed M15 candle must finish 0.03 ATR outside the boundary, print a body of at least 55% and reach 0.70 relative tick activity."},
            {"title": "Place the opposite-boundary stop", "detail": "A market order uses the far side of the one-hour range plus a 0.10 ATR buffer as its stop. Signals needing more than 3.00 H1 ATR of stop distance are rejected before sizing."},
            {"title": "Keep the native RR6 management", "detail": "The take-profit order is placed at six times original risk. Break-even, candle trailing, profile filters, VWAP, EMA trend and Dynamic 50/20 are disabled in this exact promoted preset."},
            {"title": "Limit the session and size selected risk", "detail": "Only one trade is allowed per UTC session date, spread may not exceed 12% of range width, volume uses the BAT-selected equity risk with 1% as default, and any survivor closes at 20:00 UTC."},
        ],
        "risk_note": "The locked year returned 23.00% with PF 1.72, 50.70% wins and 6.81% drawdown over seventy-one trades. Its Monte Carlo return P5 was only +0.12% and P95 drawdown was 11.25%, so this belongs on demo before live capital. Although the placed target is 6R, timed exits reduced the realized average win-to-loss ratio to about 1.68.",
        "price": 449,
        "accent": "cyan",
        "featured": True,
    },
    "US100 Selective ORB V3": {
        "strategy": "Selective New York opening-range retest",
        "tagline": "A low-frequency USTEC M5 retest model using range quality, VWAP and time-direction controls.",
        "description": "This V3 configuration builds the first thirty minutes of the New York cash session, requires a strong volume-backed breakout and waits up to three completed M5 candles for a controlled retest of the broken edge. It retains its native 2R target and 1R break-even rule. Its positive one-year result contains only five trades, so the page presents it as a cautious demo candidate rather than strong proof.",
        "session": "09:30-15:55 New York / M5",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact V3 time-direction SET, its one-year native MT5 report and the longer 2020-2026 context were reviewed together.",
        "logic": [
            {"title": "Build the 30-minute New York range", "detail": "The EA measures USTEC high, low and broker tick activity from 09:30 through 10:00 New York, using automatic daylight-saving and broker-server offset conversion."},
            {"title": "Reject weak or distorted openings", "detail": "Opening activity must reach 0.60 of its twenty-session baseline and range width must stay between 0.05 and 0.35 of daily ATR, excluding unusually quiet or expanded cash opens."},
            {"title": "Demand strong breakout evidence", "detail": "A completed M5 candle needs 0.90 relative tick activity, a body covering at least 75% of its range, a 0.015 daily-ATR boundary buffer and agreement with session VWAP."},
            {"title": "Wait for a controlled retest", "detail": "Up to three completed M5 candles may return to the broken opening-range edge. A retest tolerance above 0.25 range or pre-retest excursion above 0.60 range cancels the setup."},
            {"title": "Apply the time-direction schedule", "detail": "Both directions are allowed from 10:00-10:29 New York, only longs from 10:30-10:59, and only shorts from 11:00 until the 11:30 entry cutoff."},
            {"title": "Target 2R and protect at 1R", "detail": "The stop sits beyond the opposite range boundary with a 0.05 range buffer, advances to break-even at +1R and targets 2R. The BAT-selected equity risk defaults to 1%, and exposure closes by 15:55 New York."},
        ],
        "risk_note": "The exact last-year report returned 1.54% with PF 1.53, 60.00% wins and 2.73% drawdown, but only five trades occurred. The broader 2020-2026 context returned 18.70% with PF 2.16 over fifty-three trades; that longer sample is context rather than untouched one-year proof.",
        "price": 449,
        "accent": "mint",
        "featured": False,
    },
    "US100 ORB 0.5R": {
        "strategy": "Selective New York opening-range retest",
        "tagline": "A high-selectivity US100 ORB using relative tick volume, VWAP, candle quality and a fixed 0.5R target.",
        "description": "The active USTEC M5 preset builds the first 30 minutes of the New York cash session, waits for a qualified breakout and accepts an entry only when the next closed M5 candle retests the broken boundary. It deliberately trades infrequently in exchange for a historically high closed-trade win rate.",
        "session": "09:30-11:30 New York / M5",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the selected 0.5R preset, optimization constraints and native MT5 validation reports were reviewed together.",
        "logic": [
            {"title": "Build the 30-minute New York opening range", "detail": "The EA measures the USTEC high, low and broker tick activity from 09:30 through 10:00 New York time, with automatic US daylight-saving and live broker-server conversion."},
            {"title": "Reject weak or abnormal opening sessions", "detail": "Opening activity must reach 0.60 of its 20-session median and opening-range width must remain between 0.05 and 0.35 of the historical daily ATR, removing very quiet and unusually expanded opens."},
            {"title": "Demand a strong volume-backed breakout", "detail": "A completed M5 breakout candle needs at least 0.70 relative tick volume, a real body covering at least 75% of its range, a small daily-ATR boundary buffer and directional agreement with session VWAP."},
            {"title": "Enter only on the immediate retest", "detail": "The selected preset allows one closed M5 retest bar after the breakout. Price must return to the broken range edge without exceeding the configured pre-retest excursion or tolerance limits."},
            {"title": "Apply the time-direction schedule", "detail": "Both directions are permitted from 10:00 to 10:29 New York, only longs from 10:30 to 10:59, and only shorts from 11:00 until the 11:30 entry cutoff."},
            {"title": "Risk to the opposite range and target 0.5R", "detail": "The stop is placed beyond the opposite opening-range boundary with a five-percent range buffer, excessive ATR-sized stops and wide spreads are rejected, take profit is 0.5R, and exposure is closed by 15:55 New York."},
        ],
        "risk_note": "The BAT version uses the user's selected equity-risk percentage and disables the research-only USD 300 fixed-risk override; pressing Enter defaults to 1%. The exact one-year comparison used 1% risk; a smaller shared portfolio risk is appropriate when several EAs run together.",
        "price": 449,
        "accent": "mint",
        "featured": True,
    },
    "US100 ORB 2R": {
        "strategy": "Selective New York opening-range retest",
        "tagline": "The higher-payoff US100 ORB variant, targeting 2R after a volume- and VWAP-qualified retest.",
        "description": "The active USTEC M5 preset builds the first 30 minutes of the New York cash session, waits for a strong breakout and permits up to three completed M5 candles for a retest entry. It uses the same selective time-direction schedule as the 0.5R edition, but demands stronger breakout activity and manages the position toward a 2R target.",
        "session": "09:30-11:30 New York / M5",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the V3 2R preset and its native MT5 validation reports were reviewed together.",
        "logic": [
            {"title": "Build the 30-minute New York opening range", "detail": "The EA measures the USTEC high, low and broker tick activity from 09:30 through 10:00 New York time, using automatic US daylight-saving and live broker-server conversion."},
            {"title": "Reject weak or abnormal opening sessions", "detail": "Opening activity must reach 0.60 of its 20-session median and range width must remain between 0.05 and 0.35 of the historical daily ATR, excluding unusually quiet or expanded opens."},
            {"title": "Demand the stronger 2R breakout threshold", "detail": "A completed M5 breakout candle needs at least 0.90 relative tick volume, a body covering at least 75% of its range, a daily-ATR boundary buffer and directional agreement with session VWAP."},
            {"title": "Allow a measured three-bar retest window", "detail": "After the qualified breakout, as many as three completed M5 candles may retest the broken opening-range edge, but excessive pre-retest excursion or a tolerance violation cancels the setup."},
            {"title": "Apply the selective time-direction schedule", "detail": "Both directions are permitted from 10:00 to 10:29 New York, only longs from 10:30 to 10:59, and only shorts from 11:00 until the 11:30 entry cutoff."},
            {"title": "Protect at 1R and target 2R", "detail": "The stop starts beyond the opposite range boundary with a five-percent buffer, moves to break-even at 1R, targets 2R, rejects excessive stop or spread conditions and closes exposure by 15:55 New York."},
        ],
        "risk_note": "Dynamic equity risk controlled by the installer's adaptive percentage, defaulting to 1%. The 2R and 0.5R editions can signal on the same session, so their combined risk must be treated as additive.",
        "price": 449,
        "accent": "cyan",
        "featured": True,
    },
    "US100 Fabio ORB 1R": {
        "strategy": "Direct long-only New York opening-range breakout",
        "tagline": "A volatility-targeted US100 break of the first 30 New York minutes, protected at the range low and targeting 1R.",
        "description": "The active USTEC M5 preset is the literal, conservative version of the Fabio opening-range idea. It builds the 09:30-10:00 New York range, waits for a completed M5 close above that range, then opens one long with the opposite range boundary as its stop and an equal-distance target.",
        "session": "09:30-15:00 New York / M5",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact literal BAT preset and the native MT5 Every Tick report were reviewed together.",
        "logic": [
            {"title": "Build the first 30 New York minutes", "detail": "The EA measures the USTEC high and low from 09:30 through 10:00 New York time on M5 data. US daylight-saving rules are calculated internally and live server offset can be detected automatically."},
            {"title": "Wait for a completed close above the range", "detail": "After 10:00, a fully closed M5 candle must finish above the opening-range high. The literal preset does not require a green breakout candle and applies no additional point buffer."},
            {"title": "Enter one long on the next evaluation", "detail": "The selected configuration is long-only and submits a market buy after the completed breakout is detected. It permits no second entry on the same New York trading date."},
            {"title": "Size from current equity", "detail": "Volume is calculated from the distance between market entry and the opening-range low. The BAT installer rewrites the active risk percentage for the detected account, defaulting to 1%."},
            {"title": "Use the range low and a 1R target", "detail": "The initial stop is placed at the opening-range low with no extra stop buffer. Take profit is set one initial-risk distance above entry, producing a nominal 1:1 reward-to-risk target before costs and slippage."},
            {"title": "Enforce time and execution controls", "detail": "Entries are limited to weekdays and breakout closes before the 15:00 New York cutoff. The EA rejects spread above 10% of stop distance, closes remaining exposure at 15:00 and converts server time independently of the VPS clock."},
        ],
        "risk_note": "Dynamic equity risk from entry to the opening-range low, defaulting to 1% in the installer. Gap, slippage and broker stop execution can exceed the planned amount; the largest loss in the latest $10,000 test was $264.09.",
        "price": 449,
        "accent": "amber",
        "featured": True,
    },
    "ATR Candle Breakout": {
        "strategy": "Large-candle momentum",
        "tagline": "Trades exceptionally large H1 gold candles that finish near their directional extreme.",
        "description": "This vendor EA is available only as a compiled EX5. Its manual and active inputs show a closed-candle momentum model: a candle must be unusually large versus ATR, have enough real body and finish near its high or low. Internal source-level implementation details cannot be independently inspected in this package.",
        "session": "H1 / time filter disabled",
        "logic_audit": "Input-audited binary",
        "logic_audit_note": "The vendor manual and exact BAT preset were reviewed. No MQ5 source exists locally, so claims are limited to documented behavior and visible inputs.",
        "logic": [
            {"title": "Scan each closed H1 candle", "detail": "The active signal timeframe is H1 and its volatility baseline is ATR over 250 bars."},
            {"title": "Demand an extreme expansion", "detail": "A signal candle must be at least 2.5 times ATR and its real body must occupy at least 20% of the full high-low range."},
            {"title": "Require a strong directional close", "detail": "A bullish candidate must finish near its own high and a bearish candidate near its own low; the permitted distance is 25% of candle range. Trend, higher-timeframe ATR, time-of-day and support/resistance filters are all disabled in the active preset."},
            {"title": "Enter in the expansion direction", "detail": "The vendor manual defines buys from qualified bullish candles and sells from qualified bearish candles. Because the product is EX5-only, the exact order-call timing cannot be source-audited here."},
            {"title": "Use percentage-of-price exits", "detail": "Stop loss is 0.5% of entry price and take profit is 2.0% of entry price, producing a nominal 4:1 reward-to-risk distance before spread and slippage. Trailing stop is disabled."},
            {"title": "Size from a fixed cash-risk input", "detail": "The EA itself consumes a fixed account-currency risk amount. The installer rewrites that amount from the risk selected in the BAT; it does not continuously compound with equity unless reinstalled."},
        ],
        "risk_note": "The BAT-selected percentage of the detected balance is expressed as a fixed cash-risk input, defaulting to 1%. It is not continuously recalculated from live equity inside the compiled EA.",
        "price": 399,
        "accent": "amber",
        "featured": True,
    },
    "AAA Final Asia Breakout": {
        "strategy": "Asia-range close and retest breakout",
        "tagline": "An H1 gold breakout of the 00:00-08:00 UTC range with a same-candle threshold retest.",
        "description": "The source code measures the 00:00-08:00 UTC range and accepts only an H1 candle that closes outside a buffered boundary while its wick touches that threshold. The retained build then checks a no-lookahead D1 Markov regime before permitting the directional entry.",
        "session": "08:00-13:59 UTC / H1",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The strategy wrapper, shared execution engine and exact active preset were reviewed.",
        "logic": [
            {"title": "Measure the Asian range", "detail": "M15 bars from 00:00 through 07:59 UTC define the current day's high, low and midpoint. Broker time is converted to UTC; the preset uses the EET/EEST tester clock model."},
            {"title": "Evaluate only the London transition", "detail": "Signals are checked on each new H1 bar from 08:00 through 13:59 UTC. The EA allows no new setup if it already has exposure or has opened a trade that UTC day."},
            {"title": "Require a buffered close and touch", "detail": "The buffer is 3% of the Asian range. A buy requires the closed H1 candle above range high plus buffer while that candle's low touched the threshold. A sell is the mirror condition below range low."},
            {"title": "Apply the completed-D1 Markov gate", "detail": "Before entry, the EA labels completed D1 returns over forty bars as Bull, Sideways or Bear and builds transition probabilities without counting the newest transition. Longs require Bull-minus-Bear probability above +0.05; shorts require it below -0.05."},
            {"title": "Enter with a midpoint stop", "detail": "The order is sent at market after the H1 confirmation and regime direction both pass. Long and short stops use the Asian range midpoint, while volume targets 1% of current equity."},
            {"title": "Target 3R and trail after +2R", "detail": "Take profit is three times the entry-to-midpoint risk. After price reaches +2R, the stop follows at a distance of 0.5R; these hard-coded trailing values override the generic shared inputs."},
        ],
        "risk_note": "Dynamic 1% of current equity with one trade per UTC day. The embedded D1 Markov gate uses a 40-bar return window, 5% state threshold and 0.05 direction gate. Actual loss can exceed plan if price gaps through the midpoint stop.",
        "price": 249,
        "accent": "violet",
    },
    "Go Long": {
        "strategy": "Timed daily long",
        "tagline": "A deliberately simple US30 system that buys once at a fixed server time and exits the same day.",
        "description": "The active preset has no directional indicator or new-high requirement: it is a time-based long-only strategy. The vendor binary opens a buy at the configured server time, protects it with a percentage stop and closes it near the end of the server day.",
        "session": "01:05-23:50 broker server time",
        "logic_audit": "Input-audited binary",
        "logic_audit_note": "The vendor manual and active preset were reviewed. The EX5 has no local MQ5 source, so undocumented internal checks cannot be independently verified.",
        "logic": [
            {"title": "Long side only", "detail": "The vendor manual states that the EA only opens buy positions, intended for markets such as index CFDs that have a persistent upward tendency."},
            {"title": "Enter at 01:05 server time", "detail": "The active preset opens at 01:05 broker server time. 'Wait for new day high' is OFF, so a new daily high is not required before entry."},
            {"title": "Use no profit target", "detail": "Take-profit calculation is OFF. Break-even and classic trailing-stop calculation are also OFF."},
            {"title": "Protect with a percentage stop", "detail": "The base preset stop is 0.76430161% of the position's open price. The auto installer recalculates the exact hard-stop percentage for the connected broker contract when targeting its planned cash risk."},
            {"title": "Close at 23:50 server time", "detail": "Same-day time closure is enabled, so any surviving US30 position is instructed to close at 23:50 broker server time."},
            {"title": "Deploy with broker-specific size", "detail": "The installer forces fixed-volume mode and writes a broker-specific lot size plus hard stop designed around approximately 1% of detected balance at deployment."},
        ],
        "risk_note": "Approximately 1% of detected balance at installation, implemented with a fixed lot and broker-specific hard-stop percentage. It is not continuous equity-percent sizing inside the compiled EA.",
        "price": 179,
        "accent": "blue",
    },
    "AAA Final EMA3": {
        "strategy": "Three-EMA trend breakout",
        "tagline": "An H4 five-bar breakout gated by EMA 20/50 alignment and the slope of EMA 200.",
        "description": "EMA3 combines trend alignment with a five-bar structure break. It waits for the completed H4 candle to close beyond the previous five bars while EMA 20, EMA 50 and a rising or falling EMA 200 agree with the direction. The selected exit was re-optimized with a locked year, an exact three-year MT5 run and Monte Carlo testing.",
        "session": "All sessions / H4",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The wrapper, shared strategy engine and active XAUUSD H4 preset were reviewed.",
        "logic": [
            {"title": "Define the five-bar structure", "detail": "At every new H4 bar, the EA finds the highest high and lowest low of the five candles before the just-closed signal candle."},
            {"title": "Require the three-EMA trend", "detail": "For a buy, EMA 20 must be above EMA 50, the signal close must be above EMA 200, and EMA 200 must be above its value six H4 bars earlier. A sell uses the exact inverse."},
            {"title": "Demand a closing breakout", "detail": "The just-closed H4 candle must finish above the five-bar high for a long or below the five-bar low for a short. A wick through the level without a closing break is insufficient."},
            {"title": "Enter at market", "detail": "The order is submitted at the first tick of the new H4 bar, provided there is no existing position or pending order for this EA and symbol."},
            {"title": "Use the opposite five-bar extreme", "detail": "Long stop loss is the five-bar low; short stop loss is the five-bar high. Take profit is 1.7 times the entry-to-stop distance."},
            {"title": "Protect at 60% progress", "detail": "Native R-trailing is disabled. After a newly completed M15 candle closes at least 60% of the original entry-to-target path, the stop moves to lock 20% of that path. Each trade is dynamically sized to the risk chosen by the BAT, defaulting to 1% of equity."},
        ],
        "risk_note": "Dynamic risk chosen by the installer, default 1% of current equity, with the stop at the opposite five-bar extreme and a 1.7R target. Wide H4 structures produce smaller volume and gaps can exceed the planned loss.",
        "price": 349,
        "accent": "lime",
        "featured": True,
    },
    "AAA Final XAU Weakness": {
        "strategy": "Repeated-level continuation breakout",
        "tagline": "M30 pending breakouts from equal highs or lows after a strong directional impulse.",
        "description": "The optimized XAUUSD build searches recent M30 bars for two similar highs or two similar lows and, after a qualifying prior impulse, prepares a continuation stop through that repeated level. Standard runs the pattern directly; Full Safe applies the independently audited no-lookahead completed-D1 Markov direction gate to the same M30/4R configuration.",
        "session": "All sessions / M30",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The wrapper, shared strategy engine, corrected reward/risk and trailing wiring, exact selected preset, native MT5 development/locked/three-year reports and Monte Carlo audit were reviewed together.",
        "logic": [
            {"title": "Find a repeated M30 level", "detail": "The EA scans the latest 30 completed M30 bars for two highs or two lows separated by at least four candles. The two prices must be within 0.20 ATR(14). If both exist, the source checks the equal-high case first."},
            {"title": "Confirm the preceding impulse", "detail": "A repeated high is tradable only after an upward move of at least 2 ATR; a repeated low requires a downward move of at least 2 ATR. The impulse is measured from older bars around the first level."},
            {"title": "Place the continuation stop", "detail": "The pending entry sits 0.05 ATR beyond the repeated level. Standard accepts both directions directly; Full Safe additionally requires the forty-bar completed-D1 Markov Bull-minus-Bear probability to exceed +0.05 for a buy or fall below -0.05 for a sell."},
            {"title": "Anchor the stop to the intervening range", "detail": "The long stop goes below the lowest price in the pattern range by 0.05 ATR; the short stop goes above its highest price by the same buffer. The selected target is 4R."},
            {"title": "Expire stale orders", "detail": "The pending order expires after eight M30 bars, or four hours. No new setup is evaluated while that order or its resulting position remains active; same-magic cleanup removes any stray pending order after a fill."},
            {"title": "Protect at 50% progress", "detail": "Native R-trailing is disabled. After a newly completed M15 candle closes at least 50% of the original entry-to-target path, the stop moves to lock 20% of that path. The BAT-selected risk defaults to the validated 1% of equity."},
        ],
        "risk_note": "Dynamic risk chosen by the installer, defaulting to the validated 1% of current equity per setup, with a structure stop, 4R target and Dynamic 50/20 protection. Standard disables Markov; Full Safe uses locked 40-bar / 5% / 0.05 inputs. Gaps and slippage can exceed planned risk.",
        "price": 149,
        "accent": "red",
    },
    "Nasdaq Overnight": {
        "strategy": "Overnight anomaly",
        "tagline": "Long Nasdaq after a negative New York close, then exit one minute before the next cash open.",
        "description": "This is the optimized active long-only close-to-open configuration. It reconstructs the New York cash session from M1 data, compares today's 16:00 close with the previous trading day's 16:00 close, and buys only when that return is negative. A separately saved conservative preset adds a 1% negative-day threshold, 3% emergency stop, 0.75R target and Dynamic 50/20 management, but the larger-sample current version remains the deployed recommendation.",
        "session": "16:00 to 09:29 New York",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, the exact active USTEC preset, 40 Standard optimization tests, four native Safe validations and the untouched locked-year reports were reviewed, including exact US daylight-saving conversion.",
        "logic": [
            {"title": "Rebuild the completed cash session", "detail": "The EA reads 09:30-15:59 New York M1 bars and requires at least 300 session bars. It also finds the prior trading day's 15:59 close."},
            {"title": "Require a negative close-to-close day", "detail": "The active definition is today's 16:00 cash close below the previous trading day's close. Threshold is 0%, so any strictly negative return qualifies."},
            {"title": "Buy just after 16:00 New York", "detail": "One long may be opened during the ten-minute window beginning at the cash close. The active SET explicitly fixes the entry at 16:00 New York; Friday entries are allowed and may be held through the weekend."},
            {"title": "Use an emergency stop only", "detail": "The protective stop is 2% below entry price. There is no take profit; the position remains exposed to overnight gaps."},
            {"title": "Exit before the next cash open", "detail": "A position from an earlier New York date is closed beginning at 09:29, with a 31-minute permitted exit window."},
            {"title": "Handle account and clock differences", "detail": "Lot size targets the risk selected by the BAT, defaulting to the validated 1% of current equity against the 2% emergency stop. Broker-to-UTC offset and exact modern New York DST rules are resolved automatically in live trading."},
        ],
        "risk_note": "Every BAT asks for risk before installation; the default and validated value is 1% of current equity to a stop 2% below entry. Weekend and overnight gaps can bypass that stop, so realized risk is not capped at exactly 1%. The separate conservative preset is research-only. Native validation showed that the Markov gate reduced the locked sample from 72 to 30 trades and the exact three-year return from 7.81% to 4.14%, so Full Safe deliberately preserves this EA's Standard inputs.",
        "price": 229,
        "accent": "indigo",
    },
    "Turnaround Tuesday": {
        "strategy": "Calendar effect",
        "tagline": "A long-only Monday-to-Tuesday Nasdaq hold with a daily 9-period moving-average gate.",
        "description": "The vendor strategy buys early-week setbacks for a Tuesday recovery. In the active preset it can open a long on Monday at 01:05 server time, subject to a D1 9-period simple moving-average filter, and closes on Tuesday at 23:50.",
        "session": "Monday 01:05 to Tuesday 23:50 server time",
        "logic_audit": "Input-audited binary",
        "logic_audit_note": "The vendor manual and active preset were reviewed. No MQ5 source exists locally, so the exact MA comparison tick and any undocumented checks cannot be source-audited.",
        "logic": [
            {"title": "Long-only early-week setup", "detail": "The vendor manual defines only buy trades, intended to capture a recovery after an early-week setback."},
            {"title": "Apply the daily MA gate", "detail": "The active filter is a 9-period simple moving average on D1, calculated from the open price. The manual states that price must be on the correct long side of that average."},
            {"title": "Enter Monday at 01:05", "detail": "Open day is Monday and the configured entry time is 01:05 broker server time. Waiting for a new daily high is disabled."},
            {"title": "Hold without a profit target", "detail": "Take profit, break-even and classic trailing stop are all disabled in the active preset."},
            {"title": "Use a hard percentage stop", "detail": "The base hard stop is 0.75241337% of entry price. During automatic deployment the installer can rewrite the percentage for the broker contract and chosen fixed lot."},
            {"title": "Exit Tuesday at 23:50", "detail": "Any surviving position is instructed to close at 23:50 server time on Tuesday. The installer chooses a fixed lot and stop intended to approximate 1% of detected balance at installation."},
        ],
        "risk_note": "Approximately 1% of detected balance at installation via broker-specific fixed lot and hard-stop percentage. The compiled EA does not continuously resize from current equity.",
        "price": 149,
        "accent": "orange",
    },
    "AAA Final US100 Weakness": {
        "strategy": "10:00 reference-pair reversal",
        "tagline": "Contrarian USTEC OCO orders around the 09:15 candle after the 10:00 New York candle closes.",
        "description": "The active implementation is a precise time-and-reference pattern. It compares the direction of the M15 candle opened at 10:00 New York with the 09:15 candle and the 03:00-08:00 New York range, then places two opposite-direction pending entries around the 09:15 high and low.",
        "session": "10:15-12:00 New York / M15",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "The wrapper, shared strategy engine and active USTEC M15 preset were reviewed.",
        "logic": [
            {"title": "Capture two reference structures", "detail": "The EA records the exact 09:15 New York M15 candle high/low and the full 03:00-08:00 New York session high/low."},
            {"title": "Evaluate the 10:00 candle after it closes", "detail": "At the new bar around 10:15, the just-closed candle must have opened at exactly 10:00 New York. The strategy is allowed only once per UTC day and only when no order or position already exists."},
            {"title": "Fade bullish strength", "detail": "If the 10:00 candle is bullish and the early-session high is above the 09:15 high, the EA prepares shorts: a sell limit at the 09:15 high and a sell stop at the 09:15 low."},
            {"title": "Fade bearish weakness", "detail": "If the 10:00 candle is bearish and the early-session low is below the 09:15 low, the EA prepares longs: a buy limit at the 09:15 low and a buy stop at the 09:15 high."},
            {"title": "Use a common session-extreme stop", "detail": "Both short orders share the 03:00-08:00 high as stop; both long orders share that session's low. Each target is 1.7R and each order receives half of the 1% risk budget."},
            {"title": "Operate as OCO until noon", "detail": "Orders expire at 12:00 New York. Once one becomes a position, the remaining pending order is deleted. The active code has no trailing stop even though generic trailing fields appear in the input panel."},
        ],
        "risk_note": "Two pending orders are each sized at 0.5% of current equity, for 1% planned setup risk. OCO cleanup begins after a fill, so fast gaps or simultaneous fills can produce different realized exposure.",
        "price": 149,
        "accent": "pink",
    },
    "Engineered Liquidity XAU": {
        "strategy": "Trend-aligned engineered-liquidity reclaim",
        "tagline": "XAUUSD H1 swing sweeps reclaimed in the direction of the completed D1 EMA trend.",
        "description": "The gold build waits for price to run a confirmed H1 swing against the dominant completed-D1 trend, reclaim that level with a directional candle, and then targets opposing H1 liquidity only when the available structural reward is acceptable.",
        "session": "All sessions / H1 execution",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, exact locked XAUUSD preset and native development/locked MT5 reports were reviewed together.",
        "logic": [
            {"title": "Establish the completed-D1 trend", "detail": "The last completed D1 close must be above EMA20 with EMA20 above EMA50 and rising for longs, or below EMA20 with EMA20 below EMA50 and falling for shorts."},
            {"title": "Find the nearest confirmed swing", "detail": "The EA searches the latest 32 completed H1 bars for a two-bars-left/two-bars-right confirmed low in an uptrend or high in a downtrend. The signal candle itself cannot define that swing."},
            {"title": "Require a sweep and reclaim", "detail": "The completed H1 signal candle must pierce the swing by 0.01 to 0.75 ATR(14), close back through the level and finish in the intended direction. The improved gold preset does not require a close through the entire prior candle."},
            {"title": "Place a structural stop", "detail": "For a long, the stop goes below the sweep candle low by 0.08 ATR; for a short it goes above the sweep high by the same buffer. Broker minimum stop and freeze distances are enforced."},
            {"title": "Target opposing liquidity", "detail": "The target is the highest high or lowest low among the preceding 32 completed H1 bars. The improved entry is rejected unless that target offers between 2R and 8R after the live spread-adjusted market entry."},
            {"title": "Limit exposure and holding time", "detail": "The preset permits both directions, at most two entries per broker day and one open position for this symbol/magic. Any survivor is closed after 24 H1 bars."},
        ],
        "risk_note": "Default deployment risks 1% of current equity. Dynamic Config can instead use an exact fixed USD amount for this EA. Spread must remain at or below 0.08 of H1 ATR; gaps and slippage can exceed planned risk.",
        "price": 349,
        "accent": "gold",
        "featured": True,
    },
    "Engineered Liquidity BTC": {
        "strategy": "Trend-aligned engineered-liquidity reclaim",
        "tagline": "BTCUSD M30 swing reclaims filtered by the completed H4 EMA trend.",
        "description": "The crypto build applies the same objective swing-sweep framework on M30 with an H4 trend filter and now requires a complete displacement close. That rule improved both examined years, but it was adopted after reviewing the original locked failure, so this remains a forward-test candidate rather than an independently validated edge.",
        "session": "Continuous crypto market / M30 execution",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, exact locked BTCUSD preset and native development/locked MT5 reports were reviewed together.",
        "logic": [
            {"title": "Establish the completed-H4 trend", "detail": "Longs require the last completed H4 close above a rising EMA20 with EMA20 above EMA50; shorts require the exact inverse."},
            {"title": "Find confirmed M30 liquidity", "detail": "The EA searches the latest 36 completed M30 bars for the nearest two-sided confirmed swing low in an uptrend or swing high in a downtrend."},
            {"title": "Demand a displacement reclaim", "detail": "A completed M30 candle must sweep the selected swing by 0.01 to 0.75 ATR(14), close back through it, finish in the intended direction and close beyond the prior M30 candle's opposite extreme."},
            {"title": "Use sweep structure for the stop", "detail": "The initial stop is beyond the sweep candle extreme with a 0.08 ATR buffer and is widened only for broker minimum-distance rules."},
            {"title": "Target the opposite 36-bar extreme", "detail": "The target is the opposing high or low in the previous 36 completed M30 bars. Trades outside the 1.5R-to-8R structural reward window are rejected."},
            {"title": "Bound frequency and duration", "detail": "Both directions are enabled, no more than two entries are allowed per broker day, and open exposure is closed after 48 M30 bars if neither stop nor target has resolved it."},
        ],
        "risk_note": "Default deployment risks 1% of current equity; Dynamic Config can use exact fixed USD risk for this EA. The displacement improvement is post-hoc and must be demo/forward-tested before any live decision.",
        "price": 149,
        "accent": "orange",
    },
    "Nasdaq 5M Candle Momentum": {
        "strategy": "US-open five-minute momentum",
        "tagline": "Let the completed 09:30 Nasdaq candle choose direction, then hold for the validated 2.5R objective.",
        "description": "After the 09:30-09:35 New York M5 candle closes, this EA buys above EMA 12 or sells below EMA 12. The optimized version uses a 4x ATR initial stop, a fixed 2.5R target, no trailing stop, and closes any unresolved position at 15:55 New York.",
        "session": "09:30 New York",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable MQ5 source, all development configurations, the frozen untouched year and exact three-year Every Tick MT5 reports were reviewed. ATR(14) is the volatility indicator and risk remained fixed at 1%.",
        "logic": [
            {"title": "Wait for the opening candle to finish", "detail": "The signal is evaluated only when the closed M5 candle is timestamped 09:30 New York, meaning entry occurs just after the 09:30-09:35 bar has completed. Weekends are rejected and New York DST is calculated automatically."},
            {"title": "Make one EMA decision", "detail": "Close above the 12-period M5 EMA triggers a long; close below it triggers a short. Equality produces no trade. Both directions are active and only one entry is allowed per New York date."},
            {"title": "Set a 4x ATR initial stop", "detail": "The initial stop is four times M5 ATR(14) from entry, widened only when required by the broker's minimum stop or freeze distance. Volume is calculated so that the planned loss at that stop is exactly 1% of current equity."},
            {"title": "Target 2.5R", "detail": "The take profit is placed 2.5 times the original entry-to-stop distance from entry. The exit objective was selected on the development window before the untouched locked year was opened."},
            {"title": "Leave the position untrailed", "detail": "ATR trailing, Dynamic 50/20 and breakeven are disabled in the selected configuration. The full 2.5R payoff is preserved instead of tightening the stop during normal opening-session volatility."},
            {"title": "Finish the position by 15:55", "detail": "The position exits through the original stop, the 2.5R target, or a forced close at 15:55 New York. Only one entry is permitted per New York date and New York daylight-saving changes are handled automatically."},
        ],
        "risk_note": "Every BAT applies the user's selected equity-risk percentage to the 4x ATR(14) initial stop; pressing Enter defaults to the validated 1%. The target is fixed at 2.5R and any unresolved position is closed at 15:55 New York, but gaps and slippage can still exceed planned risk.",
        "price": 499,
        "accent": "cyan",
        "featured": True,
    },
    "AAA Final News Pulse - NFP CPI FOMC - LONG ONLY ROBUST 60s": {
        "strategy": "Scheduled news momentum",
        "tagline": "One long-only XAUUSD buy-stop placed 30 seconds before selected US macro releases.",
        "description": "The active preset is not a two-sided straddle. It watches NFP, CPI and FOMC in MT5's USD economic calendar, waits for a fresh broker-stamped quote, and places only a buy stop shortly before release. It has no take profit and closes all remaining exposure 60 seconds after the event.",
        "session": "NFP, CPI and FOMC",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable News Pulse v2.11 source and the active long-only 60-second BAT preset were reviewed. Live and tester event discovery are intentionally different.",
        "logic": [
            {"title": "Find only target USD events", "detail": "Live trading scans the native MT5 economic calendar for non-private Nonfarm Payrolls, Consumer Price Index, FOMC statements or Federal Reserve rate decisions. It looks ahead eight days and refreshes the cached event every 300 seconds."},
            {"title": "Anchor timing to the broker", "detail": "Calendar timestamps and quote timestamps are both broker-server time. VPS local timezone is ignored. Placement is blocked unless the terminal is connected and the latest quote arrived within five seconds."},
            {"title": "Place one buy stop at T-30 seconds", "detail": "During the final 30 seconds before release, the active long-only preset places a buy stop 6.0 XAUUSD price units above Ask. The sell side is disabled."},
            {"title": "Attach a 6.0-unit hard stop", "detail": "Stop loss is 6.0 XAUUSD price units below the pending entry. Volume targets 1% of current equity to that stop. No take profit is attached."},
            {"title": "Trail after +1.5R", "detail": "Once favorable movement reaches 9.0 price units, the EA may ratchet the stop to 15.0 price units behind current Bid. Because that trail is wider than the trigger gain, it improves the original stop only as price moves farther."},
            {"title": "Force a short event lifecycle", "detail": "At T+60 seconds the EA deletes any unfilled pending order and closes any open News Pulse position. State is stored by account, symbol and magic number so the lifecycle can recover after a terminal restart."},
        ],
        "risk_note": "Dynamic 1% of current equity to the 6.0-unit stop before release. News gaps, slippage, rejected modifications or a market that jumps over the stop can cause materially larger realized loss.",
        "price": 549,
        "accent": "yellow",
        "featured": True,
    },
}


def _news_pulse_meta(symbol: str, entry: str, stop: str, trail: str) -> dict[str, Any]:
    return {
        "strategy": "Scheduled two-sided news momentum",
        "tagline": f"A two-sided {symbol} event breakout with a source-locked 1.50% maximum planned exposure.",
        "description": f"This {symbol} M1 configuration watches NFP, CPI and FOMC in MT5's USD economic calendar. Thirty seconds before release it places both a buy stop and a sell stop using the market-specific optimized geometry, then removes pending exposure and closes positions sixty seconds after the event.",
        "session": "NFP, CPI and FOMC",
        "logic_audit": "Source-code verified",
        "logic_audit_note": "Readable News Pulse v2.15 source and the exact hard-risk SET were checked against independent native MT5 runs using official BLS/Federal Reserve release times. The research calendar lookup matched the untouched six-month controls trade for trade. The v2.15 live gate only accepts high-impact primary CPI/Core CPI names, preventing secondary Median CPI and inflation-expectation releases from creating another straddle. Live event discovery is unchanged; historical real-tick coverage is disclosed separately.",
        "logic": [
            {"title": "Find only primary high-impact USD events", "detail": "Live trading scans MT5's native USD calendar but accepts only high-impact target releases. CPI must begin with CPI, Core CPI, Consumer Price Index or Core Consumer Price Index, so Cleveland Fed Median CPI and inflation-expectation events cannot qualify. The schedule is cached eight days ahead and refreshed every 300 seconds. Strategy Tester uses a coverage-checked UTC calendar and version 2.15 rejects missing or out-of-range schedules. The current website history uses independently run 6-month, 1-year, 3-year and 5-year windows with official BLS/Federal Reserve release timestamps; real-tick coverage is disclosed separately."},
            {"title": "Anchor timing to broker data", "detail": "Calendar timestamps and quote timestamps share broker-server time. VPS local timezone is ignored, and placement is blocked unless MT5 is connected and a broker-stamped quote arrived during the preceding five seconds."},
            {"title": "Place both breakout stops", "detail": f"During the final thirty seconds before release, the EA places a buy stop {entry} above Ask and a sell stop {entry} below Bid on {symbol}. Buy and sell use independent pending orders and a symbol-specific magic number."},
            {"title": "Hard-lock maximum planned risk", "detail": f"Each pending direction uses a maximum base risk of 0.75% equity to its {stop} initial stop. Recommended Adaptive may taper that base lower, but the BAT cannot raise it; combined planned event exposure is therefore no more than 1.50% before gaps and slippage."},
            {"title": "Retain the optimized native trail", "detail": f"After favorable movement reaches 1.5R, the native manager may tighten the stop using a {trail} trailing distance. Dynamic 50/20 and the experimental regime gate are disabled because this exact configuration was validated without them."},
            {"title": "Force the event lifecycle to finish", "detail": "At sixty seconds after release, the EA deletes any unfilled pending order and closes any remaining News Pulse position. Account, symbol and magic-number state allow that lifecycle to recover after a terminal restart."},
        ],
        "risk_note": "Risk is not controlled by the BAT prompt for this EA. Version 2.15 caps base risk at 0.75% per pending stop and 1.50% maximum planned event exposure; Recommended Adaptive may reduce it. News gaps, spread expansion, slippage, rejections or a market jumping over the stop can still produce a larger realized loss.",
        "price": 549,
        "accent": "yellow",
        "featured": symbol in {"XAUUSD", "XAGUSD", "BTCUSD"},
    }


# Replace the retired long-only product description with the three exact
# user-approved, hard-risk market configurations.
CORE_META.pop("AAA Final News Pulse - NFP CPI FOMC - LONG ONLY ROBUST 60s", None)
CORE_META.update(
    {
        "News Pulse XAU": _news_pulse_meta("XAUUSD", "6.0 price units", "6.0-unit", "15.0-unit"),
        "News Pulse XAG": _news_pulse_meta("XAGUSD", "0.08 price units", "0.08-unit", "0.20-unit"),
        "News Pulse BTC": _news_pulse_meta("BTCUSD", "75 price units", "75-unit", "112.5-unit"),
    }
)


_orb_high_win_meta = dict(CORE_META["ORB Volume Profile"])
_orb_high_win_meta.update(
    {
        "strategy": "High-win New York opening-range breakout",
        "tagline": "The validated 0.75R version of the XAUUSD 15-minute New York ORB.",
        "description": "This separate XAUUSD M5 instance keeps the same validated 09:30-09:45 New York opening range and direct-breakout signal, but closes at 0.75R rather than 2.5R. The untouched one-year MT5 test returned 6.31% with PF 1.56, a 69.39% win rate, 3.10% maximum drawdown and 49 trades. Its exact three-year confirmation retained a 69.82% win rate over 169 trades.",
        "logic_audit_note": "Readable MQ5 source, the dedicated 0.75R SET, development and untouched locked-year tests, exact three-year MT5 Every Tick evidence and 10,000-path Monte Carlo were reviewed together.",
        "risk_note": "The BAT-selected percentage applies independently to this EA and defaults to 1% of current equity. Because the core 2.5R ORB can trigger from the same opening-range signal, running both at 1% can create approximately 2% combined planned exposure before slippage.",
        "price": 349,
        "featured": False,
    }
)
_orb_high_win_logic = [dict(step) for step in CORE_META["ORB Volume Profile"]["logic"]]
_orb_high_win_logic[4] = {
    "title": "Use the opposite range boundary as the stop",
    "detail": "The EA enters at market. Stop loss is beyond the opposite side of the opening range by 0.10 ATR; signals needing more than 2.0 ATR of stop distance are rejected. Take profit is the validated compact 0.75R objective and spread may not exceed 12% of the opening-range width.",
}
_orb_high_win_logic[5] = {
    "title": "Protect the compact target with Dynamic 50/20",
    "detail": "Risk defaults to 1% of current equity. After a completed M15 candle reaches halfway to the 0.75R target, the stop advances to lock 20% of that target path. The configured +1R break-even cannot activate before the 0.75R target, no second trade is allowed that New York date, and any survivor closes at 15:55 New York.",
}
_orb_high_win_meta["logic"] = _orb_high_win_logic
CORE_META["ORB Volume Profile High Win 0.75R"] = _orb_high_win_meta

_orb_volume_confirmed_meta = dict(CORE_META["ORB Volume Profile"])
_orb_volume_confirmed_meta.update(
    {
        "strategy": "Volume-confirmed New York opening-range breakout",
        "tagline": "A selective 2.5R XAUUSD ORB that requires stronger opening and breakout quote activity.",
        "description": "This separate XAUUSD M5 instance keeps the validated 09:30-09:45 New York range, 2.5R objective and Dynamic 50/20 management, but raises the opening relative-volume gate from 0.60 to 0.80 and the breakout gate from 0.80 to 1.10. Its untouched year returned 12.57% with PF 2.88, a 52.17% win rate, 2.92% maximum drawdown and 23 trades. The exact three-year confirmation returned 25.92% with PF 2.01 over 68 trades.",
        "logic_audit_note": "Readable MQ5 source, the dedicated stronger-volume SET, untouched locked-year test and exact three-year MT5 Every Tick confirmation were reviewed together.",
        "risk_note": "The BAT-selected percentage applies independently to this EA and defaults to 1% of current equity. It shares the same opening range with the core and high-win ORBs, so running all three at 1% can create approximately 3% combined planned exposure when their signals align.",
        "price": 399,
        "featured": False,
    }
)
_orb_volume_confirmed_logic = [dict(step) for step in CORE_META["ORB Volume Profile"]["logic"]]
_orb_volume_confirmed_logic[1] = {
    "title": "Demand stronger opening activity",
    "detail": "Opening-window tick volume must be at least 0.80 times the median activity of the same window across the previous twenty valid weekdays. This is broker quote activity rather than centralized exchange volume.",
}
_orb_volume_confirmed_logic[3] = {
    "title": "Demand a volume-confirmed M5 breakout",
    "detail": "During the next 120 minutes, a closed M5 candle must have at least a 55% body, at least 1.10 relative tick volume versus its prior twenty bars, and close beyond the range by 0.03 ATR in its own direction. Retest mode, VWAP and EMA trend filtering remain disabled.",
}
_orb_volume_confirmed_meta["logic"] = _orb_volume_confirmed_logic
CORE_META["ORB Volume Profile Volume Confirmed"] = _orb_volume_confirmed_meta

CORE_META["XAU Regime Switch"] = {
    "strategy": "Causal Markov trend / mean-reversion switch",
    "tagline": "A demo-stage XAUUSD model that changes behaviour instead of forcing one style into every regime.",
    "description": "This XAUUSD build uses completed D1 data to classify Bull, Bear and Sideways regimes without lookahead. Directional regimes enable the frozen H4 multi-horizon slow-trend setup; sufficiently persistent Sideways regimes enable the frozen M5 New York-overlap VWAP snapback setup. Native combined-EA history is now available, but the EA remains restricted to demo forward testing because its latest six-month slice is negative.",
    "session": "H4 trend all day / M5 VWAP 10:00-11:45 New York",
    "logic_audit": "Source-code verified",
    "logic_audit_note": "Readable combined MQ5 source compiled with zero errors and warnings. Its 5,380-configuration no-lookahead overlay screen, untouched locked year, mandatory XAG portability check, 10,000-path Monte Carlo audit and native MT5 Every Tick confirmation were reviewed together.",
    "logic": [
        {"title": "Classify the completed daily regime", "detail": "The EA compares the latest completed D1 close with the close forty trading days earlier. Moves above +2% are Bull, below -2% are Bear, and the middle band is Sideways; the current day is never used."},
        {"title": "Forecast persistence without lookahead", "detail": "A Laplace-smoothed three-state transition matrix is rebuilt from 126 historical transitions. The transition into the newest completed label is deliberately excluded before calculating Bull, Bear and Sideways probabilities."},
        {"title": "Trade slow momentum in directional regimes", "detail": "Bull or Bear regimes can activate the H4 one-, three- and six-month momentum vote when its direction agrees with the Markov probability signal and the completed close agrees with EMA100. The stop is 1.5 H4 ATR and the target is fixed at 6R."},
        {"title": "Trade VWAP snapback only in persistent Sideways regimes", "detail": "When the current state is Sideways and its next-state probability is at least 50%, the EA may fade a completed M5 two-deviation stretch back inside the 09:30 New York session VWAP bands. M5 ADX must be at or below 20."},
        {"title": "Use the frozen mean-reversion exit", "detail": "The VWAP leg trades only from 10:00 through 11:45 New York, permits one entry per session, uses a 1.5 M5 ATR stop and fixed 3R target, and closes any surviving VWAP position at 12:00 New York."},
            {"title": "Apply selected risk and enforce demo use", "detail": "Both legs share one unique magic number and cannot overlap. Volume uses OrderCalcProfit so the planned stop loss follows the percentage selected in the BAT; the EA still refuses to start on a real-money account while the recommended demo lock is enabled."},
    ],
    "risk_note": "Every BAT applies the user's selected equity-risk percentage; pressing Enter defaults to the validated 1%. Demo Only remains enabled. Native MT5 returned +29.28% over one year and +88.30% over three years, but the latest six months returned -4.95%; forward testing is required before reconsidering the real-account lock.",
    "price": 449,
    "accent": "purple",
    "featured": True,
}


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _extract_string(block: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*=\s*'([^']*)'", block)
    return match.group(1) if match else ""


def parse_installer_items() -> list[dict[str, Any]]:
    """Parse the literal portfolio entries from the active installer's Get-PortfolioItems."""
    if not INSTALLER_PATH.is_file():
        return list(_load_json(PUBLIC_CATALOG_MANIFEST)) if PUBLIC_CATALOG_MANIFEST.is_file() else []
    text = INSTALLER_PATH.read_text(encoding="utf-8-sig")
    start = text.index("$items = @(")
    end = text.index("\n    foreach ($item in $items)", start)
    section = text[start:end]
    blocks = re.findall(r"\[pscustomobject\]@\{(.*?)\n\s{8}\}(?:,|\s*$)", section, re.DOTALL | re.MULTILINE)
    items: list[dict[str, Any]] = []
    for block in blocks:
        label = _extract_string(block, "Label")
        if not label:
            continue
        period_match = re.search(r"\bPeriod\s*=\s*(\d+)", block)
        set_source = _extract_string(block, "SetSource")
        safe_set_source = _extract_string(block, "SafeSetSource")
        if not set_source and re.search(r"\bSetSource\s*=\s*\$atrSet", block):
            set_source = "ATR Candle Breakout EA\\RETEST PASSED 2026-08-07 - ATR Candle Breakout - XAUUSD H1 - 1pct.set"
        items.append(
            {
                "label": label,
                "canonical": _extract_string(block, "Canonical"),
                "period_minutes": int(period_match.group(1)) if period_match else 0,
                "expert": _extract_string(block, "Expert"),
                "expert_source": _extract_string(block, "ExpertSource"),
                "set_source": set_source,
                "safe_set_source": safe_set_source or None,
                "optional_symbol": bool(re.search(r"\bOptionalSymbol\s*=\s*\$true", block)),
                "supports_safe_filter": not bool(re.search(r"\bSupportsSafeFilter\s*=\s*\$false", block)),
                "recommended_safe_mode": bool(re.search(r"\bRecommendedSafe\s*=\s*\$true", block)),
                "recommended_dynamic_mode": bool(re.search(r"\bRecommendedDynamic\s*=\s*\$true", block)),
            }
        )
    if not items and PUBLIC_CATALOG_MANIFEST.is_file():
        return list(_load_json(PUBLIC_CATALOG_MANIFEST))
    if not items:
        raise RuntimeError(f"No portfolio items could be parsed from {INSTALLER_PATH}")
    return items


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _status_for(pf: float, return_pct: float, drawdown: float, trades: int) -> str:
    if pf >= 1.20 and return_pct > 0 and drawdown <= 25 and trades >= 25:
        return "Validated evidence"
    if pf >= 1.0 and return_pct > 0:
        return "Research evidence"
    return "Experimental"


def _orb_volume_high_win_evidence() -> Evidence | None:
    results_path = ACTIVE_PIPELINE_ROOT / "05 ORB Volume Profile" / "Backtest Reports" / "Locked" / "results.json"
    if not results_path.exists():
        return None
    rows = _load_json(results_path)
    row = next((item for item in rows if item.get("case") == "rr-075"), None)
    if row is None:
        return None
    chart = ACTIVE_PIPELINE_ROOT / "05 ORB Volume Profile" / "Backtest Reports" / "Locked" / "orb-volume-xau-locked-rr-075.png"
    return Evidence(
        label="Untouched locked-year MT5 configuration — high-win 0.75R",
        period=str(row["from"]).replace(".", "-") + " to " + str(row["to"]).replace(".", "-"),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "98%")),
        source_note="Exness XAUUSD M5, untouched locked-year MT5 Every Tick history, broker spread, commission, swap and random execution delay using the dedicated 0.75R Dynamic 50/20 preset at 1% risk.",
        chart_path=chart if chart.is_file() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["max_drawdown_pct"]), int(row["trades"])),
        caution="The 69.39% locked-year win rate and 69.82% three-year confirmation are historical, not guaranteed. This EA shares the same signal with the core ORB, so simultaneous positions are strongly correlated and their planned risks add together.",
    )


def _orb_volume_confirmed_evidence() -> Evidence | None:
    results_path = ACTIVE_PIPELINE_ROOT / "05 ORB Volume Profile" / "Backtest Reports" / "Locked" / "results.json"
    if not results_path.exists():
        return None
    rows = _load_json(results_path)
    row = next((item for item in rows if item.get("case") == "confirmation-volume"), None)
    if row is None:
        return None
    chart = ACTIVE_PIPELINE_ROOT / "05 ORB Volume Profile" / "Backtest Reports" / "Locked" / "orb-volume-xau-locked-confirmation-volume.png"
    return Evidence(
        label="Untouched locked-year MT5 configuration — volume confirmed",
        period=str(row["from"]).replace(".", "-") + " to " + str(row["to"]).replace(".", "-"),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "99%")),
        source_note="Exness XAUUSD M5, untouched locked-year MT5 Every Tick history, broker spread, commission, swap and random execution delay using the dedicated stronger-volume 2.5R Dynamic 50/20 preset at 1% risk.",
        chart_path=chart if chart.is_file() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["max_drawdown_pct"]), int(row["trades"])),
        caution="The 52.17% locked-year win rate is historical and based on only 23 trades. This EA is strongly correlated with the other two XAU ORBs, so their planned risks add when signals overlap.",
    )


def _one_year_evidence() -> dict[str, Evidence]:
    path = PACKAGE_ROOT / "Active BAT Backtest 2026-08-12" / "portfolio-results.json"
    if not path.exists():
        return {}
    data = _load_json(path)
    result: dict[str, Evidence] = {}
    aliases = {
        "13-aaa-final-news-pulse": "AAA Final News Pulse - NFP CPI FOMC - LONG ONLY ROBUST 60s",
    }
    for row in data.get("bots", []):
        label = aliases.get(row.get("id", ""), row["label"])
        pf = float(row["profit_factor"])
        ret = float(row["return_pct"])
        dd = float(row["equity_dd_pct"])
        trades = int(row["trades"])
        result[label] = Evidence(
            label="Latest complete one-year MT5 backtest",
            period="2025-08-11 to 2026-08-10",
            return_pct=ret,
            profit_factor=pf,
            drawdown_pct=dd,
            win_rate_pct=float(row["win_rate_pct"]),
            trades=trades,
            history_quality=str(row.get("history_quality", "99%")),
            source_note="Exness, every-tick modelling from synchronized broker M1 history, random execution delay and the exact active BAT preset.",
            chart_path=Path(row["chart_path"]) if row.get("chart_path") else None,
            status=_status_for(pf, ret, dd, trades),
            caution="One historical year is not a guarantee of future performance.",
        )
    return result


@lru_cache(maxsize=1)
def _selected_portfolio_evidence() -> dict[str, Evidence]:
    """Evidence for the exact per-EA configurations installed by the active BAT."""
    results_path = SELECTED_PORTFOLIO_ROOT / "locked-results.json"
    if not results_path.exists():
        return {}
    rows = _load_json(results_path)
    by_case = {
        (str(row.get("EaId")), str(row.get("Variant"))): row
        for row in rows
        if row.get("Stage") == "Locked" and row.get("status") == "valid"
    }
    result: dict[str, Evidence] = {}
    for installer_label, (ea_id, variant, exit_mode) in SELECTED_CONFIGS.items():
        row = by_case.get((ea_id, variant))
        if row is None:
            continue
        ret = float(row["return_pct"])
        pf = float(row["profit_factor"])
        dd = float(row["equity_dd_pct"])
        trades = int(row["trades"])
        report = Path(str(row.get("report", "")))
        chart = report.with_suffix(".png") if report else None
        result[installer_label] = Evidence(
            label=f"Applied locked-year MT5 configuration — {exit_mode}",
            period="2025-09-01 to 2026-08-31",
            return_pct=ret,
            profit_factor=pf,
            drawdown_pct=dd,
            win_rate_pct=float(row["win_rate"]),
            trades=trades,
            history_quality=f"{float(row.get('history_quality_pct', 0.0)):.0f}%",
            source_note=(
                f"Exness {row['Symbol']}, MT5 Every Tick, broker spread, commission, swap and random execution delay. "
                f"The installed selection uses {exit_mode.lower()} with no added research-session restriction."
            ),
            chart_path=chart if chart and chart.is_file() else None,
            status=_status_for(pf, ret, dd, trades),
            caution=(
                "This setting was selected after comparing exit and session variants. It is historical evidence, "
                "not a guarantee, and the combined portfolio still needs shared-margin forward observation."
            ),
        )
    return result


def _filtered_markov_evidence() -> dict[str, Evidence]:
    path = BOOKMAPER_ROOT / "artifacts" / "active-ea-regime-filter.json"
    if not path.exists():
        return {}
    data = _load_json(path)
    native_path = FILTERED_AUDIT_ROOT / "native-filter-validation.json"
    native_rows = {
        str(row["label"]): row for row in (_load_json(native_path) if native_path.exists() else [])
    }
    installer_aliases = {
        "Asia Breakout": "AAA Final Asia Breakout",
        "EMA3": "AAA Final EMA3",
        "News Pulse": "AAA Final News Pulse - NFP CPI FOMC - LONG ONLY ROBUST 60s",
        "XAU Weakness": "AAA Final XAU Weakness",
    }
    result: dict[str, Evidence] = {}
    for row in data.get("by_ea", []):
        baseline = row.get("baseline", {})
        research_filtered = row.get("filtered", {})
        return_pct = float(research_filtered.get("return_pct", 0.0))
        pf = float(research_filtered.get("profit_factor", 0.0))
        if (
            return_pct <= float(baseline.get("return_pct", 0.0))
            or pf <= float(baseline.get("profit_factor", 0.0))
        ):
            continue
        native = native_rows.get(str(row["ea"]))
        metrics = native or research_filtered
        return_pct = float(metrics["return_pct"])
        pf = float(metrics["profit_factor"])
        label = installer_aliases.get(str(row["ea"]), str(row["ea"]))
        dd = float(metrics.get("equity_dd_pct", metrics.get("max_equity_dd_pct", 0.0)))
        trades = int(metrics["trades"])
        result[label] = Evidence(
            label="Native MT5 embedded-Markov validation" if native else "Embedded Markov-filter locked-year overlay",
            period="2025-08-11 to 2026-08-21",
            return_pct=return_pct,
            profit_factor=pf,
            drawdown_pct=dd,
            win_rate_pct=float(metrics["win_rate_pct"]),
            trades=trades,
            history_quality=str(metrics.get("history_quality", "Underlying saved MT5 reports")),
            source_note="Fresh Exness Every Tick test of the rebuilt EX5 with the completed-D1 Markov gate running inside the EA, including broker spread, commission, swap and random execution delay." if native else "Prior-D1 Markov direction veto applied before entry to saved net MT5 trade cash flows, including original commission and swap.",
            chart_path=None,
            status=_status_for(pf, return_pct, dd, trades),
            caution="The filter is embedded in this EA and evaluates completed broker D1 bars before entry. One historical test is not a guarantee of future performance.",
        )
    return result


def _all_markov_safe_evidence() -> dict[str, Evidence]:
    path = BOOKMAPER_ROOT / "artifacts" / "active-ea-regime-filter.json"
    if not path.exists():
        return {}
    aliases = {
        "Asia Breakout": "AAA Final Asia Breakout",
        "EMA3": "AAA Final EMA3",
        "News Pulse": "AAA Final News Pulse - NFP CPI FOMC - LONG ONLY ROBUST 60s",
        "XAU Weakness": "AAA Final XAU Weakness",
    }
    result: dict[str, Evidence] = {}
    for row in _load_json(path).get("by_ea", []):
        metrics = row.get("filtered", {})
        if not metrics:
            continue
        label = aliases.get(str(row["ea"]), str(row["ea"]))
        ret = float(metrics["return_pct"])
        pf = float(metrics["profit_factor"])
        dd = float(metrics.get("max_equity_dd_pct", 0.0))
        trades = int(metrics["trades"])
        result[label] = Evidence(
            label="Full Safe completed-D1 regime overlay",
            period="2025-08-11 to 2026-08-21",
            return_pct=ret,
            profit_factor=pf,
            drawdown_pct=dd,
            win_rate_pct=float(metrics["win_rate_pct"]),
            trades=trades,
            history_quality="Original net MT5 trades with no-lookahead entry veto",
            source_note="The EA keeps its original setup and costs, but independently rejects entries whose direction disagrees with its own completed-D1 40-bar Markov forecast.",
            chart_path=None,
            status=_status_for(pf, ret, dd, trades),
            caution="This is a historical per-trade veto overlay. The Full Safe EX5 should be forward-tested on the target broker before live use.",
        )
    return result


def _xau_markov_evidence() -> Evidence | None:
    path = BOOKMAPER_ROOT / "artifacts" / "standalone-results.json"
    if not path.exists():
        return None
    row = _load_json(path).get("xau", {}).get("optimized")
    if not row:
        return None
    metrics = row["metrics"]
    return Evidence(
        label="Locked one-year proxy validation",
        period="2025-08-11 to 2026-08-21",
        return_pct=float(metrics["return_pct"]),
        profit_factor=float(metrics["profit_factor"]),
        drawdown_pct=float(metrics["max_equity_dd_pct"]),
        win_rate_pct=float(metrics["win_rate_pct"]),
        trades=int(metrics["trades"]),
        history_quality="Fresh Yahoo GC=F daily proxy",
        source_note="Locked out-of-sample daily proxy test with 1% risk, a 4x ATR stop, 3R target, two-times notional cap and a conservative 5 bps round-trip cost assumption.",
        chart_path=None,
        status="Research evidence",
        caution="Only ten trades occurred and GC=F is not Exness XAUUSD. Treat PF 5.50 as preliminary research, not a live-performance claim.",
    )


def _nasdaq_open_one_year_evidence() -> Evidence | None:
    cache = STORE_ROOT / "data" / "evidence-cache" / "v1" / "products" / "nasdaq-5m-candle-momentum" / "standard" / "3y.json"
    path = PACKAGE_ROOT / "Active Portfolio Full Pipeline 2026-09-05" / "11 Nasdaq 5M Candle Momentum" / "Reports" / "full" / "ustec-full-fixed-rr2.5.json"
    if not path.exists():
        return None
    cached = _load_json(cache) if cache.exists() else None
    row = cached["stats"] if cached else _load_json(path)
    profit_factor = float(row["profit_factor"])
    return_pct = float(row["return_pct"])
    drawdown = float(row.get("max_drawdown_pct", row.get("equity_dd_pct")))
    trades = int(row["trades"])
    chart = PACKAGE_ROOT / "Active Portfolio Full Pipeline 2026-09-05" / "11 Nasdaq 5M Candle Momentum" / "Charts" / "locked-and-three-year-comparison.png"
    return Evidence(
        label="Exact three-year optimized MT5 validation",
        period=str(cached["period"]) if cached else "2023-09-01 to 2026-09-01",
        return_pct=return_pct,
        profit_factor=profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=float(row.get("win_rate_pct", row.get("win_rate"))),
        trades=trades,
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", f"{row.get('history_quality_pct', 100):.0f}%")),
        source_note="Exness USTEC, synchronized Every Tick MT5 test with commission, swap and random execution delay using the frozen EMA12 / ATR4 / fixed 2.5R / no-trailing / 15:55 close preset.",
        chart_path=chart if chart.exists() else None,
        status=_status_for(profit_factor, return_pct, drawdown, trades),
        caution="The 2.5R exit was selected on the first two years and confirmed on the untouched final year. Historical performance is not a guarantee.",
    )


def _nasdaq_open_safe_evidence() -> Evidence | None:
    cache = STORE_ROOT / "data" / "evidence-cache" / "v1" / "products" / "nasdaq-5m-candle-momentum" / "safe" / "3y.json"
    path = PACKAGE_ROOT / "Active Portfolio Full Pipeline 2026-09-05" / "11 Nasdaq 5M Candle Momentum" / "Reports" / "full" / "ustec-full-fixed-rr2.5-safe.json"
    if not path.exists():
        return None
    cached = _load_json(cache) if cache.exists() else None
    row = cached["stats"] if cached else _load_json(path)
    chart = PACKAGE_ROOT / "Active Portfolio Full Pipeline 2026-09-05" / "11 Nasdaq 5M Candle Momentum" / "Charts" / "locked-and-three-year-comparison.png"
    return Evidence(
        label="Exact three-year Full Safe comparison",
        period=str(cached["period"]) if cached else "2023-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row.get("max_drawdown_pct", row.get("equity_dd_pct"))),
        win_rate_pct=float(row.get("win_rate_pct", row.get("win_rate"))),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", f"{row.get('history_quality_pct', 100):.0f}%")),
        source_note="The optimized fixed-2.5R Exness USTEC Every Tick test with the completed-D1 40-bar Markov direction gate enabled. Spread, commission, swap and random execution delay remain included.",
        chart_path=chart if chart.exists() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row.get("max_drawdown_pct", row.get("equity_dd_pct"))), int(row["trades"])),
        caution="Full Safe accepted only 189 trades, reduced return materially and did not improve exact three-year drawdown. Standard therefore remains the recommended mode.",
    )


def _us100_orb_one_year_evidence(version: str) -> Evidence | None:
    result_files = {
        "0.5R": "native-rr05-bat-one-year-results.json",
        "2R": "native-v3-time-direction-results.json",
    }
    path = PACKAGE_ROOT / "US100 Selective ORB Research 2026-08-21" / result_files[version]
    if not path.exists():
        return None
    rows = _load_json(path)
    row = next((item for item in rows if item.get("case") == "one-year-2025-2026"), None)
    if row is None:
        return None
    chart = Path(str(row["graph"]))
    trade_count = int(row["trades"])
    caution = (
        f"Only {trade_count} trades occurred in this one-year window, so the displayed win rate and profit factor "
        "are not statistically dependable."
    )
    return Evidence(
        label="Latest complete one-year MT5 backtest",
        period="2025-08-11 to 2026-08-10" if version == "0.5R" else "2025-08-21 to 2026-08-20",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate"]),
        trades=trade_count,
        history_quality=f"{float(row.get('history_quality_pct', 100)):.0f}%",
        source_note=f"Exness USTEC M5, synchronized MT5 Every Tick history, random execution delay and the exact {version} BAT adaptive-risk preset at 1% risk.",
        chart_path=chart if chart.exists() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["equity_dd_pct"]), trade_count),
        caution=caution,
    )


def _fabio_orb_one_year_evidence() -> Evidence | None:
    path = PACKAGE_ROOT / "US100 Fabio ORB Volatility Target Research 2026-08-26" / "native-results.json"
    if not path.exists():
        return None
    rows = _load_json(path)
    row = next((item for item in rows if item.get("id") == "literal-one-year-every-tick"), None)
    if row is None:
        return None
    profit_factor = float(row["profit_factor"])
    return_pct = float(row["return_pct"])
    drawdown = float(row["equity_dd_pct"])
    trades = int(row["trades"])
    chart = Path(str(row["chart_path"]))
    return Evidence(
        label="Latest complete one-year MT5 backtest",
        period=f"{row['from_date']} to {row['to_date']}",
        return_pct=return_pct,
        profit_factor=profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note="Exness USTEC M5, synchronized 100% MT5 Every Tick history, random execution delay and the exact literal ORB30 long-only 1R preset at 1% risk.",
        chart_path=chart if chart.exists() else None,
        status=_status_for(profit_factor, return_pct, drawdown, trades),
        caution="The older training segment produced only PF 1.04. This setup remains a forward-test candidate, and one historical year does not guarantee future performance.",
    )


def _top_down_fvg_one_year_evidence(symbol: str) -> Evidence | None:
    if symbol.upper() == "ETHUSD":
        path = (
            PACKAGE_ROOT
            / "Active Portfolio Full Pipeline 2026-09-05"
            / "03 ETH Top Down FVG"
            / "Backtest Reports"
            / "Locked"
            / "results.json"
        )
        if not path.exists():
            return None
        row = next(
            (item for item in _load_json(path) if item.get("case") == "combo-rr4-dynamic5020"),
            None,
        )
        if row is None:
            return None
        profit_factor = float(row["profit_factor"])
        return_pct = float(row["return_pct"])
        drawdown = float(row["max_drawdown_pct"])
        trades = int(row["trades"])
        report = Path(str(row["report"]))
        return Evidence(
            label="Approved locked-year MT5 configuration — 4R Dynamic 50/20",
            period=f"{str(row['from']).replace('.', '-')} to {str(row['to']).replace('.', '-')}",
            return_pct=return_pct,
            profit_factor=profit_factor,
            drawdown_pct=drawdown,
            win_rate_pct=float(row["win_rate_pct"]),
            trades=trades,
            sharpe_ratio=float(row["sharpe_ratio"]),
            recovery_factor=float(row["recovery_factor"]),
            history_quality=str(row.get("history_quality", "100%")),
            source_note=(
                "Exness ETHUSD M15, native MT5 Every Tick history, broker spread, commission, swap and random "
                "execution delay. The installed preset uses a 4R target, Dynamic 50/20, all-day entries, the "
                "current structural stop and 1% risk."
            ),
            chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
            status=_status_for(profit_factor, return_pct, drawdown, trades),
            caution=(
                f"Only {trades} trades occurred in this locked year and 44 in the exact three-year audit. "
                "Treat this as demo-forward-test evidence, not proof of future performance."
            ),
        )

    path = PACKAGE_ROOT / "Top Down FVG Liquidity Research 2026-08-27" / "native-results.json"
    if not path.exists():
        return None
    rows = _load_json(path)
    row_id = f"{symbol.lower()}-locked-year"
    row = next((item for item in rows if item.get("id") == row_id), None)
    if row is None:
        return None
    profit_factor = float(row["profit_factor"])
    return_pct = float(row["return_pct"])
    drawdown = float(row["equity_dd_pct"])
    trades = int(row["trades"])
    chart = Path(str(row["chart_path"]))
    return Evidence(
        label="Latest complete one-year MT5 backtest",
        period=f"{row['from_date']} to {row['to_date']}",
        return_pct=return_pct,
        profit_factor=profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        history_quality=str(row.get("history_quality", "100%")),
        source_note=f"Exness {symbol} M15, MT5 Every Tick history, broker spread, commission, swap and random execution delay using the selected 1% risk preset.",
        chart_path=chart if chart.exists() else None,
        status=_status_for(profit_factor, return_pct, drawdown, trades),
        caution=f"Only {trades} trades occurred in this locked one-year window. Treat the result as forward-test evidence, not proof of a stable future edge.",
    )


def _eth_fvg_safe_evidence() -> Evidence | None:
    path = (
        PACKAGE_ROOT
        / "Active Portfolio Full Pipeline 2026-09-05"
        / "03 ETH Top Down FVG"
        / "Backtest Reports"
        / "Locked"
        / "results.json"
    )
    if not path.exists():
        return None
    row = next(
        (item for item in _load_json(path) if item.get("case") == "combo-rr4-dynamic5020-safe"),
        None,
    )
    if row is None:
        return None
    profit_factor = float(row["profit_factor"])
    return_pct = float(row["return_pct"])
    drawdown = float(row["max_drawdown_pct"])
    trades = int(row["trades"])
    report = Path(str(row["report"]))
    return Evidence(
        label="Full Safe locked-year MT5 configuration",
        period=f"{str(row['from']).replace('.', '-')} to {str(row['to']).replace('.', '-')}",
        return_pct=return_pct,
        profit_factor=profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note=(
            "Exness ETHUSD M15 native MT5 Every Tick test. Full Safe preserves the selected 4R/Dynamic 50/20 "
            "trade management and enables the independent completed-D1 Markov direction gate."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status=_status_for(profit_factor, return_pct, drawdown, trades),
        caution=(
            "The safe gate reduced this locked result to 18 trades. It remains an optional defensive mode and "
            "is not the recommended ETH default."
        ),
    )


def _nasdaq_overnight_current_evidence() -> Evidence | None:
    path = OVERNIGHT_OPTIMIZATION_ROOT / "FINAL AUDIT.json"
    if not path.exists():
        return None
    data = _load_json(path)
    row = data.get("locked", {}).get("current-negative-close-open")
    if not row:
        return None
    report = Path(str(row["path"]))
    trades = int(row["trades"])
    return Evidence(
        label="Fresh locked-year MT5 active configuration",
        period=str(data.get("test_design", {}).get("locked", "2025-09-01 to 2026-09-01")),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note="Exness USTEC M1, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the exact active negative-day 16:00-to-09:29 preset at 1% risk.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["max_drawdown_pct"]), trades),
        caution="The conservative 0.75R alternative achieved PF 3.36 and 0.88% drawdown, but only 26 locked-year trades and +4.14% return. The active version is retained because it produced +8.67% across 72 trades; neither result guarantees future performance.",
    )


def _poc_fib_btc_evidence() -> Evidence | None:
    path = POC_FIB_ROOT / "FINAL AUDIT.json"
    if not path.exists():
        return None
    data = _load_json(path)
    row = data.get("symbols", {}).get("btcusd", {}).get("optimized_locked")
    if not row:
        return None
    report = Path(str(row["path"]))
    trades = int(row["trades"])
    return Evidence(
        label="Locked one-year MT5 demo-watch result",
        period=str(data.get("test_design", {}).get("locked", "2025-09-01 to 2026-09-01")),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        history_quality=str(row.get("history_quality", "100%")),
        source_note="Exness BTCUSD M15, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the exact optimized 1% risk preset.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Demo watch",
        caution="Only 26 locked-year trades occurred and the 10,000-path Monte Carlo return P5 was -14.32%. The model is installed at the user's request but is not classified as a robust core EA.",
    )


def _ema3_xau_evidence(*, safe: bool = False) -> Evidence | None:
    path = ACTIVE_PIPELINE_ROOT / "08 EMA3" / "Backtest Reports" / "ThreeYear" / "results.json"
    if not path.is_file():
        return None
    case_name = "manage-dynamic6020-only-safe" if safe else "manage-dynamic6020-only"
    rows = _load_json(path)
    row = next((item for item in rows if item.get("case") == case_name), None)
    if row is None:
        return None
    chart = ACTIVE_PIPELINE_ROOT / "08 EMA3" / "EMA3 XAU - FINAL DECISION AND MONTE CARLO.png"
    label = (
        "Exact three-year Full Safe MT5 validation — Dynamic 60/20 only"
        if safe
        else "Exact three-year optimized MT5 validation — Dynamic 60/20 only"
    )
    caution = (
        "The Safe gate reduced the exact three-year sample to 77 trades and return to 33.56%, while improving PF to 2.30 and max drawdown to 3.95%. Historical robustness does not guarantee future performance."
        if safe
        else "The untouched year returned 19.57% with PF 2.77, 70.73% wins and 3.45% drawdown. Monte Carlo return P5 was +15.89%, but historical robustness does not guarantee future performance."
    )
    return Evidence(
        label=label,
        period=f"{str(row['from']).replace('.', '-')} to {str(row['to']).replace('.', '-')}",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note=(
            "Exness XAUUSD H4, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the selected five-bar pivot stop, 1.7R target, Dynamic 60/20-only management and fixed 1% test risk."
            + (" The completed-D1 Markov gate is enabled." if safe else " The Markov gate is disabled.")
        ),
        chart_path=chart if chart.is_file() else None,
        status="Validated evidence",
        caution=caution,
    )


def _xau_weakness_evidence(*, safe: bool = False) -> Evidence | None:
    path = ACTIVE_PIPELINE_ROOT / "09 XAU Weakness" / "Backtest Reports" / "ThreeYear" / "results.json"
    if not path.is_file():
        return None
    case_name = "selected-m30-rr400-safe5020" if safe else "selected-m30-rr400-dynamic5020"
    rows = _load_json(path)
    row = next((item for item in rows if item.get("case") == case_name), None)
    if row is None:
        return None
    chart = ACTIVE_PIPELINE_ROOT / "09 XAU Weakness" / "XAU Weakness - FINAL DECISION AND MONTE CARLO.png"
    label = (
        "Exact three-year Full Safe MT5 validation — M30 / 4R / Dynamic 50/20"
        if safe
        else "Exact three-year optimized MT5 validation — M30 / 4R / Dynamic 50/20"
    )
    caution = (
        "The Safe gate returned 69.41% in the untouched year with PF 2.09, 43.68% wins and 5.47% drawdown. Its 10,000-path Monte Carlo return P5 was +58.22%; historical results still do not guarantee future performance."
        if safe
        else "The untouched year returned 89.60% with PF 1.89, 43.20% wins and 12.79% drawdown. The 10,000-path Monte Carlo return P5 was +89.28%; historical results still do not guarantee future performance."
    )
    return Evidence(
        label=label,
        period=f"{str(row['from']).replace('.', '-')} to {str(row['to']).replace('.', '-')}",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note=(
            "Exness XAUUSD M30, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the selected structure stop, 4R target, Dynamic 50/20 management and fixed 1% test risk."
            + (" The completed-D1 Markov gate is enabled." if safe else " The Markov gate is disabled.")
        ),
        chart_path=chart if chart.is_file() else None,
        status="Validated evidence",
        caution=caution,
    )


def _rsi_vwap_xau_evidence() -> Evidence | None:
    path = RSI_VWAP_ROOT / "final-audit.json"
    if not path.exists():
        return None
    data = _load_json(path)
    row = next(
        (
            item for item in data.get("rows", [])
            if item.get("symbol") == "xauusd"
            and item.get("timeframe") == "h1"
            and item.get("variant") == "optimized"
        ),
        None,
    )
    if row is None:
        return None
    report = Path(str(row["path"]))
    trades = int(row["trades"])
    return Evidence(
        label="Locked one-year MT5 research candidate",
        period=f"{data['period']['from']} to {data['period']['to']}",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        history_quality=str(row.get("history_quality", "99%")),
        source_note="Exness XAUUSD H1, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the exact 1% risk locked preset.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Research evidence",
        caution="The locked result contains only 44 trades and its Monte Carlo return P5 was -1.71%. Treat it as a demo forward-test candidate, not a proven production edge.",
    )


def _trend_progression_xau_evidence() -> Evidence | None:
    path = TREND_PROGRESSION_ROOT / "final-audit.json"
    if not path.exists():
        return None
    data = _load_json(path)
    row = data.get("symbols", {}).get("xauusd", {}).get("optimized_locked")
    if not row:
        return None
    report = Path(str(row["path"]))
    trades = int(row["trades"])
    return Evidence(
        label="Locked optimized one-year MT5 validation",
        period=f"{data['test_design']['locked'].replace(' to ', ' to ')}",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        history_quality=str(row.get("history_quality", "99%")),
        source_note="Exness XAUUSD H4, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the exact optimized 1% risk preset.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated evidence",
        caution="The locked year contains only 25 trades. Its 10,000-path Monte Carlo P5 was positive, but the sample remains small and does not guarantee the next year.",
    )


def _elliott_wave_xau_evidence() -> Evidence | None:
    path = ELLIOTT_WAVE_ROOT / "FINAL AUDIT.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    symbol = data.get("symbols", {}).get("xauusd", {})
    row = symbol.get("optimized_locked")
    monte_carlo = symbol.get("monte_carlo", {})
    if not row:
        return None
    report = ELLIOTT_WAVE_ROOT / "Backtest Reports" / "locked" / "xauusd--h4--optimized--locked.htm"
    trades = int(row["trades"])
    return Evidence(
        label="Untouched locked-year MT5 validation — optimized Elliott 1-2-3",
        period=str(data.get("test_design", {}).get("locked", "2025-09-01 to 2026-09-01")),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "99%")),
        source_note=(
            "Exness XAUUSD H4, native MT5 Every Tick history, broker spread, commission, swap and random "
            "execution delay. The two-year development period selected EMA50 confirmation, a signal-candle "
            "stop, fixed 3R target, no trailing, all-day entries and 1% equity risk before this year was tested."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated evidence",
        caution=(
            f"Only {trades} locked-year trades occurred. The 10,000-path bootstrap return P5 was "
            f"{float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}% with "
            f"{float(monte_carlo.get('max_dd_p95_pct', 0.0)):.2f}% P95 drawdown; this remains historical "
            "evidence rather than a guarantee of future performance."
        ),
    )


def _slow_trend_xau_evidence() -> Evidence | None:
    path = SLOW_TREND_ROOT / "summary.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    row = next((item for item in data.get("native", []) if item.get("symbol") == "XAUUSD"), None)
    if row is None:
        return None
    report = SLOW_TREND_ROOT / "Native" / "xauusd-selected-test-model0" / "xauusd-selected-test-model0.htm"
    trades = int(row["locked_trades"])
    return Evidence(
        label="Untouched locked-year MT5 validation — optimized slow trend",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["locked_return"]),
        profit_factor=float(row["locked_pf"]),
        drawdown_pct=float(row["locked_equity_dd"]),
        win_rate_pct=float(row["locked_win_rate"]),
        trades=trades,
        sharpe_ratio=float(row["locked_sharpe"]),
        recovery_factor=float(row["locked_recovery"]),
        history_quality="99%",
        source_note="Exness XAUUSD H4, native MT5 generated Every Tick history, broker spread, commission, swap and random execution delay using the frozen 1% configuration selected before the locked year.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated evidence",
        caution=f"The locked year contains {trades} trades and is historical evidence, not a forecast. The wide 6R target creates a deliberately lower win rate and requires patient demo forward testing.",
    )


def _regime_switch_xau_evidence() -> Evidence | None:
    native_cache = (
        STORE_ROOT
        / "data"
        / "evidence-cache"
        / "v1"
        / "products"
        / "xau-regime-switch"
        / "standard"
        / "1y.json"
    )
    if native_cache.is_file():
        payload = _load_json(native_cache)
        row = payload.get("stats", {})
        trades = int(row.get("trades", 0))
        if trades > 0:
            return Evidence(
                label="Native MT5 Every Tick validation — XAU regime switch",
                period=str(payload.get("period", "2025-09-01 to 2026-09-01")),
                return_pct=float(row["return_pct"]),
                profit_factor=float(row["profit_factor"]),
                drawdown_pct=float(row["max_drawdown_pct"]),
                win_rate_pct=float(row["win_rate_pct"]),
                trades=trades,
                sharpe_ratio=float(row["sharpe_ratio"]),
                recovery_factor=float(row["recovery_factor"]),
                history_quality=str(row.get("history_quality", payload.get("history_quality", "99%"))),
                source_note="Exness XAUUSD M5, native MT5 Every Tick history, broker spread, commission, swap and random execution delay using the compiled combined EA and frozen hard-1% SET.",
                chart_path=None,
                status="Validated demo-forward evidence",
                caution="The native one-year result confirms the combined implementation, but its most recent six-month slice was negative. Keep this EA on demo until forward evidence shows the recent weakness has ended.",
            )

    path = REGIME_SWITCH_ROOT / "results.json"
    monte_carlo_path = REGIME_SWITCH_ROOT / "true-switch-monte-carlo.json"
    if not path.is_file() or not monte_carlo_path.is_file():
        return None
    data = _load_json(path).get("XAUUSD", {}).get("best_by_mode", {}).get("regime-switch", {})
    row = data.get("locked")
    monte_carlo = _load_json(monte_carlo_path).get("XAUUSD", {})
    if not row:
        return None
    chart = REGIME_SWITCH_ROOT / "Charts" / "true-switch-locked.png"
    return Evidence(
        label="Untouched locked-year ledger overlay — XAU regime switch",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_dd_pct"]),
        win_rate_pct=float(row["win_rate"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery"]),
        history_quality="Native component ledgers",
        source_note="The H4 trend and M5 VWAP components came from separate native Exness MT5 broker-cost ledgers. Their frozen signals were combined using completed-D1 causal regime decisions selected before the displayed locked year was opened, at fixed 1% risk.",
        chart_path=chart if chart.is_file() else None,
        status="Demo-stage overlay evidence",
        caution=(
            f"The 10,000-path return P5 was {float(monte_carlo.get('return_p5', 0.0)):+.2f}% and P95 drawdown was "
            f"{float(monte_carlo.get('dd_p95', 0.0)):.2f}%. This is not yet a native tick-by-tick report from the new combined EA, so demo forward testing and native confirmation are mandatory before real capital."
        ),
    )


def _session_vwap_xag_evidence() -> Evidence | None:
    path = SESSION_VWAP_ROOT / "Native" / "xagusd-frozen-locked-model0" / "result.json"
    if not path.is_file():
        return None
    row = _load_json(path)
    report = path.parent / "xagusd-frozen-locked-model0.htm"
    trades = int(row["trades"])
    return Evidence(
        label="Untouched locked-year MT5 validation — XAG session VWAP snapback",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=f"{float(row['history_quality_pct']):.0f}%",
        source_note="Exness XAGUSD M30 signals tested with native MT5 generated Every Tick history, broker spread, commission, swap and random execution delay. The 2.5-sigma New York rejection setup, ADX20 filter, 1.25 ATR stop, fixed 1R target, no trailing and 1% equity risk were frozen before this year was opened.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated watch evidence",
        caution=(
            f"Only {trades} locked-year trades occurred. A 10,000-path five-trade block bootstrap was positive "
            "in 99.91% of paths with a +1.78% return P5 and 2.74% P95 drawdown, but that simulation reuses "
            "the same small trade sample and does not remove the sample-size uncertainty."
        ),
    )


def _month_end_flow_us100_evidence() -> Evidence | None:
    path = MONTH_END_FLOW_ROOT / "Native" / "ustec-frozen-locked-model0" / "result.json"
    if not path.is_file():
        return None
    row = _load_json(path)
    report = path.parent / "ustec-frozen-locked-model0.htm"
    trades = int(row["trades"])
    return Evidence(
        label="Untouched locked-year MT5 validation — US100 month-end flow",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=f"{float(row['history_quality_pct']):.0f}%",
        source_note="Exness USTEC M30 signals tested with native MT5 Every Tick history, broker spread, commission, swap and random execution delay. The first-three-business-days window, New York first-hour timing, long-only direction, 1.5 ATR stop, fixed 2.5R target, six-hour exit and 1% equity risk were frozen before this year was opened.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated demo-forward evidence",
        caution=(
            f"Only {trades} locked-year trades occurred. The 10,000-path block bootstrap had a 78.38% "
            "profit probability, -5.24% return P5 and 9.20% P95 drawdown; this is historical evidence "
            "with a meaningful downside tail, not a forecast."
        ),
    )


def _news_pulse_hard_evidence(label: str) -> Evidence | None:
    slug={"News Pulse XAU":"news-pulse-xau","News Pulse XAG":"news-pulse-xag","News Pulse BTC":"news-pulse-btc"}.get(label)
    payload=load_news_summary(slug) if slug else None
    if payload:
        stats=payload['stats']
        return Evidence(
            label="Official-calendar independent 3-year MT5 run",
            period=payload['period'], return_pct=stats['return_pct'],
            profit_factor=stats['profit_factor'] or 0.0, drawdown_pct=stats['max_drawdown_pct'],
            win_rate_pct=stats['win_rate_pct'], trades=stats['trades'],
            sharpe_ratio=stats.get('sharpe_ratio'), recovery_factor=stats.get('recovery_factor'),
            max_win_streak=stats.get('max_win_streak'), max_loss_streak=stats.get('max_loss_streak'),
            history_quality=payload['history_quality'],source_note=payload['notice'],
            status="Watch only — full calendar coverage",
            caution="Full calendar coverage is not full real-tick coverage or proof of live news execution. Review the tick-history and event-execution disclosures for each period.",
        )
    # A short legacy audit is not a substitute for a missing full-period run.
    return None


def _legacy_news_pulse_hard_evidence(label: str) -> Evidence | None:
    if label == "News Pulse BTC":
        verified_path = NEWS_PULSE_BTC_3Y_ROOT / "OFFICIAL 3Y RESULTS.json"
        if verified_path.is_file():
            result = _load_json(verified_path)
            report = NEWS_PULSE_BTC_3Y_ROOT / "Backtest Reports" / "btcusd__official-3y.htm"
            return Evidence(
                label="Official-calendar three-year replay",
                period=f"{str(result['from']).replace('.', '-')} to {str(result['to']).replace('.', '-')}",
                return_pct=float(result["return_pct"]),
                profit_factor=float(result["profit_factor"]),
                drawdown_pct=float(result["max_drawdown_pct"]),
                win_rate_pct=float(result["win_rate_pct"]),
                trades=int(result["trades"]),
                sharpe_ratio=float(result["sharpe_ratio"]),
                recovery_factor=float(result["recovery_factor"]),
                history_quality=f"{float(result['history_quality_pct']):.0f}%",
                source_note=(
                    "Exness BTCUSD M1 generated Every Tick replay using News Pulse v2.14 and 94 exact official "
                    "BLS/Federal Reserve NFP, CPI and FOMC timestamps. All 94 event straddles were placed with no "
                    "calendar-boundary violation. The report includes broker spread, $2,298.82 commission, zero "
                    "swap and random execution delay at 0.75% risk per pending stop."
                ),
                chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
                status="Watch only — official 3Y schedule",
                caution=(
                    "The full window contains 125 trades from 92 triggered events, but Model 0 generates "
                    "intra-minute ticks and the BTC parameters were selected using part of this history. Treat "
                    "this as complete research evidence, not real-tick validation or a return guarantee."
                ),
            )
    assets = {
        "News Pulse XAU": "xauusd",
        "News Pulse XAG": "xagusd",
    }
    asset = assets.get(label)
    verified_path = NEWS_PULSE_CALENDAR_ROOT / "schedule-replay-results.json"
    if asset is not None and verified_path.is_file():
        verified = _load_json(verified_path)
        result = next((item for item in verified.get("results", []) if item.get("asset") == asset), None)
        if result is not None:
            replay = result["fxmacrodata_schedule"]
            metrics = replay["metrics"]
            report = Path(str(replay["report"]))
            initial_balance = float(metrics["initial_balance"])
            net_profit = float(metrics["reported_net_profit"])
            return Evidence(
                label="FXMacroData-verified calendar replay",
                period=str(result["period"]),
                return_pct=net_profit / initial_balance * 100.0,
                profit_factor=float(metrics["reported_profit_factor"]),
                drawdown_pct=float(metrics["reported_max_drawdown_pct"]),
                win_rate_pct=float(metrics["reported_win_rate_pct"]),
                trades=int(metrics["reported_trades"]),
                sharpe_ratio=float(metrics["reported_sharpe"]),
                recovery_factor=float(metrics["reported_recovery"]),
                history_quality=str(metrics["history_quality"]),
                source_note=(
                    "Exness M1 generated-tick replay using News Pulse v2.13, the exact FXMacroData UTC schedule, "
                    "all 7 enabled NFP/CPI/FOMC events in the declared coverage window, 0.75% risk per pending "
                    "stop and a 1.50% maximum planned event exposure. Live trading continues to use MT5's native calendar."
                ),
                chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
                status="Watch only — verified schedule",
                caution=(
                    "Only 9 trades across 7 scheduled events are present. The corrected calendar added one winning "
                    "NFP trade, so these high figures are not enough evidence for a live-performance claim."
                ),
            )
    path = NEWS_PULSE_ROOT / "HARD 1P5 FINAL AUDIT.json"
    if asset is None or not path.is_file():
        return None
    data = _load_json(path)
    row = next((item for item in data.get("full", []) if item.get("asset") == asset), None)
    if row is None:
        return None
    report = Path(str(row["report"]))
    trades = int(row["trades"])
    return Evidence(
        label="One-year hard-1.50% MT5 deployment audit",
        period=str(data.get("period", "2025-09-01 to 2026-09-01")),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=trades,
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=f"{float(row.get('history_quality_pct', 0.0)):.0f}%",
        source_note="Exness M1, MT5 Every Tick broker history and costs, using the exact compiled v2.12 two-sided preset with 0.75% risk per pending stop and a 1.50% maximum planned event exposure.",
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["max_drawdown_pct"]), trades),
        caution="Only one audited year and 33–37 event trades are available. Live news spreads, gaps, slippage and order rejection can materially exceed the planned risk.",
    )


def _orb_session_evidence(label: str) -> Evidence | None:
    selection = ORB_SESSION_PRODUCTS.get(label)
    path = ORB_SESSION_AUDIT_ROOT / "FINAL AUDIT.json"
    if selection is None or not path.is_file():
        return None
    symbol, session = selection
    data = _load_json(path)
    item = data.get("symbols", {}).get(symbol, {}).get("sessions", {}).get(session)
    if not item:
        return None
    row = item["locked"]
    monte_carlo = item["monte_carlo"]
    report = Path(str(row["path"]))
    session_label = data["test_design"]["sessions"][session]
    return Evidence(
        label=f"Untouched locked-year standalone {session_label} validation",
        period=str(data["test_design"]["locked"]),
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "99%")),
        source_note=(
            f"Exness {row['config'].get('InpSignalTimeframe', 30)}-minute signal logic on "
            f"{symbol.upper()}, native MT5 Every Tick history, broker spread, commission, swap and random execution delay. "
            "The configuration was selected on the preceding two-year development period before this locked year was read."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Research evidence",
        caution=(
            f"Only {int(row['trades'])} locked-year trades were observed. The 10,000-path Monte Carlo return P5 was "
            f"{float(monte_carlo['return_p5_pct']):+.2f}%, so this configuration needs forward observation and is not a guarantee."
        ),
    )


def _orb_h1_us100_evidence() -> Evidence | None:
    path = ORB_H1_AUDIT_ROOT / "US100 RR6 VALIDATION.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    row = data.get("locked")
    monte_carlo = data.get("monte_carlo", {})
    if not row:
        return None
    report = Path(str(row["path"]))
    return Evidence(
        label="Untouched locked-year US100 H1 ORB validation",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note=(
            "Exness USTEC M15, MT5 Every Tick broker history and costs. The 13:00 UTC RR6 configuration "
            "was selected only on 2023-09-01 through 2025-08-31 before the displayed locked year was read."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Validated evidence",
        caution=(
            f"The 10,000-path Monte Carlo return P5 was {float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}% "
            f"and P95 drawdown was {float(monte_carlo.get('max_dd_p95_pct', 0.0)):.2f}%. The placed target is "
            "6R, but timed exits reduced the locked-year realized average win-to-loss ratio to about 1.68."
        ),
    )


def _selective_orb_v3_evidence() -> Evidence | None:
    path = SELECTIVE_ORB_ROOT / "native-v3-time-direction-results.json"
    if not path.is_file():
        return None
    rows = _load_json(path)
    row = next((item for item in rows if item.get("case") == "one-year-2025-2026"), None)
    if row is None:
        return None
    chart = Path(str(row.get("graph", "")))
    return Evidence(
        label="One-year native V3 time-direction validation",
        period="2025-08-21 to 2026-08-20",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["equity_dd_pct"]),
        win_rate_pct=float(row["win_rate"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe_ratio"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=f"{float(row.get('history_quality_pct', 0.0)):.0f}%",
        source_note=(
            "Exness USTEC M5, native MT5 Every Tick broker history and costs, using the exact V3 "
            "time-direction retest preset with 1% equity risk, a 2R target and break-even at 1R."
        ),
        chart_path=chart if chart.is_file() else None,
        status="Demo watch",
        caution=(
            "Only five trades occurred in the displayed one-year period. The broader 2020-2026 report "
            "returned 18.70% with PF 2.16 over fifty-three trades, but that longer result is context rather "
            "than a substitute for fresh forward evidence."
        ),
    )


def _sell_nasdaq_15m_evidence() -> Evidence | None:
    path = SELL_NASDAQ_15M_ROOT / "FINAL AUDIT.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    row = data.get("final", {}).get("selected_full")
    locked = data.get("final", {}).get("selected_locked", {})
    monte_carlo = data.get("monte_carlo", {})
    if not row:
        return None
    chart = SELL_NASDAQ_15M_ROOT / "Charts" / "LOCKED EQUITY AND MONTE CARLO.png"
    return Evidence(
        label="Exact three-year pipeline-selected MT5 configuration",
        period="2023-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "98%")),
        source_note="Exness USTEC M15, native MT5 Every Tick broker history and costs using the selected Tuesday-Friday 450/1000 configuration at 1% equity risk.",
        chart_path=chart if chart.is_file() else None,
        status="Research evidence",
        caution=(
            f"The untouched year returned {float(locked.get('return_pct', 0.0)):+.2f}% with PF "
            f"{float(locked.get('profit_factor', 0.0)):.2f} over {int(locked.get('trades', 0))} trades, and the "
            f"10,000-path locked-trade Monte Carlo return P5 was {float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}%. "
            "Treat this as a demo-forward candidate rather than a proven live-capital edge."
        ),
    )


def _sell_nasdaq_15m_safe_evidence() -> Evidence | None:
    path = SELL_NASDAQ_15M_ROOT / "FINAL AUDIT.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    row = data.get("safe_audit", {}).get("raw_london_standard_full")
    locked = data.get("final", {}).get("raw_london", {})
    monte_carlo = data.get("safe_audit", {}).get("standard_raw_london_monte_carlo", {})
    if not row:
        return None
    chart = SELL_NASDAQ_15M_ROOT / "Charts" / "LOCKED EQUITY AND MONTE CARLO.png"
    return Evidence(
        label="Exact three-year London-confirmed Safe preset",
        period="2023-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "98%")),
        source_note="Exness USTEC M15, native MT5 Every Tick broker history and costs using the dedicated bearish-London 600/1000 Safe preset at 1% equity risk.",
        chart_path=chart if chart.is_file() else None,
        status="Research evidence",
        caution=(
            f"The untouched year returned {float(locked.get('return_pct', 0.0)):+.2f}% with PF "
            f"{float(locked.get('profit_factor', 0.0)):.2f}, {float(locked.get('win_rate_pct', 0.0)):.2f}% wins and "
            f"{float(locked.get('max_drawdown_pct', 0.0)):.2f}% drawdown. Its locked-trade Monte Carlo return P5 was "
            f"{float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}%, so Safe means a more selective preset, not guaranteed safety."
        ),
    )


def _sell_nasdaq_15m_dynamic_evidence() -> Evidence | None:
    path = SELL_NASDAQ_15M_ROOT / "Dynamic Exit Research" / "DYNAMIC EXIT AUDIT.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    branch = data.get("london_safe", {})
    row = branch.get("full")
    locked = branch.get("locked", {})
    monte_carlo = branch.get("monte_carlo", {})
    if not row:
        return None
    return Evidence(
        label="Exact three-year Dynamic London research preset",
        period="2023-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "98%")),
        source_note=(
            "Exness USTEC M15, native MT5 Every Tick broker history and costs. Dynamic London requires "
            "the preceding bearish London candle, sizes its stop at ATR(14) × 2.5 and targets 3R at 1% equity risk."
        ),
        status="Research evidence",
        caution=(
            f"The untouched year returned {float(locked.get('return_pct', 0.0)):+.2f}% with PF "
            f"{float(locked.get('profit_factor', 0.0)):.2f}, {float(locked.get('win_rate_pct', 0.0)):.2f}% wins and "
            f"{float(locked.get('max_drawdown_pct', 0.0)):.2f}% drawdown. Its locked-trade Monte Carlo return P5 was "
            f"{float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}%. It is saved for comparison and demo-forward testing, "
            "but is not the recommended portfolio default."
        ),
    )


def _london_open_usdjpy_evidence() -> Evidence | None:
    path = LONDON_OPEN_FX_MOMENTUM_ROOT / "Pipeline" / "FINAL AUDIT.json"
    if not path.is_file():
        return None
    data = _load_json(path)
    symbol = next((item for item in data.get("symbols", []) if item.get("symbol") == "USDJPY"), None)
    if not symbol:
        return None
    row = symbol.get("final", {}).get("selected-latest")
    validation = symbol.get("final", {}).get("selected-validation", {})
    monte_carlo = symbol.get("monte_carlo", {})
    if not row:
        return None
    report = Path(str(row["path"]))
    return Evidence(
        label="Untouched latest-year MT5 validation — USDJPY London-open momentum",
        period="2025-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["win_rate_pct"]),
        trades=int(row["trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row.get("history_quality", "100%")),
        source_note=(
            "Exness USDJPY M15, native MT5 generated Every Tick history, broker spread, commission, swap "
            "and random execution delay. The configuration was selected only on the earlier development "
            "window and retains 1% equity risk in this displayed validation."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Demo-forward watch evidence",
        caution=(
            f"The preceding independent validation year returned {float(validation.get('return_pct', 0.0)):+.2f}% "
            f"with PF {float(validation.get('profit_factor', 0.0)):.2f} and "
            f"{float(validation.get('max_drawdown_pct', 0.0)):.2f}% drawdown. Latest-year Monte Carlo return P5 "
            f"was {float(monte_carlo.get('return_p5_pct', 0.0)):+.2f}%, so this remains a watch allocation."
        ),
    )


def _xau_squeeze_momentum_evidence(version: str) -> Evidence | None:
    if version == "high-win-075":
        cache = (
            STORE_ROOT
            / "data"
            / "evidence-cache"
            / "v1"
            / "products"
            / "xau-squeeze-momentum-high-win-0-75r"
            / "standard"
            / "3y.json"
        )
        if cache.is_file():
            payload = _load_json(cache)
            stats = payload.get("stats", {})
            return Evidence(
                label="Three-year native MT5 post-selection run — 3 ATR / 0.75R",
                period=str(payload.get("period", "2023-09-01 to 2026-09-01")),
                return_pct=float(stats["return_pct"]),
                profit_factor=float(stats["profit_factor"]),
                drawdown_pct=float(stats["max_drawdown_pct"]),
                win_rate_pct=float(stats["win_rate_pct"]),
                trades=int(stats["trades"]),
                sharpe_ratio=float(stats["sharpe_ratio"]),
                recovery_factor=float(stats["recovery_factor"]),
                max_win_streak=int(stats["max_win_streak"]),
                max_loss_streak=int(stats["max_loss_streak"]),
                history_quality=str(stats["history_quality"]),
                source_note="Exness XAUUSD H1, native MT5 Every Tick three-year run at 1% equity risk with historical spread, commission and swap included.",
                chart_path=None,
                status="Research candidate",
                caution="The three-year run was performed after selecting this exact 0.75R preset. Its latest six months lost 1.88% with PF 0.27 over five trades, so it is installable for demo-forward comparison rather than promoted as validated.",
            )
        reports = sorted(
            (XAU_SQUEEZE_MOMENTUM_ROOT / "Backtest Reports" / "XAU" / "development-management").glob(
                "*sl3.0-rr0.75*.htm"
            )
        )
        if not reports:
            return None
        report = reports[0]
        return Evidence(
            label="Development-period MT5 management comparison — 3 ATR / 0.75R",
            period="2021-09-01 to 2024-08-31",
            return_pct=16.54,
            profit_factor=1.88,
            drawdown_pct=3.01,
            win_rate_pct=60.76,
            trades=79,
            sharpe_ratio=7.38,
            recovery_factor=4.64,
            history_quality="98%",
            source_note="Exness XAUUSD H1, native MT5 Every Tick development comparison at 1% equity risk with historical spread, commission and swap included.",
            chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
            status="Research candidate",
            caution="This exact 0.75R preset was selected from development management tests and has not completed a standalone purged and untouched locked validation. Demo-forward only.",
        )

    results_path = XAU_SQUEEZE_MOMENTUM_ROOT / "final-verdict-results.json"
    if not results_path.is_file():
        return None
    wanted = "safe-1pct" if version == "safe" else "standard-1pct"
    row = next(
        (
            item
            for item in _load_json(results_path)
            if item.get("symbol") == "XAUUSD"
            and item.get("version") == wanted
            and item.get("period") == "3y"
        ),
        None,
    )
    if row is None:
        return None
    report = Path(str(row["path"]))
    safe = version == "safe"
    return Evidence(
        label="Three-year native MT5 Safe validation" if safe else "Three-year native MT5 Standard validation",
        period="2023-09-01 to 2026-09-01",
        return_pct=float(row["return_pct"]),
        profit_factor=float(row["profit_factor"]),
        drawdown_pct=float(row["max_drawdown_pct"]),
        win_rate_pct=float(row["position_win_rate_pct"]),
        trades=int(row["position_trades"]),
        sharpe_ratio=float(row["sharpe"]),
        recovery_factor=float(row["recovery_factor"]),
        history_quality=str(row["history_quality"]),
        source_note=(
            "Exness XAUUSD H1, native MT5 Every Tick history at 1% equity risk with historical spread, commission and swap included. "
            + ("The completed-D1 no-lookahead Markov direction gate is enabled." if safe else "The Markov direction gate is disabled.")
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status="Watch only — pipeline evidence",
        caution=(
            "Safe mode had only 13 trades in the untouched real-tick year despite stronger PF, win rate and drawdown. Require at least 30 new demo-forward trades before reconsidering live deployment."
            if safe
            else "Standard had broader trade evidence, but its recent-half PF was 0.93. Keep it as the broad benchmark while collecting demo-forward evidence."
        ),
    )


def _dmc_evidence() -> dict[str, Evidence]:
    pipeline_path = DMC_FRESH_REACTION_ROOT / "pipeline-progress.json"
    transfer_path = DMC_FRESH_REACTION_ROOT / "transfer-us100.json"
    if not pipeline_path.is_file() or not transfer_path.is_file():
        return {}
    pipeline = _load_json(pipeline_path)
    transfer = _load_json(transfer_path)
    specifications = {
        "DMC Current XAU": (
            pipeline.get("final", {}).get("baseline", {}).get("three_year"),
            pipeline.get("final", {}).get("baseline", {}).get("locked", {}),
            "Original XAUUSD DMC baseline using the Asia H1 rejection, fixed 22.5-unit stop, 3R target and Dynamic 50/20.",
            "Validated evidence",
        ),
        "DMC Fresh Reaction XAU": (
            pipeline.get("final", {}).get("candidate", {}).get("three_year"),
            pipeline.get("final", {}).get("candidate", {}).get("locked", {}),
            "Fresh XAUUSD DMC using no more than one earlier M15 touch, W1/MN1 body proximity, Asia H1 rejection, fixed 30-unit stop, 3R and Dynamic 50/20.",
            "Demo-forward watch evidence",
        ),
        "DMC Fresh Reaction US100": (
            transfer.get("finals", {}).get("candidate-three-year"),
            transfer.get("finals", {}).get("candidate-locked", {}),
            "Fresh USTEC DMC using no more than one earlier M15 touch, W1/MN1 body proximity, New York H1 rejection, 1.5 ATR stop, 2R and Dynamic 50/20.",
            "Demo-forward watch evidence",
        ),
    }
    result: dict[str, Evidence] = {}
    for label, (row, locked, source_detail, status) in specifications.items():
        if not row:
            continue
        report = Path(str(row.get("path", "")))
        result[label] = Evidence(
            label="Exact three-year native MT5 DMC configuration",
            period="2023-09-01 to 2026-09-01",
            return_pct=float(row["return_pct"]),
            profit_factor=float(row["profit_factor"]),
            drawdown_pct=float(row["max_drawdown_pct"]),
            win_rate_pct=float(row["win_rate_pct"]),
            trades=int(row["trades"]),
            sharpe_ratio=float(row["sharpe"]),
            recovery_factor=float(row["recovery_factor"]),
            history_quality=str(row.get("history_quality", "98%")),
            source_note=(
                f"Exness {row['symbol']} H1, native MT5 Every Tick broker history and costs at the tested 1% risk. "
                + source_detail
            ),
            chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
            status=status,
            caution=(
                f"The untouched year returned {float(locked.get('return_pct', 0.0)):+.2f}% with PF "
                f"{float(locked.get('profit_factor', 0.0)):.2f}, {float(locked.get('win_rate_pct', 0.0)):.2f}% wins, "
                f"{float(locked.get('max_drawdown_pct', 0.0)):.2f}% drawdown and {int(locked.get('trades', 0))} trades. "
                "Run the three DMC entries on demo first because their signals can overlap and create correlated portfolio exposure."
            ),
        )
    return result


def _engineered_liquidity_evidence(symbol: str, safe: bool = False) -> Evidence | None:
    root = PACKAGE_ROOT / "Engineered Liquidity Sweep Research 2026-08-30"
    improvement_path = root / "IMPROVEMENT RESULTS.json"
    production_case = "rr2" if symbol == "XAUUSD" else "displacement"
    safe_case = "safe-rr2" if symbol == "XAUUSD" else "safe-displacement"
    rows = _load_json(improvement_path) if improvement_path.exists() else []
    wanted_case = safe_case if safe else production_case
    row = next(
        (
            item
            for item in rows
            if item.get("symbol") == symbol
            and item.get("case") == wanted_case
            and item.get("phase") == "locked"
        ),
        None,
    )
    if safe:
        if row is None:
            return None
        chart = Path(str(row.get("chart_path", "")))
        return Evidence(
            label="Native MT5 Full Safe validation",
            period=f"{row['from_date']} to {row['to_date']}",
            return_pct=float(row["return_pct"]),
            profit_factor=float(row["profit_factor"]),
            drawdown_pct=float(row["equity_dd_pct"]),
            win_rate_pct=float(row["win_rate_pct"]),
            trades=int(row["trades"]),
            history_quality=str(row.get("history_quality", "100%")),
            source_note="Exness MT5 Every Tick locked-year test with the completed-D1 no-lookahead Markov direction gate enabled inside this EA; broker costs and random execution delay remain included.",
            chart_path=chart if chart.is_file() else None,
            status=_status_for(float(row["profit_factor"]), float(row["return_pct"]), float(row["equity_dd_pct"]), int(row["trades"])),
            caution="Safe mode is a completed-D1 direction veto, not a guarantee. It can reduce trades and may not improve every market regime.",
        )

    if row is not None:
        report = Path(str(row["report_path"]))
        return_pct = float(row["return_pct"])
        profit_factor = float(row["profit_factor"])
        drawdown = float(row["equity_dd_pct"])
        win_rate = float(row["win_rate_pct"])
        trades = int(row["trades"])
        history_quality = str(row.get("history_quality", "100%"))
    else:
        path = root / "RESULTS.json"
        if not path.exists():
            return None
        legacy = next((item for item in _load_json(path) if item.get("market") == symbol), None)
        if legacy is None:
            return None
        report = Path(str(legacy["locked_report"]))
        return_pct = float(legacy["locked_return_pct"])
        profit_factor = float(legacy["locked_pf"])
        drawdown = float(legacy["locked_equity_dd_pct"])
        win_rate = float(legacy["locked_win_rate_pct"])
        trades = int(legacy["locked_trades"])
        history_quality = str(legacy.get("history_quality", "100%"))
    return Evidence(
        label="Locked one-year MT5 validation" if symbol == "XAUUSD" else "Post-hoc robustness candidate",
        period="2025-08-29 to 2026-08-28",
        return_pct=return_pct,
        profit_factor=profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=win_rate,
        trades=trades,
        history_quality=history_quality,
        source_note=(
            f"Exness {symbol}, MT5 Every Tick history, broker spread, commission, swap and random execution delay. The 2R XAU improvement was selected on the preceding development year."
            if symbol == "XAUUSD"
            else f"Exness {symbol}, MT5 Every Tick history with broker costs and random execution delay. The displacement rule repaired both tested years, but it was adopted after reviewing the original locked failure and therefore needs a fresh forward test."
        ),
        chart_path=report.with_suffix(".png") if report.with_suffix(".png").is_file() else None,
        status=_status_for(profit_factor, return_pct, drawdown, trades) if symbol == "XAUUSD" else "Research evidence",
        caution=(
            "The locked year confirmed a positive result, but one year is not a guarantee of future performance."
            if symbol == "XAUUSD"
            else "The original BTC reclaim failed locked validation (-14.17%, PF 0.92, 40.78% DD). Requiring full displacement improved the same period post-hoc, so this remains demo-only until new forward data exists."
        ),
    )


def _meta_for(item: dict[str, Any]) -> dict[str, Any]:
    label = item["label"]
    canonical = item["canonical"]
    if label in CORE_META:
        meta = dict(CORE_META[label])
    elif label.startswith("Auction Stock "):
        ticker = label.removeprefix("Auction Stock ")
        meta = {
            "strategy": "Auction-market stock swing",
            "tagline": f"Value-area breakout and retest execution for {ticker}.",
            "description": f"Applies the shared Auction Market Value Area engine to {ticker}, using composite value, migration and breakout/retest conditions with the stock-specific BAT preset.",
            "session": "US equity session / swing",
            "logic_audit": "Development logic summary",
            "logic_audit_note": "This entry remains under development and is not offered as a completed product.",
            "logic": [
                {"title": "Build a composite profile", "detail": "Creates tick-activity POC, VAH and VAL reference levels from the configured lookback."},
                {"title": "Measure value migration", "detail": "Classifies whether composite value is balanced or moving directionally."},
                {"title": "Wait for break and retest", "detail": "Requires the stock-specific breakout and return conditions from the development preset."},
                {"title": "Use preset-defined management", "detail": "Stop, target and maximum hold are supplied by the instrument preset."},
            ],
            "risk_note": "Development preset; risk and execution behavior are not offered as production-ready.",
            "price": 149,
            "accent": "sky",
        }
    elif label.startswith("Auction Market "):
        instrument = label.removeprefix("Auction Market ")
        meta = {
            "strategy": "Auction-market value area",
            "tagline": f"Composite value and breakout/retest logic for {instrument}.",
            "description": f"Applies the objective technical layer of an auction-market framework to {instrument}: composite profile location, value migration and break/retest execution.",
            "session": "H4/D1 swing",
            "logic_audit": "Development logic summary",
            "logic_audit_note": "This entry remains under development and is not offered as a completed product.",
            "logic": [
                {"title": "Build composite value", "detail": "Calculates POC, VAH and VAL over the configured technical lookback."},
                {"title": "Classify value behavior", "detail": "Measures whether value is balanced or migrating."},
                {"title": "Wait for auction confirmation", "detail": "Looks for the configured failed-auction or break-and-retest condition."},
                {"title": "Apply instrument management", "detail": "Target and maximum hold come from the symbol-specific development preset."},
            ],
            "risk_note": "Development preset; risk and execution behavior are not offered as production-ready.",
            "price": 229 if instrument not in {"XAU", "XAG"} else 299,
            "accent": "teal",
        }
    else:
        meta = {
            "strategy": "Rules-based MT5 automation",
            "tagline": f"The active {canonical} configuration from the installer.",
            "description": "This page is generated from the current active BAT portfolio entry and its supplied settings file.",
            "session": "Preset-defined",
            "logic_audit": "Preset summary",
            "logic_audit_note": "A dedicated source-level explanation has not yet been connected for this entry.",
            "logic": [
                {"title": "Read market context", "detail": "Uses the symbol and timeframe configured by the installer."},
                {"title": "Wait for a deterministic signal", "detail": "Entry behavior is controlled by the supplied EA and preset."},
                {"title": "Calculate deployment size", "detail": "Risk inputs are supplied by the active installer configuration."},
                {"title": "Manage the position", "detail": "Stops, targets and exits follow the EA's configured rules."},
            ],
            "risk_note": "Preset-defined risk; verify the generated settings on the connected broker before live use.",
            "price": 199,
            "accent": "slate",
        }
    if canonical in {"XAUUSD", "XAGUSD"}:
        category, asset_group = "Metals", "metals"
    elif canonical in {"USTEC", "US30", "SP500"}:
        category, asset_group = "Indices", "indices"
    elif canonical in {"BTCUSD", "ETHUSD"}:
        category, asset_group = "Crypto", "crypto"
    elif canonical in {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD", "GBPJPY"}:
        category, asset_group = "Forex", "forex"
    else:
        category, asset_group = "Stocks", "stocks"
    meta["category"] = category
    meta["asset_group"] = asset_group
    return meta


def _buy_url(label: str, price: int) -> str:
    text = (
        f"Hello Calyx, I want to buy {label} for USD {price}. "
        "Please confirm compatibility, license terms and delivery details."
    )
    if not WHATSAPP_NUMBER:
        return CONTACT_URL
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote_plus(text)}"


@lru_cache(maxsize=1)
def get_catalog() -> list[Product]:
    selected = _selected_portfolio_evidence()
    one_year = _one_year_evidence()
    filtered = _filtered_markov_evidence()
    all_safe = _all_markov_safe_evidence()
    xau_markov = _xau_markov_evidence()
    nasdaq_open = _nasdaq_open_one_year_evidence()
    nasdaq_open_safe = _nasdaq_open_safe_evidence()
    us100_orb_rr05 = _us100_orb_one_year_evidence("0.5R")
    us100_orb_rr20 = _us100_orb_one_year_evidence("2R")
    fabio_orb = _fabio_orb_one_year_evidence()
    btc_fvg = _top_down_fvg_one_year_evidence("BTCUSD")
    eth_fvg = _top_down_fvg_one_year_evidence("ETHUSD")
    eth_fvg_safe = _eth_fvg_safe_evidence()
    nasdaq_overnight = _nasdaq_overnight_current_evidence()
    btc_poc_fib = _poc_fib_btc_evidence()
    xau_engineered = _engineered_liquidity_evidence("XAUUSD")
    btc_engineered = _engineered_liquidity_evidence("BTCUSD")
    xau_engineered_safe = _engineered_liquidity_evidence("XAUUSD", safe=True)
    btc_engineered_safe = _engineered_liquidity_evidence("BTCUSD", safe=True)
    ema3_xau = _ema3_xau_evidence()
    ema3_xau_safe = _ema3_xau_evidence(safe=True)
    xau_weakness = _xau_weakness_evidence()
    xau_weakness_safe = _xau_weakness_evidence(safe=True)
    rsi_vwap_xau = _rsi_vwap_xau_evidence()
    trend_progression_xau = _trend_progression_xau_evidence()
    elliott_wave_xau = _elliott_wave_xau_evidence()
    slow_trend_xau = _slow_trend_xau_evidence()
    regime_switch_xau = _regime_switch_xau_evidence()
    session_vwap_xag = _session_vwap_xag_evidence()
    month_end_flow_us100 = _month_end_flow_us100_evidence()
    orb_h1_us100 = _orb_h1_us100_evidence()
    selective_orb_v3 = _selective_orb_v3_evidence()
    sell_nasdaq_15m = _sell_nasdaq_15m_evidence()
    sell_nasdaq_15m_safe = _sell_nasdaq_15m_safe_evidence()
    sell_nasdaq_15m_dynamic = _sell_nasdaq_15m_dynamic_evidence()
    london_open_usdjpy = _london_open_usdjpy_evidence()
    xau_squeeze_standard = _xau_squeeze_momentum_evidence("standard")
    xau_squeeze_safe = _xau_squeeze_momentum_evidence("safe")
    xau_squeeze_high_win = _xau_squeeze_momentum_evidence("high-win-075")
    dmc_evidence = _dmc_evidence()
    orb_volume_high_win = _orb_volume_high_win_evidence()
    orb_volume_confirmed = _orb_volume_confirmed_evidence()
    news_pulse_evidence = {
        label: _news_pulse_hard_evidence(label)
        for label in ("News Pulse XAU", "News Pulse XAG", "News Pulse BTC")
    }
    orb_session_evidence = {
        label: _orb_session_evidence(label) for label in ORB_SESSION_PRODUCTS
    }
    products: list[Product] = []
    for item in parse_installer_items():
        meta = _meta_for(item)
        evidence = one_year.get(item["label"])
        if item["label"] == "Nasdaq 5M Candle Momentum":
            evidence = nasdaq_open
        elif item["label"] == "US100 ORB 0.5R":
            evidence = us100_orb_rr05
        elif item["label"] == "US100 ORB 2R":
            evidence = us100_orb_rr20
        elif item["label"] == "US100 Fabio ORB 1R":
            evidence = fabio_orb
        elif item["label"] == "BTC Top Down FVG Liquidity":
            evidence = btc_fvg
        elif item["label"] == "ETH Top Down FVG Liquidity":
            evidence = eth_fvg
        elif item["label"] == "BTC POC Fibonacci":
            evidence = btc_poc_fib
        elif item["label"] == "Engineered Liquidity XAU":
            evidence = xau_engineered
        elif item["label"] == "Engineered Liquidity BTC":
            evidence = btc_engineered
        elif item["label"] == "XAU RSI VWAP":
            evidence = rsi_vwap_xau
        elif item["label"] == "XAU Trend Progression":
            evidence = trend_progression_xau
        elif item["label"] == "XAU Elliott Wave 1-2-3":
            evidence = elliott_wave_xau
        elif item["label"] == "XAU Slow Trend":
            evidence = slow_trend_xau
        elif item["label"] == "XAU Regime Switch":
            evidence = regime_switch_xau
        elif item["label"] == "XAG Session VWAP Snapback":
            evidence = session_vwap_xag
        elif item["label"] == "US100 Month End Flow":
            evidence = month_end_flow_us100
        elif item["label"] == "US100 H1 ORB 13UTC":
            evidence = orb_h1_us100
        elif item["label"] == "US100 Selective ORB V3":
            evidence = selective_orb_v3
        elif item["label"] == "Sell Nasdaq 15min":
            evidence = sell_nasdaq_15m
        elif item["label"] == "USDJPY London Open Momentum":
            evidence = london_open_usdjpy
        elif item["label"] == "XAU Squeeze Momentum Standard":
            evidence = xau_squeeze_standard
        elif item["label"] == "XAU Squeeze Momentum High Win 0.75R":
            evidence = xau_squeeze_high_win
        elif item["label"] in dmc_evidence:
            evidence = dmc_evidence[item["label"]]
        elif item["label"] == "ORB Volume Profile High Win 0.75R":
            evidence = orb_volume_high_win
        elif item["label"] == "ORB Volume Profile Volume Confirmed":
            evidence = orb_volume_confirmed
        elif item["label"] in news_pulse_evidence:
            evidence = news_pulse_evidence[item["label"]]
        elif item["label"] in orb_session_evidence:
            evidence = orb_session_evidence[item["label"]]
        if item["label"] in filtered:
            evidence = filtered[item["label"]]
        elif item["label"] == "XAU Markov Regime":
            evidence = xau_markov
        if item["label"] in selected:
            evidence = selected[item["label"]]
        if item["label"] == "ETH Top Down FVG Liquidity" and eth_fvg is not None:
            # The focused Step 9.3 audit supersedes the older portfolio-wide
            # exit comparison for this strategy.
            evidence = eth_fvg
        if item["label"] == "AAA Final EMA3" and ema3_xau is not None:
            # Step 7 supersedes the older selected-portfolio exit comparison.
            evidence = ema3_xau
        if item["label"] == "AAA Final XAU Weakness" and xau_weakness is not None:
            # Step 8 supersedes the older portfolio-wide exit comparison.
            evidence = xau_weakness
        if item["label"] == "Nasdaq Overnight" and nasdaq_overnight is not None:
            # The overnight EA was independently re-optimized after the selected
            # portfolio audit. Prefer its fresh exact-active locked result.
            evidence = nasdaq_overnight
        if item["label"] == "Nasdaq 5M Candle Momentum" and nasdaq_open is not None:
            # Step 11 supersedes the older selected-portfolio reconstruction.
            evidence = nasdaq_open
        one_year_result = evidence
        safe_supported = bool(item["supports_safe_filter"])
        safe_evidence = all_safe.get(item["label"]) if safe_supported else None
        if safe_supported and item["label"] in filtered:
            safe_evidence = filtered[item["label"]]
        elif item["label"] == "Nasdaq 5M Candle Momentum":
            safe_evidence = nasdaq_open_safe
        elif item["label"] == "XAU Markov Regime":
            safe_evidence = xau_markov
        elif item["label"] == "Engineered Liquidity XAU":
            safe_evidence = xau_engineered_safe
        elif item["label"] == "Engineered Liquidity BTC":
            safe_evidence = btc_engineered_safe
        elif item["label"] == "ETH Top Down FVG Liquidity" and eth_fvg_safe is not None:
            safe_evidence = eth_fvg_safe
        elif item["label"] == "AAA Final EMA3" and ema3_xau_safe is not None:
            safe_evidence = ema3_xau_safe
        elif item["label"] == "AAA Final XAU Weakness" and xau_weakness_safe is not None:
            safe_evidence = xau_weakness_safe
        elif item["label"] == "Sell Nasdaq 15min":
            safe_evidence = sell_nasdaq_15m_safe
        elif item["label"] == "XAU Squeeze Momentum Standard":
            safe_evidence = xau_squeeze_safe
        if item["label"] == "AAA Final XAU Weakness" and xau_weakness_safe is not None:
            # Supersede the older portfolio-wide filter comparison with the
            # exact M30/4R Full Safe audit promoted in Step 8.
            safe_evidence = xau_weakness_safe
        recommended_safe_mode = bool(item["recommended_safe_mode"] and safe_supported and safe_evidence is not None)
        recommended_dynamic_mode = bool(
            item["recommended_dynamic_mode"]
            and item["label"] == "Sell Nasdaq 15min"
            and sell_nasdaq_15m_dynamic is not None
        )
        limitations = [
            "Historical returns are not guaranteed and live execution can differ.",
            "Broker symbol names, spread, slippage and contract size affect results.",
        ]
        if item["optional_symbol"]:
            limitations.append("This BAT entry is optional and only installs when the broker exposes a compatible symbol.")
        if evidence and evidence.caution:
            limitations.append(evidence.caution)
        if not safe_supported:
            if item["label"] == "Nasdaq Overnight":
                limitations.append("The embedded Markov gate was natively validated and rejected for deployment because it materially reduced return and sample size. Full Safe therefore preserves the stronger Standard inputs for this EA.")
            else:
                limitations.append("No embedded Markov-gate version has been validated for this EA, so Full Safe installs it with the same locked native inputs as Standard mode.")
        price = int(meta["price"])
        display_label = (
            "News Pulse"
            if item["label"].startswith("AAA Final News Pulse")
            else re.sub(r"^AAA Final\s+", "", item["label"]).strip()
        )
        development = item["label"].startswith("Auction ")
        selected_config = SELECTED_CONFIGS.get(item["label"])
        exit_mode = selected_config[2] if selected_config else "Current EA exits"
        if recommended_dynamic_mode and item["label"] == "Sell Nasdaq 15min":
            exit_mode = "ATR 2.5 stop / fixed 3R / no trailing"
        is_poc_fib = item["label"] == "BTC POC Fibonacci"
        is_standalone_orb = item["label"] in STANDALONE_ORB_LABELS
        if is_poc_fib:
            deployment_session = "New York broker-session window"
            deployment_note = " The dated Best Recommended installer preserves its optimized fixed 5R exit, disables trailing, and keeps its selected New York broker-session restriction."
        elif item["label"] in {"XAU Regime Switch", "XAG Session VWAP Snapback", "US100 Month End Flow", "USDJPY London Open Momentum", "DMC Current XAU", "DMC Fresh Reaction XAU", "DMC Fresh Reaction US100"}:
            deployment_session = meta["session"]
            deployment_note = f" Every portfolio BAT installs this selected calendar/session configuration on its own chart with {exit_mode.lower()}; the user's selected risk applies and defaults to 1%."
        elif is_standalone_orb:
            deployment_session = meta["session"]
            deployment_note = f" Every portfolio BAT installs this standalone session as its own chart with {exit_mode.lower()} and a unique magic number."
        else:
            deployment_session = "All day / native strategy window"
            deployment_note = f" The dated Best Recommended installer applies {exit_mode.lower()} and does not add a research-session restriction."
        if recommended_safe_mode:
            deployment_note += " Its independently validated completed-D1 Safe gate is enabled by default in the Best Recommended portfolio."
        if recommended_dynamic_mode:
            deployment_note += " Its Dynamic London ATR-stop/3R preset is enabled by default in the Best Recommended portfolio."
        logic_steps = [dict(step) for step in meta["logic"]]
        if logic_steps:
            if exit_mode == "Dynamic 50/20":
                logic_steps[-1]["detail"] += (
                    " Applied BAT overlay: on each newly completed M15 candle, a close at least 50% of the "
                    "original entry-to-target path moves the stop to lock 20% of that path. If the trade has "
                    "no target, the original stop distance is used as the reference."
                )
            elif exit_mode == "Dynamic 60/20 only":
                logic_steps[-1]["detail"] += (
                    " Applied BAT overlay: on each newly completed M15 candle, a close at least 60% of the "
                    "original entry-to-target path moves the stop to lock 20% of that path. Native R-trailing "
                    "is disabled in this selected preset."
                )
            else:
                logic_steps[-1]["detail"] += (
                    " The Dynamic 50/20 overlay is disabled in this selected preset, so the EA retains its "
                    "original stop and exit behavior."
                )
        products.append(
            Product(
                label=display_label,
                installer_label=item["label"],
                canonical=item["canonical"],
                period_minutes=item["period_minutes"],
                expert=item["expert"],
                expert_source=item["expert_source"],
                set_source=item["set_source"],
                safe_set_source=item["safe_set_source"],
                dynamic_expert_source=(
                    r"Sell Nasdaq 15min Research 2026-09-08\Dynamic Exit Research\EA\Sell Nasdaq 15min Dynamic Exit Research EA.ex5"
                    if item["label"] == "Sell Nasdaq 15min"
                    else None
                ),
                dynamic_set_source=(
                    r"Sell Nasdaq 15min Research 2026-09-08\Dynamic Exit Research\Sets\Sell Nasdaq 15min - london-safe dynamic exit candidate - 1pct.set"
                    if item["label"] == "Sell Nasdaq 15min"
                    else None
                ),
                optional_symbol=item["optional_symbol"],
                slug=slugify(display_label),
                timeframe=TIMEFRAMES.get(item["period_minutes"], f"{item['period_minutes']}m"),
                category=meta["category"],
                asset_group=meta["asset_group"],
                strategy=meta["strategy"],
                tagline=meta["tagline"],
                description=(
                    meta["description"]
                    + deployment_note
                ),
                session=meta["session"],
                exit_mode=exit_mode,
                deployment_session=deployment_session,
                risk_note=meta["risk_note"],
                logic_audit=meta["logic_audit"],
                logic_audit_note=meta["logic_audit_note"],
                logic=logic_steps,
                limitations=limitations,
                price=price,
                accent=meta["accent"],
                featured=bool(meta.get("featured", False)),
                development=development,
                safe_filter_supported=safe_supported,
                recommended_safe_mode=recommended_safe_mode,
                safe_mode_label="London Safe" if item["label"] == "Sell Nasdaq 15min" else "Full Safe",
                safe_mode_note=(
                    "Dedicated 600/1000 preset requiring the preceding bearish London candle; the rejected Markov gate stays off."
                    if item["label"] == "Sell Nasdaq 15min"
                    else "Independent completed-D1 Markov gate enabled inside this EA."
                ),
                dynamic_mode_supported=bool(item["label"] == "Sell Nasdaq 15min" and sell_nasdaq_15m_dynamic),
                recommended_dynamic_mode=recommended_dynamic_mode,
                dynamic_mode_label="Dynamic London",
                dynamic_mode_note=(
                    "Saved research preset: bearish London confirmation, ATR(14) × 2.5 stop and 3R target. "
                    "The full portfolio audit selected it as the Best Recommended BAT default; Standard and London Safe remain available for comparison."
                ),
                evidence=evidence,
                safe_evidence=safe_evidence,
                dynamic_evidence=sell_nasdaq_15m_dynamic if item["label"] == "Sell Nasdaq 15min" else None,
                one_year_evidence=one_year_result,
                one_year_return_pct=one_year_result.return_pct if one_year_result else None,
                one_year_note=None,
                buy_url="" if development else _buy_url(display_label, price),
            )
        )
    return products


def get_sellable_catalog() -> list[Product]:
    return [product for product in get_catalog() if not product.development]


def get_development_catalog() -> list[Product]:
    return [product for product in get_catalog() if product.development]


def get_product(slug: str) -> Product | None:
    return next((product for product in get_sellable_catalog() if product.slug == slug), None)


def package_buy_url(package_name: str, price: int) -> str:
    text = (
        f"Hello Calyx, I am interested in the {package_name} for USD {price}. "
        "Please confirm the included EAs, compatibility, license and delivery terms."
    )
    if not WHATSAPP_NUMBER:
        return CONTACT_URL
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote_plus(text)}"
