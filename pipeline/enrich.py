"""Contact enrichment pipeline.

Three-step enrichment:
1. Apollo.io org enrich (free) — gets headcount, industry, LinkedIn URL
2. Lusha contact search — finds decision-makers with phone + email
3. LinkedIn search URLs — fallback for manual contact finding

Usage:
    python main.py enrich
"""

import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from db.client import supabase
from services.apollo_client import enrich_company
import config


def _get_owner_id() -> str:
    """Get the first user's ID."""
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError("No users found. Create a user first.")
    return users.data[0]["id"]


def _get_companies_to_enrich(owner_id: str, limit: int = 20) -> list[dict]:
    """Fetch companies that need enrichment.

    Targets companies in 'researching' status with no contacts yet,
    ordered by growth_score descending (best leads first).
    """
    companies = supabase.table("companies").select(
        "id, name, domain, city, state, growth_score, linkedin_url, headcount_est"
    ).eq("owner_id", owner_id).eq(
        "status", "researching"
    ).order(
        "growth_score", desc=True
    ).limit(limit).execute()

    if not companies.data:
        return []

    # Filter out companies that already have contacts
    result = []
    for company in companies.data:
        existing = supabase.table("contacts").select(
            "id", count="exact"
        ).eq("company_id", company["id"]).execute()

        if existing.count == 0:
            result.append(company)

    return result


