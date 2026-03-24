"""Call Sheet page — today's leads with openers + log outcomes directly."""

import json
import streamlit as st
from datetime import datetime, timedelta, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import page_header, section_header, metric_row, score_badge


def render():
    page_header("Today's Call Sheet", "Your prioritised leads for today")

    sb = get_supabase()
    user_id = get_user_id()

    # Get today's callsheet
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    callsheet = sb.table("daily_callsheets").select(
        "id, total_leads, callsheet_json, email_sent, generated_at"
    ).eq("owner_id", user_id).gte(
        "generated_at", today_start
    ).order("generated_at", desc=True).limit(1).execute()

    if not callsheet.data:
        # Show most recent
        latest = sb.table("daily_callsheets").select(
            "id, total_leads, callsheet_json, email_sent, generated_at"
        ).eq("owner_id", user_id).order(
            "generated_at", desc=True
        ).limit(1).execute()

        if latest.data:
            st.warning(
                f"No call sheet for today. Showing most recent "
                f"from **{latest.data[0]['generated_at'][:10]}**"
            )
            callsheet = latest
        else:
            st.info("No call sheets generated yet. Run `python main.py callsheet --with-openers`")
            return

    sheet = callsheet.data[0]
    leads = []
    if sheet.get("callsheet_json"):
        if isinstance(sheet["callsheet_json"], str):
            leads = json.loads(sheet["callsheet_json"])
        else:
            leads = sheet["callsheet_json"]

    # Top metrics
    metric_row([
        {"label": "Leads Today", "value": sheet.get("total_leads", len(leads))},
        {"label": "Email Sent", "value": "Yes" if sheet.get("email_sent") else "No"},
        {"label": "Generated", "value": sheet["generated_at"][:16].replace("T", " ")},
    ])

    st.markdown("---")

    # Retries due
    now = datetime.now(timezone.utc).isoformat()
    retries = sb.table("outreach_log").select(
        "id, contact_id, company_id, retry_count, "
        "contacts(first_name, last_name, phone), "
        "companies(name)"
    ).eq("owner_id", user_id).lte(
        "next_retry_at", now
    ).lt("retry_count", 3).execute()

    if retries.data:
        section_header(f"Retries Due ({len(retries.data)})", "&#x1F504;")
        for retry in retries.data:
            contact = retry.get("contacts", {})
            company = retry.get("companies", {})
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
            st.markdown(
                f'<div class="lunar-card" style="border-left:3px solid #f59e0b;">'
                f'<strong>{name}</strong> at {company.get("name", "Unknown")} '
                f'&middot; Attempt #{retry["retry_count"] + 1} '
                f'&middot; Phone: <code>{contact.get("phone", "N/A")}</code>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("---")

    # Display leads
    if not leads:
        st.info("No leads in this call sheet.")
        return

    # CSV export button
    csv_data = _leads_to_csv(leads)
    st.download_button(
        "Export to CSV",
        csv_data,
        file_name="call_sheet.csv",
        mime="text/csv",
        use_container_width=False,
    )

    st.markdown("")

    for i, lead in enumerate(leads):
        score = lead.get("growth_score", 0)
        contact_name = lead.get("contact_name", "No contact")
        title = lead.get("contact_title", "")
        company = lead.get("company_name", "Unknown")

        with st.expander(
            f"#{i+1}  {company}  |  {contact_name}  |  Score: {score}",
            expanded=(i < 3),
        ):
            col_info, col_action = st.columns([3, 1])

            with col_info:
                # Company info row
                info_parts = [lead.get("industry", "Tech"), lead.get("company_city", "AU")]
                if lead.get("headcount"):
                    info_parts.append(f"~{lead['headcount']} employees")
                st.markdown(
                    f'<div style="font-size:13px;color:#64748b;margin-bottom:8px;">'
                    f'{" &middot; ".join(info_parts)}</div>',
                    unsafe_allow_html=True,
                )

                # Contact details
                if lead.get("contact_name"):
                    st.markdown(f"**{lead['contact_name']}** — {title}")
                    contact_parts = []
                    if lead.get("email"):
                        contact_parts.append(f"**Email:** {lead['email']}")
                    if lead.get("phone"):
                        contact_parts.append(f"**Phone:** `{lead['phone']}`")
                    if contact_parts:
                        st.markdown(" | ".join(contact_parts))
                else:
                    st.markdown(
                        '<span style="color:#f59e0b;">No contact found</span> '
                        '— use LinkedIn search below',
                        unsafe_allow_html=True,
                    )

                # Growth signals
                if lead.get("signals"):
                    st.markdown(
                        f'<div style="background:#f0fdf4;border-left:3px solid #22c55e;'
                        f'padding:8px 12px;border-radius:0 8px 8px 0;font-size:13px;'
                        f'margin:8px 0;">{lead["signals"]}</div>',
                        unsafe_allow_html=True,
                    )

                # AI opener
                if lead.get("opener"):
                    st.markdown(
                        f'<div style="background:#eef2ff;border-left:3px solid #6366f1;'
                        f'padding:10px 14px;border-radius:0 8px 8px 0;font-size:13px;'
                        f'font-style:italic;margin:8px 0;color:#3730a3;">'
                        f'&#x1F916; "{lead["opener"]}"</div>',
                        unsafe_allow_html=True,
                    )

                # Links
                links = []
                if lead.get("company_linkedin"):
                    links.append(f"[Company LinkedIn]({lead['company_linkedin']})")
                if lead.get("company_website"):
                    links.append(f"[Website]({lead['company_website']})")
                if lead.get("linkedin_search"):
                    links.append(f"[Find DMs on LinkedIn]({lead['linkedin_search']})")
                if links:
                    st.markdown(" &nbsp;|&nbsp; ".join(links))

            with col_action:
                if lead.get("contact_id"):
                    st.markdown("**Log Outcome**")
                    outcome = st.selectbox(
                        "Outcome",
                        ["", "no_answer", "voicemail", "spoke_gatekeeper",
                         "spoke_dm", "meeting_booked", "not_interested",
                         "callback_requested"],
                        key=f"outcome_{i}",
                        label_visibility="collapsed",
                    )
                    notes = st.text_input(
                        "Notes", key=f"notes_{i}",
                        label_visibility="collapsed",
                        placeholder="Notes...",
                    )
                    if st.button("Log Call", key=f"log_{i}", use_container_width=True):
                        if outcome:
                            _log_outcome(sb, user_id, lead, outcome, notes)
                            st.success(f"Logged: {outcome}")
                            if outcome == "meeting_booked":
                                from services.calendar_helper import generate_meeting_calendar_url
                                cal_url = generate_meeting_calendar_url(
                                    contact_name=lead.get("contact_name", ""),
                                    company_name=lead.get("company_name", ""),
                                    contact_title=lead.get("contact_title", ""),
                                    contact_phone=lead.get("phone", ""),
                                    contact_email=lead.get("email", ""),
                                )
                                st.markdown(f"[Add to Google Calendar]({cal_url})")
                        else:
                            st.warning("Select an outcome")


def _log_outcome(sb, user_id: str, lead: dict, outcome: str, notes: str):
    """Log a call outcome from the dashboard."""
    retry_count = 0
    next_retry = None

    if outcome in ("no_answer", "voicemail"):
        existing = sb.table("outreach_log").select("retry_count").eq(
            "contact_id", lead["contact_id"]
        ).order("contacted_at", desc=True).limit(1).execute()

        if existing.data:
            retry_count = existing.data[0]["retry_count"] + 1

        if retry_count < 3:
            next_retry = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()

    sb.table("outreach_log").insert({
        "contact_id": lead["contact_id"],
        "company_id": lead["company_id"],
        "owner_id": user_id,
        "channel": "cold_call",
        "outcome": outcome,
        "notes": notes,
        "retry_count": retry_count,
        "next_retry_at": next_retry,
    }).execute()

    if outcome == "not_interested":
        sb.table("companies").update({"status": "dead"}).eq("id", lead["company_id"]).execute()
    elif outcome == "meeting_booked":
        sb.table("companies").update({"status": "active"}).eq("id", lead["company_id"]).execute()


def _leads_to_csv(leads: list[dict]) -> str:
    """Convert leads to CSV string."""
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company", "Score", "Contact", "Title", "Email", "Phone",
        "Industry", "City", "Opener",
    ])
    for lead in leads:
        writer.writerow([
            lead.get("company_name", ""),
            lead.get("growth_score", ""),
            lead.get("contact_name", ""),
            lead.get("contact_title", ""),
            lead.get("email", ""),
            lead.get("phone", ""),
            lead.get("industry", ""),
            lead.get("company_city", ""),
            lead.get("opener", ""),
        ])
    return output.getvalue()
