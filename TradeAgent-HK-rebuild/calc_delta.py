import math
from scipy.stats import norm


def bs_delta(S, K, T, r, iv, type="call"):
    if min(S, K, T, iv) <= 0:
        raise ValueError("S, K, T and iv must be positive")
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
    return norm.cdf(d1) if type.lower() == "call" else norm.cdf(d1) - 1


def filter_chain(chain, max_delta=0.10, max_spread=0.30, target_abs_delta=0.08):
    out = []
    for c in chain:
        if c.get("bid", 0) <= 0 or c.get("ask", 0) <= 0:
            continue
        mid = (c["ask"] + c["bid"]) / 2
        spread = (c["ask"] - c["bid"]) / mid if mid > 0 else float("inf")
        if abs(c.get("delta", 999)) <= max_delta and spread <= max_spread:
            row = dict(c)
            row["spread"] = spread
            out.append(row)
    return sorted(out, key=lambda x: abs(abs(x["delta"]) - target_abs_delta))
