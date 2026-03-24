"""Lusha contact enrichment client.

Finds decision-makers at target companies and retrieves their
phone numbers and email addresses.

API docs: https://docs.lusha.com/
Free tier: 70 credits/month (1 credit per email, 10 per phone).

Two-step flow:
1. Prospecting API — search for people by company + title + location
2. Person API — enrich a specific person with phone + email
"""

import httpx
from dataclasses import dataclass

import config


LUSHA_BASE_URL = "https://api.lusha.com"

# All hiring stakeholders — cast a wide net
TARGET_TITLES = [
    # Technical leadership (feel the pain of unfilled roles)
    "CTO",
    "Chief Technology Officer",
    "VP Engineering",
    "VP of Engineering",
    "Head of Engineering",
    "Director of Engineering",
    "Engineering Director",
    "Engineering Manager",
    "Senior Engineering Manager",
    "Team Lead",
    "Tech Lead",
    "Development Manager",
    "Software Development Manager",
    "IT Director",
    "Head of IT",
    "IT Manager",
    "Head of Infrastructure",
    "Head of Platform",
    "Head of Data",
    "Head of Security",
    "CISO",
    "CIO",
    # HR and internal recruitment (control hiring budgets)
    "Head of People",
    "Head of HR",
    "HR Director",
    "HR Manager",
    "People & Culture Manager",
    "Head of Talent",
    "Head of Talent Acquisition",
    "Talent Acquisition Manager",
    "Talent Acquisition Lead",
    "Internal Recruiter",
    "Senior Recruiter",
    "Recruitment Manager",
    "Recruitment Lead",
    "People Operations Manager",
]


@dataclass
class LushaContact:
    """A contact found via Lusha."""
    first_name: str
    last_name: str
    title: str
    email: str | None = None
    email_type: str | None = None
    phone: str | None = None
    phone_type: str | None = None
    linkedin_url: str | None = None
    company_name: str = ""
    company_domain: str = ""
    confidence: int = 50
    source: str = "lusha"


