"""Pipeline overview page — companies by status, funnel, growth score distribution."""

import streamlit as st
from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import metric_row, pipeline_funnel


def render():
    st.title("Pipeline Overview")

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

    # Top metrics
    metric_row([
        {"label": "Total Companies", "value": total},
        {"label": "Active Pipeline", "value": active_pipeline},
        {"label": "Qualified", "value": pipeline_counts.get("qualified", 0)},
        {"label": "Meetings (Active)", "value": pipeline_counts.get("active", 0)},
    ])

    st.markdown("---")

    # Two columns: funnel + recent activity
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Pipeline Funnel")
        pipeline_funnel(pipeline_counts)

    with col2:
        st.subheader("Recently Discovered")
        recent = sb.table("companies").select(
            "name, growth_score, city, status, industry, discovered_at"
        ).eq("owner_id", user_id).order(
            "discovered_at", desc=True
        ).limit(10).execute()

        if recent.data:
            for company in recent.data:
                score = company["growth_score"]
                score_color = "#22c55e" if score >= 50 else ("#f59e0b" if score >= 30 else "#94a3b8")
                st.markdown(
                    f'<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;">'
                    f'<strong>{company["name"]}</strong> '
                    f'<span style="background:{score_color};color:#fff;padding:1px 6px;'
                    f'border-radius:8px;font-size:11px;font-weight:700;">{score}</span><br>'
                    f'<span style="color:#888;font-size:13px;">'
                    f'{company.get("industry", "Tech")} | {company.get("city", "AU")} | {company["status"]}'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No companies yet. Run `python main.py discover` to get started.")

    st.markdown("---")

    # Growth score distribution
    st.subheader("Growth Score Distribution")
    all_companies = sb.table("companies").select(
        "growth_score"
    ).eq("owner_id", user_id).in_(
        "status", ["researching", "qualified", "active"]
    ).execute()

    if all_companies.data:
        scores = [c["growth_score"] for c in all_companies.data]
        # Simple histogram using columns
        bins = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in scores:
            if s <= 20:
                bins["0-20"] += 1
            elif s <= 40:
                bins["21-40"] += 1
            elif s <= 60:
                bins["41-60"] += 1
            elif s <= 80:
                bins["61-80"] += 1
            else:
                bins["81-100"] += 1

        cols = st.columns(5)
        for col, (label, count) in zip(cols, bins.items()):
            col.metric(label, count)
    else:
        st.info("No scored companies in pipeline yet.")
