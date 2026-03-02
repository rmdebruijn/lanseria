"""Cash flow — legacy module, functions moved to engine/loop.py build_annual().

build_annual_cf_fields() and patch_annual_from_waterfall() are DEAD.
CF fields are now derived inside build_annual() (engine/loop.py) from
loop output aggregated via to_annual(). Single pass, no patching.
"""
