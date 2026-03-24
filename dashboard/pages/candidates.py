"""Candidates page — track candidates, match to roles, manage placements."""

import csv
import io
import streamlit as st
from datetime import datetime, timezone

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import page_header, section_header, metric_row


STAGE_COLORS = {
    "submitted": ("#f1f5f9", "#64748b"),
    "phone_screen": ("#fef3c7", "#92400e"),
    "interview": ("#dbeafe", "#1e40af"),
    "final_round": ("#e0e7ff", "#3730a3"),
    "offer": ("#fae8ff", "#86198f"),
    "accepted": ("#dcfce7", "#166534"),
    "started": ("#22c55e", "#fff"),
    "withdrawn": ("#fee2e2", "#991b1b"),
    "rejected": ("#fee2e2", "#991b1b"),
}


def render():
    page_header("Candidates & Placements", "Track candidates and manage placements")

    sb = get_supabase()
    user_id = get_user_id()

    tab_candidates, tab_placements, tab_add = st.tabs([
        "Candidates", "Placements", "Add Candidate",
    ])

    with tab_candidates:
        _render_candidates(sb, user_id)

    with tab_placements:
        _render_placements(sb, user_id)

    with tab_add:
        _render_add_candidate(sb, user_id)


def _render_candidates(sb, user_id: str):
    """Render the candidates list."""
    # Filters
    col_search, col_status = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Search candidates", placeholder="Name, skills, or company...",
            key="cand_search", label_visibility="collapsed",
        )
    with col_status:
        status = st.selectbox(
            "Status", ["All", "active", "placed", "unavailable", "archived"],
            key="cand_status",
        )

    query = sb.table("candidates").select("*").eq("owner_id", user_id)
    if status != "All":
        query = query.eq("status", status)

    candidates = query.order("created_at", desc=True).limit(50).execute()
    cand_list = candidates.data or []

    # Client-side search
    if search and cand_list:
        sl = search.lower()
        cand_list = [
            c for c in cand_list
            if sl in f"{c['first_name']} {c['last_name']}".lower()
            or sl in (c.get("current_title") or "").lower()
            or sl in (c.get("current_company") or "").lower()
            or any(sl in (s or "").lower() for s in (c.get("skills") or []))
        ]

    # Metrics
    total = len(cand_list)
    active = sum(1 for c in cand_list if c.get("status") == "active")
    placed = sum(1 for c in cand_list if c.get("status") == "placed")

    metric_row([
        {"label": "Total Candidates", "value": total},
        {"label": "Active", "value": active},
        {"label": "Placed", "value": placed},
    ])

    # Export
    if cand_list:
        csv_data = _candidates_to_csv(cand_list)
        st.download_button("Export CSV", csv_data, "candidates.csv", "text/csv")

    st.markdown("---")

    if not cand_list:
        st.info("No candidates yet. Use the 'Add Candidate' tab to add your first candidate.")
        return

    for cand in cand_list:
        name = f"{cand['first_name']} {cand['last_name']}"
        title = cand.get("current_title", "N/A")
        company = cand.get("current_company", "")
        status_val = cand.get("status", "active")

        status_bg, status_fg = STAGE_COLORS.get(status_val, ("#f1f5f9", "#64748b"))

        with st.expander(f"{name}  |  {title}  |  {status_val.upper()}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(
                    f'<span style="background:{status_bg};color:{status_fg};'
                    f'padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">'
                    f'{status_val.upper()}</span>',
                    unsafe_allow_html=True,
                )

                st.markdown(f"**{title}** at {company}" if company else f"**{title}**")

                if cand.get("location"):
                    st.markdown(f"Location: {cand['location']}")
                if cand.get("experience_years"):
                    st.markdown(f"Experience: {cand['experience_years']} years")

                # Skills
                skills = cand.get("skills") or []
                if skills:
                    skill_html = " ".join(
                        f'<span style="background:#eef2ff;color:#4338ca;padding:2px 8px;'
                        f'border-radius:4px;font-size:11px;font-weight:600;'
                        f'margin-right:4px;">{s}</span>'
                        for s in skills
                    )
                    st.markdown(skill_html, unsafe_allow_html=True)

                # Salary range
                if cand.get("salary_min") or cand.get("salary_max"):
                    sal_min = f"${cand['salary_min']:,}" if cand.get("salary_min") else "?"
                    sal_max = f"${cand['salary_max']:,}" if cand.get("salary_max") else "?"
                    st.markdown(f"Salary range: {sal_min} - {sal_max}")

                if cand.get("availability"):
                    st.markdown(f"Availability: {cand['availability']}")

                # Contact info
                contact_parts = []
                if cand.get("email"):
                    contact_parts.append(f"Email: {cand['email']}")
                if cand.get("phone"):
                    contact_parts.append(f"Phone: `{cand['phone']}`")
                if cand.get("linkedin_url"):
                    contact_parts.append(f"[LinkedIn]({cand['linkedin_url']})")
                if contact_parts:
                    st.markdown(" | ".join(contact_parts))

                if cand.get("notes"):
                    st.caption(f"Notes: {cand['notes'][:200]}")

            with col2:
                new_status = st.selectbox(
                    "Status",
                    ["", "active", "placed", "unavailable", "archived"],
                    key=f"cstatus_{cand['id']}",
                )
                if new_status and new_status != status_val:
                    if st.button("Update", key=f"cupdate_{cand['id']}", use_container_width=True):
                        sb.table("candidates").update({
                            "status": new_status,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", cand["id"]).execute()
                        st.success(f"Updated to {new_status}")
                        st.rerun()

                st.markdown("")

                # Quick placement button
                if st.button("Create Placement", key=f"place_{cand['id']}", use_container_width=True):
                    st.session_state["placement_candidate_id"] = cand["id"]
                    st.session_state["placement_candidate_name"] = name
                    st.info("Go to 'Placements' tab to complete")


def _render_placements(sb, user_id: str):
    """Render placements tracker."""
    placements = sb.table("placements").select(
        "*, candidates(first_name, last_name), companies(name)"
    ).eq("owner_id", user_id).order("created_at", desc=True).limit(50).execute()

    placement_list = placements.data or []

    if not placement_list:
        st.info("No placements yet. Submit candidates to companies to start tracking.")

        # Quick placement form
        if st.session_state.get("placement_candidate_id"):
            _render_placement_form(sb, user_id)
        return

    # Metrics
    total = len(placement_list)
    active_stages = {"submitted", "phone_screen", "interview", "final_round", "offer"}
    active = sum(1 for p in placement_list if p.get("stage") in active_stages)
    accepted = sum(1 for p in placement_list if p.get("stage") in ("accepted", "started"))

    total_fees = sum(
        float(p.get("fee_amount") or 0)
        for p in placement_list
        if p.get("stage") in ("accepted", "started")
    )

    metric_row([
        {"label": "Total Placements", "value": total},
        {"label": "In Progress", "value": active},
        {"label": "Accepted/Started", "value": accepted},
        {"label": "Total Fees", "value": f"${total_fees:,.0f}"},
    ])

    st.markdown("---")

    # Placement form
    if st.session_state.get("placement_candidate_id"):
        _render_placement_form(sb, user_id)
        st.markdown("---")

    for p in placement_list:
        candidate = p.get("candidates", {}) or {}
        company = p.get("companies", {}) or {}
        cand_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}"
        comp_name = company.get("name", "Unknown")
        stage = p.get("stage", "submitted")

        stage_bg, stage_fg = STAGE_COLORS.get(stage, ("#f1f5f9", "#64748b"))

        with st.expander(
            f"{cand_name} -> {comp_name}  |  {p.get('role_title', 'N/A')}  |  {stage.upper()}",
            expanded=(stage in active_stages),
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(
                    f'<span style="background:{stage_bg};color:{stage_fg};'
                    f'padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">'
                    f'{stage.replace("_", " ").upper()}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{cand_name}** -> **{comp_name}**")
                st.markdown(f"Role: {p.get('role_title', 'N/A')}")

                if p.get("salary"):
                    fee_pct = float(p.get("fee_percent", 15))
                    fee = p["salary"] * fee_pct / 100
                    st.markdown(
                        f"Salary: **${p['salary']:,}** | "
                        f"Fee: {fee_pct}% = **${fee:,.0f}**"
                    )

                if p.get("start_date"):
                    st.markdown(f"Start date: {p['start_date']}")
                if p.get("notes"):
                    st.caption(f"Notes: {p['notes'][:200]}")

            with col2:
                new_stage = st.selectbox(
                    "Stage",
                    ["", "submitted", "phone_screen", "interview",
                     "final_round", "offer", "accepted", "started",
                     "withdrawn", "rejected"],
                    key=f"pstage_{p['id']}",
                )
                if new_stage and new_stage != stage:
                    if st.button("Update", key=f"pupdate_{p['id']}", use_container_width=True):
                        updates = {
                            "stage": new_stage,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        # Auto-calculate fee when accepted
                        if new_stage in ("accepted", "started") and p.get("salary"):
                            fee_pct = float(p.get("fee_percent", 15))
                            updates["fee_amount"] = p["salary"] * fee_pct / 100

                        sb.table("placements").update(updates).eq("id", p["id"]).execute()

                        # Update candidate status
                        if new_stage == "started":
                            sb.table("candidates").update({
                                "status": "placed",
                            }).eq("id", p["candidate_id"]).execute()

                        st.success(f"Updated to {new_stage}")
                        st.rerun()


def _render_placement_form(sb, user_id: str):
    """Render a form to create a new placement."""
    section_header("New Placement", "&#x1F4CB;")

    cand_id = st.session_state.get("placement_candidate_id", "")
    cand_name = st.session_state.get("placement_candidate_name", "")

    if cand_name:
        st.markdown(f"Candidate: **{cand_name}**")

    # Get companies for dropdown
    companies = sb.table("companies").select(
        "id, name"
    ).eq("owner_id", user_id).in_(
        "status", ["qualified", "active"]
    ).order("name").execute()

    company_options = {c["name"]: c["id"] for c in (companies.data or [])}

    with st.form("new_placement"):
        if not cand_id:
            cand_id = st.text_input("Candidate ID (UUID)")

        company_name = st.selectbox("Company", [""] + list(company_options.keys()))
        role_title = st.text_input("Role Title", placeholder="Senior Software Engineer")
        salary = st.number_input("Salary (AUD)", min_value=0, step=5000, value=0)
        fee_percent = st.number_input("Fee %", min_value=0.0, max_value=30.0, value=15.0, step=0.5)
        notes = st.text_area("Notes", placeholder="Additional details...")

        submitted = st.form_submit_button("Create Placement", use_container_width=True)

    if submitted and company_name and role_title and cand_id:
        company_id = company_options.get(company_name)
        if not company_id:
            st.error("Select a valid company")
            return

        sb.table("placements").insert({
            "owner_id": user_id,
            "candidate_id": cand_id,
            "company_id": company_id,
            "role_title": role_title,
            "salary": salary if salary > 0 else None,
            "fee_percent": fee_percent,
            "fee_amount": salary * fee_percent / 100 if salary > 0 else None,
            "notes": notes,
        }).execute()

        # Clear session state
        st.session_state.pop("placement_candidate_id", None)
        st.session_state.pop("placement_candidate_name", None)

        st.success("Placement created!")
        st.rerun()


def _render_add_candidate(sb, user_id: str):
    """Render form to add a new candidate."""
    section_header("Add New Candidate", "&#x1F464;")

    with st.form("new_candidate"):
        col1, col2 = st.columns(2)

        with col1:
            first_name = st.text_input("First Name*")
            last_name = st.text_input("Last Name*")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            linkedin = st.text_input("LinkedIn URL")

        with col2:
            current_title = st.text_input("Current Title")
            current_company = st.text_input("Current Company")
            location = st.text_input("Location", value="Sydney")
            experience = st.number_input("Years Experience", min_value=0, max_value=50, value=0)
            availability = st.selectbox(
                "Availability",
                ["immediate", "2 weeks", "4 weeks", "1 month+", "passive"],
            )

        skills_input = st.text_input("Skills (comma-separated)", placeholder="Python, AWS, React, ...")
        salary_col1, salary_col2 = st.columns(2)
        with salary_col1:
            salary_min = st.number_input("Salary Min (AUD)", min_value=0, step=5000, value=0)
        with salary_col2:
            salary_max = st.number_input("Salary Max (AUD)", min_value=0, step=5000, value=0)

        source = st.selectbox("Source", ["linkedin", "referral", "seek", "indeed", "direct", "other"])
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Add Candidate", use_container_width=True)

    if submitted and first_name and last_name:
        skills = [s.strip() for s in skills_input.split(",") if s.strip()] if skills_input else []

        sb.table("candidates").insert({
            "owner_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email or None,
            "phone": phone or None,
            "linkedin_url": linkedin or None,
            "current_title": current_title or None,
            "current_company": current_company or None,
            "skills": skills,
            "experience_years": experience if experience > 0 else None,
            "salary_min": salary_min if salary_min > 0 else None,
            "salary_max": salary_max if salary_max > 0 else None,
            "location": location or None,
            "availability": availability,
            "notes": notes or None,
            "source": source,
        }).execute()

        st.success(f"Added {first_name} {last_name}!")
        st.rerun()


def _candidates_to_csv(candidates: list[dict]) -> str:
    """Convert candidates to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "First Name", "Last Name", "Title", "Company", "Email",
        "Phone", "Location", "Experience", "Skills", "Salary Range",
        "Availability", "Status",
    ])
    for c in candidates:
        skills = ", ".join(c.get("skills") or [])
        sal = ""
        if c.get("salary_min") or c.get("salary_max"):
            sal = f"{c.get('salary_min', '?')}-{c.get('salary_max', '?')}"
        writer.writerow([
            c.get("first_name", ""), c.get("last_name", ""),
            c.get("current_title", ""), c.get("current_company", ""),
            c.get("email", ""), c.get("phone", ""),
            c.get("location", ""), c.get("experience_years", ""),
            skills, sal,
            c.get("availability", ""), c.get("status", ""),
        ])
    return output.getvalue()
