"""Contacts page — contact details, outreach history timeline."""

import streamlit as st
from dashboard.components.auth import get_supabase, get_user_id


def render():
    st.title("Contacts")

    sb = get_supabase()
    user_id = get_user_id()

    # Filters
    col_search, col_dm = st.columns([3, 1])

    with col_search:
        search = st.text_input("Search contacts", placeholder="Name, title, or company...")

    with col_dm:
        dm_only = st.checkbox("Decision makers only", value=False)

    # Build query
    query = sb.table("contacts").select(
        "id, first_name, last_name, title, email, phone, linkedin_url, "
        "is_decision_maker, confidence, source, created_at, "
        "companies(id, name, growth_score, status, city)"
    ).eq("owner_id", user_id)

    if dm_only:
        query = query.eq("is_decision_maker", True)

    contacts = query.order("created_at", desc=True).limit(50).execute()

    # Filter by search term client-side (Supabase doesn't support OR ilike across joins easily)
    if search and contacts.data:
        search_lower = search.lower()
        contacts.data = [
            c for c in contacts.data
            if search_lower in f"{c['first_name']} {c['last_name']}".lower()
            or search_lower in (c.get("title") or "").lower()
            or search_lower in (c.get("companies", {}).get("name", "")).lower()
        ]

    st.markdown(f"**{len(contacts.data or [])} contacts** shown")
    st.markdown("---")

    if not contacts.data:
        st.info("No contacts found. Run `python main.py enrich` to find decision-makers.")
        return

    for contact in contacts.data:
        company = contact.get("companies", {}) or {}
        dm_badge = " [Decision Maker]" if contact.get("is_decision_maker") else ""
        name = f"{contact['first_name']} {contact['last_name']}"

        with st.expander(
            f"{name} -- {contact.get('title', 'N/A')} at {company.get('name', 'Unknown')}{dm_badge}",
            expanded=False,
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Title:** {contact.get('title', 'N/A')}")
                st.markdown(f"**Company:** {company.get('name', 'Unknown')} (Score: {company.get('growth_score', 0)})")
                st.markdown(f"**Location:** {company.get('city', 'N/A')}")

                if contact.get("email"):
                    st.markdown(f"**Email:** {contact['email']}")
                if contact.get("phone"):
                    st.markdown(f"**Phone:** {contact['phone']}")
                if contact.get("linkedin_url"):
                    st.markdown(f"[LinkedIn Profile]({contact['linkedin_url']})")

                st.caption(f"Source: {contact.get('source', 'N/A')} | Confidence: {contact.get('confidence', 0)}%")

            with col2:
                st.markdown("**Quick Actions**")
                # Log a call outcome
                outcome = st.selectbox(
                    "Log outcome",
                    ["", "no_answer", "voicemail", "spoke_gatekeeper",
                     "spoke_dm", "meeting_booked", "not_interested"],
                    key=f"outcome_{contact['id']}",
                    label_visibility="collapsed",
                )
                if outcome:
                    if st.button("Log Call", key=f"log_{contact['id']}"):
                        from datetime import datetime, timedelta, timezone
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
                            "company_id": company["id"],
                            "owner_id": user_id,
                            "channel": "cold_call",
                            "outcome": outcome,
                            "retry_count": retry_count,
                            "next_retry_at": next_retry,
                        }).execute()
                        st.success(f"Logged: {outcome}")

            # Outreach history
            history = sb.table("outreach_log").select(
                "channel, outcome, notes, contacted_at, retry_count"
            ).eq("contact_id", contact["id"]).order(
                "contacted_at", desc=True
            ).limit(10).execute()

            if history.data:
                st.markdown("**Outreach History:**")
                for entry in history.data:
                    date = entry["contacted_at"][:10]
                    channel = entry.get("channel", "unknown")
                    outcome_text = entry.get("outcome", "N/A")
                    notes = entry.get("notes", "")
                    retry = f" (retry #{entry['retry_count']})" if entry.get("retry_count") else ""

                    st.markdown(
                        f"- **{date}** | {channel} | {outcome_text}{retry}"
                        f"{' | ' + notes if notes else ''}"
                    )
            else:
                st.caption("No outreach history yet.")
