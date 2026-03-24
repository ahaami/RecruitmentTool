"""Company monitoring + ongoing intelligence.

Re-checks known companies for new growth signals, recalculates scores,
and flags companies that have gone stale or reactivated.

Usage:
    python main.py monitor
"""

import time
from datetime import datetime, timedelta, timezone

from db.client import supabase
from services.seek_scraper import scrape_seek_it_jobs
from services.google_news import fetch_news_signals
from utils.scoring import calculate_growth_score
import config


def _get_owner_id() -> str:
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError("No users found.")
    return users.data[0]["id"]


def _get_monitored_companies(owner_id: str) -> list[dict]:
    """Get active/qualified companies to monitor for new signals."""
    companies = supabase.table("companies").select(
        "id, name, domain, city, state, growth_score, status, updated_at"
    ).eq("owner_id", owner_id).in_(
        "status", ["researching", "qualified", "active"]
    ).order("updated_at").limit(50).execute()

    return companies.data or []


def _check_new_signals(company: dict, owner_id: str) -> list[dict]:
    """Check for new growth signals for a company."""
    name = company["name"]
    new_signals = []

    # Check Seek for new job postings
    try:
        city = company.get("city", "Sydney")
        seek_results = scrape_seek_it_jobs(cities=[city], pages_per_city=1)
        for result in seek_results:
            if result.name.lower().strip() == name.lower().strip():
                for title in result.job_titles[:3]:
                    existing = supabase.table("growth_signals").select(
                        "id", count="exact"
                    ).eq("company_id", company["id"]).eq(
                        "headline", f"{title} at {name}"
                    ).execute()

                    if not existing.count:
                        new_signals.append({
                            "company_id": company["id"],
                            "signal_type": "job_posting",
                            "headline": f"{title} at {name}",
                            "detail": f"Found on Seek in {city}",
                            "source": "seek_monitor",
                        })
    except Exception:
        pass

    # Check Google News for mentions
    try:
        news_results = fetch_news_signals(max_results_per_query=5)
        for signal in news_results:
            if name.lower() in signal.headline.lower():
                existing = supabase.table("growth_signals").select(
                    "id", count="exact"
                ).eq("company_id", company["id"]).eq(
                    "headline", signal.headline[:200]
                ).execute()

                if not existing.count:
                    new_signals.append({
                        "company_id": company["id"],
                        "signal_type": signal.signal_type,
                        "headline": signal.headline[:200],
                        "detail": signal.url or "",
                        "source": "google_news_monitor",
                    })
    except Exception:
        pass

    return new_signals


def _recalculate_score(company_id: str) -> int:
    """Recalculate growth score based on all signals."""
    signals = supabase.table("growth_signals").select(
        "signal_type, created_at"
    ).eq("company_id", company_id).execute()

    if not signals.data:
        return 0

    company = supabase.table("companies").select(
        "headcount_est, linkedin_url, city"
    ).eq("id", company_id).single().execute()

    company_data = company.data or {}

    return calculate_growth_score(
        signals=signals.data,
        headcount=company_data.get("headcount_est"),
        has_linkedin=bool(company_data.get("linkedin_url")),
        city=company_data.get("city", ""),
    )


def _check_stale_companies(owner_id: str) -> list[dict]:
    """Find companies with no new signals in 30+ days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    stale = supabase.table("companies").select(
        "id, name, growth_score, status, updated_at"
    ).eq("owner_id", owner_id).in_(
        "status", ["qualified", "researching"]
    ).lte("updated_at", cutoff).execute()

    return stale.data or []


def run_monitor():
    """Run the monitoring pipeline."""
    print("=" * 50)
    print("COMPANY MONITORING")
    print("=" * 50)

    owner_id = _get_owner_id()
    companies = _get_monitored_companies(owner_id)

    print(f"\n  Companies to monitor: {len(companies)}")

    if not companies:
        print("  No active companies to monitor.")
        return

    total_new_signals = 0
    score_changes = 0
    reactivated = 0

    for i, company in enumerate(companies, 1):
        print(f"\n  [{i}/{len(companies)}] {company['name']}...", end=" ")

        # Check for new signals
        new_signals = _check_new_signals(company, owner_id)

        if new_signals:
            print(f"{len(new_signals)} new signal(s)")
            for signal in new_signals:
                supabase.table("growth_signals").insert(signal).execute()
                print(f"    + {signal['signal_type']}: {signal['headline'][:60]}")
            total_new_signals += len(new_signals)
        else:
            print("no new signals")

        # Recalculate score
        old_score = company["growth_score"]
        new_score = _recalculate_score(company["id"])

        if new_score != old_score:
            supabase.table("companies").update({
                "growth_score": new_score,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", company["id"]).execute()
            print(f"    Score: {old_score} -> {new_score}")
            score_changes += 1

            # Reactivated: was low score, now high again
            if old_score < config.MIN_GROWTH_SCORE and new_score >= config.MIN_GROWTH_SCORE:
                reactivated += 1
                print(f"    ** REACTIVATED ** (score crossed {config.MIN_GROWTH_SCORE})")

        # Rate limit
        if i < len(companies):
            time.sleep(2)

    # Check for stale companies
    stale = _check_stale_companies(owner_id)

    print(f"\n{'=' * 50}")
    print(f"MONITORING COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Companies checked:    {len(companies)}")
    print(f"  New signals found:    {total_new_signals}")
    print(f"  Score changes:        {score_changes}")
    print(f"  Reactivated:          {reactivated}")

    if stale:
        print(f"\n  STALE COMPANIES (no signals in 30+ days):")
        print(f"  Consider pausing these to focus on active leads.")
        for c in stale[:10]:
            days_stale = (datetime.now(timezone.utc) - datetime.fromisoformat(
                c["updated_at"].replace("Z", "+00:00")
            )).days
            print(f"    {c['name']:<35} score: {c['growth_score']}  ({days_stale}d stale)")

        print(f"\n  To pause: python main.py pause-stale")
