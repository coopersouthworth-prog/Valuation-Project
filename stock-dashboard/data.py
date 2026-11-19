import yfinance as yf

def get_stock(ticker: str):
    stock = yf.Ticker(ticker.upper())
    info = stock.info                          # dict of company facts + ratios
    history = stock.history(period="2y")       # daily OHLCV prices
    return info, history

def get_metrics(info: dict) -> dict:
    """Pull the key valuation + size metrics. Missing values stay None."""
    return {
        "Price":           info.get("currentPrice") or info.get("regularMarketPrice"),
        "Market Cap":      info.get("marketCap"),
        "Trailing P/E":    info.get("trailingPE"),
        "Forward P/E":     info.get("forwardPE"),
        "PEG Ratio":       info.get("trailingPegRatio"),
        "EPS (TTM)":       info.get("trailingEps"),
        "Price/Book":      info.get("priceToBook"),
        "Profit Margin":   info.get("profitMargins"),
        "Revenue Growth":  info.get("revenueGrowth"),
        "Dividend Yield":  info.get("dividendYield"),
        "Beta":            info.get("beta"),
        "52W High":        info.get("fiftyTwoWeekHigh"),
        "52W Low":         info.get("fiftyTwoWeekLow"),
    }

def fmt(name: str, value):
    if value is None:
        return "N/A"
    if name == "Market Cap":
        for unit, size in [("T", 1e12), ("B", 1e9), ("M", 1e6)]:
            if value >= size:
                return f"${value / size:.2f}{unit}"
        return f"${value:,.0f}"
    if name in ("Profit Margin", "Revenue Growth"):
        return f"{value * 100:.1f}%"
    if name == "Dividend Yield":
        # yfinance has returned this both as a decimal (0.005) and a percent (0.5)
        return f"{value:.2f}%" if value > 1 else f"{value * 100:.2f}%"
    if name in ("Price", "EPS (TTM)", "52W High", "52W Low"):
        return f"${value:,.2f}"
    return f"{value:.2f}"

if __name__ == "__main__":
    for t in ["AAPL", "RIVN", "KO"]:
        info, history = get_stock(t)
        print(f"\n=== {info.get('longName', t)} ===")
        for name, value in get_metrics(info).items():
            print(f"{name:<16}{fmt(name, value)}")
