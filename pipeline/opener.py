"""AI-powered call opener generator.

Generates personalised 2-3 sentence call openers for each lead using
Claude Haiku. References specific growth signals so the recruiter
sounds informed rather than cold-calling.

Usage:
    Called automatically when: python main.py callsheet --with-openers
"""

from services.claude_client import generate_text

SYSTEM_PROMPT = """\
You are a friendly Australian IT recruiter preparing to cold-call a company.
Write a 2-3 sentence call opener that:
- References a specific growth signal (job postings, funding, news) about the company
- Sounds natural and conversational, not scripted or salesy
- Uses casual Australian professional tone (not overly formal)
- Ends with an open question to start a conversation
- Does NOT mention the recruiter's company name
- Is under 60 words

Output ONLY the opener text, nothing else."""


def generate_opener(lead: dict) -> str:
    """Generate a personalised call opener for a single lead.

    Args:
        lead: Dict with company_name, industry, signals, contact_name,
              contact_title, growth_score, headcount, company_city.

    Returns:
        Opener string, or empty string on failure.
    """
    parts = [f"Company: {lead['company_name']}"]

    if lead.get("industry"):
        parts.append(f"Industry: {lead['industry']}")
    if lead.get("company_city"):
        parts.append(f"Location: {lead['company_city']}, {lead.get('company_state', 'AU')}")
    if lead.get("headcount"):
        parts.append(f"Size: ~{lead['headcount']} employees")
    if lead.get("contact_name"):
        parts.append(f"Contact: {lead['contact_name']} ({lead.get('contact_title', 'Decision Maker')})")
    if lead.get("signals"):
        parts.append(f"Growth signals: {lead['signals']}")
    parts.append(f"Growth score: {lead['growth_score']}/100")

    user_prompt = "\n".join(parts)

    return generate_text(SYSTEM_PROMPT, user_prompt)


def generate_openers(leads: list[dict]) -> list[dict]:
    """Generate openers for a list of leads.

    Args:
        leads: List of lead dicts from callsheet pipeline.

    Returns:
        Same list with 'opener' field populated.
    """
    for i, lead in enumerate(leads):
        print(f"    Opener {i + 1}/{len(leads)}: {lead['company_name']}...", end=" ")
        opener = generate_opener(lead)
        if opener:
            lead["opener"] = opener
            # Truncate for display
            preview = opener[:60] + "..." if len(opener) > 60 else opener
            print(f"done ({preview})")
        else:
            print("skipped (no API key or error)")

    return leads
