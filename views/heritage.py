"""Heritage / lineage UI -- formula provenance for every displayed value.

Provides two interaction layers:
1. HOVER: JavaScript-powered tooltip on table cells showing formula + values.
   The table is rendered via st.html() which gives full CSS/JS freedom inside
   an iframe, bypassing Streamlit's HTML sanitizer that strips position/z-index.
2. CLICK: Streamlit expander (below the table) showing full heritage chain.

Integration:
    from views.heritage import (
        heritage_css,
        inject_pnl_heritage,
        render_heritage_inspector,
    )

    # Build and render the P&L table with working heritage tooltips
    inject_pnl_heritage(pnl_rows, annual_data, year_count, eur_fmt, year_labels)

    # Full heritage inspector (below the table)
    render_heritage_inspector(
        keys=[("pbt", "Profit Before Tax"), ...],
        annual_data=annual_rows,
        label="P&L",
    )

Architecture:
    This module depends ONLY on engine.lineage (pure Python, no Streamlit)
    and streamlit (for the inspector widget). It does NOT import the engine
    calculation modules -- zero risk of circular dependency.

    The table is rendered via st.html() which creates an iframe with full
    DOM freedom. JavaScript handles hover tooltips (positioned divs) and
    visual cell highlighting. The heritage inspector below the table uses
    native Streamlit widgets (expander, selectbox) and st.markdown for
    styled HTML that only needs simple inline properties.
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


# ======================================================================
# CSS -- heritage inspector panel (used by render_heritage_inspector)
# ======================================================================

_INSPECTOR_CSS = """
<style>
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
"""


def heritage_css() -> None:
    """Inject heritage inspector CSS into the Streamlit page.

    The table tooltip CSS is now embedded in the st.html() iframe output,
    so this function only handles the inspector panel styling. Safe to call
    multiple times -- the browser handles duplicate style blocks.
    """
    st.markdown(_INSPECTOR_CSS, unsafe_allow_html=True)


# ======================================================================
# TOOLTIP DATA BUILDER (for data-* attributes on table cells)
# ======================================================================

def _build_tooltip_text(key: str, period_values: dict[str, float] | None = None) -> str:
    """Build plain-text tooltip content for a cell.

    Returns a multi-line string with label, formula, resolved values, and source.
    Empty string if key has no lineage (leaf/driver value).
    """
    node = get_node(key)
    if node is None:
        return ""

    parts: list[str] = []

    # Line 1: label
    label = node.label or key
    parts.append(label)

    # Line 2: formula
    parts.append(f"{key} = {node.formula}")

    # Line 3: resolved values
    if period_values is not None:
        tooltip_text = get_tooltip(key, period_values)
        # Extract the "= value1 +/- value2 = result" part
        eq_parts = tooltip_text.split(" = ", 2)
        if len(eq_parts) >= 3:
            parts.append(f"= {eq_parts[2]}")

    # Line 4: source
    if node.source:
        parts.append(f"Source: {node.source}")

    return "\n".join(parts)


# ======================================================================
# HTML TABLE WITH JS TOOLTIPS (rendered via st.html)
# ======================================================================

# CSS for the table inside the st.html() iframe. Full freedom here --
# no sanitizer strips anything inside an iframe.
_TABLE_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { overflow: visible; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    color: #1f2937;
    background: transparent;
    line-height: 1.4;
}
#tooltip-root { position: relative; }
table {
    border-collapse: collapse;
    width: 100%;
    white-space: nowrap;
}
th {
    text-align: right;
    padding: 6px 8px;
    border-bottom: 2px solid #333;
    font-weight: 700;
    font-size: 13px;
    position: sticky;
    top: 0;
    background: #fff;
    z-index: 10;
}
th:first-child { text-align: left; padding-left: 10px; }
td { padding: 4px 8px; text-align: right; }
td:first-child { text-align: left; padding-left: 10px; }

/* Row types */
tr.row-line td        { border-bottom: 1px solid #f1f5f9; }
tr.row-total td       { font-weight: 600; background: #f1f5f9; border-top: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1; }
tr.row-grand td       { font-weight: 700; background: #1e3a5f; color: #fff; border-top: 2px solid #333; border-bottom: 2px solid #333; }
tr.row-memo td        { font-style: italic; color: #9ca3af; font-size: 12px; border-bottom: 1px dotted #e2e8f0; }
tr.row-sub td         { font-style: italic; color: #475569; border-bottom: 1px dashed #e2e8f0; }
tr.row-section td     { padding: 8px 10px 4px; font-weight: 700; font-size: 11px; color: #6b7280; letter-spacing: 0.08em; border-bottom: 1px solid #e5e7eb; }
tr.row-spacer td      { height: 10px; border: none; }

/* Heritage cell hover highlight */
td.hc {
    cursor: help;
    transition: background-color 0.12s ease;
    position: relative;
}
td.hc:hover {
    background-color: #dbeafe !important;
}
tr.row-grand td.hc:hover {
    background-color: #2563eb !important;
}

/* Tooltip */
#heritage-tooltip {
    display: none;
    position: absolute;
    z-index: 99999;
    min-width: 280px;
    max-width: 480px;
    padding: 10px 14px;
    background: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 11.5px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    pointer-events: none;
}
#heritage-tooltip .tt-label {
    color: #fbbf24;
    font-weight: 600;
    display: block;
    margin-bottom: 2px;
}
#heritage-tooltip .tt-formula {
    color: #7dd3fc;
    display: block;
}
#heritage-tooltip .tt-values {
    color: #86efac;
    display: block;
}
#heritage-tooltip .tt-source {
    color: #a78bfa;
    font-size: 10.5px;
    display: block;
    margin-top: 2px;
}

/* Inline heritage accordion row (inserted after clicked row) */
tr.heritage-row td {
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}
.hd-panel {
    background: #0f172a;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    margin: 4px 8px 6px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-x: auto;
}
.hd-panel .hd-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 14px;
    border-bottom: 1px solid #334155;
    background: #1e293b;
    border-radius: 6px 6px 0 0;
}
.hd-panel .hd-title {
    color: #fbbf24;
    font-weight: 700;
    font-size: 12px;
}
.hd-panel .hd-close {
    color: #94a3b8;
    cursor: pointer;
    font-size: 16px;
    font-weight: 700;
    padding: 0 5px;
    border-radius: 3px;
    transition: background 0.15s;
}
.hd-panel .hd-close:hover {
    background: #334155;
    color: #f1f5f9;
}
.hd-panel .hd-body {
    padding: 12px 16px;
}
/* Heritage depth colours inside accordion */
.hd-panel .hi-depth-0 { color: #fbbf24; font-weight: 700; }
.hd-panel .hi-depth-1 { color: #7dd3fc; }
.hd-panel .hi-depth-2 { color: #86efac; }
.hd-panel .hi-depth-3 { color: #c4b5fd; }
.hd-panel .hi-depth-4 { color: #fca5a5; }
.hd-panel .hi-depth-5 { color: #67e8f9; }
.hd-panel .hi-formula { color: #94a3b8; }
.hd-panel .hi-source  { color: #a78bfa; font-size: 11px; }
.hd-panel .hi-value   { color: #86efac; font-weight: 600; }
.hd-panel .hi-leaf    { color: #9ca3af; font-style: italic; }

/* Highlight the source row when accordion is open */
tr.hd-active td { background-color: #eff6ff !important; }
tr.row-grand.hd-active td { background-color: #1e40af !important; }
"""