def _generate_linkedin_search_url(company_name: str) -> str:
    """Generate a LinkedIn people search URL for hiring stakeholders at a company."""
    query = (
        f'"{company_name}" (CTO OR "Head of Engineering" OR "VP Engineering" '
        f'OR "Engineering Manager" OR "Team Lead" OR "HR Manager" '
        f'OR "Talent Acquisition" OR "Internal Recruiter" OR "IT Director")'
    )
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def _enrich_single_company(company: dict, owner_id: str) -> int:
    """Enrich a single company with org data and contacts.

    Returns the number of contacts found.
    """
    company_id = company["id"]
    name = company["name"]
    domain = company.get("domain")

    print(f"\n  Enriching: {name} (score: {company['growth_score']})")

    updates = {}

    # Step 1: Apollo org enrich (free) — headcount, industry, LinkedIn URL
    if config.APOLLO_API_KEY:
        org_info = enrich_company(
            company_domain=domain,
            company_name=name if not domain else None,
        )
        if org_info:
            if org_info.get("headcount") and not company.get("headcount_est"):
                updates["headcount_est"] = org_info["headcount"]
                print(f"    Headcount: ~{org_info['headcount']} employees")
            if org_info.get("industry"):
                updates["industry"] = org_info["industry"]
                print(f"    Industry: {org_info['industry']}")
            if org_info.get("linkedin_url") and not company.get("linkedin_url"):
                updates["linkedin_url"] = org_info["linkedin_url"]
                print(f"    LinkedIn: {org_info['linkedin_url']}")
            if org_info.get("domain") and not domain:
                updates["domain"] = org_info["domain"]
                updates["website"] = f"https://{org_info['domain']}"
                domain = org_info["domain"]
                print(f"    Domain: {org_info['domain']}")
        else:
            print(f"    Apollo: no org data found")

    # Step 2: Lusha contact search — find people with phone + email
    contacts_found = 0

    if config.LUSHA_API_KEY:
        try:
            from services.lusha_client import search_and_enrich

            print(f"    Searching Lusha for contacts...")
            lusha_contacts = search_and_enrich(
                company_name=name,
                company_domain=domain,
                limit=5,
            )

            for contact in lusha_contacts:
                if not contact.first_name or not contact.last_name:
                    continue

                is_dm = _is_decision_maker_title(contact.title)

                supabase.table("contacts").insert({
                    "company_id": company_id,
                    "owner_id": owner_id,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "title": contact.title,
                    "email": contact.email,
                    "phone": contact.phone,
                    "linkedin_url": contact.linkedin_url,
                    "source": contact.source,
                    "confidence": contact.confidence,
                    "is_decision_maker": is_dm,
                }).execute()

                tag = "DM" if is_dm else "  "
                email_str = contact.email or "no email"
                phone_str = contact.phone or "no phone"
                print(f"    [{tag}] {contact.first_name} {contact.last_name} -- {contact.title}")
                print(f"         {email_str} | {phone_str}")
                contacts_found += 1

        except Exception as e:
            print(f"    Lusha error: {e}")

    # Step 3: Fallback — try Apollo people search if Lusha found nothing
    if contacts_found == 0 and config.APOLLO_API_KEY:
        try:
            from services.apollo_client import search_people_at_company

            apollo_contacts = search_people_at_company(
                company_domain=domain,
                company_name=name,
                limit=5,
            )
            for contact in apollo_contacts:
                if not contact.first_name or not contact.last_name:
                    continue

                is_dm = _is_decision_maker_title(contact.title)

                supabase.table("contacts").insert({
                    "company_id": company_id,
                    "owner_id": owner_id,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "title": contact.title,
                    "email": contact.email,
                    "phone": contact.phone,
                    "linkedin_url": contact.linkedin_url,
                    "source": "apollo",
                    "confidence": contact.confidence,
                    "is_decision_maker": is_dm,
                }).execute()

                tag = "DM" if is_dm else "  "
                email_str = contact.email or "no email"
                print(f"    [{tag}] {contact.first_name} {contact.last_name} -- {contact.title} ({email_str})")
                contacts_found += 1
        except Exception:
            pass

    # Step 4: Generate LinkedIn search URL for manual contact finding
    linkedin_search = _generate_linkedin_search_url(name)
    notes_parts = []
    if contacts_found == 0:
        notes_parts.append(f"Find contacts here: {linkedin_search}")
    notes_parts.append(f"Enriched: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    updates["notes"] = " | ".join(notes_parts)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Step 5: Advance company status
    if contacts_found > 0:
        updates["status"] = "qualified"
        print(f"    -> Qualified with {contacts_found} contact(s)")
    else:
        updates["status"] = "qualified"
        print(f"    -> Qualified (find contacts via LinkedIn link in notes)")

    supabase.table("companies").update(updates).eq("id", company_id).execute()

    return contacts_found


def _is_decision_maker_title(title: str) -> bool:
    """Check if a job title indicates a hiring stakeholder."""
    if not title:
        return False

    title_lower = title.lower()

    dm_keywords = [
        # C-suite / VP
        "cto", "chief technology", "chief information", "cio", "ciso",
        "vp engineering", "vp of engineering", "vice president of engineering",
        "vp technology", "vp of technology",
        # Engineering leadership
        "head of engineering", "head of technology", "head of it",
        "head of infrastructure", "head of platform", "head of data",
        "head of security", "head of devops", "head of cloud",
        "director of engineering", "director of technology", "it director",
        "engineering director", "technology director",
        "engineering manager", "senior engineering manager",
        # Team leads
        "team lead", "tech lead", "development manager",
        "software development manager",
        # HR / Talent / Internal recruitment
        "head of talent", "head of people", "head of hr",
        "talent acquisition", "talent manager",
        "hr director", "hr manager",
        "people & culture", "people and culture",
        "people operations",
        "internal recruiter", "recruitment manager", "recruitment lead",
        "senior recruiter",
        # IT management
        "it manager", "infrastructure manager",
    ]

    for keyword in dm_keywords:
        if keyword in title_lower:
            return True

    return False


def run_enrichment(limit: int = 20):
    """Run the contact enrichment pipeline.

    Args:
        limit: Max companies to enrich per run.
    """
    print("=" * 50)
    print("CONTACT ENRICHMENT PIPELINE")
    print("=" * 50)

    owner_id = _get_owner_id()

    companies = _get_companies_to_enrich(owner_id, limit=limit)
    print(f"\nCompanies to enrich: {len(companies)}")

    if not companies:
        print("No companies need enrichment.")
        print("(Companies must be in 'researching' status with no existing contacts)")
        return

    # Show which data sources are active
    sources = []
    if config.APOLLO_API_KEY:
        sources.append("Apollo (org data)")
    if config.LUSHA_API_KEY:
        sources.append("Lusha (contacts + phone + email)")
    sources.append("LinkedIn search URLs (manual fallback)")
    print(f"Data sources: {', '.join(sources)}")

    if config.LUSHA_API_KEY:
        # Show Lusha credit usage
        try:
            from services.lusha_client import get_usage
            usage = get_usage()
            if usage:
                print(f"Lusha credits: {usage}")
        except Exception:
            pass

    total_contacts = 0
    qualified_count = 0

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}]", end="")
        contacts_found = _enrich_single_company(company, owner_id)
        total_contacts += contacts_found
        qualified_count += 1

        if i < len(companies):
            time.sleep(1)

    print(f"\n{'=' * 50}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Companies processed:    {len(companies)}")
    print(f"  Companies qualified:    {qualified_count}")
    print(f"  Contacts found:         {total_contacts}")
    if total_contacts == 0:
        print(f"\n  Tip: Check each company's 'notes' field in Supabase for")
        print(f"  LinkedIn search links to find contacts manually.")
    elif total_contacts > 0:
        print(f"\n  Contacts saved with phone + email where available.")
        print(f"  Run 'python main.py callsheet --with-openers' to generate your call sheet.")

    # Show qualified companies with contact counts
    qualified = supabase.table("companies").select(
        "id, name, growth_score, city"
    ).eq("owner_id", owner_id).eq(
        "status", "qualified"
    ).order("growth_score", desc=True).limit(10).execute()

    if qualified.data:
        print(f"\n  Top qualified companies:")
        for c in qualified.data:
            contact_count = supabase.table("contacts").select(
                "id", count="exact"
            ).eq("company_id", c["id"]).execute()
            count = contact_count.count or 0
            print(f"    {c['growth_score']:>3}  {c['name']:<35} {c.get('city', ''):<12} {count} contact(s)")
