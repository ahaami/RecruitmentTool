"""AI research summaries — generates one-page company briefs before calls.

Uses Claude to synthesise all known data about a company into a
concise brief: what they do, why they're growing, who to talk to,
and suggested talking points.

Usage:
    from pipeline.research import generate_company_brief
    brief = generate_company_brief(company_id)
"""

from services.claude_client import generate_text
from db.client import supabase


SYSTEM_PROMPT = """\
You are a research assistant for an Australian IT recruitment agency.
Generate a concise company research brief that a recruiter can scan
in 60 seconds before picking up the phone.

Write in plain, direct language. Australian business context.
Use bullet points for key facts. Keep the total under 300 words.

Structure:
1. COMPANY SNAPSHOT — what they do, size, location, industry
2. WHY THEY'RE GROWING — specific signals (job postings, funding, news)
3. KEY CONTACTS — who we know at the company + their roles
4. TALKING POINTS — 3 specific conversation starters based on their signals
5. POTENTIAL NEEDS — what roles they likely need filled based on signals

Be specific. Reference actual data. No generic filler."""


def generate_company_brief(company_id: str) -> str:
    """Generate an AI research brief for a company.

    Gathers all available data (company info, signals, contacts, outreach)
    and synthesises it into a recruiter-friendly brief.

    Returns:
        The brief as a string, or empty string on failure.
    """
    # Gather company data
    company = supabase.table("companies").select("*").eq(
        "id", company_id
    ).limit(1).execute()

    if not company.data:
        return ""

    c = company.data[0]

    # Growth signals
    signals = supabase.table("growth_signals").select(
        "signal_type, headline, source_url, created_at"
    ).eq("company_id", company_id).order(
        "created_at", desc=True
    ).limit(10).execute()

    # Contacts
    contacts = supabase.table("contacts").select(
        "first_name, last_name, title, email, phone, is_decision_maker, source"
    ).eq("company_id", company_id).execute()

    # Outreach history
    outreach = supabase.table("outreach_log").select(
        "channel, outcome, notes, contacted_at"
    ).eq("company_id", company_id).order(
        "contacted_at", desc=True
    ).limit(5).execute()

    # Build the prompt
    prompt_parts = [
        f"Company: {c['name']}",
        f"Domain: {c.get('domain', 'Unknown')}",
        f"Location: {c.get('city', 'AU')}, {c.get('state', '')}",
        f"Industry: {c.get('industry', 'Technology')}",
        f"Headcount: {c.get('headcount_est', 'Unknown')}",
        f"Growth Score: {c.get('growth_score', 0)}/100",
        f"Status: {c.get('status', 'Unknown')}",
    ]

    if c.get("linkedin_url"):
        prompt_parts.append(f"LinkedIn: {c['linkedin_url']}")
    if c.get("website"):
        prompt_parts.append(f"Website: {c['website']}")
    if c.get("notes"):
        prompt_parts.append(f"Notes: {c['notes'][:300]}")

    if signals.data:
        prompt_parts.append("\nGrowth Signals:")
        for s in signals.data:
            prompt_parts.append(f"- [{s['signal_type']}] {s['headline']} ({s['created_at'][:10]})")

    if contacts.data:
        prompt_parts.append("\nKnown Contacts:")
        for ct in contacts.data:
            dm = " [Decision Maker]" if ct.get("is_decision_maker") else ""
            has_phone = " (has phone)" if ct.get("phone") else ""
            has_email = " (has email)" if ct.get("email") else ""
            prompt_parts.append(
                f"- {ct['first_name']} {ct['last_name']} — {ct.get('title', 'N/A')}"
                f"{dm}{has_phone}{has_email}"
            )

    if outreach.data:
        prompt_parts.append("\nOutreach History:")
        for o in outreach.data:
            prompt_parts.append(
                f"- {o['contacted_at'][:10]} | {o['channel']} | {o['outcome']}"
                f"{' | ' + o['notes'] if o.get('notes') else ''}"
            )

    user_prompt = "\n".join(prompt_parts)

    return generate_text(SYSTEM_PROMPT, user_prompt, max_tokens=600)


def generate_brief_for_dashboard(company_id: str, owner_id: str) -> str:
    """Generate a brief, using cache if available.

    Stores briefs in the company's notes field with a prefix so we
    can detect cached briefs.
    """
    company = supabase.table("companies").select(
        "notes"
    ).eq("id", company_id).limit(1).execute()

    if company.data:
        notes = company.data[0].get("notes", "") or ""
        # Check for cached brief
        if notes.startswith("AI_BRIEF:"):
            return notes[9:]

    # Generate new brief
    brief = generate_company_brief(company_id)
    if brief:
        # Cache it
        current_notes = company.data[0].get("notes", "") if company.data else ""
        # Keep existing notes, prepend brief
        new_notes = f"AI_BRIEF:{brief}"
        if current_notes and not current_notes.startswith("AI_BRIEF:"):
            new_notes += f"\n\n---\nPrevious notes: {current_notes}"

        supabase.table("companies").update({
            "notes": new_notes
        }).eq("id", company_id).execute()

    return brief
