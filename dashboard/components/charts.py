"""Reusable chart and UI components for the Streamlit dashboard."""

import streamlit as st
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Colour palette (consistent across all components)
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#6366f1",
    "primary_light": "#818cf8",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#3b82f6",
    "purple": "#a855f7",
    "cyan": "#06b6d4",
    "slate": "#64748b",
    "muted": "#94a3b8",
}

STATUS_COLORS = {
    "new": ("#f1f5f9", "#64748b"),
    "researching": ("#fef3c7", "#92400e"),
    "qualified": ("#dbeafe", "#1e40af"),
    "active": ("#dcfce7", "#166534"),
    "paused": ("#f3e8ff", "#6b21a8"),
    "dead": ("#fee2e2", "#991b1b"),
}

OUTCOME_COLORS = {
    "meeting_booked": "#22c55e",
    "spoke_dm": "#3b82f6",
    "spoke_gatekeeper": "#8b5cf6",
    "callback_requested": "#06b6d4",
    "voicemail": "#f59e0b",
    "no_answer": "#94a3b8",
    "not_interested": "#ef4444",
}


# ---------------------------------------------------------------------------
# Metric cards
# ---------------------------------------------------------------------------
def metric_row(metrics: list[dict]):
    """Display a row of styled metric cards."""
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            col.metric(
                label=metric["label"],
                value=metric["value"],
                delta=metric.get("delta"),
            )


def big_number(label: str, value, subtitle: str = "", color: str = "#6366f1"):
    """Display a large number with coloured accent."""
    st.markdown(
        f'<div style="text-align:center; padding:16px 0;">'
        f'<div style="font-size:11px; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.5px; color:#64748b;">{label}</div>'
        f'<div style="font-size:36px; font-weight:800; color:{color}; '
        f'line-height:1.2;">{value}</div>'
        f'<div style="font-size:12px; color:#94a3b8;">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------
def status_badge(status: str) -> str:
    """Return an HTML status badge."""
    bg, fg = STATUS_COLORS.get(status, ("#f1f5f9", "#64748b"))
    return (
        f'<span class="badge" style="background:{bg};color:{fg};">'
        f'{status}</span>'
    )


def score_badge(score: int) -> str:
    """Return an HTML score pill."""
    if score >= 50:
        cls = "score-high"
    elif score >= 30:
        cls = "score-mid"
    else:
        cls = "score-low"
    return f'<span class="score-pill {cls}">{score}</span>'


def dm_badge() -> str:
    """Return a decision-maker badge."""
    return (
        '<span style="background:#dbeafe;color:#1e40af;padding:2px 8px;'
        'border-radius:10px;font-size:10px;font-weight:700;">DM</span>'
    )


def confidence_badge(confidence: int) -> str:
    """Return a confidence indicator."""
    if confidence >= 80:
        color, bg = "#166534", "#dcfce7"
    elif confidence >= 50:
        color, bg = "#92400e", "#fef3c7"
    else:
        color, bg = "#64748b", "#f1f5f9"
    return (
        f'<span style="background:{bg};color:{color};padding:2px 8px;'
        f'border-radius:10px;font-size:10px;font-weight:700;">'
        f'{confidence}%</span>'
    )


# ---------------------------------------------------------------------------
# Pipeline funnel (Plotly)
# ---------------------------------------------------------------------------
def pipeline_funnel(pipeline_counts: dict):
    """Display an interactive pipeline funnel chart."""
    stages = ["new", "researching", "qualified", "active"]
    labels = ["New", "Researching", "Qualified", "Active"]
    values = [pipeline_counts.get(s, 0) for s in stages]
    colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#22c55e"]

    fig = go.Figure(go.Funnel(
        y=labels,
        x=values,
        textinfo="value+percent initial",
        marker=dict(color=colors),
        connector=dict(line=dict(color="#e2e8f0", width=1)),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        height=250,
        font=dict(family="Inter", size=13),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    paused = pipeline_counts.get("paused", 0)
    dead = pipeline_counts.get("dead", 0)
    if paused or dead:
        st.markdown(
            f'<div style="text-align:center;font-size:12px;color:#94a3b8;">'
            f'Paused: {paused} &nbsp;&middot;&nbsp; Dead: {dead}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Score distribution (Plotly bar)
# ---------------------------------------------------------------------------
def score_distribution_chart(scores: list[int]):
    """Display a bar chart of growth score distribution."""
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

    colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#6366f1", "#22c55e"]

    fig = go.Figure(go.Bar(
        x=list(bins.keys()),
        y=list(bins.values()),
        marker_color=colors,
        text=list(bins.values()),
        textposition="outside",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=220,
        font=dict(family="Inter", size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Score Range"),
        yaxis=dict(title="Companies", showgrid=True, gridcolor="#f1f5f9"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Donut chart (e.g., outcome breakdown)
# ---------------------------------------------------------------------------
def donut_chart(labels: list[str], values: list[int], colors: list[str] | None = None,
                title: str = ""):
    """Display a donut chart."""
    if not colors:
        colors = [OUTCOME_COLORS.get(l, "#94a3b8") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textposition="outside",
        pull=[0.02] * len(labels),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=30 if title else 10, b=0),
        height=300,
        font=dict(family="Inter", size=11),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title=dict(text=title, font=dict(size=14)) if title else None,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Horizontal bar chart (e.g., outcomes, sources)
# ---------------------------------------------------------------------------
def horizontal_bar(labels: list[str], values: list[int],
                   colors: list[str] | None = None, height: int = 250):
    """Display a horizontal bar chart."""
    if not colors:
        colors = [OUTCOME_COLORS.get(l, "#94a3b8") for l in labels]

    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=values,
        textposition="outside",
    ))
    fig.update_layout(
        margin=dict(l=0, r=40, t=10, b=0),
        height=height,
        font=dict(family="Inter", size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Card-style container (HTML)
# ---------------------------------------------------------------------------
def card_start():
    """Open a card container."""
    st.markdown('<div class="lunar-card">', unsafe_allow_html=True)


def card_end():
    """Close a card container."""
    st.markdown('</div>', unsafe_allow_html=True)


def section_header(title: str, icon: str = ""):
    """Render a section header with optional icon."""
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:10px; '
        f'margin: 24px 0 16px 0;">'
        f'<span style="font-size:22px;">{icon}</span>'
        f'<h2 style="margin:0; font-size:20px; font-weight:700; color:#0f172a;">'
        f'{title}</h2></div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = ""):
    """Render a branded page header."""
    sub_html = (
        f'<p style="color:#64748b; font-size:14px; margin:4px 0 0 0;">'
        f'{subtitle}</p>'
    ) if subtitle else ""
    st.markdown(
        f'<div style="margin-bottom: 24px;">'
        f'<h1 style="font-size:28px; font-weight:800; color:#0f172a; margin:0;">'
        f'{title}</h1>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )
