"""Daily-resolution, historical-calibrated, pooled-bed exploratory DES.

What changed versus the first version
-------------------------------------
* Warm-up: the hospital starts "already busy" (45 days run before Day 1) instead of empty.
* Seasonal demand: optional calendar-month x weekday arrival rates (needs the new calibration.npz).
* Third lever: readmission reduction.  Demand / LOS / readmission levers can be shown one at a time.
* Paired patient sampling: age, LOS and in-hospital death come from the *same* historical encounter,
  so the age filter and the "alive at discharge" rule are consistent with LOS.
* LOS reduction is applied only to patients who survived to discharge (deaths are not "shortened").
* Uncertainty: 95% confidence intervals and paired differences versus baseline.
* "Beds needed": 95th-percentile daily occupancy with unlimited beds.
* validate(): runs the model over all 366 days of the 2011-12 historical year.
* Readmissions only follow survivals; contradiction flags are preserved in the calibration.
* Waiting only includes requests arriving during the chosen horizon; unresolved tail waits are NA.
* Zero-day historical stays require one bed-day in this daily-resolution model.

No mortality model, triage, wards or causal/clinical recommendation.  Every feature that needs a new
calibration key falls back gracefully if the key is missing (old calibration.npz).
"""
from collections import deque
from functools import lru_cache
from pathlib import Path
import math
import numpy as np
import pandas as pd

TAIL_DAYS = 140          # extra days after the window so that late returns are still processed
WARMUP_DAYS = 45
UNLIMITED = 10 ** 9
MONTHS = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
SEASONS = ['Annual average'] + MONTHS
_MONTH_NUM = {m: n for m, n in zip(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], range(1, 13))}
_T975 = {1: 12.706204736, 2: 4.30265273, 3: 3.182446305, 4: 2.776445105, 5: 2.570581836, 6: 2.446911851, 7: 2.364624252, 8: 2.306004135, 9: 2.262157163, 10: 2.228138852, 11: 2.20098516, 12: 2.17881283, 13: 2.160368656, 14: 2.144786688, 15: 2.131449546, 16: 2.119905299, 17: 2.109815578, 18: 2.10092204, 19: 2.093024054, 20: 2.085963447, 21: 2.079613845, 22: 2.073873068, 23: 2.06865761, 24: 2.063898562, 25: 2.059538553, 26: 2.055529439, 27: 2.051830516, 28: 2.048407142, 29: 2.045229642, 30: 2.042272456}



@lru_cache(maxsize=1)
def calibration():
    p = Path(__file__).with_name('calibration.npz')
    with np.load(p, allow_pickle=False) as data:
        return {k: data[k] for k in data.files}


def has(key):
    return key in calibration()


def t975(n):
    """95% two-sided Student-t quantile (df = n-1)."""
    df = max(int(n)-1, 1)
    if df in _T975:
        return _T975[df]
    # Cornish-Fisher approximation for df>=31, accurate to <.001 here.
    z = 1.959963984540054
    return (z + (z**3+z)/(4*df)
            + (5*z**5+16*z**3+3*z)/(96*df**2)
            + (3*z**7+19*z**5+17*z**3-15*z)/(384*df**3))



def season_start(season, d):
    """Calendar date of simulation Day 1."""
    if season == 'Annual average' or 'rates_m' not in d:
        return pd.Timestamp(str(d['start']))
    m = _MONTH_NUM[season]
    return pd.Timestamp(2011 if m >= 7 else 2012, m, 1)


