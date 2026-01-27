# Market Regime Monitor

Daily market regime signals built from macro and market inputs, published to GitHub Pages.

Live dashboard: https://antomba.github.io/market-regime-monitor/

## Repo layout
- `docs/`: GitHub Pages site + static data for the frontend
- `data/`: generated signal snapshots for local use
- `scripts/`: build pipeline for signals

## Automation
This repo runs a weekday GitHub Actions workflow that rebuilds signals and updates `data/` and `docs/data/`.

## Data outputs
- `latest.json` is written daily for the frontend.
- `history.sqlite` stores the full daily history (upserted by date).