# JavaScript for tooltip hover + click-to-expand inline accordion row.
_TABLE_JS = """\
(function() {
    var tip = document.getElementById('heritage-tooltip');
    var HD = window.HD || {};
    var cells = document.querySelectorAll('td.hc');
    var openRow = null;   // the inserted <tr> element
    var activeRow = null; // the data <tr> that was clicked (gets .hd-active)
    var colCount = document.querySelector('thead tr').children.length;

    /* ── Hover tooltip ── */
    cells.forEach(function(cell) {
        cell.addEventListener('mouseenter', function(e) {
            var raw = cell.getAttribute('data-tip');
            if (!raw) return;
            var lines = raw.split('\\\\n');
            var html = '';
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (i === 0) {
                    html += '<span class="tt-label">' + escHtml(line) + '</span>';
                } else if (line.indexOf('Source:') === 0) {
                    html += '<span class="tt-source">' + escHtml(line) + '</span>';
                } else if (line.indexOf('= ') === 0) {
                    html += '<span class="tt-values">' + escHtml(line) + '</span>';
                } else {
                    html += '<span class="tt-formula">' + escHtml(line) + '</span>';
                }
            }
            tip.innerHTML = html;
            tip.style.display = 'block';
            positionTip(e);
        });
        cell.addEventListener('mousemove', function(e) { positionTip(e); });
        cell.addEventListener('mouseleave', function() { tip.style.display = 'none'; });

        /* ── Click → inline accordion row ── */
        cell.addEventListener('click', function() {
            var key = cell.getAttribute('data-key');
            var yi = cell.getAttribute('data-yi');
            if (!key || yi === null) return;

            var clickedTr = cell.parentNode;
            var hdKey = key + '_' + yi;

            // If clicking same row that's already open → close (toggle)
            if (openRow && activeRow === clickedTr) {
                closeAccordion();
                return;
            }

            // Close any existing accordion first
            closeAccordion();

            // Build content
            var content = HD[hdKey];
            if (!content) {
                content = '<span class="hi-leaf">' + escHtml(key) + ': leaf value \\u2014 no formula chain</span>';
            }

            // Create the accordion <tr>
            var tr = document.createElement('tr');
            tr.className = 'heritage-row';
            var td = document.createElement('td');
            td.colSpan = colCount;
            td.innerHTML =
                '<div class="hd-panel">' +
                '<div class="hd-header">' +
                '<span class="hd-title">' + escHtml(key) + ' \\u2014 Year ' + (parseInt(yi) + 1) + '</span>' +
                '<span class="hd-close" title="Close">\\u00d7</span>' +
                '</div>' +
                '<div class="hd-body">' + content + '</div>' +
                '</div>';
            tr.appendChild(td);

            // Insert after the clicked row
            var parent = clickedTr.parentNode;
            var next = clickedTr.nextSibling;
            if (next) {
                parent.insertBefore(tr, next);
            } else {
                parent.appendChild(tr);
            }

            // Highlight source row
            clickedTr.classList.add('hd-active');
            openRow = tr;
            activeRow = clickedTr;

            // Wire close button
            td.querySelector('.hd-close').addEventListener('click', function(e) {
                e.stopPropagation();
                closeAccordion();
            });

            // Hide tooltip so it doesn't linger
            tip.style.display = 'none';
        });
    });

    function closeAccordion() {
        if (openRow) {
            openRow.parentNode.removeChild(openRow);
            openRow = null;
        }
        if (activeRow) {
            activeRow.classList.remove('hd-active');
            activeRow = null;
        }
    }

    function positionTip(e) {
        var x = e.pageX + 16;
        var y = e.pageY + 20;
        var tw = tip.offsetWidth;
        var th = tip.offsetHeight;
        var dw = document.documentElement.scrollWidth;
        if (x + tw > dw - 8) x = e.pageX - tw - 16;
        if (x < 4) x = 4;
        if (y + th > document.documentElement.scrollHeight - 8) y = e.pageY - th - 12;
        if (y < 4) y = 4;
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
    }

    function escHtml(s) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(s));
        return d.innerHTML;
    }
})();
"""


