"""Historical (2011-12 calibration) summaries for the Hospital Capacity Planner frontend.

Every number here is computed directly from ``calibration.npz`` through ``simulation.calibration()``.
Nothing in this module changes or re-implements simulation behaviour; the two functions that mirror
model rules (``expected_admissions`` and ``los_rule_preview``) copy the exact expressions used in
``simulation._run_one`` so the frontend can describe a scenario *before* it is run.

Definitions used throughout
---------------------------
* Initial admission  - one calibrated encounter row (index stay). 141,810 in total.
* Data period        - admissions dated 1 Jul 2011 to 30 Jun 2012 (366 days; 2012 is a leap year).
* Recorded LOS       - ADMIT_LOS as recorded (same-day stays = 0 days).
* Bed-days           - sum of max(recorded LOS, 1): a same-day stay uses one bed-day, the same rule
                       the daily-resolution model applies (574 stays are affected).
* Return stay        - a recorded readmission linked to a survivor-coded index stay (valid timing,
                       1-60 days after discharge). Death-coded stays with a readmission flag (761)
                       are excluded, exactly as in the model's calibration.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

import simulation as S

DATA_START = pd.Timestamp("2011-07-01")
DATA_END = pd.Timestamp("2012-06-30")
DATA_DAYS = int((DATA_END - DATA_START).days) + 1          # 366
PERIOD_LABEL = "1 July 2011 - 30 June 2012"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_FULL = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "May": "May",
              "Jun": "June", "Jul": "July", "Aug": "August", "Sep": "September", "Oct": "October",
              "Nov": "November", "Dec": "December"}
CAL_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DIAGNOSIS_NAMES = {"AMI": "Acute myocardial infarction",
                   "CHF": "Congestive heart failure",
                   "COPD": "Chronic obstructive pulmonary disease"}
SEVERITY_NAMES = {1: "minor", 2: "moderate", 3: "major", 4: "extreme"}
AGE_BANDS = ["All ages", "Under 65", "65 and over"]


def cal():
    return S.calibration()


def groups():
    return [str(x) for x in cal()["groups"]]


def diagnoses():
    return sorted({g.split("|")[0] for g in groups()})


def severities(diagnosis):
    return sorted(int(g.split("|")[1]) for g in groups() if g.split("|")[0] == diagnosis)


def group_label(group, short=False):
    dx, sev = group.split("|")
    return f"{dx} S{sev}" if short else f"{dx} · Severity {sev}"


def _age_mask(ages, age):
    """Identical expression to simulation._run_one's age filter."""
    if age == "All ages":
        return np.ones(len(ages), bool)
    return ages < 65 if age == "Under 65" else ages >= 65


# --------------------------------------------------------------------------- snapshot
@lru_cache(maxsize=1)
def snapshot():
    d = cal()
    G = len(groups())
    los = [d[f"los_{g}"].astype(int) for g in range(G)]
    n = int(sum(len(x) for x in los))
    recorded = int(sum(x.sum() for x in los))
    bed_days = int(sum(np.maximum(x, 1).sum() for x in los))
    returns = int(sum(len(d[f"ret_delay_{g}"]) for g in range(G)))
    return_bed_days = int(sum(d[f"ret_los_{g}"].sum() for g in range(G)))
    return dict(admissions=n, days=DATA_DAYS, admissions_per_day=n / DATA_DAYS,
                mean_los=recorded / n, bed_days=bed_days, avg_beds_initial=bed_days / DATA_DAYS,
                returns=returns, return_bed_days=return_bed_days,
                zero_los=int(d["zero_los_total"]) if "zero_los_total" in d else None,
                conflicts=int(d["death_return_conflicts_total"]) if "death_return_conflicts_total" in d else None)


# --------------------------------------------------------------------------- patient groups
@lru_cache(maxsize=1)
def group_table():
    """One row per diagnosis x severity group (historical, initial stays)."""
    d = cal()
    rows = []
    total_bd = snapshot()["bed_days"]
    total_n = snapshot()["admissions"]
    for gi, g in enumerate(groups()):
        los = d[f"los_{gi}"].astype(int)
        ages = d[f"ages_{gi}"]
        died = d[f"died_{gi}"] if f"died_{gi}" in d else np.zeros(len(los), bool)
        bd = int(np.maximum(los, 1).sum())
        dx, sev = g.split("|")
        rows.append(dict(
            group=g, diagnosis=dx, severity=int(sev), label=group_label(g), short=group_label(g, True),
            admissions=len(los), adm_share=100 * len(los) / total_n,
            mean_los=float(los.mean()), median_los=float(np.median(los)),
            bed_days=bd, bd_share=100 * bd / total_bd,
            pct_65_plus=100 * float((ages >= 65).mean()),
            death_pct=100 * float(died.mean()),
            return_pct_survivors=100 * float(d.get(f"prob_survivor_{gi}", d[f"prob_{gi}"])),
            returns=int(len(d[f"ret_delay_{gi}"]))))
    return pd.DataFrame(rows)


def diagnosis_table():
    """Group table aggregated to diagnosis level (severities pooled, admissions-weighted)."""
    t = group_table()
    out = []
    for dx, s in t.groupby("diagnosis", sort=True):
        n = int(s.admissions.sum())
        out.append(dict(diagnosis=dx, label=dx, admissions=n, adm_share=float(s.adm_share.sum()),
                        mean_los=float((s.mean_los * s.admissions).sum() / n),
                        bed_days=int(s.bed_days.sum()), bd_share=float(s.bd_share.sum()),
                        returns=int(s.returns.sum())))
    return pd.DataFrame(out)


