"""
market_data.py
Prices and fundamentals for NSE-listed companies via yfinance (free, no key).
NSE symbols get a ".NS" suffix on Yahoo Finance, e.g. RELIANCE -> RELIANCE.NS.
"""
from dataclasses import dataclass, field

INDICES = {"NIFTY 50": "^NSEI", "SENSEX": "^BSESN", "NIFTY BANK": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}


def to_yahoo(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith((".NS", ".BO")) or symbol.startswith("^") else f"{symbol}.NS"


@dataclass
class CompanySnapshot:
    symbol: str
    name: str
    sector: str = ""
    industry: str = ""
    price: float | None = None
    # Fundamentals - fractions (0.18 == 18%) except where noted
    market_cap_cr: float | None = None       # in INR crore
    pe: float | None = None
    pb: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None      # ratio (0.5 == 0.5x)
    operating_margin: float | None = None
    revenue_growth: float | None = None      # latest YoY
    earnings_growth: float | None = None     # latest YoY
    dividend_yield: float | None = None
    # Price trend
    return_1m: float | None = None
    return_3m: float | None = None
    return_1y: float | None = None
    pct_from_52w_high: float | None = None   # negative = below the high
    above_50dma: bool | None = None
    above_200dma: bool | None = None
    extra: dict = field(default_factory=dict)


def _pct(series, days: int) -> float | None:
    if len(series) <= days:
        return None
    return float(series.iloc[-1] / series.iloc[-1 - days] - 1)


def _price_trend(snap: CompanySnapshot, close) -> None:
    if close is None or close.empty:
        return
    snap.price = snap.price or float(close.iloc[-1])
    snap.return_1m, snap.return_3m, snap.return_1y = _pct(close, 21), _pct(close, 63), _pct(close, 250)
    snap.pct_from_52w_high = float(close.iloc[-1] / close.tail(250).max() - 1)
    if len(close) >= 50:
        snap.above_50dma = bool(close.iloc[-1] > close.tail(50).mean())
    if len(close) >= 200:
        snap.above_200dma = bool(close.iloc[-1] > close.tail(200).mean())


def _debt_to_equity(raw) -> float | None:
    # Yahoo reports D/E as a percentage (45.2 == 0.452x)
    return None if raw is None else float(raw) / 100


class YFinanceSource:
    """Default market-data source. Tests swap in a fake with the same methods."""

    def company_snapshot(self, symbol: str) -> CompanySnapshot:
        import yfinance as yf

        ticker = yf.Ticker(to_yahoo(symbol))
        try:
            info = ticker.info or {}
        except Exception as e:  # noqa: BLE001
            print(f"[market_data] info failed for {symbol}: {e}")
            info = {}
        mcap = info.get("marketCap")
        snap = CompanySnapshot(
            symbol=symbol.upper(),
            name=info.get("longName") or info.get("shortName") or symbol.upper(),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            price=info.get("currentPrice") or info.get("regularMarketPrice"),
            market_cap_cr=mcap / 1e7 if mcap else None,
            pe=info.get("trailingPE"),
            pb=info.get("priceToBook"),
            roe=info.get("returnOnEquity"),
            debt_to_equity=_debt_to_equity(info.get("debtToEquity")),
            operating_margin=info.get("operatingMargins"),
            revenue_growth=info.get("revenueGrowth"),
            earnings_growth=info.get("earningsGrowth"),
            dividend_yield=info.get("dividendYield"),
        )
        try:
            _price_trend(snap, ticker.history(period="1y", auto_adjust=True)["Close"])
        except Exception as e:  # noqa: BLE001
            print(f"[market_data] history failed for {symbol}: {e}")
        return snap

    def index_levels(self) -> dict[str, dict]:
        import yfinance as yf

        levels = {}
        for name, code in INDICES.items():
            try:
                close = yf.Ticker(code).history(period="1mo")["Close"]
                levels[name] = {
                    "level": round(float(close.iloc[-1]), 2),
                    "change_1d": round(float(close.iloc[-1] / close.iloc[-2] - 1), 4),
                    "change_1m": round(float(close.iloc[-1] / close.iloc[0] - 1), 4),
                }
            except Exception as e:  # noqa: BLE001
                print(f"[market_data] index {name} failed: {e}")
        return levels