def _build_heritage_data(
    pnl_rows: list[tuple],
    annual_data: list[dict],
    year_count: int,
) -> dict[str, str]:
    """Pre-build heritage HTML for all (key, year_index) combos.

    Returns a dict like {"pbt_0": "<span ...>...</span>", ...} to embed
    as JSON in the page for the click-to-expand panel.
    """
    data: dict[str, str] = {}
    seen_keys: set[str] = set()
    for row_data in pnl_rows:
        if len(row_data) == 4:
            _label, _vals, rtype, key = row_data
        else:
            _label, _vals, rtype = row_data[:3]
            key = ""
        if not key or rtype in ('section', 'spacer'):
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        for yi in range(min(year_count, len(annual_data))):
            heritage_html = _format_heritage_html(key, values=annual_data[yi])
            if not heritage_html:
                heritage_html = (
                    f'<span class="hi-leaf">{html_mod.escape(key)}: '
                    f'leaf value &mdash; no formula chain</span>'
                )
            data[f"{key}_{yi}"] = heritage_html
    return data


def _estimate_table_height(pnl_rows: list[tuple], year_count: int) -> int:
    """Estimate the pixel height needed for the table iframe.

    Accounts for row types: spacers are shorter, sections are taller,
    normal rows are ~28px. Adds header height and padding.
    """
    row_height = 0
    for row_data in pnl_rows:
        rtype = row_data[2] if len(row_data) >= 3 else 'line'
        if rtype == 'spacer':
            row_height += 10
        elif rtype == 'section':
            row_height += 32
        elif rtype == 'grand':
            row_height += 34
        else:
            row_height += 28
    # Header + bottom padding + tooltip overflow buffer + inline accordion.
    # The accordion row expands inside the table; scrolling=True handles
    # deep heritage trees that push beyond the estimated height.
    return row_height + 38 + 350


