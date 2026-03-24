"""Company discovery pipeline.

Orchestrates all data sources, deduplicates, scores, and inserts
net-new companies into Supabase.

Usage:
    python main.py discover
"""

from datetime import datetime, timezone

from db.client import supabase
from services.seek_scraper import scrape_seek_it_jobs
from services.indeed_scraper import scrape_indeed_it_jobs
from services.linkedin_jobs import scrape_linkedin_it_jobs
from services.google_news import fetch_news_signals
from utils.dedup import find_existing_match, normalise_name
from utils.scoring import calculate_growth_score
from utils.agency_filter import is_recruitment_agency
import config


def _get_owner_and_vertical():
    """Get the first user and IT vertical IDs.

    TODO: When multi-user auth is wired up, this should accept a user_id param.
    """
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError(
            "No users found in the database. Please create a user first.\n"
            "In Supabase: Authentication > Users > Add user (email + password).\n"
            "Then insert a row in the 'users' table with that auth user's UUID."
        )
    owner_id = users.data[0]["id"]

    verticals = supabase.table("verticals").select("id").eq("name", "IT").execute()
    if not verticals.data:
        raise RuntimeError("IT vertical not found. Did you run schema.sql?")
    vertical_id = verticals.data[0]["id"]

    return owner_id, vertical_id


def _get_existing_companies(owner_id: str) -> list[dict]:
    """Fetch all existing companies for dedup comparison."""
    result = supabase.table("companies").select(
        "id, name, domain, growth_score"
    ).eq("owner_id", owner_id).execute()
    return result.data or []


def _get_excluded(owner_id: str) -> list[dict]:
    """Fetch the exclusion list."""
    result = supabase.table("excluded_companies").select(
        "company_name, domain"
    ).eq("owner_id", owner_id).execute()
    return result.data or []


def _is_excluded(name: str, domain: str | None, exclusions: list[dict]) -> bool:
    """Check if a company is on the exclusion list."""
    norm = normalise_name(name)
    for ex in exclusions:
        if normalise_name(ex["company_name"]) == norm:
            return True
        if domain and ex.get("domain") and domain.lower() == ex["domain"].lower():
            return True
    return False


