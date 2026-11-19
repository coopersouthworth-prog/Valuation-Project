import numpy as np

# Rough sector P/E benchmarks. These are APPROXIMATE placeholders.
# Replace them with real figures, e.g. from Aswath Damodaran's
# NYU sector datasets (pages.stern.nyu.edu/~adamodar), and cite
# the source and date in your README.
SECTOR_PE = {
    "Technology": 30, "Communication Services": 22, "Consumer Cyclical": 22,
    "Consumer Defensive": 22, "Healthcare": 24, "Financial Services": 15,
    "Industrials": 22, "Energy": 12, "Utilities": 18,
    "Real Estate": 30, "Basic Materials": 18,
}
DEFAULT_PE = 20


def clip(x):
    return float(np.clip(x, -1, 1))
def score_valuation(metrics):
    if metrics["Trailing P/E"] is None:
        return None, "Not currently profitable, so P/E-based valuation is skipped."
    pe = metrics["Forward P/E"] or metrics["Trailing P/E"]
    if pe <= 0 or pe > 150:
        return None, f"P/E of {pe:.0f} is too extreme to compare meaningfully."
    benchmark = SECTOR_PE.get(metrics.get("Sector"), DEFAULT_PE)
    ratio = pe / benchmark                       # 1.0 = in line with sector
    score = clip((1 - ratio) * 2)                # 50% cheaper -> +1, 50% pricier -> -1
    label = "below" if ratio < 1 else "above"
    return score, f"P/E of {pe:.1f} is {abs(1 - ratio):.0%} {label} the sector benchmark of {benchmark}."

def score_quality(metrics):
    margin, growth = metrics["Profit Margin"], metrics["Revenue Growth"]
    parts, reasons = [], []
    if margin is not None:
        parts.append(clip(margin / 0.20))        # 20%+ margin -> +1
        reasons.append(f"margin {margin:.1%}")
    if growth is not None:
        parts.append(clip(growth / 0.15))        # 15%+ growth -> +1
        reasons.append(f"revenue growth {growth:.1%}")
    if not parts:
        return None, "No profitability or growth data."
    return float(np.mean(parts)), "Quality based on " + " and ".join(reasons) + "."


def score_momentum(history):
    close = history["Close"].dropna()
    if len(close) < 200:
        return None, "Not enough price history for momentum."
    price = close.iloc[-1]
    ma50, ma200 = close.rolling(50).mean().iloc[-1], close.rolling(200).mean().iloc[-1]
    ret_6m = price / close.iloc[-126] - 1

    trend = 0.5 * np.sign(price - ma200) + 0.5 * np.sign(ma50 - ma200)
    score = clip(0.6 * trend + 0.4 * clip(ret_6m / 0.25))
    direction = "above" if price > ma200 else "below"
    return score, f"Price is {direction} its 200-day average; 6-month return {ret_6m:.1%}."


def score_simulation(sim_summary):
    p = sim_summary["Prob. of Gain"]
    med_ret = sim_summary["Median Final"] / sim_summary["Start Price"] - 1
    score = clip((p - 0.5) * 4 * 0.6 + clip(med_ret / 0.10) * 0.4)
    return score, f"Simulation gives a {p:.0%} chance of gain, median outcome {med_ret:+.1%}."

WEIGHTS = {"Valuation": 0.30, "Quality": 0.25, "Momentum": 0.20, "Simulation": 0.25}


def recommend(metrics, history, sim_summary):
    factors = {
        "Valuation":  score_valuation(metrics),
        "Quality":    score_quality(metrics),
        "Momentum":   score_momentum(history),
        "Simulation": score_simulation(sim_summary),
    }
    # Drop missing factors and re-normalize the remaining weights
    usable = {k: v for k, v in factors.items() if v[0] is not None}
    total_w = sum(WEIGHTS[k] for k in usable)
    final = sum(WEIGHTS[k] * usable[k][0] for k in usable) / total_w

    if final > 0.25:
        rating = "BUY"
    elif final < -0.25:
        rating = "SELL"
    else:
        rating = "HOLD"

    return {
        "Rating": rating,
        "Score": final,
        "Factors": {k: {"score": v[0], "reason": v[1]} for k, v in factors.items()},
    }

if __name__ == "__main__":
    from data import get_stock, get_metrics
    from simulation import estimate_params, run_monte_carlo, summarize_simulation, choose_drift

    for t in ["AAPL", "RIVN", "KO", "NVDA"]:
        info, history = get_stock(t)
        metrics = get_metrics(info)
        mu, sigma = estimate_params(history)
        paths = run_monte_carlo(history["Close"].iloc[-1], choose_drift(mu, "risk_free"), sigma, seed=42)
        result = recommend(metrics, history, summarize_simulation(paths))

        print(f"\n=== {t}: {result['Rating']} (score {result['Score']:+.2f}) ===")
        for name, f in result["Factors"].items():
            s = "skipped" if f["score"] is None else f"{f['score']:+.2f}"
            print(f"  {name:<11}{s:>8}  {f['reason']}")
