"""Analytics page — weekly stats, conversion rates, activity trends."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import metric_row


def render():
    st.title("Analytics")

    sb = get_supabase()
    user_id = get_user_id()

    # Time range selector
    time_range = st.selectbox(
        "Time range",
        ["Last 7 days", "Last 14 days", "Last 30 days", "All time"],
    )

    days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "All time": 365}
    days = days_map[time_range]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    st.markdown("---")

    # --- Activity metrics ---
    st.subheader("Activity")

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

    not_interested = sb.table("outreach_log").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq(
        "outcome", "not_interested"
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

    # --- Conversion rates ---
    st.subheader("Conversion Rates")

    col1, col2, col3 = st.columns(3)

    with col1:
        if calls_count > 0:
            dm_rate = round((spoke_dm_count / calls_count) * 100, 1)
            st.metric("Call -> Spoke DM", f"{dm_rate}%")
        else:
            st.metric("Call -> Spoke DM", "N/A")

    with col2:
        if spoke_dm_count > 0:
            meeting_rate = round((meetings_count / spoke_dm_count) * 100, 1)
            st.metric("DM -> Meeting", f"{meeting_rate}%")
        else:
            st.metric("DM -> Meeting", "N/A")

    with col3:
        if total_count > 0:
            overall_rate = round((meetings_count / total_count) * 100, 1)
            st.metric("Overall Conversion", f"{overall_rate}%")
        else:
            st.metric("Overall Conversion", "N/A")

    st.markdown("---")

    # --- Outcome breakdown ---
    st.subheader("Outcome Breakdown")

    outcomes = sb.table("outreach_log").select(
        "outcome"
    ).eq("owner_id", user_id).gte("contacted_at", since).execute()

    if outcomes.data:
        outcome_counts = {}
        for entry in outcomes.data:
            o = entry.get("outcome", "unknown")
            outcome_counts[o] = outcome_counts.get(o, 0) + 1

        # Sort by count descending
        sorted_outcomes = sorted(outcome_counts.items(), key=lambda x: x[1], reverse=True)

        for outcome_name, count in sorted_outcomes:
            pct = round((count / total_count) * 100, 1) if total_count > 0 else 0
            bar_width = min(pct * 3, 100)
            color = _outcome_color(outcome_name)
            st.markdown(
                f'<div style="margin:4px 0;">'
                f'<span style="display:inline-block;width:160px;font-size:13px;">{outcome_name}</span>'
                f'<span style="display:inline-block;background:{color};color:#fff;'
                f'padding:2px 8px;border-radius:4px;min-width:{max(bar_width, 30)}px;'
                f'font-size:12px;font-weight:600;text-align:center;">{count} ({pct}%)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No outreach data yet. Start making calls to see analytics!")

    st.markdown("---")

    # --- Pipeline discovery stats ---
    st.subheader("Discovery Stats")

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


def _outcome_color(outcome: str) -> str:
    """Return a color for each outcome type."""
    colors = {
        "meeting_booked": "#22c55e",
        "spoke_dm": "#3b82f6",
        "spoke_gatekeeper": "#8b5cf6",
        "callback_requested": "#06b6d4",
        "voicemail": "#f59e0b",
        "no_answer": "#94a3b8",
        "not_interested": "#ef4444",
    }
    return colors.get(outcome, "#666")
