"""Heritage / lineage UI — formula provenance for every displayed value.

Provides two interaction layers:
1. HOVER: CSS tooltip on table cells showing first-order formula + values
2. CLICK: Streamlit expander showing full heritage chain (notepad style)

Integration:
    from views.heritage import (
        heritage_css,
        build_heritage_html_cell,
        render_heritage_inspector,
    )

    # Inject CSS once per page
    heritage_css()

    # Wrap a cell value with tooltip
    html = build_heritage_html_cell(
        display_value="EUR 785,000",
        key="pbt",
        period_values=annual_row,
    )

    # Full heritage inspector (below the table)
    render_heritage_inspector(
        keys=[("pbt", "Profit Before Tax"), ...],
        annual_data=annual_rows,
        label="P&L",
    )

Architecture:
    This module depends ONLY on engine.lineage (pure Python, no Streamlit)
    and streamlit (for the inspector widget). It does NOT import the engine
    calculation modules — zero risk of circular dependency.

    The CSS tooltip approach was chosen because the P&L table is already
    rendered as raw HTML via st.markdown(unsafe_allow_html=True). We inject
    tooltip spans directly into that HTML pipeline.
"""

from __future__ import annotations

import html as html_mod
from typing import Sequence

import streamlit as st

from engine.lineage import (
    format_heritage_text,
    get_heritage,
    get_node,
    get_tooltip,
)
# Available for future value-type coloring in tooltips:
# from engine.value_tags import VTYPE_COLORS, ValueType


# ══════════════════════════════════════════════════════════════════════
# CSS INJECTION
# ══════════════════════════════════════════════════════════════════════