def _run_one(d, seed, days, beds, warmup, demand, los_reduction, readmit_reduction, label, age, season,
             intervene=True, collect=False, readmit_scope='hospital'):
    """One replication.  `intervene=False` gives the baseline (all levers off).

    readmit_scope: 'hospital' (original behaviour) reduces every group's return probability;
    'group' reduces it only for initial admissions of the target group in the selected age band
    (the same patients eligible for the LOS change). Eligibility is fixed at admission (age at the
    initial admission, as in the data) and carried with the patient.
    v4.6: each new patient's readmission draws (decision, delay, return LOS) are made at admission, so the
    number and order of random draws do not depend on the readmission rate (common random numbers).
    """
    groups = [str(x) for x in d['groups']]
    G = len(groups)
    rng = np.random.default_rng(seed)
    start = season_start(season, d)
    seasonal = season != 'Annual average' and 'rates_m' in d
    horizon = warmup + days + TAIL_DAYS
    releases = np.zeros(horizon + 300, dtype=np.int32)
    returns = [[] for _ in range(horizon + 300)]
    q = deque()
    occupied = admit_count = return_count = total_bed_days = 0
    waitvals, daydata = [], []
    window_requests = 0
    group_counts = {g: [0, 0, 0] for g in groups}
    los_arr = [d[f'los_{g}'] for g in range(G)]
    age_arr = [d[f'ages_{g}'] for g in range(G)]
    died_arr = [d[f'died_{g}'] if f'died_{g}' in d else None for g in range(G)]
    tgt = groups.index(label) if label in groups else -1
    for t in range(horizon):
        occupied = max(0, occupied - int(releases[t]))
        active = intervene and t >= warmup
        measuring = t >= warmup
        for g, rlos in returns[t]:
            q.append((t, g, int(rlos), True, False, False, 1.0, 0, 0))
            if warmup <= t < warmup + days:
                window_requests += 1
        if t < warmup + days:
            date = start + pd.Timedelta(days=t - warmup)
            base_rate = d['rates_m'][date.month - 1][date.dayofweek] if seasonal else d['rates'][date.dayofweek]
            ns = rng.poisson(base_rate * ((1 + demand / 100) if active else 1))
            for g, n in enumerate(ns):
                if not n:
                    continue
                n = int(n)
                idx = rng.integers(0, len(los_arr[g]), n)             # one historical encounter per patient
                # v4.6 common random numbers: each new patient's readmission draws (return decision,
                # return delay, return LOS) are taken here, at admission, so the number and order of
                # random draws never depend on the readmission rate, bed limit or queueing.
                da, la = d[f'ret_delay_{g}'], d[f'ret_los_{g}']
                u_ret = rng.random(n)
                lag_ret = da[rng.integers(0, len(da), n)] if len(da) else np.zeros(n, dtype=int)
                los_ret = la[rng.integers(0, len(la), n)] if len(la) else np.zeros(n, dtype=int)
                # In a daily model, every inpatient episode consumes at least
                # one bed-day. Apply that floor BOTH to LOS statistics and beds.
                stays = np.maximum(1, los_arr[g][idx].astype(int).copy())
                alive = ~died_arr[g][idx] if died_arr[g] is not None else np.ones(n, dtype=bool)
                if g == tgt:
                    ages = age_arr[g][idx]
                    in_band = np.ones(n, bool) if age == 'All ages' else (ages < 65 if age == 'Under 65' else ages >= 65)
                else:
                    in_band = np.zeros(n, bool)
                if active and g == tgt and los_reduction > 0:
                    ok = in_band & alive                # never "shorten" a deceased episode
                    cut = np.minimum(stays, np.maximum(1, np.rint(stays * (1 - los_reduction / 100)).astype(int)))
                    # Count ONLY stays actually shortened, not merely eligible patients.
                    if measuring:
                        group_counts[groups[g]][2] += int((ok & (cut < stays)).sum())
                    stays = np.where(ok, cut, stays)
                for si, s in enumerate(stays):
                    q.append((t, g, int(s), False, bool(alive[si]), bool(in_band[si]),
                              float(u_ret[si]), int(lag_ret[si]), int(los_ret[si])))
                if measuring and t < warmup + days:
                    window_requests += n
                if measuring:
                    group_counts[groups[g]][0] += n
                    group_counts[groups[g]][1] += int(stays.sum())
                    admit_count += n
        while q and occupied < beds:
            req_day, g, los, is_return, eligible_for_return, targeted, u_ret_i, lag_i, rlos_i = q.popleft()
            if warmup <= req_day < warmup + days:
                waitvals.append(t - req_day)
            occupied += 1
            finish = min(t + max(1, los), len(releases) - 1)           # a same-day stay still uses one bed-day
            releases[finish] += 1
            if not is_return and eligible_for_return:
                reduce = active and (readmit_scope == 'hospital' or targeted)
                p = float(d.get(f'prob_survivor_{g}', d[f'prob_{g}'])) * ((1 - readmit_reduction / 100) if reduce else 1)
                if u_ret_i < p:                                         # pre-drawn at admission (v4.6)
                    da, la = d[f'ret_delay_{g}'], d[f'ret_los_{g}']
                    if len(da) and len(la):
                        lag, rlos = lag_i, rlos_i
                        rd = finish + lag
                        if rd < len(returns):
                            returns[rd].append((g, rlos))
                            # Return events are *scheduled* by index admissions
                            # occurring DURING the selected period. Do not include
                            # extra return events scheduled by admissions served
                            # in the post-period queue-clearing tail.
                            if warmup <= t < warmup + days:
                                return_count += 1
        if measuring and t < warmup + days:
            total_bed_days += occupied
            daydata.append((t - warmup + 1, occupied, len(q), admit_count, return_count))
    # Count admissions requested during the selected period that remain
    # unserved even after the tail. Do not silently drop these from the mean.
    unresolved = sum(1 for req_day, *_ in q if warmup <= req_day < warmup + days)
    waits = np.array(waitvals, dtype=float)
    if window_requests != len(waits) + unresolved:
        raise AssertionError(f'Waiting accounting error: {window_requests} != {len(waits)} + {unresolved}')
    series = pd.DataFrame(daydata, columns=['day', 'occupied', 'queue', 'cumulative_admissions', 'cumulative_returns'])
    tot_n = max(1, sum(v[0] for v in group_counts.values()))
    row = dict(average_los=sum(v[1] for v in group_counts.values()) / tot_n,
               admissions=admit_count, avg_admissions_day=admit_count / days,
               occupancy_pct=100 * series.occupied.mean() / beds if beds < UNLIMITED else np.nan,
               avg_occupied=series.occupied.mean(), peak_occupied=series.occupied.max(),
               beds_needed=float(np.percentile(series.occupied, 95)),
               bed_days=total_bed_days,
               # If requests remain unresolved after the 140-day tail, there is
               # no unbiased complete-case waiting-time estimate; show NA.
               mean_wait_days=waits.mean() if unresolved == 0 and len(waits) else (float('nan') if unresolved else 0.0),
               p95_wait_days=np.percentile(waits, 95) if unresolved == 0 and len(waits) else (float('nan') if unresolved else 0.0),
               waited_pct=100 * (waits > 0).mean() if unresolved == 0 and len(waits) else (float('nan') if unresolved else 0.0),
               unresolved_requests=unresolved, window_requests=window_requests, returns=return_count,
               peak_queue=series.queue.max(), pending_at_end=int(series.queue.iloc[-1]),
               targeted_admissions=group_counts.get(label, [0, 0, 0])[2],
               target_mean_los=group_counts[label][1] / max(group_counts[label][0], 1) if label in group_counts else np.nan)
    return (row, series, waits, group_counts) if collect else row