def group_detail(group, age="All ages"):
    """Historical facts for one group, optionally restricted to the model's age bands."""
    d = cal()
    gi = groups().index(group)
    los = d[f"los_{gi}"].astype(int)
    ages = d[f"ages_{gi}"]
    died = d[f"died_{gi}"] if f"died_{gi}" in d else np.zeros(len(los), bool)
    m = _age_mask(ages, age)
    n = int(m.sum())
    return dict(group=group, age=age, admissions=n,
                admissions_per_day=n / DATA_DAYS,
                mean_los=float(los[m].mean()) if n else float("nan"),
                median_los=float(np.median(los[m])) if n else float("nan"),
                bed_days=int(np.maximum(los[m], 1).sum()),
                bd_share=100 * int(np.maximum(los[m], 1).sum()) / snapshot()["bed_days"],
                death_pct=100 * float(died[m].mean()) if n else float("nan"),
                group_total=len(los))


def age_breakdown(group):
    d = cal()
    gi = groups().index(group)
    los = d[f"los_{gi}"].astype(int)
    ages = d[f"ages_{gi}"]
    rows = []
    for band in ("Under 65", "65 and over"):
        m = _age_mask(ages, band)
        rows.append({"Age band": band, "Admissions": int(m.sum()),
                     "Share of group": f"{100 * m.mean():.0f}%",
                     "Average stay (days)": round(float(los[m].mean()), 1) if m.any() else None,
                     "Bed-days": int(np.maximum(los[m], 1).sum())})
    return pd.DataFrame(rows)


def interpret_group_ranking(metric, by="group"):
    """Short data-grounded interpretation for the patient-group chart."""
    t = group_table() if by == "group" else diagnosis_table()
    snap = snapshot()
    name = "label"
    if metric == "bed_days":
        top = t.sort_values("bed_days", ascending=False).iloc[0]
        los_ratio = top.mean_los / snap["mean_los"]
        if top.adm_share >= 20 and los_ratio >= 1.05:
            driver = "both a large number of admissions and longer-than-average stays"
        elif los_ratio >= 1.05:
            driver = "longer-than-average stays more than admission volume"
        elif top.adm_share >= 20:
            driver = "its large number of admissions rather than unusually long stays"
        else:
            driver = "a combination of admission volume and stay length"
        txt = (f"<b>{top[name]}</b> used the most bed-days: {top.bed_days:,.0f} "
               f"({top.bd_share:.0f}% of all initial-stay bed-days) from {top.adm_share:.0f}% of admissions. "
               f"Its average stay was {top.mean_los:.1f} days versus {snap['mean_los']:.1f} days overall, "
               f"so its share reflects {driver}.")
        long = t[(t.mean_los >= 1.4 * snap["mean_los"])]
        long = long[long[name] != top[name]]
        if len(long):
            r = long.sort_values("mean_los", ascending=False).iloc[0]
            txt += (f" <b>{r[name]}</b> has the longest stays ({r.mean_los:.1f} days on average) "
                    f"but only {r.adm_share:.0f}% of admissions, so it uses {r.bd_share:.0f}% of bed-days.")
        return txt
    if metric == "admissions":
        s = t.sort_values("admissions", ascending=False)
        top2 = s.head(2)
        return (f"<b>{top2.iloc[0][name]}</b> and <b>{top2.iloc[1][name]}</b> together account for "
                f"{top2.adm_share.sum():.0f}% of all initial admissions.")
    s = t.sort_values("mean_los", ascending=False)
    hi, lo = s.iloc[0], s.iloc[-1]
    txt = (f"Average stays range from {lo.mean_los:.1f} days (<b>{lo[name]}</b>) to "
           f"{hi.mean_los:.1f} days (<b>{hi[name]}</b>).")
    if by == "group":
        rising = all(np.all(np.diff(x.sort_values("severity").mean_los.values) > 0)
                     for _, x in t.groupby("diagnosis"))
        if rising:
            txt += " In every diagnosis, average stay rises with each recorded severity level."
    return txt


# --------------------------------------------------------------------------- admission demand
@lru_cache(maxsize=1)
def monthly_demand():
    """Observed admissions by calendar month of the data year.

    calibration rates_m[m, :, g] = (admissions in month m / days in month m) x weekday factor with
    mean 1, so the weekday-mean of rates_m recovers the observed monthly daily average exactly.
    """
    d = cal()
    days = pd.date_range(DATA_START, DATA_END)
    rows = []
    for m in S.MONTHS:                        # Jul .. Jun (data-year order)
        mi = CAL_MONTHS.index(m)
        n_days = int((days.month == mi + 1).sum())
        per_day = float(d["rates_m"][mi].mean(axis=0).sum())
        year = 2011 if mi + 1 >= 7 else 2012
        rows.append(dict(month=m, label=f"{m} {year}", days=n_days, per_day=per_day,
                         admissions=int(round(per_day * n_days))))
    return pd.DataFrame(rows)


def weekday_pattern(month=None):
    """Admissions per day by weekday.

    month=None -> whole data year, directly observed (admissions on that weekday / number of such days).
    month='Jan' etc. -> the model's calibrated month x weekday rates. These are an approximation
    (observed monthly level x annual weekday profile), NOT observed counts for that month.
    """
    d = cal()
    if month is None:
        vals = d["rates"].sum(axis=1)
        kind = "observed"
    else:
        vals = d["rates_m"][CAL_MONTHS.index(month)].sum(axis=1)
        kind = "calibrated"
    return pd.DataFrame({"weekday": WEEKDAYS, "per_day": vals.astype(float)}), kind


def interpret_weekday(df):
    hi, lo = df.loc[df.per_day.idxmax()], df.loc[df.per_day.idxmin()]
    ratio = hi.per_day / lo.per_day if lo.per_day > 0 else float("nan")
    return (f"Admissions peak on <b>{hi.weekday}</b> (about {hi.per_day:,.0f} per day) and are lowest on "
            f"<b>{lo.weekday}</b> (about {lo.per_day:,.0f}) - roughly {ratio:.1f}× as many on the busiest day. "
            "Uneven weekday arrivals mean bed pressure can build on particular days even when the average looks manageable.")


