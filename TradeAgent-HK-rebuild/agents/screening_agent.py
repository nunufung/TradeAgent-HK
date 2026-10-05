from tradeagent.engine.rules import rank_options


class ScreeningAgent:
    """Backward-compatible facade over the canonical rule engine."""
    def __init__(self, rules):
        self.rules = rules

    def screen(self, contracts, stocks, on_date):
        return rank_options(contracts, stocks, self.rules, on_date)