def heritage_css() -> None:
    """Inject heritage tooltip CSS into the Streamlit page.

    Safe to call multiple times per render -- the CSS is small and the browser
    handles duplicate style blocks gracefully. We always emit it because
    Streamlit rebuilds the page DOM on each script rerun.
    """
    st.markdown("""
<style>
/* Heritage tooltip container */
.heritage-cell {
    position: relative;
    cursor: help;
    display: inline-block;
}
.heritage-cell .heritage-tip {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    z-index: 9999;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    min-width: 320px;
    max-width: 520px;
    padding: 10px 14px;
    background: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 11.5px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    pointer-events: none;
    transition: opacity 0.15s ease-in-out, visibility 0.15s;
}
.heritage-cell:hover .heritage-tip {
    visibility: visible;
    opacity: 1;
}
/* Tooltip arrow */
.heritage-cell .heritage-tip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: #1a1a2e transparent transparent transparent;
}
/* Formula highlight inside tooltip */
.heritage-tip .ht-formula {
    color: #7dd3fc;
}
.heritage-tip .ht-value {
    color: #86efac;
}
.heritage-tip .ht-source {
    color: #a78bfa;
    font-size: 10.5px;
}
.heritage-tip .ht-label {
    color: #fbbf24;
    font-weight: 600;
}
/* Heritage inspector panel */
.heritage-inspector {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.6;
    background: #0f172a;
    color: #e2e8f0;
    padding: 16px 20px;
    border-radius: 8px;
    border: 1px solid #334155;
    white-space: pre-wrap;
    overflow-x: auto;
}
.heritage-inspector .hi-depth-0 { color: #fbbf24; font-weight: 700; }
.heritage-inspector .hi-depth-1 { color: #7dd3fc; }
.heritage-inspector .hi-depth-2 { color: #86efac; }
.heritage-inspector .hi-depth-3 { color: #c4b5fd; }
.heritage-inspector .hi-depth-4 { color: #fca5a5; }
.heritage-inspector .hi-depth-5 { color: #67e8f9; }
.heritage-inspector .hi-formula { color: #94a3b8; }
.heritage-inspector .hi-source  { color: #a78bfa; font-size: 11px; }
.heritage-inspector .hi-value   { color: #86efac; font-weight: 600; }
.heritage-inspector .hi-leaf    { color: #9ca3af; font-style: italic; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TOOLTIP BUILDER (for HTML table cells)
# ══════════════════════════════════════════════════════════════════════

def build_heritage_tooltip_html(key: str, values: dict[str, float] | None = None) -> str:
    """Build the inner HTML for a tooltip popup.

    Returns empty string if key has no lineage (leaf/driver value).
    """
    node = get_node(key)
    if node is None:
        return ""

    parts: list[str] = []

    # Line 1: label
    label = node.label or key
    parts.append(f'<span class="ht-label">{html_mod.escape(label)}</span>')

    # Line 2: formula
    parts.append(f'<span class="ht-formula">{html_mod.escape(key)} = {html_mod.escape(node.formula)}</span>')

    # Line 3: with values
    if values is not None:
        tooltip_text = get_tooltip(key, values)
        # Extract the "= value1 +/- value2 = result" part
        eq_parts = tooltip_text.split(" = ", 2)
        if len(eq_parts) >= 3:
            parts.append(f'<span class="ht-value">= {html_mod.escape(eq_parts[2])}</span>')

    # Line 4: source
    if node.source:
        parts.append(f'<span class="ht-source">Source: {html_mod.escape(node.source)}</span>')

    return "\n".join(parts)


def build_heritage_html_cell(
    display_value: str,
    key: str,
    period_values: dict[str, float] | None = None,
    cell_style: str = "",
) -> str:
    """Wrap a display value in a heritage-tooltip span.

    If the key has no lineage, returns the display value as-is (no tooltip).

    Args:
        display_value: Already-formatted cell text (e.g. "EUR 785,000")
        key: Column key in the lineage graph
        period_values: Dict of all values for this period (for value substitution)
        cell_style: Additional inline CSS for the cell

    Returns:
        HTML string: either a plain value or a tooltip-wrapped value.
    """
    tooltip_html = build_heritage_tooltip_html(key, period_values)
    if not tooltip_html:
        return display_value

    return (
        f'<span class="heritage-cell" style="{cell_style}">'
        f'{display_value}'
        f'<span class="heritage-tip">{tooltip_html}</span>'
        f'</span>'
    )


# ══════════════════════════════════════════════════════════════════════
# HERITAGE INSPECTOR (expander / selectbox)
# ══════════════════════════════════════════════════════════════════════

def _format_heritage_html(
    key: str,
    values: dict[str, float] | None = None,
    max_depth: int = 8,
) -> str:
    """Format the heritage chain as styled HTML for the inspector panel."""
    steps = get_heritage(key, max_depth=max_depth, values=values)
    if not steps:
        node = get_node(key)
        if node is None:
            return f'<span class="hi-leaf">{html_mod.escape(key)}: leaf value (config input / driver)</span>'
        return f'<span class="hi-depth-0">{html_mod.escape(get_tooltip(key, values))}</span>'

    lines: list[str] = []
    _depth_classes = [
        "hi-depth-0", "hi-depth-1", "hi-depth-2", "hi-depth-3",
        "hi-depth-4", "hi-depth-5",
    ]

    for step in steps:
        indent = "&nbsp;" * (step.depth * 4)
        child_indent = "&nbsp;" * ((step.depth + 1) * 4)
        depth_cls = _depth_classes[min(step.depth, len(_depth_classes) - 1)]

        # Header line
        result_str = ""
        if step.result_value is not None:
            from engine.lineage import _fmt_val
            result_str = f' = <span class="hi-value">{html_mod.escape(_fmt_val(step.result_value, step.unit))}</span>'
        label_esc = html_mod.escape(step.label)
        key_esc = html_mod.escape(step.key)
        lines.append(
            f'{indent}<span class="{depth_cls}">Level {step.depth}: {label_esc} ({key_esc}){result_str}</span>'
        )

        # Formula line
        formula_esc = html_mod.escape(step.formula)
        lines.append(f'{child_indent}<span class="hi-formula">= {formula_esc}</span>')

        # Values line
        if step.input_values:
            from engine.lineage import _fmt_val
            val_parts: list[str] = []
            for inp, s in zip(step.inputs, step.sign):
                v = step.input_values.get(inp)
                if v is not None:
                    prefix = "- " if s < 0 and val_parts else ("+ " if s > 0 and val_parts else "")
                    if s < 0 and not val_parts:
                        prefix = "-"
                    val_parts.append(f'{prefix}<span class="hi-value">{html_mod.escape(_fmt_val(abs(v), step.unit))}</span>')
                else:
                    prefix = "- " if s < 0 and val_parts else ("+ " if s > 0 and val_parts else "")
                    val_parts.append(f'{prefix}<span class="hi-leaf">{html_mod.escape(inp)}</span>')
            if val_parts:
                lines.append(f'{child_indent}<span class="hi-formula">= {" ".join(val_parts)}</span>')

        # Source line
        if step.source:
            source_esc = html_mod.escape(step.source)
            lines.append(f'{child_indent}<span class="hi-source">Source: {source_esc}</span>')

        lines.append("")  # blank line

    return "<br>".join(lines)


def render_heritage_inspector(
    row_keys: Sequence[tuple[str, str]],
    annual_data: list[dict],
    label: str = "Heritage",
    year_labels: list[str] | None = None,
) -> None:
    """Render an interactive heritage inspector below a financial table.

    Provides a selectbox to choose a row (key), then a year selector,
    then displays the full heritage chain in a styled panel.

    Args:
        row_keys: List of (key, display_label) tuples for selectable rows.
                  Only keys with lineage nodes will be shown.
        annual_data: List of annual dicts (one per year).
        label: Display label for the inspector section.
        year_labels: Optional year labels (e.g. ["Y1", "Y2", ...]). Defaults
                     to "Year 1", "Year 2", etc.
    """
    # Filter to keys that actually have lineage
    available = [(k, lbl) for k, lbl in row_keys if get_node(k) is not None]
    if not available:
        return

    heritage_css()

    with st.expander(f"Inspect {label} Heritage", expanded=False, icon=":material/account_tree:"):
        col_row, col_year = st.columns([3, 1])

        with col_row:
            options = [f"{lbl}  ({k})" for k, lbl in available]
            selected_idx = st.selectbox(
                "Select row",
                range(len(options)),
                format_func=lambda i: options[i],
                key=f"heritage_row_{label}",
                label_visibility="collapsed",
            )

        if year_labels is None:
            year_labels = [f"Year {i+1}" for i in range(len(annual_data))]

        with col_year:
            year_idx = st.selectbox(
                "Year",
                range(len(annual_data)),
                format_func=lambda i: year_labels[i],
                key=f"heritage_year_{label}",
                label_visibility="collapsed",
            )

        if selected_idx is not None and year_idx is not None:
            sel_key = available[selected_idx][0]
            period_data = annual_data[year_idx]

            # Show the heritage chain
            heritage_html = _format_heritage_html(sel_key, values=period_data)

            st.markdown(
                f'<div class="heritage-inspector">{heritage_html}</div>',
                unsafe_allow_html=True,
            )

            # Also show leaf inputs
            from engine.lineage import get_leaf_inputs
            leaves = get_leaf_inputs(sel_key)
            if leaves:
                leaf_items: list[str] = []
                for leaf in sorted(leaves):
                    v = period_data.get(leaf)
                    if v is not None:
                        leaf_items.append(f"  {leaf} = {v:,.2f}")
                    else:
                        leaf_items.append(f"  {leaf} = (not in period data)")
                st.caption("Leaf inputs (config/driver values):")
                st.code("\n".join(leaf_items), language="text")


# ══════════════════════════════════════════════════════════════════════
# P&L TABLE INTEGRATION
# ══════════════════════════════════════════════════════════════════════

def inject_pnl_heritage(
    pnl_rows: list[tuple],
    annual_data: list[dict],
    year_count: int,
    eur_fmt: str = "\u20ac{:,.0f}",
    year_labels: list[str] | None = None,
) -> str:
    """Build the P&L HTML table with heritage tooltips injected into value cells.

    This replaces the inline HTML table builder in app.py. It takes the same
    _pnl_rows structure and produces HTML with heritage tooltips on each cell.

    Args:
        pnl_rows: List of (label, values, row_type, key) tuples.
                  key is the column key for lineage lookup (may be empty).
        annual_data: List of annual dicts (one per year) for value resolution.
        year_count: Number of year columns.
        eur_fmt: Format string for EUR values.
        year_labels: Column headers for year columns. Defaults to Y1, Y2, etc.

    Returns:
        Complete HTML string for the table.
    """
    heritage_css()

    ncols = year_count + 1  # years + total column

    h: list[str] = []
    h.append('<div style="overflow-x:auto;width:100%;">')
    h.append('<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">')
    h.append('<thead><tr>')
    h.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')

    # Year headers
    if year_labels is None:
        year_labels = [f"Y{i+1}" for i in range(year_count)]
    col_headers = list(year_labels) + ["Total"]
    for c in col_headers:
        h.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
    h.append('</tr></thead><tbody>')

    for row_data in pnl_rows:
        if len(row_data) == 4:
            label, vals, rtype, key = row_data
        else:
            label, vals, rtype = row_data
            key = ""

        if rtype == 'spacer':
            h.append(f'<tr><td colspan="{ncols + 1}" style="height:10px;border:none;"></td></tr>')
            continue
        if rtype == 'section':
            h.append(
                f'<tr><td colspan="{ncols + 1}" style="padding:8px 10px 4px;font-weight:700;'
                f'font-size:11px;color:#6B7280;letter-spacing:0.08em;'
                f'border-bottom:1px solid #E5E7EB;">{html_mod.escape(label)}</td></tr>'
            )
            continue

        # Row styling by type
        if rtype == 'grand':
            td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
        elif rtype == 'total':
            td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
        elif rtype == 'memo':
            td_style = 'font-style:italic;color:#9CA3AF;font-size:12px;border-bottom:1px dotted #E2E8F0;'
        elif rtype == 'sub':
            td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
        else:
            td_style = 'border-bottom:1px solid #F1F5F9;'

        h.append('<tr>')
        h.append(f'<td style="text-align:left;padding:4px 10px;{td_style}">{html_mod.escape(label)}</td>')

        for vi, v in enumerate(vals):
            if v is not None and not isinstance(v, str):
                cell_text = eur_fmt.format(v)
                # Inject heritage tooltip for year columns (not Total)
                if key and vi < year_count and vi < len(annual_data):
                    cell_text = build_heritage_html_cell(
                        cell_text, key, annual_data[vi],
                    )
            else:
                cell_text = ''
            h.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell_text}</td>')

        h.append('</tr>')

    h.append('</tbody></table></div>')
    return ''.join(h)
