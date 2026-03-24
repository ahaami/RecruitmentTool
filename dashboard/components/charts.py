"""Reusable chart components for the Streamlit dashboard."""

import streamlit as st


def metric_row(metrics: list[dict]):
    """Display a row of metric cards.

    Args:
        metrics: List of dicts with 'label', 'value', and optional 'delta'.
    """
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            delta = metric.get("delta")
            col.metric(
                label=metric["label"],
                value=metric["value"],
                delta=delta,
            )


def status_badge(status: str) -> str:
    """Return a coloured status badge as markdown."""
    colors = {
        "new": "#94a3b8",
        "researching": "#f59e0b",
        "qualified": "#3b82f6",
        "active": "#22c55e",
        "paused": "#a855f7",
        "dead": "#ef4444",
    }
    color = colors.get(status, "#666")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600;">{status}</span>'


def score_badge(score: int) -> str:
    """Return a coloured score badge as markdown."""
    if score >= 50:
        color = "#22c55e"
    elif score >= 30:
        color = "#f59e0b"
    else:
        color = "#94a3b8"
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600;">{score}</span>'


def pipeline_funnel(pipeline_counts: dict):
    """Display a simple pipeline funnel visualisation."""
    stages = [
        ("New", pipeline_counts.get("new", 0), "#94a3b8"),
        ("Researching", pipeline_counts.get("researching", 0), "#f59e0b"),
        ("Qualified", pipeline_counts.get("qualified", 0), "#3b82f6"),
        ("Active", pipeline_counts.get("active", 0), "#22c55e"),
    ]

    for label, count, color in stages:
        if count > 0:
            bar_width = min(count * 3, 100)
            st.markdown(
                f'<div style="margin:4px 0;">'
                f'<span style="display:inline-block;width:100px;font-size:13px;color:#666;">{label}</span>'
                f'<span style="display:inline-block;background:{color};color:#fff;'
                f'padding:2px 8px;border-radius:4px;min-width:{bar_width}px;'
                f'font-size:12px;font-weight:600;text-align:center;">{count}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Show dead/paused below
    paused = pipeline_counts.get("paused", 0)
    dead = pipeline_counts.get("dead", 0)
    if paused or dead:
        st.caption(f"Paused: {paused} | Dead: {dead}")
