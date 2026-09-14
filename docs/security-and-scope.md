# Security, privacy and repository scope

This repository is a clean portfolio and documentation boundary, not the production trading workspace.

## Included

- Portfolio-safe website source and branding assets
- Reusable statistical audit code
- Point-in-time macro/calendar tooling
- Explicit promotion policy
- Architecture and operating documentation
- Tests for the public surface

## Never included

- MetaTrader EA or include source (`.mq4`, `.mq5`, `.mqh`)
- Compiled trading programs (`.ex4`, `.ex5`)
- Strategy presets or terminal configuration (`.set`, `.ini`, `.tpl`)
- Broker credentials, API keys, account identifiers or live telemetry
- Tick histories, backtest reports, generated evidence caches or logs
- Deployment scripts that expose private hosts or local machine paths

The `.gitignore` treats these as denied classes. A pre-push audit should still scan the entire tracked tree, because ignore rules cannot remove a file that was already added.

