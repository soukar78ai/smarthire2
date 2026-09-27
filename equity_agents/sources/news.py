"""
news.py
Free news sources for the Indian market - RSS only, no API keys.

- Company news: Google News RSS search, India edition (aggregates ET, Mint,
  Moneycontrol, Business Standard, etc.)
- Market news: Google News topic searches plus the main Indian business-paper
  market feeds.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import mktime
from urllib.parse import quote_plus

GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

MARKET_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.livemint.com/rss/markets",
    "https://www.moneycontrol.com/rss/marketreports.xml",
]
MARKET_QUERIES = [
    "Sensex Nifty today",
    "RBI monetary policy",
    "FII DII flows India",
    "Indian economy GDP inflation",
]


@dataclass
class Headline:
    title: str
    source: str
    link: str
    published: datetime | None

    def as_line(self) -> str:
        date = self.published.strftime("%d %b") if self.published else "n/a"
        return f"[{date}] {self.title} ({self.source})"


def _parse_feed(url: str) -> list[Headline]:
    import feedparser

    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        published = None
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if stamp:
            published = datetime.fromtimestamp(mktime(stamp), tz=timezone.utc)
        source = entry.get("source", {}).get("title") or feed.feed.get("title", "")
        items.append(Headline(entry.get("title", "").strip(), source, entry.get("link", ""), published))
    return items


def _recent_unique(items: list[Headline], lookback_days: int, limit: int) -> list[Headline]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    seen, out = set(), []
    for h in sorted(items, key=lambda h: h.published or cutoff, reverse=True):
        key = h.title.lower()[:80]
        if not h.title or key in seen or (h.published and h.published < cutoff):
            continue
        seen.add(key)
        out.append(h)
    return out[:limit]


class RSSNewsSource:
    """Default news source. Tests swap in a fake with the same two methods."""

    def company_news(self, company_name: str, symbol: str, lookback_days: int, limit: int) -> list[Headline]:
        query = quote_plus(f'"{company_name}" OR "{symbol}" share when:{lookback_days}d')
        try:
            items = _parse_feed(GOOGLE_NEWS_SEARCH.format(query=query))
        except Exception as e:  # noqa: BLE001 - network failures just mean no news
            print(f"[news] company feed failed for {symbol}: {e}")
            items = []
        return _recent_unique(items, lookback_days, limit)

    def market_news(self, lookback_days: int, limit: int) -> list[Headline]:
        urls = MARKET_FEEDS + [
            GOOGLE_NEWS_SEARCH.format(query=quote_plus(f"{q} when:{lookback_days}d")) for q in MARKET_QUERIES
        ]
        items: list[Headline] = []
        for url in urls:
            try:
                items.extend(_parse_feed(url))
            except Exception as e:  # noqa: BLE001
                print(f"[news] market feed failed ({url}): {e}")
        return _recent_unique(items, lookback_days, limit)