def interpret_monthly(df):
    hi, lo = df.loc[df.per_day.idxmax()], df.loc[df.per_day.idxmin()]
    return (f"The highest month is <b>{hi.label}</b> ({hi.per_day:,.0f} admissions per day) and the lowest is "
            f"<b>{lo.label}</b> ({lo.per_day:,.0f} per day).")


# --------------------------------------------------------------------------- scenario previews
def sim_dates(season, days):
    """Calendar dates of simulation Day 1..days, using the model's own start-date rule."""
    start = S.season_start(season, cal())
    return pd.date_range(start, periods=days, freq="D")


def is_seasonal(season):
    return season != "Annual average" and "rates_m" in cal()


def expected_admissions(season, days, group=None):
    """Expected initial admissions per day over the simulated window (before any demand change).

    Uses exactly the arrival-rate lookup in simulation._run_one:
    rates_m[month-1][weekday] when a month-based pattern is used, otherwise rates[weekday].
    The model draws Poisson counts around these rates, so actual simulated counts vary.
    """
    d = cal()
    gi = None if group is None else groups().index(group)
    seasonal = is_seasonal(season)
    total = 0.0
    for date in sim_dates(season, days):
        r = d["rates_m"][date.month - 1][date.dayofweek] if seasonal else d["rates"][date.dayofweek]
        total += float(r.sum() if gi is None else r[gi])
    return total / days


def months_covered(season, days):
    """Ordered calendar-month names the simulation passes through, with day counts."""
    dates = sim_dates(season, days)
    out = []
    for m in dates.month:
        name = CAL_MONTHS[m - 1]
        if out and out[-1][0] == name:
            out[-1][1] += 1
        else:
            out.append([name, 1])
    return out


def los_rule_preview(group, age, pct):
    """Apply the model's LOS rule to the group's historical stays (no simulation).

    Mirrors simulation._run_one: stays = max(1, LOS); eligible = age band & survived;
    cut = min(stay, max(1, rint(stay x (1 - pct/100)))). Returns shares, not a forecast.
    """
    d = cal()
    gi = groups().index(group)
    stays = np.maximum(1, d[f"los_{gi}"].astype(int))
    died = d[f"died_{gi}"] if f"died_{gi}" in d else np.zeros(len(stays), bool)
    ok = _age_mask(d[f"ages_{gi}"], age) & ~died
    cut = np.minimum(stays, np.maximum(1, np.rint(stays * (1 - pct / 100)).astype(int)))
    shortened = ok & (cut < stays)
    return dict(n=len(stays), eligible_pct=100 * ok.mean(), shortened_pct=100 * shortened.mean(),
                shortened_of_eligible_pct=100 * shortened.sum() / max(ok.sum(), 1),
                deaths_pct=100 * died.mean(),
                age_excluded_pct=100 * (~_age_mask(d[f"ages_{gi}"], age)).mean())


# --------------------------------------------------------------------------- v3.1 overview helpers
def one_line_insight(metric):
    """One concise, data-grounded sentence for the patient-group chart."""
    t = group_table()
    snap = snapshot()
    if metric == "bed_days":
        top = t.sort_values("bed_days", ascending=False).iloc[0]
        why = ("more admissions and longer stays" if top.adm_share >= 20 and top.mean_los >= 1.05 * snap["mean_los"]
               else "longer stays" if top.mean_los >= 1.05 * snap["mean_los"] else "its admission volume")
        return (f"<b>{top.label}</b> uses <b>{top.bd_share:.0f}%</b> of all bed-days from {top.adm_share:.0f}% of "
                f"admissions — driven by {why} (average stay {top.mean_los:.1f} vs {snap['mean_los']:.1f} days overall).")
    if metric == "admissions":
        top2 = t.sort_values("admissions", ascending=False).head(2)
        return (f"<b>{top2.iloc[0].label}</b> and <b>{top2.iloc[1].label}</b> account for "
                f"<b>{top2.adm_share.sum():.0f}%</b> of all admissions.")
    s = t.sort_values("mean_los", ascending=False)
    return (f"Average stays range from {s.iloc[-1].mean_los:.1f} days (<b>{s.iloc[-1].label}</b>) to "
            f"<b>{s.iloc[0].mean_los:.1f} days</b> (<b>{s.iloc[0].label}</b>); stays lengthen with severity.")


def month_weekday_grid():
    """12 x 7 grid of the model's calibrated admissions/day (data-year order Jul..Jun).

    Cells are the calibration's month x weekday rates = observed monthly average x whole-year weekday
    profile (an approximation, not observed counts). Row totals (observed monthly averages) come from
    monthly_demand()."""
    d = cal()
    md = monthly_demand()
    z = [d["rates_m"][CAL_MONTHS.index(m)].sum(axis=1).astype(float).tolist() for m in md.month]
    return md, z


def demand_extremes():
    md = monthly_demand()
    wd, _ = weekday_pattern()
    return dict(busy_month=md.loc[md.per_day.idxmax()], quiet_month=md.loc[md.per_day.idxmin()],
                busy_day=wd.loc[wd.per_day.idxmax()], quiet_day=wd.loc[wd.per_day.idxmin()])


# --------------------------------------------------------------------------- v3.4 demand-story helpers
# Return stays (verified against build_calibration.py):
#   * at most one recorded return per initial admission (READMIT_* columns sit on the index encounter row);
#   * counted only for index stays NOT ending in in-hospital death (eligible survivors);
#   * every recorded return began 1-60 days after discharge (observed range of ret_delay);
#   * return LOS = READMIT_LOS (duration of the return stay) - NOT the delay before returning;
#   * return dates are not stored and returns are not linked to individual index stays in calibration.npz,
#     so returns cannot be placed on calendar dates or split by age band.
RETURN_RATE_LABEL = "Returned within 60 days"
RETURN_RATE_DEF = ("Share of initial admissions discharged alive that had a recorded return stay starting 1–60 days "
                   "after discharge. One return at most is counted per initial admission. Initial stays ending in "
                   "death are excluded from the denominator.")


