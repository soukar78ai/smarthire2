"""
base.py
Shared report type and a tiny rule-based sentiment scorer used as the
fallback when no LLM is configured.
"""
import re
from dataclasses import asdict, dataclass, field

POSITIVE_WORDS = {
    "surge", "surges", "jump", "jumps", "rally", "rallies", "gain", "gains", "rise", "rises", "soar",
    "soars", "record", "beat", "beats", "upgrade", "upgrades", "outperform", "buy", "order", "orders",
    "wins", "win", "profit", "growth", "expansion", "acquire", "acquisition", "dividend", "bonus",
    "buyback", "approval", "approves", "strong", "robust", "bullish", "high", "highs", "inflows",
}
NEGATIVE_WORDS = {
    "fall", "falls", "drop", "drops", "slump", "slumps", "plunge", "plunges", "crash", "decline",
    "declines", "loss", "losses", "miss", "misses", "downgrade", "downgrades", "underperform", "sell",
    "probe", "penalty", "fine", "raid", "fraud", "default", "weak", "bearish", "low", "lows",
    "outflows", "resigns", "resignation", "pledge", "lawsuit", "ban", "tariff", "tariffs", "hike",
    "slowdown", "concern", "concerns", "warning",
}
# Ambiguous words ("cut": rate cut vs guidance cut) are left out on purpose -
# the LLM path handles that nuance; this is only the no-key fallback.


def keyword_sentiment(titles: list[str]) -> float:
    """Average per-headline sentiment in [-1, 1] from a word lexicon."""
    if not titles:
        return 0.0
    scores = []
    for title in titles:
        words = re.findall(r"[a-z]+", title.lower())
        pos = sum(w in POSITIVE_WORDS for w in words)
        neg = sum(w in NEGATIVE_WORDS for w in words)
        scores.append(0.0 if pos == neg else (pos - neg) / (pos + neg))
    return round(sum(scores) / len(scores), 3)


@dataclass
class AgentReport:
    agent: str
    subject: str                     # company symbol, or "MARKET"
    score: float                     # normalised to [-1, 1]; + is bullish
    summary: str
    highlights: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    method: str = "rules"            # "llm" or "rules"

    def to_dict(self) -> dict:
        return asdict(self)
