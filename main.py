"""Recruiter Intelligence Tool — CLI entry point.

Usage:
    python main.py test-db                             Test Supabase connection
    python main.py discover                            Find new AU tech companies
    python main.py enrich                              Enrich companies with contacts
    python main.py callsheet [--limit N] [--with-openers]  Generate & email daily call sheet
    python main.py log-call <contact_id> <outcome>     Log a call outcome
    python main.py exclude <company_name> [--reason R] Block a company
    python main.py warmup [--limit N]                  Generate LinkedIn warm-up messages
    python main.py warmup-list                         Show pending LinkedIn messages
    python main.py warmup-sent <warmup_id>             Mark a LinkedIn message as sent
    python main.py monitor                             Re-check companies for new signals
    python main.py weekly-summary                      Send weekly pipeline summary email
    python main.py pause-stale                         Pause companies with no signals in 30+ days
    python main.py run-all                             Run full daily pipeline
"""

import argparse
import sys


def cmd_test_db(args):
    """Test the Supabase connection by counting rows in core tables."""
    from db.client import supabase

    tables = ["companies", "contacts", "outreach_log", "growth_signals",
              "warmup_queue", "daily_callsheets", "excluded_companies"]

    print("Supabase connection OK!\n")
    print(f"{'Table':<25} {'Rows':>6}")
    print("-" * 33)

    for table in tables:
        try:
            result = supabase.table(table).select("id", count="exact").execute()
            count = result.count if result.count is not None else 0
            print(f"{table:<25} {count:>6}")
        except Exception as e:
            print(f"{table:<25} ERROR: {e}")

    print("\nVerticals:")
    verticals = supabase.table("verticals").select("name, description").execute()
    for v in verticals.data:
        print(f"  - {v['name']}: {v['description']}")


def cmd_discover(args):
    """Run company discovery pipeline."""
    from pipeline.discover import run_discovery
    run_discovery()


def cmd_enrich(args):
    """Run contact enrichment pipeline."""
    from pipeline.enrich import run_enrichment
    run_enrichment()


def cmd_callsheet(args):
    """Generate and email the daily call sheet."""
    from pipeline.callsheet import run_callsheet
    run_callsheet(limit=args.limit, with_openers=args.with_openers)


def cmd_log_call(args):
    """Log the outcome of a call."""
    from db.client import supabase
    import config
    from datetime import datetime, timedelta, timezone

    valid_outcomes = [
        "no_answer", "voicemail", "spoke_gatekeeper", "spoke_dm",
        "meeting_booked", "not_interested", "callback_requested",
    ]

    if args.outcome not in valid_outcomes:
        print(f"Invalid outcome '{args.outcome}'. Must be one of:")
        for o in valid_outcomes:
            print(f"  - {o}")
        sys.exit(1)

    # Get the contact info
    contact = supabase.table("contacts").select("*, companies(*)").eq(
        "id", args.contact_id
    ).single().execute()

    if not contact.data:
        print(f"Contact {args.contact_id} not found.")
        sys.exit(1)

    contact_data = contact.data
    company = contact_data["companies"]

    # Calculate retry schedule
    next_retry = None
    retry_count = 0

    if args.outcome in ("no_answer", "voicemail"):
        # Check existing retry count
        existing = supabase.table("outreach_log").select("retry_count").eq(
            "contact_id", args.contact_id
        ).order("contacted_at", desc=True).limit(1).execute()

        if existing.data:
            retry_count = existing.data[0]["retry_count"] + 1

        if retry_count < config.MAX_RETRIES:
            next_retry = (
                datetime.now(timezone.utc)
                + timedelta(days=config.RETRY_DELAY_DAYS)
            ).isoformat()
            print(f"Retry #{retry_count + 1} scheduled for {config.RETRY_DELAY_DAYS} days from now.")
        else:
            print(f"Max retries ({config.MAX_RETRIES}) reached. Contact parked.")

    # Insert outreach log entry
    supabase.table("outreach_log").insert({
        "contact_id": args.contact_id,
        "company_id": company["id"],
        "owner_id": company["owner_id"],
        "channel": "cold_call",
        "outcome": args.outcome,
        "notes": args.notes or "",
        "retry_count": retry_count,
        "next_retry_at": next_retry,
    }).execute()

    # Update company status based on outcome
    if args.outcome == "not_interested":
        supabase.table("companies").update({"status": "dead"}).eq(
            "id", company["id"]
        ).execute()
        print(f"Company '{company['name']}' marked as dead.")

    elif args.outcome == "meeting_booked":
        supabase.table("companies").update({"status": "active"}).eq(
            "id", company["id"]
        ).execute()
        print(f"Meeting booked with {contact_data['first_name']} at {company['name']}!")

    else:
        print(f"Logged: {args.outcome} for {contact_data['first_name']} {contact_data['last_name']} at {company['name']}")