@lru_cache(maxsize=1)
def demand_sources():
    """Initial vs return stays: counts, average stay, bed-days (same-day stays count as one bed-day)."""
    d = cal()
    G = len(groups())
    los = np.concatenate([d[f"los_{g}"].astype(int) for g in range(G)])
    died = np.concatenate([d[f"died_{g}"] for g in range(G)])
    rlos = np.concatenate([d[f"ret_los_{g}"].astype(int) for g in range(G)])
    ini_bd = int(np.maximum(los, 1).sum())
    ret_bd = int(np.maximum(rlos, 1).sum())
    survivors = int((~died).sum())
    return dict(ini_n=int(len(los)), ini_per_day=len(los) / DATA_DAYS, ini_mean_los=float(np.maximum(los, 1).mean()),
                ini_bd=ini_bd, ret_n=int(len(rlos)), ret_mean_los=float(np.maximum(rlos, 1).mean()), ret_bd=ret_bd,
                survivors=survivors, ret_rate=100 * len(rlos) / survivors, total_bd=ini_bd + ret_bd,
                ret_share=100 * ret_bd / (ini_bd + ret_bd))


@lru_cache(maxsize=1)
def group_demand_table():
    """Per diagnosis x severity group: initial and attributable return-stay demand (all ages)."""
    d = cal()
    base = group_table().set_index("group")
    tot = demand_sources()["total_bd"]
    rows = []
    for gi, g in enumerate(groups()):
        los = d[f"los_{gi}"].astype(int)
        died = d[f"died_{gi}"]
        rlos = d[f"ret_los_{gi}"].astype(int)
        surv = int((~died).sum())
        ini_bd = int(np.maximum(los, 1).sum())
        ret_bd = int(np.maximum(rlos, 1).sum())
        r = base.loc[g]
        rows.append(dict(group=g, label=r.label, short=r.short, diagnosis=r.diagnosis, severity=r.severity,
                         admissions=int(len(los)), adm_share=float(r.adm_share), mean_los=float(np.maximum(los, 1).mean()),
                         ini_bd=ini_bd, survivors=surv, returns=int(len(rlos)),
                         ret_rate=100 * len(rlos) / surv if surv else float("nan"),
                         ret_mean_los=float(np.maximum(rlos, 1).mean()) if len(rlos) else float("nan"),
                         ret_bd=ret_bd, total_bd=ini_bd + ret_bd, total_share=100 * (ini_bd + ret_bd) / tot))
    return pd.DataFrame(rows)


def group_story(group):
    """Short, data-grounded reading of why a group carries the bed-day burden it does (no clinical claims)."""
    t = group_demand_table()
    src = demand_sources()
    r = t.set_index("group").loc[group]
    rank = int((t.total_bd > r.total_bd).sum()) + 1
    traits = []
    if r.adm_share >= 12:
        traits.append(f"many admissions ({r.adm_share:.0f}% of all)")
    if r.mean_los >= 1.1 * src["ini_mean_los"]:
        traits.append(f"longer initial stays ({r.mean_los:.1f} vs {src['ini_mean_los']:.1f} days on average)")
    if r.returns and r.ret_rate >= 1.1 * src["ret_rate"]:
        traits.append(f"a higher return rate ({r.ret_rate:.0f}% vs {src['ret_rate']:.0f}%)")
    head = f"<b>{r.label}</b> accounts for <b>{r.total_share:.1f}%</b> of historical bed-days (#{rank} of {len(t)})"
    if traits:
        head += ", driven by " + (traits[0] if len(traits) == 1 else ", ".join(traits[:-1]) + " and " + traits[-1])
    head += "."
    if r.total_share >= 10:
        head += " That substantial share makes it a useful group to explore in a what-if scenario."
    elif r.total_share < 3:
        head += " Because its share is small, a change for this group alone is likely to move hospital-wide bed use only a little."
    return head


def monthly_highlight():
    md = monthly_demand()
    wd, _ = weekday_pattern()
    hi = md.loc[md.per_day.idxmax()]
    late = md[~md.month.isin(["Jul", "Aug", "Sep"])]
    lo = late.loc[late.per_day.idxmin()]
    whi, wlo = wd.loc[wd.per_day.idxmax()], wd.loc[wd.per_day.idxmin()]
    return (f"Busiest month: <b>{hi.label}</b> ({hi.per_day:,.0f} admissions/day); from October onwards the quietest was "
            f"<b>{lo.label}</b> ({lo.per_day:,.0f}/day). <b>{WEEKDAY_FULL[whi.weekday]}s</b> are the busiest weekday "
            f"({whi.per_day:,.0f}/day), <b>{WEEKDAY_FULL[wlo.weekday]}s</b> the quietest ({wlo.per_day:,.0f}/day).")


WEEKDAY_FULL = dict(Mon="Monday", Tue="Tuesday", Wed="Wednesday", Thu="Thursday", Fri="Friday", Sat="Saturday",
                    Sun="Sunday")


# --------------------------------------------------------------------------- v3.5 concise insights
def group_why(group):
    """One sentence for 'Why explore this group?' - descriptive, built from the data, no clinical claims."""
    t = group_demand_table()
    src = demand_sources()
    r = t.set_index("group").loc[group]
    rank = int((t.total_bd > r.total_bd).sum()) + 1
    drivers = []
    if r.adm_share >= 12:
        drivers.append("high admission volume")
    if r.mean_los >= 1.1 * src["ini_mean_los"]:
        drivers.append("longer stays")
    if r.returns and r.ret_rate >= 1.1 * src["ret_rate"]:
        drivers.append("frequent readmissions")
    txt = f"{r.label} contributes {r.total_share:.0f}% of recorded bed-days (#{rank} of {len(t)})"
    if r.total_share < 1:
        txt = f"{r.label} contributes under 1% of recorded bed-days (#{rank} of {len(t)})"
    if drivers:
        txt += ", mainly through " + (drivers[0] if len(drivers) == 1 else ", ".join(drivers[:-1]) + " and " + drivers[-1])
    if r.total_share >= 10:
        txt += " — a useful group to explore in a capacity scenario."
    elif r.total_share < 3:
        txt += " — a change for this group alone would move hospital-wide bed use only a little."
    else:
        txt += "."
    return txt


