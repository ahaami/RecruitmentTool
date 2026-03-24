"""LinkedIn warm-up queue generator.

Generates personalised LinkedIn connection requests and follow-up messages
for qualified leads. NO automation — generates messages for Alex to send
manually via LinkedIn.

The warm-up flow:
1. Day 0: Send LinkedIn connection request (300 char max)
2. Day 1-3: Once connected, send a follow-up message
3. Day 3+: Call the contact (they've seen your name now)

Usage:
    python main.py warmup [--limit N]
"""

from datetime import datetime, timezone
from pathlib import Path

from db.client import supabase
from services.claude_client import generate_text
import config


CONNECT_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "linkedin_connect.txt"

CONNECT_SYSTEM_PROMPT = """\
You are writing a LinkedIn connection request note for an Australian IT recruiter.
The note MUST be under 300 characters (LinkedIn's limit). It should:
- Be warm and professional, not salesy
- Reference something specific about their company (growth, hiring, signals)
- Use casual Australian professional tone
- NOT ask for a meeting or pitch services
- End with a reason to connect

Output ONLY the connection note text, nothing else. Keep it under 300 characters."""

FOLLOWUP_SYSTEM_PROMPT = """\
You are writing a short LinkedIn follow-up message for an Australian IT recruiter.
This is sent AFTER the person accepted the connection request. It should:
- Thank them for connecting
- Reference a specific growth signal or hiring activity at their company
- Casually mention you work in IT recruitment (not a hard pitch)
- End with an open question about their hiring plans
- Be 2-4 sentences, conversational Australian tone
- Be under 500 characters

Output ONLY the message text, nothing else."""


def _get_owner_id() -> str:
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        raise RuntimeError("No users found.")
    return users.data[0]["id"]


def _get_warmup_candidates(owner_id: str, limit: int) -> list[dict]:
    """Get contacts eligible for LinkedIn warm-up.

    Targets: qualified companies with contacts that have LinkedIn URLs,
    not already in warmup queue or recently contacted.
    """
    contacts = supabase.table("contacts").select(
        "id, first_name, last_name, title, linkedin_url, company_id, "
        "companies(id, name, industry, city, growth_score, domain)"
    ).eq("owner_id", owner_id).not_.is_(
        "linkedin_url", "null"
    ).eq("is_decision_maker", True).limit(limit * 2).execute()

    if not contacts.data:
        return []

    candidates = []
    for contact in contacts.data:
        company = contact.get("companies")
        if not company or company.get("status") == "dead":
            continue

        # Skip if already in warmup queue
        existing = supabase.table("warmup_queue").select(
            "id", count="exact"
        ).eq("contact_id", contact["id"]).execute()
        if existing.count and existing.count > 0:
            continue

        # Get recent signals for personalisation
        signals = supabase.table("growth_signals").select(
            "signal_type, headline"
        ).eq("company_id", company["id"]).order(
            "created_at", desc=True
        ).limit(2).execute()

        signal_text = ""
        if signals.data:
            signal_text = " | ".join(s["headline"] for s in signals.data)

        candidates.append({
            "contact_id": contact["id"],
            "company_id": company["id"],
            "first_name": contact["first_name"],
            "last_name": contact["last_name"],
            "title": contact.get("title", ""),
            "linkedin_url": contact.get("linkedin_url", ""),
            "company_name": company["name"],
            "industry": company.get("industry", ""),
            "city": company.get("city", ""),
            "growth_score": company.get("growth_score", 0),
            "signals": signal_text,
        })

        if len(candidates) >= limit:
            break

    return candidates


def _generate_connect_note(candidate: dict) -> str:
    """Generate a LinkedIn connection request note (300 char max)."""
    parts = [
        f"Contact: {candidate['first_name']} {candidate['last_name']} ({candidate['title']})",
        f"Company: {candidate['company_name']}",
    ]
    if candidate.get("industry"):
        parts.append(f"Industry: {candidate['industry']}")
    if candidate.get("city"):
        parts.append(f"Location: {candidate['city']}")
    if candidate.get("signals"):
        parts.append(f"Growth signals: {candidate['signals'][:200]}")

    user_prompt = "\n".join(parts)
    note = generate_text(CONNECT_SYSTEM_PROMPT, user_prompt, max_tokens=100)

    # Enforce 300 char limit
    if len(note) > 300:
        note = note[:297] + "..."

    return note


