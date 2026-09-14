from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from app.adaptive_portfolio import NEWS_ADAPTIVE_EXEMPTIONS, simulate_adaptive_portfolio
from app.catalog import PACKAGE_ROOT, get_product
from app.evidence_cache import CACHE_ROOT


def trade(slug, number, at, net):
    return {
        'cache_slug': slug, 'ea': NEWS_ADAPTIVE_EXEMPTIONS.get(slug, slug), 'number': number,
        'open_time': at.isoformat(), 'close_time': (at + timedelta(minutes=1)).isoformat(),
        'net_profit': net, 'gross_profit': net + 3, 'commission': -2, 'swap': -1,
        'lots': .1,
    }


@pytest.mark.parametrize('slug', NEWS_ADAPTIVE_EXEMPTIONS)
def test_news_bypasses_daily_stop_drawdown_and_own_loss_streak(slug):
    at = datetime(2026, 1, 5)
    rows = [trade('seed-loss', 1, at, -800)]
    news = [trade(slug, i + 2, at + timedelta(hours=i + 1), -100) for i in range(6)]
    rows += news + [trade('non-news', 9, at + timedelta(hours=8), 100)]
    rows += [trade('non-news', 10, at + timedelta(days=1), 100)]
    result, counters, skips = simulate_adaptive_portfolio(rows)
    actual = [r for r in result if r['cache_slug'] == slug]
    assert len(actual) == 6
    for source, accepted in zip(news, actual):
        assert accepted['risk_multiplier'] == 1
        for field in ('net_profit', 'gross_profit', 'commission', 'swap', 'lots'):
            assert accepted[field] == source[field]
    assert counters['news_exempt_entries'] == 6 and slug not in skips
    assert skips['non-news'] == 1
    # Account drawdown still constrains ordinary entries on the following day.
    assert next(r for r in result if r['number'] == 10)['risk_multiplier'] == .25


def test_non_news_allocation_and_streak_controls_are_unchanged():
    at = datetime(2026, 1, 5)
    rows = [trade('ordinary', i, at + timedelta(days=i), -10) for i in range(6)]
    rows += [trade('nasdaq-5m-candle-momentum', 10, at + timedelta(days=8), 100)]
    result, _, _ = simulate_adaptive_portfolio(rows)
    assert [r['risk_multiplier'] for r in result[:6]] == [1, 1, 1, .5, .5, .25]
    assert result[-1]['risk_multiplier'] == .25


@pytest.mark.parametrize('period', ('6m', '1y', '3y', '5y'))
def test_published_portfolio_retains_every_news_trade_at_original_risk(period):
    def ledger(mode):
        return json.loads((CACHE_ROOT/'portfolio'/mode/f'{period}.trades.json').read_text())
    def key(row):
        return row['cache_slug'], row['open_time'], row['close_time'], row['number']
    originals = {key(r): r for r in ledger('current') if r['cache_slug'] in NEWS_ADAPTIVE_EXEMPTIONS}
    accepted = {key(r): r for r in ledger('recommended-adaptive') if r['cache_slug'] in NEWS_ADAPTIVE_EXEMPTIONS}
    assert originals and originals.keys() == accepted.keys()
    for identity, source in originals.items():
        assert accepted[identity]['risk_multiplier'] == 1
        for field in ('net_profit', 'commission', 'swap'):
            assert source[field] == accepted[identity][field]


def test_all_four_selected_news_presets_explicitly_disable_governor():
    for slug in NEWS_ADAPTIVE_EXEMPTIONS:
        product = get_product(slug)
        text = (PACKAGE_ROOT/product.set_source).read_text(encoding='utf-8-sig')
        assert 'InpAdaptivePortfolioControls=false' in text
        assert 'InpRiskPercent=0.75' in text


@pytest.mark.skipif(sys.platform != 'win32', reason='PowerShell installer contract')
def test_shared_installer_exempts_exactly_four_news_even_with_stale_true_input():
    # Load only pure input-building functions, never the installer entry point.
    script = r'''
$ErrorActionPreference = 'Stop'
$PackageRoot = $env:CALYX_TEST_PACKAGE_ROOT
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PackageRoot '_Auto Deploy\Install-BMTradingPortfolio.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Installer syntax error' }
$names = @('Get-PortfolioItems','Get-EffectiveInputs','Test-NewsAdaptiveExemption')
$functions = $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in $names}, $true)
foreach ($function in $functions) { . ([scriptblock]::Create($function.Extent.Text)) }
function Read-SetInputs([string]$Path) { return [ordered]@{InpRiskPercent='0.75';InpAdaptivePortfolioControls='true'} }
$UseRecommendedSelections=$true; $IsFullSafe=$false; $IsAdaptiveAccount=$true; $IsSmallAccount=$false
$UsesDynamicRisk=$true; $RiskMode='PERCENT'; $GoldNewsRoot=Join-Path $PackageRoot '..\..\AI news'
foreach ($UseAdaptiveProfile in @($true,$false)) {
  $items = @(Get-PortfolioItems)
  $exemptCount = 0
  foreach ($item in $items) {
    $risk = if ($item.LockRisk) { .75 } else { 2 * $item.AdaptiveBaseMultiplier }
    $item | Add-Member EffectiveRiskPercent $risk
    $item | Add-Member EffectiveRisk (10000 * $risk / 100)
    $item | Add-Member EffectiveLot .01
    $item | Add-Member EffectiveStopPercent 1
    $inputs = Get-EffectiveInputs $item
    if (Test-NewsAdaptiveExemption $item) {
      $exemptCount++
      if ($inputs['InpAdaptivePortfolioControls'] -ne 'false' -or $inputs['InpRiskPercent'] -ne '0.75') { throw "News exemption failed: $($item.Label)" }
    } elseif ($UseAdaptiveProfile -and $inputs['InpAdaptivePortfolioControls'] -ne 'true') { throw "Non-News controls disabled: $($item.Label)" }
  }
  if ($items.Count -ne 32 -or $exemptCount -ne 4) { throw 'Wrong exemption scope' }
}
Write-Output 'PASS: 32 EAs, exactly 4 news exemptions, both profile paths, stale true inputs overridden'
'''
    import os
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env={**os.environ, 'CALYX_TEST_PACKAGE_ROOT': str(PACKAGE_ROOT)},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
