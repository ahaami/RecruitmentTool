"""LinkedIn warm-up page — manage connection requests and follow-up messages."""

import streamlit as st
from datetime import datetime, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import page_header, section_header, metric_row


def render():
    page_header("LinkedIn Warm-Up", "Manage your connection requests and follow-up messages")

    sb = get_supabase()
    user_id = get_user_id()

    # --- Top metrics ---
    pending = sb.table("warmup_queue").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq("status", "pending").execute()

    sent = sb.table("warmup_queue").select(
        "id", count="exact"
    ).eq("owner_id", user_id).eq("status", "sent").execute()

    total = sb.table("warmup_queue").select(
        "id", count="exact"
    ).eq("owner_id", user_id).execute()

    metric_row([
        {"label": "Pending", "value": pending.count or 0},
        {"label": "Sent", "value": sent.count or 0},
        {"label": "Total Queued", "value": total.count or 0},
    ])

    st.markdown("---")

    # --- Tabs ---
    tab_pending, tab_sent, tab_all = st.tabs(["Pending", "Sent", "All"])

    with tab_pending:
        _render_queue(sb, user_id, "pending")

    with tab_sent:
        _render_queue(sb, user_id, "sent")

    with tab_all:
        _render_queue(sb, user_id, None)


def _render_queue(sb, user_id: str, status_filter: str | None):
    """Render warm-up queue items."""
    query = sb.table("warmup_queue").select(
        "id, contact_id, message_type, message, status, created_at, sent_at, "
        "contacts(first_name, last_name, title, linkedin_url, "
        "companies(name, growth_score))"
    ).eq("owner_id", user_id)

    if status_filter:
        query = query.eq("status", status_filter)

    items = query.order("created_at", desc=True).limit(50).execute()

    if not items.data:
        st.info("No messages in this queue.")
        return

    for item in items.data:
        contact = item.get("contacts", {}) or {}
        company = contact.get("companies", {}) or {}
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
        comp_name = company.get("name", "Unknown")
        msg_type = item.get("message_type", "connect")
        is_pending = item.get("status") == "pending"

        type_label = "Connection Request" if msg_type == "connect" else "Follow-up Message"
        type_color = "#6366f1" if msg_type == "connect" else "#22c55e"

        with st.expander(
            f"{name} at {comp_name}  |  {type_label}  |  {item['status'].upper()}",
            expanded=is_pending,
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                # Type badge
                st.markdown(
                    f'<span style="background:{type_color};color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:11px;font-weight:600;">'
                    f'{type_label}</span>',
                    unsafe_allow_html=True,
                )

                st.markdown(f"**{name}** — {contact.get('title', 'N/A')} at **{comp_name}**")

                if contact.get("linkedin_url"):
                    st.markdown(f"[Open LinkedIn Profile]({contact['linkedin_url']})")

                # The message (copyable)
                st.markdown("**Message:**")
                message = item.get("message", "")
                st.code(message, language=None)

                char_count = len(message)
                if msg_type == "connect":
                    limit = 300
                    color = "#22c55e" if char_count <= limit else "#ef4444"
                    st.markdown(
                        f'<span style="font-size:12px;color:{color};">'
                        f'{char_count}/{limit} characters</span>',
                        unsafe_allow_html=True,
                    )

                st.caption(f"Created: {item['created_at'][:10]}")
                if item.get("sent_at"):
                    st.caption(f"Sent: {item['sent_at'][:10]}")

            with col2:
                if is_pending:
                    if st.button(
                        "Mark as Sent",
                        key=f"sent_{item['id']}",
                        use_container_width=True,
                    ):
                        sb.table("warmup_queue").update({
                            "status": "sent",
                            "sent_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", item["id"]).execute()

                        # Also log in outreach_log
                        channel = "linkedin_connect" if msg_type == "connect" else "linkedin_message"
                        sb.table("outreach_log").insert({
                            "contact_id": item["contact_id"],
                            "company_id": company.get("id") if isinstance(company, dict) else None,
                            "owner_id": user_id,
                            "channel": channel,
                            "outcome": "sent",
                            "notes": f"LinkedIn {msg_type}: {message[:100]}",
                        }).execute()

                        st.success("Marked as sent!")
                        st.rerun()

                    if st.button(
                        "Skip",
                        key=f"skip_{item['id']}",
                        use_container_width=True,
                    ):
                        sb.table("warmup_queue").update({
                            "status": "skipped",
                        }).eq("id", item["id"]).execute()
                        st.rerun()
