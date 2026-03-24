"""Contact enrichment pipeline.

Two-step enrichment:
1. Apollo.io org enrich (free) — gets headcount, industry, LinkedIn URL
2. LinkedIn search URLs — generates ready-to-click links for Alex to find DMs

When Apollo paid plan is available, also searches for people directly.

Usage:
    python main.py enrich
"""

import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from db.client import supabase
from services.apollo_client import search_people_at_company, enrich_company
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
    """Generate a LinkedIn people search URL for decision-makers at a company."""
    # Search for IT leadership at the company
    query = f'"{company_name}" (CTO OR "Head of Engineering" OR "VP Engineering" OR "IT Director" OR "Engineering Manager")'
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def _enrich_single_company(company: dict, owner_id: str) -> int:
    """Enrich a single company with org data and contact search links.

    Returns the number of contacts found (from Apollo paid) or 0 if manual needed.
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

    # Step 2: Try Apollo people search (paid plans only)
    contacts_found = 0
    try:
        contacts = search_people_at_company(
            company_domain=domain,
            company_name=name,
            limit=5,
        )
        if contacts:
            for contact in contacts:
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
                print(f"    [{tag}] {contact.first_name} {contact.last_name} — {contact.title} ({email_str})")
                contacts_found += 1
    except Exception:
        # People search not available on free plan — that's fine
        pass

    # Step 3: Generate LinkedIn search URL for manual contact finding
    linkedin_search = _generate_linkedin_search_url(name)
    notes_parts = []
    if contacts_found == 0:
        notes_parts.append(f"Find DMs here: {linkedin_search}")
    notes_parts.append(f"Enriched: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    updates["notes"] = " | ".join(notes_parts)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Step 4: Advance company status
    if contacts_found > 0:
        # Found contacts via Apollo — advance to qualified
        has_dm = any(
            _is_decision_maker_title(c.title)
            for c in (contacts if 'contacts' in dir() else [])
        )
        if has_dm:
            updates["status"] = "qualified"
            print(f"    -> Company advanced to 'qualified'")
    else:
        # No Apollo contacts but we enriched org data — still advance to qualified
        # Alex will find contacts manually via the LinkedIn search URL
        updates["status"] = "qualified"
        print(f"    -> Qualified (find contacts via LinkedIn link in notes)")

    supabase.table("companies").update(updates).eq("id", company_id).execute()

    return contacts_found


def _is_decision_maker_title(title: str) -> bool:
    """Check if a job title indicates a decision-maker for IT hiring."""
    if not title:
        return False

    title_lower = title.lower()

    dm_keywords = [
        "cto", "chief technology", "chief information", "cio", "ciso",
        "vp engineering", "vp of engineering", "vice president of engineering",
        "vp technology", "vp of technology",
        "head of engineering", "head of technology", "head of it",
        "head of infrastructure", "head of platform", "head of data",
        "head of security", "head of devops", "head of cloud",
        "director of engineering", "director of technology", "it director",
        "engineering director", "technology director",
        "engineering manager", "senior engineering manager",
        "head of talent", "head of people", "talent acquisition",
        "hr director", "head of hr",
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

    if not config.APOLLO_API_KEY:
        print("\nNote: APOLLO_API_KEY not set — skipping org enrichment.")
        print("Companies will still be qualified with LinkedIn search links.\n")

    total_contacts = 0
    qualified_count = 0

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}]", end="")
        contacts_found = _enrich_single_company(company, owner_id)
        total_contacts += contacts_found
        qualified_count += 1  # All processed companies get qualified now

        if i < len(companies):
            time.sleep(1)

    print(f"\n{'=' * 50}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Companies processed:    {len(companies)}")
    print(f"  Companies qualified:    {qualified_count}")
    print(f"  Contacts found (Apollo):{total_contacts}")
    if total_contacts == 0:
        print(f"\n  Tip: Check each company's 'notes' field in Supabase for")
        print(f"  LinkedIn search links to find decision-makers manually.")

    # Show qualified companies
    qualified = supabase.table("companies").select(
        "name, growth_score, city, notes"
    ).eq("owner_id", owner_id).eq(
        "status", "qualified"
    ).order("growth_score", desc=True).limit(10).execute()

    if qualified.data:
        print(f"\n  Qualified companies:")
        for c in qualified.data:
            print(f"    {c['growth_score']:>3}  {c['name']:<35} {c['city']}")
