# Final deployment outcome

The live lookup is NOT enabled. The free Hugging Face ZeroGPU runtime rejected the CPU-only backend with `No @spaces.GPU function detected during startup`. The original static snapshot dashboard was restored and verified RUNNING in the browser. Backend-only secrets were removed before publishing as static. A suitable CPU backend host is required to activate Futu/public lookup and owner-only paid research. No paid hosting was purchased.

The ZeroGPU Python 3.10 restriction was reproduced; an isolated managed Python 3.11 environment successfully installed the pinned TradingAgents v0.6. Twenty-eight backend/connector/research tests passed under Python 3.10. A timeout-class difference was caught and regression-tested there. The full live frontend/configuration is retained at d6c44a69dc949c7a3830f9d0c23c23754557ae36. No real Mac OpenD connection or paid DeepSeek research run was verified.

---

# Live lookup validation

Plan: 2026-10-30-live-lookup.md. User approved Futu first with public-data fallback.

- 37 focused Python checks pass, including existing public-data privacy tests.
- Six JavaScript checks pass, including unchanged Refresh behavior, source display and submitted-ticker race protection.
- Source syntax, shell syntax, exported snapshot and exact publish allowlist checks pass.
- A genuine Yahoo Finance HK.00700 request returned a provider timestamp and 126 daily candles. Public data is not called guaranteed real time.
- The actual pinned TradingAgents v0.6 graph constructs with all four analysts and the expected instrument-context interface. No paid model call was made by this check.
- A separate reviewer checked security, OAuth, deployment, restart behavior and the quote/research flow. Four issues were fixed with tests that failed before the repair: provider capacity wait timeout; Hong Kong midnight date mismatch against upstream; cached retrieval timestamp preservation; and device-token survival across backend restarts.

## Rulings

- Use the Gradio Python runtime to host FastAPI on the existing Space without requesting another hardware tier; preserve the existing HTML dashboard.
- Owner sign-in is required for Futu data and paid DeepSeek calls. Anonymous visitors get public quotes and calculated commentary, explicitly labelled as separate from the four analysts.
- Use a dedicated, domain-separated HMAC key derived by the existing publisher to issue 30-day connector tokens. The raw publisher token never reaches the running backend. Re-pairing does not revoke old unexpired tokens; publisher-key rotation does. This avoids daily manual pairing after snapshot redeployment.
- Pass the server-local current date to TradingAgents to match its validator; display quote and report timestamps in HKT.

## Whole-repository limits

The complete pytest collection is blocked by the environment's missing WenQuanYi Chinese PDF font. Running while excluding test_news_pdf.py produced 173 passes, three skips and seven failures. Four failures are PDF-font dependent: test_market_pdf_contains_news_and_codes_without_single_stock_price_card, test_pdf_puts_decision_before_news_overview, test_recommendations_and_four_actual_excerpts_survive_pdf, and test_single_stock_pdf_keeps_its_recommendation_section.

The other three failures were reproduced on the unchanged 780c069 baseline: test_daily_pipeline_propagates_book_context_and_records_its_fingerprint, test_daily_profile_preserves_actual_four_analysts_and_limits_generation, and test_gateway_forwards_once_clamps_output_and_blocks_exhausted_calls. They concern the existing daily pipeline and 800/1600-token expectations. They are outside this lookup change and were not altered.

Deployment and browser verification must still be recorded before claiming the feature live. Futu on the actual user Mac and a signed-in paid four-agent request remain unverified until those real paths complete.
