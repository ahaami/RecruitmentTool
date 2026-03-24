"""Apollo.io contact enrichment client.

Finds decision-maker contacts at target companies using Apollo's
people search API. Free tier: 50 credits/month.

API docs: https://apolloio.github.io/apollo-api-docs/
"""

import httpx
from dataclasses import dataclass, field

import config


APOLLO_BASE_URL = "https://api.apollo.io"

# Decision-maker titles to search for, ordered by priority.
# Technical leadership first (they feel the pain of unfilled roles),
# then HR/talent (gatekeepers but still useful).
DM_TITLES = [
    "CTO",
    "Chief Technology Officer",
    "VP Engineering",
    "VP of Engineering",
    "Head of Engineering",
    "Engineering Manager",
    "Director of Engineering",
    "IT Director",
    "Head of IT",
    "Chief Information Officer",
    "CIO",
    "CISO",
    "Head of Infrastructure",
    "Head of Data",
    "Head of Platform",
    "Head of Talent",
    "Talent Acquisition Manager",
    "Head of People",
]


@dataclass
class ApolloContact:
    """A contact found via Apollo.io."""
    first_name: str
    last_name: str
    title: str
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    company_name: str = ""
    company_domain: str = ""
    confidence: int = 50  # 0-100
    source: str = "apollo"


def _get_headers() -> dict:
    """Return headers with API key."""
    if not config.APOLLO_API_KEY:
        raise RuntimeError(
            "APOLLO_API_KEY not set in .env. "
            "Sign up free at https://app.apollo.io/ and add your key."
        )
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": config.APOLLO_API_KEY,
    }


def search_people_at_company(
    company_domain: str | None = None,
    company_name: str | None = None,
    titles: list[str] | None = None,
    limit: int = 5,
) -> list[ApolloContact]:
    """Search Apollo for decision-makers at a specific company.

    Args:
        company_domain: Company website domain (e.g. "canva.com"). Preferred.
        company_name: Company name (fallback if no domain).
        titles: Job titles to search for. Defaults to DM_TITLES.
        limit: Max contacts to return per company.

    Returns:
        List of ApolloContact objects.
    """
    if not company_domain and not company_name:
        return []

    if titles is None:
        titles = DM_TITLES

    headers = _get_headers()

    # Build the search payload
    payload: dict = {

        "page": 1,
        "per_page": limit,
        "person_titles": titles,
        "person_locations": ["Australia"],
    }

    if company_domain:
        payload["q_organization_domains"] = company_domain
    elif company_name:
        payload["q_organization_name"] = company_name

    try:
        resp = httpx.post(
            f"{APOLLO_BASE_URL}/v1/mixed_people/search",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code in (401, 403):
            # Free plan doesn't include people search — expected
            return []

        if resp.status_code == 429:
            print("    Apollo rate limit hit. Wait and retry later.")
            return []

        if resp.status_code != 200:
            return []

        data = resp.json()
        people = data.get("people", [])

        contacts = []
        for person in people:
            if not person:
                continue

            # Determine confidence based on email verification
            email = person.get("email")
            email_status = person.get("email_status", "")
            confidence = 30
            if email_status == "verified":
                confidence = 90
            elif email_status == "guessed":
                confidence = 60
            elif email:
                confidence = 50

            # Extract phone numbers
            phone = None
            phone_numbers = person.get("phone_numbers", [])
            if phone_numbers:
                # Prefer direct dial, then mobile
                for pn in phone_numbers:
                    if pn.get("type") in ("direct", "mobile"):
                        phone = pn.get("sanitized_number") or pn.get("number")
                        break
                if not phone and phone_numbers:
                    phone = phone_numbers[0].get("sanitized_number") or phone_numbers[0].get("number")

            org = person.get("organization", {}) or {}

            contacts.append(ApolloContact(
                first_name=person.get("first_name", ""),
                last_name=person.get("last_name", ""),
                title=person.get("title", ""),
                email=email,
                phone=phone,
                linkedin_url=person.get("linkedin_url"),
                company_name=org.get("name", company_name or ""),
                company_domain=org.get("primary_domain", company_domain or ""),
                confidence=confidence,
                source="apollo",
            ))

        return contacts

    except httpx.HTTPError as e:
        print(f"    Apollo HTTP error: {e}")
        return []


def enrich_company(
    company_domain: str | None = None,
    company_name: str | None = None,
) -> dict | None:
    """Look up company info from Apollo.

    Uses /organizations/enrich (by domain) or /organizations/search (by name).
    Returns dict with headcount, industry, description, etc.
    """
    if not company_domain and not company_name:
        return None

    headers = _get_headers()
    org = None

    # Strategy 1: Enrich by domain (most accurate)
    if company_domain:
        try:
            resp = httpx.post(
                f"{APOLLO_BASE_URL}/v1/organizations/enrich",
                json={"domain": company_domain},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                org = resp.json().get("organization")
        except httpx.HTTPError:
            pass

    # Strategy 2: Search by name (when no domain or enrich returned nothing)
    if not org and company_name:
        try:
            resp = httpx.post(
                f"{APOLLO_BASE_URL}/v1/organizations/search",
                json={
                    "page": 1,
                    "per_page": 1,
                    "q_organization_name": company_name,
                },
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                orgs = resp.json().get("organizations", [])
                if orgs:
                    org = orgs[0]
        except httpx.HTTPError:
            pass

    if not org:
        return None

    return {
        "name": org.get("name", ""),
        "domain": org.get("primary_domain", ""),
        "industry": org.get("industry", ""),
        "headcount": org.get("estimated_num_employees"),
        "linkedin_url": org.get("linkedin_url", ""),
        "description": org.get("short_description", ""),
        "city": org.get("city", ""),
        "state": org.get("state", ""),
        "country": org.get("country", ""),
    }
