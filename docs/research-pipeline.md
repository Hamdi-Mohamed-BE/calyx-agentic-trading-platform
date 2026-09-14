# Research and validation pipeline

## Inputs

The audit command accepts a native MetaTrader 5 HTML report, the number of configurations explored during development, a strategy name and an output directory. Optional policy inputs define account loss limits and broker-specific execution costs.

## Evidence produced

- Native report metrics and reconstructed closed-trade cash flows
- Wilson confidence interval for win rate
- Chronological subperiod stability and recent-half profit factor
- Daily expected shortfall
- Deflated Sharpe probability adjusted for the number of configurations tested
- 10,000-path block-bootstrap distributions for return, profit factor and drawdown
- Daily and total loss-limit breach probability proxies
- Broker-specific spread, commission and slippage stress verdicts

## Promotion rule

The default policy favors repeatable evidence rather than peak return. A candidate must have an adequate sample, positive conservative bootstrap bounds, profitable chronological coverage, strong adjusted Sharpe probability and acceptable loss-limit risk. Missing execution-cost assumptions are disclosed, never invented.

## Example

```powershell
python -m agentic_flow.calyx_pipeline `
  --report "C:\path\to\locked-report.htm" `
  --name "Candidate strategy" `
  --tested-configurations 144 `
  --output ".\local-results"
```

Generated results are intentionally ignored by Git. Review the command help for the complete set of risk and cost-stress arguments:

```powershell
python -m agentic_flow.calyx_pipeline --help
```

## Optional macro layer

Set `FXMD_API_KEY` locally when authenticated historical coverage is required. The client redacts the key in request metadata and enforces point-in-time and coverage checks before macro evidence can affect a decision.

