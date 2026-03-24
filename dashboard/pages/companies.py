"""Companies page — browse, search, filter, exclude companies."""

import streamlit as st
from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import metric_row


def render():
    st.title("Companies")

    sb = get_supabase()
    user_id = get_user_id()

    # Filters
    col_search, col_status, col_sort = st.columns([2, 1, 1])

    with col_search:
        search = st.text_input("Search companies", placeholder="Company name...")

    with col_status:
        status_filter = st.selectbox(
            "Status",
            ["All", "new", "researching", "qualified", "active", "paused", "dead"],
        )

    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Growth Score", "Name", "Recently Added"],
        )

    # Build query
    query = sb.table("companies").select(
        "id, name, domain, city, state, industry, headcount_est, "
        "growth_score, status, linkedin_url, website, notes, discovered_at"
    ).eq("owner_id", user_id)

    if status_filter != "All":
        query = query.eq("status", status_filter)

    if search:
        query = query.ilike("name", f"%{search}%")

    if sort_by == "Growth Score":
        query = query.order("growth_score", desc=True)
    elif sort_by == "Name":
        query = query.order("name")
    else:
        query = query.order("discovered_at", desc=True)

    companies = query.limit(50).execute()

    st.markdown(f"**{len(companies.data or [])} companies** shown")
    st.markdown("---")

    if not companies.data:
        st.info("No companies found matching your filters.")
        return

    for company in companies.data:
        score = company["growth_score"]
        score_color = "#22c55e" if score >= 50 else ("#f59e0b" if score >= 30 else "#94a3b8")
        status = company["status"]
        status_colors = {
            "new": "#94a3b8", "researching": "#f59e0b", "qualified": "#3b82f6",
            "active": "#22c55e", "paused": "#a855f7", "dead": "#ef4444",
        }
        s_color = status_colors.get(status, "#666")

        with st.expander(
            f"{company['name']} | Score: {score} | {status}",
            expanded=False,
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(
                    f"**Industry:** {company.get('industry', 'N/A')} | "
                    f"**Location:** {company.get('city', 'AU')}, {company.get('state', '')} | "
                    f"**Headcount:** {company.get('headcount_est', 'N/A')}"
                )

                if company.get("domain"):
                    st.markdown(f"**Domain:** {company['domain']}")

                links = []
                if company.get("linkedin_url"):
                    links.append(f"[LinkedIn]({company['linkedin_url']})")
                if company.get("website"):
                    links.append(f"[Website]({company['website']})")
                if links:
                    st.markdown(" | ".join(links))

                if company.get("notes"):
                    st.caption(f"Notes: {company['notes'][:200]}")

                # Show growth signals
                signals = sb.table("growth_signals").select(
                    "signal_type, headline, created_at"
                ).eq("company_id", company["id"]).order(
                    "created_at", desc=True
                ).limit(5).execute()

                if signals.data:
                    st.markdown("**Recent Signals:**")
                    for sig in signals.data:
                        st.markdown(f"- {sig['signal_type']}: {sig['headline'][:80]}")

                # Show contacts
                contacts = sb.table("contacts").select(
                    "first_name, last_name, title, email, phone, is_decision_maker"
                ).eq("company_id", company["id"]).execute()

                if contacts.data:
                    st.markdown(f"**Contacts ({len(contacts.data)}):**")
                    for contact in contacts.data:
                        dm_tag = " [DM]" if contact.get("is_decision_maker") else ""
                        st.markdown(
                            f"- {contact['first_name']} {contact['last_name']}"
                            f" -- {contact.get('title', 'N/A')}{dm_tag}"
                            f" | {contact.get('email', 'no email')}"
                        )

            with col2:
                # Status change
                new_status = st.selectbox(
                    "Change status",
                    ["", "new", "researching", "qualified", "active", "paused", "dead"],
                    key=f"status_{company['id']}",
                )
                if new_status and new_status != company["status"]:
                    if st.button("Update", key=f"update_{company['id']}"):
                        sb.table("companies").update({
                            "status": new_status
                        }).eq("id", company["id"]).execute()
                        st.success(f"Updated to {new_status}")
                        st.rerun()

                # Exclude button
                if st.button("Exclude", key=f"exclude_{company['id']}"):
                    sb.table("excluded_companies").upsert({
                        "owner_id": user_id,
                        "company_name": company["name"],
                        "domain": company.get("domain"),
                        "reason": "Excluded from dashboard",
                    }).execute()
                    sb.table("companies").update({
                        "status": "dead"
                    }).eq("id", company["id"]).execute()
                    st.success(f"Excluded {company['name']}")
                    st.rerun()
