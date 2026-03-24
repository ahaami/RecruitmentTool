"""Email outreach automation — personalised intro emails via Resend.

Generates and sends customised outreach emails to decision-makers,
using Claude for personalisation and Resend for delivery.

Usage:
    python main.py email-outreach
    python main.py email-outreach --limit 5 --dry-run
"""

import time
from datetime import datetime, timezone

from db.client import supabase
from services.claude_client import generate_text
import resend
import config


EMAIL_SYSTEM_PROMPT = """\
You are writing a brief, professional outreach email for an Australian IT recruiter.

Rules:
- First person, conversational but professional Australian tone
- Reference a specific growth signal (job posting, funding, news) if available
- Keep it under 120 words total
- Subject line must be under 60 characters
- No hard sell. Position as a helpful resource, not a pushy salesperson
- End with a soft call to action (e.g. "Worth a quick chat?")
- Do NOT use emojis, excessive exclamation marks, or fake urgency
- Personalise with the contact's name and title

Output format:
SUBJECT: <subject line>
---
<email body>"""


def generate_outreach_email(contact: dict, company: dict, signals: list[dict]) -> dict | None:
    """Generate a personalised outreach email using Claude.

    Returns:
        Dict with 'subject' and 'body' keys, or None on failure.
    """
    prompt_parts = [
        f"Contact: {contact['first_name']} {contact['last_name']}",
        f"Title: {contact.get('title', 'N/A')}",
        f"Company: {company['name']}",
        f"Industry: {company.get('industry', 'Technology')}",
        f"Location: {company.get('city', 'AU')}",
        f"Headcount: {company.get('headcount_est', 'Unknown')}",
    ]

    if signals:
        prompt_parts.append("\nGrowth Signals:")
        for s in signals[:5]:
            prompt_parts.append(f"- [{s['signal_type']}] {s['headline']}")

    prompt_parts.append(
        "\nRecruiter: Alex from Lunar Recruitment, specialist IT recruitment in Australia."
    )

    text = generate_text(EMAIL_SYSTEM_PROMPT, "\n".join(prompt_parts), max_tokens=400)
    if not text:
        return None

    # Parse subject and body
    if "SUBJECT:" in text and "---" in text:
        parts = text.split("---", 1)
        subject = parts[0].replace("SUBJECT:", "").strip()
        body = parts[1].strip()
        return {"subject": subject, "body": body}

    return None


def send_outreach_email(
    contact: dict,
    company: dict,
    subject: str,
    body: str,
    owner_id: str,
) -> bool:
    """Send an outreach email and log it.

    Returns True if sent successfully.
    """
    if not contact.get("email"):
        return False

    if not config.RESEND_API_KEY:
        print(f"    Resend API key not set — skipping email")
        return False

    # Build HTML email
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;
                padding: 20px; color: #333;">
        <p>{body.replace(chr(10), '<br>')}</p>
        <br>
        <p style="color: #666; font-size: 13px;">
            Alex<br>
            Lunar Recruitment<br>
            Specialist IT Recruitment — Australia
        </p>
    </div>
    """

    from_email = config.CALLSHEET_FROM_EMAIL or "onboarding@resend.dev"
    resend.api_key = config.RESEND_API_KEY

    try:
        resp = resend.Emails.send({
            "from": from_email,
            "to": [contact["email"]],
            "subject": subject,
            "html": html_body,
        })

        if not resp or not resp.get("id"):
            print(f"    Email send failed: {resp}")
            return False

        # Log in outreach_log
        supabase.table("outreach_log").insert({
            "contact_id": contact["id"],
            "company_id": company["id"],
            "owner_id": owner_id,
            "channel": "email",
            "outcome": "sent",
            "notes": f"Subject: {subject}",
        }).execute()

        return True

    except Exception as e:
        print(f"    Email send error: {e}")
        return False


def run_email_outreach(limit: int = 10, dry_run: bool = False):
    """Run email outreach for qualified contacts who haven't been emailed.

    Args:
        limit: Max emails to send per run.
        dry_run: If True, generate emails but don't send.
    """
    print("=" * 50)
    print("EMAIL OUTREACH")
    print("=" * 50)

    # Get first user
    users = supabase.table("users").select("id").limit(1).execute()
    if not users.data:
        print("No users found.")
        return
    owner_id = users.data[0]["id"]

    # Find contacts with email who haven't been emailed yet
    contacts = supabase.table("contacts").select(
        "id, first_name, last_name, title, email, company_id, is_decision_maker, "
        "companies(id, name, industry, city, state, headcount_est, growth_score)"
    ).eq("owner_id", owner_id).eq(
        "is_decision_maker", True
    ).not_.is_("email", "null").order(
        "created_at", desc=True
    ).limit(limit * 3).execute()

    if not contacts.data:
        print("No contacts with email found.")
        return

    # Filter out already-emailed contacts
    eligible = []
    for contact in contacts.data:
        existing = supabase.table("outreach_log").select(
            "id", count="exact"
        ).eq("contact_id", contact["id"]).eq("channel", "email").execute()

        if (existing.count or 0) == 0:
            eligible.append(contact)

        if len(eligible) >= limit:
            break

    print(f"\nEligible contacts: {len(eligible)}")

    if not eligible:
        print("All contacts have already been emailed.")
        return

    sent_count = 0
    for i, contact in enumerate(eligible, 1):
        company = contact.get("companies", {}) or {}
        name = f"{contact['first_name']} {contact['last_name']}"
        print(f"\n[{i}/{len(eligible)}] {name} at {company.get('name', 'Unknown')}")

        # Get signals
        signals = supabase.table("growth_signals").select(
            "signal_type, headline"
        ).eq("company_id", contact["company_id"]).order(
            "created_at", desc=True
        ).limit(5).execute()

        # Generate email
        email_data = generate_outreach_email(
            contact, company, signals.data or []
        )

        if not email_data:
            print(f"    Could not generate email — skipping")
            continue

        print(f"    Subject: {email_data['subject']}")

        if dry_run:
            print(f"    [DRY RUN] Would send to: {contact['email']}")
            print(f"    Body preview: {email_data['body'][:100]}...")
        else:
            success = send_outreach_email(
                contact, company,
                email_data["subject"], email_data["body"],
                owner_id,
            )
            if success:
                sent_count += 1
                print(f"    Sent to: {contact['email']}")
            else:
                print(f"    Failed to send")

        if i < len(eligible):
            time.sleep(2)  # Rate limit

    print(f"\n{'=' * 50}")
    print(f"EMAIL OUTREACH COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Emails {'generated' if dry_run else 'sent'}: {sent_count if not dry_run else len(eligible)}")
