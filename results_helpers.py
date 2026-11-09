"""Read-only helpers that turn existing simulation outputs into manager-facing results.

All statistics come from the unchanged backend:
* means and 95% Monte Carlo intervals  -> simulation.ci_summary
* paired Scenario-minus-Baseline effects -> simulation.paired_effects
* unrestricted bed-demand reference      -> simulation.needed_beds (with its paired CI)

This module only (a) looks values up, (b) re-indexes the replication-averaged daily series by
calendar date using the model's own start-date rule, and (c) writes plain-language text from those
numbers. It never changes how the model runs.
"""
import math

import numpy as np
import pandas as pd

import simulation as S
import historical_summary as H

LEVER_NAMES = {"LOS only": "Shorter stays only", "Demand only": "Demand change only",
               "Readmissions only": "Fewer return stays only", "Scenario": "All changes together"}


# --------------------------------------------------------------------------- formatting
def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def num(x, dp=0):
    if not finite(x):
        return "n/a"
    return f"{x:,.{dp}f}"


def signed(x, dp=0):
    if not finite(x):
        return "n/a"
    if round(x, dp) == 0:
        return f"{0:.{dp}f}"
    return f"{x:+,.{dp}f}"


def pct_change(diff, base, min_base=1e-9):
    """Percentage change, or None where it would be undefined or misleading."""
    if not (finite(diff) and finite(base)) or abs(base) <= min_base:
        return None
    return 100.0 * diff / base


def age_phrase(age):
    return "" if age == "All ages" else (" aged under 65" if age == "Under 65" else " aged 65 and over")


def season_phrase(season, days):
    if not H.is_seasonal(season):
        return "Annual-average admission pattern"
    months = [m for m, _ in H.months_covered(season, days)]
    span = months[0] if len(months) == 1 else f"{months[0]}–{months[-1]}"
    return f"Starts 1 {H.MONTH_FULL[season]} · historical month pattern ({span})"


# --------------------------------------------------------------------------- comparison runs (v4.2)
READMIT_SCOPE = "group"      # product decision v4.2: readmission reduction applies to the selected group only


def unlimited_values(days, demand, los, readmit, diagnosis, severity, age, seed, reps, season, intervene=True,
                     readmit_scope=READMIT_SCOPE):
    """Per-run results of the unlimited-bed runs used for the busy-day reference (v4.9).

    Same loop, seeds (seed+500+r) and model call as simulation.needed_beds; besides the 95th-percentile daily
    occupancy it keeps the run's bed-days, i.e. the bed-days patients would use over the period if no one had to
    wait for a bed (bed-day demand before the bed limit). No extra model runs and no model change."""
    d = S.calibration()
    rows = [S._run_one(d, seed + 500 + r, days, S.UNLIMITED, S.WARMUP_DAYS, demand, los, readmit,
                       f"{diagnosis}|{severity}", age, season, intervene=intervene, readmit_scope=readmit_scope)
            for r in range(reps)]
    return (np.array([x["beds_needed"] for x in rows], dtype=float),
            np.array([x["bed_days"] for x in rows], dtype=float))


def nb_values(days, demand, los, readmit, diagnosis, severity, age, seed, reps, season, intervene=True,
              readmit_scope=READMIT_SCOPE):
    """Per-run busy-day bed use (95th-percentile daily occupancy with unlimited beds).

    Identical loop to simulation.needed_beds (same seeds seed+500+r, same warm-up, same model call); kept here
    so that any two configurations can be compared run by run."""
    d = S.calibration()
    return np.array([S._run_one(d, seed + 500 + r, days, S.UNLIMITED, S.WARMUP_DAYS, demand, los, readmit,
                                f"{diagnosis}|{severity}", age, season, intervene=intervene,
                                readmit_scope=readmit_scope)["beds_needed"]
                     for r in range(reps)], dtype=float)


def relabel(df, src, dst):
    if "scenario" not in df.columns:              # e.g. no request waited in any run
        return df.iloc[0:0].copy()
    out = df[df.scenario == src].copy()
    out["scenario"] = dst
    return out


def build_runs(duration, beds, demand, reduction, readmit, diagnosis, severity, age, seed, reps, season, breakdown,
               ref_beds, readmit_scope=READMIT_SCOPE):
    """Model runs for one scenario. Besides the model's own Baseline (same beds, no changes) and Scenario, two
    comparison runs are added when they differ from the Baseline, with the same seeds so runs stay paired:

    * "Conditions only"  - same demand and beds as the scenario, without the patient-flow improvements;
    * "Reference"        - no changes at all, with the planning-reference number of beds.
    """
    kw = dict(days=duration, diagnosis=diagnosis, severity=severity, age=age, seed=seed, replications=reps,
              season=season, readmit_scope=readmit_scope)
    summary, reps_df, daily, waits, sub = S.simulate(beds=beds, demand=demand, los_reduction=reduction,
                                                     readmit_reduction=readmit, breakdown=breakdown, **kw)
    parts = dict(reps=[reps_df], daily=[daily], waits=[waits], sub=[sub])

    def take(res, src, dst):
        for k, df in zip(("reps", "daily", "waits", "sub"), (res[1], res[2], res[3], res[4])):
            parts[k].append(relabel(df, src, dst))

    main = (summary, reps_df, daily, waits, sub)
    improve = bool(reduction or readmit)
    if improve:
        if demand == 0:
            take(main, "Baseline", "Conditions only")
        else:
            take(S.simulate(beds=beds, demand=demand, los_reduction=0, readmit_reduction=0, breakdown=False, **kw),
                 "Scenario", "Conditions only")
    if beds == ref_beds:
        take(main, "Baseline", "Reference")
    else:
        take(S.simulate(beds=ref_beds, demand=0, los_reduction=0, readmit_reduction=0, breakdown=False, **kw),
             "Baseline", "Reference")
    nb_reps = min(reps, 5)
    nbk = dict(days=duration, diagnosis=diagnosis, severity=severity, age=age, seed=seed, reps=nb_reps, season=season,
               readmit_scope=readmit_scope)
    un = {"Reference": unlimited_values(demand=0, los=0, readmit=0, intervene=False, **nbk),
          "Scenario": unlimited_values(demand=demand, los=reduction, readmit=readmit, **nbk)}
    if improve:
        un["Conditions only"] = (un["Reference"] if demand == 0 else
                                 unlimited_values(demand=demand, los=0, readmit=0, **nbk))
    nb_vals = {k: v[0] for k, v in un.items()}
    bd_demand = {k: v[1] for k, v in un.items()}         # bed-day demand before the bed limit (v4.9)
    nb = pd.DataFrame([dict(scenario=k, beds_needed=v.mean(),
                            ci95=S.t975(len(v)) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0)
                       for k, v in nb_vals.items()])
    return dict(reps=pd.concat(parts["reps"], ignore_index=True), daily=pd.concat(parts["daily"], ignore_index=True),
                waits=pd.concat(parts["waits"], ignore_index=True), sub=pd.concat(parts["sub"], ignore_index=True),
                nb=nb, nb_vals=nb_vals, bd_demand=bd_demand)


