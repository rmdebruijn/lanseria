"""
SVG Generators
--------------
Functions that generate SVG diagram strings from config data.
Each function is self-contained and returns a complete SVG string
suitable for embedding in Streamlit via st.markdown (unsafe_allow_html)
or writing directly to a .svg file.

Visual style follows the project's funding-structure.svg:
  - Background:  #F8FAFC rounded rect
  - Font:        'Segoe UI', Arial, sans-serif
  - Shadow:      feDropShadow dx=1 dy=2 stdDeviation=3 flood-opacity=0.12
  - Boxes:       white fill, #94A3B8 stroke 1.2px, 8px radius, shadow filter
  - Entity grad: linear vertical, white text
  - Headings:    #1E293B    Body: #64748B    Subtle: #94A3B8
  - Palette:     Navy #1E3A5F, Blue #2563EB, Gold #EAB308,
                 Brown #8B4513, Green #16a34a, Slate #64748B,
                 Purple #7C3AED
"""

from __future__ import annotations

from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Shared constants & helpers
# ---------------------------------------------------------------------------

FONT = "'Segoe UI', Arial, sans-serif"

# Standard SVG defs block reused across diagrams
_SHADOW_FILTER = (
    '<filter id="shadow" x="-4%" y="-4%" width="108%" height="112%">'
    '<feDropShadow dx="1" dy="2" stdDeviation="3" flood-opacity="0.12"/>'
    '</filter>'
)


def _fmt_eur(value: float) -> str:
    """Format a euro amount as EUR X.XM."""
    return f"\u20ac{value / 1_000_000:.1f}M"


def _fmt_rand_kwh(value: float) -> str:
    """Format a ZAR/kWh rate."""
    return f"R{value:.2f}/kWh"


def _fmt_int_comma(value: int) -> str:
    """Format an integer with thousands separators."""
    return f"{value:,}"


def _svg_open(viewbox: str, *, extra_defs: str = "") -> str:
    """Return the opening <svg> tag with standard defs."""
    w, h = viewbox.split("x")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}">\n'
        f'  <defs>\n'
        f'    {_SHADOW_FILTER}\n'
        f'{extra_defs}'
        f'  </defs>\n'
    )


def _bg_rect(w: int, h: int) -> str:
    """Background rounded rect in #F8FAFC."""
    return f'  <rect width="{w}" height="{h}" rx="12" fill="#F8FAFC"/>\n'


def _title(text: str, x: int, y: int, *, size: int = 16) -> str:
    """Centered title text in heading color."""
    return (
        f'  <text x="{x}" y="{y}" text-anchor="middle" '
        f'font-size="{size}" font-weight="700" fill="#1E293B">'
        f'{text}</text>\n'
    )


def _subtitle(text: str, x: int, y: int, *, size: int = 12) -> str:
    """Centered subtitle in body color."""
    return (
        f'  <text x="{x}" y="{y}" text-anchor="middle" '
        f'font-size="{size}" fill="#64748B">{text}</text>\n'
    )


def _white_box(x: int, y: int, w: int, h: int, *,
               stroke: str = "#94A3B8", stroke_w: float = 1.2,
               rx: int = 8, shadow: bool = True) -> str:
    """White rounded box with optional shadow."""
    filt = ' filter="url(#shadow)"' if shadow else ""
    return (
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="{rx}" fill="#FFFFFF" stroke="{stroke}" '
        f'stroke-width="{stroke_w}"{filt}/>\n'
    )


def _gradient_def(gid: str, top: str, bottom: str) -> str:
    """Return a linearGradient definition (top-to-bottom)."""
    return (
        f'    <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">\n'
        f'      <stop offset="0%" stop-color="{top}"/>\n'
        f'      <stop offset="100%" stop-color="{bottom}"/>\n'
        f'    </linearGradient>\n'
    )


# ---------------------------------------------------------------------------
# 1. Green Drop Compliance Trend
# ---------------------------------------------------------------------------

