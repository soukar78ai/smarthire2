"""
equity_agents
A small multi-agent system for the Indian equity market (NSE/BSE).

Agents:
- CompanyNewsAgent   - reads recent news for one company, scores sentiment,
                       extracts catalysts and risks
- FundamentalsAgent  - scores a company's financial health, growth,
                       valuation and price trend
- MarketNewsAgent    - reads broad Indian market/macro news and index levels,
                       judges the overall market mood and sector tilts
- DailyAdvisor       - orchestrates the three agents across a watchlist and
                       produces a daily recommendation brief

Every agent works without an LLM key (rule-based fallback), and uses Groq
when GROQ_API_KEY is configured - same pattern as the SmartHire2 app.

NOT investment advice. See the disclaimer in the generated report.
"""
