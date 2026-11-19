import streamlit as st
import plotly.graph_objects as go

from data import get_stock, get_metrics, fmt, get_overview, build_summary, get_analyst_view
from simulation import estimate_params, run_monte_carlo, summarize_simulation, choose_drift, fan_chart
from signal_model import recommend

st.set_page_config(page_title="Stock Analysis Dashboard", page_icon="📈", layout="wide")


# ---------- Data loading (cached) ----------
@st.cache_data(ttl=3600, show_spinner=False)
def load(ticker):
    return get_stock(ticker)


# ---------- Sidebar ----------
st.sidebar.title("📈 Stock Dashboard")
ticker = st.sidebar.text_input("Ticker", "AAPL").strip().upper()
months = st.sidebar.slider("Simulation horizon (months)", 1, 12, 3)
n_sims = st.sidebar.select_slider("Number of simulations", [1_000, 5_000, 10_000, 25_000], value=10_000)
drift_label = st.sidebar.selectbox(
    "Drift assumption",
    ["Risk-free (~4%/yr)", "Zero", "Historical (past year)"],
    help="Historical drift can be extreme after a big run-up or crash.",
)
drift_mode = {"Risk-free (~4%/yr)": "risk_free", "Zero": "zero",
              "Historical (past year)": "historical"}[drift_label]

if not ticker:
    st.info("Enter a ticker in the sidebar to get started.")
    st.stop()

with st.spinner(f"Loading {ticker}..."):
    try:
        info, history = load(ticker)
    except Exception as e:
        st.error(f"Couldn't load data for {ticker}: {e}")
        st.stop()

if history.empty:
    st.error(f"No price data found for **{ticker}**. Check the symbol and try again.")
    st.stop()


# ---------- Calculations ----------
metrics = get_metrics(info)
overview = get_overview(info)
analyst = get_analyst_view(info)
price = history["Close"].iloc[-1]
prev = history["Close"].iloc[-2]
mu, sigma = estimate_params(history)

# Simulation the user controls (for the chart)
paths = run_monte_carlo(price, choose_drift(mu, drift_mode), sigma, days=months * 21, n_sims=n_sims)
sim = summarize_simulation(paths)

# Signal always uses a fixed 3-month risk-free simulation, so the rating
# doesn't change just because someone moves a sidebar slider.
signal_paths = run_monte_carlo(price, choose_drift(mu, "risk_free"), sigma, days=63, n_sims=10_000, seed=0)
result = recommend(metrics, history, summarize_simulation(signal_paths))


# ---------- Header ----------
st.title(f"{overview['Name'] or ticker} ({ticker})")
st.caption(" · ".join(x for x in [overview["Sector"], overview["Industry"], overview["HQ"]] if x))

row1 = st.columns(6)
row1[0].metric("Price", fmt("Price", price), f"{(price / prev - 1):+.2%}")
for col, name in zip(row1[1:], ["Market Cap", "Trailing P/E", "Forward P/E", "EPS (TTM)", "Dividend Yield"]):
    col.metric(name, fmt(name, metrics[name]))

row2 = st.columns(6)
for col, name in zip(row2[:5], ["Profit Margin", "Revenue Growth", "PEG Ratio", "Price/Book", "Beta"]):
    col.metric(name, fmt(name, metrics[name]))
row2[5].metric("52W Range", f"{fmt('52W Low', metrics['52W Low'])} – {fmt('52W High', metrics['52W High'])}")

st.divider()


# ---------- Summary + Signal ----------
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("Summary")
    st.write(build_summary(info, metrics))

    with st.expander("Company overview"):
        st.write(overview["Description"] or "No description available.")
        if overview["Employees"]:
            st.caption(f"Employees: {overview['Employees']:,}")
        if overview["Website"]:
            st.caption(f"Website: {overview['Website']}")

with right:
    st.subheader("Model Signal")
    rating, score = result["Rating"], result["Score"]
    box = {"BUY": st.success, "HOLD": st.warning, "SELL": st.error}[rating]
    box(f"### {rating}  \nComposite score: **{score:+.2f}** (range −1 to +1)")

    for name, f in result["Factors"].items():
        if f["score"] is None:
            st.caption(f"**{name}**: skipped. {f['reason']}")
        else:
            st.progress((f["score"] + 1) / 2, text=f"{name}: {f['score']:+.2f}")
            st.caption(f["reason"])

    st.subheader("Analyst Consensus")
    a1, a2 = st.columns(2)
    consensus = (analyst["Consensus"] or "N/A").replace("_", " ").upper()
    a1.metric("Rating", consensus, help=f"{analyst['# Analysts'] or 0} analysts")
    if analyst["Target Mean"]:
        a2.metric("Mean Target", f"${analyst['Target Mean']:,.2f}",
                  f"{analyst['Target Mean'] / price - 1:+.1%} vs. price")

st.divider()


# ---------- Charts ----------
tab_mc, tab_hist = st.tabs(["🎲 Monte Carlo Simulation", "📉 Price History"])

with tab_mc:
    st.plotly_chart(fan_chart(paths, ticker), use_container_width=True)
    c = st.columns(5)
    c[0].metric("Median Price", f"${sim['Median Final']:,.2f}", f"{sim['Median Final'] / price - 1:+.1%}")
    c[1].metric("5th Percentile", f"${sim['5th Percentile']:,.2f}")
    c[2].metric("95th Percentile", f"${sim['95th Percentile']:,.2f}")
    c[3].metric("Prob. of Gain", f"{sim['Prob. of Gain']:.0%}")
    c[4].metric("VaR (95%)", f"{sim['VaR (95%)']:.1%}")
    st.caption(
        f"{n_sims:,} simulated paths over {months} month(s) using geometric Brownian motion. "
        f"Annualized volatility: {sigma * 252 ** 0.5:.1%}. Drift: {drift_label}."
    )

with tab_hist:
    close = history["Close"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=close.index, y=close, name="Close", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=close.index, y=close.rolling(50).mean(), name="50-day MA", line=dict(dash="dot")))
    fig.add_trace(go.Scatter(x=close.index, y=close.rolling(200).mean(), name="200-day MA", line=dict(dash="dash")))
    fig.update_layout(title=f"{ticker}: 2-year price history", yaxis_title="Price ($)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Model signal is a transparent rule-based score for educational purposes, not investment advice. "
           "Data via Yahoo Finance (yfinance).")
