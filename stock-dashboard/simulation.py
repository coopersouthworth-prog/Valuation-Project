import numpy as np
import pandas as pd
import plotly.graph_objects as go

def estimate_params(history: pd.DataFrame, lookback: int = 252):
    """Daily mean and std of log returns over the last `lookback` trading days (~1 year)."""
    closes = history["Close"].dropna().iloc[-(lookback + 1):]
    log_returns = np.log(closes / closes.shift(1)).dropna()
    return log_returns.mean(), log_returns.std()


def run_monte_carlo(start_price: float, mu: float, sigma: float,
                    days: int = 63, n_sims: int = 10_000, seed: int | None = None):
    """
    Returns an array of shape (days + 1, n_sims).
    Row 0 is today's price; each column is one simulated path.
    """
    rng = np.random.default_rng(seed)
    daily_log_returns = rng.normal(mu, sigma, size=(days, n_sims))
    cumulative = np.cumsum(daily_log_returns, axis=0)
    paths = start_price * np.exp(cumulative)
    return np.vstack([np.full(n_sims, start_price), paths])


def summarize_simulation(paths: np.ndarray) -> dict:
    start = paths[0, 0]
    final = paths[-1]
    returns = final / start - 1
    return {
        "Start Price":     start,
        "Median Final":    np.median(final),
        "5th Percentile":  np.percentile(final, 5),
        "95th Percentile": np.percentile(final, 95),
        "Prob. of Gain":   (final > start).mean(),
        "Expected Return": returns.mean(),
        "VaR (95%)":       -np.percentile(returns, 5),   # loss you'd exceed only 5% of the time
    }

def choose_drift(mu_hist: float, mode: str = "historical", annual_rate: float = 0.04):
    """
    'historical' - use the past year's average (can be extreme)
    'zero'       - pure volatility, no directional bias
    'risk_free'  - grow at roughly the Treasury rate (the textbook default)
    """
    if mode == "zero":
        return 0.0
    if mode == "risk_free":
        return np.log(1 + annual_rate) / 252
    return mu_hist

def fan_chart(paths: np.ndarray, ticker: str):
    days = np.arange(paths.shape[0])
    p5, p25, p50, p75, p95 = np.percentile(paths, [5, 25, 50, 75, 95], axis=1)

    fig = go.Figure()
    # 5-95% band
    fig.add_trace(go.Scatter(x=days, y=p95, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=days, y=p5, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(99,110,250,0.15)", name="5–95%"))
    # 25-75% band
    fig.add_trace(go.Scatter(x=days, y=p75, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=days, y=p25, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(99,110,250,0.35)", name="25–75%"))
    # A few sample paths for texture
    for i in range(15):
        fig.add_trace(go.Scatter(x=days, y=paths[:, i], line=dict(width=0.6, color="gray"),
                                 opacity=0.4, showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=days, y=p50, line=dict(width=2.5), name="Median"))

    fig.update_layout(title=f"{ticker}: Monte Carlo price paths",
                      xaxis_title="Trading days from today", yaxis_title="Price ($)")
    return fig

if __name__ == "__main__":
    from data import get_stock

    info, history = get_stock("AAPL")
    mu, sigma = estimate_params(history)
    print(f"Daily mu={mu:.5f}, sigma={sigma:.4f}")
    print(f"Annualized: return ~{mu * 252:.1%}, volatility ~{sigma * 252 ** 0.5:.1%}")

    start = history["Close"].iloc[-1]
    for mode in ["historical", "zero", "risk_free"]:
        paths = run_monte_carlo(start, choose_drift(mu, mode), sigma, seed=42)
        s = summarize_simulation(paths)
        print(f"\n[{mode}] median ${s['Median Final']:.2f} | "
              f"90% range ${s['5th Percentile']:.2f}-${s['95th Percentile']:.2f} | "
              f"P(gain) {s['Prob. of Gain']:.0%} | VaR {s['VaR (95%)']:.1%}")

    import os, webbrowser
    path = os.path.abspath("fan_chart.html")
    fan_chart(paths, "AAPL").write_html(path)
    webbrowser.open("file://" + path)
