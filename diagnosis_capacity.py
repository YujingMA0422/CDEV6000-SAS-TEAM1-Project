"""Diagnosis-level (service-line) bed-demand references from the unchanged DES.

How it works
------------
* Uses ``simulation._run_one`` exactly as ``simulation.needed_beds`` does for its baseline: unlimited beds,
  120 simulated days, 3 replications, seeds ``seed + 500 + r``, no interventions, annual-average pattern.
* For one diagnosis, the run is given an in-memory copy of the calibration in which the arrival rates of the
  other diagnoses are set to zero. Only that diagnosis's admissions (and the return stays they generate) are
  simulated. ``simulation.py`` and ``calibration.npz`` are not changed.
* With unlimited beds there is no queue, so patients never affect each other: a diagnosis-only run reproduces
  that diagnosis's share of the hospital-wide unrestricted run. Its 95th-percentile daily occupancy is therefore
  the busy-day bed reference IF that service line were planned on its own.
* These references are NOT additive. The sum of the three is larger than the pooled hospital reference because
  busy days of different service lines do not all coincide (the benefit of sharing one bed pool).
* Not a staffed-bed count, not a department, not a guarantee of zero waiting; historical 2011-12 patient mix.
"""
from functools import lru_cache

import numpy as np

import simulation as S

DAYS, REPS, SEED = 120, 3, 2026


def _calibration_for(diagnosis=None):
    d = dict(S.calibration())
    if diagnosis is None:
        return d
    keep = np.array([str(g).split("|")[0] == diagnosis for g in d["groups"]], dtype=float)
    d["rates"] = d["rates"] * keep[None, :]
    if "rates_m" in d:
        d["rates_m"] = d["rates_m"] * keep[None, None, :]
    return d


@lru_cache(maxsize=8)
def busy_day_reference(diagnosis=None, days=DAYS, reps=REPS, seed=SEED, season="Annual average"):
    """Mean (over replications) of the 95th-percentile and average daily occupancy, unlimited beds, baseline."""
    d = _calibration_for(diagnosis)
    rows = [S._run_one(d, seed + 500 + r, days, S.UNLIMITED, S.WARMUP_DAYS, 0, 0, 0, "CHF|3", "All ages", season,
                       intervene=False) for r in range(reps)]
    return dict(p95=float(np.mean([r["beds_needed"] for r in rows])),
                avg=float(np.mean([r["avg_occupied"] for r in rows])))


def service_line_references(diagnoses=("AMI", "CHF", "COPD")):
    pooled = busy_day_reference(None)
    lines = {dx: busy_day_reference(dx) for dx in diagnoses}
    return dict(pooled=pooled, lines=lines, sum_p95=sum(v["p95"] for v in lines.values()))