def cmd_exclude(args):
    """Add a company to the exclusion list."""
    from db.client import supabase

    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        print("No users found. Please set up a user first.")
        sys.exit(1)

    owner_id = users.data[0]["id"]

    supabase.table("excluded_companies").upsert({
        "owner_id": owner_id,
        "company_name": args.company_name,
        "domain": args.domain,
        "reason": args.reason or "",
    }).execute()

    print(f"Excluded: '{args.company_name}'")
    if args.reason:
        print(f"  Reason: {args.reason}")


def cmd_warmup(args):
    """Generate LinkedIn warm-up messages."""
    from pipeline.warmup import run_warmup
    run_warmup(limit=args.limit)


def cmd_warmup_list(args):
    """Show pending LinkedIn warm-up messages."""
    from pipeline.warmup import list_pending_warmups
    list_pending_warmups()


def cmd_warmup_sent(args):
    """Mark a LinkedIn warm-up message as sent."""
    from pipeline.warmup import mark_warmup_sent
    mark_warmup_sent(args.warmup_id)


def cmd_monitor(args):
    """Run company monitoring for new signals."""
    from pipeline.monitor import run_monitor
    run_monitor()


def cmd_weekly_summary(args):
    """Generate and send weekly summary email."""
    from pipeline.weekly_summary import run_weekly_summary
    run_weekly_summary()


def cmd_pause_stale(args):
    """Pause companies with no new signals in 30+ days."""
    from db.client import supabase
    from datetime import datetime, timedelta, timezone

    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        print("No users found.")
        sys.exit(1)

    owner_id = users.data[0]["id"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    stale = supabase.table("companies").select(
        "id, name, growth_score, status, updated_at"
    ).eq("owner_id", owner_id).in_(
        "status", ["qualified", "researching"]
    ).lte("updated_at", cutoff).execute()

    if not stale.data:
        print("No stale companies found.")
        return

    print(f"Pausing {len(stale.data)} stale companies:\n")
    for company in stale.data:
        supabase.table("companies").update({
            "status": "paused",
        }).eq("id", company["id"]).execute()
        print(f"  Paused: {company['name']} (score: {company['growth_score']})")

    print(f"\n{len(stale.data)} companies paused. They'll reactivate if new signals are found.")


def cmd_run_all(args):
    """Run the full daily pipeline."""
    from scheduler import run_daily
    run_daily()


def main():
    parser = argparse.ArgumentParser(
        description="Recruiter Intelligence Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # test-db
    subparsers.add_parser("test-db", help="Test Supabase connection")

    # discover
    subparsers.add_parser("discover", help="Find new AU tech companies")

    # enrich
    subparsers.add_parser("enrich", help="Enrich companies with contacts")

    # callsheet
    cs_parser = subparsers.add_parser("callsheet", help="Generate daily call sheet")
    cs_parser.add_argument("--limit", type=int, default=None,
                           help="Max leads on call sheet (default: from .env)")
    cs_parser.add_argument("--with-openers", action="store_true", default=False,
                           help="Include AI-generated call openers")

    # log-call
    lc_parser = subparsers.add_parser("log-call", help="Log a call outcome")
    lc_parser.add_argument("contact_id", help="Contact UUID")
    lc_parser.add_argument("outcome", help="Call outcome (no_answer, voicemail, spoke_gatekeeper, spoke_dm, meeting_booked, not_interested, callback_requested)")
    lc_parser.add_argument("--notes", help="Optional notes about the call")

    # exclude
    ex_parser = subparsers.add_parser("exclude", help="Block a company")
    ex_parser.add_argument("company_name", help="Company name to exclude")
    ex_parser.add_argument("--domain", help="Company domain to exclude")
    ex_parser.add_argument("--reason", help="Why this company is excluded")

    # warmup
    wu_parser = subparsers.add_parser("warmup", help="Generate LinkedIn warm-up messages")
    wu_parser.add_argument("--limit", type=int, default=10,
                           help="Max contacts to generate messages for")

    # warmup-list
    subparsers.add_parser("warmup-list", help="Show pending LinkedIn messages")

    # warmup-sent
    ws_parser = subparsers.add_parser("warmup-sent", help="Mark LinkedIn message as sent")
    ws_parser.add_argument("warmup_id", help="Warmup queue entry UUID")

    # monitor
    subparsers.add_parser("monitor", help="Re-check companies for new growth signals")

    # weekly-summary
    subparsers.add_parser("weekly-summary", help="Send weekly pipeline summary email")

    # pause-stale
    subparsers.add_parser("pause-stale", help="Pause companies with no signals in 30+ days")

    # run-all
    subparsers.add_parser("run-all", help="Run full daily pipeline")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "test-db": cmd_test_db,
        "discover": cmd_discover,
        "enrich": cmd_enrich,
        "callsheet": cmd_callsheet,
        "log-call": cmd_log_call,
        "exclude": cmd_exclude,
        "warmup": cmd_warmup,
        "warmup-list": cmd_warmup_list,
        "warmup-sent": cmd_warmup_sent,
        "monitor": cmd_monitor,
        "weekly-summary": cmd_weekly_summary,
        "pause-stale": cmd_pause_stale,
        "run-all": cmd_run_all,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