def scenario_case(settings):
    """'improve' (patient-flow only), 'conditions' (demand/beds only), 'combined' or 'none'."""
    improve = bool(settings["reduction"] or settings["readmit"])
    cond = bool(settings["demand"]) or settings["beds"] != settings["ref_beds"]
    return {(True, False): "improve", (False, True): "conditions", (True, True): "combined"}.get((improve, cond), "none")


def comparator(settings):
    """Capacity-first (v4.4): every scenario is compared with the planning reference."""
    return "Reference"


def improvement_comparator(settings):
    """Run that isolates the patient-flow improvements: same demand and beds without them (None if no improvements).
    When demand and beds are at the reference this run is the reference itself."""
    if not (settings["reduction"] or settings["readmit"]):
        return None
    return "Conditions only" if scenario_case(settings) == "combined" else "Reference"


def secondary_comparator(settings):
    """Kept for compatibility: the incremental-improvement run for combined scenarios."""
    return "Conditions only" if scenario_case(settings) == "combined" else None


def comparison_label(settings, name):
    if name == "Reference":
        return f"the reference scenario (historical demand, {settings['ref_beds']:,} beds, no improvements)"
    dem = "historical demand" if not settings["demand"] else f"{settings['demand']:+d}% demand"
    return f"the same conditions without the improvements ({dem}, {settings['beds']:,} beds)"


def view_of(res, comp):
    """Present one comparison (comp vs Scenario) through the audited Results helpers, which compare a run called
    'Baseline' with 'Scenario': the chosen comparison run is shown under that name."""
    pick = lambda df: pd.concat([relabel(df, comp, "Baseline"), relabel(df, "Scenario", "Scenario")],
                                ignore_index=True)
    vals = res["nb_vals"]
    b, sc = vals[comp], vals["Scenario"]
    diff = sc - b
    half = S.t975(len(diff)) * diff.std(ddof=1) / np.sqrt(len(diff)) if len(diff) > 1 else 0.0
    nbdf = pd.DataFrame([dict(scenario="Baseline", beds_needed=b.mean(), ci95=0.0, paired_diff_ci95=0.0),
                         dict(scenario="Scenario", beds_needed=sc.mean(), ci95=0.0, paired_diff_ci95=half)])
    for name, v in (("Baseline", b), ("Scenario", sc)):
        nbdf.loc[nbdf.scenario == name, "ci95"] = S.t975(len(v)) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0
    return dict(reps=pick(res["reps"]), daily=pick(res["daily"]), waits=pick(res["waits"]), sub=pick(res["sub"]),
                nb=nbdf)



