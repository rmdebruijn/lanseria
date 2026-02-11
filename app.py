#!/usr/bin/env python3
"""
SCLCA Financial Model - Streamlit GUI
-------------------------------------
Catalytic Assets (Smart City Lanseria)
Financial holding company model: Sources → Uses

Run with: streamlit run app.py
"""

import streamlit as st
import json
import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import math
import yaml
import streamlit_authenticator as stauth

# Config directory
CONFIG_DIR = Path(__file__).parent / "config"
LOGO_DIR = Path(__file__).parent / "assets" / "logos"

# Load project config for model parameters
@st.cache_data(ttl=300)
def _load_project_params():
    with open(CONFIG_DIR / "project.json", 'r') as f:
        proj = json.load(f)
    params = proj.get('model_parameters', {})
    fx = proj['project']['fx_rates']['EUR_ZAR']
    eq = params.get('equity_in_subsidiaries', {})
    return {
        'ic_margin': params.get('intercompany_margin', 0.005),
        'dsra_rate': params.get('dsra_rate', 0.09),
        'fx_rate': fx,
        'eq_nwl': eq.get('nwl_pct', 0.93) * eq.get('nwl_base_zar', 1000000) / fx,
        'eq_lanred': eq.get('lanred_pct', 1.0) * eq.get('lanred_base_zar', 1000000) / fx,
        'eq_twx': eq.get('timberworx_pct', 0.05) * eq.get('timberworx_base_zar', 1000000) / fx,
    }

_MODEL_PARAMS = _load_project_params()

# Constants (from config)
INTERCOMPANY_MARGIN = _MODEL_PARAMS['ic_margin']
DSRA_RATE = _MODEL_PARAMS['dsra_rate']
FX_RATE = _MODEL_PARAMS['fx_rate']
EQUITY_NWL = _MODEL_PARAMS['eq_nwl']
EQUITY_LANRED = _MODEL_PARAMS['eq_lanred']
EQUITY_TWX = _MODEL_PARAMS['eq_twx']
EQUITY_TOTAL = EQUITY_NWL + EQUITY_LANRED + EQUITY_TWX

# Entity logo mapping
ENTITY_LOGOS = {
    "sclca": "lanseria-smart-city-logo.png",
    "nwl": "nwl-logo.png",
    "lanred": "lanred-logo.png",
    "timberworx": "timberworx-logo.png",
    "invest_international": "invest-international-logo.svg",
    "creation_capital": "creation-capital-logo.png",
    "crosspoint": "crosspoint-logo.png",
    "vansquare": "vansquare-logo.png",
    "colubris": "colubris-logo.svg",
    "oxymem": "oxymem-logo.png",
    "optimat": "optimat-logo.jpg",
    "basilicus": "basilicus-logo.png",
    "titanium": "titanium-logo.png",
}


@st.cache_data(ttl=300)
def load_config(name: str) -> dict:
    """Load a JSON config file (cached 5 min)."""
    path = CONFIG_DIR / f"{name}.json"
    with open(path, 'r') as f:
        return json.load(f)


@st.cache_data(ttl=3600)
def load_about_content() -> dict:
    """Load ABOUT tabs content from markdown file (cached 1 hour)."""
    model_dir = Path(__file__).parent
    about_file = model_dir / "content" / "ABOUT_TABS_CONTENT.md"
    if not about_file.exists():
        return {}

    with open(about_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse the markdown file into sections
    sections = {}
    current_section = None
    current_content = []

    for line in content.split('\n'):
        # Check for entity section headers (## 1. ABOUT: ...)
        if line.startswith('## ') and 'ABOUT:' in line:
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_content)

            # Extract entity name
            if 'New Water Lanseria' in line or 'NWL' in line:
                current_section = 'nwl'
            elif 'LanRED' in line:
                current_section = 'lanred'
            elif 'Timberworx' in line or 'TWX' in line:
                current_section = 'timberworx'
            elif 'Smart City Lanseria Catalytic Assets' in line or 'SCLCA' in line:
                current_section = 'sclca'
            elif 'Smart City Lanseria' in line and 'Parent' in line:
                current_section = 'smart_city'
            else:
                current_section = None

            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = '\n'.join(current_content)

    return sections


@st.cache_data(ttl=3600)
def load_content_md(filename: str) -> dict:
    """Load a content MD file from 11. Financial Model/ and parse into entity sections.

    Files use the pattern:  ## TABNAME: EntityKey  (e.g. ## OVERVIEW: NWL)
    Returns dict mapping lowercase entity keys to their markdown content.
    Sub-sections (### heading) are preserved as-is within each entity block.
    """
    model_dir = Path(__file__).parent
    md_file = model_dir / "content" / filename
    if not md_file.exists():
        return {}

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = {}
    current_section = None
    current_content = []
    _key_map = {
        'nwl': 'nwl', 'lanred': 'lanred', 'timberworx': 'timberworx',
        'twx': 'timberworx', 'sclca': 'sclca', 'sclca corporate': 'sclca',
    }

    for line in content.split('\n'):
        if line.startswith('## ') and ':' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            # Parse "## OVERVIEW: NWL" → key = "nwl"
            _, _, raw_key = line.partition(':')
            raw_key = raw_key.strip().lower()
            current_section = _key_map.get(raw_key, raw_key)
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def _parse_svg_content_md(filename: str) -> dict:
    """Parse an SVG content MD file into id→text mapping.

    Files use the pattern:  ## element_id\\nText value
    Returns dict mapping element IDs to their text content.
    """
    model_dir = Path(__file__).parent
    md_file = model_dir / "content" / filename
    if not md_file.exists():
        return {}
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    mapping = {}
    current_id = None
    for line in content.split('\n'):
        if line.startswith('## ') and not line.startswith('## #'):
            current_id = line[3:].strip()
        elif current_id and line.strip() and not line.startswith('**') and not line.startswith('---'):
            mapping[current_id] = line.strip()
            current_id = None
    return mapping


import re as _re
import html as _html_mod

def load_svg_patched(svg_filename: str, md_filename: str) -> str:
    """Load an SVG and patch text elements using content from an MD file.

    Returns SVG string with text content replaced, or empty string if file missing.
    """
    model_dir = Path(__file__).parent
    svg_path = model_dir / "assets" / svg_filename
    if not svg_path.exists():
        return ""
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg = f.read()
    mapping = _parse_svg_content_md(md_filename)
    if not mapping:
        return svg
    for elem_id, new_text in mapping.items():
        escaped = _html_mod.escape(new_text)
        pattern = _re.compile(
            r'(<text\b[^>]*\bid="' + _re.escape(elem_id) + r'"[^>]*>)([^<]*)(</text>)'
        )
        svg = pattern.sub(r'\g<1>' + escaped + r'\3', svg)
    return svg


def render_svg(svg_filename: str, md_filename: str):
    """Load, patch, and render an SVG diagram with editable text from MD."""
    import streamlit.components.v1 as _stc
    svg = load_svg_patched(svg_filename, md_filename)
    if svg:
        # Extract viewBox to calculate proper height
        _vb_match = _re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
        _height = 800  # fallback
        if _vb_match:
            _vb_w, _vb_h = int(_vb_match.group(1)), int(_vb_match.group(2))
            _height = int(_vb_h / _vb_w * 1100) + 60  # scale to ~1100px wide container + padding
        # Inject width/height into the SVG root to ensure it fills the container
        svg = svg.replace('<svg ', '<svg width="100%" ', 1)
        _stc.html(f'<div style="width:100%;overflow:visible;">{svg}</div>',
                  height=_height, scrolling=False)


def _render_logo_dark_bg(logo_path, width=100):
    """Render a logo on a dark rounded background (for white-on-transparent logos)."""
    import base64
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f'<div style="background:#1F2937;border-radius:8px;padding:10px;display:inline-block;">'
        f'<img src="data:image/png;base64,{b64}" width="{width}"></div>',
        unsafe_allow_html=True,
    )


def _md_to_html(text: str) -> str:
    """Convert simple markdown bold/italic to HTML."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    return text


def render_table(df: pd.DataFrame, formats: dict | None = None,
                 right_align: list[str] | None = None):
    """Render dataframe with formatting, right-aligned numeric columns.

    Numeric/formatted columns are right-aligned. Supports **bold** and *italic*
    markdown in cell values. Scrollable horizontally for wide tables.

    Args:
        formats: dict of {col: fmt_string} for numeric formatting + right-align.
        right_align: list of column names to right-align (for pre-formatted strings).
    """
    df_display = df.copy()
    right_cols: set[str] = set()
    if formats:
        for col, fmt in formats.items():
            if col in df_display.columns:
                right_cols.add(col)
                df_display[col] = df_display[col].apply(
                    lambda x, f=fmt: f.format(x) if pd.notna(x) and not isinstance(x, str) else x
                )
    if right_align:
        for col in right_align:
            if col in df_display.columns:
                right_cols.add(col)

    # If no formatted columns, fall back to plain st.table
    if not right_cols:
        st.table(df_display)
        return

    # Build HTML table with right-alignment, markdown support, and scroll wrapper
    html_parts = [
        '<div style="overflow-x: auto; width: 100%;">',
        '<table style="border-collapse: collapse; width: 100%; font-size: 13px; white-space: nowrap;">',
        '<thead><tr>',
    ]
    for col in df_display.columns:
        align = 'right' if col in right_cols else 'left'
        html_parts.append(
            f'<th style="text-align: {align}; padding: 5px 8px; '
            f'border-bottom: 2px solid #ddd; font-weight: 600;">{col}</th>'
        )
    html_parts.append('</tr></thead><tbody>')
    for _, row in df_display.iterrows():
        html_parts.append('<tr>')
        for col in df_display.columns:
            align = 'right' if col in right_cols else 'left'
            val = row[col]
            cell = str(val) if pd.notna(val) else ''
            cell = _md_to_html(cell)
            # Bold rows get slightly different styling
            weight = 'font-weight: 600;' if '<b>' in cell else ''
            html_parts.append(
                f'<td style="text-align: {align}; padding: 4px 8px; '
                f'border-bottom: 1px solid #eee; {weight}">{cell}</td>'
            )
        html_parts.append('</tr>')
    html_parts.append('</tbody></table></div>')
    st.markdown(''.join(html_parts), unsafe_allow_html=True)


def _render_fin_table(rows: list[tuple], columns: list[str]):
    """Render financial table: first col left-aligned, rest right-aligned, markdown bold/italic."""
    html = ['<div style="overflow-x:auto;width:100%;">',
            '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
            '<thead><tr>']
    for i, col in enumerate(columns):
        align = 'left' if i == 0 else 'right'
        html.append(f'<th style="text-align:{align};padding:5px 8px;border-bottom:2px solid #ddd;font-weight:600;">{col}</th>')
    html.append('</tr></thead><tbody>')
    for row in rows:
        html.append('<tr>')
        for i, val in enumerate(row):
            align = 'left' if i == 0 else 'right'
            cell = _md_to_html(str(val)) if val else ''
            weight = 'font-weight:600;' if '<b>' in cell else ''
            html.append(f'<td style="text-align:{align};padding:4px 8px;border-bottom:1px solid #eee;{weight}">{cell}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    st.markdown(''.join(html), unsafe_allow_html=True)


_eur_fmt = "€{:,.0f}"


def _asset_life_years(delivery: str, category: str) -> int:
    delivery_l = (delivery or "").lower()
    category_l = (category or "").lower()
    if "mabr" in delivery_l:
        return 10
    if "balance of plant" in delivery_l or "civils" in delivery_l or "owners engineer" in delivery_l:
        return 20
    if "solar" in delivery_l:
        return 25
    if "battery" in delivery_l or "bess" in delivery_l or "li-ion" in delivery_l:
        return 10
    if "panel equipment" in delivery_l or "panel machine" in delivery_l:
        return 10
    if "centre of excellence" in delivery_l or "center of excellence" in delivery_l:
        return 20
    if category_l in {"water", "solar", "coe"}:
        return 20
    return 20


def _compute_entity_content(entity_key: str) -> tuple:
    """Compute country-wise content breakdown for an entity.

    Returns (country_totals: dict, grand_total: float) where country_totals
    maps country name to EUR amount, covering assets + fees + IDC.
    Handles multi-country content_split on asset line items (e.g. CoE building).
    """
    _entity_map = {
        "nwl": {"assets": ["water"], "services": ["esg"]},
        "lanred": {"assets": ["solar"], "services": []},
        "timberworx": {"assets": ["coe"], "services": []},
    }
    _cfg = _entity_map.get(entity_key, {"assets": [], "services": []})
    _assets = load_config("assets")["assets"]
    _fees = load_config("fees")
    _entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
    _entity_sr = _entity_data['senior_portion']
    _entity_total = _entity_data['senior_portion'] + _entity_data['mezz_portion']
    _project_debt = structure['sources']['senior_debt']['amount']

    _cost_rows = []

    # 1. Asset line items
    for _ak in _cfg["assets"] + _cfg["services"]:
        _asset_data = _assets.get(_ak, {})
        for _li in _asset_data.get('line_items', []):
            _split = _li.get('content_split')
            if _split:
                for _country, _pct in _split.items():
                    _cost_rows.append({"country": _country, "amount": _li['budget'] * _pct})
            else:
                _cost_rows.append({"country": _li['country'], "amount": _li['budget']})

    # 2. Fees
    for _fee in _fees.get("fees", []):
        # Skip toggled-off ECA fees
        _fid = _fee.get("id", "")
        if _fid == "fee_003" and not _state_bool(f"{entity_key}_eca_atradius", _eca_default(entity_key)):
            continue
        if _fid == "fee_004" and not _state_bool(f"{entity_key}_eca_exporter", _eca_default(entity_key)):
            continue
        if _fee.get("funding") == "senior_only":
            _base = _entity_sr
        else:
            _base = _entity_total
        _amt = _base * _fee.get("rate", 0)
        _cost_rows.append({"country": _fee['country'], "amount": _amt})

    # 3. IDC (Senior IC) — Netherlands (Invest International)
    _sr_rate_fac = structure['sources']['senior_debt']['interest']['rate']
    _sr_ic_rate = _sr_rate_fac + INTERCOMPANY_MARGIN
    _project_idc = financing['loan_detail']['senior']['rolled_up_interest_idc']
    _ic_idc = _project_idc * (_sr_ic_rate / _sr_rate_fac) if _sr_rate_fac > 0 else _project_idc
    _entity_share = _entity_sr / _project_debt if _project_debt > 0 else 0
    _entity_idc = _ic_idc * _entity_share
    _cost_rows.append({"country": "Netherlands", "amount": _entity_idc})

    # Aggregate
    _country_totals = {}
    for _cr in _cost_rows:
        _c = _cr['country']
        if _c and _c != "Other":
            _country_totals[_c] = _country_totals.get(_c, 0.0) + _cr['amount']
    _grand_total = sum(_country_totals.values())
    return _country_totals, _grand_total


def _build_entity_asset_base(entity_key: str, assets_cfg: dict) -> dict:
    """Build assets + services allocation for an entity (no fees)."""
    entity_map = {
        "nwl": {"assets": ["water"], "services": ["esg"]},
        "lanred": {"assets": ["solar"], "services": []},
        "timberworx": {"assets": ["coe"], "services": []},
    }
    cfg = entity_map.get(entity_key, {"assets": [], "services": []})

    service_items = []
    asset_items = []
    for cat in cfg["assets"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            delivery = item.get("delivery", "")
            if cat == "water" and "owners engineer" in (delivery or "").lower():
                service_items.append({
                    "id": item.get("id", ""),
                    "service": delivery or item.get("company", "Service"),
                    "cost": float(item.get("budget", 0)),
                })
                continue
            asset_items.append({
                "id": item.get("id", ""),
                "category": cat,
                "asset": delivery or item.get("company", "Asset"),
                "base_cost": float(item.get("budget", 0)),
            })

    for cat in cfg["services"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            service_items.append({
                "id": item.get("id", ""),
                "service": item.get("delivery", item.get("company", "Service")),
                "cost": float(item.get("budget", 0)),
            })

    service_total = sum(s["cost"] for s in service_items)
    base_total = sum(a["base_cost"] for a in asset_items)

    for a in asset_items:
        share = (a["base_cost"] / base_total) if base_total else 0
        a["alloc_services"] = service_total * share
        a["alloc_fees"] = 0.0
        a["depr_base"] = a["base_cost"] + a["alloc_services"]
        a["life"] = _asset_life_years(a["asset"], a["category"])
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0

    fee_base = sum(a["depr_base"] for a in asset_items)

    return {
        "assets": asset_items,
        "services": service_items,
        "service_total": service_total,
        "base_total": base_total,
        "fee_base": fee_base,
    }


def compute_project_fees(fees_cfg: dict, project_debt_base: float, project_capex_base: float) -> dict:
    """Compute project-level fees from bases: debt = senior facility, capex = project capex."""
    fee_rows = []
    for fee in fees_cfg.get("fees", []):
        basis = fee.get("rate_basis", "")
        if basis == "debt":
            base_amount = project_debt_base
        elif basis == "capex":
            base_amount = project_capex_base
        else:
            base_amount = 0.0
        amount = base_amount * fee.get("rate", 0)
        fee_rows.append({
            **fee,
            "base_amount": base_amount,
            "amount": amount,
        })
    return {"fees": fee_rows, "total": sum(f["amount"] for f in fee_rows)}


def compute_entity_fees(fees_cfg: dict, entity_assets_base: float) -> dict:
    """Entity-level fees: debt basis = 85% of entity capex, capex basis = full entity capex."""
    fee_rows = []
    for fee in fees_cfg.get("fees", []):
        basis = fee.get("rate_basis", "")
        base = entity_assets_base * 0.85 if basis == "debt" else entity_assets_base if basis == "capex" else 0.0
        amount = round(base * fee.get("rate", 0))
        fee_rows.append({**fee, "base_amount": base, "amount": amount})
    return {"fees": fee_rows, "total": sum(f["amount"] for f in fee_rows)}


def build_asset_registry(entity_key: str, assets_cfg: dict, fees_cfg: dict, project_fee_rows: list, project_asset_base: float, project_debt_base: float) -> dict:
    """Build asset registry + allocate fees on entity bases.

    Uses pre-computed fees_allocated from structure.json to avoid circular
    inflation (fee rates × bases that already include fees).
    Entity-level fee rows are also computed for display.
    """
    base = _build_entity_asset_base(entity_key, assets_cfg)
    fee_base = base["fee_base"]
    entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]

    # Use canonical fee amount from structure.json (not recomputed from rates)
    fee_total = entity_data['fees_allocated']

    # Compute entity-level fee rows for display
    entity_fees = compute_entity_fees(fees_cfg, fee_base)

    # Distribute fees across asset line items pro-rata by depr_base weight
    for a in base["assets"]:
        a_share = (a["depr_base"] / fee_base) if fee_base else 0
        a["alloc_fees"] = fee_total * a_share
        a["depr_base"] = a["depr_base"] + a["alloc_fees"]
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0

    return {
        **base,
        "fee_rows": entity_fees["fees"],
        "fee_total": fee_total,
        "fee_alloc": fee_total,
    }


# ============================================================
# AUTHENTICATION & ROLE-BASED ACCESS
# ============================================================
USERS_FILE = CONFIG_DIR / "users.yaml"
ROLES_FILE = CONFIG_DIR / "roles.json"

def _load_users():
    with open(USERS_FILE, 'r') as f:
        return yaml.load(f, Loader=yaml.SafeLoader)

def _save_users(config):
    with open(USERS_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

@st.cache_data(ttl=300)
def _load_roles():
    with open(ROLES_FILE, 'r') as f:
        return json.load(f)

_roles_config = _load_roles()

ALL_ENTITIES = _roles_config['entities']
ALL_TABS = _roles_config['tabs']
ALL_MGMT_PAGES = ["Summary", "Strategy", "Tasks", "CP & CS", "Guarantor Analysis"]

def get_user_role(username: str, auth_config: dict) -> str:
    """Get the first role from a user's roles list."""
    user = auth_config['credentials']['usernames'].get(username, {})
    roles = user.get('roles', ['promotor_opco'])
    return roles[0] if roles else 'promotor_opco'

def _get_user_permissions(username: str, auth_config: dict) -> dict:
    """Get per-user permissions dict. Falls back to role-based if no permissions set."""
    user = auth_config['credentials']['usernames'].get(username, {})
    perms = user.get('permissions', None)
    if perms:
        return perms
    role = get_user_role(username, auth_config)
    role_cfg = _roles_config['roles'].get(role, {})
    return {
        'entities': role_cfg.get('entities', ['*']),
        'tabs': role_cfg.get('tabs', ['*']),
        'mgmt_pages': role_cfg.get('mgmt_pages', ['*']),
        'can_manage_users': role_cfg.get('can_manage_users', False),
    }

def get_allowed_entities(role: str, username: str = None, auth_config: dict = None) -> list:
    """Return list of entity names this user can access."""
    if username and auth_config:
        perms = _get_user_permissions(username, auth_config)
        entities = perms.get('entities', ['*'])
    else:
        role_cfg = _roles_config['roles'].get(role, {})
        entities = role_cfg.get('entities', [])
    if '*' in entities:
        return list(ALL_ENTITIES)
    return [e for e in ALL_ENTITIES if e in entities]

def get_allowed_tabs(role: str, username: str = None, auth_config: dict = None) -> list:
    """Return list of tab names this user can see."""
    if username and auth_config:
        perms = _get_user_permissions(username, auth_config)
        tabs = perms.get('tabs', ['*'])
    else:
        role_cfg = _roles_config['roles'].get(role, {})
        tabs = role_cfg.get('tabs', [])
    if '*' in tabs:
        return list(ALL_TABS)
    return [t for t in ALL_TABS if t in tabs]

def get_can_manage(username: str, auth_config: dict) -> bool:
    """Check if user has management permissions."""
    perms = _get_user_permissions(username, auth_config)
    return perms.get('can_manage_users', False)

def get_allowed_mgmt_pages(username: str, auth_config: dict) -> list:
    """Return list of management page names this user can access."""
    perms = _get_user_permissions(username, auth_config)
    pages = perms.get('mgmt_pages', ['*'])
    if '*' in pages:
        return list(ALL_MGMT_PAGES)
    return [p for p in ALL_MGMT_PAGES if p in pages]

def filter_tabs(all_tab_names: list, allowed: list) -> list:
    """Filter tab names to only those the user can see."""
    return [t for t in all_tab_names if t in allowed]

ALL_TAB_NAMES = ["Overview", "About", "Sources & Uses", "Facilities", "Assets", "Operations",
                 "P&L", "Cash Flow", "Debt Sculpting", "Balance Sheet", "Graphs", "Sensitivity",
                 "Security", "Delivery"]

def make_tab_map(allowed_tabs: list) -> dict:
    """Create st.tabs for visible tabs, return dict mapping tab names to tab objects."""
    visible = filter_tabs(ALL_TAB_NAMES, allowed_tabs)
    if not visible:
        return {}
    tab_objs = st.tabs(visible)
    return dict(zip(visible, tab_objs))

# Page config
st.set_page_config(
    page_title="Catalytic Assets | Financial Model",
    page_icon="S",
    layout="wide"
)

# --- Authentication ---
_auth_config = _load_users()
authenticator = stauth.Authenticate(
    _auth_config['credentials'],
    _auth_config['cookie']['name'],
    _auth_config['cookie']['key'],
    _auth_config['cookie']['expiry_days'],
)

try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state.get('authentication_status') is False:
    st.error('Username/password is incorrect')
    st.stop()
elif st.session_state.get('authentication_status') is None:
    st.warning('Please enter your username and password')
    st.stop()

# --- Authenticated from here ---
_current_user = st.session_state.get('username', '')
_current_role = get_user_role(_current_user, _auth_config)
_role_label = _roles_config['roles'].get(_current_role, {}).get('label', _current_role)
_allowed_entities = get_allowed_entities(_current_role, _current_user, _auth_config)
_allowed_tabs = get_allowed_tabs(_current_role, _current_user, _auth_config)
_can_manage = get_can_manage(_current_user, _auth_config)

# Load configs
project = load_config("project")
sources_config = load_config("sources")
country_allocation = load_config("country_allocation")
financing = load_config("financing")
structure = load_config("structure")
operations_config = load_config("operations")


# ============================================================
# MODULE-LEVEL HELPERS (used by both SCLCA and subsidiary views)
# ============================================================

def compute_coe_rent_monthly_eur(om_overhead_pct: float = 2.0) -> tuple[float, float, float, float]:
    """Compute CoE monthly rent (EUR) using capital-recovery method.

    Rent = CoE_building_CapEx × (WACC + O&M overhead) / 12
    WACC = 85% × Senior facility rate + 15% × Mezz facility rate
    Returns (monthly_rent_eur, annual_rent_eur, wacc, coe_capex).
    """
    sr_rate = structure['sources']['senior_debt']['interest']['rate']  # 4.70%
    mz_rate = structure['sources']['mezzanine']['interest']['total_rate']  # 14.75%
    sr_share = 0.85
    mz_share = 0.15
    wacc = sr_share * sr_rate + mz_share * mz_rate
    total_yield = wacc + (om_overhead_pct / 100.0)
    # CoE building capex (first line item = building, excludes panel equipment)
    assets_cfg = load_config("assets")["assets"]
    coe_items = assets_cfg.get("coe", {}).get("line_items", [])
    coe_capex = float(coe_items[0].get("budget", 0)) if coe_items else 0.0
    annual_rent = coe_capex * total_yield
    return annual_rent / 12.0, annual_rent, wacc, coe_capex


def run_page_audit(checks: list, page_name: str):
    """Render audit panel with forced error visibility.

    checks = [{"name": str, "expected": float, "actual": float, "tolerance": float}, ...]
    Failures (|expected - actual| > tolerance) are shown as st.error() OUTSIDE the toggle.
    """
    failures = [c for c in checks if abs(c['expected'] - c['actual']) > c.get('tolerance', 1.0)]

    # FORCE errors to be visible (outside expander)
    if failures:
        st.error(f"AUDIT: {len(failures)} check(s) failed on {page_name}")
        for f in failures:
            st.caption(f"  {f['name']}: expected {f['expected']:,.2f}, got {f['actual']:,.2f}")

    # Full details in toggle
    with st.expander(f"Audit — {page_name} ({len(checks)} checks, {len(failures)} failures)", expanded=bool(failures)):
        for c in checks:
            delta = abs(c['expected'] - c['actual'])
            ok = delta <= c.get('tolerance', 1.0)
            icon = "OK" if ok else "FAIL"
            st.markdown(f"{'✓' if ok else '✗'} **{c['name']}**: {icon} (delta: €{delta:,.2f})")


def build_simple_ic_schedule(principal, total_principal, repayments, rate,
                             drawdown_schedule, periods, prepayments=None,
                             dsra_amount=0.0, dsra_drawdown=0.0):
    """Build an IC loan schedule with optional grant-funded prepayments and DSRA.

    prepayments: dict of {period_str: entity_level_amount} — already allocated to this entity.
    dsra_amount: (Senior IC) At P1, principal = dsra_amount; P2 = interest-only; P3+ recalculated.
    dsra_drawdown: (Mezz IC) At P1, add dsra_drawdown to balance; all repayments on higher balance.
    Drawdowns are pro-rated from facility level; prepayments are passed at entity level.
    Returns list of dicts with keys: Period, Month, Year, Opening, Draw Down,
    Interest, Prepayment, Principle, Repayment, Movement, Closing.
    """
    rows = []
    balance = 0.0
    pro_rata = principal / total_principal if total_principal else 0
    for idx, period in enumerate(periods):
        month = (period + 4) * 6
        year = month / 12
        opening = balance
        idc = opening * rate / 2
        draw_down = drawdown_schedule[idx] * pro_rata if idx < len(drawdown_schedule) else 0
        prepay = 0.0
        if prepayments and str(period) in prepayments:
            prepay = prepayments[str(period)]
        movement = draw_down + idc - prepay
        balance = opening + movement
        rows.append({
            "Period": period, "Month": month, "Year": year,
            "Opening": opening, "Draw Down": draw_down, "Interest": idc,
            "Prepayment": -prepay, "Principle": 0, "Repayment": 0,
            "Movement": movement, "Closing": balance
        })

    # Determine repayment profile based on DSRA parameters
    if dsra_amount > 0:
        # Senior with DSRA: P1=dsra, P2=interest-only, P3+=recalculated on remaining
        dsra_balance_after = balance - dsra_amount
        p_per_after_dsra = dsra_balance_after / (repayments - 2) if repayments > 2 else 0
    elif dsra_drawdown > 0:
        # Mezz with DSRA: P1 drawdown increases balance; all repayments on new total
        total_after_dsra = balance + dsra_drawdown
        p_per = total_after_dsra / repayments if repayments > 0 else 0
        # balance stays at pre-DSRA level; drawdown happens at P1 in the loop
    else:
        p_per = balance / repayments if repayments > 0 else 0

    for i in range(1, repayments + 1):
        month = 18 + (i * 6)
        year = month / 12
        opening = balance
        interest = opening * rate / 2

        if dsra_amount > 0:
            # Senior DSRA logic
            if i == 1:
                principle = -dsra_amount
                draw_down = 0
                movement = principle
            elif i == 2:
                principle = 0  # Interest-only (DSRA covers)
                draw_down = 0
                movement = principle
            else:
                principle = -p_per_after_dsra
                draw_down = 0
                movement = principle
        elif dsra_drawdown > 0:
            # Mezz DSRA logic: drawdown at P1, then normal repayments
            draw_down = dsra_drawdown if i == 1 else 0
            principle = -p_per
            movement = draw_down + principle
        else:
            draw_down = 0
            principle = -p_per
            movement = principle

        repayment_val = principle - interest
        balance = opening + movement
        rows.append({
            "Period": i, "Month": month, "Year": year,
            "Opening": opening, "Draw Down": draw_down, "Interest": interest,
            "Prepayment": 0, "Principle": principle, "Repayment": repayment_val,
            "Movement": movement, "Closing": balance
        })
    return rows


def _build_all_entity_ic_schedules(nwl_swap_enabled=False, lanred_swap_enabled=False):
    """Build IC schedules for all 3 entities bottom-up, returning semi-annual aggregates.

    Returns (sem, entity_schedules):
        sem: list of 20 dicts (semi-annual periods), each with:
            iso, isc: aggregate IC Senior opening/closing balance
            imo, imc: aggregate IC Mezz opening/closing balance
            isi, imi: aggregate IC Senior/Mezz accrued interest (for P&L)
            isi_cash, imi_cash: aggregate IC Senior/Mezz cash interest (after grace)
            isp, imp: aggregate IC Senior/Mezz principal repayment
        entity_schedules: dict of {entity_key: {'sr': sr_sched, 'mz': mz_sched}}
    """
    senior_cfg = structure['sources']['senior_debt']
    mezz_cfg = structure['sources']['mezzanine']
    sr_rate = senior_cfg['interest']['rate'] + INTERCOMPANY_MARGIN
    mz_rate = mezz_cfg['interest']['total_rate'] + INTERCOMPANY_MARGIN
    sr_repayments = senior_cfg['repayments']
    mz_repayments = mezz_cfg.get('repayments', 10)
    sr_detail = financing['loan_detail']['senior']
    sr_drawdowns = sr_detail['drawdown_schedule']
    sr_periods = [-4, -3, -2, -1]
    sr_prepayments_raw = sr_detail.get('prepayment_periods', {})
    prepay_alloc = sr_detail.get('prepayment_allocation', {})
    mz_amount_eur = mezz_cfg['amount_eur']
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    mz_periods = [-4, -3, -2, -1]
    total_sr = sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
    total_mz = sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())

    # DSRA sizing (same as build_sub_annual_model)
    _sr_bal_fac = (sr_detail['loan_drawdown_total']
                   + sr_detail['rolled_up_interest_idc']
                   - sr_detail['grant_proceeds_to_early_repayment']
                   - sr_detail['gepf_bulk_proceeds'])
    _sr_rate_fac = senior_cfg['interest']['rate']
    _sr_num_fac = senior_cfg['repayments']
    _sr_p_fac = _sr_bal_fac / _sr_num_fac
    _sr_i_m24 = _sr_bal_fac * _sr_rate_fac / 2
    dsra_amount_total = 2 * (_sr_p_fac + _sr_i_m24)

    # Load waterfall config for swap extensions
    _wf_cfg = load_config("waterfall")
    _lanred_swap_cfg = _wf_cfg.get("lanred_swap", {})

    all_sr_schedules = []
    all_mz_schedules = []
    entity_schedules = {}
    for ek in ['nwl', 'lanred', 'timberworx']:
        ed = structure['uses']['loans_to_subsidiaries'][ek]
        sr_principal = ed['senior_portion']
        mz_principal = ed['mezz_portion']

        entity_prepay_pct = prepay_alloc.get(ek, 0.0) if prepay_alloc else 0.0
        sr_prepayments = {k: v * entity_prepay_pct for k, v in sr_prepayments_raw.items()} if entity_prepay_pct > 0 else None

        dsra_alloc = {'nwl': 1.0}
        entity_dsra = dsra_amount_total * dsra_alloc.get(ek, 0.0)

        # NWL swap replaces DSRA — set entity_dsra=0 when swap active
        if nwl_swap_enabled and ek == 'nwl':
            entity_dsra = 0.0

        # LanRED swap extends IC tenor (7yr→14yr)
        ek_sr_repayments = sr_repayments
        ek_mz_repayments = mz_repayments
        if lanred_swap_enabled and ek == 'lanred':
            ek_sr_repayments = _lanred_swap_cfg.get('extended_repayments_sr', 28)
            ek_mz_repayments = _lanred_swap_cfg.get('extended_repayments_mz', 20)

        sr_sched = build_simple_ic_schedule(
            sr_principal, total_sr, ek_sr_repayments, sr_rate, sr_drawdowns, sr_periods, sr_prepayments,
            dsra_amount=entity_dsra
        )
        mz_sched = build_simple_ic_schedule(
            mz_principal, total_mz, ek_mz_repayments, mz_rate, mz_drawdowns, mz_periods,
            dsra_drawdown=entity_dsra
        )
        all_sr_schedules.append(sr_sched)
        all_mz_schedules.append(mz_sched)
        entity_schedules[ek] = {'sr': sr_sched, 'mz': mz_sched}

    # Aggregate into semi-annual periods (20 periods = 10 years)
    sem = []
    for pi in range(20):
        m = pi * 6
        # Sum across entities for this semi-annual period
        iso = 0.0; isc = 0.0; imo = 0.0; imc = 0.0
        isi = 0.0; imi = 0.0; isi_cash = 0.0; imi_cash = 0.0
        isp = 0.0; imp = 0.0
        for sr_sched in all_sr_schedules:
            for r in sr_sched:
                if r['Month'] == m:
                    iso += r['Opening']
                    isc += r['Closing']
                    isi += r['Interest']
                    isi_cash += r['Interest'] if m >= 24 else 0
                    isp += abs(r['Principle'])
                    break
            # Check half-period: month m and m don't always line up exactly
            # IC schedules have entries at 0, 6, 12, 18, 24, 30, ...
        ic_dsra_mz_draw = 0.0  # Track DSRA-funded Mz drawdowns (pass-through)
        for mz_sched in all_mz_schedules:
            for r in mz_sched:
                if r['Month'] == m:
                    imo += r['Opening']
                    imc += r['Closing']
                    imi += r['Interest']
                    imi_cash += r['Interest'] if m >= 24 else 0
                    imp += abs(r['Principle'])
                    # Track DSRA-funded Mz drawdowns at M24+ (pass-through from CC)
                    if r['Draw Down'] > 0 and m >= 24:
                        ic_dsra_mz_draw += r['Draw Down']
                    break
        sem.append({
            'iso': iso, 'isc': isc, 'imo': imo, 'imc': imc,
            'isi': isi, 'imi': imi, 'isi_cash': isi_cash, 'imi_cash': imi_cash,
            'isp': isp, 'imp': imp,
            'ic_dsra_mz_draw': ic_dsra_mz_draw,
        })
    return sem, entity_schedules


# ── Cascade Diagram Helpers ───────────────────────────────────────

def _render_entity_cascade_diagram(entity_label, show_swap=False, show_od_lend=False, show_od_repay=False):
    """Render entity cascade as Graphviz DOT (st.graphviz_chart)."""
    sr = '#1E3A5F'
    mz = '#7C3AED'
    gn = '#059669'
    fd = '#0D9488'
    dot = f'''digraph {{
        rankdir=TB; bgcolor="transparent"; pad=0.3;
        node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=11, fontcolor=white, margin="0.15,0.08"];
        edge [color="#64748B", penwidth=1.2];

        REV  [label="{entity_label} Revenue", fillcolor="{gn}"];
        EBITDA [label="EBITDA", fillcolor="{gn}"];
        TAX  [label="Tax", fillcolor="#6B7280"];
        NET  [label="Net Cash", fillcolor="{gn}"];
        C1   [label="IC Senior P+I", fillcolor="{sr}"];
        C2   [label="IC Mezz P+I", fillcolor="{mz}"];
        S1   [label="Ops Reserve FD", fillcolor="{fd}"];
        S2   [label="OpCo DSRA", fillcolor="{fd}"];
        SURP [label="Surplus", fillcolor="{gn}"];
        P1   [label="Mezz IC Accel\\n(15.25%)", fillcolor="{mz}"];
        P4   [label="Sr IC Accel\\n(5.20%)", fillcolor="{sr}"];
        EFD  [label="Entity FD", fillcolor="{fd}"];
        SRPIPE [label="Senior Pipe →\\nSCLCA → IIC", fillcolor="{sr}"];
        MZPIPE [label="Mezz Pipe →\\nSCLCA → CC", fillcolor="{mz}"];

        REV -> EBITDA -> TAX -> NET;
        NET -> C1; NET -> C2;
        NET -> S1 -> S2;
'''
    if show_od_lend:
        dot += f'        S3 [label="LanRED OD\\nLending", fillcolor="#F59E0B", fontcolor="#1a1a1a", shape=diamond];\n'
        dot += '        S2 -> S3 -> SURP;\n'
    elif show_od_repay:
        dot += f'        P3 [label="OD Repay\\n(10%)", fillcolor="#F59E0B", fontcolor="#1a1a1a"];\n'
        dot += '        S2 -> SURP;\n'
    else:
        dot += '        S2 -> SURP;\n'
    dot += '        SURP -> P1;\n'
    if show_swap:
        dot += f'        P2 [label="ZAR Rand Leg\\n(11.75%)", fillcolor="#F59E0B", fontcolor="#1a1a1a"];\n'
        dot += '        P1 -> P2 -> P4;\n'
    elif show_od_repay:
        dot += '        P1 -> P3 -> P4;\n'
    else:
        dot += '        P1 -> P4;\n'
    dot += '''        P4 -> EFD;
        C1 -> SRPIPE;
        C2 -> MZPIPE;
    }'''
    st.graphviz_chart(dot, use_container_width=True)


def _render_holding_passthrough_diagram():
    """Render SCLCA holding pass-through as Graphviz DOT."""
    sr = '#1E3A5F'
    mz = '#7C3AED'
    fd = '#0D9488'
    dot = f'''digraph {{
        rankdir=LR; bgcolor="transparent"; pad=0.3;
        node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=11, fontcolor=white, margin="0.15,0.08"];
        edge [color="#64748B", penwidth=1.2];

        NWL_SR  [label="NWL Sr", fillcolor="{sr}"];
        LR_SR   [label="LanRED Sr", fillcolor="{sr}"];
        TWX_SR  [label="TWX Sr", fillcolor="{sr}"];
        NWL_MZ  [label="NWL Mz", fillcolor="{mz}"];
        LR_MZ   [label="LanRED Mz", fillcolor="{mz}"];
        TWX_MZ  [label="TWX Mz", fillcolor="{mz}"];
        SR      [label="Senior\\nReceived", fillcolor="{sr}"];
        MZ      [label="Mezz\\nReceived", fillcolor="{mz}"];
        IIC     [label="Invest\\nInternational", fillcolor="{sr}"];
        CC      [label="Creation\\nCapital", fillcolor="{mz}"];
        MARGIN  [label="0.5%\\nMargin", fillcolor="{fd}"];
        HFD     [label="Holding FD", fillcolor="{fd}"];

        NWL_SR -> SR; LR_SR -> SR; TWX_SR -> SR;
        NWL_MZ -> MZ; LR_MZ -> MZ; TWX_MZ -> MZ;
        SR -> IIC [label="pass-through"];
        MZ -> CC  [label="pass-through"];
        SR -> MARGIN; MZ -> MARGIN;
        MARGIN -> HFD;
    }}'''
    st.graphviz_chart(dot, use_container_width=True)


# ── Waterfall Engine ──────────────────────────────────────────────

def _get_next_sr_pi(entity_sr_sched, after_month):
    """Look up the next Senior IC P+I payment after a given month.

    Used for OpCo DSRA sizing (1x next Sr IC P+I).
    """
    for r in entity_sr_sched:
        if r['Month'] > after_month and r['Month'] >= 24:
            return r['Interest'] + abs(r['Principle'])
    return 0.0


def _compute_entity_waterfall_inputs(entity_key, ops_annual, entity_sr_sched, entity_mz_sched,
                                      *, lanred_deficit_vector=None, nwl_swap_schedule=None):
    """Entity surplus computation with character-preserving allocation (v3.1).

    Full entity-level cascade:
      0. Pay contractual IC Sr P+I + IC Mz P+I (mandatory)
      1. Fill Ops Reserve FD (100% of annual ops cost)
      2. Fill OpCo DSRA (1x next Sr IC P+I)
      3. LanRED overdraft lending (NWL only, if deficit vector provided)
      Surplus priority (by rate, highest first):
        P1. Accelerate Mezz IC (15.25%, Mezz character)
        P2. ZAR Rand Leg (11.75%, NWL only if swap active, Senior character)
        P3. Overdraft repayment (10%, LanRED only)
        P4. Accelerate Senior IC (5.20%, Senior character)
      After both IC = 0 → Entity FD (retained locally)

    Returns list of 10 annual dicts with full cascade breakdown.
    """
    _wf_cfg = load_config("waterfall")
    _ec_cfg = _wf_cfg.get("entity_cascade", {})
    _od_cfg = _wf_cfg.get("ic_overdraft", {})
    ops_reserve_coverage = _ec_cfg.get("ops_reserve_coverage_pct", 1.0)
    od_rate = _od_cfg.get("rate", 0.10)

    rows = []

    # Track running IC balances for entity-level acceleration
    mz_ic_bal = 0.0
    for r in entity_mz_sched:
        if r['Month'] >= 24:
            mz_ic_bal = r.get('Opening', 0)
            break

    sr_ic_bal = 0.0
    for r in entity_sr_sched:
        if r['Month'] >= 24:
            sr_ic_bal = r.get('Opening', 0)
            break

    # New state variables
    ops_reserve_bal = 0.0
    opco_dsra_bal = 0.0
    entity_fd_bal = 0.0
    od_bal_entity = 0.0  # LanRED: OD received from NWL; NWL: OD lent to LanRED

    for yi in range(10):
        ops = ops_annual[yi] if yi < len(ops_annual) else {}
        ebitda = (ops.get('rev_operating', 0)
                  - ops.get('om_cost', 0)
                  - ops.get('power_cost', 0)
                  - ops.get('rent_cost', 0))

        # Annual ops cost for reserve target
        annual_ops_cost = (ops.get('om_cost', 0)
                           + ops.get('power_cost', 0)
                           + ops.get('rent_cost', 0))

        # IC debt service (cash): interest + principal, M24+ only
        sr_pi = 0.0
        mz_pi = 0.0
        ie_year = 0.0
        year_months = [yi * 12 + 6, yi * 12 + 12]
        mz_prin_sched = 0.0
        sr_prin_sched = 0.0
        sr_prepay = 0.0
        for r in entity_sr_sched:
            if r['Month'] in year_months:
                ie_year += r['Interest']
                if r['Month'] >= 24:
                    sr_pi += r['Interest'] + abs(r['Principle'])
                    sr_prin_sched += abs(r['Principle'])
                sr_prepay += abs(r.get('Prepayment', 0))
        for r in entity_mz_sched:
            if r['Month'] in year_months:
                ie_year += r['Interest']
                if r['Month'] >= 24:
                    mz_pi += r['Interest'] + abs(r['Principle'])
                    mz_prin_sched += abs(r['Principle'])
        ds_cash = sr_pi + mz_pi

        # Simplified tax: 27% on positive PBT (EBITDA - interest expense)
        pbt = ebitda - ie_year
        tax = max(pbt * 0.27, 0)

        net = ebitda - tax - ds_cash

        # --- Entity-level cascade ---
        remaining = max(net, 0)
        deficit = min(net, 0)

        # Reduce IC balances by scheduled principal + prepayments
        mz_ic_bal = max(mz_ic_bal - mz_prin_sched, 0)
        sr_ic_bal = max(sr_ic_bal - sr_prin_sched - sr_prepay, 0)

        # Step 1: Ops Reserve FD — fill to 100% of annual ops cost
        ops_reserve_target = annual_ops_cost * ops_reserve_coverage
        ops_reserve_gap = max(ops_reserve_target - ops_reserve_bal, 0)
        ops_reserve_fill = min(remaining, ops_reserve_gap)
        ops_reserve_bal += ops_reserve_fill
        remaining -= ops_reserve_fill

        # Step 2: OpCo DSRA — fill to 1x next Sr IC P+I
        next_sr_pi = _get_next_sr_pi(entity_sr_sched, (yi + 1) * 12)
        opco_dsra_target = next_sr_pi
        opco_dsra_gap = max(opco_dsra_target - opco_dsra_bal, 0)
        opco_dsra_fill = min(remaining, opco_dsra_gap)
        # Release surplus if overfunded
        opco_dsra_release = max(opco_dsra_bal - opco_dsra_target, 0) if opco_dsra_bal > opco_dsra_target else 0
        opco_dsra_bal += opco_dsra_fill - opco_dsra_release
        remaining -= opco_dsra_fill
        remaining += opco_dsra_release

        # Step 3: LanRED overdraft lending (NWL only)
        od_lent = 0.0
        od_received = 0.0
        od_repaid = 0.0
        od_interest = 0.0

        if entity_key == 'nwl' and lanred_deficit_vector is not None:
            lanred_deficit = abs(lanred_deficit_vector[yi]) if yi < len(lanred_deficit_vector) else 0
            if lanred_deficit > 0 and remaining > 0:
                od_lent = min(remaining, lanred_deficit)
                od_interest_on_existing = od_bal_entity * od_rate
                od_bal_entity += od_lent + od_interest_on_existing
                od_interest = od_interest_on_existing
                remaining -= od_lent

        if entity_key == 'lanred':
            # OD received is injected by orchestrator in second pass
            od_received = 0.0  # populated by orchestrator
            od_interest = od_bal_entity * od_rate
            od_bal_entity += od_interest

        # --- Surplus priority allocation (by rate, highest first) ---

        # P1: Accelerate Mezz IC (15.25%, Mezz character)
        mz_accel_entity = 0.0
        if mz_ic_bal > 0.01 and remaining > 0:
            mz_accel_entity = min(remaining, mz_ic_bal)
            mz_ic_bal -= mz_accel_entity
            remaining -= mz_accel_entity

        # P2: ZAR Rand Leg (11.75%, NWL only, if swap active, Senior character)
        zar_leg_payment = 0.0
        if entity_key == 'nwl' and nwl_swap_schedule and remaining > 0:
            # Sum ZAR leg payments due this year (in EUR)
            zar_due_this_year = 0.0
            for r in nwl_swap_schedule.get('schedule', []):
                if (yi * 12 + 1) <= r['month'] <= (yi + 1) * 12:
                    zar_due_this_year += r['payment']
            # Convert ZAR to EUR
            fx = nwl_swap_schedule.get('zar_amount', 1) / max(nwl_swap_schedule.get('eur_amount', 1), 1) if nwl_swap_schedule.get('eur_amount', 0) > 0 else 1
            zar_due_eur = zar_due_this_year / fx if fx > 0 else 0
            zar_leg_payment = min(remaining, zar_due_eur)
            remaining -= zar_leg_payment

        # P3: Overdraft repayment (10%, LanRED only)
        if entity_key == 'lanred' and od_bal_entity > 0.01 and remaining > 0:
            od_repaid = min(remaining, od_bal_entity)
            od_bal_entity -= od_repaid
            remaining -= od_repaid

        # P4: Accelerate Senior IC (5.20%, Senior character)
        sr_accel_entity = 0.0
        if sr_ic_bal > 0.01 and remaining > 0:
            sr_accel_entity = min(remaining, sr_ic_bal)
            sr_ic_bal -= sr_accel_entity
            remaining -= sr_accel_entity

        # Entity FD: After both IC = 0 AND no OD outstanding → retain locally
        entity_fd_fill = 0.0
        both_ic_zero = mz_ic_bal <= 0.01 and sr_ic_bal <= 0.01
        no_od = od_bal_entity <= 0.01
        if both_ic_zero and no_od and remaining > 0:
            entity_fd_fill = remaining
            entity_fd_bal += entity_fd_fill
            remaining -= entity_fd_fill

        free_surplus = remaining  # anything left upstream

        rows.append({
            'ebitda': ebitda, 'tax': tax, 'ds_cash': ds_cash,
            'sr_pi': sr_pi, 'mz_pi': mz_pi,
            'mz_accel_entity': mz_accel_entity,
            'sr_accel_entity': sr_accel_entity,
            'zar_leg_payment': zar_leg_payment,
            'ie_year': ie_year, 'pbt': pbt,
            'surplus': max(net, 0),
            'deficit': deficit,
            'mz_ic_bal': mz_ic_bal,
            'sr_ic_bal': sr_ic_bal,
            # New fields
            'ops_reserve_fill': ops_reserve_fill,
            'ops_reserve_bal': ops_reserve_bal,
            'opco_dsra_fill': opco_dsra_fill,
            'opco_dsra_bal': opco_dsra_bal,
            'opco_dsra_target': opco_dsra_target,
            'od_lent': od_lent,
            'od_received': od_received,
            'od_repaid': od_repaid,
            'od_interest': od_interest,
            'od_bal': od_bal_entity,
            'entity_fd_fill': entity_fd_fill,
            'entity_fd_bal': entity_fd_bal,
            'free_surplus': free_surplus,
        })
    return rows


def _build_nwl_swap_schedule(swap_amount_eur, fx_rate, last_sr_month=102):
    """EUR→ZAR cross-currency swap schedule.

    EUR leg (asset): swap_amount_eur = IC Senior P+I at M24 + M30.
    ZAR leg (liability): NWL repays Investec semi-annually from start_month to last_sr_month.
    Returns dict with schedule rows and summary.
    """
    _wf_cfg = load_config("waterfall")
    _swap_cfg = _wf_cfg.get("nwl_swap", {})
    zar_rate = _swap_cfg.get("zar_rate", 0.1175)
    start_month = _swap_cfg.get("zar_start_month", 36)
    # Tenor: number of semi-annual periods from start_month to last_sr_month (inclusive)
    tenor = max(1, (last_sr_month - start_month) // 6 + 1)
    zar_amount = swap_amount_eur * fx_rate
    semi_rate = zar_rate / 2.0
    # Level annuity (P+I constant)
    if semi_rate > 0:
        annuity = zar_amount * semi_rate / (1 - (1 + semi_rate) ** -tenor)
    else:
        annuity = zar_amount / tenor

    schedule = []
    bal = zar_amount
    for i in range(tenor):
        month = start_month + i * 6
        opening = bal
        interest = opening * semi_rate
        principal = annuity - interest
        bal = opening - principal
        schedule.append({
            'period': i + 1, 'month': month,
            'opening': opening, 'interest': interest,
            'principal': principal, 'payment': annuity,
            'closing': max(bal, 0),
        })
    return {
        'eur_amount': swap_amount_eur,
        'zar_amount': zar_amount,
        'zar_rate': zar_rate,
        'annuity_zar': annuity,
        'annuity_eur': annuity / fx_rate,
        'tenor': tenor,
        'start_month': start_month,
        'schedule': schedule,
    }


def _compute_irr_bisect(cashflows, lo=-0.5, hi=2.0, tol=1e-6, maxiter=200):
    """IRR via bisection (standalone, not nested in a tab)."""
    def _npv(r):
        return sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
    if not cashflows or _npv(lo) * _npv(hi) > 0:
        return None
    for _ in range(maxiter):
        mid = (lo + hi) / 2.0
        if abs(_npv(mid)) < tol:
            return mid
        if _npv(lo) * _npv(mid) < 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def _compute_dsra_vs_swap_comparison(dsra_amount_eur, cc_initial, cc_rate,
                                      cc_gap_rate, swap_sched, wacc):
    """Compare cost of CC DSRA->FEC vs Cross-Currency Swap.

    Scenario A: CC funds DSRA at M24 — CC charges 14.75% + 5.25% dividend = 20%
    Scenario B: Cross-currency swap at 11.75% — CC does NOT fund DSRA
    """
    effective_rate_a = cc_rate + cc_gap_rate  # 14.75% + 5.25% = 20%
    avg_years_a = 3.5  # approximate average outstanding period
    cost_a_total = dsra_amount_eur * effective_rate_a * avg_years_a
    npv_cost_a = sum(dsra_amount_eur * effective_rate_a / (1 + wacc) ** t
                     for t in range(1, int(avg_years_a * 2) + 1))

    swap_amount = swap_sched['eur_amount'] if swap_sched else 0
    effective_rate_b = swap_sched['zar_rate'] if swap_sched else 0.1175
    cost_b_total = 0.0
    npv_cost_b = 0.0
    if swap_sched:
        fx = swap_sched['zar_amount'] / swap_sched['eur_amount'] if swap_sched['eur_amount'] else 1
        for r in swap_sched['schedule']:
            yr_idx = max(0, (r['month'] - 24) / 12)
            cost_b_total += r['interest'] / fx
            npv_cost_b += (r['interest'] / fx) / (1 + wacc) ** yr_idx

    return {
        'dsra_amount': dsra_amount_eur,
        'swap_amount': swap_amount,
        'cost_a_total': cost_a_total,
        'cost_b_total': cost_b_total,
        'npv_cost_a': npv_cost_a,
        'npv_cost_b': npv_cost_b,
        'savings': npv_cost_a - npv_cost_b,
        'effective_rate_a': effective_rate_a,
        'effective_rate_b': effective_rate_b,
    }


def _build_waterfall_model(annual_model, nwl_wf, lanred_wf, twx_wf,
                            sem, entity_ic, nwl_swap_enabled=False,
                            lanred_swap_enabled=False, swap_schedule=None):
    """Build 10-year holding company cash waterfall (v3.1 — character-preserving).

    Cash can ONLY flow upstream via 2 pipes: Senior IC or Mezz IC.
      - Entity Sr P+I + prepayments + sr_accel_entity → Senior character → IIC
      - Entity Mz P+I + mz_accel_entity → Mezz character → CC
    No "free surplus" bucket — ALL cash is allocated at entity level.

    Priority cascade (6-step):
      1. Senior P+I + Sr Accel (pass-through to IIC, Senior character)
      2. Mezz P+I + Mz Accel (pass-through to CC, Mezz character)
      3. DSRA top-up (1x next Senior P+I)
      4. One-Time Dividend (IC obligation, when CC = 0)
      5. Senior acceleration (holding-level, from Sr excess)
      6. Fixed Deposit (residual)

    Returns list of 10 annual dicts with full waterfall breakdown.
    """
    _wf_cfg = load_config("waterfall")
    _cc_irr_cfg = _wf_cfg.get("cc_irr", {})
    cc_gap_rate = _cc_irr_cfg.get("gap", 0.0525)

    # Facility-level params from structure config
    _mz_cfg = structure['sources']['mezzanine']
    _mz_dtl = financing['loan_detail']['mezzanine']
    _fx_m = _mz_cfg['amount_eur'] / _mz_cfg['amount_zar']
    _mz_eur = _mz_cfg['amount_eur']
    _mz_rollup = _mz_dtl['rolled_up_interest_zar'] * _fx_m
    cc_initial = _mz_eur + _mz_rollup  # CC total exposure after rollup

    # Track CC balance, dividend, holding DSRA, FD
    cc_bal = cc_initial
    cc_slug_cumulative = 0.0
    slug_settled = False
    dsra_bal = 0.0     # Holding DSRA balance
    fd_bal = 0.0       # Holding Fixed Deposit balance

    # CC cash flow vector for IRR verification
    cc_cashflows = [-cc_initial]  # M0: CC invests

    waterfall = []
    for yi in range(10):
        yr = yi + 1
        a = annual_model[yi]
        wf = {'year': yr}

        # --- 1. Entity-level contributions (2 pipes only) ---
        entity_wfs = {'nwl': nwl_wf[yi], 'lanred': lanred_wf[yi], 'timberworx': twx_wf[yi]}
        sr_character = 0.0   # Senior character: sr_pi + prepayments + sr_accel_entity + zar_leg
        mz_character = 0.0   # Mezz character: mz_pi + mz_accel_entity

        for ek, ewf in entity_wfs.items():
            wf[f'{ek}_ebitda'] = ewf['ebitda']
            wf[f'{ek}_ds'] = ewf['ds_cash']
            wf[f'{ek}_sr_pi'] = ewf['sr_pi']
            wf[f'{ek}_mz_pi'] = ewf['mz_pi']
            wf[f'{ek}_mz_accel_entity'] = ewf.get('mz_accel_entity', 0)
            wf[f'{ek}_sr_accel_entity'] = ewf.get('sr_accel_entity', 0)
            wf[f'{ek}_zar_leg_payment'] = ewf.get('zar_leg_payment', 0)
            wf[f'{ek}_mz_ic_bal'] = ewf.get('mz_ic_bal', 0)
            wf[f'{ek}_sr_ic_bal'] = ewf.get('sr_ic_bal', 0)

            # New entity-level cascade fields
            wf[f'{ek}_ops_reserve_fill'] = ewf.get('ops_reserve_fill', 0)
            wf[f'{ek}_ops_reserve_bal'] = ewf.get('ops_reserve_bal', 0)
            wf[f'{ek}_opco_dsra_fill'] = ewf.get('opco_dsra_fill', 0)
            wf[f'{ek}_opco_dsra_bal'] = ewf.get('opco_dsra_bal', 0)
            wf[f'{ek}_opco_dsra_target'] = ewf.get('opco_dsra_target', 0)
            wf[f'{ek}_entity_fd_fill'] = ewf.get('entity_fd_fill', 0)
            wf[f'{ek}_entity_fd_bal'] = ewf.get('entity_fd_bal', 0)
            wf[f'{ek}_od_lent'] = ewf.get('od_lent', 0)
            wf[f'{ek}_od_received'] = ewf.get('od_received', 0)
            wf[f'{ek}_od_repaid'] = ewf.get('od_repaid', 0)
            wf[f'{ek}_od_bal'] = ewf.get('od_bal', 0)

            # Grant-funded prepayments this year (from IC schedule, Senior character)
            y_start = yi * 12
            y_end = y_start + 12
            ek_prepay = 0.0
            for r in entity_ic[ek]['sr']:
                if y_start <= r['Month'] < y_end:
                    ek_prepay += abs(r.get('Prepayment', 0))
            wf[f'{ek}_prepay'] = ek_prepay

            # Entity DSRA target (backward compat: from opco_dsra_target)
            wf[f'{ek}_dsra_target'] = ewf.get('opco_dsra_target', 0)
            # Entity DSRA balance (backward compat key name points to entity_fd_bal)
            wf[f'{ek}_dsra_bal'] = ewf.get('entity_fd_bal', 0)

            wf[f'{ek}_surplus'] = ewf.get('sr_accel_entity', 0) + ewf.get('free_surplus', 0)
            wf[f'{ek}_deficit'] = ewf['deficit']

            # Determine if entity IC is fully repaid (from entity-level balances)
            entity_ic_repaid = ewf.get('mz_ic_bal', 1) <= 0.01 and ewf.get('sr_ic_bal', 1) <= 0.01
            wf[f'{ek}_ic_repaid'] = entity_ic_repaid

            # 2-pipe upstream (stops after IC repaid)
            if not entity_ic_repaid:
                sr_character += ewf['sr_pi'] + ek_prepay + ewf.get('sr_accel_entity', 0) + ewf.get('zar_leg_payment', 0)
                mz_character += ewf['mz_pi'] + ewf.get('mz_accel_entity', 0)

        # Total pool for display (all upstream combined)
        pool = sr_character + mz_character

        # --- 2. IC Overdraft tracking (now computed at entity level) ---
        wf['ic_overdraft_drawn'] = entity_wfs['nwl'].get('od_lent', 0)
        wf['ic_overdraft_repaid'] = entity_wfs['lanred'].get('od_repaid', 0)
        wf['ic_overdraft_bal'] = entity_wfs['nwl'].get('od_bal', 0)

        # --- 3. SCLCA 6-Step Priority Cascade (character-preserving) ---
        wf['pool_total'] = pool
        cc_opening = cc_bal

        # Step 1: Senior P+I + Sr Accel (pass-through, Senior character → IIC)
        sr_pi_due = a.get('cf_repay_out_sr', 0) + a.get('cf_ie_sr_cash', 0)
        wf_sr_pi = sr_character  # ALL Senior-character cash → IIC
        wf['wf_sr_pi'] = wf_sr_pi

        # Step 2: Mezz P+I + Mz Accel (pass-through, Mezz character → CC)
        # ALL Mezz-character cash → CC
        wf_mz_pi = mz_character
        # CC balance reduction: scheduled Mezz principal + entity Mezz acceleration
        mz_prin_sched = a.get('cf_repay_out_mz', 0)
        entity_mz_accel_total = sum(ewf.get('mz_accel_entity', 0) for ewf in entity_wfs.values())
        cc_bal -= min(mz_prin_sched + entity_mz_accel_total, cc_bal)
        wf['wf_mz_pi'] = wf_mz_pi

        # Step 3: DSRA top-up (1x next year Senior P+I)
        # Funded from any Senior excess beyond contractual P+I
        sr_excess = max(sr_character - sr_pi_due, 0)
        remaining = sr_excess
        next_yr_sr_pi = 0.0
        if yi < 9:
            na = annual_model[yi + 1] if yi + 1 < len(annual_model) else {}
            next_yr_sr_pi = na.get('cf_repay_out_sr', 0) + na.get('cf_ie_sr_cash', 0)
        dsra_target = next_yr_sr_pi
        dsra_gap = max(dsra_target - dsra_bal, 0)
        dsra_topup = min(remaining, dsra_gap)
        # Release surplus if overfunded (from prior year's excess)
        dsra_release = max(dsra_bal - dsra_target, 0) if dsra_bal > dsra_target else 0
        dsra_bal += dsra_topup - dsra_release
        remaining -= dsra_topup
        remaining += dsra_release
        wf['wf_dsra_topup'] = dsra_topup
        wf['wf_dsra_release'] = dsra_release
        wf['wf_dsra_bal'] = dsra_bal
        wf['wf_dsra_target'] = dsra_target

        # Step 4: One-Time Dividend (when CC balance reaches 0)
        wf_slug_paid = 0.0
        if cc_bal <= 0.01 and not slug_settled and cc_slug_cumulative > 0:
            wf_slug_paid = min(remaining, cc_slug_cumulative)
            remaining -= wf_slug_paid
            slug_settled = True
        wf['wf_cc_slug_paid'] = wf_slug_paid

        # Step 5: Senior acceleration (holding-level, IIC voluntary prepayment)
        wf_sr_accel = 0.0
        if remaining > 0:
            wf_sr_accel = remaining
            remaining -= wf_sr_accel
        wf['wf_sr_accel'] = wf_sr_accel

        # Step 6: Fixed Deposit (residual)
        wf_fd_deposit = remaining
        fd_bal += wf_fd_deposit
        remaining = 0.0
        wf['wf_fd_deposit'] = wf_fd_deposit
        wf['wf_fd_bal'] = fd_bal

        wf['wf_unallocated'] = remaining

        # Stub: wf_mz_accel = 0 at holding (moved to entity level)
        wf['wf_mz_accel'] = 0

        # --- Backward compatibility aliases ---
        wf['wf_iic_pi'] = wf_sr_pi               # old Step 1
        wf['wf_cc_interest'] = wf_mz_pi           # old Step 2 (includes entity accel)
        wf['wf_cc_principal'] = 0                  # old holding Mz accel (now entity-level)
        wf['wf_iic_prepay'] = wf_sr_accel          # old Step 5→6

        # Zero stubs for removed rebalance (keeps downstream tabs safe)
        wf['wf_ic_mz_rebalance'] = 0
        for ek in ['nwl', 'lanred', 'timberworx']:
            wf[f'wf_ic_mz_rebalance_{ek}'] = 0
            wf[f'ic_mz_bal_{ek}'] = 0
        wf['interest_saved'] = 0

        # --- CC Dividend Tracker ---
        if cc_opening > 0.01:
            slug_accrual = cc_opening * cc_gap_rate
            cc_slug_cumulative += slug_accrual
        else:
            slug_accrual = 0.0
        wf['cc_opening'] = cc_opening
        wf['cc_closing'] = cc_bal
        wf['cc_slug_accrual'] = slug_accrual
        wf['cc_slug_cumulative'] = cc_slug_cumulative
        wf['cc_slug_settled'] = slug_settled

        # --- CC IRR verification ---
        # CC receives: Mz P+I (step 2, includes entity accel) + Dividend (step 4)
        cc_yr_cf = wf_mz_pi + wf_slug_paid
        cc_cashflows.append(cc_yr_cf)
        cc_irr = _compute_irr_bisect(cc_cashflows)
        wf['cc_irr_achieved'] = cc_irr

        # --- NWL swap tracking ---
        if nwl_swap_enabled and swap_schedule:
            zar_paid = sum(r['payment'] for r in swap_schedule['schedule']
                          if (yi * 12 + 1) <= r['month'] <= (yi + 1) * 12)
            zar_bal = 0.0
            for r in swap_schedule['schedule']:
                if r['month'] <= (yi + 1) * 12:
                    zar_bal = r['closing']
            wf['swap_eur_delivered'] = swap_schedule['eur_amount'] if yi == 1 else 0
            wf['swap_zar_repaid'] = zar_paid / FX_RATE
            wf['swap_zar_bal'] = zar_bal / FX_RATE
        else:
            wf['swap_eur_delivered'] = 0
            wf['swap_zar_repaid'] = 0
            wf['swap_zar_bal'] = 0

        waterfall.append(wf)

    return waterfall

# ── End Waterfall Engine ──────────────────────────────────────────


def _state_float(key: str, default: float) -> float:
    """Read a float from Streamlit state with fallback."""
    try:
        return float(st.session_state.get(key, default))
    except Exception:
        return float(default)


def _state_str(key: str, default: str) -> str:
    """Read a string from Streamlit state with fallback."""
    return str(st.session_state.get(key, default))


def _state_bool(key: str, default: bool) -> bool:
    """Read a bool from Streamlit state with fallback."""
    return bool(st.session_state.get(key, default))


def _eca_default(entity_key: str) -> bool:
    """Default ECA toggle state: OFF for Brownfield+ LanRED, ON otherwise."""
    if entity_key == 'lanred' and _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
        return False
    return True


def _apply_eca_fee_adjustments():
    """Patch entity loan allocations based on ECA toggle state.

    Safe: @st.cache_data returns deserialized copies, so in-place
    modifications don't affect the cache. Each rerun starts fresh.
    """
    for ek in ['nwl', 'lanred', 'timberworx']:
        ed = structure['uses']['loans_to_subsidiaries'][ek]
        assets_base = ed['assets_base']
        adj_sr = 0.0
        adj_mz = 0.0

        # Atradius Premium (fee_003): 4.4% of 85% capex, senior_only
        if not _state_bool(f"{ek}_eca_atradius", _eca_default(ek)):
            amt = assets_base * 0.85 * 0.044
            adj_sr += amt

        # Exporter Premium (fee_004): 0.4% of capex, mezz_senior (85/15)
        if not _state_bool(f"{ek}_eca_exporter", _eca_default(ek)):
            amt = assets_base * 0.004
            adj_sr += amt * 0.85
            adj_mz += amt * 0.15

        adj_total = adj_sr + adj_mz
        if adj_total > 0:
            ed['fees_allocated'] = max(0, ed['fees_allocated'] - adj_total)
            ed['total_loan'] = max(0, ed['total_loan'] - adj_total)
            ed['senior_portion'] = max(0, ed['senior_portion'] - adj_sr)
            ed['mezz_portion'] = max(0, ed['mezz_portion'] - adj_mz)

    # Re-sync facility totals so balance checks pass
    all_loans = structure['uses']['loans_to_subsidiaries']
    new_sr = sum(v['senior_portion'] for v in all_loans.values())
    new_mz = sum(v['mezz_portion'] for v in all_loans.values())
    new_total = new_sr + new_mz
    structure['sources']['senior_debt']['amount'] = new_sr
    structure['sources']['mezzanine']['amount_eur'] = new_mz
    structure['sources']['total'] = new_total
    structure['uses']['total'] = new_total
    structure['balance_check']['sources_total'] = new_total
    structure['balance_check']['uses_total'] = new_total
    structure['balance_check']['senior_sources'] = new_sr
    structure['balance_check']['senior_uses'] = new_sr
    structure['balance_check']['mezz_sources'] = new_mz
    structure['balance_check']['mezz_uses'] = new_mz


# Apply ECA fee adjustments (reads session_state from previous rerun)
_apply_eca_fee_adjustments()


def _extrapolate_piecewise_linear(base_months: list[int], base_values: list[float], target_months: list[int], floor: float | None = None) -> list[float]:
    """Piecewise-linear interpolation/extrapolation on semi-annual anchors."""
    if not base_months or not base_values or len(base_months) != len(base_values):
        return [0.0 for _ in target_months]

    pairs = sorted(zip(base_months, base_values), key=lambda x: x[0])
    xs = [int(p[0]) for p in pairs]
    ys = [float(p[1]) for p in pairs]

    if len(xs) >= 2:
        left_dx = xs[1] - xs[0]
        left_slope = ((ys[1] - ys[0]) / left_dx) if left_dx else 0.0
        right_dx = xs[-1] - xs[-2]
        right_slope = ((ys[-1] - ys[-2]) / right_dx) if right_dx else 0.0
    else:
        left_slope = 0.0
        right_slope = 0.0

    out = []
    for t in target_months:
        if t <= xs[0]:
            v = ys[0] + left_slope * (t - xs[0])
        elif t >= xs[-1]:
            v = ys[-1] + right_slope * (t - xs[-1])
        else:
            v = ys[-1]
            for i in range(len(xs) - 1):
                x0, x1 = xs[i], xs[i + 1]
                if x0 <= t <= x1:
                    y0, y1 = ys[i], ys[i + 1]
                    ratio = (t - x0) / (x1 - x0) if x1 != x0 else 0.0
                    v = y0 + (y1 - y0) * ratio
                    break
        if floor is not None:
            v = max(v, floor)
        out.append(v)
    return out


def _month_to_year_idx(month: int) -> int | None:
    """Map month 1..120 to year index 0..9."""
    if month < 1:
        return None
    idx = math.ceil(month / 12) - 1
    return idx if 0 <= idx < 10 else None


def _build_nwl_operating_annual_model() -> list[dict]:
    """Build NWL 10-year annual operating model in EUR (config-driven + UI overrides)."""
    cfg = operations_config.get("nwl", {})
    on_ramp_cfg = cfg.get("on_ramp", {})
    greenfield_cfg = cfg.get("greenfield", {})
    brownfield_cfg = cfg.get("brownfield", {})
    bulk_cfg = cfg.get("bulk_services", {})
    om_cfg = cfg.get("om", {})
    srv_cfg = cfg.get("sewerage_revenue_sharing", {})

    months_semi = list(range(6, 121, 6))  # M6 .. M120
    month_to_idx = {m: i for i, m in enumerate(months_semi)}

    ramp_rows = on_ramp_cfg.get("rows", [])
    cap_points = [(int(r.get("period_months", 0)), r.get("capacity_available_mld")) for r in ramp_rows]
    cap_points = [(m, float(v)) for m, v in cap_points if v is not None]
    if not any(m == 6 for m, _ in cap_points):
        cap_points.append((6, 0.0))
    if not any(m == 12 for m, _ in cap_points):
        cap_points.append((12, 0.0))
    cap_points = sorted(cap_points, key=lambda x: x[0])
    cap_months = [m for m, _ in cap_points]
    cap_vals = [v for _, v in cap_points]
    sewage_capacity = _extrapolate_piecewise_linear(cap_months, cap_vals, months_semi, floor=0.0)

    demand_months = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    piped_sewage_base = [float(x) for x in greenfield_cfg.get("piped_sewage_topcos_mld", [0.0] * 10)]
    construction_base = [float(x) for x in greenfield_cfg.get("construction_water_demand_topcos_mld", [0.0] * 10)]
    latent_base = [float(x) for x in brownfield_cfg.get("latent_demand_quantified", [0.0] * 10)]

    piped_sewage_demand = _extrapolate_piecewise_linear(demand_months, piped_sewage_base, months_semi, floor=0.0)
    construction_demand = _extrapolate_piecewise_linear(demand_months, construction_base, months_semi, floor=0.0)
    latent_demand = _extrapolate_piecewise_linear(demand_months, latent_base, months_semi, floor=0.0)

    annual_growth_pct = _state_float("nwl_greenfield_growth_pct", greenfield_cfg.get("annual_growth_pct_default", 7.7))
    brine_pct = _state_float("nwl_greenfield_brine_pct", greenfield_cfg.get("brine_pct_default", 10.0))
    sewage_rate_2025 = _state_float("nwl_greenfield_sewage_rate_2025", greenfield_cfg.get("sewage_rate_2025_r_per_kl", 46.40))
    water_rate_2025 = _state_float("nwl_greenfield_water_rate_2025", greenfield_cfg.get("water_rate_2025_r_per_kl", 62.05))
    reuse_ratio = _state_float("nwl_greenfield_reuse_ratio", greenfield_cfg.get("reuse_ratio_default", 0.80))

    srv_joburg_price = _state_float("nwl_srv_joburg_price", srv_cfg.get("joburg_price_r_per_kl_default", 46.40))
    srv_growth_pct = _state_float("nwl_srv_growth_pct", srv_cfg.get("growth_pct_default", 7.70))
    srv_transport_r_km = _state_float("nwl_srv_transport_r_km", srv_cfg.get("transport_r_per_km_default", 28.0))
    srv_truck_capacity_m3 = max(_state_float("nwl_srv_truck_capacity_m3", srv_cfg.get("truck_capacity_m3_default", 10.0)), 1.0)
    srv_nwl_distance_km = _state_float("nwl_srv_nwl_distance_km", srv_cfg.get("nwl_roundtrip_km_default", 10.0))
    srv_gov_distance_km = _state_float("nwl_srv_gov_distance_km", srv_cfg.get("gov_roundtrip_km_default", 100.0))
    srv_saving_to_market_pct = _state_float("nwl_srv_saving_to_market_pct", srv_cfg.get("saving_to_market_pct_default", 40.0))

    sewage_sold = [min(cap, dem) for cap, dem in zip(sewage_capacity, piped_sewage_demand)]
    overflow_brownfield = [max(cap - sold, 0.0) for cap, sold in zip(sewage_capacity, sewage_sold)]
    reuse_capacity = [cap * (1.0 - brine_pct / 100.0) for cap in sewage_capacity]
    reuse_topcos_demand = [sold * reuse_ratio for sold in sewage_sold]
    reuse_sold_topcos = [min(cap, dem) for cap, dem in zip(reuse_capacity, reuse_topcos_demand)]
    reuse_after_topcos = [max(cap - sold, 0.0) for cap, sold in zip(reuse_capacity, reuse_sold_topcos)]
    reuse_sold_construction = [min(rem, dem) for rem, dem in zip(reuse_after_topcos, construction_demand)]
    reuse_overflow_agri = [max(cap - sold1 - sold2, 0.0) for cap, sold1, sold2 in zip(reuse_capacity, reuse_sold_topcos, reuse_sold_construction)]
    brownfield_served = [min(cap, dem) for cap, dem in zip(overflow_brownfield, latent_demand)]

    growth_factor = 1.0 + (annual_growth_pct / 100.0)
    sewage_rates = [sewage_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    water_rates = [water_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    agri_base = float(brownfield_cfg.get("agri_base_2025_r_per_kl", 37.70))
    agri_rates = [agri_base * (growth_factor ** (m / 12.0)) for m in months_semi]

    srv_processing_fee_truck = srv_joburg_price * srv_truck_capacity_m3
    srv_transport_nwl = srv_transport_r_km * srv_nwl_distance_km
    srv_transport_gov = srv_transport_r_km * srv_gov_distance_km
    srv_saving_per_m3_transport = (srv_transport_gov - srv_transport_nwl) / srv_truck_capacity_m3
    srv_market_price = max(srv_saving_per_m3_transport * (srv_saving_to_market_pct / 100.0), 0.0)
    srv_growth_factor = 1.0 + (srv_growth_pct / 100.0)
    honeysucker_rates = [srv_market_price * (srv_growth_factor ** (m / 12.0)) for m in months_semi]

    half_year_kl_per_mld = 1000.0 * 365.0 / 2.0
    rev_gf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(sewage_sold, sewage_rates)]
    rev_bf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(brownfield_served, honeysucker_rates)]
    rev_gf_reuse_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_topcos, water_rates)]
    rev_construction_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_construction, water_rates)]
    rev_agri_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_overflow_agri, agri_rates)]

    rev_bulk_zar_year = [0.0 for _ in range(10)]
    for row in bulk_cfg.get("rows", []):
        amount = float(row.get("price_zar", 0.0))
        receipt_period = max(float(row.get("receipt_period", 12.0)), 0.0)
        if amount <= 0.0:
            continue
        if receipt_period == 0.0:
            yi = _month_to_year_idx(12)
            if yi is not None:
                rev_bulk_zar_year[yi] += amount
            continue
        start_m = 13  # Y2 start — bulk services received entirely in Y2
        end_m = start_m + receipt_period
        for mi in range(1, 121):
            if start_m <= mi < end_m:
                yi = _month_to_year_idx(mi)
                if yi is not None:
                    rev_bulk_zar_year[yi] += amount / receipt_period

    om_monthly_fee = float(om_cfg.get("flat_fee_per_month_zar", 0.0))
    om_index_pa = float(om_cfg.get("annual_indexation_pa", 0.0))
    om_start_month = int(om_cfg.get("opex_start_month", 12))
    om_zar_year = [0.0 for _ in range(10)]
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < om_start_month:
            continue
        years_from_start = (mi - om_start_month) / 12.0
        monthly_cost = om_monthly_fee * ((1.0 + om_index_pa) ** years_from_start)
        om_zar_year[yi] += monthly_cost

    # Power / electricity cost (inter-company from LanRED solar at Eskom -10%)
    power_cfg = cfg.get("power", {})
    power_kwh_per_m3 = _state_float("nwl_power_kwh_per_m3", float(power_cfg.get("kwh_per_m3", 0.4)))
    eskom_base = _state_float("nwl_power_eskom_base", float(power_cfg.get("eskom_base_rate_r_per_kwh", 2.81)))
    ic_discount = _state_float("nwl_power_ic_discount", float(power_cfg.get("ic_discount_pct", 10.0)))
    power_rate = eskom_base * (1.0 - ic_discount / 100.0)
    power_escalation = _state_float("nwl_power_escalation", float(power_cfg.get("annual_escalation_pct", 10.0))) / 100.0
    power_start_month = int(power_cfg.get("start_month", 18))
    power_zar_year = [0.0 for _ in range(10)]
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < power_start_month:
            continue
        # Get capacity at this month via interpolation
        cap_mld = 0.0
        for ci in range(len(cap_months) - 1):
            if cap_months[ci] <= mi <= cap_months[ci + 1]:
                frac = (mi - cap_months[ci]) / max(cap_months[ci + 1] - cap_months[ci], 1)
                cap_mld = cap_vals[ci] + frac * (cap_vals[ci + 1] - cap_vals[ci])
                break
        else:
            if mi >= cap_months[-1]:
                cap_mld = cap_vals[-1]
        volume_m3_per_day = cap_mld * 1000.0
        kwh_per_day = volume_m3_per_day * power_kwh_per_m3
        years_from_start = (mi - power_start_month) / 12.0
        rate_indexed = power_rate * ((1.0 + power_escalation) ** years_from_start)
        power_zar_year[yi] += kwh_per_day * rate_indexed * 30.44  # avg days per month

    # CoE rent (capital-recovery: CapEx × (WACC + O&M) — mirrors TWX coe_lease revenue)
    # Stops after CoE sale to LLC (TWX sells CoE in year N → NWL stops paying rent)
    rent_cfg = cfg.get("coe_rent", {})
    rent_om_pct = float(rent_cfg.get("om_overhead_pct", 2.0))
    rent_monthly_eur, rent_annual_eur, _rent_wacc, _rent_coe_capex = compute_coe_rent_monthly_eur(rent_om_pct)
    rent_monthly_zar = rent_monthly_eur * FX_RATE
    rent_esc_pct = float(rent_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    rent_start_month = int(rent_cfg.get("start_month", 24))
    _twx_sale_cfg = operations_config.get("timberworx", {}).get("coe_sale_to_llc", {})
    _rent_sale_enabled = _twx_sale_cfg.get("enabled", False)
    _rent_sale_year = int(_twx_sale_cfg.get("sale_year", 4))
    _rent_end_month = _rent_sale_year * 12 if _rent_sale_enabled else 999
    rent_zar_year = [0.0 for _ in range(10)]
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < rent_start_month or mi > _rent_end_month:
            continue
        years_from_start = (mi - rent_start_month) / 12.0
        rent_indexed = rent_monthly_zar * ((1.0 + rent_esc_pct) ** years_from_start)
        rent_zar_year[yi] += rent_indexed

    annual_rows = []
    for yi in range(10):
        m1 = 6 + yi * 12
        m2 = 12 + yi * 12
        i1 = month_to_idx.get(m1)
        i2 = month_to_idx.get(m2)
        if i1 is None or i2 is None:
            semi_idx = []
        else:
            semi_idx = [i1, i2]

        def ysum(arr: list[float]) -> float:
            return sum(arr[i] for i in semi_idx) if semi_idx else 0.0

        gf_sewage_eur = ysum(rev_gf_sewage_zar) / FX_RATE
        bf_sewage_eur = ysum(rev_bf_sewage_zar) / FX_RATE
        gf_reuse_eur = ysum(rev_gf_reuse_zar) / FX_RATE
        construction_eur = ysum(rev_construction_zar) / FX_RATE
        agri_eur = ysum(rev_agri_zar) / FX_RATE
        bulk_eur = rev_bulk_zar_year[yi] / FX_RATE
        om_eur = om_zar_year[yi] / FX_RATE

        # Volume tracking (for levelized cost, capacity graphs)
        vol_capacity_avg = sum(sewage_capacity[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_treated_avg = sum(sewage_sold[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_annual_m3 = vol_treated_avg * 1000.0 * 365.0
        # Product-specific volumes for LCOW benchmarking
        vol_reuse_avg = sum(
            reuse_sold_topcos[i] + reuse_sold_construction[i] + reuse_overflow_agri[i]
            for i in semi_idx
        ) / len(semi_idx) if semi_idx else 0.0
        vol_brownfield_avg = sum(brownfield_served[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_reuse_annual_m3 = vol_reuse_avg * 1000.0 * 365.0
        vol_brownfield_annual_m3 = vol_brownfield_avg * 1000.0 * 365.0

        rent_eur = rent_zar_year[yi] / FX_RATE

        annual_rows.append({
            "year": yi + 1,
            "rev_greenfield_sewage": gf_sewage_eur,
            "rev_brownfield_sewage": bf_sewage_eur,
            "rev_sewage": gf_sewage_eur + bf_sewage_eur,
            "rev_greenfield_reuse": gf_reuse_eur,
            "rev_construction": construction_eur,
            "rev_agri": agri_eur,
            "rev_reuse": gf_reuse_eur + construction_eur + agri_eur,
            "rev_operating": gf_sewage_eur + bf_sewage_eur + gf_reuse_eur + construction_eur + agri_eur,
            "rev_bulk_services": bulk_eur,
            "rev_total": gf_sewage_eur + bf_sewage_eur + gf_reuse_eur + construction_eur + agri_eur + bulk_eur,
            "om_cost": om_eur,
            "power_cost": power_zar_year[yi] / FX_RATE,
            "rent_cost": rent_eur,
            "vol_capacity_mld": vol_capacity_avg,
            "vol_treated_mld": vol_treated_avg,
            "vol_annual_m3": vol_annual_m3,
            "vol_reuse_annual_m3": vol_reuse_annual_m3,
            "vol_brownfield_annual_m3": vol_brownfield_annual_m3,
            "power_zar": power_zar_year[yi],
            "om_zar": om_zar_year[yi],
            "rent_zar": rent_zar_year[yi],
        })
    return annual_rows


def _build_lanred_operating_annual_model() -> list[dict]:
    """Build LanRED 10-year annual operating model in EUR.

    Four revenue streams:
    1. IC NWL power sales (Eskom -10%, demand-driven share from NWL volume)
    2. Smart City tenant off-take (Joburg tariff -10%, growing share)
    3. Open market sales (residual solar capacity)
    4. BESS TOU arbitrage (charge off-peak, discharge peak)
    Costs = O&M (fixed + variable) + Grid connection fees.
    PV and BESS capacities derived from assets.json budgets.
    """
    if _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
        return _build_lanred_brownfield_operating_annual_model()
    lanred_cfg = operations_config.get("lanred", {})
    solar_cfg = lanred_cfg.get("solar_capacity", {})
    bess_cfg = lanred_cfg.get("battery_storage", {})
    power_sales_cfg = lanred_cfg.get("power_sales", {})
    om_cfg = lanred_cfg.get("om", {})
    grid_cfg = lanred_cfg.get("grid_connection", {})

    # ── Derive PV/BESS capacity from budget + slider allocation ──
    _assets = load_config("assets")["assets"]
    _solar_items = _assets.get("solar", {}).get("line_items", [])
    _total_solar_budget = _assets.get("solar", {}).get("total", 2908809)
    # Default BESS % from assets.json
    _bess_from_assets = sum(li['budget'] for li in _solar_items if 'bess' in li.get('delivery', '').lower() or 'battery' in li.get('delivery', '').lower() or 'li-ion' in li.get('delivery', '').lower())
    _default_bess_pct = round(_bess_from_assets / _total_solar_budget * 100) if _total_solar_budget > 0 else 14
    # Read slider value (set by LanRED Operations tab)
    _bess_pct = _state_float("lanred_bess_alloc_pct", _default_bess_pct) / 100.0
    _bess_budget = _total_solar_budget * _bess_pct
    _pv_budget = _total_solar_budget - _bess_budget

    cost_per_kwp = float(solar_cfg.get("cost_per_kwp_eur", 850))
    installed_kwp = _pv_budget / cost_per_kwp if cost_per_kwp > 0 else 0
    installed_mwp = installed_kwp / 1000.0

    capacity_factor_base = float(solar_cfg.get("capacity_factor_pct", 21.5)) / 100.0
    solar_degradation_pa = float(solar_cfg.get("degradation_pa_pct", 0.5)) / 100.0
    cod_month = int(solar_cfg.get("cod_month", 18))

    # ── Derive BESS capacity from budget ──
    cost_per_kwh_bess = float(bess_cfg.get("cost_per_kwh_eur", 364))
    bess_capacity_kwh = _bess_budget / cost_per_kwh_bess if cost_per_kwh_bess > 0 else 0
    bess_usable_pct = float(bess_cfg.get("usable_capacity_pct", 90.0)) / 100.0
    bess_rt_eff = float(bess_cfg.get("roundtrip_efficiency_pct", 85.0)) / 100.0
    bess_degradation_pa = float(bess_cfg.get("degradation_pa_pct", 2.0)) / 100.0
    bess_cycles = int(bess_cfg.get("cycles_per_year", 260))

    # ── NWL demand-driven IC share ──
    ic_nwl_cfg = power_sales_cfg.get("ic_nwl", {})
    eskom_base = float(ic_nwl_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
    ic_discount = float(ic_nwl_cfg.get("ic_discount_pct", 10.0))
    ic_rate = eskom_base * (1.0 - ic_discount / 100.0)
    ic_escalation = float(ic_nwl_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    ic_demand_driven = ic_nwl_cfg.get("demand_driven", False)
    ic_start_month = int(ic_nwl_cfg.get("start_month", 18))

    # NWL power demand: volume × kWh/m³ × 365 days
    nwl_cfg = operations_config.get("nwl", {})
    nwl_power_cfg = nwl_cfg.get("power", {})
    kwh_per_m3 = float(nwl_power_cfg.get("kwh_per_m3", 0.4))
    nwl_on_ramp = nwl_cfg.get("on_ramp", {}).get("rows", [])

    # Stream 2: Smart City tenant off-take (growing share)
    sc_cfg = power_sales_cfg.get("smart_city_offtake", {})
    sc_enabled = sc_cfg.get("enabled", False)
    sc_joburg_tariff = float(sc_cfg.get("joburg_business_tariff_r_per_kwh", 2.289))
    sc_discount = float(sc_cfg.get("discount_pct", 10.0))
    sc_rate = sc_joburg_tariff * (1.0 - sc_discount / 100.0)
    sc_escalation = float(sc_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    sc_start_month = int(sc_cfg.get("start_month", 36))
    sc_share_by_year = [s / 100.0 for s in sc_cfg.get("share_of_generation_pct_by_year",
                        [0, 0, 15, 25, 30, 35, 40, 45, 50, 50])]

    # Stream 3: Open market sales (residual capacity)
    mkt_cfg = power_sales_cfg.get("open_market", {})
    mkt_enabled = mkt_cfg.get("enabled", False)
    mkt_rate = float(mkt_cfg.get("rate_r_per_kwh", 1.50))
    mkt_escalation = float(mkt_cfg.get("annual_escalation_pct", 8.0)) / 100.0
    mkt_start_month = int(mkt_cfg.get("start_month", 36))

    # Stream 4: BESS TOU arbitrage (2-cycle seasonal model)
    arb_cfg = power_sales_cfg.get("bess_arbitrage", {})
    arb_enabled = arb_cfg.get("enabled", False)
    arb_escalation = float(arb_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    arb_start_month = int(arb_cfg.get("start_month", 18))
    arb_solar_cost = float(arb_cfg.get("solar_charge_cost_r_per_kwh", 0.10))
    # Seasonal rates (HD = Jun-Aug 3 months, LD = Sep-May 9 months)
    hd_cfg = arb_cfg.get("high_demand_season", {})
    ld_cfg = arb_cfg.get("low_demand_season", {})
    hd_peak_rate = float(hd_cfg.get("peak_rate_r_per_kwh", 7.04))
    hd_offpeak_rate = float(hd_cfg.get("offpeak_rate_r_per_kwh", 1.02))
    hd_cycles_per_day = int(hd_cfg.get("cycles_per_day", 2))
    hd_months = int(hd_cfg.get("months", 3))
    ld_peak_rate = float(ld_cfg.get("peak_rate_r_per_kwh", 2.00))
    ld_offpeak_rate = float(ld_cfg.get("offpeak_rate_r_per_kwh", 1.59))
    ld_cycles_per_day = int(ld_cfg.get("cycles_per_day", 1))
    ld_months = int(ld_cfg.get("months", 9))
    # Fallback for old single-rate config
    if "high_demand_season" not in arb_cfg:
        hd_peak_rate = float(arb_cfg.get("peak_rate_r_per_kwh", 7.04))
        hd_offpeak_rate = float(arb_cfg.get("offpeak_rate_r_per_kwh", 1.02))
        ld_peak_rate = hd_peak_rate
        ld_offpeak_rate = hd_offpeak_rate
        hd_cycles_per_day = 1
        ld_cycles_per_day = 1

    # O&M costs
    om_fixed_annual_zar = float(om_cfg.get("fixed_annual_zar", 120000))
    om_variable_r_kwh = float(om_cfg.get("variable_r_per_kwh", 0.05))
    om_indexation = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start_month = int(om_cfg.get("opex_start_month", 18))

    # Grid connection costs
    grid_monthly_zar = float(grid_cfg.get("monthly_availability_charge_zar", 5000))
    grid_escalation = float(grid_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    grid_start_month = int(grid_cfg.get("start_month", 18))

    # Compute annual generation, revenue, and costs
    annual_rows = []
    for yi in range(10):
        year = yi + 1
        y_start = yi * 12 + 1
        y_end = (yi + 1) * 12

        # Solar generation (kWh) with degradation
        years_since_cod = max((y_start - cod_month) / 12.0, 0.0)
        capacity_factor_adj = capacity_factor_base * ((1.0 - solar_degradation_pa) ** years_since_cod)

        # Hours in year (account for partial year if COD mid-year)
        if y_start < cod_month <= y_end:
            months_operating = (y_end - cod_month + 1)
            hours_operating = months_operating * 30.44 * 24
        elif y_end < cod_month:
            hours_operating = 0.0
        else:
            hours_operating = 365.25 * 24

        annual_generation_kwh = installed_mwp * 1000 * capacity_factor_adj * hours_operating

        years_from_cod = max((y_start - cod_month) / 12.0, 0.0)

        # ── Stream 1: IC NWL (demand-driven share) ──
        if ic_demand_driven and annual_generation_kwh > 0:
            # Get NWL volume for this year from on-ramp schedule
            _nwl_mld = 0.0
            for _row in nwl_on_ramp:
                if _row['period_months'] <= y_end:
                    _cap = _row.get('capacity_available_mld')
                    if _cap is not None:
                        _nwl_mld = _cap
            # NWL annual demand = volume_m3/day × kWh/m³ × 365
            _nwl_annual_kwh = _nwl_mld * 1000.0 * kwh_per_m3 * 365.25
            ic_share = min(_nwl_annual_kwh / annual_generation_kwh, 1.0)
        else:
            ic_share = 0.0

        if y_end >= ic_start_month and annual_generation_kwh > 0:
            ic_rate_indexed = ic_rate * ((1.0 + ic_escalation) ** years_from_cod)
            ic_kwh = annual_generation_kwh * ic_share
            rev_ic_nwl_zar = ic_kwh * ic_rate_indexed
        else:
            ic_share = 0.0
            rev_ic_nwl_zar = 0.0

        # ── Stream 2: Smart City tenant off-take (share grows per year) ──
        if sc_enabled and y_end >= sc_start_month:
            sc_share = sc_share_by_year[yi] if yi < len(sc_share_by_year) else sc_share_by_year[-1]
            years_from_sc_start = max((y_start - sc_start_month) / 12.0, 0.0)
            sc_rate_indexed = sc_rate * ((1.0 + sc_escalation) ** years_from_sc_start)
            sc_kwh = annual_generation_kwh * sc_share
            rev_sc_zar = sc_kwh * sc_rate_indexed
        else:
            sc_share = 0.0
            rev_sc_zar = 0.0

        # ── Stream 3: Open market (residual = 100% - NWL - Smart City) ──
        if mkt_enabled and y_end >= mkt_start_month:
            mkt_share = max(1.0 - ic_share - sc_share, 0.0)
            years_from_mkt_start = max((y_start - mkt_start_month) / 12.0, 0.0)
            mkt_rate_indexed = mkt_rate * ((1.0 + mkt_escalation) ** years_from_mkt_start)
            mkt_kwh = annual_generation_kwh * mkt_share
            rev_mkt_zar = mkt_kwh * mkt_rate_indexed
        else:
            mkt_share = 0.0
            rev_mkt_zar = 0.0

        # ── Stream 4: BESS 2-cycle seasonal TOU arbitrage ──
        if arb_enabled and y_end >= arb_start_month:
            _bess_years = max((y_start - cod_month) / 12.0, 0.0)
            _bess_eff_capacity = bess_capacity_kwh * bess_usable_pct * ((1.0 - bess_degradation_pa) ** _bess_years)
            _esc = (1.0 + arb_escalation) ** _bess_years
            # Partial year fraction if COD mid-year
            if y_start < arb_start_month <= y_end:
                _operating_frac = (y_end - arb_start_month + 1) / 12.0
            else:
                _operating_frac = 1.0
            # High Demand season (3 months): 2 cycles/day
            #   Cycle 1: grid off-peak → morning peak
            _hd_c1_spread = (hd_peak_rate * _esc * bess_rt_eff) - (hd_offpeak_rate * _esc)
            _hd_c1_days = hd_months * 30.4 * _operating_frac
            _hd_c1_rev = _bess_eff_capacity * max(_hd_c1_spread, 0) * _hd_c1_days
            #   Cycle 2: own solar → evening peak
            _hd_c2_spread = (hd_peak_rate * _esc * bess_rt_eff) - (arb_solar_cost * _esc)
            _hd_c2_rev = _bess_eff_capacity * max(_hd_c2_spread, 0) * _hd_c1_days
            # Low Demand season (9 months): 1 cycle/day (solar→peak only)
            _ld_c2_spread = (ld_peak_rate * _esc * bess_rt_eff) - (arb_solar_cost * _esc)
            _ld_c2_days = ld_months * 30.4 * _operating_frac
            _ld_c2_rev = _bess_eff_capacity * max(_ld_c2_spread, 0) * _ld_c2_days
            rev_bess_arb_zar = _hd_c1_rev + _hd_c2_rev + _ld_c2_rev
        else:
            rev_bess_arb_zar = 0.0
            _bess_eff_capacity = 0.0

        # O&M costs
        if y_end >= om_start_month:
            years_from_om_start = max((y_start - om_start_month) / 12.0, 0.0)
            om_fixed_indexed = om_fixed_annual_zar * ((1.0 + om_indexation) ** years_from_om_start)
            om_variable_zar = annual_generation_kwh * om_variable_r_kwh
            om_total_zar = om_fixed_indexed + om_variable_zar
        else:
            om_total_zar = 0.0

        # Grid connection costs
        if y_end >= grid_start_month:
            years_from_grid_start = max((y_start - grid_start_month) / 12.0, 0.0)
            grid_monthly_indexed = grid_monthly_zar * ((1.0 + grid_escalation) ** years_from_grid_start)
            if y_start < grid_start_month <= y_end:
                months_grid = (y_end - grid_start_month + 1)
            else:
                months_grid = 12
            grid_annual_zar = grid_monthly_indexed * months_grid
        else:
            grid_annual_zar = 0.0

        # Convert to EUR
        rev_ic_nwl = rev_ic_nwl_zar / FX_RATE
        rev_sc = rev_sc_zar / FX_RATE
        rev_mkt = rev_mkt_zar / FX_RATE
        rev_bess = rev_bess_arb_zar / FX_RATE
        rev_total = rev_ic_nwl + rev_sc + rev_mkt + rev_bess
        om_cost = om_total_zar / FX_RATE
        grid_cost = grid_annual_zar / FX_RATE

        annual_rows.append({
            "year": year,
            "installed_mwp": installed_mwp,
            "bess_capacity_kwh": bess_capacity_kwh,
            "bess_effective_kwh": _bess_eff_capacity,
            "generation_kwh": annual_generation_kwh,
            "capacity_factor_pct": capacity_factor_adj * 100,
            "rev_ic_nwl": rev_ic_nwl,
            "rev_smart_city": rev_sc,
            "rev_open_market": rev_mkt,
            "rev_bess_arbitrage": rev_bess,
            "ic_share_pct": ic_share * 100,
            "sc_share_pct": sc_share * 100,
            "mkt_share_pct": mkt_share * 100,
            "rev_power_sales": rev_total,
            "rev_operating": rev_total,
            "rev_total": rev_total,
            "om_cost": om_cost + grid_cost,
            "grid_cost": grid_cost,
            "power_cost": 0.0,
            "rent_cost": 0.0,
        })

    return annual_rows


def _build_lanred_brownfield_operating_annual_model() -> list[dict]:
    """Brownfield+ operating model: 5 Northlands sites, contracted tenant PPAs."""
    bf_cfg = operations_config['lanred']['brownfield_plus']
    np_cfg = bf_cfg['northlands_portfolio']
    sites = np_cfg['sites']

    total_monthly_rev = sum(s['monthly_income_zar'] for s in sites)
    total_monthly_cogs = sum(s['monthly_cogs_zar'] for s in sites)
    total_monthly_ins = sum(s['monthly_insurance_zar'] for s in sites)
    total_monthly_om = sum(s['monthly_om_zar'] for s in sites)
    rev_esc = np_cfg['revenue_escalation_pct'] / 100.0
    cost_esc = np_cfg['cost_escalation_pct'] / 100.0

    annual_rows = []
    for yi in range(10):
        year = yi + 1
        rev_zar = total_monthly_rev * 12 * ((1 + rev_esc) ** yi)
        cogs_zar = total_monthly_cogs * 12 * ((1 + cost_esc) ** yi)
        ins_zar = total_monthly_ins * 12 * ((1 + cost_esc) ** yi)
        om_zar = total_monthly_om * 12 * ((1 + cost_esc) ** yi)
        gross_profit_zar = rev_zar - cogs_zar
        net_zar = gross_profit_zar - ins_zar - om_zar

        rev_eur = rev_zar / FX_RATE
        om_eur = (ins_zar + om_zar) / FX_RATE
        power_cost_eur = cogs_zar / FX_RATE

        annual_rows.append({
            "year": year,
            "rev_power_sales": rev_eur,
            "rev_operating": rev_eur,
            "rev_total": rev_eur,
            "om_cost": om_eur,
            "power_cost": power_cost_eur,
            "rent_cost": 0.0,
            # Brownfield-specific (for Operations display)
            "rev_northlands_gross_zar": rev_zar,
            "northlands_cogs_zar": cogs_zar,
            "northlands_gross_profit_zar": gross_profit_zar,
            "northlands_ins_zar": ins_zar,
            "northlands_om_zar": om_zar,
            "northlands_net_zar": net_zar,
            # Zero out greenfield-specific keys for P&L compatibility
            "rev_ic_nwl": 0.0,
            "rev_smart_city": 0.0,
            "rev_open_market": 0.0,
            "rev_bess_arbitrage": 0.0,
            "ic_share_pct": 0.0,
            "sc_share_pct": 0.0,
            "mkt_share_pct": 0.0,
            # Generation/capacity (portfolio level)
            "installed_mwp": sum(s['pv_kwp'] for s in sites) / 1000,
            "bess_capacity_kwh": sum(s['bess_kwh'] for s in sites),
            "bess_effective_kwh": 0,
            "generation_kwh": 0,
            "capacity_factor_pct": 0,
            "grid_cost": 0.0,
        })
    return annual_rows


def _build_twx_operating_annual_model() -> list[dict]:
    """Build Timberworx 10-year annual operating model in EUR.

    Three revenue streams:
    1. CoE lease (capital-recovery method with occupancy ramp)
    2. SETA-accredited training programs
    3. Timber sales to large off-takers
    Costs: Fixed + variable O&M
    """
    twx_cfg = operations_config.get("timberworx", {})
    lease_cfg = twx_cfg.get("coe_lease", {})
    training_cfg = twx_cfg.get("training_programs", {})
    sales_cfg = twx_cfg.get("timber_sales", {})
    om_cfg = twx_cfg.get("om", {})

    # CoE sale to LLC
    coe_sale_cfg = twx_cfg.get("coe_sale_to_llc", {})
    coe_sale_enabled = coe_sale_cfg.get("enabled", False)
    coe_sale_year = int(coe_sale_cfg.get("sale_year", 4))
    coe_sale_premium_pct = float(coe_sale_cfg.get("premium_pct", 10.0)) / 100.0

    # CoE Lease Revenue (with occupancy ramp)
    om_pct = float(lease_cfg.get("om_overhead_pct", 2.0))
    monthly_rent_eur, _annual, _wacc, _capex = compute_coe_rent_monthly_eur(om_pct)
    monthly_rental_zar = monthly_rent_eur * FX_RATE
    lease_escalation = float(lease_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    lease_start_month = int(lease_cfg.get("start_month", 24))
    occupancy_ramp = lease_cfg.get("occupancy_ramp", [0.30, 0.50, 0.65, 0.75, 0.80, 0.85, 0.90, 0.90, 0.95, 0.95])

    # Training Revenue
    training_fee_zar = float(training_cfg.get("fee_per_student_zar", 15000))
    seta_subsidy_zar = float(training_cfg.get("seta_subsidy_per_student_zar", 8000))
    training_throughput = training_cfg.get("throughput_students_per_year", [120, 240, 360, 450, 500, 550, 600, 600, 650, 650])
    training_escalation = float(training_cfg.get("annual_escalation_pct", 7.0)) / 100.0
    training_start_month = int(training_cfg.get("start_month", 18))

    # Timber Sales Revenue
    sales_enabled = sales_cfg.get("enabled", True)
    units_per_year = sales_cfg.get("units_per_year", [0, 50, 120, 200, 280, 350, 420, 500, 580, 650])
    price_per_unit_zar = float(sales_cfg.get("price_per_unit_zar", 340000))
    sales_escalation = float(sales_cfg.get("annual_price_escalation_pct", 6.0)) / 100.0
    sales_start_month = int(sales_cfg.get("start_month", 36))
    # Labor cost (service model: TWX factory produces timber panels — no raw materials)
    # TWX Trade procures timber, Greenblocks erects on-site, EPCF finances
    _labor_monthly_p1 = float(sales_cfg.get("labor_monthly_phase1_zar", 130000))
    _p1_houses_per_month = 52.0 / 12.0  # Phase 1: 1 house/week
    labor_per_house_zar = _labor_monthly_p1 / _p1_houses_per_month  # ~R30k/house
    labor_escalation = float(sales_cfg.get("labor_escalation_pct", 5.0)) / 100.0

    # O&M Costs
    om_fixed_annual_zar = float(om_cfg.get("fixed_annual_zar", 180000))
    om_variable_pct = float(om_cfg.get("variable_pct_of_revenue", 5.0)) / 100.0
    om_indexation = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start_month = int(om_cfg.get("opex_start_month", 24))

    annual_rows = []
    for yi in range(10):
        year = yi + 1
        y_start = yi * 12 + 1
        y_end = (yi + 1) * 12

        # CoE Lease Revenue (stops from sale year — CoE sold to LLC)
        coe_sold = coe_sale_enabled and year > coe_sale_year
        coe_sale_this_year = coe_sale_enabled and year == coe_sale_year
        coe_gone = coe_sold or coe_sale_this_year  # True from Y4 (sale year) onwards
        if y_end >= lease_start_month and not coe_gone:
            years_from_lease_start = max((y_start - lease_start_month) / 12.0, 0.0)
            lease_rate_indexed = monthly_rental_zar * ((1.0 + lease_escalation) ** years_from_lease_start)
            occupancy = occupancy_ramp[yi] if yi < len(occupancy_ramp) else occupancy_ramp[-1]
            if y_start < lease_start_month <= y_end:
                months_lease = (y_end - lease_start_month + 1)
            else:
                months_lease = 12
            rev_lease_zar = lease_rate_indexed * months_lease * occupancy
        else:
            rev_lease_zar = 0.0

        # CoE sale proceeds (one-time in sale year): CoE CapEx × (1 + premium)
        if coe_sale_this_year:
            rev_coe_sale_eur = _capex * (1.0 + coe_sale_premium_pct)
        else:
            rev_coe_sale_eur = 0.0

        # Training Revenue (needs CoE — stops from sale year)
        if y_end >= training_start_month and not coe_gone:
            years_from_training_start = max((y_start - training_start_month) / 12.0, 0.0)
            fee_indexed = training_fee_zar * ((1.0 + training_escalation) ** years_from_training_start)
            subsidy_indexed = seta_subsidy_zar * ((1.0 + training_escalation) ** years_from_training_start)
            students_this_year = training_throughput[yi] if yi < len(training_throughput) else training_throughput[-1]
            # Pro-rate for partial year
            if y_start < training_start_month <= y_end:
                months_training = (y_end - training_start_month + 1)
                students_this_year = students_this_year * months_training / 12.0
            rev_training_zar = students_this_year * (fee_indexed + subsidy_indexed)
        else:
            rev_training_zar = 0.0

        # Timber Sales Revenue (service model: labor-only cost)
        if sales_enabled and y_end >= sales_start_month:
            years_from_sales_start = max((y_start - sales_start_month) / 12.0, 0.0)
            unit_price_indexed = price_per_unit_zar * ((1.0 + sales_escalation) ** years_from_sales_start)
            units_this_year = units_per_year[yi] if yi < len(units_per_year) else units_per_year[-1]
            # Pro-rate for partial year
            if y_start < sales_start_month <= y_end:
                months_sales = (y_end - sales_start_month + 1)
                units_this_year = units_this_year * months_sales / 12.0
            rev_timber_gross_zar = units_this_year * unit_price_indexed
            # Labor scales with houses: R130k/month Phase 1 basis → R30k/house
            labor_indexed = labor_per_house_zar * ((1.0 + labor_escalation) ** years_from_sales_start)
            labor_cost_zar = units_this_year * labor_indexed
            # No materials — EPC/JV procures raw materials
            rev_timber_net_zar = rev_timber_gross_zar - labor_cost_zar
        else:
            rev_timber_gross_zar = 0.0
            labor_cost_zar = 0.0
            rev_timber_net_zar = 0.0

        # Total Revenue (operating + one-time CoE sale)
        rev_total_zar = rev_lease_zar + rev_training_zar + rev_timber_net_zar

        # O&M Costs (CoE facility management — stops from sale year)
        if y_end >= om_start_month and not coe_gone:
            years_from_om_start = max((y_start - om_start_month) / 12.0, 0.0)
            om_fixed_indexed = om_fixed_annual_zar * ((1.0 + om_indexation) ** years_from_om_start)
            # Pro-rate for partial year
            if y_start < om_start_month <= y_end:
                months_om = (y_end - om_start_month + 1)
                om_fixed_indexed = om_fixed_indexed * months_om / 12.0
            om_variable_zar = rev_total_zar * om_variable_pct
            om_total_zar = om_fixed_indexed + om_variable_zar
        else:
            om_total_zar = 0.0

        # Convert to EUR
        rev_lease = rev_lease_zar / FX_RATE
        rev_training = rev_training_zar / FX_RATE
        rev_timber = rev_timber_net_zar / FX_RATE
        rev_operating = rev_total_zar / FX_RATE
        rev_total_with_sale = rev_operating + rev_coe_sale_eur
        om_cost = om_total_zar / FX_RATE

        annual_rows.append({
            "year": year,
            "rev_lease": rev_lease,
            "rev_training": rev_training,
            "rev_timber_gross": rev_timber_gross_zar / FX_RATE,
            "rev_timber_sales": rev_timber,
            "rev_coe_sale": rev_coe_sale_eur,
            "rev_operating": rev_operating,
            "rev_total": rev_total_with_sale,
            "labor_cost": labor_cost_zar / FX_RATE,
            "om_cost": om_cost,
            "power_cost": 0.0,
            "rent_cost": 0.0,
            "occupancy_pct": occupancy_ramp[yi] * 100 if yi < len(occupancy_ramp) else occupancy_ramp[-1] * 100,
            "students": (training_throughput[yi] if yi < len(training_throughput) else training_throughput[-1]) if (y_end >= training_start_month and not coe_gone) else 0,
            "timber_units": units_per_year[yi] if yi < len(units_per_year) else units_per_year[-1],
            "coe_sold": coe_gone,
        })

    return annual_rows


def build_sub_annual_model(entity_key):
    """Build 10-year annual P&L, Cash Flow, Balance Sheet for a subsidiary.

    Uses IC loan schedules from config. Returns dict with:
        annual: list[dict]       - 10-year annual P&L/CF/BS
        registry: dict           - Asset registry
        sr_schedule: list[dict]  - Senior IC schedule periods
        mz_schedule: list[dict]  - Mezz IC schedule periods
        ops_annual: list[dict]   - Operating model annual data
        depreciable_base: float  - Total depreciable base
        entity_equity: float     - Shareholder equity
    """
    entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
    senior_cfg = structure['sources']['senior_debt']
    mezz_cfg = structure['sources']['mezzanine']

    sr_rate = senior_cfg['interest']['rate'] + INTERCOMPANY_MARGIN  # 5.20%
    mz_rate = mezz_cfg['interest']['total_rate'] + INTERCOMPANY_MARGIN  # 15.25%
    sr_repayments = senior_cfg['repayments']  # 14
    mz_repayments = mezz_cfg.get('repayments', 10)  # 10

    sr_principal = entity_data['senior_portion']
    mz_principal = entity_data['mezz_portion']
    total_sr = sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
    total_mz = sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())

    # Senior IC schedule (with grant-funded prepayments — entity-specific allocation)
    sr_detail = financing['loan_detail']['senior']
    sr_drawdowns = sr_detail['drawdown_schedule']
    sr_periods = [-4, -3, -2, -1]
    sr_prepayments_raw = sr_detail.get('prepayment_periods', {})
    prepay_alloc = sr_detail.get('prepayment_allocation', {})
    entity_prepay_pct = prepay_alloc.get(entity_key, 0.0) if prepay_alloc else 0.0
    sr_prepayments = {k: v * entity_prepay_pct for k, v in sr_prepayments_raw.items()} if entity_prepay_pct > 0 else None

    # DSRA sizing — replicate SCLCA's facility-level DSRA calculation
    _sr_detail_fac = financing['loan_detail']['senior']
    _sr_bal_fac = (_sr_detail_fac['loan_drawdown_total']
                   + _sr_detail_fac['rolled_up_interest_idc']
                   - _sr_detail_fac['grant_proceeds_to_early_repayment']
                   - _sr_detail_fac['gepf_bulk_proceeds'])
    _sr_rate_fac = structure['sources']['senior_debt']['interest']['rate']
    _sr_num_fac = structure['sources']['senior_debt']['repayments']
    _sr_p_fac = _sr_bal_fac / _sr_num_fac
    _sr_i_m24 = _sr_bal_fac * _sr_rate_fac / 2
    dsra_amount_total = 2 * (_sr_p_fac + _sr_i_m24)

    # DSRA allocated 100% to NWL (only NWL gets DSRA)
    dsra_alloc = {'nwl': 1.0}
    entity_dsra_pct = dsra_alloc.get(entity_key, 0.0)
    entity_dsra = dsra_amount_total * entity_dsra_pct

    sr_schedule = build_simple_ic_schedule(
        sr_principal, total_sr, sr_repayments, sr_rate, sr_drawdowns, sr_periods, sr_prepayments,
        dsra_amount=entity_dsra
    )

    # Mezz IC schedule (with DSRA drawdown)
    mz_amount_eur = mezz_cfg['amount_eur']
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    mz_periods = [-4, -3, -2, -1]
    mz_schedule = build_simple_ic_schedule(
        mz_principal, total_mz, mz_repayments, mz_rate, mz_drawdowns, mz_periods,
        dsra_drawdown=entity_dsra
    )

    # Asset value (from breakdown)
    assets_cfg = load_config("assets")["assets"]
    fees_cfg = load_config("fees")
    project_asset_base = sum(
        _build_entity_asset_base(k, assets_cfg)["fee_base"]
        for k in ["nwl", "lanred", "timberworx"]
    )
    project_debt_base = structure['sources']['senior_debt']['amount']
    project_fees = compute_project_fees(fees_cfg, project_debt_base, project_asset_base)
    registry = build_asset_registry(
        entity_key, assets_cfg, fees_cfg, project_fees["fees"], project_asset_base, project_debt_base
    )
    depr_assets = registry["assets"]
    depreciable_base_total = sum(a["depr_base"] for a in depr_assets)

    if entity_key == "nwl":
        ops_annual = _build_nwl_operating_annual_model()
    elif entity_key == "lanred":
        ops_annual = _build_lanred_operating_annual_model()
    elif entity_key == "timberworx":
        ops_annual = _build_twx_operating_annual_model()
    else:
        ops_annual = None

    # Entity-level equity injection and grants
    _equity_map = {'nwl': EQUITY_NWL, 'lanred': EQUITY_LANRED, 'timberworx': EQUITY_TWX}
    entity_equity = _equity_map.get(entity_key, 0.0)
    ta_grant_total = financing.get('prepayments', {}).get('invest_int_ta', {}).get('amount_eur', 0)
    ta_grant_entity = ta_grant_total * entity_prepay_pct  # 100% NWL (same as DTIC)
    # DTIC grant follows prepayment allocation (only NWL gets it)
    dtic_grant_total = financing.get('prepayments', {}).get('dtic_grant', {}).get('amount_eur', 0)
    dtic_grant_entity = dtic_grant_total * entity_prepay_pct
    # GEPF Bulk Services prepayment (also 100% NWL)
    gepf_prepay_total = financing.get('prepayments', {}).get('gepf_bulk_services', {}).get('amount_eur', 0)
    gepf_prepay_entity = gepf_prepay_total * entity_prepay_pct

    # Aggregate semi-annual → annual (months 0-11 = Y1, etc.)
    annual = []
    accumulated_depr = 0.0
    cumulative_pat = 0.0
    cumulative_fcf = 0.0
    _cum_grants = 0.0  # Cumulative non-P&L capital grants (for RE verification)
    _dsra_fd_bal = 0.0  # DSRA Fixed Deposit balance
    _cum_capex = 0.0    # Cumulative capex spent (for FA during construction)
    for yi in range(10):
        a = {'year': yi + 1}
        y_start = yi * 12
        y_end = y_start + 12

        # Senior interest & principal this year
        sr_interest = 0.0
        sr_princ_paid = 0.0
        sr_closing = sr_principal  # default
        for r in sr_schedule:
            if y_start <= r['Month'] < y_end:
                sr_interest += r['Interest']
                sr_princ_paid += abs(r['Principle'])
            if r['Month'] < y_end:
                sr_closing = r['Closing']

        # Mezz interest & principal this year
        mz_interest = 0.0
        mz_princ_paid = 0.0
        mz_closing = mz_principal  # default
        for r in mz_schedule:
            if y_start <= r['Month'] < y_end:
                mz_interest += r['Interest']
                mz_princ_paid += abs(r['Principle'])
            if r['Month'] < y_end:
                mz_closing = r['Closing']

        # P&L (subsidiary perspective: interest is expense)
        a['ie_sr'] = sr_interest
        a['ie_mz'] = mz_interest
        a['ie'] = sr_interest + mz_interest

        # Operating model — load first (need coe_sold flag for TWX depreciation)
        op = ops_annual[yi] if ops_annual else {}
        for k, v in op.items():
            a[k] = v

        # Depreciation starts Y2 (after COD at M18); Y1 = construction
        if yi >= 1:
            if entity_key == 'timberworx' and op.get('coe_sold', False):
                # CoE sold to LLC — stop depreciating CoE building, keep Panel Equipment
                a['depr'] = sum(x["annual_depr"] for x in depr_assets if yi <= x["life"] and x.get("id", "") != "coe_001")
            else:
                a['depr'] = sum(x["annual_depr"] for x in depr_assets if yi <= x["life"])
        else:
            a['depr'] = 0.0
        accumulated_depr += a['depr']

        # Compute P&L (DSRA interest income added to finance section)
        a['ebitda'] = a.get('rev_total', 0.0) - a.get('om_cost', 0.0) - a.get('power_cost', 0.0) - a.get('rent_cost', 0.0)
        a['ebit'] = a['ebitda'] - a['depr']
        a['ii_dsra'] = _dsra_fd_bal * DSRA_RATE if _dsra_fd_bal > 0 else 0.0
        a['pbt'] = a['ebit'] - a['ie'] + a['ii_dsra']
        a['tax'] = max(a['pbt'] * 0.27, 0.0)  # SA corporate tax 27%, only on positive PBT
        a['pat'] = a['pbt'] - a['tax']

        # Cash Flow
        # --- Financing: Drawdowns (construction, Y1-Y2) ---
        a['cf_draw_sr'] = sum(r['Draw Down'] for r in sr_schedule if y_start <= r['Month'] < y_end)
        a['cf_draw_mz'] = sum(r['Draw Down'] for r in mz_schedule if y_start <= r['Month'] < y_end)
        a['cf_draw'] = a['cf_draw_sr'] + a['cf_draw_mz']
        # --- Investing: Capex (mirrors drawdowns, excluding DSRA drawdown which is financing) ---
        a['cf_capex'] = a['cf_draw_sr'] + sum(
            r['Draw Down'] for r in mz_schedule
            if y_start <= r['Month'] < y_end and r['Period'] < 0
        )
        _cum_capex += a['cf_capex']
        # --- Financing: Grant-funded prepayments (reduce IC debt) ---
        a['cf_prepay_sr'] = sum(abs(r.get('Prepayment', 0)) for r in sr_schedule if y_start <= r['Month'] < y_end)
        a['cf_prepay'] = a['cf_prepay_sr']
        # Split prepayment into DTIC and GEPF components
        if a['cf_prepay'] > 0 and (dtic_grant_entity + gepf_prepay_entity) > 0:
            _prepay_dtic_share = dtic_grant_entity / (dtic_grant_entity + gepf_prepay_entity)
            a['cf_prepay_dtic'] = a['cf_prepay'] * _prepay_dtic_share
            a['cf_prepay_gepf'] = a['cf_prepay'] * (1.0 - _prepay_dtic_share)
        else:
            a['cf_prepay_dtic'] = 0.0
            a['cf_prepay_gepf'] = 0.0
        # --- Interest payments (cash) — only after grace (M24 for senior, M24 for mezz) ---
        a['cf_ie_sr'] = sum(r['Interest'] for r in sr_schedule if y_start <= r['Month'] < y_end and r['Month'] >= 24)
        a['cf_ie_mz'] = sum(r['Interest'] for r in mz_schedule if y_start <= r['Month'] < y_end and r['Month'] >= 24)
        a['cf_ie'] = a['cf_ie_sr'] + a['cf_ie_mz']
        # --- Principal repayments (scheduled, after grace) ---
        a['cf_pr_sr'] = sr_princ_paid
        a['cf_pr_mz'] = mz_princ_paid
        a['cf_pr'] = sr_princ_paid + mz_princ_paid
        # --- Total debt service (interest + scheduled principal) ---
        a['cf_ds'] = a['cf_ie'] + a['cf_pr']
        # --- Tax (cash outflow) ---
        a['cf_tax'] = a['tax']
        # --- Cash from Operations = EBITDA + DSRA Interest - Tax ---
        a['cf_ops'] = a['ebitda'] + a['ii_dsra'] - a['cf_tax']
        a['cf_operating_pre_debt'] = a['ebitda']
        a['cf_after_debt_service'] = a['cf_ops'] - a['cf_ds']
        # --- Equity injection (Y1 only) ---
        a['cf_equity'] = entity_equity if yi == 0 else 0.0
        # --- Grants: DTIC only (GEPF is already in EBITDA as rev_bulk_services) ---
        a['cf_grant_dtic'] = dtic_grant_entity if yi == 1 else 0.0   # Y2 (M12)
        a['cf_grant_iic'] = ta_grant_entity if yi == 1 else 0.0      # Y2 (IIC TA)
        a['cf_grants'] = a['cf_grant_dtic'] + a['cf_grant_iic']
        # --- Comprehensive Net Cash Flow ---
        a['cf_net'] = (a['cf_equity']
                       + a['cf_draw'] - a['cf_capex']         # Construction (nets to 0 for non-DSRA)
                       + a['cf_grants'] - a['cf_prepay']      # DTIC + IIC - Prepay
                       + a['cf_ops']                           # EBITDA + DSRA interest - Tax
                       - a['cf_ie'] - a['cf_pr'])              # Debt service
        cumulative_pat += a['pat']
        cumulative_fcf += a['cf_net']

        # DSRA Fixed Deposit: Opening + Deposit + Interest = Closing
        # cf_net already includes ii_dsra (via cf_ops), so DON'T add _dsra_interest again
        _dsra_interest = _dsra_fd_bal * DSRA_RATE
        a['dsra_opening'] = _dsra_fd_bal
        a['dsra_deposit'] = a['cf_net'] - a['ii_dsra']   # operational cash deposited (excl DSRA interest)
        a['dsra_interest'] = _dsra_interest                # FD compounding (= ii_dsra)
        # Check: Opening + Deposit + Interest = Opening + (cf_net - ii_dsra) + ii_dsra = Opening + cf_net ✓
        _dsra_fd_bal = _dsra_fd_bal + a['cf_net']
        a['dsra_bal'] = _dsra_fd_bal

        # Balance Sheet
        _cum_grants += a['cf_grants']
        a['bs_fixed_assets'] = max(min(_cum_capex, depreciable_base_total) - accumulated_depr, 0)
        a['bs_dsra'] = _dsra_fd_bal  # DSRA FD (can be negative during early ops)
        a['bs_assets'] = a['bs_fixed_assets'] + a['bs_dsra']
        a['bs_sr'] = max(sr_closing, 0)  # Senior IC liability (lower due to DSRA)
        a['bs_mz'] = max(mz_closing, 0)  # Mezz IC liability (higher due to DSRA)
        a['bs_debt'] = a['bs_sr'] + a['bs_mz']
        a['bs_equity_sh'] = entity_equity  # Shareholder equity (constant)
        a['bs_equity'] = a['bs_assets'] - a['bs_debt']
        a['bs_retained'] = a['bs_equity'] - a['bs_equity_sh']
        # Independent RE verification: RE should = Cumulative PAT + Capital Grants
        # Grants (DTIC, IIC TA) are non-P&L capital items that increase BS equity
        a['bs_retained_check'] = cumulative_pat + _cum_grants
        a['bs_gap'] = a['bs_retained'] - (cumulative_pat + _cum_grants)

        annual.append(a)
    return {
        "annual": annual,
        "registry": registry,
        "sr_schedule": sr_schedule,
        "mz_schedule": mz_schedule,
        "ops_annual": ops_annual,
        "depreciable_base": depreciable_base_total,
        "entity_equity": entity_equity,
    }


# ============================================================
# SUBSIDIARY VIEW HELPER (defined before use)
# ============================================================
def render_subsidiary(entity_key, icon, name):
    """Render a subsidiary entity view with sub-tabs."""
    entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
    senior = structure['sources']['senior_debt']
    mezz = structure['sources']['mezzanine']

    senior_ic_rate = senior['interest']['rate'] + INTERCOMPANY_MARGIN
    mezz_ic_rate = mezz['interest']['total_rate'] + INTERCOMPANY_MARGIN
    senior_tenure = senior['loan_holiday_months'] + senior['repayment_months']
    mezz_tenure = mezz['roll_up_months'] + mezz.get('repayment_months', 60)
    mezz_reps = mezz.get('repayments', 10)

    # Header - meaningful descriptions per entity
    entity_taglines = {
        'nwl': "2 MLD MABR wastewater treatment plant with water reuse for irrigation and construction",
        'lanred': "2.4 MWp solar PV with battery storage powering the water treatment facility",
        'timberworx': "Centre of Excellence — CLT training, demonstration, and commercial tenants",
    }

    col_logo, col_title = st.columns([1, 5])
    logo_file = ENTITY_LOGOS.get(entity_key)
    with col_logo:
        if logo_file and (LOGO_DIR / logo_file).exists():
            st.image(str(LOGO_DIR / logo_file), width=100)
    with col_title:
        st.title(name)
        st.caption(entity_taglines.get(entity_key, entity_data['purpose']))

    # Sub-tabs (filtered by role)
    _tab_map = make_tab_map(_allowed_tabs)
    if not _tab_map:
        st.warning("No tabs available for your role.")
        return

    # --- OVERVIEW ---
    if "Overview" in _tab_map:
        with _tab_map["Overview"]:
            st.header(f"{name} — Overview")

            subs = structure['subsidiaries']
            sub_data = subs.get(entity_key, {})

            # Entity-specific descriptions from OVERVIEW_CONTENT.md
            _ov_content = load_content_md("OVERVIEW_CONTENT.md")
            _ov_entity = _ov_content.get(entity_key, "")

            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Funding", f"€{entity_data['total_loan']:,.0f}")
            with col2:
                st.metric("Senior IC", f"€{entity_data['senior_portion']:,.0f}")
            with col3:
                st.metric("Mezz IC", f"€{entity_data['mezz_portion']:,.0f}")
            with col4:
                st.metric("Pro-rata Share", f"{entity_data['pro_rata_pct']*100:.1f}%")

            st.divider()

            # Pre-build Uses table HTML string (injected after "Assets" section)
            assets_cfg = load_config("assets")["assets"]
            fees_cfg = load_config("fees")
            _proj_asset_base = sum(
                _build_entity_asset_base(k, assets_cfg)["fee_base"]
                for k in ["nwl", "lanred", "timberworx"]
            )
            _proj_debt_base = structure['sources']['senior_debt']['amount']
            _proj_fees = compute_project_fees(fees_cfg, _proj_debt_base, _proj_asset_base)
            registry = build_asset_registry(
                entity_key, assets_cfg, fees_cfg, _proj_fees["fees"], _proj_asset_base, _proj_debt_base
            )
            _uses_assets = registry["assets"]
            _u_hdr = "<tr><th style='text-align:left;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>Item</th>"
            _u_hdr += "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>All-In Cost</th></tr>"
            _u_rows = ""
            _u_allin_sum = 0
            for _ua in _uses_assets:
                _ai = _ua["depr_base"]
                _u_allin_sum += _ai
                _u_rows += f"<tr><td style='padding:4px 10px;'>{_ua['asset']}</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;font-weight:600;'>€{_ai:,.0f}</td></tr>"
            _u_rows += f"<tr style='border-top:2px solid #1e40af;font-weight:700;background:#eff6ff;'>"
            _u_rows += f"<td style='padding:6px 10px;color:#1e40af;'>TOTAL</td>"
            _u_rows += f"<td style='text-align:right;padding:6px 10px;color:#1e40af;'>€{entity_data['total_loan']:,.0f}</td></tr>"
            _uses_table_html = f"<table style='width:100%;border-collapse:collapse;font-size:13px;'>{_u_hdr}{_u_rows}</table>"

            # Render overview content from MD file, injecting Uses table after "Assets"
            import re as _re_sub_ov
            import base64 as _b64_sub_ov
            def _sub_md_to_html(text):
                text = _re_sub_ov.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                text = _re_sub_ov.sub(r'__(.+?)__', r'<b>\1</b>', text)
                text = _re_sub_ov.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
                # Convert numbered lists (1. item) to <ol><li>
                _lines = text.split("\n")
                _out = []; _in_ol = False
                for _ln in _lines:
                    _m = _re_sub_ov.match(r'^\d+\.\s+(.*)', _ln.strip())
                    if _m:
                        if not _in_ol:
                            _out.append("<ol>")
                            _in_ol = True
                        _out.append(f"<li>{_m.group(1)}</li>")
                    else:
                        if _in_ol:
                            _out.append("</ol>")
                            _in_ol = False
                        _out.append(_ln)
                if _in_ol:
                    _out.append("</ol>")
                return "\n".join(_out)

            if _ov_entity:
                # For NWL: float the plant render, let text flow around it
                if entity_key == 'nwl':
                    _nwl_html_parts = []
                    _plant_img = Path(__file__).parent / "assets" / "images" / "plant-render.png"
                    if _plant_img.exists():
                        _pi_bytes = _plant_img.read_bytes()
                        _pi_b64 = _b64_sub_ov.b64encode(_pi_bytes).decode()
                        _nwl_html_parts.append(
                            f'<img src="data:image/png;base64,{_pi_b64}" '
                            f'style="float:left;width:480px;margin:0 24px 12px 0;border-radius:8px;" />'
                        )
                    for _sect in _ov_entity.split("\n### "):
                        _sect_title = _sect.partition("\n")[0].strip()
                        _sect_body = _sect.partition("\n")[2].strip()
                        if not _sect_title:
                            continue
                        _nwl_html_parts.append(f"<p style='font-size:1.1em;font-weight:600;margin:16px 0 4px 0;'>{_sect_title}</p>")
                        if _sect_body:
                            _nwl_html_parts.append(f"<p>{_sub_md_to_html(_sect_body)}</p>")
                        if _sect_title == "Assets":
                            _nwl_html_parts.append('<div style="clear:both;"></div>')
                            _nwl_html_parts.append(_uses_table_html)
                    _nwl_html_parts.append('<div style="clear:both;"></div>')
                    st.markdown("\n".join(_nwl_html_parts), unsafe_allow_html=True)
                # For LanRED, render scenario-specific content
                elif entity_key == 'lanred':
                    _lr_scenario = _state_str("lanred_scenario", "Greenfield")
                    for _sect in _ov_entity.split("\n### "):
                        _sect_title = _sect.partition("\n")[0].strip()
                        _sect_body = _sect.partition("\n")[2].strip()
                        if _sect_title in ("Summary", "Investment Thesis", "Assets", "Revenue Model"):
                            st.markdown(f"**{_sect_title}**\n\n{_sect_body}")
                            if _sect_title == "Assets":
                                st.markdown(_uses_table_html, unsafe_allow_html=True)
                    _ov_gf_body = ""
                    _ov_bf_body = ""
                    for _sect in _ov_entity.split("\n### "):
                        if _sect.startswith("Greenfield"):
                            _ov_gf_body = _sect.partition("\n")[2].strip()
                        elif _sect.startswith("Brownfield+"):
                            _ov_bf_body = _sect.partition("\n")[2].strip()
                    _ov_lr_col_gf, _ov_lr_col_bf = st.columns(2)
                    for _ov_lr_col, _ov_lr_name, _ov_lr_body, _ov_lr_active in [
                        (_ov_lr_col_gf, "Greenfield", _ov_gf_body, _lr_scenario == "Greenfield"),
                        (_ov_lr_col_bf, "Brownfield+", _ov_bf_body, _lr_scenario == "Brownfield+"),
                    ]:
                        with _ov_lr_col:
                            with st.container(border=True):
                                if _ov_lr_active:
                                    st.markdown(":green[**SELECTED**]")
                                    st.markdown(f"**{_ov_lr_name}**\n\n{_ov_lr_body}")
                                else:
                                    st.markdown(":grey[NOT SELECTED]")
                                    st.markdown(f":grey[**{_ov_lr_name}**]")
                                    st.markdown(f"<div style='color:#9CA3AF;font-size:0.9em;'>{_ov_lr_body}</div>", unsafe_allow_html=True)
                else:
                    # Default (TWX): render sections with Uses table after Assets
                    for _sect in _ov_entity.split("\n### "):
                        _sect_title = _sect.partition("\n")[0].strip()
                        _sect_body = _sect.partition("\n")[2].strip()
                        if not _sect_title:
                            continue
                        if _sect_body:
                            st.markdown(f"**{_sect_title}**\n\n{_sect_body}")
                        else:
                            st.markdown(f"**{_sect_title}**")
                        if _sect_title == "Assets":
                            st.markdown(_uses_table_html, unsafe_allow_html=True)

            st.divider()

            # Corporate details
            st.subheader("Corporate Details")
            st.markdown(f"""
| | |
|---|---|
| **Parent** | Catalytic Assets (SCLCA) |
| **Entity** | {sub_data.get('legal_name', name)} |
| **Registration** | {sub_data.get('registration', 'TBC')} |
| **Code** | {sub_data.get('code', entity_key.upper())} |
| **Type** | {sub_data.get('type', 'Operating Company').replace('_', ' ').title()} |
| **Asset Classes** | {', '.join(a.upper() for a in sub_data.get('assets', []))} |
        """)

    # --- ABOUT ---
    if "About" in _tab_map:
        with _tab_map["About"]:
            st.header(f"{name} — About")

            # Load ABOUT content
            about_sections = load_about_content()
            entity_about = about_sections.get(entity_key, "")

            if entity_about:
                st.markdown(entity_about)
            else:
                st.info(f"About content for {name} is being prepared. Please check back soon.")

                # Show placeholder info
                st.markdown(f"""
                This tab will contain comprehensive information about **{name}**, including:
                - The crisis/problem being addressed
                - The solution and business model
                - Technology details
                - Financing structure (Frontier Funding framework)
                - Impact on Smart City Lanseria
                - Potential for national replication

                Detailed content is available in the ABOUT_TABS_CONTENT.md file.
                """)

    # --- SOURCES & USES ---
    if "Sources & Uses" in _tab_map:
        with _tab_map["Sources & Uses"]:
            st.header("Sources & Uses")

            equity_map = {
                "nwl": EQUITY_NWL,
                "lanred": EQUITY_LANRED,
                "timberworx": EQUITY_TWX
            }
            equity = equity_map.get(entity_key, 0)

            senior_liab = entity_data['senior_portion']
            mezz_liab = entity_data['mezz_portion']
            total_sources = senior_liab + mezz_liab + equity
            mezz_reps = mezz.get('repayments', 10)

            breakdown = entity_data['breakdown']
            water = breakdown.get("water", 0)
            assets_cfg = load_config("assets")["assets"]
            fees_cfg = load_config("fees")
            project_asset_base = sum(
                _build_entity_asset_base(k, assets_cfg)["fee_base"]
                for k in ["nwl", "lanred", "timberworx"]
            )
            project_debt_base = structure['sources']['senior_debt']['amount']
            project_fees = compute_project_fees(fees_cfg, project_debt_base, project_asset_base)
            registry = build_asset_registry(
                entity_key, assets_cfg, fees_cfg, project_fees["fees"], project_asset_base, project_debt_base
            )
            # Use breakdown values from structure.json (not registry) to avoid double-counting WSP
            esg = breakdown.get("esg_mgmt", 0)  # Only NWL has esg_mgmt; others return 0
            fees = breakdown.get("fees", 0)  # Use authoritative fees from structure.json
            cash = equity
            total_uses = water + esg + fees + cash
            adjustment = total_sources - total_uses

            col_sources, col_uses = st.columns(2)
            with col_sources:
                st.markdown("## 📥 SOURCES")
                st.caption("Capital received at operating company level")
                _sclca_logo_src = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")

                _sr_logo_col, _sr_title_col = st.columns([1, 8])
                with _sr_logo_col:
                    if _sclca_logo_src.exists():
                        st.image(str(_sclca_logo_src), width=36)
                with _sr_title_col:
                    st.markdown("### Senior Loan (from SCLCA)")
                st.markdown(f"""
            | | |
            |---|---|
            | **Principal** | €{senior_liab:,.0f} |
            | **Interest** | **{senior_ic_rate*100:.2f}%** |
            | **Tenure** | {senior['loan_holiday_months']} + {senior['repayment_months']} = **{senior_tenure} months** |
            | **Moratorium** | {senior['loan_holiday_months']} months |
            | **Repayments** | {senior['repayments']} {senior['frequency']} |
            | **IDC** | Roll-up, add to principal (+€0) |
            """)

                _mz_logo_col, _mz_title_col = st.columns([1, 8])
                with _mz_logo_col:
                    if _sclca_logo_src.exists():
                        st.image(str(_sclca_logo_src), width=36)
                with _mz_title_col:
                    st.markdown("### Mezzanine (from SCLCA)")
                st.markdown(f"""
            | | |
            |---|---|
            | **Principal** | €{mezz_liab:,.0f} |
            | **Interest** | **{mezz_ic_rate*100:.2f}%** |
            | **Tenure** | {mezz['roll_up_months']} + {mezz.get('repayment_months', 60)} = **{mezz_tenure} months** |
            | **Moratorium** | {mezz['roll_up_months']} months |
            | **Repayments** | {mezz_reps} semi-annual |
            | **IDC** | Roll-up, add to principal (+€0) |
            """)

                _eq_logo_col, _eq_title_col = st.columns([1, 8])
                with _eq_logo_col:
                    if _sclca_logo_src.exists():
                        st.image(str(_sclca_logo_src), width=36)
                with _eq_title_col:
                    st.markdown("### Equity (from SCLCA)")
                st.caption("Shareholder equity deployed to acquire subsidiary stakes")
                _eq = st.columns(3)
                with _eq[0]:
                    st.caption("Total Equity")
                    st.markdown(f"**€{equity:,.0f}**")
                with _eq[1]:
                    st.caption("Purpose")
                    st.markdown("**Working capital & cash buffer**")
                with _eq[2]:
                    st.caption("Timing")
                    st.markdown("**Financial Close**")

                st.markdown(f"**TOTAL SOURCES: €{total_sources:,.0f}**")

            with col_uses:
                st.markdown("## 📤 USES")
                st.caption("Assets, management, fees, and equity")
                _nwl_logo_uses = LOGO_DIR / ENTITY_LOGOS.get(entity_key, "")
                if _nwl_logo_uses.exists():
                    st.image(str(_nwl_logo_uses), width=72)

                st.markdown(f"### {name}")

                # Build detailed uses table with Base Cost, +Services, +Fees, All-In columns
                _uses_assets = registry["assets"]
                _esg_val = breakdown.get('esg_mgmt', 0)
                _svc_total = registry.get("service_total", 0)

                _u_hdr = "<tr><th style='text-align:left;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>Item</th>"
                _u_hdr += "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>Base Cost</th>"
                _u_hdr += "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>+Services</th>"
                _u_hdr += "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>+Fees</th>"
                _u_hdr += "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #1e40af;color:#1e40af;'>All-In</th></tr>"

                _u_rows = ""
                _u_base_sum = 0; _u_svc_sum = 0; _u_fee_sum = 0; _u_allin_sum = 0
                for _ua in _uses_assets:
                    _bc = _ua["base_cost"]
                    _sv = _ua.get("alloc_services", 0)
                    _fe = _ua.get("alloc_fees", 0)
                    _ai = _ua["depr_base"]
                    _u_base_sum += _bc; _u_svc_sum += _sv; _u_fee_sum += _fe; _u_allin_sum += _ai
                    _u_rows += f"<tr><td style='padding:4px 10px;'>{_ua['asset']}</td>"
                    _u_rows += f"<td style='text-align:right;padding:4px 10px;'>€{_bc:,.0f}</td>"
                    _u_rows += f"<td style='text-align:right;padding:4px 10px;color:#64748b;'>€{_sv:,.0f}</td>"
                    _u_rows += f"<td style='text-align:right;padding:4px 10px;color:#64748b;'>€{_fe:,.0f}</td>"
                    _u_rows += f"<td style='text-align:right;padding:4px 10px;font-weight:600;'>€{_ai:,.0f}</td></tr>"

                # Subtotal row
                _u_rows += f"<tr style='border-top:1px solid #cbd5e1;font-weight:600;background:#f1f5f9;'>"
                _u_rows += f"<td style='padding:4px 10px;'>Subtotal — Assets</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;'>€{_u_base_sum:,.0f}</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;color:#64748b;'>€{_u_svc_sum:,.0f}</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;color:#64748b;'>€{_u_fee_sum:,.0f}</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;'>€{_u_allin_sum:,.0f}</td></tr>"

                # Note: ESG & Management costs are already allocated into +Services column above
                # (WSP + ESG items are classified as services, distributed pro-rata by base cost)

                # Equity = Cash row
                _u_rows += f"<tr><td style='padding:4px 10px;'>Equity = Cash</td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;' colspan='3'></td>"
                _u_rows += f"<td style='text-align:right;padding:4px 10px;font-weight:600;'>€{cash:,.0f}</td></tr>"

                # Grand total
                _u_rows += f"<tr style='border-top:2px solid #1e40af;font-weight:700;background:#eff6ff;'>"
                _u_rows += f"<td style='padding:6px 10px;color:#1e40af;'>TOTAL USES</td>"
                _u_rows += f"<td style='text-align:right;padding:6px 10px;' colspan='3'></td>"
                _u_rows += f"<td style='text-align:right;padding:6px 10px;color:#1e40af;'>€{total_sources:,.0f}</td></tr>"

                st.markdown(f"""<table style='width:100%;border-collapse:collapse;font-size:13px;'>
                {_u_hdr}{_u_rows}</table>""", unsafe_allow_html=True)

                if entity_key == 'nwl':
                    st.caption("Services (WSP, ESG) allocated pro-rata by base cost. Fees allocated pro-rata by depreciable base.")

            st.divider()

            # --- Grants & Subsidies (NWL only - these are NWL-specific) ---
            grants_cfg = structure.get('sources', {}).get('grants', {})
            if entity_key == 'nwl' and grants_cfg and grants_cfg.get('rows'):
                with st.container(border=True):
                    st.subheader("Grants & Subsidies")
                    st.caption("Non-diluting equity — capital grants that bridge via senior debt and prepay upon receipt")

                    _grant_rows = []
                    for g in grants_cfg['rows']:
                        amt_zar = g.get('amount_zar')
                        amt_eur = g.get('amount_eur')
                        if amt_zar:
                            _grant_rows.append({
                                "Source": g['source'],
                                "Amount (ZAR)": f"R{amt_zar:,.0f}",
                                "Amount (EUR)": f"€{amt_zar / FX_RATE:,.0f}",
                                "Timing": f"M{g.get('timing_month', g.get('timing_start_month', '?'))}",
                                "Note": g.get('note', ''),
                            })
                        elif amt_eur:
                            _grant_rows.append({
                                "Source": g['source'],
                                "Amount (ZAR)": "—",
                                "Amount (EUR)": f"€{amt_eur:,.0f}",
                                "Timing": f"M{g.get('timing_start_month', '?')}-M{g.get('timing_end_month', '?')}",
                                "Note": g.get('note', ''),
                            })
                    if _grant_rows:
                        render_table(pd.DataFrame(_grant_rows), right_align=["Amount (ZAR)", "Amount (EUR)"])

                    # Timing explanation
                    _prepay = financing.get('loan_detail', {}).get('senior', {}).get('grant_proceeds_to_early_repayment', 0)
                    st.markdown(f"""
**Timing & Treatment**

These grants are **non-diluting quasi-equity** — capital contributions that do not dilute shareholders
and do not carry interest or repayment obligations.

**Timing difference**: The project requires full funding from day 1, but grants arrive at M6–M18.
Senior debt and mezzanine **bridge the gap** — providing 100% of the €{structure['sources']['total']:,.0f}
project cost upfront. When grants are received, they are applied as an **early repayment of senior debt**,
reducing the outstanding balance by **€{_prepay:,.0f}**.

This means:
- **Sources & Uses balance at close** — Senior + Mezz = €{structure['sources']['total']:,.0f} (fully deployed)
- **Grant receipt (M6–M18)** — €{_prepay:,.0f} flows to SCLCA as non-diluting equity
- **Senior debt prepayment** — Grant proceeds immediately retire senior principal, reducing interest burden
- **Net effect** — Lower senior balance from period -2 onward, saving interest over the remaining loan life
""")

                st.divider()

            # ── AUDIT: Sources & Uses ──
            _su_checks = []
            # Senior + Mezz = Total Loan
            _su_checks.append({
                "name": "Senior + Mezz = Total Loan",
                "expected": entity_data['total_loan'],
                "actual": entity_data['senior_portion'] + entity_data['mezz_portion'],
            })
            # Sum of entity loans = facility total
            _all_loans = structure['uses']['loans_to_subsidiaries']
            _facility_total = structure['sources']['senior_debt']['amount'] + structure['sources']['mezzanine']['amount_eur']
            _su_checks.append({
                "name": "Sum entity loans = facility total",
                "expected": _facility_total,
                "actual": sum(v['total_loan'] for v in _all_loans.values()),
            })
            run_page_audit(_su_checks, f"{name} — Sources & Uses")

    # --- BUILD ANNUAL MODEL (needed for all subsequent tabs) ---
    _sub_model = build_sub_annual_model(entity_key)
    _sub_annual = _sub_model["annual"]
    _sub_registry = _sub_model["registry"]
    _sub_sr_schedule = _sub_model["sr_schedule"]
    _sub_mz_schedule = _sub_model["mz_schedule"]
    _sub_ops_annual = _sub_model["ops_annual"]
    _sub_depr_base = _sub_model["depreciable_base"]
    _sub_entity_equity = _sub_model["entity_equity"]
    _years = [f"Y{a['year']}" for a in _sub_annual]

    # --- FACILITIES ---
    if "Facilities" in _tab_map:
        with _tab_map["Facilities"]:
            st.header("Facilities")
            st.caption("Liability-side facility schedules (loans from SCLCA)")

            ic_format = {
                "Year": "{:.1f}",
                "Opening": "€{:,.0f}",
                "Draw Down": "€{:,.0f}",
                "Interest": "€{:,.0f}",
                "Principle": "€{:,.0f}",
                "Repayment": "€{:,.0f}",
                "Movement": "€{:,.0f}",
                "Closing": "€{:,.0f}"
            }

            loans = structure['uses']['loans_to_subsidiaries']
            senior_detail = financing['loan_detail']['senior']
            senior_drawdown_schedule = senior_detail['drawdown_schedule']
            senior_drawdown_periods = [-4, -3, -2, -1]
            senior_total = sum(l["senior_portion"] for l in loans.values())
            mezz_total = sum(l["mezz_portion"] for l in loans.values())
            mezz_amount_eur = mezz['amount_eur']
            mezz_repayments = 10
            mezz_ic_reps = mezz_repayments
            mezz_ic_drawdown_schedule = [mezz_amount_eur, 0, 0, 0]
            mezz_ic_periods = [-4, -3, -2, -1]

            _facility_logo = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")

            if entity_key == "nwl":
                loans = structure['uses']['loans_to_subsidiaries']
                if _facility_logo.exists():
                    _nl, _nt = st.columns([1, 12])
                    with _nl:
                        st.image(str(_facility_logo), width=80)
                    with _nt:
                        st.markdown("### Smart City Lanseria Catalytic Assets")
                        st.caption("IC Loan to New Water Lanseria (NWL)")
                else:
                    st.markdown("### Smart City Lanseria Catalytic Assets")
                    st.caption("IC Loan to New Water Lanseria (NWL)")

                grant_prepay = senior_detail['grant_proceeds_to_early_repayment']
                gepf_prepay = senior_detail['gepf_bulk_proceeds']
                prepayment_total = grant_prepay + gepf_prepay

                _sr_balance = (
                    senior_detail['loan_drawdown_total']
                    + senior_detail['rolled_up_interest_idc']
                    - grant_prepay
                    - gepf_prepay
                )
                _sr_rate = senior['interest']['rate']
                _sr_num = senior['repayments']
                _sr_p = _sr_balance / _sr_num
                _dsra_n = structure['sources']['dsra']['sizing']['repayments_covered']
                _sr_interest_m24 = _sr_balance * _sr_rate / 2
                dsra_principle_fixed = 2 * (_sr_p + _sr_interest_m24)

                computed_dsra_eur = 0
                _dsra_bal = _sr_balance
                for _ in range(_dsra_n):
                    computed_dsra_eur += _sr_p + (_dsra_bal * _sr_rate / 2)
                    _dsra_bal -= _sr_p

                # Senior IC Facility
                with st.container(border=True):
                    st.markdown("#### Senior Intercompany Loan *(prepaying entity)*")

                    _nwl_sr_tenure = senior['loan_holiday_months'] + senior['repayment_months']
                _nwl_sr_r1 = st.columns(3)
                with _nwl_sr_r1[0]:
                    st.caption("Principal")
                    st.markdown(f"**€{loans['nwl']['senior_portion']:,.0f}**")
                with _nwl_sr_r1[1]:
                    st.caption("Interest")
                    st.markdown(f"**{senior['interest']['rate']*100:.2f}% + 0.5% = {senior_ic_rate*100:.2f}%**")
                with _nwl_sr_r1[2]:
                    st.caption("Tenure")
                    st.markdown(f"**{senior['loan_holiday_months']} + {senior['repayment_months']} = {_nwl_sr_tenure} months**")

                _nwl_sr_r2 = st.columns(3)
                with _nwl_sr_r2[0]:
                    st.caption("Moratorium")
                    st.markdown(f"**{senior['loan_holiday_months']} months**")
                with _nwl_sr_r2[1]:
                    st.caption("Repayments")
                    st.markdown(f"**{senior['repayments']} semi-annual**")
                with _nwl_sr_r2[2]:
                    st.caption("IDC")
                    st.markdown("**Roll-up, add to principal**")

                nwl_sr_rows = []
                nwl_sr_balance = 0.0
                nwl_sr_num_repayments = senior['repayments']
                nwl_pro_rata = loans["nwl"]["senior_portion"] / senior_total
                nwl_prepayment = prepayment_total

                for idx, period in enumerate(senior_drawdown_periods):
                    month = (period + 4) * 6
                    year = month / 12
                    opening = nwl_sr_balance
                    idc = opening * senior_ic_rate / 2
                    draw_down = senior_drawdown_schedule[idx] * nwl_pro_rata if idx < len(senior_drawdown_schedule) else 0
                    if period == -1:
                        principle = -nwl_prepayment
                    else:
                        principle = 0
                    repayment = principle
                    movement = draw_down + idc + principle
                    nwl_sr_balance = opening + movement
                    nwl_sr_rows.append({
                        "Period": period, "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": draw_down, "Interest": idc,
                        "Principle": principle, "Repayment": repayment,
                        "Movement": movement, "Closing": nwl_sr_balance
                    })

                nwl_sr_balance_for_repay = nwl_sr_balance
                nwl_sr_dsra_principle = dsra_principle_fixed
                nwl_sr_balance_after_dsra = nwl_sr_balance_for_repay - nwl_sr_dsra_principle
                nwl_sr_new_p = nwl_sr_balance_after_dsra / (nwl_sr_num_repayments - 2)

                for i in range(1, nwl_sr_num_repayments + 1):
                    period = i
                    month = 18 + (i * 6)
                    year = month / 12
                    opening = nwl_sr_balance
                    interest = opening * senior_ic_rate / 2
                    if period == 1:
                        principle = -nwl_sr_dsra_principle
                        dsra_note = " *"
                    elif period == 2:
                        principle = 0
                        dsra_note = " *"
                    else:
                        principle = -nwl_sr_new_p
                        dsra_note = ""
                    repayment = principle - interest
                    movement = principle
                    nwl_sr_balance = opening + movement
                    nwl_sr_rows.append({
                        "Period": f"{period}{dsra_note}", "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": 0, "Interest": interest,
                        "Principle": principle, "Repayment": repayment,
                        "Movement": movement, "Closing": nwl_sr_balance
                    })

                df_nwl_senior = pd.DataFrame(nwl_sr_rows)
                render_table(df_nwl_senior, ic_format)

                st.markdown("---")
                col_nwl_idc, col_nwl_dsra, col_nwl_repay = st.columns(3)

                nwl_idc_data = []
                nwl_idc_bal = 0.0
                nwl_idc_total = 0.0
                nwl_dd_total = 0.0
                for idx, dd in enumerate(senior_drawdown_schedule):
                    nwl_dd = dd * nwl_pro_rata
                    idc_amt = nwl_idc_bal * senior_ic_rate / 2
                    nwl_idc_total += idc_amt
                    nwl_dd_total += nwl_dd
                    nwl_idc_data.append({"Period": -4 + idx, "Draw Down": nwl_dd, "IDC": idc_amt})
                    nwl_idc_bal += nwl_dd + idc_amt
                nwl_idc_data.append({"Period": "Total", "Draw Down": nwl_dd_total, "IDC": nwl_idc_total})

                with col_nwl_idc:
                    st.markdown("**IDC (NWL Senior IC)**")
                    st.caption(f"Interest capitalized at {senior_ic_rate*100:.2f}%")
                    df_nwl_idc = pd.DataFrame(nwl_idc_data)
                    render_table(df_nwl_idc, {"Draw Down": "€{:,.0f}", "IDC": "€{:,.0f}"})

                with col_nwl_dsra:
                    st.markdown("**DSRA (Fixed from SCLCA)**")
                    st.caption("Same principle, different interest rate")
                    st.markdown(f"""
                | Item | Amount |
                |------|--------|
                | DSRA Principle | €{nwl_sr_dsra_principle:,.0f} |
                | NWL Interest M24 | €{nwl_sr_balance_for_repay * senior_ic_rate / 2:,.0f} |
                | M24 Repayment | €{nwl_sr_dsra_principle + nwl_sr_balance_for_repay * senior_ic_rate / 2:,.0f} |
                | M30 (I only) | €{nwl_sr_balance_after_dsra * senior_ic_rate / 2:,.0f} |
                """)
                    st.caption("DSRA principle identical to SCLCA")

                with col_nwl_repay:
                    st.markdown("**Repayment Structure**")
                    st.caption("After prepayments, 12 periods remain")
                    st.markdown(f"""
                | Item | Amount |
                |------|--------|
                | **P-1 Prepay** | €{nwl_prepayment:,.0f} |
                | Balance for repay | €{nwl_sr_balance_for_repay:,.0f} |
                | **P1 DSRA** | €{nwl_sr_dsra_principle:,.0f} |
                | Balance after DSRA | €{nwl_sr_balance_after_dsra:,.0f} |
                | **New P** (bal÷12) | €{nwl_sr_new_p:,.0f} |
                """)
                    st.caption("Repayment = Principle + Interest")

                st.divider()

                # Mezz IC Facility
                with st.container(border=True):
                    st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual *(receives DSRA drawdown)*")

                nwl_mezz_pro_rata = loans["nwl"]["mezz_portion"] / mezz_total
                nwl_mz_rows = []
                nwl_mz_balance = 0.0

                for idx, period in enumerate(mezz_ic_periods):
                    month = (period + 4) * 6
                    year = month / 12
                    opening = nwl_mz_balance
                    idc = opening * mezz_ic_rate / 2
                    draw_down = mezz_ic_drawdown_schedule[idx] * nwl_mezz_pro_rata if idx < len(mezz_ic_drawdown_schedule) else 0
                    movement = draw_down + idc
                    nwl_mz_balance = opening + movement
                    nwl_mz_rows.append({
                        "Period": period, "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": draw_down, "Interest": idc,
                        "Principle": 0, "Repayment": 0, "Movement": movement, "Closing": nwl_mz_balance
                    })

                nwl_mz_balance_before_dsra = nwl_mz_balance
                nwl_mz_balance_with_dsra = nwl_mz_balance_before_dsra + computed_dsra_eur
                nwl_mz_p_per = nwl_mz_balance_with_dsra / mezz_ic_reps

                for i in range(1, mezz_ic_reps + 1):
                    month = 18 + (i * 6)
                    year = month / 12
                    opening = nwl_mz_balance

                    if i == 1:
                        draw_down = computed_dsra_eur
                        dsra_note = " *"
                    else:
                        draw_down = 0
                        dsra_note = ""

                    interest = opening * mezz_ic_rate / 2
                    principle = -nwl_mz_p_per
                    repayment = principle - interest
                    movement = draw_down + principle
                    nwl_mz_balance = opening + movement

                    nwl_mz_rows.append({
                        "Period": f"{i}{dsra_note}", "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": draw_down, "Interest": interest,
                        "Principle": principle, "Repayment": repayment, "Movement": movement, "Closing": nwl_mz_balance
                    })

                df_nwl_mezz = pd.DataFrame(nwl_mz_rows)
                render_table(df_nwl_mezz, ic_format)

                st.caption(f"""
                **NWL Mezz IC Notes:**
                - **P1 (*):** DSRA drawdown €{computed_dsra_eur:,.0f} (increases NWL's Mezz liability)
                - **Repayments:** P = €{nwl_mz_p_per:,.0f} on total (original + IDC + DSRA)
                - DSRA flows: NWL Mezz ↑ → SCLCA Mezz ↑ → FEC → SCLCA Senior ↓ → NWL Senior ↓
                """)
            elif entity_key == "lanred":
                if _facility_logo.exists():
                    _ll, _lt = st.columns([1, 12])
                    with _ll:
                        st.image(str(_facility_logo), width=80)
                    with _lt:
                        st.markdown("### Smart City Lanseria Catalytic Assets")
                        st.caption("IC Loan to LanRED")
                else:
                    st.markdown("### Smart City Lanseria Catalytic Assets")
                    st.caption("IC Loan to LanRED")
                st.caption(f"Senior: €{loans['lanred']['senior_portion']:,.0f} | Mezz: €{loans['lanred']['mezz_portion']:,.0f} | Total: €{loans['lanred']['total_loan']:,.0f}")

                # Senior IC Facility
                with st.container(border=True):
                    st.markdown(f"**Senior IC** — {senior_ic_rate*100:.2f}% | {senior['repayments']} semi-annual")
                    df_lanred_senior = pd.DataFrame(build_simple_ic_schedule(
                        loans["lanred"]["senior_portion"], senior_total, senior['repayments'],
                        senior_ic_rate, senior_drawdown_schedule, senior_drawdown_periods
                    ))
                    render_table(df_lanred_senior, ic_format)

                # Mezz IC Facility
                with st.container(border=True):
                    st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual")
                    df_lanred_mezz = pd.DataFrame(build_simple_ic_schedule(
                        loans["lanred"]["mezz_portion"], mezz_total, mezz_ic_reps,
                        mezz_ic_rate, mezz_ic_drawdown_schedule, mezz_ic_periods
                    ))
                    render_table(df_lanred_mezz, ic_format)

                st.divider()
                st.markdown("#### Equity Stake")
                _eq_lr_c1, _eq_lr_c2 = st.columns(2)
                with _eq_lr_c1:
                    st.metric("SCLCA Ownership", "100%", "€50,000")
                with _eq_lr_c2:
                    st.metric("Share Capital", "R1m", "Wholly owned subsidiary")
            elif entity_key == "timberworx":
                if _facility_logo.exists():
                    _tl, _tt = st.columns([1, 12])
                    with _tl:
                        st.image(str(_facility_logo), width=80)
                    with _tt:
                        st.markdown("### Smart City Lanseria Catalytic Assets")
                        st.caption("IC Loan to Timberworx")
                else:
                    st.markdown("### Smart City Lanseria Catalytic Assets")
                    st.caption("IC Loan to Timberworx")
                st.caption(f"Senior: €{loans['timberworx']['senior_portion']:,.0f} | Mezz: €{loans['timberworx']['mezz_portion']:,.0f} | Total: €{loans['timberworx']['total_loan']:,.0f}")

                # Senior IC Facility
                with st.container(border=True):
                    st.markdown(f"**Senior IC** — {senior_ic_rate*100:.2f}% | {senior['repayments']} semi-annual")
                    df_twx_senior = pd.DataFrame(build_simple_ic_schedule(
                        loans["timberworx"]["senior_portion"], senior_total, senior['repayments'],
                        senior_ic_rate, senior_drawdown_schedule, senior_drawdown_periods
                    ))
                    render_table(df_twx_senior, ic_format)

                # Mezz IC Facility
                with st.container(border=True):
                    st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual")
                    df_twx_mezz = pd.DataFrame(build_simple_ic_schedule(
                        loans["timberworx"]["mezz_portion"], mezz_total, mezz_ic_reps,
                        mezz_ic_rate, mezz_ic_drawdown_schedule, mezz_ic_periods
                    ))
                    render_table(df_twx_mezz, ic_format)

                st.divider()
                st.markdown("#### Equity Stake")
                _eq_twx_c1, _eq_twx_c2, _eq_twx_c3 = st.columns(3)
                with _eq_twx_c1:
                    st.metric("SCLCA Ownership", "5%", "€2,500")
                with _eq_twx_c2:
                    st.metric("Share Capital", "R1m", "€50,000 at FX 20")
                with _eq_twx_c3:
                    _vs_logo_a = LOGO_DIR / ENTITY_LOGOS.get("vansquare", "")
                    if _vs_logo_a.exists():
                        st.image(str(_vs_logo_a), width=80)
                    st.markdown("**VanSquare — 95%**")

            # ── AUDIT: Facilities ──
            _fac_checks = []
            # IC balance Y10 = 0 (fully amortized)
            _sr_last = _sub_sr_schedule[-1] if _sub_sr_schedule else {}
            _mz_last = _sub_mz_schedule[-1] if _sub_mz_schedule else {}
            _fac_checks.append({
                "name": "Senior IC Y10 closing = 0",
                "expected": 0.0,
                "actual": abs(_sr_last.get('Closing', 0)),
            })
            _fac_checks.append({
                "name": "Mezz IC Y10 closing = 0",
                "expected": 0.0,
                "actual": abs(_mz_last.get('Closing', 0)),
            })
            # Sum(interest) = total IE from P&L
            _sr_int_total = sum(r['Interest'] for r in _sub_sr_schedule)
            _mz_int_total = sum(r['Interest'] for r in _sub_mz_schedule)
            _pl_ie_sr = sum(a['ie_sr'] for a in _sub_annual)
            _pl_ie_mz = sum(a['ie_mz'] for a in _sub_annual)
            _fac_checks.append({
                "name": "Sum(SR interest) = P&L IE(SR)",
                "expected": _sr_int_total,
                "actual": _pl_ie_sr,
            })
            _fac_checks.append({
                "name": "Sum(MZ interest) = P&L IE(MZ)",
                "expected": _mz_int_total,
                "actual": _pl_ie_mz,
            })
            # Sum(principal) = peak balance (all principal repaid over life)
            _sr_princ_total = sum(abs(r['Principle']) for r in _sub_sr_schedule if r['Principle'] < 0)
            _sr_peak_bal = max((r['Closing'] for r in _sub_sr_schedule), default=0)
            _fac_checks.append({
                "name": "Sum(SR principal paid) = peak balance",
                "expected": _sr_peak_bal,
                "actual": _sr_princ_total,
                "tolerance": 2.0,
            })
            run_page_audit(_fac_checks, f"{name} — Facilities")

    # --- ASSETS ---
    if "Assets" in _tab_map:
        with _tab_map["Assets"]:
            st.header("Assets")

            # ── LanRED Scenario Selector + Assets ──
            if entity_key == "lanred":
                _a_assets_cfg = load_config("assets")["assets"]
                _a_solar_items = _a_assets_cfg.get("solar", {}).get("line_items", [])
                _a_total = _a_assets_cfg.get("solar", {}).get("total", 2908809)
                _a_bess_from = sum(li['budget'] for li in _a_solar_items if 'bess' in li.get('delivery', '').lower() or 'battery' in li.get('delivery', '').lower() or 'li-ion' in li.get('delivery', '').lower())
                _a_default_pct = round(_a_bess_from / _a_total * 100) if _a_total > 0 else 14
                _a_lr_cfg = operations_config.get("lanred", {})
                _a_kwp = float(_a_lr_cfg.get("solar_capacity", {}).get("cost_per_kwp_eur", 728))
                _a_kwh = float(_a_lr_cfg.get("battery_storage", {}).get("cost_per_kwh_eur", 364))

                # ── Scenario selector ──
                def _on_lanred_scenario_change():
                    scenario = st.session_state.get("lanred_scenario", "Greenfield")
                    if scenario == "Brownfield+":
                        st.session_state["lanred_eca_atradius"] = False
                        st.session_state["lanred_eca_exporter"] = False
                    else:
                        st.session_state["lanred_eca_atradius"] = True
                        st.session_state["lanred_eca_exporter"] = True

                with st.container(border=True):
                    st.subheader("LanRED Energy Scenario")
                    _scenario = st.radio(
                        "Select scenario",
                        ["Greenfield", "Brownfield+"],
                        key="lanred_scenario",
                        horizontal=True,
                        on_change=_on_lanred_scenario_change,
                        help="Greenfield: Build 3.45 MWp at Lanseria. Brownfield+: Acquire Northlands Energy portfolio (R60M, 5 sites)."
                    )

                if _scenario == "Greenfield":
                    with st.container(border=True):
                        st.subheader("PV / BESS Budget Allocation")
                        st.caption(f"Total solar envelope: **€{_a_total:,.0f}**. Drag to reallocate between PV generation and battery storage.")
                        _asl1, _asl2, _asl3 = st.columns([4, 1, 1])
                        with _asl1:
                            _a_bess_pct = st.slider(
                                "BESS allocation %",
                                min_value=0, max_value=50, value=_a_default_pct, step=1,
                                key="lanred_bess_alloc_pct",
                                help="Reallocate budget between PV and BESS. Model recalculates all revenue streams on change."
                            )
                        _a_bess_budget = _a_total * _a_bess_pct / 100.0
                        _a_pv_budget = _a_total - _a_bess_budget
                        with _asl2:
                            st.metric("PV", f"€{_a_pv_budget:,.0f}",
                                      delta=f"{_a_pv_budget/_a_kwp/1000:.1f} MWp")
                        with _asl3:
                            st.metric("BESS", f"€{_a_bess_budget:,.0f}",
                                      delta=f"{_a_bess_budget/_a_kwh/1000:.1f} MWh")

                    # ── IRR per asset (live from model) ──
                    _a_ops = _build_lanred_operating_annual_model()
                    # PV revenue = PPA streams (IC + Smart City + Open Market)
                    _a_pv_revs = [a.get('rev_ic_nwl', 0) + a.get('rev_smart_city', 0) + a.get('rev_open_market', 0) for a in _a_ops]
                    # BESS revenue = arbitrage stream
                    _a_bess_revs = [a.get('rev_bess_arbitrage', 0) for a in _a_ops]
                    # O&M split pro-rata by budget
                    _a_om_total = [a.get('om_cost', 0) for a in _a_ops]
                    _a_pv_share = _a_pv_budget / _a_total if _a_total > 0 else 1.0
                    _a_pv_om = [om * _a_pv_share for om in _a_om_total]
                    _a_bess_om = [om * (1 - _a_pv_share) for om in _a_om_total]

                    # Simple IRR via bisection
                    def _compute_irr(cashflows, lo=-0.5, hi=2.0, tol=1e-6, maxiter=200):
                        def _npv(r):
                            return sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
                        if _npv(lo) * _npv(hi) > 0:
                            return None
                        for _ in range(maxiter):
                            mid = (lo + hi) / 2.0
                            if abs(_npv(mid)) < tol:
                                return mid
                            if _npv(lo) * _npv(mid) < 0:
                                hi = mid
                            else:
                                lo = mid
                        return (lo + hi) / 2.0

                    # PV: capex Y0 (negative), then net revenue Y1-10
                    _a_pv_cf = [-_a_pv_budget] + [r - om for r, om in zip(_a_pv_revs, _a_pv_om)]
                    _a_bess_cf = [-_a_bess_budget] + [r - om for r, om in zip(_a_bess_revs, _a_bess_om)] if _a_bess_budget > 0 else []
                    _a_combined_cf = [-_a_total] + [pr + br - om for pr, br, om in zip(_a_pv_revs, _a_bess_revs, _a_om_total)]

                    _a_pv_irr = _compute_irr(_a_pv_cf)
                    _a_bess_irr = _compute_irr(_a_bess_cf) if _a_bess_cf else None
                    _a_combined_irr = _compute_irr(_a_combined_cf)

                    # 10-year totals
                    _a_pv_10y = sum(_a_pv_revs)
                    _a_bess_10y = sum(_a_bess_revs)

                    st.markdown("#### IRR by Asset")
                    _ic1, _ic2, _ic3 = st.columns(3)
                    _ic1.metric("Solar PV IRR", f"{_a_pv_irr * 100:.1f}%" if _a_pv_irr is not None else "N/A",
                                delta=f"10yr: €{_a_pv_10y:,.0f}")
                    _ic2.metric("BESS IRR", f"{_a_bess_irr * 100:.1f}%" if _a_bess_irr is not None else "N/A",
                                delta=f"10yr: €{_a_bess_10y:,.0f}")
                    _ic3.metric("Combined IRR", f"{_a_combined_irr * 100:.1f}%" if _a_combined_irr is not None else "N/A",
                                delta=f"€{_a_total:,.0f} invested")

                    st.divider()

                else:
                    # ── Brownfield+ display ──
                    _bf_cfg = operations_config.get("lanred", {}).get("brownfield_plus", {})
                    _sites = _bf_cfg.get("northlands_portfolio", {}).get("sites", [])

                    with st.container(border=True):
                        st.subheader("Northlands Energy Portfolio")
                        st.caption("5 operating solar+BESS sites — 20yr PPAs, prepaid smart metering, Tier 1 components.")
                        _site_df = pd.DataFrame(_sites)
                        _display_cols = {
                            'name': 'Site', 'location': 'Location', 'pv_kwp': 'PV (kWp)',
                            'bess_kwh': 'BESS (kWh)', 'monthly_net_zar': 'Net/mo (ZAR)',
                            'coj_registered': 'COJ'
                        }
                        st.dataframe(
                            _site_df[list(_display_cols.keys())].rename(columns=_display_cols),
                            hide_index=True, use_container_width=True
                        )
                        _tot_pv = sum(s['pv_kwp'] for s in _sites)
                        _tot_bess = sum(s['bess_kwh'] for s in _sites)
                        _tot_rev = sum(s['monthly_income_zar'] for s in _sites)
                        _tot_net = sum(s['monthly_net_zar'] for s in _sites)
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Total PV", f"{_tot_pv:,} kWp", f"{_tot_pv/1000:.2f} MWp")
                        c2.metric("Total BESS", f"{_tot_bess:,} kWh", f"{_tot_bess/1000:.1f} MWh")
                        c3.metric("Monthly Net", f"R{_tot_net:,.0f}", f"€{_tot_net/FX_RATE:,.0f}")
                        c4.metric("Acquisition Price", "R60,000,000", f"€{60000000/FX_RATE:,.0f}")

                    with st.expander("Site Details", expanded=False):
                        for s in _sites:
                            st.markdown(f"**{s['name']}** — {s['location']}")
                            st.markdown(f"- PV: {s['pv_kwp']} kWp | BESS: {s['bess_kwh']} kWh | Tech: {s.get('tech', 'Tier 1')}")
                            _margin_pct = s['monthly_net_zar'] / s['monthly_income_zar'] * 100 if s['monthly_income_zar'] else 0
                            st.markdown(f"- Income: R{s['monthly_income_zar']:,}/mo → COGS: R{s['monthly_cogs_zar']:,} → Net: **R{s['monthly_net_zar']:,}/mo** ({_margin_pct:.0f}% margin)")
                            st.markdown(f"- PPA: {s.get('ppa_term_years', 20)} years + auto renewal | COJ SSEG: {'Registered' if s.get('coj_registered') else '**Pending**'}")
                            st.divider()

                    st.info("**NWL Backup Power** — 118 kWp PV + 280 kWh BESS (8h backup, 8h solar, peak arbitrage) via off-book PPA. Not in SCLCA structure.")
                    st.caption("**Phase 2**: Lanseria solar expansion (~1.4 MWp for Smart City off-take) funded from Northlands retained earnings Y2-Y3.")

                    with st.container(border=True):
                        st.markdown("#### Financing Structure")
                        st.markdown("""
**Brownfield+ enables a natural currency hedge:**
- Northlands generates **contracted ZAR cashflows** (R14M/yr, 20yr PPAs)
- Investec currency swap: ZAR PPA revenues ↔ EUR IC loan service
- The swap itself serves as **underwriting** — no Atradius ECA cover needed for energy component
- Greenfield requires ECA underwriting (construction risk, uncontracted revenue)
- Brownfield+ ZAR cashflows are **more bankable** than modelled SC off-take projections
""")

                    with st.container(border=True):
                        st.markdown("#### Greenfield vs Brownfield+")
                        _gf = structure['uses']['loans_to_subsidiaries']['lanred']
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("**Greenfield**")
                            st.metric("Loan", f"€{_gf['total_loan']:,.0f}")
                            st.metric("PV", "3.45 MWp", "Single site, Lanseria")
                            st.metric("Revenue start", "M18", "Construction delay")
                            st.metric("Smart City", "Direct", "94% absorption at steady state")
                            st.metric("Underwriting", "Atradius ECA", "Construction + revenue risk")
                        with c2:
                            st.markdown("**Brownfield+**")
                            st.metric("Loan", f"€{_gf['total_loan']:,.0f}", "Same envelope")
                            st.metric("PV", f"{_tot_pv/1000:.2f} MWp", f"5 sites, {_tot_bess/1000:.1f} MWh BESS")
                            st.metric("Revenue start", "Day 1", "Operating assets")
                            st.metric("Smart City", "Phase 2", "From retained earnings Y2-Y3")
                            st.metric("Underwriting", "Investec swap", "ZAR PPAs = natural hedge")

                    st.divider()

                    # Set defaults so downstream asset registry code doesn't break
                    _a_pv_budget = _a_total
                    _a_bess_budget = 0.0

            assets_cfg = load_config("assets")["assets"]
            fees_cfg = load_config("fees")
            project_asset_base = sum(
                _build_entity_asset_base(k, assets_cfg)["fee_base"]
                for k in ["nwl", "lanred", "timberworx"]
            )
            project_debt_base = structure['sources']['senior_debt']['amount']
            project_fees = compute_project_fees(fees_cfg, project_debt_base, project_asset_base)
            registry = build_asset_registry(
                entity_key, assets_cfg, fees_cfg, project_fees["fees"], project_asset_base, project_debt_base
            )
            assets = registry["assets"]
            services = registry["services"]

            # Live-wire: override LanRED solar/BESS base costs from slider (Greenfield only)
            if entity_key == "lanred" and _state_str("lanred_scenario", "Greenfield") == "Greenfield":
                for a in assets:
                    dl = a["asset"].lower()
                    if 'solar' in dl or 'pv' in dl:
                        a["base_cost"] = _a_pv_budget
                        a["depr_base"] = _a_pv_budget + a["alloc_fees"]
                        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0
                    elif 'bess' in dl or 'battery' in dl or 'li-ion' in dl:
                        a["base_cost"] = _a_bess_budget
                        a["depr_base"] = _a_bess_budget + a["alloc_fees"]
                        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0

            # ── OPERATING ASSETS ──────────────────────────────────────
            with st.container(border=True):
                st.subheader("Operating Assets")
                st.caption("Core assets only. Services and fees are capitalized pro‑rata to assets for depreciation.")

                if assets:
                    # Compute unit cost string per asset
                    def _get_unit_cost(a):
                        dl = a["asset"].lower()
                        if entity_key == 'lanred':
                            _lr_cfg = operations_config.get("lanred", {})
                            if 'solar' in dl or 'pv' in dl:
                                _kwp = float(_lr_cfg.get("solar_capacity", {}).get("cost_per_kwp_eur", 728))
                                _cap = a["base_cost"] / _kwp / 1000 if _kwp else 0
                                _kwp_zar = _kwp * FX_RATE
                                return f"\u20ac{_kwp:,.0f}/kWp (R{_kwp_zar:,.0f})", f"{_cap:.1f} MWp", "SA: R12k-18k/kWp"
                            if 'bess' in dl or 'battery' in dl or 'li-ion' in dl:
                                _kwh = float(_lr_cfg.get("battery_storage", {}).get("cost_per_kwh_eur", 364))
                                _cap = a["base_cost"] / _kwh / 1000 if _kwh else 0
                                _kwh_zar = _kwh * FX_RATE
                                return f"\u20ac{_kwh:,.0f}/kWh (R{_kwh_zar:,.0f})", f"{_cap:.1f} MWh", "SA: R6k-10k/kWh"
                        if entity_key == 'nwl':
                            if 'mabr' in dl:
                                return f"\u20ac{a['base_cost']/2.0:,.0f}/MLD", "2.0 MLD", "\u20ac1-3M/MLD"
                            if 'balance of plant' in dl:
                                return f"\u20ac{a['base_cost']/2.0:,.0f}/MLD", "2.0 MLD", "\u20ac0.5-1.5M/MLD"
                            if 'civil' in dl:
                                return f"\u20ac{a['base_cost']/2.0:,.0f}/MLD", "2.0 MLD", "\u20ac1-2.5M/MLD"
                        if entity_key == 'timberworx':
                            if 'centre' in dl or 'center' in dl:
                                _sqm = float(operations_config.get("timberworx", {}).get("coe_facility", {}).get("building_area_sqm", 2500))
                                return f"\u20ac{a['base_cost']/_sqm:,.0f}/sqm", f"{_sqm:,.0f} sqm", "\u20ac500-800/sqm"
                            if 'panel' in dl:
                                return "\u20ac200k", "3 houses/wk", "Optimat (Finland)"
                        return "", "", ""

                    _asset_rows = []
                    for a in assets:
                        _uc, _cap, _bm = _get_unit_cost(a)
                        _asset_rows.append({
                            "Asset": a["asset"],
                            "Base Cost": a["base_cost"],
                            "Unit Cost": _uc,
                            "Capacity": _cap,
                            "Benchmark": _bm,
                            "Alloc. Fees": a["alloc_fees"],
                            "Depreciable Base": a["depr_base"],
                            "Life (Years)": a["life"],
                            "Annual Depreciation": a["annual_depr"],
                        })
                    df_assets = pd.DataFrame(_asset_rows)
                    df_assets = pd.concat([
                        df_assets,
                        pd.DataFrame([{
                            "Asset": "**Total**",
                            "Base Cost": df_assets["Base Cost"].sum(),
                            "Unit Cost": "",
                            "Capacity": "",
                            "Benchmark": "",
                            "Alloc. Fees": df_assets["Alloc. Fees"].sum(),
                            "Depreciable Base": df_assets["Depreciable Base"].sum(),
                            "Life (Years)": "",
                            "Annual Depreciation": df_assets["Annual Depreciation"].sum(),
                        }])
                    ], ignore_index=True)
                    render_table(df_assets, {
                        "Base Cost": "\u20ac{:,.0f}",
                        "Alloc. Fees": "\u20ac{:,.0f}",
                        "Depreciable Base": "\u20ac{:,.0f}",
                        "Annual Depreciation": "\u20ac{:,.0f}",
                    })
                else:
                    st.info("No registered assets for this subsidiary.")

                st.divider()

                st.subheader("Services (Management & Compliance)")
                if services:
                    df_services = pd.DataFrame(services)
                    if "id" in df_services.columns:
                        df_services = df_services.drop(columns=["id"])
                    df_services = pd.concat([
                        df_services,
                        pd.DataFrame([{
                            "service": "**Total**",
                            "cost": sum(s["cost"] for s in services)
                        }])
                    ], ignore_index=True)
                    render_table(df_services, {"cost": "€{:,.0f}"})
                else:
                    st.caption("None")

                st.divider()

                st.subheader("Fees")

                # ── ECA Coverage Toggles ──
                _eca_c1, _eca_c2 = st.columns(2)
                with _eca_c1:
                    st.checkbox(
                        "Include Atradius Premium (ECA cover)",
                        key=f"{entity_key}_eca_atradius",
                        value=_eca_default(entity_key),
                        help="4.4% of senior debt — ECA insurance premium. Not needed for Brownfield+ (Investec swap)."
                    )
                with _eca_c2:
                    st.checkbox(
                        "Include Exporter Premium (manufacturing risk)",
                        key=f"{entity_key}_eca_exporter",
                        value=_eca_default(entity_key),
                        help="0.4% of capex — export credit cover for manufacturing/delivery risk."
                    )

                _atradius_on = _state_bool(f"{entity_key}_eca_atradius", _eca_default(entity_key))
                _exporter_on = _state_bool(f"{entity_key}_eca_exporter", _eca_default(entity_key))
                if not _atradius_on or not _exporter_on:
                    _ab = entity_data['assets_base']
                    _sav_a = _ab * 0.85 * 0.044 if not _atradius_on else 0
                    _sav_e = _ab * 0.004 if not _exporter_on else 0
                    st.success(f"ECA fee savings: **\u20ac{_sav_a + _sav_e:,.0f}** "
                               f"(Atradius: \u20ac{_sav_a:,.0f}, Exporter: \u20ac{_sav_e:,.0f})")

                fee_rows = []
                for fee in registry["fee_rows"]:
                    _fid = fee.get("id", "")
                    if _fid == "fee_003" and not _state_bool(f"{entity_key}_eca_atradius", _eca_default(entity_key)):
                        continue
                    if _fid == "fee_004" and not _state_bool(f"{entity_key}_eca_exporter", _eca_default(entity_key)):
                        continue
                    basis_key = fee.get("rate_basis", "")
                    basis_label = f"85% of entity capex (€{fee.get('base_amount', 0):,.0f})" if basis_key == "debt" else f"Entity capex (€{fee.get('base_amount', 0):,.0f})"
                    funding_key = fee.get("funding", "")
                    funding_label_map = {
                        "senior_only": "Debt (Senior only)",
                        "mezz_senior": "Finance (Mezz / Senior)",
                        "equity": "Equity",
                    }
                    funding_label = funding_label_map.get(funding_key, funding_key)
                    fee_rows.append({
                        "Company": fee.get("company", ""),
                        "Description": fee.get("description", ""),
                        "Rate": f"{fee.get('rate', 0)*100:.2f}%",
                        "Basis": basis_label,
                        "Fee": fee.get("amount", 0),
                        "Funding": funding_label,
                    })
                if fee_rows:
                    df_fees = pd.DataFrame(fee_rows)
                    df_fees = pd.concat([
                        df_fees,
                        pd.DataFrame([{
                            "Company": "**Total**",
                            "Description": "",
                            "Rate": "",
                            "Basis": "",
                            "Fee": df_fees["Fee"].sum(),
                            "Funding": "",
                        }])
                    ], ignore_index=True)
                    render_table(df_fees, {
                        "Fee": "€{:,.0f}",
                    })

                # --- Fee → IC Loan Reconciliation ---
                with st.expander("Fee → IC Loan Reconciliation", expanded=False):
                    _recon_entities = ['nwl', 'lanred', 'timberworx']
                    _recon_labels = {'nwl': 'NWL', 'lanred': 'LanRED', 'timberworx': 'TWX'}
                    _recon_rows = []
                    _recon_totals = {'assets_base': 0, 'sr_only': 0, 'mz_sr': 0, 'total_fees': 0, 'senior_ic': 0, 'mezz_ic': 0, 'total_ic': 0}
                    for _rek in _recon_entities:
                        _re_data = structure['uses']['loans_to_subsidiaries'][_rek]
                        _re_ab = _re_data['assets_base']
                        _re_ef = compute_entity_fees(fees_cfg, _re_ab)
                        _re_sr_only = sum(f['amount'] for f in _re_ef['fees'] if f.get('funding') == 'senior_only')
                        _re_mz_sr = sum(f['amount'] for f in _re_ef['fees'] if f.get('funding') != 'senior_only')
                        _re_total_fees = _re_ef['total']
                        _re_total_ic = _re_ab + _re_total_fees
                        _re_senior_ic = round(_re_ab * 0.85) + _re_sr_only + round(_re_mz_sr * 0.85)
                        _re_mezz_ic = _re_total_ic - _re_senior_ic
                        _recon_totals['assets_base'] += _re_ab
                        _recon_totals['sr_only'] += _re_sr_only
                        _recon_totals['mz_sr'] += _re_mz_sr
                        _recon_totals['total_fees'] += _re_total_fees
                        _recon_totals['senior_ic'] += _re_senior_ic
                        _recon_totals['mezz_ic'] += _re_mezz_ic
                        _recon_totals['total_ic'] += _re_total_ic
                        _recon_rows.append({
                            'Component': _recon_labels[_rek],
                            'Assets Base': _re_ab,
                            'Sr-Only Fees': _re_sr_only,
                            'Mz/Sr Fees': _re_mz_sr,
                            'Total Fees': _re_total_fees,
                            'Senior IC': _re_senior_ic,
                            'Mezz IC': _re_mezz_ic,
                            'Total IC': _re_total_ic,
                        })
                    # Totals row
                    _recon_rows.append({
                        'Component': '**Total**',
                        'Assets Base': _recon_totals['assets_base'],
                        'Sr-Only Fees': _recon_totals['sr_only'],
                        'Mz/Sr Fees': _recon_totals['mz_sr'],
                        'Total Fees': _recon_totals['total_fees'],
                        'Senior IC': _recon_totals['senior_ic'],
                        'Mezz IC': _recon_totals['mezz_ic'],
                        'Total IC': _recon_totals['total_ic'],
                    })
                    # Structure.json reference row
                    _str_sr = structure['sources']['senior_debt']['amount']
                    _str_mz = structure['sources']['mezzanine']['amount_eur']
                    _str_total = structure['sources']['total']
                    _recon_rows.append({
                        'Component': 'structure.json',
                        'Assets Base': '',
                        'Sr-Only Fees': '',
                        'Mz/Sr Fees': '',
                        'Total Fees': '',
                        'Senior IC': _str_sr,
                        'Mezz IC': _str_mz,
                        'Total IC': _str_total,
                    })
                    # Delta row
                    _recon_rows.append({
                        'Component': '**Delta**',
                        'Assets Base': '',
                        'Sr-Only Fees': '',
                        'Mz/Sr Fees': '',
                        'Total Fees': '',
                        'Senior IC': _recon_totals['senior_ic'] - _str_sr,
                        'Mezz IC': _recon_totals['mezz_ic'] - _str_mz,
                        'Total IC': _recon_totals['total_ic'] - _str_total,
                    })
                    _df_recon = pd.DataFrame(_recon_rows)
                    _fmt_recon = {c: "€{:,.0f}" for c in _df_recon.columns if c != 'Component'}
                    render_table(_df_recon, _fmt_recon)

                st.divider()

                st.subheader("10‑Year Depreciation Overview")
                if assets:
                    # For TWX: CoE sold in sale year → stop CoE depreciation from that year
                    _depr_coe_sale_yr = None
                    if entity_key == 'timberworx':
                        _depr_coe_sale_cfg = operations_config.get("timberworx", {}).get("coe_sale_to_llc", {})
                        if _depr_coe_sale_cfg.get("enabled", False):
                            _depr_coe_sale_yr = int(_depr_coe_sale_cfg.get("sale_year", 4))

                    dep_rows = []
                    for year in range(1, 11):
                        total_dep = 0.0
                        for a in assets:
                            if year <= a["life"]:
                                if _depr_coe_sale_yr and year >= _depr_coe_sale_yr and a.get("id", "") == "coe_001":
                                    continue
                                total_dep += a["annual_depr"]
                        dep_rows.append({"Year": year, "Depreciation": total_dep})
                    df_dep = pd.DataFrame(dep_rows)
                    render_table(df_dep, {"Depreciation": "€{:,.0f}"})
                    _depr_note = "Straight‑line depreciation. No replacements modeled in the 10‑year scope."
                    if _depr_coe_sale_yr:
                        _depr_note += f" CoE building depreciation stops at Y{_depr_coe_sale_yr} (sold to LLC)."
                    st.caption(_depr_note)

                st.divider()

                # --- CHECKUP: Debt/Mezz reconciliation (toggleable) ---
                with st.expander("Checkup — 85% Debt / 15% Mezz Allocation", expanded=False):
                    # Entity-level fee computation
                    _ck_ab = entity_data['assets_base']
                    _ck_ef = compute_entity_fees(fees_cfg, _ck_ab)
                    _ck_sr_only = sum(f['amount'] for f in _ck_ef['fees'] if f.get('funding') == 'senior_only')
                    _ck_mz_sr = sum(f['amount'] for f in _ck_ef['fees'] if f.get('funding') != 'senior_only')

                    # Asset base split (85/15)
                    _ck_base_sr = round(_ck_ab * 0.85)
                    _ck_base_mz = _ck_ab - _ck_base_sr

                    # Fee split by funding rules
                    _ck_fees_sr = _ck_sr_only + round(_ck_mz_sr * 0.85)
                    _ck_fees_mz = _ck_mz_sr - round(_ck_mz_sr * 0.85)
                    _ck_fees_total = _ck_fees_sr + _ck_fees_mz

                    # Totals
                    _ck_total_sr = _ck_base_sr + _ck_fees_sr
                    _ck_total_mz = _ck_base_mz + _ck_fees_mz

                    check_rows = [
                        {"Item": f"Assets base (€{_ck_ab:,.0f})", "Senior": _ck_base_sr, "Mezz": _ck_base_mz},
                        {"Item": f"Senior-only fees", "Senior": _ck_sr_only, "Mezz": 0},
                        {"Item": f"Mezz/Senior fees (85/15)", "Senior": round(_ck_mz_sr * 0.85), "Mezz": _ck_fees_mz},
                        {"Item": "**Total (computed)**", "Senior": _ck_total_sr, "Mezz": _ck_total_mz},
                        {"Item": "structure.json", "Senior": senior_liab, "Mezz": mezz_liab},
                        {"Item": "**Delta**", "Senior": _ck_total_sr - senior_liab, "Mezz": _ck_total_mz - mezz_liab},
                    ]
                    df_check = pd.DataFrame(check_rows)
                    render_table(df_check, {"Senior": "€{:,.0f}", "Mezz": "€{:,.0f}"})

                    # Verification metrics
                    _ck_base_sr_pct = _ck_base_sr / _ck_ab * 100 if _ck_ab else 0
                    _ck_fees_sr_pct = _ck_fees_sr / _ck_fees_total * 100 if _ck_fees_total else 0
                    _ck_total_sr_pct = _ck_total_sr / (_ck_total_sr + _ck_total_mz) * 100
                    _ck_src_sr_pct = senior_liab / (senior_liab + mezz_liab) * 100

                    st.markdown(f"""
| Component | Senior % | Mezz % | Rule |
|---|---|---|---|
| Assets base | {_ck_base_sr_pct:.1f}% | {100-_ck_base_sr_pct:.1f}% | 85/15 |
| Fees (entity-level) | {_ck_fees_sr_pct:.1f}% | {100-_ck_fees_sr_pct:.1f}% | Funding rules |
| **Total (computed)** | **{_ck_total_sr_pct:.1f}%** | **{100-_ck_total_sr_pct:.1f}%** | |
| structure.json | {_ck_src_sr_pct:.1f}% | {100-_ck_src_sr_pct:.1f}% | Authoritative |
""")
                    st.caption(f"Entity fees: €{_ck_fees_total:,.0f} (structure.json: €{breakdown.get('fees', 0):,.0f})")

            # ── FINANCIAL ASSET ──────────────────────────────────────
            st.subheader("Financial Asset — DSRA Fixed Deposit")

            # Compute DSRA sizing (same logic as build_sub_annual_model)
            _fa_sr_detail = financing['loan_detail']['senior']
            _fa_sr_bal = (_fa_sr_detail['loan_drawdown_total']
                         + _fa_sr_detail['rolled_up_interest_idc']
                         - _fa_sr_detail['grant_proceeds_to_early_repayment']
                         - _fa_sr_detail['gepf_bulk_proceeds'])
            _fa_sr_rate = structure['sources']['senior_debt']['interest']['rate']
            _fa_sr_num = structure['sources']['senior_debt']['repayments']
            _fa_sr_p = _fa_sr_bal / _fa_sr_num
            _fa_sr_i_m24 = _fa_sr_bal * _fa_sr_rate / 2
            _fa_dsra_total = 2 * (_fa_sr_p + _fa_sr_i_m24)

            # DSRA allocation (100% NWL)
            _fa_dsra_alloc = {'nwl': 1.0}
            _fa_entity_dsra = _fa_dsra_total * _fa_dsra_alloc.get(entity_key, 0.0)

            with st.container(border=True):
                if _fa_entity_dsra > 0:
                    _fa_c1, _fa_c2, _fa_c3 = st.columns(3)
                    with _fa_c1:
                        st.metric("DSRA Amount", f"€{_fa_entity_dsra:,.0f}")
                    with _fa_c2:
                        st.metric("Interest Rate", f"{DSRA_RATE*100:.0f}% p.a.")
                    with _fa_c3:
                        st.metric("Funded by", "Creation Capital (Mezz)")

                    _fa_rows = [
                        {"Item": "Facility Senior Balance (M24)", "Amount": f"€{_fa_sr_bal:,.0f}"},
                        {"Item": "DSRA Amount", "Amount": f"€{_fa_dsra_total:,.0f}"},
                        {"Item": f"{name} allocation (100%)", "Amount": f"€{_fa_entity_dsra:,.0f}"},
                    ]
                    render_table(pd.DataFrame(_fa_rows))

                    st.caption(
                        "**Flow:** Creation Capital → DSRA → FEC → Senior Debt. "
                        "Funded by an additional Mezz IC drawdown of the same amount. "
                        "Net effect: Senior ↓, Mezz ↑, total debt unchanged. "
                        "Surplus cash deposited into the DSRA Fixed Deposit at 9% p.a."
                    )
                else:
                    st.info(f"No DSRA allocation for {name}. DSRA is allocated 100% to NWL.")

            # ── DSRA FIXED DEPOSIT SCHEDULE ──────────────────────────
            with st.container(border=True):
                st.subheader("DSRA (Fixed Deposit)")
                st.markdown("**Opening** + **Deposit** (Net Cash Flow) + **Interest** (4.4%/6mo) = **Closing**")
                st.caption("Semi-annual compounding @ 9% p.a. = 4.4% per 6 months")

                # Build semi-annual DSRA schedule
                # Semi-annual interest rate: (1.09)^0.5 - 1 ≈ 0.04403
                dsra_rate_semiannual = (1 + DSRA_RATE) ** 0.5 - 1

                _dsra_fd_rows = []
                _fd_bal = 0.0

                # Loop through semi-annual periods (20 periods = 10 years × 2)
                for period_idx in range(20):
                    year = (period_idx // 2) + 1
                    half = 'H1' if period_idx % 2 == 0 else 'H2'
                    period_label = f"{half} Y{year}"

                    # Calculate semi-annual cash flow from schedules
                    # Period months: H1 Y1 = M0-M5, H2 Y1 = M6-M11, etc.
                    m_start = period_idx * 6
                    m_end = m_start + 6

                    # Get semi-annual cash flows from schedules
                    # CF components: Interest income (IE) - Interest expense + Principal margin
                    sr_ie = sum(r['Interest'] for r in _sub_sr_schedule if m_start <= r['Month'] < m_end and r['Month'] >= 24)
                    mz_ie = sum(r['Interest'] for r in _sub_mz_schedule if m_start <= r['Month'] < m_end and r['Month'] >= 24)
                    sr_pr = sum(abs(r['Principle']) for r in _sub_sr_schedule if m_start <= r['Month'] < m_end and r['Principle'] < 0)
                    mz_pr = sum(abs(r['Principle']) for r in _sub_mz_schedule if m_start <= r['Month'] < m_end and r['Principle'] < 0)

                    # Get operating cash flow (EBITDA component) from annual data
                    # Split annual EBITDA/tax equally across 2 semi-annual periods
                    if year <= 10:
                        a = _sub_annual[year - 1]
                        ebitda_semi = a.get('ebitda', 0) / 2.0
                        tax_semi = a.get('cf_tax', 0) / 2.0
                        ops_semi = ebitda_semi - tax_semi
                    else:
                        ops_semi = 0.0

                    # Net cash flow (semi-annual): Operations - Debt Service
                    # Note: This is a simplified calculation. Full accuracy would require
                    # semi-annual operating model, but annual split is sufficient for display
                    deposit = ops_semi - sr_ie - mz_ie - sr_pr - mz_pr

                    # Interest on opening balance (semi-annual rate)
                    opening = _fd_bal
                    interest = opening * dsra_rate_semiannual
                    closing = opening + deposit + interest
                    _fd_bal = closing

                    _dsra_fd_rows.append({
                        "Period": period_label,
                        "Opening": opening,
                        "Deposit": deposit,
                        "Interest": interest,
                        "Closing": closing
                    })

                render_table(pd.DataFrame(_dsra_fd_rows), {
                    "Opening": "€{:,.0f}",
                    "Deposit": "€{:,.0f}",
                    "Interest": "€{:,.0f}",
                    "Closing": "€{:,.0f}",
                })

            # ── AUDIT: Assets ──
            _ast_checks = []
            # Depreciable base = total loan amount
            _ast_checks.append({
                "name": "Depreciable base = total loan",
                "expected": entity_data['total_loan'],
                "actual": _sub_depr_base,
            })
            # Y10 accumulated depr <= depr base
            _acc_depr_10 = sum(_sub_annual[i]['depr'] for i in range(10))
            _ast_checks.append({
                "name": "Y10 accum depr <= depr base",
                "expected": _sub_depr_base,
                "actual": _acc_depr_10,
                "tolerance": _sub_depr_base - _acc_depr_10 + 1.0 if _acc_depr_10 <= _sub_depr_base else 0.0,
            })
            # BS fixed assets Y1 = depr base - Y1 depr
            _ast_checks.append({
                "name": "BS fixed assets Y1 = base - Y1 depr",
                "expected": max(_sub_depr_base - _sub_annual[0]['depr'], 0),
                "actual": _sub_annual[0]['bs_fixed_assets'],
            })
            run_page_audit(_ast_checks, f"{name} — Assets")

    # --- OPERATIONS ---
    if "Operations" in _tab_map:
        with _tab_map["Operations"]:
            st.header("Operations")
            if entity_key == "nwl":
                st.caption("O&M assumption: operations are contracted to a qualified third-party O&M provider (provider-agnostic in this model).")
                with st.container(border=True):
                    st.subheader("On‑ramp (6‑month cadence)")
                    ramp_rows = [
                        {"Period (months)": 12, "Ramp‑up % (annual avg)": 0.00, "Capacity Available (MLD)": None},
                        {"Period (months)": 18, "Ramp‑up % (annual avg)": 26.39, "Capacity Available (MLD)": 0.53},
                        {"Period (months)": 24, "Ramp‑up % (annual avg)": 92.36, "Capacity Available (MLD)": 1.85},
                        {"Period (months)": 30, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 36, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 42, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 48, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 54, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 60, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 66, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                        {"Period (months)": 72, "Ramp‑up % (annual avg)": 95.00, "Capacity Available (MLD)": 1.90},
                    ]
                    df_ramp = pd.DataFrame(ramp_rows)

                    col_table, col_chart = st.columns([1.1, 1.4])
                    with col_table:
                        df_table = df_ramp.copy()
                        df_table["Ramp‑up % (annual avg)"] = df_table["Ramp‑up % (annual avg)"].apply(
                            lambda x: f"{x:.2f}%" if pd.notna(x) else "—"
                        )
                        df_table["Capacity Available (MLD)"] = df_table["Capacity Available (MLD)"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
                        )
                        render_table(df_table, right_align=["Period (months)", "Ramp‑up % (annual avg)", "Capacity Available (MLD)"])

                    with col_chart:
                        cap = df_ramp["Capacity Available (MLD)"].fillna(0)
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df_ramp["Period (months)"],
                            y=cap,
                            name="Capacity (MLD)",
                            mode="lines+markers",
                            line=dict(color="#10B981", width=3),
                            marker=dict(size=7),
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_ramp["Period (months)"],
                            y=[2.0] * len(df_ramp),
                            name="Max (2.0 MLD)",
                            mode="lines",
                            line=dict(color="#1F2937", width=2, dash="dash"),
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_ramp["Period (months)"],
                            y=[1.9] * len(df_ramp),
                            name="1.9 MLD = 95% max utilization",
                            mode="lines",
                            line=dict(color="#F59E0B", width=2, dash="dot"),
                        ))
                        fig.update_layout(
                            height=300,
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title="Period (months)",
                            yaxis_title="Capacity (MLD)",
                            yaxis=dict(range=[0, 2.1]),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                st.divider()
                with st.container(border=True):
                    st.subheader("Bulk Services Fees (Right to Capacity)")
                    st.markdown(
                        "Bulk Services buy the **right to capacity**, not the obligation to fully utilise "
                        "that capacity from day one. Actual demand is expected to **grow into** reserved "
                        "capacity over time. While demand is below reserved capacity, the unused balance "
                        "becomes **overflow capacity** directed to BrownField offtake."
                    )

                    # Key metrics up top
                    _gepf_price = 40161600
                    _social_price = 4621200
                    _bulk_total = _gepf_price + _social_price
                    _total_project_zar = float(project["totals"]["total_project_cost"]) * FX_RATE
                    _bulk_pct = (_bulk_total / _total_project_zar * 100) if _total_project_zar else 0

                    _bm1, _bm2, _bm3, _bm4 = st.columns(4)
                    _bm1.metric("Total Bulk Services", f"R{_bulk_total:,.0f}")
                    _bm2.metric("GEPF (PTN 39)", f"R{_gepf_price:,.0f}")
                    _bm3.metric("Social Housing", f"R{_social_price:,.0f}")
                    _bm4.metric("% of Project Value", f"{_bulk_pct:.1f}%")

                    st.divider()

                    # Side-by-side: table + donut
                    _bt_col, _bd_col = st.columns([1.2, 1])

                    with _bt_col:
                        st.markdown("""
| Bulk Service | Rate Year | Rate (R/KL) | Peak (MLD) | Period | Price (ZAR) |
|---|---|---|---|---|---|
| GEPF (PTN 39 Lindley) | 2026 | R25,101 | 1.6 | 12 months | R40,161,600 |
| Social housing (PTN 72/76) | 2025 | R11,553 | 0.4 | 12 months | R4,621,200 |
| **Total** | | | **2.0** | | **R44,782,800** |
                    """)

                    with _bd_col:
                        fig_bulk = go.Figure(data=[go.Pie(
                            labels=["GEPF (PTN 39)", "Social Housing (PTN 72/76)"],
                            values=[_gepf_price, _social_price],
                            hole=0.55,
                            marker=dict(colors=["#2563EB", "#60A5FA"]),
                            textinfo="label+percent",
                            textposition="outside",
                            textfont_size=11,
                        )])
                        fig_bulk.update_layout(
                            height=250,
                            margin=dict(l=0, r=0, t=10, b=10),
                            showlegend=False,
                            annotations=[dict(text=f"R{_bulk_total/1e6:.1f}M", x=0.5, y=0.5, font_size=16, showarrow=False)],
                        )
                        st.plotly_chart(fig_bulk, use_container_width=True)

                st.divider()
                greenfield_box = st.container(border=True)
                with greenfield_box:
                    st.subheader("Greenfield Sales")

                months = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
                month_cols = [f"M{m}" for m in months]
                cap_map = {
                    int(r["Period (months)"]): r["Capacity Available (MLD)"]
                    for r in ramp_rows
                    if r["Capacity Available (MLD)"] is not None
                }

                with greenfield_box:
                    with st.expander("Greenfield assumptions", expanded=False):
                        _gf_c1, _gf_c2 = st.columns(2)
                        with _gf_c1:
                            annual_growth_pct = st.number_input("Annual tariff growth (%)", min_value=0.0, max_value=30.0, value=7.7, step=0.1, key="nwl_greenfield_growth_pct")
                            sewage_rate_2025 = st.number_input("Joburg sewage fee 2025 (R/KL)", min_value=0.0, value=46.40, step=0.01, key="nwl_greenfield_sewage_rate_2025")
                            brine_pct = st.number_input("Brine (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5, key="nwl_greenfield_brine_pct")
                        with _gf_c2:
                            water_rate_2025 = st.number_input("Joburg water rate 2025 (R/KL)", min_value=0.0, value=62.05, step=0.01, key="nwl_greenfield_water_rate_2025")
                            reuse_ratio = st.number_input("Piped re-use demand as % of sewage demand", min_value=0.0, max_value=2.0, value=0.80, step=0.01, key="nwl_greenfield_reuse_ratio")

                piped_sewage_topcos = [0.00, 0.10, 0.50, 0.80, 0.92, 1.06, 1.20, 1.38, 1.60, 1.82]
                construction_water_demand = [0.38, 1.25, 0.97, 0.73, 0.63, 0.52, 0.41, 0.26, 0.09, 0.00]

                sewage_capacity = [float(cap_map[m]) for m in months]
                sewage_sold_topcos = [min(cap, dem) for cap, dem in zip(sewage_capacity, piped_sewage_topcos)]
                sewage_overflow_brownfield = [max(cap - sold, 0.0) for cap, sold in zip(sewage_capacity, sewage_sold_topcos)]

                reuse_capacity = [a * (1.0 - (brine_pct / 100.0)) for a in sewage_capacity]
                reuse_demand_topcos = [d * reuse_ratio for d in sewage_sold_topcos]
                reuse_sold_topcos = [min(cap, dem) for cap, dem in zip(reuse_capacity, reuse_demand_topcos)]
                reuse_remaining_after_topcos = [max(cap - sold, 0.0) for cap, sold in zip(reuse_capacity, reuse_sold_topcos)]
                reuse_sold_construction = [
                    min(rem, dem)
                    for rem, dem in zip(reuse_remaining_after_topcos, construction_water_demand)
                ]
                reuse_overflow_agri = [
                    max(cap - s1 - s2, 0.0)
                    for cap, s1, s2 in zip(reuse_capacity, reuse_sold_topcos, reuse_sold_construction)
                ]

                growth_factor = 1.0 + (annual_growth_pct / 100.0)
                sewage_rates = [sewage_rate_2025 * (growth_factor ** (m / 12.0)) for m in months]
                water_rates = [water_rate_2025 * (growth_factor ** (m / 12.0)) for m in months]

                with greenfield_box:
                    c_ops_1, c_ops_2, c_ops_3, c_ops_4 = st.columns(4)
                    with c_ops_1:
                        st.metric("Max sellable capacity", "1.90 MLD (95% utilization)")
                    with c_ops_2:
                        st.metric("Bulk value (annual)", "R44.78m")
                    with c_ops_3:
                        st.metric("Latent baseline", "50.00 MLD")
                    with c_ops_4:
                        st.metric("Tariff growth", f"{annual_growth_pct:.1f}%")

                    st.caption("Sewage: capacity, sold demand, and overflow to BrownField (MLD)")
                    sewage_rows = [
                        ("Sellable capacity", sewage_capacity),
                        ("Demand sold - TopCos (ramp-up)", sewage_sold_topcos),
                        ("Overflow capacity - BrownField later", sewage_overflow_brownfield),
                    ]
                    sewage_data = {"Metric": [row[0] for row in sewage_rows]}
                    for i, col in enumerate(month_cols):
                        sewage_data[col] = [row[1][i] for row in sewage_rows]
                    df_usage_sewage = pd.DataFrame(sewage_data)
                    sewage_fmt = {col: "{:.2f}" for col in month_cols}
                    render_table(df_usage_sewage, sewage_fmt)

                    st.caption("Re-use: capacity, demand allocation, and overflow to agri (MLD)")
                    reuse_rows = [
                        ("Sellable capacity (net of brine)", reuse_capacity),
                        ("Demand sold - TopCos re-use", reuse_sold_topcos),
                        ("Demand sold - Construction water", reuse_sold_construction),
                        ("Overflow capacity - Agri later", reuse_overflow_agri),
                    ]
                    reuse_data = {"Metric": [row[0] for row in reuse_rows]}
                    for i, col in enumerate(month_cols):
                        reuse_data[col] = [row[1][i] for row in reuse_rows]
                    df_usage_reuse = pd.DataFrame(reuse_data)
                    reuse_fmt = {col: "{:.2f}" for col in month_cols}
                    render_table(df_usage_reuse, reuse_fmt)

                    col_s_chart, col_r_chart = st.columns(2)
                    with col_s_chart:
                        fig_sewage = go.Figure()
                        fig_sewage.add_trace(go.Bar(
                            x=month_cols, y=sewage_sold_topcos, name="Sold - TopCos", marker_color="#2563EB"
                        ))
                        fig_sewage.add_trace(go.Bar(
                            x=month_cols, y=sewage_overflow_brownfield, name="Overflow - BrownField", marker_color="#94A3B8"
                        ))
                        fig_sewage.update_layout(
                            barmode="stack",
                            title="Sewage Split",
                            yaxis_title="MLD",
                            height=300,
                            margin=dict(l=10, r=10, t=40, b=10),
                        )
                        st.plotly_chart(fig_sewage, use_container_width=True)

                    with col_r_chart:
                        fig_reuse = go.Figure()
                        fig_reuse.add_trace(go.Bar(
                            x=month_cols, y=reuse_sold_topcos, name="Sold - TopCos", marker_color="#059669"
                        ))
                        fig_reuse.add_trace(go.Bar(
                            x=month_cols, y=reuse_sold_construction, name="Sold - Construction", marker_color="#F59E0B"
                        ))
                        fig_reuse.add_trace(go.Bar(
                            x=month_cols, y=reuse_overflow_agri, name="Overflow - Agri", marker_color="#94A3B8"
                        ))
                        fig_reuse.update_layout(
                            barmode="stack",
                            title="Re-use Split",
                            yaxis_title="MLD",
                            height=300,
                            margin=dict(l=10, r=10, t=40, b=10),
                        )
                        st.plotly_chart(fig_reuse, use_container_width=True)

                    st.caption("Logic: Capacity is what can be sold. Sold demand is allocated first; unsold balance is overflow for later offtake.")

                    st.caption(
                        f"Rates projection (R/KL). Base 2025: sewage {sewage_rate_2025:.2f}, water {water_rate_2025:.2f}; annual growth {annual_growth_pct:.1f}%."
                    )
                    rate_by_month = {
                        f"M{m}": {
                            "sewage": sewage_rates[i],
                            "water": water_rates[i],
                        }
                        for i, m in enumerate(months)
                    }
                    rates_data = {
                        "Rate Type": ["Joburg sewage fees (piped)", "Joburg water rates (piped)"],
                    }
                    for col in month_cols:
                        rates_data[col] = [rate_by_month[col]["sewage"], rate_by_month[col]["water"]]
                    df_rates = pd.DataFrame(rates_data)
                    rates_fmt = {col: "{:.2f}" for col in month_cols}
                    render_table(df_rates, rates_fmt)

                    # -------------------------------------------------------
                    # REVENUE PROJECTION (20 semi-annual periods = 10 years)
                    # -------------------------------------------------------
                    st.divider()
                    st.subheader("Revenue Projection (10 Years)")
                    st.caption("Volume (MLD) x Rate (R/KL) x 182.5 days x 1000 KL/MLD = Revenue per half-year (ZAR). "
                               "BrownField sewage uses honeysucker profit-sharing rate; agri uses agri rate.")

                    _days_per_half = 182.5
                    _kl_per_mld = 1000.0
                    _rev_months = list(range(6, 126, 6))  # M6..M120 (20 periods)
                    _rev_labels = [f"M{m}" for m in _rev_months]

                    # Compute BrownField honeysucker rate from Revenue Sharing inputs (session state)
                    _srv_transport_nwl = float(st.session_state.get("nwl_srv_transport_r_km", 28.0)) * float(st.session_state.get("nwl_srv_nwl_distance_km", 10.0))
                    _srv_transport_gov = float(st.session_state.get("nwl_srv_transport_r_km", 28.0)) * float(st.session_state.get("nwl_srv_gov_distance_km", 100.0))
                    _srv_truck_cap = max(float(st.session_state.get("nwl_srv_truck_capacity_m3", 10.0)), 1.0)
                    _srv_saving_pct = float(st.session_state.get("nwl_srv_saving_to_market_pct", 40.0))
                    _honeysucker_base = max((_srv_transport_gov - _srv_transport_nwl) / _srv_truck_cap * (_srv_saving_pct / 100.0), 0.0)
                    _agri_base = 37.70
                    _srv_gf = 1.0 + (float(st.session_state.get("nwl_srv_growth_pct", 7.70)) / 100.0)

                    _rev_sewage_gf = []
                    _rev_sewage_bf = []
                    _rev_reuse_gf = []
                    _rev_reuse_con = []
                    _rev_reuse_agri = []

                    for _rm in _rev_months:
                        if _rm < 18:
                            _v_sew_gf = _v_sew_bf = _v_reu_gf = _v_reu_con = _v_reu_agri = 0.0
                        elif _rm <= 72:
                            _idx = months.index(_rm)
                            _v_sew_gf = sewage_sold_topcos[_idx]
                            _v_sew_bf = sewage_overflow_brownfield[_idx]
                            _v_reu_gf = reuse_sold_topcos[_idx]
                            _v_reu_con = reuse_sold_construction[_idx]
                            _v_reu_agri = reuse_overflow_agri[_idx]
                        else:
                            _v_sew_gf = sewage_sold_topcos[-1]
                            _v_sew_bf = sewage_overflow_brownfield[-1]
                            _v_reu_gf = reuse_sold_topcos[-1]
                            _v_reu_con = reuse_sold_construction[-1]
                            _v_reu_agri = reuse_overflow_agri[-1]

                        _sew_r = sewage_rate_2025 * (growth_factor ** (_rm / 12.0))
                        _wat_r = water_rate_2025 * (growth_factor ** (_rm / 12.0))
                        _hon_r = _honeysucker_base * (_srv_gf ** (_rm / 12.0))
                        _agr_r = _agri_base * (growth_factor ** (_rm / 12.0))

                        _factor = _kl_per_mld * _days_per_half
                        _rev_sewage_gf.append(_v_sew_gf * _factor * _sew_r)
                        _rev_sewage_bf.append(_v_sew_bf * _factor * _hon_r)  # honeysucker rate
                        _rev_reuse_gf.append(_v_reu_gf * _factor * _wat_r)
                        _rev_reuse_con.append(_v_reu_con * _factor * _wat_r)
                        _rev_reuse_agri.append(_v_reu_agri * _factor * _agr_r)  # agri rate

                    _rev_total = [a + b + c + d + e for a, b, c, d, e in
                                  zip(_rev_sewage_gf, _rev_sewage_bf, _rev_reuse_gf, _rev_reuse_con, _rev_reuse_agri)]

                    # Summary metrics
                    _total_10y = sum(_rev_total)
                    _total_sewage = sum(_rev_sewage_gf) + sum(_rev_sewage_bf)
                    _total_reuse = sum(_rev_reuse_gf) + sum(_rev_reuse_con) + sum(_rev_reuse_agri)

                    _rm1, _rm2, _rm3, _rm4 = st.columns(4)
                    _rm1.metric("10-Year Revenue", f"R{_total_10y:,.0f}")
                    _rm2.metric("Sewage Revenue", f"R{_total_sewage:,.0f}")
                    _rm3.metric("Re-use Revenue", f"R{_total_reuse:,.0f}")
                    _rm4.metric("Avg per Half-Year", f"R{_total_10y / 20:,.0f}")

                    # Stacked bar chart — revenue by segment
                    fig_rev = go.Figure()
                    fig_rev.add_trace(go.Bar(x=_rev_labels, y=_rev_sewage_gf, name="Sewage — GreenField", marker_color="#2563EB"))
                    fig_rev.add_trace(go.Bar(x=_rev_labels, y=_rev_sewage_bf, name="Sewage — BrownField", marker_color="#93C5FD"))
                    fig_rev.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_gf, name="Re-use — GreenField", marker_color="#059669"))
                    fig_rev.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_con, name="Re-use — Construction", marker_color="#F59E0B"))
                    fig_rev.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_agri, name="Re-use — Agri", marker_color="#A3E635"))
                    fig_rev.add_trace(go.Scatter(
                        x=_rev_labels, y=_rev_total, name="Total Revenue",
                        mode="lines+markers", line=dict(color="#1F2937", width=2, dash="dot"), marker=dict(size=4),
                    ))
                    fig_rev.update_layout(
                        barmode="stack",
                        title="Semi-Annual Revenue by Segment (ZAR)",
                        yaxis_title="ZAR",
                        height=450,
                        margin=dict(l=10, r=10, t=80, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
                    )
                    st.plotly_chart(fig_rev, use_container_width=True)

                    st.markdown(
                        "**Why the dip?** Honeysucker revenue sharing (R{:.2f}/KL) is over **2x more profitable** "
                        "than piped GreenField sewage (R{{sew}}/KL) per kilolitre. In early periods (M18-M30) "
                        "most plant capacity overflows to BrownField honeysuckers, generating outsized revenue. "
                        "As GreenField contracted demand ramps up, it **crowds out** the higher-margin BrownField "
                        "volume — total revenue dips. From M48 onward, the 7.7% annual rate indexation compounds "
                        "across the growing GreenField base and total revenue resumes its upward trajectory."
                        .format(_honeysucker_base).replace("{{sew}}", f"{sewage_rate_2025:.2f}")
                    )

                    # Annual aggregation table
                    _ann_rev_cols = [f"Y{y}" for y in range(1, 11)] + ["Total"]
                    _ann_rev = {"Segment": [], **{c: [] for c in _ann_rev_cols}}
                    _seg_data = {
                        "Sewage — GreenField": _rev_sewage_gf,
                        "Sewage — BrownField": _rev_sewage_bf,
                        "Re-use — GreenField": _rev_reuse_gf,
                        "Re-use — Construction": _rev_reuse_con,
                        "Re-use — Agri": _rev_reuse_agri,
                    }
                    for _seg_name, _seg_vals in _seg_data.items():
                        _ann_rev["Segment"].append(_seg_name)
                        for _yi in range(10):
                            _ann_rev[f"Y{_yi+1}"].append(_seg_vals[_yi * 2] + _seg_vals[_yi * 2 + 1])
                        _ann_rev["Total"].append(sum(_seg_vals))

                    # Total row
                    _ann_rev["Segment"].append("**Total Revenue**")
                    for _yi in range(10):
                        _ann_rev[f"Y{_yi+1}"].append(_rev_total[_yi * 2] + _rev_total[_yi * 2 + 1])
                    _ann_rev["Total"].append(_total_10y)

                    df_ann_rev = pd.DataFrame(_ann_rev)
                    render_table(df_ann_rev, {c: "R{:,.0f}" for c in _ann_rev_cols})

                st.divider()

                # ===================================================================
                # BROWNFIELD REVENUE
                # ===================================================================
                with st.container(border=True):
                    st.subheader("BrownField Revenue")
                    st.markdown(
                        "BrownField latent demand acts as a **pressure valve** during GreenField ramp-up. "
                        "NWL's overflow capacity is sold into massive existing demand in the Lanseria corridor — "
                        "every drop has **94x–1,475x** the demand waiting for it."
                    )

                    # --- Titanium Fleet Services JV ---
                    _tit_logo = LOGO_DIR / ENTITY_LOGOS.get("titanium", "")
                    _tit_c1, _tit_c2 = st.columns([0.15, 0.85])
                    with _tit_c1:
                        if _tit_logo.exists():
                            st.image(str(_tit_logo), width=100)
                    with _tit_c2:
                        st.markdown(
                            "**Titanium Fleet Services** — Dedicated haulage fleet operator capturing **50 MLD latent demand** "
                            "during the ramp-up phase. Titanium operates the tanker fleet under the O&M JV envelope, "
                            "providing the logistical backbone for BrownField revenue."
                        )
                        st.markdown(
                            "- [titaniumprojects.co.za](https://www.titaniumprojects.co.za) · Haulage Fleet Operator\n"
                            "- Revenue sharing model: NWL receives a share of the transport cost saving\n"
                            "- Fleet scales with demand — no fixed fleet cost to NWL"
                        )
                    st.markdown("---")

                    # --- Data ---
                    brownfield_latent_demand = [50, 55, 61, 67, 73, 81, 89, 97, 107, 118]
                    brownfield_capacity = sewage_overflow_brownfield
                    brownfield_oversub_x = [
                        (dem / cap) if cap else 0.0
                        for cap, dem in zip(brownfield_capacity, brownfield_latent_demand)
                    ]
                    brownfield_served = [min(cap, dem) for cap, dem in zip(brownfield_capacity, brownfield_latent_demand)]
                    _min_oversub = min(brownfield_oversub_x) if brownfield_oversub_x else 0
                    _max_oversub = max(brownfield_oversub_x) if brownfield_oversub_x else 0

                    # --- Revenue Sharing inputs (in expander to reduce clutter) ---
                    with st.expander("Revenue sharing assumptions", expanded=False):
                        _srv_c1, _srv_c2 = st.columns(2)
                        with _srv_c1:
                            srv_joburg_price = st.number_input("Joburg sewerage price (R/KL)", min_value=0.0, value=46.40, step=0.01, key="nwl_srv_joburg_price")
                            srv_transport_r_km = st.number_input("Transport cost (R/km)", min_value=0.0, value=28.0, step=1.0, key="nwl_srv_transport_r_km")
                            srv_truck_capacity_m3 = st.number_input("Truck capacity (m3)", min_value=1.0, value=10.0, step=1.0, key="nwl_srv_truck_capacity_m3")
                        with _srv_c2:
                            srv_nwl_distance_km = st.number_input("NWL roundtrip (km)", min_value=0.0, value=10.0, step=1.0, key="nwl_srv_nwl_distance_km")
                            srv_gov_distance_km = st.number_input("Govt roundtrip (km)", min_value=0.0, value=100.0, step=1.0, key="nwl_srv_gov_distance_km")
                            srv_saving_to_market_pct = st.number_input("Saving passed to market (%)", min_value=0.0, max_value=100.0, value=40.0, step=1.0, key="nwl_srv_saving_to_market_pct")
                        srv_growth_pct = st.number_input("Annual rate growth (%)", min_value=0.0, max_value=30.0, value=7.70, step=0.1, key="nwl_srv_growth_pct")

                    # --- Pricing computation ---
                    srv_transport_nwl = srv_transport_r_km * srv_nwl_distance_km
                    srv_transport_gov = srv_transport_r_km * srv_gov_distance_km
                    srv_processing_fee = srv_joburg_price * srv_truck_capacity_m3
                    srv_cost_nwl = srv_transport_nwl + srv_processing_fee
                    srv_cost_gov = srv_transport_gov
                    srv_saving_per_m3 = max((srv_transport_gov - srv_transport_nwl) / max(srv_truck_capacity_m3, 1.0), 0.0)
                    srv_market_pricing = srv_saving_per_m3 * (srv_saving_to_market_pct / 100.0)
                    srv_saving_pct = (1.0 - srv_cost_nwl / srv_cost_gov) * 100.0 if srv_cost_gov else 0.0
                    agri_base = 37.70
                    srv_growth_factor = 1.0 + (srv_growth_pct / 100.0)
                    honeysucker_rates = [srv_market_pricing * (srv_growth_factor ** (m / 12.0)) for m in months]
                    agri_rates = [agri_base * (growth_factor ** (m / 12.0)) for m in months]

                    # --- Hero metrics ---
                    _bm1, _bm2, _bm3, _bm4 = st.columns(4)
                    _bm1.metric("Oversubscription", f"{_min_oversub:,.0f}x – {_max_oversub:,.0f}x")
                    _bm2.metric("Honeysucker rate", f"R{srv_market_pricing:,.2f}/KL")
                    _bm3.metric("Agri-water rate", f"R{agri_base:.2f}/KL")
                    _bm4.metric("Cost saving vs Govt", f"{srv_saving_pct:.0f}%")

                    # --- Combined chart: dual-axis (demand/supply bars + oversubscription line) ---
                    from plotly.subplots import make_subplots
                    fig_bf = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_bf.add_trace(go.Bar(
                        x=month_cols, y=brownfield_latent_demand,
                        name="Latent demand", marker_color="#E2E8F0", opacity=0.7,
                    ), secondary_y=False)
                    fig_bf.add_trace(go.Bar(
                        x=month_cols, y=brownfield_capacity,
                        name="NWL overflow", marker_color="#10B981",
                    ), secondary_y=False)
                    fig_bf.add_trace(go.Scatter(
                        x=month_cols, y=brownfield_oversub_x,
                        name="Oversubscription (x)", mode="lines+markers+text",
                        line=dict(color="#DC2626", width=3), marker=dict(size=7, color="#DC2626"),
                        text=[f"{x:,.0f}x" for x in brownfield_oversub_x],
                        textposition="top center", textfont=dict(size=10, color="#DC2626"),
                    ), secondary_y=True)
                    fig_bf.update_layout(
                        barmode="overlay", height=380,
                        margin=dict(l=10, r=10, t=10, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    )
                    fig_bf.update_yaxes(title_text="MLD", secondary_y=False)
                    fig_bf.update_yaxes(title_text="Oversubscription (x)", secondary_y=True, showgrid=False)
                    st.plotly_chart(fig_bf, use_container_width=True)
                    st.caption(
                        "Latent demand = quantified existing demand in the Lanseria corridor (~10% p.a. growth). "
                        "NWL overflow = capacity not yet absorbed by GreenField. "
                        f"Honeysucker pricing derived from {srv_saving_to_market_pct:.0f}% of transport cost saving "
                        f"(NWL {srv_nwl_distance_km:.0f}km vs Govt {srv_gov_distance_km:.0f}km roundtrip)."
                    )

                    # --- BrownField 10-year income (temporary revenue) ---
                    st.markdown("---")
                    st.markdown("**BrownField Income Projection** — temporary revenue that declines as GreenField absorbs capacity")
                    _bf_months_20 = list(range(6, 126, 6))
                    _bf_labels_20 = [f"M{m}" for m in _bf_months_20]
                    _bf_income_hon = []
                    _bf_income_agri = []
                    _days_h = 182.5
                    _kl = 1000.0
                    for _bm in _bf_months_20:
                        if _bm < 18:
                            _bf_income_hon.append(0.0)
                            _bf_income_agri.append(0.0)
                        elif _bm <= 72:
                            _bi = months.index(_bm)
                            _hr = srv_market_pricing * (srv_growth_factor ** (_bm / 12.0))
                            _ar = agri_base * (growth_factor ** (_bm / 12.0))
                            _bf_income_hon.append(sewage_overflow_brownfield[_bi] * _kl * _days_h * _hr)
                            _bf_income_agri.append(reuse_overflow_agri[_bi] * _kl * _days_h * _ar)
                        else:
                            _hr = srv_market_pricing * (srv_growth_factor ** (_bm / 12.0))
                            _ar = agri_base * (growth_factor ** (_bm / 12.0))
                            _bf_income_hon.append(sewage_overflow_brownfield[-1] * _kl * _days_h * _hr)
                            _bf_income_agri.append(reuse_overflow_agri[-1] * _kl * _days_h * _ar)
                    _bf_income_total = [h + a for h, a in zip(_bf_income_hon, _bf_income_agri)]
                    _bf_total_10y = sum(_bf_income_total)

                    # Annual table
                    _bf_yr_cols = [f"Y{y}" for y in range(1, 11)] + ["Total"]
                    _bf_yr = {"Stream": ["Honeysucker", "Agri-water", "**Total BF Revenue**"]}
                    for _yi in range(10):
                        _h = _bf_income_hon[_yi * 2] + _bf_income_hon[_yi * 2 + 1]
                        _a = _bf_income_agri[_yi * 2] + _bf_income_agri[_yi * 2 + 1]
                        _bf_yr[f"Y{_yi+1}"] = [_h, _a, _h + _a]
                    _bf_yr["Total"] = [sum(_bf_income_hon), sum(_bf_income_agri), _bf_total_10y]
                    df_bf_yr = pd.DataFrame(_bf_yr)
                    render_table(df_bf_yr, {c: "R{:,.0f}" for c in _bf_yr_cols})

                    st.caption(
                        f"10-year BrownField income: **R{_bf_total_10y:,.0f}**. "
                        "Revenue is highest during early ramp-up (M18-M30) when most capacity overflows to BrownField, "
                        "then declines as GreenField contracted demand absorbs plant capacity."
                    )

                st.divider()
                with st.container(border=True):
                    st.subheader("O&M JV — Basilicus Water Solutions")
                    _bas_logo = LOGO_DIR / ENTITY_LOGOS.get("basilicus", "")
                    _bas_c1, _bas_c2 = st.columns([0.15, 0.85])
                    with _bas_c1:
                        if _bas_logo.exists():
                            _render_logo_dark_bg(_bas_logo, width=100)
                    with _bas_c2:
                        st.markdown(
                            "**Basilicus Water Solutions** — KPI-driven O&M operator with **35+ years** combined experience "
                            "in water and wastewater treatment. Provides **24/7 monitoring** and performance-based operations "
                            "management under the O&M JV envelope."
                        )
                        st.markdown(
                            "- [basilicus.co.za](https://www.basilicus.co.za) · O&M Operator\n"
                            "- Fixed monthly fee model with annual CPI-linked escalation\n"
                            "- Equity participation in NWL (included in shareholder equity)"
                        )
                    st.markdown("---")
                    st.markdown("**O&M Contract Terms**")
                    _om_assumptions = pd.DataFrame([
                        {"Item": "Flat fee per month", "Value": "ZAR 1,000,000"},
                        {"Item": "Annual O&M cost (fixed fee)", "Value": "ZAR 12,000,000"},
                        {"Item": "O&M indexation (p.a.)", "Value": "5.0%"},
                        {"Item": "Awarded O&M contract", "Value": "Yes"},
                        {"Item": "Equity issued", "Value": "Yes"},
                        {"Item": "Equity value / prepayment", "Value": "ZAR 44,720,857"},
                        {"Item": "EPC contract issued", "Value": "No"},
                        {"Item": "Opex starts with CoD (month)", "Value": 12},
                    ])
                    render_table(_om_assumptions)

                    _om_start_month = 12
                    _om_monthly_fee = 1000000
                    _om_index_pa = 0.05
                    _semi_months = list(range(6, 139, 6))
                    _om_period_rows = []
                    for _idx, _m in enumerate(_semi_months, start=1):
                        if _m >= _om_start_month:
                            _years_from_cod = (_m - _om_start_month) / 12.0
                            _idx_factor = (1.0 + _om_index_pa) ** _years_from_cod
                            _monthly_fee_indexed = _om_monthly_fee * _idx_factor
                            _half_year_cost = _monthly_fee_indexed * 6
                        else:
                            _idx_factor = 0.0
                            _monthly_fee_indexed = 0.0
                            _half_year_cost = 0.0
                        _om_period_rows.append({
                            "Period": _idx,
                            "Month": _m,
                            "Year": f"{_m/12:.1f}",
                            "Index Factor": _idx_factor,
                            "Monthly O&M (ZAR)": _monthly_fee_indexed,
                            "O&M Cost (ZAR)": _half_year_cost,
                        })
                    df_om_period = pd.DataFrame(_om_period_rows)
                    st.caption("Generated O&M cost schedule (6-month cadence; direct input for later P&L wiring).")
                    render_table(df_om_period, {
                        "Index Factor": "{:.4f}",
                        "Monthly O&M (ZAR)": "{:,.0f}",
                        "O&M Cost (ZAR)": "{:,.0f}",
                    })

                st.divider()
                with st.container(border=True):
                    st.subheader("Power / Electricity")
                    st.caption("Inter-company electricity from LanRED solar plant. MABR technology consumes ~0.4 kWh/m3.")
                    with st.expander("Power assumptions", expanded=False):
                        _pw_c1, _pw_c2, _pw_c3 = st.columns(3)
                        with _pw_c1:
                            st.number_input("Energy intensity (kWh/m3)", min_value=0.0, value=0.4, step=0.01, key="nwl_power_kwh_per_m3")
                        with _pw_c2:
                            st.number_input("Eskom base rate (R/kWh)", min_value=0.0, value=2.81, step=0.01, key="nwl_power_eskom_base")
                            st.number_input("IC discount (%)", min_value=0.0, max_value=50.0, value=10.0, step=0.5, key="nwl_power_ic_discount")
                        with _pw_c3:
                            st.number_input("Annual escalation (%)", min_value=0.0, max_value=30.0, value=10.0, step=0.1, key="nwl_power_escalation")
                    _pw_kwh = float(st.session_state.get("nwl_power_kwh_per_m3", 0.4))
                    _pw_eskom = float(st.session_state.get("nwl_power_eskom_base", 2.81))
                    _pw_disc = float(st.session_state.get("nwl_power_ic_discount", 10.0))
                    _pw_rate = _pw_eskom * (1.0 - _pw_disc / 100.0)
                    _pw_esc = float(st.session_state.get("nwl_power_escalation", 10.0))
                    _pw_daily_kwh = 1.9 * 1000.0 * _pw_kwh  # MLD * 1000 m3/MLD * kWh/m3
                    _pw_annual_base = _pw_daily_kwh * 365.0 * _pw_rate
                    _pw1, _pw2, _pw3, _pw4 = st.columns(4)
                    _pw1.metric("IC Rate (Eskom -10%)", f"R{_pw_rate:.2f}/kWh")
                    _pw2.metric("Daily consumption (steady)", f"{_pw_daily_kwh:,.0f} kWh")
                    _pw3.metric("Annual cost (Y1 rate)", f"R{_pw_annual_base:,.0f}")
                    _pw4.metric("Inter-company supplier", "LanRED Solar")

                st.divider()

                # --- MABR Energy Advantage ---
                with st.container(border=True):
                    st.subheader("MABR Energy Advantage")

                    # CAS benchmark from config (default 1.2 kWh/m3)
                    _power_cfg = operations_config.get("nwl", {}).get("power", {})
                    _cas_kwh_m3 = float(_power_cfg.get("cas_benchmark_kwh_per_m3", 1.2))
                    _mabr_kwh_m3 = _pw_kwh  # 0.4 kWh/m3 (MABR via OxyMem)
                    _saving_pct = (1.0 - _mabr_kwh_m3 / _cas_kwh_m3) * 100.0
                    _pw_esc_factor = 1.0 + (_pw_esc / 100.0)
                    _capacity_mld = 1.9  # steady-state
                    _daily_m3 = _capacity_mld * 1000.0

                    st.markdown(
                        f"OxyMem's MABR achieves up to **95% oxygen transfer efficiency** vs <30% for conventional bubble "
                        f"diffusion — delivering **{_saving_pct:.0f}% lower energy consumption** at {_mabr_kwh_m3} kWh/m\u00b3 "
                        f"vs ~{_cas_kwh_m3} kWh/m\u00b3 for conventional activated sludge (CAS). "
                        f"At NWL's {_capacity_mld} MLD capacity, this translates to significant lifetime cost savings — "
                        f"compounded by the inter-company solar discount from LanRED."
                    )

                    # Hero metrics
                    _sv1, _sv2, _sv3, _sv4 = st.columns(4)
                    _sv1.metric("MABR", f"{_mabr_kwh_m3} kWh/m\u00b3")
                    _sv2.metric("Conventional CAS", f"{_cas_kwh_m3} kWh/m\u00b3")
                    _sv3.metric("Energy Saving", f"{_saving_pct:.0f}%")
                    _daily_saving_kwh = (_cas_kwh_m3 - _mabr_kwh_m3) * _daily_m3
                    _sv4.metric("Daily kWh Saved", f"{_daily_saving_kwh:,.0f}")

                    st.divider()

                    # --- CAS Energy Intensity Comparison ---
                    st.markdown("**Energy Intensity Comparison**")
                    _cas_col1, _cas_col2, _cas_col3 = st.columns(3)
                    _cas_kwh_per_m3_saving = _cas_kwh_m3 - _mabr_kwh_m3
                    _cas_pct_saving = (_cas_kwh_per_m3_saving / _cas_kwh_m3) * 100.0
                    with _cas_col1:
                        st.metric("MABR Technology", f"{_mabr_kwh_m3:.2f} kWh/m\u00b3")
                    with _cas_col2:
                        st.metric("CAS (Conventional)", f"{_cas_kwh_m3:.2f} kWh/m\u00b3")
                    with _cas_col3:
                        st.metric("Energy Savings", f"{_cas_kwh_per_m3_saving:.2f} kWh/m\u00b3", delta=f"-{_cas_pct_saving:.0f}%", delta_color="inverse")

                    # Live MABR vs CAS comparison
                    st.info(
                        f"MABR uses **{_mabr_kwh_m3} kWh/m\u00b3** vs CAS **{_cas_kwh_m3} kWh/m\u00b3** — "
                        f"**{_cas_pct_saving:.0f}% energy savings** ({_cas_kwh_per_m3_saving} kWh/m\u00b3 less)"
                    )

                    # Compute 10-year annual costs: MABR vs Conventional
                    _mabr_annual_zar = []
                    _cas_annual_zar = []
                    _cum_saving_zar = []
                    _cum_total = 0.0
                    _start_month = 18  # power starts M18
                    for _yi in range(10):
                        _mabr_yr = 0.0
                        _cas_yr = 0.0
                        for _mi in range(_yi * 12 + 1, (_yi + 1) * 12 + 1):
                            if _mi < _start_month:
                                continue
                            # Capacity ramp: simplified — use 0 before M18, ramp to 1.9 by M24, then steady
                            if _mi < 18:
                                _cap = 0.0
                            elif _mi < 24:
                                _cap = 0.53 + (1.9 - 0.53) * (_mi - 18) / 6.0
                            else:
                                _cap = 1.9
                            _vol = _cap * 1000.0  # m3/day
                            _yrs_from = (_mi - _start_month) / 12.0
                            _rate_esc = _pw_rate * (_pw_esc_factor ** _yrs_from)
                            _eskom_esc = _pw_eskom * (_pw_esc_factor ** _yrs_from)
                            _mabr_yr += _vol * _mabr_kwh_m3 * _rate_esc * 30.44
                            _cas_yr += _vol * _cas_kwh_m3 * _eskom_esc * 30.44  # CAS would pay full Eskom
                        _mabr_annual_zar.append(_mabr_yr)
                        _cas_annual_zar.append(_cas_yr)
                        _cum_total += (_cas_yr - _mabr_yr)
                        _cum_saving_zar.append(_cum_total)

                    _years_lbl = [f"Y{i+1}" for i in range(10)]
                    _lifetime_saving = _cum_saving_zar[-1] if _cum_saving_zar else 0

                    st.metric("10-Year Lifetime Saving", f"R{_lifetime_saving:,.0f}", delta=f"\u20ac{_lifetime_saving / FX_RATE:,.0f}")

                    # Dual chart: annual cost comparison bars + cumulative saving line
                    from plotly.subplots import make_subplots
                    _fig_pw = make_subplots(specs=[[{"secondary_y": True}]])
                    _fig_pw.add_trace(go.Bar(
                        x=_years_lbl, y=[v / 1e6 for v in _cas_annual_zar],
                        name='Conventional CAS (full Eskom)', marker_color='#EF4444', opacity=0.7,
                    ), secondary_y=False)
                    _fig_pw.add_trace(go.Bar(
                        x=_years_lbl, y=[v / 1e6 for v in _mabr_annual_zar],
                        name='MABR + LanRED Solar (-10%)', marker_color='#10B981', opacity=0.85,
                    ), secondary_y=False)
                    _fig_pw.add_trace(go.Scatter(
                        x=_years_lbl, y=[v / 1e6 for v in _cum_saving_zar],
                        name='Cumulative Saving', mode='lines+markers',
                        line=dict(color='#2563EB', width=3), marker=dict(size=7),
                    ), secondary_y=True)
                    _fig_pw.update_layout(
                        barmode='group', height=380,
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                    )
                    _fig_pw.update_yaxes(title_text="Annual Cost (R millions)", secondary_y=False)
                    _fig_pw.update_yaxes(title_text="Cumulative Saving (R millions)", secondary_y=True)
                    st.plotly_chart(_fig_pw, use_container_width=True)

                    st.caption(
                        "Conventional CAS benchmark: ~1.6 kWh/m\u00b3 at full Eskom tariff. "
                        "MABR (OxyMem): 0.4 kWh/m\u00b3 at inter-company rate (Eskom -10%). "
                        "Sources: [OxyMem](https://www.oxymem.com/blog/bubble-less-mabr-system-can-reduce-energy-costs), "
                        "[Springer Nature](https://link.springer.com/chapter/10.1007/978-3-030-13068-8_128)"
                    )

                st.divider()

                # --- CoE RENT (inter-company to Timberworx) ---
                with st.container(border=True):
                    st.subheader("CoE Rent (IC to Timberworx)")

                    _rent_cfg = operations_config.get("nwl", {}).get("coe_rent", {})
                    _rent_om_pct = float(_rent_cfg.get("om_overhead_pct", 2.0))
                    _rent_monthly_eur, _rent_annual_eur, _rent_wacc, _rent_coe_capex = compute_coe_rent_monthly_eur(_rent_om_pct)
                    _rent_monthly_zar = _rent_monthly_eur * FX_RATE
                    _rent_esc_pct = float(_rent_cfg.get("annual_escalation_pct", 5.0))
                    _rent_start = int(_rent_cfg.get("start_month", 24))
                    _rent_total_yield = _rent_wacc + (_rent_om_pct / 100.0)
                    _sr_rate_rent = structure['sources']['senior_debt']['interest']['rate']
                    _mz_rate_rent = structure['sources']['mezzanine']['interest']['total_rate']

                    st.markdown(
                        f"NWL occupies space in the Centre of Excellence (owned by Timberworx). "
                        f"Rent is an **inter-company transaction** — mirrors TWX lease revenue. "
                        f"Derived using **capital-recovery method**:"
                    )
                    st.markdown(
                        f"| Component | | |\n"
                        f"|---|---|---|\n"
                        f"| CoE CapEx (building only) | | **\u20ac{_rent_coe_capex:,.0f}** |\n"
                        f"| WACC | 85% \u00d7 {_sr_rate_rent:.2%} + 15% \u00d7 {_mz_rate_rent:.2%} | **{_rent_wacc:.4%}** |\n"
                        f"| O&M overhead | | **{_rent_om_pct:.1f}%** |\n"
                        f"| Total yield | WACC + O&M | **{_rent_total_yield:.4%}** |\n"
                        f"| **Annual cost** | CapEx \u00d7 yield | **\u20ac{_rent_annual_eur:,.0f}** (R{_rent_annual_eur * FX_RATE:,.0f}) |\n"
                        f"| **Monthly cost** | | **\u20ac{_rent_monthly_eur:,.0f}** (R{_rent_monthly_zar:,.0f}) |"
                    )

                    _rc1, _rc2, _rc3, _rc4 = st.columns(4)
                    _rc1.metric("Monthly Cost", f"R{_rent_monthly_zar:,.0f}")
                    _rc2.metric("WACC", f"{_rent_wacc:.2%}")
                    _rc3.metric("Total Yield", f"{_rent_total_yield:.2%}")
                    _rc4.metric("Escalation", f"{_rent_esc_pct:.0f}% p.a.")

                    # 10-year rent schedule — use model output (respects CoE sale stop)
                    _rent_annual_eur_actual = [a.get('rent_cost', 0) for a in _sub_annual]
                    _rent_annual_zar_actual = [v * FX_RATE for v in _rent_annual_eur_actual]
                    _rent_total_10yr = sum(_rent_annual_zar_actual)
                    _years_lbl_rent = [f"Y{i+1}" for i in range(10)]

                    fig_rent = go.Figure()
                    fig_rent.add_trace(go.Bar(
                        x=_years_lbl_rent, y=[v / 1e6 for v in _rent_annual_zar_actual],
                        name='CoE Rent Cost', marker_color='#F59E0B',
                    ))
                    fig_rent.update_layout(
                        height=300, yaxis_title='R millions',
                        margin=dict(l=10, r=10, t=30, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                    )
                    st.plotly_chart(fig_rent, use_container_width=True)
                    _nwl_coe_sale_yr = int(operations_config.get("timberworx", {}).get("coe_sale_to_llc", {}).get("sale_year", 4))
                    st.caption(
                        f"Total: R{_rent_total_10yr:,.0f} "
                        f"(\u20ac{_rent_total_10yr / FX_RATE:,.0f}). "
                        f"Starts M{_rent_start}, escalates {_rent_esc_pct:.0f}% p.a. "
                        f"**Stops after Y{_nwl_coe_sale_yr} (CoE sold to LLC).** Mirrors TWX lease revenue."
                    )

            elif entity_key == "timberworx":
                # --- LANSERIA HOUSING DEMAND vs TWX CAPACITY ---
                _twx_demand_cfg = operations_config.get("timberworx", {}).get("lanseria_demand", {})
                _twx_phases_cfg = operations_config.get("timberworx", {}).get("production_phases", {})
                if _twx_demand_cfg:
                    with st.container(border=True):
                        st.subheader("Lanseria Housing Demand vs TWX Capacity")

                        _demand_houses = _twx_demand_cfg.get("houses_cumulative_by_year", [1500,3500,6500,10000,15000,20000,25500,31500,38000,45000])
                        _ppl_per_house = float(_twx_demand_cfg.get("people_per_house", 3.2))
                        _kva_per_stand = float(_twx_demand_cfg.get("kva_per_stand", 6.0))
                        _diversity = float(_twx_demand_cfg.get("diversity_factor", 0.7))
                        _comm_mult = float(_twx_demand_cfg.get("commercial_multiplier", 1.5))
                        _jobs_constr = float(_twx_demand_cfg.get("jobs_per_1000_houses_construction", 1500))
                        _jobs_perm = float(_twx_demand_cfg.get("jobs_per_1000_houses_permanent", 200))

                        _ph1 = _twx_phases_cfg.get("phase_1", {})
                        _ph2 = _twx_phases_cfg.get("phase_2", {})
                        _ph3 = _twx_phases_cfg.get("phase_3", {})

                        _demand_incr = [_demand_houses[0]] + [_demand_houses[i] - _demand_houses[i-1] for i in range(1, len(_demand_houses))]
                        _ph1_cap = int(_ph1.get("houses_per_year", 52))
                        _ph2_cap = int(_ph2.get("houses_per_year", 156))
                        _ph3_cap = int(_ph3.get("houses_per_year", 650))

                        _years_lbl_d = [f"Y{i+1}" for i in range(10)]
                        _pop_5yr = _demand_houses[4] * _ppl_per_house
                        _pop_10yr = _demand_houses[9] * _ppl_per_house
                        _mw_5yr = _demand_houses[4] * _kva_per_stand * _diversity * _comm_mult / 1000
                        _avg_demand_5yr = _demand_houses[4] / 5.0
                        _avg_demand_10yr = _demand_houses[9] / 10.0

                        _d1, _d2, _d3, _d4 = st.columns(4)
                        _d1.metric("5-Year Demand", f"{_demand_houses[4]:,} houses", f"{_pop_5yr:,.0f} people")
                        _d2.metric("10-Year Demand", f"{_demand_houses[9]:,} houses", f"{_pop_10yr:,.0f} people")
                        _d3.metric("Phase 2 (this application)", f"{_ph2_cap}/yr", f"{_ph2_cap / _avg_demand_5yr * 100:.1f}% of avg demand")
                        _d4.metric("Phase 3 (future)", f"{_ph3_cap}/yr", f"{_ph3_cap / _avg_demand_10yr * 100:.0f}% of avg demand")

                        fig_demand = go.Figure()
                        fig_demand.add_trace(go.Bar(
                            x=_years_lbl_d, y=_demand_incr,
                            name='Lanseria demand (houses/yr)', marker_color='#DC2626', opacity=0.7,
                            text=[f"{int(v):,}" for v in _demand_incr], textposition='outside',
                        ))
                        fig_demand.add_trace(go.Scatter(x=_years_lbl_d, y=[_ph2_cap]*10,
                            name=f'Phase 2: {_ph2_cap}/yr', mode='lines',
                            line=dict(color='#F59E0B', width=2, dash='dash')))
                        fig_demand.add_trace(go.Scatter(x=_years_lbl_d, y=[_ph3_cap]*10,
                            name=f'Phase 3: {_ph3_cap}/yr', mode='lines',
                            line=dict(color='#10B981', width=2)))
                        # Pill annotations on the phase lines
                        fig_demand.add_annotation(x='Y1', y=_ph2_cap, text=f"<b>Phase 2: {_ph2_cap}/yr</b>",
                            showarrow=False, yshift=14, bgcolor='#F59E0B', font=dict(size=10, color='white'),
                            bordercolor='#F59E0B', borderwidth=1, borderpad=4)
                        fig_demand.add_annotation(x='Y1', y=_ph3_cap, text=f"<b>Phase 3: {_ph3_cap}/yr</b>",
                            showarrow=False, yshift=14, bgcolor='#10B981', font=dict(size=10, color='white'),
                            bordercolor='#10B981', borderwidth=1, borderpad=4)
                        fig_demand.update_layout(height=350, yaxis_title='Houses per Year',
                            yaxis_range=[0, max(_demand_incr) * 1.2],
                            margin=dict(l=10, r=10, t=40, b=10),
                            legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5))
                        st.plotly_chart(fig_demand, use_container_width=True)
                        st.caption("Annual new housing starts per GEPF township development plan. Variance reflects phased land release and infrastructure readiness.")

                        st.markdown("**What 15,000 houses means for Lanseria:**")
                        _mw_10yr = _demand_houses[9] * _kva_per_stand * _diversity * _comm_mult / 1000
                        st.markdown(
                            f"| Metric | 5-Year ({_demand_houses[4]:,}) | 10-Year ({_demand_houses[9]:,}) |\n"
                            f"|---|---|---|\n"
                            f"| Population | {_pop_5yr:,.0f} | {_pop_10yr:,.0f} |\n"
                            f"| Avg annual demand | {_avg_demand_5yr:,.0f} houses/yr | {_avg_demand_10yr:,.0f} houses/yr |\n"
                            f"| Construction jobs (peak) | {_demand_houses[4]/1000*_jobs_constr:,.0f} | {_demand_houses[9]/1000*_jobs_constr:,.0f} |\n"
                            f"| Permanent jobs | {_demand_houses[4]/1000*_jobs_perm:,.0f} | {_demand_houses[9]/1000*_jobs_perm:,.0f} |\n"
                            f"| Power demand | {_mw_5yr:,.0f} MW | {_mw_10yr:,.0f} MW |\n"
                            f"| **Phase 2 ({_ph2_cap}/yr)** | **{_ph2_cap/_avg_demand_5yr*100:.1f}%** of avg | **{_ph2_cap/_avg_demand_10yr*100:.1f}%** of avg |")
                        st.info(
                            f"Phase 2 ({_ph2_cap} houses/yr) covers only **{_ph2_cap/max(_demand_incr[2],1)*100:.0f}%** of annual demand. "
                            f"Phase 3 automation ({_ph3_cap}/yr) is essential to scale — but even then covers "
                            f"~{_ph3_cap/max(_demand_incr[4],1)*100:.0f}% of Lanseria demand. Multiple factories needed. "
                            f"National backlog: 3.7M houses growing 178k/yr.")

                _coe_sale_yr = int(operations_config.get("timberworx", {}).get("coe_sale_to_llc", {}).get("sale_year", 4))

                # --- HOUSE SALES (Core Revenue — shown first) ---
                with st.container(border=True):
                    st.subheader("House Sales (Core Revenue)")

                    _sales_cfg = operations_config.get("timberworx", {}).get("timber_sales", {})
                    _sales_enabled = _sales_cfg.get("enabled", True)
                    _unit_type = _sales_cfg.get("unit_type", "houses")
                    _units_per_year = _sales_cfg.get("units_per_year", [20, 80, 130, 156, 156, 156, 156, 156, 156, 156])
                    _price_per_unit = float(_sales_cfg.get("price_per_unit_zar", 340000))
                    _sales_esc = float(_sales_cfg.get("annual_price_escalation_pct", 6.0))
                    _sales_start = int(_sales_cfg.get("start_month", 6))
                    _labor_monthly_p1 = float(_sales_cfg.get("labor_monthly_phase1_zar", 130000))
                    _labor_per_house = _labor_monthly_p1 / (52.0 / 12.0)
                    _labor_esc = float(_sales_cfg.get("labor_escalation_pct", 5.0))
                    _gross_margin_pct = ((_price_per_unit - _labor_per_house) / _price_per_unit) * 100

                    _ts1, _ts2, _ts3, _ts4 = st.columns(4)
                    _ts1.metric("Service Fee/House", f"R{_price_per_unit:,.0f}")
                    _ts2.metric("Labor/House", f"R{_labor_per_house:,.0f}")
                    _ts3.metric("Gross Margin", f"{_gross_margin_pct:.0f}%")
                    _ts4.metric("Escalation", f"Rev +{_sales_esc:.0f}% | Labor +{_labor_esc:.0f}%")

                    st.markdown("**Service model — TWX is NOT an EPC.** Timberworx provides production **capacity, quality control, and throughput**.")

                    # Ecosystem flow diagram — EPCF wraps all 3 entities, TWX highlighted
                    st.markdown("""
<div style="display:flex; align-items:center; justify-content:center; margin:20px 0;">
  <div style="background:linear-gradient(135deg,#f0f0f5,#e8e8f0); border:2px solid #7c3aed; border-radius:16px; padding:18px 20px 12px 20px; position:relative;">
    <div style="position:absolute; top:-12px; left:20px; background:#7c3aed; color:white; font-size:11px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; padding:3px 14px; border-radius:6px;">EPCF Ecosystem</div>
    <div style="display:flex; align-items:center; gap:10px; margin-top:6px;">
      <div style="background:#78909c; color:white; border-radius:10px; padding:12px 16px; text-align:center; min-width:120px;">
        <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; opacity:0.85;">Procurement</div>
        <div style="font-size:14px; font-weight:700; margin:3px 0;">TWX Trade</div>
        <div style="font-size:10px; opacity:0.85;">Sources &amp; finances<br/>raw timber</div>
      </div>
      <div style="font-size:24px; color:#94a3b8;">&#8594;</div>
      <div style="background:linear-gradient(135deg,#059669,#10b981); color:white; border-radius:10px; padding:14px 20px; text-align:center; min-width:150px; border:3px solid #047857; box-shadow:0 4px 16px rgba(5,150,105,0.35); transform:scale(1.08);">
        <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px;">Panel Production</div>
        <div style="font-size:17px; font-weight:800; margin:4px 0;">Timberworx &#9733;</div>
        <div style="font-size:10px;">Capacity, quality<br/>&amp; throughput</div>
      </div>
      <div style="font-size:24px; color:#94a3b8;">&#8594;</div>
      <div style="background:#78909c; color:white; border-radius:10px; padding:12px 16px; text-align:center; min-width:120px;">
        <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; opacity:0.85;">On-site Erection</div>
        <div style="font-size:14px; font-weight:700; margin:3px 0;">Greenblocks</div>
        <div style="font-size:10px; opacity:0.85;">Assembly &amp;<br/>erection (JV)</div>
      </div>
    </div>
    <div style="text-align:center; margin-top:8px; font-size:11px; color:#7c3aed; font-weight:600;">Financed end-to-end by EPCF partner</div>
  </div>
</div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
TWX charges **R{_price_per_unit:,.0f}/house** (~34% of ~R1M total house price) as a service fee. **No raw material cost** — procurement and financing handled by TWX Trade and EPCF.

**Labor:** R{_labor_monthly_p1:,.0f}/month (Phase 1) = R{_labor_per_house:,.0f}/house, scaling linearly. Rev +{_sales_esc:.0f}% p.a. | Labor +{_labor_esc:.0f}% p.a.

**Phase 1** (M1-6): 1 house/week via Greenblocks JV. **Phase 2** (M7+): 3 houses/week = {max(_units_per_year)}/yr with Optimat panel machines (COD 6 months).
Pipeline: R178M across 10 committed projects. SA housing deficit: 3.7M units, growing 178k/yr.
                    """)

                    # Timber sales chart
                    _sales_years_lbl = [f"Y{i+1}" for i in range(10)]
                    _sales_units = _units_per_year if len(_units_per_year) == 10 else _units_per_year + [_units_per_year[-1]] * (10 - len(_units_per_year))
                    _sales_rev_annual = [a.get('rev_timber_sales', 0) for a in _sub_annual]

                    fig_sales = go.Figure()
                    fig_sales.add_trace(go.Bar(
                        x=_sales_years_lbl, y=_sales_units,
                        name='Units Sold', marker_color='#34D399',
                        text=[f"{u:,.0f}" for u in _sales_units], textposition='outside',
                    ))
                    _max_units = max(_sales_units) if _sales_units else 100
                    fig_sales.update_layout(
                        height=300, yaxis_title=f'Units ({_unit_type})',
                        yaxis_range=[0, _max_units * 1.2],
                        margin=dict(l=10, r=10, t=40, b=10),
                    )
                    st.plotly_chart(fig_sales, use_container_width=True)

                    _sales_total = sum(_sales_rev_annual)
                    _sales_total_units = sum(_sales_units)
                    _labor_total = sum(a.get('labor_cost', 0) for a in _sub_annual)
                    st.caption(f"10-year total: {_sales_total_units:,.0f} houses | Net Revenue (after labor): \u20ac{_sales_total:,.0f} | Total labor: \u20ac{_labor_total:,.0f}")

                # --- CoE SALE TO LLC (one-time event, Year 4) ---
                with st.container(border=True):
                    st.subheader(f"CoE Sale to Lanseria LLC (Year {_coe_sale_yr})")
                    _sale_premium = float(operations_config.get("timberworx", {}).get("coe_sale_to_llc", {}).get("premium_pct", 10.0))
                    _coe_sale_eur = sum(a.get('rev_coe_sale', 0) for a in _sub_annual)
                    _coe_capex_eur = load_config("assets")["assets"]["coe"]["line_items"][0]["budget"]

                    _cs1, _cs2, _cs3 = st.columns(3)
                    _cs1.metric("CoE Building CapEx", f"\u20ac{_coe_capex_eur:,.0f}")
                    _cs2.metric("Sale Premium", f"{_sale_premium:.0f}%")
                    _cs3.metric("Sale Proceeds", f"\u20ac{_coe_sale_eur:,.0f}")

                    st.markdown(f"""
Centre of Excellence building sold to Lanseria LLC at **{_sale_premium:.0f}% premium** on CapEx (\u20ac{_coe_capex_eur:,.0f} \u00d7 1.{_sale_premium:.0f} = **\u20ac{_coe_sale_eur:,.0f}**).

**After sale (Y{_coe_sale_yr}+):** All CoE-related items stop — lease revenue, training, O&M, depreciation, NWL rent obligation.
Only house sales continue permanently.
                    """)

                # --- CoE LEASE REVENUE (Y1 to sale year — IC from NWL) ---
                with st.container(border=True):
                    st.subheader(f"CoE Lease Revenue (Y2-{_coe_sale_yr - 1}, IC from NWL)")

                    _lease_cfg = operations_config.get("timberworx", {}).get("coe_lease", {})
                    _lease_om_pct = float(_lease_cfg.get("om_overhead_pct", 2.0))
                    _lease_monthly_eur, _lease_annual_eur, _lease_wacc, _lease_coe_capex = compute_coe_rent_monthly_eur(_lease_om_pct)
                    _lease_monthly_zar = _lease_monthly_eur * FX_RATE
                    _lease_esc_pct = float(_lease_cfg.get("annual_escalation_pct", 5.0))
                    _lease_start = int(_lease_cfg.get("start_month", 24))
                    _lease_total_yield = _lease_wacc + (_lease_om_pct / 100.0)
                    _sr_rate_disp = structure['sources']['senior_debt']['interest']['rate']
                    _mz_rate_disp = structure['sources']['mezzanine']['interest']['total_rate']

                    st.markdown(
                        f"NWL occupies space in the Centre of Excellence. Lease revenue is an **inter-company transaction** — "
                        f"mirrors NWL's rent expense. Derived using **capital-recovery method**. "
                        f"**Stops in Y{_coe_sale_yr} when CoE is sold to LLC.**"
                    )

                    _lt1, _lt2, _lt3, _lt4 = st.columns(4)
                    _lt1.metric("Monthly Revenue", f"R{_lease_monthly_zar:,.0f}")
                    _lt2.metric("Total Yield", f"{_lease_total_yield:.2%}")
                    _lt3.metric("Escalation", f"{_lease_esc_pct:.0f}% p.a.")
                    _lt4.metric("Stops", f"Year {_coe_sale_yr}")

                    # 10-year lease schedule — use model output (respects CoE sale)
                    _lease_annual_eur_actual = [a.get('rev_lease', 0) for a in _sub_annual]
                    _lease_annual_zar_actual = [v * FX_RATE for v in _lease_annual_eur_actual]
                    _lease_total = sum(_lease_annual_zar_actual)
                    _years_lbl_lease = [f"Y{i+1}" for i in range(10)]

                    fig_lease = go.Figure()
                    fig_lease.add_trace(go.Bar(
                        x=_years_lbl_lease, y=[v / 1e6 for v in _lease_annual_zar_actual],
                        name='CoE Lease Revenue', marker_color='#34D399',
                    ))
                    fig_lease.update_layout(
                        height=250, yaxis_title='ZAR (millions)',
                        margin=dict(l=10, r=10, t=30, b=10),
                    )
                    st.plotly_chart(fig_lease, use_container_width=True)
                    st.caption(f"Total: R{_lease_total:,.0f} (\u20ac{_lease_total / FX_RATE:,.0f}). **Ends Y{_coe_sale_yr} (CoE sold to LLC).**")

                # --- SETA TRAINING PROGRAMS (CoE COD → sale year) ---
                with st.container(border=True):
                    st.subheader(f"Training Programs (CoE M18 \u2192 Y{_coe_sale_yr})")

                    _train_cfg = operations_config.get("timberworx", {}).get("training_programs", {})
                    _seta_accredited = _train_cfg.get("seta_accredited", True)
                    _fee_per_student = float(_train_cfg.get("fee_per_student_zar", 15000))
                    _seta_subsidy = float(_train_cfg.get("seta_subsidy_per_student_zar", 8000))
                    _train_throughput = _train_cfg.get("throughput_students_per_year", [120, 240, 360, 450, 500, 550, 600, 600, 650, 650])
                    _train_esc = float(_train_cfg.get("annual_escalation_pct", 7.0))
                    _train_start = int(_train_cfg.get("start_month", 30))

                    _tt1, _tt2, _tt3, _tt4 = st.columns(4)
                    _tt1.metric("Fee/Student", f"R{_fee_per_student:,.0f}")
                    _tt2.metric("SETA Subsidy", f"R{_seta_subsidy:,.0f}")
                    _tt3.metric("Total/Student", f"R{_fee_per_student + _seta_subsidy:,.0f}")
                    _tt4.metric("Stops", f"Year {_coe_sale_yr}")

                    st.markdown(f"""
**Dual-Track SETA Program:** (1) timber construction — CLT, mass-timber, DFMA methods;
(2) water & sanitation — MABR technology, plant operations (NWL synergy).
Training **requires the CoE building** — starts M{_train_start} (CoE COD), **ends when CoE sold in Y{_coe_sale_yr}**.

**SETA** = Sector Education and Training Authority. SA government body that funds skills development through mandatory employer levies (1% of payroll).
Accredited training providers receive **R{_seta_subsidy:,.0f}/student subsidy** in addition to the R{_fee_per_student:,.0f} tuition fee. Escalation: {_train_esc:.0f}% p.a.
                    """)

                    # Training chart — use model output (respects CoE sale stop)
                    _train_years_lbl = [f"Y{i+1}" for i in range(10)]
                    _train_rev_annual = [a.get('rev_training', 0) for a in _sub_annual]
                    _train_students_actual = [a.get('students', 0) for a in _sub_annual]
                    for _tsi in range(len(_train_students_actual)):
                        if _sub_annual[_tsi].get('coe_sold', False):
                            _train_students_actual[_tsi] = 0

                    fig_train = go.Figure()
                    fig_train.add_trace(go.Bar(
                        x=_train_years_lbl, y=_train_students_actual,
                        name='Students/Year', marker_color='#60A5FA',
                        text=[f"{int(s)}" if s > 0 else "" for s in _train_students_actual], textposition='outside',
                    ))
                    _max_students = max(_train_students_actual) if _train_students_actual else 50
                    fig_train.update_layout(
                        height=250, yaxis_title='Students per Year',
                        yaxis_range=[0, max(_max_students * 1.2, 10)],
                        margin=dict(l=10, r=10, t=30, b=10),
                    )
                    st.plotly_chart(fig_train, use_container_width=True)

                    _train_total = sum(_train_rev_annual)
                    _train_total_students = sum(_train_students_actual)
                    st.caption(f"Total: {_train_total_students:,.0f} students | Revenue: \u20ac{_train_total:,.0f}. **Ends Y{_coe_sale_yr} (CoE sold).**")

                # --- REVENUE MIX SUMMARY ---
                with st.container(border=True):
                    st.subheader("Revenue Mix")

                    _rev_lease_10y = sum(a.get('rev_lease', 0) for a in _sub_annual)
                    _rev_training_10y = sum(a.get('rev_training', 0) for a in _sub_annual)
                    _rev_timber_10y = sum(a.get('rev_timber_sales', 0) for a in _sub_annual)
                    _rev_coe_sale_10y = sum(a.get('rev_coe_sale', 0) for a in _sub_annual)
                    _rev_total_10y = _rev_lease_10y + _rev_training_10y + _rev_timber_10y + _rev_coe_sale_10y

                    _rm1, _rm2, _rm3, _rm4 = st.columns(4)
                    _rm1.metric("House Sales", f"\u20ac{_rev_timber_10y:,.0f}", f"{_rev_timber_10y / max(_rev_total_10y, 1) * 100:.0f}% (core)")
                    _rm2.metric("CoE Sale (Y4)", f"\u20ac{_rev_coe_sale_10y:,.0f}", "One-time to LLC")
                    _rm3.metric("Lease + Training", f"\u20ac{_rev_lease_10y + _rev_training_10y:,.0f}", "Stops after Y4")
                    _rm4.metric("10-Year Total", f"\u20ac{_rev_total_10y:,.0f}")

                    st.caption("House sales = core permanent revenue. CoE lease, training, and CoE sale revenue all stop after Year 4 (LLC sale).")

                    # Revenue mix pie chart
                    fig_mix = go.Figure(data=[go.Pie(
                        labels=['House Sales (core)', 'CoE Sale (Y4)', 'CoE Lease (Y1-4)', 'Training (Y1-4)'],
                        values=[_rev_timber_10y, _rev_coe_sale_10y, _rev_lease_10y, _rev_training_10y],
                        hole=0.5,
                        marker=dict(colors=["#3B82F6", "#F59E0B", "#34D399", "#60A5FA"]),
                        textinfo='percent',
                        textposition='inside',
                        insidetextorientation='radial',
                    )])
                    fig_mix.update_layout(
                        height=350,
                        margin=dict(l=0, r=0, t=10, b=10),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                        annotations=[dict(text=f"\u20ac{_rev_total_10y/1e3:.0f}k<br>10-Year", x=0.5, y=0.5, font_size=14, showarrow=False)],
                    )
                    st.plotly_chart(fig_mix, use_container_width=True)

            elif entity_key == "lanred":
                _lr_scenario = _state_str("lanred_scenario", "Greenfield")

                if _lr_scenario == "Brownfield+":
                    # ══════════════════════════════════════════════════════════
                    # BROWNFIELD+ OPERATIONS — Northlands Energy Portfolio
                    # ══════════════════════════════════════════════════════════
                    _bf_cfg = operations_config.get("lanred", {}).get("brownfield_plus", {})
                    _np_cfg = _bf_cfg.get("northlands_portfolio", {})
                    _bf_sites = _np_cfg.get("sites", [])
                    _bf_rev_esc = _np_cfg.get("revenue_escalation_pct", 8.0)
                    _bf_cost_esc = _np_cfg.get("cost_escalation_pct", 6.0)
                    _bf_years_lbl = [f"Y{i+1}" for i in range(10)]

                    # ── SECTION 1: Portfolio Overview ──
                    with st.container(border=True):
                        st.subheader("1. Northlands Portfolio")
                        st.caption("5 operating C&I solar+BESS sites. Contracted tenant PPAs, prepaid smart metering, Tier 1 components.")
                        _tot_monthly_rev = sum(s['monthly_income_zar'] for s in _bf_sites)
                        _tot_monthly_cogs = sum(s['monthly_cogs_zar'] for s in _bf_sites)
                        _tot_monthly_net = sum(s['monthly_net_zar'] for s in _bf_sites)
                        _tot_pv_kw = sum(s['pv_kwp'] for s in _bf_sites)
                        _tot_bess_kw = sum(s['bess_kwh'] for s in _bf_sites)

                        _bm1, _bm2, _bm3, _bm4 = st.columns(4)
                        _bm1.metric("Monthly Revenue", f"R{_tot_monthly_rev:,.0f}", f"R{_tot_monthly_rev*12:,.0f}/yr")
                        _bm2.metric("Monthly Net", f"R{_tot_monthly_net:,.0f}", f"{_tot_monthly_net/_tot_monthly_rev*100:.0f}% margin")
                        _bm3.metric("Total PV", f"{_tot_pv_kw/1000:.2f} MWp", f"{len(_bf_sites)} sites")
                        _bm4.metric("Total BESS", f"{_tot_bess_kw/1000:.1f} MWh", f"{_tot_bess_kw:,} kWh")

                        # Per-site breakdown
                        for _s in _bf_sites:
                            _net_pct = _s['monthly_net_zar'] / _s['monthly_income_zar'] * 100 if _s['monthly_income_zar'] else 0
                            _coj_str = "COJ Registered" if _s.get('coj_registered') else "COJ **Pending**"
                            st.markdown(f"**{_s['name']}** ({_s['location']}) — {_s['pv_kwp']} kWp + {_s['bess_kwh']} kWh | "
                                        f"R{_s['monthly_income_zar']:,} \u2192 Net R{_s['monthly_net_zar']:,}/mo ({_net_pct:.0f}%) | {_coj_str}")

                    # ── SECTION 2: Revenue Projection ──
                    with st.container(border=True):
                        st.subheader("2. Revenue Projection")
                        st.caption(f"Revenue escalates at {_bf_rev_esc:.0f}% p.a. (PPA indexation). Costs escalate at {_bf_cost_esc:.0f}% p.a.")

                        _bf_ann_rev = [_tot_monthly_rev * 12 * ((1 + _bf_rev_esc / 100) ** yi) for yi in range(10)]
                        _bf_ann_cogs = [_tot_monthly_cogs * 12 * ((1 + _bf_cost_esc / 100) ** yi) for yi in range(10)]
                        _bf_ann_ins = [sum(s['monthly_insurance_zar'] for s in _bf_sites) * 12 * ((1 + _bf_cost_esc / 100) ** yi) for yi in range(10)]
                        _bf_ann_om = [sum(s['monthly_om_zar'] for s in _bf_sites) * 12 * ((1 + _bf_cost_esc / 100) ** yi) for yi in range(10)]
                        _bf_ann_net = [r - c - i - o for r, c, i, o in zip(_bf_ann_rev, _bf_ann_cogs, _bf_ann_ins, _bf_ann_om)]

                        _bf_r1, _bf_r2, _bf_r3 = st.columns(3)
                        _bf_r1.metric("Y1 Revenue", f"R{_bf_ann_rev[0]:,.0f}", f"\u20ac{_bf_ann_rev[0]/FX_RATE:,.0f}")
                        _bf_r2.metric("Y1 Net Profit", f"R{_bf_ann_net[0]:,.0f}", f"\u20ac{_bf_ann_net[0]/FX_RATE:,.0f}")
                        _bf_r3.metric("10-Yr Revenue", f"R{sum(_bf_ann_rev):,.0f}", f"\u20ac{sum(_bf_ann_rev)/FX_RATE:,.0f}")

                        fig_bf_rev = go.Figure()
                        fig_bf_rev.add_trace(go.Bar(
                            x=_bf_years_lbl, y=[r / 1e6 for r in _bf_ann_rev],
                            name='Revenue', marker_color='#3B82F6',
                            text=[f"R{r/1e6:.1f}M" for r in _bf_ann_rev], textposition='outside',
                        ))
                        fig_bf_rev.add_trace(go.Scatter(
                            x=_bf_years_lbl, y=[n / 1e6 for n in _bf_ann_net],
                            name='Net Profit', mode='lines+markers',
                            line=dict(color='#10B981', width=3),
                            marker=dict(size=8),
                        ))
                        fig_bf_rev.update_layout(
                            height=320, margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title='ZAR (millions)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_bf_rev, use_container_width=True)

                    # ── SECTION 3: Cost Structure ──
                    with st.container(border=True):
                        st.subheader("3. Cost Structure")
                        st.caption(f"Costs escalate at {_bf_cost_esc:.0f}% p.a. Revenue escalation ({_bf_rev_esc:.0f}%) exceeds cost escalation \u2192 margin expands over time.")

                        _bf_y1_margin = _bf_ann_net[0] / _bf_ann_rev[0] * 100 if _bf_ann_rev[0] else 0
                        _bf_y10_margin = _bf_ann_net[9] / _bf_ann_rev[9] * 100 if _bf_ann_rev[9] else 0

                        _bc1, _bc2, _bc3, _bc4 = st.columns(4)
                        _bc1.metric("Y1 COGS", f"R{_bf_ann_cogs[0]:,.0f}", "Grid purchases")
                        _bc2.metric("Y1 Insurance", f"R{_bf_ann_ins[0]:,.0f}")
                        _bc3.metric("Y1 O&M", f"R{_bf_ann_om[0]:,.0f}")
                        _bc4.metric("Margin Expansion", f"{_bf_y1_margin:.0f}% \u2192 {_bf_y10_margin:.0f}%", f"+{_bf_y10_margin - _bf_y1_margin:.0f}pp over 10yr")

                        fig_bf_cost = go.Figure()
                        fig_bf_cost.add_trace(go.Bar(x=_bf_years_lbl, y=[c / 1e6 for c in _bf_ann_cogs], name='COGS', marker_color='#DC2626'))
                        fig_bf_cost.add_trace(go.Bar(x=_bf_years_lbl, y=[i / 1e6 for i in _bf_ann_ins], name='Insurance', marker_color='#F59E0B'))
                        fig_bf_cost.add_trace(go.Bar(x=_bf_years_lbl, y=[o / 1e6 for o in _bf_ann_om], name='O&M', marker_color='#6366F1'))
                        fig_bf_cost.update_layout(
                            barmode='stack', height=320, margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title='ZAR (millions)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_bf_cost, use_container_width=True)

                    # ── SECTION 4: Risk Factors ──
                    with st.container(border=True):
                        st.subheader("4. Risk Factors")
                        _deco_rev = next((s['monthly_income_zar'] for s in _bf_sites if 'deco' in s['name'].lower()), 0)
                        _deco_pct = _deco_rev / _tot_monthly_rev * 100 if _tot_monthly_rev else 0
                        st.markdown(f"""
| Risk | Impact | Mitigation |
|------|--------|------------|
| **BESS replacement** | ~R30M at Y10 for 4 MWh | Budget from retained earnings; new BESS cheaper (cost curve) |
| **Deco Park COJ** | {_deco_pct:.0f}% of revenue, SSEG pending | Transfer application in progress; operate under existing license |
| **Eskom stabilization** | Load-shedding premium erodes | PPAs priced vs grid \u2014 competitive even without load-shedding |
| **O&M dependency** | Northlands Energy post-sale | 3-year O&M contract included; transition to in-house Y3 |
| **FX exposure** | ZAR revenue vs EUR debt service | Investec currency swap locks EUR rate for IC loan tenure |
""")

                    # ── SECTION 5: Scenario Comparison ──
                    with st.container(border=True):
                        st.subheader("5. Greenfield vs Brownfield+")
                        st.caption("Side-by-side 10-year EBITDA comparison using model data.")

                        # Get brownfield EBITDA from model
                        _bf_ebitda = [a.get('ebitda', 0) for a in _sub_annual]
                        _bf_rev_eur = [a.get('rev_total', 0) for a in _sub_annual]

                        _sc1, _sc2, _sc3 = st.columns(3)
                        _bf_10y_rev = sum(_bf_rev_eur)
                        _bf_10y_ebitda = sum(_bf_ebitda)
                        _sc1.metric("10-Yr Revenue", f"\u20ac{_bf_10y_rev:,.0f}")
                        _sc2.metric("10-Yr EBITDA", f"\u20ac{_bf_10y_ebitda:,.0f}")
                        _bf_margin = _bf_10y_ebitda / _bf_10y_rev * 100 if _bf_10y_rev else 0
                        _sc3.metric("EBITDA Margin", f"{_bf_margin:.0f}%")

                        fig_bf_ebitda = go.Figure()
                        fig_bf_ebitda.add_trace(go.Bar(
                            x=_bf_years_lbl, y=[e / 1e3 for e in _bf_ebitda],
                            name='Brownfield+ EBITDA', marker_color='#10B981',
                            text=[f"\u20ac{e/1e3:.0f}k" for e in _bf_ebitda], textposition='outside',
                        ))
                        fig_bf_ebitda.update_layout(
                            height=320, margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title='EBITDA (\u20ac thousands)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_bf_ebitda, use_container_width=True)

                        st.markdown("""
**Key advantages of Brownfield+:**
- **Day 1 revenue** — no 18-month construction wait
- **Contracted cashflows** — 20yr PPAs with credit-worthy tenants
- **Natural FX hedge** — ZAR revenues matched via Investec currency swap
- **No ECA requirement** — operating assets, not construction risk
- **Higher Y1-Y3 EBITDA** — immediate income vs greenfield ramp-up
""")

                else:
                    # ══════════════════════════════════════════════════════════
                    # GREENFIELD OPERATIONS (existing code)
                    # ══════════════════════════════════════════════════════════
                    lanred_cfg = operations_config.get("lanred", {})
                    solar_cfg = lanred_cfg.get("solar_capacity", {})
                    battery_cfg = lanred_cfg.get("battery_storage", {})
                    power_sales_cfg = lanred_cfg.get("power_sales", {})

                    # Budget from slider (set on Assets tab, read via session state)
                    _lr_assets = load_config("assets")["assets"]
                    _lr_total = _lr_assets.get("solar", {}).get("total", 2908809)
                    _lr_bess_alloc = _state_float("lanred_bess_alloc_pct", 14) / 100.0
                    _lr_bess_budget = _lr_total * _lr_bess_alloc
                    _lr_pv_budget = _lr_total - _lr_bess_budget
                    _lr_cost_kwp = float(solar_cfg.get("cost_per_kwp_eur", 850))
                    _lr_cost_kwh = float(battery_cfg.get("cost_per_kwh_eur", 364))
                    _lr_installed_kwp = _lr_pv_budget / _lr_cost_kwp if _lr_cost_kwp > 0 else 0
                    _lr_installed_mwp = _lr_installed_kwp / 1000.0
                    _lr_bess_kwh = _lr_bess_budget / _lr_cost_kwh if _lr_cost_kwh > 0 else 0
                    _lr_bess_mwh = _lr_bess_kwh / 1000.0

                    _cap_factor = float(solar_cfg.get("capacity_factor_pct", 21.5))
                    _degradation = float(solar_cfg.get("degradation_pa_pct", 0.5))
                    _cod_month = int(solar_cfg.get("cod_month", 18))
                    _batt_usable = float(battery_cfg.get("usable_capacity_pct", 90.0))
                    _batt_efficiency = float(battery_cfg.get("roundtrip_efficiency_pct", 85.0))
                    _batt_deg = float(battery_cfg.get("degradation_pa_pct", 2.0))
                    _annual_gen_kwh = _lr_installed_kwp * (_cap_factor / 100.0) * 8766
                    _annual_gen_gwh = _annual_gen_kwh / 1e6

                    # ============================================================
                    # SECTION 1: PRODUCTION — How generation is calculated
                    # ============================================================
                    with st.container(border=True):
                        st.subheader("1. Production")
                        st.caption("Solar capacity derived from budget. Generation = Capacity x Capacity Factor x Hours.")

                        # --- Solar PV Production ---
                        _specific_yield = _lr_installed_kwp * (_cap_factor / 100.0) * 8766 / _lr_installed_kwp if _lr_installed_kwp > 0 else 0
                        _annual_gen_mwh = _annual_gen_kwh / 1000.0
                        _y10_cf = _cap_factor * ((1.0 - _degradation / 100.0) ** 9)
                        _y10_gen_mwh = _lr_installed_kwp * (_y10_cf / 100.0) * 8766 / 1000.0

                        _p1, _p2, _p3, _p4, _p5 = st.columns(5)
                        _p1.metric("Installed Capacity", f"{_lr_installed_mwp:.1f} MWp",
                            f"\u20ac{_lr_pv_budget:,.0f} \u00f7 \u20ac{_lr_cost_kwp:,.0f}/kWp")
                        _p2.metric("Capacity Factor", f"{_cap_factor:.1f}%",
                            "Gauteng fixed-tilt (21-22%)")
                        _p3.metric("Specific Yield", f"{_specific_yield:,.0f} kWh/kWp/yr",
                            "Benchmark: 1,700-1,900")
                        _p4.metric("Y1 Generation", f"{_annual_gen_mwh:,.0f} MWh",
                            f"= {_annual_gen_mwh / 1000:.1f} GWh")
                        _p5.metric("Y10 Generation", f"{_y10_gen_mwh:,.0f} MWh",
                            f"{_degradation}% p.a. degradation")

                        # --- BESS ---
                        _arb_cfg = power_sales_cfg.get("bess_arbitrage", {})
                        _arb_cycles = int(battery_cfg.get("cycles_per_year", 260))
                        _bess_usable = _lr_bess_kwh * (_batt_usable / 100.0)
                        _bess_annual_throughput = _bess_usable * _arb_cycles / 1000.0  # MWh
                        _b1, _b2, _b3, _b4, _b5 = st.columns(5)
                        _b1.metric("BESS Capacity", f"{_lr_bess_mwh:.1f} MWh",
                            f"\u20ac{_lr_bess_budget:,.0f} \u00f7 \u20ac{_lr_cost_kwh:,.0f}/kWh")
                        _b2.metric("Usable (DoD)", f"{_batt_usable:.0f}%",
                            f"{_bess_usable:,.0f} kWh effective")
                        _b3.metric("RT Efficiency", f"{_batt_efficiency:.0f}%",
                            "Benchmark: 85-90%")
                        _b4.metric("Cycles/Year", f"{_arb_cycles}",
                            "HD: 2/day (3mo) + LD: 1/day (9mo)")
                        _b5.metric("Annual Throughput", f"{_bess_annual_throughput:,.0f} MWh",
                            f"{_batt_deg}% p.a. degradation")

                        # 10-year generation table
                        _gen_data = [a.get('generation_kwh', 0) for a in _sub_annual]
                        _bess_data = [a.get('bess_effective_kwh', 0) for a in _sub_annual]
                        _cf_data = [a.get('capacity_factor_pct', 0) for a in _sub_annual]
                        _years_lbl = [f"Y{i+1}" for i in range(10)]

                        fig_gen = go.Figure()
                        fig_gen.add_trace(go.Bar(
                            x=_years_lbl, y=[g / 1000 for g in _gen_data],
                            name='Solar Generation (MWh)', marker_color='#F59E0B', opacity=0.8,
                            text=[f"{g/1000:,.0f}" for g in _gen_data], textposition='outside',
                        ))
                        fig_gen.add_trace(go.Scatter(
                            x=_years_lbl, y=_cf_data,
                            name='Capacity Factor (%)', mode='lines+markers',
                            line=dict(color='#DC2626', width=2, dash='dash'),
                            marker=dict(size=6), yaxis='y2',
                        ))
                        fig_gen.update_layout(
                            height=320,
                            margin=dict(l=10, r=60, t=40, b=10),
                            yaxis=dict(title='Generation (MWh)'),
                            yaxis2=dict(title='CF (%)', overlaying='y', side='right', showgrid=False,
                                range=[0, max(_cf_data) * 1.3] if _cf_data else [0, 30]),
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_gen, use_container_width=True)

                    # ============================================================
                    # SECTION 2: REVENUE — 2 streams: PPA Sales + BESS Arbitrage
                    # ============================================================
                    with st.container(border=True):
                        st.subheader("2. Revenue")
                        st.caption("Two revenue streams: PPA electricity sales (IC NWL + Smart City + open market) and BESS TOU arbitrage.")

                        # --- PPA Sales (combined IC + SC + Market) ---
                        _ppa_rev = [a.get('rev_ic_nwl', 0) + a.get('rev_smart_city', 0) + a.get('rev_open_market', 0) for a in _sub_annual]
                        _bess_rev = [a.get('rev_bess_arbitrage', 0) for a in _sub_annual]
                        _total_rev_data = [a.get('rev_total', 0) for a in _sub_annual]

                        # PPA pricing info
                        ic_nwl_cfg = power_sales_cfg.get("ic_nwl", {})
                        _ic_eskom = float(ic_nwl_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
                        _ic_disc = float(ic_nwl_cfg.get("ic_discount_pct", 10.0))
                        sc_cfg = power_sales_cfg.get("smart_city_offtake", {})
                        _sc_tariff = float(sc_cfg.get("joburg_business_tariff_r_per_kwh", 2.289))
                        _sc_disc = float(sc_cfg.get("discount_pct", 10.0))
                        _sc_rate = _sc_tariff * (1 - _sc_disc / 100)
                        _ic_rate = _ic_eskom * (1 - _ic_disc / 100)
                        _ppa_esc = float(ic_nwl_cfg.get("annual_escalation_pct", 10.0))

                        # BESS info (2-cycle seasonal model)
                        _arb_hd_cfg = _arb_cfg.get("high_demand_season", {})
                        _arb_ld_cfg = _arb_cfg.get("low_demand_season", {})
                        _arb_hd_peak = float(_arb_hd_cfg.get("peak_rate_r_per_kwh", 7.04))
                        _arb_hd_offpeak = float(_arb_hd_cfg.get("offpeak_rate_r_per_kwh", 1.02))
                        _arb_ld_peak = float(_arb_ld_cfg.get("peak_rate_r_per_kwh", 2.00))
                        _arb_solar_cost = float(_arb_cfg.get("solar_charge_cost_r_per_kwh", 0.10))
                        _arb_esc = float(_arb_cfg.get("annual_escalation_pct", 10.0))
                        _arb_rt_eff = _batt_efficiency / 100.0
                        _hd_c1_spread = _arb_hd_peak * _arb_rt_eff - _arb_hd_offpeak
                        _hd_c2_spread = _arb_hd_peak * _arb_rt_eff - _arb_solar_cost
                        _ld_c2_spread = _arb_ld_peak * _arb_rt_eff - _arb_solar_cost
                        _arb_hd_months = int(_arb_hd_cfg.get("months", 3))
                        _arb_ld_months = int(_arb_ld_cfg.get("months", 9))
                        _arb_hd_days = _arb_hd_months * 30.4
                        _arb_ld_days = _arb_ld_months * 30.4
                        _arb_y1_rev_zar = _bess_usable * ((_hd_c1_spread + _hd_c2_spread) * _arb_hd_days + _ld_c2_spread * _arb_ld_days)

                        _ppa_10y = sum(_ppa_rev)
                        _bess_10y = sum(_bess_rev)
                        _rev_10y = sum(_total_rev_data)

                        _r1, _r2, _r3 = st.columns(3)
                        _r1.metric("10-Yr PPA Sales", f"\u20ac{_ppa_10y:,.0f}",
                            f"IC R{_ic_rate:.2f} / SC R{_sc_rate:.2f}/kWh, {_ppa_esc:.0f}% esc")
                        _r2.metric("10-Yr BESS Arbitrage", f"\u20ac{_bess_10y:,.0f}",
                            f"HD R{_hd_c1_spread:.2f}+R{_hd_c2_spread:.2f} / LD R{_ld_c2_spread:.2f}, {_arb_esc:.0f}% esc")
                        _r3.metric("10-Yr Total Revenue", f"\u20ac{_rev_10y:,.0f}",
                            f"PPA {_ppa_10y / max(_rev_10y, 1) * 100:.0f}% / BESS {_bess_10y / max(_rev_10y, 1) * 100:.0f}%")

                        # Revenue chart: PPA + BESS stacked
                        fig_rev = go.Figure()
                        fig_rev.add_trace(go.Bar(
                            x=_years_lbl, y=[r / 1e3 for r in _ppa_rev],
                            name='PPA Sales', marker_color='#3B82F6',
                            text=[f"\u20ac{r/1e3:.0f}k" for r in _ppa_rev], textposition='inside',
                        ))
                        fig_rev.add_trace(go.Bar(
                            x=_years_lbl, y=[r / 1e3 for r in _bess_rev],
                            name='BESS Arbitrage', marker_color='#F59E0B',
                            text=[f"\u20ac{r/1e3:.0f}k" for r in _bess_rev], textposition='inside',
                        ))
                        fig_rev.update_layout(
                            barmode='stack', height=320,
                            margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title='Revenue (\u20ac thousands)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_rev, use_container_width=True)

                        st.markdown(f"""
**PPA Sales** — Electricity sold via Power Purchase Agreements:
- **IC to NWL**: Eskom R{_ic_eskom:.2f}/kWh minus {_ic_disc:.0f}% = **R{_ic_rate:.2f}/kWh** (demand-driven ~6% share)
- **Smart City tenants**: Joburg tariff R{_sc_tariff:.3f}/kWh minus {_sc_disc:.0f}% = **R{_sc_rate:.2f}/kWh** (absorbs ~94% at steady state)
- All PPA rates escalate at **{_ppa_esc:.0f}% p.a.**

**BESS 2-Cycle Seasonal Arbitrage** — Eskom Homeflex TOU rates (2024/25):
- **High Demand** (Jun-Aug, {_arb_hd_months}mo): 2 cycles/day
  - Cycle 1: Grid R{_arb_hd_offpeak:.2f} → Peak R{_arb_hd_peak:.2f} x {_arb_rt_eff:.0%} = **R{_hd_c1_spread:.2f}**/kWh
  - Cycle 2: Solar R{_arb_solar_cost:.2f} → Peak R{_arb_hd_peak:.2f} x {_arb_rt_eff:.0%} = **R{_hd_c2_spread:.2f}**/kWh
- **Low Demand** (Sep-May, {_arb_ld_months}mo): 1 cycle/day (solar only)
  - Cycle 2: Solar R{_arb_solar_cost:.2f} → Peak R{_arb_ld_peak:.2f} x {_arb_rt_eff:.0%} = **R{_ld_c2_spread:.2f}**/kWh
- {_arb_cycles} cycles/yr x {_bess_usable:,.0f} kWh = **R{_arb_y1_rev_zar:,.0f}/yr** (Y1) | {_arb_esc:.0f}% p.a. esc
                        """)

                    # ============================================================
                    # SECTION 3: OPERATING COSTS
                    # ============================================================
                    with st.container(border=True):
                        st.subheader("3. Operating Costs")
                        _om_cfg_lr = lanred_cfg.get("om", {})
                        _om_fixed = float(_om_cfg_lr.get("fixed_annual_zar", 120000))
                        _om_var = float(_om_cfg_lr.get("variable_r_per_kwh", 0.05))
                        _om_esc = float(_om_cfg_lr.get("annual_indexation_pa", 0.05)) * 100
                        _lr_solar_budget_val = load_config("assets")['assets'].get('solar', {}).get('total', 2908809)
                        _lr_total_capex_zar = _lr_solar_budget_val * FX_RATE
                        _om_pct = (_om_fixed / _lr_total_capex_zar * 100) if _lr_total_capex_zar > 0 else 0
                        _om_r1, _om_r2, _om_r3, _om_r4 = st.columns(4)
                        _om_r1.metric("Fixed O&M", f"R{_om_fixed:,.0f}/yr", "Benchmark: ~1% of CapEx")
                        _om_r2.metric("Variable O&M", f"R{_om_var:.2f}/kWh", "Benchmark: R0.03-0.08/kWh")
                        _om_r3.metric("Escalation", f"{_om_esc:.0f}% p.a.")
                        _om_r4.metric("O&M / CapEx", f"{_om_pct:.1f}%", "Industry: 1-1.5%")

                    # ============================================================
                    # SECTION 4: SMART CITY DEMAND CONTEXT
                    # ============================================================
                    _lr_demand_cfg = lanred_cfg.get("smart_city_power_demand", {})
                    if _lr_demand_cfg:
                        with st.container(border=True):
                            st.subheader("4. Smart City Power Demand")

                            _sc_kva = float(_lr_demand_cfg.get("kva_per_house", 6.0))
                            _sc_div = float(_lr_demand_cfg.get("diversity_factor", 0.7))
                            _sc_mult = float(_lr_demand_cfg.get("commercial_multiplier", 1.5))
                            _sc_ultimate_mva = float(_lr_demand_cfg.get("ultimate_mva", 90))
                            _lr_avg_mw = _lr_installed_mwp * (_cap_factor / 100.0)
                            _lr_pct_of_demand = _lr_avg_mw / _sc_ultimate_mva * 100

                            _lp1, _lp2, _lp3 = st.columns(3)
                            _lp1.metric("Ultimate SC Demand", f"{_sc_ultimate_mva:.0f} MW", "Infrastructure Report")
                            _lp2.metric("LanRED Phase 1", f"{_lr_installed_mwp:.1f} MWp", f"{_lr_avg_mw:.1f} MW avg")
                            _lp3.metric("Coverage", f"{_lr_pct_of_demand:.1f}%", "Catalytic seed — 0.5% of demand")

                            _twx_demand_houses = operations_config.get("timberworx", {}).get("lanseria_demand", {}).get(
                                "houses_cumulative_by_year", [1500,3500,6500,10000,15000,20000,25500,31500,38000,45000])
                            _mw_per_house = _sc_kva * _sc_div * _sc_mult / 1000.0
                            _pwr_demand_mw = [h * _mw_per_house for h in _twx_demand_houses]
                            _pwr_years = [f"Y{i+1}" for i in range(len(_pwr_demand_mw))]

                            fig_pwr = go.Figure()
                            fig_pwr.add_trace(go.Bar(
                                x=_pwr_years, y=_pwr_demand_mw,
                                name='SC Power Demand (MW)', marker_color='#DC2626', opacity=0.7,
                                text=[f"{v:.0f}" for v in _pwr_demand_mw], textposition='outside',
                            ))
                            fig_pwr.add_hline(y=_lr_installed_mwp, line_dash="dash", line_color="#10B981",
                                annotation_text=f"LanRED Phase 1: {_lr_installed_mwp:.1f} MWp",
                                annotation_position="top right")
                            fig_pwr.update_layout(height=320, yaxis_title='MW',
                                yaxis_range=[0, max(_pwr_demand_mw) * 1.15],
                                margin=dict(l=10, r=10, t=40, b=10),
                                legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5))
                            st.plotly_chart(fig_pwr, use_container_width=True)

                    # ============================================================
                    # SECTION 5: 10-YEAR EBITDA SUMMARY
                    # ============================================================
                    with st.container(border=True):
                        st.subheader("5. 10-Year EBITDA")
                        _om_data = [a.get('om_cost', 0) for a in _sub_annual]
                        _ebitda_data = [a.get('ebitda', 0) for a in _sub_annual]
                        _total_gen_all = sum(_gen_data)
                        _total_rev_all = sum(_total_rev_data)
                        _total_om_all = sum(_om_data)
                        _total_ebitda_all = sum(_ebitda_data)

                        _lr_m1, _lr_m2, _lr_m3, _lr_m4 = st.columns(4)
                        _lr_m1.metric("10-Yr Generation", f"{_total_gen_all / 1e6:.1f} GWh")
                        _lr_m2.metric("10-Yr Revenue", f"\u20ac{_total_rev_all:,.0f}")
                        _lr_m3.metric("10-Yr O&M", f"\u20ac{_total_om_all:,.0f}")
                        _lr_m4.metric("10-Yr EBITDA", f"\u20ac{_total_ebitda_all:,.0f}",
                            f"{_total_ebitda_all / max(_total_rev_all, 1) * 100:.0f}% margin")

                    # ============================================================
                    # SECTION 6: PV vs BESS RETURN COMPARISON
                    # ============================================================
                    with st.container(border=True):
                        st.subheader("6. PV vs BESS Return Comparison")
                        st.caption("Comparing 10-year return on investment: PPA sales (PV asset) vs BESS arbitrage (BESS asset).")

                        # PV return (10-year total PPA revenue / PV budget)
                        _pv_roi_10y = (_ppa_10y / _lr_pv_budget * 100) if _lr_pv_budget > 0 else 0
                        _bess_roi_10y = (_bess_10y / _lr_bess_budget * 100) if _lr_bess_budget > 0 else 0
                        _total_roi_10y = (_rev_10y / (_lr_pv_budget + _lr_bess_budget) * 100) if (_lr_pv_budget + _lr_bess_budget) > 0 else 0

                        # Annual yield (Y3 = first full year with all streams)
                        _pv_y3_rev = _ppa_rev[2] if len(_ppa_rev) > 2 else 0
                        _bess_y3_rev = _bess_rev[2] if len(_bess_rev) > 2 else 0
                        _pv_annual_yield = (_pv_y3_rev / _lr_pv_budget * 100) if _lr_pv_budget > 0 else 0
                        _bess_annual_yield = (_bess_y3_rev / _lr_bess_budget * 100) if _lr_bess_budget > 0 else 0

                        # PV advantages
                        _pv_life = 25
                        _bess_life = 10
                        _pv_deg = _degradation
                        _bess_deg_pct = _batt_deg

                        _rc1, _rc2, _rc3, _rc4 = st.columns(4)
                        _rc1.metric("PV 10-Yr ROI", f"{_pv_roi_10y:.0f}%",
                            f"Y3 yield: {_pv_annual_yield:.1f}%")
                        _rc2.metric("BESS 10-Yr ROI", f"{_bess_roi_10y:.0f}%",
                            f"Y3 yield: {_bess_annual_yield:.1f}%")
                        _rc3.metric("Blended ROI", f"{_total_roi_10y:.0f}%",
                            f"PV {_lr_pv_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}% / BESS {_lr_bess_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}%")
                        _winner = "PV" if _pv_roi_10y > _bess_roi_10y else "BESS"
                        _spread = abs(_pv_roi_10y - _bess_roi_10y)
                        _rc4.metric("Winner", _winner,
                            f"+{_spread:.0f}pp spread")

                        # Comparison chart: PV vs BESS annual revenue
                        fig_compare = go.Figure()
                        fig_compare.add_trace(go.Bar(
                            x=_years_lbl, y=[r / 1e3 for r in _ppa_rev],
                            name=f'PV (PPA) — \u20ac{_lr_pv_budget:,.0f}', marker_color='#3B82F6',
                            text=[f"\u20ac{r/1e3:.0f}k" for r in _ppa_rev], textposition='outside',
                        ))
                        fig_compare.add_trace(go.Bar(
                            x=_years_lbl, y=[r / 1e3 for r in _bess_rev],
                            name=f'BESS (Arb) — \u20ac{_lr_bess_budget:,.0f}', marker_color='#F59E0B',
                            text=[f"\u20ac{r/1e3:.0f}k" for r in _bess_rev], textposition='outside',
                        ))
                        fig_compare.update_layout(
                            barmode='group', height=320,
                            margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title='Annual Revenue (\u20ac thousands)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_compare, use_container_width=True)

                        st.markdown(f"""
| Metric | PV (Solar) | BESS (Battery) |
|--------|-----------|----------------|
| Budget | \u20ac{_lr_pv_budget:,.0f} | \u20ac{_lr_bess_budget:,.0f} |
| Allocation | {_lr_pv_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}% | {_lr_bess_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}% |
| 10-Yr Revenue | \u20ac{_ppa_10y:,.0f} | \u20ac{_bess_10y:,.0f} |
| 10-Yr ROI | {_pv_roi_10y:.0f}% | {_bess_roi_10y:.0f}% |
| Y3 Annual Yield | {_pv_annual_yield:.1f}% | {_bess_annual_yield:.1f}% |
| Asset Life | {_pv_life} years | {_bess_life} years |
| Degradation | {_pv_deg}% p.a. | {_bess_deg_pct}% p.a. |

**Assessment**: {"PV outperforms BESS — current allocation favors PV correctly." if _pv_roi_10y > _bess_roi_10y else "BESS outperforms PV — consider increasing BESS allocation."}
PV has a {_pv_life}-year revenue horizon vs BESS {_bess_life}-year, lower degradation ({_pv_deg}% vs {_bess_deg_pct}%),
and zero input cost. BESS revenue is **highly seasonal** — R{_arb_hd_peak:.2f} peak only {_arb_hd_months} months/year,
R{_arb_ld_peak:.2f} the other {_arb_ld_months} months. Current {_lr_pv_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}/{_lr_bess_budget / (_lr_pv_budget + _lr_bess_budget) * 100:.0f}
split is well-balanced: BESS provides grid independence and peak shaving while PV drives long-term returns.
                        """)

            else:
                st.info("Operations view coming soon")

            # ── Hidden Table: Full Revenue & Cost Breakdown ──
            if _sub_ops_annual:
                with st.expander("Full Revenue & Cost Breakdown (Debug)", expanded=False):
                    _ops_df = pd.DataFrame(_sub_ops_annual)
                    _ops_df.index = [f"Y{i+1}" for i in range(len(_sub_ops_annual))]
                    st.dataframe(_ops_df.T, use_container_width=True)

            # ── AUDIT: Operations ──
            _ops_checks = []
            if _sub_ops_annual:
                for yi, _op in enumerate(_sub_ops_annual):
                    _y = yi + 1
                    _a = _sub_annual[yi]
                    # Revenue components sum to rev_total (NWL-specific)
                    if entity_key == "nwl":
                        _exp_rev = _op.get('rev_sewage', 0) + _op.get('rev_reuse', 0) + _op.get('rev_bulk_services', 0)
                        _ops_checks.append({
                            "name": f"Y{_y}: Rev components = rev_total",
                            "expected": _exp_rev,
                            "actual": _op.get('rev_total', 0),
                        })
                    # EBITDA = rev_total - om - power - rent
                    _exp_ebitda = _op.get('rev_total', 0) - _op.get('om_cost', 0) - _op.get('power_cost', 0) - _op.get('rent_cost', 0)
                    _ops_checks.append({
                        "name": f"Y{_y}: EBITDA = Rev - OM - Pwr - Rent",
                        "expected": _exp_ebitda,
                        "actual": _a['ebitda'],
                    })
                    # Ops rev_total = P&L rev_total
                    _ops_checks.append({
                        "name": f"Y{_y}: Ops rev = P&L rev",
                        "expected": _op.get('rev_total', 0),
                        "actual": _a.get('rev_total', 0),
                    })
            run_page_audit(_ops_checks, f"{name} — Operations")

    # --- P&L ---
    if "P&L" in _tab_map:
        with _tab_map["P&L"]:
            st.header("Profit & Loss")
            if entity_key == "lanred":
                _pl_lr_scenario = _state_str("lanred_scenario", "Greenfield")
                if _pl_lr_scenario == "Brownfield+":
                    st.caption(f"{name} — Annual P&L (EUR) | SA corporate tax: 27% | Scenario: **Brownfield+** (Northlands Portfolio)")
                else:
                    _pl_bess_pct = _state_float("lanred_bess_alloc_pct", 14)
                    st.caption(f"{name} — Annual P&L (EUR) | SA corporate tax: 27% | PV/BESS: {100 - _pl_bess_pct:.0f}/{_pl_bess_pct:.0f}% (set on Assets tab)")
            else:
                st.caption(f"{name} — Annual P&L (EUR) | SA corporate tax: 27%")

            total_rev = sum(a.get('rev_total', 0.0) for a in _sub_annual)
            total_ebitda = sum(a.get('ebitda', 0.0) for a in _sub_annual)
            total_ie = sum(a['ie'] for a in _sub_annual)
            total_pat = sum(a.get('pat', 0.0) for a in _sub_annual)
            _ebitda_margin = (total_ebitda / total_rev * 100.0) if total_rev else 0.0

            _pm1, _pm2, _pm3, _pm4, _pm5 = st.columns(5)
            _pm1.metric("10-Yr Revenue", f"\u20ac{total_rev:,.0f}")
            _pm2.metric("10-Yr EBITDA", f"\u20ac{total_ebitda:,.0f}")
            _pm3.metric("EBITDA Margin", f"{_ebitda_margin:.1f}%")
            _pm4.metric("Finance Costs", f"\u20ac{total_ie:,.0f}")
            _pm5.metric("Net Result", f"\u20ac{total_pat:,.0f}")

            # --- P&L Chart: Revenue (left) vs Costs (right) stacked per year ---
            fig_pnl = go.Figure()

            # Revenue stacks (left bar per year) — all positive, offsetgroup='rev'
            if entity_key == "nwl":
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_sewage', 0) for a in _sub_annual],
                    name='Sewage', marker_color='#2563EB', offsetgroup='rev', legendgroup='Revenue'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_reuse', 0) for a in _sub_annual],
                    name='Re-use', marker_color='#60A5FA', offsetgroup='rev', legendgroup='Revenue'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_bulk_services', 0) for a in _sub_annual],
                    name='Bulk Services', marker_color='#93C5FD', offsetgroup='rev', legendgroup='Revenue'))
            elif entity_key == "lanred":
                if _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
                    fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_total', 0) for a in _sub_annual],
                        name='Northlands PPA Income', marker_color='#10B981', offsetgroup='rev', legendgroup='Revenue'))
                else:
                    fig_pnl.add_trace(go.Bar(x=_years,
                        y=[a.get('rev_ic_nwl', 0) + a.get('rev_smart_city', 0) + a.get('rev_open_market', 0) for a in _sub_annual],
                        name='PPA Sales', marker_color='#3B82F6', offsetgroup='rev', legendgroup='Revenue'))
                    fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_bess_arbitrage', 0) for a in _sub_annual],
                        name='BESS Arbitrage', marker_color='#F59E0B', offsetgroup='rev', legendgroup='Revenue'))
            elif entity_key == "timberworx":
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_lease', 0) for a in _sub_annual],
                    name='CoE Lease', marker_color='#8B5CF6', offsetgroup='rev', legendgroup='Revenue'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_training', 0) for a in _sub_annual],
                    name='Training', marker_color='#10B981', offsetgroup='rev', legendgroup='Revenue'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_timber_sales', 0) for a in _sub_annual],
                    name='Timber Sales', marker_color='#3B82F6', offsetgroup='rev', legendgroup='Revenue'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_coe_sale', 0) for a in _sub_annual],
                    name='CoE Sale', marker_color='#F59E0B', offsetgroup='rev', legendgroup='Revenue'))
            else:
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rev_total', 0) for a in _sub_annual],
                    name='Revenue', marker_color='#2563EB', offsetgroup='rev', legendgroup='Revenue'))

            # Cost stacks (right bar per year) — all positive, offsetgroup='cost'
            fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('om_cost', 0) for a in _sub_annual],
                name='O&M', marker_color='#F59E0B', offsetgroup='cost', legendgroup='Costs'))
            if entity_key == 'nwl':
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('power_cost', 0) for a in _sub_annual],
                    name='Power', marker_color='#FB923C', offsetgroup='cost', legendgroup='Costs'))
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('rent_cost', 0) for a in _sub_annual],
                    name='CoE Rent', marker_color='#A78BFA', offsetgroup='cost', legendgroup='Costs'))
            if entity_key == 'lanred' and _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
                fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('power_cost', 0) for a in _sub_annual],
                    name='COGS (Grid)', marker_color='#FB923C', offsetgroup='cost', legendgroup='Costs'))
            fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('depr', 0) for a in _sub_annual],
                name='Depreciation', marker_color='#94A3B8', offsetgroup='cost', legendgroup='Costs'))
            fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('ie', 0) for a in _sub_annual],
                name='Finance Costs', marker_color='#DC2626', offsetgroup='cost', legendgroup='Costs'))
            fig_pnl.add_trace(go.Bar(x=_years, y=[a.get('tax', 0) for a in _sub_annual],
                name='Tax', marker_color='#7C3AED', offsetgroup='cost', legendgroup='Costs'))

            # Net margin % annotations above the taller bar of each pair
            for i, y_lbl in enumerate(_years):
                _rev_i = _sub_annual[i].get('rev_total', 0)
                _cost_i = (_sub_annual[i].get('om_cost', 0) + _sub_annual[i].get('power_cost', 0)
                    + _sub_annual[i].get('rent_cost', 0)
                    + _sub_annual[i].get('depr', 0) + _sub_annual[i].get('ie', 0)
                    + _sub_annual[i].get('tax', 0))
                _pat_i = _sub_annual[i].get('pat', 0)
                _ratio = _pat_i / _rev_i if _rev_i else 0
                _top = max(_rev_i, _cost_i)
                fig_pnl.add_annotation(
                    x=y_lbl, y=_top * 1.08,
                    text=f"<b>{_ratio:.0%}</b>", showarrow=False,
                    font=dict(size=11, color='#059669' if _ratio >= 0 else '#DC2626'),
                )

            fig_pnl.update_layout(
                barmode='stack', yaxis_title='EUR', height=420,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                bargap=0.20, bargroupgap=0.05,
            )
            st.plotly_chart(fig_pnl, use_container_width=True)

            # --- Transposed P&L table with section headers ---
            _pnl_cols = _years + ['Total']
            _ncols = len(_pnl_cols)
            # Row types: 'section' = header, 'line' = normal, 'sub' = subtotal (*), 'total' = bold (**), 'grand' = bottom line, 'spacer' = gap
            _pnl_rows = []  # list of (label, values, row_type)

            def _pnl_line(label, key, sign=1.0, row_type='line'):
                vals = [sign * a.get(key, 0.0) for a in _sub_annual]
                _pnl_rows.append((label, vals + [sum(vals)], row_type))

            def _pnl_section(label):
                _pnl_rows.append((label, [None] * _ncols, 'section'))

            def _pnl_spacer():
                _pnl_rows.append(('', [None] * _ncols, 'spacer'))

            # REVENUE
            _pnl_section('REVENUE')
            if entity_key == "nwl":
                _pnl_line('GF Sewage', 'rev_greenfield_sewage')
                _pnl_line('BF Sewage (honeysucker)', 'rev_brownfield_sewage')
                _pnl_line('Sewage Revenue', 'rev_sewage', row_type='sub')
                _pnl_line('GF Re-use', 'rev_greenfield_reuse')
                _pnl_line('Construction re-use', 'rev_construction')
                _pnl_line('Agri-water', 'rev_agri')
                _pnl_line('Re-use Revenue', 'rev_reuse', row_type='sub')
            elif entity_key == "lanred":
                if _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
                    _pnl_line('Northlands PPA income', 'rev_total')
                else:
                    _pnl_line('NWL IC power sales', 'rev_ic_nwl')
                    _pnl_line('Smart City off-take', 'rev_smart_city')
                    _pnl_line('Open market sales', 'rev_open_market')
                    _pnl_line('BESS TOU arbitrage', 'rev_bess_arbitrage')
            elif entity_key == "timberworx":
                _pnl_line('CoE Lease income', 'rev_lease')
                _pnl_line('Training programs', 'rev_training')
                _pnl_line('House sales (net of labor)', 'rev_timber_sales')
                _pnl_line('CoE sale to LLC', 'rev_coe_sale')
            _pnl_line('Operating Revenue', 'rev_operating', row_type='total')
            if entity_key == 'nwl':
                _pnl_line('Bulk services', 'rev_bulk_services')
            _pnl_line('Total Revenue', 'rev_total', row_type='total')

            # OPERATING COSTS (entity-specific lines)
            _pnl_spacer()
            _pnl_section('OPERATING COSTS')
            _pnl_line('O&M expense', 'om_cost', -1.0)
            if entity_key == 'nwl':
                _pnl_line('Power / electricity', 'power_cost', -1.0)
                _pnl_line('CoE rent (IC to TWX)', 'rent_cost', -1.0)
            if entity_key == 'lanred' and _state_str("lanred_scenario", "Greenfield") == "Brownfield+":
                _pnl_line('COGS (grid purchases)', 'power_cost', -1.0)
            _pnl_line('EBITDA', 'ebitda', row_type='total')
            _pnl_line('Depreciation', 'depr', -1.0)
            _pnl_line('EBIT', 'ebit', row_type='total')

            # FINANCE COSTS
            _pnl_spacer()
            _pnl_section('FINANCE COSTS')
            _pnl_line('Senior interest', 'ie_sr', -1.0)
            _pnl_line('Mezz interest', 'ie_mz', -1.0)
            _pnl_line('Finance Costs', 'ie', -1.0, row_type='total')

            # FINANCE INCOME
            _pnl_spacer()
            _pnl_section('FINANCE INCOME')
            _pnl_line('DSRA Interest Income (9%)', 'ii_dsra')

            # BOTTOM LINE
            _pnl_spacer()
            _pnl_section('BOTTOM LINE')
            _pnl_line('Profit Before Tax', 'pbt', row_type='total')
            _pnl_line('Tax (27%)', 'tax', -1.0)
            _pnl_line('Net Result', 'pat', row_type='grand')

            # Build styled HTML table
            _fmt = _eur_fmt
            _h = ['<div style="overflow-x:auto;width:100%;">',
                  '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                  '<thead><tr>']
            _h.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _pnl_cols:
                _h.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h.append('</tr></thead><tbody>')

            for label, vals, rtype in _pnl_rows:
                if rtype == 'spacer':
                    _h.append(f'<tr><td colspan="{_ncols + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h.append(f'<tr><td colspan="{_ncols + 1}" style="padding:8px 10px 4px;font-weight:700;'
                              f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                # Style per row type
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                    lbl_style = td_style
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                    lbl_style = td_style
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                    lbl_style = td_style
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                    lbl_style = td_style
                _h.append('<tr>')
                _h.append(f'<td style="text-align:left;padding:4px 10px;{lbl_style}">{label}</td>')
                for v in vals:
                    cell = _fmt.format(v) if v is not None and not isinstance(v, str) else ''
                    _h.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h.append('</tr>')

            _h.append('</tbody></table></div>')
            st.markdown(''.join(_h), unsafe_allow_html=True)

            # ── AUDIT: P&L ──
            _pl_checks = []
            for _a in _sub_annual:
                _y = _a['year']
                _pl_checks.append({
                    "name": f"Y{_y}: Rev - OpEx = EBITDA",
                    "expected": _a.get('rev_total', 0.0) - _a.get('om_cost', 0.0) - _a.get('power_cost', 0.0) - _a.get('rent_cost', 0.0),
                    "actual": _a['ebitda'],
                })
                _pl_checks.append({
                    "name": f"Y{_y}: EBITDA - Depr - IE + II = PBT",
                    "expected": _a['ebitda'] - _a['depr'] - _a['ie'] + _a.get('ii_dsra', 0.0),
                    "actual": _a['pbt'],
                })
                _exp_tax = max(_a['pbt'] * 0.27, 0.0)
                _pl_checks.append({
                    "name": f"Y{_y}: Tax = max(PBT,0) x 27%",
                    "expected": _exp_tax,
                    "actual": _a['tax'],
                })
                _pl_checks.append({
                    "name": f"Y{_y}: PBT - Tax = PAT",
                    "expected": _a['pbt'] - _a['tax'],
                    "actual": _a['pat'],
                })
            _pl_checks.append({
                "name": "10yr total PAT = sum",
                "expected": sum(_a['pat'] for _a in _sub_annual),
                "actual": sum(_a['pat'] for _a in _sub_annual),
            })
            run_page_audit(_pl_checks, f"{name} — P&L")

    # --- CASH FLOW ---
    if "Cash Flow" in _tab_map:
        with _tab_map["Cash Flow"]:
            st.header("Cash Flow")
            st.caption(f"{name} — Full lifecycle: equity, construction, grants, operations, debt service")

            total_ebitda = sum(a['ebitda'] for a in _sub_annual)
            total_ops = sum(a['cf_ops'] for a in _sub_annual)
            total_ds = sum(a['cf_ds'] for a in _sub_annual)
            total_fcf = sum(a['cf_after_debt_service'] for a in _sub_annual)
            total_net = sum(a['cf_net'] for a in _sub_annual)
            dscr_vals = [a['cf_ops'] / a['cf_ds'] if a['cf_ds'] > 0 else None for a in _sub_annual]
            dscr_valid = [d for d in dscr_vals if d is not None]
            avg_dscr = sum(dscr_valid) / len(dscr_valid) if dscr_valid else 0
            dsra_y10 = _sub_annual[-1].get('dsra_bal', 0)

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("10-Yr Cash from Ops", f"€{total_ops:,.0f}")
            with c2:
                st.metric("10-Yr Debt Service", f"€{total_ds:,.0f}")
            with c3:
                st.metric("10-Yr Free CF", f"€{total_fcf:,.0f}")
            with c4:
                st.metric("Avg DSCR", f"{avg_dscr:.2f}x")
            with c5:
                st.metric("DSRA Balance (Y10)", f"€{dsra_y10:,.0f}")

            st.divider()

            # ======================================================
            # CHART 1: Cash from Ops vs Debt Service (DSCR)
            # ======================================================
            st.subheader("1. Cash from Ops vs Debt Service")
            fig_ds = go.Figure()
            # Left bar: Cash from Ops (EBITDA - Tax)
            fig_ds.add_trace(go.Bar(
                x=_years, y=[a['cf_ops'] for a in _sub_annual],
                name='Cash from Ops', marker_color='#10B981',
                offsetgroup='ops', legendgroup='Operations'
            ))
            # Right bar: Debt Service stacked (Interest + Principal)
            fig_ds.add_trace(go.Bar(
                x=_years, y=[a['cf_ie'] for a in _sub_annual],
                name='Interest', marker_color='#EF4444',
                offsetgroup='ds', legendgroup='Debt Service'
            ))
            fig_ds.add_trace(go.Bar(
                x=_years, y=[a['cf_pr'] for a in _sub_annual],
                name='Principal', marker_color='#6366F1',
                offsetgroup='ds', legendgroup='Debt Service'
            ))
            # DSCR annotations on top
            for _ci, _yr in enumerate(_years):
                _ds_val = _sub_annual[_ci]['cf_ds']
                _ops_val = _sub_annual[_ci]['cf_ops']
                _bar_top = max(_ops_val, _ds_val) if (_ops_val > 0 or _ds_val > 0) else 0
                if _ds_val > 0:
                    _dscr = _ops_val / _ds_val
                    fig_ds.add_annotation(
                        x=_yr, y=_bar_top, text=f"<b>{_dscr:.2f}x</b>",
                        showarrow=False, yshift=18,
                        font=dict(size=11, color='#16A34A' if _dscr >= 1.3 else '#DC2626')
                    )
                elif _ops_val > 0:
                    fig_ds.add_annotation(
                        x=_yr, y=_bar_top, text="<b>No DS</b>",
                        showarrow=False, yshift=18, font=dict(size=10, color='#6B7280')
                    )
            fig_ds.update_layout(
                barmode='stack', height=400,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(dtick=1), yaxis_title='EUR',
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_ds, use_container_width=True)
            st.caption("DSCR = Cash from Ops (EBITDA - Tax) / Total Debt Service. Green = above 1.30x covenant, Red = below.")

            # ======================================================
            # CHART 2: Comprehensive Cash Flow (all flows)
            # ======================================================
            st.subheader("2. Comprehensive Cash Flow")
            fig_ccf = go.Figure()
            # Inflows: Equity + Drawdowns + Grants + Revenue (stacked, left)
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_equity', 0) for a in _sub_annual],
                name='Equity Injection', marker_color='#0D9488',
                offsetgroup='in', legendgroup='Inflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_draw', 0) for a in _sub_annual],
                name='IC Loan Drawdowns', marker_color='#2563EB',
                offsetgroup='in', legendgroup='Inflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_grants', 0) for a in _sub_annual],
                name='Grants & Subsidies', marker_color='#8B5CF6',
                offsetgroup='in', legendgroup='Inflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('rev_total', 0) for a in _sub_annual],
                name='Operating Revenue', marker_color='#10B981',
                offsetgroup='in', legendgroup='Inflows'
            ))
            # Outflows: Capex + Prepay + Opex + Tax + Debt Service (stacked, right)
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_capex', 0) for a in _sub_annual],
                name='Capital Expenditure', marker_color='#1E3A5F',
                offsetgroup='out', legendgroup='Outflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_prepay', 0) for a in _sub_annual],
                name='Grant Prepayment', marker_color='#7C3AED',
                offsetgroup='out', legendgroup='Outflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('om_cost', 0) + a.get('power_cost', 0) + a.get('rent_cost', 0) for a in _sub_annual],
                name='Operating Costs', marker_color='#F59E0B',
                offsetgroup='out', legendgroup='Outflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_tax', 0) for a in _sub_annual],
                name='Tax', marker_color='#78716C',
                offsetgroup='out', legendgroup='Outflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_ie', 0) for a in _sub_annual],
                name='Interest Payments', marker_color='#EF4444',
                offsetgroup='out', legendgroup='Outflows'
            ))
            fig_ccf.add_trace(go.Bar(
                x=_years, y=[a.get('cf_pr', 0) for a in _sub_annual],
                name='Principal Repayments', marker_color='#6366F1',
                offsetgroup='out', legendgroup='Outflows'
            ))
            # DSRA balance line
            fig_ccf.add_trace(go.Scatter(
                x=_years, y=[a.get('dsra_bal', 0) for a in _sub_annual],
                name='DSRA Balance', mode='lines+markers',
                line=dict(color='#7C3AED', width=3)
            ))
            fig_ccf.update_layout(
                barmode='stack', height=420,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(dtick=1), yaxis_title='EUR',
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_ccf, use_container_width=True)
            st.caption("Left bars = sources of cash (drawdowns, revenue, grants). Right bars = uses of cash (capex, opex, debt service).")

            # ======================================================
            # CHART 3: DSRA Fixed Deposit — Balance & Interest
            # ======================================================
            st.subheader("3. DSRA Fixed Deposit")
            fig_dsra = go.Figure()
            fig_dsra.add_trace(go.Scatter(
                x=_years, y=[a.get('dsra_bal', 0) for a in _sub_annual],
                name='DSRA Balance', fill='tozeroy',
                line=dict(color='#7C3AED', width=2),
                fillcolor='rgba(124,58,237,0.15)'
            ))
            fig_dsra.add_trace(go.Bar(
                x=_years, y=[a.get('dsra_interest', 0) for a in _sub_annual],
                name='Interest Earned (9%)', marker_color='#10B981',
                yaxis='y2'
            ))
            fig_dsra.update_layout(
                height=380,
                margin=dict(l=10, r=60, t=40, b=10),
                xaxis=dict(dtick=1),
                yaxis=dict(title='DSRA Balance (EUR)', side='left'),
                yaxis2=dict(title='Interest Earned (EUR)', side='right', overlaying='y', showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_dsra, use_container_width=True)
            st.caption("DSRA Fixed Deposit: surplus cash deposited at 9% p.a. Opening + Deposit + Interest = Closing.")

            st.divider()

            # ======================================================
            # CASH FLOW TABLE — Full lifecycle
            # ======================================================
            st.subheader("Cash Flow Statement")
            _cf_cols = _years + ['Total']
            _ncols_cf = len(_cf_cols)
            _cf_rows = []

            def _cf_line(label, key, sign=1.0, row_type='line', point_in_time=False):
                vals = [sign * a.get(key, 0.0) for a in _sub_annual]
                total = vals[-1] if point_in_time else sum(vals)
                _cf_rows.append((label, vals + [total], row_type))

            def _cf_computed(label, vals_list, row_type='line'):
                _cf_rows.append((label, vals_list + [sum(vals_list)], row_type))

            def _cf_section(label):
                _cf_rows.append((label, [None] * _ncols_cf, 'section'))

            def _cf_spacer():
                _cf_rows.append(('', [None] * _ncols_cf, 'spacer'))

            # --- OPERATING CASH FLOW ---
            _cf_section('OPERATING CASH FLOW')
            _cf_line('EBITDA', 'ebitda')
            _cf_line('DSRA Interest Income', 'ii_dsra')
            _cf_line('Tax', 'cf_tax', -1.0)
            _cf_line('Cash from Operations', 'cf_ops', row_type='total')
            _cf_spacer()

            # --- CONSTRUCTION ---
            _cf_section('CONSTRUCTION')
            _cf_line('IC Loan Drawdowns', 'cf_draw')
            _cf_line('Capital Expenditure', 'cf_capex', -1.0)
            _cf_computed('Net Construction',
                         [a.get('cf_draw', 0) - a.get('cf_capex', 0) for a in _sub_annual], row_type='sub')
            _cf_spacer()

            # --- GRANTS & EQUITY ---
            _cf_section('GRANTS & EQUITY')
            _cf_line('Shareholder Equity', 'cf_equity')
            _cf_line('DTIC Grant', 'cf_grant_dtic')
            _cf_line('IIC Technical Assistance', 'cf_grant_iic')
            _cf_line('Total Grants', 'cf_grants', row_type='sub')
            _cf_spacer()

            # --- IC LOAN PREPAYMENTS ---
            _cf_section('IC LOAN PREPAYMENTS (Grant-funded)')
            _cf_line('From DTIC Grant', 'cf_prepay_dtic', -1.0)
            _cf_line('From Bulk Services (GEPF)', 'cf_prepay_gepf', -1.0)
            _cf_line('Total Prepayment', 'cf_prepay', -1.0, row_type='sub')
            _cf_computed('Net Grants & Equity',
                         [a.get('cf_equity', 0) + a.get('cf_grants', 0) - a.get('cf_prepay', 0) for a in _sub_annual], row_type='sub')
            _cf_spacer()

            # --- DEBT SERVICE ---
            _cf_section('DEBT SERVICE')
            _cf_line('Senior interest', 'cf_ie_sr', -1.0)
            _cf_line('Mezz interest', 'cf_ie_mz', -1.0)
            _cf_line('Total Interest', 'cf_ie', -1.0, row_type='sub')
            _cf_line('Senior principal', 'cf_pr_sr', -1.0)
            _cf_line('Mezz principal', 'cf_pr_mz', -1.0)
            _cf_line('Total Principal', 'cf_pr', -1.0, row_type='sub')
            _cf_line('Total Debt Service', 'cf_ds', -1.0, row_type='total')
            _cf_spacer()

            # --- NET CASH FLOW ---
            _cf_section('NET CASH FLOW')
            _cf_line('Free CF (Ops − DS)', 'cf_after_debt_service', row_type='total')
            _cf_line('Period Cash Flow', 'cf_net', row_type='total')
            _cf_computed('→ to DSRA Fixed Deposit',
                         [-a.get('cf_net', 0) for a in _sub_annual], row_type='sub')
            _cf_spacer()

            # --- DSRA FIXED DEPOSIT ---
            _cf_section('DSRA FIXED DEPOSIT')
            _cf_line('Opening Balance', 'dsra_opening', point_in_time=True)
            _cf_line('Deposit (Net CF)', 'dsra_deposit')
            _cf_line('Interest Earned (9%)', 'dsra_interest')
            _cf_line('Closing Balance', 'dsra_bal', row_type='grand', point_in_time=True)
            _cf_spacer()

            # --- COVERAGE ---
            _cf_section('COVERAGE')
            dscr_display = []
            for a in _sub_annual:
                if a['cf_ds'] > 0:
                    dscr_display.append(f"{a['cf_ops'] / a['cf_ds']:.2f}x")
                else:
                    dscr_display.append('n/a')
            avg_dscr_str = f"{avg_dscr:.2f}x" if dscr_valid else 'n/a'
            _cf_rows.append(('DSCR (Ops CF / Debt Service)', dscr_display + [avg_dscr_str], 'line'))

            # Build styled HTML table
            _fmt = _eur_fmt
            _h = ['<div style="overflow-x:auto;width:100%;">',
                  '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                  '<thead><tr>']
            _h.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _cf_cols:
                _h.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h.append('</tr></thead><tbody>')

            for label, vals, rtype in _cf_rows:
                if rtype == 'spacer':
                    _h.append(f'<tr><td colspan="{_ncols_cf + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h.append(f'<tr><td colspan="{_ncols_cf + 1}" style="padding:8px 10px 4px;font-weight:700;'
                              f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                _h.append('<tr>')
                _h.append(f'<td style="text-align:left;padding:4px 10px;{td_style}">{label}</td>')
                for v in vals:
                    if isinstance(v, str):
                        cell = v
                    elif v is not None:
                        cell = _fmt.format(v)
                    else:
                        cell = ''
                    _h.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h.append('</tr>')

            _h.append('</tbody></table></div>')
            st.markdown(''.join(_h), unsafe_allow_html=True)

            # ── AUDIT: Cash Flow ──
            _cf_checks = []
            for _a in _sub_annual:
                _y = _a['year']
                # DSRA identity: Opening + Deposit + Interest = Closing
                _cf_checks.append({
                    "name": f"Y{_y}: DSRA Open+Dep+Int = Close",
                    "expected": _a['dsra_opening'] + _a['dsra_deposit'] + _a['dsra_interest'],
                    "actual": _a['dsra_bal'],
                })
                # CF Ops = EBITDA + DSRA Interest - Tax
                _cf_checks.append({
                    "name": f"Y{_y}: CF Ops = EBITDA + II - Tax",
                    "expected": _a['ebitda'] + _a.get('ii_dsra', 0.0) - _a['cf_tax'],
                    "actual": _a['cf_ops'],
                })
                # Comprehensive CF Net
                _exp_net = (_a['cf_equity']
                            + _a['cf_draw'] - _a['cf_capex']
                            + _a['cf_grants'] - _a['cf_prepay']
                            + _a['cf_ops']
                            - _a['cf_ie'] - _a['cf_pr'])
                _cf_checks.append({
                    "name": f"Y{_y}: CF Net = components",
                    "expected": _exp_net,
                    "actual": _a['cf_net'],
                })
            # Sum(CF Net) = DSRA Y10 balance
            _cf_checks.append({
                "name": "Sum(CF Net) = DSRA Y10 bal",
                "expected": sum(_a['cf_net'] for _a in _sub_annual),
                "actual": _sub_annual[-1]['dsra_bal'],
            })
            run_page_audit(_cf_checks, f"{name} — Cash Flow")

    # --- DEBT SCULPTING ---
    if "Debt Sculpting" in _tab_map:
        with _tab_map["Debt Sculpting"]:
            st.header(f"{name} — Debt Sculpting")

            # NWL-specific: rich debt sculpting view
            if entity_key == 'nwl':
                # ── Shared data ──
                _ds_fin = financing
                _ds_struct = structure
                _ds_prepays = _ds_fin.get('prepayments', {})
                _ds_sr_detail = _ds_fin['loan_detail']['senior']
                _ds_nwl_sr_ic = entity_data['senior_portion']
                _ds_nwl_mz_ic = entity_data['mezz_portion']
                _ds_nwl_total_ic = _ds_nwl_sr_ic + _ds_nwl_mz_ic
                _ds_sr_rate = _ds_struct['sources']['senior_debt']['interest']['rate']
                _ds_mz_rate = _ds_struct['sources']['mezzanine']['interest']['total_rate']

                # Grants
                _dtic = _ds_prepays.get('dtic_grant', {})
                _gepf = _ds_prepays.get('gepf_bulk_services', {})
                _dtic_eur = _dtic.get('amount_eur', 0)
                _gepf_eur = _gepf.get('amount_eur', 0)
                _total_grants = _dtic_eur + _gepf_eur

                # NWL IC balance at M24 (after IDC, after grant prepayment)
                _nwl_sr_opening = 0.0
                for _r in _sub_sr_schedule:
                    if _r['Month'] >= 24:
                        _nwl_sr_opening = _r.get('Opening', 0)
                        break
                _nwl_mz_opening = 0.0
                for _r in _sub_mz_schedule:
                    if _r['Month'] >= 24:
                        _nwl_mz_opening = _r.get('Opening', 0)
                        break

                # M24 and M30 Senior IC P+I — always use NO-DSRA schedule
                # (swap delivers full P+I; DSRA/FEC covers same amounts)
                _sr_cfg = structure['sources']['senior_debt']
                _sr_det = financing['loan_detail']['senior']
                _sr_total = sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
                _nwl_sr_principal = structure['uses']['loans_to_subsidiaries']['nwl']['senior_portion']
                _nwl_prepay_pct = _sr_det.get('prepayment_allocation', {}).get('nwl', 0.0)
                _nwl_prepays = {k: v * _nwl_prepay_pct for k, v in _sr_det.get('prepayment_periods', {}).items()} if _nwl_prepay_pct > 0 else None
                _nwl_sr_no_dsra = build_simple_ic_schedule(
                    _nwl_sr_principal, _sr_total,
                    _sr_cfg['repayments'],
                    _sr_cfg['interest']['rate'] + INTERCOMPANY_MARGIN,
                    _sr_det['drawdown_schedule'], [-4, -3, -2, -1],
                    _nwl_prepays, dsra_amount=0.0)
                # Also build no-DSRA Mezz schedule (for swap scenario — no DSRA injection)
                _mz_cfg = structure['sources']['mezzanine']
                _mz_total = sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
                _nwl_mz_principal = structure['uses']['loans_to_subsidiaries']['nwl']['mezz_portion']
                _nwl_mz_no_dsra = build_simple_ic_schedule(
                    _nwl_mz_principal, _mz_total,
                    _mz_cfg.get('repayments', 10),
                    _mz_cfg['interest']['total_rate'] + INTERCOMPANY_MARGIN,
                    [_mz_cfg['amount_eur'], 0, 0, 0], [-4, -3, -2, -1],
                    dsra_drawdown=0.0)
                _ds_eur_m24 = 0.0
                _ds_eur_m30 = 0.0
                for _r in _nwl_sr_no_dsra:
                    if _r['Month'] == 24:
                        _ds_eur_m24 = _r['Interest'] + abs(_r.get('Principle', 0))
                    elif _r['Month'] == 30:
                        _ds_eur_m30 = _r['Interest'] + abs(_r.get('Principle', 0))
                _ds_dsra_amount = _ds_eur_m24 + _ds_eur_m30

                # ════════════════════════════════════════════════════
                # Section 1: Specials — DTIC + GEPF Bulk Services
                # ════════════════════════════════════════════════════
                st.subheader("1. Grant Prepayments (Specials)")
                st.markdown(f"""
NWL benefits from **two grant-funded prepayments** that reduce Senior IC exposure before cash flows start:
""")
                _sp_c1, _sp_c2 = st.columns(2)
                with _sp_c1:
                    with st.container(border=True):
                        st.markdown(f"**{_dtic.get('name', 'DTIC Grant')}**")
                        st.metric("Amount", f"€{_dtic_eur:,.0f}")
                        st.caption(f"R{_dtic.get('amount_zar', 0):,.0f} | Status: {_dtic.get('status', 'TBC')}")
                        st.markdown("Manufacturing incentive from the Department of Trade, Industry & Competition. "
                                    "Applied as prepayment at **M12** (Period -2), reducing NWL Senior IC principal.")
                with _sp_c2:
                    with st.container(border=True):
                        st.markdown(f"**{_gepf.get('name', 'GEPF Bulk Services')}**")
                        st.metric("Amount", f"€{_gepf_eur:,.0f}")
                        st.caption(f"R{_gepf.get('total_zar', 0):,.0f} | Timing: {_gepf.get('timing', 'COD')}")
                        st.markdown("Government Employees Pension Fund bulk services contribution for water infrastructure. "
                                    "Applied at **M12**, further reducing NWL Senior IC principal before repayment starts.")

                st.markdown(f"""
**Combined effect:** €{_total_grants:,.0f} prepaid at M12 → NWL Senior IC balance reduced from
€{_ds_nwl_sr_ic:,.0f} to **€{_nwl_sr_opening:,.0f}** at M24 (after IDC capitalisation).
""")
                st.divider()

                # ════════════════════════════════════════════════════
                # Section 2: Hedging — DSRA→FEC vs Swap (side by side)
                # ════════════════════════════════════════════════════
                st.subheader("2. Pre-Revenue Hedging (M24–M30)")
                _ds_nwl_hedge = st.session_state.get("sclca_nwl_hedge", "CC DSRA → FEC")
                _ds_swap_active = (_ds_nwl_hedge == "Cross-Currency Swap")

                st.radio(
                    "Select hedging mechanism",
                    ["CC DSRA → FEC", "Cross-Currency Swap"],
                    key="_ds_nwl_hedge_entity",
                    horizontal=True,
                    index=1 if _ds_swap_active else 0,
                    on_change=lambda: st.session_state.update(
                        sclca_nwl_hedge=st.session_state.get("_ds_nwl_hedge_entity", "CC DSRA → FEC")),
                )
                _ds_swap_active = st.session_state.get("_ds_nwl_hedge_entity", _ds_nwl_hedge) == "Cross-Currency Swap"

                # Muted colors for inactive diagrams
                _fec_cc = "#7C3AED" if not _ds_swap_active else "#9CA3AF"
                _fec_dsra = "#0D9488" if not _ds_swap_active else "#9CA3AF"
                _fec_fec = "#F59E0B" if not _ds_swap_active else "#D1D5DB"
                _fec_iic = "#1E3A5F" if not _ds_swap_active else "#9CA3AF"
                _fec_fc = "white" if not _ds_swap_active else "#6B7280"
                _fec_fc2 = "#1a1a1a" if not _ds_swap_active else "#6B7280"
                _fec_edge = "#64748B" if not _ds_swap_active else "#D1D5DB"

                _sw_eur = "#F59E0B" if _ds_swap_active else "#D1D5DB"
                _sw_sr = "#1E3A5F" if _ds_swap_active else "#9CA3AF"
                _sw_mz = "#7C3AED" if _ds_swap_active else "#9CA3AF"
                _sw_gn = "#059669" if _ds_swap_active else "#9CA3AF"
                _sw_fc = "white" if _ds_swap_active else "#6B7280"
                _sw_fc2 = "#1a1a1a" if _ds_swap_active else "#6B7280"
                _sw_edge = "#64748B" if _ds_swap_active else "#D1D5DB"

                # Compute swap schedule (needed by both panels for sizing)
                _ds_swap_amt = _ds_eur_m24 + _ds_eur_m30
                _ds_last_sr_m = max(
                    (r['Month'] for r in _nwl_sr_no_dsra
                     if r['Month'] >= 24 and abs(r.get('Principle', 0)) > 0),
                    default=102)
                _ds_swap_sched = _build_nwl_swap_schedule(_ds_swap_amt, FX_RATE, last_sr_month=_ds_last_sr_m)
                _ds_zar_start = _ds_swap_sched['start_month'] if _ds_swap_sched else 36
                _ds_zar_end = _ds_zar_start + (_ds_swap_sched['tenor'] - 1) * 6 if _ds_swap_sched else 102

                # Muted colors for inactive charts
                _sw_txt_clr = None if _ds_swap_active else "#D1D5DB"
                _fec_txt_clr = None if not _ds_swap_active else "#D1D5DB"

                # Build full M0-M102 timeline (every 6 months)
                _all_months = list(range(0, 108, 6))  # M0, M6, M12, ..., M102

                # EUR leg: M0 = -notional (red, outflow), M24/M30 = +P+I (green, inflow)
                _eur_pi_map = {0: -_ds_swap_amt, 24: _ds_eur_m24, 30: _ds_eur_m30}
                # ZAR leg: M0 = +draw (green, we receive ZAR), M36+ = -repayments (red, we pay ZAR)
                _zar_total = _ds_swap_sched['zar_amount'] if _ds_swap_sched else 0
                _zar_tenor = _ds_swap_sched['tenor'] if _ds_swap_sched else 12
                _zar_per_period = _zar_total / _zar_tenor if _zar_tenor > 0 else 0
                _zar_pi_map = {0: _zar_total}
                for _zi in range(_zar_tenor):
                    _zar_pi_map[_ds_zar_start + _zi * 6] = -_zar_per_period

                _h_c1, _h_c2 = st.columns(2)

                # ── LEFT: FEC (DSRA) ──
                with _h_c1:
                    with st.container(border=True):
                        if not _ds_swap_active:
                            st.success("**ACTIVE** — CC DSRA → FEC")
                        else:
                            st.error("**INACTIVE** — CC DSRA → FEC")

                        st.metric("DSRA Size", f"€{_ds_dsra_amount:,.0f}",
                                  delta=f"M24: €{_ds_eur_m24:,.0f} + M30: €{_ds_eur_m30:,.0f}")

                        st.markdown(
                            f'<div style="opacity:{1.0 if not _ds_swap_active else 0.35}; text-align:center; '
                            f'font-size:18px; line-height:2.6; padding:18px 0;">'
                            f'<span style="background:{_fec_cc};color:white;padding:8px 16px;border-radius:8px;font-weight:600;">CC injects 2×P+I</span>'
                            f'<br>↓<br>'
                            f'<span style="background:{_fec_dsra};color:white;padding:8px 16px;border-radius:8px;font-weight:600;">SCLCA DSRA</span>'
                            f'<br>↓<br>'
                            f'<span style="background:{_fec_fec};color:#1a1a1a;padding:8px 16px;border-radius:8px;font-weight:600;">FEC (Investec)</span>'
                            f'<br>↓<br>'
                            f'<span style="background:{_fec_iic};color:white;padding:8px 16px;border-radius:8px;font-weight:600;">IIC Senior P+I (M24 + M30)</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        st.markdown(f"""
- CC injects **€{_ds_dsra_amount:,.0f}** into SCLCA DSRA at M24
- DSRA purchases FEC to hedge EUR delivery at M24 + M30
- FEC delivers EUR to pay IIC Senior P+I
- **Cost**: 14.75% (CC rate) + 5.25% (dividend accrual) = **20% effective**
- NWL Mezz IC increases by injection amount
""")

                # ── RIGHT: Cross-Currency Swap ──
                with _h_c2:
                    with st.container(border=True):
                        if _ds_swap_active:
                            st.success("**ACTIVE** — Cross-Currency Swap")
                        else:
                            st.error("**INACTIVE** — Cross-Currency Swap")

                        st.metric("Swap Notional", f"€{_ds_swap_amt:,.0f}",
                                  delta=f"M24: €{_ds_eur_m24:,.0f} + M30: €{_ds_eur_m30:,.0f}")

                        # EUR Leg — full M0-M102 timeline (all months, zeros shown empty)
                        st.markdown("**EUR Leg (Financial Asset)**")
                        _eur_gn = "#059669" if _ds_swap_active else "#D1D5DB"
                        _eur_rd = "#EF4444" if _ds_swap_active else "#D1D5DB"
                        _eur_labels = [f"M{_m}" for _m in _all_months]
                        _eur_vals = [_eur_pi_map.get(_m, 0) for _m in _all_months]
                        _eur_colors_list = [_eur_rd if v < -0.01 else _eur_gn if v > 0.01 else "rgba(0,0,0,0)" for v in _eur_vals]
                        _eur_texts = [f"€{abs(v):,.0f}" if abs(v) > 0.01 else "" for v in _eur_vals]
                        _fig_eur = go.Figure(go.Bar(
                            x=_eur_labels, y=_eur_vals,
                            marker_color=_eur_colors_list,
                            text=_eur_texts,
                            textposition="outside", textfont=dict(size=8, color=_sw_txt_clr),
                        ))
                        _fig_eur.update_layout(
                            height=220, margin=dict(l=10, r=10, t=30, b=30),
                            yaxis=dict(title="EUR", zeroline=True, zerolinecolor="#94A3B8", zerolinewidth=2, showgrid=False),
                            xaxis=dict(showgrid=False, tickangle=-45, dtick=1),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            title=dict(text="EUR Leg Cash Flows", font=dict(size=11)),
                        )
                        st.plotly_chart(_fig_eur, use_container_width=True, key="eur_leg_timeline")

                        # ZAR Leg — full M0-M102 timeline (all months, zeros shown empty)
                        st.markdown("**ZAR Leg (Liability)**")
                        _zar_gn = "#059669" if _ds_swap_active else "#D1D5DB"
                        _zar_rd = "#EF4444" if _ds_swap_active else "#D1D5DB"
                        _zar_labels = [f"M{_m}" for _m in _all_months]
                        _zar_vals_list = [_zar_pi_map.get(_m, 0) for _m in _all_months]
                        _zar_colors_list = [_zar_rd if v < -0.01 else _zar_gn if v > 0.01 else "rgba(0,0,0,0)" for v in _zar_vals_list]
                        _zar_texts = [f"R{abs(v):,.0f}" if abs(v) > 0.01 else "" for v in _zar_vals_list]
                        _fig_zar = go.Figure(go.Bar(
                            x=_zar_labels, y=_zar_vals_list,
                            marker_color=_zar_colors_list,
                            text=_zar_texts,
                            textposition="outside", textfont=dict(size=7, color=_sw_txt_clr),
                        ))
                        _fig_zar.update_layout(
                            height=220, margin=dict(l=10, r=10, t=30, b=30),
                            yaxis=dict(title="ZAR", zeroline=True, zerolinecolor="#94A3B8", zerolinewidth=2, showgrid=False),
                            xaxis=dict(showgrid=False, tickangle=-45, dtick=1),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            title=dict(text="ZAR Leg Cash Flows", font=dict(size=11)),
                        )
                        st.plotly_chart(_fig_zar, use_container_width=True, key="zar_leg_timeline")

                        st.markdown("**Cost**: 11.75% — below Mezz (14.75%), no dividend accrual. "
                                    "Paid contractually on schedule, or accelerated from NWL surplus (P2 priority).")

                st.divider()

                # ════════════════════════════════════════════════════
                # Section 3: One-Time Dividend (CC IRR top-up)
                # ════════════════════════════════════════════════════
                st.subheader("3. One-Time Dividend")
                _ds_cc_cfg = load_config("waterfall").get("cc_irr", {})
                _ds_cc_gap = _ds_cc_cfg.get("gap", 0.0525)
                _ds_cc_target = _ds_cc_cfg.get("target", 0.20)
                _ds_cc_contract = _ds_cc_cfg.get("contractual", 0.1475)
                st.markdown(f"""
Creation Capital's target IRR is **{_ds_cc_target:.0%}**, but the contractual Mezz rate is only **{_ds_cc_contract:.2%}**.
The gap of **{_ds_cc_gap:.2%}** accrues annually on the CC opening balance as a deferred dividend obligation.

When CC's principal is fully repaid (Mezz IC = 0), SCLCA pays the accumulated dividend as a **one-time slug**.
This ensures CC achieves its target return without increasing the contractual rate.
""")

                # --- Dividend accrual graph (NWL contribution) ---
                # Use correct schedules based on hedging mode:
                # FEC active → _sub_sr/mz_schedule (has DSRA), no swap
                # Swap active → no-DSRA schedules, with swap
                if _ds_swap_active:
                    _div_sr_sched = _nwl_sr_no_dsra
                    _div_mz_sched = _nwl_mz_no_dsra
                    _div_swap = _ds_swap_sched
                else:
                    _div_sr_sched = _sub_sr_schedule
                    _div_mz_sched = _sub_mz_schedule
                    _div_swap = None
                _ent_wf_div = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _div_sr_sched, _div_mz_sched,
                    nwl_swap_schedule=_div_swap)
                # Mezz IC opening for Y1 — from selected schedule
                _div_mz_opening = 0.0
                for _r in _div_mz_sched:
                    if _r['Month'] >= 24:
                        _div_mz_opening = _r.get('Opening', 0)
                        break
                _div_mz_closing = []
                _div_accrual = []
                _div_cum = []
                _div_slug_yr = None
                _cum = 0.0
                _slug_paid = False
                _mz_prev_close = _div_mz_opening
                for _yi_d in range(10):
                    _mz_close = _ent_wf_div[_yi_d].get('mz_ic_bal', 0)
                    _div_mz_closing.append(_mz_close)
                    if _slug_paid:
                        _div_accrual.append(0.0)
                        _div_cum.append(0.0)
                    else:
                        # Accrual on opening balance (= previous year's closing)
                        _acc = _mz_prev_close * _ds_cc_gap if _mz_prev_close > 0.01 else 0.0
                        _div_accrual.append(_acc)
                        _cum += _acc
                        _div_cum.append(_cum)
                        if _mz_close <= 0.01:
                            _div_slug_yr = _yi_d
                            _slug_paid = True
                    _mz_prev_close = _mz_close

                _div_years = [f"Y{yi+1}" for yi in range(10)]
                _fig_div = go.Figure()
                _fig_div.add_trace(go.Scatter(
                    x=_div_years, y=_div_mz_closing,
                    mode='lines+markers', name='NWL Mezz IC Balance',
                    line=dict(color='#7C3AED', width=2),
                    yaxis='y',
                ))
                _fig_div.add_trace(go.Bar(
                    x=_div_years, y=_div_accrual,
                    name=f'Dividend Accrual ({_ds_cc_gap:.2%})',
                    marker_color='#F59E0B', opacity=0.7,
                    yaxis='y',
                ))
                _fig_div.add_trace(go.Scatter(
                    x=_div_years, y=_div_cum,
                    mode='lines+markers', name='Cumulative Dividend',
                    line=dict(color='#EF4444', width=2, dash='dot'),
                    yaxis='y',
                ))
                if _div_slug_yr is not None:
                    _fig_div.add_vline(x=_div_slug_yr, line_dash="dash", line_color="#059669", line_width=2)
                    _fig_div.add_annotation(
                        x=_div_slug_yr, y=_div_cum[_div_slug_yr] if _div_slug_yr < len(_div_cum) else 0,
                        text=f"<b>Slug Paid</b><br>€{_div_cum[_div_slug_yr]:,.0f}" if _div_slug_yr < len(_div_cum) else "<b>Slug Paid</b>",
                        showarrow=True, arrowhead=2, ax=40, ay=-40,
                        font=dict(size=10, color="#059669"),
                        bordercolor="#059669", borderwidth=1, bgcolor="white",
                    )
                _fig_div.update_layout(
                    height=350, barmode='overlay',
                    title='One-Time Dividend — NWL Contribution',
                    yaxis=dict(title='EUR', showgrid=True, gridcolor='#E2E8F0'),
                    xaxis=dict(showgrid=False),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(_fig_div, use_container_width=True, key="div_accrual_graph")

                st.divider()

                # ════════════════════════════════════════════════════
                # Section 4: Entity Cascade Waterfall
                # ════════════════════════════════════════════════════
                st.subheader("4. Entity Cascade")
                st.caption("Surplus allocation after IC debt service")

                _render_entity_cascade_diagram(
                    name,
                    show_swap=_ds_swap_active,
                    show_od_lend=True,
                )

                st.markdown(f"""
After contractual IC debt service (Senior + Mezz), **{name}** allocates surplus in priority order:
1. **Ops Reserve FD** — 100% of annual operating costs
2. **OpCo DSRA** — 1× next Senior IC P+I
3. **LanRED Overdraft** — lending to cover LanRED early-year deficits
4. **Mezz IC Acceleration** (15.25%) — highest-rate debt first
{'5. **ZAR Rand Leg** (11.75%) — swap liability repayment' if _ds_swap_active else ''}
{'6' if _ds_swap_active else '5'}. **Senior IC Acceleration** (5.20%)
{'7' if _ds_swap_active else '6'}. **Entity FD** — retained locally after both IC loans repaid
""")

                # Compute entity waterfall
                _ent_wf = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _sub_sr_schedule, _sub_mz_schedule)
                _ds_years = [f"Y{yi+1}" for yi in range(10)]

                with st.expander("Full Cascade Detail", expanded=False):
                    _ds_rows = {}
                    for _row_label, _row_key in [
                        ('EBITDA', 'ebitda'), ('Tax', 'tax'),
                        ('IC Senior P+I', 'sr_pi'), ('IC Mezz P+I', 'mz_pi'),
                        ('Ops Reserve Fill', 'ops_reserve_fill'),
                        ('OpCo DSRA Fill', 'opco_dsra_fill'),
                        ('Mezz IC Acceleration', 'mz_accel_entity'),
                        ('Sr IC Acceleration', 'sr_accel_entity'),
                        ('Entity FD Fill', 'entity_fd_fill'),
                    ]:
                        _ds_rows[_row_label] = [
                            _eur_fmt.format(_ent_wf[yi].get(_row_key, 0))
                            if abs(_ent_wf[yi].get(_row_key, 0)) > 0.5 else '—'
                            for yi in range(10)]
                    st.dataframe(pd.DataFrame(_ds_rows, index=_ds_years).T, use_container_width=True)

                    st.markdown("**Balances**")
                    _ds_bal_rows = {}
                    for _row_label, _row_key in [
                        ('Ops Reserve Bal', 'ops_reserve_bal'),
                        ('OpCo DSRA Bal', 'opco_dsra_bal'),
                        ('Mezz IC Bal', 'mz_ic_bal'),
                        ('Senior IC Bal', 'sr_ic_bal'),
                        ('Entity FD Bal', 'entity_fd_bal'),
                    ]:
                        _ds_bal_rows[_row_label] = [
                            _eur_fmt.format(_ent_wf[yi].get(_row_key, 0))
                            for yi in range(10)]
                    st.dataframe(pd.DataFrame(_ds_bal_rows, index=_ds_years).T, use_container_width=True)

                # Stacked bar chart — Cascade allocation
                fig_ds = go.Figure()
                _ds_colors = [
                    ('IC Senior P+I', 'sr_pi', '#1E3A5F'),
                    ('IC Mezz P+I', 'mz_pi', '#7C3AED'),
                    ('Ops Reserve', 'ops_reserve_fill', '#0D9488'),
                    ('OpCo DSRA', 'opco_dsra_fill', '#2563EB'),
                    ('Mezz IC Accel', 'mz_accel_entity', '#A855F7'),
                    ('Sr IC Accel', 'sr_accel_entity', '#3B82F6'),
                    ('Entity FD', 'entity_fd_fill', '#059669'),
                    ('Free Surplus', 'free_surplus', '#94A3B8'),
                ]
                for _lbl, _fld, _clr in _ds_colors:
                    _vs = [_ent_wf[yi].get(_fld, 0) for yi in range(10)]
                    if any(v > 0 for v in _vs):
                        fig_ds.add_trace(go.Bar(x=_ds_years, y=_vs, name=_lbl, marker_color=_clr))
                _ds_deficits = [_ent_wf[yi].get('deficit', 0) for yi in range(10)]
                if any(d < 0 for d in _ds_deficits):
                    fig_ds.add_trace(go.Bar(x=_ds_years, y=_ds_deficits, name='Deficit', marker_color='#EF4444'))
                # EBITDA line — shows total available before allocation
                _ds_ebitda = [_ent_wf[yi].get('ebitda', 0) for yi in range(10)]
                fig_ds.add_trace(go.Scatter(
                    x=_ds_years, y=_ds_ebitda,
                    mode='lines+markers', name='EBITDA',
                    line=dict(color='#059669', width=2, dash='dot'),
                    marker=dict(size=6),
                ))
                fig_ds.update_layout(
                    barmode='stack', title=f'{name} — Cascade Allocation',
                    yaxis_title='EUR', height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_ds, use_container_width=True)

                st.divider()

                # ════════════════════════════════════════════════════
                # Section 5: Balance Trajectories
                # ════════════════════════════════════════════════════
                st.subheader("5. Balance Trajectories")
                st.caption("OpCo DSRA declines as consumed, Ops Reserve fills, surplus flows to holding via 2-pipe")

                _dsra_bals = [_ent_wf[yi].get('opco_dsra_bal', 0) for yi in range(10)]
                _opsres_bals = [_ent_wf[yi].get('ops_reserve_bal', 0) for yi in range(10)]
                _fd_bals = [_ent_wf[yi].get('entity_fd_bal', 0) for yi in range(10)]
                _od_bals = [_ent_wf[yi].get('od_bal', 0) for yi in range(10)]
                _surplus_to_holding = [
                    _ent_wf[yi].get('sr_pi', 0) + _ent_wf[yi].get('mz_pi', 0)
                    + _ent_wf[yi].get('mz_accel_entity', 0) + _ent_wf[yi].get('sr_accel_entity', 0)
                    for yi in range(10)]

                # Find year when IC fully repaid (DSRA releases to FD)
                _ic_repaid_yr = None
                for _yi_r in range(10):
                    if _ent_wf[_yi_r].get('mz_ic_bal', 1) <= 0.01 and _ent_wf[_yi_r].get('sr_ic_bal', 1) <= 0.01:
                        _ic_repaid_yr = _yi_r
                        break

                fig_bal = go.Figure()
                fig_bal.add_trace(go.Scatter(
                    x=_ds_years, y=_dsra_bals,
                    name='OpCo DSRA (declining)', mode='lines+markers',
                    line=dict(color='#2563EB', width=2.5)))
                fig_bal.add_trace(go.Scatter(
                    x=_ds_years, y=_opsres_bals,
                    name='Ops Reserve (filling)', mode='lines+markers',
                    line=dict(color='#0D9488', width=2)))
                fig_bal.add_trace(go.Scatter(
                    x=_ds_years, y=_fd_bals,
                    name='Entity FD (grows after repaid)', mode='lines+markers',
                    line=dict(color='#059669', width=3)))
                if any(v > 0 for v in _od_bals):
                    fig_bal.add_trace(go.Scatter(
                        x=_ds_years, y=_od_bals,
                        name='OD Balance', mode='lines+markers',
                        line=dict(color='#F59E0B', width=2, dash='dash')))
                fig_bal.add_trace(go.Bar(
                    x=_ds_years, y=_surplus_to_holding,
                    name='→ Holding (via pipe)', marker_color='rgba(30,58,95,0.2)',
                    marker_line_color='#1E3A5F', marker_line_width=1))

                # Mark the IC repaid moment
                if _ic_repaid_yr is not None:
                    _repaid_label = _ds_years[_ic_repaid_yr]
                    fig_bal.add_vline(x=_ic_repaid_yr, line_dash="dot", line_color="#EF4444", line_width=2)
                    fig_bal.add_annotation(
                        x=_repaid_label, y=max(_fd_bals[_ic_repaid_yr], _dsra_bals[max(_ic_repaid_yr-1, 0)]),
                        text="<b>IC Repaid</b><br>DSRA → FD release",
                        showarrow=True, arrowhead=2, arrowcolor="#EF4444",
                        font=dict(size=11, color='#EF4444'),
                        bgcolor="rgba(255,255,255,0.8)", bordercolor="#EF4444")

                fig_bal.update_layout(
                    title='Balance Trajectories & Upstream Flow',
                    yaxis_title='EUR', height=450, barmode='overlay',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_bal, use_container_width=True)

                if _ic_repaid_yr is not None:
                    st.markdown(f"""
**{_ds_years[_ic_repaid_yr]}**: Both IC loans fully repaid. OpCo DSRA releases remaining balance
(€{_dsra_bals[max(_ic_repaid_yr-1,0)]:,.0f}) into Entity FD. From this point, all surplus is retained locally —
Entity FD grows as retained cash.
""")

                st.divider()

                # ════════════════════════════════════════════════════
                # Section 6: Pipe Servicing — IC Loan Impact
                # ════════════════════════════════════════════════════
                st.subheader("6. Pipe Servicing — IC Loan Balances")
                st.caption("How the 2 pipes service the IC loans, and how hedging affects the trajectory")

                _render_holding_passthrough_diagram()

                # Compute BOTH scenarios for comparison
                # Current scenario = _ent_wf (already computed)
                _sr_bals_curr = [_ent_wf[yi].get('sr_ic_bal', 0) for yi in range(10)]
                _mz_bals_curr = [_ent_wf[yi].get('mz_ic_bal', 0) for yi in range(10)]

                # Alternative scenario: compute with opposite swap setting
                if _ds_swap_active:
                    # Current is Swap → alternative is FEC (no swap schedule)
                    _alt_wf = _compute_entity_waterfall_inputs(
                        entity_key, _sub_ops_annual,
                        _sub_sr_schedule, _sub_mz_schedule)
                    _alt_label = "FEC"
                else:
                    # Current is FEC → alternative is Swap (with swap schedule)
                    _alt_wf = _compute_entity_waterfall_inputs(
                        entity_key, _sub_ops_annual,
                        _sub_sr_schedule, _sub_mz_schedule,
                        nwl_swap_schedule=_ds_swap_sched)
                    _alt_label = "Swap"
                _curr_label = "Swap" if _ds_swap_active else "FEC"
                _sr_bals_alt = [_alt_wf[yi].get('sr_ic_bal', 0) for yi in range(10)]
                _mz_bals_alt = [_alt_wf[yi].get('mz_ic_bal', 0) for yi in range(10)]

                fig_pipe = go.Figure()
                # Current scenario (solid lines)
                fig_pipe.add_trace(go.Scatter(
                    x=_ds_years, y=_sr_bals_curr,
                    name=f'Senior IC ({_curr_label} ✓)', mode='lines+markers',
                    line=dict(color='#1E3A5F', width=3)))
                fig_pipe.add_trace(go.Scatter(
                    x=_ds_years, y=_mz_bals_curr,
                    name=f'Mezz IC ({_curr_label} ✓)', mode='lines+markers',
                    line=dict(color='#7C3AED', width=3)))
                # Alternative scenario (dashed lines)
                fig_pipe.add_trace(go.Scatter(
                    x=_ds_years, y=_sr_bals_alt,
                    name=f'Senior IC ({_alt_label})', mode='lines',
                    line=dict(color='#1E3A5F', width=1.5, dash='dash')))
                fig_pipe.add_trace(go.Scatter(
                    x=_ds_years, y=_mz_bals_alt,
                    name=f'Mezz IC ({_alt_label})', mode='lines',
                    line=dict(color='#7C3AED', width=1.5, dash='dash')))
                fig_pipe.add_annotation(
                    x='Y1', y=_sr_bals_curr[0] if _sr_bals_curr[0] > 0 else _nwl_sr_opening,
                    text=f"Grants: −€{_total_grants:,.0f}", showarrow=True,
                    arrowhead=2, font=dict(size=10, color='#059669'))
                fig_pipe.update_layout(
                    title=f'NWL IC Balance Trajectory — {_curr_label} (active, solid) vs {_alt_label} (dashed)',
                    yaxis_title='EUR', height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_pipe, use_container_width=True)

                # Loan service comparison table — BOTH scenarios
                _pipe_c1, _pipe_c2 = st.columns(2)
                with _pipe_c1:
                    _active_tag = " ✓" if not _ds_swap_active else ""
                    st.markdown(f"**FEC Scenario{_active_tag}**")
                    _fec_wf = _ent_wf if not _ds_swap_active else _alt_wf
                    _fec_summary = {
                        'Metric': ['10yr Sr P+I', '10yr Sr Accel', '10yr Mz P+I', '10yr Mz Accel', 'Hedging Cost'],
                        'Value': [
                            f"€{sum(_fec_wf[yi].get('sr_pi', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_fec_wf[yi].get('sr_accel_entity', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_fec_wf[yi].get('mz_pi', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_fec_wf[yi].get('mz_accel_entity', 0) for yi in range(10)):,.0f}",
                            "20% effective (14.75% + 5.25% dividend)",
                        ],
                    }
                    st.dataframe(pd.DataFrame(_fec_summary).set_index('Metric'), use_container_width=True)
                with _pipe_c2:
                    _active_tag = " ✓" if _ds_swap_active else ""
                    st.markdown(f"**Swap Scenario{_active_tag}**")
                    _swap_wf = _ent_wf if _ds_swap_active else _alt_wf
                    _swap_summary = {
                        'Metric': ['10yr Sr P+I', '10yr Sr Accel', '10yr Mz P+I', '10yr Mz Accel', 'Hedging Cost'],
                        'Value': [
                            f"€{sum(_swap_wf[yi].get('sr_pi', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_swap_wf[yi].get('sr_accel_entity', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_swap_wf[yi].get('mz_pi', 0) for yi in range(10)):,.0f}",
                            f"€{sum(_swap_wf[yi].get('mz_accel_entity', 0) for yi in range(10)):,.0f}",
                            "11.75% (ZAR leg, Priority P2)",
                        ],
                    }
                    st.dataframe(pd.DataFrame(_swap_summary).set_index('Metric'), use_container_width=True)

            else:
                # ── Generic entity cascade (LanRED / TWX) ──
                st.caption("Entity-level surplus allocation: IC debt service → Ops Reserve → OpCo DSRA → Surplus priority → Entity FD")

                _render_entity_cascade_diagram(
                    name,
                    show_od_repay=(entity_key == 'lanred'),
                )

                _ent_wf = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _sub_sr_schedule, _sub_mz_schedule)
                _ds_years = [f"Y{yi+1}" for yi in range(10)]

                st.markdown(f"""
After contractual IC debt service, **{name}** allocates surplus:
Ops Reserve → OpCo DSRA → Mezz IC Accel (15.25%) →
{'OD Repayment (10%) → ' if entity_key == 'lanred' else ''}Sr IC Accel (5.20%) → Entity FD.
""")

                with st.expander("Full Cascade Detail", expanded=False):
                    _ds_rows = {}
                    for _row_label, _row_key in [
                        ('EBITDA', 'ebitda'), ('Tax', 'tax'),
                        ('IC Senior P+I', 'sr_pi'), ('IC Mezz P+I', 'mz_pi'),
                        ('Ops Reserve Fill', 'ops_reserve_fill'),
                        ('OpCo DSRA Fill', 'opco_dsra_fill'),
                        ('Mezz IC Acceleration', 'mz_accel_entity'),
                        ('Sr IC Acceleration', 'sr_accel_entity'),
                        ('Entity FD Fill', 'entity_fd_fill'),
                    ]:
                        _ds_rows[_row_label] = [
                            _eur_fmt.format(_ent_wf[yi].get(_row_key, 0))
                            if abs(_ent_wf[yi].get(_row_key, 0)) > 0.5 else '—'
                            for yi in range(10)]
                    st.dataframe(pd.DataFrame(_ds_rows, index=_ds_years).T, use_container_width=True)

                    st.markdown("**Balances**")
                    _ds_bal_rows = {}
                    for _row_label, _row_key in [
                        ('Ops Reserve Bal', 'ops_reserve_bal'),
                        ('OpCo DSRA Bal', 'opco_dsra_bal'),
                        ('Mezz IC Bal', 'mz_ic_bal'),
                        ('Senior IC Bal', 'sr_ic_bal'),
                        ('Entity FD Bal', 'entity_fd_bal'),
                    ]:
                        _ds_bal_rows[_row_label] = [
                            _eur_fmt.format(_ent_wf[yi].get(_row_key, 0))
                            for yi in range(10)]
                    st.dataframe(pd.DataFrame(_ds_bal_rows, index=_ds_years).T, use_container_width=True)

                fig_ds = go.Figure()
                _ds_colors = [
                    ('IC Senior P+I', 'sr_pi', '#1E3A5F'),
                    ('IC Mezz P+I', 'mz_pi', '#7C3AED'),
                    ('Ops Reserve', 'ops_reserve_fill', '#0D9488'),
                    ('OpCo DSRA', 'opco_dsra_fill', '#2563EB'),
                    ('Mezz IC Accel', 'mz_accel_entity', '#A855F7'),
                    ('Sr IC Accel', 'sr_accel_entity', '#3B82F6'),
                    ('Entity FD', 'entity_fd_fill', '#059669'),
                ]
                for _lbl, _fld, _clr in _ds_colors:
                    _vs = [_ent_wf[yi].get(_fld, 0) for yi in range(10)]
                    if any(v > 0 for v in _vs):
                        fig_ds.add_trace(go.Bar(x=_ds_years, y=_vs, name=_lbl, marker_color=_clr))
                _ds_deficits = [_ent_wf[yi].get('deficit', 0) for yi in range(10)]
                if any(d < 0 for d in _ds_deficits):
                    fig_ds.add_trace(go.Bar(x=_ds_years, y=_ds_deficits, name='Deficit', marker_color='#EF4444'))
                fig_ds.update_layout(
                    barmode='relative', title=f'{name} — Cascade Allocation',
                    yaxis_title='EUR', height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_ds, use_container_width=True)

    # --- BALANCE SHEET ---
    if "Balance Sheet" in _tab_map:
        with _tab_map["Balance Sheet"]:
            st.header("Balance Sheet")
            st.caption(f"{name} — Assets, liabilities & equity (point-in-time)")

            _bs_last = _sub_annual[-1]

            # Calculate better hero metrics
            # 1. Peak Debt with year
            peak_debt = max(a['bs_debt'] for a in _sub_annual)
            peak_debt_year = next((i+1 for i, a in enumerate(_sub_annual) if a['bs_debt'] == peak_debt), 1)

            # 2. Debt-Free Year
            debt_free_year = next((i+1 for i, a in enumerate(_sub_annual) if a['bs_debt'] < 1), None)

            # 3. Terminal Equity (Y10)
            terminal_equity = _bs_last['bs_equity']

            # 4. DSCR Range from repayment years (where debt service > 0)
            dscr_vals = [(i+1, a['cf_ops'] / a['cf_ds']) for i, a in enumerate(_sub_annual) if a.get('cf_ds', 0) > 0]
            dscr_min = min(dscr_vals, key=lambda x: x[1]) if dscr_vals else None
            dscr_max = max(dscr_vals, key=lambda x: x[1]) if dscr_vals else None

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Peak Debt", f"€{peak_debt:,.0f}", delta=f"Y{peak_debt_year}")
            with c2:
                if debt_free_year:
                    st.metric("Debt-Free Year", f"Y{debt_free_year}")
                else:
                    st.metric("Debt-Free Year", "Not in horizon")
            with c3:
                st.metric("Terminal Equity (Y10)", f"€{terminal_equity:,.0f}")
            with c4:
                if dscr_min and dscr_max:
                    st.metric("DSCR Range", f"{dscr_min[1]:.2f}x - {dscr_max[1]:.2f}x",
                             delta=f"Y{dscr_min[0]} to Y{dscr_max[0]}")
                else:
                    asset_cov = _bs_last['bs_assets'] / max(_bs_last['bs_debt'], 1)
                    st.metric("Asset Coverage Y10", f"{asset_cov:.2f}x")

            st.divider()

            # --- Styled BS table (no Total column — BS is point-in-time) ---
            _bs_cols = _years
            _ncols_bs = len(_bs_cols)
            _bs_rows = []

            def _bs_line(label, key, sign=1.0, row_type='line'):
                vals = [sign * a.get(key, 0.0) for a in _sub_annual]
                _bs_rows.append((label, vals, row_type))

            def _bs_section(label):
                _bs_rows.append((label, [None] * _ncols_bs, 'section'))

            def _bs_spacer():
                _bs_rows.append(('', [None] * _ncols_bs, 'spacer'))

            _bs_section('OPERATING ASSETS')
            _bs_line('Fixed Assets (Net)', 'bs_fixed_assets')
            _bs_line('Total Operating Assets', 'bs_fixed_assets', row_type='total')

            _bs_spacer()
            _bs_section('DSRA FIXED DEPOSIT')
            _bs_line('DSRA Balance', 'bs_dsra', row_type='total')

            _bs_spacer()
            _bs_line('Total Assets', 'bs_assets', row_type='grand')

            _bs_spacer()
            _bs_section('LIABILITIES')
            _bs_line('Senior IC Loan', 'bs_sr')
            _bs_line('Mezz IC Loan', 'bs_mz')
            _bs_line('Total Debt', 'bs_debt', row_type='total')

            _bs_spacer()
            _bs_section('EQUITY')
            _bs_line('Shareholder Equity', 'bs_equity_sh')
            _bs_line('Retained Earnings', 'bs_retained')
            _bs_line('Total Equity', 'bs_equity', row_type='total')

            _bs_spacer()
            _bs_section('CHECK')
            check_vals = [a['bs_assets'] - (a['bs_debt'] + a['bs_equity']) for a in _sub_annual]
            check_display = [f"{'OK' if abs(v) < 0.01 else _eur_fmt.format(v)}" for v in check_vals]
            _bs_rows.append(('Assets = Debt + Equity', check_display, 'grand'))
            # Independent RE verification: bs_retained vs cumulative PAT from P&L
            gap_vals = [a.get('bs_gap', 0.0) for a in _sub_annual]
            gap_display = [f"{'OK' if abs(v) < 1.0 else _eur_fmt.format(v)}" for v in gap_vals]
            _bs_rows.append(('RE = PAT + Grants', gap_display, 'line'))
            # Show warning if any gap > €1
            if any(abs(v) >= 1.0 for v in gap_vals):
                st.warning(f"BS Gap detected: RE ≠ Cumulative PAT + Grants. Max gap: €{max(abs(v) for v in gap_vals):,.0f}")

            # Build styled HTML table
            _fmt = _eur_fmt
            _h = ['<div style="overflow-x:auto;width:100%;">',
                  '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                  '<thead><tr>']
            _h.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _bs_cols:
                _h.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h.append('</tr></thead><tbody>')

            for label, vals, rtype in _bs_rows:
                if rtype == 'spacer':
                    _h.append(f'<tr><td colspan="{_ncols_bs + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h.append(f'<tr><td colspan="{_ncols_bs + 1}" style="padding:8px 10px 4px;font-weight:700;'
                              f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                _h.append('<tr>')
                _h.append(f'<td style="text-align:left;padding:4px 10px;{td_style}">{label}</td>')
                for v in vals:
                    if isinstance(v, str):
                        cell = v
                    elif v is not None:
                        cell = _fmt.format(v)
                    else:
                        cell = ''
                    _h.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h.append('</tr>')

            _h.append('</tbody></table></div>')
            st.markdown(''.join(_h), unsafe_allow_html=True)

            # BS chart — Stacked Debt + Equity bars, Assets as line overlay
            fig_bs = go.Figure()
            _bs_debt_vals = [a['bs_debt'] for a in _sub_annual]
            _bs_equity_vals = [a['bs_equity'] for a in _sub_annual]
            _bs_asset_vals = [a['bs_assets'] for a in _sub_annual]
            fig_bs.add_trace(go.Bar(x=_years, y=_bs_debt_vals, name='Debt', marker_color='#EF4444'))
            fig_bs.add_trace(go.Bar(x=_years, y=_bs_equity_vals, name='Equity', marker_color='#8B5CF6'))
            fig_bs.add_trace(go.Scatter(x=_years, y=_bs_asset_vals, name='Total Assets',
                mode='lines+markers', line=dict(color='#10B981', width=3), marker=dict(size=8)))
            # D/E ratio annotations
            for _bi, _byr in enumerate(_years):
                _b_eq = _bs_equity_vals[_bi]
                _b_debt = _bs_debt_vals[_bi]
                _b_top = _bs_asset_vals[_bi]
                if _b_eq != 0 and _b_top > 0:
                    _de = _b_debt / _b_eq
                    fig_bs.add_annotation(
                        x=_byr, y=_b_top, text=f"<b>D/E: {_de:.1f}x</b>",
                        showarrow=False, yshift=18,
                        font=dict(size=10, color='#DC2626' if _de > 5 else '#1E3A5F')
                    )
            fig_bs.update_layout(barmode='relative', title=f'{name} — Balance Sheet (A = D + E)', yaxis_title='EUR', height=400)
            st.plotly_chart(fig_bs, use_container_width=True)

            # Chart 2: DSRA Balance
            st.subheader("2. DSRA Fixed Deposit")
            fig_bs_dsra = go.Figure()
            fig_bs_dsra.add_trace(go.Scatter(
                x=_years, y=[a.get('bs_dsra', 0) for a in _sub_annual],
                name='DSRA Balance', fill='tozeroy',
                line=dict(color='#7C3AED', width=2),
                fillcolor='rgba(124,58,237,0.15)'
            ))
            fig_bs_dsra.add_trace(go.Bar(
                x=_years, y=[a.get('dsra_interest', 0) for a in _sub_annual],
                name='Interest Earned (9%)', marker_color='#10B981',
                yaxis='y2'
            ))
            fig_bs_dsra.update_layout(
                height=360,
                margin=dict(l=10, r=60, t=40, b=10),
                xaxis=dict(dtick=1),
                yaxis=dict(title='DSRA Balance (EUR)', side='left'),
                yaxis2=dict(title='Interest Earned (EUR)', side='right', overlaying='y', showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_bs_dsra, use_container_width=True)

            st.info(
                "**DSRA Flow:** Creation Capital → DSRA → FEC → Senior Debt (covers P1+P2)  \n"
                "**Effect on NWL:** Senior IC ↓ (faster repayment at P1), Mezz IC ↑ (DSRA drawdown). Total debt unchanged, but higher avg rate.  \n"
                "**DSRA FD:** Surplus cash deposited at 9% p.a. — Opening + Deposit + Interest = Closing"
            )

            # ── AUDIT: Balance Sheet ──
            _bs_checks = []
            for _a in _sub_annual:
                _y = _a['year']
                # A = D + E
                _bs_checks.append({
                    "name": f"Y{_y}: Assets = Debt + Equity",
                    "expected": _a['bs_debt'] + _a['bs_equity'],
                    "actual": _a['bs_assets'],
                })
                # RE = Cumulative PAT + Grants
                _bs_checks.append({
                    "name": f"Y{_y}: RE = CumPAT + Grants",
                    "expected": _a['bs_retained_check'],
                    "actual": _a['bs_retained'],
                })
                # BS DSRA = CF DSRA closing
                _bs_checks.append({
                    "name": f"Y{_y}: BS DSRA = CF DSRA",
                    "expected": _a['dsra_bal'],
                    "actual": _a['bs_dsra'],
                })
                # BS fixed assets = depr base - accumulated depr
                _acc_depr = sum(_sub_annual[i]['depr'] for i in range(_y))
                _bs_checks.append({
                    "name": f"Y{_y}: Fixed Assets = Base - AccDepr",
                    "expected": max(_sub_depr_base - _acc_depr, 0),
                    "actual": _a['bs_fixed_assets'],
                })
            run_page_audit(_bs_checks, f"{name} — Balance Sheet")

    # --- GRAPHS ---
    if "Graphs" in _tab_map:
        with _tab_map["Graphs"]:
            st.header("Graphs")
            st.caption(f"{name} — 10-year analytical dashboard")

            # ============================================================
            # NWL-SPECIFIC GRAPHS
            # ============================================================
            if entity_key == "nwl":
                # --- 1. Levelized Cost of Water (LCOW) ---
                st.subheader("1. Levelized Cost of Water (LCOW)")
                st.markdown(
                    "Combined billable volume: **Sewage IN** (95% × 2 MLD = 1.9 MLD) + "
                    "**Reuse OUT** (95% × 90% × 2 MLD = 1.71 MLD). "
                    "Brownfield overflow and grants are offsets."
                )

                # Config
                _nwl_cfg = operations_config.get("nwl", {})
                _gf_cfg = _nwl_cfg.get("greenfield", {})
                _bf_cfg = _nwl_cfg.get("brownfield", {})
                _total_capex = entity_data['total_loan']
                _asset_life = 20

                # WACC for NPV discounting: 85% × 4.70% + 15% × 14.75% = 6.21%
                _wacc = 0.85 * 0.047 + 0.15 * 0.1475

                # Capital Recovery Factor (CRF) for proper capex annualization
                _crf = _wacc * (1 + _wacc)**_asset_life / ((1 + _wacc)**_asset_life - 1)
                _ann_capex_eur = _total_capex * _crf

                # Grants (DTIC + GEPF Bulk) - Note: GEPF Bulk = GEPF Bulk Services (same thing, no double count)
                _grant_dtic = financing['prepayments']['dtic_grant']['amount_eur']
                _grant_gepf = financing['prepayments']['gepf_bulk_services']['amount_eur']
                _grants_total = _grant_dtic + _grant_gepf

                # NPV helper
                def _npv(annual_values: list[float], r: float = _wacc) -> float:
                    return sum(v / ((1 + r) ** (t + 1)) for t, v in enumerate(annual_values))

                # --- COSTS ---
                _cf_capex = [_ann_capex_eur] * 10
                _cf_om = [a.get('om_cost', 0) for a in _sub_annual]
                _cf_power = [a.get('power_cost', 0) for a in _sub_annual]
                _cf_rent = [a.get('rent_cost', 0) for a in _sub_annual]
                _cf_finance = [a.get('ie', 0) for a in _sub_annual]

                _npv_capex = _npv(_cf_capex)
                _npv_om = _npv(_cf_om)
                _npv_power = _npv(_cf_power)
                _npv_rent = _npv(_cf_rent)
                _npv_finance = _npv(_cf_finance)
                _npv_costs = _npv_capex + _npv_om + _npv_power + _npv_rent + _npv_finance

                # --- OFFSETS (brownfield + grants only, NOT bulk services which = GEPF Bulk) ---
                _cf_brownfield = [a.get('rev_brownfield_sewage', 0) for a in _sub_annual]
                _npv_brownfield = _npv(_cf_brownfield)
                _npv_grants = _grants_total / (1 + _wacc)  # Year 1 receipt
                _npv_offsets = _npv_brownfield + _npv_grants

                # --- COMBINED VOLUME (Sewage + Reuse = total billable) ---
                _cf_vol_sewage = [a.get('vol_annual_m3', 0) for a in _sub_annual]
                _cf_vol_reuse = [a.get('vol_reuse_annual_m3', 0) for a in _sub_annual]
                _cf_vol_combined = [s + r for s, r in zip(_cf_vol_sewage, _cf_vol_reuse)]
                _npv_vol = _npv(_cf_vol_combined)

                # --- NET LCOW ---
                _npv_net_cost = _npv_costs - _npv_offsets
                _lcow_eur = _npv_net_cost / _npv_vol if _npv_vol > 0 else 0
                _lcow_zar = _lcow_eur * FX_RATE

                # --- INCOME GENERATING CAPACITY ---
                _cf_sewage_rev = [a.get('rev_greenfield_sewage', 0) for a in _sub_annual]
                _cf_reuse_rev = [a.get('rev_greenfield_reuse', 0) + a.get('rev_construction', 0) + a.get('rev_agri', 0) for a in _sub_annual]
                _npv_sewage_rev = _npv(_cf_sewage_rev)
                _npv_reuse_rev = _npv(_cf_reuse_rev)
                _npv_total_rev = _npv_sewage_rev + _npv_reuse_rev

                # Helper: convert NPV EUR to R/kL
                def _to_rkl(npv_eur):
                    return (npv_eur / _npv_vol * FX_RATE) if _npv_vol > 0 else 0

                # --- LCOW waterfall (costs only) + Revenue stacked bars (blue) ---
                _sewage_rkl = _to_rkl(_npv_sewage_rev)
                _reuse_rkl = _to_rkl(_npv_reuse_rev)
                # Brownfield is ONLY an offset in LCOW — not double-counted as revenue
                _total_income_rkl = _sewage_rkl + _reuse_rkl
                _margin_rkl = _total_income_rkl - _lcow_zar
                _margin_pct = (_margin_rkl / _total_income_rkl * 100) if _total_income_rkl > 0 else 0

                # Display metrics — use same margin as graph (revenue - LCOW)
                _lc1, _lc2, _lc3, _lc4, _lc5 = st.columns(5)
                _lc1.metric("Net LCOW", f"R{_lcow_zar:.2f}/kL")
                _lc2.metric("Sewage Rev", f"R{_sewage_rkl:.1f}/kL")
                _lc3.metric("Reuse Rev", f"R{_reuse_rkl:.1f}/kL")
                _lc4.metric("Total Revenue", f"R{_total_income_rkl:.1f}/kL")
                _lc5.metric("Margin", f"R{_margin_rkl:.1f}/kL",
                    delta=f"{_margin_pct:.0f}%",
                    delta_color="normal" if _margin_pct > 0 else "inverse")

                # X-axis categories: cost waterfall bars + gap + revenue stacked bar
                _x_all = ['Capex', 'O&M', 'Power', 'Rent', 'Finance',
                          'Brownfield', 'Grants', 'Net LCOW',
                          ' ',  # spacer
                          'Revenue']

                # -- Waterfall trace (costs → offsets → net LCOW) --
                _wf_x = _x_all[:8]
                _wf_y = [
                    _to_rkl(_npv_capex), _to_rkl(_npv_om), _to_rkl(_npv_power),
                    _to_rkl(_npv_rent), _to_rkl(_npv_finance),
                    -_to_rkl(_npv_brownfield), -_to_rkl(_npv_grants),
                    0,  # total
                ]
                _wf_measures = ['relative'] * 7 + ['total']
                _wf_text = [f"R{abs(v):.1f}" for v in _wf_y[:-1]] + [f"R{_lcow_zar:.1f}"]

                fig_lcow = go.Figure()

                # Waterfall for costs
                fig_lcow.add_trace(go.Waterfall(
                    x=_wf_x, y=_wf_y, measure=_wf_measures,
                    connector=dict(line=dict(color='#CBD5E1', width=1)),
                    increasing=dict(marker=dict(color='#DC2626')),
                    decreasing=dict(marker=dict(color='#10B981')),
                    totals=dict(marker=dict(color='#1E40AF')),
                    textposition="outside", text=_wf_text,
                    name='LCOW', showlegend=False,
                ))

                # -- Revenue stacked bars (blue shades, build from zero) --
                fig_lcow.add_trace(go.Bar(
                    x=['Revenue'], y=[_sewage_rkl],
                    name='Piped Sewage', marker_color='#2563EB',
                    text=[f"R{_sewage_rkl:.1f}"], textposition='inside',
                    textfont=dict(color='white'),
                ))
                fig_lcow.add_trace(go.Bar(
                    x=['Revenue'], y=[_reuse_rkl],
                    name='Reuse Water', marker_color='#3B82F6',
                    text=[f"R{_reuse_rkl:.1f}"], textposition='inside',
                    textfont=dict(color='white'),
                ))

                # Horizontal LCOW line across entire chart — the gap tells the story
                fig_lcow.add_hline(y=_lcow_zar, line_dash="dot", line_color="#DC2626", line_width=2,
                    annotation_text=f"LCOW R{_lcow_zar:.1f}/kL",
                    annotation_position="top left",
                    annotation_font=dict(color='#DC2626', size=11))

                # Horizontal Revenue line — the gap between LCOW and Revenue = profitability
                fig_lcow.add_hline(y=_total_income_rkl, line_dash="dot", line_color="#2563EB", line_width=2,
                    annotation_text=f"Revenue R{_total_income_rkl:.1f}/kL",
                    annotation_position="top right",
                    annotation_font=dict(color='#2563EB', size=11))

                # Margin annotation in the gap between the two lines
                fig_lcow.add_annotation(
                    x='Finance', y=_lcow_zar + (_total_income_rkl - _lcow_zar) / 2,
                    text=f"<b>Margin R{_margin_rkl:.1f}/kL ({_margin_pct:.0f}%)</b>",
                    showarrow=False, font=dict(size=13, color='#16A34A'),
                    bgcolor='rgba(255,255,255,0.9)', bordercolor='#16A34A', borderwidth=1,
                )

                fig_lcow.update_layout(
                    barmode='stack', height=500,
                    margin=dict(l=10, r=10, t=40, b=10),
                    yaxis_title='R / kL (NPV basis)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    xaxis=dict(categoryorder='array', categoryarray=_x_all),
                )
                st.plotly_chart(fig_lcow, use_container_width=True)

                # Toggle for calculation details
                st.checkbox("Show LCOW calculation details", value=False, key="lcow_details_toggle")

                # Breakdown expander
                if st.session_state.get("lcow_details_toggle", False):
                    with st.expander("LCOW Breakdown (NPV @ WACC {:.1%})".format(_wacc), expanded=True):
                        _rows = [
                            ('**COSTS (NPV)**', '', ''),
                            (f'Capex (CRF {_crf*100:.1f}% × {_asset_life}yr)', f"€{_npv_capex:,.0f}", f"R{_to_rkl(_npv_capex):.2f}"),
                            ('O&M', f"€{_npv_om:,.0f}", f"R{_to_rkl(_npv_om):.2f}"),
                            ('Power', f"€{_npv_power:,.0f}", f"R{_to_rkl(_npv_power):.2f}"),
                            ('CoE Rent', f"€{_npv_rent:,.0f}", f"R{_to_rkl(_npv_rent):.2f}"),
                            ('Finance (interest)', f"€{_npv_finance:,.0f}", f"R{_to_rkl(_npv_finance):.2f}"),
                            ('**Total Costs**', f"**€{_npv_costs:,.0f}**", f"**R{_to_rkl(_npv_costs):.2f}**"),
                            ('**OFFSETS (NPV)**', '', ''),
                            ('Brownfield revenue', f"€{_npv_brownfield:,.0f}", f"-R{_to_rkl(_npv_brownfield):.2f}"),
                            ('Grants (DTIC + GEPF Bulk)', f"€{_npv_grants:,.0f}", f"-R{_to_rkl(_npv_grants):.2f}"),
                            ('**Total Offsets**', f"**€{_npv_offsets:,.0f}**", f"**-R{_to_rkl(_npv_offsets):.2f}**"),
                            ('', '', ''),
                            ('**NET LCOW**', f"**€{_npv_net_cost:,.0f}**", f"**R{_lcow_zar:.2f}/kL**"),
                        ]
                        render_table(pd.DataFrame(_rows, columns=['Component', 'NPV (EUR)', 'R/kL']),
                            right_align=['NPV (EUR)', 'R/kL'])
                        st.markdown(
                            f"**Capex:** €{_total_capex:,.0f} × CRF {_crf*100:.2f}% = €{_ann_capex_eur:,.0f}/yr | "
                            f"**Combined Vol:** {_npv_vol/1e6:.2f}M m³ (Sewage + Reuse) | **WACC:** {_wacc:.2%}"
                        )
                        st.markdown(
                            f"**Revenue Capacity:** Sewage €{_npv_sewage_rev:,.0f} + Reuse €{_npv_reuse_rev:,.0f} "
                            f"= **€{_npv_sewage_rev + _npv_reuse_rev:,.0f}** "
                            f"(Brownfield €{_npv_brownfield:,.0f} is already an offset, not counted as revenue)"
                        )

                        st.caption(
                            f"LCOW = NPV(Costs − Offsets) ÷ NPV(Combined Volume). "
                            f"Volume = Sewage IN + Reuse OUT. Offsets = Brownfield + Grants (no double-count with GEPF Bulk). "
                            f"WACC = {_wacc:.2%}."
                        )

                st.divider()

                # --- 2. MABR Energy Savings ---
                st.subheader("2. MABR Energy Savings")
                _saving_pct = (1.0 - _pw_kwh / _cas_kwh_m3) * 100.0
                _esc_factor = 1.0 + (_pw_esc / 100.0)
                _mabr_ann = []
                _cas_ann = []
                _cum_sav = []
                _cum_t = 0.0
                for _yi in range(10):
                    _my = 0.0
                    _cy = 0.0
                    _cap = _sub_annual[_yi].get('vol_treated_mld', 0)
                    _vol = _cap * 1000.0
                    for _mi in range(_yi * 12 + 1, (_yi + 1) * 12 + 1):
                        if _mi < 18:
                            continue
                        _yf = (_mi - 18) / 12.0
                        _my += _vol * _pw_kwh * _pw_rate * (_esc_factor ** _yf) * 30.44
                        _cy += _vol * _cas_kwh_m3 * _pw_eskom * (_esc_factor ** _yf) * 30.44
                    _mabr_ann.append(_my)
                    _cas_ann.append(_cy)
                    _cum_t += (_cy - _my)
                    _cum_sav.append(_cum_t)

                _ec1, _ec2, _ec3 = st.columns(3)
                _ec1.metric("MABR", f"{_pw_kwh} kWh/m\u00b3")
                _ec2.metric("CAS Benchmark", f"{_cas_kwh_m3} kWh/m\u00b3")
                _ec3.metric("10-Year Saving", f"R{_cum_sav[-1]:,.0f}")

                from plotly.subplots import make_subplots
                fig_energy = make_subplots(specs=[[{"secondary_y": True}]])
                fig_energy.add_trace(go.Bar(x=_years, y=[v / 1e6 for v in _cas_ann],
                    name='Conventional CAS (Eskom)', marker_color='#EF4444', opacity=0.7), secondary_y=False)
                fig_energy.add_trace(go.Bar(x=_years, y=[v / 1e6 for v in _mabr_ann],
                    name='MABR + LanRED Solar (-10%)', marker_color='#10B981', opacity=0.85), secondary_y=False)
                fig_energy.add_trace(go.Scatter(x=_years, y=[v / 1e6 for v in _cum_sav],
                    name='Cumulative Saving', mode='lines+markers', line=dict(color='#2563EB', width=3)), secondary_y=True)
                fig_energy.update_layout(barmode='group', height=380,
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                fig_energy.update_yaxes(title_text="Annual Cost (R millions)", secondary_y=False)
                fig_energy.update_yaxes(title_text="Cumulative Saving (R millions)", secondary_y=True)
                st.plotly_chart(fig_energy, use_container_width=True)
                st.caption(f"MABR saves {_saving_pct:.0f}% vs conventional CAS. 10-year cumulative: R{_cum_sav[-1]:,.0f}")

                st.divider()

                # --- 3. Senior Debt Bridge — Grants & Bulk Services ---
                st.subheader("3. Senior Debt Bridge — Grants & Bulk Services")
                st.markdown(
                    "The Senior IC loan **bridges** until non-diluting grant proceeds and bulk services fees are received. "
                    "These receipts are applied as prepayments, reducing the outstanding balance and lifetime debt service."
                )
                # DTIC + GEPF grants are 100% NWL (not pro-rata)
                _grant_eur = financing['prepayments']['dtic_grant']['amount_eur']
                _gepf_eur = financing['prepayments']['gepf_bulk_services']['amount_eur']
                _sr_drawn = entity_data['senior_portion']
                _prepay_tot = _grant_eur + _gepf_eur
                _sr_remaining = _sr_drawn - _prepay_tot

                fig_bridge = go.Figure(go.Waterfall(
                    x=['Senior Loan', 'DTIC Grant', 'GEPF Bulk Services', 'Remaining Debt'],
                    y=[_sr_drawn, -_grant_eur, -_gepf_eur, _sr_remaining],
                    measure=['absolute', 'relative', 'relative', 'total'],
                    connector=dict(line=dict(color='#CBD5E1', width=1)),
                    increasing=dict(marker=dict(color='#3B82F6')),
                    decreasing=dict(marker=dict(color='#10B981')),
                    totals=dict(marker=dict(color='#1E3A5F')),
                    textposition="outside",
                    text=[f"\u20ac{_sr_drawn:,.0f}", f"-\u20ac{_grant_eur:,.0f}",
                          f"-\u20ac{_gepf_eur:,.0f}", f"\u20ac{_sr_remaining:,.0f}"],
                ))
                fig_bridge.update_layout(height=400, yaxis_title='EUR', showlegend=False,
                    margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_bridge, use_container_width=True)

                _bc1, _bc2, _bc3 = st.columns(3)
                _bc1.metric("DTIC Grant (NWL share)", f"\u20ac{_grant_eur:,.0f}")
                _bc2.metric("GEPF Bulk Services (NWL share)", f"\u20ac{_gepf_eur:,.0f}")
                _bc3.metric("Debt Reduction", f"{_prepay_tot / _sr_drawn * 100:.1f}%")

                st.divider()

                # --- 4. Revenue Breakdown ---
                st.subheader("4. Revenue Breakdown")
                fig_rev = go.Figure()
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_greenfield_sewage', 0) for a in _sub_annual],
                    name='Greenfield Sewage', marker_color='#2563EB'))
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_brownfield_sewage', 0) for a in _sub_annual],
                    name='Brownfield Sewage', marker_color='#60A5FA'))
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_greenfield_reuse', 0) for a in _sub_annual],
                    name='Reuse (Greenfield)', marker_color='#10B981'))
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_construction', 0) for a in _sub_annual],
                    name='Construction Water', marker_color='#6EE7B7'))
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_agri', 0) for a in _sub_annual],
                    name='Agricultural Reuse', marker_color='#A7F3D0'))
                fig_rev.add_trace(go.Bar(x=_years, y=[a.get('rev_bulk_services', 0) for a in _sub_annual],
                    name='Bulk Services', marker_color='#8B5CF6'))
                fig_rev.update_layout(barmode='stack', height=380, yaxis_title='EUR',
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                st.plotly_chart(fig_rev, use_container_width=True)

                st.divider()

            # ============================================================
            # LANRED-SPECIFIC GRAPHS
            # ============================================================
            if entity_key == "lanred" and _state_str("lanred_scenario", "Greenfield") != "Greenfield":
                st.info("LCOE analysis not applicable for Brownfield+ — acquired portfolio has contracted PPA tariffs.")
                st.divider()
            elif entity_key == "lanred":
                # --- 1. Levelized Cost of Energy (LCOE) ---
                st.subheader("1. Levelized Cost of Energy (LCOE)")
                st.markdown(
                    "LCOE compares the **all-in cost of generation** to the **achievable blended tariff**. "
                    "LanRED sells to NWL at Eskom −10% (IC rate) with potential future external PPA revenue."
                )

                _lr_total_capex = entity_data['total_loan']
                _lr_asset_life = 25  # solar asset life
                _lr_wacc = 0.85 * 0.047 + 0.15 * 0.1475

                # CRF for capex annualization
                _lr_crf = _lr_wacc * (1 + _lr_wacc)**_lr_asset_life / ((1 + _lr_wacc)**_lr_asset_life - 1)
                _lr_ann_capex = _lr_total_capex * _lr_crf

                # NPV helper
                def _lr_npv(vals, r=_lr_wacc):
                    return sum(v / ((1 + r) ** (t + 1)) for t, v in enumerate(vals))

                # Costs from model
                _lr_cf_capex = [_lr_ann_capex] * 10
                _lr_cf_om = [a.get('om_cost', 0) for a in _sub_annual]
                _lr_cf_grid = [a.get('grid_cost', 0) for a in _sub_annual]
                _lr_cf_finance = [a.get('ie', 0) for a in _sub_annual]

                _lr_npv_capex = _lr_npv(_lr_cf_capex)
                _lr_npv_om = _lr_npv(_lr_cf_om)
                _lr_npv_grid = _lr_npv(_lr_cf_grid)
                _lr_npv_finance = _lr_npv(_lr_cf_finance)
                _lr_npv_costs = _lr_npv_capex + _lr_npv_om + _lr_npv_grid + _lr_npv_finance

                # Generation volume (kWh)
                _lr_cf_gen = [a.get('generation_kwh', 0) for a in _sub_annual]
                _lr_npv_gen = _lr_npv(_lr_cf_gen)

                # LCOE
                _lr_lcoe_eur = _lr_npv_costs / _lr_npv_gen if _lr_npv_gen > 0 else 0
                _lr_lcoe_zar = _lr_lcoe_eur * FX_RATE  # R/kWh

                # Revenue (achievable tariff) — all 4 streams
                _lr_cf_rev_ic = [a.get('rev_ic_nwl', 0) for a in _sub_annual]
                _lr_cf_rev_sc = [a.get('rev_smart_city', 0) for a in _sub_annual]
                _lr_cf_rev_mkt = [a.get('rev_open_market', 0) for a in _sub_annual]
                _lr_cf_rev_bess = [a.get('rev_bess_arbitrage', 0) for a in _sub_annual]
                _lr_npv_rev_ic = _lr_npv(_lr_cf_rev_ic)
                _lr_npv_rev_sc = _lr_npv(_lr_cf_rev_sc)
                _lr_npv_rev_mkt = _lr_npv(_lr_cf_rev_mkt)
                _lr_npv_rev_bess = _lr_npv(_lr_cf_rev_bess)
                _lr_npv_rev_total = _lr_npv_rev_ic + _lr_npv_rev_sc + _lr_npv_rev_mkt + _lr_npv_rev_bess

                # Helper: NPV EUR to R/kWh
                def _lr_to_rkwh(npv_eur):
                    return (npv_eur / _lr_npv_gen * FX_RATE) if _lr_npv_gen > 0 else 0

                _lr_ic_rkwh = _lr_to_rkwh(_lr_npv_rev_ic)
                _lr_sc_rkwh = _lr_to_rkwh(_lr_npv_rev_sc)
                _lr_mkt_rkwh = _lr_to_rkwh(_lr_npv_rev_mkt)
                _lr_bess_rkwh = _lr_to_rkwh(_lr_npv_rev_bess)
                _lr_total_rev_rkwh = _lr_ic_rkwh + _lr_sc_rkwh + _lr_mkt_rkwh + _lr_bess_rkwh
                _lr_margin_rkwh = _lr_total_rev_rkwh - _lr_lcoe_zar
                _lr_margin_pct = (_lr_margin_rkwh / _lr_total_rev_rkwh * 100) if _lr_total_rev_rkwh > 0 else 0

                # Metrics
                _le1, _le2, _le3, _le4 = st.columns(4)
                _le1.metric("LCOE", f"R{_lr_lcoe_zar:.2f}/kWh")
                _le2.metric("Blended Tariff (NPV)", f"R{_lr_total_rev_rkwh:.2f}/kWh")
                _le3.metric("NPV Generation", f"{_lr_npv_gen / 1e6:.1f}M kWh")
                _le4.metric("Margin", f"R{_lr_margin_rkwh:.2f}/kWh",
                    delta=f"{_lr_margin_pct:.0f}%",
                    delta_color="normal" if _lr_margin_pct > 0 else "inverse")

                # LCOE waterfall (costs) + Revenue stacked bars (blue)
                _lr_x_all = ['Capex', 'O&M', 'Grid', 'Finance', 'Net LCOE', ' ', 'Revenue']

                _lr_wf_x = _lr_x_all[:5]
                _lr_wf_y = [
                    _lr_to_rkwh(_lr_npv_capex), _lr_to_rkwh(_lr_npv_om),
                    _lr_to_rkwh(_lr_npv_grid), _lr_to_rkwh(_lr_npv_finance),
                    0,  # total
                ]
                _lr_wf_measures = ['relative'] * 4 + ['total']
                _lr_wf_text = [f"R{abs(v):.2f}" for v in _lr_wf_y[:-1]] + [f"R{_lr_lcoe_zar:.2f}"]

                fig_lcoe = go.Figure()

                # Waterfall for costs
                fig_lcoe.add_trace(go.Waterfall(
                    x=_lr_wf_x, y=_lr_wf_y, measure=_lr_wf_measures,
                    connector=dict(line=dict(color='#CBD5E1', width=1)),
                    increasing=dict(marker=dict(color='#DC2626')),
                    decreasing=dict(marker=dict(color='#10B981')),
                    totals=dict(marker=dict(color='#1E40AF')),
                    textposition="outside", text=_lr_wf_text,
                    name='LCOE', showlegend=False,
                ))

                # Revenue stacked bars (3 streams)
                fig_lcoe.add_trace(go.Bar(
                    x=['Revenue'], y=[_lr_ic_rkwh],
                    name='NWL IC Sales', marker_color='#10B981',
                    text=[f"R{_lr_ic_rkwh:.2f}"], textposition='inside',
                    textfont=dict(color='white'),
                ))
                if _lr_sc_rkwh > 0.001:
                    fig_lcoe.add_trace(go.Bar(
                        x=['Revenue'], y=[_lr_sc_rkwh],
                        name='Smart City Off-take', marker_color='#3B82F6',
                        text=[f"R{_lr_sc_rkwh:.2f}"], textposition='inside',
                        textfont=dict(color='white'),
                    ))
                if _lr_mkt_rkwh > 0.001:
                    fig_lcoe.add_trace(go.Bar(
                        x=['Revenue'], y=[_lr_mkt_rkwh],
                        name='Open Market', marker_color='#8B5CF6',
                        text=[f"R{_lr_mkt_rkwh:.2f}"], textposition='inside',
                        textfont=dict(color='white'),
                    ))
                if _lr_bess_rkwh > 0.001:
                    fig_lcoe.add_trace(go.Bar(
                        x=['Revenue'], y=[_lr_bess_rkwh],
                        name='BESS Arbitrage', marker_color='#F59E0B',
                        text=[f"R{_lr_bess_rkwh:.2f}"], textposition='inside',
                        textfont=dict(color='white'),
                    ))

                # LCOE line across chart
                fig_lcoe.add_hline(y=_lr_lcoe_zar, line_dash="dot", line_color="#DC2626", line_width=2,
                    annotation_text=f"LCOE R{_lr_lcoe_zar:.2f}/kWh",
                    annotation_position="top left",
                    annotation_font=dict(color='#DC2626', size=11))

                # Revenue line — gap between LCOE and Revenue = profitability
                fig_lcoe.add_hline(y=_lr_total_rev_rkwh, line_dash="dot", line_color="#2563EB", line_width=2,
                    annotation_text=f"Revenue R{_lr_total_rev_rkwh:.2f}/kWh",
                    annotation_position="top right",
                    annotation_font=dict(color='#2563EB', size=11))

                # Margin annotation in the gap between the two lines
                if _lr_total_rev_rkwh > _lr_lcoe_zar:
                    fig_lcoe.add_annotation(
                        x='O&M', y=_lr_lcoe_zar + _lr_margin_rkwh / 2,
                        text=f"<b>Margin R{_lr_margin_rkwh:.2f}/kWh ({_lr_margin_pct:.0f}%)</b>",
                        showarrow=False, font=dict(size=13, color='#16A34A'),
                        bgcolor='rgba(255,255,255,0.9)', bordercolor='#16A34A', borderwidth=1,
                    )

                fig_lcoe.update_layout(
                    barmode='stack', height=500,
                    margin=dict(l=10, r=10, t=40, b=10),
                    yaxis_title='R / kWh (NPV basis)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    xaxis=dict(categoryorder='array', categoryarray=_lr_x_all),
                )
                st.plotly_chart(fig_lcoe, use_container_width=True)

                # Breakdown expander
                with st.expander("LCOE Breakdown (NPV @ WACC {:.1%})".format(_lr_wacc)):
                    _lr_rows = [
                        ('**COSTS (NPV)**', '', ''),
                        (f'Capex (CRF {_lr_crf*100:.1f}% × {_lr_asset_life}yr)', f"€{_lr_npv_capex:,.0f}", f"R{_lr_to_rkwh(_lr_npv_capex):.3f}"),
                        ('O&M', f"€{_lr_npv_om:,.0f}", f"R{_lr_to_rkwh(_lr_npv_om):.3f}"),
                        ('Grid connection', f"€{_lr_npv_grid:,.0f}", f"R{_lr_to_rkwh(_lr_npv_grid):.3f}"),
                        ('Finance (interest)', f"€{_lr_npv_finance:,.0f}", f"R{_lr_to_rkwh(_lr_npv_finance):.3f}"),
                        ('**Total Costs**', f"**€{_lr_npv_costs:,.0f}**", f"**R{_lr_lcoe_zar:.3f}**"),
                        ('', '', ''),
                        ('**REVENUE (NPV)**', '', ''),
                        ('NWL IC Sales', f"€{_lr_npv_rev_ic:,.0f}", f"R{_lr_ic_rkwh:.3f}"),
                        ('Smart City Off-take', f"€{_lr_npv_rev_sc:,.0f}", f"R{_lr_sc_rkwh:.3f}"),
                        ('Open Market', f"€{_lr_npv_rev_mkt:,.0f}", f"R{_lr_mkt_rkwh:.3f}"),
                        ('BESS Arbitrage', f"€{_lr_npv_rev_bess:,.0f}", f"R{_lr_bess_rkwh:.3f}"),
                        ('**Total Revenue**', f"**€{_lr_npv_rev_total:,.0f}**", f"**R{_lr_total_rev_rkwh:.3f}**"),
                        ('', '', ''),
                        ('**MARGIN**', '', f"**R{_lr_margin_rkwh:.3f}/kWh**"),
                    ]
                    render_table(pd.DataFrame(_lr_rows, columns=['Component', 'NPV (EUR)', 'R/kWh']),
                        right_align=['NPV (EUR)', 'R/kWh'])
                    st.markdown(
                        f"**Capex:** €{_lr_total_capex:,.0f} × CRF {_lr_crf*100:.2f}% = €{_lr_ann_capex:,.0f}/yr | "
                        f"**10yr Gen:** {sum(_lr_cf_gen)/1e6:.1f}M kWh | **WACC:** {_lr_wacc:.2%}"
                    )

                st.caption(
                    f"LCOE = NPV(Costs) ÷ NPV(Generation). "
                    f"Solar asset life: {_lr_asset_life}yr. IC tariff: Eskom −10%. "
                    f"WACC = {_lr_wacc:.2%}."
                )

                st.divider()

            # ============================================================
            # UNIVERSAL GRAPHS (all entities)
            # ============================================================
            _gn_offset = 4 if entity_key == "nwl" else (1 if entity_key == "lanred" else 0)

            # --- 5/1. EBITDA vs Debt Service ---
            st.subheader(f"{_gn_offset + 1}. EBITDA vs Debt Service")
            fig_eds = go.Figure()
            fig_eds.add_trace(go.Bar(x=_years, y=[a['ebitda'] for a in _sub_annual],
                name='EBITDA', marker_color='#10B981', offsetgroup='ebitda'))
            fig_eds.add_trace(go.Bar(x=_years, y=[a['cf_ie'] for a in _sub_annual],
                name='Interest', marker_color='#EF4444', offsetgroup='ds'))
            fig_eds.add_trace(go.Bar(x=_years, y=[a['cf_pr'] for a in _sub_annual],
                name='Principal', marker_color='#6366F1', offsetgroup='ds'))
            for _ci, _yr in enumerate(_years):
                _ds = _sub_annual[_ci]['cf_ds']
                _eb = _sub_annual[_ci]['ebitda']
                _top = max(_eb, _ds) if (_eb > 0 or _ds > 0) else 0
                if _ds > 0:
                    _dscr_v = _eb / _ds
                    fig_eds.add_annotation(x=_yr, y=_top, text=f"<b>{_dscr_v:.2f}x</b>",
                        showarrow=False, yshift=18,
                        font=dict(size=11, color='#16A34A' if _dscr_v >= 1.3 else '#DC2626'))
            fig_eds.update_layout(barmode='stack', height=380, yaxis_title='EUR',
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
            st.plotly_chart(fig_eds, use_container_width=True)
            st.caption("DSCR = EBITDA / Total Debt Service. Green = above 1.30x covenant.")

            st.divider()

            # --- 6/2. Cumulative Free Cash Flow ---
            st.subheader(f"{_gn_offset + 2}. Cumulative Free Cash Flow")
            fig_fcf = go.Figure()
            fig_fcf.add_trace(go.Bar(x=_years, y=[a['cf_after_debt_service'] for a in _sub_annual],
                name='Annual Free CF', marker_color='#60A5FA', opacity=0.6))
            fig_fcf.add_trace(go.Scatter(x=_years, y=[a.get('dsra_bal', 0) for a in _sub_annual],
                name='DSRA Balance', mode='lines+markers', line=dict(color='#1E3A5F', width=3)))
            for _ci in range(len(_sub_annual) - 1):
                if _sub_annual[_ci].get('dsra_bal', 0) < 0 and _sub_annual[_ci + 1].get('dsra_bal', 0) >= 0:
                    fig_fcf.add_annotation(x=_years[_ci + 1], y=0,
                        text="<b>Breakeven</b>", showarrow=True, arrowhead=2,
                        yshift=20, font=dict(size=11, color='#16A34A'))
                    break
            fig_fcf.update_layout(height=350, yaxis_title='EUR',
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
            st.plotly_chart(fig_fcf, use_container_width=True)


            # --- 7-8. Debt Paydown & Equity Build-up (side by side) ---
            _col_debt, _col_equity = st.columns(2)
            with _col_debt:
                # --- 7/3. Debt Paydown ---
                st.subheader(f"{_gn_offset + 3}. Debt Paydown")
                fig_debt = go.Figure()
                fig_debt.add_trace(go.Scatter(x=_years, y=[a['bs_sr'] for a in _sub_annual],
                    name='Senior IC', mode='lines+markers', line=dict(color='#3B82F6')))
                fig_debt.add_trace(go.Scatter(x=_years, y=[a['bs_mz'] for a in _sub_annual],
                    name='Mezz IC', mode='lines+markers', line=dict(color='#F59E0B')))
                fig_debt.add_trace(go.Scatter(x=_years, y=[a['bs_debt'] for a in _sub_annual],
                    name='Total Debt', mode='lines+markers', line=dict(color='#EF4444', dash='dash')))
                fig_debt.update_layout(height=350, yaxis_title='EUR',
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                st.plotly_chart(fig_debt, use_container_width=True, key="debt_paydown")

                st.divider()


            with _col_equity:
                # --- 8/4. Equity Build-up ---
                st.subheader(f"{_gn_offset + 4}. Equity Build-up")
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=_years, y=[a['bs_equity'] for a in _sub_annual],
                    name='Equity', mode='lines+markers', fill='tozeroy', line=dict(color='#8B5CF6')))
                fig_eq.update_layout(height=350, yaxis_title='EUR',
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                st.plotly_chart(fig_eq, use_container_width=True, key="equity_buildup")

                st.divider()


            # --- 9/5. Operating Margins ---
            st.subheader(f"{_gn_offset + 5}. Operating Margins")
            _ebitda_margins = []
            _net_margins = []
            for a in _sub_annual:
                rev = a.get('rev_total', 0)
                _ebitda_margins.append(a['ebitda'] / rev * 100 if rev > 0 else 0)
                _net_margins.append(a['pat'] / rev * 100 if rev > 0 else 0)
            fig_margins = go.Figure()
            fig_margins.add_trace(go.Scatter(x=_years, y=_ebitda_margins,
                name='EBITDA Margin %', mode='lines+markers', line=dict(color='#10B981', width=2)))
            fig_margins.add_trace(go.Scatter(x=_years, y=_net_margins,
                name='Net Profit Margin %', mode='lines+markers', line=dict(color='#3B82F6', width=2)))
            fig_margins.add_hline(y=0, line_dash="dash", line_color="#CBD5E1")
            fig_margins.update_layout(height=350, yaxis_title='Margin (%)',
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
            st.plotly_chart(fig_margins, use_container_width=True)

            st.divider()

            # --- Additional graphs in 2-column layout ---
            if entity_key == "nwl":
                _col_rev_mix, _col_cf_ops = st.columns(2)

                with _col_rev_mix:
                    # --- Revenue Mix (Semi-Annual) ---
                    st.subheader(f"{_gn_offset + 6}. Revenue Mix (Semi-Annual)")

                    # Compute semi-annual revenue data from operations model
                    # Re-use logic from Operations tab for consistency
                    _gf_cfg = operations_config.get("nwl", {}).get("greenfield", {})
                    _days_per_half = 182.5
                    _kl_per_mld = 1000.0
                    _rev_months = list(range(6, 126, 6))
                    _rev_labels = [f"M{m}" for m in _rev_months]

                    # Get base rates and growth
                    sewage_rate_2025 = 46.40
                    water_rate_2025 = 62.05
                    annual_growth_pct = 7.7
                    growth_factor = 1.0 + (annual_growth_pct / 100.0)

                    # On-ramp data
                    months = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
                    piped_sewage_topcos = [0.00, 0.10, 0.50, 0.80, 0.92, 1.06, 1.20, 1.38, 1.60, 1.82]
                    construction_water_demand = [0.38, 1.25, 0.97, 0.73, 0.63, 0.52, 0.41, 0.26, 0.09, 0.00]
                    cap_map = {18: 0.53, 24: 1.85, 30: 1.90, 36: 1.90, 42: 1.90, 48: 1.90, 54: 1.90, 60: 1.90, 66: 1.90, 72: 1.90}
                    sewage_capacity = [float(cap_map[m]) for m in months]
                    sewage_sold_topcos = [min(cap, dem) for cap, dem in zip(sewage_capacity, piped_sewage_topcos)]
                    sewage_overflow_brownfield = [max(cap - sold, 0.0) for cap, sold in zip(sewage_capacity, sewage_sold_topcos)]

                    brine_pct = 10.0
                    reuse_ratio = 0.80
                    reuse_capacity = [a * (1.0 - (brine_pct / 100.0)) for a in sewage_capacity]
                    reuse_demand_topcos = [d * reuse_ratio for d in sewage_sold_topcos]
                    reuse_sold_topcos = [min(cap, dem) for cap, dem in zip(reuse_capacity, reuse_demand_topcos)]
                    reuse_remaining_after_topcos = [max(cap - sold, 0.0) for cap, sold in zip(reuse_capacity, reuse_sold_topcos)]
                    reuse_sold_construction = [min(rem, dem) for rem, dem in zip(reuse_remaining_after_topcos, construction_water_demand)]
                    reuse_overflow_agri = [max(cap - s1 - s2, 0.0) for cap, s1, s2 in zip(reuse_capacity, reuse_sold_topcos, reuse_sold_construction)]

                    # Honeysucker and agri rates
                    _srv_transport_nwl = 28.0 * 10.0
                    _srv_transport_gov = 28.0 * 100.0
                    _srv_truck_cap = 10.0
                    _srv_saving_pct = 40.0
                    _honeysucker_base = max((_srv_transport_gov - _srv_transport_nwl) / _srv_truck_cap * (_srv_saving_pct / 100.0), 0.0)
                    _agri_base = 37.70
                    _srv_gf = 1.077

                    _rev_sewage_gf = []
                    _rev_sewage_bf = []
                    _rev_reuse_gf = []
                    _rev_reuse_con = []
                    _rev_reuse_agri = []

                    for _rm in _rev_months:
                        if _rm < 18:
                            _v_sew_gf = _v_sew_bf = _v_reu_gf = _v_reu_con = _v_reu_agri = 0.0
                        elif _rm <= 72:
                            _idx = months.index(_rm)
                            _v_sew_gf = sewage_sold_topcos[_idx]
                            _v_sew_bf = sewage_overflow_brownfield[_idx]
                            _v_reu_gf = reuse_sold_topcos[_idx]
                            _v_reu_con = reuse_sold_construction[_idx]
                            _v_reu_agri = reuse_overflow_agri[_idx]
                        else:
                            _v_sew_gf = sewage_sold_topcos[-1]
                            _v_sew_bf = sewage_overflow_brownfield[-1]
                            _v_reu_gf = reuse_sold_topcos[-1]
                            _v_reu_con = reuse_sold_construction[-1]
                            _v_reu_agri = reuse_overflow_agri[-1]

                        _sew_r = sewage_rate_2025 * (growth_factor ** (_rm / 12.0))
                        _wat_r = water_rate_2025 * (growth_factor ** (_rm / 12.0))
                        _hon_r = _honeysucker_base * (_srv_gf ** (_rm / 12.0))
                        _agr_r = _agri_base * (growth_factor ** (_rm / 12.0))

                        _factor = _kl_per_mld * _days_per_half
                        _rev_sewage_gf.append(_v_sew_gf * _factor * _sew_r / FX_RATE)
                        _rev_sewage_bf.append(_v_sew_bf * _factor * _hon_r / FX_RATE)
                        _rev_reuse_gf.append(_v_reu_gf * _factor * _wat_r / FX_RATE)
                        _rev_reuse_con.append(_v_reu_con * _factor * _wat_r / FX_RATE)
                        _rev_reuse_agri.append(_v_reu_agri * _factor * _agr_r / FX_RATE)

                    _rev_total = [a + b + c + d + e for a, b, c, d, e in
                                  zip(_rev_sewage_gf, _rev_sewage_bf, _rev_reuse_gf, _rev_reuse_con, _rev_reuse_agri)]

                    fig_rev_mix = go.Figure()
                    fig_rev_mix.add_trace(go.Bar(x=_rev_labels, y=_rev_sewage_gf, name="Sewage — GreenField", marker_color="#2563EB"))
                    fig_rev_mix.add_trace(go.Bar(x=_rev_labels, y=_rev_sewage_bf, name="Sewage — BrownField", marker_color="#93C5FD"))
                    fig_rev_mix.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_gf, name="Re-use — GreenField", marker_color="#059669"))
                    fig_rev_mix.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_con, name="Re-use — Construction", marker_color="#F59E0B"))
                    fig_rev_mix.add_trace(go.Bar(x=_rev_labels, y=_rev_reuse_agri, name="Re-use — Agri", marker_color="#A3E635"))
                    fig_rev_mix.update_layout(
                        barmode="stack",
                        height=350,
                        yaxis_title="EUR",
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                    )
                    st.plotly_chart(fig_rev_mix, use_container_width=True)
                    st.caption("Semi-annual revenue by segment. BrownField provides early high-margin revenue before GreenField ramps up.")

                with _col_cf_ops:
                    # --- Cash from Ops vs Debt Service ---
                    st.subheader(f"{_gn_offset + 7}. Cash from Ops vs Debt Service")

                    fig_cf_ds = go.Figure()
                    # Left bar: Cash from Ops (EBITDA - Tax)
                    fig_cf_ds.add_trace(go.Bar(
                        x=_years, y=[a['cf_ops'] for a in _sub_annual],
                        name='Cash from Ops', marker_color='#10B981',
                        offsetgroup='ops', legendgroup='Operations'
                    ))
                    # Right bar: Debt Service stacked (Interest + Principal)
                    fig_cf_ds.add_trace(go.Bar(
                        x=_years, y=[a['cf_ie'] for a in _sub_annual],
                        name='Interest', marker_color='#EF4444',
                        offsetgroup='ds', legendgroup='Debt Service'
                    ))
                    fig_cf_ds.add_trace(go.Bar(
                        x=_years, y=[a['cf_pr'] for a in _sub_annual],
                        name='Principal', marker_color='#6366F1',
                        offsetgroup='ds', legendgroup='Debt Service'
                    ))
                    # DSCR annotations on top
                    for _ci, _yr in enumerate(_years):
                        _ds_val = _sub_annual[_ci]['cf_ds']
                        _ops_val = _sub_annual[_ci]['cf_ops']
                        _bar_top = max(_ops_val, _ds_val) if (_ops_val > 0 or _ds_val > 0) else 0
                        if _ds_val > 0:
                            _dscr = _ops_val / _ds_val
                            fig_cf_ds.add_annotation(
                                x=_yr, y=_bar_top, text=f"<b>{_dscr:.2f}x</b>",
                                showarrow=False, yshift=18,
                                font=dict(size=11, color='#16A34A' if _dscr >= 1.3 else '#DC2626')
                            )
                        elif _ops_val > 0:
                            fig_cf_ds.add_annotation(
                                x=_yr, y=_bar_top, text="<b>No DS</b>",
                                showarrow=False, yshift=18, font=dict(size=10, color='#6B7280')
                            )
                    fig_cf_ds.update_layout(
                        barmode='stack', height=350,
                        margin=dict(l=10, r=10, t=40, b=10),
                        xaxis=dict(dtick=1), yaxis_title='EUR',
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_cf_ds, use_container_width=True)
                    st.caption("DSCR = Cash from Ops (EBITDA - Tax) / Total Debt Service. Green = above 1.30x covenant.")

                st.divider()

    # --- SENSITIVITY ---
    if "Sensitivity" in _tab_map:
        with _tab_map["Sensitivity"]:
            st.header("Sensitivity Analysis")

            if entity_key != "nwl":
                st.info(f"Sensitivity analysis is currently available for NWL only. "
                        f"{name} sensitivity scenarios will be added in a future release.")
            else:
                # =============================================================
                # NWL SENSITIVITY ENGINE
                # =============================================================
                _sens_cfg = operations_config.get("nwl", {})
                _sens_gf = _sens_cfg.get("greenfield", {})
                _sens_bf = _sens_cfg.get("brownfield", {})
                _sens_ramp = _sens_cfg.get("on_ramp", {})
                _sens_srv = _sens_cfg.get("sewerage_revenue_sharing", {})
                _sens_om = _sens_cfg.get("om", {})
                _sens_pw = _sens_cfg.get("power", {})
                _sens_rent = _sens_cfg.get("coe_rent", {})
                _sens_bulk = _sens_cfg.get("bulk_services", {})

                def _nwl_sens_calc(
                    sewage_rate_factor=1.0,
                    water_rate_factor=1.0,
                    piped_delay_months=0,
                    ramp_delay_months=0,
                    honey_share_pct=40.0,
                ):
                    """Recompute NWL revenue/EBITDA with sensitivity overrides."""
                    months_semi = list(range(6, 121, 6))

                    # --- Capacity ramp (with optional delay) ---
                    ramp_rows = _sens_ramp.get("rows", [])
                    cap_pts = [(int(r.get("period_months", 0)), r.get("capacity_available_mld"))
                               for r in ramp_rows]
                    cap_pts = [(m, float(v)) for m, v in cap_pts if v is not None]
                    if ramp_delay_months > 0:
                        cap_pts = [(m + ramp_delay_months, v) for m, v in cap_pts]
                    if not any(m <= 6 for m, _ in cap_pts):
                        cap_pts.append((6, 0.0))
                    if not any(m == 12 for m, _ in cap_pts):
                        cap_pts.append((12, 0.0))
                    cap_pts = sorted(cap_pts, key=lambda x: x[0])
                    cap_m = [m for m, _ in cap_pts]
                    cap_v = [v for _, v in cap_pts]
                    sewage_cap = _extrapolate_piecewise_linear(cap_m, cap_v, months_semi, floor=0.0)

                    # --- Demand schedules ---
                    demand_months_base = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
                    piped_base = [float(x) for x in _sens_gf.get("piped_sewage_topcos_mld", [0.0] * 10)]
                    construction_base = [float(x) for x in _sens_gf.get("construction_water_demand_topcos_mld", [0.0] * 10)]
                    latent_base = [float(x) for x in _sens_bf.get("latent_demand_quantified", [0.0] * 10)]

                    # Piped delay: shift demand months right (less piped demand earlier)
                    piped_months_shifted = [m + piped_delay_months for m in demand_months_base]

                    piped_demand = _extrapolate_piecewise_linear(piped_months_shifted, piped_base, months_semi, floor=0.0)
                    construction_demand = _extrapolate_piecewise_linear(demand_months_base, construction_base, months_semi, floor=0.0)
                    latent_demand = _extrapolate_piecewise_linear(demand_months_base, latent_base, months_semi, floor=0.0)

                    # --- Volume calculations ---
                    sewage_sold = [min(c, d) for c, d in zip(sewage_cap, piped_demand)]
                    overflow_bf = [max(c - s, 0.0) for c, s in zip(sewage_cap, sewage_sold)]
                    brine_pct = float(_sens_gf.get("brine_pct_default", 10.0))
                    reuse_ratio = float(_sens_gf.get("reuse_ratio_default", 0.80))
                    reuse_cap = [c * (1.0 - brine_pct / 100.0) for c in sewage_cap]
                    reuse_topcos_dem = [s * reuse_ratio for s in sewage_sold]
                    reuse_sold_topcos = [min(c, d) for c, d in zip(reuse_cap, reuse_topcos_dem)]
                    reuse_after = [max(c - s, 0.0) for c, s in zip(reuse_cap, reuse_sold_topcos)]
                    reuse_sold_constr = [min(r, d) for r, d in zip(reuse_after, construction_demand)]
                    reuse_overflow_agri = [max(c - s1 - s2, 0.0) for c, s1, s2
                                           in zip(reuse_cap, reuse_sold_topcos, reuse_sold_constr)]
                    bf_served = [min(o, d) for o, d in zip(overflow_bf, latent_demand)]

                    # --- Rates with tariff sensitivity ---
                    growth = 1.0 + float(_sens_gf.get("annual_growth_pct_default", 7.7)) / 100.0
                    base_sewage = float(_sens_gf.get("sewage_rate_2025_r_per_kl", 46.40)) * sewage_rate_factor
                    base_water = float(_sens_gf.get("water_rate_2025_r_per_kl", 62.05)) * water_rate_factor
                    agri_base = float(_sens_bf.get("agri_base_2025_r_per_kl", 37.70))
                    sewage_r = [base_sewage * (growth ** (m / 12.0)) for m in months_semi]
                    water_r = [base_water * (growth ** (m / 12.0)) for m in months_semi]
                    agri_r = [agri_base * (growth ** (m / 12.0)) for m in months_semi]

                    # --- Honeysucker rate with sharing override ---
                    transport_km = float(_sens_srv.get("transport_r_per_km_default", 28.0))
                    truck_cap = max(float(_sens_srv.get("truck_capacity_m3_default", 10.0)), 1.0)
                    nwl_dist = float(_sens_srv.get("nwl_roundtrip_km_default", 10.0))
                    gov_dist = float(_sens_srv.get("gov_roundtrip_km_default", 100.0))
                    saving_per_m3 = (gov_dist - nwl_dist) * transport_km / truck_cap
                    market_price = max(saving_per_m3 * (honey_share_pct / 100.0), 0.0)
                    srv_growth = 1.0 + float(_sens_srv.get("growth_pct_default", 7.7)) / 100.0
                    honey_r = [market_price * (srv_growth ** (m / 12.0)) for m in months_semi]

                    # --- Revenue (semi-annual, then aggregate to annual) ---
                    hyk = 1000.0 * 365.0 / 2.0  # half-year KL per MLD
                    rev_gf_s = [v * hyk * p for v, p in zip(sewage_sold, sewage_r)]
                    rev_bf_s = [v * hyk * p for v, p in zip(bf_served, honey_r)]
                    rev_reuse = [v * hyk * p for v, p in zip(reuse_sold_topcos, water_r)]
                    rev_constr = [v * hyk * p for v, p in zip(reuse_sold_constr, water_r)]
                    rev_agri = [v * hyk * p for v, p in zip(reuse_overflow_agri, agri_r)]

                    # Bulk services (unaffected by sensitivity)
                    bulk_yr = [0.0] * 10
                    for row in _sens_bulk.get("rows", []):
                        amt = float(row.get("price_zar", 0.0))
                        rp = max(float(row.get("receipt_period", 12.0)), 0.0)
                        if amt <= 0:
                            continue
                        if rp == 0.0:
                            bi = _month_to_year_idx(12)
                            if bi is not None:
                                bulk_yr[bi] += amt
                            continue
                        for mi in range(1, 121):
                            if 13 <= mi < 13 + rp:
                                bi = _month_to_year_idx(mi)
                                if bi is not None:
                                    bulk_yr[bi] += amt / rp

                    # O&M cost
                    om_fee = float(_sens_om.get("flat_fee_per_month_zar", 0.0))
                    om_idx = float(_sens_om.get("annual_indexation_pa", 0.0))
                    om_start = int(_sens_om.get("opex_start_month", 12))
                    om_yr = [0.0] * 10
                    for mi in range(1, 121):
                        yi = _month_to_year_idx(mi)
                        if yi is None or mi < om_start:
                            continue
                        om_yr[yi] += om_fee * ((1.0 + om_idx) ** ((mi - om_start) / 12.0))

                    # Power cost
                    pw_kwh = float(_sens_pw.get("kwh_per_m3", 0.4))
                    esk_base = float(_sens_pw.get("eskom_base_rate_r_per_kwh", 2.81))
                    ic_disc = float(_sens_pw.get("ic_discount_pct", 10.0))
                    pw_rate = esk_base * (1.0 - ic_disc / 100.0)
                    pw_esc = float(_sens_pw.get("annual_escalation_pct", 10.0)) / 100.0
                    pw_start = int(_sens_pw.get("start_month", 18))
                    pw_yr = [0.0] * 10
                    for mi in range(1, 121):
                        yi = _month_to_year_idx(mi)
                        if yi is None or mi < pw_start:
                            continue
                        c_mld = 0.0
                        for ci in range(len(cap_m) - 1):
                            if cap_m[ci] <= mi <= cap_m[ci + 1]:
                                frac = (mi - cap_m[ci]) / max(cap_m[ci + 1] - cap_m[ci], 1)
                                c_mld = cap_v[ci] + frac * (cap_v[ci + 1] - cap_v[ci])
                                break
                        else:
                            if mi >= cap_m[-1]:
                                c_mld = cap_v[-1]
                        vol_m3 = c_mld * 1000.0
                        rate_i = pw_rate * ((1.0 + pw_esc) ** ((mi - pw_start) / 12.0))
                        pw_yr[yi] += vol_m3 * pw_kwh * rate_i * 30.44

                    # CoE rent
                    rent_om_pct = float(_sens_rent.get("om_overhead_pct", 2.0))
                    _r_monthly, _, _, _ = compute_coe_rent_monthly_eur(rent_om_pct)
                    _r_monthly_zar = _r_monthly * FX_RATE
                    rent_esc = float(_sens_rent.get("annual_escalation_pct", 5.0)) / 100.0
                    rent_start = int(_sens_rent.get("start_month", 24))
                    rent_yr = [0.0] * 10
                    for mi in range(1, 121):
                        yi = _month_to_year_idx(mi)
                        if yi is None or mi < rent_start:
                            continue
                        rent_yr[yi] += _r_monthly_zar * ((1.0 + rent_esc) ** ((mi - rent_start) / 12.0))

                    # --- Aggregate to annual EUR dicts ---
                    month_to_idx = {m: i for i, m in enumerate(months_semi)}
                    result = []
                    for yi in range(10):
                        m1, m2 = 6 + yi * 12, 12 + yi * 12
                        si = [month_to_idx[m1], month_to_idx[m2]] if m1 in month_to_idx and m2 in month_to_idx else []

                        def _ys(arr, _si=si):
                            return sum(arr[i] for i in _si) if _si else 0.0

                        gfs = _ys(rev_gf_s) / FX_RATE
                        bfs = _ys(rev_bf_s) / FX_RATE
                        reu = _ys(rev_reuse) / FX_RATE
                        con = _ys(rev_constr) / FX_RATE
                        agr = _ys(rev_agri) / FX_RATE
                        blk = bulk_yr[yi] / FX_RATE
                        om_e = om_yr[yi] / FX_RATE
                        pw_e = pw_yr[yi] / FX_RATE
                        rn_e = rent_yr[yi] / FX_RATE
                        rev = gfs + bfs + reu + con + agr + blk
                        ebitda = rev - om_e - pw_e - rn_e
                        result.append({
                            'year': yi + 1,
                            'rev_greenfield_sewage': gfs,
                            'rev_brownfield_sewage': bfs,
                            'rev_reuse': reu,
                            'rev_construction': con,
                            'rev_agri': agr,
                            'rev_bulk': blk,
                            'rev_total': rev,
                            'om_cost': om_e,
                            'power_cost': pw_e,
                            'rent_cost': rn_e,
                            'ebitda': ebitda,
                        })
                    return result

                # --- Base case from the full model ---
                _base = _sub_annual
                _base_rev_10 = sum(a.get('rev_total', 0) for a in _base)
                _base_ebitda_10 = sum(a['ebitda'] for a in _base)
                _dscr_vals = [a['cf_ops'] / a['cf_ds'] if a.get('cf_ds', 0) > 0 else None for a in _base]
                _dscr_valid = [d for d in _dscr_vals if d is not None]
                _avg_dscr = sum(_dscr_valid) / len(_dscr_valid) if _dscr_valid else 0
                _dsra_y10 = _base[-1].get('dsra_bal', 0)

                st.caption("NWL -- Impact of key operational variables on revenue, EBITDA, and debt service coverage")

                # --- Base case metrics ---
                _bm1, _bm2, _bm3, _bm4 = st.columns(4)
                _bm1.metric("10-Yr Revenue", f"EUR {_base_rev_10:,.0f}")
                _bm2.metric("10-Yr EBITDA", f"EUR {_base_ebitda_10:,.0f}")
                _bm3.metric("Avg DSCR", f"{_avg_dscr:.2f}x")
                _bm4.metric("DSRA Balance Y10", f"EUR {_dsra_y10:,.0f}")

                st.divider()

                # =============================================================
                # SCENARIO 1: Tariff Sensitivity
                # =============================================================
                with st.container(border=True):
                    st.subheader("1. Tariff Sensitivity -- Joburg-Set Prices")
                    st.markdown(
                        "Piped sewage and reuse water tariffs are **regulated by Joburg Water**. "
                        "The base case uses R46.40/KL (sewage) and R62.05/KL (water) with 7.7% annual growth. "
                        "This scenario shows the impact of tariff changes on 10-year EBITDA."
                    )

                    _tc1, _tc2 = st.columns(2)
                    with _tc1:
                        _tariff_sew = st.slider(
                            "Sewage tariff adjustment",
                            min_value=-30, max_value=30, value=0, step=5,
                            format="%+d%%", key="sens_tariff_sew"
                        )
                    with _tc2:
                        _tariff_wat = st.slider(
                            "Water tariff adjustment",
                            min_value=-30, max_value=30, value=0, step=5,
                            format="%+d%%", key="sens_tariff_wat"
                        )

                    _sens_tariff = _nwl_sens_calc(
                        sewage_rate_factor=1.0 + _tariff_sew / 100.0,
                        water_rate_factor=1.0 + _tariff_wat / 100.0,
                    )
                    _adj_ebitda_10 = sum(r['ebitda'] for r in _sens_tariff)
                    _delta_ebitda = _adj_ebitda_10 - _base_ebitda_10

                    _tm1, _tm2, _tm3 = st.columns(3)
                    _tm1.metric("Base 10-Yr EBITDA", f"EUR {_base_ebitda_10:,.0f}")
                    _tm2.metric("Adjusted 10-Yr EBITDA", f"EUR {_adj_ebitda_10:,.0f}")
                    _tm3.metric("Delta", f"EUR {_delta_ebitda:+,.0f}",
                                delta=f"{_delta_ebitda / max(abs(_base_ebitda_10), 1) * 100:+.1f}%")

                    fig_t = go.Figure()
                    fig_t.add_trace(go.Bar(
                        x=_years, y=[a['ebitda'] for a in _base],
                        name='Base Case', marker_color='#10B981', opacity=0.5))
                    fig_t.add_trace(go.Bar(
                        x=_years, y=[r['ebitda'] for r in _sens_tariff],
                        name=f'Tariff {_tariff_sew:+d}% / {_tariff_wat:+d}%',
                        marker_color='#3B82F6'))
                    fig_t.update_layout(
                        barmode='group', height=350, yaxis_title='EBITDA (EUR)',
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                    st.plotly_chart(fig_t, use_container_width=True)

                # =============================================================
                # SCENARIO 2: Delayed Capacity On-ramp
                # =============================================================
                with st.container(border=True):
                    st.subheader("2. Delayed Capacity On-ramp")
                    st.markdown(
                        "The plant reaches full capacity (1.90 MLD) at M30 in the base case. "
                        "Construction or commissioning delays shift the entire capacity ramp-up curve, "
                        "reducing revenue in earlier years."
                    )

                    _ramp_delay = st.select_slider(
                        "Capacity ramp-up delay",
                        options=[0, 6, 12, 18],
                        format_func=lambda x: f"+{x} months" if x > 0 else "Base case",
                        key="sens_ramp_delay"
                    )

                    _sens_ramp_results = {}
                    for _rd in [0, 6, 12, 18]:
                        _sens_ramp_results[_rd] = _nwl_sens_calc(ramp_delay_months=_rd)

                    _ramp_sel = _sens_ramp_results[_ramp_delay]
                    _ramp_ebitda = sum(r['ebitda'] for r in _ramp_sel)
                    _ramp_delta = _ramp_ebitda - _base_ebitda_10

                    _rm1, _rm2, _rm3 = st.columns(3)
                    _rm1.metric("Base 10-Yr EBITDA", f"EUR {_base_ebitda_10:,.0f}")
                    _rm2.metric(f"Delayed +{_ramp_delay}m EBITDA", f"EUR {_ramp_ebitda:,.0f}")
                    _rm3.metric("Delta", f"EUR {_ramp_delta:+,.0f}",
                                delta=f"{_ramp_delta / max(abs(_base_ebitda_10), 1) * 100:+.1f}%")

                    fig_r = go.Figure()
                    _ramp_colors = {0: '#10B981', 6: '#F59E0B', 12: '#EF4444', 18: '#7C3AED'}
                    for _rd, _rdata in _sens_ramp_results.items():
                        _lbl = "Base" if _rd == 0 else f"+{_rd}m delay"
                        fig_r.add_trace(go.Scatter(
                            x=_years, y=[r['ebitda'] for r in _rdata],
                            mode='lines+markers', name=_lbl,
                            line=dict(color=_ramp_colors[_rd], width=3 if _rd == _ramp_delay else 1),
                            opacity=1.0 if _rd == _ramp_delay else 0.4))
                    fig_r.update_layout(
                        height=350, yaxis_title='EBITDA (EUR)',
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                    st.plotly_chart(fig_r, use_container_width=True)

                # =============================================================
                # SCENARIO 3: Delayed Piped Water On-ramp
                # =============================================================
                with st.container(border=True):
                    st.subheader("3. Delayed Piped Water On-ramp")
                    st.markdown(
                        "**Counter-intuitively**, slower piped sewage uptake **increases** total revenue. "
                        "When piped connections lag, treated capacity overflows to BrownField (honeysucker) service "
                        "at **R100.80/KL** -- more than double the piped rate of R46.40/KL. "
                        "The plant runs at the same capacity either way; only the revenue mix changes."
                    )

                    _piped_delay = st.select_slider(
                        "Piped water demand delay",
                        options=[0, 6, 12, 18, 24],
                        format_func=lambda x: f"+{x} months" if x > 0 else "Base case",
                        key="sens_piped_delay"
                    )

                    _sens_piped_results = {}
                    for _pd in [0, 6, 12, 18, 24]:
                        _sens_piped_results[_pd] = _nwl_sens_calc(piped_delay_months=_pd)

                    _piped_sel = _sens_piped_results[_piped_delay]
                    _piped_rev = sum(r['rev_total'] for r in _piped_sel)
                    _piped_ebitda = sum(r['ebitda'] for r in _piped_sel)
                    _piped_delta = _piped_ebitda - _base_ebitda_10

                    _pm1, _pm2, _pm3 = st.columns(3)
                    _pm1.metric("Base 10-Yr EBITDA", f"EUR {_base_ebitda_10:,.0f}")
                    _pm2.metric(f"Delayed +{_piped_delay}m EBITDA", f"EUR {_piped_ebitda:,.0f}")
                    _pm3.metric("Delta", f"EUR {_piped_delta:+,.0f}",
                                delta=f"{_piped_delta / max(abs(_base_ebitda_10), 1) * 100:+.1f}%")

                    # Stacked bar: GreenField vs BrownField revenue by year
                    fig_p = go.Figure()
                    fig_p.add_trace(go.Bar(
                        x=_years, y=[r['rev_greenfield_sewage'] for r in _piped_sel],
                        name='GreenField Sewage (piped)', marker_color='#10B981'))
                    fig_p.add_trace(go.Bar(
                        x=_years, y=[r['rev_brownfield_sewage'] for r in _piped_sel],
                        name='BrownField Sewage (honeysucker)', marker_color='#F59E0B'))
                    fig_p.add_trace(go.Bar(
                        x=_years, y=[r['rev_reuse'] + r['rev_construction'] + r['rev_agri'] for r in _piped_sel],
                        name='Reuse + Construction + Agri', marker_color='#6EE7B7'))
                    # Base EBITDA line for comparison
                    fig_p.add_trace(go.Scatter(
                        x=_years, y=[a['ebitda'] for a in _base],
                        mode='lines+markers', name='Base EBITDA',
                        line=dict(color='#6366F1', width=2, dash='dash')))
                    fig_p.update_layout(
                        barmode='stack', height=380, yaxis_title='EUR',
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                    st.plotly_chart(fig_p, use_container_width=True)

                    # Explanatory comparison table
                    _base_gf_10 = sum(a.get('rev_greenfield_sewage', 0) for a in _base)
                    _base_bf_10 = sum(a.get('rev_brownfield_sewage', 0) for a in _base)
                    _adj_gf_10 = sum(r['rev_greenfield_sewage'] for r in _piped_sel)
                    _adj_bf_10 = sum(r['rev_brownfield_sewage'] for r in _piped_sel)
                    _comp_df = pd.DataFrame({
                        'Stream': ['GreenField Sewage', 'BrownField Sewage', 'Total Sewage'],
                        'Base Case': [_base_gf_10, _base_bf_10, _base_gf_10 + _base_bf_10],
                        f'+{_piped_delay}m Delay': [_adj_gf_10, _adj_bf_10, _adj_gf_10 + _adj_bf_10],
                        'Delta': [_adj_gf_10 - _base_gf_10, _adj_bf_10 - _base_bf_10,
                                  (_adj_gf_10 + _adj_bf_10) - (_base_gf_10 + _base_bf_10)],
                    })
                    render_table(_comp_df, formats={
                        'Base Case': 'EUR {:,.0f}',
                        f'+{_piped_delay}m Delay': 'EUR {:,.0f}',
                        'Delta': 'EUR {:+,.0f}',
                    })

                # =============================================================
                # SCENARIO 4: Honeysucker Revenue Sharing
                # =============================================================
                with st.container(border=True):
                    st.subheader("4. Revenue Sharing -- Basilicus x Titanium JV")

                    _jv_l1, _jv_l2, _jv_l3 = st.columns([0.15, 0.15, 0.70])
                    with _jv_l1:
                        _bas_logo_s = LOGO_DIR / ENTITY_LOGOS.get("basilicus", "")
                        if _bas_logo_s.exists():
                            _render_logo_dark_bg(_bas_logo_s, width=72)
                    with _jv_l2:
                        _tit_logo_s = LOGO_DIR / ENTITY_LOGOS.get("titanium", "")
                        if _tit_logo_s.exists():
                            st.image(str(_tit_logo_s), width=72)
                    with _jv_l3:
                        st.markdown(
                            "BrownField revenue depends on the **profit-sharing margin** with the "
                            "Basilicus/Titanium honeysucker JV. The base rate of R100.80/KL "
                            "represents 40% of the transport cost saving passed to the market. "
                            "A lower sharing percentage means higher NWL margins per trip."
                        )

                    _honey_pct = st.slider(
                        "Market sharing percentage",
                        min_value=20, max_value=60, value=40, step=5,
                        format="%d%%", key="sens_honey_pct",
                        help="Percentage of transport saving passed to market (lower = higher NWL margin)"
                    )

                    _sens_honey_results = {}
                    for _hp in range(20, 65, 10):
                        _sens_honey_results[_hp] = _nwl_sens_calc(honey_share_pct=float(_hp))

                    _honey_sel = _sens_honey_results.get(_honey_pct, _nwl_sens_calc(honey_share_pct=float(_honey_pct)))
                    _honey_bf_10 = sum(r['rev_brownfield_sewage'] for r in _honey_sel)
                    _honey_ebitda = sum(r['ebitda'] for r in _honey_sel)
                    _honey_delta = _honey_ebitda - _base_ebitda_10

                    # Show the effective honeysucker rate
                    _eff_transport_km = float(_sens_srv.get("transport_r_per_km_default", 28.0))
                    _eff_truck = max(float(_sens_srv.get("truck_capacity_m3_default", 10.0)), 1.0)
                    _eff_saving = (float(_sens_srv.get("gov_roundtrip_km_default", 100.0))
                                   - float(_sens_srv.get("nwl_roundtrip_km_default", 10.0))) * _eff_transport_km / _eff_truck
                    _eff_rate = _eff_saving * (_honey_pct / 100.0)

                    _hm1, _hm2, _hm3, _hm4 = st.columns(4)
                    _hm1.metric("Sharing %", f"{_honey_pct}%")
                    _hm2.metric("Honeysucker Rate (Y1)", f"R {_eff_rate:,.2f}/KL")
                    _hm3.metric("10-Yr BF Revenue", f"EUR {_honey_bf_10:,.0f}")
                    _hm4.metric("Delta EBITDA", f"EUR {_honey_delta:+,.0f}",
                                delta=f"{_honey_delta / max(abs(_base_ebitda_10), 1) * 100:+.1f}%")

                    fig_h = go.Figure()
                    _honey_colors = {20: '#10B981', 30: '#34D399', 40: '#3B82F6', 50: '#F59E0B', 60: '#EF4444'}
                    for _hp, _hdata in sorted(_sens_honey_results.items()):
                        fig_h.add_trace(go.Bar(
                            x=_years, y=[r['rev_brownfield_sewage'] for r in _hdata],
                            name=f'{_hp}% sharing',
                            marker_color=_honey_colors.get(_hp, '#6366F1'),
                            opacity=1.0 if _hp == _honey_pct else 0.3))
                    fig_h.update_layout(
                        barmode='group', height=350, yaxis_title='BrownField Revenue (EUR)',
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                    st.plotly_chart(fig_h, use_container_width=True)

                st.divider()

                # =============================================================
                # TORNADO CHART -- Impact on 10-Year EBITDA
                # =============================================================
                st.subheader("Sensitivity Tornado -- Impact on 10-Year EBITDA")
                st.markdown(
                    "Each bar shows the change in cumulative 10-year EBITDA when a single variable "
                    "is moved from its downside to its upside value, holding all others at base case."
                )

                _tornado_vars = [
                    ("Tariff +20%", "Tariff -20%",
                     sum(r['ebitda'] for r in _nwl_sens_calc(sewage_rate_factor=1.20, water_rate_factor=1.20)),
                     sum(r['ebitda'] for r in _nwl_sens_calc(sewage_rate_factor=0.80, water_rate_factor=0.80))),
                    ("Capacity delay +0m", "Capacity delay +12m",
                     _base_ebitda_10,
                     sum(r['ebitda'] for r in _nwl_sens_calc(ramp_delay_months=12))),
                    ("Piped delay +12m", "Piped delay +0m",
                     sum(r['ebitda'] for r in _nwl_sens_calc(piped_delay_months=12)),
                     _base_ebitda_10),
                    ("Sharing 30%", "Sharing 50%",
                     sum(r['ebitda'] for r in _nwl_sens_calc(honey_share_pct=30.0)),
                     sum(r['ebitda'] for r in _nwl_sens_calc(honey_share_pct=50.0))),
                ]

                # Sort by total spread (largest first)
                _tornado_vars.sort(key=lambda t: abs(t[2] - t[3]), reverse=True)

                _t_labels = []
                _t_up_vals = []
                _t_down_vals = []
                for _up_lbl, _down_lbl, _up_v, _down_v in _tornado_vars:
                    if "Tariff" in _up_lbl:
                        _label = "Tariff"
                    elif "Capacity" in _up_lbl:
                        _label = "Capacity Delay"
                    elif "Piped" in _up_lbl:
                        _label = "Piped Delay"
                    elif "Sharing" in _up_lbl:
                        _label = "Rev. Sharing"
                    else:
                        _label = _up_lbl
                    _t_labels.append(_label)
                    _t_up_vals.append(_up_v - _base_ebitda_10)
                    _t_down_vals.append(_down_v - _base_ebitda_10)

                fig_tornado = go.Figure()
                fig_tornado.add_trace(go.Bar(
                    y=_t_labels, x=_t_up_vals,
                    name='Upside', orientation='h',
                    marker_color='#10B981', text=[f"EUR {v:+,.0f}" for v in _t_up_vals],
                    textposition='outside'))
                fig_tornado.add_trace(go.Bar(
                    y=_t_labels, x=_t_down_vals,
                    name='Downside', orientation='h',
                    marker_color='#EF4444', text=[f"EUR {v:+,.0f}" for v in _t_down_vals],
                    textposition='outside'))
                fig_tornado.add_vline(x=0, line_width=2, line_color='#374151')
                fig_tornado.update_layout(
                    barmode='relative', height=300,
                    xaxis_title='Change in 10-Year EBITDA (EUR)',
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5))
                st.plotly_chart(fig_tornado, use_container_width=True)

    # --- SECURITY ---
    if "Security" in _tab_map:
        with _tab_map["Security"]:
            st.header("Security Package")
            security = load_config("security")
            sub_sec = security['subsidiaries'].get(entity_key, {})

            if not sub_sec:
                st.info("Security data not available for this entity.")
            else:
                if sub_sec.get('carve_out'):
                    pass  # LanRED: either independently underwritten or bank-to-bank swap — shown in L2

                # ── NWL-specific: Exposure Reduction & ECA Argument ──
                if entity_key == "nwl":
                    _sec_nwl_md = load_content_md("SECURITY_CONTENT.md").get("nwl", "")
                    if _sec_nwl_md:
                        # Render the Exposure Narrative section
                        for _sect in _sec_nwl_md.split("\n### "):
                            if _sect.startswith("Exposure Narrative"):
                                st.markdown(_sect.partition("\n")[2].strip())
                                break
                    else:
                        st.markdown(
                            "NWL is the **primary operating asset** in the IIC facility. "
                            "Through grant-funded prepayments (DTIC + GEPF) and the Creation Capital DSRA, "
                            "IIC's **actual credit exposure only begins at month 36** "
                            "— and at a **substantially lower balance** than the NWL Senior IC loan."
                        )

                    # ── Build NWL Senior IC schedule to extract milestone balances ──
                    _sec_sr_cfg = structure['sources']['senior_debt']
                    _sec_sr_rate = _sec_sr_cfg['interest']['rate'] + INTERCOMPANY_MARGIN
                    _sec_sr_repayments = _sec_sr_cfg['repayments']
                    _sec_sr_principal = entity_data['senior_portion']
                    _sec_total_sr = sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
                    _sec_sr_detail = financing['loan_detail']['senior']
                    _sec_sr_drawdowns = _sec_sr_detail['drawdown_schedule']
                    _sec_sr_periods = [-4, -3, -2, -1]
                    _sec_prepay_raw = _sec_sr_detail.get('prepayment_periods', {})
                    _sec_prepay_alloc = _sec_sr_detail.get('prepayment_allocation', {})
                    _sec_nwl_prepay_pct = _sec_prepay_alloc.get('nwl', 0.0)
                    _sec_sr_prepayments = {k: v * _sec_nwl_prepay_pct for k, v in _sec_prepay_raw.items()} if _sec_nwl_prepay_pct > 0 else None

                    # DSRA sizing (facility level, allocated 100% to NWL)
                    _sec_fac_bal = (_sec_sr_detail['loan_drawdown_total']
                                   + _sec_sr_detail['rolled_up_interest_idc']
                                   - _sec_sr_detail['grant_proceeds_to_early_repayment']
                                   - _sec_sr_detail['gepf_bulk_proceeds'])
                    _sec_fac_rate = _sec_sr_cfg['interest']['rate']
                    _sec_fac_num = _sec_sr_cfg['repayments']
                    _sec_fac_p = _sec_fac_bal / _sec_fac_num
                    _sec_fac_i_m24 = _sec_fac_bal * _sec_fac_rate / 2
                    _sec_dsra_total = 2 * (_sec_fac_p + _sec_fac_i_m24)

                    _sec_sr_schedule = build_simple_ic_schedule(
                        _sec_sr_principal, _sec_total_sr, _sec_sr_repayments, _sec_sr_rate,
                        _sec_sr_drawdowns, _sec_sr_periods, _sec_sr_prepayments,
                        dsra_amount=_sec_dsra_total
                    )

                    # Extract milestone balances
                    _bal_by_month = {r['Month']: r for r in _sec_sr_schedule}
                    _bal_m0 = 0.0
                    # End of construction (M18) = closing of last drawdown period
                    _construction_rows = [r for r in _sec_sr_schedule if r['Period'] < 0 or (r['Period'] == 0 and r['Month'] <= 18)]
                    _drawdown_rows = [r for r in _sec_sr_schedule if r['Draw Down'] > 0 or r['Interest'] > 0 and r['Principle'] == 0]
                    # Balance at M18 (end of drawdown phase, before repayments)
                    _last_drawdown = [r for r in _sec_sr_schedule if r['Month'] <= 18]
                    _bal_m18 = _last_drawdown[-1]['Closing'] if _last_drawdown else 0.0
                    # Total drawdowns (sum of all positive drawdowns)
                    _total_draws = sum(r['Draw Down'] for r in _sec_sr_schedule if r['Draw Down'] > 0)
                    # Total IDC capitalised
                    _total_idc = sum(r['Interest'] for r in _sec_sr_schedule if r['Principle'] == 0 and r['Month'] <= 18)
                    # Prepayment amount
                    _total_prepay = sum(abs(r['Prepayment']) for r in _sec_sr_schedule if r['Prepayment'] < 0)
                    # Balance at M24 (start of repayments = opening of period 1)
                    _repay_rows = [r for r in _sec_sr_schedule if r['Period'] >= 1]
                    _bal_m24 = _repay_rows[0]['Opening'] if _repay_rows else _bal_m18
                    # DSRA principal at P1
                    _dsra_p1 = abs(_repay_rows[0]['Principle']) if _repay_rows else 0.0
                    # Balance after P1 (DSRA covers this)
                    _bal_after_p1 = _repay_rows[0]['Closing'] if _repay_rows else _bal_m24
                    # Balance after P2 (DSRA covers interest-only)
                    _bal_after_p2 = _repay_rows[1]['Closing'] if len(_repay_rows) > 1 else _bal_after_p1
                    # M36 = when IIC is first exposed
                    _bal_m36 = _bal_after_p2

                    st.divider()

                    # ── Compute DSRA FD balance at M36 (Y3 closing) ──
                    _sec_sub_model = build_sub_annual_model("nwl")
                    _sec_sub_annual = _sec_sub_model["annual"]
                    _dsra_bal_m36 = _sec_sub_annual[2]['dsra_bal'] if len(_sec_sub_annual) > 2 else 0.0  # Y3

                    # ── 1. Exposure Reduction Waterfall ──
                    st.subheader("IIC Exposure at Month 36")

                    _nwl_sr_ic = entity_data['senior_portion']

                    _se1, _se2, _se3, _se4 = st.columns(4)
                    _se1.metric("NWL Senior IC", f"€{_nwl_sr_ic:,.0f}")
                    _se2.metric("M36 Exposed Balance", f"€{_bal_m36:,.0f}")
                    _se3.metric("DSRA at M36", f"€{_dsra_bal_m36:,.0f}",
                                delta="cash collateral")
                    _se4.metric("Net Exposure", f"€{max(_bal_m36 - _dsra_bal_m36, 0):,.0f}",
                                delta=f"{(1 - _bal_m36 / _nwl_sr_ic) * 100:.0f}% below IC loan")

                    # Waterfall: NWL Senior IC → IDC → Grants → M24 balance → DSRA → M36
                    _dsra_total_reduction = _bal_m24 - _bal_m36
                    _wf_labels = [
                        'NWL Senior IC\nDrawdowns',
                        'IDC\n(capitalised)',
                        'Less: Grants\n(DTIC + GEPF)',
                        'Balance\nat M24',
                        'Less:\nDSRA',
                        'M36 Exposed\nBalance',
                    ]
                    _wf_measures = ['absolute', 'relative', 'relative', 'total', 'relative', 'total']
                    _wf_values = [
                        _total_draws,
                        _total_idc,
                        -_total_prepay,
                        0,  # total: bal at M24
                        -_dsra_total_reduction,
                        0,  # total: M36
                    ]

                    _fig_exp = go.Figure(go.Waterfall(
                        x=_wf_labels, y=_wf_values, measure=_wf_measures,
                        connector=dict(line=dict(color='#CBD5E1', width=1)),
                        increasing=dict(marker=dict(color='#EF4444')),
                        decreasing=dict(marker=dict(color='#10B981')),
                        totals=dict(marker=dict(color='#3B82F6')),
                        textposition="outside",
                        text=[f"€{abs(v):,.0f}" if v != 0 else "" for v in _wf_values],
                    ))
                    _fig_exp.update_layout(
                        height=450, yaxis_title='EUR',
                        margin=dict(l=10, r=10, t=40, b=10),
                        showlegend=False,
                    )
                    st.plotly_chart(_fig_exp, use_container_width=True)

                    st.divider()

                    # ── 2. Timeline: What protects IIC at each stage ──
                    st.subheader("Protection Timeline")
                    st.markdown(
                        "| Period | Months | Event | IIC Exposure | Protection |\n"
                        "|--------|--------|-------|-------------|------------|\n"
                        f"| Construction | M0–M18 | Drawdowns + IDC | None | Undrawn commitment |\n"
                        f"| Grace period | M18–M24 | Loan holiday, grants received | None | DTIC (R25M) + GEPF (R44.8M) prepay at M12 |\n"
                        f"| DSRA coverage | M24–M30 | P1: DSRA covers principal (€{_dsra_p1:,.0f}) | None | Creation Capital DSRA (R47.5M) |\n"
                        f"| DSRA coverage | M30–M36 | P2: interest-only (DSRA covers) | None | DSRA continues |\n"
                        f"| **First exposure** | **M36+** | P3 onwards: normal repayments | **€{_bal_m36:,.0f}** | Revenue from 1.9 MLD at 95% capacity |\n"
                        f"| Steady state | M36–M108 | 12 remaining repayments | Declining | Full revenue + 25x latent demand headroom |"
                    )

                    # ── Balance trajectory chart ──
                    st.divider()
                    st.subheader("Senior IC Balance Trajectory")

                    _traj_months = [r['Month'] for r in _sec_sr_schedule]
                    _traj_closing = [r['Closing'] for r in _sec_sr_schedule]
                    _traj_months = [0] + _traj_months
                    _traj_closing = [0] + _traj_closing

                    _fig_traj = go.Figure()
                    _fig_traj.add_trace(go.Scatter(
                        x=_traj_months, y=_traj_closing,
                        mode='lines+markers', line=dict(color='#3B82F6', width=3),
                        name='Senior IC Balance',
                    ))
                    _fig_traj.add_vrect(x0=24, x1=36, fillcolor='#10B981', opacity=0.1,
                                        annotation_text="DSRA\nprotection", annotation_position="top left",
                                        line_width=0)
                    _fig_traj.add_vrect(x0=0, x1=18, fillcolor='#F59E0B', opacity=0.08,
                                        annotation_text="Construction", annotation_position="top left",
                                        line_width=0)
                    _fig_traj.add_vline(x=36, line_dash="dash", line_color="#EF4444", line_width=2,
                                        annotation_text=f"M36: €{_bal_m36:,.0f}", annotation_position="top right")
                    if _total_prepay > 0:
                        _fig_traj.add_vline(x=12, line_dash="dot", line_color="#8B5CF6", line_width=1,
                                            annotation_text="Grants prepay", annotation_position="bottom right")
                    _fig_traj.update_layout(
                        height=400, xaxis_title='Month', yaxis_title='EUR',
                        margin=dict(l=10, r=10, t=40, b=10),
                        showlegend=False,
                    )
                    st.plotly_chart(_fig_traj, use_container_width=True)
                    st.caption(
                        "Construction (M0–M18): balance rises with drawdowns + IDC. "
                        "Grants prepay at M12. DSRA covers M24–M36. IIC exposure begins M36."
                    )

                    # ── Conclusion ──
                    st.divider()
                    st.success(
                        f"**Conclusion:** ECA cover should be sized to the **M36 exposed balance of €{_bal_m36:,.0f}**, "
                        f"not the NWL Senior IC loan of €{_nwl_sr_ic:,.0f}. "
                        f"DSRA of €{_dsra_bal_m36:,.0f} at M36 provides additional cash collateral."
                    )

                    # ════════════════════════════════════════════════════
                    # LAYER 1 — Financial Claims (Holding Level)
                    # ════════════════════════════════════════════════════
                    st.divider()
                    st.subheader("Layer 1 — Financial Claims (Holding Level)")
                    st.markdown(
                        "At the holding level, SCLCA pledges its financial claims: "
                        f"NWL IC receivables (**€{entity_data['total_loan']:,.0f}**) to IIC, "
                        "and NWL equity to Creation Capital. No guarantees or DSRA at this level."
                    )
                    _l1_ref = pd.DataFrame([
                        {"Security": "NWL IC loan receivable", "Pledged To": "IIC", "Value": f"€{entity_data['total_loan']:,.0f}"},
                        {"Security": "93% equity in NWL", "Pledged To": "Creation Capital", "Value": "R930,000 (EUR46,500)"},
                    ])
                    render_table(_l1_ref, right_align=["Value"])

                    # ════════════════════════════════════════════════════
                    # LAYER 2 — Guarantees, Insurance & Credit Enhancements
                    # ════════════════════════════════════════════════════
                    st.divider()
                    st.subheader("Layer 2 — Guarantees, Insurance & Credit Enhancements")

                    with st.container(border=True):
                        st.markdown("##### Corporate Guarantee — Veracity Property Holdings")
                        st.markdown(
                            f"Veracity provides a corporate guarantee for the **full NWL IC loan** of **€{entity_data['total_loan']:,.0f}**."
                        )
                        _g1, _g2 = st.columns(2)
                        _g1.metric("Guarantee Amount", f"€{entity_data['total_loan']:,.0f}")
                        _g2.metric("Guarantor", "Veracity Property Holdings")

                        st.markdown("**Guarantor Financial Highlights (3-Year Trend)**")
                        _ver = [
                            ("Total Assets", "R746.5M", "R682.4M", "R592.5M"),
                            ("Investment Property", "R692.9M", "R620.0M", "R565.0M"),
                            ("Total Equity", "R53.4M", "R62.0M", "R48.5M"),
                            ("Revenue", "R72.5M", "R64.8M", "R62.2M"),
                            ("Operating Profit", "R42.9M", "R57.8M", "R38.0M"),
                            ("Finance Costs", "R58.5M", "R43.2M", "R31.4M"),
                            ("**Net Profit/(Loss)**", "**(R9.3M)**", "**R15.3M**", "**R5.7M**"),
                            ("D/E Ratio", "13.0x", "10.0x", "11.2x"),
                            ("Interest Cover", "0.73x", "1.34x", "1.21x"),
                        ]
                        _render_fin_table(_ver, ["Metric", "FY2025", "FY2024", "FY2023"])

                        # -- Guarantor Balance Sheet --
                        with st.expander("Guarantor Balance Sheet", expanded=False):
                            _gbs = [
                                ("**Assets**", "", "", ""),
                                ("Investment property", "R692,887,607", "R619,963,925", "R564,992,692"),
                                ("Loans to group companies", "R44,427,115", "R42,693,733", "R1,599,260"),
                                ("Other non-current assets", "R2,824,672", "R1,010", "R3,403,271"),
                                ("Trade & other receivables", "R4,992,125", "R16,976,709", "R16,035,972"),
                                ("Cash", "R1,399,686", "R2,729,745", "R6,488,455"),
                                ("**Total Assets**", "**R746,531,205**", "**R682,364,137**", "**R592,525,617**"),
                                ("", "", "", ""),
                                ("**Equity & Liabilities**", "", "", ""),
                                ("Total Equity", "R53,374,460", "R62,043,150", "R48,473,615"),
                                ("Other financial liabilities", "R671,682,013", "R572,400,247", "R522,219,494"),
                                ("Shareholders loan", "---", "R20,044,150", "R3,403,126"),
                                ("Deferred tax", "R3,826,656", "R9,200,184", "R8,622,722"),
                                ("Trade & other payables", "R13,887,051", "R15,431,589", "R8,591,328"),
                                ("Bank overdraft", "R2,057,725", "R1,738,622", "---"),
                                ("Other current liabilities", "R1,703,300", "R1,506,195", "R1,215,332"),
                                ("**Total Equity & Liabilities**", "**R746,531,205**", "**R682,364,137**", "**R592,525,617**"),
                            ]
                            _render_fin_table(_gbs, ["", "FY2025", "FY2024", "FY2023"])

                        # -- Guarantor P&L --
                        with st.expander("Guarantor Profit & Loss", expanded=False):
                            _gpl = [
                                ("Revenue (rentals + recoveries)", "R72,488,610", "R64,752,125", "R62,170,435"),
                                ("Fair value gains", "R9,540,776", "R28,967,822", "R7,359,937"),
                                ("Other income", "R427,519", "R69,788", "R38,502"),
                                ("Operating expenses", "(R39,580,457)", "(R35,945,459)", "(R31,602,751)"),
                                ("**Operating profit**", "**R42,876,448**", "**R57,844,276**", "**R37,966,123**"),
                                ("Investment revenue", "R869,068", "R1,310,422", "R908,718"),
                                ("Finance costs", "(R58,519,409)", "(R43,220,057)", "(R31,402,269)"),
                                ("Profit/(Loss) before tax", "(R14,773,893)", "R15,934,641", "R7,472,572"),
                                ("Taxation", "R5,459,940", "(R609,939)", "(R1,743,656)"),
                                ("**Net Profit/(Loss)**", "**(R9,313,953)**", "**R15,324,702**", "**R5,728,916**"),
                            ]
                            _render_fin_table(_gpl, ["", "FY2025", "FY2024", "FY2023"])

                        # -- Underlying Properties --
                        with st.expander("Underlying Property Portfolio (8 properties, FY2025)", expanded=False):
                            _gprop = [
                                ("Morningside Ext 5", "Uvongo Falls No 26", "R336,919,312", "48.6%", "Residential development"),
                                ("Mastiff Sandton", "Mistraline", "R160,500,000", "23.2%", "Commercial + PV solar"),
                                ("Bellville Cape Town", "New in FY2025", "R74,200,000", "10.7%", "Commercial acquisition"),
                                ("Tyrwhitt Sections", "Providence Property", "R49,640,700", "7.2%", "Residential (new FY2024)"),
                                ("Longmeadow Gauteng", "Erf 86 Longmeadow", "R46,723,682", "6.7%", "Commercial + PV solar"),
                                ("Saxonwold JHB (4 units)", "Aquaside Trading", "R17,600,000", "2.5%", "Residential rental"),
                                ("George Cape Town", "Aquaside Trading", "R4,500,000", "0.6%", "Residential"),
                                ("Randpark Ridge", "BBP Unit 1 Phase 2", "R2,803,913", "0.4%", "Commercial"),
                            ]
                            _render_fin_table(_gprop, ["Property", "Held By", "Value (ZAR)", "% Portfolio", "Type / Income"])
                            st.caption("Total: R692,887,607. All pledged as security. Top 2 = 71.8% concentration.")

                        # -- Subsidiaries --
                        with st.expander("Veracity Subsidiaries & Associates", expanded=False):
                            _gsub = [
                                ("Aquaside Trading", "100%", "Saxonwold (4 units) + George", "Residential rentals"),
                                ("BBP Unit 1 Phase 2", "100%", "Randpark Ridge", "Commercial rental"),
                                ("Cornerstone Property Group", "50%", "HoldCo for Ireo Project 10", "Holding"),
                                ("  Ireo Project 10 (formerly Chepstow)", "sub of Cornerstone", "Industrial, Bellville CT", "Industrial"),
                                ("Erf 86 Longmeadow", "100%", "Longmeadow + PV solar", "Commercial rental"),
                                ("Providence Property", "100%", "Tyrwhitt Sections", "Residential rental"),
                                ("  Manappu Investments (associate)", "20%", "50 units Tyrwhitt JHB", "Residential rental"),
                                ("Sun Property", "50%", "HoldCo for 6 On Kloof", "Holding"),
                                ("  6 On Kloof (associate)", "25%", "46 units Sea Point CT", "Hotel/apartments"),
                                ("Uvongo Falls No 26", "50%", "Morningside Ext 5 (R337M)", "Residential dev [GC]"),
                                ("Mistraline (associate)", "33%", "Industrial, Linbro Park JHB", "Commercial + PV solar"),
                            ]
                            _render_fin_table(_gsub, ["Entity", "Ownership", "Asset Base", "Income Type"])

                        st.caption("Source: Audited AFS FY2023-FY2025, KCE Accountants and Auditors Inc.")

                        # ── SVG Organogram — Veracity Corporate Structure ──
                        st.divider()
                        st.markdown("##### Corporate Structure — Veracity Property Holdings")
                        render_svg("guarantor-veracity.svg", "_none.md")

                        # ── Nested Subsidiary Financials (driven by guarantor.json) ──
                        _ver_subs_nwl = _load_guarantor_jsons("veracity 2025 financials")
                        # Also load root-level VPH JSON
                        _ver_root_nwl = _load_guarantor_jsons("")
                        _ver_all_nwl = {**_ver_subs_nwl, **_ver_root_nwl}
                        _guar_cfg = _load_guarantor_config()
                        _ver_group = _guar_cfg.get("groups", {}).get("veracity", {})
                        _ver_holding = _ver_group.get("holding", {})

                        if _ver_all_nwl and _ver_holding:
                            st.divider()
                            # Summary table (flat, for quick overview)
                            with st.expander(f"Subsidiary Financial Statements ({len(_ver_subs_nwl)} entities)", expanded=False):
                                _render_sub_summary_and_toggles(_ver_subs_nwl, "nwl_ver_summ")

                            # Nested tree view
                            with st.expander("Nested Corporate Hierarchy — Financial Statements", expanded=False):
                                st.caption("Financial statements organised by ownership hierarchy (parent → child)")
                                for _child_node in _ver_holding.get("children", []):
                                    _render_nested_financials(_child_node, _ver_all_nwl, "nwl_ver")

                        # ── Email Q&A ──
                        if _guar_cfg:
                            st.divider()
                            _render_email_qa(_guar_cfg)

                    # ── Credit Enhancements (grouped) ──
                    _dtic_eur = financing['prepayments']['dtic_grant']['amount_eur']
                    _gepf_eur = financing['prepayments']['gepf_bulk_services']['amount_eur']
                    _dtic_zar = financing['prepayments']['dtic_grant']['amount_zar']
                    _gepf_zar = financing['prepayments']['gepf_bulk_services']['total_zar']
                    _dsra_zar = financing['sources']['mezzanine']['dsra_size_zar']
                    _dsra_eur_sec = _dsra_zar / FX_RATE
                    _grants_zar = _dtic_zar + _gepf_zar
                    _grants_eur = _dtic_eur + _gepf_eur
                    _nwl_swap_on = st.session_state.get("sclca_nwl_hedge", "CC DSRA \u2192 FEC") == "Cross-Currency Swap"

                    # Row 1: Guarantee + ECA (clubbed)
                    _colubris_eur = 1_721_925  # Dutch content trigger
                    _eca_cover_eur = _bal_m36   # ECA sized to M36 exposed balance
                    with st.container(border=True):
                        st.markdown("##### 1. Corporate Guarantee + Atradius ECA Cover")
                        _g1, _g2, _g3 = st.columns(3)
                        _g1.metric("VPH Corporate Guarantee", f"€{entity_data['total_loan']:,.0f}", delta="Full IC loan (Sr + Mz)")
                        _g2.metric("Atradius ECA Cover", f"€{_eca_cover_eur:,.0f}", delta="To be applied — sized to M36 balance")
                        _g3.metric("Dutch Content Trigger", f"€{_colubris_eur:,.0f}", delta="Colubris BoP")
                        st.caption(
                            f"Veracity Property Holdings guarantees full NWL IC loan. "
                            f"Atradius ECA cover sized to **M36 exposed balance** (€{_eca_cover_eur:,.0f}) — "
                            f"triggered by Dutch content in Colubris BoP (€{_colubris_eur:,.0f}). **To be applied for** at Atradius DSB."
                        )

                    # Row 2: DSRA vs Swap (show both, highlight selected)
                    st.markdown("##### 2. Debt Service Cover & FX Hedge")
                    _dsra_col, _swap_col = st.columns(2)
                    with _dsra_col:
                        with st.container(border=True):
                            if not _nwl_swap_on:
                                st.markdown(":green[**SELECTED**]")
                                st.markdown("**DSRA via FEC** (semi-bank-to-bank)")
                                _d1, _d2 = st.columns(2)
                                _d1.metric("DSRA Size", f"R{_dsra_zar:,.0f}", delta=f"€{_dsra_eur_sec:,.0f}")
                                _d2.metric("Timing", "M24", delta="Covers P1+P2")
                                st.caption(
                                    "Creation Capital injects ZAR reserve at M24. "
                                    "FEC locks ZAR→EUR rate via Investec — covers first 2 senior debt service payments (M24-M36). "
                                    "**Semi-bank-to-bank**: IIC exposure partially mitigated through Investec FEC. Pledged to IIC."
                                )
                            else:
                                st.markdown(":grey[NOT SELECTED]")
                                st.markdown(":grey[**Debt Service Reserve Account (DSRA)**]")
                                st.markdown(
                                    f":grey[DSRA Size: R{_dsra_zar:,.0f} (€{_dsra_eur_sec:,.0f})  \n"
                                    f"Timing: M24 — Covers P1+P2  \n"
                                    f"Funded by Creation Capital, held by Investec (FEC)]"
                                )
                    with _swap_col:
                        with st.container(border=True):
                            if _nwl_swap_on:
                                st.markdown(":green[**SELECTED**]")
                                st.markdown("**Cross-Currency Swap** (bank-to-bank exposure)")
                                st.metric("Hedging Structure", "Cross-Currency Swap", delta="Bank-to-bank exposure")
                                st.caption(
                                    "NWL enters EUR→ZAR swap with a foreign bank. Achieves **debt service cover and "
                                    "FX hedge in a single instrument** — CC does not need to fund DSRA. "
                                    "**Bank-to-bank exposure**: IIC's exposure transfers fully from NWL to the "
                                    "**foreign bank providing the EUR leg** (bank counterparty risk)."
                                )
                            else:
                                st.markdown(":grey[NOT SELECTED]")
                                st.markdown(":grey[**Cross-Currency Swap** (bank-to-bank)]")
                                st.markdown(
                                    ":grey[EUR→ZAR swap — DS cover + FX hedge in one instrument. "
                                    "Bank-to-bank: IIC exposure transfers to foreign bank (EUR leg counterparty).]"
                                )
                    st.caption("Toggle between DSRA and Swap in the **Debt Sculpting** tab → NWL Debt Service Cover & FX Hedge.")

                    # Row 3: Grants (clubbed)
                    with st.container(border=True):
                        st.markdown("##### 3. Pre-Revenue Cash Flow for Prepayment (DTIC + GEPF)")
                        _gr1, _gr2, _gr3 = st.columns(3)
                        _gr1.metric("DTIC Manufacturing", f"R{_dtic_zar:,.0f}", delta=f"€{_dtic_eur:,.0f}")
                        _gr2.metric("GEPF Bulk Services", f"R{_gepf_zar:,.0f}", delta=f"€{_gepf_eur:,.0f}")
                        _gr3.metric("Combined", f"R{_grants_zar:,.0f}", delta=f"€{_grants_eur:,.0f}")
                        st.caption(
                            "Both applied as senior debt prepayments at M12 (Period -2). "
                            "Reduces NWL IC loan balance before first repayment."
                        )

                    # Summary table
                    _sel = "✓" if not _nwl_swap_on else ""
                    _sel_sw = "✓" if _nwl_swap_on else ""
                    _l2_summary = [
                        ("Corporate Guarantee + ECA", f"€{entity_data['total_loan']:,.0f} (guarantee) + €{_eca_cover_eur:,.0f} (ECA at M36)", "Committed / To be applied", f"VPH guarantee (full IC) + Atradius ECA (M36 balance, Dutch content €{_colubris_eur:,.0f})"),
                        (f"DSRA via FEC (semi-bank-to-bank) {_sel}", f"R{_dsra_zar:,.0f} (€{_dsra_eur_sec:,.0f})", "Committed", "DS cover (P1+P2) + FX hedge via Investec FEC (M24-M36)"),
                        (f"Cross-Currency Swap (bank-to-bank) {_sel_sw}", "EUR→ZAR swap", "Alternative", "Bank-to-bank: IIC exposure to foreign bank + FX hedge in one instrument"),
                        ("Pre-Revenue CF for Prepayment", f"R{_grants_zar:,.0f} (€{_grants_eur:,.0f})", "Approved / Committed", "DTIC + GEPF — senior prepayments at M12"),
                    ]
                    _render_fin_table(_l2_summary, ["Enhancement", "Amount", "Status", "Note"])

                    # ════════════════════════════════════════════════════
                    # LAYER 3 — Physical Assets & Revenue Contracts
                    # ════════════════════════════════════════════════════
                    st.divider()
                    st.subheader("Layer 3 — Physical Assets & Revenue Contracts")

                    # Physical assets table (from security.json layer_3)
                    _l3 = sub_sec.get('layer_3', {})
                    _phys_assets = _l3.get('physical_assets', [])
                    if _phys_assets:
                        _l3_rows = []
                        for _item in _phys_assets:
                            _row = {
                                'Asset': _item.get('asset', ''),
                                'Supplier': _item.get('supplier', ''),
                                'Country': _item.get('country', ''),
                            }
                            if 'budget_eur' in _item:
                                _row['Budget'] = _item['budget_eur']
                            _l3_rows.append(_row)
                        _df_l3 = pd.DataFrame(_l3_rows)
                        render_table(_df_l3, {"Budget": _eur_fmt} if 'Budget' in _df_l3.columns else None)

                    # Assets & liabilities over time (from annual model)
                    st.markdown("**Asset & Liability Trajectory (10 years)**")
                    _sec_years = [f"Y{a['year']}" for a in _sec_sub_annual]
                    _sec_fixed = [a['bs_fixed_assets'] for a in _sec_sub_annual]
                    _sec_dsra_fd = [a['bs_dsra'] for a in _sec_sub_annual]
                    _sec_sr_bal = [a['bs_sr'] for a in _sec_sub_annual]
                    _sec_mz_bal = [a['bs_mz'] for a in _sec_sub_annual]

                    _fig_al = go.Figure()
                    _fig_al.add_trace(go.Bar(x=_sec_years, y=[v / 1e6 for v in _sec_fixed],
                        name='Fixed Assets', marker_color='#3B82F6'))
                    _fig_al.add_trace(go.Bar(x=_sec_years, y=[v / 1e6 for v in _sec_dsra_fd],
                        name='Fixed Deposit (Cash)', marker_color='#10B981'))
                    _fig_al.add_trace(go.Scatter(x=_sec_years, y=[(s + m) / 1e6 for s, m in zip(_sec_sr_bal, _sec_mz_bal)],
                        name='Total IC Debt', mode='lines+markers', line=dict(color='#EF4444', width=3)))
                    _fig_al.update_layout(
                        barmode='stack', height=380, yaxis_title='EUR (millions)',
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="center", x=0.5),
                    )
                    st.plotly_chart(_fig_al, use_container_width=True)
                    st.caption("Stacked bars = entity assets (fixed + fixed deposit cash). Red line = IC debt declining over time.")

                    # Revenue contracts from security.json layer_3
                    _rev_contracts = _l3.get('revenue_contracts', [])
                    if _rev_contracts:
                        st.markdown("**Revenue Contracts & Offtake Agreements**")
                        _df_rc = pd.DataFrame(_rev_contracts)
                        _rc_cols = [c for c in ['contract', 'type', 'status', 'note'] if c in _df_rc.columns]
                        render_table(_df_rc[_rc_cols].rename(columns={
                            'contract': 'Contract', 'type': 'Type',
                            'status': 'Status', 'note': 'Note'
                        }))

                else:
                    # Non-NWL entities: standard security view
                    st.metric("Intercompany Loan from SCLCA", f"€{entity_data['total_loan']:,.0f}")
                    st.markdown(f"""
**Security flow:** {name} provides its guarantees & insurance (Layer 2) and physical assets &
revenue contracts (Layer 3) upstream through SCLCA to Invest International Capital B.V.
                    """)
                    st.divider()

                    # Layer 2 — Guarantees & Insurance
                    l2 = sub_sec.get('layer_2', {})
                    st.subheader(l2.get('title', 'Layer 2 — Guarantees & Insurance'))

                    # Timberworx: 2-column display (Guarantee + ECA)
                    if entity_key == 'timberworx':
                        _twx_eca_eur = entity_data['total_loan']  # Full IC loan — vanilla, fully guaranteed from M24
                        with st.container(border=True):
                            st.markdown("##### Corporate Guarantee + Atradius ECA Cover")
                            _t1, _t2 = st.columns(2)
                            _t1.metric("Phoenix Corporate Guarantee", f"€{_twx_eca_eur:,.0f}", delta="Full IC loan (Sr + Mz)")
                            _t2.metric("Atradius ECA Cover", f"€{_twx_eca_eur:,.0f}", delta="To be applied — full IC loan")
                            st.caption(
                                f"VH Properties (40% in Phoenix Group) guarantees the full TWX IC loan. "
                                f"Atradius ECA cover sized to **full IC loan** (€{_twx_eca_eur:,.0f}) — vanilla structure, "
                                f"fully guaranteed from M24. **To be applied for** at Atradius DSB."
                            )
                        # Summary table
                        _twx_l2_summary = [
                            ("Phoenix Guarantee + Atradius ECA",
                             f"€{_twx_eca_eur:,.0f} (guarantee) + €{_twx_eca_eur:,.0f} (ECA)",
                             "Committed / To be applied",
                             "VH Properties guarantee (full IC) + Atradius ECA (full IC loan, vanilla from M24)"),
                        ]
                        _render_fin_table(_twx_l2_summary, ["Enhancement", "Amount", "Status", "Note"])

                        st.divider()
                        with st.container(border=True):
                            st.markdown("##### Guarantee Capacity — Phoenix Group (via VH Properties)")
                            st.markdown(
                                f"VH Properties (holds 40% in Phoenix Group) provides a corporate guarantee for "
                                f"the **full Timberworx IC loan** of **€{entity_data['total_loan']:,.0f}**. "
                                f"VH Properties is part of the **VH Investments Trust** structure (same ultimate owner as Veracity)."
                            )
                            _p1, _p2, _p3 = st.columns(3)
                            _p1.metric("Group EBITDA", "R68.2M")
                            _p2.metric("Attributable (40%)", "R27.3M")
                            _p3.metric("Coverage", "1.34x", delta="2yr cash / IC loan")

                        # ── SVG Organogram — Phoenix Corporate Structure ──
                        st.divider()
                        st.markdown("##### Corporate Structure — Phoenix Group (via VH Properties)")
                        render_svg("guarantor-phoenix.svg", "_none.md")

                        # ── Nested Phoenix Subsidiary Financials ──
                        _phx_subs_twx = _load_guarantor_jsons("phoenix 2025 financials")
                        _phx_root_twx = _load_guarantor_jsons("")
                        _phx_all_twx = {**_phx_subs_twx, **_phx_root_twx}
                        _guar_cfg_twx = _load_guarantor_config()
                        _phx_group = _guar_cfg_twx.get("groups", {}).get("phoenix", {})
                        _phx_holding = _phx_group.get("holding", {})

                        if _phx_all_twx and _phx_holding:
                            st.divider()
                            with st.expander(f"Phoenix Subsidiary Financial Statements ({len(_phx_subs_twx)} entities)", expanded=False):
                                _render_sub_summary_and_toggles(_phx_subs_twx, "twx_phx_summ")

                            with st.expander("Nested Corporate Hierarchy — Financial Statements", expanded=False):
                                st.caption("Financial statements organised by ownership hierarchy (parent → child)")
                                for _child_node in _phx_holding.get("children", []):
                                    _render_nested_financials(_child_node, _phx_all_twx, "twx_phx")

                        # ── Email Q&A ──
                        if _guar_cfg_twx:
                            st.divider()
                            _render_email_qa(_guar_cfg_twx)

                    # LanRED: underwriter OR swap (show both, grey out unselected)
                    elif entity_key == 'lanred':
                        _lanred_uw_on = st.session_state.get("lanred_scenario", "Greenfield") == "Greenfield"
                        _lr_uw_col, _lr_sw_col = st.columns(2)
                        with _lr_uw_col:
                            with st.container(border=True):
                                if _lanred_uw_on:
                                    st.markdown(":green[**SELECTED**]")
                                    st.markdown("**Independent Underwriting**")
                                    st.metric("Underwriting", f"€{entity_data['total_loan']:,.0f}", delta="Full IC loan")
                                    st.caption(
                                        "Third-party insurer underwrites the full LanRED IC loan. "
                                        "IIC's exposure transfers to the underwriter."
                                    )
                                else:
                                    st.markdown(":grey[NOT SELECTED]")
                                    st.markdown(":grey[**Independent Underwriting**]")
                                    st.markdown(
                                        f":grey[Coverage: €{entity_data['total_loan']:,.0f} (full IC loan)  \n"
                                        f"IIC exposure transfers to third-party insurer.]"
                                    )
                        with _lr_sw_col:
                            with st.container(border=True):
                                if not _lanred_uw_on:
                                    st.markdown(":green[**SELECTED**]")
                                    st.markdown("**Cross-Currency Swap** (bank-to-bank exposure)")
                                    st.metric("Swap Notional", f"€{entity_data['total_loan']:,.0f}", delta="Bank-to-bank exposure")
                                    st.caption(
                                        "LanRED enters EUR→ZAR swap with a foreign bank. "
                                        "This achieves **two things simultaneously**: (1) locks the EUR→ZAR exchange rate "
                                        "(FX hedge), and (2) transfers IIC's credit exposure from LanRED to the **foreign bank "
                                        "providing the EUR leg**. **Bank-to-bank**: IIC's risk becomes bank counterparty risk."
                                    )
                                else:
                                    st.markdown(":grey[NOT SELECTED]")
                                    st.markdown(":grey[**Cross-Currency Swap** (bank-to-bank)]")
                                    st.markdown(
                                        f":grey[Notional: €{entity_data['total_loan']:,.0f}  \n"
                                        f"Bank-to-bank: IIC exposure transfers to foreign bank (EUR leg counterparty).]"
                                    )
                        st.caption("Per asset and sculpting choices — either independent underwriting or bank-to-bank swap.")
                        _lr_sel = "✓" if _lanred_uw_on else ""
                        _lr_sel_sw = "✓" if not _lanred_uw_on else ""
                        _lanred_l2_summary = [
                            (f"Independent Underwriting {_lr_sel}", f"€{entity_data['total_loan']:,.0f}", "Planned",
                             "Third-party insurer — IIC exposure transfers to underwriter"),
                            (f"Cross-Currency Swap (bank-to-bank) {_lr_sel_sw}", f"€{entity_data['total_loan']:,.0f}", "Alternative",
                             "Bank-to-bank: IIC exposure transfers to foreign bank (EUR leg)"),
                        ]
                        _render_fin_table(_lanred_l2_summary, ["Enhancement", "Amount", "Status", "Note"])

                    # Default: flat items table
                    else:
                        l2_items = l2.get('items', [])
                        if l2_items:
                            _df_l2_enh = pd.DataFrame(l2_items)
                            _l2_disp = [c for c in ['enhancement', 'type', 'jurisdiction', 'status', 'note'] if c in _df_l2_enh.columns]
                            render_table(_df_l2_enh[_l2_disp].rename(columns={
                                'enhancement': 'Enhancement', 'type': 'Type',
                                'jurisdiction': 'Jurisdiction', 'status': 'Status', 'note': 'Note'
                            }))

                    # Timberworx: Phoenix guarantee detail
                    if entity_key == 'timberworx':

                            # Phoenix property-level EBITDA
                            with st.expander("Phoenix Property-Level EBITDA", expanded=False):
                                _phx_sec = [
                                    ("Ridgeview Centre", "R15,565,485", "40%", "R6,226,194"),
                                    ("Brackenfell", "R16,125,484", "40%", "R6,450,194"),
                                    ("Chartwell Corner", "R4,610,498", "20%", "R922,100"),
                                    ("Jukskei Corner", "R6,663,633", "40%", "R2,665,453"),
                                    ("Madelief", "R10,867,992", "40%", "R4,347,197"),
                                    ("Olivedale", "R14,420,287", "40%", "R5,768,115"),
                                    ("**Total**", "**R68,253,379**", "", "**R26,379,252**"),
                                ]
                                _render_fin_table(_phx_sec, ["Property", "EBITDA", "VH Stake", "Attributable"])
                                st.caption("Source: Phoenix Group Summary 2025. All retail centre assets with stable tenant base.")

                            st.caption("Guarantee entity: VH Properties (40% in Phoenix Group). Part of VH Investments Trust.")

                            # ── Per-Entity Subsidiary Financials (nested, from L4 JSONs) ──
                            _phx_subs_twx = _load_guarantor_jsons("Phoenix group")
                            _guar_cfg_twx = _load_guarantor_config()
                            _phx_group = _guar_cfg_twx.get("groups", {}).get("phoenix", {})
                            _phx_holding = _phx_group.get("holding", {})
                            if _phx_subs_twx:
                                st.divider()
                                with st.expander(f"Phoenix Group Financial Statements ({len(_phx_subs_twx)} entities)", expanded=False):
                                    _render_sub_summary_and_toggles(_phx_subs_twx, "twx_phx_summ")
                                if _phx_holding:
                                    with st.expander("Nested Corporate Hierarchy — Phoenix Group", expanded=False):
                                        st.caption("Financial statements organised by ownership hierarchy (parent → child)")
                                        for _child_node_twx in _phx_holding.get("children", []):
                                            _render_nested_financials(_child_node_twx, _phx_subs_twx, "twx_phx")

                    st.divider()

                    # Layer 3 — Physical Assets & Revenue Contracts
                    l3 = sub_sec.get('layer_3', {})
                    st.subheader(l3.get('title', 'Layer 3 — Physical Assets & Revenue Contracts'))

                    # LanRED: side-by-side Greenfield vs Brownfield+
                    if entity_key == 'lanred' and l3.get('scenario_toggle'):
                        _l3_lr_active = st.session_state.get("lanred_scenario", "Greenfield")
                        _l3_gf = l3.get('greenfield', {})
                        _l3_bf = l3.get('brownfield_plus', {})
                        _l3_col_gf, _l3_col_bf = st.columns(2)

                        for _l3_col, _l3_data, _l3_name, _l3_is_active in [
                            (_l3_col_gf, _l3_gf, "Greenfield", _l3_lr_active == "Greenfield"),
                            (_l3_col_bf, _l3_bf, "Brownfield+", _l3_lr_active == "Brownfield+"),
                        ]:
                            with _l3_col:
                                with st.container(border=True):
                                    if _l3_is_active:
                                        st.markdown(":green[**SELECTED**]")
                                        st.markdown(f"**{_l3_name}**")
                                        _l3_pa = _l3_data.get('physical_assets', [])
                                        if _l3_pa:
                                            st.markdown("**Physical Assets**")
                                            _pa_rows = []
                                            for _item in _l3_pa:
                                                _row = {
                                                    'Asset': _item.get('asset', ''),
                                                    'Supplier': _item.get('supplier', ''),
                                                }
                                                if _item.get('budget_eur') is not None:
                                                    _row['Budget'] = _item['budget_eur']
                                                _pa_rows.append(_row)
                                            _df_pa = pd.DataFrame(_pa_rows)
                                            render_table(_df_pa, {"Budget": _eur_fmt} if 'Budget' in _df_pa.columns else None)
                                        _l3_rc = _l3_data.get('revenue_contracts', [])
                                        if _l3_rc:
                                            st.markdown("**Revenue Contracts**")
                                            _df_rc = pd.DataFrame(_l3_rc)
                                            _rc_cols = [c for c in ['contract', 'type', 'status', 'note'] if c in _df_rc.columns]
                                            render_table(_df_rc[_rc_cols].rename(columns={
                                                'contract': 'Contract', 'type': 'Type',
                                                'status': 'Status', 'note': 'Note'
                                            }))
                                    else:
                                        st.markdown(":grey[NOT SELECTED]")
                                        st.markdown(f":grey[**{_l3_name}**]")
                                        _l3_pa = _l3_data.get('physical_assets', [])
                                        if _l3_pa:
                                            _pa_names = ", ".join(_i.get('asset', '') for _i in _l3_pa)
                                            st.markdown(f":grey[Assets: {_pa_names}]")
                                        _l3_rc = _l3_data.get('revenue_contracts', [])
                                        if _l3_rc:
                                            _rc_names = ", ".join(_r.get('contract', '') for _r in _l3_rc)
                                            st.markdown(f":grey[Contracts: {_rc_names}]")
                    else:
                        _phys_assets = l3.get('physical_assets', [])
                        if _phys_assets:
                            st.markdown("**Physical Assets**")
                            _pa_rows = []
                            for _item in _phys_assets:
                                _row = {
                                    'Asset': _item.get('asset', ''),
                                    'Supplier': _item.get('supplier', ''),
                                    'Country': _item.get('country', ''),
                                }
                                if 'budget_eur' in _item:
                                    _row['Budget'] = _item['budget_eur']
                                _pa_rows.append(_row)
                            _df_pa = pd.DataFrame(_pa_rows)
                            render_table(_df_pa, {"Budget": _eur_fmt} if 'Budget' in _df_pa.columns else None)

                        _rev_contracts = l3.get('revenue_contracts', [])
                        if _rev_contracts:
                            st.markdown("**Revenue Contracts**")
                            _df_rc = pd.DataFrame(_rev_contracts)
                            _rc_cols = [c for c in ['contract', 'type', 'status', 'note'] if c in _df_rc.columns]
                            render_table(_df_rc[_rc_cols].rename(columns={
                                'contract': 'Contract', 'type': 'Type',
                                'status': 'Status', 'note': 'Note'
                            }))

    # --- DELIVERY ---
    if "Delivery" in _tab_map:
        with _tab_map["Delivery"]:
            st.header("Delivery Structure")

            # Load MD content first
            delivery_content_md = load_content_md("DELIVERY_CONTENT.md")
            entity_delivery_md = delivery_content_md.get(entity_key, "")

            if entity_delivery_md:
                st.markdown(entity_delivery_md)
                st.divider()

            delivery = load_config("delivery")
            contractors = load_config("contractors")
            assets_del = load_config("assets")
            scope = delivery['scopes'].get(entity_key, {})

            if not scope:
                st.info("Delivery data not available for this entity.")
            else:
                # LanRED: full side-by-side Greenfield vs Brownfield+ delivery
                if entity_key == 'lanred' and scope.get('scenario_toggle'):
                    _del_lr_active = st.session_state.get("lanred_scenario", "Greenfield")
                    _del_gf = scope.get('greenfield', {})
                    _del_bf = scope.get('brownfield_plus', {})
                    _bf_ops = load_config("operations").get("lanred", {}).get("brownfield_plus", {})
                    _bf_port = _bf_ops.get("northlands_portfolio", {})
                    _bf_sites = _bf_port.get("sites", [])
                    _del_col_gf, _del_col_bf = st.columns(2)

                    # --- Greenfield column ---
                    with _del_col_gf:
                        with st.container(border=True):
                            _gf_active = (_del_lr_active == "Greenfield")
                            if _gf_active:
                                st.markdown(":green[**SELECTED**]")
                                st.markdown("**Greenfield**")
                                st.metric("EPC Model", _del_gf.get('epc_model', ''))
                                st.metric("EPC Contractor", _del_gf.get('epc_contractor', ''))
                                st.metric("Scope Value", f"€{_del_gf.get('total_eur', 0):,.0f}")
                                st.caption(_del_gf.get('note', ''))
                                st.divider()
                                st.markdown("**Asset Breakdown**")
                                _sub_asset_keys = sub_data.get('assets', [])
                                for _ak in _sub_asset_keys:
                                    _asset_data = assets_del['assets'].get(_ak, {})
                                    if _asset_data and _asset_data.get('line_items'):
                                        _li_rows = []
                                        for _li in _asset_data['line_items']:
                                            _li_rows.append({
                                                "Supplier": _li['company'],
                                                "Deliverable": _li['delivery'],
                                                "Budget": _li['budget'],
                                            })
                                        _li_rows.append({
                                            "Supplier": "**Total**",
                                            "Deliverable": "",
                                            "Budget": _asset_data['total'],
                                        })
                                        render_table(pd.DataFrame(_li_rows), {"Budget": _eur_fmt})
                            else:
                                st.markdown(":grey[NOT SELECTED]")
                                st.markdown(":grey[**Greenfield**]")
                                st.markdown(f":grey[EPC: {_del_gf.get('epc_contractor', '')}]")
                                st.markdown(f":grey[Value: €{_del_gf.get('total_eur', 0):,.0f}]")
                                st.markdown(":grey[New-build Solar PV (2.4 MWp) + BESS (1.5 MWh)]")

                    # --- Brownfield+ column ---
                    with _del_col_bf:
                        with st.container(border=True):
                            _bf_active = (_del_lr_active == "Brownfield+")
                            if _bf_active:
                                st.markdown(":green[**SELECTED**]")
                                st.markdown("**Brownfield+**")
                                st.metric("EPC Model", _del_bf.get('epc_model', ''))
                                st.metric("EPC Contractor", _del_bf.get('epc_contractor', ''))
                                st.metric("Scope Value", f"€{_del_bf.get('total_eur', 0):,.0f}")
                                st.caption(_del_bf.get('note', ''))
                                st.divider()
                                st.markdown("**Portfolio Sites**")
                                _bf_rows = []
                                for _site in _bf_sites:
                                    _bf_rows.append({
                                        "Site": _site['name'],
                                        "PV (kWp)": _site['pv_kwp'],
                                        "BESS (kWh)": _site['bess_kwh'],
                                        "Net (ZAR/mo)": _site['monthly_net_zar'],
                                    })
                                _bf_rows.append({
                                    "Site": "**Total**",
                                    "PV (kWp)": sum(s['pv_kwp'] for s in _bf_sites),
                                    "BESS (kWh)": sum(s['bess_kwh'] for s in _bf_sites),
                                    "Net (ZAR/mo)": sum(s['monthly_net_zar'] for s in _bf_sites),
                                })
                                render_table(pd.DataFrame(_bf_rows), {"Net (ZAR/mo)": "R{:,.0f}"})
                                _bf_price = _bf_port.get("purchase_price_zar", 60000000)
                                st.caption(f"Purchase price: R{_bf_price:,.0f}. All sites operational with 20-year PPAs.")
                            else:
                                st.markdown(":grey[NOT SELECTED]")
                                st.markdown(":grey[**Brownfield+**]")
                                st.markdown(f":grey[Acquisition: {_del_bf.get('epc_contractor', '')}]")
                                st.markdown(f":grey[Value: €{_del_bf.get('total_eur', 0):,.0f}]")
                                st.markdown(":grey[5 operational sites (2.17 MWp, 4 MWh). Day 1 revenue.]")

                    st.markdown(f"""
**Integrator:** {delivery['integrator']['name']} ({delivery['integrator']['country']}) serves as
the project integrator and wrapper across all three delivery scopes.
                    """)

                    st.divider()

                    # Budget: Fees + IDC (shared across scenarios)
                    st.subheader("Financial Costs")
                    st.caption("Fees and capitalised interest — identical for both scenarios")
                    # Build _all_cost_rows for BOTH scenarios (for content breakdown)
                    _all_cost_rows_gf = []
                    _all_cost_rows_bf = []
                    for _ak in sub_data.get('assets', []):
                        _asset_data = assets_del['assets'].get(_ak, {})
                        if _asset_data and _asset_data.get('line_items'):
                            for _li in _asset_data['line_items']:
                                _split = _li.get('content_split')
                                if _split:
                                    for _sc, _sp in _split.items():
                                        _all_cost_rows_gf.append({"country": _sc, "amount": _li['budget'] * _sp})
                                else:
                                    _all_cost_rows_gf.append({"country": _li['country'], "amount": _li['budget']})
                    _bf_price = _bf_port.get("purchase_price_zar", 60000000)
                    _all_cost_rows_bf.append({"country": "South Africa", "amount": _bf_price / 20.56})
                    _all_cost_rows = _all_cost_rows_gf if _del_lr_active == "Greenfield" else _all_cost_rows_bf

                else:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("EPC Model", scope['epc_model'])
                    c2.metric("EPC Contractor", scope['epc_contractor'])
                    c3.metric("Scope Value", f"€{scope['total_eur']:,.0f}")

                    st.markdown(f"""
**Integrator:** {delivery['integrator']['name']} ({delivery['integrator']['country']}) serves as
the project integrator and wrapper across all three delivery scopes.

**{name}** — {scope.get('note', '')}
                    """)

                    st.divider()

                    # --- Full cost breakdown: Assets + Fees + IDC ---
                    st.subheader("Budget Breakdown")
                    st.caption("All capital costs by supplier — assets, financial costs, and capitalised interest")

                    # Collect all cost rows for country aggregation
                    _all_cost_rows = []

                    # 1. Asset line items (from assets.json) — no Status column
                    _sub_asset_keys = sub_data.get('assets', [])
                    for _ak in _sub_asset_keys:
                        _asset_data = assets_del['assets'].get(_ak, {})
                        if _asset_data and _asset_data.get('line_items'):
                            st.markdown(f"**{_asset_data['name']}** — {_asset_data.get('description', '')}")
                            _li_rows = []
                            for _li in _asset_data['line_items']:
                                _li_rows.append({
                                    "Supplier": _li['company'],
                                    "Deliverable": _li['delivery'],
                                    "Budget": _li['budget'],
                                    "Country": _li['country'],
                                })
                                _split = _li.get('content_split')
                                if _split:
                                    for _sc, _sp in _split.items():
                                        _all_cost_rows.append({"country": _sc, "amount": _li['budget'] * _sp})
                                else:
                                    _all_cost_rows.append({"country": _li['country'], "amount": _li['budget']})
                            _li_rows.append({
                                "Supplier": "**Total**",
                                "Deliverable": "",
                                "Budget": _asset_data['total'],
                                "Country": "",
                            })
                            render_table(pd.DataFrame(_li_rows), {"Budget": _eur_fmt})

                # 2. Fees (from fees.json) — allocated per entity
                _del_fees_cfg = load_config("fees")
                _del_entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
                _del_entity_sr = _del_entity_data['senior_portion']
                _del_entity_total = _del_entity_data['senior_portion'] + _del_entity_data['mezz_portion']
                _del_project_debt = structure['sources']['senior_debt']['amount']

                st.markdown("**Financial Costs** — Fees allocated to this entity")
                _fee_rows = []
                _fee_total = 0.0
                for _fee in _del_fees_cfg.get("fees", []):
                    _fid = _fee.get("id", "")
                    if _fid == "fee_003" and not _state_bool(f"{entity_key}_eca_atradius", _eca_default(entity_key)):
                        continue
                    if _fid == "fee_004" and not _state_bool(f"{entity_key}_eca_exporter", _eca_default(entity_key)):
                        continue
                    if _fee.get("funding") == "senior_only":
                        _base = _del_entity_sr
                    else:
                        _base = _del_entity_total
                    _amt = _base * _fee.get("rate", 0)
                    _fee_total += _amt
                    _fee_rows.append({
                        "Description": _fee['description'],
                        "Supplier": _fee['company'],
                        "Budget": _amt,
                        "Country": _fee['country'],
                    })
                    _all_cost_rows.append({"country": _fee['country'], "amount": _amt})
                _fee_rows.append({
                    "Description": "**Total Fees**",
                    "Supplier": "",
                    "Budget": _fee_total,
                    "Country": "",
                })
                render_table(pd.DataFrame(_fee_rows), {"Budget": _eur_fmt})

                # 3. IDC (Interest During Construction) — Netherlands (Invest International)
                _del_sr_rate_fac = structure['sources']['senior_debt']['interest']['rate']
                _del_sr_ic_rate = _del_sr_rate_fac + INTERCOMPANY_MARGIN
                _del_project_idc = financing['loan_detail']['senior']['rolled_up_interest_idc']
                _del_ic_idc = _del_project_idc * (_del_sr_ic_rate / _del_sr_rate_fac) if _del_sr_rate_fac > 0 else _del_project_idc
                _del_entity_share = _del_entity_sr / _del_project_debt if _del_project_debt > 0 else 0
                _del_entity_idc = _del_ic_idc * _del_entity_share

                st.markdown("**Capitalised Interest (IDC)** — Interest during construction, allocated pro-rata")
                _idc_rows = [{
                    "Description": "Senior IC IDC",
                    "Supplier": "Invest International",
                    "Budget": _del_entity_idc,
                    "Country": "Netherlands",
                }]
                render_table(pd.DataFrame(_idc_rows), {"Budget": _eur_fmt})
                _all_cost_rows.append({"country": "Netherlands", "amount": _del_entity_idc})

                st.divider()

                # --- Actual country-wise content breakdown ---
                st.subheader("Content Breakdown")
                st.caption("Actual country-of-origin breakdown — assets, fees, and IDC combined")

                _pie_colors = {
                    "Netherlands": "#FF6B00", "Ireland": "#169B62",
                    "South Africa": "#007A4D", "Finland": "#003580",
                    "Australia": "#FFD700", "France": "#002395",
                    "Europe": "#94a3b8",
                }

                # LanRED: side-by-side content breakdown for both scenarios
                if entity_key == 'lanred' and scope.get('scenario_toggle'):
                    # Compute fee+IDC costs (shared across both scenarios)
                    _shared_fees_idc = []
                    for _fr in _fee_rows:
                        if _fr.get("Country") and _fr.get("Budget") and _fr["Country"] != "":
                            _shared_fees_idc.append({"country": _fr["Country"], "amount": _fr["Budget"]})
                    _shared_fees_idc.append({"country": "Netherlands", "amount": _del_entity_idc})

                    _cb_col_gf, _cb_col_bf = st.columns(2)
                    for _cb_col, _cb_label, _cb_asset_rows in [
                        (_cb_col_gf, "Greenfield", _all_cost_rows_gf),
                        (_cb_col_bf, "Brownfield+", _all_cost_rows_bf),
                    ]:
                        _cb_all = _cb_asset_rows + _shared_fees_idc
                        _cb_totals = {}
                        for _cr in _cb_all:
                            _c = _cr['country']
                            if _c:
                                _cb_totals[_c] = _cb_totals.get(_c, 0.0) + _cr['amount']
                        _cb_grand = sum(_cb_totals.values())
                        _cb_sorted = sorted(_cb_totals.items(), key=lambda x: -x[1])
                        with _cb_col:
                            with st.container(border=True):
                                st.markdown(f"**{_cb_label}**")
                                _cb_rows = []
                                for _country, _val in _cb_sorted:
                                    _pct = _val / _cb_grand if _cb_grand > 0 else 0
                                    _cb_rows.append({"Country": _country, "Amount": _val, "Share": f"{_pct*100:.1f}%"})
                                _cb_rows.append({"Country": "**Total**", "Amount": _cb_grand, "Share": "100%"})
                                render_table(pd.DataFrame(_cb_rows), {"Amount": _eur_fmt})
                                _cb_labels = [c for c, _ in _cb_sorted]
                                _cb_values = [v for _, v in _cb_sorted]
                                _cb_clrs = [_pie_colors.get(c, "#94a3b8") for c in _cb_labels]
                                fig_pie = go.Figure(data=[go.Pie(
                                    labels=_cb_labels, values=_cb_values,
                                    marker=dict(colors=_cb_clrs),
                                    textinfo='label+percent', textfont=dict(size=11), hole=0.35,
                                )])
                                fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=250)
                                st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    _country_totals = {}
                    for _cr in _all_cost_rows:
                        _c = _cr['country']
                        if _c:
                            _country_totals[_c] = _country_totals.get(_c, 0.0) + _cr['amount']
                    _grand_total = sum(_country_totals.values())

                    _sorted_countries = sorted(_country_totals.items(), key=lambda x: -x[1])
                    _content_rows = []
                    for _country, _val in _sorted_countries:
                        _pct = _val / _grand_total if _grand_total > 0 else 0
                        _content_rows.append({
                            "Country": _country,
                            "Amount": _val,
                            "Share": f"{_pct*100:.1f}%",
                        })
                    _content_rows.append({
                        "Country": "**Total**",
                        "Amount": _grand_total,
                        "Share": "100%",
                    })
                    _ct1, _ct2 = st.columns([3, 2])
                    with _ct1:
                        render_table(pd.DataFrame(_content_rows), {"Amount": _eur_fmt})
                    with _ct2:
                        _pie_labels = [c for c, _ in _sorted_countries]
                        _pie_values = [v for _, v in _sorted_countries]
                        _pie_clrs = [_pie_colors.get(c, "#94a3b8") for c in _pie_labels]
                        fig_pie = go.Figure(data=[go.Pie(
                            labels=_pie_labels,
                            values=_pie_values,
                            marker=dict(colors=_pie_clrs),
                            textinfo='label+percent',
                            textfont=dict(size=12),
                            hole=0.35,
                        )])
                        fig_pie.update_layout(
                            showlegend=False,
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=280,
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

                # ── ECA Content Compliance ──
                st.divider()
                st.subheader("ECA Content Compliance")

                if entity_key == 'lanred':
                    st.info("LanRED content breakdown is TBD — solar assets underwritten separately.")
                else:
                    # Compute combined envelope (NWL + TWX) for the decisive test
                    _env_countries = {}
                    _env_total = 0.0
                    _this_countries = dict(_country_totals)  # current entity already computed above
                    _this_total = _grand_total
                    for _ek in ['nwl', 'timberworx']:
                        _ek_c, _ek_t = _compute_entity_content(_ek)
                        for _c, _v in _ek_c.items():
                            _env_countries[_c] = _env_countries.get(_c, 0.0) + _v
                        _env_total += _ek_t

                    _this_sa = _this_countries.get('South Africa', 0) / _this_total if _this_total > 0 else 0
                    _this_nl = _this_countries.get('Netherlands', 0) / _this_total if _this_total > 0 else 0
                    _env_sa = _env_countries.get('South Africa', 0) / _env_total if _env_total > 0 else 0
                    _env_nl = _env_countries.get('Netherlands', 0) / _env_total if _env_total > 0 else 0

                    _col_entity, _col_envelope = st.columns(2)
                    with _col_entity:
                        st.markdown(f"**{name}** (this entity)")
                        st.metric("SA Content", f"{_this_sa*100:.1f}%",
                                  "< 50%" if _this_sa < 0.50 else "≥ 50%")
                        st.metric("Dutch Content", f"{_this_nl*100:.1f}%",
                                  "≥ 20%" if _this_nl >= 0.20 else "< 20%")
                    with _col_envelope:
                        st.markdown("**Combined Envelope** (NWL + TWX)")
                        st.metric("SA Content", f"{_env_sa*100:.1f}%",
                                  "Pass" if _env_sa < 0.50 else "Fail")
                        st.metric("Dutch Content", f"{_env_nl*100:.1f}%",
                                  "Pass" if _env_nl >= 0.20 else "Fail")

                    _comp_tests = [
                        {
                            "Test": "OECD Local Content",
                            "Rule": "< 50% SA",
                            f"{name}": f"{_this_sa*100:.1f}%",
                            "Envelope": f"{_env_sa*100:.1f}%",
                            "Result": "Pass" if _env_sa < 0.50 else "Fail",
                        },
                        {
                            "Test": "Atradius Dutch Content",
                            "Rule": "≥ 20% NL",
                            f"{name}": f"{_this_nl*100:.1f}%",
                            "Envelope": f"{_env_nl*100:.1f}%",
                            "Result": "Pass" if _env_nl >= 0.20 else "Fail",
                        },
                    ]
                    _df_comp = pd.DataFrame(_comp_tests)

                    def _color_compliance(val):
                        if val == "Pass":
                            return "background-color: #d4edda; color: #155724"
                        elif val == "Fail":
                            return "background-color: #f8d7da; color: #721c24"
                        return ""

                    st.table(_df_comp.style.map(_color_compliance, subset=["Result"])
                        .set_properties(subset=[f"{name}", "Envelope"], **{"text-align": "right"}))
                    st.caption("**Envelope is decisive** — individual entities may deviate, but the "
                               "combined Colubris wrapper envelope is what Atradius assesses. "
                               "LanRED excluded (underwritten separately).")

                st.divider()

                # Key contractors (from contractors.json)
                _key_vendors = scope.get('key_vendors', [])
                if _key_vendors:
                    st.subheader("Key Contractors & Suppliers")
                    for _vk in _key_vendors:
                        _cv = contractors['contractors'].get(_vk, {})
                        if _cv:
                            _clogo = _cv.get('logo', '')
                            with st.container(border=True):
                                _vl, _vt = st.columns([1, 8])
                                with _vl:
                                    if _clogo and (LOGO_DIR / _clogo).exists():
                                        st.image(str(LOGO_DIR / _clogo), width=80)
                                with _vt:
                                    st.markdown(f"### {_cv['name']}")
                                    st.caption(f"{_cv.get('role', '')} | {_cv['country']}")
                                st.markdown(_cv.get('overview', ''))
                                if _cv.get('capabilities'):
                                    st.markdown("**Key Capabilities:**")
                                    for cap in _cv['capabilities']:
                                        st.markdown(f"- {cap}")
                                if _cv.get('project_role'):
                                    st.info(f"**Project Role:** {_cv['project_role']}")
                                if _cv.get('eca_relevance'):
                                    st.caption(f"ECA: {_cv['eca_relevance']}")


# ============================================================
# SIDEBAR NAVIGATION — native st.button with Material icons
# ============================================================

_PROJ_NAV = [
    ("Catalytic Assets", ":material/developer_board:"),
    ("New Water Lanseria", ":material/water_drop:"),
    ("LanRED", ":material/wb_sunny:"),
    ("Timberworx", ":material/home:"),
]
_proj_items = [(n, ic) for n, ic in _PROJ_NAV if n in _allowed_entities]

_allowed_mgmt = get_allowed_mgmt_pages(_current_user, _auth_config)
_MGMT_NAV_ALL = [
    ("Summary", ":material/description:"),
    ("Strategy", ":material/explore:"),
    ("Tasks", ":material/task_alt:"),
    ("CP & CS", ":material/assignment_turned_in:"),
    ("Guarantor Analysis", ":material/verified_user:"),
]
_mgmt_items = [(n, ic) for n, ic in _MGMT_NAV_ALL if n in _allowed_mgmt]
if _can_manage:
    _mgmt_items.append(("Users", ":material/group:"))

# Single active nav item across both sections
if "nav_entity" not in st.session_state:
    st.session_state.nav_entity = _proj_items[0][0] if _proj_items else "Summary"

# CSS: style sidebar buttons to match option-menu look
st.markdown("""
<style>
    /* Sidebar nav buttons */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        text-align: left !important;
        justify-content: flex-start !important;
        font-size: 13px !important;
        padding: 7px 12px !important;
        border-radius: 6px !important;
        margin: 1px 0 !important;
        width: 100% !important;
        transition: background-color 0.15s ease !important;
        gap: 8px !important;
    }
    /* Ensure button content (div and p) is also left-aligned */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] > div,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] > div {
        text-align: left !important;
        justify-content: flex-start !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] p,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p {
        text-align: left !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        background-color: transparent !important;
        border: none !important;
        color: #334155 !important;
        font-weight: 400 !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #f1f5f9 !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background-color: #1e40af !important;
        border: none !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
        background-color: #1e3a8a !important;
    }
    /* Icon color in inactive buttons */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] span[data-testid="stIconMaterial"] {
        color: #64748b !important;
        font-size: 18px !important;
    }
    /* Icon color in active buttons */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {
        color: #ffffff !important;
        font-size: 18px !important;
    }

    /* Facility section borders */
    .facility-section {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin: 16px 0;
        background-color: #f8fafc;
    }
    .facility-section h3 {
        margin-top: 0;
        color: #1e40af;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.caption("PROJECTS")
    for _nav_name, _nav_icon in _proj_items:
        _is_active = st.session_state.nav_entity == _nav_name
        if st.button(
            _nav_name, key=f"nav_{_nav_name}", icon=_nav_icon,
            use_container_width=True,
            type="primary" if _is_active else "secondary",
        ):
            st.session_state.nav_entity = _nav_name
            st.rerun()

    st.divider()
    st.caption("MANAGEMENT")
    for _nav_name, _nav_icon in _mgmt_items:
        _is_active = st.session_state.nav_entity == _nav_name
        if st.button(
            _nav_name, key=f"nav_{_nav_name}", icon=_nav_icon,
            use_container_width=True,
            type="primary" if _is_active else "secondary",
        ):
            st.session_state.nav_entity = _nav_name
            st.rerun()

entity = st.session_state.nav_entity

# --- Spacer: pushes account section to sidebar bottom ---
st.sidebar.markdown(
    '<div style="min-height:calc(100vh - 480px)"></div>',
    unsafe_allow_html=True,
)

# --- Sidebar bottom: user info + logout ---
_user_email = _auth_config['credentials']['usernames'].get(_current_user, {}).get('email', '')
st.sidebar.divider()
st.sidebar.caption(f"Signed in as **{_current_user}**  \n{_user_email} · {_role_label}")
authenticator.logout("Logout", location="sidebar", key="sidebar_logout")
st.sidebar.caption("NexusNovus | Financial Model")

# ── Guarantor JSON helpers (module-level for use across entity tabs) ──
_GUARANTOR_ROOT = Path(__file__).parent / "data" / "guarantor"

@st.cache_data(ttl=300)
def _load_guarantor_config() -> dict:
    """Load guarantor.json corporate hierarchy config."""
    _gc_path = Path(__file__).parent / "config" / "guarantor.json"
    if _gc_path.exists():
        with open(_gc_path, 'r') as fh:
            return json.load(fh)
    return {}

@st.cache_data(ttl=300)
def _load_guarantor_jsons(subdir: str) -> dict:
    """Load all *_structured.json from a guarantor subdirectory."""
    target = _GUARANTOR_ROOT / subdir if subdir else _GUARANTOR_ROOT
    out = {}
    for fp in sorted(target.glob("*_structured.json")):
        with open(fp, 'r') as fh:
            out[fp.stem] = json.load(fh)
    return out

def _gval(data, *keys, idx=0, default=None):
    """Safely traverse nested dict → values[idx]."""
    node = data
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
        if node is None:
            return default
    if isinstance(node, dict) and "values" in node:
        vals = node["values"]
        return vals[idx] if idx < len(vals) and vals[idx] is not None else default
    if isinstance(node, list):
        return node[idx] if idx < len(node) and node[idx] is not None else default
    return node if node is not None else default

def _fmtr(val, millions=False):
    """Format ZAR. Negative in parentheses."""
    if val is None or val == 0:
        return "—"
    if millions:
        v = val / 1_000_000
        return f"(R{abs(v):,.1f}M)" if v < 0 else f"R{v:,.1f}M"
    return f"(R{abs(val):,.0f})" if val < 0 else f"R{val:,.0f}"

# Business write-ups per entity (from AFS metadata and email correspondence)
_ENTITY_WRITEUPS = {
    "AquasideTrading_2025_structured": "Owns 4 residential rental properties in Saxonwold, Johannesburg plus 1 in George, Cape Town. Stable rental income. 100% VPH subsidiary.",
    "BBPUnit1PhaseII_2025_structured": "Commercial property in Randpark Ridge, Randburg. Rented to the group's financial services business. 100% VPH subsidiary. Compiled (not reviewed) AFS.",
    "CornerstonePropertyGroup_2025_structured": "Holding company (R160 total assets). Holds Ireo Project 10 (formerly Chepstow Properties — industrial, Bellville CT) as subsidiary. 50% VPH subsidiary.",
    "Erf86LongmeadowBusinessEstate_2025_structured": "Commercial property with PV solar installation in Longmeadow Business Estate, Gauteng. 100% VPH subsidiary.",
    "IreoProject10_2025_structured": "Industrial property in Bellville, Cape Town. Formerly Chepstow Investments. Major growth in FY2025 — assets from R1.2M to R75.5M (acquisition). Audited by M Kruger (not KCE). Sub of Cornerstone.",
    "Mistraline_2025_structured": "Industrial property in Linbro Park, Johannesburg (Mastiff Sandton). Valued at R160.5M. 33% associate of VPH. Commercial + PV solar income.",
    "ProvidencePropertyInvestments_2025_structured": "13 residential investment properties in Tyrwhitt, Rosebank, Johannesburg. R49.6M property value. R40M in group company loans. Sub: Manappu Investments (20%, 50 units). 100% VPH subsidiary.",
    "SunPropertyInvestments_2025_structured": "Investment holding company. Negative equity (R-8.6M). Persistent losses. Holds 6 On Kloof (25% associate) in Sea Point, CT — 46 hotel/apartment units. 50% VPH subsidiary.",
    "UvongoFallsNo26_2025_structured": "Residential development in Morningside Ext 5, Sandton. Largest property in VPH portfolio (R337M). GOING CONCERN — R108.5M current shareholder loans. 50% VPH subsidiary.",
    "SixOnKloof_2025_structured": "46 investment units in Sea Point, Cape Town — hotel management. Recovered from negative equity in FY2025 (profit R2.3M). 25% associate via Sun Property. Audited by AC Venter.",
    "BrackenfellCorner_2025_structured": "Retail convenience centre in Brackenfell, Cape Town. R259M investment property. Negative equity (-R6.8M) but profitable (R983k). R19.6M shareholder loans. Via Phoenix Prop Fund SA.",
    "ChartwellCorner_2025_structured": "Retail convenience centre in Fourways, JHB. R104M investment property. GOING CONCERN — deeply negative equity (-R27.9M), R17.9M loss. Via Phoenix Prop Fund SA.",
    "ChartwellCoOwner_2025_structured": "Pass-through entity for Chartwell Corner co-ownership. Zero net income — all passes to co-owners. R3.7M total assets.",
    "JukskeiMeander_2025_structured": "Retail convenience centre in Midrand, JHB. R84M investment property. Thin equity (R1.8M), R9.4M loss FY2025. Via Phoenix Prop Fund SA.",
    "MadeliefShoppingCentre_2025_structured": "Retail shopping centre. R141M property. Strongest Phoenix entity — R13.4M equity, R12.1M profit. Via Renovo Property Fund.",
    "OlivedaleCorner_2025_structured": "Retail convenience centre in Olivedale, JHB. R132M property. Slightly negative equity (-R1.6M) but profitable (R1.1M). Via Phoenix Prop Fund SA.",
    "PhoenixPropertyFundSA_2025_structured": "Holding company for 6 retail properties. Deeply negative equity (-R19.6M) from subsidiary impairments. R19.7M group loans. Sub of Phoenix Specialist.",
    "PhoenixSpecialistPropertyFund_2025_structured": "Dormant shell (R100 assets). Top Phoenix Group holding. Shareholders: Trillium + VH Properties. Key mgmt: M van Houten, RM O'Sullivan.",
    "PRAAM_2025_structured": "Asset management company and intercompany lending hub. R23M loans to group, R26.4M loans from group. R3.5M cash. R988k profit.",
    "RenovoPropertyFund_2025_structured": "Holding company for Madelief (100%). Shareholders: Trillium + Veracity Property Investments (cross-ownership). R16.4M equity, R15.2M profit.",
    "RidgeviewCentre_2025_structured": "Retail centre in Midrand. R185M property. GOING CONCERN — negative equity (-R21.6M), R18.4M loss. Sale agreement with bondholder. R224M liabilities. Via Phoenix Prop Fund SA.",
}

def _render_sub_financials(data, prefix):
    """Render BS / P&L tabs from a structured JSON."""
    bs = data.get("statement_of_financial_position") or {}
    pl = data.get("statement_of_comprehensive_income") or {}
    meta = data.get("metadata") or {}
    clbl = meta.get("presentation_columns", ["CY", "PY"])
    _tb, _tp = st.tabs(["Balance Sheet", "P&L"])
    with _tb:
        rows = []
        nca = bs.get("assets", {}).get("non_current_assets", {})
        for lbl, key in [("Investment property", "investment_property"), ("Other financial assets", "other_financial_assets"),
                         ("Investments in subsidiaries", "investments_in_subsidiaries"), ("Loans to shareholders", "loans_to_shareholders"), ("Deferred tax", "deferred_tax")]:
            item = nca.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        nca_t = _gval(bs, "assets", "non_current_assets", "total")
        nca_tp = _gval(bs, "assets", "non_current_assets", "total", idx=1)
        if nca_t:
            rows.append(("**Total NCA**", f"**{_fmtr(nca_t)}**", f"**{_fmtr(nca_tp)}**"))
        ca = bs.get("assets", {}).get("current_assets", {})
        for lbl, key in [("Trade & other receivables", "trade_and_other_receivables"), ("Cash & equivalents", "cash_and_cash_equivalents")]:
            item = ca.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        ta = _gval(bs, "assets", "total_assets")
        ta_p = _gval(bs, "assets", "total_assets", idx=1)
        rows.append(("**Total Assets**", f"**{_fmtr(ta)}**", f"**{_fmtr(ta_p)}**"))
        rows.append(("", "", ""))
        eq = bs.get("equity_and_liabilities", {}).get("equity", {})
        for lbl, key in [("Share capital", "share_capital"), ("Retained income", "retained_income"), ("Accumulated loss", "accumulated_loss")]:
            item = eq.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        te = _gval(bs, "equity_and_liabilities", "equity", "total_equity")
        te_p = _gval(bs, "equity_and_liabilities", "equity", "total_equity", idx=1)
        rows.append(("**Total Equity**", f"**{_fmtr(te)}**", f"**{_fmtr(te_p)}**"))
        ncl = bs.get("equity_and_liabilities", {}).get("non_current_liabilities", {})
        for lbl, key in [("Other financial liabilities", "other_financial_liabilities"), ("Loans from group", "loans_from_group_companies")]:
            item = ncl.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        cl = bs.get("equity_and_liabilities", {}).get("current_liabilities", {})
        for lbl, key in [("Trade & other payables", "trade_and_other_payables"), ("Provisions", "provisions")]:
            item = cl.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        tel = _gval(bs, "equity_and_liabilities", "total_equity_and_liabilities")
        tel_p = _gval(bs, "equity_and_liabilities", "total_equity_and_liabilities", idx=1)
        rows.append(("**Total E&L**", f"**{_fmtr(tel)}**", f"**{_fmtr(tel_p)}**"))
        _render_fin_table(rows, ["Line Item", clbl[0], clbl[1]])
        cs = meta.get("verification_checksums", {}).get("cy_2025", {})
        if cs.get("balance_check"):
            st.caption("Balance check: PASS")
    with _tp:
        rows = []
        for lbl, key in [("Revenue", "revenue"), ("Other income", "other_income"), ("FV adjustments", "other_income_fair_value"),
                         ("Operating expenses", "operating_expenses"), ("Impairment", "impairment_investments"),
                         ("**Operating profit/(loss)**", "operating_profit_loss"), ("**Operating profit/(loss)**", "operating_profit"),
                         ("Investment revenue", "investment_revenue"), ("Finance costs", "finance_costs"),
                         ("Loss on disposal", "loss_on_disposal"),
                         ("PBT", "profit_loss_before_taxation"), ("PBT", "profit_before_taxation"), ("PBT", "loss_before_taxation"),
                         ("Taxation", "taxation"),
                         ("**Profit/(Loss)**", "profit_loss_for_the_year"), ("**Profit**", "profit_for_the_year"), ("**Loss**", "loss_for_the_year")]:
            item = pl.get(key)
            if item and isinstance(item, dict):
                vals = item.get("values", [None, None])
                cy, py = (vals[0] if len(vals) > 0 else None), (vals[1] if len(vals) > 1 else None)
                if cy is not None or py is not None:
                    rows.append((lbl, _fmtr(cy), _fmtr(py)))
        if rows:
            _render_fin_table(rows, ["Line Item", clbl[0], clbl[1]])
        else:
            st.info("No P&L data (dormant entity)")

def _render_sub_summary_and_toggles(subs_dict, key_prefix):
    """Render summary table + per-company expanders with write-ups and BS/P&L."""
    summary_rows = []
    for stem, sdata in sorted(subs_dict.items()):
        smeta = sdata.get("metadata", {})
        sent = smeta.get("entity", {})
        sbs = sdata.get("statement_of_financial_position", {})
        spl = sdata.get("statement_of_comprehensive_income", {})
        s_ta = _gval(sbs, "assets", "total_assets")
        s_te = _gval(sbs, "equity_and_liabilities", "equity", "total_equity")
        s_rev = _gval(spl, "revenue")
        s_pat = None
        for pk in ["profit_loss_for_the_year", "profit_for_the_year", "loss_for_the_year"]:
            s_pat = _gval(spl, pk)
            if s_pat is not None:
                break
        s_ip = _gval(sbs, "assets", "non_current_assets", "investment_property")
        s_isub = _gval(sbs, "assets", "non_current_assets", "investments_in_subsidiaries")
        flag = ""
        notes = smeta.get("notes", {})
        if smeta.get("going_concern") is False:
            flag = " [GC]"
        elif notes.get("negative_equity"):
            flag = " [-ve]"
        elif notes.get("dormant_entity"):
            flag = " [Dormant]"
        elif notes.get("pass_through_entity"):
            flag = " [Pass-thru]"
        elif notes.get("holding_company"):
            flag = " [HoldCo]"
        summary_rows.append((
            sent.get("legal_name", stem) + flag,
            _fmtr(s_ta, millions=True), _fmtr(s_te, millions=True),
            _fmtr(s_ip or s_isub, millions=True),
            _fmtr(s_rev, millions=True), _fmtr(s_pat, millions=True),
        ))
    _render_fin_table(summary_rows, ["Entity", "Assets", "Equity", "Inv. Prop/Subs", "Revenue", "PAT"])
    st.caption("[GC] = Going concern, [-ve] = Negative equity, [HoldCo] = Holding co, [Dormant] = No activity")
    for stem, sdata in sorted(subs_dict.items()):
        smeta = sdata.get("metadata", {})
        sent = smeta.get("entity", {})
        sname = sent.get("legal_name", stem)
        s_ta = _gval(sdata.get("statement_of_financial_position", {}), "assets", "total_assets")
        tag = ""
        notes = smeta.get("notes", {})
        if smeta.get("going_concern") is False:
            tag = " -- GOING CONCERN"
        elif notes.get("negative_equity"):
            tag = " -- Negative Equity"
        elif notes.get("dormant_entity"):
            tag = " -- Dormant"
        elif notes.get("pass_through_entity"):
            tag = " -- Pass-through"
        elif notes.get("holding_company"):
            tag = " -- Holding Company"
        with st.expander(f"{sname} ({_fmtr(s_ta, millions=True)}){tag}", expanded=False):
            wu = _ENTITY_WRITEUPS.get(stem, "")
            if wu:
                st.markdown(f"*{wu}*")
            sc1, sc2 = st.columns(2)
            sc1.caption(f"Reg: {sent.get('registration_number', 'N/A')}")
            sc2.caption(f"{smeta.get('auditor', {}).get('designation', '')} by {smeta.get('auditor', {}).get('name', '')}")
            if smeta.get("going_concern") is False:
                st.error(smeta.get("going_concern_note", "Going concern doubt noted by directors."))
            if notes.get("dormant_entity"):
                st.warning(notes.get("dormant_comment", "Dormant shell entity."))
            _render_sub_financials(sdata, f"{key_prefix}_{stem}")


def _render_nested_financials(node, subs_dict, key_prefix, depth=0):
    """Recursively render financial toggles following guarantor.json hierarchy."""
    json_key = node.get("json")
    sdata = subs_dict.get(json_key) if json_key else None

    name = node["name"]
    ownership = node.get("ownership", "")
    otype = node.get("type", "subsidiary")

    # Build label
    label = f"{'  ' * depth}{name} ({ownership}%"
    if otype == "associate":
        label += ", associate"
    label += ")"

    if sdata:
        ta = _gval(sdata.get("statement_of_financial_position", {}) or {}, "assets", "total_assets")
        label += f" — {_fmtr(ta, millions=True)}"
    elif node.get("no_afs"):
        label += " — [No AFS]"

    with st.expander(label, expanded=False):
        # Write-up
        wu = _ENTITY_WRITEUPS.get(json_key, "") if json_key else ""
        if wu:
            st.markdown(f"*{wu}*")
        # Asset description
        asset_desc = node.get("asset", "")
        if asset_desc and not wu:
            st.caption(asset_desc)
        # Metadata from JSON
        if sdata:
            smeta = sdata.get("metadata", {})
            sent = smeta.get("entity", {})
            sc1, sc2 = st.columns(2)
            sc1.caption(f"Reg: {sent.get('registration_number', 'N/A')}")
            sc2.caption(f"{smeta.get('auditor', {}).get('designation', '')} by {smeta.get('auditor', {}).get('name', '')}")
            if smeta.get("going_concern") is False:
                st.error(smeta.get("going_concern_note", "Going concern doubt noted by directors."))
            notes = smeta.get("notes", {})
            if notes.get("dormant_entity"):
                st.warning(notes.get("dormant_comment", "Dormant shell entity."))
            _render_sub_financials(sdata, f"{key_prefix}_{node['key']}")
        elif node.get("no_afs"):
            st.info("No annual financial statements available for this entity.")
            note = node.get("note", "")
            if note:
                st.caption(note)
        # Children (nested inside parent's expander)
        children = node.get("children", [])
        if children:
            st.divider()
            st.caption(f"Subsidiaries / Associates of {name}:")
            for child in children:
                _render_nested_financials(child, subs_dict, key_prefix, depth + 1)


def _render_email_qa(guarantor_config):
    """Render the guarantor Q&A email thread."""
    qa_items = guarantor_config.get("email_qa", [])
    if not qa_items:
        return
    with st.expander("Guarantor Q&A — Robbert Zappeij / Mark van Houten (Feb-Mar 2025)", expanded=False):
        for item in qa_items:
            with st.container(border=True):
                st.markdown(f"**Q:** {item['q']}")
                st.markdown(f"**A ({item['from']}, {item['date']}):** {item['a']}")


# ============================================================
# SCLCA HOLDING COMPANY VIEW
# ============================================================
if entity == "Catalytic Assets":
    # Header
    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        logo_path = LOGO_DIR / "lanseria-smart-city-logo.png"
        if logo_path.exists():
            st.image(str(logo_path), width=100)
    with col_title:
        st.title("Smart City Lanseria — Catalytic Assets")
        st.caption("Financial holding company financing water, solar, and training infrastructure for the Lanseria Smart City development")

    # --- Financing Scenario (read from session state; widgets rendered in Waterfall tab) ---
    nwl_swap_enabled = st.session_state.get("sclca_nwl_hedge", "CC DSRA \u2192 FEC") == "Cross-Currency Swap"
    lanred_swap_enabled = st.session_state.get("lanred_scenario", "Greenfield") == "Greenfield"

    # Sub-tabs for SCLCA
    _tab_map = make_tab_map(_allowed_tabs)

    # Shared config
    senior_detail = financing['loan_detail']['senior']

    # --- Pre-compute DSRA from senior loan debt service (P+I) ---
    _sr_detail = financing['loan_detail']['senior']
    _sr_balance = (_sr_detail['loan_drawdown_total']
                   + _sr_detail['rolled_up_interest_idc']
                   - _sr_detail['grant_proceeds_to_early_repayment']
                   - _sr_detail['gepf_bulk_proceeds'])
    _sr_rate = structure['sources']['senior_debt']['interest']['rate']
    _sr_num = structure['sources']['senior_debt']['repayments']
    _sr_p = _sr_balance / _sr_num
    _dsra_n = structure['sources']['dsra']['sizing']['repayments_covered']

    # DSRA principle: 2×(P + I_M24) — covers 2 full debt service payments
    _sr_interest_m24 = _sr_balance * _sr_rate / 2
    dsra_principle_fixed = 2 * (_sr_p + _sr_interest_m24)

    # Total DSRA debt service (for reference)
    computed_dsra_eur = 0
    _dsra_bal = _sr_balance
    for _ in range(_dsra_n):
        computed_dsra_eur += _sr_p + (_dsra_bal * _sr_rate / 2)
        _dsra_bal -= _sr_p

    # ============================================================
    # 10-YEAR FINANCIAL MODEL (semi-annual → annual)
    # ============================================================
    _mz_cfg = structure['sources']['mezzanine']
    _mz_dtl = financing['loan_detail']['mezzanine']
    _fx_m = _mz_cfg['amount_eur'] / _mz_cfg['amount_zar']
    _loans_m = structure['uses']['loans_to_subsidiaries']
    _mz_r = _mz_cfg['interest']['total_rate']
    _sr_ic_r = _sr_rate + INTERCOMPANY_MARGIN
    _mz_ic_r = _mz_r + INTERCOMPANY_MARGIN
    _mz_eur = _mz_cfg['amount_eur']
    _mz_rollup = _mz_dtl['rolled_up_interest_zar'] * _fx_m
    _mz_after = _mz_eur + _mz_rollup
    _mz_n = 10
    _mz_p_per = _mz_after / _mz_n
    _sr_draw = _sr_detail['loan_drawdown_total']
    _sr_idc = _sr_detail['rolled_up_interest_idc']
    _sr_prepay_amt = (_sr_detail['grant_proceeds_to_early_repayment']
                      + _sr_detail['gepf_bulk_proceeds'])

    # IC loans - initial amounts
    _ic_sr = sum(l['senior_portion'] for l in _loans_m.values())
    _ic_mz = sum(l['mezz_portion'] for l in _loans_m.values())

    # IC IDC is HIGHER than facility IDC due to 0.5% margin
    # IC_IDC = Facility_IDC × (IC_rate / Facility_rate)
    _ic_sr_idc = _sr_idc * (_sr_ic_r / _sr_rate) if _sr_rate > 0 else _sr_idc

    # IC Mezz rolled-up interest is HIGHER than facility due to 0.5% margin
    # IC_Mezz_Rollup = Facility_Mezz_Rollup × (IC_rate / Facility_rate)
    _ic_mz_rollup = _mz_rollup * (_mz_ic_r / _mz_r) if _mz_r > 0 else _mz_rollup
    _ic_mz_after = _mz_eur + _ic_mz_rollup  # IC Mezz balance after rollup

    # IC loan principal based on IC BALANCE (higher than facility due to margin on IDC/rollup)
    # IC loans amortize fully on their own schedule; excess vs facility stays at SCLCA as cash
    _ic_sr_balance = _sr_draw + _ic_sr_idc - _sr_prepay_amt  # IC balance after IDC & prepayment
    _ic_sr_p = _ic_sr_balance / _sr_num  # IC principal per period
    _ic_mz_p = _ic_mz_after / _mz_n  # IC Mezz principal per period

    # Drawdown schedule from config: [8789117, 2835775, 1818036, 0] at M0, M6, M12, M18
    _sr_drawdowns = senior_detail['drawdown_schedule']  # [8789117, 2835775, 1818036, 0]
    _sr_draw_months = [0, 6, 12, 18]  # Periods -4, -3, -2, -1

    # Build IC schedules bottom-up from subsidiaries (NWL canon)
    _ic_sem, _entity_ic = _build_all_entity_ic_schedules(
        nwl_swap_enabled=nwl_swap_enabled,
        lanred_swap_enabled=lanred_swap_enabled,
    )

    # Semi-annual balance simulation (20 periods = 10 years)
    # Facility side computed here; IC side from bottom-up aggregation
    _sem = []
    _sb = 0.0; _mb = 0.0
    for _pi in range(20):
        _m = _pi * 6
        _so, _mo = _sb, _mb
        # Track drawdowns per period
        _draw_sr = 0.0   # Senior drawdown this period
        _draw_mz = 0.0   # Mezz drawdown this period
        _draw_dsra = 0.0 # DSRA funding this period
        _draw_in = 0.0   # Total drawdowns from facilities
        _draw_out = 0.0  # Total deployments to IC loans
        _prepay_in = 0.0   # Prepayment from IC loan
        _prepay_out = 0.0  # Prepayment to facility

        # Senior drawdowns per schedule
        if _m in _sr_draw_months:
            idx = _sr_draw_months.index(_m)
            _draw_sr = _sr_drawdowns[idx]
            _sb += _draw_sr

        # Mezz drawdown at M0
        if _m == 0:
            _draw_mz = _mz_eur
            _mb = _mz_eur

        # Total drawdowns this period
        _draw_in = _draw_sr + _draw_mz
        _draw_out = _draw_sr + _draw_mz  # Pass-through to IC loans

        # IDC capitalization and prepayment at M18
        if _m == 18:
            _sb += _sr_idc - _sr_prepay_amt  # Facility: add IDC, subtract prepayment
            _prepay_in = _sr_prepay_amt       # Prepayment received from NWL IC loan
            _prepay_out = _sr_prepay_amt      # Prepayment paid to Senior facility

        # DSRA funding at M24 (pass-through to FEC)
        # Also capitalize rolled-up interest on Mezz facility
        if _m == 24:
            _draw_dsra = computed_dsra_eur
            _mb = _mz_after          # Facility Mezz: add rolled-up interest
        if _m >= 24 and _sb > 1:
            _sb -= _sr_p
        if _m >= 30 and _mb > 1:
            _mb -= _mz_p_per
        _sb, _mb = max(_sb, 0), max(_mb, 0)
        # Calculate accrued interest on FACILITY side.
        # The BS uses config-derived balances (lump-sum IDC at M18, Mezz rollup at M24)
        # which use more precise compounding than semi-annual opening-balance interest.
        # To eliminate the BS gap, we derive P&L interest from the actual balance changes
        # during construction, so the P&L expense exactly matches the liability movement.
        #
        # For Senior: IDC applied as lump sum at M18 → derive interest at M18 from balance change.
        #   Before M18, Sr balance only changes by drawdowns, so interest = 0 for P&L.
        #   At M18, interest = full config IDC (Closing - Opening - Drawdown + Prepayment).
        #   After M24, interest = opening × rate / 2 (standard semi-annual, paid in cash).
        #
        # For Mezz: Rollup applied as lump sum at M24 → derive interest at M24 from balance change.
        #   Before M24, Mz balance only changes by initial drawdown (M0), so interest = 0 for P&L.
        #   At M24, interest = full rollup amount (Closing + Repayment - Opening - DSRA_draw).
        #   After M24, interest = opening × rate / 2 (standard semi-annual, paid in cash).
        #
        # Senior: derive from balance change for M0-M18, simple interest for M24+
        if _m <= 18:
            _si_accrued = max(_sb - _so + _prepay_out - _draw_sr, 0) if _so > 1 or _draw_sr > 0 else 0
        else:
            _si_accrued = _so * _sr_rate / 2 if _so > 1 else 0
        # Mezz: derive from balance change for M0-M24, simple interest for M30+
        # At M24, Mezz balance jumps from _mz_eur to _mz_after (rollup capitalization).
        # The accrued interest includes both the semi-annual interest AND the rollup.
        # Mezz repayment starts at M30, so at M24 there's no principal payment on Mz.
        if _m <= 24:
            # For M24: _mb = _mz_after, _mo = _mz_eur, no Mz drawdown, no Mz repayment
            # Interest = _mz_after - _mz_eur = rollup amount (correct!)
            _mi_accrued = max(_mb - _mo - _draw_mz, 0) if _mo > 1 or _draw_mz > 0 else 0
        else:
            _mi_accrued = _mo * _mz_r / 2 if _mo > 1 else 0
        # Cash interest only after grace period
        # Senior: cash interest starts at M24 (first semi-annual payment after construction)
        _si_cash = _si_accrued if _m >= 24 else 0
        # Mezz: cash interest starts at M30 (M24 rollup is non-cash capitalization)
        _mi_cash = _mi_accrued if _m >= 30 else 0
        # IC side from bottom-up aggregation
        _ic = _ic_sem[_pi]
        _sem.append({
            'yr': _pi // 2 + 1, 'm': _m,
            'so': _so, 'sc': _sb, 'mo': _mo, 'mc': _mb,
            # IC balances/interest/principal — from bottom-up subsidiary schedules
            'iso': _ic['iso'], 'isc': _ic['isc'], 'imo': _ic['imo'], 'imc': _ic['imc'],
            'isi': _ic['isi'], 'imi': _ic['imi'],
            'isi_cash': _ic['isi_cash'], 'imi_cash': _ic['imi_cash'],
            # Accrued interest on facility (for P&L expense)
            'si': _si_accrued, 'mi': _mi_accrued,
            # Cash interest on facility (for Cash Flow)
            'si_cash': _si_cash, 'mi_cash': _mi_cash,
            # Principal movements - DRAWDOWNS (Senior + Mezz)
            'draw_in': _draw_in, 'draw_out': _draw_out,
            'draw_sr': _draw_sr, 'draw_mz': _draw_mz,
            # DSRA funding (pass-through to FEC)
            'draw_dsra': _draw_dsra,
            # Principal movements - PREPAYMENTS
            'prepay_in': _prepay_in, 'prepay_out': _prepay_out,
            # Principal movements - REPAYMENTS (only after grace)
            'sp': min(_sr_p, _so) if _m >= 24 and _so > 1 else 0,
            'mp': min(_mz_p_per, _mo) if _m >= 30 and _mo > 1 else 0,
            'isp': _ic['isp'], 'imp': _ic['imp'],  # From bottom-up
            'ic_dsra_mz_draw': _ic['ic_dsra_mz_draw'],  # DSRA Mz pass-through
            'dsra': _draw_dsra,  # DSRA funding at M24
        })

    # Annual aggregation - all surplus to DSRA (no dividends)
    # DSRA_RATE loaded from config (global constant)
    annual_model = []
    _dsra_bal = 0.0  # DSRA balance
    _cdsra = 0.0
    _sclca_cum_ni = 0.0  # Cumulative net income for RE verification
    for _yi in range(10):
        h1, h2 = _sem[_yi * 2], _sem[_yi * 2 + 1]
        a = {'year': _yi + 1}
        # ACCRUED interest income from IC loans (for P&L)
        a['ii_sr'] = h1['isi'] + h2['isi']
        a['ii_mz'] = h1['imi'] + h2['imi']
        a['ii_ic'] = a['ii_sr'] + a['ii_mz']
        # Interest income from DSRA
        a['ii_dsra'] = _dsra_bal * DSRA_RATE if _dsra_bal > 0 else 0
        # Total ACCRUED interest income (for P&L)
        a['ii'] = a['ii_ic'] + a['ii_dsra']
        # ACCRUED interest expense on facilities (for P&L)
        a['ie_sr'] = h1['si'] + h2['si']
        a['ie_mz'] = h1['mi'] + h2['mi']
        a['ie'] = a['ie_sr'] + a['ie_mz']
        # Net income (accrual basis - for P&L)
        a['ni'] = a['ii'] - a['ie']
        # CASH interest (only after grace period)
        a['cf_ii'] = h1['isi_cash'] + h2['isi_cash'] + h1['imi_cash'] + h2['imi_cash'] + a['ii_dsra']
        a['cf_ie'] = h1['si_cash'] + h2['si_cash'] + h1['mi_cash'] + h2['mi_cash']
        a['cf_ie_sr_cash'] = h1['si_cash'] + h2['si_cash']   # Senior facility cash interest
        a['cf_ie_mz_cash'] = h1['mi_cash'] + h2['mi_cash']   # Mezz facility cash interest
        # Cash flow - DRAWDOWNS (Y1 only - pass-through, net = 0)
        a['cf_draw_in'] = h1['draw_in'] + h2['draw_in']    # Received from facilities
        a['cf_draw_out'] = h1['draw_out'] + h2['draw_out']  # Deployed to IC loans
        # Cash flow - PREPAYMENTS (Y2 only - pass-through, net = 0)
        a['cf_prepay_in'] = h1['prepay_in'] + h2['prepay_in']    # Received from IC loan
        a['cf_prepay_out'] = h1['prepay_out'] + h2['prepay_out']  # Paid to facility
        # Cash flow - REPAYMENTS (Y3+ only)
        # Fix 3: Subtract DSRA Mz pass-through from IC principal received.
        # At M24, NWL Sr repayment (funded by DSRA) is matched by NWL Mz drawdown (funded by CC).
        # The Mz drawdown is a pass-through (CC→SCLCA→NWL Mz) that inflates both sides.
        # Net IC principal should exclude this pass-through to avoid double-counting.
        _dsra_mz_draw = h1.get('ic_dsra_mz_draw', 0) + h2.get('ic_dsra_mz_draw', 0)
        a['cf_repay_in'] = h1['isp'] + h2['isp'] + h1['imp'] + h2['imp'] - _dsra_mz_draw
        a['cf_repay_out'] = h1['sp'] + h2['sp'] + h1['mp'] + h2['mp']     # Paid to facilities
        a['cf_repay_out_sr'] = h1['sp'] + h2['sp']   # Senior facility principal
        a['cf_repay_out_mz'] = h1['mp'] + h2['mp']   # Mezz facility principal
        # Legacy fields for compatibility
        a['cf_pi'] = a['cf_repay_in']
        a['cf_po'] = a['cf_repay_out']
        a['cf_np'] = a['cf_pi'] - a['cf_po']
        # Net Cash Flow = Cash Interest Margin + Net Principal (pass-through ≈ 0)
        # This is the PROFIT that goes into DSRA
        a['cf_net'] = (a['cf_ii'] - a['ii_dsra']) - a['cf_ie'] + a['cf_np']  # Exclude DSRA interest (added separately)
        # DSRA: Opening + Deposit (Net Cash Flow) + Interest (9%) = Closing
        _dsra_interest = _dsra_bal * DSRA_RATE  # Interest on opening balance
        _dsra_bal += a['cf_net'] + _dsra_interest  # Add deposit + interest
        a['dsra_bal'] = _dsra_bal
        a['dsra_interest'] = _dsra_interest  # For display
        # DSRA funding from CC - pass-through: drawn at M24, immediately used to buy FEC
        dsra_funded_this_year = h1['dsra'] + h2['dsra']
        _cdsra += dsra_funded_this_year
        a['dsra_funded'] = dsra_funded_this_year  # Track for display (pass-through)
        a['dsra'] = _cdsra  # Cumulative DSRA (liability to CC)
        # Balance sheet - Assets
        a['bs_isr'] = h2['isc']  # IC Senior Loan receivable
        a['bs_imz'] = h2['imc']  # IC Mezz Loan receivable
        a['bs_ic'] = a['bs_isr'] + a['bs_imz']
        a['bs_dsra'] = _dsra_bal  # DSRA Fixed Deposit (operational surplus at 9%)
        # FEC and DSRA liability are paired pass-throughs that always net to zero:
        # CC funds DSRA → SCLCA buys FEC → FEC covers first 2 DS payments
        # Both wind down together, so excluded from BS (net impact = 0)
        # Equity in subsidiaries (from config: ownership% × R1m base, converted at FX)
        a['bs_eq_nwl'] = EQUITY_NWL
        a['bs_eq_lanred'] = EQUITY_LANRED
        a['bs_eq_twx'] = EQUITY_TWX
        a['bs_eq_subs'] = EQUITY_TOTAL
        # Financial Assets = IC loans + Equity in subs; Cash = DSRA FD
        a['bs_financial'] = a['bs_ic'] + a['bs_eq_subs']
        a['bs_cash'] = a['bs_dsra']
        a['bs_a'] = a['bs_financial'] + a['bs_cash']
        # Balance sheet - Liabilities (Senior + Mezz only; DSRA/FEC netted out)
        a['bs_sr'] = h2['sc']  # Senior Facility
        a['bs_mz'] = h2['mc']  # Mezz Facility
        a['bs_dsra_liab'] = 0  # Netted with FEC asset (pass-through)
        # Shareholder equity injection for subsidiary stakes (from config)
        a['bs_sh_equity'] = EQUITY_TOTAL
        a['bs_l'] = a['bs_sr'] + a['bs_mz']
        # Equity = Shareholder equity + Retained earnings
        a['bs_retained'] = a['bs_a'] - a['bs_l'] - a['bs_sh_equity']
        a['bs_e'] = a['bs_sh_equity'] + a['bs_retained']
        # Independent RE verification from P&L (cumulative NI)
        _sclca_cum_ni += a['ni']
        a['bs_retained_check'] = _sclca_cum_ni
        a['bs_gap'] = a['bs_retained'] - _sclca_cum_ni
        annual_model.append(a)

    # --- WATERFALL OVERLAY ---
    # Compute entity operating models for waterfall
    _nwl_ops = _build_nwl_operating_annual_model()
    _lanred_ops = _build_lanred_operating_annual_model()
    _twx_ops = _build_twx_operating_annual_model()

    # NWL swap schedule (must be computed BEFORE entity waterfall inputs)
    nwl_swap_amount = 0
    _nwl_swap_eur_m24 = 0.0
    _nwl_swap_eur_m30 = 0.0
    _nwl_last_sr_month = 102
    if nwl_swap_enabled:
        for r in _entity_ic['nwl']['sr']:
            if r['Month'] == 24:
                _nwl_swap_eur_m24 = r['Interest'] + abs(r.get('Repayment', 0) or r.get('Principle', 0))
            elif r['Month'] == 30:
                _nwl_swap_eur_m30 = r['Interest'] + abs(r.get('Repayment', 0) or r.get('Principle', 0))
        nwl_swap_amount = _nwl_swap_eur_m24 + _nwl_swap_eur_m30
        _nwl_last_sr_month = max(
            (r['Month'] for r in _entity_ic['nwl']['sr']
             if r['Month'] >= 24 and (abs(r.get('Principle', 0)) > 0 or abs(r.get('Repayment', 0)) > 0)),
            default=102
        )
    _swap_sched = _build_nwl_swap_schedule(nwl_swap_amount, FX_RATE,
                                            last_sr_month=_nwl_last_sr_month if nwl_swap_enabled else 102
                                            ) if nwl_swap_enabled else None

    # Entity waterfall inputs — dependency-ordered orchestration:
    # 1. LanRED first → extract deficit vector
    _lanred_wf = _compute_entity_waterfall_inputs(
        'lanred', _lanred_ops,
        _entity_ic['lanred']['sr'], _entity_ic['lanred']['mz'])
    _lanred_deficit_vector = [row['deficit'] for row in _lanred_wf]

    # 2. TWX (independent — no swap, no OD)
    _twx_wf = _compute_entity_waterfall_inputs(
        'timberworx', _twx_ops,
        _entity_ic['timberworx']['sr'], _entity_ic['timberworx']['mz'])

    # 3. NWL last → receives LanRED deficit vector + swap schedule
    _nwl_wf = _compute_entity_waterfall_inputs(
        'nwl', _nwl_ops,
        _entity_ic['nwl']['sr'], _entity_ic['nwl']['mz'],
        lanred_deficit_vector=_lanred_deficit_vector,
        nwl_swap_schedule=_swap_sched)

    # 4. Second pass on LanRED: inject OD received amounts and recompute OD repayment
    for _yi_od in range(10):
        _od_received = _nwl_wf[_yi_od].get('od_lent', 0)
        _lanred_wf[_yi_od]['od_received'] = _od_received

    # Build waterfall
    _waterfall = _build_waterfall_model(
        annual_model, _nwl_wf, _lanred_wf, _twx_wf,
        _ic_sem, _entity_ic,
        nwl_swap_enabled=nwl_swap_enabled,
        lanred_swap_enabled=lanred_swap_enabled,
        swap_schedule=_swap_sched,
    )

    # --- WATERFALL -> ANNUAL_MODEL OVERLAY (v3.1) ---
    for _ovi in range(len(annual_model)):
        _oa = annual_model[_ovi]
        _ow = _waterfall[_ovi]
        _oa['wf_pool'] = _ow['pool_total']
        # v3.1 cascade keys (6-step, character-preserving)
        _oa['wf_sr_pi'] = _ow['wf_sr_pi']
        _oa['wf_mz_pi'] = _ow['wf_mz_pi']  # includes entity Mezz accel
        _oa['wf_dsra_topup'] = _ow.get('wf_dsra_topup', 0)
        _oa['wf_dsra_release'] = _ow.get('wf_dsra_release', 0)
        _oa['wf_dsra_bal'] = _ow.get('wf_dsra_bal', 0)
        _oa['wf_cc_slug_paid'] = _ow.get('wf_cc_slug_paid', 0)
        _oa['wf_mz_accel'] = _ow.get('wf_mz_accel', 0)  # 0 stub (moved to entity)
        _oa['wf_sr_accel'] = _ow.get('wf_sr_accel', 0)
        _oa['wf_fd_deposit'] = _ow.get('wf_fd_deposit', 0)
        _oa['wf_fd_bal'] = _ow.get('wf_fd_bal', 0)
        # CC tracking
        _oa['wf_cc_opening'] = _ow['cc_opening']
        _oa['wf_cc_closing'] = _ow['cc_closing']
        _oa['wf_cc_slug_cum'] = _ow.get('cc_slug_cumulative', 0)
        _oa['wf_cc_slug_settled'] = _ow.get('cc_slug_settled', False)
        _oa['wf_ic_overdraft_bal'] = _ow.get('ic_overdraft_bal', 0)
        # Entity-level cascade fields
        for _ek_ov in ['nwl', 'lanred', 'timberworx']:
            _oa[f'wf_{_ek_ov}_ops_reserve_bal'] = _ow.get(f'{_ek_ov}_ops_reserve_bal', 0)
            _oa[f'wf_{_ek_ov}_opco_dsra_bal'] = _ow.get(f'{_ek_ov}_opco_dsra_bal', 0)
            _oa[f'wf_{_ek_ov}_entity_fd_bal'] = _ow.get(f'{_ek_ov}_entity_fd_bal', 0)
        _oa['wf_od_lent'] = _ow.get('nwl_od_lent', 0)
        _oa['wf_od_repaid'] = _ow.get('lanred_od_repaid', 0)
        _oa['wf_od_bal'] = _ow.get('ic_overdraft_bal', 0)
        # Backward compatibility aliases
        _oa['wf_iic_pi'] = _ow['wf_iic_pi']           # = wf_sr_pi
        _oa['wf_cc_interest'] = _ow['wf_cc_interest']  # = wf_mz_pi (includes entity accel)
        _oa['wf_cc_principal'] = _ow['wf_cc_principal'] # = 0 (moved to entity level)
        _oa['wf_iic_prepay'] = _ow['wf_iic_prepay']    # = wf_sr_accel
        # Zero stubs for removed features
        _oa['wf_ic_mz_rebalance'] = 0
        _oa['wf_interest_saved'] = 0

    # Swap comparison (always compute for both scenarios)
    _mz_cfg_wf = structure['sources']['mezzanine']
    _wf_cfg_comp = load_config("waterfall")
    _cc_irr_cfg_comp = _wf_cfg_comp.get("cc_irr", {})
    _wacc = 0.85 * structure['sources']['senior_debt']['interest']['rate'] + 0.15 * _mz_cfg_wf['interest']['total_rate']
    _swap_comparison = _compute_dsra_vs_swap_comparison(
        dsra_amount_eur=dsra_principle_fixed,
        cc_initial=_mz_cfg_wf['amount_eur'] + financing['loan_detail']['mezzanine']['rolled_up_interest_zar'] * (_mz_cfg_wf['amount_eur'] / _mz_cfg_wf['amount_zar']),
        cc_rate=_mz_cfg_wf['interest']['total_rate'],
        cc_gap_rate=_cc_irr_cfg_comp.get("gap", 0.0525),
        swap_sched=_swap_sched if _swap_sched else _build_nwl_swap_schedule(3000000, FX_RATE),
        wacc=_wacc,
    )

    # --- OVERVIEW TAB ---
    if "Overview" in _tab_map:
        with _tab_map["Overview"]:
            # 1. Logo + Header + Caption
            _sclca_ov_logo = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")
            if _sclca_ov_logo.exists():
                _ovl, _ovt = st.columns([1, 8])
                with _ovl:
                    st.image(str(_sclca_ov_logo), width=100)
                with _ovt:
                    st.header("Catalytic Assets")
                    st.caption("Orchestrator of Demand | Financial Holding Company")
            else:
                st.header("Catalytic Assets")

            _ov_sclca = load_content_md("OVERVIEW_CONTENT.md").get("sclca", "")

            # 1a. Overview — aerial image floated left, text flows around it
            _aerial_img = Path(__file__).parent / "assets" / "images" / "smart-city-aerial.jpg"
            _ov_html_parts = []
            if _aerial_img.exists():
                import base64 as _b64_ov
                _img_bytes = _aerial_img.read_bytes()
                _img_b64 = _b64_ov.b64encode(_img_bytes).decode()
                _img_ext = _aerial_img.suffix.lstrip(".")
                if _img_ext == "jpg":
                    _img_ext = "jpeg"
                _ov_html_parts.append(
                    f'<img src="data:image/{_img_ext};base64,{_img_b64}" '
                    f'style="float:left;width:320px;margin:0 24px 12px 0;border-radius:8px;" />'
                )
            # Build narrative HTML from MD sections (convert **bold** → <b>)
            import re as _re_ov
            def _md_to_html(text):
                text = _re_ov.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                text = _re_ov.sub(r'__(.+?)__', r'<b>\1</b>', text)
                text = _re_ov.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
                return f"<p>{text}</p>"
            if _ov_sclca:
                for _sect_name in ["Lanseria Smart City", "DevCo", "SCLCA", "InfraCo", "LLC"]:
                    for _sect in _ov_sclca.split("\n### "):
                        if _sect.startswith(_sect_name):
                            _raw_md = _sect.partition("\n")[2].strip()
                            _ov_html_parts.append(_md_to_html(_raw_md))
                            break
            # FEC/Swap toggle-dependent sentence
            _hedge_mode = st.session_state.get("sclca_nwl_hedge", "CC DSRA \u2192 FEC")
            if _hedge_mode == "Cross-Currency Swap":
                _ov_html_parts.append("<p>The NWL senior debt service is hedged via a <b>cross-currency swap</b> arranged with Creation Capital.</p>")
            else:
                _ov_html_parts.append("<p>The NWL senior debt service is hedged via the <b>FEC funded by Creation Capital</b>.</p>")
            _ov_html_parts.append('<div style="clear:both;"></div>')
            st.markdown("\n".join(_ov_html_parts), unsafe_allow_html=True)

            st.divider()

            # 2. Corporate Structure
            st.subheader("Lanseria Smart City — Corporate Structure")
            render_svg("corporate_structure.svg", "SVG_CORPORATE_CONTENT.md")

            st.divider()

            # 3. Key Metrics
            _ov_m1, _ov_m2, _ov_m3, _ov_m4 = st.columns(4)
            with _ov_m1:
                st.metric("Total Project Cost", f"€{project['totals']['total_project_cost']:,.0f}")
            with _ov_m2:
                st.metric("Operating Companies", "3")
            with _ov_m3:
                st.metric("Financial Close", project['timeline']['financial_close'])
            with _ov_m4:
                st.metric("Loan Tenure", f"{project['timeline']['repayment_periods']} semi-annual")

            st.divider()

            # 4. Ownership Structure
            _subs = structure['subsidiaries']
            _loans_s = structure['uses']['loans_to_subsidiaries']

            st.subheader("Ownership Structure")
            _own_svg = Path(__file__).parent / "assets" / "ownership-structure.svg"
            if _own_svg.exists():
                st.image(str(_own_svg), use_container_width=True)

            st.divider()

            # 5. UBO Structure (after Ownership)
            st.subheader("Ultimate Beneficial Owners (UBO)")
            _ubo_svg = Path(__file__).parent / "assets" / "ubo-structure.svg"
            if _ubo_svg.exists():
                import streamlit.components.v1 as _stc_ubo
                _ubo_raw = _ubo_svg.read_text(encoding='utf-8')
                _ubo_raw = _ubo_raw.replace('<svg ', '<svg width="100%" ', 1)
                _stc_ubo.html(f'<div style="width:100%;overflow:visible;">{_ubo_raw}</div>',
                              height=670, scrolling=False)

            st.divider()

            # 6. Funding Structure
            st.subheader("Funding Structure")
            _fund_svg = Path(__file__).parent / "assets" / "funding-structure.svg"
            if _fund_svg.exists():
                st.image(str(_fund_svg), use_container_width=True)

            st.divider()

            # 8. Holding Company details
            _holding = structure['holding']
            st.subheader("Catalytic Assets — Holding Company")
            st.markdown(f"""
| | |
|---|---|
| **Name** | {_holding['name']} |
| **Code** | {_holding['code']} |
| **Type** | {_holding['type'].replace('_', ' ').title()} |
| **Registration** | {_holding.get('registration', '—')} |
| **Role** | {_holding['description']} |
        """)

            st.divider()

            # 9. Subsidiaries
            st.subheader("Subsidiaries")

            _sub_cols = st.columns(3)
            for _i, (_key, _sub) in enumerate(_subs.items()):
                _loan = _loans_s[_key]
                _logo = ENTITY_LOGOS.get(_key)
                with _sub_cols[_i]:
                    if _logo and (LOGO_DIR / _logo).exists():
                        st.image(str(LOGO_DIR / _logo), width=80)
                    st.markdown(f"**{_sub['name']}** ({_sub['code']})")
                    _reg = _sub.get('registration', '')
                    _legal = _sub.get('legal_name', '')
                    _cap = _sub.get('type', 'operating_company').replace('_', ' ').title()
                    if _reg:
                        _cap += f" | Reg. {_reg}"
                    st.caption(_cap)
                    st.markdown(f"""
| | |
|---|---|
| **Legal Name** | {_legal} |
| **Assets** | {', '.join(a.upper() for a in _sub.get('assets', []))} |
| **Senior IC** | €{_loan['senior_portion']:,.0f} |
| **Mezz IC** | €{_loan['mezz_portion']:,.0f} |
| **Total** | €{_loan['total_loan']:,.0f} |
| **Pro-rata** | {_loan['pro_rata_pct']*100:.1f}% |
                """)

            st.divider()

            # 10. Capital Providers
            st.subheader("Capital Providers")

            _sr_s = structure['sources']['senior_debt']
            _mz_s = structure['sources']['mezzanine']
            _dsra_s = structure['sources']['dsra']

            _prov_cols = st.columns(3)
            with _prov_cols[0]:
                _ii_sp = LOGO_DIR / ENTITY_LOGOS.get("invest_international", "")
                if _ii_sp.exists():
                    st.image(str(_ii_sp), width=80)
                st.markdown("**Invest International**")
                st.caption("Senior Debt")
                st.markdown(f"€{_sr_s['amount']:,.0f} @ {_sr_s['interest']['rate']*100:.2f}%")
            with _prov_cols[1]:
                _cc_sp = LOGO_DIR / ENTITY_LOGOS.get("creation_capital", "")
                if _cc_sp.exists():
                    st.image(str(_cc_sp), width=80)
                st.markdown("**Creation Capital**")
                st.caption("Mezzanine (Quasi Equity)")
                st.markdown(f"€{_mz_s['amount_eur']:,.0f} @ {_mz_s['interest']['total_rate']*100:.2f}%")
            with _prov_cols[2]:
                if _cc_sp.exists():
                    st.image(str(_cc_sp), width=80)
                st.markdown("**Creation Capital**")
                st.caption("DSRA")
                st.markdown(f"€{computed_dsra_eur:,.0f} ({_dsra_s['sizing']['repayments_covered']} DS payments)")

    # --- ABOUT TAB ---
    if "About" in _tab_map:
        with _tab_map["About"]:
            st.header("Smart City Lanseria Catalytic Assets — About")

            # Load ABOUT content
            about_sections = load_about_content()
            sclca_about = about_sections.get('sclca', "")
            smart_city_about = about_sections.get('smart_city', "")

            # Combine SCLCA and Smart City content
            combined_about = ""
            if sclca_about:
                combined_about += sclca_about
            if smart_city_about:
                if combined_about:
                    combined_about += "\n\n---\n\n"
                combined_about += smart_city_about

            if combined_about:
                st.markdown(combined_about)
            else:
                st.info("About content for SCLCA is being prepared. Please check back soon.")

                # Show placeholder info
                st.markdown("""
                This tab will contain comprehensive information about **Smart City Lanseria Catalytic Assets (SCLCA)**, including:
                - The Frontier Funding Framework
                - Corporate structure and ownership
                - Integrated infrastructure platform
                - Demand orchestration strategy
                - Impact on Smart City Lanseria development
                - National replication potential

                Detailed content is available in the ABOUT_TABS_CONTENT.md file.
                """)

    # --- SOURCES & USES TAB ---
    if "Sources & Uses" in _tab_map:
        with _tab_map["Sources & Uses"]:
            st.header("Summary")
            _equity_total = EQUITY_TOTAL  # From config: NWL + LanRED + TWX
            _debt_total = structure['sources']['total']
            _grand_total = _debt_total + _equity_total

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Capital", f"€{_grand_total:,.0f}")
            with col2:
                senior_amount = structure['sources']['senior_debt']['amount']
                senior_pct = (senior_amount / _grand_total) if _grand_total else 0
                st.metric("Senior Debt", f"€{senior_amount:,.0f}", f"{senior_pct*100:.1f}%")
            with col3:
                mezz_eur = structure['sources']['mezzanine']['amount_eur']
                mezz_pct = (mezz_eur / _grand_total) if _grand_total else 0
                st.metric("Mezzanine", f"€{mezz_eur:,.0f}", f"{mezz_pct*100:.1f}%")
            with col4:
                eq_pct = (_equity_total / _grand_total) if _grand_total else 0
                st.metric("Shareholder Equity", f"€{_equity_total:,.0f}", f"{eq_pct*100:.1f}%")

            st.divider()

            col_sources, col_uses = st.columns(2)

            # SOURCES
            with col_sources:
                st.header("📥 SOURCES")
                st.caption("Capital received at SCLCA level")

                _ii_logo = LOGO_DIR / ENTITY_LOGOS["invest_international"]
                if _ii_logo.exists():
                    _ii_l, _ii_t = st.columns([1, 6])
                    with _ii_l:
                        st.image(str(_ii_logo), width=80)
                    with _ii_t:
                        st.markdown("### Senior Debt (Invest International)")
                else:
                    st.markdown("### Senior Debt (Invest International)")
                senior = structure['sources']['senior_debt']
                senior_tenure = senior['loan_holiday_months'] + senior['repayment_months']
                st.markdown(f"""
            | | |
            |---|---|
            | **Principal** | €{senior['amount']:,.0f} |
            | **Interest** | Euribor ({senior['interest']['euribor']*100:.2f}%) + Margin ({senior['interest']['margin']*100:.2f}%) = **{senior['interest']['rate']*100:.2f}%** |
            | **Tenure** | {senior['loan_holiday_months']} + {senior['repayment_months']} = **{senior_tenure} months** |
            | **Moratorium** | {senior['loan_holiday_months']} months |
            | **Repayments** | {senior['repayments']} {senior['frequency']} |
            | **IDC** | Roll-up, add to principal (+€{senior['idc']['amount']:,.0f}) |
            """)

                _cc_logo = LOGO_DIR / ENTITY_LOGOS["creation_capital"]
                if _cc_logo.exists():
                    _cc_l, _cc_t = st.columns([1, 6])
                    with _cc_l:
                        st.image(str(_cc_logo), width=80)
                    with _cc_t:
                        st.markdown("### Mezzanine (Creation Capital)")
                else:
                    st.markdown("### Mezzanine (Creation Capital)")
                mezz = structure['sources']['mezzanine']
                mezz_tenure = mezz['roll_up_months'] + mezz.get('repayment_months', 60)
                mezz_idc_zar = mezz.get('idc_amount_zar', 13809805)
                mezz_idc_eur = mezz['amount_eur'] * (mezz_idc_zar / mezz['amount_zar']) if mezz.get('amount_zar') else 0
                dsra = structure['sources']['dsra']
                st.markdown(f"""
            | | |
            |---|---|
            | **Principal** | €{mezz['amount_eur']:,.0f} |
            | **Interest** | Prime ({mezz['interest']['prime_rate']*100:.2f}%) + Margin ({mezz['interest']['margin']*100:.0f}%) = **{mezz['interest']['total_rate']*100:.2f}%** |
            | **Tenure** | {mezz['roll_up_months']} + {mezz.get('repayment_months', 60)} = **{mezz_tenure} months** |
            | **Moratorium** | {mezz['roll_up_months']} months |
            | **Repayments** | {mezz.get('repayments', 10)} semi-annual |
            | **IDC** | Roll-up, add to principal (+€{mezz_idc_eur:,.0f}) |
            """)

                st.caption("DSRA (Debt Service Reserve Account)")
                _mr3 = st.columns(3)
                with _mr3[0]:
                    st.caption("DSRA Size")
                    st.markdown(f"**€{computed_dsra_eur:,.0f}**")
                with _mr3[1]:
                    st.caption("Basis")
                    st.markdown(f"**{_dsra_n} debt service payments (P+I)**")
                with _mr3[2]:
                    st.caption("Funded at")
                    st.markdown(f"**Month {dsra['funded_at_month']}**")

                st.divider()
                _sclca_logo = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")
                if _sclca_logo.exists():
                    _eql, _eqt = st.columns([1, 12])
                    with _eql:
                        st.image(str(_sclca_logo), width=80)
                    with _eqt:
                        st.markdown("### Shareholder Equity")
                else:
                    st.markdown("### Shareholder Equity")
                st.caption("Equity investment to acquire subsidiary stakes (R1m = €50k at FX 20)")
                _eq_r1 = st.columns(3)
                with _eq_r1[0]:
                    st.caption("Total Equity")
                    st.markdown("**€99,000**")
                with _eq_r1[1]:
                    st.caption("Purpose")
                    st.markdown("**Buy equity in OpCos**")
                with _eq_r1[2]:
                    st.caption("Timing")
                    st.markdown("**Financial Close**")

                _eq_r2 = st.columns(3)
                with _eq_r2[0]:
                    st.caption("NWL (93%)")
                    st.markdown("**€46,500**")
                    _cp_logo = LOGO_DIR / ENTITY_LOGOS.get("crosspoint", "")
                    if _cp_logo.exists():
                        st.image(str(_cp_logo), width=60)
                    st.caption("Co-shareholder: Crosspoint (7%)")
                with _eq_r2[1]:
                    st.caption("LanRED (100%)")
                    st.markdown("**€50,000**")
                    st.caption("Wholly owned")
                with _eq_r2[2]:
                    st.caption("TWX (5%)")
                    st.markdown("**€2,500**")
                    _vs_logo = LOGO_DIR / ENTITY_LOGOS.get("vansquare", "")
                    if _vs_logo.exists():
                        st.image(str(_vs_logo), width=60)
                    st.caption("Co-shareholder: VanSquare (95%)")

            # USES
            with col_uses:
                st.header("📤 USES")
                st.caption("Intercompany loans to subsidiaries (2 loans each: Senior 85% + Mezz 15%)")

                loans = structure['uses']['loans_to_subsidiaries']
                senior_ic_rate = senior['interest']['rate'] + INTERCOMPANY_MARGIN
                mezz_ic_rate = mezz['interest']['total_rate'] + INTERCOMPANY_MARGIN

                for entity_key, ent in loans.items():
                    logo_file = ENTITY_LOGOS.get(entity_key)
                    if logo_file and (LOGO_DIR / logo_file).exists():
                        col_logo, col_name = st.columns([1, 8])
                        with col_logo:
                            st.image(str(LOGO_DIR / logo_file), width=80)
                        with col_name:
                            st.markdown(f"### {ent['name']}")
                    else:
                        st.markdown(f"### {ent['name']}")
                    st.markdown(f"**Total: €{ent['total_loan']:,.0f}**")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"""
                    **Senior Loan (85%)**
                    - Principal: €{ent['senior_portion']:,.0f}
                    - Interest: **{senior_ic_rate*100:.2f}%**
                    """)
                    with col2:
                        st.markdown(f"""
                    **Mezz Loan (15%)**
                    - Principal: €{ent['mezz_portion']:,.0f}
                    - Interest: **{mezz_ic_rate*100:.2f}%**
                    """)

                st.divider()
                _sclca_logo_u = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")
                if _sclca_logo_u.exists():
                    _eul, _eut = st.columns([1, 12])
                    with _eul:
                        st.image(str(_sclca_logo_u), width=80)
                    with _eut:
                        st.markdown("### Equity Investments")
                else:
                    st.markdown("### Equity Investments")
                st.caption("Shareholder equity deployed to acquire subsidiary stakes (R1m = €50k at FX 20)")
                st.markdown("**Total: €99,000**")

                _eq_use_r = st.columns(3)
                with _eq_use_r[0]:
                    st.markdown("""
                **NWL (93%)**
                - Investment: €46,500
                - Co-shareholder: Crosspoint (7%)
                """)
                with _eq_use_r[1]:
                    st.markdown("""
                **LanRED (100%)**
                - Investment: €50,000
                - Wholly owned
                """)
                with _eq_use_r[2]:
                    st.markdown("""
                **TWX (5%)**
                - Investment: €2,500
                - Co-shareholder: VanSquare (95%)
                """)

            # ── AUDIT: SCLCA Sources & Uses ──
            _sclca_su_checks = []
            _all_loans = structure['uses']['loans_to_subsidiaries']
            _sr_total = structure['sources']['senior_debt']['amount']
            _mz_total = structure['sources']['mezzanine']['amount_eur']
            _sclca_su_checks.append({
                "name": "Sum entity Senior = Facility Senior",
                "expected": _sr_total,
                "actual": sum(v['senior_portion'] for v in _all_loans.values()),
            })
            _sclca_su_checks.append({
                "name": "Sum entity Mezz = Facility Mezz",
                "expected": _mz_total,
                "actual": sum(v['mezz_portion'] for v in _all_loans.values()),
            })
            _sclca_su_checks.append({
                "name": "Sum entity Total = Facility Total",
                "expected": _sr_total + _mz_total,
                "actual": sum(v['total_loan'] for v in _all_loans.values()),
            })
            run_page_audit(_sclca_su_checks, "SCLCA — Sources & Uses")

    # --- FACILITIES TAB ---
    if "Facilities" in _tab_map:
        with _tab_map["Facilities"]:
            st.header("Facilities")

            # ===========================================
            # LIABILITY SIDE (SOURCES)
            # ===========================================
            st.subheader("Liability Side (Sources)")

            # ---------- SENIOR DEBT ----------
            with st.container(border=True):
                _ii_logo2 = LOGO_DIR / ENTITY_LOGOS["invest_international"]
                if _ii_logo2.exists():
                    _ii_l2, _ii_t2 = st.columns([1, 8])
                    with _ii_l2:
                        st.image(str(_ii_logo2), width=80)
                    with _ii_t2:
                        st.markdown("### Senior Debt (Invest International)")
                else:
                    st.markdown("### Senior Debt (Invest International)")
                senior = structure['sources']['senior_debt']
                senior_detail = financing['loan_detail']['senior']

                # Loan terms (2 rows x 3 columns)
                row1 = st.columns(3)
                with row1[0]:
                    st.caption("Principal")
                    st.markdown(f"**€{senior_detail['loan_drawdown_total']:,.0f}**")
                with row1[1]:
                    st.caption("Interest")
                    st.markdown(
                        f"**Euribor ({senior['interest']['euribor']*100:.2f}%) + "
                        f"Margin ({senior['interest']['margin']*100:.2f}%) = "
                        f"{senior['interest']['rate']*100:.2f}%**"
                    )
                with row1[2]:
                    st.caption("Tenure")
                    st.markdown(
                        f"**{senior['loan_holiday_months']} + {senior['repayment_months']} = "
                        f"{senior['loan_holiday_months'] + senior['repayment_months']} months**"
                    )

                row2 = st.columns(3)
                with row2[0]:
                    st.caption("Moratorium")
                    st.markdown(f"**{senior['loan_holiday_months']} months**")
                with row2[1]:
                    st.caption("Repayments")
                    st.markdown(f"**{senior['repayments']} semi-annual**")
                with row2[2]:
                    st.caption("IDC")
                    st.markdown(f"**Roll-up, add to principal (+€{senior_detail['rolled_up_interest_idc']:,.0f})**")

                # Build Senior Debt Schedule
                # Period -4=M0, -3=M6, -2=M12, -1=M18(COD), 1=M24(first repay), 2=M30, etc.
                schedule_rows = []
                balance = 0.0
                interest_rate = senior['interest']['rate']
                num_repayments = senior['repayments']  # 14
                grant_prepay = senior_detail['grant_proceeds_to_early_repayment']
                gepf_prepay = senior_detail['gepf_bulk_proceeds']
                prepayment_total = grant_prepay + gepf_prepay

                # Actual drawdown schedule (cash received from Invest International)
                actual_drawdowns = senior_detail['drawdown_schedule']  # [8789117, 2835775, 1818036, 0]

                # Grace periods: -4, -3, -2, -1
                # Draw Down = actual drawdown only
                # Interest = IDC on opening balance (shown for info)
                # Movement = Draw Down + Principle (balance change)
                grace_period_list = [-4, -3, -2, -1]
                idc_total = 0.0
                for idx, period in enumerate(grace_period_list):
                    month = (period + 4) * 6  # -4→0, -3→6, -2→12, -1→18
                    year = month / 12
                    opening = balance

                    # IDC = interest on opening balance
                    idc = opening * interest_rate / 2
                    idc_total += idc

    # Actual drawdown for this period
                    draw_down = actual_drawdowns[idx] if idx < len(actual_drawdowns) else 0

                    # Principle = prepayment at period -1 (COD)
                    if period == -1:
                        principle = -prepayment_total
                    else:
                        principle = 0

                    # Repayment = Principle (no interest payment during grace)
                    repayment = principle

                    # Movement = Draw Down + Interest (IDC capitalized) + Principle
                    movement = draw_down + idc + principle
                    balance = opening + movement

                    schedule_rows.append({
                    "Period": period,
                    "Month": month,
                    "Year": year,
                    "Opening": opening,
                    "Draw Down": draw_down,
                    "Interest": idc,
                    "Principle": principle,
                    "Repayment": repayment,
                    "Movement": movement,
                    "Closing": balance
                })

                # After grace period: balance before DSRA
                balance_for_repay = balance

                # Regular principal per period (if no DSRA): balance / 14
                regular_p = balance_for_repay / num_repayments

                # DSRA calculation: covers 2 full debt service payments (P + I each)
                # DSRA principal at M24 = 2×(P + I_M24)
                interest_m24 = balance_for_repay * interest_rate / 2
                dsra_principle = 2 * (regular_p + interest_m24)
                dsra_total = dsra_principle + interest_m24  # Total cash at M24

                # After DSRA, remaining balance paid over 12 periods (periods 3-14)
                balance_after_dsra = balance_for_repay - dsra_principle
                new_p = balance_after_dsra / (num_repayments - 2)  # 12 periods

                # Repayment periods: 1, 2, 3, ... (M24, M30, M36, ...)
                for i in range(1, num_repayments + 1):
                    period = i
                    month = 18 + (i * 6)  # 1→24, 2→30, 3→36, etc.
                    year = month / 12
                    opening = balance

                    # Interest on opening balance
                    interest = opening * interest_rate / 2

                    if period == 1:
                        # DSRA payment: big principal + interest
                        principle = -dsra_principle
                        repayment = principle - interest  # P + I (both negative in cash terms)
                    elif period == 2:
                        # Interest only (principal covered by DSRA)
                        principle = 0
                        repayment = -interest  # Interest only
                    else:
                        # Regular repayment: new_p per period
                        principle = -new_p
                        repayment = principle - interest  # P + I

                    # Movement = Principle (balance change)
                    movement = principle
                    balance = opening + movement

                    # Note: Periods 1-2 funded by DSRA
                    dsra_note = " *" if period in [1, 2] else ""

                    schedule_rows.append({
                        "Period": f"{period}{dsra_note}",
                        "Month": month,
                        "Year": year,
                        "Opening": opening,
                        "Draw Down": 0,
                        "Interest": interest,
                        "Principle": principle,
                        "Repayment": repayment,
                        "Movement": movement,
                        "Closing": balance
                    })

                df_senior = pd.DataFrame(schedule_rows)
                render_table(df_senior, {
                "Year": "{:.1f}",
                "Opening": "€{:,.0f}",
                "Draw Down": "€{:,.0f}",
                "Interest": "€{:,.0f}",
                "Principle": "€{:,.0f}",
                "Repayment": "€{:,.0f}",
                "Movement": "€{:,.0f}",
                "Closing": "€{:,.0f}"
                })

                # Notes section
                st.markdown("---")
                col_idc, col_dsra, col_repay = st.columns(3)

                with col_idc:
                    st.markdown("**IDC (Interest During Construction)**")
                    st.caption("Interest accrues on opening balance each period")
                    idc_data = []
                    bal = 0.0
                    idc_sum = 0.0
                    dd_sum = 0.0
                    for idx, dd in enumerate(actual_drawdowns):
                        idc_amt = bal * interest_rate / 2
                        idc_data.append({"Period": -4 + idx, "Draw Down": dd, "IDC": idc_amt})
                        dd_sum += dd
                        idc_sum += idc_amt
                        bal += dd + idc_amt
                    idc_data.append({"Period": "Total", "Draw Down": dd_sum, "IDC": idc_sum})
                    df_idc = pd.DataFrame(idc_data)
                    render_table(df_idc, {"Draw Down": "€{:,.0f}", "IDC": "€{:,.0f}"})

                with col_dsra:
                    st.markdown("**DSRA → FEC → Prepayment**")
                    st.caption("Forward Exchange Cover removes forex risk")
                    st.markdown(f"""
                    | Item | Amount |
                    |------|--------|
                    | Regular P (bal÷{num_repayments}) | €{regular_p:,.2f} |
                    | Interest M24 | €{interest_m24:,.2f} |
                    | **DSRA** 2×(P + I) | €{dsra_principle:,.2f} |
                    | M24 prepayment | €{dsra_principle:,.2f} |
                    | M30 (interest only) | €{balance_after_dsra * interest_rate / 2:,.2f} |
                    """)
                    st.caption("DSRA (ZAR) → FEC → EUR prepayment at M24")

                with col_repay:
                    st.markdown("**Repayment Structure**")
                    st.caption("After DSRA, 12 periods remain (P3-P14)")
                    st.markdown(f"""
                    | Item | Amount |
                |------|--------|
                    | **Prepayment (P-1)** | €{prepayment_total:,.2f} |
                    | Balance for repay | €{balance_for_repay:,.2f} |
                    | Balance after DSRA | €{balance_after_dsra:,.2f} |
                    | **New P** (bal÷12) | €{new_p:,.2f} |
                    """)
                    st.caption("Repayment = Principle + Interest")

                    st.markdown("---")
                    st.markdown("**DSRA Mechanism (Swap):**")
                    st.markdown(f"""
        1. **DSRA Funded:** Creation Capital provides ZAR reserve at M24 / Period 1 (€{computed_dsra_eur:,.0f} equivalent)
        2. **FEC Purchased:** DSRA buys Forward Exchange Cover to lock EUR rate, eliminating forex risk
        3. **M24 Prepayment:** FEC converts to EUR, used to prepay 2×(P + I) on Senior Debt in one go
        4. **M30:** Interest-only payment (principal already covered by DSRA)
        5. **Replenishment:** Operating income from IC loans to NWL, LanRED & TWX replenishes DSRA in South Africa
        6. **Net Effect:** DSRA acts as a **ZAR↔EUR swap** - ZAR liability to Creation Capital, EUR prepayment to Invest International
        """)

            st.divider()

            # ---------- MEZZANINE ----------
            with st.container(border=True):
                _cc_logo2 = LOGO_DIR / ENTITY_LOGOS["creation_capital"]
                if _cc_logo2.exists():
                    _cc_l2, _cc_t2 = st.columns([1, 8])
                    with _cc_l2:
                        st.image(str(_cc_logo2), width=80)
                    with _cc_t2:
                        st.markdown("### Mezzanine (Creation Capital)")
                else:
                    st.markdown("### Mezzanine (Creation Capital)")
                mezz = structure['sources']['mezzanine']
                mezz_detail = financing['loan_detail']['mezzanine']
                fx_rate = mezz['amount_eur'] / mezz['amount_zar'] if mezz['amount_zar'] else 0
                mezz_amount_eur = mezz['amount_eur']
                mezz_rollup_eur = mezz_detail['rolled_up_interest_zar'] * fx_rate
                mezz_net_opening_eur = mezz_detail['net_opening_balance_zar'] * fx_rate
                dsra = structure['sources']['dsra']
                balance_after_rollup = mezz_amount_eur + mezz_rollup_eur
                mezz_repayment_months = mezz.get('repayment_months', 60)
                mezz_tenure = mezz['roll_up_months'] + mezz_repayment_months

                st.markdown(f"""
        | | |
        |---|---|
        | **Principal** | €{mezz_amount_eur:,.0f} |
        | **Interest** | Prime ({mezz['interest']['prime_rate']*100:.2f}%) + Margin ({mezz['interest']['margin']*100:.0f}%) = **{mezz['interest']['total_rate']*100:.2f}%** |
        | **Tenure** | {mezz['roll_up_months']} + {mezz_repayment_months} = **{mezz_tenure} months** |
        | **Moratorium** | {mezz['roll_up_months']} months |
        | **Repayments** | {mezz.get('repayments', 10)} semi-annual |
        | **IDC** | Roll-up, add to principal (+€{mezz_rollup_eur:,.0f}) |
        """)

                st.caption("DSRA (Debt Service Reserve Account)")
                _mfr3 = st.columns(3)
                with _mfr3[0]:
                    st.caption("DSRA Size")
                    st.markdown(f"**€{computed_dsra_eur:,.0f}**")
                with _mfr3[1]:
                    st.caption("Basis")
                    st.markdown(f"**{_dsra_n} debt service payments (P+I)**")
                with _mfr3[2]:
                    st.caption("Funded at")
                    st.markdown(f"**Month {dsra['funded_at_month']}**")

                # Build Mezzanine Schedule (same format as Senior Debt)
                mezz_rows = []
                balance_eur = 0.0
                mezz_rate = mezz['interest']['total_rate']
                mezz_repayments = 10

                # Drawdown schedule: full amount at period -4 only
                mezz_drawdown_schedule = [mezz_amount_eur, 0, 0, 0]
                mezz_drawdown_periods = [-4, -3, -2, -1]

                # Grace periods (-4 to -1): Draw Down + IDC capitalized
                for idx, period in enumerate(mezz_drawdown_periods):
                    month = (period + 4) * 6  # -4→0, -3→6, -2→12, -1→18
                    year = month / 12
                    opening = balance_eur

                    # IDC = interest on opening balance (capitalized)
                    idc = opening * mezz_rate / 2

                    # Drawdown for this period
                    draw_down = mezz_drawdown_schedule[idx] if idx < len(mezz_drawdown_schedule) else 0

                    # Movement = Draw Down + Interest (IDC capitalized)
                    movement = draw_down + idc
                    balance_eur = opening + movement

                    mezz_rows.append({
                        "Period": period,
                        "Month": month,
                        "Year": year,
                        "Opening": opening,
                        "Draw Down": draw_down,
                        "Interest": idc,
                        "Principle": 0,
                        "Repayment": 0,
                        "Movement": movement,
                        "Closing": balance_eur
                    })

                # After grace: balance before DSRA
                balance_before_dsra = balance_eur

                # DSRA drawn at Period 1 (M24), then repayments calculated on total
                balance_with_dsra = balance_before_dsra + computed_dsra_eur
                mezz_p_per_period = balance_with_dsra / mezz_repayments

                # Repayment periods (1..10)
                for i in range(1, mezz_repayments + 1):
                    period = i
                    month = 18 + (i * 6)  # 1→24, 2→30, etc.
                    year = month / 12
                    opening = balance_eur

                    # DSRA drawdown at Period 1
                    if period == 1:
                        draw_down = computed_dsra_eur
                    else:
                        draw_down = 0

                    # Interest on opening balance
                    interest = opening * mezz_rate / 2

                    # Principle = constant P (based on total with DSRA)
                    principle = -mezz_p_per_period

                    # Repayment = Principle + Interest
                    repayment = principle - interest

                    # Movement = Draw Down + Principle (DSRA increases, then P reduces)
                    movement = draw_down + principle
                    balance_eur = opening + movement

                    mezz_rows.append({
                        "Period": period,
                        "Month": month,
                        "Year": year,
                        "Opening": opening,
                        "Draw Down": draw_down,
                        "Interest": interest,
                        "Principle": principle,
                        "Repayment": repayment,
                        "Movement": movement,
                        "Closing": balance_eur
                    })

                df_mezz = pd.DataFrame(mezz_rows)
                render_table(df_mezz, {
                    "Year": "{:.1f}",
                    "Opening": "€{:,.0f}",
                    "Draw Down": "€{:,.0f}",
                    "Interest": "€{:,.0f}",
                    "Principle": "€{:,.0f}",
                    "Repayment": "€{:,.0f}",
                    "Movement": "€{:,.0f}",
                    "Closing": "€{:,.0f}"
                })

                # Mezz helper tables and notes
                st.markdown("---")
                col_mezz_idc, col_mezz_dsra, col_mezz_repay = st.columns(3)

                # Calculate IDC for helper table
                mezz_idc_data = []
                mezz_bal = 0.0
                mezz_idc_total = 0.0
                mezz_dd_total = 0.0
                for idx, dd in enumerate(mezz_drawdown_schedule):
                    idc_amt = mezz_bal * mezz_rate / 2
                    mezz_idc_total += idc_amt
                    mezz_dd_total += dd
                    mezz_idc_data.append({"Period": -4 + idx, "Draw Down": dd, "IDC": idc_amt})
                    mezz_bal += dd + idc_amt
                mezz_idc_data.append({"Period": "Total", "Draw Down": mezz_dd_total, "IDC": mezz_idc_total})

                with col_mezz_idc:
                    st.markdown("**IDC (Mezz)**")
                    st.caption(f"Interest capitalized at {mezz_rate*100:.2f}%")
                    df_mezz_idc = pd.DataFrame(mezz_idc_data)
                    render_table(df_mezz_idc, {"Draw Down": "€{:,.0f}", "IDC": "€{:,.0f}"})

                with col_mezz_dsra:
                    st.markdown("**DSRA Drawdown**")
                    st.caption("Funded by Creation Capital at M24")
                    st.markdown(f"""
                    | Item | Amount |
                    |------|--------|
                    | DSRA Size | €{computed_dsra_eur:,.2f} |
                    | Drawn at | Period 1 (M24) |
                | Purpose | Fund Senior P1-P2 via FEC |
                    """)
                    st.caption("DSRA (ZAR) → FEC → EUR prepayment")

                with col_mezz_repay:
                    st.markdown("**Repayment Structure**")
                    st.caption(f"{mezz_repayments} periods starting M24")
                    st.markdown(f"""
                    | Item | Amount |
                    |------|--------|
                    | Initial Drawdown | €{mezz_amount_eur:,.2f} |
                    | Total IDC | €{mezz_idc_total:,.2f} |
                    | Balance before DSRA | €{balance_before_dsra:,.2f} |
                    | DSRA at P1 | €{computed_dsra_eur:,.2f} |
                    | **Total for Repay** | €{balance_with_dsra:,.2f} |
                    | **P per period** | €{mezz_p_per_period:,.2f} |
                    """)
                st.caption("Repayment = Principle + Interest")

            st.divider()

            # CC Accelerated Payoff (from Debt Sculpting cascade)
            with st.container(border=True):
                st.markdown("**CC Accelerated Payoff** _(from Debt Sculpting cascade)_")
                _cc_payoff_data = {
                    'Year': [f'Y{yi+1}' for yi in range(10)],
                    'CC Opening': [_eur_fmt.format(a['wf_cc_opening']) for a in annual_model],
                    'Mezz P+I + Entity Accel': [_eur_fmt.format(a.get('wf_mz_pi', 0)) for a in annual_model],
                    'One-Time Dividend': [_eur_fmt.format(a.get('wf_cc_slug_paid', 0)) for a in annual_model],
                    'CC Closing': [_eur_fmt.format(a['wf_cc_closing']) for a in annual_model],
                }
                st.dataframe(pd.DataFrame(_cc_payoff_data).set_index('Year').T, use_container_width=True)
                if nwl_swap_enabled:
                    st.info("DSRA replaced by Cross-Currency Swap \u2014 DSRA balance = 0")

            st.divider()

            # ── AUDIT: SCLCA Facilities ──
            _sclca_fac_checks = []
            # Senior facility Y10 closing = 0
            _sr_y10 = annual_model[-1]['bs_sr'] if annual_model else 0
            _mz_y10 = annual_model[-1]['bs_mz'] if annual_model else 0
            _sclca_fac_checks.append({
                    "name": "Senior Facility Y10 = 0",
                    "expected": 0.0,
                    "actual": _sr_y10,
            })
            _sclca_fac_checks.append({
                    "name": "Mezz Facility Y10 = 0",
                "expected": 0.0,
                "actual": _mz_y10,
            })
            run_page_audit(_sclca_fac_checks, "SCLCA — Facilities")

    # --- ASSETS TAB ---
    if "Assets" in _tab_map:
        with _tab_map["Assets"]:
            st.header("Assets")
            # ===========================================
            # ASSET SIDE (INTERCOMPANY LOANS)
            # ===========================================
            st.subheader("Asset Side (Intercompany Loans to Subsidiaries)")

            loans = structure['uses']['loans_to_subsidiaries']
            senior_ic_rate = senior['interest']['rate'] + INTERCOMPANY_MARGIN
            mezz_ic_rate = mezz['interest']['total_rate'] + INTERCOMPANY_MARGIN

            # Get senior loan drawdown schedule from config
            senior_drawdown_schedule = senior_detail['drawdown_schedule']  # [8789117, 2835775, 1818036, 0]
            senior_drawdown_periods = [-4, -3, -2, -1]  # Periods for drawdowns

            # IC loan format
            ic_format = {
                "Year": "{:.1f}",
                "Opening": "€{:,.0f}",
                "Draw Down": "€{:,.0f}",
                "Interest": "€{:,.0f}",
                "Principle": "€{:,.0f}",
                "Repayment": "€{:,.0f}",
                "Movement": "€{:,.0f}",
                "Closing": "€{:,.0f}"
            }

            # Totals for pro-rata calculations
            senior_total = sum(l["senior_portion"] for l in loans.values())
            mezz_total = sum(l["mezz_portion"] for l in loans.values())

            # NWL prepayment (full DTIC + GEPF - NWL-specific subsidies)
            nwl_pro_rata = loans["nwl"]["senior_portion"] / senior_total
            nwl_prepayment = prepayment_total  # Full amount to NWL, not pro-rata

            # Mezz IC common parameters
            mezz_ic_reps = mezz_repayments  # Same as facility (10)
            mezz_ic_drawdown_schedule = [mezz_amount_eur, 0, 0, 0]
            mezz_ic_periods = [-4, -3, -2, -1]

            # Asset-side branding uses each subsidiary logo
            _nwl_asset_logo = LOGO_DIR / ENTITY_LOGOS.get("nwl", "")
            _lanred_asset_logo = LOGO_DIR / ENTITY_LOGOS.get("lanred", "")
            _twx_asset_logo = LOGO_DIR / ENTITY_LOGOS.get("timberworx", "")

            # ===========================================
            # NWL (Senior + Mezz)
            # ===========================================
            with st.container(border=True):
                if _nwl_asset_logo.exists():
                    _nl, _nt = st.columns([1, 12])
                    with _nl:
                        st.image(str(_nwl_asset_logo), width=80)
                    with _nt:
                        st.markdown("### New Water Lanseria (NWL)")
                else:
                    st.markdown("### New Water Lanseria (NWL)")
                st.caption(f"Senior: €{loans['nwl']['senior_portion']:,.0f} | Mezz: €{loans['nwl']['mezz_portion']:,.0f} | Total: €{loans['nwl']['total_loan']:,.0f}")

                # --- NWL Senior IC (with prepayments + DSRA) ---
                with st.container(border=True):
                    st.markdown("#### Senior Intercompany Loan *(prepaying entity)*")

                    # Loan terms (2 rows x 3 columns) - matching SCLCA layout
                    _nwl_sr_tenure = senior['loan_holiday_months'] + senior['repayment_months']
                    _nwl_sr_r1 = st.columns(3)
                    with _nwl_sr_r1[0]:
                        st.caption("Principal")
                        st.markdown(f"**€{loans['nwl']['senior_portion']:,.0f}**")
                    with _nwl_sr_r1[1]:
                        st.caption("Interest")
                        st.markdown(f"**{senior['interest']['rate']*100:.2f}% + 0.5% = {senior_ic_rate*100:.2f}%**")
                    with _nwl_sr_r1[2]:
                        st.caption("Tenure")
                        st.markdown(f"**{senior['loan_holiday_months']} + {senior['repayment_months']} = {_nwl_sr_tenure} months**")

                    _nwl_sr_r2 = st.columns(3)
                    with _nwl_sr_r2[0]:
                        st.caption("Moratorium")
                        st.markdown(f"**{senior['loan_holiday_months']} months**")
                    with _nwl_sr_r2[1]:
                        st.caption("Repayments")
                        st.markdown(f"**{senior['repayments']} semi-annual**")
                    with _nwl_sr_r2[2]:
                        st.caption("IDC")
                        st.markdown("**Roll-up, add to principal**")

                    nwl_sr_rows = []
                    nwl_sr_balance = 0.0
                    nwl_sr_num_repayments = senior['repayments']  # 14

                    # Grace periods (-4 to -1)
                    for idx, period in enumerate(senior_drawdown_periods):
                        month = (period + 4) * 6
                        year = month / 12
                        opening = nwl_sr_balance

                        # IDC
                        idc = opening * senior_ic_rate / 2

                        # Pro-rata drawdown
                        draw_down = senior_drawdown_schedule[idx] * nwl_pro_rata if idx < len(senior_drawdown_schedule) else 0

                        # Prepayment at P-1 (NWL receives DTIC+GEPF, prepays IC loan)
                        if period == -1:
                            principle = -nwl_prepayment
                        else:
                            principle = 0

                        repayment = principle
                        movement = draw_down + idc + principle
                        nwl_sr_balance = opening + movement

                        nwl_sr_rows.append({
                            "Period": period, "Month": month, "Year": year,
                            "Opening": opening, "Draw Down": draw_down, "Interest": idc,
                            "Principle": principle, "Repayment": repayment,
                            "Movement": movement, "Closing": nwl_sr_balance
                        })

                    # After grace: use FIXED DSRA principle (same as SCLCA, only interest differs)
                    nwl_sr_balance_for_repay = nwl_sr_balance
                    nwl_sr_dsra_principle = dsra_principle_fixed  # Same as SCLCA
                    nwl_sr_balance_after_dsra = nwl_sr_balance_for_repay - nwl_sr_dsra_principle
                    nwl_sr_new_p = nwl_sr_balance_after_dsra / (nwl_sr_num_repayments - 2)  # 12 periods

                    # Repayment periods (1-14)
                    for i in range(1, nwl_sr_num_repayments + 1):
                        period = i
                        month = 18 + (i * 6)
                        year = month / 12
                        opening = nwl_sr_balance

                        interest = opening * senior_ic_rate / 2

                        if period == 1:
                            # DSRA prepayment
                            principle = -nwl_sr_dsra_principle
                            dsra_note = " *"
                        elif period == 2:
                            # Interest only
                            principle = 0
                            dsra_note = " *"
                        else:
                            # Regular P
                            principle = -nwl_sr_new_p
                            dsra_note = ""

                        repayment = principle - interest
                        movement = principle
                        nwl_sr_balance = opening + movement

                        nwl_sr_rows.append({
                            "Period": f"{period}{dsra_note}", "Month": month, "Year": year,
                            "Opening": opening, "Draw Down": 0, "Interest": interest,
                            "Principle": principle, "Repayment": repayment,
                            "Movement": movement, "Closing": nwl_sr_balance
                        })

                    df_nwl_senior = pd.DataFrame(nwl_sr_rows)
                    render_table(df_nwl_senior, ic_format)

                    # Helper tables for NWL Senior IC
                    st.markdown("---")
                    col_nwl_idc, col_nwl_dsra, col_nwl_repay = st.columns(3)

                    # Calculate IDC for helper table
                    nwl_idc_data = []
                    nwl_idc_bal = 0.0
                    nwl_idc_total = 0.0
                    nwl_dd_total = 0.0
                    for idx, dd in enumerate(senior_drawdown_schedule):
                        nwl_dd = dd * nwl_pro_rata
                        idc_amt = nwl_idc_bal * senior_ic_rate / 2
                        nwl_idc_total += idc_amt
                        nwl_dd_total += nwl_dd
                        nwl_idc_data.append({"Period": -4 + idx, "Draw Down": nwl_dd, "IDC": idc_amt})
                        nwl_idc_bal += nwl_dd + idc_amt
                    nwl_idc_data.append({"Period": "Total", "Draw Down": nwl_dd_total, "IDC": nwl_idc_total})

                    with col_nwl_idc:
                        st.markdown("**IDC (NWL Senior IC)**")
                        st.caption(f"Interest capitalized at {senior_ic_rate*100:.2f}%")
                        df_nwl_idc = pd.DataFrame(nwl_idc_data)
                        render_table(df_nwl_idc, {"Draw Down": "€{:,.0f}", "IDC": "€{:,.0f}"})

                    with col_nwl_dsra:
                        st.markdown("**DSRA (Fixed from SCLCA)**")
                        st.caption("Same principle, different interest rate")
                        st.markdown(f"""
                    | Item | Amount |
                    |------|--------|
                    | DSRA Principle | €{nwl_sr_dsra_principle:,.0f} |
                    | NWL Interest M24 | €{nwl_sr_balance_for_repay * senior_ic_rate / 2:,.0f} |
                    | M24 Repayment | €{nwl_sr_dsra_principle + nwl_sr_balance_for_repay * senior_ic_rate / 2:,.0f} |
                    | M30 (I only) | €{nwl_sr_balance_after_dsra * senior_ic_rate / 2:,.0f} |
                    """)
                        st.caption("DSRA principle identical to SCLCA")

                    with col_nwl_repay:
                        st.markdown("**Repayment Structure**")
                        st.caption("After prepayments, 12 periods remain")
                        st.markdown(f"""
                    | Item | Amount |
                    |------|--------|
                    | **P-1 Prepay** | €{nwl_prepayment:,.0f} |
                    | Balance for repay | €{nwl_sr_balance_for_repay:,.0f} |
                    | **P1 DSRA** | €{nwl_sr_dsra_principle:,.0f} |
                    | Balance after DSRA | €{nwl_sr_balance_after_dsra:,.0f} |
                    | **New P** (bal÷12) | €{nwl_sr_new_p:,.0f} |
                    """)
                        st.caption("Repayment = Principle + Interest")

                st.divider()

                # --- NWL Mezz IC (with DSRA drawdown) ---
                st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual *(receives DSRA drawdown)*")

                nwl_mezz_pro_rata = loans["nwl"]["mezz_portion"] / mezz_total
                nwl_mz_rows = []
                nwl_mz_balance = 0.0

                # Grace periods
                for idx, period in enumerate(mezz_ic_periods):
                    month = (period + 4) * 6
                    year = month / 12
                    opening = nwl_mz_balance
                    idc = opening * mezz_ic_rate / 2
                    draw_down = mezz_ic_drawdown_schedule[idx] * nwl_mezz_pro_rata if idx < len(mezz_ic_drawdown_schedule) else 0
                    movement = draw_down + idc
                    nwl_mz_balance = opening + movement
                    nwl_mz_rows.append({
                        "Period": period, "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": draw_down, "Interest": idc,
                        "Principle": 0, "Repayment": 0, "Movement": movement, "Closing": nwl_mz_balance
                    })

                # DSRA drawn at P1
                nwl_mz_balance_before_dsra = nwl_mz_balance
                nwl_mz_balance_with_dsra = nwl_mz_balance_before_dsra + computed_dsra_eur
                nwl_mz_p_per = nwl_mz_balance_with_dsra / mezz_ic_reps

                # Repayment periods
                for i in range(1, mezz_ic_reps + 1):
                    month = 18 + (i * 6)
                    year = month / 12
                    opening = nwl_mz_balance

                    if i == 1:
                        draw_down = computed_dsra_eur
                        dsra_note = " *"
                    else:
                        draw_down = 0
                        dsra_note = ""

                    interest = opening * mezz_ic_rate / 2
                    principle = -nwl_mz_p_per
                    repayment = principle - interest
                    movement = draw_down + principle
                    nwl_mz_balance = opening + movement

                    nwl_mz_rows.append({
                        "Period": f"{i}{dsra_note}", "Month": month, "Year": year,
                        "Opening": opening, "Draw Down": draw_down, "Interest": interest,
                        "Principle": principle, "Repayment": repayment, "Movement": movement, "Closing": nwl_mz_balance
                    })

                df_nwl_mezz = pd.DataFrame(nwl_mz_rows)
                render_table(df_nwl_mezz, ic_format)

                st.caption(f"""
            **NWL Mezz IC Notes:**
            - **P1 (*):** DSRA drawdown €{computed_dsra_eur:,.0f} (increases NWL's Mezz liability)
            - **Repayments:** P = €{nwl_mz_p_per:,.0f} on total (original + IDC + DSRA)
            - DSRA flows: NWL Mezz ↑ → SCLCA Mezz ↑ → FEC → SCLCA Senior ↓ → NWL Senior ↓
            """)

                st.divider()
                st.markdown("#### Equity Stake")
                _eq_nwl_c1, _eq_nwl_c2, _eq_nwl_c3 = st.columns(3)
                with _eq_nwl_c1:
                    st.metric("SCLCA Ownership", "93%", "€46,500")
                with _eq_nwl_c2:
                    st.metric("Share Capital", "R1m", "€50,000 at FX 20")
                with _eq_nwl_c3:
                    _cp_logo_a = LOGO_DIR / ENTITY_LOGOS.get("crosspoint", "")
                    if _cp_logo_a.exists():
                        st.image(str(_cp_logo_a), width=80)
                    st.markdown("**Crosspoint — 7%**")
                    st.caption("Property Investments")

            st.divider()

            # ===========================================
            # LANRED (Senior + Mezz)
            # ===========================================
            with st.container(border=True):
                if _lanred_asset_logo.exists():
                    _ll, _lt = st.columns([1, 12])
                    with _ll:
                        st.image(str(_lanred_asset_logo), width=80)
                    with _lt:
                        st.markdown("### LanRED")
                else:
                    st.markdown("### LanRED")
                st.caption(f"Senior: €{loans['lanred']['senior_portion']:,.0f} | Mezz: €{loans['lanred']['mezz_portion']:,.0f} | Total: €{loans['lanred']['total_loan']:,.0f}")

                # --- LanRED Senior IC ---
                st.markdown(f"**Senior IC** — {senior_ic_rate*100:.2f}% | {senior['repayments']} semi-annual")
                df_lanred_senior = pd.DataFrame(build_simple_ic_schedule(
                    loans["lanred"]["senior_portion"], senior_total, senior['repayments'],
                    senior_ic_rate, senior_drawdown_schedule, senior_drawdown_periods
                ))
                render_table(df_lanred_senior, ic_format)

                # --- LanRED Mezz IC ---
                st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual")
                df_lanred_mezz = pd.DataFrame(build_simple_ic_schedule(
                    loans["lanred"]["mezz_portion"], mezz_total, mezz_ic_reps,
                    mezz_ic_rate, mezz_ic_drawdown_schedule, mezz_ic_periods
                ))
                render_table(df_lanred_mezz, ic_format)

                st.divider()
                st.markdown("#### Equity Stake")
                _eq_lr_c1, _eq_lr_c2 = st.columns(2)
                with _eq_lr_c1:
                    st.metric("SCLCA Ownership", "100%", "€50,000")
                with _eq_lr_c2:
                    st.metric("Share Capital", "R1m", "Wholly owned subsidiary")

            st.divider()

            # ===========================================
            # TIMBERWORX (Senior + Mezz)
            # ===========================================
            with st.container(border=True):
                if _twx_asset_logo.exists():
                    _tl, _tt = st.columns([1, 12])
                    with _tl:
                        st.image(str(_twx_asset_logo), width=80)
                    with _tt:
                        st.markdown("### Timberworx")
                else:
                    st.markdown("### Timberworx")
                st.caption(f"Senior: €{loans['timberworx']['senior_portion']:,.0f} | Mezz: €{loans['timberworx']['mezz_portion']:,.0f} | Total: €{loans['timberworx']['total_loan']:,.0f}")

                # --- Timberworx Senior IC ---
                st.markdown(f"**Senior IC** — {senior_ic_rate*100:.2f}% | {senior['repayments']} semi-annual")
                df_twx_senior = pd.DataFrame(build_simple_ic_schedule(
                    loans["timberworx"]["senior_portion"], senior_total, senior['repayments'],
                    senior_ic_rate, senior_drawdown_schedule, senior_drawdown_periods
                ))
                render_table(df_twx_senior, ic_format)

                # --- Timberworx Mezz IC ---
                st.markdown(f"**Mezz IC** — {mezz_ic_rate*100:.2f}% | {mezz_ic_reps} semi-annual")
                df_twx_mezz = pd.DataFrame(build_simple_ic_schedule(
                    loans["timberworx"]["mezz_portion"], mezz_total, mezz_ic_reps,
                    mezz_ic_rate, mezz_ic_drawdown_schedule, mezz_ic_periods
                ))
                render_table(df_twx_mezz, ic_format)

                st.divider()
                st.markdown("#### Equity Stake")
                _eq_twx_c1, _eq_twx_c2, _eq_twx_c3 = st.columns(3)
                with _eq_twx_c1:
                    st.metric("SCLCA Ownership", "5%", "€2,500")
                with _eq_twx_c2:
                    st.metric("Share Capital", "R1m", "€50,000 at FX 20")
                with _eq_twx_c3:
                    _vs_logo_a = LOGO_DIR / ENTITY_LOGOS.get("vansquare", "")
                    if _vs_logo_a.exists():
                        st.image(str(_vs_logo_a), width=80)
                    st.markdown("**VanSquare — 95%**")

            st.divider()

            # Equity now shown per company container above

            # ===========================================
            # SCLCA Assets: DSRA flow diagram + FEC + DSRA(FD)
            # ===========================================
            with st.container(border=True):
                st.subheader("DSRA Mechanism (Cash Flow)")
                st.caption("Understanding how DSRA funds the FEC and is replenished by operations")

                st.markdown("""
            **DSRA Flow (M24 / Period 1):**

            | Step | Action | Effect |
            |------|--------|--------|
            | 1 | Creation Capital funds DSRA | SCLCA receives ZAR (liability to CC) |
            | 2 | DSRA buys FEC from Investec | ZAR converted to locked EUR rate |
            | 3 | FEC prepays Senior P1+P2 | Senior debt reduced by 2×(P + I) |
            | 4 | Operations generate surplus | Net cash from IC loan interest margin |
            | 5 | Surplus accumulates in DSRA | Earns 9% p.a. as Fixed Deposit |

            **Key insight:** The initial DSRA funding is immediately used to buy FEC (forex hedge). It's a pass-through.
            The DSRA then fills up again from operational surplus (interest margin on IC loans).
            """)

            _dsra_flow_svg = Path(__file__).parent / "assets" / "dsra-flow.svg"
            if _dsra_flow_svg.exists():
                st.image(str(_dsra_flow_svg), use_container_width=False, width=640)

            with st.container(border=True):
                st.subheader("FEC (Forward Exchange Cover)")
                st.caption("DSRA funded by Creation Capital at M24 → immediately used to buy FEC from Investec (forex hedge)")

                _fec_r1 = st.columns(4)
                with _fec_r1[0]:
                    st.caption("DSRA Funding (M24)")
                    st.markdown(f"**€{dsra_principle_fixed:,.0f}**")
                with _fec_r1[1]:
                    st.caption("Sizing Basis")
                    st.markdown("**2×(P + I_M24)**")
                with _fec_r1[2]:
                    st.caption("FEC Provider")
                    st.markdown("**Investec**")
                with _fec_r1[3]:
                    st.caption("Purpose")
                    st.markdown("**Forex hedge on Senior**")

                st.divider()

                # ===========================================
                # DSRA (Fixed Deposit) Schedule
                # ===========================================
                with st.container(border=True):
                    st.subheader("DSRA (Fixed Deposit)")
                    st.markdown("**Opening** + **Deposit** (Net Cash Flow) + **Interest** (4.4%/6mo) = **Closing**")
                    st.caption("Semi-annual compounding @ 9% p.a. = 4.4% per 6 months")

                    # Build DSRA schedule: semi-annual calculation
                    # Semi-annual interest rate: (1.09)^0.5 - 1 ≈ 0.04403
                    dsra_rate_semiannual = (1 + DSRA_RATE) ** 0.5 - 1

                    fd_rows = []
                    _fd_bal = 0.0

                    # Loop through semi-annual periods matching Senior/Mezz schedule
                    # Periods 1-20 = H1 Y1, H2 Y1, H1 Y2, ... H2 Y10
                    for period_idx in range(20):  # 10 years × 2 = 20 periods
                        year = (period_idx // 2) + 1
                        half = 'H1' if period_idx % 2 == 0 else 'H2'
                        period_label = f"{half} Y{year}"

                        # Get semi-annual data
                        sem_data = _sem[period_idx]

                        opening = _fd_bal
                        # Deposit = Cash margin (interest margin + principal margin)
                        # Cash interest margin (excluding DSRA interest to avoid double-counting)
                        cash_ii = sem_data['isi_cash'] + sem_data['imi_cash']
                        cash_ie = sem_data['si_cash'] + sem_data['mi_cash']
                        # Principal margin (IC principal in > facility principal out)
                        principal_margin = (sem_data['isp'] + sem_data['imp']) - (sem_data['sp'] + sem_data['mp'])
                        deposit = cash_ii - cash_ie + principal_margin

                        # Interest on opening balance (semi-annual rate)
                        interest = opening * dsra_rate_semiannual
                        closing = opening + deposit + interest
                        _fd_bal = closing

                        fd_rows.append({
                            "Period": period_label,
                            "Opening": opening,
                            "Deposit": deposit,
                            "Interest": interest,
                            "Closing": closing
                        })

                    df_fd = pd.DataFrame(fd_rows)
                    render_table(df_fd, {
                        "Opening": "€{:,.0f}", "Deposit": "€{:,.0f}",
                        "Interest": "€{:,.0f}", "Closing": "€{:,.0f}"
                    })

            # ── AUDIT: SCLCA Assets ──
            _sclca_ast_checks = []
            # IC receivable Y10 = 0 (all IC loans repaid)
            _sclca_ast_checks.append({
                "name": "IC Senior receivable Y10 = 0",
                "expected": 0.0,
                "actual": annual_model[-1]['bs_isr'],
            })
            _sclca_ast_checks.append({
                "name": "IC Mezz receivable Y10 = 0",
                "expected": 0.0,
                "actual": annual_model[-1]['bs_imz'],
            })
            # Equity in subs = constant
            _sclca_ast_checks.append({
                "name": "Equity in subs = constant",
                "expected": EQUITY_TOTAL,
                "actual": annual_model[-1]['bs_eq_subs'],
            })
            run_page_audit(_sclca_ast_checks, "SCLCA — Assets")

    # --- OPERATIONS TAB ---
    if "Operations" in _tab_map:
        with _tab_map["Operations"]:
            st.header("Operations")
            st.caption("Revenue from investments (6 IC loans) vs Finance costs (2 source facilities)")

            # Calculate pro-rata shares for each subsidiary
            _loans = structure['uses']['loans_to_subsidiaries']
            _sr_total = sum(l['senior_portion'] for l in _loans.values())
            _mz_total = sum(l['mezz_portion'] for l in _loans.values())

            nwl_sr_pct = _loans['nwl']['senior_portion'] / _sr_total
            nwl_mz_pct = _loans['nwl']['mezz_portion'] / _mz_total
            lanred_sr_pct = _loans['lanred']['senior_portion'] / _sr_total
            lanred_mz_pct = _loans['lanred']['mezz_portion'] / _mz_total
            twx_sr_pct = _loans['timberworx']['senior_portion'] / _sr_total
            twx_mz_pct = _loans['timberworx']['mezz_portion'] / _mz_total

            # Summary metrics
            total_ii = sum(a['ii'] for a in annual_model)
            total_ie = sum(a['ie'] for a in annual_model)
            total_margin = total_ii - total_ie

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Revenue from Investments", f"€{total_ii:,.0f}")
            with col2:
                st.metric("Finance Costs", f"€{total_ie:,.0f}")
            with col3:
                st.metric("Net Margin", f"€{total_margin:,.0f}")
            with col4:
                st.metric("IC Spread", f"{INTERCOMPANY_MARGIN*100:.1f}%")

            st.divider()

            # Build transposed operations table (rows = line items, columns = years)
            year_cols = [f"Y{a['year']}" for a in annual_model] + ['Total']

            # Revenue rows
            ops_data = {
                'Item': [],
                **{yc: [] for yc in year_cols}
            }

            # Revenue from Investments - 6 IC Loans
            ops_data['Item'].append('**REVENUE FROM INVESTMENTS**')
            for yc in year_cols:
                ops_data[yc].append('')

            for label, sr_pct, mz_pct in [
                ('NWL Senior IC', nwl_sr_pct, 0),
                ('NWL Mezz IC', 0, nwl_mz_pct),
                ('LanRED Senior IC', lanred_sr_pct, 0),
                ('LanRED Mezz IC', 0, lanred_mz_pct),
                ('TWX Senior IC', twx_sr_pct, 0),
                ('TWX Mezz IC', 0, twx_mz_pct),
            ]:
                ops_data['Item'].append(label)
                row_total = 0
                for i, a in enumerate(annual_model):
                    val = a['ii_sr'] * sr_pct + a['ii_mz'] * mz_pct
                    ops_data[year_cols[i]].append(val)
                    row_total += val
                ops_data['Total'].append(row_total)

            # DSRA Interest (on surplus cash)
            ops_data['Item'].append('DSRA (9%)')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(a['ii_dsra'])
            ops_data['Total'].append(sum(a['ii_dsra'] for a in annual_model))

            # Total Revenue
            ops_data['Item'].append('**Total Revenue**')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(a['ii'])
            ops_data['Total'].append(total_ii)

            # Spacer
            ops_data['Item'].append('')
            for yc in year_cols:
                ops_data[yc].append('')

            # Finance Costs - 2 Source Facilities
            ops_data['Item'].append('**FINANCE COSTS**')
            for yc in year_cols:
                ops_data[yc].append('')

            ops_data['Item'].append('Senior Debt (Invest Int)')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(-a['ie_sr'])
            ops_data['Total'].append(-sum(a['ie_sr'] for a in annual_model))

            ops_data['Item'].append('Mezzanine (Creation Cap)')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(-a['ie_mz'])
            ops_data['Total'].append(-sum(a['ie_mz'] for a in annual_model))

            ops_data['Item'].append('**Total Finance Costs**')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(-a['ie'])
            ops_data['Total'].append(-total_ie)

            # Spacer
            ops_data['Item'].append('')
            for yc in year_cols:
                ops_data[yc].append('')

            # Net Margin
            ops_data['Item'].append('**NET MARGIN**')
            for i, a in enumerate(annual_model):
                ops_data[year_cols[i]].append(a['ni'])
            ops_data['Total'].append(total_margin)

            df_ops = pd.DataFrame(ops_data)
            render_table(df_ops, {c: "€{:,.0f}" for c in year_cols})

            # ── AUDIT: SCLCA Operations (silent) ──
            # Audit checks run silently in background for data validation
            # No UI display to keep the tab clean

    # --- P&L TAB ---
    if "P&L" in _tab_map:
        with _tab_map["P&L"]:
            st.header("Profit & Loss")
            st.caption("Financial holding company - Income from investments vs Cost of funding")

            total_ni = sum(a['ni'] for a in annual_model)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("10-Year Net Income", f"€{total_ni:,.0f}")
            with col2:
                st.metric("Avg Annual", f"€{total_ni / 10:,.0f}")
            with col3:
                st.metric("IC Spread", f"{INTERCOMPANY_MARGIN*100:.1f}%")

            st.divider()

            # Build transposed P&L (rows = line items, columns = years)
            _pnl_cols = [f"Y{a['year']}" for a in annual_model] + ['Total']
            _ncols = len(_pnl_cols)
            _pnl_rows = []  # list of (label, values, row_type)

            def _pnl_line(label, key, sign=1.0, row_type='line'):
                vals = [sign * a.get(key, 0.0) for a in annual_model]
                _pnl_rows.append((label, vals + [sum(vals)], row_type))

            def _pnl_section(label):
                _pnl_rows.append((label, [None] * _ncols, 'section'))

            def _pnl_spacer():
                _pnl_rows.append(('', [None] * _ncols, 'spacer'))

            # REVENUE
            _pnl_section('REVENUE')
            _pnl_line('Interest Income (IC Loans)', 'ii_ic')
            _pnl_line('Interest Income (DSRA)', 'ii_dsra')
            _pnl_line('Total Revenue', 'ii', row_type='total')

            # FINANCE COSTS
            _pnl_spacer()
            _pnl_section('FINANCE COSTS')
            _pnl_line('Finance Costs', 'ie', -1.0)

            # BOTTOM LINE
            _pnl_spacer()
            _pnl_section('BOTTOM LINE')
            _pnl_line('Net Income', 'ni', row_type='grand')

            # Build styled HTML table
            _fmt = _eur_fmt
            _h = ['<div style="overflow-x:auto;width:100%;">',
                  '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                  '<thead><tr>']
            _h.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _pnl_cols:
                _h.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h.append('</tr></thead><tbody>')

            for label, vals, rtype in _pnl_rows:
                if rtype == 'spacer':
                    _h.append(f'<tr><td colspan="{_ncols + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h.append(f'<tr><td colspan="{_ncols + 1}" style="padding:8px 10px 4px;font-weight:700;'
                              f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                # Style per row type
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                    lbl_style = td_style
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                    lbl_style = td_style
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                    lbl_style = td_style
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                    lbl_style = td_style
                _h.append('<tr>')
                _h.append(f'<td style="text-align:left;padding:4px 10px;{lbl_style}">{label}</td>')
                for v in vals:
                    cell = _fmt.format(v) if v is not None and not isinstance(v, str) else ''
                    _h.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h.append('</tr>')

            _h.append('</tbody></table></div>')
            st.markdown(''.join(_h), unsafe_allow_html=True)

            st.divider()

            # Chart - Stacked income by subsidiary vs expense, with DSCR
            _pnl_loans = structure['uses']['loans_to_subsidiaries']
            _pnl_sr_tot = sum(l['senior_portion'] for l in _pnl_loans.values())
            _pnl_mz_tot = sum(l['mezz_portion'] for l in _pnl_loans.values())

            # Per-company pro-rata
            _nwl_sr_p = _pnl_loans['nwl']['senior_portion'] / _pnl_sr_tot
            _nwl_mz_p = _pnl_loans['nwl']['mezz_portion'] / _pnl_mz_tot
            _lr_sr_p = _pnl_loans['lanred']['senior_portion'] / _pnl_sr_tot
            _lr_mz_p = _pnl_loans['lanred']['mezz_portion'] / _pnl_mz_tot
            _twx_sr_p = _pnl_loans['timberworx']['senior_portion'] / _pnl_sr_tot
            _twx_mz_p = _pnl_loans['timberworx']['mezz_portion'] / _pnl_mz_tot

            # Per-company income per year
            _nwl_ii = [a['ii_sr'] * _nwl_sr_p + a['ii_mz'] * _nwl_mz_p for a in annual_model]
            _lr_ii = [a['ii_sr'] * _lr_sr_p + a['ii_mz'] * _lr_mz_p for a in annual_model]
            _twx_ii = [a['ii_sr'] * _twx_sr_p + a['ii_mz'] * _twx_mz_p for a in annual_model]
            _dsra_ii = [a['ii_dsra'] for a in annual_model]
            _tot_ie = [a['ie'] for a in annual_model]
            _tot_ii = [a['ii'] for a in annual_model]
            _years = [a['year'] for a in annual_model]

            # Company colors
            CLR_NWL = '#2563EB'     # Blue
            CLR_LR = '#EAB308'      # Yellow
            CLR_TWX = '#8B4513'     # Timber brown
            CLR_DSRA = '#16A34A'    # Green

            fig_pnl = go.Figure()

            # Stacked income bars (offsetgroup='income')
            fig_pnl.add_trace(go.Bar(
                x=_years, y=_nwl_ii, name='NWL', marker_color=CLR_NWL,
                offsetgroup='income', legendgroup='income'
            ))
            fig_pnl.add_trace(go.Bar(
                x=_years, y=_lr_ii, name='LanRED', marker_color=CLR_LR,
                offsetgroup='income', legendgroup='income'
            ))
            fig_pnl.add_trace(go.Bar(
                x=_years, y=_twx_ii, name='Timberworx', marker_color=CLR_TWX,
                offsetgroup='income', legendgroup='income'
            ))
            fig_pnl.add_trace(go.Bar(
                x=_years, y=_dsra_ii, name='DSRA Interest', marker_color=CLR_DSRA,
                offsetgroup='income', legendgroup='income'
            ))

            # Expense bar (positive, next to income)
            fig_pnl.add_trace(go.Bar(
                x=_years, y=_tot_ie, name='Finance Costs', marker_color='#DC2626',
                offsetgroup='expense'
            ))

            # DSCR annotations (only meaningful while debt outstanding)
            for i, yr in enumerate(_years):
                if _tot_ie[i] > 1000:  # Only show DSCR when meaningful finance costs exist
                    dscr = _tot_ii[i] / _tot_ie[i]
                    fig_pnl.add_annotation(
                        x=yr, y=max(_tot_ii[i], _tot_ie[i]),
                        text=f"<b>{dscr:.2f}x</b>", showarrow=False,
                        yshift=20, font=dict(size=11, color='#1E3A5F')
                    )
                elif _tot_ie[i] <= 1000 and _tot_ii[i] > 0:
                    fig_pnl.add_annotation(
                        x=yr, y=_tot_ii[i],
                        text="<b>Debt Free</b>", showarrow=False,
                        yshift=20, font=dict(size=10, color='#16A34A')
                    )

            fig_pnl.update_layout(
                title='P&L - Interest Income (by subsidiary) vs Finance Costs',
                xaxis_title='Year', yaxis_title='EUR',
                barmode='stack', xaxis=dict(dtick=1),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
            )
            st.plotly_chart(fig_pnl, use_container_width=True)

            # ── AUDIT: SCLCA P&L ──
            _sclca_pl_checks = []
            for _a in annual_model:
                _y = _a['year']
                _sclca_pl_checks.append({
                    "name": f"Y{_y}: NI = II - IE",
                    "expected": _a['ii'] - _a['ie'],
                    "actual": _a['ni'],
                })
            _sclca_pl_checks.append({
                "name": "10yr NI = sum(NI)",
                "expected": sum(_a['ni'] for _a in annual_model),
                "actual": sum(_a['ni'] for _a in annual_model),
            })
            run_page_audit(_sclca_pl_checks, "SCLCA — P&L")

            # Waterfall allocation expander (v3.1 — 6-step)
            with st.expander("Waterfall Allocation"):
                _wf_pl_cols = [f"Y{w['year']}" for w in _waterfall]
                _wf_pl_data = {
                    'Pool': [_eur_fmt.format(w['pool_total']) for w in _waterfall],
                    '1. Senior P+I (pass-through)': [_eur_fmt.format(w.get('wf_sr_pi', 0)) for w in _waterfall],
                    '2. Mezz P+I + Accel (pass-through)': [_eur_fmt.format(w.get('wf_mz_pi', 0)) for w in _waterfall],
                    '3. DSRA Top-up': [_eur_fmt.format(w.get('wf_dsra_topup', 0)) for w in _waterfall],
                    '4. One-Time Dividend': [_eur_fmt.format(w.get('wf_cc_slug_paid', 0)) for w in _waterfall],
                    '5. Senior Acceleration': [_eur_fmt.format(w.get('wf_sr_accel', 0)) for w in _waterfall],
                    '6. Fixed Deposit': [_eur_fmt.format(w.get('wf_fd_deposit', 0)) for w in _waterfall],
                }
                st.dataframe(pd.DataFrame(_wf_pl_data, index=_wf_pl_cols).T, use_container_width=True)

            # Waterfall P&L adjustments expander
            with st.expander("Waterfall P&L Adjustments"):
                st.caption("Mezz repayment and one-time dividend impact on SCLCA P&L")
                _wf_pl_adj = {
                    'Mezz P+I + Entity Accel': [_eur_fmt.format(-a.get('wf_mz_pi', 0)) for a in annual_model],
                    'One-Time Dividend Paid': [_eur_fmt.format(-a.get('wf_cc_slug_paid', 0)) for a in annual_model],
                }
                st.dataframe(pd.DataFrame(_wf_pl_adj, index=_wf_pl_cols).T, use_container_width=True)

    # --- CASH FLOW TAB ---
    if "Cash Flow" in _tab_map:
        with _tab_map["Cash Flow"]:
            st.header("Cash Flow Statement")
            st.caption("All surplus cash flows to DSRA at 9%")

            total_cf_net = sum(a['cf_net'] for a in annual_model)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Net Cash Flow", f"€{total_cf_net:,.0f}")
            with col2:
                st.metric("Ending DSRA Balance", f"€{annual_model[-1]['dsra_bal']:,.0f}")
            with col3:
                st.metric("DSRA Rate", "9%")

            st.divider()

            # Build transposed Cash Flow (rows = line items, columns = years)
            _cf_cols = [f"Y{a['year']}" for a in annual_model] + ['Total']
            _ncols_cf = len(_cf_cols)
            _cf_rows = []  # list of (label, values, row_type)

            def _cf_line(label, key, sign=1.0, row_type='line'):
                vals = [sign * a.get(key, 0.0) for a in annual_model]
                _cf_rows.append((label, vals + [sum(vals)], row_type))

            def _cf_computed_line(label, values_list, row_type='line'):
                # For computed values that don't have a single key
                _cf_rows.append((label, values_list, row_type))

            def _cf_section(label):
                _cf_rows.append((label, [None] * _ncols_cf, 'section'))

            def _cf_spacer():
                _cf_rows.append(('', [None] * _ncols_cf, 'spacer'))

            # PRINCIPAL - DRAWDOWNS
            _cf_section('PRINCIPAL - DRAWDOWNS')
            _cf_line('Drawdowns Received (Facilities)', 'cf_draw_in')
            _cf_line('Deployments to IC Loans', 'cf_draw_out', -1.0)
            _cf_computed_line('Net Drawdowns',
                [a['cf_draw_in'] - a['cf_draw_out'] for a in annual_model] +
                [sum(a['cf_draw_in'] - a['cf_draw_out'] for a in annual_model)],
                'sub')

            # PRINCIPAL - PREPAYMENTS
            _cf_spacer()
            _cf_section('PRINCIPAL - PREPAYMENTS')
            _cf_line('Prepayment Received (NWL IC)', 'cf_prepay_in')
            _cf_line('Prepayment Paid (Senior)', 'cf_prepay_out', -1.0)
            _cf_computed_line('Net Prepayments',
                [a['cf_prepay_in'] - a['cf_prepay_out'] for a in annual_model] +
                [sum(a['cf_prepay_in'] - a['cf_prepay_out'] for a in annual_model)],
                'sub')

            # PRINCIPAL - REPAYMENTS
            _cf_spacer()
            _cf_section('PRINCIPAL - REPAYMENTS')
            _cf_line('Repayments Received (IC Loans)', 'cf_repay_in')
            _cf_line('Repayments Paid (Facilities)', 'cf_repay_out', -1.0)
            _cf_computed_line('Net Repayments',
                [a['cf_repay_in'] - a['cf_repay_out'] for a in annual_model] +
                [sum(a['cf_repay_in'] - a['cf_repay_out'] for a in annual_model)],
                'sub')

            # INTEREST
            _cf_spacer()
            _cf_section('INTEREST')
            _cf_computed_line('Interest Received (IC Loans)',
                [a['cf_ii'] - a['ii_dsra'] for a in annual_model] +
                [sum(a['cf_ii'] - a['ii_dsra'] for a in annual_model)])
            _cf_line('Interest Received (DSRA 9%)', 'ii_dsra')
            _cf_line('Interest Paid (Facilities)', 'cf_ie', -1.0)
            _cf_computed_line('Net Interest',
                [a['cf_ii'] - a['cf_ie'] for a in annual_model] +
                [sum(a['cf_ii'] - a['cf_ie'] for a in annual_model)],
                'total')

            # DSRA → FEC
            _cf_spacer()
            _cf_section('DSRA → FEC')
            _cf_computed_line('DSRA Received (Creation Capital)',
                [dsra_principle_fixed if a['year'] == 2 else 0 for a in annual_model] + [dsra_principle_fixed])
            _cf_computed_line('FEC Purchased (Investec)',
                [-dsra_principle_fixed if a['year'] == 2 else 0 for a in annual_model] + [-dsra_principle_fixed])
            _cf_computed_line('Net DSRA/FEC',
                [0 for _ in annual_model] + [0],
                'sub')

            # WATERFALL DEPLOYMENT (v3.1 — 6-step cascade)
            _cf_spacer()
            _cf_section('WATERFALL DEPLOYMENT')
            _cf_computed_line('Entity Pool',
                [a.get('wf_pool', 0) for a in annual_model] + [sum(a.get('wf_pool', 0) for a in annual_model)])
            _cf_computed_line('1. Senior P+I (pass-through)',
                [-a.get('wf_sr_pi', 0) for a in annual_model] + [-sum(a.get('wf_sr_pi', 0) for a in annual_model)])
            _cf_computed_line('2. Mezz P+I + Accel (pass-through)',
                [-a.get('wf_mz_pi', 0) for a in annual_model] + [-sum(a.get('wf_mz_pi', 0) for a in annual_model)])
            _cf_computed_line('3. DSRA Top-up',
                [-a.get('wf_dsra_topup', 0) for a in annual_model] + [-sum(a.get('wf_dsra_topup', 0) for a in annual_model)])
            _cf_computed_line('4. One-Time Dividend',
                [-a.get('wf_cc_slug_paid', 0) for a in annual_model] + [-sum(a.get('wf_cc_slug_paid', 0) for a in annual_model)])
            _cf_computed_line('5. Senior Acceleration',
                [-a.get('wf_sr_accel', 0) for a in annual_model] + [-sum(a.get('wf_sr_accel', 0) for a in annual_model)])
            _cf_computed_line('6. Fixed Deposit',
                [-a.get('wf_fd_deposit', 0) for a in annual_model] + [-sum(a.get('wf_fd_deposit', 0) for a in annual_model)])
            _cf_computed_line('Residual Check',
                [a.get('wf_pool', 0) - a.get('wf_sr_pi', 0) - a.get('wf_mz_pi', 0)
                 - a.get('wf_dsra_topup', 0) - a.get('wf_cc_slug_paid', 0)
                 - a.get('wf_sr_accel', 0) - a.get('wf_fd_deposit', 0)
                 for a in annual_model] +
                [sum(a.get('wf_pool', 0) - a.get('wf_sr_pi', 0) - a.get('wf_mz_pi', 0)
                     - a.get('wf_dsra_topup', 0) - a.get('wf_cc_slug_paid', 0)
                     - a.get('wf_sr_accel', 0) - a.get('wf_fd_deposit', 0)
                     for a in annual_model)],
                'sub')

            # SUMMARY
            _cf_spacer()
            _cf_section('SUMMARY')
            _cf_line('Net Cash Flow (Operations)', 'cf_net', row_type='total')
            _cf_line('DSRA Balance', 'dsra_bal', row_type='grand')

            # Build styled HTML table
            _fmt = _eur_fmt
            _h_cf = ['<div style="overflow-x:auto;width:100%;">',
                     '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                     '<thead><tr>']
            _h_cf.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _cf_cols:
                _h_cf.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h_cf.append('</tr></thead><tbody>')

            for label, vals, rtype in _cf_rows:
                if rtype == 'spacer':
                    _h_cf.append(f'<tr><td colspan="{_ncols_cf + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h_cf.append(f'<tr><td colspan="{_ncols_cf + 1}" style="padding:8px 10px 4px;font-weight:700;'
                                 f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                # Style per row type
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                    lbl_style = td_style
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                    lbl_style = td_style
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                    lbl_style = td_style
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                    lbl_style = td_style
                _h_cf.append('<tr>')
                _h_cf.append(f'<td style="text-align:left;padding:4px 10px;{lbl_style}">{label}</td>')
                for v in vals:
                    cell = _fmt.format(v) if v is not None and not isinstance(v, str) else ''
                    _h_cf.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h_cf.append('</tr>')

            _h_cf.append('</tbody></table></div>')
            st.markdown(''.join(_h_cf), unsafe_allow_html=True)

            st.divider()

            # Chart - Inflows vs Outflows side by side, with coverage ratio
            _cf_years = [a['year'] for a in annual_model]

            # Inflows: principal received + interest received (stacked)
            _cf_pi = [a['cf_pi'] for a in annual_model]
            _cf_ii_vals = [a['cf_ii'] for a in annual_model]
            _cf_total_in = [a['cf_pi'] + a['cf_ii'] for a in annual_model]

            # Outflows: principal paid + interest paid (stacked, shown positive)
            _cf_po = [a['cf_po'] for a in annual_model]
            _cf_ie_vals = [a['cf_ie'] for a in annual_model]
            _cf_total_out = [a['cf_po'] + a['cf_ie'] for a in annual_model]

            fig_cf = go.Figure()

            # Inflow bars (stacked)
            fig_cf.add_trace(go.Bar(
                x=_cf_years, y=_cf_pi, name='Principal Received',
                marker_color='#2563EB', offsetgroup='inflow', legendgroup='inflow'
            ))
            fig_cf.add_trace(go.Bar(
                x=_cf_years, y=_cf_ii_vals, name='Interest Received',
                marker_color='#16A34A', offsetgroup='inflow', legendgroup='inflow'
            ))

            # Outflow bars (stacked, positive, next to inflows)
            fig_cf.add_trace(go.Bar(
                x=_cf_years, y=_cf_po, name='Principal Paid',
                marker_color='#DC2626', offsetgroup='outflow', legendgroup='outflow'
            ))
            fig_cf.add_trace(go.Bar(
                x=_cf_years, y=_cf_ie_vals, name='Interest Paid',
                marker_color='#F97316', offsetgroup='outflow', legendgroup='outflow'
            ))

            # DSRA balance line
            fig_cf.add_trace(go.Scatter(
                x=_cf_years, y=[a['dsra_bal'] for a in annual_model],
                name='DSRA Balance', mode='lines+markers',
                line=dict(color='#7C3AED', width=3)
            ))

            # Coverage ratio annotations
            for _ci, _cyr in enumerate(_cf_years):
                if _cf_total_out[_ci] > 1000:
                    _cov = _cf_total_in[_ci] / _cf_total_out[_ci]
                    fig_cf.add_annotation(
                        x=_cyr, y=max(_cf_total_in[_ci], _cf_total_out[_ci]),
                        text=f"<b>{_cov:.2f}x</b>", showarrow=False,
                        yshift=20, font=dict(size=11, color='#1E3A5F')
                    )
                elif _cf_total_out[_ci] <= 1000 and _cf_total_in[_ci] > 0:
                    fig_cf.add_annotation(
                        x=_cyr, y=_cf_total_in[_ci],
                        text="<b>Debt Free</b>", showarrow=False,
                        yshift=20, font=dict(size=10, color='#16A34A')
                    )

            fig_cf.update_layout(
                title='Cash Flow - Inflows vs Outflows (Cash Basis)',
                xaxis_title='Year', yaxis_title='EUR',
                barmode='stack', xaxis=dict(dtick=1),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
            )
            st.plotly_chart(fig_cf, use_container_width=True)
            st.caption("*Note: Principal received > paid because IC loans have higher IDC (0.5% margin). The difference is SCLCA's capitalized margin.*")

            # ── AUDIT: SCLCA Cash Flow ──
            _sclca_cf_checks = []
            for _a in annual_model:
                _y = _a['year']
                # Drawdowns net = 0 (pass-through)
                _sclca_cf_checks.append({
                    "name": f"Y{_y}: Draw net = 0",
                    "expected": 0.0,
                    "actual": _a['cf_draw_in'] - _a['cf_draw_out'],
                })
                # Prepayments net = 0 (pass-through)
                _sclca_cf_checks.append({
                    "name": f"Y{_y}: Prepay net = 0",
                    "expected": 0.0,
                    "actual": _a['cf_prepay_in'] - _a['cf_prepay_out'],
                })
            # DSRA Y10 = sum of cf_net + compounding
            _sclca_cf_checks.append({
                "name": "DSRA Y10 = accumulated surplus",
                "expected": annual_model[-1]['dsra_bal'],
                "actual": annual_model[-1]['dsra_bal'],
            })
            run_page_audit(_sclca_cf_checks, "SCLCA — Cash Flow")

            # Waterfall cascade breakdown expander (v3.1 — 6-step)
            with st.expander("Waterfall Cascade Breakdown"):
                _wf_cf_data = {
                    'Entity Pool': [_eur_fmt.format(w['pool_total']) for w in _waterfall],
                    'IC Overdraft': [_eur_fmt.format(-w['ic_overdraft_drawn'] + w['ic_overdraft_repaid']) for w in _waterfall],
                    '1. Senior P+I (pass-through)': [_eur_fmt.format(-w.get('wf_sr_pi', 0)) for w in _waterfall],
                    '2. Mezz P+I + Accel (pass-through)': [_eur_fmt.format(-w.get('wf_mz_pi', 0)) for w in _waterfall],
                    '3. DSRA Top-up': [_eur_fmt.format(-w.get('wf_dsra_topup', 0)) for w in _waterfall],
                    '4. One-Time Dividend': [_eur_fmt.format(-w.get('wf_cc_slug_paid', 0)) for w in _waterfall],
                    '5. Senior Acceleration': [_eur_fmt.format(-w.get('wf_sr_accel', 0)) for w in _waterfall],
                    '6. Fixed Deposit': [_eur_fmt.format(-w.get('wf_fd_deposit', 0)) for w in _waterfall],
                }
                _wf_cf_cols = [f"Y{w['year']}" for w in _waterfall]
                st.dataframe(pd.DataFrame(_wf_cf_data, index=_wf_cf_cols).T, use_container_width=True)

    # --- WATERFALL TAB ---
    if "Debt Sculpting" in _tab_map:
        with _tab_map["Debt Sculpting"]:
            st.header("Cash Waterfall")
            st.caption("Holding company 6-step character-preserving cascade: Senior and Mezz pass-throughs, then DSRA, Dividend, Senior Accel, and Fixed Deposit")

            # --- Financing Scenario (split-screen NWL + LanRED) ---
            _wf_cfg_ui = load_config("waterfall")
            _nwl_swap_cfg = _wf_cfg_ui.get("nwl_swap", {})

            # Shadow key sync: _wf_nwl_hedge <-> sclca_nwl_hedge
            def _sync_nwl_hedge_from_wf():
                st.session_state["sclca_nwl_hedge"] = st.session_state.get("_wf_nwl_hedge", "CC DSRA \u2192 FEC")

            _nwl_hedge_primary = st.session_state.get("sclca_nwl_hedge", "CC DSRA \u2192 FEC")
            if "_wf_nwl_hedge" not in st.session_state:
                st.session_state["_wf_nwl_hedge"] = _nwl_hedge_primary
            if st.session_state.get("_wf_nwl_hedge") != _nwl_hedge_primary:
                st.session_state["_wf_nwl_hedge"] = _nwl_hedge_primary

            # Shadow key sync: _wf_lanred_scenario <-> lanred_scenario
            def _sync_lanred_from_wf():
                _val = st.session_state.get("_wf_lanred_scenario", "Greenfield")
                st.session_state["lanred_scenario"] = _val
                if _val == "Brownfield+":
                    st.session_state["lanred_eca_atradius"] = False
                    st.session_state["lanred_eca_exporter"] = False
                else:
                    st.session_state["lanred_eca_atradius"] = True
                    st.session_state["lanred_eca_exporter"] = True

            _lr_primary = st.session_state.get("lanred_scenario", "Greenfield")
            if "_wf_lanred_scenario" not in st.session_state:
                st.session_state["_wf_lanred_scenario"] = _lr_primary
            if st.session_state.get("_wf_lanred_scenario") != _lr_primary:
                st.session_state["_wf_lanred_scenario"] = _lr_primary

            with st.container(border=True):
                st.markdown("### Financing Scenarios")
                # CSS to force equal-height columns
                st.markdown("""<style>
                    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div {
                        height: 100%;
                    }
                    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div > div[data-testid="stVerticalBlockBorderWrapper"] {
                        height: 100%;
                    }
                </style>""", unsafe_allow_html=True)
                _sw_c1, _sw_c2 = st.columns(2)

                # ── NWL Column (left) ──
                _cmp = _swap_comparison
                with _sw_c1:
                    with st.container(border=True):
                        _nwl_logo_wf = LOGO_DIR / ENTITY_LOGOS.get("nwl", "")
                        if _nwl_logo_wf.exists():
                            st.image(str(_nwl_logo_wf), width=60)
                        st.markdown("**NWL Hedging Strategy**")
                        st.radio(
                            "Hedging mechanism",
                            ["CC DSRA \u2192 FEC", "Cross-Currency Swap"],
                            key="_wf_nwl_hedge",
                            label_visibility="collapsed",
                            on_change=_sync_nwl_hedge_from_wf,
                        )
                        st.markdown("---")
                        if not nwl_swap_enabled:
                            st.markdown(
                                "**CC DSRA \u2192 FEC**: Creation Capital injects \u20ac2.3M at M24, which "
                                "purchases a Forward Exchange Contract to hedge IIC payments M24\u2013M30. "
                                "Cost: **20%** effective (14.75% CC rate + 5.25% dividend accrual)."
                            )
                        else:
                            _zar_start = _swap_sched['start_month'] if _swap_sched else 36
                            _zar_end = _zar_start + (_swap_sched['tenor'] - 1) * 6 if _swap_sched else 102
                            st.markdown(
                                f"**Cross-Currency Swap**: NWL enters a EUR\u2192ZAR swap. The EUR leg "
                                f"(financial asset) = \u20ac{nwl_swap_amount:,.0f}, identical to IIC "
                                f"repayments at M24 + M30. The ZAR leg (liability) runs "
                                f"M{_zar_start}\u2013M{_zar_end} at **11.75%**, matching the IIC facility "
                                f"tenure. Interest rate below Mezz; FX cost below FEC."
                            )
                        # NWL Hedging Cost Comparison
                        st.markdown("---")
                        st.caption("Cost Comparison")
                        _zar_s = _swap_sched['start_month'] if _swap_sched else 36
                        _zar_e = _zar_s + (_swap_sched['tenor'] - 1) * 6 if _swap_sched else 102
                        _cmp_data = {
                            'Metric': ['Base Rate', 'Dividend Premium', 'Effective Rate',
                                       'EUR Amount', 'EUR Covers', 'ZAR Duration', '10yr NPV Cost'],
                            'DSRA \u2192 FEC': [
                                f"{_cmp['effective_rate_a'] - 0.0525:.2%}",
                                f"+{0.0525:.2%}",
                                f"{_cmp['effective_rate_a']:.2%}",
                                f"\u20ac{_cmp['dsra_amount']:,.0f}",
                                "M24\u2013M30",
                                "M24 \u2192 CC payoff",
                                f"\u20ac{_cmp['npv_cost_a']:,.0f}",
                            ],
                            'Swap': [
                                f"{_cmp['effective_rate_b']:.2%}",
                                "\u2014",
                                f"{_cmp['effective_rate_b']:.2%}",
                                f"\u20ac{_cmp['swap_amount']:,.0f}",
                                "M24 + M30",
                                f"M{_zar_s}\u2013M{_zar_e}",
                                f"\u20ac{_cmp['npv_cost_b']:,.0f}",
                            ],
                        }
                        st.dataframe(pd.DataFrame(_cmp_data).set_index('Metric'), use_container_width=True)
                        if _cmp['savings'] > 0:
                            st.caption(f"Swap saves \u20ac{_cmp['savings']:,.0f} in NPV terms")
                        else:
                            st.caption(f"DSRA cheaper by \u20ac{abs(_cmp['savings']):,.0f} in NPV terms")

                # ── LanRED Column (right) ──
                with _sw_c2:
                    with st.container(border=True):
                        _lr_logo_wf = LOGO_DIR / ENTITY_LOGOS.get("lanred", "")
                        if _lr_logo_wf.exists():
                            st.image(str(_lr_logo_wf), width=60)
                        st.markdown("**LanRED Underwriting Scenario**")
                        st.radio(
                            "Underwriting scenario",
                            ["Greenfield", "Brownfield+"],
                            key="_wf_lanred_scenario",
                            label_visibility="collapsed",
                            on_change=_sync_lanred_from_wf,
                        )
                        st.markdown("---")
                        _lr_is_gf = st.session_state.get("_wf_lanred_scenario", "Greenfield") == "Greenfield"
                        if _lr_is_gf:
                            st.markdown(
                                "**Greenfield**: Greenfield assets require a longer runway. LanRED may "
                                "require overdraft facilities in early years."
                            )
                        else:
                            st.markdown(
                                "**Brownfield+**: Brownfield assets start generating cash from Year 1, and qualify "
                                "for a EUR-ZAR swap in which the EUR leg follows the cadence of the IIC loan at "
                                "holding level, while the ZAR leg is extended from 7 to 14 years with the same "
                                "24-month moratorium."
                            )
                        # LanRED Scenario Effects Comparison
                        st.markdown("---")
                        st.caption("Scenario Effects")
                        _lr_effects = {
                            'Parameter': ['Revenue Start', 'Early-Year Cash',
                                          'FX Strategy', 'ZAR Leg Tenor',
                                          'Overdraft Needed', 'Breakeven'],
                            'Greenfield': [
                                'M18 (post-construction)', 'May require overdraft',
                                'DSRA + FEC (M24-M36)', 'N/A',
                                'Yes (early years)', '~Y3',
                            ],
                            'Brownfield+': [
                                'Day 1 (PPA revenue)', 'Cash-positive from Y1',
                                'EUR-ZAR cross-currency swap', '14 years (24-mo moratorium)',
                                'No', '~Y2',
                            ],
                        }
                        st.dataframe(pd.DataFrame(_lr_effects).set_index('Parameter'), use_container_width=True)

            st.divider()

            # Section 2+: Entity-Narrative Waterfall (NWL -> LanRED -> Holding -> TWX)

            _wf_years = [f"Y{w['year']}" for w in _waterfall]

            # ============================================================
            # Helper: render entity waterfall section (reusable)
            # ============================================================
            def _render_entity_waterfall_section(ek_key, ek_label, ek_logo_key, show_swap=False, show_od=False):
                """Render a single entity's waterfall cascade section."""
                _ek_logo = LOGO_DIR / ENTITY_LOGOS.get(ek_logo_key, "")
                if _ek_logo.exists():
                    _logo_col, _title_col = st.columns([1, 8])
                    with _logo_col:
                        st.image(str(_ek_logo), width=60)
                    with _title_col:
                        st.subheader(f"{ek_label} Entity Cascade")
                else:
                    st.subheader(f"{ek_label} Entity Cascade")

                # Cascade flow diagram (Graphviz)
                _render_entity_cascade_diagram(
                    ek_label,
                    show_swap=show_swap,
                    show_od_lend=(ek_key == 'nwl'),
                    show_od_repay=show_od,
                )

                # Summary
                st.markdown(f"""
Cash flows upstream via **2 pipes only** (Senior IC and Mezz IC). After contractual debt service,
surplus is allocated at {ek_label} level: Ops Reserve -> OpCo DSRA ->
{'LanRED overdraft lending -> ' if ek_key == 'nwl' else ''}Mezz IC acceleration (15.25%)
{'-> ZAR Rand Leg (11.75%) ' if show_swap else ''}{'-> OD repayment (10%) ' if show_od else ''}-> Senior IC acceleration (5.20%) -> Entity FD.
""")

                # Cascade table rows
                _ent_rows = {}
                _has_prepay = any(w.get(f'{ek_key}_prepay', 0) > 0 for w in _waterfall)
                if _has_prepay:
                    _ent_rows['Grant Prepayment'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_prepay', 0))
                                                      if w.get(f'{ek_key}_prepay', 0) > 0 else '\u2014'
                                                      for yr, w in zip(_wf_years, _waterfall)}
                for _row_label, _row_key in [
                    ('IC Senior P+I', 'sr_pi'), ('IC Mezz P+I', 'mz_pi'),
                    ('Ops Reserve Fill', 'ops_reserve_fill'), ('OpCo DSRA Fill', 'opco_dsra_fill'),
                ]:
                    _ent_rows[_row_label] = {yr: _eur_fmt.format(w.get(f'{ek_key}_{_row_key}', 0))
                                              if w.get(f'{ek_key}_{_row_key}', 0) > 0 else '\u2014'
                                              for yr, w in zip(_wf_years, _waterfall)}
                if ek_key == 'nwl':
                    if any(w.get(f'{ek_key}_od_lent', 0) > 0 for w in _waterfall):
                        _ent_rows['OD Lent to LanRED'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_od_lent', 0))
                                                           if w.get(f'{ek_key}_od_lent', 0) > 0 else '\u2014'
                                                           for yr, w in zip(_wf_years, _waterfall)}
                if ek_key == 'lanred':
                    if any(w.get(f'{ek_key}_od_received', 0) > 0 for w in _waterfall):
                        _ent_rows['OD Received'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_od_received', 0))
                                                     if w.get(f'{ek_key}_od_received', 0) > 0 else '\u2014'
                                                     for yr, w in zip(_wf_years, _waterfall)}
                    if any(w.get(f'{ek_key}_od_repaid', 0) > 0 for w in _waterfall):
                        _ent_rows['OD Repaid'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_od_repaid', 0))
                                                   if w.get(f'{ek_key}_od_repaid', 0) > 0 else '\u2014'
                                                   for yr, w in zip(_wf_years, _waterfall)}
                for _row_label, _row_key in [
                    ('Mezz IC Acceleration', 'mz_accel_entity'),
                    ('Sr IC Acceleration', 'sr_accel_entity'),
                ]:
                    _ent_rows[_row_label] = {}
                    for yr, w in zip(_wf_years, _waterfall):
                        if w.get(f'{ek_key}_ic_repaid', False):
                            _ent_rows[_row_label][yr] = '\u2014'
                        else:
                            v = w.get(f'{ek_key}_{_row_key}', 0)
                            _ent_rows[_row_label][yr] = _eur_fmt.format(v) if v > 0 else '\u2014'
                if show_swap:
                    _ent_rows['ZAR Rand Leg'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_zar_leg_payment', 0))
                                                  if w.get(f'{ek_key}_zar_leg_payment', 0) > 0 else '\u2014'
                                                  for yr, w in zip(_wf_years, _waterfall)}
                _ent_rows['Entity FD Fill'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_entity_fd_fill', 0))
                                                if w.get(f'{ek_key}_entity_fd_fill', 0) > 0 else '\u2014'
                                                for yr, w in zip(_wf_years, _waterfall)}

                # Balance rows
                _bal_rows = {}
                for _row_label, _row_key in [
                    ('Ops Reserve Bal', 'ops_reserve_bal'), ('OpCo DSRA Bal', 'opco_dsra_bal'),
                    ('Mezz IC Bal', 'mz_ic_bal'), ('Senior IC Bal', 'sr_ic_bal'),
                    ('Entity FD Bal', 'entity_fd_bal'),
                ]:
                    _bal_rows[_row_label] = {yr: _eur_fmt.format(w.get(f'{ek_key}_{_row_key}', 0))
                                              for yr, w in zip(_wf_years, _waterfall)}
                if ek_key in ('nwl', 'lanred'):
                    _bal_rows['OD Bal'] = {yr: _eur_fmt.format(w.get(f'{ek_key}_od_bal', 0))
                                            for yr, w in zip(_wf_years, _waterfall)}

                with st.expander("Full cascade detail", expanded=False):
                    st.dataframe(pd.DataFrame(_ent_rows).T, use_container_width=True)
                    st.markdown("**Balances**")
                    st.dataframe(pd.DataFrame(_bal_rows).T, use_container_width=True)

                # Stacked bar chart
                fig_ent = go.Figure()
                _cascade_colors = [
                    ('IC Senior P+I', 'sr_pi', '#1E3A5F'),
                    ('IC Mezz P+I', 'mz_pi', '#7C3AED'),
                    ('Ops Reserve', 'ops_reserve_fill', '#0D9488'),
                    ('OpCo DSRA', 'opco_dsra_fill', '#2563EB'),
                    ('Mezz IC Accel', 'mz_accel_entity', '#A855F7'),
                    ('Sr IC Accel', 'sr_accel_entity', '#3B82F6'),
                    ('Entity FD', 'entity_fd_fill', '#059669'),
                ]
                if show_swap:
                    _cascade_colors.insert(5, ('ZAR Rand Leg', 'zar_leg_payment', '#F59E0B'))
                for _lbl, _fld, _clr in _cascade_colors:
                    _vs = [w.get(f'{ek_key}_{_fld}', 0) for w in _waterfall]
                    if any(v > 0 for v in _vs):
                        fig_ent.add_trace(go.Bar(x=_wf_years, y=_vs, name=_lbl, marker_color=_clr))
                _deficits = [w.get(f'{ek_key}_deficit', 0) for w in _waterfall]
                if any(d < 0 for d in _deficits):
                    fig_ent.add_trace(go.Bar(x=_wf_years, y=_deficits, name='Deficit', marker_color='#EF4444'))
                fig_ent.update_layout(
                    barmode='relative', title=f'{ek_label} Cascade Allocation',
                    yaxis_title='EUR', height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_ent, use_container_width=True)

            # ============================================================
            # Section 2: NWL Entity
            # ============================================================
            _render_entity_waterfall_section(
                'nwl', 'NWL', 'nwl',
                show_swap=nwl_swap_enabled and _swap_sched is not None)

            # Conditional: NWL Cross-Currency Swap details
            if nwl_swap_enabled and _swap_sched:
                with st.expander("NWL Cross-Currency Swap Details", expanded=False):
                    _zar_end_m = _swap_sched['start_month'] + (_swap_sched['tenor'] - 1) * 6
                    st.markdown(f"**EUR Leg (asset):** \u20ac{_swap_sched['eur_amount']:,.0f} \u2014 covers IIC Senior P+I at M24 + M30.")
                    st.markdown(f"**ZAR Leg (liability):** R{_swap_sched['zar_amount']:,.0f} at {_swap_sched['zar_rate']*100:.2f}% p.a. \u2014 {_swap_sched['tenor']} semi-annual instalments M{_swap_sched['start_month']}\u2013M{_zar_end_m}.")
                    _swap_lc, _swap_rc = st.columns(2)
                    with _swap_lc:
                        st.markdown("**EUR Asset Leg**")
                        _eur_asset_rows = [
                            {'Payment': 'M24 (P1)', 'Amount': f"\u20ac{_nwl_swap_eur_m24:,.0f}"},
                            {'Payment': 'M30 (P2)', 'Amount': f"\u20ac{_nwl_swap_eur_m30:,.0f}"},
                            {'Payment': '**Total**', 'Amount': f"\u20ac{_swap_sched['eur_amount']:,.0f}"},
                        ]
                        st.dataframe(pd.DataFrame(_eur_asset_rows).set_index('Payment'), use_container_width=True)
                    with _swap_rc:
                        st.markdown("**ZAR Liability Leg**")
                        _swap_df = pd.DataFrame(_swap_sched['schedule'])
                        _swap_df['month'] = _swap_df['month'].astype(int)
                        for _col_name in ['opening', 'interest', 'principal', 'payment', 'closing']:
                            _swap_df[_col_name] = _swap_df[_col_name].map(lambda x: f"R{x:,.0f}")
                        _swap_df = _swap_df.rename(columns={
                            'period': 'Period', 'month': 'Month',
                            'opening': 'Opening (ZAR)', 'interest': 'Interest (ZAR)',
                            'principal': 'Principal (ZAR)', 'payment': 'Payment (ZAR)',
                            'closing': 'Closing (ZAR)',
                        })
                        st.dataframe(_swap_df.set_index('Period'), use_container_width=True)

            if not nwl_swap_enabled:
                with st.expander("DSRA-Injection (CC \u2192 FEC)", expanded=False):
                    st.markdown("**DSRA-Injection** at M24: Creation Capital injects 2x Senior P+I into SCLCA Holding. "
                                "Holding passes cash to NWL; NWL uses it to pay IC Senior P+I at M24 and M30. "
                                "NWL's Mezz IC balance increases by the injection amount. "
                                "After M30, normal surplus flow resumes \u2014 Mezz IC acceleration pays this down first.")

            st.divider()

            # ============================================================
            # Section 3: LanRED Entity
            # ============================================================
            _render_entity_waterfall_section('lanred', 'LanRED', 'lanred', show_od=True)

            if lanred_swap_enabled:
                with st.expander("LanRED Brownfield+ Swap Details", expanded=False):
                    _lr_swap_cfg = load_config("waterfall").get("lanred_swap", {})
                    st.markdown(f"**Brownfield+ Swap**: Notional = full LanRED Senior IC value. "
                                f"EUR leg 1:1 = IIC schedule (7yr). "
                                f"ZAR leg extended to 14yr ({_lr_swap_cfg.get('extended_repayments_sr', 28)} semi-annual). "
                                f"Effect: halves per-period DS, frees surplus, accelerates Mezz IC repayment.")

            _lr_od_active = any(w.get('lanred_od_received', 0) > 0 or w.get('lanred_od_bal', 0) > 0 for w in _waterfall)
            if _lr_od_active:
                with st.expander("LanRED Overdraft Tracking", expanded=False):
                    st.markdown("NWL lends surplus to LanRED via inter-entity overdraft at 10% p.a.")
                    _lr_od_table = {
                        'OD Received': [_eur_fmt.format(w.get('lanred_od_received', 0)) for w in _waterfall],
                        'OD Repaid': [_eur_fmt.format(w.get('lanred_od_repaid', 0)) for w in _waterfall],
                        'OD Balance': [_eur_fmt.format(w.get('lanred_od_bal', 0)) for w in _waterfall],
                    }
                    st.dataframe(pd.DataFrame(_lr_od_table, index=_wf_years).T, use_container_width=True)

            st.divider()

            # ============================================================
            # Section 4: SCLCA Holding (Pass-Through)
            # ============================================================
            st.subheader("SCLCA Holding (Pass-Through)")

            _render_holding_passthrough_diagram()

            st.markdown("**Aggregate Upstream (2 Pipes)**")
            _agg_data = {
                'Senior Character': [_eur_fmt.format(w['wf_sr_pi']) for w in _waterfall],
                'Mezz Character': [_eur_fmt.format(w['wf_mz_pi']) for w in _waterfall],
                'Pool Total': [_eur_fmt.format(w['pool_total']) for w in _waterfall],
            }
            st.dataframe(pd.DataFrame(_agg_data, index=_wf_years).T, use_container_width=True)

            st.markdown("**6-Step Holding Cascade**")
            st.caption("Steps 1-2 are character-preserving pass-throughs. Steps 3-6 are discretionary.")
            _cascade_items = [
                ("1. Senior P+I (pass-through)", 'wf_sr_pi', '#1E3A5F'),
                ("2. Mezz P+I + Accel (pass-through)", 'wf_mz_pi', '#7C3AED'),
                ("3. DSRA Top-up", 'wf_dsra_topup', '#2563EB'),
                ("4. One-Time Dividend", 'wf_cc_slug_paid', '#EA580C'),
                ("5. Senior Acceleration", 'wf_sr_accel', '#0D9488'),
                ("6. Fixed Deposit", 'wf_fd_deposit', '#059669'),
            ]
            _casc_data = {}
            for label, key, _ in _cascade_items:
                _casc_data[label] = {yr: _eur_fmt.format(w.get(key, 0)) for yr, w in zip(_wf_years, _waterfall)}
            _casc_data['Pool Total'] = {yr: _eur_fmt.format(w['pool_total']) for yr, w in zip(_wf_years, _waterfall)}
            st.dataframe(pd.DataFrame(_casc_data).T, use_container_width=True)

            _discretionary_items = _cascade_items[2:]
            fig_casc = go.Figure()
            for label, key, color in _discretionary_items:
                vals = [w.get(key, 0) for w in _waterfall]
                if any(v > 0 for v in vals):
                    fig_casc.add_trace(go.Bar(x=_wf_years, y=vals, name=label, marker_color=color))
            fig_casc.update_layout(
                barmode='stack', title='Discretionary Cascade (Steps 3-6)',
                yaxis_title='EUR', height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_casc, use_container_width=True)

            st.caption("**One-Time Dividend** accrues at 5.25% p.a. on CC opening balance. "
                        "Settled as lump sum once CC principal reaches zero.")

            st.divider()

            # CC Balance & Dividend & IRR
            st.subheader("CC Balance & One-Time Dividend")
            st.markdown("**Creation Capital** is repaid via Mezz-character cash (step 2): "
                         "scheduled Mezz P+I + entity-level Mezz IC acceleration. "
                         "When the CC balance reaches zero, a one-time dividend (5.25% p.a. accrual) is paid.")

            _cc_close = [w['cc_closing'] for w in _waterfall]
            _cc_slug_cum = [w['cc_slug_cumulative'] for w in _waterfall]
            _wf_cc_payoff = next((i + 1 for i, v in enumerate(_cc_close) if v <= 0), None)

            fig_cc = go.Figure()
            fig_cc.add_trace(go.Scatter(x=_wf_years, y=_cc_close, name='CC Balance',
                mode='lines+markers', line=dict(color='#DB2777', width=3)))
            fig_cc.add_trace(go.Scatter(x=_wf_years, y=_cc_slug_cum, name='Dividend (cumulative)',
                mode='lines+markers', line=dict(color='#EA580C', width=2, dash='dash'), yaxis='y2'))
            fig_cc.update_layout(
                title='CC Balance Trajectory & Dividend Accrual',
                yaxis=dict(title='CC Balance (EUR)', side='left'),
                yaxis2=dict(title='Dividend Cumulative (EUR)', side='right', overlaying='y'),
                height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            if _wf_cc_payoff:
                fig_cc.add_annotation(x=f"Y{_wf_cc_payoff}", y=0, text=f"CC paid off Y{_wf_cc_payoff}",
                    showarrow=True, arrowhead=2, ax=0, ay=-40, font=dict(size=12, color='#16A34A'))
            st.plotly_chart(fig_cc, use_container_width=True)

            _cc_table = {
                'CC Opening': [_eur_fmt.format(w['cc_opening']) for w in _waterfall],
                'Mezz P+I + Entity Accel': [_eur_fmt.format(w.get('wf_mz_pi', 0)) for w in _waterfall],
                'Dividend Accrual': [_eur_fmt.format(w['cc_slug_accrual']) for w in _waterfall],
                'Dividend Cumulative': [_eur_fmt.format(w['cc_slug_cumulative']) for w in _waterfall],
                'CC Closing': [_eur_fmt.format(w['cc_closing']) for w in _waterfall],
            }
            st.dataframe(pd.DataFrame(_cc_table, index=_wf_years).T, use_container_width=True)

            _final_irr = _waterfall[-1].get('cc_irr_achieved')
            if _final_irr is not None:
                _irr_pct = _final_irr * 100
                if abs(_irr_pct - 20.0) < 1.0:
                    st.success(f"CC Achieved IRR: {_irr_pct:.1f}%")
                else:
                    st.info(f"CC IRR at Y10: {_irr_pct:.1f}% (target: 20%)")
            else:
                st.info("CC IRR: Insufficient data for calculation")

            st.markdown("**Holding FD Balance**")
            _hfd_data = {'Holding FD': [_eur_fmt.format(w.get('wf_fd_bal', 0)) for w in _waterfall]}
            st.dataframe(pd.DataFrame(_hfd_data, index=_wf_years).T, use_container_width=True)

            st.divider()

            # ============================================================
            # Section 5: TWX Entity
            # ============================================================
            _render_entity_waterfall_section('timberworx', 'Timberworx', 'timberworx')

            st.divider()

            # ============================================================
            # Section 6: Pre-Revenue Hedging (WIP stub)
            # ============================================================
            st.subheader("Pre-Revenue Hedging")
            st.info(
                "**Work in Progress** — We are leaning towards **currency options** (rather than FECs) "
                "for hedging the DTIC subsidy and GEPF bulk services pre-payment. Currency options are "
                "better suited because timing of these inflows is uncertain, and a missed FEC delivery "
                "date would require an additional guarantee. Options provide the right without the "
                "obligation. Note: if selected, option premiums will impact the drawdown requirement "
                "(upfront cost)."
            )

    # --- BALANCE SHEET TAB ---
    if "Balance Sheet" in _tab_map:
        with _tab_map["Balance Sheet"]:
            st.header("Balance Sheet")
            st.caption("Standard format: Assets = Liabilities + Equity")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Year 1 Equity", f"€{annual_model[0]['bs_e']:,.0f}")
            with col2:
                peak_e = max(a['bs_e'] for a in annual_model)
                st.metric("Peak Equity", f"€{peak_e:,.0f}")
            with col3:
                st.metric("Year 10 Equity", f"€{annual_model[-1]['bs_e']:,.0f}")

            st.divider()

            # Build transposed Balance Sheet (rows = line items, columns = years)
            _bs_cols = [f"Y{a['year']}" for a in annual_model]
            _ncols_bs = len(_bs_cols)
            _bs_rows = []  # list of (label, values, row_type)

            def _bs_line(label, key, sign=1.0, row_type='line'):
                vals = [sign * a.get(key, 0.0) for a in annual_model]
                _bs_rows.append((label, vals, row_type))

            def _bs_computed_line(label, values_list, row_type='line'):
                _bs_rows.append((label, values_list, row_type))

            def _bs_section(label):
                _bs_rows.append((label, [None] * _ncols_bs, 'section'))

            def _bs_spacer():
                _bs_rows.append(('', [None] * _ncols_bs, 'spacer'))

            # Compute entity percentages
            nwl_sr_pct = structure['uses']['loans_to_subsidiaries']['nwl']['senior_portion'] / sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
            nwl_mz_pct = structure['uses']['loans_to_subsidiaries']['nwl']['mezz_portion'] / sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
            lanred_sr_pct = structure['uses']['loans_to_subsidiaries']['lanred']['senior_portion'] / sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
            lanred_mz_pct = structure['uses']['loans_to_subsidiaries']['lanred']['mezz_portion'] / sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
            twx_sr_pct = structure['uses']['loans_to_subsidiaries']['timberworx']['senior_portion'] / sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
            twx_mz_pct = structure['uses']['loans_to_subsidiaries']['timberworx']['mezz_portion'] / sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())

            # ASSETS
            _bs_section('ASSETS')
            _bs_computed_line('IC Loan - NWL (Senior)', [a['bs_isr'] * nwl_sr_pct for a in annual_model])
            _bs_computed_line('IC Loan - NWL (Mezz)', [a['bs_imz'] * nwl_mz_pct for a in annual_model])
            _bs_computed_line('IC Loan - LanRED (Senior)', [a['bs_isr'] * lanred_sr_pct for a in annual_model])
            _bs_computed_line('IC Loan - LanRED (Mezz)', [a['bs_imz'] * lanred_mz_pct for a in annual_model])
            _bs_computed_line('IC Loan - Timberworx (Senior)', [a['bs_isr'] * twx_sr_pct for a in annual_model])
            _bs_computed_line('IC Loan - Timberworx (Mezz)', [a['bs_imz'] * twx_mz_pct for a in annual_model])
            _bs_line('Total IC Loans', 'bs_ic', row_type='sub')
            # IC Overdraft receivable (waterfall)
            _od_active_bs = any(w['ic_overdraft_bal'] > 0 for w in _waterfall)
            if _od_active_bs:
                _bs_computed_line('IC Overdraft Receivable', [_waterfall[yi]['ic_overdraft_bal'] for yi in range(10)])
            _bs_line('Equity - NWL (93%)', 'bs_eq_nwl')
            _bs_line('Equity - LanRED (100%)', 'bs_eq_lanred')
            _bs_line('Equity - Timberworx (5%)', 'bs_eq_twx')
            _bs_line('Financial Assets', 'bs_financial', row_type='total')

            _bs_spacer()
            _bs_line('DSRA Fixed Deposit', 'bs_dsra')
            _bs_computed_line('Holding DSRA (Sr P+I)', [a.get('wf_dsra_bal', 0) for a in annual_model])
            _bs_computed_line('Holding Fixed Deposit', [a.get('wf_fd_bal', 0) for a in annual_model])
            _bs_line('Cash & Equivalents', 'bs_cash', row_type='total')
            _bs_line('Total Assets', 'bs_a', row_type='grand')

            # LIABILITIES
            _bs_spacer()
            _bs_section('LIABILITIES')
            _bs_line('Senior Debt (Invest Intl)', 'bs_sr')
            _bs_line('Mezzanine (Creation Capital)', 'bs_mz')
            _bs_computed_line('  Mezz (Sculpted)', [a['wf_cc_closing'] for a in annual_model])
            _bs_line('Total Debt', 'bs_l', row_type='total')
            # One-Time Dividend liability (waterfall — accruing until settled)
            _slug_vals = [_waterfall[yi]['cc_slug_cumulative'] if not _waterfall[yi]['cc_slug_settled'] else 0.0 for yi in range(10)]
            if any(v > 0 for v in _slug_vals):
                _bs_computed_line('One-Time Dividend Liability', _slug_vals)

            # EQUITY
            _bs_spacer()
            _bs_section('EQUITY')
            _bs_line('Shareholder Equity (€99k)', 'bs_sh_equity')
            _bs_line('Retained Earnings', 'bs_retained')
            _bs_line('Total Equity', 'bs_e', row_type='total')

            # CHECKS
            _bs_spacer()
            _bs_computed_line('Check: A = L + E', [a['bs_a'] - a['bs_l'] - a['bs_e'] for a in annual_model], row_type='sub')
            _bs_computed_line('RE = Cumulative NI', [a.get('bs_gap', 0.0) for a in annual_model], row_type='sub')

            # Show warning if any gap > €1
            _sclca_gaps = [a.get('bs_gap', 0.0) for a in annual_model]
            if any(abs(v) >= 1.0 for v in _sclca_gaps):
                st.warning(f"SCLCA BS Gap: RE ≠ Cumulative NI. Max gap: €{max(abs(v) for v in _sclca_gaps):,.0f}")

            # Build styled HTML table
            _fmt = _eur_fmt
            _h_bs = ['<div style="overflow-x:auto;width:100%;">',
                     '<table style="border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;">',
                     '<thead><tr>']
            _h_bs.append('<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-weight:700;">Item</th>')
            for c in _bs_cols:
                _h_bs.append(f'<th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;font-weight:700;">{c}</th>')
            _h_bs.append('</tr></thead><tbody>')

            for label, vals, rtype in _bs_rows:
                if rtype == 'spacer':
                    _h_bs.append(f'<tr><td colspan="{_ncols_bs + 1}" style="height:10px;border:none;"></td></tr>')
                    continue
                if rtype == 'section':
                    _h_bs.append(f'<tr><td colspan="{_ncols_bs + 1}" style="padding:8px 10px 4px;font-weight:700;'
                                 f'font-size:11px;color:#6B7280;letter-spacing:0.08em;border-bottom:1px solid #E5E7EB;">{label}</td></tr>')
                    continue
                # Style per row type
                if rtype == 'grand':
                    td_style = 'font-weight:700;background:#1E3A5F;color:#fff;border-top:2px solid #333;border-bottom:2px solid #333;'
                    lbl_style = td_style
                elif rtype == 'total':
                    td_style = 'font-weight:600;background:#F1F5F9;border-top:1px solid #CBD5E1;border-bottom:1px solid #CBD5E1;'
                    lbl_style = td_style
                elif rtype == 'sub':
                    td_style = 'font-style:italic;color:#475569;border-bottom:1px dashed #E2E8F0;'
                    lbl_style = td_style
                else:
                    td_style = 'border-bottom:1px solid #F1F5F9;'
                    lbl_style = td_style
                _h_bs.append('<tr>')
                _h_bs.append(f'<td style="text-align:left;padding:4px 10px;{lbl_style}">{label}</td>')
                for v in vals:
                    cell = _fmt.format(v) if v is not None and not isinstance(v, str) else ''
                    _h_bs.append(f'<td style="text-align:right;padding:4px 8px;{td_style}">{cell}</td>')
                _h_bs.append('</tr>')

            _h_bs.append('</tbody></table></div>')
            st.markdown(''.join(_h_bs), unsafe_allow_html=True)

            # --- Balance Sheet Chart: A = D + E ---
            _bs_fin = [a['bs_financial'] for a in annual_model]
            _bs_cash = [a['bs_cash'] for a in annual_model]
            _bs_total_d = [a['bs_l'] for a in annual_model]
            _bs_total_e = [a['bs_e'] for a in annual_model]
            _bs_total_a = [a['bs_a'] for a in annual_model]

            fig_bs = go.Figure()

            # Left bar: Assets = Financial Assets + Cash (stacked)
            fig_bs.add_trace(go.Bar(
                x=_years, y=_bs_fin, name='Financial Assets', marker_color='#2563EB',
                offsetgroup='assets'
            ))
            fig_bs.add_trace(go.Bar(
                x=_years, y=_bs_cash, name='Cash (DSRA)', marker_color='#16A34A',
                offsetgroup='assets'
            ))

            # Right bar: Debt + Equity stacked (D+E = A always)
            fig_bs.add_trace(go.Bar(
                x=_years, y=_bs_total_e, name='Equity', marker_color='#0D9488',
                offsetgroup='d_and_e'
            ))
            fig_bs.add_trace(go.Bar(
                x=_years, y=_bs_total_d, name='Debt', marker_color='#DC2626',
                offsetgroup='d_and_e'
            ))

            # D/E ratio annotations
            for i, yr in enumerate(_years):
                if _bs_total_a[i] > 1000 and _bs_total_e[i] != 0:
                    de_ratio = _bs_total_d[i] / _bs_total_e[i]
                    fig_bs.add_annotation(
                        x=yr, y=_bs_total_a[i],
                        text=f"<b>D/E: {de_ratio:.1f}x</b>", showarrow=False,
                        yshift=20, font=dict(size=11, color='#DC2626' if de_ratio > 5 else '#1E3A5F')
                    )

            fig_bs.update_layout(
                title='Balance Sheet — A = D + E',
                xaxis_title='Year', yaxis_title='EUR',
                barmode='relative', xaxis=dict(dtick=1),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
            )
            st.plotly_chart(fig_bs, use_container_width=True)

            # ── AUDIT: SCLCA Balance Sheet ──
            _sclca_bs_checks = []
            for _a in annual_model:
                _y = _a['year']
                # A = L + E
                _sclca_bs_checks.append({
                    "name": f"Y{_y}: A = L + E",
                    "expected": _a['bs_l'] + _a['bs_e'],
                    "actual": _a['bs_a'],
                })
                # RE = Cumulative NI
                _sclca_bs_checks.append({
                    "name": f"Y{_y}: RE = Cum NI",
                    "expected": _a['bs_retained_check'],
                    "actual": _a['bs_retained'],
                })
                # BS DSRA = CF DSRA
                _sclca_bs_checks.append({
                    "name": f"Y{_y}: BS DSRA = CF DSRA",
                    "expected": _a['dsra_bal'],
                    "actual": _a['bs_dsra'],
                })
            run_page_audit(_sclca_bs_checks, "SCLCA — Balance Sheet")

            # Waterfall BS adjustments expander
            with st.expander("Waterfall Balance Sheet Adjustments"):
                _wf_bs_years = [f"Y{w['year']}" for w in _waterfall]
                _wf_bs_data = {
                    'CC Balance (Sculpted)': [_eur_fmt.format(w['cc_closing']) for w in _waterfall],
                    'Dividend Accruing': [_eur_fmt.format(w['cc_slug_cumulative'] if not w['cc_slug_settled'] else 0) for w in _waterfall],
                    'IC Overdraft': [_eur_fmt.format(w['ic_overdraft_bal']) for w in _waterfall],
                }
                st.dataframe(pd.DataFrame(_wf_bs_data, index=_wf_bs_years).T, use_container_width=True)
                st.caption("CC balance sculpted from waterfall cascade; dividend accrues at 5.25% until CC=0")

            # ══════════════════════════════════════════════
            # INTER-COMPANY RECONCILIATION
            # ══════════════════════════════════════════════
            st.divider()
            st.subheader("Inter-Company Reconciliation")
            st.caption("SCLCA income/receivables vs sum of subsidiary expenses/liabilities")

            # Build all 3 subsidiary models
            _nwl_model = build_sub_annual_model("nwl")
            _lanred_model = build_sub_annual_model("lanred")
            _twx_model = build_sub_annual_model("timberworx")
            _nwl_ann = _nwl_model["annual"]
            _lanred_ann = _lanred_model["annual"]
            _twx_ann = _twx_model["annual"]

            _ic_checks = []
            for yi in range(10):
                _y = yi + 1
                _na = _nwl_ann[yi]
                _la = _lanred_ann[yi]
                _ta = _twx_ann[yi]
                _sa = annual_model[yi]

                # IC Senior interest: SCLCA income = sum(sub IE senior)
                _sub_ie_sr = _na['ie_sr'] + _la['ie_sr'] + _ta['ie_sr']
                _ic_checks.append({
                    "name": f"Y{_y}: IC Sr Interest: SCLCA = Subs",
                    "expected": _sa['ii_sr'],
                    "actual": _sub_ie_sr,
                })
                # IC Mezz interest
                _sub_ie_mz = _na['ie_mz'] + _la['ie_mz'] + _ta['ie_mz']
                _ic_checks.append({
                    "name": f"Y{_y}: IC Mz Interest: SCLCA = Subs",
                    "expected": _sa['ii_mz'],
                    "actual": _sub_ie_mz,
                })
                # IC Senior receivable = sum(sub BS senior debt)
                _sub_bs_sr = _na['bs_sr'] + _la['bs_sr'] + _ta['bs_sr']
                _ic_checks.append({
                    "name": f"Y{_y}: IC Sr Bal: SCLCA = Subs",
                    "expected": _sa['bs_isr'],
                    "actual": _sub_bs_sr,
                })
                # IC Mezz receivable = sum(sub BS mezz debt)
                _sub_bs_mz = _na['bs_mz'] + _la['bs_mz'] + _ta['bs_mz']
                _ic_checks.append({
                    "name": f"Y{_y}: IC Mz Bal: SCLCA = Subs",
                    "expected": _sa['bs_imz'],
                    "actual": _sub_bs_mz,
                })
                # IC principal received = sum(sub principal paid)
                _sub_pr = _na['cf_pr'] + _la['cf_pr'] + _ta['cf_pr']
                _ic_checks.append({
                    "name": f"Y{_y}: IC Principal: SCLCA = Subs",
                    "expected": _sa['cf_repay_in'],
                    "actual": _sub_pr,
                })

            # NWL power_cost = LanRED rev (cross-entity operating IC)
            for yi in range(10):
                _y = yi + 1
                _nwl_pwr = _nwl_ann[yi].get('power_cost', 0)
                _lr_rev = _lanred_ann[yi].get('rev_total', 0)
                if _nwl_pwr > 0 or _lr_rev > 0:
                    _ic_checks.append({
                        "name": f"Y{_y}: NWL power = LanRED rev",
                        "expected": _nwl_pwr,
                        "actual": _lr_rev,
                    })
                # NWL rent = TWX lease rev
                _nwl_rent = _nwl_ann[yi].get('rent_cost', 0)
                _twx_rev = _twx_ann[yi].get('rev_total', 0)
                if _nwl_rent > 0 or _twx_rev > 0:
                    _ic_checks.append({
                        "name": f"Y{_y}: NWL rent = TWX rev",
                        "expected": _nwl_rent,
                        "actual": _twx_rev,
                    })

            run_page_audit(_ic_checks, "SCLCA — IC Reconciliation")

    # --- GRAPHS TAB ---
    if "Graphs" in _tab_map:
        with _tab_map["Graphs"]:
            st.header("Graphs")
            st.caption("Visual summary of SCLCA's 10-year financial projection")

            _g_loans = structure['uses']['loans_to_subsidiaries']
            _g_sr_total = sum(l['senior_portion'] for l in _g_loans.values())
            _g_mz_total = sum(l['mezz_portion'] for l in _g_loans.values())
            _g_nwl_pct = (_g_loans['nwl']['total_loan'] / (_g_sr_total + _g_mz_total))
            _g_lr_pct = (_g_loans['lanred']['total_loan'] / (_g_sr_total + _g_mz_total))
            # _g_twx_pct removed - was unused

            # ---- 1. Debt Paydown Curve ----
            st.subheader("1. Debt Paydown")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=_years, y=[a['bs_sr'] for a in annual_model],
                name='Senior Debt', fill='tozeroy', mode='lines',
                line=dict(width=0.5, color='#DC2626'), fillcolor='rgba(220,38,38,0.4)'
            ))
            fig1.add_trace(go.Scatter(
                x=_years, y=[a['bs_sr'] + a['bs_mz'] for a in annual_model],
                name='+ Mezzanine', fill='tonexty', mode='lines',
                line=dict(width=0.5, color='#F97316'), fillcolor='rgba(249,115,22,0.4)'
            ))
            # DSRA facility removed (netted with FEC — pass-through)
            fig1.update_layout(title='Total Debt Outstanding', xaxis_title='Year', yaxis_title='EUR', xaxis=dict(dtick=1),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
            st.plotly_chart(fig1, use_container_width=True)

            _g_row1 = st.columns(2)

            # ---- 2. DSCR Timeline ----
            with _g_row1[0]:
                st.subheader("2. DSCR")
                _dscr_vals = []
                for a in annual_model:
                    if a['ie'] > 1000:
                        _dscr_vals.append(a['ii'] / a['ie'])
                    else:
                        _dscr_vals.append(None)
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=_years, y=_dscr_vals, name='DSCR', mode='lines+markers',
                    line=dict(color='#2563EB', width=3), marker=dict(size=8)))
                fig2.add_hline(y=1.3, line_dash="dash", line_color="#DC2626", annotation_text="Covenant 1.3x",
                    annotation_position="top left")
                fig2.add_hline(y=1.0, line_dash="dot", line_color="#6B7280", annotation_text="Breakeven",
                    annotation_position="bottom left")
                fig2.update_layout(title='Debt Service Coverage Ratio', xaxis_title='Year', yaxis_title='DSCR (x)',
                    xaxis=dict(dtick=1))
                st.plotly_chart(fig2, use_container_width=True)

            # ---- 3. Net Interest Margin ----
            with _g_row1[1]:
                st.subheader("3. Net Interest Margin")
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(x=_years, y=[a['ii'] for a in annual_model], name='Interest Income',
                    marker_color='#16A34A'))
                fig3.add_trace(go.Bar(x=_years, y=[-a['ie'] for a in annual_model], name='Finance Costs',
                    marker_color='#DC2626'))
                fig3.add_trace(go.Scatter(x=_years, y=[a['ni'] for a in annual_model], name='Net Margin',
                    mode='lines+markers', line=dict(color='#0D9488', width=3)))
                fig3.update_layout(title='Interest Margin (SCLCA spread)', xaxis_title='Year', yaxis_title='EUR',
                    barmode='group', xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig3, use_container_width=True)

            _g_row2 = st.columns(2)

            # ---- 4. Exposure by Subsidiary ----
            with _g_row2[0]:
                st.subheader("4. Exposure by Subsidiary")
                fig4 = go.Figure()
                fig4.add_trace(go.Scatter(
                    x=_years, y=[a['bs_ic'] * _g_nwl_pct for a in annual_model],
                    name='NWL', fill='tozeroy', mode='lines',
                    line=dict(width=0.5, color='#2563EB'), fillcolor='rgba(37,99,235,0.5)'
                ))
                fig4.add_trace(go.Scatter(
                    x=_years, y=[a['bs_ic'] * _g_nwl_pct + a['bs_ic'] * _g_lr_pct for a in annual_model],
                    name='LanRED', fill='tonexty', mode='lines',
                    line=dict(width=0.5, color='#EAB308'), fillcolor='rgba(234,179,8,0.5)'
                ))
                fig4.add_trace(go.Scatter(
                    x=_years, y=[a['bs_ic'] for a in annual_model],
                    name='Timberworx', fill='tonexty', mode='lines',
                    line=dict(width=0.5, color='#8B4513'), fillcolor='rgba(139,69,19,0.4)'
                ))
                fig4.update_layout(title='IC Loan Exposure by Subsidiary', xaxis_title='Year', yaxis_title='EUR',
                    xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig4, use_container_width=True)

            # ---- 5. Cumulative Cash Flow ----
            with _g_row2[1]:
                st.subheader("5. Cumulative Cash Flow")
                _cum_cf = []
                _running = 0.0
                for a in annual_model:
                    _running += a['cf_net']
                    _cum_cf.append(_running)
                fig5 = go.Figure()
                fig5.add_trace(go.Scatter(x=_years, y=_cum_cf, name='Cumulative Net CF',
                    fill='tozeroy', mode='lines+markers',
                    line=dict(color='#0D9488', width=3), fillcolor='rgba(13,148,136,0.2)'))
                fig5.add_trace(go.Scatter(x=_years, y=[a['dsra_bal'] for a in annual_model],
                    name='DSRA Balance', mode='lines+markers',
                    line=dict(color='#7C3AED', width=2, dash='dot')))
                fig5.update_layout(title='Cumulative Cash & DSRA Build-up', xaxis_title='Year', yaxis_title='EUR',
                    xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig5, use_container_width=True)

            _g_row3 = st.columns(2)

            # ---- 6. Debt Maturity Profile ----
            with _g_row3[0]:
                st.subheader("6. Debt Service Profile")
                fig6 = go.Figure()
                fig6.add_trace(go.Bar(x=_years, y=[a['cf_po'] for a in annual_model],
                    name='Principal Paid', marker_color='#DC2626'))
                fig6.add_trace(go.Bar(x=_years, y=[a['cf_ie'] for a in annual_model],
                    name='Interest Paid', marker_color='#F97316'))
                fig6.update_layout(title='Debt Service Payments (P + I)', xaxis_title='Year', yaxis_title='EUR',
                    barmode='stack', xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig6, use_container_width=True)

            # ---- 7. Equity Build-Up ----
            with _g_row3[1]:
                st.subheader("7. Equity Build-Up")
                fig7 = go.Figure()
                fig7.add_trace(go.Bar(x=_years, y=[a['bs_sh_equity'] for a in annual_model],
                    name='Shareholder Equity', marker_color='#0D9488'))
                fig7.add_trace(go.Bar(x=_years, y=[a['bs_retained'] for a in annual_model],
                    name='Retained Earnings', marker_color='rgba(13,148,136,0.4)'))
                # Leverage ratio line (E/A)
                _lev = [a['bs_e'] / a['bs_a'] * 100 if a['bs_a'] > 0 else 0 for a in annual_model]
                fig7.add_trace(go.Scatter(x=_years, y=_lev, name='Equity/Assets %', yaxis='y2',
                    mode='lines+markers', line=dict(color='#1E3A5F', width=2, dash='dot')))
                fig7.update_layout(title='Equity Growth & Leverage', xaxis_title='Year',
                    yaxis=dict(title='EUR'), yaxis2=dict(title='E/A %', overlaying='y', side='right', range=[0, 100]),
                    barmode='stack', xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig7, use_container_width=True)

            _g_row4 = st.columns(2)

            # ---- 8. Income Composition (Donut) ----
            with _g_row4[0]:
                st.subheader("8. Income Composition")
                _total_ii_sr = sum(a['ii_sr'] for a in annual_model)
                _total_ii_mz = sum(a['ii_mz'] for a in annual_model)
                _total_ii_dsra = sum(a['ii_dsra'] for a in annual_model)
                fig8 = go.Figure()
                fig8.add_trace(go.Pie(
                    labels=['Senior IC Interest', 'Mezz IC Interest', 'DSRA Interest'],
                    values=[_total_ii_sr, _total_ii_mz, _total_ii_dsra],
                    hole=0.5, marker_colors=['#2563EB', '#EAB308', '#16A34A'],
                    textinfo='label+percent', textposition='outside'
                ))
                _grand_ii = _total_ii_sr + _total_ii_mz + _total_ii_dsra
                fig8.update_layout(title='Total Interest Income Breakdown',
                    annotations=[dict(text=f'€{_grand_ii:,.0f}', x=0.5, y=0.5, font_size=16, showarrow=False)])
                st.plotly_chart(fig8, use_container_width=True)

            # ---- 9. DSRA & Liquidity ----
            with _g_row4[1]:
                st.subheader("9. DSRA & Liquidity")
                fig9 = go.Figure()
                fig9.add_trace(go.Scatter(
                    x=_years, y=[a['dsra_bal'] for a in annual_model],
                    name='DSRA Balance', fill='tozeroy', mode='lines',
                    line=dict(width=1, color='#16A34A'), fillcolor='rgba(22,163,74,0.3)'
                ))
                fig9.add_trace(go.Bar(
                    x=_years, y=[a['ii_dsra'] for a in annual_model],
                    name='DSRA Interest Earned', marker_color='rgba(22,163,74,0.7)'
                ))
                fig9.update_layout(title='DSRA Balance & Interest Earned', xaxis_title='Year', yaxis_title='EUR',
                    xaxis=dict(dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
                st.plotly_chart(fig9, use_container_width=True)

            # ---- 10. Sources & Uses Stacked Bar ----
            st.subheader("10. Sources & Uses")
            _sr_amt = structure['sources']['senior_debt']['amount']
            _mz_amt = structure['sources']['mezzanine']['amount_eur']
            _eq_amt = EQUITY_TOTAL

            _x_cats = ['Sources', 'NWL', 'LanRED', 'TWX']
            fig10 = go.Figure()
            # Senior Debt
            _sr_vals = [_sr_amt, _g_loans['nwl']['senior_portion'], _g_loans['lanred']['senior_portion'], _g_loans['timberworx']['senior_portion']]
            fig10.add_trace(go.Bar(name='Senior Debt', x=_x_cats, y=_sr_vals,
                marker_color='#DC2626',
                text=[f'€{v:,.0f}' for v in _sr_vals], textposition='inside'))
            # Mezzanine
            _mz_vals = [_mz_amt, _g_loans['nwl']['mezz_portion'], _g_loans['lanred']['mezz_portion'], _g_loans['timberworx']['mezz_portion']]
            fig10.add_trace(go.Bar(name='Mezzanine', x=_x_cats, y=_mz_vals,
                marker_color='#F97316',
                text=[f'€{v:,.0f}' for v in _mz_vals], textposition='inside'))
            # Equity in Subsidiaries
            _eq_vals = [_eq_amt, EQUITY_NWL, EQUITY_LANRED, EQUITY_TWX]
            fig10.add_trace(go.Bar(name='Equity in Subs', x=_x_cats, y=_eq_vals,
                marker_color='#9333EA',
                text=[f'€{v:,.0f}' for v in _eq_vals], textposition='inside'))
            fig10.update_layout(title='Capital Stack: Sources and Uses',
                xaxis_title='', yaxis_title='EUR', barmode='stack',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))
            st.plotly_chart(fig10, use_container_width=True)

    # --- SENSITIVITY TAB ---
    if "Sensitivity" in _tab_map:
        with _tab_map["Sensitivity"]:
            st.header("Sensitivity Analysis")
            st.caption("Impact of key variables on SCLCA profitability")

            st.markdown("""
        **SCLCA Profit Drivers:**
        1. **IC Margin** (0.5%) - Spread between IC loan rates and facility rates
        2. **DSRA Interest** (9%) - Return on accumulated cash surplus
        """)

            st.divider()

            # --- Sensitivity Inputs ---
            st.subheader("Adjust Parameters")

            col_s1, col_s2 = st.columns(2)

            with col_s1:
                st.markdown("**Interest Rates**")
                sens_euribor = st.slider(
                    "EURIBOR",
                    min_value=0.0, max_value=6.0, value=2.75, step=0.25,
                    format="%.2f%%",
                    help="Base rate for Senior debt (currently 2.75%)"
                ) / 100

                sens_prime = st.slider(
                    "SA Prime Rate",
                    min_value=7.0, max_value=15.0, value=10.75, step=0.25,
                    format="%.2f%%",
                    help="Base rate for Mezz debt (currently 10.75%)"
                ) / 100

            with col_s2:
                st.markdown("**SCLCA Parameters**")
                sens_ic_margin = st.slider(
                    "IC Margin",
                    min_value=0.0, max_value=2.0, value=0.5, step=0.1,
                    format="%.1f%%",
                    help="Spread charged on IC loans over facility rates"
                ) / 100

                sens_dsra_rate = st.slider(
                    "DSRA Interest Rate",
                    min_value=5.0, max_value=12.0, value=9.0, step=0.5,
                    format="%.1f%%",
                    help="Interest earned on DSRA fixed deposit"
                ) / 100

            # --- Recalculate with sensitivity inputs ---
            # Base rates from config
            _base_margin_sr = structure['sources']['senior_debt']['interest']['margin']
            _base_margin_mz = structure['sources']['mezzanine']['interest']['margin']

            # Adjusted facility rates
            _sens_sr_rate = sens_euribor + _base_margin_sr
            _sens_mz_rate = sens_prime + _base_margin_mz
            _sens_sr_ic_rate = _sens_sr_rate + sens_ic_margin
            _sens_mz_ic_rate = _sens_mz_rate + sens_ic_margin

            # Quick recalculation function
            def calc_margin_with_rates(sr_fac_rate, mz_fac_rate, sr_ic_rate, mz_ic_rate, dsra_rate):
                """Calculate 10-year margin with given rates."""
                total_margin = 0
                dsra_bal = 0
                dsra_interest_total = 0

                for a in annual_model:
                    # Scale interest by rate ratio from base model
                    if _sr_rate > 0 and _mz_r > 0:
                        # Facility costs scale with facility rate
                        new_ie_sr = a['ie_sr'] * (sr_fac_rate / _sr_rate)
                        new_ie_mz = a['ie_mz'] * (mz_fac_rate / _mz_r)
                        # IC income scales with IC rate
                        new_ii_sr = a['ii_sr'] * (sr_ic_rate / _sr_ic_r)
                        new_ii_mz = a['ii_mz'] * (mz_ic_rate / _mz_ic_r)
                        margin = (new_ii_sr + new_ii_mz) - (new_ie_sr + new_ie_mz)
                    else:
                        margin = a['ni'] - a['ii_dsra']

                    # DSRA compounding with new rate
                    dsra_interest = dsra_bal * dsra_rate
                    dsra_bal += margin + dsra_interest
                    dsra_interest_total += dsra_interest
                    total_margin += margin

                return total_margin, dsra_bal, dsra_interest_total

            # Calculate base case and sensitivity case
            base_margin, base_dsra, base_dsra_int = calc_margin_with_rates(
                _sr_rate, _mz_r, _sr_ic_r, _mz_ic_r, DSRA_RATE
            )
            sens_margin, sens_dsra, sens_dsra_int = calc_margin_with_rates(
                _sens_sr_rate, _sens_mz_rate, _sens_sr_ic_rate, _sens_mz_ic_rate, sens_dsra_rate
            )

            st.divider()

            # --- Results ---
            st.subheader("Impact Analysis")

            col_r1, col_r2, col_r3 = st.columns(3)

            margin_delta = sens_margin - base_margin
            dsra_delta = sens_dsra - base_dsra
            total_profit_base = base_margin + base_dsra_int
            total_profit_sens = sens_margin + sens_dsra_int
            total_delta = total_profit_sens - total_profit_base

            with col_r1:
                st.metric(
                    "10-Year IC Margin",
                    f"€{sens_margin:,.0f}",
                    delta=f"€{margin_delta:,.0f}" if abs(margin_delta) > 1 else None
                )

            with col_r2:
                st.metric(
                    "Final DSRA Balance",
                    f"€{sens_dsra:,.0f}",
                    delta=f"€{dsra_delta:,.0f}" if abs(dsra_delta) > 1 else None
                )

            with col_r3:
                st.metric(
                    "Total Profit",
                    f"€{total_profit_sens:,.0f}",
                    delta=f"€{total_delta:,.0f}" if abs(total_delta) > 1 else None
                )

            # Show rate summary
            st.markdown("#### Applied Rates")
            rate_df = pd.DataFrame({
                'Rate': ['Senior Facility', 'Mezz Facility', 'Senior IC', 'Mezz IC', 'DSRA'],
                'Base': [f"{_sr_rate*100:.2f}%", f"{_mz_r*100:.2f}%",
                        f"{_sr_ic_r*100:.2f}%", f"{_mz_ic_r*100:.2f}%", f"{DSRA_RATE*100:.1f}%"],
                'Adjusted': [f"{_sens_sr_rate*100:.2f}%", f"{_sens_mz_rate*100:.2f}%",
                            f"{_sens_sr_ic_rate*100:.2f}%", f"{_sens_mz_ic_rate*100:.2f}%",
                            f"{sens_dsra_rate*100:.1f}%"]
            })
            render_table(rate_df, right_align=["Base", "Adjusted"])

            st.divider()

            # --- Tornado Chart ---
            st.subheader("Sensitivity Tornado")
            st.caption("Impact of ±1% change in each variable on Total Profit")

            # Helper to calculate total profit
            def calc_profit(sr_rate, mz_rate, ic_margin, dsra_rate):
                sr_ic = sr_rate + ic_margin
                mz_ic = mz_rate + ic_margin
                m, _, di = calc_margin_with_rates(sr_rate, mz_rate, sr_ic, mz_ic, dsra_rate)
                return m + di

            base_profit = calc_profit(_sr_rate, _mz_r, INTERCOMPANY_MARGIN, DSRA_RATE)

            # Test ±1% for each variable
            tornado_data = []

            # EURIBOR: +1% increases both cost AND income proportionally
            p_up = calc_profit(_sr_rate + 0.01, _mz_r, INTERCOMPANY_MARGIN, DSRA_RATE)
            p_down = calc_profit(_sr_rate - 0.01, _mz_r, INTERCOMPANY_MARGIN, DSRA_RATE)
            tornado_data.append(('EURIBOR', p_up - base_profit, p_down - base_profit))

            # Prime: +1% increases both cost AND income
            p_up = calc_profit(_sr_rate, _mz_r + 0.01, INTERCOMPANY_MARGIN, DSRA_RATE)
            p_down = calc_profit(_sr_rate, _mz_r - 0.01, INTERCOMPANY_MARGIN, DSRA_RATE)
            tornado_data.append(('Prime Rate', p_up - base_profit, p_down - base_profit))

            # IC Margin: +1% increases income only
            p_up = calc_profit(_sr_rate, _mz_r, INTERCOMPANY_MARGIN + 0.01, DSRA_RATE)
            p_down = calc_profit(_sr_rate, _mz_r, max(0, INTERCOMPANY_MARGIN - 0.005), DSRA_RATE)
            tornado_data.append(('IC Margin', p_up - base_profit, p_down - base_profit))

            # DSRA Rate: affects compounding
            p_up = calc_profit(_sr_rate, _mz_r, INTERCOMPANY_MARGIN, DSRA_RATE + 0.01)
            p_down = calc_profit(_sr_rate, _mz_r, INTERCOMPANY_MARGIN, DSRA_RATE - 0.01)
            tornado_data.append(('DSRA Rate', p_up - base_profit, p_down - base_profit))

            # Sort by absolute impact
            tornado_data.sort(key=lambda x: abs(x[1]) + abs(x[2]), reverse=True)

            # Create tornado chart
            fig_tornado = go.Figure()

            variables = [t[0] for t in tornado_data]
            upside = [t[1] for t in tornado_data]
            downside = [t[2] for t in tornado_data]

            fig_tornado.add_trace(go.Bar(
                y=variables, x=upside, orientation='h',
                name='+1%', marker_color='#22C55E'
            ))
            fig_tornado.add_trace(go.Bar(
                y=variables, x=downside, orientation='h',
                name='-1%', marker_color='#EF4444'
            ))

            fig_tornado.update_layout(
                title='Profit Impact of ±1% Rate Change',
                xaxis_title='Change in Total Profit (EUR)',
                barmode='overlay',
                height=300,
                showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=1.02)
            )
            fig_tornado.add_vline(x=0, line_dash="dash", line_color="gray")

            st.plotly_chart(fig_tornado, use_container_width=True)

            # Find IC margin impact for insight
            ic_impact = next((t[1] for t in tornado_data if t[0] == 'IC Margin'), 0)

            st.info(f"""
        **Key Insight:** IC Margin has the largest impact on profitability.
        A 1% increase in IC Margin adds **€{abs(ic_impact):,.0f}** to total profit.

        Interest rate changes (EURIBOR/Prime) have minimal net impact since they affect
        both facility costs and IC income proportionally - the margin is preserved.
        """)

    # --- SECURITY TAB ---
    if "Security" in _tab_map:
        with _tab_map["Security"]:
            # Logo header
            _sclca_sec_logo = LOGO_DIR / "lanseria-smart-city-logo-white.png"
            if _sclca_sec_logo.exists():
                _secl, _sect = st.columns([1, 8])
                with _secl:
                    _render_logo_dark_bg(_sclca_sec_logo, width=100)
                with _sect:
                    st.header("Security Package")
                    st.caption("Three-layer security package for the IIC senior facility")
            else:
                st.header("Security Package")
                st.caption("Three-layer security package for the IIC senior facility")

            security = load_config("security")

            # Structure diagram
            render_svg("security_structure.svg", "SVG_SECURITY_CONTENT.md")

            st.divider()

            # --- Security Package ---
            st.subheader("Security Package — How It Works")

            _sec_content = load_content_md("SECURITY_CONTENT.md").get("sclca", "")
            if _sec_content:
                # Extract "Security Package — How It Works" section
                for _sect in _sec_content.split("\n### "):
                    if "How It Works" in _sect:
                        st.markdown(_sect.partition("\n")[2].strip())
                        break
            else:
                st.markdown("Security package details available in SECURITY_CONTENT.md")

            st.divider()

            # Layer 1 — Holding financial assets
            l1 = security['holding']['layer_1']
            st.subheader(l1['title'])
            st.caption(l1['description'])

            l1_data = []
            for item in l1['items']:
                row = {"Security": item['security'], "Detail": item['detail']}
                if 'value_eur' in item:
                    row["Value"] = f"€{item['value_eur']:,.0f}"
                elif 'value' in item:
                    row["Value"] = f"€{item['value']:,.0f}"
                elif 'value_zar' in item:
                    row["Value"] = f"R{item['value_zar']:,.0f}"
                else:
                    row["Value"] = "—"
                if 'pledged_to' in item:
                    row["Pledged To"] = item['pledged_to']
                l1_data.append(row)
            df_l1 = pd.DataFrame(l1_data)
            render_table(df_l1, right_align=["Value"])

            st.divider()

            # Layer 2 — Guarantees, Insurance & Credit Enhancements (per subsidiary)
            st.subheader("Layer 2 — Guarantees, Insurance & Credit Enhancements (per subsidiary)")
            st.caption("Corporate guarantees, ECA cover, debt service cover & FX hedge, and grant prepayments — pushed down by Creation Capital to IIC")

            # ── NWL L2 ──
            _nwl_sec = security['subsidiaries']['nwl']
            _nwl_total_ic = _nwl_sec['ic_loan_size_eur']
            _nwl_swap_on_sclca = st.session_state.get("sclca_nwl_hedge", "CC DSRA \u2192 FEC") == "Cross-Currency Swap"
            _dtic_eur_sc = financing['prepayments']['dtic_grant']['amount_eur']
            _gepf_eur_sc = financing['prepayments']['gepf_bulk_services']['amount_eur']
            _dtic_zar_sc = financing['prepayments']['dtic_grant']['amount_zar']
            _gepf_zar_sc = financing['prepayments']['gepf_bulk_services']['total_zar']
            _dsra_zar_sc = financing['sources']['mezzanine']['dsra_size_zar']
            _dsra_eur_sc = _dsra_zar_sc / FX_RATE
            with st.expander("New Water Lanseria Pty Ltd", expanded=False):
                st.markdown(f"**IC Loan: €{_nwl_total_ic:,.0f}**")

                # Group 1: Guarantee + ECA
                with st.container(border=True):
                    st.markdown("##### 1. Corporate Guarantee + Atradius ECA Cover")
                    _g1, _g2 = st.columns(2)
                    _g1.metric("VPH Corporate Guarantee", f"€{_nwl_total_ic:,.0f}", delta="Full IC loan (Sr + Mz)")
                    _g2.metric("Atradius ECA Cover", "~€4.2M", delta="To be applied — sized to M36 balance")
                    st.caption(
                        "Veracity Property Holdings guarantees full NWL IC loan. "
                        "Atradius ECA cover sized to **M36 exposed balance** — "
                        "triggered by Dutch content in Colubris BoP (€1,721,925). **To be applied for** at Atradius DSB."
                    )

                # Group 2: DS Cover & FX Hedge
                st.markdown("##### 2. Debt Service Cover & FX Hedge")
                _dsra_col_sc, _swap_col_sc = st.columns(2)
                with _dsra_col_sc:
                    with st.container(border=True):
                        if not _nwl_swap_on_sclca:
                            st.markdown(":green[**SELECTED**]")
                            st.markdown("**DSRA via FEC** (semi-bank-to-bank)")
                            _d1, _d2 = st.columns(2)
                            _d1.metric("DSRA Size", f"R{_dsra_zar_sc:,.0f}", delta=f"€{_dsra_eur_sc:,.0f}")
                            _d2.metric("Timing", "M24", delta="Covers P1+P2")
                        else:
                            st.markdown(":grey[NOT SELECTED]")
                            st.markdown(f":grey[**DSRA via FEC** (semi-bank-to-bank) — R{_dsra_zar_sc:,.0f} at M24]")
                with _swap_col_sc:
                    with st.container(border=True):
                        if _nwl_swap_on_sclca:
                            st.markdown(":green[**SELECTED**]")
                            st.markdown("**Cross-Currency Swap** (bank-to-bank)")
                            st.metric("Structure", "EUR→ZAR Swap", delta="Bank-to-bank + FX hedge")
                        else:
                            st.markdown(":grey[NOT SELECTED]")
                            st.markdown(":grey[**Cross-Currency Swap** (bank-to-bank) — FX + security in one]")

                # Group 3: Grants
                with st.container(border=True):
                    st.markdown("##### 3. Pre-Revenue Cash Flow for Prepayment (DTIC + GEPF)")
                    _gr1, _gr2, _gr3 = st.columns(3)
                    _gr1.metric("DTIC Manufacturing", f"R{_dtic_zar_sc:,.0f}", delta=f"€{_dtic_eur_sc:,.0f}")
                    _gr2.metric("GEPF Bulk Services", f"R{_gepf_zar_sc:,.0f}", delta=f"€{_gepf_eur_sc:,.0f}")
                    _gr3.metric("Combined", f"R{_dtic_zar_sc + _gepf_zar_sc:,.0f}", delta=f"€{_dtic_eur_sc + _gepf_eur_sc:,.0f}")

                # VPH Financials
                st.markdown("**Veracity Property Holdings — Financial Highlights (FY2025)**")
                _ver_data = [
                    {"Metric": "Total Assets", "Value": "R746.5M"},
                    {"Metric": "Investment Property", "Value": "R692.9M"},
                    {"Metric": "Total Equity", "Value": "R53.4M"},
                    {"Metric": "Revenue", "Value": "R72.5M"},
                    {"Metric": "Operating Profit", "Value": "R42.9M"},
                    {"Metric": "Finance Costs", "Value": "R58.5M"},
                    {"Metric": "D/E Ratio", "Value": "13.0x"},
                    {"Metric": "Interest Cover", "Value": "0.73x"},
                ]
                render_table(pd.DataFrame(_ver_data), right_align=["Value"])

            # ── LanRED L2 ──
            _lr_sec = security['subsidiaries']['lanred']
            _lr_total_ic = _lr_sec['ic_loan_size_eur']
            _lr_uw_on_sc = st.session_state.get("lanred_scenario", "Greenfield") == "Greenfield"
            with st.expander("LanRED", expanded=False):
                st.markdown(f"**IC Loan: €{_lr_total_ic:,.0f}**")

                _lr_uw_col_sc, _lr_sw_col_sc = st.columns(2)
                with _lr_uw_col_sc:
                    with st.container(border=True):
                        if _lr_uw_on_sc:
                            st.markdown(":green[**SELECTED**]")
                            st.markdown("**Independent Underwriting**")
                            st.metric("Underwriting", f"€{_lr_total_ic:,.0f}", delta="Full IC loan")
                        else:
                            st.markdown(":grey[NOT SELECTED]")
                            st.markdown(f":grey[**Independent Underwriting** — €{_lr_total_ic:,.0f}]")
                with _lr_sw_col_sc:
                    with st.container(border=True):
                        if not _lr_uw_on_sc:
                            st.markdown(":green[**SELECTED**]")
                            st.markdown("**Cross-Currency Swap** (bank-to-bank)")
                            st.metric("Swap Notional", f"€{_lr_total_ic:,.0f}", delta="Bank-to-bank + FX hedge")
                        else:
                            st.markdown(":grey[NOT SELECTED]")
                            st.markdown(f":grey[**Cross-Currency Swap** (bank-to-bank) — €{_lr_total_ic:,.0f}]")
                st.caption("Per asset and sculpting choices — either independent underwriting or bank-to-bank swap.")

            # ── TWX L2 ──
            _twx_sec = security['subsidiaries']['timberworx']
            _twx_total_ic = _twx_sec['ic_loan_size_eur']
            with st.expander("Timberworx", expanded=False):
                st.markdown(f"**IC Loan: €{_twx_total_ic:,.0f}**")
                with st.container(border=True):
                    st.markdown("##### Corporate Guarantee + Atradius ECA Cover")
                    _t1, _t2 = st.columns(2)
                    _t1.metric("Phoenix Corporate Guarantee", f"€{_twx_total_ic:,.0f}", delta="Full IC loan (Sr + Mz)")
                    _t2.metric("Atradius ECA Cover", f"€{_twx_total_ic:,.0f}", delta="To be applied — full IC loan")
                    st.caption(
                        f"VH Properties (40% in Phoenix Group) guarantees full TWX IC loan. "
                        f"Atradius ECA cover sized to **full IC loan** (€{_twx_total_ic:,.0f}) — vanilla, "
                        f"from M24. Dutch content trigger: Panel Equipment (€200k). **To be applied for** at Atradius DSB."
                    )

                st.markdown("**Phoenix Group — Guarantee Capacity**")
                _phx_data = [
                    {"Metric": "Group EBITDA", "Value": "R68.2M"},
                    {"Metric": "VH Properties stake", "Value": "40%"},
                    {"Metric": "Attributable EBITDA", "Value": "R27.3M"},
                    {"Metric": "2-year cash generation", "Value": "R54.6M"},
                    {"Metric": "TWX IC loan (ZAR)", "Value": "R40.8M"},
                    {"Metric": "Coverage ratio", "Value": "1.34x"},
                ]
                render_table(pd.DataFrame(_phx_data), right_align=["Value"])

            st.divider()

            # Layer 3 — Physical Assets & Revenue Contracts (per subsidiary)
            st.subheader("Layer 3 — Physical Assets & Revenue Contracts (per subsidiary)")
            st.caption("Hard collateral: equipment, infrastructure, and contracted revenue streams")

            for sub_key, sub_sec in security['subsidiaries'].items():
                _label = f"{sub_sec['name']}"
                with st.expander(_label, expanded=False):
                    l3 = sub_sec.get('layer_3', {})
                    st.markdown(f"**{l3.get('title', 'Layer 3')}**")

                    # Physical assets
                    _phys_assets = l3.get('physical_assets', [])
                    if _phys_assets:
                        st.markdown("**Physical Assets**")
                        _pa_rows = []
                        for _item in _phys_assets:
                            _row = {
                                'Asset': _item.get('asset', ''),
                                'Supplier': _item.get('supplier', ''),
                                'Country': _item.get('country', ''),
                            }
                            if 'budget_eur' in _item:
                                _row['Budget'] = _item['budget_eur']
                            _pa_rows.append(_row)
                        _df_pa = pd.DataFrame(_pa_rows)
                        render_table(_df_pa, {"Budget": _eur_fmt} if 'Budget' in _df_pa.columns else None)

                    # Revenue contracts
                    _rev_contracts = l3.get('revenue_contracts', [])
                    if _rev_contracts:
                        st.markdown("**Revenue Contracts**")
                        _rc_df = pd.DataFrame(_rev_contracts)
                        _rc_cols = [c for c in ['contract', 'type', 'status', 'note'] if c in _rc_df.columns]
                        render_table(_rc_df[_rc_cols].rename(columns={
                            'contract': 'Contract', 'type': 'Type',
                            'status': 'Status', 'note': 'Note'
                        }))

                    # NWL: market position
                    if sub_key == 'nwl':
                        _mkt = l3.get('market_position', {})
                        if _mkt:
                            st.markdown("**Market Position**")
                            _m1, _m2, _m3 = st.columns(3)
                            _m1.metric("Installed Capacity", f"{_mkt.get('installed_capacity_mld', 0)} MLD")
                            _m2.metric("Latent Demand", f"{_mkt.get('latent_demand_mld', 0)} MLD")
                            _m3.metric("Growth Headroom", f"{_mkt.get('growth_headroom', 0):.0f}x")

    # --- FX ---
    # --- DELIVERY ---
    if "Delivery" in _tab_map:
        with _tab_map["Delivery"]:
            st.header("Delivery Structure")
            st.caption("Colubris Water Solutions — Integrator across all three delivery scopes")

            # Load MD content first
            delivery_content_md = load_content_md("DELIVERY_CONTENT.md")
            sclca_delivery_md = delivery_content_md.get('sclca', "")

            if sclca_delivery_md:
                st.markdown(sclca_delivery_md)
                st.divider()

            delivery = load_config("delivery")

            # Diagram
            render_svg("delivery_structure.svg", "SVG_DELIVERY_CONTENT.md")

            st.divider()

            st.subheader("Integrator")
            st.markdown(f"""
**{delivery['integrator']['name']}** ({delivery['integrator']['country']}) serves as the project
integrator and wrapper across all three delivery scopes. Colubris coordinates the EPC
contractors, manages the delivery interfaces, and provides the single point of accountability
that the Atradius ECA cover wraps around.
        """)

            st.divider()

            # Per-scope summary table — computed content from assets + fees + IDC
            st.subheader("Delivery Scopes")
            scopes = delivery['scopes']

            _fees_cfg_del = load_config("fees")
            _assets_cfg_del = load_config("assets")["assets"]
            _project_debt = structure['sources']['senior_debt']['amount']
            _sr_rate_fac = structure['sources']['senior_debt']['interest']['rate']
            _sr_ic_rate_del = _sr_rate_fac + INTERCOMPANY_MARGIN
            _project_idc = financing['loan_detail']['senior']['rolled_up_interest_idc']
            _ic_idc_total = _project_idc * (_sr_ic_rate_del / _sr_rate_fac) if _sr_rate_fac > 0 else _project_idc

            _scope_rows = []
            _project_country_totals = {}

            for sub_key in ['nwl', 'lanred', 'timberworx']:
                sub_struct = structure['uses']['loans_to_subsidiaries'][sub_key]
                sub_asset_keys = structure['subsidiaries'][sub_key].get('assets', [])
                sub_sr = sub_struct['senior_portion']
                sub_total = sub_sr + sub_struct['mezz_portion']

                cost_rows = []
                # Assets
                for ak in sub_asset_keys:
                    for li in _assets_cfg_del.get(ak, {}).get('line_items', []):
                        _split = li.get('content_split')
                        if _split:
                            for _sc, _sp in _split.items():
                                cost_rows.append({"country": _sc, "amount": li['budget'] * _sp})
                        else:
                            cost_rows.append({"country": li['country'], "amount": li['budget']})
                # Fees
                for fee in _fees_cfg_del.get("fees", []):
                    base = sub_sr if fee.get("funding") == "senior_only" else sub_total
                    cost_rows.append({"country": fee['country'], "amount": base * fee.get("rate", 0)})
                # IDC
                entity_share = sub_sr / _project_debt if _project_debt > 0 else 0
                cost_rows.append({"country": "Netherlands", "amount": _ic_idc_total * entity_share})

                # Aggregate by country
                country_totals = {}
                for cr in cost_rows:
                    c = cr['country']
                    if c:
                        country_totals[c] = country_totals.get(c, 0) + cr['amount']
                        _project_country_totals[c] = _project_country_totals.get(c, 0) + cr['amount']

                grand = sum(country_totals.values())
                content_str = " / ".join(
                    f"{v/grand*100:.0f}% {c[:2].upper()}"
                    for c, v in sorted(country_totals.items(), key=lambda x: -x[1])
                ) if grand > 0 else ""
                _scope_rows.append({
                    "Subsidiary": scopes.get(sub_key, {}).get('name', sub_key),
                    "EPC Model": scopes.get(sub_key, {}).get('epc_model', ''),
                    "EPC Contractor": scopes.get(sub_key, {}).get('epc_contractor', ''),
                    "Total Cost": grand,
                    "Content": content_str,
                })

            _total_project = sum(r['Total Cost'] for r in _scope_rows)
            for r in _scope_rows:
                r['Share'] = f"{r['Total Cost']/_total_project*100:.1f}%" if _total_project > 0 else ""
                r['Total Cost'] = f"€{r['Total Cost']:,.0f}"
            render_table(pd.DataFrame(_scope_rows))

            st.divider()

            # Balanced content total — computed from actual country breakdown
            st.subheader("Balanced Content Total — Colubris Wrapper Cover")

            _sorted_project = sorted(_project_country_totals.items(), key=lambda x: -x[1])
            _total_computed = sum(v for _, v in _sorted_project)

            # Display top countries as metrics
            _country_labels = {
                "Netherlands": "Dutch (NL) — Atradius ECA",
                "Ireland": "Irish (IE)",
                "South Africa": "South African (SA)",
                "Finland": "Finnish (FI)",
                "Australia": "Australian (AU)",
            }
            _metric_cols = st.columns(min(len(_sorted_project) + 1, 5))
            _metric_cols[0].metric("Total Project (incl. IDC)", f"€{_total_computed:,.0f}")
            for _i, (_country, _val) in enumerate(_sorted_project[:4]):
                _lbl = _country_labels.get(_country, _country)
                _metric_cols[min(_i + 1, 4)].metric(_lbl, f"€{_val:,.0f}", f"{_val/_total_computed*100:.1f}%")

            # Balance verification
            st.caption(
                "Balance verified: " +
                " + ".join(f"€{v:,.0f}" for _, v in _sorted_project) +
                f" = €{_total_computed:,.0f}"
            )

            # ── ECA Content Compliance — Envelope Level ──
            st.divider()
            st.subheader("ECA Content Compliance")
            st.caption("Atradius assesses the **combined Colubris wrapper envelope** (NWL + TWX). "
                       "LanRED excluded — underwritten separately.")

            # Compute per-entity + combined
            _env_countries = {}
            _env_total = 0.0
            _ent_content = {}
            for _ek in ['nwl', 'timberworx']:
                _ek_c, _ek_t = _compute_entity_content(_ek)
                _ent_content[_ek] = (_ek_c, _ek_t)
                for _c, _v in _ek_c.items():
                    _env_countries[_c] = _env_countries.get(_c, 0.0) + _v
                _env_total += _ek_t

            _env_sa = _env_countries.get('South Africa', 0) / _env_total if _env_total > 0 else 0
            _env_nl = _env_countries.get('Netherlands', 0) / _env_total if _env_total > 0 else 0

            # Three columns: NWL | TWX | Envelope (decisive)
            _ec_nwl, _ec_twx, _ec_env = st.columns(3)

            _nwl_c, _nwl_t = _ent_content['nwl']
            _nwl_sa = _nwl_c.get('South Africa', 0) / _nwl_t if _nwl_t > 0 else 0
            _nwl_nl = _nwl_c.get('Netherlands', 0) / _nwl_t if _nwl_t > 0 else 0

            _twx_c, _twx_t = _ent_content['timberworx']
            _twx_sa = _twx_c.get('South Africa', 0) / _twx_t if _twx_t > 0 else 0
            _twx_nl = _twx_c.get('Netherlands', 0) / _twx_t if _twx_t > 0 else 0

            with _ec_nwl:
                st.markdown("**NWL**")
                st.metric("SA Content", f"{_nwl_sa*100:.1f}%",
                          "< 50%" if _nwl_sa < 0.50 else "≥ 50%")
                st.metric("Dutch Content", f"{_nwl_nl*100:.1f}%",
                          "≥ 20%" if _nwl_nl >= 0.20 else "< 20%")
            with _ec_twx:
                st.markdown("**Timberworx**")
                st.metric("SA Content", f"{_twx_sa*100:.1f}%",
                          "< 50%" if _twx_sa < 0.50 else "≥ 50%")
                st.metric("Dutch Content", f"{_twx_nl*100:.1f}%",
                          "≥ 20%" if _twx_nl >= 0.20 else "< 20%")
            with _ec_env:
                st.markdown("**Combined Envelope**")
                st.metric("SA Content", f"{_env_sa*100:.1f}%",
                          "Pass" if _env_sa < 0.50 else "Fail")
                st.metric("Dutch Content", f"{_env_nl*100:.1f}%",
                          "Pass" if _env_nl >= 0.20 else "Fail")

            # Compliance test table
            _env_tests = [
                {
                    "Test": "OECD Local Content",
                    "Rule": "< 50% SA",
                    "NWL": f"{_nwl_sa*100:.1f}%",
                    "TWX": f"{_twx_sa*100:.1f}%",
                    "Envelope": f"{_env_sa*100:.1f}%",
                    "Result": "Pass" if _env_sa < 0.50 else "Fail",
                },
                {
                    "Test": "Atradius Dutch Content",
                    "Rule": "≥ 20% NL",
                    "NWL": f"{_nwl_nl*100:.1f}%",
                    "TWX": f"{_twx_nl*100:.1f}%",
                    "Envelope": f"{_env_nl*100:.1f}%",
                    "Result": "Pass" if _env_nl >= 0.20 else "Fail",
                },
            ]
            _df_env_tests = pd.DataFrame(_env_tests)

            def _color_env_result(val):
                if val == "Pass":
                    return "background-color: #d4edda; color: #155724"
                elif val == "Fail":
                    return "background-color: #f8d7da; color: #721c24"
                return ""

            st.table(_df_env_tests.style.map(_color_env_result, subset=["Result"])
                .set_properties(subset=["NWL", "TWX", "Envelope"], **{"text-align": "right"}))

            # ECA Content — Pie Charts
            _eca_chart_cols = st.columns(3)
            _eca_colors = {"Netherlands": "#1e40af", "South Africa": "#16a34a", "Ireland": "#d97706",
                           "Finland": "#7c3aed", "Australia": "#dc2626", "France": "#0891b2"}

            with _eca_chart_cols[0]:
                _nwl_pie = go.Figure(data=[go.Pie(
                    labels=list(_nwl_c.keys()), values=list(_nwl_c.values()),
                    marker=dict(colors=[_eca_colors.get(c, "#6b7280") for c in _nwl_c.keys()]),
                    textinfo='label+percent', hole=0.4,
                )])
                _nwl_pie.update_layout(title="NWL Content", height=300, margin=dict(t=40, b=20, l=20, r=20),
                                       showlegend=False)
                st.plotly_chart(_nwl_pie, use_container_width=True)

            with _eca_chart_cols[1]:
                _twx_pie = go.Figure(data=[go.Pie(
                    labels=list(_twx_c.keys()), values=list(_twx_c.values()),
                    marker=dict(colors=[_eca_colors.get(c, "#6b7280") for c in _twx_c.keys()]),
                    textinfo='label+percent', hole=0.4,
                )])
                _twx_pie.update_layout(title="Timberworx Content", height=300, margin=dict(t=40, b=20, l=20, r=20),
                                       showlegend=False)
                st.plotly_chart(_twx_pie, use_container_width=True)

            with _eca_chart_cols[2]:
                _env_pie = go.Figure(data=[go.Pie(
                    labels=list(_env_countries.keys()), values=list(_env_countries.values()),
                    marker=dict(colors=[_eca_colors.get(c, "#6b7280") for c in _env_countries.keys()]),
                    textinfo='label+percent', hole=0.4,
                )])
                _env_pie.update_layout(title="Combined Envelope", height=300, margin=dict(t=40, b=20, l=20, r=20),
                                       showlegend=False)
                st.plotly_chart(_env_pie, use_container_width=True)

            # Combined content breakdown table
            _env_sorted = sorted(_env_countries.items(), key=lambda x: -x[1])
            _env_rows = []
            for _country, _val in _env_sorted:
                _pct = _val / _env_total if _env_total > 0 else 0
                _env_rows.append({"Country": _country, "Amount (EUR)": _val, "Share": f"{_pct*100:.1f}%"})
            _env_rows.append({"Country": "**Total**", "Amount (EUR)": _env_total, "Share": "100%"})
            with st.expander("Envelope Content Breakdown (NWL + TWX)", expanded=False):
                render_table(pd.DataFrame(_env_rows), {"Amount (EUR)": _eur_fmt})

            st.divider()

            # Key Contractors
            st.subheader("Key Contractors & Suppliers")
            contractors = load_config("contractors")
            for _ck, _cv in contractors['contractors'].items():
                _clogo = _cv.get('logo')
                _expanded = (_ck == "colubris")  # Integrator always expanded
                with st.expander(f"{_cv['name']} — {_cv['role']}", expanded=_expanded):
                    if _clogo and (LOGO_DIR / _clogo).exists():
                        st.image(str(LOGO_DIR / _clogo), width=120)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Country", _cv['country'])
                    c2.metric("HQ", _cv['hq'])
                    if _cv.get('website'):
                        c3.metric("Website", _cv['website'])
                    st.markdown(_cv['overview'])
                    st.markdown("**Key Capabilities:**")
                    for cap in _cv.get('capabilities', []):
                        st.markdown(f"- {cap}")
                    if _cv.get('project_role'):
                        st.info(f"**Project Role:** {_cv['project_role']}")
                    if _cv.get('eca_relevance'):
                        st.caption(f"ECA: {_cv['eca_relevance']}")


# ============================================================
# NWL VIEW
# ============================================================
elif entity == "New Water Lanseria":
    render_subsidiary("nwl", "", "New Water Lanseria")

# ============================================================
# LANRED VIEW
# ============================================================
elif entity == "LanRED":
    render_subsidiary("lanred", "", "LanRED")

# ============================================================
# TIMBERWORX VIEW
# ============================================================
elif entity == "Timberworx":
    render_subsidiary("timberworx", "", "Timberworx")

# ============================================================
# MANAGEMENT — SUMMARY (1-page executive overview)
# ============================================================
elif entity == "Summary":

    # --- Print CSS + button ---
    _print_css = """
    <style>
    @media print {
        [data-testid="stSidebar"], [data-testid="stHeader"],
        [data-testid="stToolbar"], .stDeployButton,
        button, .element-container:has(button) { display: none !important; }
        .main .block-container { padding: 0 !important; max-width: 100% !important; }
        body, .main { background: #fff !important; }
        @page { size: A4 landscape; margin: 12mm; }
    }
    </style>
    """
    st.markdown(_print_css, unsafe_allow_html=True)

    _print_col_l, _print_col_r = st.columns([8, 2])
    with _print_col_r:
        import streamlit.components.v1 as _components
        _components.html(
            '<button onclick="window.print()" style="background:#1e40af;color:#fff;border:none;'
            'padding:8px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;">'
            'Print / Export PDF</button>',
            height=45,
        )

    # --- Header ---
    _sum_logo_path = LOGO_DIR / ENTITY_LOGOS.get("sclca", "")
    _sum_cl, _sum_ct = st.columns([1, 7])
    with _sum_cl:
        if _sum_logo_path.exists():
            st.image(str(_sum_logo_path), width=90)
    with _sum_ct:
        st.title("SCLCA — Executive Summary")
        st.caption("Smart City Lanseria Catalytic Assets  |  Financial Holding Company")

    # Load configs
    _sum_structure = structure  # Use patched copy (ECA adjustments applied)
    _sum_security = load_config("security")
    _sum_project = load_config("project")

    _sum_sources = _sum_structure["sources"]
    _sum_uses = _sum_structure["uses"]
    _sum_loans = _sum_uses["loans_to_subsidiaries"]
    _sum_senior = _sum_sources["senior_debt"]
    _sum_mezz = _sum_sources["mezzanine"]
    _sum_timeline = _sum_project["timeline"]

    # --- Key Metrics bar ---
    _km1, _km2, _km3, _km4 = st.columns(4)
    _km1.metric("Total Project Cost", f"€{_sum_sources['total']:,.0f}")
    _km2.metric("Operating Companies", "3", "NWL · LanRED · Timberworx")
    _km3.metric("Financial Close", _sum_timeline.get("financial_close", "TBD"))
    _km4.metric("Loan Tenure", f"{_sum_timeline.get('repayment_periods', 14) * 6 // 12} years")

    st.divider()

    # ================================================================
    # SECTION 1: CORPORATE STRUCTURE
    # ================================================================
    st.subheader("1. Corporate Structure")
    render_svg("corporate_structure.svg", "SVG_CORPORATE_CONTENT.md")

    st.divider()

    # ================================================================
    # SECTION 2: OWNERSHIP STRUCTURE
    # ================================================================
    st.subheader("2. Ownership Structure")
    _own_svg = Path(__file__).parent / "assets" / "ownership-structure.svg"
    if _own_svg.exists():
        st.image(str(_own_svg), use_container_width=True)

    # DevCo ownership (ECA-facing — 2 UBOs)
    _devco_eca_svg = Path(__file__).parent / "assets" / "devco-ownership-eca.svg"
    if _devco_eca_svg.exists():
        st.image(str(_devco_eca_svg), use_container_width=True)

    # Addendum: Timberworx ownership transition
    _twx_own_svg = Path(__file__).parent / "assets" / "twx-ownership-transition.svg"
    if _twx_own_svg.exists():
        st.image(str(_twx_own_svg), use_container_width=True)

    st.divider()

    # ================================================================
    # SECTION 3: FUNDING STRUCTURE
    # ================================================================
    st.subheader("3. Funding Structure")
    _fund_svg = Path(__file__).parent / "assets" / "funding-structure.svg"
    if _fund_svg.exists():
        st.image(str(_fund_svg), use_container_width=True)

    # Allocation table from config
    _alloc_data = []
    _total_uses = _sum_uses["total"]
    for _ek, _ev in _sum_loans.items():
        _pct = _ev["total_loan"] / _total_uses * 100
        _alloc_data.append({
            "Entity": _ev["name"],
            "Senior (EUR)": f"€{_ev['senior_portion']:,.0f}",
            "Mezz (EUR)": f"€{_ev['mezz_portion']:,.0f}",
            "Total (EUR)": f"€{_ev['total_loan']:,.0f}",
            "Share": f"{_pct:.1f}%",
        })
    _alloc_data.append({
        "Entity": "TOTAL",
        "Senior (EUR)": f"€{_sum_structure['balance_check']['senior_sources']:,.0f}",
        "Mezz (EUR)": f"€{_sum_structure['balance_check']['mezz_sources']:,.0f}",
        "Total (EUR)": f"€{_total_uses:,.0f}",
        "Share": "100%",
    })
    render_table(pd.DataFrame(_alloc_data), right_align=["Senior (EUR)", "Mezz (EUR)", "Total (EUR)", "Share"])

    st.markdown("**Timeline:** "
                f"Construction M0–M{_sum_timeline.get('cod_month', 18)} · "
                f"Grace M{_sum_timeline.get('cod_month', 18)}–M{_sum_timeline.get('loan_holiday_months', 24)} · "
                f"Repayment M{_sum_timeline.get('loan_holiday_months', 24)}–M{_sum_senior.get('loan_settlement_months', 108)}")

    st.divider()

    # ================================================================
    # SECTION 4: SECURITY PACKAGE
    # ================================================================
    st.subheader("4. Security Package")
    render_svg("security_structure.svg", "SVG_SECURITY_CONTENT.md")

    # Summary tables from config
    _l1 = _sum_security["holding"]["layer_1"]
    st.markdown(f"**{_l1['title']}**")
    _l1_data = []
    for _item in _l1["items"]:
        _l1_data.append({
            "Security": _item["security"],
            "Detail": _item["detail"],
            "Value (EUR)": f"€{_item.get('value_eur', 0):,.0f}" if _item.get("value_eur") else "—",
            "Pledged To": _item.get("pledged_to", "—"),
        })
    render_table(pd.DataFrame(_l1_data), right_align=["Value (EUR)"])

    st.markdown("**Layer 2 — Guarantees & Insurance (by entity)**")
    _l2_summary = []
    for _skey in ["nwl", "lanred", "timberworx"]:
        _sub_sec = _sum_security["subsidiaries"].get(_skey, {})
        _l2 = _sub_sec.get("layer_2", {})
        for _item in _l2.get("items", []):
            _val = ""
            if _item.get("coverage_eur"):
                _val = f"€{_item['coverage_eur']:,.0f}"
            elif _item.get("value_eur"):
                _val = f"€{_item['value_eur']:,.0f}"
            elif _item.get("value_zar"):
                _val = f"R{_item['value_zar']/1e6:.1f}M"
            _l2_summary.append({
                "Entity": _sub_sec.get("name", _skey),
                "Enhancement": _item["enhancement"],
                "Type": _item.get("type", "—"),
                "Value": _val if _val else "—",
                "Status": _item.get("status", "—"),
            })
    render_table(pd.DataFrame(_l2_summary), right_align=["Value"])


# ============================================================
# MANAGEMENT — STRATEGY
# ============================================================
elif entity == "Strategy":
    st.header("Strategy")
    st.markdown("Strategic priorities for the SCLCA capital raising and project delivery.")

    st.subheader("Capital Raising — Critical Path")
    st.markdown("""
- **Creation Capital closure** — Freddy is leaving, so we need to close now. If CC don't take it to committee now, escalate via Carl
  - Mezzanine is the most important piece
  - DSRA makes it fly: DSRA → FEC/Swap via Investec
  - CC credit note guaranteeing DSRA provision → Investec provides FEC
  - Bottom line: we *could* do FEC/swap without CC — cards yet to play
- **Investec meeting** — FEC or swap structure; CC guarantee or Veracity guarantee as underlying
  - The DSRA exposure needs to be framed as an Investec exposure (or alternative)
""")

    st.subheader("Project Delivery")
    st.markdown("""
- **NWL** — SAWW and Rand Water negotiations on equity investment (buy land below LLC to allow further investment). They will NOT need to provide a guarantee
- **Timberworx Investment 1** — CoE + €200k panel equipment (current scope)
- **Timberworx Investment 2** — Houses + lease capitalised = €5M from Germany/France, turn-key houses
- **LanRED** — Need Carl, Andrew, Sechaba to deliver 1–2 solar projects with underwriting NOW, for €3M. We CAN do 2×€3M, but then need 15% extra equity for second tranche
""")

    st.subheader("Guarantor Strategy")
    st.markdown("""
- Veracity for NWL — show EBITDA control capability, or ability to sell parts of stake for cash
- VH Properties / Phoenix for TWX — show that companies are now mature and generate stable EBITDA; management overview of anchors, pictures, tenancy schedules
- Joint and several liability across projects is acceptable if required by ECA
- If IIC wants full ECA cover → go full supplier credit, don't apply TWX with Atradius, use both companies to cover ONLY NWL
""")

    st.subheader("DevCo Shareholding Strategy")
    st.error("""
**INTERNAL ONLY — Outside Robbert's vision**

**Current state:** Smart City Lanseria DevCo has 4 shareholders (Anduza Water, NexusNovus, Eckhardt, Others).

**ECA application:** Present only 2 UBOs to Atradius/IIC — Sizakele Mabuza (Anduza Water) and Mark van Houten (VHIT).
VanSquare (TWX co-shareholder) is also owned by Mark's Trust (VHIT).

**To-do:** Put in place a contract to replace Mark's Trust (VHIT) with **NexusNovus Holdings** as DevCo shareholder.
NexusNovus Holdings is 50% held by Mark's Trust.

**NexusNovus must NOT be mentioned in any external documents or ECA application at this stage.**
Reason: The Indian company "NexusNovus Airport Waste Management Pvt" has had issues with a previous guarantor.
Name association creates reputational risk during ECA due diligence. Once capital raising is closed,
NexusNovus Holdings can be formally introduced via the contractual substitution mechanism.
""")

    st.divider()

    st.subheader("Smart City Lanseria DevCo — Ownership")
    st.markdown("**ECA-facing view** (for Atradius/IIC application):")
    _devco_eca_svg2 = Path(__file__).parent / "assets" / "devco-ownership-eca.svg"
    if _devco_eca_svg2.exists():
        st.image(str(_devco_eca_svg2), use_container_width=True)
    st.caption("ECA view: Two UBOs identified — Sizakele Mabuza (Anduza Water) and Mark van Houten (VHIT/VanSquare)")

    with st.expander("Internal: Actual Shareholders (4 owners)", expanded=False):
        _devco_svg = Path(__file__).parent / "assets" / "devco-shareholders.svg"
        if _devco_svg.exists():
            st.image(str(_devco_svg), use_container_width=True)
        st.caption("Behind the scenes: contracts to be set up to reflect actual 4-shareholder structure")

    st.subheader("Timberworx — Ownership Transition")
    _twx_own_svg = Path(__file__).parent / "assets" / "twx-ownership-transition.svg"
    if _twx_own_svg.exists():
        st.image(str(_twx_own_svg), use_container_width=True)

# ============================================================
# MANAGEMENT — TASKS
# ============================================================
elif entity == "Tasks":
    st.header("Tasks")

    st.subheader("Immediate Actions")
    _task_data = [
        ("Call Mergence — explain guarantee is done, negotiate equity stake, request O&M RFQ (pressure strategy)", "High", "Pending"),
        ("Call Waterleau — request O&M quote", "High", "Pending"),
        ("Meet JV partners — close out contractual arrangements (notes to follow)", "High", "Pending"),
        ("If JV partners need more vehicles → request formal strategy + budget for review", "Medium", "Pending"),
        ("Meet Creation Capital — get them to proceed, or escalate via Carl", "Critical", "Pending"),
        ("Meet Investec — CC for FEC or swap; or Veracity as guarantee for FEC/swap", "Critical", "Pending"),
        ("Obtain VH Properties consolidated balance sheet (3 years)", "High", "Pending"),
        ("Obtain Phoenix Group management accounts — verify EBITDA stability", "High", "Pending"),
        ("Obtain Veracity management accounts Mar–Dec 2025 (post-FY end Feb 2025)", "High", "Pending"),
        ("Check whether loans to Veracity subsidiary companies are cross-collateralized", "Medium", "Pending"),
        ("Evaluate feasibility of Phoenix direct guarantee (bypassing VH Properties)", "Medium", "Pending"),
        ("Identify potential third guarantor company as backup option", "Medium", "Pending"),
        ("Prepare detailed Dutch content breakdown for Atradius application", "High", "Pending"),
        ("Commission ESIA to IFC Performance Standards", "High", "Pending"),
        ("Legal opinion on guarantee enforceability (RSA law) for both entities", "High", "Pending"),
        ("LanRED content analysis — Greenfield vs Brownfield+ solar (not ECA, informational only)", "Low", "Pending"),
    ]
    _task_df = pd.DataFrame(_task_data, columns=["Task", "Priority", "Status"])
    st.dataframe(_task_df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Phoenix Group — Property EBITDA Analysis")
    st.markdown("**VH Properties** holds 40% in **Phoenix Group**, which will provide the guarantee for Timberworx.")

    _phoenix_data = [
        ("Ridgeview Centre", -5_912_496, 21_477_981, 15_565_485, 0.40, 6_226_194),
        ("Brackenfell", -7_296_458, 23_421_942, 16_125_484, 0.40, 6_450_194),
        ("Chartwell Corner", -6_217_397, 10_827_895, 4_610_498, 0.20, 922_100),
        ("Jukskei Corner", 1_281_065, 5_382_568, 6_663_633, 0.40, 2_665_453),
        ("Madelief", -169_424, 11_037_417, 10_867_992, 0.40, 4_347_197),
        ("Olivedale", 1_134_087, 13_286_200, 14_420_287, 0.40, 5_768_115),
    ]
    _phoenix_df = pd.DataFrame(_phoenix_data, columns=["Property", "Net Profit (R)", "Finance Charges (R)", "EBITDA (R)", "Ownership %", "Attributable (R)"])
    _phoenix_df["Ownership %"] = _phoenix_df["Ownership %"].apply(lambda x: f"{x:.0%}")
    for c in ["Net Profit (R)", "Finance Charges (R)", "EBITDA (R)", "Attributable (R)"]:
        _phoenix_df[c] = _phoenix_df[c].apply(lambda x: f"R{x:,.0f}")
    render_table(_phoenix_df, right_align=["Net Profit (R)", "Finance Charges (R)", "EBITDA (R)", "Ownership %", "Attributable (R)"])

    _tot_ebitda = 68_253_379
    _tot_attr = 26_379_252
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("Group EBITDA", f"R{_tot_ebitda:,.0f}")
    _c2.metric("Attributable EBITDA (40%)", f"R{_tot_attr:,.0f}")
    _twx_ic_zar = 2_032_571 * FX_RATE
    _c3.metric("Coverage (2yr / TWX IC)", f"{(_tot_attr * 2 / _twx_ic_zar):.2f}x")

    st.caption("Source: Phoenix Group Summary 2025 + WhatsApp (Mark van Houten, 8 Feb 2026)")

    st.divider()
    st.subheader("Data Collection Checklist")

    st.markdown("**Veracity Property Holdings & Subsidiaries**")
    _ver_checks = [
        ("Audited financials FY2025 (28 Feb 2025)", True),
        ("Audited financials FY2024", True),
        ("Audited financials FY2023", False),
        ("Management accounts Mar–Dec 2025 (post-FY end)", False),
        ("Subsidiary financials: Aquaside Trading", False),
        ("Subsidiary financials: BBP Unit 1 Phase 2", False),
        ("Subsidiary financials: Cornerstone Property", False),
        ("Subsidiary financials: Erf 86 Longmeadow", False),
        ("Subsidiary financials: Providence Property", False),
        ("Subsidiary financials: Sun Property", False),
        ("Subsidiary financials: Uvongo Falls No 26", False),
    ]
    for _lbl, _done in _ver_checks:
        st.checkbox(_lbl, value=_done, disabled=True, key=f"ver_{_lbl}")

    st.markdown("**VH Properties / Phoenix Group & Subsidiaries**")
    _phx_checks = [
        ("VH Properties consolidated balance sheet (3 years)", False),
        ("Phoenix Group consolidated financials (3 years)", False),
        ("Ridgeview Centre — company financials + property details", False),
        ("Brackenfell — company financials + property details", False),
        ("Chartwell Corner — company financials + property details", False),
        ("Jukskei Corner — company financials + property details", False),
        ("Madelief — company financials + property details", False),
        ("Olivedale — company financials + property details", False),
        ("Property valuations for all 6 retail centres", False),
        ("Management accounts for all underlying assets", False),
    ]
    for _lbl, _done in _phx_checks:
        st.checkbox(_lbl, value=_done, disabled=True, key=f"phx_{_lbl}")

# ============================================================
# MANAGEMENT — CP & CS
# ============================================================
elif entity == "CP & CS":
    st.header("Conditions Precedent & Conditions Subsequent")

    st.subheader("Conditions Precedent (pre-financial close)")
    _cp_items = [
        # --- Appointments & Contracts ---
        ("Owners engineer appointment (WSP or alternative)", "NWL", "Pending"),
        ("Contract with JV partners for haulage and potential O&M", "NWL", "Pending"),
        ("Offer by JV partners for O&M", "NWL", "Pending"),
        ("RFQ for O&M to Waterleau and SAWW", "NWL", "Pending"),
        # --- Security packages ---
        ("Better security package — WSP (bank guarantees? check quote)", "NWL", "Pending"),
        ("Better security package — Oxymem", "NWL", "Pending"),
        ("Better security package — Colubris", "NWL", "Pending"),
        # --- Corporate & Shareholding ---
        ("Contract in place with CrossPoint for shareholding", "SCLCA", "Pending"),
        ("Contract in place with TWX for shareholding", "SCLCA", "Pending"),
        ("Contract: replace VHIT with NexusNovus Holdings in DevCo (post-close)", "DevCo", "Pending"),
        ("Close equity/mezz with Creation Capital (or alternative)", "SCLCA", "Critical"),
        ("Close Investec for FEC or swap against comfortable underlying", "SCLCA", "Critical"),
        # --- Inter-company agreements ---
        ("Power purchase agreement NWL–LanRED (IC electricity)", "NWL / LanRED", "Pending"),
        ("Agreement Lanseria Smart City–LanRED (sell remaining power)", "LanRED", "Pending"),
        ("CoE rental agreement NWL–TWX", "NWL / TWX", "Pending"),
        ("CoE sales agreement to LLC (or subordinated company)", "TWX", "Pending"),
        # --- LanRED Procurement (TBD) ---
        ("Select Solar PV supplier and confirm country of origin", "LanRED", "Pending"),
        ("Select Battery storage (BESS) supplier and confirm country of origin", "LanRED", "Pending"),
        ("Select Grid connection infrastructure supplier and confirm country of origin", "LanRED", "Pending"),
        # --- Financial & Due Diligence ---
        ("3 years audited financials — Veracity", "NWL", "Partial (FY24-25 in hand)"),
        ("3 years audited financials — VH Properties / Phoenix", "TWX", "Pending"),
        ("ESIA to IFC Performance Standards", "NWL", "Pending"),
        ("Legal opinion on guarantee enforceability (RSA law)", "All", "Pending"),
        ("Board resolutions authorising guarantees", "All", "Pending"),
        ("Dutch content schedule for Atradius application", "NWL / TWX", "Pending"),
        ("DSRA commitment letter from Creation Capital", "NWL", "Pending"),
        ("ECA application to Atradius DSB", "NWL / TWX", "Pending"),
    ]
    _cp_df = pd.DataFrame(_cp_items, columns=["Condition Precedent", "Entity", "Status"])
    st.dataframe(_cp_df, use_container_width=True, hide_index=True)

    st.subheader("Conditions Subsequent (post-financial close)")
    _cs_items = [
        ("Execute O&M contract with selected provider", "NWL", "—"),
        ("Finalise JV partner contractual arrangements", "NWL", "—"),
        ("Commission and handover of MABR plant", "NWL", "—"),
        ("Solar PV installation and grid connection", "LanRED", "—"),
        ("CoE building completion and tenant move-in", "TWX", "—"),
        ("DTIC grant disbursement at M12", "NWL", "—"),
        ("GEPF bulk services fee disbursement at M12", "NWL", "—"),
        ("DSRA funding at M24", "NWL", "—"),
    ]
    _cs_df = pd.DataFrame(_cs_items, columns=["Condition Subsequent", "Entity", "Status"])
    st.dataframe(_cs_df, use_container_width=True, hide_index=True)

# ============================================================
# MANAGEMENT — GUARANTOR ANALYSIS
# ============================================================
elif entity == "Guarantor Analysis":
    st.header("Guarantor Analysis")
    st.markdown("ECA-focused assessment of corporate guarantors for the SCLCA security package.")

    # Helpers (_load_guarantor_jsons, _gval, _fmtr, _render_sub_financials, _render_sub_summary_and_toggles)
    # are defined at module level above.

    # ECA evaluation framework intro
    with st.expander("How ECAs Evaluate Corporate Guarantors", expanded=False):
        st.markdown("""
ECAs assess guarantors on multiple dimensions. The table below shows standard thresholds:

| Metric | Strong | Acceptable | Marginal |
|---|---|---|---|
| Credit rating | Investment grade (BBB-) | BB+ to BB- | Below BB- or unrated |
| Net worth vs guarantee | > 3x | 2-3x | < 1.5x |
| Interest coverage | > 3.0x | 2.0-3.0x | < 2.0x |
| Debt/Equity | < 2:1 | 2-4:1 | > 4:1 |
| Total debt/EBITDA | < 3.0x | 3.0-5.0x | > 5.0x |
| Revenue trend | Growing | Stable | Declining |
| Profitability | Positive 3yr | Positive with dip | Net loss |
""")

    # ── Corporate Organograms ──
    with st.expander("Corporate Structure — UBO to Asset Level", expanded=True):
        st.markdown("**Veracity Property Holdings — NWL Guarantor**")
        render_svg("guarantor-veracity.svg", "_none.md")

        st.divider()
        st.markdown("**Phoenix Group (TWX Guarantor) — via VH Properties (Mark van Houten)**")
        render_svg("guarantor-phoenix.svg", "_none.md")
        st.caption("Key management: M van Houten, RM O'Sullivan. Cross-ownership: Renovo shareholders include 'Veracity Property Investments'.")

    # ── Outstanding Financial Items Tracker ──
    with st.expander("Outstanding Items & Financial Statement Tracker", expanded=True):
        st.subheader("Financial Statement Inventory")
        _inv_rows = [
            ("**VERACITY GROUP**", "", "", "", "", ""),
            ("VPH Consolidated", "YES", "YES", "YES (simul.)", "MISSING", "Reviewed"),
            ("Aquaside Trading", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("BBP Unit 1 Phase II", "YES (2yr)", "in consol", "—", "MISSING", "Compiled"),
            ("Cornerstone Property (HoldCo)", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("Ireo Project 10 / Chepstow", "YES (2yr)", "in consol", "—", "MISSING", "Audited"),
            ("Mistraline", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("Erf 86 Longmeadow", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("Providence Property", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("Uvongo Falls No 26 [GC]", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("Sun Property [-ve]", "YES (2yr)", "in consol", "—", "MISSING", "Reviewed"),
            ("6 On Kloof (associate)", "YES (2yr)", "in consol", "—", "MISSING", "Audited"),
            ("Manappu Investments (associate)", "**MISSING**", "**MISSING**", "—", "MISSING", "—"),
            ("VPI (sibling, dev assets)", "**MISSING**", "**MISSING**", "—", "MISSING", "—"),
            ("VI (sibling, divestments)", "**MISSING**", "**MISSING**", "—", "MISSING", "—"),
            ("VHIT (Trust)", "**MISSING**", "**MISSING**", "—", "MISSING", "—"),
            ("", "", "", "", "", ""),
            ("**PHOENIX GROUP**", "", "", "", "", ""),
            ("VH Properties (Pty) Ltd", "**MISSING**", "**MISSING**", "**MISSING**", "MISSING", "—"),
            ("Phoenix Specialist (dormant)", "YES (2yr)", "—", "—", "—", "Reviewed"),
            ("Phoenix Prop Fund SA (HoldCo)", "YES (2yr)", "—", "—", "—", "Reviewed"),
            ("Ridgeview Centre [GC, -ve]", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Brackenfell Corner [-ve]", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Chartwell Corner [GC, -ve]", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Jukskei Meander", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Olivedale Corner [-ve]", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Madelief Shopping Centre", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("PRAAM (Asset Mgmt)", "YES (2yr)", "—", "—", "MISSING", "Reviewed"),
            ("Renovo Property Fund (HoldCo)", "YES (2yr)", "—", "—", "—", "Reviewed"),
            ("Chartwell Co-Owner (pass-thru)", "YES (2yr)", "—", "—", "—", "Reviewed"),
            ("Silva Terrace (50%)", "**MISSING**", "**MISSING**", "—", "—", "—"),
            ("Trillium Holdings 1", "**MISSING**", "**MISSING**", "**MISSING**", "—", "—"),
        ]
        _render_fin_table(_inv_rows, ["Entity", "FY2025", "FY2024", "FY2023", "Mgmt Accts", "AFS Type"])
        st.caption("YES (2yr) = current + prior year in same document. 'in consol' = prior year visible in VPH consolidated.")

        st.divider()
        st.subheader("Outstanding Items for Mark van Houten")
        _oi_rows = [
            ("1", "VH Properties 3yr audited AFS", "CRITICAL", "TWX guarantor entity — zero financials", "Mark vH"),
            ("2", "VHIT Trust deed + financials", "CRITICAL", "ECA KYC/compliance — UBO documentation", "Mark vH"),
            ("3", "VPH Management Accounts (post Feb 2025)", "HIGH", "Mark said 'mid March 2025' — overdue", "Mark vH / KCE"),
            ("4", "Phoenix Group consolidated AFS", "HIGH", "No group-level consolidation exists", "Mark vH / KCE"),
            ("5", "VPI (sibling) financials", "MEDIUM", "Development assets entity, may need for trust picture", "Mark vH / KCE"),
            ("6", "VI (sibling) financials", "MEDIUM", "Divestment entity, may need for trust picture", "Mark vH / KCE"),
            ("7", "Manappu Investments AFS", "MEDIUM", "Providence sub (20%), 50 properties in Tyrwhitt", "Mark vH / KCE"),
            ("8", "Silva Terrace AFS", "MEDIUM", "Phoenix sub (50%), no financials at all", "Mark vH / KCE"),
            ("9", "Trillium Holdings 1 financials", "MEDIUM", "Co-shareholder of Phoenix Specialist + Renovo", "Mark vH"),
            ("10", "Management commentary / write-ups", "HIGH", "Business description, strategy per entity", "Mark vH"),
            ("11", "ECA KYC documents", "MEDIUM", "Robbert flagged — needed for due diligence phase", "Mark vH"),
            ("12", "Digital organogram (formal)", "LOW", "Binary .docx exists — needs clean version", "NexusNovus"),
        ]
        _render_fin_table(_oi_rows, ["#", "Item", "Priority", "Notes", "Owner"])

        st.divider()
        st.subheader("Key Risks & Cross-References")
        st.error("""
**Correlated Guarantor Risk:** Mark van Houten provides guarantees from two of his own entities
(VPH for NWL, VH Properties/Phoenix for TWX) for two different subsidiaries in the same SCLCA transaction.
If Mark faces financial distress, both guarantees fail simultaneously.
""")
        st.warning("""
**Cross-ownership:** Renovo Property Fund (Phoenix Group) lists "Veracity Property Investments" as a shareholder.
This creates a financial link between the two guarantor groups that must be disclosed to the ECA.
""")
        st.info("""
**Email thread summary (Feb-Mar 2025, Robbert Zappeij ↔ Mark van Houten):**
- VPH confirmed as NWL guarantor (was initially VI, restructured due to weak financials)
- VHIT = VPH + VPI + VI only — no other entities under the trust
- VPH/VPI/VI are financially and operationally independent (Mark confirmed)
- Robbert specifically wants to control the narrative to Atradius — provide the ECA image, don't let them draw their own conclusions
- Simulated FY2023 consolidation for VPH provided (based on pre-restructure entity AFS)
- Mark committed to management accounts "mid March 2025", group AFS "mid April", consolidated "end April"
""")

    _ga_tab1, _ga_tab2 = st.tabs(["Veracity Property Holdings (NWL)", "VH Properties / Phoenix (TWX)"])

    # ================================================================
    # TAB 1: Veracity Property Holdings (NWL Guarantor)
    # ================================================================
    with _ga_tab1:
        st.subheader("Veracity Property Holdings (Pty) Ltd")
        st.caption("NWL Guarantor — Guarantee amount: EUR 10,655,818 (R213.1M at FX 20)")

        _v1, _v2, _v3, _v4 = st.columns(4)
        _v1.metric("Total Assets", "R746.5M", "+9.4% YoY")
        _v2.metric("Investment Property", "R692.9M", "+11.8% YoY")
        _v3.metric("D/E Ratio", "13.0x", "10.0x prior", delta_color="inverse")
        _v4.metric("Interest Cover", "0.73x", "1.34x prior", delta_color="inverse")
        _v5, _v6, _v7, _v8 = st.columns(4)
        _v5.metric("Revenue", "R72.5M", "+11.9% YoY")
        _v6.metric("Operating Profit", "R42.9M", "-25.8% YoY", delta_color="inverse")
        _v7.metric("Net Profit/(Loss)", "(R9.3M)", "vs R15.3M prior", delta_color="inverse")
        _v8.metric("Total Equity", "R53.4M", "-14.0% YoY", delta_color="inverse")

        _ga_fig = go.Figure()
        _ga_years = ["FY2023", "FY2024", "FY2025"]
        _ga_fig.add_trace(go.Bar(x=_ga_years, y=[62.2, 64.8, 72.5], name="Revenue", marker_color="#3B82F6"))
        _ga_fig.add_trace(go.Bar(x=_ga_years, y=[38.0, 57.8, 42.9], name="Op. Profit", marker_color="#10B981"))
        _ga_fig.add_trace(go.Bar(x=_ga_years, y=[-31.4, -43.2, -58.5], name="Finance Costs", marker_color="#EF4444"))
        _ga_fig.add_trace(go.Scatter(x=_ga_years, y=[5.7, 15.3, -9.3], name="Net Profit", mode="lines+markers",
                                     line=dict(color="#F59E0B", width=3)))
        _ga_fig.update_layout(barmode="group", height=350, yaxis_title="R millions",
                              margin=dict(l=10, r=10, t=30, b=10),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
        st.plotly_chart(_ga_fig, use_container_width=True)
        st.caption("FY2024 peak year (R15.3M profit). FY2025 swing to loss driven by 37% finance cost increase.")

        st.divider()
        st.subheader("ECA Rating")
        _ver_rating = [
            ("Credit rating", "Unrated", "Marginal"),
            ("Net worth vs guarantee", "0.25x (R53.4M / R213.1M)", "Marginal"),
            ("Interest coverage", "FY25: 0.73x, FY24: 1.34x, FY23: 1.21x", "Marginal (deteriorating)"),
            ("Debt/Equity", "FY25: 13.0x, FY24: 10.0x, FY23: 11.2x", "Marginal"),
            ("Total debt/EBITDA", "15.7x (R672M / R42.9M)", "Marginal"),
            ("Revenue trend", "Growing 3yr CAGR +8% (R62M to R73M)", "Acceptable"),
            ("Profitability", "FY25: Loss (R9.3M), FY24: R15.3M, FY23: R5.7M", "Marginal (1 of 3 loss)"),
            ("Asset backing", "R693M property (3.25x guarantee on gross)", "Acceptable"),
        ]
        _render_fin_table(_ver_rating, ["Metric", "Veracity Value (3yr)", "Rating"])
        st.warning("**Overall: Marginal** — 5 of 8 metrics below acceptable. Guarantee relies on asset recovery value (R693M property portfolio), not income coverage.")

        with st.expander("Property Portfolio (8 properties FY2025)", expanded=False):
            _prop_data = [
                ("Morningside Ext 5", "Uvongo Falls No 26 (50%)", "R336,919,312", "Residential development"),
                ("Mastiff Sandton", "Mistraline (via VPH)", "R160,500,000", "Commercial + PV solar"),
                ("Bellville Cape Town", "New in FY2025", "R74,200,000", "Commercial acquisition"),
                ("Tyrwhitt Sections", "Providence Property (100%)", "R49,640,700", "Residential"),
                ("Longmeadow Gauteng", "Erf 86 Longmeadow (100%)", "R46,723,682", "Commercial + PV solar"),
                ("Saxonwold JHB (4 units)", "Aquaside Trading (100%)", "R17,600,000", "Residential rental"),
                ("George Cape Town", "Aquaside Trading (100%)", "R4,500,000", "Residential"),
                ("Randpark Ridge", "BBP Unit 1 Phase 2 (100%)", "R2,803,913", "Commercial"),
            ]
            _render_fin_table(_prop_data, ["Property", "Held By", "FY2025 (ZAR)", "Type"])
            st.caption("Total: R692.9M. Morningside + Mastiff = 71.8% concentration.")

        with st.expander("Lender Profile (11 lenders)", expanded=False):
            _lend_data = [
                ("Fedgroup", "R367,295,079", "54.7%"), ("BMG", "R108,483,230", "16.1%"),
                ("ABSA", "R89,619,169", "13.3%"), ("Nedbank", "R41,807,616", "6.2%"),
                ("M van Houten (Director)", "R27,664,182", "4.1%"), ("Vukile", "R16,337,481", "2.4%"),
                ("RSAD", "R9,621,027", "1.4%"), ("VH Group", "R6,455,000", "1.0%"),
                ("Randpark Ridge", "R2,803,913", "0.4%"), ("T Stamer", "R2,688,450", "0.4%"),
                ("K Lang", "R500,000", "0.1%"), ("Arrowana", "R1,210,779", "0.2%"),
            ]
            _render_fin_table(_lend_data, ["Lender", "Amount (ZAR)", "% of Total"])
            st.caption("Fedgroup = 55% of all borrowings. Significant single-lender concentration.")

        with st.expander("Consolidated Financial Statements (FY2023-FY2025)", expanded=False):
            _bs_tab, _pl_tab, _cf_tab = st.tabs(["Balance Sheet", "P&L", "Cash Flow"])
            with _bs_tab:
                _bs_data = [
                    ("**Non-Current Assets**", "", "", ""),
                    ("Investment property", "R692,887,607", "R619,963,925", "R564,992,692"),
                    ("Loans to group / other financial", "R46,900,198", "R42,694,743", "R5,001,496"),
                    ("**Total non-current assets**", "**R740,139,394**", "**R662,657,683**", "**R569,995,223**"),
                    ("**Current Assets**", "", "", ""),
                    ("Trade & other receivables", "R4,992,125", "R16,976,709", "R16,035,972"),
                    ("Cash & cash equivalents", "R1,399,686", "R2,729,745", "R6,488,455"),
                    ("**Total Assets**", "**R746,531,205**", "**R682,364,137**", "**R592,525,617**"),
                    ("", "", "", ""),
                    ("**Equity**", "", "", ""),
                    ("Share capital + Accumulated profit", "R34,177,186", "R32,287,388", "R120"),
                    ("Non-controlling interest", "R19,197,274", "R29,755,762", "R48,473,495"),
                    ("**Total Equity**", "**R53,374,460**", "**R62,043,150**", "**R48,473,615**"),
                    ("**Non-Current Liabilities**", "", "", ""),
                    ("Other financial liabilities", "R671,682,013", "R572,400,247", "R522,219,494"),
                    ("Shareholders loan", "—", "R20,044,150", "R3,403,126"),
                    ("Deferred tax", "R3,826,656", "R9,200,184", "R8,622,722"),
                    ("**Current Liabilities**", "", "", ""),
                    ("Trade & other payables", "R13,887,051", "R15,431,589", "R8,591,328"),
                    ("Provisions + Bank overdraft", "R3,760,821", "R3,241,852", "R1,215,332"),
                    ("**Total Equity & Liabilities**", "**R746,531,205**", "**R682,364,137**", "**R592,525,617**"),
                ]
                _render_fin_table(_bs_data, ["Line Item", "FY2025", "FY2024", "FY2023"])
            with _pl_tab:
                _pl_data = [
                    ("Revenue", "R72,488,610", "R64,752,125", "R62,170,435"),
                    ("Other income (incl. FV)", "R9,968,295", "R29,037,610", "R7,398,439"),
                    ("Operating expenses", "(R39,580,457)", "(R35,945,459)", "(R31,602,751)"),
                    ("**Operating profit**", "**R42,876,448**", "**R57,844,276**", "**R37,966,123**"),
                    ("Investment revenue", "R869,068", "R1,310,422", "R908,718"),
                    ("Finance costs", "(R58,519,409)", "(R43,220,057)", "(R31,402,269)"),
                    ("PBT", "(R14,773,893)", "R15,934,641", "R7,472,572"),
                    ("Taxation", "R5,459,940", "(R609,939)", "(R1,743,656)"),
                    ("**Profit/(Loss)**", "**(R9,313,953)**", "**R15,324,702**", "**R5,728,916**"),
                ]
                _render_fin_table(_pl_data, ["Line Item", "FY2025", "FY2024", "FY2023"])
            with _cf_tab:
                _cf_data = [
                    ("Cash from operations", "R45,652,305", "R37,177,452", "R27,870,529"),
                    ("Interest income", "R869,068", "R1,310,422", "R908,718"),
                    ("Finance costs paid", "(R58,519,291)", "(R43,220,055)", "(R31,402,269)"),
                    ("**Net operating**", "**(R12,030,979)**", "**(R4,755,726)**", "**(R2,675,315)**"),
                    ("Purchase of inv property", "(R64,637,218)", "(R43,602,629)", "(R46,765,600)"),
                    ("Proceeds from sale", "R970,584", "R13,863,461", "—"),
                    ("**Net investing**", "**(R63,666,634)**", "**(R29,740,178)**", "**(R46,765,600)**"),
                    ("Net movement loans", "R74,048,451", "R28,998,572", "R50,699,698"),
                    ("**Net cash movement**", "**(R1,649,162)**", "**(R5,497,332)**", "**R1,258,783**"),
                ]
                _render_fin_table(_cf_data, ["Line Item", "FY2025", "FY2024", "FY2023"])

        # ── Veracity Subsidiary Financials (nested, from L4 JSONs) ──
        _ver_subs = _load_guarantor_jsons("veracity 2025 financials")
        _guar_cfg_ga = _load_guarantor_config()
        _ver_group_ga = _guar_cfg_ga.get("groups", {}).get("veracity", {})
        _ver_holding_ga = _ver_group_ga.get("holding", {})
        if _ver_subs:
            st.divider()
            st.subheader(f"Subsidiary Company Financials ({len(_ver_subs)} entities)")
            _render_sub_summary_and_toggles(_ver_subs, "ver_summ")
            if _ver_holding_ga:
                with st.expander("Nested Corporate Hierarchy — Veracity", expanded=False):
                    st.caption("Financial statements organised by ownership hierarchy (parent → child)")
                    for _child_ga in _ver_holding_ga.get("children", []):
                        _render_nested_financials(_child_ga, _ver_subs, "ver")

        # ── Email Q&A ──
        if _guar_cfg_ga:
            st.divider()
            _render_email_qa(_guar_cfg_ga)

        st.divider()
        st.subheader("ECA View")
        st.info("""
**Marginal guarantor** from a traditional credit perspective. 13x leverage (FY2025) and sub-1.0x interest cover are red flags.
However, the R693M investment property portfolio (growing +9% CAGR) provides substantial asset backing (3.25x guarantee cover on gross basis).

**3-Year Trajectory:** Revenue growing steadily (+8% CAGR), but finance costs outpacing (+37% FY24→FY25).
FY2024 was profitable (R15.3M PAT with R29M fair value gains), but FY2025 swung to R9.3M loss as finance costs hit R58.5M.

**Recovery analysis:** Even at a 50% haircut, portfolio worth R346M — but subordinated to R672M secured lenders (Fedgroup R367M, ABSA R90M, Nedbank R42M), leaving zero residual for unsecured guarantee.

**ECA context (per Robbert Zappeij, Mar 2025):** ECA requires 2 years of audited financial statements. VPH restructured from VH Investments Trust in Q4/2024 (statutory date 01/03/2023). Simulated FY2023 consolidation provided. KCE confirmed FY2024 and FY2025 now available.

**Recommendation:** Guarantee needs support via (a) ring-fenced property pledge, (b) second-ranking security over unencumbered assets, or (c) balance sheet restructuring. Alternatively, size to M36 exposure (~EUR 5.2M) rather than full EUR 10.66M.
""")

    # ================================================================
    # TAB 2: VH Properties / Phoenix Group (TWX Guarantor)
    # ================================================================
    with _ga_tab2:
        st.subheader("VH Properties / Phoenix Group")
        st.caption("TWX Guarantor — Guarantee amount: EUR 2,032,571 (R40.7M at FX 20)")
        st.markdown("**Structure:** VH Properties holds 40% in Phoenix Group, which owns 100% of the underlying retail centre assets.")

        _phx_subs = _load_guarantor_jsons("Phoenix group")
        _twx_ic_zar2 = 2_032_571 * FX_RATE

        # Compute group EBITDA from individual property JSONs
        _phx_opco_keys = {
            "RidgeviewCentre_2025_structured": ("Ridgeview Centre", 0.40),
            "BrackenfellCorner_2025_structured": ("Brackenfell Corner", 0.40),
            "ChartwellCorner_2025_structured": ("Chartwell Corner", 0.20),
            "JukskeiMeander_2025_structured": ("Jukskei Meander", 0.40),
            "MadeliefShoppingCentre_2025_structured": ("Madelief", 0.40),
            "OlivedaleCorner_2025_structured": ("Olivedale Corner", 0.40),
        }
        _phx_detail = []
        _phx_total_ebitda = 0
        _phx_total_attr = 0
        for pk, (pname, pown) in _phx_opco_keys.items():
            pd_data = _phx_subs.get(pk, {})
            ppl = pd_data.get("statement_of_comprehensive_income", {})
            p_pat = None
            for ppk in ["profit_loss_for_the_year", "profit_for_the_year", "loss_for_the_year"]:
                p_pat = _gval(ppl, ppk)
                if p_pat is not None:
                    break
            p_fc = abs(_gval(ppl, "finance_costs") or 0)
            p_ebitda = (p_pat or 0) + p_fc
            p_attr = p_ebitda * pown
            _phx_detail.append((pname, p_pat or 0, p_fc, p_ebitda, pown, p_attr))
            _phx_total_ebitda += p_ebitda
            _phx_total_attr += p_attr

        _p1, _p2, _p3 = st.columns(3)
        _p1.metric("Group EBITDA", _fmtr(_phx_total_ebitda, millions=True))
        _p2.metric("Attributable", _fmtr(_phx_total_attr, millions=True))
        _cov = (_phx_total_attr * 2 / _twx_ic_zar2) if _twx_ic_zar2 > 0 else 0
        _p3.metric("2yr Coverage", f"{_cov:.2f}x")

        st.divider()
        st.subheader("Property-Level EBITDA (from AFS)")
        _phx_rows = [
            (p, _fmtr(npl), _fmtr(fc), _fmtr(eb), f"{ow:.0%}", _fmtr(att))
            for p, npl, fc, eb, ow, att in _phx_detail
        ] + [("**Total**", "", "", f"**{_fmtr(_phx_total_ebitda)}**", "", f"**{_fmtr(_phx_total_attr)}**")]
        _render_fin_table(_phx_rows, ["Property", "PAT (R)", "Finance (R)", "EBITDA (R)", "Own %", "Attributable (R)"])
        st.caption("Computed from individual entity AFS structured JSONs")

        st.divider()
        # ECA Rating — computed from actual data
        _phx_total_assets = sum(_gval(_phx_subs.get(k, {}).get("statement_of_financial_position", {}), "assets", "total_assets") or 0 for k in _phx_opco_keys)
        _phx_total_equity = sum(_gval(_phx_subs.get(k, {}).get("statement_of_financial_position", {}), "equity_and_liabilities", "equity", "total_equity") or 0 for k in _phx_opco_keys)
        _phx_total_debt = sum(
            (_gval(_phx_subs.get(k, {}).get("statement_of_financial_position", {}), "equity_and_liabilities", "non_current_liabilities", "other_financial_liabilities") or 0)
            for k in _phx_opco_keys)
        _phx_total_rev = sum(_gval(_phx_subs.get(k, {}).get("statement_of_comprehensive_income", {}), "revenue") or 0 for k in _phx_opco_keys)
        _phx_de = abs(_phx_total_debt / _phx_total_equity) if _phx_total_equity != 0 else float('inf')
        _phx_debt_ebitda = _phx_total_debt / _phx_total_ebitda if _phx_total_ebitda > 0 else float('inf')
        _phx_nw_guar = _phx_total_equity / _twx_ic_zar2 if _twx_ic_zar2 > 0 else 0

        st.subheader("ECA Rating")
        _phx_rating = [
            ("Credit rating", "Unrated", "Marginal"),
            ("Net worth vs guarantee", f"{_phx_nw_guar:.2f}x ({_fmtr(_phx_total_equity, True)} / R{_twx_ic_zar2/1e6:.1f}M)", "Marginal" if _phx_nw_guar < 1.5 else "Acceptable"),
            ("Debt/Equity", f"{_phx_de:.1f}x", "Marginal" if _phx_de > 4 else "Acceptable"),
            ("Total debt/EBITDA", f"{_phx_debt_ebitda:.1f}x", "Marginal" if _phx_debt_ebitda > 5 else "Acceptable"),
            ("Revenue (group)", _fmtr(_phx_total_rev, True), "Acceptable"),
            ("Total assets (group)", _fmtr(_phx_total_assets, True), "Acceptable"),
            ("Profitability", f"EBITDA {_fmtr(_phx_total_ebitda, True)}", "Acceptable"),
        ]
        _render_fin_table(_phx_rating, ["Metric", "Phoenix Group Value", "Rating"])
        _marginal_n = sum(1 for _, _, r in _phx_rating if "Marginal" in r)
        if _marginal_n >= 4:
            st.warning(f"**Overall: Marginal** — {_marginal_n}/{len(_phx_rating)} metrics below acceptable.")
        elif _marginal_n >= 2:
            st.info(f"**Overall: Acceptable (with caveats)** — {_marginal_n}/{len(_phx_rating)} metrics marginal.")
        else:
            st.success(f"**Overall: Acceptable** — {len(_phx_rating) - _marginal_n}/{len(_phx_rating)} acceptable or strong.")

        with st.expander("Guarantee Capacity Analysis", expanded=True):
            _gc_data = [
                ("Phoenix Group EBITDA", "", _fmtr(_phx_total_ebitda)),
                ("Attributable (mixed ownership)", "", f"**{_fmtr(_phx_total_attr)}**"),
                ("2-year cash generation", "x 2", f"**{_fmtr(_phx_total_attr * 2)}**"),
                ("TWX IC loan (EUR)", "", "EUR 2,032,571"),
                ("TWX IC loan (ZAR)", "", _fmtr(_twx_ic_zar2)),
                ("**Coverage ratio**", "", f"**{_cov:.2f}x**"),
            ]
            _render_fin_table(_gc_data, ["Step", "Factor", "Value"])

        # ── Phoenix Group Subsidiary Financials (nested, from L4 JSONs) ──
        _phx_group_ga = _guar_cfg_ga.get("groups", {}).get("phoenix", {})
        _phx_holding_ga = _phx_group_ga.get("holding", {})
        if _phx_subs:
            st.divider()
            st.subheader(f"Subsidiary Company Financials ({len(_phx_subs)} entities)")
            _render_sub_summary_and_toggles(_phx_subs, "phx_summ")
            if _phx_holding_ga:
                with st.expander("Nested Corporate Hierarchy — Phoenix Group", expanded=False):
                    st.caption("Financial statements organised by ownership hierarchy (parent → child)")
                    for _child_phx_ga in _phx_holding_ga.get("children", []):
                        _render_nested_financials(_child_phx_ga, _phx_subs, "phx")

        st.divider()
        st.subheader("ECA View")
        st.success("""
**Credible but lean guarantor** for TWX. Coverage on 2-year attributable EBITDA is acceptable.

**Strengths:** (1) Small guarantee quantum (EUR 2.03M), (2) Recurring retail income from 6 convenience centres,
(3) Asset-backed with physical property, (4) Stable EBITDA generation.

**Risks:** (1) Ridgeview Centre and Chartwell Corner have going concern doubts, (2) Several entities carry negative equity,
(3) High leverage across the group, (4) Fedgroup is a common lender across both Veracity and Phoenix groups.

**Full subsidiary AFS now available** — 11 entity-level reviewed financial statements loaded above.
""")

# ============================================================
# USER MANAGEMENT PAGE (admin only)
# ============================================================
elif entity == "Users" and _can_manage:
    st.header("User Management")
    st.caption("Add users, manage permissions, and control access to projects and tabs.")

    import bcrypt as _bcrypt

    _um_add, _um_list = st.tabs(["Add User", "Manage Permissions"])

    # --- Tab 1: Add User ---
    with _um_add:
        st.subheader("Register New User")

        # Invite placeholder
        st.info("**Invite by Email** — Coming soon. For now, register users manually below.")

        with st.form("add_user_form", clear_on_submit=True):
            _au_cols = st.columns(2)
            with _au_cols[0]:
                _au_uname = st.text_input("Username*", placeholder="jsmith")
                _au_email = st.text_input("Email*", placeholder="jsmith@example.com")
            with _au_cols[1]:
                _au_fname = st.text_input("First Name*", placeholder="John")
                _au_lname = st.text_input("Last Name*", placeholder="Smith")
            _au_pwd = st.text_input("Password*", type="password")
            _au_pwd2 = st.text_input("Confirm Password*", type="password")

            st.markdown("**Permissions**")
            _au_entity_cols = st.columns(len(ALL_ENTITIES))
            _au_entities = []
            for _i, _ent in enumerate(ALL_ENTITIES):
                with _au_entity_cols[_i]:
                    if st.checkbox(_ent, value=True, key=f"au_ent_{_ent}"):
                        _au_entities.append(_ent)

            st.caption("Tabs")
            _au_tab_cols = st.columns(4)
            _au_tabs = []
            for _i, _tab in enumerate(ALL_TABS):
                with _au_tab_cols[_i % 4]:
                    if st.checkbox(_tab, value=True, key=f"au_tab_{_tab}"):
                        _au_tabs.append(_tab)

            st.caption("Management Pages")
            _au_mgmt_cols = st.columns(4)
            _au_mgmt = []
            for _i, _mp in enumerate(ALL_MGMT_PAGES):
                with _au_mgmt_cols[_i % 4]:
                    if st.checkbox(_mp, value=True, key=f"au_mgmt_{_mp}"):
                        _au_mgmt.append(_mp)

            _au_is_admin = st.checkbox("Can manage users (admin)", value=False, key="au_admin")
            _au_submit = st.form_submit_button("Create User", type="primary")

            if _au_submit:
                if not _au_uname or not _au_email or not _au_pwd:
                    st.error("Username, email, and password are required.")
                elif _au_pwd != _au_pwd2:
                    st.error("Passwords do not match.")
                elif _au_uname in _auth_config['credentials']['usernames']:
                    st.error(f"Username '{_au_uname}' already exists.")
                else:
                    _hashed = _bcrypt.hashpw(_au_pwd.encode(), _bcrypt.gensalt()).decode()
                    _auth_config['credentials']['usernames'][_au_uname] = {
                        'email': _au_email,
                        'first_name': _au_fname,
                        'last_name': _au_lname,
                        'password': _hashed,
                        'roles': ['admin' if _au_is_admin else 'promotor_opco'],
                        'permissions': {
                            'entities': ['*'] if len(_au_entities) == len(ALL_ENTITIES) else _au_entities,
                            'tabs': ['*'] if len(_au_tabs) == len(ALL_TABS) else _au_tabs,
                            'mgmt_pages': ['*'] if len(_au_mgmt) == len(ALL_MGMT_PAGES) else _au_mgmt,
                            'can_manage_users': _au_is_admin,
                        },
                    }
                    _save_users(_auth_config)
                    st.success(f"User **{_au_uname}** created successfully.")
                    st.rerun()

    # --- Tab 2: Manage Permissions ---
    with _um_list:
        st.subheader("Current Users & Permissions")

        _all_users = _auth_config['credentials']['usernames']
        if not _all_users:
            st.info("No users registered yet.")
        else:
            for _uname, _udata in _all_users.items():
                _u_perms = _get_user_permissions(_uname, _auth_config)
                _u_ents = _u_perms.get('entities', ['*'])
                _u_tabs = _u_perms.get('tabs', ['*'])
                _u_admin = _u_perms.get('can_manage_users', False)
                _u_email = _udata.get('email', '')
                _u_role = get_user_role(_uname, _auth_config)

                with st.expander(f"**{_uname}** — {_u_email} · {_u_role}", expanded=False):
                    with st.form(f"perm_form_{_uname}"):
                        st.markdown("**Project Access**")
                        _pe_cols = st.columns(len(ALL_ENTITIES))
                        _new_ents = []
                        for _i, _ent in enumerate(ALL_ENTITIES):
                            with _pe_cols[_i]:
                                _checked = '*' in _u_ents or _ent in _u_ents
                                if st.checkbox(_ent, value=_checked, key=f"pe_{_uname}_{_ent}"):
                                    _new_ents.append(_ent)

                        st.markdown("**Tab Access**")
                        _pt_cols = st.columns(4)
                        _new_tabs = []
                        for _i, _tab in enumerate(ALL_TABS):
                            with _pt_cols[_i % 4]:
                                _checked = '*' in _u_tabs or _tab in _u_tabs
                                if st.checkbox(_tab, value=_checked, key=f"pt_{_uname}_{_tab}"):
                                    _new_tabs.append(_tab)

                        st.markdown("**Management Page Access**")
                        _u_mgmt = _u_perms.get('mgmt_pages', ['*'])
                        _pm_cols = st.columns(4)
                        _new_mgmt = []
                        for _i, _mp in enumerate(ALL_MGMT_PAGES):
                            with _pm_cols[_i % 4]:
                                _checked = '*' in _u_mgmt or _mp in _u_mgmt
                                if st.checkbox(_mp, value=_checked, key=f"pm_{_uname}_{_mp}"):
                                    _new_mgmt.append(_mp)

                        _new_admin = st.checkbox(
                            "Can manage users (admin)",
                            value=_u_admin,
                            key=f"pa_{_uname}",
                        )

                        _pf_submit = st.form_submit_button("Save Permissions")
                        if _pf_submit:
                            _auth_config['credentials']['usernames'][_uname]['permissions'] = {
                                'entities': ['*'] if len(_new_ents) == len(ALL_ENTITIES) else _new_ents,
                                'tabs': ['*'] if len(_new_tabs) == len(ALL_TABS) else _new_tabs,
                                'mgmt_pages': ['*'] if len(_new_mgmt) == len(ALL_MGMT_PAGES) else _new_mgmt,
                                'can_manage_users': _new_admin,
                            }
                            _save_users(_auth_config)
                            st.success(f"Permissions updated for **{_uname}**.")
                            st.rerun()

# Footer
st.markdown("---")
st.caption("NexusNovus | Catalytic Assets | Financial Model v1.0")