def run_discovery():
    """Run the full company discovery pipeline."""
    print("=" * 50)
    print("COMPANY DISCOVERY PIPELINE")
    print("=" * 50)

    owner_id, vertical_id = _get_owner_and_vertical()
    existing = _get_existing_companies(owner_id)
    exclusions = _get_excluded(owner_id)

    print(f"\nExisting companies: {len(existing)}")
    print(f"Excluded companies: {len(exclusions)}")

    # ── Collect from all sources ─────────────────────────
    # We'll merge all companies into a unified dict keyed by normalised name
    # Each entry tracks: name, city, state, domain, linkedin_url, sources, signals

    merged: dict[str, dict] = {}

    def _merge_company(name, city="", state="", domain="", linkedin_url="",
                       source="", job_titles=None, job_count=0):
        key = normalise_name(name)
        if not key:
            return
        if key not in merged:
            merged[key] = {
                "name": name,
                "city": city,
                "state": state,
                "domain": domain,
                "linkedin_url": linkedin_url,
                "sources": set(),
                "signals": [],
                "total_jobs": 0,
            }
        entry = merged[key]
        if source:
            entry["sources"].add(source)
        if city and not entry["city"]:
            entry["city"] = city
        if state and not entry["state"]:
            entry["state"] = state
        if domain and not entry["domain"]:
            entry["domain"] = domain
        if linkedin_url and not entry["linkedin_url"]:
            entry["linkedin_url"] = linkedin_url
        entry["total_jobs"] += job_count

        # Add job posting signals
        if job_titles:
            for title in job_titles[:5]:  # Cap at 5 per source
                entry["signals"].append({
                    "signal_type": "job_posting",
                    "headline": f"{title} at {name}",
                    "source": source,
                    "signal_date": datetime.now(timezone.utc).isoformat(),
                })

    # ── Source 1: Seek ──
    print("\n--- Seek.com.au ---")
    try:
        seek_companies = scrape_seek_it_jobs(pages_per_city=2, delay=3.0)
        print(f"  Total companies from Seek: {len(seek_companies)}")
        for sc in seek_companies:
            _merge_company(
                name=sc.name, city=sc.city, state=sc.state,
                source="seek", job_titles=sc.job_titles, job_count=sc.job_count,
            )
    except Exception as e:
        print(f"  Seek scraper error: {e}")

    # ── Source 2: Indeed ──
    print("\n--- Indeed AU ---")
    try:
        indeed_companies = scrape_indeed_it_jobs(searches_per_city=2, delay=3.0)
        print(f"  Total companies from Indeed: {len(indeed_companies)}")
        for ic in indeed_companies:
            _merge_company(
                name=ic.name, city=ic.city, state=ic.state,
                source="indeed", job_titles=ic.job_titles, job_count=ic.job_count,
            )
    except Exception as e:
        print(f"  Indeed scraper error: {e}")

    # ── Source 3: LinkedIn ──
    print("\n--- LinkedIn Jobs ---")
    try:
        linkedin_companies = scrape_linkedin_it_jobs(results_per_city=25, delay=5.0)
        print(f"  Total companies from LinkedIn: {len(linkedin_companies)}")
        for lc in linkedin_companies:
            _merge_company(
                name=lc.name, city=lc.city, state=lc.state,
                source="linkedin", linkedin_url=lc.linkedin_url,
                job_titles=lc.job_titles, job_count=lc.job_count,
            )
    except Exception as e:
        print(f"  LinkedIn scraper error: {e}")

    # ── Source 4: Google News ──
    print("\n--- Google News ---")
    try:
        news_signals = fetch_news_signals(max_results_per_query=5)
        print(f"  Total news signals: {len(news_signals)}")
        news_with_companies = [s for s in news_signals if s.companies_mentioned]
        print(f"  Signals with company names: {len(news_with_companies)}")

        for signal in news_with_companies:
            for company_name in signal.companies_mentioned:
                key = normalise_name(company_name)
                if key not in merged:
                    merged[key] = {
                        "name": company_name,
                        "city": "",
                        "state": "",
                        "domain": "",
                        "linkedin_url": "",
                        "sources": {"google_news"},
                        "signals": [],
                        "total_jobs": 0,
                    }
                merged[key]["sources"].add("google_news")
                merged[key]["signals"].append({
                    "signal_type": signal.signal_type,
                    "headline": signal.headline,
                    "source": "google_news",
                    "signal_date": signal.published.isoformat() if signal.published else None,
                    "detail": signal.url,
                })
    except Exception as e:
        print(f"  Google News error: {e}")

    # ── Deduplicate & score ──────────────────────────────
    print(f"\n--- Processing {len(merged)} unique companies ---")

    new_count = 0
    updated_count = 0
    skipped_count = 0
    agency_count = 0

    for key, data in merged.items():
        name = data["name"]
        domain = data.get("domain")

        # Filter out recruitment agencies (competitors, not clients)
        if is_recruitment_agency(name):
            agency_count += 1
            continue

        # Check exclusion list
        if _is_excluded(name, domain, exclusions):
            skipped_count += 1
            continue

        # Calculate growth score
        score = calculate_growth_score(
            signals=data["signals"],
            city=data.get("city", ""),
            has_linkedin=bool(data.get("linkedin_url")),
            source_count=len(data["sources"]),
        )

        # Check if company already exists
        match = find_existing_match(name, domain, existing)

        if match:
            # Update existing company's score if signals are stronger
            if score > match.get("growth_score", 0):
                supabase.table("companies").update({
                    "growth_score": score,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", match["id"]).execute()
                updated_count += 1

            # Still add new signals
            for signal in data["signals"]:
                supabase.table("growth_signals").insert({
                    "company_id": match["id"],
                    "signal_type": signal["signal_type"],
                    "headline": signal["headline"],
                    "source": signal.get("source", "unknown"),
                    "signal_date": signal.get("signal_date"),
                    "detail": signal.get("detail"),
                }).execute()

        else:
            # Insert new company
            sources_str = ",".join(sorted(data["sources"]))
            status = "researching" if score >= config.MIN_GROWTH_SCORE else "new"

            result = supabase.table("companies").insert({
                "owner_id": owner_id,
                "vertical_id": vertical_id,
                "name": name,
                "domain": domain or None,
                "city": data.get("city", ""),
                "state": data.get("state", ""),
                "linkedin_url": data.get("linkedin_url") or None,
                "website": f"https://{domain}" if domain else None,
                "source": sources_str,
                "growth_score": score,
                "status": status,
            }).execute()

            company_id = result.data[0]["id"]

            # Insert signals
            for signal in data["signals"]:
                supabase.table("growth_signals").insert({
                    "company_id": company_id,
                    "signal_type": signal["signal_type"],
                    "headline": signal["headline"],
                    "source": signal.get("source", "unknown"),
                    "signal_date": signal.get("signal_date"),
                    "detail": signal.get("detail"),
                }).execute()

            # Add to existing list for dedup within this run
            existing.append({
                "id": company_id,
                "name": name,
                "domain": domain,
                "growth_score": score,
            })

            new_count += 1

    # ── Summary ──────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"DISCOVERY COMPLETE")
    print(f"{'=' * 50}")
    print(f"  New companies added:    {new_count}")
    print(f"  Existing updated:       {updated_count}")
    print(f"  Agencies filtered:      {agency_count}")
    print(f"  Excluded/skipped:       {skipped_count}")
    print(f"  Total in database:      {len(existing)}")

    # Show top companies by score
    if new_count > 0:
        top = supabase.table("companies").select(
            "name, growth_score, city, status, source"
        ).eq("owner_id", owner_id).order(
            "growth_score", desc=True
        ).limit(10).execute()

        print(f"\n  Top companies by growth score:")
        for c in top.data:
            print(f"    {c['growth_score']:>3}  {c['name']:<30} {c['city']:<12} [{c['source']}]")
