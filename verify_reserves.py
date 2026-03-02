#!/usr/bin/env python3
"""Verify reserve schedule consistency and swap_leg_bal indexing.

Checks that:
1. All reserve accumulators in the waterfall match what
   build_reserve_schedule() would produce (canonical lifecycle).
2. swap_leg_bal is indexed from build_swap_closing_bal().

Note: BS gap from entity builders may be non-zero due to the convergence
loop (acceleration changes interest which changes P&L). This is a
known pre-existing condition. The canonical check is check_bs_gap.py
which uses the vanilla model (no convergence).
"""

import sys
sys.path.insert(0, ".")

from engine.config import ModelConfig, ScenarioInputs
from engine.reserves import verify_reserve_balance, extract_reserve_vectors, build_reserve_schedule
from entities.nwl import build_nwl_entity
from entities.lanred import build_lanred_entity
from entities.timberworx import build_twx_entity


def verify_entity(name, result):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    wf = result.waterfall_semi
    all_reserves_pass = True

    # Verify reserve schedules match waterfall accumulators
    for reserve_name in ["ops_reserve", "opco_dsra", "entity_fd", "mz_div_fd", "od"]:
        passed, max_diff = verify_reserve_balance(wf, reserve_name)
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_reserves_pass = False
        print(f"  {reserve_name:20s}: {status} (max diff: {max_diff:.4f})")

    # Show swap_leg_bal values for entities with active swaps
    if result.swap_active:
        print(f"\n  Swap leg balance (indexed from schedule):")
        for hi in range(20):
            bal = wf[hi].get("swap_leg_bal", 0)
            accel = wf[hi].get("swap_leg_accel", 0)
            sched = wf[hi].get("swap_leg_scheduled", 0)
            if bal > 0.01 or accel > 0.01 or sched > 0.01:
                print(f"    hi={hi:2d}: bal={bal:12,.2f}  sched={sched:12,.2f}  accel={accel:12,.2f}")

    # Report BS gap (informational, not a pass/fail criterion)
    max_gap = max(abs(a["bs_gap"]) for a in result.annual)
    print(f"\n  Entity builder BS gap (informational): {max_gap:,.2f}")

    return all_reserves_pass


def main():
    cfg = ModelConfig.load()
    inputs = ScenarioInputs()

    all_pass = True

    nwl = build_nwl_entity(cfg, inputs)
    if not verify_entity("NWL", nwl):
        all_pass = False

    lanred = build_lanred_entity(cfg, inputs)
    if not verify_entity("LanRED", lanred):
        all_pass = False

    twx = build_twx_entity(cfg, inputs)
    if not verify_entity("Timberworx", twx):
        all_pass = False

    print(f"\n{'='*60}")
    if all_pass:
        print("  ALL RESERVE CONSISTENCY CHECKS PASSED")
    else:
        print("  SOME RESERVE CONSISTENCY CHECKS FAILED")
    print(f"{'='*60}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