def generate_nwl_crisis_svg(trend_data: List[Dict]) -> str:
    """
    Green Drop Compliance Trend -- horizontal stacked bars showing
    worsening compliance over time.

    Parameters
    ----------
    trend_data : list of dict
        Each dict has keys:
            year        : int or str   -- year label (e.g. 2014)
            compliant_pct : float      -- percentage compliant (0-100)
            source      : str          -- data source note
            label       : str, optional -- extra label text

    Returns
    -------
    str : complete SVG string (viewBox 860x320)
    """
    VW, VH = 860, 320
    GREEN = "#16a34a"
    RED = "#ef4444"
    BAR_X = 120          # left edge of bars
    BAR_MAX_W = 580      # maximum bar width
    BAR_H = 30           # bar height
    GAP = 8              # vertical gap between bars
    TOP_Y = 60           # y of first bar

    n = len(trend_data)

    svg = _svg_open(f"{VW}x{VH}")
    svg += _bg_rect(VW, VH)
    svg += _title("Green Drop Compliance Trend", VW // 2, 32)

    for i, row in enumerate(trend_data):
        y = TOP_Y + i * (BAR_H + GAP)
        comp = row["compliant_pct"]
        non_comp = 100.0 - comp
        green_w = BAR_MAX_W * (comp / 100.0)
        red_w = BAR_MAX_W * (non_comp / 100.0)
        year_label = str(row.get("label", row["year"]))

        # Year label (left)
        svg += (
            f'  <text x="{BAR_X - 12}" y="{y + BAR_H // 2 + 5}" '
            f'text-anchor="end" font-size="13" font-weight="600" '
            f'fill="#1E293B">{year_label}</text>\n'
        )

        # Green bar (compliant)
        if green_w > 0:
            svg += (
                f'  <rect x="{BAR_X}" y="{y}" width="{green_w:.1f}" '
                f'height="{BAR_H}" rx="4" fill="{GREEN}" opacity="0.85"/>\n'
            )
            if comp >= 8:
                svg += (
                    f'  <text x="{BAR_X + green_w / 2}" y="{y + BAR_H // 2 + 5}" '
                    f'text-anchor="middle" font-size="11" font-weight="600" '
                    f'fill="#FFFFFF">{comp:.0f}%</text>\n'
                )

        # Red bar (non-compliant)
        if red_w > 0:
            rx_left = "0" if green_w > 0 else "4"
            svg += (
                f'  <rect x="{BAR_X + green_w:.1f}" y="{y}" '
                f'width="{red_w:.1f}" height="{BAR_H}" '
                f'rx="4" fill="{RED}" opacity="0.75"/>\n'
            )
            if non_comp >= 8:
                svg += (
                    f'  <text x="{BAR_X + green_w + red_w / 2:.1f}" '
                    f'y="{y + BAR_H // 2 + 5}" text-anchor="middle" '
                    f'font-size="11" font-weight="600" fill="#FFFFFF">'
                    f'{non_comp:.0f}%</text>\n'
                )

        # Source annotation (right of bar)
        src = row.get("source", "")
        if src:
            svg += (
                f'  <text x="{BAR_X + BAR_MAX_W + 10}" y="{y + BAR_H // 2 + 4}" '
                f'text-anchor="start" font-size="9" fill="#94A3B8">'
                f'{src}</text>\n'
            )

    # "Worsening" arrow annotation on the right side
    arrow_x = BAR_X + BAR_MAX_W + 90
    arrow_top = TOP_Y + 10
    arrow_bot = TOP_Y + n * (BAR_H + GAP) - GAP - 10
    arrow_mid = (arrow_top + arrow_bot) / 2

    svg += (
        f'  <line x1="{arrow_x}" y1="{arrow_top}" x2="{arrow_x}" '
        f'y2="{arrow_bot}" stroke="#ef4444" stroke-width="2" '
        f'marker-end="url(#arrowDown)"/>\n'
    )
    # Arrow marker definition (inline)
    svg += (
        f'  <defs><marker id="arrowDown" viewBox="0 0 10 10" '
        f'refX="5" refY="10" markerWidth="8" markerHeight="8" '
        f'orient="auto-start-reverse">'
        f'<path d="M0,0 L5,10 L10,0" fill="#ef4444"/>'
        f'</marker></defs>\n'
    )
    svg += (
        f'  <text x="{arrow_x + 8}" y="{arrow_mid + 4}" '
        f'font-size="11" font-weight="600" fill="#ef4444" '
        f'writing-mode="tb">Worsening</text>\n'
    )

    # Legend at bottom
    legend_y = TOP_Y + n * (BAR_H + GAP) + 20
    svg += (
        f'  <rect x="{BAR_X}" y="{legend_y}" width="14" height="14" '
        f'rx="3" fill="{GREEN}" opacity="0.85"/>\n'
        f'  <text x="{BAR_X + 20}" y="{legend_y + 12}" font-size="11" '
        f'fill="#64748B">Compliant</text>\n'
        f'  <rect x="{BAR_X + 110}" y="{legend_y}" width="14" height="14" '
        f'rx="3" fill="{RED}" opacity="0.75"/>\n'
        f'  <text x="{BAR_X + 134}" y="{legend_y + 12}" font-size="11" '
        f'fill="#64748B">Non-Compliant</text>\n'
    )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# 2. NWL Financing Risk Timeline
# ---------------------------------------------------------------------------

def generate_nwl_financing_svg(
    grants_eur: float,
    dsra_start: int,
    dsra_end: int,
    exposure_m36_eur: float,
    facility_eur: float,
    grace_end: int,
    maturity: int,
) -> str:
    """
    Frontier Funding Risk Timeline -- horizontal timeline with milestones,
    phases, and IIC exposure curve.

    Parameters
    ----------
    grants_eur       : float -- total grants in EUR (e.g. 3_236_004)
    dsra_start       : int   -- month DSRA protection starts (e.g. 24)
    dsra_end         : int   -- month DSRA protection ends (e.g. 36)
    exposure_m36_eur : float -- IIC balance at M36 in EUR
    facility_eur     : float -- total IIC facility in EUR
    grace_end        : int   -- end of grace period month (e.g. 24)
    maturity         : int   -- final maturity month (e.g. 120)

    Returns
    -------
    str : complete SVG string (viewBox 860x400)
    """
    VW, VH = 860, 400

    # Timeline geometry
    TL_Y = 160           # y-center of timeline bar
    TL_X0 = 80           # left edge
    TL_X1 = 780          # right edge
    TL_W = TL_X1 - TL_X0
    BAR_H = 28

    # Milestones as (month, label)
    milestones = [
        (0, "M0"), (12, "M12"), (dsra_start, f"M{dsra_start}"),
        (dsra_end, f"M{dsra_end}"), (maturity, f"M{maturity}"),
    ]
    # Remove duplicates preserving order
    seen = set()
    unique_ms = []
    for m, lbl in milestones:
        if m not in seen:
            seen.add(m)
            unique_ms.append((m, lbl))
    milestones = unique_ms

    def mx(month: int) -> float:
        """Map month to x-coordinate."""
        return TL_X0 + TL_W * (month / maturity)

    # Phase definitions: (start_month, end_month, color, label)
    phases = [
        (0, 12, "#94A3B8", "Construction"),
        (12, grace_end, "#60A5FA", "Grace Period"),
        (dsra_start, dsra_end, "#16a34a", "DSRA Protected"),
        (dsra_end, maturity, "#F1F5F9", "Revenue Service"),
    ]

    # Build SVG
    svg = _svg_open(f"{VW}x{VH}")
    svg += _bg_rect(VW, VH)
    svg += _title("Frontier Funding Risk Timeline", VW // 2, 32)

    # Subtitle
    svg += _subtitle(
        f"IIC Facility: {_fmt_eur(facility_eur)}  |  "
        f"NWL Senior IC  |  10-year amortisation",
        VW // 2, 54
    )

    # Phase bars
    for ms, me, color, label in phases:
        x0 = mx(ms)
        x1 = mx(me)
        pw = x1 - x0
        opacity = "0.25" if color == "#F1F5F9" else "0.65"
        stroke = "#94A3B8" if color == "#F1F5F9" else "none"
        svg += (
            f'  <rect x="{x0:.1f}" y="{TL_Y - BAR_H // 2}" '
            f'width="{pw:.1f}" height="{BAR_H}" rx="4" '
            f'fill="{color}" opacity="{opacity}" '
            f'stroke="{stroke}" stroke-width="0.8"/>\n'
        )
        # Phase label inside bar
        mid_x = (x0 + x1) / 2
        text_fill = "#FFFFFF" if color not in ("#F1F5F9",) else "#64748B"
        if pw > 60:
            svg += (
                f'  <text x="{mid_x:.1f}" y="{TL_Y + 5}" '
                f'text-anchor="middle" font-size="10" font-weight="600" '
                f'fill="{text_fill}">{label}</text>\n'
            )

    # Milestone ticks and labels
    for month, label in milestones:
        x = mx(month)
        svg += (
            f'  <line x1="{x:.1f}" y1="{TL_Y - BAR_H // 2 - 6}" '
            f'x2="{x:.1f}" y2="{TL_Y + BAR_H // 2 + 6}" '
            f'stroke="#1E293B" stroke-width="1.5"/>\n'
            f'  <text x="{x:.1f}" y="{TL_Y + BAR_H // 2 + 22}" '
            f'text-anchor="middle" font-size="11" font-weight="600" '
            f'fill="#1E293B">{label}</text>\n'
        )

    # Annotations above timeline
    # Grants at M12
    grants_x = mx(12)
    svg += _white_box(int(grants_x) - 70, 72, 140, 42)
    svg += (
        f'  <text x="{grants_x:.0f}" y="90" text-anchor="middle" '
        f'font-size="11" font-weight="700" fill="#16a34a">'
        f'{_fmt_eur(grants_eur)} Grants</text>\n'
        f'  <text x="{grants_x:.0f}" y="106" text-anchor="middle" '
        f'font-size="10" fill="#64748B">Accel at M12</text>\n'
    )
    # Arrow from annotation to timeline
    svg += (
        f'  <line x1="{grants_x:.0f}" y1="114" '
        f'x2="{grants_x:.0f}" y2="{TL_Y - BAR_H // 2 - 8}" '
        f'stroke="#16a34a" stroke-width="1.2" stroke-dasharray="4,3"/>\n'
    )

    # DSRA Covers annotation
    dsra_mid_x = (mx(dsra_start) + mx(dsra_end)) / 2
    svg += _white_box(int(dsra_mid_x) - 60, 72, 120, 42)
    svg += (
        f'  <text x="{dsra_mid_x:.0f}" y="90" text-anchor="middle" '
        f'font-size="11" font-weight="700" fill="#16a34a">'
        f'DSRA Covers</text>\n'
        f'  <text x="{dsra_mid_x:.0f}" y="106" text-anchor="middle" '
        f'font-size="10" fill="#64748B">'
        f'M{dsra_start}\u2013M{dsra_end}</text>\n'
    )
    svg += (
        f'  <line x1="{dsra_mid_x:.0f}" y1="114" '
        f'x2="{dsra_mid_x:.0f}" y2="{TL_Y - BAR_H // 2 - 8}" '
        f'stroke="#16a34a" stroke-width="1.2" stroke-dasharray="4,3"/>\n'
    )

    # Exposed IIC annotation at M36
    exp_x = mx(dsra_end)
    svg += _white_box(int(exp_x) + 10, 72, 140, 42)
    svg += (
        f'  <text x="{exp_x + 80:.0f}" y="90" text-anchor="middle" '
        f'font-size="11" font-weight="700" fill="#ef4444">'
        f'IIC First Exposed</text>\n'
        f'  <text x="{exp_x + 80:.0f}" y="106" text-anchor="middle" '
        f'font-size="10" fill="#64748B">'
        f'{_fmt_eur(exposure_m36_eur)} at M{dsra_end}</text>\n'
    )
    svg += (
        f'  <line x1="{exp_x:.0f}" y1="114" '
        f'x2="{exp_x:.0f}" y2="{TL_Y - BAR_H // 2 - 8}" '
        f'stroke="#ef4444" stroke-width="1.2" stroke-dasharray="4,3"/>\n'
    )

    # IIC Exposure curve below timeline
    curve_top = TL_Y + BAR_H // 2 + 40
    curve_bot = VH - 40
    curve_h = curve_bot - curve_top

    # Curve label
    svg += (
        f'  <text x="{TL_X0 - 5}" y="{curve_top + curve_h // 2 + 4}" '
        f'text-anchor="end" font-size="10" font-weight="600" '
        f'fill="#64748B">IIC</text>\n'
        f'  <text x="{TL_X0 - 5}" y="{curve_top + curve_h // 2 + 16}" '
        f'text-anchor="end" font-size="10" font-weight="600" '
        f'fill="#64748B">Balance</text>\n'
    )

    # Simple declining curve from M36 to maturity
    # Model as concave curve (faster repayment early)
    exp_x_start = mx(dsra_end)
    exp_x_end = mx(maturity)
    num_points = 20
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        px = exp_x_start + t * (exp_x_end - exp_x_start)
        # Quadratic decline: balance = exposure * (1-t)^1.5
        balance_frac = (1 - t) ** 1.5
        py = curve_top + curve_h * (1 - balance_frac)
        points.append(f"{px:.1f},{py:.1f}")

    # Area fill under curve
    svg += (
        f'  <polygon points="{exp_x_start:.1f},{curve_bot} '
        f'{" ".join(points)} {exp_x_end:.1f},{curve_bot}" '
        f'fill="#ef4444" opacity="0.12"/>\n'
    )
    # Curve line
    path_d = f"M{points[0]}"
    for p in points[1:]:
        path_d += f" L{p}"
    svg += (
        f'  <path d="{path_d}" fill="none" stroke="#ef4444" '
        f'stroke-width="2"/>\n'
    )

    # Start label on curve
    svg += (
        f'  <text x="{exp_x_start + 4:.0f}" y="{curve_top - 6}" '
        f'font-size="10" font-weight="600" fill="#ef4444">'
        f'{_fmt_eur(exposure_m36_eur)}</text>\n'
    )
    # End label
    svg += (
        f'  <text x="{exp_x_end:.0f}" y="{curve_bot - 6}" '
        f'text-anchor="middle" font-size="10" font-weight="600" '
        f'fill="#16a34a">\u20ac0</text>\n'
    )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# 3. LanRED Tariff Comparison
# ---------------------------------------------------------------------------

def generate_lanred_tariff_svg(
    eskom_rate: float,
    sc_discount_pct: float,
    solar_lcoe: float,
) -> str:
    """
    Tariff Comparison -- vertical bar chart comparing Eskom vs LanRED
    Smart City vs Solar LCOE.

    Parameters
    ----------
    eskom_rate      : float -- Eskom business tariff in R/kWh (e.g. 2.81)
    sc_discount_pct : float -- Smart City discount percentage (e.g. 10)
    solar_lcoe      : float -- Solar LCOE in R/kWh (e.g. 0.95)

    Returns
    -------
    str : complete SVG string (viewBox 700x380)
    """
    VW, VH = 700, 380

    lanred_rate = eskom_rate * (1 - sc_discount_pct / 100)

    # Chart area
    CHART_X = 100        # left edge of chart area
    CHART_Y = 60         # top of chart area
    CHART_W = 480        # chart width
    CHART_H = 220        # chart height
    CHART_BOT = CHART_Y + CHART_H

    # Y-axis: max value slightly above eskom_rate (for diesel ref line space)
    y_max = max(eskom_rate, solar_lcoe, lanred_rate) * 1.4

    def val_to_y(v: float) -> float:
        return CHART_BOT - (v / y_max) * CHART_H

    # Bars: 3 bars evenly spaced
    bar_w = 90
    bar_gap = (CHART_W - 3 * bar_w) / 4

    bars = [
        ("Eskom Business", eskom_rate, "#ef4444"),
        ("LanRED Smart City", lanred_rate, "#16a34a"),
        ("Solar LCOE", solar_lcoe, "#EAB308"),
    ]

    svg = _svg_open(f"{VW}x{VH}")
    svg += _bg_rect(VW, VH)
    svg += _title("Tariff Comparison", VW // 2, 32)
    svg += _subtitle("R/kWh at current rates", VW // 2, 50)

    # Y-axis
    svg += (
        f'  <line x1="{CHART_X}" y1="{CHART_Y}" '
        f'x2="{CHART_X}" y2="{CHART_BOT}" '
        f'stroke="#94A3B8" stroke-width="1"/>\n'
    )
    # Y-axis gridlines and labels
    n_ticks = 5
    for i in range(n_ticks + 1):
        val = y_max * i / n_ticks
        y = val_to_y(val)
        svg += (
            f'  <line x1="{CHART_X}" y1="{y:.1f}" '
            f'x2="{CHART_X + CHART_W}" y2="{y:.1f}" '
            f'stroke="#E2E8F0" stroke-width="0.8"/>\n'
            f'  <text x="{CHART_X - 8}" y="{y + 4:.1f}" '
            f'text-anchor="end" font-size="10" fill="#94A3B8">'
            f'R{val:.1f}</text>\n'
        )

    # X-axis baseline
    svg += (
        f'  <line x1="{CHART_X}" y1="{CHART_BOT}" '
        f'x2="{CHART_X + CHART_W}" y2="{CHART_BOT}" '
        f'stroke="#94A3B8" stroke-width="1"/>\n'
    )

    # Draw bars
    for idx, (label, value, color) in enumerate(bars):
        bx = CHART_X + bar_gap * (idx + 1) + bar_w * idx
        by = val_to_y(value)
        bh = CHART_BOT - by

        svg += (
            f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" '
            f'height="{bh:.1f}" rx="4" fill="{color}" opacity="0.8"/>\n'
        )
        # Value label above bar
        svg += (
            f'  <text x="{bx + bar_w / 2:.1f}" y="{by - 8:.1f}" '
            f'text-anchor="middle" font-size="12" font-weight="700" '
            f'fill="{color}">{_fmt_rand_kwh(value)}</text>\n'
        )
        # Label below bar
        # Split label into lines if too long
        parts = label.split(" ", 1)
        svg += (
            f'  <text x="{bx + bar_w / 2:.1f}" y="{CHART_BOT + 16}" '
            f'text-anchor="middle" font-size="11" font-weight="600" '
            f'fill="#1E293B">{parts[0]}</text>\n'
        )
        if len(parts) > 1:
            svg += (
                f'  <text x="{bx + bar_w / 2:.1f}" y="{CHART_BOT + 30}" '
                f'text-anchor="middle" font-size="11" fill="#64748B">'
                f'{parts[1]}</text>\n'
            )

    # Savings arrow between Eskom and LanRED bars
    eskom_bx = CHART_X + bar_gap + bar_w / 2
    lanred_bx = CHART_X + bar_gap * 2 + bar_w + bar_w / 2
    eskom_top = val_to_y(eskom_rate)
    lanred_top = val_to_y(lanred_rate)
    arrow_x = (eskom_bx + lanred_bx) / 2
    arrow_y1 = eskom_top + 10
    arrow_y2 = lanred_top - 5

    svg += (
        f'  <line x1="{arrow_x:.1f}" y1="{arrow_y1:.1f}" '
        f'x2="{arrow_x:.1f}" y2="{arrow_y2:.1f}" '
        f'stroke="#16a34a" stroke-width="2" stroke-dasharray="4,3"/>\n'
    )
    # Saving label
    saving_y = (arrow_y1 + arrow_y2) / 2
    svg += _white_box(int(arrow_x) - 42, int(saving_y) - 12, 84, 24, rx=6)
    svg += (
        f'  <text x="{arrow_x:.1f}" y="{saving_y + 4:.1f}" '
        f'text-anchor="middle" font-size="11" font-weight="700" '
        f'fill="#16a34a">{sc_discount_pct:.0f}% Saving</text>\n'
    )

    # Diesel reference line at top (truncated -- shown as dashed line)
    diesel_min = 50
    diesel_label_y = CHART_Y + 12
    svg += (
        f'  <line x1="{CHART_X}" y1="{CHART_Y + 4}" '
        f'x2="{CHART_X + CHART_W}" y2="{CHART_Y + 4}" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="6,4"/>\n'
        f'  <text x="{CHART_X + CHART_W + 6}" y="{CHART_Y + 8}" '
        f'font-size="9" fill="#DC2626" font-weight="600">'
        f'Diesel Backup</text>\n'
        f'  <text x="{CHART_X + CHART_W + 6}" y="{CHART_Y + 20}" '
        f'font-size="9" fill="#DC2626">'
        f'R50\u2013150/kWh</text>\n'
    )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# 4. TWX Housing Delivery Gap
# ---------------------------------------------------------------------------

def generate_twx_velocity_svg(
    annual_need: int,
    annual_delivered: int,
    backlog: int,
) -> str:
    """
    Housing Delivery Gap -- horizontal bar comparison.

    Parameters
    ----------
    annual_need      : int -- houses needed per year (e.g. 178000)
    annual_delivered : int -- houses delivered per year (e.g. 80000)
    backlog          : int -- total backlog units (e.g. 2_400_000)

    Returns
    -------
    str : complete SVG string (viewBox 860x300)
    """
    VW, VH = 860, 300
    gap = annual_need - annual_delivered

    BAR_X = 200
    BAR_MAX_W = 500
    BAR_H = 44
    BAR_GAP = 20
    TOP_Y = 70

    max_val = annual_need  # normalize to the largest value

    items = [
        ("Needed / Year", annual_need, "#ef4444"),
        ("Delivered / Year", annual_delivered, "#16a34a"),
        ("Gap / Year", gap, "#f59e0b"),
    ]

    svg = _svg_open(f"{VW}x{VH}")
    svg += _bg_rect(VW, VH)
    svg += _title("Housing Delivery Gap", VW // 2, 32)
    svg += _subtitle("South Africa national housing crisis", VW // 2, 50)

    for i, (label, value, color) in enumerate(items):
        y = TOP_Y + i * (BAR_H + BAR_GAP)
        bw = BAR_MAX_W * (value / max_val) if max_val > 0 else 0

        # Label (left)
        svg += (
            f'  <text x="{BAR_X - 14}" y="{y + BAR_H // 2 + 5}" '
            f'text-anchor="end" font-size="13" font-weight="600" '
            f'fill="#1E293B">{label}</text>\n'
        )

        # Bar
        svg += (
            f'  <rect x="{BAR_X}" y="{y}" width="{bw:.1f}" '
            f'height="{BAR_H}" rx="6" fill="{color}" opacity="0.8" '
            f'filter="url(#shadow)"/>\n'
        )

        # Value inside bar
        formatted = _fmt_int_comma(value)
        text_x = BAR_X + bw / 2 if bw > 120 else BAR_X + bw + 10
        anchor = "middle" if bw > 120 else "start"
        text_color = "#FFFFFF" if bw > 120 else color
        svg += (
            f'  <text x="{text_x:.1f}" y="{y + BAR_H // 2 + 6}" '
            f'text-anchor="{anchor}" font-size="14" font-weight="700" '
            f'fill="{text_color}">{formatted}</text>\n'
        )

    # Backlog callout box
    callout_x = BAR_X + BAR_MAX_W - 200
    callout_y = TOP_Y + 3 * (BAR_H + BAR_GAP) + 10
    svg += _white_box(callout_x, callout_y, 240, 44,
                      stroke="#ef4444", stroke_w=1.5)

    backlog_fmt = f"{backlog / 1_000_000:.1f}M" if backlog >= 1_000_000 else _fmt_int_comma(backlog)
    svg += (
        f'  <text x="{callout_x + 120}" y="{callout_y + 18}" '
        f'text-anchor="middle" font-size="11" fill="#64748B">'
        f'National Backlog</text>\n'
        f'  <text x="{callout_x + 120}" y="{callout_y + 36}" '
        f'text-anchor="middle" font-size="14" font-weight="700" '
        f'fill="#ef4444">{backlog_fmt} units</text>\n'
    )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# 5. TWX JV Partnership Structure
# ---------------------------------------------------------------------------

def generate_twx_jv_svg() -> str:
    """
    JV Partnership Structure -- organizational diagram showing Timberworx
    at the center connected to its ecosystem partners.

    Returns
    -------
    str : complete SVG string (viewBox 800x400)
    """
    VW, VH = 800, 400

    extra_defs = (
        _gradient_def("gradTWX", "#8B4513", "#6B3410")
        + _gradient_def("gradPartner", "#F8FAFC", "#EFF6FF")
    )

    svg = _svg_open(f"{VW}x{VH}", extra_defs=extra_defs)
    svg += _bg_rect(VW, VH)
    svg += _title("JV Partnership Structure", VW // 2, 32)

    # Central node: Timberworx
    cx, cy = VW // 2, VH // 2
    cw, ch = 180, 60
    svg += (
        f'  <rect x="{cx - cw // 2}" y="{cy - ch // 2}" '
        f'width="{cw}" height="{ch}" rx="10" '
        f'fill="url(#gradTWX)" filter="url(#shadow)"/>\n'
        f'  <text x="{cx}" y="{cy + 2}" text-anchor="middle" '
        f'font-size="16" font-weight="700" fill="#FFFFFF">'
        f'Timberworx</text>\n'
        f'  <text x="{cx}" y="{cy + 18}" text-anchor="middle" '
        f'font-size="10" fill="#FBBF24">'
        f'Panel Fabrication</text>\n'
    )

    # Partner nodes: (x, y, name, subtitle, connection_label)
    partners = [
        (160, 100,  "BG&E (SYSTRA)", "EPC Design & QA", "Design"),
        (640, 100,  "Greenblock.co.za", "On-Site Assembly", "Assembly"),
        (100, 290,  "Finnish Timber JV", "Material Supply", "Timber"),
        (700, 290,  "Offtakers", "NBI, DBSA, GEPF", "Demand"),
    ]

    pw, ph = 160, 54  # partner box size

    for px, py, name, sub, conn_label in partners:
        # Partner box
        svg += (
            f'  <rect x="{px - pw // 2}" y="{py - ph // 2}" '
            f'width="{pw}" height="{ph}" rx="8" '
            f'fill="#FFFFFF" stroke="#94A3B8" stroke-width="1.2" '
            f'filter="url(#shadow)"/>\n'
            f'  <text x="{px}" y="{py - 2}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#1E293B">'
            f'{name}</text>\n'
            f'  <text x="{px}" y="{py + 14}" text-anchor="middle" '
            f'font-size="10" fill="#64748B">{sub}</text>\n'
        )

        # Connection line from partner to center
        # Calculate edge points
        dx = cx - px
        dy = cy - py
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist == 0:
            continue

        # Start from partner edge
        nx, ny = dx / dist, dy / dist
        sx = px + nx * (pw // 2 + 4)
        sy = py + ny * (ph // 2 + 4)
        # End at center edge
        ex = cx - nx * (cw // 2 + 4)
        ey = cy - ny * (ch // 2 + 4)

        svg += (
            f'  <line x1="{sx:.1f}" y1="{sy:.1f}" '
            f'x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="#94A3B8" stroke-width="1.5" '
            f'stroke-dasharray="6,4"/>\n'
        )

        # Connection label at midpoint
        mx_pt = (sx + ex) / 2
        my_pt = (sy + ey) / 2
        # Offset label slightly perpendicular to line
        perp_x = -ny * 14
        perp_y = nx * 14
        svg += (
            f'  <text x="{mx_pt + perp_x:.1f}" y="{my_pt + perp_y:.1f}" '
            f'text-anchor="middle" font-size="9" font-weight="600" '
            f'fill="#8B4513">{conn_label}</text>\n'
        )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# 6. Lanseria DevCo Divisions
# ---------------------------------------------------------------------------

def generate_devco_divisions_svg(divisions: List[Dict]) -> str:
    """
    Lanseria DevCo Divisions -- hierarchical org chart showing
    DevCo -> SCLCA -> subsidiary divisions.

    Parameters
    ----------
    divisions : list of dict
        Each dict has keys:
            name        : str  -- division name (e.g. "NWL")
            subtitle    : str  -- short description
            color       : str  -- hex color for gradient top
            description : str, optional -- capacity or extra info

    Returns
    -------
    str : complete SVG string (viewBox 900x420)
    """
    VW, VH = 900, 420

    # Pre-compute darker version of each color for gradient bottom
    def darken(hex_color: str) -> str:
        """Simple darkening: reduce each channel by ~20%."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        factor = 0.78
        r2 = max(0, int(r * factor))
        g2 = max(0, int(g * factor))
        b2 = max(0, int(b * factor))
        return f"#{r2:02x}{g2:02x}{b2:02x}"

    # Build gradient defs for each division
    extra_defs = _gradient_def("gradDevCo", "#0F172A", "#1E293B")
    extra_defs += _gradient_def("gradSCLCA", "#1E3A5F", "#162D4A")
    for i, div in enumerate(divisions):
        c = div["color"]
        extra_defs += _gradient_def(f"gradDiv{i}", c, darken(c))

    svg = _svg_open(f"{VW}x{VH}", extra_defs=extra_defs)
    svg += _bg_rect(VW, VH)

    # DevCo box at top
    dc_w, dc_h = 260, 52
    dc_x = (VW - dc_w) // 2
    dc_y = 20
    svg += (
        f'  <rect x="{dc_x}" y="{dc_y}" width="{dc_w}" height="{dc_h}" '
        f'rx="10" fill="url(#gradDevCo)" filter="url(#shadow)"/>\n'
        f'  <text x="{VW // 2}" y="{dc_y + 22}" text-anchor="middle" '
        f'font-size="15" font-weight="700" fill="#FFFFFF">'
        f'Lanseria DevCo</text>\n'
        f'  <text x="{VW // 2}" y="{dc_y + 40}" text-anchor="middle" '
        f'font-size="10" fill="#93C5FD">'
        f'Development Company</text>\n'
    )

    # Connector from DevCo to SCLCA
    sclca_w, sclca_h = 300, 52
    sclca_x = (VW - sclca_w) // 2
    sclca_y = dc_y + dc_h + 36
    mid_connector_y = dc_y + dc_h

    svg += (
        f'  <line x1="{VW // 2}" y1="{mid_connector_y}" '
        f'x2="{VW // 2}" y2="{sclca_y}" '
        f'stroke="#64748B" stroke-width="1.8"/>\n'
    )

    # SCLCA box
    svg += (
        f'  <rect x="{sclca_x}" y="{sclca_y}" width="{sclca_w}" '
        f'height="{sclca_h}" rx="10" fill="url(#gradSCLCA)" '
        f'filter="url(#shadow)"/>\n'
        f'  <text x="{VW // 2}" y="{sclca_y + 20}" text-anchor="middle" '
        f'font-size="11" fill="#93C5FD">Smart City Lanseria</text>\n'
        f'  <text x="{VW // 2}" y="{sclca_y + 38}" text-anchor="middle" '
        f'font-size="14" font-weight="700" fill="#FFFFFF">'
        f'Catalytic Assets</text>\n'
    )

    # Division boxes
    n = len(divisions)
    div_w = 120
    div_h = 80
    total_divs_w = n * div_w + (n - 1) * 12  # 12px gap between boxes
    div_start_x = (VW - total_divs_w) / 2
    div_y = sclca_y + sclca_h + 60

    # Horizontal connector bar from SCLCA
    bar_y = sclca_y + sclca_h + 30
    svg += (
        f'  <line x1="{VW // 2}" y1="{sclca_y + sclca_h}" '
        f'x2="{VW // 2}" y2="{bar_y}" '
        f'stroke="#64748B" stroke-width="1.8"/>\n'
    )

    # Calculate x positions for each division
    div_positions = []
    for i in range(n):
        x = div_start_x + i * (div_w + 12) + div_w / 2
        div_positions.append(x)

    # Horizontal bar connecting all vertical lines
    if n > 1:
        svg += (
            f'  <line x1="{div_positions[0]:.1f}" y1="{bar_y}" '
            f'x2="{div_positions[-1]:.1f}" y2="{bar_y}" '
            f'stroke="#64748B" stroke-width="1.8"/>\n'
        )

    # Draw each division
    for i, div in enumerate(divisions):
        dx = div_positions[i]

        # Vertical connector from bar to division box
        svg += (
            f'  <line x1="{dx:.1f}" y1="{bar_y}" '
            f'x2="{dx:.1f}" y2="{div_y}" '
            f'stroke="#64748B" stroke-width="1.2"/>\n'
        )

        # Division box with gradient
        bx = dx - div_w / 2
        svg += (
            f'  <rect x="{bx:.1f}" y="{div_y}" width="{div_w}" '
            f'height="{div_h}" rx="8" fill="url(#gradDiv{i})" '
            f'filter="url(#shadow)"/>\n'
        )

        # Name
        svg += (
            f'  <text x="{dx:.1f}" y="{div_y + 22}" text-anchor="middle" '
            f'font-size="13" font-weight="700" fill="#FFFFFF">'
            f'{div["name"]}</text>\n'
        )

        # Subtitle
        svg += (
            f'  <text x="{dx:.1f}" y="{div_y + 40}" text-anchor="middle" '
            f'font-size="9" fill="rgba(255,255,255,0.8)">'
            f'{div["subtitle"]}</text>\n'
        )

        # Description (optional)
        desc = div.get("description", "")
        if desc:
            # Wrap long descriptions
            if len(desc) > 18:
                parts = desc.split(" ", 1)
                svg += (
                    f'  <text x="{dx:.1f}" y="{div_y + 56}" '
                    f'text-anchor="middle" font-size="8" '
                    f'fill="rgba(255,255,255,0.65)">{parts[0]}</text>\n'
                )
                if len(parts) > 1:
                    svg += (
                        f'  <text x="{dx:.1f}" y="{div_y + 67}" '
                        f'text-anchor="middle" font-size="8" '
                        f'fill="rgba(255,255,255,0.65)">{parts[1]}</text>\n'
                    )
            else:
                svg += (
                    f'  <text x="{dx:.1f}" y="{div_y + 58}" '
                    f'text-anchor="middle" font-size="9" '
                    f'fill="rgba(255,255,255,0.65)">{desc}</text>\n'
                )

    svg += '</svg>'
    return svg


# ---------------------------------------------------------------------------
# Convenience: render all diagrams with sample data (for testing)
# ---------------------------------------------------------------------------

def _sample_all() -> Dict[str, str]:
    """Generate all SVGs with representative sample data. For testing only."""

    results = {}

    # 1. Green Drop Compliance Trend
    results["nwl_crisis"] = generate_nwl_crisis_svg([
        {"year": 2014, "compliant_pct": 73, "source": "DWS Green Drop"},
        {"year": 2016, "compliant_pct": 60, "source": "DWS Green Drop"},
        {"year": 2019, "compliant_pct": 48, "source": "DWS Green Drop"},
        {"year": 2022, "compliant_pct": 39, "source": "DWS Green Drop"},
        {"year": 2023, "compliant_pct": 28, "source": "DWS Estimate"},
    ])

    # 2. NWL Financing Risk Timeline
    results["nwl_financing"] = generate_nwl_financing_svg(
        grants_eur=3_236_004,
        dsra_start=24,
        dsra_end=36,
        exposure_m36_eur=7_200_000,
        facility_eur=13_597_304,
        grace_end=24,
        maturity=120,
    )

    # 3. LanRED Tariff Comparison
    results["lanred_tariff"] = generate_lanred_tariff_svg(
        eskom_rate=2.81,
        sc_discount_pct=10,
        solar_lcoe=0.95,
    )

    # 4. TWX Housing Delivery Gap
    results["twx_velocity"] = generate_twx_velocity_svg(
        annual_need=178_000,
        annual_delivered=80_000,
        backlog=2_400_000,
    )

    # 5. TWX JV Partnership Structure
    results["twx_jv"] = generate_twx_jv_svg()

    # 6. Lanseria DevCo Divisions
    results["devco_divisions"] = generate_devco_divisions_svg([
        {"name": "NWL", "subtitle": "Water & Reuse",
         "color": "#2563EB", "description": "2 MLD Capacity"},
        {"name": "LanRED", "subtitle": "Renewable Energy",
         "color": "#EAB308", "description": "2.4 MWp Solar"},
        {"name": "Timberworx", "subtitle": "Modular Housing",
         "color": "#8B4513", "description": "52 houses/yr"},
        {"name": "IWMSA", "subtitle": "Waste Management",
         "color": "#16a34a", "description": "Circular Economy"},
        {"name": "Cradle Cloud", "subtitle": "Smart City IoT",
         "color": "#7C3AED", "description": "Data Platform"},
        {"name": "LLC", "subtitle": "Land & Property",
         "color": "#64748B", "description": "Precinct Mgmt"},
    ])

    return results


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "output", "svg_test")
    os.makedirs(out_dir, exist_ok=True)

    samples = _sample_all()
    for name, svg_str in samples.items():
        path = os.path.join(out_dir, f"{name}.svg")
        with open(path, "w") as f:
            f.write(svg_str)
        print(f"  Wrote {path}")

    print(f"\nGenerated {len(samples)} SVG diagrams in {out_dir}")