def peak_insight(view):
    """Key-insight content for the selected time view (observed initial admissions per day)."""
    if view == "Monthly":
        md = monthly_demand()
        hi, lo = md.loc[md.per_day.idxmax()], md.loc[md.per_day.idxmin()]
        return dict(hi_label="Busiest month", hi=hi.label, hi_v=hi.per_day, lo_label="Quietest month", lo=lo.label,
                    lo_v=lo.per_day,
                    note=f"Daily admissions in {hi.label} were about {hi.per_day / lo.per_day:.1f}× those in {lo.label}. "
                         "Choosing a starting month lets your scenario test busier or quieter periods.")
    wd, _ = weekday_pattern()
    hi, lo = wd.loc[wd.per_day.idxmax()], wd.loc[wd.per_day.idxmin()]
    return dict(hi_label="Busiest weekday", hi=WEEKDAY_FULL[hi.weekday], hi_v=hi.per_day, lo_label="Quietest weekday",
                lo=WEEKDAY_FULL[lo.weekday], lo_v=lo.per_day,
                note=f"{WEEKDAY_FULL[hi.weekday]} admissions are about {hi.per_day / lo.per_day:.1f}× "
                     f"{WEEKDAY_FULL[lo.weekday]}'s, so bed pressure tends to build at the same point each week.")


# --------------------------------------------------------------------------- v3.6 hierarchical explorer
@lru_cache(maxsize=1)
def dx_demand_table():
    """Diagnosis level = sum of its severity groups (initial + attributable return stays)."""
    t = group_demand_table()
    out = []
    for dx, s in t.groupby("diagnosis", sort=False):
        adm, ret, surv = int(s.admissions.sum()), int(s.returns.sum()), int(s.survivors.sum())
        ini_bd, ret_bd = int(s.ini_bd.sum()), int(s.ret_bd.sum())
        out.append(dict(diagnosis=dx, label=dx, name=DIAGNOSIS_NAMES.get(dx, dx), admissions=adm, returns=ret,
                        survivors=surv, ret_rate=100 * ret / surv if surv else float("nan"),
                        mean_los=ini_bd / adm, ret_mean_los=ret_bd / ret if ret else float("nan"),
                        ini_bd=ini_bd, ret_bd=ret_bd, total_bd=ini_bd + ret_bd,
                        total_share=float(s.total_share.sum()), severities=sorted(s.severity.tolist())))
    return pd.DataFrame(out).sort_values("total_bd", ascending=False).reset_index(drop=True)


def severity_breakdown(diagnosis):
    t = group_demand_table()
    s = t[t.diagnosis == diagnosis].copy()
    s["share_in_dx"] = 100 * s.total_bd / s.total_bd.sum()
    return s.sort_values("severity").reset_index(drop=True)


def age_split(group):
    """Initial stays by the model's age bands (<65 / >=65; ages missing in the raw data were median-filled
    during calibration). Bands are exhaustive, so they add up to the group. Returns are not recorded by age."""
    rows = []
    tot = group_detail(group)["bed_days"]
    for band in ("Under 65", "65 and over"):
        g = group_detail(group, band)
        rows.append(dict(band=band, admissions=g["admissions"], mean_los=g["mean_los"], ini_bd=g["bed_days"],
                         share=100 * g["bed_days"] / tot if tot else float("nan")))
    return pd.DataFrame(rows)


def beds_equivalent(bed_days):
    """Average historical bed-use equivalent: recorded bed-days / days in the data year."""
    return bed_days / DATA_DAYS


def dx_insight():
    t = dx_demand_table()
    top = t.iloc[0]
    return f"{top.label} contributes the largest share of recorded bed-days ({top.total_share:.0f}%)."


def severity_insight(diagnosis):
    s = severity_breakdown(diagnosis)
    top = s.loc[s.total_bd.idxmax()]
    return (f"Severity {top.severity} accounts for the greatest bed-day burden within {diagnosis} "
            f"({top.share_in_dx:.0f}% of its recorded bed-days).")


def age_insight(group, age):
    if age == "All ages":
        a = age_split(group).set_index("band")
        older = a.loc["65 and over"]
        return (f"Among {group_label(group)} stays, patients aged 65 and over account for {older.share:.0f}% of the "
                "group's initial-stay bed-days.")
    a = age_split(group).set_index("band").loc[age]
    return (f"Among {group_label(group)} stays, patients {age.lower()} contribute {a.share:.0f}% of the group's "
            "initial-stay bed-days.")


# --------------------------------------------------------------------------- v3.7 observed admission calendar
# history_calendar.npz is built from the original CSV by build_history_calendar.py (same cleaning rules as the
# model). It holds aggregated daily counts only. If it is missing, the page falls back to initial admissions
# from calibration.npz.
SOURCES = {"total": "Total Admissions", "initial": "Initial Admissions", "readmissions": "Readmissions"}
INCOMPLETE_MONTHS = ("Jul", "Aug")      # Jul-Aug 2011: readmissions of patients admitted before July 2011 not in data


@lru_cache(maxsize=1)
def _calendar():
    p = Path(S.__file__).with_name("history_calendar.npz")
    if not p.exists():
        return None
    with np.load(p, allow_pickle=False) as h:
        out = {k: h[k] for k in h.files}
    out["meta"] = dict(zip(out["meta_keys"].tolist(), out["meta_values"].tolist()))
    return out


def calendar_available():
    return _calendar() is not None


