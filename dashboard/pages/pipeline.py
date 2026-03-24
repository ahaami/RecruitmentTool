"""Pipeline overview page — funnel, score distribution, recent activity."""

import streamlit as st
from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import (
    page_header, section_header, metric_row, big_number,
    pipeline_funnel, score_distribution_chart, status_badge, score_badge,
)


def render():
    page_header("Pipeline Overview", "Track your companies from discovery to placement")

    sb = get_supabase()
    user_id = get_user_id()

    # Get pipeline counts by status
    statuses = ["new", "researching", "qualified", "active", "paused", "dead"]
    pipeline_counts = {}
    for status in statuses:
        result = sb.table("companies").select(
            "id", count="exact"
        ).eq("owner_id", user_id).eq("status", status).execute()
        pipeline_counts[status] = result.count or 0

    total = sum(pipeline_counts.values())
    active_pipeline = sum(pipeline_counts.get(s, 0) for s in ["researching", "qualified", "active"])

    # Contact count
    contacts = sb.table("contacts").select(
        "id", count="exact"
    ).eq("owner_id", user_id).execute()
    contact_count = contacts.count or 0

    # Top metrics
    metric_row([
        {"label": "Total Companies", "value": total},
        {"label": "Active Pipeline", "value": active_pipeline},
        {"label": "Qualified Leads", "value": pipeline_counts.get("qualified", 0)},
        {"label": "Meetings Active", "value": pipeline_counts.get("active", 0)},
        {"label": "Total Contacts", "value": contact_count},
    ])

    st.markdown("---")

    # Two columns: funnel + score distribution
    col1, col2 = st.columns(2)

    with col1:
        section_header("Pipeline Funnel", "&#x1F4CA;")
        pipeline_funnel(pipeline_counts)

    with col2:
        section_header("Growth Score Distribution", "&#x1F4C8;")
        all_companies = sb.table("companies").select(
            "growth_score"
        ).eq("owner_id", user_id).in_(
            "status", ["researching", "qualified", "active"]
        ).execute()

        if all_companies.data:
            scores = [c["growth_score"] for c in all_companies.data]
            score_distribution_chart(scores)
        else:
            st.info("No scored companies in pipeline yet.")

    st.markdown("---")

    # Recently discovered companies
    section_header("Recently Discovered", "&#x1F195;")

    recent = sb.table("companies").select(
        "id, name, growth_score, city, status, industry, headcount_est, discovered_at"
    ).eq("owner_id", user_id).order(
        "discovered_at", desc=True
    ).limit(10).execute()

    if recent.data:
        for company in recent.data:
            score = company["growth_score"]
            status = company["status"]
            industry = company.get("industry", "Tech")
            city = company.get("city", "AU")
            headcount = company.get("headcount_est")
            headcount_str = f"~{headcount} employees" if headcount else ""
            date_str = company.get("discovered_at", "")[:10]

            st.markdown(
                f'<div class="lunar-card">'
                f'<div class="lunar-card-header">'
                f'<div>'
                f'<span class="lunar-card-title">{company["name"]}</span> '
                f'{score_badge(score)} {status_badge(status)}'
                f'</div>'
                f'<span style="font-size:12px;color:#94a3b8;">{date_str}</span>'
                f'</div>'
                f'<div style="font-size:13px;color:#64748b;">'
                f'{industry} &middot; {city}'
                f'{" &middot; " + headcount_str if headcount_str else ""}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No companies yet. Run `python main.py discover` to get started.")
