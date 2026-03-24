"""Weekly summary email generator.

Sends a Monday morning email with pipeline health, activity stats,
and highlights from the past week.

Usage:
    python main.py weekly-summary
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Template

from db.client import supabase
from services.resend_client import send_callsheet_email
import config


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "weekly_summary_email.html"


def _get_owner_id() -> str:
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError("No users found.")
    return users.data[0]["id"]


def _get_weekly_stats(owner_id: str) -> dict:
    """Gather stats for the past 7 days."""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    # New companies discovered this week
    new_companies = supabase.table("companies").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).gte("discovered_at", week_ago).execute()

    # Companies enriched (moved to qualified this week)
    enriched = supabase.table("companies").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).eq(
        "status", "qualified"
    ).gte("updated_at", week_ago).execute()

    # Total outreach this week
    outreach = supabase.table("outreach_log").select(
        "id, outcome", count="exact"
    ).eq("owner_id", owner_id).gte("contacted_at", week_ago).execute()

    # Meetings booked
    meetings = supabase.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).eq(
        "outcome", "meeting_booked"
    ).gte("contacted_at", week_ago).execute()

    # Calls made (cold_call channel)
    calls = supabase.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).eq(
        "channel", "cold_call"
    ).gte("contacted_at", week_ago).execute()

    # LinkedIn messages sent
    linkedin = supabase.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).in_(
        "channel", ["linkedin_connect", "linkedin_message"]
    ).gte("contacted_at", week_ago).execute()

    # Pipeline counts by status
    statuses = ["new", "researching", "qualified", "active", "paused", "dead"]
    pipeline = {}
    for status in statuses:
        result = supabase.table("companies").select(
            "id", count="exact"
        ).eq("owner_id", owner_id).eq("status", status).execute()
        pipeline[status] = result.count or 0

    # Contacts added this week
    new_contacts = supabase.table("contacts").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).gte("created_at", week_ago).execute()

    # Top leads (highest score qualified companies)
    top_leads = supabase.table("companies").select(
        "name, growth_score, city, industry"
    ).eq("owner_id", owner_id).eq(
        "status", "qualified"
    ).order("growth_score", desc=True).limit(5).execute()

    # Cooldown queue size
    cooldown_cutoff = (now - timedelta(days=config.COOLDOWN_DAYS)).isoformat()
    cooldown = supabase.table("outreach_log").select(
        "company_id", count="exact"
    ).eq("owner_id", owner_id).gte("contacted_at", cooldown_cutoff).execute()

    # Retries due
    retries = supabase.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", owner_id).lte(
        "next_retry_at", now.isoformat()
    ).lt("retry_count", config.MAX_RETRIES).execute()

    return {
        "new_companies": new_companies.count or 0,
        "enriched": enriched.count or 0,
        "total_outreach": outreach.count or 0,
        "meetings_booked": meetings.count or 0,
        "calls_made": calls.count or 0,
        "linkedin_sent": linkedin.count or 0,
        "new_contacts": new_contacts.count or 0,
        "pipeline": pipeline,
        "total_pipeline": sum(pipeline.get(s, 0) for s in ["researching", "qualified", "active"]),
        "top_leads": top_leads.data or [],
        "cooldown_count": cooldown.count or 0,
        "retries_due": retries.count or 0,
    }


def _render_summary(stats: dict) -> str:
    """Render the weekly summary HTML email."""
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    return template.render(
        stats=stats,
        week_start=week_ago.strftime("%d %b"),
        week_end=now.strftime("%d %b %Y"),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
    )


def run_weekly_summary():
    """Generate and send the weekly summary email."""
    print("=" * 50)
    print("WEEKLY SUMMARY")
    print("=" * 50)

    owner_id = _get_owner_id()
    stats = _get_weekly_stats(owner_id)

    print(f"\n  Week in Review:")
    print(f"    New companies:     {stats['new_companies']}")
    print(f"    Companies enriched:{stats['enriched']}")
    print(f"    New contacts:      {stats['new_contacts']}")
    print(f"    Calls made:        {stats['calls_made']}")
    print(f"    LinkedIn sent:     {stats['linkedin_sent']}")
    print(f"    Meetings booked:   {stats['meetings_booked']}")
    print(f"\n  Pipeline Health:")
    for status, count in stats['pipeline'].items():
        print(f"    {status:<15} {count}")
    print(f"    {'Active pipeline':<15} {stats['total_pipeline']}")
    print(f"    {'In cooldown':<15} {stats['cooldown_count']}")
    print(f"    {'Retries due':<15} {stats['retries_due']}")

    if stats['top_leads']:
        print(f"\n  Top Leads:")
        for lead in stats['top_leads']:
            print(f"    {lead['growth_score']:>3}  {lead['name']:<35} {lead.get('city', '')}")

    # Render and send
    html = _render_summary(stats)

    now = datetime.now(timezone.utc)
    subject = f"Weekly Summary - {now.strftime('%d %b %Y')}"

    print(f"\n  Sending weekly summary email...")
    sent = send_callsheet_email(html, subject)

    if sent:
        print("  Email sent!")
    else:
        print("  Email not sent (check Resend config).")

    # Save preview
    output_path = Path(__file__).parent.parent / "weekly_summary_preview.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  Preview saved: {output_path}")
