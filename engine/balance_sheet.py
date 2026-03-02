"""Balance sheet — legacy module, functions moved to engine/loop.py build_annual().

build_annual_bs_fields() is DEAD.
BS fields are now derived inside build_annual() (engine/loop.py) from
loop output aggregated via to_annual(). Single pass, no patching.
"""
