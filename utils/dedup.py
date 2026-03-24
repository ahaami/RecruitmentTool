"""Company deduplication logic.

Matches incoming companies against existing ones in the database using:
1. Exact domain match (strongest signal)
2. Fuzzy company name match (catches "Canva" vs "Canva Pty Ltd")
"""

import re


def normalise_name(name: str) -> str:
    """Normalise a company name for fuzzy comparison.

    Strips common suffixes (Pty Ltd, Inc, etc.), lowercases,
    and removes punctuation.
    """
    text = name.lower().strip()

    # Remove common corporate suffixes
    suffixes = [
        r"\bpty\.?\s*ltd\.?",
        r"\blimited\b",
        r"\bltd\.?\b",
        r"\binc\.?\b",
        r"\bcorp\.?\b",
        r"\bcorporation\b",
        r"\bgroup\b",
        r"\bholdings?\b",
        r"\baustralia\b",
        r"\bau\b",
    ]
    for suffix in suffixes:
        text = re.sub(suffix, "", text)

    # Remove punctuation and extra whitespace
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalise_domain(domain: str) -> str:
    """Normalise a domain for matching.

    Strips www., protocol, trailing slashes, etc.
    """
    text = domain.lower().strip()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    text = text.rstrip("/")
    return text


def names_match(name_a: str, name_b: str) -> bool:
    """Check if two company names likely refer to the same company.

    Uses normalised comparison — not a fuzzy distance metric,
    but handles the most common variations (Pty Ltd, etc.).
    """
    norm_a = normalise_name(name_a)
    norm_b = normalise_name(name_b)

    if not norm_a or not norm_b:
        return False

    # Exact match after normalisation
    if norm_a == norm_b:
        return True

    # One contains the other (handles "Atlassian" vs "Atlassian Software")
    if norm_a in norm_b or norm_b in norm_a:
        # Only if the shorter name is at least 4 chars (avoid false positives)
        shorter = min(len(norm_a), len(norm_b))
        if shorter >= 4:
            return True

    return False


def domains_match(domain_a: str | None, domain_b: str | None) -> bool:
    """Check if two domains match after normalisation."""
    if not domain_a or not domain_b:
        return False
    return normalise_domain(domain_a) == normalise_domain(domain_b)


def find_existing_match(
    company_name: str,
    company_domain: str | None,
    existing_companies: list[dict],
) -> dict | None:
    """Find a matching company in the existing list.

    Args:
        company_name: Name of the incoming company.
        company_domain: Domain of the incoming company (optional).
        existing_companies: List of dicts with 'name' and 'domain' keys.

    Returns:
        The matching existing company dict, or None.
    """
    # First pass: domain match (strongest)
    if company_domain:
        for existing in existing_companies:
            if domains_match(company_domain, existing.get("domain")):
                return existing

    # Second pass: name match
    for existing in existing_companies:
        if names_match(company_name, existing.get("name", "")):
            return existing

    return None
