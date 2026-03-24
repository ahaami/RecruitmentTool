"""Company growth-signal scoring (0-100).

Calculates a composite score based on the strength and recency
of growth signals. Higher score = more likely to be actively hiring.
"""

from datetime import datetime, timezone, timedelta

import config


# Points per signal type
SIGNAL_WEIGHTS = {
    "job_posting": 12,       # Each job posting is worth 12 points (3+ = 36+)
    "funding": 25,           # Funding round is a strong signal
    "news_mention": 10,      # Generic growth/hiring news
    "headcount_jump": 20,    # Reported headcount increase
    "new_office": 15,        # Opening a new office
    "leadership_hire": 12,   # Hired a new exec
}

# Bonus points for company characteristics
CITY_BONUS = {
    "Sydney": 5,
    "Melbourne": 5,
    "Brisbane": 3,
    "Perth": 3,
    "Canberra": 2,
}

# Sweet spot: companies 50-500 employees are ideal for external recruiters
HEADCOUNT_BONUS = {
    (50, 500): 15,   # Sweet spot
    (20, 49): 8,     # Growing but may not have budget
    (501, 2000): 10, # Larger, may have internal TA but still use agencies
}


def calculate_growth_score(
    signals: list[dict],
    city: str = "",
    headcount: int | None = None,
    has_linkedin: bool = False,
    source_count: int = 1,
) -> int:
    """Calculate a company's growth score (0-100).

    Args:
        signals: List of signal dicts with 'signal_type' and optional 'signal_date'.
        city: Company's primary city.
        headcount: Estimated employee count (optional).
        has_linkedin: Whether the company has a LinkedIn page.
        source_count: Number of distinct sources that found this company.

    Returns:
        Integer score clamped to 0-100.
    """
    score = 0

    # Score from signals
    now = datetime.now(timezone.utc)
    for signal in signals:
        signal_type = signal.get("signal_type", "news_mention")
        base_points = SIGNAL_WEIGHTS.get(signal_type, 5)

        # Recency multiplier: signals from last 7 days get full points,
        # older signals get reduced points
        signal_date = signal.get("signal_date")
        if signal_date:
            if isinstance(signal_date, str):
                try:
                    signal_date = datetime.fromisoformat(signal_date)
                except ValueError:
                    signal_date = None

            if signal_date:
                if not signal_date.tzinfo:
                    signal_date = signal_date.replace(tzinfo=timezone.utc)
                age = now - signal_date
                if age <= timedelta(days=7):
                    multiplier = 1.0
                elif age <= timedelta(days=14):
                    multiplier = 0.8
                elif age <= timedelta(days=30):
                    multiplier = 0.5
                else:
                    multiplier = 0.3
                base_points = int(base_points * multiplier)

        score += base_points

    # City bonus
    score += CITY_BONUS.get(city, 0)

    # Headcount bonus
    if headcount:
        for (low, high), bonus in HEADCOUNT_BONUS.items():
            if low <= headcount <= high:
                score += bonus
                break

    # LinkedIn presence bonus
    if has_linkedin:
        score += 5

    # Multi-source bonus (found on multiple job boards = stronger signal)
    if source_count >= 3:
        score += 10
    elif source_count >= 2:
        score += 5

    # Clamp to 0-100
    return max(0, min(100, score))
