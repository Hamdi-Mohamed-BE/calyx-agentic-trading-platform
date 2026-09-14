# Contributing

This repository documents the portfolio-safe surface of Calyx. Contributions should improve the website, public research utilities, tests or documentation without weakening the boundary around proprietary trading assets.

Before opening a pull request:

1. Run `pytest -q`.
2. Confirm no MetaTrader source, include, binary, preset or tick-history file is present.
3. Confirm no credential, broker/account identifier, live telemetry, generated report or local machine path is present.
4. Keep claims evidence-based and preserve the distinction between historical research, demo forward testing and live-capital decisions.

The automated check rejects common MetaTrader source, binary, preset and generated-data extensions. It is a backstop, not a substitute for reviewing the full diff.

