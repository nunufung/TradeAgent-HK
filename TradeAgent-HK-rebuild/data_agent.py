"""Compatibility wrapper for legacy imports.

Production code no longer fabricates option chains. Use tradeagent.data.market for
stock data and tradeagent.data.options.load_verified_csv for option observations.
"""
from tradeagent.config import load_watchlist
from tradeagent.data.market import fetch_watchlist


class DataAgent:
    def get_stock_snapshots(self):
        stocks, errors = fetch_watchlist(load_watchlist())
        return stocks, errors

    def get_chains(self):
        raise RuntimeError("Synthetic option chains were removed. Supply verified data/options.csv instead.")
