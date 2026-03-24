"""Companies page — browse, search, filter, bulk actions, CSV export."""

import csv
import io
import streamlit as st
from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import (
    page_header, metric_row, status_badge, score_badge,
)


def render():
    page_header("Companies", "Browse and manage your company pipeline")

    sb = get_supabase()
    user_id = get_user_id()

    # --- Filters ---
    col_search, col_status, col_city, col_sort = st.columns([2, 1, 1, 1])

    with col_search:
        search = st.text_input("Search", placeholder="Company name...", label_visibility="collapsed")

    with col_status:
        status_filter = st.selectbox(
            "Status",
            ["All", "new", "researching", "qualified", "active", "paused", "dead"],
        )

    with col_city:
        city_filter = st.selectbox(
            "City",
            ["All", "Sydney", "Melbourne", "Brisbane", "Perth", "Canberra"],
        )

    with col_sort:
        sort_by = st.selectbox(
            "Sort",
            ["Growth Score", "Name", "Recently Added"],
        )

    # Build query
    query = sb.table("companies").select(
        "id, name, domain, city, state, industry, headcount_est, "
        "growth_score, status, linkedin_url, website, notes, discovered_at"
    ).eq("owner_id", user_id)

    if status_filter != "All":
        query = query.eq("status", status_filter)
    if city_filter != "All":
        query = query.eq("city", city_filter)
    if search:
        query = query.ilike("name", f"%{search}%")

    if sort_by == "Growth Score":
        query = query.order("growth_score", desc=True)
    elif sort_by == "Name":
        query = query.order("name")
    else:
        query = query.order("discovered_at", desc=True)

    companies = query.limit(50).execute()
    company_list = companies.data or []

    # --- Results header with bulk actions ---
    col_count, col_export, col_bulk = st.columns([2, 1, 1])

    with col_count:
        st.markdown(f"**{len(company_list)} companies** shown")

    with col_export:
        if company_list:
            csv_data = _companies_to_csv(company_list)
            st.download_button(
                "Export CSV",
                csv_data,
                file_name="companies.csv",
                mime="text/csv",
            )

    with col_bulk:
        if company_list:
            bulk_action = st.selectbox(
                "Bulk action",
                ["", "Set Researching", "Set Qualified", "Set Paused", "Set Dead"],
                label_visibility="collapsed",
            )

    st.markdown("---")

    if not company_list:
        st.info("No companies found matching your filters.")
        return

    # --- Company cards ---
    for company in company_list:
        score = company["growth_score"]
        status = company["status"]
        industry = company.get("industry", "Tech")
        city = company.get("city", "AU")
        headcount = company.get("headcount_est")

        with st.expander(
            f"{company['name']}  |  Score: {score}  |  {status.upper()}",
            expanded=False,
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                # Header badges
                st.markdown(
                    f'{score_badge(score)} {status_badge(status)}',
                    unsafe_allow_html=True,
                )

                # Info grid
                info_parts = []
                if industry:
                    info_parts.append(f"**Industry:** {industry}")
                if city:
                    info_parts.append(f"**Location:** {city}, {company.get('state', '')}")
                if headcount:
                    info_parts.append(f"**Headcount:** ~{headcount}")
                if company.get("domain"):
                    info_parts.append(f"**Domain:** {company['domain']}")
                st.markdown(" | ".join(info_parts))

                # Links
                links = []
                if company.get("linkedin_url"):
                    links.append(f"[LinkedIn]({company['linkedin_url']})")
                if company.get("website"):
                    links.append(f"[Website]({company['website']})")
                if links:
                    st.markdown(" | ".join(links))

                if company.get("notes"):
                    st.caption(f"Notes: {company['notes'][:200]}")

                # Growth signals
                signals = sb.table("growth_signals").select(
                    "signal_type, headline, created_at"
                ).eq("company_id", company["id"]).order(
                    "created_at", desc=True
                ).limit(5).execute()

                if signals.data:
                    st.markdown("**Growth Signals:**")
                    for sig in signals.data:
                        sig_type = sig["signal_type"]
                        color = "#22c55e" if sig_type == "job_posting" else "#3b82f6"
                        st.markdown(
                            f'<span style="background:{color};color:#fff;padding:1px 6px;'
                            f'border-radius:4px;font-size:10px;font-weight:600;">'
                            f'{sig_type}</span> {sig["headline"][:80]}',
                            unsafe_allow_html=True,
                        )

                # Contacts
                contacts = sb.table("contacts").select(
                    "first_name, last_name, title, email, phone, is_decision_maker"
                ).eq("company_id", company["id"]).execute()

                if contacts.data:
                    st.markdown(f"**Contacts ({len(contacts.data)}):**")
                    for contact in contacts.data:
                        dm = " **[DM]**" if contact.get("is_decision_maker") else ""
                        email = contact.get("email", "")
                        phone = contact.get("phone", "")
                        contact_info = " | ".join(filter(None, [email, phone]))
                        st.markdown(
                            f"- {contact['first_name']} {contact['last_name']}"
                            f" — {contact.get('title', 'N/A')}{dm}"
                            f"{' | ' + contact_info if contact_info else ''}"
                        )

            # Show AI brief if generated
            brief_key = f"brief_{company['id']}"
            if brief_key in st.session_state:
                st.markdown(
                    f'<div style="background:#eef2ff;border-left:3px solid #6366f1;'
                    f'padding:14px 18px;border-radius:0 10px 10px 0;margin:12px 0;'
                    f'font-size:13px;line-height:1.6;">'
                    f'<strong style="color:#4338ca;">AI Research Brief</strong><br><br>'
                    f'{st.session_state[brief_key].replace(chr(10), "<br>")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with col2:
                # Status change
                new_status = st.selectbox(
                    "Change status",
                    ["", "new", "researching", "qualified", "active", "paused", "dead"],
                    key=f"status_{company['id']}",
                )
                if new_status and new_status != status:
                    if st.button("Update", key=f"update_{company['id']}", use_container_width=True):
                        sb.table("companies").update({
                            "status": new_status
                        }).eq("id", company["id"]).execute()
                        st.success(f"Updated to {new_status}")
                        st.rerun()

                st.markdown("")

                # AI Research Brief
                if st.button("AI Brief", key=f"brief_{company['id']}", use_container_width=True):
                    with st.spinner("Generating research brief..."):
                        try:
                            from pipeline.research import generate_company_brief
                            brief = generate_company_brief(company["id"])
                            if brief:
                                st.session_state[f"brief_{company['id']}"] = brief
                            else:
                                st.warning("Could not generate brief")
                        except Exception as e:
                            st.error(f"Error: {e}")

                # Exclude button
                if st.button("Exclude", key=f"exclude_{company['id']}", use_container_width=True):
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


def _companies_to_csv(companies: list[dict]) -> str:
    """Convert companies to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Score", "Status", "Industry", "City",
        "Headcount", "Domain", "Website",
    ])
    for c in companies:
        writer.writerow([
            c.get("name", ""), c.get("growth_score", ""),
            c.get("status", ""), c.get("industry", ""),
            c.get("city", ""), c.get("headcount_est", ""),
            c.get("domain", ""), c.get("website", ""),
        ])
    return output.getvalue()
