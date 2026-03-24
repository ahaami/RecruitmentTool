"""Run Pipeline page — trigger all pipeline actions from the dashboard."""

import streamlit as st
import subprocess
import sys
from pathlib import Path

from dashboard.components.auth import get_supabase, get_user_id
from dashboard.components.charts import page_header, section_header


# Repo root for running CLI commands
REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
PYTHON = sys.executable


def _run_command(args: list[str], placeholder) -> tuple[bool, str]:
    """Run a CLI command and stream output to the placeholder."""
    try:
        result = subprocess.run(
            [PYTHON, "main.py"] + args,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        success = result.returncode == 0
        placeholder.code(output or "(no output)", language=None)
        return success, output
    except subprocess.TimeoutExpired:
        placeholder.error("Command timed out after 5 minutes")
        return False, "Timeout"
    except Exception as e:
        placeholder.error(f"Error: {e}")
        return False, str(e)


def render():
    page_header("Run Pipeline", "Trigger pipeline actions without the command line")

    sb = get_supabase()
    user_id = get_user_id()

    # --- Quick Stats ---
    statuses = ["new", "researching", "qualified", "active"]
    counts = {}
    for s in statuses:
        r = sb.table("companies").select("id", count="exact").eq(
            "owner_id", user_id
        ).eq("status", s).execute()
        counts[s] = r.count or 0

    contacts_count = sb.table("contacts").select(
        "id", count="exact"
    ).eq("owner_id", user_id).execute()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("New", counts["new"])
    col2.metric("Researching", counts["researching"])
    col3.metric("Qualified", counts["qualified"])
    col4.metric("Contacts", contacts_count.count or 0)

    st.markdown("---")

    # --- Pipeline Actions ---
    section_header("Discovery & Enrichment", "&#x1F50D;")

    col_disc, col_enrich = st.columns(2)

    with col_disc:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Discover Companies</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Scrape job boards and news for growing AU tech companies. '
            'Scores and adds them to your pipeline.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Run Discovery", key="btn_discover", use_container_width=True):
            with st.spinner("Discovering companies..."):
                output_area = st.empty()
                success, _ = _run_command(["discover"], output_area)
                if success:
                    st.success("Discovery complete!")
                else:
                    st.error("Discovery had errors — check output above")

    with col_enrich:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Enrich Contacts</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Find decision-makers at researching companies using Apollo + Lusha. '
            'Gets phone numbers and emails.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Run Enrichment", key="btn_enrich", use_container_width=True):
            with st.spinner("Enriching contacts..."):
                output_area = st.empty()
                success, _ = _run_command(["enrich"], output_area)
                if success:
                    st.success("Enrichment complete!")
                else:
                    st.error("Enrichment had errors — check output above")

    st.markdown("---")
    section_header("Call Sheet & Outreach", "&#x1F4DE;")

    col_cs, col_email = st.columns(2)

    with col_cs:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Generate Call Sheet</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Build today\'s prioritised call list with AI-generated openers. '
            'Sends it to your email.</p></div>',
            unsafe_allow_html=True,
        )
        with_openers = st.checkbox("Include AI openers", value=True, key="cs_openers")
        cs_limit = st.number_input("Max leads", min_value=5, max_value=50, value=20, key="cs_limit")
        if st.button("Generate Call Sheet", key="btn_callsheet", use_container_width=True):
            cmd = ["callsheet", "--limit", str(cs_limit)]
            if with_openers:
                cmd.append("--with-openers")
            with st.spinner("Generating call sheet..."):
                output_area = st.empty()
                success, _ = _run_command(cmd, output_area)
                if success:
                    st.success("Call sheet generated and emailed!")
                else:
                    st.error("Call sheet had errors — check output above")

    with col_email:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Email Outreach</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Send personalised intro emails to decision-makers. '
            'Claude writes a custom email for each contact.</p></div>',
            unsafe_allow_html=True,
        )
        email_limit = st.number_input("Max emails", min_value=1, max_value=50, value=10, key="email_limit")
        dry_run = st.checkbox("Dry run (preview only)", value=True, key="email_dry")
        if st.button("Send Emails", key="btn_email", use_container_width=True):
            cmd = ["email-outreach", "--limit", str(email_limit)]
            if dry_run:
                cmd.append("--dry-run")
            with st.spinner("Generating emails..."):
                output_area = st.empty()
                success, _ = _run_command(cmd, output_area)
                if success:
                    st.success("Email outreach complete!")
                else:
                    st.error("Email outreach had errors — check output above")

    st.markdown("---")
    section_header("LinkedIn & Monitoring", "&#x1F4F1;")

    col_wu, col_mon = st.columns(2)

    with col_wu:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">LinkedIn Warm-Up</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Generate connection request notes and follow-up messages. '
            'You send them manually from LinkedIn.</p></div>',
            unsafe_allow_html=True,
        )
        wu_limit = st.number_input("Max messages", min_value=1, max_value=30, value=10, key="wu_limit")
        if st.button("Generate Messages", key="btn_warmup", use_container_width=True):
            with st.spinner("Generating LinkedIn messages..."):
                output_area = st.empty()
                success, _ = _run_command(["warmup", "--limit", str(wu_limit)], output_area)
                if success:
                    st.success("Messages generated! Check the LinkedIn tab.")
                else:
                    st.error("Warm-up had errors — check output above")

    with col_mon:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Monitor Companies</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Re-check existing companies for new job postings and news. '
            'Updates growth scores and flags reactivated leads.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Run Monitor", key="btn_monitor", use_container_width=True):
            with st.spinner("Monitoring companies..."):
                output_area = st.empty()
                success, _ = _run_command(["monitor"], output_area)
                if success:
                    st.success("Monitoring complete!")
                else:
                    st.error("Monitor had errors — check output above")

    st.markdown("---")
    section_header("Maintenance", "&#x2699;")

    col_stale, col_weekly, col_full = st.columns(3)

    with col_stale:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Pause Stale</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Pause companies with no new signals in 30+ days.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Pause Stale", key="btn_stale", use_container_width=True):
            with st.spinner("Checking for stale companies..."):
                output_area = st.empty()
                _run_command(["pause-stale"], output_area)

    with col_weekly:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Weekly Summary</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Send the weekly pipeline summary email.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Send Summary", key="btn_weekly", use_container_width=True):
            with st.spinner("Generating weekly summary..."):
                output_area = st.empty()
                _run_command(["weekly-summary"], output_area)

    with col_full:
        st.markdown(
            '<div class="lunar-card">'
            '<div class="lunar-card-title">Full Pipeline</div>'
            '<p style="font-size:13px;color:#64748b;">'
            'Run the entire daily pipeline: discover, enrich, callsheet, warmup, monitor.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Run All", key="btn_runall", use_container_width=True, type="primary"):
            with st.spinner("Running full pipeline (this may take a few minutes)..."):
                output_area = st.empty()
                success, _ = _run_command(["run-all"], output_area)
                if success:
                    st.success("Full pipeline complete!")
                else:
                    st.error("Pipeline had errors — check output above")

    # --- SQL Runner for schema setup ---
    st.markdown("---")
    section_header("Database Setup", "&#x1F5C4;")

    with st.expander("Run SQL schema (first-time setup)", expanded=False):
        st.markdown(
            "If you need to create the `candidates` and `placements` tables, "
            "paste this SQL into your [Supabase SQL Editor](https://supabase.com/dashboard)."
        )
        try:
            schema_path = Path(REPO_ROOT) / "db" / "candidates_schema.sql"
            if schema_path.exists():
                st.code(schema_path.read_text(), language="sql")
            else:
                st.info("Schema file not found")
        except Exception:
            st.info("Could not read schema file")
