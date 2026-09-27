"""
fundamentals.py
Agent 2 - scores a company's performance and financial health.

The score itself is a deterministic scorecard (so it's reproducible and
explainable); the LLM, when available, only writes the narrative on top of
the numbers. Thresholds are tuned for Indian large/mid caps.
"""
from equity_agents import llm
from equity_agents.agents.base import AgentReport
from equity_agents.sources.market_data import CompanySnapshot, YFinanceSource

# Banks/NBFCs carry debt as their raw material - D/E isn't meaningful for them
FINANCIAL_SECTORS = {"Financial Services"}

SYSTEM_PROMPT = """You are a fundamental equity analyst covering Indian companies. You are \
given a company's key metrics and a rule-based scorecard. Explain what the numbers say about \
business quality, growth, balance sheet, valuation and price trend. Use only the numbers \
provided; call out missing data rather than guessing. Compare against typical Indian \
benchmarks (e.g. ROE above 15% is healthy; Nifty 50 trades around 20-23x earnings)."""

USER_PROMPT = """Company: {name} (NSE: {symbol}) - {sector} / {industry}

Metrics:
{metrics}

Scorecard (each pillar -1 to +1):
{scorecard}

Return a JSON object with exactly these fields:
{{
  "summary": "<2-3 sentence verdict on the company's fundamentals and valuation>",
  "strengths": ["..."],
  "concerns": ["..."]
}}"""


def _band(value, good, bad, higher_is_better=True) -> float | None:
    """Linear score: +1 at/after `good`, -1 at/after `bad`, 0 halfway."""
    if value is None:
        return None
    if not higher_is_better:
        value, good, bad = -value, -good, -bad
    if value >= good:
        return 1.0
    if value <= bad:
        return -1.0
    return round(2 * (value - bad) / (good - bad) - 1, 3)


def _avg(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def scorecard(s: CompanySnapshot) -> dict[str, float | None]:
    is_financial = s.sector in FINANCIAL_SECTORS
    trend = [
        None if s.above_200dma is None else (0.5 if s.above_200dma else -0.5),
        None if s.above_50dma is None else (0.25 if s.above_50dma else -0.25),
        _band(s.return_1y, 0.20, -0.10),
    ]
    return {
        "quality": _avg([_band(s.roe, 0.18, 0.08), None if is_financial else _band(s.operating_margin, 0.20, 0.05)]),
        "balance_sheet": None if is_financial else _band(s.debt_to_equity, 0.3, 1.5, higher_is_better=False),
        "growth": _avg([_band(s.revenue_growth, 0.15, 0.0), _band(s.earnings_growth, 0.15, -0.05)]),
        "valuation": _avg([_band(s.pe, 18, 60, higher_is_better=False), _band(s.pb, 2, 10, higher_is_better=False)]),
        "trend": _avg([sum(trend[:2]) if None not in trend[:2] else None, trend[2]]),
    }


# Quality and growth matter most for a medium-term view; valuation and trend temper it
WEIGHTS = {"quality": 0.3, "growth": 0.25, "balance_sheet": 0.15, "valuation": 0.15, "trend": 0.15}


def composite(card: dict) -> float:
    total = sum(WEIGHTS[k] for k, v in card.items() if v is not None)
    if not total:
        return 0.0
    return round(sum(WEIGHTS[k] * v for k, v in card.items() if v is not None) / total, 3)


def _fmt_pct(v):
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _fmt_num(v, suffix=""):
    return "n/a" if v is None else f"{v:,.2f}{suffix}"


def metrics_table(s: CompanySnapshot) -> dict[str, str]:
    return {
        "Price (INR)": _fmt_num(s.price),
        "Market cap (INR cr)": _fmt_num(s.market_cap_cr),
        "P/E": _fmt_num(s.pe, "x"),
        "P/B": _fmt_num(s.pb, "x"),
        "ROE": _fmt_pct(s.roe),
        "Operating margin": _fmt_pct(s.operating_margin),
        "Debt/Equity": _fmt_num(s.debt_to_equity, "x"),
        "Revenue growth (YoY)": _fmt_pct(s.revenue_growth),
        "Earnings growth (YoY)": _fmt_pct(s.earnings_growth),
        "Return 1M / 3M / 1Y": f"{_fmt_pct(s.return_1m)} / {_fmt_pct(s.return_3m)} / {_fmt_pct(s.return_1y)}",
        "From 52-week high": _fmt_pct(s.pct_from_52w_high),
        "Above 50 / 200 DMA": f"{s.above_50dma} / {s.above_200dma}",
    }


def _rule_notes(s: CompanySnapshot, card: dict) -> tuple[list[str], list[str]]:
    labels = {
        "quality": f"profitability (ROE {_fmt_pct(s.roe)})",
        "balance_sheet": f"balance sheet (D/E {_fmt_num(s.debt_to_equity, 'x')})",
        "growth": f"growth (revenue {_fmt_pct(s.revenue_growth)}, earnings {_fmt_pct(s.earnings_growth)})",
        "valuation": f"valuation (P/E {_fmt_num(s.pe, 'x')})",
        "trend": f"price trend (1Y {_fmt_pct(s.return_1y)})",
    }
    strengths = [f"Strong {labels[k]}" for k, v in card.items() if v is not None and v >= 0.4]
    concerns = [f"Weak {labels[k]}" for k, v in card.items() if v is not None and v <= -0.4]
    return strengths, concerns


class FundamentalsAgent:
    name = "Fundamentals Agent"

    def __init__(self, market_data=None):
        self.data = market_data or YFinanceSource()

    def run(self, symbol: str) -> AgentReport:
        snap = self.data.company_snapshot(symbol)
        card = scorecard(snap)
        score = composite(card)
        metrics = metrics_table(snap)
        details = {"name": snap.name, "sector": snap.sector, "industry": snap.industry,
                   "metrics": metrics, "scorecard": card}

        if all(v is None for v in card.values()):
            return AgentReport(self.name, symbol, 0.0, "No fundamental data available.", details=details)

        result = llm.chat_json(
            SYSTEM_PROMPT,
            USER_PROMPT.format(
                name=snap.name, symbol=symbol, sector=snap.sector or "n/a", industry=snap.industry or "n/a",
                metrics="\n".join(f"- {k}: {v}" for k, v in metrics.items()),
                scorecard="\n".join(f"- {k}: {'n/a' if v is None else v}" for k, v in card.items()),
            ),
        )
        if result:
            return AgentReport(self.name, symbol, score, result.get("summary", ""),
                               list(result.get("strengths", [])), list(result.get("concerns", [])),
                               details, method="llm")

        strengths, concerns = _rule_notes(snap, card)
        verdict = "solid" if score > 0.25 else "weak" if score < -0.25 else "average"
        return AgentReport(self.name, symbol, score,
                           f"{snap.name}: fundamentals look {verdict} overall (composite {score:+.2f}).",
                           strengths, concerns, details)
