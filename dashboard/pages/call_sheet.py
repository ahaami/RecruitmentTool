"""Call Sheet page — today's leads with openers + log outcomes directly."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from dashboard.components.auth import get_supabase, get_user_id


def render():
    st.title("Today's Call Sheet")

    sb = get_supabase()
    user_id = get_user_id()

    # Get today's callsheet from database
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    callsheet = sb.table("daily_callsheets").select(
        "id, total_leads, callsheet_json, email_sent, generated_at"
    ).eq("owner_id", user_id).gte(
        "generated_at", today_start
    ).order("generated_at", desc=True).limit(1).execute()

    if not callsheet.data:
        st.warning("No call sheet generated today.")
        st.markdown("Run `python main.py callsheet --with-openers` to generate today's list.")

        # Show most recent callsheet instead
        latest = sb.table("daily_callsheets").select(
            "id, total_leads, callsheet_json, email_sent, generated_at"
        ).eq("owner_id", user_id).order(
            "generated_at", desc=True
        ).limit(1).execute()

        if latest.data:
            st.info(f"Showing most recent call sheet from {latest.data[0]['generated_at'][:10]}")
            callsheet = latest
        else:
            return

    sheet = callsheet.data[0]
    leads = []
    if sheet.get("callsheet_json"):
        import json
        if isinstance(sheet["callsheet_json"], str):
            leads = json.loads(sheet["callsheet_json"])
        else:
            leads = sheet["callsheet_json"]

    # Top metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Leads Today", sheet.get("total_leads", len(leads)))
    col2.metric("Email Sent", "Yes" if sheet.get("email_sent") else "No")
    col3.metric("Generated", sheet["generated_at"][:16].replace("T", " "))

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
        st.subheader(f"Retries Due ({len(retries.data)})")
        for retry in retries.data:
            contact = retry.get("contacts", {})
            company = retry.get("companies", {})
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
            st.markdown(
                f"**{name}** at {company.get('name', 'Unknown')} "
                f"| Attempt #{retry['retry_count'] + 1} "
                f"| Phone: {contact.get('phone', 'N/A')}"
            )
        st.markdown("---")

    # Display leads
    if not leads:
        st.info("No leads in this call sheet.")
        return

    for i, lead in enumerate(leads):
        score = lead.get("growth_score", 0)
        score_color = "#22c55e" if score >= 50 else ("#f59e0b" if score >= 30 else "#94a3b8")

        with st.expander(
            f"#{i+1} {lead.get('company_name', 'Unknown')} (Score: {score})",
            expanded=(i < 3),
        ):
            col_info, col_action = st.columns([3, 1])

            with col_info:
                st.markdown(
                    f"**{lead.get('industry', 'Tech')}** | "
                    f"{lead.get('company_city', 'AU')}"
                    f"{' | ~' + str(lead['headcount']) + ' employees' if lead.get('headcount') else ''}"
                )

                if lead.get("contact_name"):
                    st.markdown(
                        f"**Contact:** {lead['contact_name']} -- {lead.get('contact_title', '')}"
                    )
                    if lead.get("email"):
                        st.markdown(f"Email: {lead['email']}")
                    if lead.get("phone"):
                        st.markdown(f"Phone: {lead['phone']}")
                else:
                    st.markdown("**No contact yet** -- Find DM via LinkedIn search below")

                if lead.get("signals"):
                    st.markdown(f"*Signals: {lead['signals']}*")

                if lead.get("opener"):
                    st.info(f'"{lead["opener"]}"')

                # Links
                links = []
                if lead.get("company_linkedin"):
                    links.append(f"[Company LinkedIn]({lead['company_linkedin']})")
                if lead.get("company_website"):
                    links.append(f"[Website]({lead['company_website']})")
                if lead.get("linkedin_search"):
                    links.append(f"[Find DMs]({lead['linkedin_search']})")
                if links:
                    st.markdown(" | ".join(links))

            with col_action:
                # Log outcome form
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
                    notes = st.text_input("Notes", key=f"notes_{i}", label_visibility="collapsed", placeholder="Notes...")

                    if st.button("Log", key=f"log_{i}", use_container_width=True):
                        if outcome:
                            _log_outcome(sb, user_id, lead, outcome, notes)
                            st.success(f"Logged: {outcome}")
                        else:
                            st.warning("Select an outcome first")


def _log_outcome(sb, user_id: str, lead: dict, outcome: str, notes: str):
    """Log a call outcome from the dashboard."""
    from datetime import timedelta

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

    # Update company status for terminal outcomes
    if outcome == "not_interested":
        sb.table("companies").update({"status": "dead"}).eq("id", lead["company_id"]).execute()
    elif outcome == "meeting_booked":
        sb.table("companies").update({"status": "active"}).eq("id", lead["company_id"]).execute()
