# Reviewed upstream and source routes

- Repository: https://github.com/Fincept-Corporation/FinceptTerminal
- Reviewed date: 2026-10-25, Asia/Hong_Kong.
- Reviewed source commit: 3d8617cae3f13c93874d4bee4fb0f2846e9c83bc.
- [README](https://github.com/Fincept-Corporation/FinceptTerminal/blob/3d8617cae3f13c93874d4bee4fb0f2846e9c83bc/README.md).
- [Getting started](https://github.com/Fincept-Corporation/FinceptTerminal/blob/3d8617cae3f13c93874d4bee4fb0f2846e9c83bc/docs/GETTING_STARTED.md).
- [Architecture](https://github.com/Fincept-Corporation/FinceptTerminal/blob/3d8617cae3f13c93874d4bee4fb0f2846e9c83bc/docs/ARCHITECTURE.md).
- [License file](https://github.com/Fincept-Corporation/FinceptTerminal/blob/3d8617cae3f13c93874d4bee4fb0f2846e9c83bc/LICENSE).

## Verified layout

The reviewed source contains a native C++20/Qt6 application under fincept-qt, with Python analytics scripts. Source-based setup calls for Python 3.11, Qt 6.8.x and CMake 3.27+ in the getting-started guide. Check the selected revision's manifests for exact build requirements; architecture documents also discuss target states. Building the desktop application is distinct from importing an individual analytics module.

These file paths exist at the reviewed revision; this is source discovery, not a claim that execution, provider access or numerical accuracy has been tested:

| Research area | Actual route |
| --- | --- |
| Yahoo data provider | fincept-qt/scripts/yfinance_data.py |
| Corporate valuation | fincept-qt/scripts/Analytics/corporateFinance/valuation/dcf_model.py |
| Portfolio risk | fincept-qt/scripts/Analytics/portfolioManagement/risk_management.py |
| Backtest abstraction | fincept-qt/scripts/Analytics/backtesting/base/base_provider.py |
| Option pricing wrapper | fincept-qt/scripts/Analytics/fortitudo_tech_wrapper/option_pricing.py |
| IV smile | fincept-qt/scripts/Analytics/options/iv_smile.py |
| IV surface | fincept-qt/scripts/Analytics/options/iv_surface.py |
| Option open interest | fincept-qt/scripts/Analytics/options/oi_tracker.py |

The Analytics README contains an example import from Analytics.derivatives.options, but that corresponding file was absent from the reviewed tree. Do not copy that example as a verified callable interface. Inspect actual files and their definitions before writing any adapter.

## Version and installation procedure

For an explicitly requested installation, use a separate tooling directory and select an official platform-compatible release or build the reviewed revision from source. For source review:

```bash
git clone --filter=blob:none https://github.com/Fincept-Corporation/FinceptTerminal.git /absolute/tooling/FinceptTerminal
git -C /absolute/tooling/FinceptTerminal checkout --detach 3d8617cae3f13c93874d4bee4fb0f2846e9c83bc
```

Resolve a real absolute path first; do not reuse a dirty checkout or discard local changes. Continue with the pinned getting-started instructions for that platform. This Skill registration does not run these installation commands, install a desktop application or enable an account.

The README, getting-started guide and LICENSE contain differing descriptions of edition availability and commercial licensing. Consult the actual license and relevant module notices before copying or redistributing code; do not label the entire project MIT or assume the badge is the complete license. This Skill supplies original operational guidance and upstream links; it does not vendor application source or imply upstream endorsement.

## Evidence standard

Record source/version and actual provider independently. Validate HK symbols (retain leading zeros), exchange/calendar, data age, units, currency and adjustment conventions. Confirm HKEX options coverage rather than assuming US/Indian/crypto connectors apply. Treat delayed prices, estimated values and theoretical Greeks as labeled inputs, not executable prices.

Before report integration, specify a validated artifact schema and consumer, then test success, missing/stale inputs and provider failure without blocking the existing morning deadline. Do not infer that a desktop build supplies a hosted API or that an available MCP registry is connected to this conversation.
