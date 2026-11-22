"""Deck v5 Phase 6: demo rehearsal, AAES (A0) and AAES+ (AP_RRRL) side by side, 3 runs per scenario.

Run from Sources/ with the backend at http://127.0.0.1:8000:  python scripts/deck_v5_demo.py
-> Report/slides/deck_v4/demo_trials_v5.csv. Same procedure and fields as deck_v4_demo.py (run 1 cold after unloading
the models, runs 2-3 warm; reply types by evaluator v2); only the methods, the scenarios and the output file change.
"""

from __future__ import annotations

import deck_v4_demo as demo

demo.METHODS = {"A0": "A0_AAES", "AAES+": "AP_RRRL"}
demo.SCENARIOS = [s for s in demo.SCENARIOS if s[0] in ("S5", "S2")]  # winter school (dev T14-042); Scenario 2 (counseling)
demo.OUT = demo.OUT.with_name("demo_trials_v5.csv")

if __name__ == "__main__":
    raise SystemExit(demo.main())