def daily_counts(source, group=None):
    """Observed counts per day within the reference period (1 Jul 2011 - 30 Jun 2012), all groups or one group."""
    h = _calendar()
    days = pd.date_range(DATA_START, DATA_END)
    gi = None if group is None else [str(g) for g in h["groups"]].index(group)
    pick = (lambda a: a.sum(axis=1)) if gi is None else (lambda a: a[:, gi])
    init = pick(h["init"])[: len(days)]
    ret = pick(h["ret"])[: len(days)]
    vals = {"initial": init, "readmissions": ret, "total": init + ret}[source]
    return pd.Series(vals.astype(int), index=days)


def readmissions_in_period():
    s = daily_counts("readmissions")
    return int(s.sum()), s.sum() / DATA_DAYS


def monthly_series(source):
    if source != "initial" and not calendar_available():
        source = "initial"
    if calendar_available():
        s = daily_counts(source)
        g = s.groupby(s.index.to_period("M"))
        df = pd.DataFrame({"count": g.sum(), "days": g.size()}).reset_index(names="period")
    else:
        md = monthly_demand()
        df = pd.DataFrame({"period": pd.period_range("2011-07", "2012-06", freq="M"), "count": md.admissions.values,
                           "days": md.days.values})
    df["per_day"] = df["count"] / df["days"]
    df["month"] = [CAL_MONTHS[p.month - 1] for p in df.period]
    df["label"] = [f"{CAL_MONTHS[p.month - 1]} {p.year}" for p in df.period]
    df["incomplete"] = (source != "initial") & df.period.isin(pd.period_range("2011-07", "2011-08", freq="M"))
    return df


def weekday_series(source):
    if source != "initial" and not calendar_available():
        source = "initial"
    days = pd.date_range(DATA_START, DATA_END)
    n_wd = np.bincount(days.dayofweek, minlength=7)
    if calendar_available():
        s = daily_counts(source)
        tot = np.bincount(s.index.dayofweek, weights=s.values, minlength=7)
    else:
        wd, _ = weekday_pattern()
        tot = wd.per_day.values * n_wd
    return pd.DataFrame({"weekday": WEEKDAYS, "count": tot, "per_day": tot / n_wd})


def month_weekday_observed(source):
    """Observed average admissions per day for each month x weekday cell (count / number of such days)."""
    s = daily_counts(source)
    df = pd.DataFrame({"v": s.values, "m": s.index.to_period("M"), "w": s.index.dayofweek})
    g = df.groupby(["m", "w"]).v.agg(["sum", "size"]).reset_index()
    g["per_day"] = g["sum"] / g["size"]
    months = pd.period_range("2011-07", "2012-06", freq="M")
    z = [[float(g[(g.m == m) & (g.w == w)].per_day.iloc[0]) for w in range(7)] for m in months]
    return [f"{CAL_MONTHS[m.month - 1]} {m.year}" for m in months], z


def time_insight(source, view):
    """Headline + highest/lowest for the active source and view (incomplete months excluded from extremes)."""
    name = SOURCES[source if (source == "initial" or calendar_available()) else "initial"].lower()
    if view == "Monthly":
        df = monthly_series(source)
        full = df[~df.incomplete]
        hi, lo = full.loc[full.per_day.idxmax()], full.loc[full.per_day.idxmin()]
        head = f"{MONTH_FULL[hi.month]} {hi.period.year} had the highest {name}."
        note = ("Jul–Aug 2011 are incomplete for readmissions and are not compared."
                if df.incomplete.any() else "")
        return dict(head=head, hi=f"{MONTH_FULL[hi.month]} {hi.period.year}", hi_v=hi.per_day,
                    lo=f"{MONTH_FULL[lo.month]} {lo.period.year}", lo_v=lo.per_day, unit="per day", note=note,
                    plan="Choosing a starting month lets your scenario test busier or quieter periods.")
    df = weekday_series(source)
    hi, lo = df.loc[df.per_day.idxmax()], df.loc[df.per_day.idxmin()]
    return dict(head=f"{WEEKDAY_FULL[hi.weekday]}s had the highest {name}.", hi=WEEKDAY_FULL[hi.weekday], hi_v=hi.per_day,
                lo=WEEKDAY_FULL[lo.weekday], lo_v=lo.per_day, unit="per day", note="",
                plan=f"{WEEKDAY_FULL[hi.weekday]} averages {hi.per_day / lo.per_day:.1f}× {WEEKDAY_FULL[lo.weekday]}, "
                     "so bed pressure tends to build at the same point each week.")


# --------------------------------------------------------------------------- v3.8 consistent page measures
# One basis for every count and bed-day figure on Historical Overview: stays that BEGAN in the reference period
# (1 Jul 2011 - 30 Jun 2012). Initial admissions are dated by ADMIT_DATE, readmissions by READMIT_DATE.
# The Readmission Rate is the only cohort measure: readmissions within 60 days of discharge / patients discharged
# alive, following every initial admission of the period (including returns in Jul-Aug 2012).
# All from history_calendar.npz (age_stats), built from the original CSV; reconciles with calibration.npz.
AGE_SHORT = {"All ages": "All Ages", "Under 65": "Under 65", "65 and over": "65+"}


def measures_available():
    h = _calendar()
    return h is not None and "age_stats" in h


@lru_cache(maxsize=1)
def age_table():
    """One row per group x age band with the raw aggregates (see build_history_calendar.AGE_KEYS)."""
    h = _calendar()
    keys = [str(k) for k in h["age_keys"]]
    rows = []
    for gi, g in enumerate(str(x) for x in h["groups"]):
        dx, sev = g.split("|")
        for bi, band in enumerate(str(b) for b in h["age_bands"]):
            rows.append(dict(group=g, diagnosis=dx, severity=int(sev), band=band,
                             **{k: int(v) for k, v in zip(keys, h["age_stats"][gi, bi])}))
    return pd.DataFrame(rows)