def inject_pnl_heritage(
    pnl_rows: list[tuple],
    annual_data: list[dict],
    year_count: int,
    eur_fmt: str = "\u20ac{:,.0f}",
    year_labels: list[str] | None = None,
) -> str:
    """Build the P&L HTML table with heritage tooltips and render it.

    Uses st.html() to render the table in an iframe where CSS/JS are not
    sanitized. Hover tooltips are powered by JavaScript event handlers.

    The function both builds the HTML AND renders it via st.html(). It also
    returns the HTML string for backward compatibility, though callers should
    NOT re-render it via st.markdown().

    Args:
        pnl_rows: List of (label, values, row_type, key) tuples.
                  key is the column key for lineage lookup (may be empty).
        annual_data: List of annual dicts (one per year) for value resolution.
        year_count: Number of year columns.
        eur_fmt: Format string for EUR values.
        year_labels: Column headers for year columns. Defaults to Y1, Y2, etc.

    Returns:
        Complete HTML string for the table (already rendered via st.html).
    """
    ncols = year_count + 1  # years + total column

    h: list[str] = []

    # Table structure
    h.append('<table>')
    h.append('<thead><tr>')
    h.append('<th>Item</th>')

    if year_labels is None:
        year_labels = [f"Y{i+1}" for i in range(year_count)]
    col_headers = list(year_labels) + ["Total"]
    for c in col_headers:
        h.append(f'<th>{html_mod.escape(c)}</th>')
    h.append('</tr></thead><tbody>')

    for row_data in pnl_rows:
        if len(row_data) == 4:
            label, vals, rtype, key = row_data
        else:
            label, vals, rtype = row_data
            key = ""

        if rtype == 'spacer':
            h.append(f'<tr class="row-spacer"><td colspan="{ncols + 1}"></td></tr>')
            continue
        if rtype == 'section':
            h.append(
                f'<tr class="row-section"><td colspan="{ncols + 1}">'
                f'{html_mod.escape(label)}</td></tr>'
            )
            continue

        row_cls = f"row-{rtype}" if rtype in ('grand', 'total', 'memo', 'sub') else "row-line"
        h.append(f'<tr class="{row_cls}">')
        h.append(f'<td>{html_mod.escape(label)}</td>')

        for vi, v in enumerate(vals):
            if v is not None and not isinstance(v, str):
                cell_text = html_mod.escape(eur_fmt.format(v))
                # ALL value cells get hc class for uniform styling
                if key and vi < year_count and vi < len(annual_data):
                    tip_text = _build_tooltip_text(key, annual_data[vi])
                    if not tip_text:
                        # Leaf/driver value — minimal tooltip
                        tip_text = f"{key}\nConfig / driver input"
                    tip_encoded = tip_text.replace("\n", "\\n")
                    tip_attr = html_mod.escape(tip_encoded, quote=True)
                    key_attr = html_mod.escape(key)
                    h.append(f'<td class="hc" data-tip="{tip_attr}" data-key="{key_attr}" data-yi="{vi}">{cell_text}</td>')
                else:
                    h.append(f'<td class="hc">{cell_text}</td>')
            else:
                h.append('<td></td>')

        h.append('</tr>')

    h.append('</tbody></table>')

    table_html = ''.join(h)

    # Pre-build heritage HTML for click-to-expand panel
    import json as _json
    heritage_data = _build_heritage_data(pnl_rows, annual_data, year_count)
    hd_json = _json.dumps(heritage_data, ensure_ascii=True)

    # Build complete self-contained HTML document for st.html()
    full_html = (
        '<!DOCTYPE html>'
        '<html><head><meta charset="utf-8">'
        f'<style>{_TABLE_CSS}</style>'
        '</head><body>'
        f'<script>var HD={hd_json};</script>'
        '<div id="tooltip-root">'
        f'<div style="overflow-x:auto;width:100%;">{table_html}</div>'
        '<div id="heritage-tooltip"></div>'
        '</div>'
        f'<script>{_TABLE_JS}</script>'
        '</body></html>'
    )

    # Estimate height for the iframe
    height = _estimate_table_height(pnl_rows, year_count)

    # Render via streamlit.components.v1.html -- full CSS/JS freedom,
    # no sanitizer. This is the same approach used by render_svg() in app.py.
    import streamlit.components.v1 as _stc
    _stc.html(full_html, height=height, scrolling=True)

    return full_html