def _generate_followup_message(candidate: dict) -> str:
    """Generate a LinkedIn follow-up message."""
    parts = [
        f"Contact: {candidate['first_name']} {candidate['last_name']} ({candidate['title']})",
        f"Company: {candidate['company_name']}",
    ]
    if candidate.get("industry"):
        parts.append(f"Industry: {candidate['industry']}")
    if candidate.get("signals"):
        parts.append(f"Growth signals: {candidate['signals'][:200]}")

    user_prompt = "\n".join(parts)
    return generate_text(FOLLOWUP_SYSTEM_PROMPT, user_prompt, max_tokens=200)


def run_warmup(limit: int = 10):
    """Generate LinkedIn warm-up messages for qualified leads.

    Args:
        limit: Max contacts to generate messages for.
    """
    print("=" * 50)
    print("LINKEDIN WARM-UP QUEUE")
    print("=" * 50)

    owner_id = _get_owner_id()
    candidates = _get_warmup_candidates(owner_id, limit)

    print(f"\n  Candidates for warm-up: {len(candidates)}")

    if not candidates:
        print("  No eligible contacts with LinkedIn profiles.")
        print("  Run 'python main.py enrich' to find contacts first.")
        return

    queued = 0
    for i, candidate in enumerate(candidates, 1):
        print(f"\n  [{i}/{len(candidates)}] {candidate['first_name']} {candidate['last_name']}")
        print(f"    {candidate['title']} at {candidate['company_name']}")

        # Generate connection note
        print("    Generating connection note...", end=" ")
        connect_note = _generate_connect_note(candidate)
        if not connect_note:
            print("skipped (API error)")
            continue
        print(f"done ({len(connect_note)} chars)")

        # Generate follow-up message
        print("    Generating follow-up message...", end=" ")
        followup = _generate_followup_message(candidate)
        if followup:
            print("done")
        else:
            print("skipped")

        # Combine into one message field (connection note + separator + follow-up)
        full_message = f"CONNECTION REQUEST (paste into LinkedIn):\n{connect_note}"
        if followup:
            full_message += f"\n\n---\n\nFOLLOW-UP MESSAGE (send after they accept):\n{followup}"

        # Save to warmup queue
        supabase.table("warmup_queue").insert({
            "contact_id": candidate["contact_id"],
            "company_id": candidate["company_id"],
            "owner_id": owner_id,
            "linkedin_message": full_message,
            "status": "pending",
        }).execute()

        queued += 1
        print(f"    LinkedIn: {candidate.get('linkedin_url', 'N/A')}")

    print(f"\n{'=' * 50}")
    print(f"WARM-UP COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Messages queued: {queued}")
    print(f"  View in dashboard or run: python main.py warmup-list")


def list_pending_warmups():
    """Display pending LinkedIn warm-up messages."""
    owner_id = _get_owner_id()

    pending = supabase.table("warmup_queue").select(
        "id, linkedin_message, queued_at, "
        "contacts(first_name, last_name, title, linkedin_url), "
        "companies(name)"
    ).eq("owner_id", owner_id).eq(
        "status", "pending"
    ).order("queued_at", desc=True).limit(20).execute()

    if not pending.data:
        print("No pending LinkedIn messages.")
        return

    print(f"\n  PENDING LINKEDIN MESSAGES ({len(pending.data)})")
    print(f"  {'=' * 50}")

    for i, item in enumerate(pending.data, 1):
        contact = item.get("contacts", {})
        company = item.get("companies", {})
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
        print(f"\n  #{i} {name} at {company.get('name', 'Unknown')}")
        print(f"  LinkedIn: {contact.get('linkedin_url', 'N/A')}")
        print(f"  ID: {item['id']}")
        print(f"  ---")

        # Show just the connection request part
        msg = item.get("linkedin_message", "")
        lines = msg.split("\n")
        for line in lines:
            print(f"  {line}")

        print()


def mark_warmup_sent(warmup_id: str):
    """Mark a warmup message as sent."""
    supabase.table("warmup_queue").update({
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", warmup_id).execute()

    # Also log to outreach_log
    warmup = supabase.table("warmup_queue").select(
        "contact_id, company_id, owner_id"
    ).eq("id", warmup_id).single().execute()

    if warmup.data:
        supabase.table("outreach_log").insert({
            "contact_id": warmup.data["contact_id"],
            "company_id": warmup.data["company_id"],
            "owner_id": warmup.data["owner_id"],
            "channel": "linkedin_connect",
            "outcome": "pending",
            "notes": "LinkedIn connection request sent",
        }).execute()

    print(f"  Marked as sent: {warmup_id}")