def _summarise(t):
    s = t[["init_n", "init_bd", "survivors", "coh_ret", "coh_ret_bd", "cal_ret", "cal_ret_bd"]].sum()
    n, ret = int(s.init_n), int(s.cal_ret)
    total = int(s.init_bd + s.cal_ret_bd)
    return dict(init_n=n, init_per_day=n / DATA_DAYS, init_stay=s.init_bd / n if n else float("nan"),
                init_bd=int(s.init_bd), ret_n=ret, ret_per_day=ret / DATA_DAYS,
                ret_stay=s.cal_ret_bd / ret if ret else float("nan"), ret_bd=int(s.cal_ret_bd),
                total_bd=total, ret_bd_share=100 * s.cal_ret_bd / total if total else float("nan"),
                survivors=int(s.survivors), coh_ret=int(s.coh_ret),
                rate=100 * s.coh_ret / s.survivors if s.survivors else float("nan"))


def page_measures(diagnosis=None, severity=None, age="All ages"):
    """Hospital, condition, group or group x age measures, all on the same basis (see above)."""
    t = age_table()
    if diagnosis:
        t = t[t.diagnosis == diagnosis]
    if severity:
        t = t[t.severity == int(severity)]
    if age != "All ages":
        t = t[t.band == age]
    out = _summarise(t)
    out["share_total"] = 100 * out["total_bd"] / _summarise(age_table())["total_bd"]
    return out


def _table(by):
    rows = []
    for key, s in age_table().groupby(by, sort=False):
        r = _summarise(s)
        r.update(dict(zip(by, key)) if isinstance(by, list) else {by: key})
        rows.append(r)
    out = pd.DataFrame(rows)
    hosp = _summarise(age_table())
    out["share_total"] = 100 * out.total_bd / hosp["total_bd"]
    out["adm_share"] = 100 * out.init_n / hosp["init_n"]
    return out


def condition_table():
    return _table("diagnosis").sort_values("total_bd", ascending=False).reset_index(drop=True)


def severity_table(diagnosis):
    t = _table(["diagnosis", "severity"])
    t = t[t.diagnosis == diagnosis].sort_values("severity").reset_index(drop=True)
    t["share_in_dx"] = 100 * t.total_bd / t.total_bd.sum()
    t["adm_share_in_dx"] = 100 * t.init_n / t.init_n.sum()
    return t


def all_groups_table():
    t = _table(["diagnosis", "severity"])
    t["group"] = t.diagnosis + "|" + t.severity.astype(str)
    return t


def age_bed_use(diagnosis, severity):
    """Under 65 / 65+: initial, readmission and total bed-days for one group (bands are exhaustive)."""
    rows = []
    for band in ("Under 65", "65 and over"):
        m = page_measures(diagnosis, severity, band)
        rows.append(dict(band=band, init_bd=m["init_bd"], ret_bd=m["ret_bd"], total_bd=m["total_bd"],
                         rate=m["rate"], ret_n=m["ret_n"], init_n=m["init_n"]))
    df = pd.DataFrame(rows)
    df["share"] = 100 * df.total_bd / df.total_bd.sum()
    return df


def _pct(x):
    return f"{x:.0f}%" if x >= 1 else "less than 1%"