# ======================================================================
# DataFrame-aware heritage wrapper (facility schedules, SCLCA assets)
# ======================================================================

def inject_df_heritage(
    df: "pd.DataFrame",
    key_map: dict[str, str] | None = None,
    label_col: str | None = None,
    value_cols: list[str] | None = None,
    formats: dict[str, str] | None = None,
    row_data: list[dict] | None = None,
) -> str:
    """Render a DataFrame table with per-column heritage tooltips.

    Unlike inject_pnl_heritage() which assigns one lineage key per ROW
    (financial concepts as rows, years as columns), this function assigns
    lineage keys per COLUMN via key_map. This makes it suitable for
    facility schedules and similar tables where:
      - Rows = periods (H1, H2, ... H20)
      - Columns = financial concepts (Opening, Interest, Principal, Closing)

    Each cell in a mapped column gets hover tooltip + click-to-expand
    heritage using the same CSS/JS infrastructure as inject_pnl_heritage().

    Args:
        df: DataFrame to render. Each row becomes a table row.
        key_map: {column_name: lineage_key}. E.g. {"Opening": "sr_opening",
                 "Interest": "ie_sr"}. Columns not in key_map render plain.
        label_col: Column to use as row label (left-aligned). If None, uses
                   first column of df.
        value_cols: Which columns to display as value cells. If None, all
                    columns except label_col.
        formats: {column_name: format_string}. E.g. {"Opening": "EUR{:,.0f}"}.
                 Columns without a format entry render as-is.
        row_data: Optional list of dicts (one per DataFrame row) for heritage
                  value resolution. If None, tooltips show formula only.

    Returns:
        Complete HTML string (already rendered via st.html).
    """
    import json as _json
    import pandas as pd
    import streamlit.components.v1 as _stc

    if key_map is None:
        key_map = {}
    if formats is None:
        formats = {}

    # Determine label and value columns
    all_cols = list(df.columns)
    if label_col is None:
        label_col = all_cols[0]
    if value_cols is None:
        value_cols = [c for c in all_cols if c != label_col]

    # ── Build HTML table ──
    h: list[str] = []
    h.append('<table>')
    h.append('<thead><tr>')
    h.append(f'<th>{html_mod.escape(str(label_col))}</th>')
    for c in value_cols:
        h.append(f'<th>{html_mod.escape(str(c))}</th>')
    h.append('</tr></thead><tbody>')

    heritage_data: dict[str, str] = {}

    for ri, (_, row) in enumerate(df.iterrows()):
        h.append('<tr class="row-line">')
        # Label cell (left-aligned by CSS th:first-child / td:first-child)
        lbl_val = row[label_col] if label_col in row.index else ""
        h.append(f'<td>{html_mod.escape(str(lbl_val))}</td>')

        for col in value_cols:
            v = row.get(col)
            key = key_map.get(col, "")
            fmt = formats.get(col, "")

            # Format numeric values
            if v is not None and not isinstance(v, str) and pd.notna(v):
                if fmt:
                    try:
                        cell_text = html_mod.escape(fmt.format(v))
                    except (ValueError, KeyError, IndexError):
                        cell_text = html_mod.escape(f"{v:,.2f}")
                else:
                    cell_text = html_mod.escape(f"{v:,.2f}")

                if key:
                    # Build tooltip from lineage
                    period_data = row_data[ri] if row_data and ri < len(row_data) else None
                    tip_text = _build_tooltip_text(key, period_data)
                    if not tip_text:
                        tip_text = f"{key}\nConfig / driver input"
                    tip_encoded = tip_text.replace("\n", "\\n")
                    tip_attr = html_mod.escape(tip_encoded, quote=True)
                    key_attr = html_mod.escape(key)
                    h.append(
                        f'<td class="hc" data-tip="{tip_attr}" '
                        f'data-key="{key_attr}" data-yi="{ri}">'
                        f'{cell_text}</td>'
                    )

                    # Pre-build heritage HTML for click-to-expand panel
                    hd_key = f"{key}_{ri}"
                    if hd_key not in heritage_data:
                        heritage_html = _format_heritage_html(key, values=period_data)
                        if not heritage_html:
                            heritage_html = (
                                f'<span class="hi-leaf">'
                                f'{html_mod.escape(key)}: leaf value '
                                f'&mdash; no formula chain</span>'
                            )
                        heritage_data[hd_key] = heritage_html
                else:
                    h.append(f'<td class="hc">{cell_text}</td>')
            else:
                cell_text = html_mod.escape(str(v)) if v is not None else ""
                h.append(f'<td>{cell_text}</td>')

        h.append('</tr>')

    h.append('</tbody></table>')
    table_html = ''.join(h)

    hd_json = _json.dumps(heritage_data, ensure_ascii=True)

    # Build complete self-contained HTML document for st.html()
    full_html = (
        '<!DOCTYPE html>'
        '<html><head><meta charset="utf-8">'
        f'<style>{_TABLE_CSS}</style>'
        '</head><body>'
        f'<script>var HD={hd_json};</script>'
        '<div id="tooltip-root">'
        f'<div style="overflow-x:auto;width:100%;">{table_html}</div>'
        '<div id="heritage-tooltip"></div>'
        '</div>'
        f'<script>{_TABLE_JS}</script>'
        '</body></html>'
    )

    # Height estimate: rows * 28 + header + padding + accordion buffer
    height = len(df) * 28 + 38 + 350

    _stc.html(full_html, height=height, scrolling=True)

    return full_html


