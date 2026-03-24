"""Google News RSS scraper for Australian tech company signals.

Searches Google News RSS for AU tech hiring, funding, and growth stories.
No API key required — uses public RSS feeds.
"""

import feedparser
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsSignal:
    """A growth signal found in a news article."""
    headline: str
    url: str
    source: str
    published: datetime | None
    signal_type: str  # 'funding', 'news_mention', 'leadership_hire'
    companies_mentioned: list[str]


# Search queries targeting AU tech growth signals
SEARCH_QUERIES = [
    "Australian tech company hiring",
    "Australia startup funding round",
    "Australian technology company expansion",
    "Australia SaaS company growing",
    "Australian IT company new office",
    "Australia tech Series A OR Series B OR Series C",
    "Australian cybersecurity company",
    "Australia fintech hiring",
    "Australian cloud company",
    "Australia AI company funding",
]

# Patterns that suggest funding
FUNDING_PATTERNS = [
    r"(?:raises?|raised|secures?|secured|closes?|closed)\s+\$[\d.]+\s*[mb]",
    r"series\s+[a-d]",
    r"seed\s+(?:round|funding)",
    r"funding\s+round",
    r"venture\s+capital",
]

# Patterns that suggest hiring/growth
GROWTH_PATTERNS = [
    r"hir(?:ing|es?|ed)\s+\d+",
    r"new\s+(?:office|headquarters|hq)",
    r"expand(?:s|ing|ed)",
    r"headcount",
    r"growing\s+team",
    r"recruit(?:ing|ment)",
]

# Patterns that suggest leadership changes
LEADERSHIP_PATTERNS = [
    r"(?:appoints?|appointed|hires?|hired|names?|named)\s+(?:new\s+)?(?:cto|ceo|cfo|vp|head\s+of)",
    r"new\s+(?:cto|ceo|chief)",
]


def _classify_signal(headline: str) -> str:
    """Classify a headline into a signal type."""
    text = headline.lower()
    for pattern in FUNDING_PATTERNS:
        if re.search(pattern, text):
            return "funding"
    for pattern in LEADERSHIP_PATTERNS:
        if re.search(pattern, text):
            return "leadership_hire"
    for pattern in GROWTH_PATTERNS:
        if re.search(pattern, text):
            return "news_mention"
    return "news_mention"


def _extract_company_names(headline: str) -> list[str]:
    """Try to extract company names from a headline.

    Heuristic: capitalised multi-word sequences at the start of the headline,
    or after common prepositions. Not perfect, but useful as a starting point.
    """
    # Remove common prefixes
    cleaned = re.sub(
        r"^(?:Australian|Australia[n']?s?|AU)\s+", "", headline, flags=re.IGNORECASE
    )

    # Look for patterns like "CompanyName raises..." or "CompanyName, the..."
    match = re.match(r"^([A-Z][\w.]+(?:\s+[A-Z][\w.]*)*)", cleaned)
    if match:
        name = match.group(1).strip()
        # Filter out generic words that start sentences
        generic = {
            "The", "This", "New", "How", "Why", "What", "When", "Top",
            "Best", "More", "Local", "Tech", "Big",
        }
        if name.split()[0] not in generic and len(name) > 2:
            return [name]

    return []


def _parse_date(entry) -> datetime | None:
    """Parse the published date from a feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            return None
    return None


def fetch_news_signals(max_results_per_query: int = 10) -> list[NewsSignal]:
    """Fetch growth signals from Google News RSS.

    Returns a list of NewsSignal objects with classified signal types.
    """
    all_signals: list[NewsSignal] = []
    seen_urls: set[str] = set()

    for query in SEARCH_QUERIES:
        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={query.replace(' ', '+')}&hl=en-AU&gl=AU&ceid=AU:en"
        )

        try:
            feed = feedparser.parse(rss_url)
        except Exception:
            continue

        for entry in feed.entries[:max_results_per_query]:
            url = entry.get("link", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            headline = entry.get("title", "").strip()
            if not headline:
                continue

            signal = NewsSignal(
                headline=headline,
                url=url,
                source="google_news",
                published=_parse_date(entry),
                signal_type=_classify_signal(headline),
                companies_mentioned=_extract_company_names(headline),
            )
            all_signals.append(signal)

    return all_signals
