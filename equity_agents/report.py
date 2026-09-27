"""
report.py
Renders a DailyBrief as Markdown (for the CLI, saved reports, and email/chat).
"""
from equity_agents.agents.advisor import DailyBrief

ACTION_ICONS = {"BUY": "🟢", "ACCUMULATE": "🟩", "HOLD": "⚪", "REDUCE": "🟧", "AVOID": "🔴"}


def to_markdown(brief: DailyBrief) -> str:
    m = brief.market
    lines = [
        f"# Indian Equity Daily Brief — {brief.date}",
        "",
        f"**{brief.headline}**" if brief.headline else "",
        "",
        brief.brief,
        "",
        f"## Market pulse — {m.details.get('mood', 'Neutral')} ({m.score:+.2f})",
        "",
    ]
    for name, v in m.details.get("indices", {}).items():
        lines.append(f"- **{name}**: {v['level']:,} ({v['change_1d'] * 100:+.2f}% 1D, {v['change_1m'] * 100:+.2f}% 1M)")
    if m.highlights:
        lines += ["", "**Key themes:**"] + [f"- {t}" for t in m.highlights]
    if m.risks:
        lines += ["", "**Risks:**"] + [f"- {r}" for r in m.risks]
    if m.details.get("sector_views"):
        views = ", ".join(f"{k} {v:+.1f}" for k, v in sorted(m.details["sector_views"].items(), key=lambda kv: -kv[1]))
        lines += ["", f"**Sector tilt:** {views}"]

    if brief.top_ideas:
        lines += ["", "## Top ideas today", ""] + [f"- **{i['symbol']}** — {i.get('reason', '')}" for i in brief.top_ideas]
    if brief.watch_out:
        lines += ["", "## Watch out", ""] + [f"- **{i['symbol']}** — {i.get('reason', '')}" for i in brief.watch_out]

    lines += [
        "",
        "## Watchlist scorecard",
        "",
        "| Stock | Sector | Action | Composite | Fundamentals | News | Market/Sector |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for c in brief.calls:
        lines.append(
            f"| {c.symbol} | {c.sector or 'n/a'} | {ACTION_ICONS.get(c.action, '')} {c.action} | {c.composite:+.2f} "
            f"| {c.fundamentals.score:+.2f} | {c.news.score:+.2f} | {c.market_component:+.2f} |"
        )

    lines += ["", "## Stock notes", ""]
    for c in brief.calls:
        lines += [f"### {c.symbol} — {c.name} · {c.action}", "", f"*Fundamentals:* {c.fundamentals.summary}"]
        if c.fundamentals.highlights:
            lines.append(f"  - Strengths: {'; '.join(c.fundamentals.highlights)}")
        if c.fundamentals.risks:
            lines.append(f"  - Concerns: {'; '.join(c.fundamentals.risks)}")
        lines.append(f"*News:* {c.news.summary}")
        if c.news.highlights:
            lines.append(f"  - Catalysts: {'; '.join(c.news.highlights)}")
        if c.news.risks:
            lines.append(f"  - Risks: {'; '.join(c.news.risks)}")
        lines.append("")

    lines += ["---", f"_Narrative: {brief.method}. {brief.disclaimer}_", ""]
    return "\n".join(lines)