def _ord(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---- insights: observed facts first, then one arithmetic contributor; no causal or clinical claims
def condition_insight(names):
    """(primary, supporting) for the condition with the largest bed use. names: dx -> display name."""
    t = condition_table()
    hosp = page_measures()
    top = t.iloc[0]
    name = names.get(top.diagnosis, top.diagnosis)
    primary = (f"{name} accounts for {top.share_total:.0f}% of total Bed-days, the largest share among the "
               f"{len(t)} conditions.")
    parts = []
    if top.adm_share >= top.share_total - 5:
        parts.append(f"its high number of initial admissions ({top.adm_share:.0f}% of the total)")
    if top.init_stay >= 1.05 * hosp["init_stay"]:
        parts.append(f"longer initial stays ({top.init_stay:.1f} vs {hosp['init_stay']:.1f} days on average)")
    if top.rate >= 1.05 * hosp["rate"]:
        parts.append(f"a higher Readmission Rate ({top.rate:.1f}% vs {hosp['rate']:.1f}%)")
    elif top.ret_bd_share >= hosp["ret_bd_share"] + 1:
        parts.append(f"readmissions ({top.ret_bd_share:.0f}% of its Bed-days)")
    if not parts:
        return primary, ""
    return primary, "This reflects " + _join(parts[:2]) + "."


def severity_insight_v2(diagnosis, name):
    s = severity_table(diagnosis)
    top = s.loc[s.total_bd.idxmax()]
    txt = f"Severity {top.severity} accounts for {top.share_in_dx:.0f}% of {name} Bed-days"
    if top.share_in_dx >= top.adm_share_in_dx + 5:
        dx_stay = page_measures(diagnosis)["init_stay"]
        txt += (f", more than its {top.adm_share_in_dx:.0f}% share of admissions, because its stays are longer "
                f"({top.init_stay:.1f} vs {dx_stay:.1f} days)")
    return txt + "."


def group_insight_v2(diagnosis, severity, age, label):
    """One or two sentences: the group's position, then one notable feature (descriptive only)."""
    t = all_groups_table()
    hosp = page_measures()
    r = t[(t.diagnosis == diagnosis) & (t.severity == int(severity))].iloc[0]
    in_dx = t[t.diagnosis == diagnosis].sort_values("total_bd", ascending=False)
    rank_dx = list(in_dx.severity).index(int(severity)) + 1
    rank_all = int((t.total_bd > r.total_bd).sum()) + 1
    if age != "All ages":
        a = age_bed_use(diagnosis, severity).set_index("band")
        me, other = a.loc[age], a.drop(age).iloc[0]
        who = "patients aged 65+" if age == "65 and over" else "patients under 65"
        txt = f"In {label}, {who} account for {_pct(me.share)} of the group's Bed-days."
        if me.ret_n and other.ret_n and abs(me.rate - other.rate) >= 1:
            txt += (f" Their Readmission Rate is {me.rate:.1f}%, compared with {other.rate:.1f}% for "
                    f"{'patients under 65' if age == '65 and over' else 'patients aged 65+'}.")
        elif not me.ret_n:
            txt += " No readmissions were recorded for this age group."
        return txt
    cond = label.split(" Severity")[0]
    where = (f"has the largest bed use within {cond}" if rank_dx == 1 and len(in_dx) > 1
             else f"ranks {_ord(rank_dx)} of {len(in_dx)} severity levels within {cond} by Bed-days")
    txt = (f"{label} {where} and accounts for {_pct(r.share_total)} of total Bed-days "
           f"({_ord(rank_all)} of {len(t)} patient groups).")
    if r.ret_n and r.ret_bd_share >= hosp["ret_bd_share"] + 2:
        txt += (f" Readmissions make up {r.ret_bd_share:.0f}% of its Bed-days, above the hospital-wide "
                f"{hosp['ret_bd_share']:.0f}%.")
    elif r.coh_ret and r.rate >= 1.1 * hosp["rate"]:
        txt += f" Its Readmission Rate is {r.rate:.1f}%, above the hospital-wide {hosp['rate']:.1f}%."
    elif r.init_stay >= 1.15 * hosp["init_stay"]:
        txt += f" Its average initial stay is {r.init_stay:.1f} days, compared with {hosp['init_stay']:.1f} hospital-wide."
    elif r.share_total < 3:
        txt += " Changes to this group alone would have a small effect on hospital-wide bed use."
    return txt


# ---- time patterns
def _runs(labels, mask):
    """Contiguous runs of True as (first, last) labels."""
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        if not m and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _span(df, a, b):
    lab = lambda i: f"{MONTH_FULL[df.month.iloc[i]]} {df.period.iloc[i].year}"
    if a == b:
        return lab(a)
    y1, y2 = df.period.iloc[a].year, df.period.iloc[b].year
    first = MONTH_FULL[df.month.iloc[a]] + ("" if y1 == y2 else f" {y1}")
    return f"{first} to {lab(b)}"


def monthly_pattern(source):
    """One-sentence monthly pattern + highest/lowest month. Months with incomplete readmission records
    (Jul-Aug 2011 for readmissions and total) are shown on the chart but not used in the comparison."""
    df = monthly_series(source)
    full = df[~df.incomplete].reset_index(drop=True)
    name = SOURCES[source] if source != "readmissions" else "Recorded readmissions"
    v = full.per_day.values
    imax, imin = int(v.argmax()), int(v.argmin())
    hi_run = next((a, b) for a, b in _runs(full.label, v >= 0.8 * v.max()) if a <= imax <= b)
    span = _span(full, *hi_run)
    third = max(1, len(v) // 3)
    early, late = v[:third].mean(), v[-third:].mean()
    if late >= 1.15 * early:
        head = (f"{name} generally increased over the year, with the highest levels "
                f"{'in' if hi_run[0] == hi_run[1] else 'from'} {span}.")
    elif late <= 0.87 * early:
        head = f"{name} were highest early in the period ({span}) and generally declined afterwards."
    else:
        head = f"{name} were fairly steady across the year, peaking {'in' if hi_run[0] == hi_run[1] else 'from'} {span}."
    return dict(head=head, hi=full.label.iloc[imax], hi_v=v[imax], lo=full.label.iloc[imin], lo_v=v[imin],
                unit="per day")


def weekday_pattern_v2(source):
    """One sentence describing the weekly shape (days well above / below the weekly average)."""
    wd = weekday_series(source)
    v, mean = wd.per_day.values, wd.per_day.mean()
    days = [WEEKDAY_FULL[w] for w in wd.weekday]
    name = SOURCES[source] if source != "readmissions" else "Recorded readmissions"
    hi = [days[i] for i in range(7) if v[i] >= 1.1 * mean]
    if "Sunday" in hi:                                  # read the week as Sunday -> Saturday for the high days
        hi = ["Sunday"] + [x for x in hi if x != "Sunday"]
    lo = [days[i] for i in range(7) if v[i] <= 0.9 * mean]
    imax, imin = int(v.argmax()), int(v.argmin())
    plural = lambda xs: [x + "s" for x in xs]

    def hi_txt(xs):
        if "Saturday" in xs and "Sunday" in xs:
            rest = [x for x in xs if x not in ("Saturday", "Sunday")]
            return "weekends" + (" and " + _join(plural(rest)) if rest else "")
        return _join(plural(xs))

    second_lowest = sorted(v)[1]
    if not hi and not lo:
        head = f"{name} were fairly even across the week."
    elif hi and lo:
        if second_lowest >= 1.15 * v[imin]:              # one clearly quietest day
            head = f"{name} were particularly high on {hi_txt(hi)}, and lowest on {days[imin]}s."
        elif len(lo) > 3:
            head = f"{name} were highest around {_join(hi)}, with lower volumes on several weekdays."
        else:
            head = f"{name} were higher on {hi_txt(hi)}, with lower volumes on {_join(plural(lo))}."
    elif hi:
        head = f"{name} were higher on {hi_txt(hi)}; other days were close to the weekly average."
    else:
        head = f"{name} were lower on {_join(plural(lo))}; other days were close to the weekly average."
    return dict(head=head, hi=WEEKDAY_FULL[wd.weekday[imax]], hi_v=v[imax], lo=WEEKDAY_FULL[wd.weekday[imin]],
                lo_v=v[imin], unit="per day")


def chart_note(source, view):
    """Short, accurate qualification shown under the chart (not in the Key Insight)."""
    if view == "Monthly":
        if source == "initial":
            return ""
        return ("○ July–August 2011: readmission records are incomplete (patients admitted before July 2011 are not "
                "in the data), so these months are not compared.")
    if source == "readmissions":
        active = int((daily_counts(source) > 0).sum())
        return (f"Readmission dates fall on only {active} of {DATA_DAYS} days in this dataset, so weekday differences "
                "mostly reflect how dates were recorded.")
    return "Admission dates in this dataset cluster on some days, so treat weekday differences as indicative."
