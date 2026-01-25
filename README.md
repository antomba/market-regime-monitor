# Market Regime Monitor

Daily market regime signals built from macro and market inputs, published to GitHub Pages.

Live dashboard: https://antomba.github.io/market-regime-monitor/

## Repo layout
- `docs/`: GitHub Pages site
- `data/`: generated signal snapshots
- `scripts/`: build pipeline for signals

## Automation
This repo runs a weekday GitHub Actions workflow that rebuilds signals and updates `data/` and `docs/data/`.