# ======================================================================
# HERITAGE INSPECTOR (expander / selectbox)
# ======================================================================

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


# ======================================================================
# BACKWARD COMPATIBILITY -- old API surface kept for imports
# ======================================================================

def build_heritage_html_cell(
    display_value: str,
    key: str,
    period_values: dict[str, float] | None = None,
    cell_style: str = "",
) -> str:
    """Wrap a display value with heritage tooltip data.

    DEPRECATED: This function is kept for backward compatibility. The new
    inject_pnl_heritage() handles tooltip injection internally using
    data-* attributes and JavaScript in the st.html() iframe.

    When called directly, returns the display value with a title attribute
    as a basic fallback.
    """
    node = get_node(key)
    if node is None:
        return display_value

    tip_text = _build_tooltip_text(key, period_values)
    if not tip_text:
        return display_value

    title_attr = html_mod.escape(tip_text.replace("\n", "&#10;"), quote=True)
    return (
        f'<span style="cursor:help;{cell_style}" title="{title_attr}">'
        f'{display_value}</span>'
    )


def build_heritage_tooltip_html(key: str, values: dict[str, float] | None = None) -> str:
    """Build the inner HTML for a tooltip popup.

    DEPRECATED: Kept for backward compatibility. Use _build_tooltip_text()
    for plain-text tooltip content instead.
    """
    return _build_tooltip_text(key, values)
