"""Legacy annual row builders — DEAD CODE.

Moved here from cashflow.py, balance_sheet.py, and entity builders.
Kept ONLY as reference for reading old logic. NOT imported anywhere.
Do NOT call these functions.
"""

# Legacy functions that lived here:
# - build_annual_cf_fields()      — was in engine/cashflow.py
# - patch_annual_from_waterfall() — was in engine/cashflow.py
# - build_annual_bs_fields()      — was in engine/balance_sheet.py
# - _build_annual_rows()          — was in entities/{nwl,lanred,timberworx}.py
# - aggregate_to_annual()         — was in engine/waterfall.py (replaced by to_annual in engine/loop.py)
#
# All replaced by build_annual() in engine/loop.py (single pass, single source of truth).