def scenario_defs(demand, los_reduction, readmit_reduction, breakdown=True):
    """Baseline, the full scenario, and (optionally) each active lever on its own."""
    defs = {'Baseline': dict(intervene=False, demand=0, los_reduction=0, readmit_reduction=0),
            'Scenario': dict(intervene=True, demand=demand, los_reduction=los_reduction, readmit_reduction=readmit_reduction)}
    active = [k for k, v in (('LOS only', los_reduction), ('Demand only', demand), ('Readmissions only', readmit_reduction)) if v]
    if breakdown and len(active) > 1:
        if los_reduction:
            defs['LOS only'] = dict(intervene=True, demand=0, los_reduction=los_reduction, readmit_reduction=0)
        if demand:
            defs['Demand only'] = dict(intervene=True, demand=demand, los_reduction=0, readmit_reduction=0)
        if readmit_reduction:
            defs['Readmissions only'] = dict(intervene=True, demand=0, los_reduction=0, readmit_reduction=readmit_reduction)
    return defs


def simulate(days=90, beds=3500, demand=0, los_reduction=10, diagnosis='CHF', severity=3, age='All ages',
             seed=2026, replications=10, readmit_reduction=0, season='Annual average', breakdown=True,
             warmup=WARMUP_DAYS, readmit_scope='hospital'):
    d = calibration()
    label = f'{diagnosis}|{severity}'
    results, timeseries, patient_rows, subgroups = [], [], [], []
    for name, kw in scenario_defs(demand, los_reduction, readmit_reduction, breakdown).items():
        for rep in range(replications):
            # same seed per replication across scenarios -> paired comparison (common random numbers where possible)
            row, series, waits, gc = _run_one(d, seed + rep, days, beds, warmup, kw['demand'], kw['los_reduction'],
                                              kw['readmit_reduction'], label, age, season, intervene=kw['intervene'],
                                              collect=True, readmit_scope=readmit_scope)
            results.append({'scenario': name, 'rep': rep + 1, **row})
            timeseries.append(series.assign(scenario=name, rep=rep + 1))
            if name in ('Baseline', 'Scenario'):
                # Wait histogram uses an example replication (could be pooled later).
                if rep == 0:
                    patient_rows.extend({'scenario': name, 'wait_days': v} for v in waits)
                # Capture all replications so cohort charts use the SAME aggregation
                # as the headline target_mean_los KPI (average of per-run means).
                for g, (count, bed_use, selected) in gc.items():
                    subgroups.append({'scenario': name, 'group': g, 'admissions': count,
                                      'mean_index_los': bed_use / max(count, 1), 'targeted_admissions': selected})
    reps = pd.DataFrame(results)
    summary = reps.groupby('scenario', sort=False).mean(numeric_only=True).reset_index()
    daily = (pd.concat(timeseries, ignore_index=True)
             .groupby(['scenario', 'day'], as_index=False)[['occupied', 'queue', 'cumulative_admissions', 'cumulative_returns']].mean())
    subgroup_all = pd.DataFrame(subgroups)
    subgroup_means = (subgroup_all.groupby(['scenario', 'group'], sort=False, as_index=False)
                      [['admissions', 'mean_index_los', 'targeted_admissions']].mean())
    return summary, reps, daily, pd.DataFrame(patient_rows), subgroup_means


