# Security, privacy and repository scope

This repository is a clean portfolio and documentation boundary, not the production trading workspace.

## Included

- Portfolio-safe website source and branding assets
- Complete store backend, all Jinja pages/partials, frontend JavaScript/CSS, original tests, and sanitized maintenance tooling
- Reusable statistical audit code
- Point-in-time macro/calendar tooling
- Explicit promotion policy
- Architecture and operating documentation
- Sanitized, package-loadable master-agent and MCP-bootstrap prompts
- Tests for the public surface

## Never included

- MetaTrader EA or include source (`.mq4`, `.mq5`, `.mqh`)
- Compiled trading programs (`.ex4`, `.ex5`)
- Strategy presets or terminal configuration (`.set`, `.ini`, `.tpl`)
- Broker credentials, API keys, account identifiers or live telemetry
- Tick histories, backtest reports, generated evidence caches or logs
- Deployment scripts that expose private hosts or local machine paths

The `.gitignore` treats these as denied classes. A pre-push audit should still scan the entire tracked tree, because ignore rules cannot remove a file that was already added.

Sensitive runtime values have been replaced with environment variables. The copied public code contains no default broker login, server, private IP address, personal contact number, credential, or account telemetry. Live MT5 polling is disabled unless explicitly enabled in a private environment.

The source prompt documents remain in the private workspace. Their public adaptations preserve research and safety behavior while removing personal absolute paths, current account/server identity, private strategy/deployment inventory, and fixed ownership identifiers. Private runtime context must be injected locally and kept untracked.
