"""
equity_app.py
Streamlit dashboard for the Indian equity agents.

Run with:  streamlit run equity_app.py
(Run from the project root so the "equity_agents" package imports cleanly.)
"""
import pandas as pd
import streamlit as st

from equity_agents import config
from equity_agents.agents import CompanyNewsAgent, DailyAdvisor, FundamentalsAgent, MarketNewsAgent
from equity_agents.cli import load_watchlist
from equity_agents.report import ACTION_ICONS, to_markdown

st.set_page_config(page_title="Indian Equity Agents", page_icon="📈", layout="wide")
st.title("📈 Indian Equity Agents")
if not config.groq_is_configured():
    st.info("GROQ_API_KEY not set — agents run in rule-based mode (no LLM narrative).")


def show_report(report):
    st.markdown(f"**Score:** {report.score:+.2f} · _method: {report.method}_")
    st.write(report.summary)
    col1, col2 = st.columns(2)
    with col1:
        for h in report.highlights:
            st.markdown(f"✅ {h}")
    with col2:
        for r in report.risks:
            st.markdown(f"⚠️ {r}")


tab_daily, tab_company, tab_market = st.tabs(["🗞️ Daily Brief", "🏢 Company Deep-Dive", "🌐 Market Pulse"])

with tab_daily:
    default = ", ".join(load_watchlist())
    symbols_text = st.text_area("Watchlist (NSE symbols, comma-separated)", default, height=80)
    if st.button("Run all agents", type="primary"):
        symbols = [s.strip().upper() for s in symbols_text.replace("\n", ",").split(",") if s.strip()]
        with st.spinner(f"Running 3 agents across {len(symbols)} stocks..."):
            brief = DailyAdvisor().run(symbols)
        st.subheader(brief.headline)
        st.write(brief.brief)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Top ideas")
            for i in brief.top_ideas:
                st.markdown(f"- **{i['symbol']}** — {i.get('reason', '')}")
        with col2:
            st.markdown("#### Watch out")
            for i in brief.watch_out:
                st.markdown(f"- **{i['symbol']}** — {i.get('reason', '')}")
        st.dataframe(
            pd.DataFrame([
                {"Stock": c.symbol, "Name": c.name, "Sector": c.sector,
                 "Action": f"{ACTION_ICONS.get(c.action, '')} {c.action}", "Composite": c.composite,
                 "Fundamentals": c.fundamentals.score, "News": c.news.score, "Market/Sector": c.market_component}
                for c in brief.calls
            ]),
            use_container_width=True, hide_index=True,
        )
        st.download_button("Download brief (.md)", to_markdown(brief), f"equity_brief_{brief.date}.md")
        st.caption(brief.disclaimer)

with tab_company:
    symbol = st.text_input("NSE symbol", "RELIANCE").strip().upper()
    if st.button("Analyze company") and symbol:
        with st.spinner("Fundamentals Agent..."):
            fundamentals = FundamentalsAgent().run(symbol)
        st.subheader(f"{fundamentals.details.get('name', symbol)} — {fundamentals.details.get('sector', '')}")
        st.markdown("#### 📊 Fundamentals Agent")
        show_report(fundamentals)
        st.table(pd.Series(fundamentals.details.get("metrics", {}), name="Value"))
        with st.spinner("Company News Agent..."):
            news = CompanyNewsAgent().run(symbol, fundamentals.details.get("name"))
        st.markdown("#### 📰 Company News Agent")
        show_report(news)
        with st.expander("Headlines read"):
            for h in news.details.get("headlines", []):
                st.markdown(f"- [{h['title']}]({h['link']}) — {h['source']}")

with tab_market:
    if st.button("Read the market"):
        with st.spinner("Market News Agent..."):
            market = MarketNewsAgent().run()
        cols = st.columns(max(1, len(market.details.get("indices", {}))))
        for col, (name, v) in zip(cols, market.details.get("indices", {}).items()):
            col.metric(name, f"{v['level']:,}", f"{v['change_1d'] * 100:+.2f}%")
        st.markdown(f"#### Mood: {market.details.get('mood', 'Neutral')}")
        show_report(market)
        if market.details.get("sector_views"):
            st.bar_chart(pd.Series(market.details["sector_views"], name="Sector view"))
        with st.expander("Headlines read"):
            for h in market.details.get("headlines", []):
                st.markdown(f"- [{h['title']}]({h['link']}) — {h['source']}")