def ci_summary(reps, metrics):
    """Mean and 95% CI half-width per scenario."""
    rows = []
    for sc, g in reps.groupby('scenario', sort=False):
        for m in metrics:
            x = g[m].astype(float).values
            half = t975(len(x)) * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else 0.0
            rows.append(dict(scenario=sc, metric=m, mean=x.mean(), ci95=half))
    return pd.DataFrame(rows)


def paired_effects(reps, metrics, versus='Baseline'):
    """Scenario minus baseline, paired by replication, with 95% CI and a 'clear difference?' flag."""
    base = reps[reps.scenario == versus].set_index('rep')
    rows = []
    for sc in [s for s in reps.scenario.unique() if s != versus]:
        cur = reps[reps.scenario == sc].set_index('rep')
        for m in metrics:
            diff = (cur[m] - base[m]).astype(float).values
            half = t975(len(diff)) * diff.std(ddof=1) / math.sqrt(len(diff)) if len(diff) > 1 else 0.0
            rows.append(dict(scenario=sc, metric=m, diff=diff.mean(), ci95=half, clear=abs(diff.mean()) > half))
    return pd.DataFrame(rows)


def needed_beds(days=90, demand=0, los_reduction=10, diagnosis='CHF', severity=3, age='All ages', seed=2026,
                replications=5, readmit_reduction=0, season='Annual average', warmup=WARMUP_DAYS,
                readmit_scope='hospital'):
    """Beds needed (95th-percentile daily occupancy with unlimited beds) for Baseline and Scenario."""
    d = calibration()
    label = f'{diagnosis}|{severity}'
    out = []
    values_by_scenario = {}
    for name, kw in list(scenario_defs(demand, los_reduction, readmit_reduction, False).items()):
        vals = [_run_one(d, seed + 500 + r, days, UNLIMITED, warmup, kw['demand'], kw['los_reduction'],
                         kw['readmit_reduction'], label, age, season, intervene=kw['intervene'],
                         readmit_scope=readmit_scope)['beds_needed']
                for r in range(replications)]
        v = np.asarray(vals, dtype=float)
        values_by_scenario[name] = v
        out.append(dict(scenario=name, beds_needed=v.mean(),
                        ci95=t975(len(v)) * v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else 0.0))
    # Since identical random seeds are used per replication, the 95% CI of
    # the difference MUST be computed from paired differences, not by
    # root-sum-square combining two marginal confidence intervals.
    for row in out:
        diff = values_by_scenario[row['scenario']] - values_by_scenario['Baseline']
        row['paired_diff_ci95'] = (t975(len(diff)) * diff.std(ddof=1) / math.sqrt(len(diff))
                                   if len(diff) > 1 else 0.0)
    return pd.DataFrame(out)


def recommended_beds(season='Annual average', seed=2026, replications=3):
    """Default bed count: baseline 95th-percentile daily occupancy, rounded to the nearest 100."""
    nb = needed_beds(days=120, demand=0, los_reduction=0, season=season, seed=seed, replications=replications)
    return int(round(nb.beds_needed.iloc[0] / 100.0) * 100)