# --------------------------------------------------------------------------- result wrapper
class Results:
    """Look-ups over one completed simulation (Baseline, Scenario and optional single-lever runs)."""

    def __init__(self, settings, res):
        self.s = dict(settings)
        self.reps = res["reps"]
        self.daily = res["daily"]
        self.waits = res["waits"]
        self.sub = res["sub"]
        self.nbdf = res["nb"]
        self.metrics = [c for c in self.reps.select_dtypes(include="number").columns if c != "rep"]
        self.cis = S.ci_summary(self.reps, self.metrics)
        self.eff = S.paired_effects(self.reps, self.metrics)
        self.group = f"{self.s['diagnosis']}|{self.s['severity']}"
        self.scenarios = list(self.reps.scenario.unique())

    # ---- look-ups (same arithmetic as the audited dashboard)
    def m(self, metric, scen):
        r = self.cis[(self.cis.scenario == scen) & (self.cis.metric == metric)].iloc[0]
        return float(r["mean"]), float(r["ci95"])

    def e(self, metric, scen="Scenario"):
        r = self.eff[(self.eff.scenario == scen) & (self.eff.metric == metric)].iloc[0]
        return float(r["diff"]), float(r["ci95"]), bool(r["clear"])

    def nb(self, scen):
        r = self.nbdf[self.nbdf.scenario == scen].iloc[0]
        return float(r.beds_needed), float(r.ci95)

    def nb_effect(self):
        (b, _), (s, _) = self.nb("Baseline"), self.nb("Scenario")
        half = float(self.nbdf.loc[self.nbdf.scenario == "Scenario", "paired_diff_ci95"].iloc[0])
        return s - b, half, abs(s - b) > half

    def levers(self):
        out = []
        if self.s["reduction"]:
            out.append("los")
        if self.s["demand"]:
            out.append("demand")
        if self.s["readmit"]:
            out.append("readmit")
        return out

    # ---- time series ------------------------------------------------------------
    def daily_frame(self):
        """Replication-averaged daily series with calendar date, weekday and new-event counts.

        new_admissions = day-on-day difference of the mean cumulative admissions (= mean of each
        run's daily admissions). new_returns is the number of return stays *scheduled* that day by
        index patients who were given a bed that day - not readmissions occurring that day.
        """
        dates = H.sim_dates(self.s["season"], self.s["duration"])
        out = []
        for sc, g in self.daily.groupby("scenario", sort=False):
            g = g.sort_values("day").copy()
            g["date"] = dates[g.day.values - 1]
            g["weekday"] = [H.WEEKDAYS[x] for x in g.date.dt.dayofweek]
            g["month"] = [H.CAL_MONTHS[x - 1] for x in g.date.dt.month]
            g["new_admissions"] = g.cumulative_admissions.diff().fillna(g.cumulative_admissions)
            g["new_returns"] = g.cumulative_returns.diff().fillna(g.cumulative_returns)
            out.append(g)
        return pd.concat(out, ignore_index=True)

    def by_period(self, column, resolution, how="mean"):
        """Aggregate a daily column to Daily / Weekly (7-day blocks from Day 1) / Monthly (calendar)."""
        df = self.daily_frame()
        df = df[df.scenario.isin(["Baseline", "Scenario"])]
        if resolution == "Daily":
            return df[["scenario", "day", column]].rename(columns={"day": "period", column: "value"}), "Day"
        if resolution == "Weekly":
            df = df.assign(period=(df.day - 1) // 7 + 1)
            agg = df.groupby(["scenario", "period"], sort=False).agg(value=(column, how), n=("day", "size")).reset_index()
            agg["label"] = [f"Wk {p}" + ("" if n == 7 else f" ({n}d)") for p, n in zip(agg.period, agg.n)]
            return agg, "Week of simulation"
        # Monthly: calendar months of the simulated window (meaningful only for month-based patterns)
        df = df.assign(ym=df.date.dt.to_period("M"))
        agg = df.groupby(["scenario", "ym"], sort=True).agg(value=(column, how), n=("day", "size")).reset_index()
        agg["label"] = [H.CAL_MONTHS[p.month - 1] + ("" if n == p.days_in_month else f" ({n} of {p.days_in_month} days)")
                        for p, n in zip(agg.ym, agg.n)]
        agg = agg.drop(columns="ym")
        return agg, "Month"

    def weekday_profile(self, column):
        df = self.daily_frame()
        df = df[df.scenario.isin(["Baseline", "Scenario"])]
        agg = df.groupby(["scenario", "weekday"], sort=False)[column].mean().reset_index()
        agg["order"] = agg.weekday.map({w: i for i, w in enumerate(H.WEEKDAYS)})
        return agg.sort_values(["scenario", "order"])

    # ---- by diagnosis --------------------------------------------------------------
    def modelled_by_group(self, level="group"):
        """Mean admissions and modelled initial-stay bed-days by group for Baseline/Scenario.

        initial-stay bed-days ~= (mean admissions) x (mean modelled initial stay) per group. Both
        factors are replication means returned by simulation.simulate; their product is an
        approximation of the mean of per-run products (the difference is their covariance, which is
        small). These are bed-days *generated by admissions in the period*, not occupied beds.
        """
        sub = self.sub[self.sub.scenario.isin(["Baseline", "Scenario"])].copy()
        sub["bed_days"] = sub.admissions * sub.mean_index_los
        sub["diagnosis"] = sub.group.str.split("|").str[0]
        if level == "diagnosis":
            sub = sub.groupby(["scenario", "diagnosis"], sort=False)[["admissions", "bed_days"]].sum().reset_index()
            sub["label"] = sub.diagnosis
        else:
            sub["label"] = [H.group_label(g) for g in sub.group]
        sub["mean_los"] = sub.bed_days / sub.admissions.where(sub.admissions > 0)
        return sub


# --------------------------------------------------------------------------- KPI cards
def kpi_cards(R):
    s = R.s
    gl = H.group_label(R.group)
    cards = []

    # 1. Beds needed - unrestricted p95 reference
    (b, _), (sc, _) = R.nb("Baseline"), R.nb("Scenario")
    d, half, clear = R.nb_effect()
    if not R.levers():
        sent = "No assumptions changed, so both runs describe the same hospital."
    elif not clear:
        sent = "No clear change: the difference is within simulation noise."
    else:
        sent = f"The scenario's busy-day bed use is about {abs(d):,.0f} beds {'higher' if d > 0 else 'lower'}."
    pressure = sc > s["beds"]
    if pressure:
        sent += f" This is above the {s['beds']:,} beds available, so queues are likely on busy days."
    cards.append(dict(key="beds", title="Beds needed", sub="Planning reference (95th percentile, unlimited beds)",
                      base=num(b), scen=num(sc), unit="beds", delta=signed(d), pct=pct_change(d, b),
                      clear=clear, sentence=sent, alert=pressure,
                      better="down", good_txt="fewer beds needed", bad_txt="more beds needed"))

    # 2. Length of stay - target group
    (b, _), (sc, _) = R.m("target_mean_los", "Baseline"), R.m("target_mean_los", "Scenario")
    d, half, clear = R.e("target_mean_los")
    shortened, _ = R.m("targeted_admissions", "Scenario")
    if s["reduction"] == 0:
        sent = "No length-of-stay change was assumed for this group."
    elif not clear:
        sent = "The assumed reduction produced no clear change in this group's modelled average stay."
    else:
        sent = (f"The assumed {s['reduction']}% reduction shortened about {shortened:,.0f} stays, "
                f"lowering the group's average by {abs(d):.2f} days.")
    cards.append(dict(key="los", title="Length of stay", sub=f"Average modelled initial stay · {gl}",
                      base=num(b, 2), scen=num(sc, 2), unit="days", delta=signed(d, 2), pct=pct_change(d, b),
                      clear=clear, sentence=sent, alert=False,
                      better="down", good_txt="fewer bed-days", bad_txt="more bed-days"))

    # 3. Waiting
    (b, _), (sc, _) = R.m("mean_wait_days", "Baseline"), R.m("mean_wait_days", "Scenario")
    (wb, _), (ws, _) = R.m("waited_pct", "Baseline"), R.m("waited_pct", "Scenario")
    d, half, clear = R.e("mean_wait_days")
    if not (finite(b) and finite(sc)):
        cards.append(dict(key="wait", title="Waiting for a bed", sub="Average wait per bed request",
                          base=num(b, 2) if finite(b) else "Not estimable",
                          scen=num(sc, 2) if finite(sc) else "Not estimable", unit="days",
                          delta=None, pct=None, clear=False, alert=True,
                          sentence="Some bed requests were still waiting at the end of the 140-day follow-up, "
                                   "so an average wait cannot be calculated without understating it."))
    else:
        if ws < 1 and wb < 1:
            sent = "Almost no requests had to wait in either run."
        else:
            sent = f"{ws:.0f}% of bed requests waited at least a day (baseline {wb:.0f}%)."
        cards.append(dict(key="wait", title="Waiting for a bed", sub="Average wait per bed request",
                          base=num(b, 2), scen=num(sc, 2), unit="days", delta=signed(d, 2),
                          pct=pct_change(d, b, min_base=0.05), clear=clear, sentence=sent,
                          alert=bool(ws >= 20), better="down", good_txt="shorter waits", bad_txt="longer waits"))

    # 4. Admissions
    (b, _), (sc, _) = R.m("avg_admissions_day", "Baseline"), R.m("avg_admissions_day", "Scenario")
    d, half, clear = R.e("avg_admissions_day")
    if s["demand"]:
        sent = f"Reflects the {s['demand']:+d}% admission-demand assumption applied to every patient group."
    else:
        sent = "No demand change was assumed; small differences are random variation."
    cards.append(dict(key="adm", title="Admissions", sub="New (initial) admissions per day, all groups",
                      base=num(b, 0), scen=num(sc, 0), unit="per day", delta=signed(d, 0), pct=pct_change(d, b),
                      clear=clear, sentence=sent, alert=False, better=None, neutral_txt="your demand assumption"))
    return cards


# --------------------------------------------------------------------------- insights
def insights(R):
    """Three-part, data-grounded explanation: what changed / what contributed / planning meaning."""
    s = R.s
    gl = H.group_label(R.group)
    days = s["duration"]
    levers = R.levers()
    out = dict(what=[], why=[], meaning=[])

    if not levers:
        out["what"].append("No assumptions were changed, so the scenario and the baseline describe the same "
                           "simulated hospital. Adjust length of stay, demand or return stays to see an effect.")
    bd, bdci, bdclear = R.e("bed_days")
    base_bd, _ = R.m("bed_days", "Baseline")
    if levers:
        if bdclear:
            p = pct_change(bd, base_bd)
            out["what"].append(f"Over the {days}-day period the scenario uses <b>{abs(bd):,.0f} {'fewer' if bd < 0 else 'more'} "
                               f"bed-days</b> than the baseline ({p:+.1f}%).")
        else:
            out["what"].append(f"Total bed-days over the {days} days are <b>essentially unchanged</b> "
                               f"(difference {bd:+,.0f}, within simulation noise).")
        (nbb, _), (nbs, _) = R.nb("Baseline"), R.nb("Scenario")
        dnb, _, nbclear = R.nb_effect()
        if nbclear:
            out["what"].append(f"The busy-day planning reference moves from about <b>{nbb:,.0f} to {nbs:,.0f} beds</b>.")
        else:
            out["what"].append(f"The busy-day planning reference stays at about <b>{nbs:,.0f} beds</b>.")
        (wb, _), (ws, _) = R.m("waited_pct", "Baseline"), R.m("waited_pct", "Scenario")
        if finite(wb) and finite(ws):
            if abs(ws - wb) >= 1:
                out["what"].append(f"The share of bed requests that waited goes from <b>{wb:.0f}% to {ws:.0f}%</b>.")
            (mb, _), (ms, _) = R.m("mean_wait_days", "Baseline"), R.m("mean_wait_days", "Scenario")
            dw, _, wclear = R.e("mean_wait_days")
            if wclear and abs(dw) >= 0.05:
                out["what"].append(f"The average wait for a bed goes from <b>{mb:.2f} to {ms:.2f} days</b>.")
        else:
            out["what"].append("Waiting cannot be fully measured: some requests were still unserved after the follow-up period.")

    # ---- what contributed
    if "los" in levers:
        (lb, _), (ls, _) = R.m("target_mean_los", "Baseline"), R.m("target_mean_los", "Scenario")
        short, _ = R.m("targeted_admissions", "Scenario")
        adm = R.sub[(R.sub.scenario == "Scenario") & (R.sub.group == R.group)].admissions
        adm = float(adm.iloc[0]) if len(adm) else float("nan")
        out["why"].append(
            f"<b>Shorter stays ({s['reduction']}%) for {gl}{age_phrase(s['age'])}.</b> About {short:,.0f} of roughly "
            f"{adm:,.0f} admissions in this group had a shorter modelled stay, so its average fell from {lb:.2f} to {ls:.2f} days. "
            "Patients who died in hospital, were outside the chosen age band, or whose stay could not shrink after "
            "rounding to whole days (minimum one day) were not shortened.")
    if "demand" in levers:
        (ab, _), (as_, _) = R.m("avg_admissions_day", "Baseline"), R.m("avg_admissions_day", "Scenario")
        effect = ("adding arrivals that compete for the same beds" if s["demand"] > 0
                  else "leaving fewer arrivals to compete for the same beds")
        out["why"].append(f"<b>Admission demand {s['demand']:+d}% for all patient groups.</b> New admissions per day went "
                          f"from about {ab:,.0f} to {as_:,.0f}, {effect}.")
    if "readmit" in levers:
        (rb, _), (rs, _) = R.m("returns", "Baseline"), R.m("returns", "Scenario")
        out["why"].append(f"<b>Return stays {s['readmit']}% less likely, hospital-wide.</b> Return stays scheduled by "
                          f"patients admitted in the period went from about {rb:,.0f} to {rs:,.0f}. This applies to every "
                          "group, not only the selected one.")
    singles = [x for x in ("LOS only", "Demand only", "Readmissions only") if x in R.scenarios]
    if singles:
        parts = []
        for sc in singles:
            dd, _, cl = R.e("bed_days", sc)
            parts.append(f"{LEVER_NAMES[sc].lower()} {dd:+,.0f}" + ("" if cl else " (within noise)"))
        out["why"].append("<b>Each assumption on its own</b> (bed-days vs baseline): " + "; ".join(parts) +
                          f". All together: {bd:+,.0f}. Patients share one pool of beds, so separate effects do not "
                          "simply add up.")
    elif len(levers) > 1:
        out["why"].append("Several assumptions changed at once and their effects interact. Turn on "
                          "<i>Show each assumption on its own</i> under Advanced settings to separate them.")
    (occ_s, _) = R.m("occupancy_pct", "Scenario")
    (pq, _) = R.m("peak_queue", "Scenario")
    if levers and finite(occ_s) and occ_s >= 97:
        out["why"].append(f"<b>Beds were fixed at {s['beds']:,}</b> in both runs and averaged {occ_s:.0f}% full in the scenario. "
                          "When every bed is taken, additional demand shows up as waiting rather than as extra bed-days.")

    # ---- planning meaning
    (nbs, _) = R.nb("Scenario")
    (ws, _) = R.m("waited_pct", "Scenario")
    (unres, _) = R.m("unresolved_requests", "Scenario")
    beds = s["beds"]
    if unres > 0:
        out["meaning"].append(f"With {beds:,} beds, the modelled queue does not clear even after the follow-up period. "
                              "Under these combined assumptions the bed pool is overloaded; the capacity or demand "
                              "assumptions would need to change before waiting results are meaningful.")
    elif finite(ws) and ws >= 20:
        out["meaning"].append(f"With {beds:,} beds against a busy-day reference of about {nbs:,.0f}, the modelled hospital "
                              f"runs close to full and {ws:.0f}% of bed requests wait. These assumptions point to sustained "
                              "capacity pressure in this simplified pooled-bed model.")
    elif beds < nbs:
        out["meaning"].append(f"The {beds:,} available beds sit below the scenario's busy-day reference (about {nbs:,.0f}), "
                              "so short spells of waiting are likely when demand peaks.")
    else:
        out["meaning"].append(f"The {beds:,} available beds are at or above the scenario's busy-day reference "
                              f"(about {nbs:,.0f}), so waiting stays limited in this model.")
    if levers and bdclear and bd < 0:
        occ_d, _, _ = R.e("avg_occupied")
        out["meaning"].append(f"The bed-days released are equivalent to about {abs(occ_d):,.0f} fewer occupied beds on an "
                              "average day. This shows the scale of capacity the assumed change could free up; it is not a "
                              "measured or guaranteed saving.")
    if len(levers) > 1:
        out["meaning"].append("Because several assumptions changed together, read the result as a combined what-if, "
                              "not as the effect of any single change.")
    return out


# --------------------------------------------------------------------------- bottom line
def capacity_status(beds, ref, waited_pct, unresolved):
    """Simple three-level reading of capacity pressure for one run (used for Baseline and Scenario)."""
    if unresolved > 0 or (finite(waited_pct) and waited_pct >= 20):
        return "over"
    if beds < ref or (finite(waited_pct) and waited_pct >= 5):
        return "tight"
    return "ok"


STATUS_LABEL = {"ok": "Enough beds", "tight": "Tight on busy days", "over": "Under sustained pressure"}


def verdict(R):
    """One-line answer to the manager's first question: are there enough beds under this scenario?"""
    s = R.s
    beds = s["beds"]
    out = {}
    for sc in ("Baseline", "Scenario"):
        ref, _ = R.nb(sc)
        w, _ = R.m("waited_pct", sc)
        u, _ = R.m("unresolved_requests", sc)
        out[sc] = dict(ref=ref, waited=w, unres=u, level=capacity_status(beds, ref, w, u))
    sc = out["Scenario"]
    gap = beds - sc["ref"]
    if gap >= 0:
        head = (f"With <b>{beds:,} beds</b>, this scenario needs about <b>{sc['ref']:,.0f}</b> on busy days — "
                f"<b>{gap:,.0f} spare</b>.")
    else:
        head = (f"With <b>{beds:,} beds</b>, this scenario needs about <b>{sc['ref']:,.0f}</b> on busy days — "
                f"<b>{-gap:,.0f} short</b>.")
    if sc["unres"] > 0:
        sub = "Some patients are still waiting for a bed long after the period ends: the bed pool is overloaded."
    elif finite(sc["waited"]):
        sub = f"{sc['waited']:.0f}% of bed requests would wait at least a day."
    else:
        sub = ""
    b = out["Baseline"]
    if b["level"] != sc["level"]:
        sub += f" Without your changes (baseline) the status would be: <b>{STATUS_LABEL[b['level']].lower()}</b>."
    else:
        sub += " The baseline has the same status."
    return dict(level=sc["level"], label=STATUS_LABEL[sc["level"]], head=head, sub=sub.strip())


def rhythm_text(R, what="occupied", lead="Why does the line go up and down every week?"):
    """Plain-language explanation of the weekly up-and-down pattern, computed from the data and this run."""
    wd, _ = H.weekday_pattern()
    top = wd.sort_values("per_day", ascending=False)
    hi1, hi2, lo = top.iloc[0], top.iloc[1], top.iloc[-1]
    prof = R.weekday_profile("occupied")
    prof = prof[prof.scenario == "Baseline"]
    peak = prof.loc[prof.occupied.idxmax(), "weekday"]
    trough = prof.loc[prof.occupied.idxmin(), "weekday"]
    q = R.weekday_profile("queue")
    q = q[q.scenario.isin(["Baseline", "Scenario"])]
    qtot = q.queue.sum()
    qtxt = ""
    if qtot > 0:
        qd = q.groupby("weekday").queue.sum()
        top_q = qd.idxmax()
        share = 100 * qd.max() / qtot
        if share >= 40:
            qtxt = (f" Waiting builds up at the same point in the week: about {share:.0f}% of the queue is on "
                    f"<b>{top_q}s</b>.")
        else:
            qtxt = (f" Waiting starts on the busy days (most often on <b>{top_q}s</b>) and, when beds stay full, "
                    "carries over into the following days.")
    return (f"<b>{lead}</b> It is the weekly admission rhythm in the historical "
            f"data, not an error or random noise. In 2011–12 most patients were admitted on <b>{hi1.weekday}</b> "
            f"(≈{hi1.per_day:,.0f}/day) and <b>{hi2.weekday}</b> (≈{hi2.per_day:,.0f}/day) and fewest on "
            f"<b>{lo.weekday}</b> (≈{lo.per_day:,.0f}/day). Because patients stay several days, beds fill up after the "
            f"busy days, are fullest on <b>{peak}</b> and emptiest on <b>{trough}</b>.{qtxt} "
            "<b>For planning:</b> the weekly peak, not the average, decides whether beds run out.")


def compare_row(R, name):
    """Compact record of one completed run for the scenario-comparison table."""
    s = R.s
    ref, _ = R.nb("Scenario")
    w, _ = R.m("waited_pct", "Scenario")
    mw, _ = R.m("mean_wait_days", "Scenario")
    u, _ = R.m("unresolved_requests", "Scenario")
    bd, _, bdclear = R.e("bed_days")
    return {"Scenario": name,
            "Beds available": f"{s['beds']:,}",
            "Beds needed on busy days": f"{ref:,.0f}",
            "Spare (+) / short (−)": f"{s['beds'] - ref:+,.0f}",
            "Requests waiting": "Not estimable" if not finite(w) else f"{w:.0f}%",
            "Average wait (days)": "Not estimable" if not finite(mw) else f"{mw:.2f}",
            "Bed-days vs baseline": f"{bd:+,.0f}" + ("" if bdclear else " (no clear change)"),
            "Status": STATUS_LABEL[capacity_status(s["beds"], ref, w, u)]}


def scenario_name(s):
    parts = [H.group_label(f"{s['diagnosis']}|{s['severity']}", short=True)]
    if s["reduction"]:
        parts.append(f"LOS −{s['reduction']}%")
    if s["demand"]:
        parts.append(f"demand {s['demand']:+d}%")
    if s["readmit"]:
        parts.append(f"returns −{s['readmit']}%")
    parts.append(f"{s['beds']:,} beds")
    parts.append(f"{s['duration']}d" + ("" if s["season"] == "Annual average" else f" from {s['season']}"))
    return " · ".join(parts)


# --------------------------------------------------------------------------- exports
DATA_DICTIONARY = pd.DataFrame([
    ("scenario", "Baseline = no change; Scenario = all selected changes; 'LOS only' / 'Demand only' / 'Readmissions only' = one change on its own"),
    ("rep", "Replication number. Baseline and Scenario share a random seed per replication (paired comparison)"),
    ("average_los", "Mean modelled initial length of stay of all new admissions in the period (days; same-day stays count as 1)"),
    ("target_mean_los", "Mean modelled initial length of stay of the selected diagnosis x severity group, all ages (days)"),
    ("admissions / avg_admissions_day", "New (initial) admissions in the period / per day. Excludes return stays"),
    ("occupancy_pct", "Average beds occupied / available beds x 100"),
    ("avg_occupied / peak_occupied", "Mean / maximum beds in use per day with the selected bed capacity"),
    ("beds_needed (replication file)", "95th-percentile daily occupancy of that capped run. Use the beds-reference file for the unrestricted planning reference"),
    ("beds_needed (beds-reference file)", "95th-percentile daily occupancy with unlimited beds: a planning reference, NOT a guarantee of zero waiting"),
    ("paired_diff_ci95", "95% Monte Carlo interval half-width of the paired Scenario-minus-Baseline difference"),
    ("bed_days", "Sum over the period of beds occupied each day (index and return stays)"),
    ("mean_wait_days / p95_wait_days", "Mean / 95th percentile whole-day wait for requests arriving in the period; blank (NA) if any remain unresolved after the 140-day follow-up"),
    ("waited_pct", "% of bed requests arriving in the period that waited at least one day"),
    ("window_requests / unresolved_requests", "Bed requests arriving in the period / still unserved after the follow-up"),
    ("returns", "Return stays SCHEDULED by index patients admitted in the period (some fall after the period). Not a 30-day readmission rate"),
    ("peak_queue / pending_at_end", "Largest daily queue / requests still queued on the last day"),
    ("targeted_admissions", "Target-group stays actually shortened (eligible age band, survived to discharge, changed after rounding)"),
    ("day, occupied, queue, cumulative_admissions, cumulative_returns", "Daily series, averaged over replications"),
    ("group, admissions, mean_index_los", "Cohort file: mean admissions and mean modelled initial stay per diagnosis x severity group"),
], columns=["column", "meaning"])


# =========================================================================== v3.1 decision-oriented helpers
PRESSURE = {"low": "Low", "moderate": "Moderate", "high": "High"}


def fmt_pct_small(x):
    """Percentages without misleading zeros: 0 -> '0%', 0 < x < 1 -> '<1%'."""
    if not finite(x):
        return "Not estimable"
    if x == 0:
        return "0%"
    if x < 1:
        return "<1%"
    return f"{x:.0f}%"


def fmt_days(x):
    if not finite(x):
        return "Not estimable"
    if x == 0:
        return "0"
    if x < 0.01:
        return "<0.01"
    return f"{x:.2f}" if x < 1 else f"{x:.1f}"


def pressure_level(beds, ref, waited_pct, unresolved):
    """Modelled capacity pressure for one run. A reading of model outputs, not a guarantee.
    High: requests still unserved after follow-up, or >=20% of requests wait.
    Moderate: available beds below the busy-day reference, or >=5% wait.  Low: otherwise."""
    return {"over": "high", "tight": "moderate", "ok": "low"}[capacity_status(beds, ref, waited_pct, unresolved)]


def pressure_pair(R):
    out = {}
    for sc in ("Baseline", "Scenario"):
        ref, _ = R.nb(sc)
        w, _ = R.m("waited_pct", sc)
        u, _ = R.m("unresolved_requests", sc)
        out[sc] = dict(ref=ref, waited=w, unres=u, level=pressure_level(R.s["beds"], ref, w, u))
    return out


def lever_phrase(R):
    s = R.s
    gl = H.group_label(R.group)
    parts = []
    if s["reduction"]:
        parts.append(f"{s['reduction']}% shorter stays for {gl}{age_phrase(s['age'])}")
    if s["demand"]:
        parts.append(f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'less'} admission demand")
    if s["readmit"]:
        parts.append(f"{s['readmit']}% fewer return stays")
    if not parts:
        return ""
    txt = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return txt[0].upper() + txt[1:]


def round_nice(x):
    x = abs(x)
    if x >= 1000:
        return f"{round(x, -1):,.0f}"
    return f"{x:,.0f}"


def key_message(R):
    """Single management headline built only from this run's outputs."""
    s = R.s
    days = s["duration"]
    phrase = lever_phrase(R)
    if not phrase:
        return dict(headline="No assumptions were changed, so this run shows the baseline hospital.",
                    sub="Change length of stay, demand, beds or return stays in the simulator to test a scenario.")
    bd, _, bdclear = R.e("bed_days")
    (nbb, _), (nbs, _) = R.nb("Baseline"), R.nb("Scenario")
    dnb, _, nbclear = R.nb_effect()
    (wb, _), (ws, _) = R.m("waited_pct", "Baseline"), R.m("waited_pct", "Scenario")
    if bdclear:
        verb = "release" if bd < 0 else "add"
        head = f"{phrase} would {verb} about <b>{round_nice(bd)} modelled bed-days</b> over {days} days"
    elif finite(wb) and finite(ws) and abs(ws - wb) >= 1:
        head = (f"{phrase}: total bed-days stay about the same because beds are full, but the share of bed requests "
                f"that wait goes from <b>{fmt_pct_small(wb)} to {fmt_pct_small(ws)}</b>")
    else:
        head = f"{phrase} would make <b>no clear difference</b> to total bed-days over {days} days"
    if nbclear:
        head += f", moving the busy-day bed reference from about <b>{nbb:,.0f} to {nbs:,.0f} beds</b>."
    else:
        head += f"; the busy-day bed reference stays at about <b>{nbs:,.0f} beds</b>."
    return dict(headline=head, sub="")


def pressure_sentence(R):
    p = pressure_pair(R)
    beds = R.s["beds"]
    gap = beds - p["Scenario"]["ref"]
    if p["Scenario"]["unres"] > 0:
        return (f"With {beds:,} beds, some requests are still waiting long after the period ends — the bed pool is "
                "overloaded under these assumptions.")
    where = f"{abs(gap):,.0f} beds below" if gap >= 0 else f"{abs(gap):,.0f} beds above"
    tail = ("short waits are still possible on peak days" if gap >= 0 else "waiting on peak days is likely")
    return f"With {beds:,} beds available, the scenario's busy-day reference is {where} that capacity, so {tail}."


def wait_change_phrase(wb, ws):
    a, b = fmt_pct_small(wb), fmt_pct_small(ws)
    return f"stay at {a}" if a == b else f"go from {a} to {b}"


def short_insights(R):
    """At most three one-sentence answers: what changed / what contributed / planning meaning."""
    s = R.s
    levers = R.levers()
    days = s["duration"]
    bd, _, bdclear = R.e("bed_days")
    base_bd, _ = R.m("bed_days", "Baseline")
    (wb, _), (ws, _) = R.m("waited_pct", "Baseline"), R.m("waited_pct", "Scenario")
    if not levers:
        what = "Nothing was changed, so baseline and scenario differ only by random variation."
    elif bdclear:
        p = pct_change(bd, base_bd)
        what = (f"Modelled bed-days {'fall' if bd < 0 else 'rise'} by {abs(bd):,.0f} ({p:+.1f}%) over {days} days; "
                f"bed requests that wait {wait_change_phrase(wb, ws)}.")
    else:
        what = f"Total bed-days show no clear change; bed requests that wait {wait_change_phrase(wb, ws)}."
    scope = {"los": f"shorter stays ({H.group_label(R.group, True)} only)",
             "demand": f"{s['demand']:+d}% demand (whole hospital)",
             "readmit": f"fewer return stays (whole hospital)"}
    singles = {"los": "LOS only", "demand": "Demand only", "readmit": "Readmissions only"}
    if not levers:
        why = "No assumption was active."
    elif len(levers) == 1:
        why = f"The only change is {scope[levers[0]]}, so it accounts for the difference."
    elif all(singles[l] in R.scenarios for l in levers):
        eff = {l: R.e("bed_days", singles[l])[0] for l in levers}
        down = [scope[l] for l in levers if eff[l] < 0]
        up = [scope[l] for l in levers if eff[l] > 0]
        bits = []
        if down:
            bits.append(" and ".join(down) + (" lower" if len(down) > 1 else " lowers") + " bed use")
        if up:
            bits.append(" and ".join(up) + (" raise" if len(up) > 1 else " raises") + " it")
        txt = "; ".join(bits) if bits else "No single assumption shows a clear effect on its own"
        why = txt[0].upper() + txt[1:] + " — the effects interact because all patients share one pool of beds."
    else:
        why = ("Several assumptions changed together (" + ", ".join(scope[l] for l in levers) +
               "); their effects interact.")
    return dict(what=what, why=why, meaning=pressure_sentence(R))


def delay_if_waited(R, sc):
    """Approximate average wait of requests that did wait = mean wait (all requests) / share waiting.
    Ratio of replication means (pooled-ratio estimate); None when nobody waited or not estimable."""
    mw, _ = R.m("mean_wait_days", sc)
    w, _ = R.m("waited_pct", sc)
    if not (finite(mw) and finite(w)) or w <= 0:
        return None
    return mw / (w / 100.0)


def dx_bed_use(R):
    """Average beds in use by diagnosis group (estimate) for Baseline and Scenario.

    Initial stays: Little's law, average beds = admissions per day x average modelled stay, using the cohort
    outputs of simulate() (both replication means). Return stays are not tracked by diagnosis, so they are
    reported as one remainder: model average occupied beds minus the diagnosis estimates. In tests this
    reconciles with the model's own occupancy to within about 1% when few requests wait. It is an average,
    not a busy-day requirement, and diagnosis groups are not separately staffed wards.
    """
    days = R.s["duration"]
    sub = R.sub[R.sub.scenario.isin(["Baseline", "Scenario"])].copy()
    sub["beds"] = sub.admissions * sub.mean_index_los / days
    sub["diagnosis"] = sub.group.str.split("|").str[0]
    dx = sub.groupby(["scenario", "diagnosis"], sort=False).beds.sum().reset_index()
    rows, constrained = [], False
    for sc in ("Baseline", "Scenario"):
        part = dx[dx.scenario == sc]
        occ, _ = R.m("avg_occupied", sc)
        w, _ = R.m("waited_pct", sc)
        u, _ = R.m("unresolved_requests", sc)
        if u > 0 or not finite(w) or w >= 20 or occ - part.beds.sum() <= 0:
            constrained = True
    for sc in ("Baseline", "Scenario"):
        part = dx[dx.scenario == sc]
        for r in part.itertuples():
            rows.append(dict(scenario=sc, label=r.diagnosis, beds=float(r.beds), kind="dx"))
        if not constrained:
            occ, _ = R.m("avg_occupied", sc)
            rows.append(dict(scenario=sc, label="Return stays (all groups)", beds=float(occ - part.beds.sum()),
                             kind="rest"))
    out = pd.DataFrame(rows)
    # When many requests queue, patients waiting are not in beds: the figures then describe bed DEMAND, and the
    # remainder against actual occupancy is not meaningful, so it is omitted.
    out.attrs["constrained"] = constrained
    return out


def dx_los(R):
    """Admissions-weighted average modelled initial stay by diagnosis, plus the target group, Baseline vs Scenario."""
    sub = R.sub[R.sub.scenario.isin(["Baseline", "Scenario"])].copy()
    sub["diagnosis"] = sub.group.str.split("|").str[0]
    sub["bd"] = sub.admissions * sub.mean_index_los
    g = sub.groupby(["scenario", "diagnosis"], sort=False)[["bd", "admissions"]].sum().reset_index()
    g["los"] = g.bd / g.admissions
    rows = [dict(scenario=r.scenario, label=f"All {r.diagnosis}", los=float(r.los)) for r in g.itertuples()]
    # The target-group row only when the completed run applied a length-of-stay reduction (R.s = settings saved
    # with the result, not the builder's current or default patient-group selection).
    if R.s.get("reduction", 0) > 0:
        for sc in ("Baseline", "Scenario"):
            rows.append(dict(scenario=sc, label=H.group_label(R.group) + " (target)",
                             los=R.m("target_mean_los", sc)[0]))
    return pd.DataFrame(rows)


def dx_admissions(R):
    days = R.s["duration"]
    sub = R.sub[R.sub.scenario.isin(["Baseline", "Scenario"])].copy()
    sub["diagnosis"] = sub.group.str.split("|").str[0]
    g = sub.groupby(["scenario", "diagnosis"], sort=False).admissions.sum().reset_index()
    g["per_day"] = g.admissions / days
    return g


def compare_record(R, settings, bed_mode):
    """Everything the comparison view needs, stored with the run's assumptions."""
    p = pressure_pair(R)
    bd, _, bdclear = R.e("bed_days")
    return dict(name=scenario_name(settings), settings=dict(settings), bed_mode=bed_mode,
                beds=settings["beds"], ref_base=p["Baseline"]["ref"], ref_scen=p["Scenario"]["ref"],
                bd=bd, bd_clear=bdclear, waited_base=p["Baseline"]["waited"], waited=p["Scenario"]["waited"],
                unres=p["Scenario"]["unres"], tlos_base=R.m("target_mean_los", "Baseline")[0],
                tlos=R.m("target_mean_los", "Scenario")[0], pressure=p["Scenario"]["level"],
                pressure_base=p["Baseline"]["level"])
