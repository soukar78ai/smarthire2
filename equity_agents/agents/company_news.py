"""
company_news.py
Agent 1 - reads the last few days of news for one company and turns it into
a sentiment score plus concrete catalysts and risks.
"""
from equity_agents import config, llm
from equity_agents.agents.base import AgentReport, keyword_sentiment
from equity_agents.sources.news import RSSNewsSource

SYSTEM_PROMPT = """You are an equity research analyst covering Indian listed companies \
(NSE/BSE). You read recent news headlines about one company and judge what they mean for \
its share price over the next few weeks. Use only the headlines provided - do not invent \
events. Distinguish company-specific news from generic market noise, and weigh \
materiality: order wins, results, guidance, regulatory action (SEBI/RBI), management \
changes, promoter pledges, M&A and block deals matter more than routine price-move stories."""

USER_PROMPT = """Company: {name} (NSE: {symbol})

Recent headlines (newest first):
{headlines}

Return a JSON object with exactly these fields:
{{
  "sentiment_score": <float -1.0 (very negative) to 1.0 (very positive)>,
  "summary": "<2-3 sentences on what the news flow says about the company right now>",
  "catalysts": ["<positive, company-specific developments>"],
  "risks": ["<negative developments or red flags>"],
  "materiality": "<Low | Medium | High - how much this news should move the stock>"
}}"""


class CompanyNewsAgent:
    name = "Company News Agent"

    def __init__(self, news_source=None):
        self.news = news_source or RSSNewsSource()

    def run(self, symbol: str, company_name: str | None = None) -> AgentReport:
        company_name = company_name or symbol
        headlines = self.news.company_news(company_name, symbol, config.NEWS_LOOKBACK_DAYS, config.MAX_HEADLINES)
        lines = [h.as_line() for h in headlines]
        details = {"headlines": [{"title": h.title, "source": h.source, "link": h.link} for h in headlines]}

        if not headlines:
            return AgentReport(self.name, symbol, 0.0, "No recent news found.", details=details)

        result = llm.chat_json(
            SYSTEM_PROMPT, USER_PROMPT.format(name=company_name, symbol=symbol, headlines="\n".join(lines))
        )
        if result:
            details["materiality"] = result.get("materiality", "Medium")
            return AgentReport(
                agent=self.name,
                subject=symbol,
                score=llm.clamp(result.get("sentiment_score"), -1, 1),
                summary=result.get("summary", ""),
                highlights=list(result.get("catalysts", [])),
                risks=list(result.get("risks", [])),
                details=details,
                method="llm",
            )

        score = keyword_sentiment([h.title for h in headlines])
        tone = "positive" if score > 0.15 else "negative" if score < -0.15 else "mixed/neutral"
        return AgentReport(
            agent=self.name,
            subject=symbol,
            score=score,
            summary=f"{len(headlines)} headlines in the last {config.NEWS_LOOKBACK_DAYS} days; "
            f"keyword tone is {tone}. Latest: {headlines[0].title}",
            highlights=[h.title for h in headlines[:3]],
            details=details,
        )