def validate(replications=3, seed=2026):
    """Run the model across the real 2011-12 year (no interventions, unlimited beds) and compare with the data.
    Returns (monthly occupancy table, headline metric table)."""
    d = calibration()
    if 'actual_occ' not in d:
        return None, None
    G = len(d['groups'])
    actual = d['actual_occ']
    edges = pd.date_range('2011-07-01', periods=13, freq='MS')
    validation_days = (edges[-1] - edges[0]).days  # 366, because 2012 is a leap year
    aligned = dict(d, start=np.array('2011-07-01'))
    day0 = pd.Timestamp(str(d['actual_start']))
    rng_idx = [((edges[i] - day0).days, (edges[i + 1] - day0).days) for i in range(12)]
    month_names = [e.strftime('%b %Y') for e in edges[:12]]
    cols, sims = {}, {}
    modes = ['Annual average'] + (['Jul'] if 'rates_m' in d else [])
    for mode in modes:
        occs, rows = [], []
        for r in range(replications):
            row, series, _, gc = _run_one(aligned, seed + 900 + r, validation_days, UNLIMITED, 0, 0, 0, 0, '', 'All ages',
                                          'Jul' if mode == 'Jul' else 'Annual average', intervene=False, collect=True)
            occs.append(series.occupied.values)
            rows.append((row, gc))
        occ = np.mean(occs, axis=0)
        # Day 1 of the validation run is 1 Jul 2011 only for the seasonal run; annual run starts on a Monday,
        # but the monthly means below are over 'day since start' so the comparison stays like-for-like.
        sims[mode] = (occ, rows)
    mon = pd.DataFrame({'month': month_names,
                        'actual_beds': [float(actual[a:b].mean()) for a, b in rng_idx]})
    labels = {'Annual average': 'model_annual_average', 'Jul': 'model_seasonal'}
    for mode, (occ, _) in sims.items():
        mon[labels[mode]] = [float(occ[a:b].mean()) for a, b in rng_idx]
    for k in labels.values():
        if k in mon:
            mon[k + '_diff_pct'] = 100 * (mon[k] - mon.actual_beds) / mon.actual_beds
    # headline metrics (observed from the calibration arrays, simulated from the first mode available)
    obs_n = sum(len(d[f'los_{g}']) for g in range(G))
    obs_los = sum(d[f'los_{g}'].sum() for g in range(G)) / obs_n
    obs_ret = sum(float(d.get(f'prob_survivor_{g}', d[f'prob_{g}'])) *
                  (len(d[f'los_{g}']) - int(d[f'died_{g}'].sum()) if f'died_{g}' in d else len(d[f'los_{g}']))
                  for g in range(G)) / obs_n
    obs_rlos = (sum(d[f'ret_los_{g}'].sum() for g in range(G)) /
                max(1, sum(len(d[f'ret_los_{g}']) for g in range(G))))
    mode = 'Jul' if 'Jul' in sims else 'Annual average'
    rows = sims[mode][1]
    sim_n = np.mean([r[0]['admissions'] for r in rows])
    sim_los = np.mean([r[0]['average_los'] for r in rows])
    sim_ret = np.mean([100 * r[0]['returns'] / max(r[0]['admissions'], 1) for r in rows])
    sim_bd = np.mean([r[0]['bed_days'] for r in rows])
    obs_bd = float(actual[:validation_days].sum())
    met = pd.DataFrame([
        ('Admissions in the year', obs_n, sim_n),
        ('Mean index LOS (days; recorded)', obs_los, sim_los),
        ('Readmission rate (%)', 100 * obs_ret, sim_ret),
        ('Bed-days (index + return stays)', obs_bd, sim_bd)], columns=['measure', 'observed', 'simulated'])
    met['difference_pct'] = 100 * (met.simulated - met.observed) / met.observed
    return mon, met


def pathways(group):
    """Discharge pathway shares and mean LOS for one group (needs the new calibration)."""
    d = calibration()
    if 'pathway_share' not in d:
        return None
    gi = [str(x) for x in d['groups']].index(group)
    return pd.DataFrame({'pathway': [str(x) for x in d['pathway_names']],
                         'share_pct': 100 * d['pathway_share'][gi],
                         'mean_los_days': d['pathway_los'][gi],
                         'patients': d['pathway_n'][gi].astype(int)})


def death_share(group):
    """% of this group's historical admissions that ended in in-hospital death (None if unknown)."""
    d = calibration()
    gi = [str(x) for x in d['groups']].index(group)
    k = f'died_{gi}'
    return 100 * float(d[k].mean()) if k in d else None
