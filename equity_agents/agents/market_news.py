"""
market_news.py
Agent 3 - reads broad Indian market and macro news plus index levels, and
judges the overall market mood and which sectors are in or out of favour.
"""
from equity_agents import config, llm
from equity_agents.agents.base import AgentReport, keyword_sentiment
from equity_agents.sources.market_data import YFinanceSource
from equity_agents.sources.news import RSSNewsSource

# Yahoo Finance sector names - the advisor matches company sectors against these
SECTORS = [
    "Technology", "Financial Services", "Energy", "Consumer Defensive", "Consumer Cyclical",
    "Healthcare", "Industrials", "Basic Materials", "Communication Services", "Utilities", "Real Estate",
]

SYSTEM_PROMPT = """You are the chief market strategist for an Indian equity desk. Each \
morning you read market and macro headlines (Sensex/Nifty moves, RBI policy, inflation, \
FII/DII flows, crude oil, rupee, global cues, budget/policy news) and index levels, and \
brief the team on the market mood and sector positioning. Use only the information \
provided. Be balanced - call out risks even on bullish days."""

USER_PROMPT = """Index snapshot:
{indices}

Market headlines (newest first):
{headlines}

Return a JSON object with exactly these fields:
{{
  "mood_score": <float -1.0 (very bearish) to 1.0 (very bullish)>,
  "mood": "<Bearish | Cautious | Neutral | Positive | Bullish>",
  "summary": "<3-4 sentence morning brief on the Indian market>",
  "key_themes": ["<main drivers today>"],
  "risks": ["<what could go wrong>"],
  "sector_views": {{"<sector>": <float -1.0 to 1.0>}}
}}
Only use these sector names in sector_views, and only for sectors the news actually
speaks to: {sectors}"""


def _mood_label(score: float) -> str:
    if score >= 0.5:
        return "Bullish"
    if score >= 0.15:
        return "Positive"
    if score > -0.15:
        return "Neutral"
    if score > -0.5:
        return "Cautious"
    return "Bearish"


def _index_signal(indices: dict) -> float | None:
    """Rule-based read of index trend and volatility, in [-1, 1]."""
    parts = []
    nifty = indices.get("NIFTY 50")
    if nifty:
        parts.append(max(-1.0, min(1.0, nifty["change_1m"] / 0.05)))  # +/-5% in a month = full signal
    vix = indices.get("INDIA VIX")
    if vix:
        parts.append(0.3 if vix["level"] < 13 else -0.5 if vix["level"] > 20 else 0.0)
    return sum(parts) / len(parts) if parts else None


class MarketNewsAgent:
    name = "Market News Agent"

    def __init__(self, news_source=None, market_data=None):
        self.news = news_source or RSSNewsSource()
        self.data = market_data or YFinanceSource()

    def run(self) -> AgentReport:
        headlines = self.news.market_news(lookback_days=2, limit=config.MAX_HEADLINES * 2)
        indices = self.data.index_levels()
        details = {
            "indices": indices,
            "headlines": [{"title": h.title, "source": h.source, "link": h.link} for h in headlines],
            "sector_views": {},
        }
        index_text = "\n".join(
            f"- {k}: {v['level']:,} ({v['change_1d'] * 100:+.2f}% 1D, {v['change_1m'] * 100:+.2f}% 1M)"
            for k, v in indices.items()
        ) or "- unavailable"

        result = None
        if headlines or indices:
            result = llm.chat_json(
                SYSTEM_PROMPT,
                USER_PROMPT.format(
                    indices=index_text,
                    headlines="\n".join(h.as_line() for h in headlines) or "- none available",
                    sectors=", ".join(SECTORS),
                ),
            )
        if result:
            score = llm.clamp(result.get("mood_score"), -1, 1)
            details["mood"] = result.get("mood") or _mood_label(score)
            details["sector_views"] = {
                k: llm.clamp(v, -1, 1) for k, v in (result.get("sector_views") or {}).items() if k in SECTORS
            }
            return AgentReport(self.name, "MARKET", score, result.get("summary", ""),
                               list(result.get("key_themes", [])), list(result.get("risks", [])),
                               details, method="llm")

        news_score = keyword_sentiment([h.title for h in headlines]) if headlines else None
        idx_score = _index_signal(indices)
        parts = [p for p in (news_score, idx_score) if p is not None]
        score = round(sum(parts) / len(parts), 3) if parts else 0.0
        details["mood"] = _mood_label(score)
        if not headlines and not indices:
            return AgentReport(self.name, "MARKET", 0.0,
                               "No market news or index data could be fetched - check your internet connection.",
                               details=details)
        nifty = indices.get("NIFTY 50")
        summary = f"Market mood reads {details['mood'].lower()} from {len(headlines)} headlines"
        if nifty:
            summary += f"; Nifty 50 at {nifty['level']:,} ({nifty['change_1m'] * 100:+.1f}% over 1M)"
        return AgentReport(self.name, "MARKET", score, summary + ".",
                           [h.title for h in headlines[:5]], details=details)
