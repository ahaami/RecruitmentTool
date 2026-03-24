"""Lusha contact enrichment client.

Finds decision-makers at target companies and retrieves their
phone numbers and email addresses using the Person API v2.

API docs: https://docs.lusha.com/
Free tier: 50 credits, 10 calls/hour.

Strategy: Use the Person API to look up known contacts by name+company
or LinkedIn URL. For discovering who to look up, we pair this with
Apollo org data and LinkedIn search URLs.

Usage:
    from services.lusha_client import enrich_person
    contact = enrich_person(first_name="Jane", last_name="Smith", company_name="Canva")
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


def enrich_person(
    first_name: str | None = None,
    last_name: str | None = None,
    company_name: str | None = None,
    company_domain: str | None = None,
    linkedin_url: str | None = None,
) -> LushaContact | None:
    """Enrich a person with phone + email via Lusha Person API v2.

    Can look up by:
    - LinkedIn URL (most accurate)
    - Name + company domain
    - Name + company name

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

        if resp.status_code == 401:
            print("    Lusha: invalid API key")
            return None

        if resp.status_code == 403:
            print("    Lusha: access denied")
            return None

        if resp.status_code == 429:
            print("    Lusha: rate limit hit (10 calls/hour on free tier)")
            return None

        if resp.status_code == 404:
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()

        # Lusha v2 wraps the result in a 'contact' key
        contact_data = data.get("contact", data.get("data", data))
        if not contact_data:
            return None

        # Check for errors (e.g. compliance restrictions)
        if isinstance(contact_data, dict) and contact_data.get("error"):
            return None

        person = contact_data.get("data", contact_data)
        if not person:
            return None

        # Extract email
        email = None
        email_type = None
        emails = person.get("emailAddresses") or person.get("emails") or []
        if isinstance(emails, list) and emails:
            for e in emails:
                if isinstance(e, dict):
                    if e.get("type", "").lower() in ("work", "business"):
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

        if not email:
            email = person.get("email")

        # Extract phone
        phone = None
        phone_type = None
        phones = person.get("phoneNumbers") or person.get("phones") or []
        if isinstance(phones, list) and phones:
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

        # Confidence based on data found
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
            linkedin_url=person.get("linkedinUrl") or linkedin_url,
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


def enrich_from_apollo_contacts(
    apollo_contacts: list,
    company_name: str = "",
    company_domain: str = "",
) -> list[LushaContact]:
    """Take contacts found by Apollo and enrich them with Lusha for phone + email.

    This is the main integration point: Apollo finds WHO works at the company
    (free tier), then Lusha gets their phone + email (paid data).

    Args:
        apollo_contacts: List of ApolloContact objects from Apollo people search.
        company_name: Company name for Lusha lookup.
        company_domain: Company domain for Lusha lookup.

    Returns:
        List of LushaContact objects with phone + email.
    """
    results = []

    for ac in apollo_contacts:
        if not ac.first_name or not ac.last_name:
            continue

        enriched = enrich_person(
            first_name=ac.first_name,
            last_name=ac.last_name,
            company_name=company_name,
            company_domain=company_domain,
            linkedin_url=ac.linkedin_url,
        )

        if enriched:
            # Keep the title from Apollo if Lusha didn't return one
            if not enriched.title and ac.title:
                enriched.title = ac.title
            results.append(enriched)
        else:
            # Convert Apollo contact to LushaContact format (no phone/email)
            results.append(LushaContact(
                first_name=ac.first_name,
                last_name=ac.last_name,
                title=ac.title,
                email=ac.email,
                phone=ac.phone,
                linkedin_url=ac.linkedin_url,
                company_name=company_name,
                company_domain=company_domain,
                confidence=ac.confidence,
                source="apollo",
            ))

    return results
