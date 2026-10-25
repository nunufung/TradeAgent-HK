"""Trace real TradingAgents graph stream without logging messages or model text.

Mirrors the pinned TradingAgentsGraph._run_graph debug state aggregation,
decision persistence, and checkpoint handling; no model output is serialized.
"""
from __future__ import annotations

REPORTS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

def propagate_traced(graph, ticker, trade_date, underlying, run_config_fn, emit):
    """Run the actual graph ONCE and record when each nonempty report first appears.

    IMPORTANT: An observed report event proves output availability, NOT node start
    or a sequential analyst handoff. Four analysts can run concurrently.
    """
    from tradingagents.agents.rating import run_rating
    with run_config_fn(graph.config), graph.checkpoint_scope(ticker, trade_date, "stock", None) as thread:
        initial = graph.create_run_state(ticker, trade_date, "stock", None)
        args = graph.propagator.get_graph_args()
        if thread is not None:
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = thread
        graph_input = graph.checkpoint_input(initial)
        final_state = {}
        seen = set()
        for _messages, partial in graph.stream_run(graph_input, **args):
            if not isinstance(partial, dict):
                continue
            final_state.update(partial)
            for role, key in REPORTS.items():
                if role not in seen and isinstance(partial.get(key), str) and partial[key].strip():
                    emit("REPORT_OBSERVED", ticker=underlying, role=role, state="OBSERVED")
                    seen.add(role)
        # Same persistence/cleanup behavior as the pinned graph's _run_graph.
        graph.record_decision(ticker, trade_date, final_state)
        graph.clear_checkpoint_on_success(ticker, trade_date, "stock", None)
        return final_state, run_rating(final_state)
