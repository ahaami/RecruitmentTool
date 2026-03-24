"""Google Calendar integration — generates calendar event links.

Since Google Calendar API requires OAuth (complex setup), we use the
simpler approach of generating Google Calendar event URLs that
auto-populate the event form when clicked.

For a recruiter workflow, this is actually preferable — the recruiter
clicks "Add to Calendar" from the dashboard and confirms the event
in their own Google Calendar.

Usage:
    from services.calendar_helper import generate_calendar_url
    url = generate_calendar_url(
        title="Meeting with Jane Smith at Canva",
        start_dt=datetime(2026, 3, 25, 10, 0),
        duration_mins=30,
        description="Discuss IT recruitment needs",
    )
"""

from datetime import datetime, timedelta
from urllib.parse import quote_plus


def generate_calendar_url(
    title: str,
    start_dt: datetime,
    duration_mins: int = 30,
    description: str = "",
    location: str = "",
) -> str:
    """Generate a Google Calendar event creation URL.

    When the user clicks this link, it opens Google Calendar with the
    event form pre-filled. They can adjust and save.

    Args:
        title: Event title (e.g. "Meeting: Jane Smith at Canva")
        start_dt: Event start datetime (should be in local time)
        duration_mins: Event duration in minutes
        description: Event description / notes
        location: Meeting location or "Phone" or video link

    Returns:
        Google Calendar URL string
    """
    end_dt = start_dt + timedelta(minutes=duration_mins)

    # Format dates for Google Calendar URL (YYYYMMDDTHHMMSS)
    fmt = "%Y%m%dT%H%M%S"
    start_str = start_dt.strftime(fmt)
    end_str = end_dt.strftime(fmt)

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": description,
        "location": location,
    }

    query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items() if v)
    return f"https://calendar.google.com/calendar/render?{query}"


def generate_meeting_calendar_url(
    contact_name: str,
    company_name: str,
    contact_title: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    notes: str = "",
) -> str:
    """Generate a calendar URL for a booked meeting.

    Creates a nicely formatted event with all contact details
    in the description.

    Args:
        contact_name: Full name of the person to meet
        company_name: Company name
        contact_title: Their job title
        contact_phone: Phone number
        contact_email: Email address
        notes: Any additional notes

    Returns:
        Google Calendar URL
    """
    title = f"Meeting: {contact_name} at {company_name}"

    desc_parts = [
        f"Meeting with {contact_name}",
        f"Company: {company_name}",
    ]
    if contact_title:
        desc_parts.append(f"Title: {contact_title}")
    if contact_phone:
        desc_parts.append(f"Phone: {contact_phone}")
    if contact_email:
        desc_parts.append(f"Email: {contact_email}")
    if notes:
        desc_parts.append(f"\nNotes: {notes}")

    desc_parts.append("\n---\nCreated by Lunar Recruitment Tool")

    # Default to tomorrow at 10am
    from datetime import date
    tomorrow = date.today() + timedelta(days=1)
    start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 10, 0)

    return generate_calendar_url(
        title=title,
        start_dt=start,
        duration_mins=30,
        description="\n".join(desc_parts),
        location="Phone",
    )
