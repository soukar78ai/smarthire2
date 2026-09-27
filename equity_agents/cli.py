"""
cli.py
Command-line entry point.

    python -m equity_agents.cli daily                 # full brief for the watchlist
    python -m equity_agents.cli daily -s INFY TCS     # brief for specific stocks
    python -m equity_agents.cli news RELIANCE         # company news agent only
    python -m equity_agents.cli fundamentals HDFCBANK # fundamentals agent only
    python -m equity_agents.cli market                # market news agent only

`daily` also saves the brief to reports/<date>.md.
"""
import argparse
import json

from equity_agents import config


def load_watchlist(path=None) -> list[str]:
    path = path or config.WATCHLIST_PATH
    lines = (line.split("#")[0].strip().upper() for line in open(path, encoding="utf-8"))
    return [s for s in lines if s]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Indian equity multi-agent advisor")
    sub = parser.add_subparsers(dest="command", required=True)
    daily = sub.add_parser("daily", help="run all agents and produce the daily brief")
    daily.add_argument("-s", "--symbols", nargs="+", help="NSE symbols (default: watchlist.txt)")
    daily.add_argument("-w", "--watchlist", help="path to a watchlist file")
    daily.add_argument("--no-save", action="store_true", help="print only, don't write reports/<date>.md")
    sub.add_parser("news", help="company news agent").add_argument("symbol")
    sub.add_parser("fundamentals", help="fundamentals agent").add_argument("symbol")
    sub.add_parser("market", help="market news agent")
    args = parser.parse_args(argv)

    if not config.groq_is_configured():
        print("[info] GROQ_API_KEY not set - running rule-based agents only.\n")

    from equity_agents.agents import CompanyNewsAgent, DailyAdvisor, FundamentalsAgent, MarketNewsAgent

    if args.command == "daily":
        from equity_agents.report import to_markdown

        symbols = [s.upper() for s in args.symbols] if args.symbols else load_watchlist(args.watchlist)
        markdown = to_markdown(DailyAdvisor().run(symbols))
        print(markdown)
        if not args.no_save:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            out = config.REPORTS_DIR / f"{datetime.now(ZoneInfo('Asia/Kolkata')):%Y-%m-%d}.md"
            out.write_text(markdown, encoding="utf-8")
            print(f"\n[saved] {out}")
        return

    if args.command == "news":
        report = CompanyNewsAgent().run(args.symbol.upper())
    elif args.command == "fundamentals":
        report = FundamentalsAgent().run(args.symbol.upper())
    else:
        report = MarketNewsAgent().run()
    print(json.dumps(report.to_dict(), indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
