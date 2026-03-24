"""Contacts page — contact details, outreach history, quick actions, CSV export."""

import csv
import io
import streamlit as st
from datetime import datetime, timedelta, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import (
    page_header, metric_row, dm_badge, confidence_badge,
    OUTCOME_COLORS,
)


def render():
    page_header("Contacts", "Manage your decision-maker contacts")

    sb = get_supabase()
    user_id = get_user_id()

    # --- Filters ---
    col_search, col_dm, col_source = st.columns([3, 1, 1])

    with col_search:
        search = st.text_input(
            "Search", placeholder="Name, title, or company...",
            label_visibility="collapsed",
        )

    with col_dm:
        dm_only = st.checkbox("Decision makers only", value=False)

    with col_source:
        source_filter = st.selectbox("Source", ["All", "apollo", "lusha"])

    # Build query
    query = sb.table("contacts").select(
        "id, first_name, last_name, title, email, phone, linkedin_url, "
        "is_decision_maker, confidence, source, created_at, "
        "companies(id, name, growth_score, status, city)"
    ).eq("owner_id", user_id)

    if dm_only:
        query = query.eq("is_decision_maker", True)
    if source_filter != "All":
        query = query.eq("source", source_filter)

    contacts = query.order("created_at", desc=True).limit(100).execute()

    # Client-side search filter
    if search and contacts.data:
        sl = search.lower()
        contacts.data = [
            c for c in contacts.data
            if sl in f"{c['first_name']} {c['last_name']}".lower()
            or sl in (c.get("title") or "").lower()
            or sl in (c.get("companies", {}).get("name", "")).lower()
        ]

    contact_list = contacts.data or []

    # --- Top metrics ---
    total = len(contact_list)
    dm_count = sum(1 for c in contact_list if c.get("is_decision_maker"))
    with_email = sum(1 for c in contact_list if c.get("email"))
    with_phone = sum(1 for c in contact_list if c.get("phone"))

    metric_row([
        {"label": "Total Contacts", "value": total},
        {"label": "Decision Makers", "value": dm_count},
        {"label": "With Email", "value": with_email},
        {"label": "With Phone", "value": with_phone},
    ])

    # Export
    col_count, col_export = st.columns([3, 1])
    with col_count:
        st.markdown(f"**{total} contacts** shown")
    with col_export:
        if contact_list:
            csv_data = _contacts_to_csv(contact_list)
            st.download_button("Export CSV", csv_data, "contacts.csv", "text/csv")

    st.markdown("---")

    if not contact_list:
        st.info("No contacts found. Run `python main.py enrich` to find decision-makers.")
        return

    # --- Contact cards ---
    for contact in contact_list:
        company = contact.get("companies", {}) or {}
        name = f"{contact['first_name']} {contact['last_name']}"
        title = contact.get("title", "N/A")
        comp_name = company.get("name", "Unknown")

        with st.expander(f"{name}  |  {title}  |  {comp_name}", expanded=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                # Badges
                badges = []
                if contact.get("is_decision_maker"):
                    badges.append(dm_badge())
                badges.append(confidence_badge(contact.get("confidence", 0)))
                st.markdown(" ".join(badges), unsafe_allow_html=True)

                # Details
                st.markdown(f"**{title}** at **{comp_name}**")
                st.markdown(
                    f'<span style="font-size:13px;color:#64748b;">'
                    f'{company.get("city", "AU")} &middot; '
                    f'Score: {company.get("growth_score", 0)} &middot; '
                    f'{company.get("status", "").upper()}</span>',
                    unsafe_allow_html=True,
                )

                # Contact info
                contact_html = []
                if contact.get("email"):
                    contact_html.append(
                        f'<div style="margin:4px 0;"><strong>Email:</strong> '
                        f'{contact["email"]}</div>'
                    )
                if contact.get("phone"):
                    contact_html.append(
                        f'<div style="margin:4px 0;"><strong>Phone:</strong> '
                        f'<code>{contact["phone"]}</code></div>'
                    )
                if contact.get("linkedin_url"):
                    contact_html.append(
                        f'<div style="margin:4px 0;">'
                        f'<a href="{contact["linkedin_url"]}" target="_blank">'
                        f'LinkedIn Profile</a></div>'
                    )
                if contact_html:
                    st.markdown(
                        '<div style="background:#f8fafc;padding:10px 14px;'
                        'border-radius:8px;margin:8px 0;">'
                        + "".join(contact_html) + '</div>',
                        unsafe_allow_html=True,
                    )

                st.caption(
                    f"Source: {contact.get('source', 'N/A')} | "
                    f"Added: {contact.get('created_at', '')[:10]}"
                )

            with col2:
                st.markdown("**Log Outcome**")
                outcome = st.selectbox(
                    "Outcome",
                    ["", "no_answer", "voicemail", "spoke_gatekeeper",
                     "spoke_dm", "meeting_booked", "not_interested",
                     "callback_requested"],
                    key=f"outcome_{contact['id']}",
                    label_visibility="collapsed",
                )
                notes = st.text_input(
                    "Notes", key=f"notes_{contact['id']}",
                    label_visibility="collapsed",
                    placeholder="Notes...",
                )
                if outcome:
                    if st.button("Log Call", key=f"log_{contact['id']}", use_container_width=True):
                        _log_outcome(sb, user_id, contact, company, outcome, notes)
                        st.success(f"Logged: {outcome}")
                        if outcome == "meeting_booked":
                            from services.calendar_helper import generate_meeting_calendar_url
                            cal_url = generate_meeting_calendar_url(
                                contact_name=f"{contact['first_name']} {contact['last_name']}",
                                company_name=company.get("name", ""),
                                contact_title=contact.get("title", ""),
                                contact_phone=contact.get("phone", ""),
                                contact_email=contact.get("email", ""),
                            )
                            st.markdown(f"[Add to Google Calendar]({cal_url})")

            # Outreach history
            history = sb.table("outreach_log").select(
                "channel, outcome, notes, contacted_at, retry_count"
            ).eq("contact_id", contact["id"]).order(
                "contacted_at", desc=True
            ).limit(10).execute()

            if history.data:
                st.markdown("**Outreach History**")
                for entry in history.data:
                    date = entry["contacted_at"][:10]
                    ch = entry.get("channel", "unknown")
                    out = entry.get("outcome", "N/A")
                    color = OUTCOME_COLORS.get(out, "#94a3b8")
                    retry = f" (retry #{entry['retry_count']})" if entry.get("retry_count") else ""
                    entry_notes = entry.get("notes", "")

                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid #f1f5f9;'
                        f'font-size:13px;">'
                        f'<span style="color:#94a3b8;">{date}</span> &middot; '
                        f'{ch} &middot; '
                        f'<span style="background:{color};color:#fff;padding:1px 6px;'
                        f'border-radius:4px;font-size:11px;font-weight:600;">{out}</span>'
                        f'{retry}'
                        f'{"  &middot; " + entry_notes if entry_notes else ""}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


def _log_outcome(sb, user_id, contact, company, outcome, notes):
    """Log a call outcome."""
    retry_count = 0
    next_retry = None

    if outcome in ("no_answer", "voicemail"):
        existing = sb.table("outreach_log").select("retry_count").eq(
            "contact_id", contact["id"]
        ).order("contacted_at", desc=True).limit(1).execute()
        if existing.data:
            retry_count = existing.data[0]["retry_count"] + 1
        if retry_count < 3:
            next_retry = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()

    sb.table("outreach_log").insert({
        "contact_id": contact["id"],
        "company_id": company.get("id"),
        "owner_id": user_id,
        "channel": "cold_call",
        "outcome": outcome,
        "notes": notes,
        "retry_count": retry_count,
        "next_retry_at": next_retry,
    }).execute()

    if outcome == "not_interested":
        sb.table("companies").update({"status": "dead"}).eq("id", company.get("id")).execute()
    elif outcome == "meeting_booked":
        sb.table("companies").update({"status": "active"}).eq("id", company.get("id")).execute()


def _contacts_to_csv(contacts: list[dict]) -> str:
    """Convert contacts to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "First Name", "Last Name", "Title", "Company",
        "Email", "Phone", "Decision Maker", "Confidence",
        "Source", "LinkedIn",
    ])
    for c in contacts:
        comp = c.get("companies", {}) or {}
        writer.writerow([
            c.get("first_name", ""), c.get("last_name", ""),
            c.get("title", ""), comp.get("name", ""),
            c.get("email", ""), c.get("phone", ""),
            "Yes" if c.get("is_decision_maker") else "No",
            c.get("confidence", ""),
            c.get("source", ""), c.get("linkedin_url", ""),
        ])
    return output.getvalue()
