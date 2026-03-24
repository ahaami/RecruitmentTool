"""Daily call sheet generator.

Builds a prioritised list of leads, renders it as an HTML email,
and sends it via Resend. Also saves a snapshot to the database.

Usage:
    python main.py callsheet [--limit N] [--with-openers]
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from jinja2 import Template

from db.client import supabase
from services.resend_client import send_callsheet_email
import config


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "callsheet_email.html"


def _get_owner_id() -> str:
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError("No users found.")
    return users.data[0]["id"]


def _get_qualified_leads(owner_id: str, limit: int) -> list[dict]:
    """Get call-ready leads: qualified companies, preferring those with contacts."""
    # Get qualified companies ordered by score
    companies = supabase.table("companies").select(
        "id, name, domain, city, state, growth_score, industry, "
        "headcount_est, linkedin_url, website, notes"
    ).eq("owner_id", owner_id).eq(
        "status", "qualified"
    ).order(
        "growth_score", desc=True
    ).limit(limit).execute()

    if not companies.data:
        return []

    leads = []
    for company in companies.data:
        # Check cooldown — skip if contacted in last COOLDOWN_DAYS
        from datetime import timedelta
        cooldown_since = (datetime.now(timezone.utc) - timedelta(days=config.COOLDOWN_DAYS)).isoformat()
        cooldown = supabase.table("outreach_log").select(
            "id", count="exact"
        ).eq("company_id", company["id"]).gte(
            "contacted_at", cooldown_since
        ).execute()

        if cooldown.count and cooldown.count > 0:
            continue

        # Get best contact for this company (decision-maker preferred)
        contact = supabase.table("contacts").select(
            "id, first_name, last_name, title, email, phone, linkedin_url"
        ).eq("company_id", company["id"]).eq(
            "is_decision_maker", True
        ).limit(1).execute()

        if not contact.data:
            # Fall back to any contact
            contact = supabase.table("contacts").select(
                "id, first_name, last_name, title, email, phone, linkedin_url"
            ).eq("company_id", company["id"]).limit(1).execute()

        # Get recent growth signals
        signals = supabase.table("growth_signals").select(
            "signal_type, headline"
        ).eq("company_id", company["id"]).order(
            "created_at", desc=True
        ).limit(3).execute()

        signal_text = ""
        if signals.data:
            signal_text = " | ".join(s["headline"] for s in signals.data[:3])

        # Build LinkedIn search URL for finding DMs
        linkedin_search = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={quote_plus(company['name'] + ' CTO OR Head of Engineering')}"
        )

        contact_data = contact.data[0] if contact.data else None

        lead = {
            "company_id": company["id"],
            "company_name": company["name"],
            "company_city": company.get("city", ""),
            "company_state": company.get("state", ""),
            "growth_score": company["growth_score"],
            "industry": company.get("industry", ""),
            "headcount": company.get("headcount_est"),
            "company_linkedin": company.get("linkedin_url", ""),
            "company_website": company.get("website", ""),
            "linkedin_search": linkedin_search,
            "contact_id": contact_data["id"] if contact_data else None,
            "contact_name": (
                f"{contact_data['first_name']} {contact_data['last_name']}"
                if contact_data else ""
            ),
            "contact_title": contact_data.get("title", "") if contact_data else "",
            "email": contact_data.get("email", "") if contact_data else "",
            "phone": contact_data.get("phone", "") if contact_data else "",
            "contact_linkedin": contact_data.get("linkedin_url", "") if contact_data else "",
            "signals": signal_text,
            "opener": "",  # Filled in by Phase 4 (AI openers)
        }

        leads.append(lead)

        if len(leads) >= limit:
            break

    return leads


def _get_retry_leads(owner_id: str) -> list[dict]:
    """Get leads that are due for retry (voicemail/no answer follow-ups)."""
    # Check for outreach logs with next_retry_at <= now
    retries = supabase.table("outreach_log").select(
        "contact_id, company_id, retry_count"
    ).eq("owner_id", owner_id).lte(
        "next_retry_at", datetime.now(timezone.utc).isoformat()
    ).lt("retry_count", config.MAX_RETRIES).execute()

    return retries.data or []


def _render_email(leads: list[dict], retry_count: int, total_pipeline: int) -> str:
    """Render the call sheet HTML email from template."""
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)

    now = datetime.now(timezone.utc)

    return template.render(
        leads=leads,
        retry_count=retry_count,
        total_in_pipeline=total_pipeline,
        date=now.strftime("%A, %d %B %Y"),
        day_of_week=now.strftime("%A"),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
    )


def run_callsheet(limit: int | None = None, with_openers: bool = False):
    """Generate and send the daily call sheet.

    Args:
        limit: Max leads on the sheet. Defaults to config.DAILY_CALL_LIMIT.
        with_openers: Whether to generate AI call openers (Phase 4).
    """
    print("=" * 50)
    print("DAILY CALL SHEET")
    print("=" * 50)

    owner_id = _get_owner_id()
    call_limit = limit or config.DAILY_CALL_LIMIT

    # Get leads
    leads = _get_qualified_leads(owner_id, call_limit)
    retries = _get_retry_leads(owner_id)

    # Count total pipeline
    pipeline = supabase.table("companies").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).in_(
        "status", ["researching", "qualified", "active"]
    ).execute()
    total_pipeline = pipeline.count or 0

    print(f"\n  Leads ready:      {len(leads)}")
    print(f"  Retries due:      {len(retries)}")
    print(f"  Total pipeline:   {total_pipeline}")

    if not leads:
        print("\n  No leads available for today's call sheet.")
        print("  Run 'python main.py discover' and 'python main.py enrich' first.")
        return

    # Generate AI call openers via Claude
    if with_openers:
        print("\n  Generating AI call openers...")
        from pipeline.opener import generate_openers
        leads = generate_openers(leads)

    # Print call sheet to console
    print(f"\n{'-' * 50}")
    print(f"  CALL SHEET — {len(leads)} leads")
    print(f"{'-' * 50}")
    for i, lead in enumerate(leads, 1):
        print(f"\n  #{i} {lead['company_name']} (Score: {lead['growth_score']})")
        print(f"     {lead['industry'] or 'Tech'} | {lead['company_city'] or 'AU'}", end="")
        if lead.get("headcount"):
            print(f" | ~{lead['headcount']} emp", end="")
        print()
        if lead["contact_name"]:
            print(f"     Contact: {lead['contact_name']} — {lead['contact_title']}")
            if lead["email"]:
                print(f"     Email: {lead['email']}")
            if lead["phone"]:
                print(f"     Phone: {lead['phone']}")
        else:
            print(f"     Contact: Find DM via LinkedIn search")
        if lead["signals"]:
            print(f"     Signals: {lead['signals'][:80]}")
        if lead["opener"]:
            print(f"     Opener: \"{lead['opener']}\"")

    # Render HTML email
    html = _render_email(leads, len(retries), total_pipeline)

    # Save to database
    supabase.table("daily_callsheets").insert({
        "owner_id": owner_id,
        "total_leads": len(leads),
        "callsheet_json": json.dumps(leads, default=str),
        "email_sent": False,
    }).execute()

    # Send email
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"Call Sheet — {len(leads)} leads for {today}"

    print(f"\n  Sending email...")
    sent = send_callsheet_email(html, subject)

    if sent:
        # Update the most recent callsheet record
        latest = supabase.table("daily_callsheets").select("id").eq(
            "owner_id", owner_id
        ).order("generated_at", desc=True).limit(1).execute()
        if latest.data:
            supabase.table("daily_callsheets").update({
                "email_sent": True,
            }).eq("id", latest.data[0]["id"]).execute()

    # Also save HTML locally for preview
    output_path = Path(__file__).parent.parent / "callsheet_preview.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"\n  Preview saved: {output_path}")
    print(f"  Open in browser to see the formatted call sheet.")