def _get_headers() -> dict:
    """Return headers with Lusha API key."""
    if not config.LUSHA_API_KEY:
        raise RuntimeError(
            "LUSHA_API_KEY not set in .env. "
            "Get your API key from your Lusha dashboard."
        )
    return {
        "api_key": config.LUSHA_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_usage() -> dict | None:
    """Check remaining Lusha credits."""
    try:
        resp = httpx.get(
            f"{LUSHA_BASE_URL}/account/usage",
            headers=_get_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"    Lusha usage check error: {e}")
    return None


def prospect_contacts(
    company_name: str | None = None,
    company_domain: str | None = None,
    titles: list[str] | None = None,
    location: str = "Australia",
    limit: int = 5,
) -> list[dict]:
    """Search for people at a company using Lusha Prospecting API.

    Args:
        company_name: Company name to search.
        company_domain: Company domain (preferred, more accurate).
        titles: Job titles to filter by. Defaults to TARGET_TITLES.
        location: Geographic filter.
        limit: Max results to return.

    Returns:
        List of prospect dicts with name, title, company info.
    """
    if not company_name and not company_domain:
        return []

    headers = _get_headers()

    # Build prospecting search payload
    filters = {
        "limit": limit,
    }

    if company_domain:
        filters["companyDomain"] = [company_domain]
    elif company_name:
        filters["companyName"] = [company_name]

    if titles:
        filters["jobTitle"] = titles
    else:
        filters["jobTitle"] = TARGET_TITLES

    if location:
        filters["location"] = [location]

    try:
        resp = httpx.post(
            f"{LUSHA_BASE_URL}/prospecting/contact/search",
            json=filters,
            headers=headers,
            timeout=30,
        )

        if resp.status_code == 401:
            print("    Lusha: invalid API key")
            return []

        if resp.status_code == 403:
            print("    Lusha: prospecting not available on your plan")
            return []

        if resp.status_code == 429:
            print("    Lusha: rate limit hit, try again later")
            return []

        if resp.status_code != 200:
            print(f"    Lusha prospecting error: {resp.status_code}")
            return []

        data = resp.json()
        return data.get("contacts", data.get("data", []))

    except httpx.HTTPError as e:
        print(f"    Lusha HTTP error: {e}")
        return []


def enrich_person(
    first_name: str | None = None,
    last_name: str | None = None,
    company_name: str | None = None,
    company_domain: str | None = None,
    linkedin_url: str | None = None,
) -> LushaContact | None:
    """Enrich a specific person with phone + email via Lusha Person API.

    Can look up by:
    - LinkedIn URL (most accurate)
    - Name + company domain
    - Name + company name

    Args:
        first_name: Person's first name.
        last_name: Person's last name.
        company_name: Company name.
        company_domain: Company domain (preferred).
        linkedin_url: LinkedIn profile URL (most accurate).

    Returns:
        LushaContact with email + phone, or None if not found.
    """
    headers = _get_headers()
    params = {}

    if linkedin_url:
        params["linkedinUrl"] = linkedin_url
    elif first_name and last_name:
        params["firstName"] = first_name
        params["lastName"] = last_name
        if company_domain:
            params["companyDomain"] = company_domain
        elif company_name:
            params["companyName"] = company_name
        else:
            return None
    else:
        return None

    try:
        resp = httpx.get(
            f"{LUSHA_BASE_URL}/v2/person",
            params=params,
            headers=headers,
            timeout=30,
        )

        if resp.status_code in (401, 403):
            return None

        if resp.status_code == 429:
            print("    Lusha: rate limit / credits exhausted")
            return None

        if resp.status_code == 404:
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()
        person = data.get("data", data)

        if not person:
            return None

        # Extract email
        email = None
        email_type = None
        emails = person.get("emails") or person.get("emailAddresses") or []
        if isinstance(emails, list) and emails:
            # Prefer business email
            for e in emails:
                if isinstance(e, dict):
                    if e.get("type", "").lower() == "business":
                        email = e.get("email") or e.get("value")
                        email_type = "business"
                        break
            if not email and emails:
                first_email = emails[0]
                if isinstance(first_email, dict):
                    email = first_email.get("email") or first_email.get("value")
                    email_type = first_email.get("type", "unknown")
                elif isinstance(first_email, str):
                    email = first_email
        elif isinstance(emails, str):
            email = emails

        # Also check top-level email field
        if not email:
            email = person.get("email")

        # Extract phone
        phone = None
        phone_type = None
        phones = person.get("phones") or person.get("phoneNumbers") or []
        if isinstance(phones, list) and phones:
            # Prefer mobile, then direct
            for p in phones:
                if isinstance(p, dict):
                    ptype = (p.get("type") or "").lower()
                    if ptype in ("mobile", "direct"):
                        phone = p.get("number") or p.get("value") or p.get("phone")
                        phone_type = ptype
                        break
            if not phone and phones:
                first_phone = phones[0]
                if isinstance(first_phone, dict):
                    phone = first_phone.get("number") or first_phone.get("value") or first_phone.get("phone")
                    phone_type = first_phone.get("type", "unknown")
                elif isinstance(first_phone, str):
                    phone = first_phone
        elif isinstance(phones, str):
            phone = phones

        # Confidence based on what we got
        confidence = 30
        if email and phone:
            confidence = 90
        elif email:
            confidence = 70
        elif phone:
            confidence = 60

        return LushaContact(
            first_name=person.get("firstName", first_name or ""),
            last_name=person.get("lastName", last_name or ""),
            title=person.get("jobTitle") or person.get("title", ""),
            email=email,
            email_type=email_type,
            phone=phone,
            phone_type=phone_type,
            linkedin_url=person.get("linkedinUrl") or person.get("linkedin_url") or linkedin_url,
            company_name=person.get("company", {}).get("name", company_name or "")
                if isinstance(person.get("company"), dict)
                else person.get("companyName", company_name or ""),
            company_domain=person.get("company", {}).get("domain", company_domain or "")
                if isinstance(person.get("company"), dict)
                else company_domain or "",
            confidence=confidence,
            source="lusha",
        )

    except httpx.HTTPError as e:
        print(f"    Lusha HTTP error: {e}")
        return None


def search_and_enrich(
    company_name: str | None = None,
    company_domain: str | None = None,
    titles: list[str] | None = None,
    limit: int = 5,
) -> list[LushaContact]:
    """Combined flow: prospect for people, then enrich each with contact info.

    This is the main function to call from the enrichment pipeline.
    Uses 2 API calls per contact (1 prospect + 1 enrich).

    Args:
        company_name: Target company name.
        company_domain: Target company domain (preferred).
        titles: Job titles to search for.
        limit: Max contacts to return.

    Returns:
        List of LushaContact objects with phone + email.
    """
    # Step 1: Find people at the company
    prospects = prospect_contacts(
        company_name=company_name,
        company_domain=company_domain,
        titles=titles,
        limit=limit,
    )

    if not prospects:
        # Fall back to direct enrichment if we have enough info
        return []

    contacts = []
    for prospect in prospects[:limit]:
        fname = prospect.get("firstName", "")
        lname = prospect.get("lastName", "")
        title = prospect.get("jobTitle") or prospect.get("title", "")
        li_url = prospect.get("linkedinUrl") or prospect.get("linkedin_url")

        if not fname or not lname:
            continue

        # Step 2: Enrich each prospect with phone + email
        enriched = enrich_person(
            first_name=fname,
            last_name=lname,
            company_name=company_name,
            company_domain=company_domain,
            linkedin_url=li_url,
        )

        if enriched:
            # Use the title from prospecting if enrichment didn't return one
            if not enriched.title and title:
                enriched.title = title
            contacts.append(enriched)
        else:
            # Still save the prospect even without enrichment
            contacts.append(LushaContact(
                first_name=fname,
                last_name=lname,
                title=title,
                linkedin_url=li_url,
                company_name=company_name or "",
                company_domain=company_domain or "",
                confidence=20,
                source="lusha_prospect",
            ))

    return contacts
