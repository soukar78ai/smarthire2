"""
advisor.py
The orchestrator. Runs the Market News Agent once, then the Company News and
Fundamentals agents for every stock on the watchlist, blends their scores
into a daily action per stock, and writes the morning brief.

Action = weighted blend of three views (all in [-1, 1]):
    55% fundamentals  - is this a good business at a fair price?
    30% company news  - is the recent news flow helping or hurting?
    15% market/sector - is the tide with it or against it today?
The LLM (when configured) writes the narrative but never changes the actions,
so recommendations stay reproducible and traceable to the agents' numbers.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from equity_agents import llm
from equity_agents.agents.base import AgentReport
from equity_agents.agents.company_news import CompanyNewsAgent
from equity_agents.agents.fundamentals import FundamentalsAgent
from equity_agents.agents.market_news import MarketNewsAgent

WEIGHTS = {"fundamentals": 0.55, "news": 0.30, "market": 0.15}

# (minimum composite score, action), checked top-down
ACTIONS = [(0.40, "BUY"), (0.15, "ACCUMULATE"), (-0.15, "HOLD"), (-0.40, "REDUCE"), (-1.01, "AVOID")]

DISCLAIMER = (
    "Generated automatically by AI agents from public news and Yahoo Finance data. "
    "This is not investment advice and the author is not a SEBI-registered adviser. "
    "Data can be delayed or wrong - verify before acting, and size positions to your own risk."
)

SYSTEM_PROMPT = """You are the head of research at an Indian equity advisory desk writing \
the morning note for a retail investor. You receive the market strategist's view and, for \
each stock on the watchlist, the fundamentals and news analysts' findings plus the action \
already decided by the desk's scoring model. Explain the day's recommendations clearly. Do \
not change any action and do not recommend stocks outside the list provided."""

USER_PROMPT = """Market view ({mood}, score {mood_score:+.2f}):
{market_summary}

Stocks (sorted by composite score):
{stocks}

Return a JSON object with exactly these fields:
{{
  "headline": "<one-line takeaway for today>",
  "brief": "<4-6 sentence morning note: market context, best ideas and why, what to avoid>",
  "top_ideas": [{{"symbol": "...", "reason": "<one sentence>"}}],
  "watch_out": [{{"symbol": "...", "reason": "<one sentence>"}}]
}}
top_ideas: up to 3 stocks with BUY/ACCUMULATE. watch_out: up to 3 with REDUCE/AVOID or
material negative news."""


def action_for(score: float) -> str:
    return next(action for threshold, action in ACTIONS if score >= threshold)


@dataclass
class StockCall:
    symbol: str
    name: str
    sector: str
    composite: float
    action: str
    fundamentals: AgentReport
    news: AgentReport
    market_component: float


@dataclass
class DailyBrief:
    date: str
    market: AgentReport
    calls: list[StockCall]
    headline: str = ""
    brief: str = ""
    top_ideas: list[dict] = field(default_factory=list)
    watch_out: list[dict] = field(default_factory=list)
    method: str = "rules"
    disclaimer: str = DISCLAIMER


class DailyAdvisor:
    name = "Daily Advisor"

    def __init__(self, news_source=None, market_data=None, max_workers: int = 3):
        self.market_agent = MarketNewsAgent(news_source, market_data)
        self.news_agent = CompanyNewsAgent(news_source)
        self.fundamentals_agent = FundamentalsAgent(market_data)
        self.max_workers = max_workers

    def analyze_stock(self, symbol: str, market: AgentReport) -> StockCall:
        fundamentals = self.fundamentals_agent.run(symbol)
        name = fundamentals.details.get("name", symbol)
        sector = fundamentals.details.get("sector", "")
        news = self.news_agent.run(symbol, name)
        # Use the strategist's sector view when it has one, else the overall mood
        market_component = market.details.get("sector_views", {}).get(sector, market.score)
        composite = round(
            WEIGHTS["fundamentals"] * fundamentals.score
            + WEIGHTS["news"] * news.score
            + WEIGHTS["market"] * market_component,
            3,
        )
        return StockCall(symbol, name, sector, composite, action_for(composite), fundamentals, news, market_component)

    def run(self, symbols: list[str]) -> DailyBrief:
        market = self.market_agent.run()
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            calls = list(pool.map(lambda s: self.analyze_stock(s, market), symbols))
        calls.sort(key=lambda c: c.composite, reverse=True)

        brief = DailyBrief(datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"), market, calls)
        result = llm.chat_json(
            SYSTEM_PROMPT,
            USER_PROMPT.format(
                mood=market.details.get("mood", "Neutral"), mood_score=market.score,
                market_summary=market.summary, stocks="\n".join(self._stock_line(c) for c in calls),
            ),
        )
        if result:
            brief.headline = result.get("headline", "")
            brief.brief = result.get("brief", "")
            valid = {c.symbol for c in calls}
            brief.top_ideas = [i for i in result.get("top_ideas", []) if i.get("symbol") in valid]
            brief.watch_out = [i for i in result.get("watch_out", []) if i.get("symbol") in valid]
            brief.method = "llm"
        else:
            self._rule_brief(brief)
        return brief

    @staticmethod
    def _stock_line(c: StockCall) -> str:
        return (
            f"- {c.symbol} ({c.name}, {c.sector or 'n/a'}): action {c.action}, composite {c.composite:+.2f} | "
            f"fundamentals {c.fundamentals.score:+.2f}: {c.fundamentals.summary} | "
            f"news {c.news.score:+.2f}: {c.news.summary} | news risks: {'; '.join(c.news.risks) or 'none'}"
        )

    @staticmethod
    def _rule_brief(brief: DailyBrief) -> None:
        buys = [c for c in brief.calls if c.action in ("BUY", "ACCUMULATE")][:3]
        sells = [c for c in reversed(brief.calls) if c.action in ("REDUCE", "AVOID")][:3]
        mood = brief.market.details.get("mood", "Neutral")
        brief.headline = f"Market {mood.lower()}; {len(buys)} idea(s) to buy/accumulate, {len(sells)} to trim/avoid."
        brief.brief = brief.market.summary
        brief.top_ideas = [
            {"symbol": c.symbol, "reason": f"Composite {c.composite:+.2f} - {c.fundamentals.summary}"} for c in buys
        ]
        brief.watch_out = [
            {"symbol": c.symbol, "reason": f"Composite {c.composite:+.2f} - {c.fundamentals.summary}"} for c in sells
        ]
