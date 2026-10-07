#!/usr/bin/env bash
set -euo pipefail

if [[ "${EVENT_NAME:-}" == "schedule" || "${REPORT_SCOPE:-stock}" == "market" ]]; then
    echo "Market briefing: Hong Kong blue chips, technology stocks and AI news"
    python -u hk_market_briefing.py | tee run_market.log
    python market_recommendations.py --select > market_shortlist.txt
    STOCKS=()
    while IFS= read -r stock; do STOCKS+=("$stock"); done < market_shortlist.txt
    python -u linked_stock_analysis.py "${STOCKS[@]}" --signals stock_signals.json --report stock_analysis.md --market-news market_candidates.json
    python market_recommendations.py
else
    ticker="${TICKER:-700}"
    [[ "$ticker" =~ ^[0-9]{1,5}$ ]] && (( 10#$ticker > 0 )) || { echo "Invalid stock code"; exit 1; }
    echo "Requested stock analysis: $ticker"
    python -u hk_adapter.py "$ticker" | tee "run_${ticker}.log"
fi
