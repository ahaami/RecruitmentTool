"""Analytics page — interactive charts, conversion rates, activity trends."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import (
    page_header, section_header, metric_row, big_number,
    donut_chart, horizontal_bar, OUTCOME_COLORS,
)


def render():
    page_header("Analytics", "Track your outreach performance")

    sb = get_supabase()
    user_id = get_user_id()

    # Time range selector
    col_range, _ = st.columns([1, 3])
    with col_range:
        time_range = st.selectbox(
            "Time range",
            ["Last 7 days", "Last 14 days", "Last 30 days", "All time"],
        )

    days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "All time": 365}
    days = days_map[time_range]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    st.markdown("---")

    # --- Activity metrics ---
    section_header("Activity Overview", "&#x1F4CA;")

    calls = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq(
        "channel", "cold_call"
    ).gte("contacted_at", since).execute()

    linkedin = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).in_(
        "channel", ["linkedin_connect", "linkedin_message"]
    ).gte("contacted_at", since).execute()

    meetings = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq(
        "outcome", "meeting_booked"
    ).gte("contacted_at", since).execute()

    spoke_dm = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq(
        "outcome", "spoke_dm"
    ).gte("contacted_at", since).execute()

    total_outreach = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).gte("contacted_at", since).execute()

    calls_count = calls.count or 0
    linkedin_count = linkedin.count or 0
    meetings_count = meetings.count or 0
    spoke_dm_count = spoke_dm.count or 0
    total_count = total_outreach.count or 0

    metric_row([
        {"label": "Calls Made", "value": calls_count},
        {"label": "LinkedIn Sent", "value": linkedin_count},
        {"label": "Spoke to DM", "value": spoke_dm_count},
        {"label": "Meetings Booked", "value": meetings_count},
    ])

    st.markdown("---")

    # --- Two-column layout: Conversion rates + Donut chart ---
    col1, col2 = st.columns(2)

    with col1:
        section_header("Conversion Rates", "&#x1F4C8;")

        # Call -> Spoke DM
        if calls_count > 0:
            dm_rate = round((spoke_dm_count / calls_count) * 100, 1)
            big_number("Call to DM Conversation", f"{dm_rate}%",
                       f"{spoke_dm_count} of {calls_count} calls", "#3b82f6")
        else:
            big_number("Call to DM Conversation", "N/A", "No calls yet", "#94a3b8")

        # DM -> Meeting
        if spoke_dm_count > 0:
            meeting_rate = round((meetings_count / spoke_dm_count) * 100, 1)
            big_number("DM to Meeting", f"{meeting_rate}%",
                       f"{meetings_count} of {spoke_dm_count} DM conversations", "#22c55e")
        else:
            big_number("DM to Meeting", "N/A", "No DM conversations yet", "#94a3b8")

        # Overall
        if total_count > 0:
            overall_rate = round((meetings_count / total_count) * 100, 1)
            big_number("Overall Conversion", f"{overall_rate}%",
                       f"{meetings_count} meetings from {total_count} touches", "#6366f1")
        else:
            big_number("Overall Conversion", "N/A", "No outreach yet", "#94a3b8")

    with col2:
        section_header("Outcome Breakdown", "&#x1F4CA;")

        outcomes = sb.table("outreach_log").select(
            "outcome"
        ).eq("owner_id", user_id).gte("contacted_at", since).execute()

        if outcomes.data:
            outcome_counts = {}
            for entry in outcomes.data:
                o = entry.get("outcome", "unknown")
                outcome_counts[o] = outcome_counts.get(o, 0) + 1

            sorted_outcomes = sorted(outcome_counts.items(), key=lambda x: x[1], reverse=True)
            labels = [o[0] for o in sorted_outcomes]
            values = [o[1] for o in sorted_outcomes]
            colors = [OUTCOME_COLORS.get(l, "#94a3b8") for l in labels]

            donut_chart(labels, values, colors)
        else:
            st.info("No outreach data yet. Start making calls to see analytics!")

    st.markdown("---")

    # --- Discovery stats ---
    section_header("Discovery Stats", "&#x1F50D;")

    new_companies = sb.table("companies").select(
        "id", count="exact"
    ).eq("owner_id", user_id).gte("discovered_at", since).execute()

    new_contacts = sb.table("contacts").select(
        "id", count="exact"
    ).eq("owner_id", user_id).gte("created_at", since).execute()

    new_signals = sb.table("growth_signals").select(
        "id", count="exact"
    ).gte("created_at", since).execute()

    metric_row([
        {"label": "Companies Discovered", "value": new_companies.count or 0},
        {"label": "Contacts Added", "value": new_contacts.count or 0},
        {"label": "Growth Signals", "value": new_signals.count or 0},
    ])

    # --- Contact source breakdown ---
    st.markdown("---")
    section_header("Contact Sources", "&#x1F465;")

    all_contacts = sb.table("contacts").select(
        "source"
    ).eq("owner_id", user_id).execute()

    if all_contacts.data:
        source_counts = {}
        for c in all_contacts.data:
            src = c.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        source_colors = {
            "apollo": "#6366f1",
            "lusha": "#22c55e",
            "linkedin": "#3b82f6",
            "manual": "#f59e0b",
        }

        horizontal_bar(
            [s[0] for s in sorted_sources],
            [s[1] for s in sorted_sources],
            [source_colors.get(s[0], "#94a3b8") for s in sorted_sources],
            height=max(len(sorted_sources) * 50, 120),
        )
