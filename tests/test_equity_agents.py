"""Offline tests for the equity agents - fake data sources, no network, no LLM key."""
from datetime import datetime, timezone

import pytest

from equity_agents import llm
from equity_agents.agents import CompanyNewsAgent, DailyAdvisor, FundamentalsAgent, MarketNewsAgent
from equity_agents.agents.advisor import action_for
from equity_agents.agents.base import keyword_sentiment
from equity_agents.agents.fundamentals import composite, scorecard
from equity_agents.report import to_markdown
from equity_agents.sources.market_data import CompanySnapshot, to_yahoo
from equity_agents.sources.news import Headline

NOW = datetime.now(timezone.utc)

STRONG = CompanySnapshot(
    symbol="GOOD", name="Good Industries Ltd", sector="Technology", price=1500, pe=20, pb=3, roe=0.28,
    debt_to_equity=0.05, operating_margin=0.25, revenue_growth=0.18, earnings_growth=0.20,
    return_1y=0.30, above_50dma=True, above_200dma=True,
)
WEAK = CompanySnapshot(
    symbol="BAD", name="Bad Holdings Ltd", sector="Industrials", price=40, pe=90, pb=12, roe=0.03,
    debt_to_equity=2.5, operating_margin=0.02, revenue_growth=-0.10, earnings_growth=-0.40,
    return_1y=-0.35, above_50dma=False, above_200dma=False,
)


class FakeNews:
    def company_news(self, company_name, symbol, lookback_days, limit):
        titles = {
            "GOOD": ["Good Industries wins record order, shares surge", "Good Industries profit beats estimates"],
            "BAD": ["Bad Holdings shares plunge after SEBI probe", "Bad Holdings reports loss, lenders flag default"],
        }[symbol]
        return [Headline(t, "Test Wire", "https://example.com", NOW) for t in titles]

    def market_news(self, lookback_days, limit):
        return [Headline("Sensex, Nifty rally to record high on strong FII inflows", "Test Wire", "", NOW)]


class FakeMarketData:
    def company_snapshot(self, symbol):
        return {"GOOD": STRONG, "BAD": WEAK}[symbol]

    def index_levels(self):
        return {"NIFTY 50": {"level": 25000.0, "change_1d": 0.005, "change_1m": 0.03},
                "INDIA VIX": {"level": 12.0, "change_1d": -0.02, "change_1m": -0.1}}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(llm.config, "GROQ_API_KEY", None)


def test_to_yahoo():
    assert to_yahoo("reliance") == "RELIANCE.NS"
    assert to_yahoo("INFY.BO") == "INFY.BO"
    assert to_yahoo("^NSEI") == "^NSEI"


def test_keyword_sentiment_direction():
    assert keyword_sentiment(["Shares surge on record profit"]) > 0
    assert keyword_sentiment(["Shares plunge after fraud probe"]) < 0
    assert keyword_sentiment([]) == 0.0


def test_scorecard_separates_strong_and_weak():
    assert composite(scorecard(STRONG)) > 0.5
    assert composite(scorecard(WEAK)) < -0.5


def test_financials_skip_debt_to_equity():
    bank = CompanySnapshot(symbol="BANK", name="Bank", sector="Financial Services", roe=0.16, debt_to_equity=8.0)
    card = scorecard(bank)
    assert card["balance_sheet"] is None
    assert card["quality"] is not None


def test_missing_data_is_neutral():
    empty = CompanySnapshot(symbol="X", name="X")
    assert composite(scorecard(empty)) == 0.0
    assert FundamentalsAgent(FakeMarketDataEmpty()).run("X").score == 0.0


class FakeMarketDataEmpty:
    def company_snapshot(self, symbol):
        return CompanySnapshot(symbol=symbol, name=symbol)


def test_action_thresholds():
    assert action_for(0.6) == "BUY"
    assert action_for(0.2) == "ACCUMULATE"
    assert action_for(0.0) == "HOLD"
    assert action_for(-0.3) == "REDUCE"
    assert action_for(-1.0) == "AVOID"


def test_agents_rule_mode():
    assert CompanyNewsAgent(FakeNews()).run("GOOD").score > 0
    assert CompanyNewsAgent(FakeNews()).run("BAD").score < 0
    market = MarketNewsAgent(FakeNews(), FakeMarketData()).run()
    assert market.score > 0 and market.method == "rules"


def test_daily_advisor_end_to_end():
    brief = DailyAdvisor(FakeNews(), FakeMarketData()).run(["BAD", "GOOD"])
    assert [c.symbol for c in brief.calls] == ["GOOD", "BAD"]
    assert brief.calls[0].action in ("BUY", "ACCUMULATE")
    assert brief.calls[1].action in ("REDUCE", "AVOID")
    assert brief.top_ideas[0]["symbol"] == "GOOD"
    assert brief.watch_out[0]["symbol"] == "BAD"
    md = to_markdown(brief)
    assert "GOOD" in md and "not investment advice" in md


def test_llm_output_is_sanitised(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "sentiment_score": 7, "summary": "s", "catalysts": ["c"], "risks": [], "materiality": "High",
    })
    report = CompanyNewsAgent(FakeNews()).run("GOOD")
    assert report.score == 1.0 and report.method == "llm"


def test_advisor_drops_llm_symbols_outside_watchlist(monkeypatch):
    brief_json = {"headline": "h", "brief": "b",
                  "top_ideas": [{"symbol": "GOOD", "reason": "r"}, {"symbol": "ZOMATO", "reason": "hallucinated"}],
                  "watch_out": []}
    advisor = DailyAdvisor(FakeNews(), FakeMarketData())
    monkeypatch.setattr("equity_agents.agents.advisor.llm.chat_json", lambda *a, **k: brief_json)
    brief = advisor.run(["GOOD"])
    assert [i["symbol"] for i in brief.top_ideas] == ["GOOD"]
