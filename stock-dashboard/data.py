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

def get_overview(info: dict) -> dict:
    city, state, country = info.get("city"), info.get("state"), info.get("country")
    hq = ", ".join(p for p in [city, state, country] if p)
    return {
        "Name":        info.get("longName") or info.get("shortName"),
        "Ticker":      info.get("symbol"),
        "Sector":      info.get("sector"),
        "Industry":    info.get("industry"),
        "HQ":          hq or None,
        "Employees":   info.get("fullTimeEmployees"),
        "Website":     info.get("website"),
        "Description": info.get("longBusinessSummary"),
    }

def range_position(price, low, high):
    """0 = at 52-week low, 1 = at 52-week high."""
    if None in (price, low, high) or high == low:
        return None
    return (price - low) / (high - low)

def build_summary(info: dict, metrics: dict) -> str:
    name = info.get("shortName", info.get("symbol", "This company"))
    lines = []

    # Valuation
    pe, fpe = metrics["Trailing P/E"], metrics["Forward P/E"]
    if pe is None:
        lines.append(f"{name} has no trailing P/E, which usually means it isn't currently profitable.")
    elif pe < 15:
        lines.append(f"At a trailing P/E of {pe:.1f}, {name} trades at a value-style multiple.")
    elif pe < 30:
        lines.append(f"At a trailing P/E of {pe:.1f}, {name} is moderately valued.")
    else:
        lines.append(f"At a trailing P/E of {pe:.1f}, {name} is priced for strong future growth.")
    if pe and fpe:
        if fpe < pe * 0.85:
            lines.append("Its forward P/E is noticeably lower, so analysts expect earnings to grow.")
        elif fpe > pe * 1.15:
            lines.append("Its forward P/E is higher, so analysts expect earnings to shrink.")

    # Profitability and growth
    margin, growth = metrics["Profit Margin"], metrics["Revenue Growth"]
    if margin is not None:
        quality = "strong" if margin > 0.20 else "healthy" if margin > 0.08 else "thin" if margin > 0 else "negative"
        lines.append(f"Profit margins are {quality} at {margin * 100:.1f}%.")
    if growth is not None:
        direction = "grew" if growth >= 0 else "shrank"
        lines.append(f"Revenue {direction} {abs(growth) * 100:.1f}% year over year.")

    # Where the price sits
    pos = range_position(metrics["Price"], metrics["52W Low"], metrics["52W High"])
    if pos is not None:
        if pos > 0.85:
            lines.append("The stock is trading near its 52-week high.")
        elif pos < 0.15:
            lines.append("The stock is trading near its 52-week low.")
        else:
            lines.append(f"The stock sits {pos * 100:.0f}% of the way up its 52-week range.")

    # Risk
    beta = metrics["Beta"]
    if beta is not None:
        if beta > 1.3:
            lines.append(f"With a beta of {beta:.2f}, it tends to swing more than the overall market.")
        elif beta < 0.8:
            lines.append(f"With a beta of {beta:.2f}, it tends to be steadier than the overall market.")

    return " ".join(lines)

def get_analyst_view(info: dict) -> dict:
    return {
        "Consensus":    info.get("recommendationKey"),   # e.g. "buy", "hold"
        "Target Mean":  info.get("targetMeanPrice"),
        "Target Low":   info.get("targetLowPrice"),
        "Target High":  info.get("targetHighPrice"),
        "# Analysts":   info.get("numberOfAnalystOpinions"),
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
        metrics = get_metrics(info)
        overview = get_overview(info)

        print(f"\n=== {overview['Name']} ({overview['Ticker']}) ===")
        print(f"{overview['Sector']} / {overview['Industry']} | {overview['HQ']}")
        print(f"\nSUMMARY: {build_summary(info, metrics)}")
        print(f"\nANALYSTS: {get_analyst_view(info)}")
