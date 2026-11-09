"""Hospital Capacity Planner - manager-facing Streamlit front end (v3.1).

Run:   python -m streamlit run app.py
Needs: simulation.py and calibration.npz in the same folder, plus the frontend helpers
       historical_summary.py, results_helpers.py and ui_components.py.

The discrete-event simulation (simulation.py) is used unchanged. This file arranges inputs, calls the
existing model functions and presents their outputs. Research prototype - not a clinical or forecasting tool.
"""
import inspect
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import simulation as S
import historical_summary as H
import results_helpers as RH
import diagnosis_capacity as DC
import ui_components as UI

APP_VERSION = "4.2 guided scenarios"
MODEL_VERSION = "2.1-audited"
HERE = Path(__file__).parent
MAX_SAVED = 4

st.set_page_config(page_title="Hospital Capacity Planner", page_icon="🏥", layout="wide",
                   initial_sidebar_state="collapsed")
UI.inject_css()


def _stretch(fn):
    """'width=stretch' on current Streamlit, 'use_container_width' on older versions."""
    return {"width": "stretch"} if "width" in inspect.signature(fn).parameters else {"use_container_width": True}


PLOT_KW, DF_KW, BTN_KW = _stretch(st.plotly_chart), _stretch(st.dataframe), _stretch(st.button)
DL_KW = _stretch(st.download_button)
PLOT_CFG = {"displayModeBar": False, "displaylogo": False}
ss = st.session_state

# --------------------------------------------------------------------------- state
DEFAULTS = dict(diagnosis="CHF", severity=3, age="All ages", reduction=10, demand=0, readmit=0,
                pattern="Annual average", start_month="Jan", duration=90, bed_mode="reference",
                custom_beds=None, reps=10, seed=2026, breakdown=True, flow_on=False)
UI_DEFAULTS = dict(reduction_pick=10, readmit_pick=0, demand_pick=0, ov_metric="total_bd", ov_all=False, ov_pick="CHF|3", ex_dx="CHF", ex_sev=3, ov_age="All ages",
                   ov_view="Monthly", ov_source="total", ov_split=False, bed_view="Weekly trend",
                   adm_series="New admissions", adm_view="Weekly")
if "cfg" not in ss:
    ss.cfg = dict(DEFAULTS)
if "ui" not in ss:
    ss.ui = dict(UI_DEFAULTS)
for k, v in UI_DEFAULTS.items():
    ss.ui.setdefault(k, v)
ss.setdefault("page", "welcome")
ss.setdefault("prev_page", "welcome")
ss.setdefault("result", None)
ss.setdefault("saved", [])          # runs saved for side-by-side comparison
ss.setdefault("saved_seq", 0)

NAMES = ["duration", "beds", "demand", "reduction", "readmit", "diagnosis", "severity", "age", "seed", "reps",
         "season", "breakdown", "ref_beds"]
BED_MODES = {"reference": "Default beds", "minus5": "5% fewer", "minus10": "10% fewer", "plus10": "10% more",
             "custom": "Custom"}


def go_to(page):
    if ss.page != page:
        ss.prev_page = ss.page
    ss.page = page


def bind(name, widget, label, store="cfg", **kw):
    """Render a widget whose value survives page changes (widget state is cleared when not shown)."""
    data = ss[store]
    if name not in data:                         # a setting added after this session started
        data[name] = (DEFAULTS if store == "cfg" else UI_DEFAULTS).get(name)
    wkey = f"w_{store}_{name}"
    opts = kw.get("options")
    if opts is not None:
        opts = list(opts)
        default = (DEFAULTS if store == "cfg" else UI_DEFAULTS).get(name)
        fallback = default if default in opts else opts[0]
        if data[name] not in opts:
            data[name] = fallback
        if wkey in ss and ss[wkey] not in opts:
            ss[wkey] = data[name]
    if wkey not in ss:
        ss[wkey] = data[name]
    value = widget(label, key=wkey, **kw)
    data[name] = value
    return value


def clear_widget(name, store="cfg"):
    ss.pop(f"w_{store}_{name}", None)


def sync_cfg():
    """Pull the latest widget values into cfg before anything on the page reads them."""
    for name in DEFAULTS:
        wkey = f"w_cfg_{name}"
        if wkey in ss:
            ss.cfg[name] = ss[wkey]


# --------------------------------------------------------------------------- cached model calls
@st.cache_data(show_spinner="Calculating the default bed count...")
def rec_beds(season=None):
    """Default beds: ONE fixed, model-derived value (2,800 with the current data), independent of the period.

    = 95th-percentile daily occupancy when the typical-week admission pattern is simulated with unlimited beds
    (120 days x 3 runs, seed 2026), rounded to the nearest 100 (simulation.recommended_beds). A planning default,
    not an observed or staffed bed count. v4.5 audit: earlier versions used the selected month's value (January
    3,900; July 2,500), which silently changed capacity with the demand pattern. v4.7: the month's own value is no
    longer shown on the page (it is a simulated unlimited-bed figure, not comparable to an available-bed setting).
    The `season` argument is ignored and kept only for call compatibility."""
    return S.recommended_beds(season="Annual average")


@st.cache_data(show_spinner=False, max_entries=20)
def run_all(duration, beds, demand, reduction, readmit, diagnosis, severity, age, seed, reps, season, breakdown,
            ref_beds):
    """Cached wrapper; see results_helpers.build_runs (unchanged model calls plus the comparison runs)."""
    return RH.build_runs(duration, beds, demand, reduction, readmit, diagnosis, severity, age, seed, reps, season,
                         breakdown, ref_beds)


comparator, secondary_comparator, comparison_label, view_of = (RH.comparator, RH.secondary_comparator,
                                                               RH.comparison_label, RH.view_of)


def active_cfg(cfg):
    """Settings actually passed to the model: improvements count only when they are switched on."""
    a = dict(cfg)
    if not cfg.get("flow_on"):
        a["reduction"] = a["readmit"] = 0
    return a


def season_of(cfg):
    return "Annual average" if cfg["pattern"] == "Annual average" else cfg["start_month"]


def beds_for(cfg, ref):
    mode = cfg["bed_mode"]
    if mode == "custom":
        return int(cfg["custom_beds"] or ref)
    factor = {"reference": 1.0, "minus5": 0.95, "minus10": 0.90, "plus10": 1.10}[mode]
    return int(round(ref * factor / 10) * 10)


def current_settings():
    cfg = active_cfg(ss.cfg)
    season = season_of(cfg)
    ref = rec_beds(season)
    return dict(duration=int(cfg["duration"]), beds=beds_for(cfg, ref), demand=int(cfg["demand"]),
                reduction=int(cfg["reduction"]), readmit=int(cfg["readmit"]), diagnosis=cfg["diagnosis"],
                severity=int(cfg["severity"]), age=cfg["age"], seed=int(cfg["seed"]), reps=int(cfg["reps"]),
                season=season, breakdown=bool(cfg["breakdown"]), ref_beds=int(ref)), ref


def run_problem(settings):
    """Why the scenario cannot run yet (None when it can)."""
    for name, label in (("demand", "Change in admissions"), ("reduction", "Shorter stays"),
                        ("readmit", "Fewer readmissions")):
        spec = PCT_CHOICES[name]
        if not spec["lo"] <= settings[name] <= spec["hi"]:
            return f"{label} must be a whole number from {spec['lo']}% to {spec['hi']}%."
    if not BED_LO <= settings["beds"] <= BED_HI:
        return f"Available beds must be a whole number from {BED_LO} to {BED_HI:,}."
    return None


def do_run():
    settings, ref = current_settings()
    if run_problem(settings):
        return
    t = tuple(settings[n] for n in NAMES)
    with st.spinner(f"Running the simulation ({settings['duration']} days × {settings['reps']} runs for your scenario "
                    "and its comparisons). This usually takes under a minute..."):
        res = run_all(*t)
    ss.result = dict(settings=settings, key=t, res=res, bed_mode=ss.cfg["bed_mode"], reference=ref,
                     finished=datetime.now().strftime("%d %b %Y, %H:%M"))
    go_to("results")
    st.rerun()


TRACE_NAMES = {"Baseline": "Reference", "Scenario": "Your Scenario"}


def show(fig, key):
    if ss.get("page") == "results":                 # same labels as the Results page text
        for tr in fig.data:
            if getattr(tr, "name", None) in TRACE_NAMES:
                tr.name = TRACE_NAMES[tr.name]
    st.plotly_chart(fig, config=PLOT_CFG, key=key, **PLOT_KW)


def monday_ticks(fig, frame, daycol="day"):
    """Label the x-axis at every Monday so the weekly rhythm is easy to read."""
    mons = frame[frame.weekday == "Mon"][daycol].drop_duplicates().tolist()
    fig.update_xaxes(tickvals=mons, ticktext=[f"Mon<br>day {d}" for d in mons])


# --------------------------------------------------------------------------- navigation + footer
NAV_ITEMS = [("welcome", "Welcome"), ("overview", "Historical Overview"), ("simulator", "Build a Scenario"),
             ("results", "Results")]


def render_help():
    """Help / About popover: product summary, disclaimer, data scope, versions and documentation link."""
    snap = H.snapshot()
    UI.md('<div class="helpbox"><div class="hb-t">About this tool</div>'
          '<p>A research prototype for exploring hypothetical hospital planning scenarios. It is not a clinical '
          'decision-making tool or a validated forecast of actual hospital bed requirements.</p>'
          '<div class="hb-t">Data</div>'
          f'<p>{snap["admissions"]:,} historical admissions for AMI, CHF and COPD, {H.PERIOD_LABEL}, pooled across '
          '39 hospitals. Historical figures do not describe any hospital today.</p>'
          '<div class="hb-t">Definitions and limitations</div>'
          '<p>One shared pool of beds, daily time steps, results averaged over repeat runs. Planning references are '
          'not guaranteed capacity requirements; length-of-stay changes are hypothetical assumptions.</p>'
          f'<p class="hb-v">Model {MODEL_VERSION} · interface {APP_VERSION}</p></div>')
    st.button("Model documentation", key="help_docs", icon=":material/menu_book:", on_click=go_to, args=("docs",),
              **BTN_KW)


def render_nav():
    with st.container(key="topnav", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        with st.container(key="navbrand", width="content"):
            UI.md('<div class="brand2"><span class="bmark"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" '
                  'stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></span>'
                  '<span class="btext"><span class="bname">Hospital Capacity Planner</span>'
                  '<span class="bsub">Data Doctors · UNSW × SAS Industry Project</span></span></div>')
        with st.container(key="navlinks", horizontal=True, gap="medium", width="content", vertical_alignment="center"):
            for key, label in NAV_ITEMS:
                st.button(label, key=f"nav_{key}", type="primary" if ss.page == key else "tertiary",
                          on_click=go_to, args=(key,))
        with st.container(key="navactions", horizontal=True, gap="xsmall", width="content", vertical_alignment="center"):
            st.button("Export", key="nav_export", icon=":material/download:",
                      type="primary" if ss.page == "export" else "tertiary", on_click=go_to, args=("export",),
                      help="Download data from your latest completed run")
            with st.popover("", icon=":material/help:", help="Help and about", key="nav_help"):
                render_help()


def render_footer():
    c1, c2 = st.columns([5, 1.2], vertical_alignment="center")
    c1.markdown('<div class="footer">Research prototype for exploring hypothetical scenarios — not a clinical tool or a '
                f'forecast of bed requirements. Historical data {H.PERIOD_LABEL}.</div>', unsafe_allow_html=True)
    if ss.page != "simulator":                     # Build a Scenario: documentation stays in the Help menu
        c2.button("Model documentation", key="foot_docs", on_click=go_to, args=("docs",), **BTN_KW)


# =========================================================================== PAGE 1: WELCOME
WELCOME_QUESTIONS = [
    ("demand", "Higher admission demand", "What happens if more patients need admission?",
     "Explore how higher demand could affect hospital capacity and waiting times.", "Set expected admissions", "step-2"),
    ("beds", "Available bed capacity", "What if the hospital has more or fewer beds?",
     "Test how different bed numbers could affect occupancy and waiting.", "Set available beds", "step-3"),
    ("flow", "Patient flow improvements", "Could shorter stays or fewer readmissions help?",
     "Explore whether targeted improvements could reduce pressure on hospital beds.", "Test improvements", "step-4"),
]


def open_step(anchor):
    """Open Build a Scenario at one step. Nothing in the scenario changes."""
    ss.scroll_to = anchor
    go_to("simulator")


def scroll_to_anchor(target):
    import streamlit.components.v1 as components
    components.html(
        "<script>const go=(n)=>{const el=window.parent.document.getElementById('" + target + "');"
        "if(el){el.scrollIntoView({behavior:'smooth',block:'start'});}else if(n<40){setTimeout(()=>go(n+1),100);}};"
        "go(0);</script>", height=0)


def page_welcome():
    """Editorial introduction: why (hero), what (management questions), how (simulation), where to start."""
    UI.md(UI.WELCOME_CSS)
    with st.container(key="wl_hero"):
        c1, c2 = st.columns([1, 1.1], gap="large", vertical_alignment="center")
        with c1:
            UI.md('<h1 class="wl-h1">See the Impact<br>Before You Act</h1>'
                  '<p class="wl-lead">Plan for changing hospital demand. Test different bed capacity and patient-flow '
                  'improvements to see how they could affect bed pressure and waiting times.</p>'
                  '<p class="wl-q">Could your hospital manage higher patient demand with its available beds?</p>')
            with st.container(key="wl_cta", horizontal=True):
                st.button("Build a Scenario", key="wl_build", type="primary", icon=":material/arrow_forward:",
                          icon_position="right", on_click=go_to, args=("simulator",))
                st.button("Explore Historical Data", key="wl_explore", type="tertiary", on_click=go_to,
                          args=("overview",))
        with c2:
            UI.md(UI.flow_art())

    UI.md('<h2 class="wl-h2">What can you explore?</h2>'
          '<p class="wl-sub">Three planning questions, all answered in the same scenario. Start with demand and beds; '
          'patient-flow improvements are optional.</p>')
    with st.container(key="wl_qs"):
        cols = st.columns(3)
        for col, (key, kicker, q, d, action, anchor) in zip(cols, WELCOME_QUESTIONS):
            with col:
                opt = '<span class="wl-opt">Optional</span>' if key == "flow" else ""
                UI.md(f'<div class="wlq-ic">{UI.WL_ICONS[key]}</div><div class="wlq-k">{kicker}{opt}</div>'
                      f'<div class="wlq-t">{q}</div><div class="wlq-d">{d}</div>')
                st.button(action, key=f"wl_q_{key}", type="tertiary", icon=":material/arrow_forward:",
                          icon_position="right", on_click=open_step, args=(anchor,))

    with st.container(key="wl_des"):
        a, b = st.columns([1, 1.25], gap="large")
        with a:
            UI.md('<div class="wl-des"><h2 class="wl-h2">How does the simulation help?</h2>'
                  '<p>The tool uses Discrete-Event Simulation (DES) to recreate how patients arrive, stay in hospital, '
                  'wait for beds and return after discharge.</p>'
                  '<p>This helps you explore how different planning decisions might affect hospital capacity before '
                  'making changes in practice.</p></div>')
        with b:
            UI.md(UI.mechanism())

    UI.md('<h2 class="wl-h2">How it works</h2>')
    with st.container(key="wl_path"):
        has_result = ss.get("result") is not None
        steps = [("Explore historical data", "Understand historical admissions and which patient groups use the most "
                  "bed resources."),
                 ("Build a scenario", "Choose a planning period, set admissions and beds, and optionally test "
                  "patient-flow improvements."),
                 ("Understand the results", "See how your scenario affects capacity and waiting, and compare different "
                  "planning options.")]
        cols = st.columns(3)
        for i, (col, (t, d)) in enumerate(zip(cols, steps), 1):
            with col:
                UI.md(f'<div class="wlp-n{" cur" if i == 2 else ""}">{i}</div><div class="wlp-t">{t}</div>'
                      f'<div class="wlp-d">{d}</div>')
                if i == 1:
                    st.button("Explore Historical Data", key="how_explore", type="secondary",
                              icon=":material/arrow_forward:", icon_position="right", on_click=go_to, args=("overview",))
                elif i == 2:
                    st.button("Build a Scenario", key="how_simulate", type="primary", icon=":material/arrow_forward:",
                              icon_position="right", on_click=go_to, args=("simulator",))
                elif has_result:
                    st.button("View Latest Results", key="how_compare", type="secondary",
                              icon=":material/arrow_forward:", icon_position="right", on_click=go_to, args=("results",))
                else:
                    UI.md('<p class="wlp-none">Your results appear here after you run your first scenario.</p>')


# =========================================================================== PAGE 2: OVERVIEW
NO_MONTH = "none"
COND_NAMES = {"CHF": "Heart Failure", "AMI": "Heart Attack", "COPD": "COPD"}
COND_FULL = {"CHF": "Heart Failure (CHF)", "AMI": "Heart Attack (AMI)", "COPD": "COPD"}
COND_DESC = {"CHF": "Congestive Heart Failure", "AMI": "Acute Myocardial Infarction",
             "COPD": "Chronic Obstructive Pulmonary Disease"}
TIPS = dict(
    readmissions="Readmissions recorded between July 2011 and June 2012.",
    rate="Percentage of eligible patients readmitted within 60 days after discharge.",
    bed_days="Days patients spent in hospital beds. A same-day stay counts as one day.",
    avg_stay="Average number of days per hospital stay.",
    total="All Bed-days of stays that began during the historical year.",
)
SECTIONS = [("hospital-overview", "Hospital at a Glance"), ("explore-patient-groups", "Explore Patient Groups"),
            ("admission-patterns", "Admission Patterns")]
# Kept for the Results redesign: modelled busy-day references per condition (see diagnosis_capacity.py).
REF_TIP_LINE = ("Modelled with the unchanged simulation: only this condition's admissions and their readmissions, "
                "unlimited beds, no changes, 120 days × 3 runs; the 95th-percentile daily occupancy.")


@st.cache_data(show_spinner=False)
def service_line_refs():
    """Not shown on Historical Overview (moved out of this page); retained for the Results page redesign."""
    return DC.service_line_references(tuple(H.dx_demand_table().label))


def _tip(text):
    return UI.tip(text)


def cond_label(dx, full=False):
    return (COND_FULL if full else COND_NAMES).get(dx, dx)


def group_name(dx, sev):
    return f"{cond_label(dx)} · Severity {sev}"


def _days(x):
    return "—" if x != x else f"{x:.1f} days"          # NaN-safe


def page_overview():
    for name in UI_DEFAULTS:                     # use this run's widget values everywhere on the page
        if f"w_ui_{name}" in ss:
            ss.ui[name] = ss[f"w_ui_{name}"]
    target = ss.pop("scroll_to", None)
    if target:                                  # arriving from "Explore Patient Groups" in the scenario builder
        scroll_to_anchor(target)
    if not H.measures_available():
        st.error("Historical summary data (history_calendar.npz) is missing. Rebuild it with "
                 "`python build_history_calendar.py --raw \"Original Data/table_READMIT_HISTORICAL.csv\"`.")
        return
    hosp = H.page_measures()
    UI.md(UI.section_nav(SECTIONS))
    UI.md('<div class="ovhead"><h1>Understand Hospital Demand</h1>'
          '<p>Explore hospital activity, discover high-demand patient groups, and understand when demand is highest.</p>'
          + UI.period_strip("Historical Data Period", "1 July 2011 – 30 June 2012",
                            "Initial admissions during this period, with readmissions tracked for up to 60 days after "
                            "discharge.")
          + '</div>')

    # ================================================================ 01 Hospital at a Glance
    UI.qhead(1, "Hospital at a Glance", anchor="hospital-overview")
    c1, c2 = st.columns(2, gap="medium")
    c1.markdown(UI.stat_card(
        "Initial Admissions", "admit", "teal", f"{hosp['init_n']:,}", "",
        [("Initial Admissions<br>per Day", f"{hosp['init_per_day']:,.0f}"),
         ("Average<br>Initial Stay", _days(hosp["init_stay"])),
         ("Initial-stay<br>Bed-days", f"{hosp['init_bd']:,}")]), unsafe_allow_html=True)
    c2.markdown(UI.stat_card(
        "Readmissions " + _tip(TIPS["readmissions"]), "readmit", "navy", f"{hosp['ret_n']:,}", "",
        [("Readmissions<br>per Day", f"{hosp['ret_per_day']:,.0f}"),
         ("Average<br>Readmission Stay", _days(hosp["ret_stay"])),
         ("Readmission<br>Bed-days", f"{hosp['ret_bd']:,}"),
         ("60-Day<br>Readmission Rate", f"{hosp['rate']:.1f}%")]),
        unsafe_allow_html=True)
    UI.md(UI.total_bar(hosp["init_bd"], hosp["ret_bd"]))

    # ================================================================ 02 Explore Patient Groups
    UI.qhead(2, "Explore Patient Groups", anchor="explore-patient-groups")
    if not ss.get("ex_init"):                       # start from the group already in the scenario
        ss.ui["ex_dx"], ss.ui["ex_sev"], ss.ex_init = ss.cfg["diagnosis"], int(ss.cfg["severity"]), True
    dx, sev = ss.ui.get("ex_dx"), ss.ui.get("ex_sev")
    dxt = H.condition_table()

    def _set(level_dx, level_sev):
        ss.ui["ex_dx"], ss.ui["ex_sev"] = level_dx, level_sev
        if level_dx and level_sev:
            ss.ui["ov_pick"] = f"{level_dx}|{level_sev}"

    UI.md(UI.big_insight(H.condition_insight({k: cond_label(k) for k in COND_NAMES})[0]))
    h1, h2 = st.columns([1, 2], vertical_alignment="center")
    h1.markdown('<div class="lvl2">Bed Use by Condition</div>', unsafe_allow_html=True)
    with h2:
        with st.container(key="crumbs", horizontal=True, gap="xsmall", vertical_alignment="center",
                          horizontal_alignment="right"):
            st.button("Whole Hospital", key="crumb_all", type="tertiary", on_click=_set, args=(None, None),
                      disabled=dx is None)
            if dx:
                UI.md('<span class="crsep">/</span>')
                st.button(cond_label(dx), key="crumb_dx", type="tertiary", on_click=_set, args=(dx, None),
                          disabled=sev is None)
            if dx and sev:
                UI.md(f'<span class="crsep">/</span><span class="crcur">Severity {sev}</span>'
                      f'<span class="crsep">/</span><span class="crcur">'
                      f'{H.AGE_SHORT[ss.ui.get("ov_age") or "All ages"]}</span>')
    cols = st.columns(len(dxt), gap="small")
    for col, r in zip(cols, dxt.itertuples()):
        on = r.diagnosis == dx
        with col:
            with st.container(key=f"pick_dx_{r.diagnosis}{'_on' if on else ''}"):
                UI.md(UI.dx_card(cond_label(r.diagnosis, True), COND_DESC.get(r.diagnosis, ""), r.total_bd,
                                 r.share_total, r.init_n, r.ret_n, on))
                st.button("Selected" if on else f"Explore {cond_label(r.diagnosis)}", key=f"btn_dx_{r.diagnosis}",
                          type="tertiary", icon=":material/check:" if on else ":material/arrow_forward:",
                          icon_position="right", on_click=_set, args=(r.diagnosis, None if not on else sev))
    if dx and sev:
        UI.md(f'<div class="selnote">✓ {group_name(dx, sev)} selected</div>')

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        if dx is None:
            UI.md('<div class="emptylvl">Select a condition above to see its severity breakdown.</div>')
        else:
            sb = H.severity_table(dx)
            t1, t2 = st.columns([2.1, 1.3], vertical_alignment="center")
            t1.markdown(f'<div class="lvl2">Severity Breakdown — {cond_label(dx)}</div>', unsafe_allow_html=True)
            with t2:
                with st.popover("Severity Levels", icon=":material/info:", key="sev_levels"):
                    UI.md(UI.SEVERITY_HTML)
            UI.md(UI.big_insight(H.severity_insight_v2(dx, cond_label(dx)), small=True))
            UI.md(UI.sev_head(_tip(f"Percentage of {cond_label(dx)}'s total Bed-days.")))
            for r in sb.itertuples():
                on = r.severity == sev
                with st.container(key=f"pick_sev_{dx}_{r.severity}{'_on' if on else ''}"):
                    UI.md(UI.sev_row(r.severity, H.SEVERITY_NAMES.get(r.severity, "").title(), r.total_bd,
                                     r.share_in_dx, sb.share_in_dx.max(), on))
                    st.button(f"Select {cond_label(dx)} severity {r.severity}", key=f"btn_sev_{dx}_{r.severity}",
                              type="tertiary", on_click=_set, args=(dx, int(r.severity)))

    age = (ss.ui.get("ov_age") or "All ages") if (dx and sev) else "All ages"
    with right:
        with st.container(key="ovprofile"):
            if dx is None:
                UI.md(UI.profile_head("Selected", "Whole Hospital"))
                UI.md(_profile_grid(hosp) + UI.insight_line(
                    "Group Insight", "Select a condition to see how its bed use breaks down by severity and age group."))
            elif sev is None:
                m = H.page_measures(dx)
                UI.md(UI.profile_head("Selected Condition", cond_label(dx, True)))
                UI.md(_profile_grid(m) + UI.insight_line(
                    "Group Insight", f"{cond_label(dx)} accounts for {m['share_total']:.0f}% of total Bed-days. "
                                     "Choose a severity level to see a patient group's profile."))
            else:
                UI.md(UI.profile_head("Selected Group", group_name(dx, sev)))
                age_sel = bind("ov_age", st.segmented_control if hasattr(st, "segmented_control") else st.radio,
                               "Age Group", store="ui", options=H.AGE_BANDS, format_func=H.AGE_SHORT.get,
                               **({} if hasattr(st, "segmented_control") else {"horizontal": True}))
                if age_sel is None:
                    age_sel = ss.ui["ov_age"] = "All ages"
                age = age_sel
                m = H.page_measures(dx, sev, age)
                legend = ("" if age == "All ages" else
                          f'<p class="pflegend"><i></i>All figures below are for patients '
                          f'{"aged 65+" if age == "65 and over" else "under 65"}.</p>')
                UI.md(legend + _profile_grid(m, by_age=age != "All ages")
                      + '<div class="abhd"><div class="al">Total Bed-days by Age Group</div>'
                        '<div class="as">Compare hospital bed use across age groups.</div></div>')
                split = bind("ov_split", st.toggle, "Show Initial vs Readmission Breakdown", store="ui")
                UI.md(UI.age_bed_use(H.age_bed_use(dx, sev), age, split=bool(split))
                      + UI.insight_line("Group Insight", H.group_insight_v2(dx, sev, age, f"{cond_label(dx)} Severity {sev}")))
    grp = f"{dx}|{sev}" if dx and sev else None

    # ================================================================ 03 How Does Admission Demand Change?
    UI.qhead(3, "How Does Admission Demand Change?", anchor="admission-patterns")
    c1, c2, _ = st.columns([1.6, 1, 1.4], vertical_alignment="bottom")
    seg = st.segmented_control if hasattr(st, "segmented_control") else st.radio
    seg_kw = {} if hasattr(st, "segmented_control") else {"horizontal": True}
    with c1:
        source = bind("ov_source", seg, "Admissions", store="ui", options=list(H.SOURCES),
                      format_func=H.SOURCES.get, **seg_kw) or "total"
    with c2:
        view = bind("ov_view", seg, "View", store="ui", options=["Monthly", "By Weekday"], **seg_kw) or "Monthly"
    ins = H.monthly_pattern(source) if view == "Monthly" else H.weekday_pattern_v2(source)
    UI.md(UI.time_insight(ins, "Highest Month" if view == "Monthly" else "Highest Weekday",
                          "Lowest Month" if view == "Monthly" else "Lowest Weekday"))
    if view == "Monthly":
        df = H.monthly_series(source)
        full = df[~df.incomplete]
        ihi, ilo = full.per_day.idxmax(), full.per_day.idxmin()
        colors = [UI.WARM if i == ihi else UI.TEAL if i == ilo else UI.HIST for i in df.index]
        sizes = [13 if i in (ihi, ilo) else 9 for i in df.index]
        symbols = ["circle-open" if inc else "circle" for inc in df.incomplete]
        tag = ["Highest month · " if i == ihi else "Lowest month · " if i == ilo else "" for i in df.index]
        fig = go.Figure(go.Scatter(
            x=df.label, y=df.per_day, mode="lines+markers+text", line=dict(color="#9DB3C9", width=2.5),
            marker=dict(size=sizes, color=colors, symbol=symbols, line=dict(width=2, color=colors)),
            text=[f"{v:,.0f}" for v in df.per_day], textposition="top center",
            textfont=dict(size=[14 if i in (ihi, ilo) else 12 for i in df.index],
                          color=[UI.WARM_DARK if i == ihi else UI.TEAL_DARK if i == ilo else UI.MUTED for i in df.index]),
            customdata=np.stack([df["count"], df.incomplete.map({True: " · incomplete month", False: ""}), tag], axis=1),
            hovertemplate="<b>%{x}</b><br>%{customdata[2]}%{y:,.0f} per day · %{customdata[0]:,} in the month"
                          "%{customdata[1]}<extra></extra>"))
        UI.style_fig(fig, 340, f"{H.SOURCES[source]} per Day, by Month", legend=False)
        fig.update_yaxes(range=[0, df.per_day.max() * 1.22], gridcolor="#EEF2F6", tickformat=",")
        show(fig, f"ov_monthly_{source}")
        _chart_note(H.chart_note(source, view))
    else:
        wd = H.weekday_series(source)
        ihi, ilo = wd.per_day.idxmax(), wd.per_day.idxmin()
        fig = go.Figure(go.Bar(
            x=[H.WEEKDAY_FULL[w] for w in wd.weekday], y=wd.per_day,
            marker_color=[UI.WARM if i == ihi else UI.TEAL if i == ilo else "#B5C4D3" for i in wd.index],
            text=[f"{v:,.0f}" for v in wd.per_day], textposition="outside", cliponaxis=False,
            textfont=dict(size=13, color=UI.INK),
            customdata=["Highest · " if i == ihi else "Lowest · " if i == ilo else "" for i in wd.index],
            hovertemplate="%{x}: %{customdata}%{y:,.0f} per day<extra></extra>"))
        UI.style_fig(fig, 340, f"{H.SOURCES[source]} per Day, by Weekday", legend=False)
        fig.update_layout(bargap=0.35)
        fig.update_yaxes(range=[0, wd.per_day.max() * 1.2], gridcolor="#EEF2F6", tickformat=",")
        show(fig, f"ov_weekday_{source}")
        _chart_note(H.chart_note(source, view))
    with st.expander("Month × Weekday Detail"):
        ylab, z = H.month_weekday_observed(source)
        flat = [v for row in z for v in row]
        unit = f"Average {H.SOURCES[source]} per Day"
        UI.md(UI.heat_legend(unit, min(flat), max(flat)))
        fig = go.Figure(go.Heatmap(z=z, x=[H.WEEKDAY_FULL[w] for w in H.WEEKDAYS], y=ylab, colorscale=UI.HEAT_SEQ,
                                   zmin=0, zmax=max(flat), showscale=False, xgap=2, ygap=2,
                                   hovertemplate="%{y} · %{x}: %{z:,.0f} per day<extra></extra>"))
        UI.style_fig(fig, 400, legend=False)
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        fig.update_xaxes(side="top")
        show(fig, f"ov_heat_{source}")
        st.caption("Hover a cell for its value."
                   + (" July–August 2011 readmission records are incomplete." if source != "initial" else ""))

    # ================================================================ simple end-of-page action
    def _to_simulator():
        """Prefill the most recently explored group (never runs anything; demand pattern is chosen in the simulator)."""
        d_, s_ = ss.ui.get("ex_dx"), ss.ui.get("ex_sev")
        if d_ and s_:
            ss.cfg.update(diagnosis=d_, severity=int(s_), age=ss.ui.get("ov_age") or "All ages")
            for n in ("diagnosis", "severity", "age"):
                clear_widget(n)
        go_to("simulator")

    with st.container(key="ovcta", horizontal=True, vertical_alignment="center", horizontal_alignment="center",
                      gap="large"):
        UI.md('<div class="ctaq">Ready to explore how changes could affect hospital capacity?</div>')
        st.button("Build a Scenario", type="primary", key="ov_build", icon=":material/arrow_forward:",
                  icon_position="right", on_click=_to_simulator)


def _chart_note(text):
    if text:
        UI.md(f'<p class="tchart-note">{UI.esc(text)}</p>')


def _profile_grid(m, by_age=False):
    """Selected-level metrics; every value follows the age group when one is chosen."""
    has_ret = m["ret_n"] > 0 or m["coh_ret"] > 0
    return UI.metric_grid(
        [("Initial Admissions", f"{m['init_n']:,}", by_age),
         ("Readmissions", f"{m['ret_n']:,}" if has_ret else "None Recorded", by_age),
         ("Total Bed-days", f"{m['total_bd']:,}", by_age)],
        [("Average Initial Stay", _days(m["init_stay"]), by_age),
         ("Average Readmission Stay", _days(m["ret_stay"]) if m["ret_n"] else "—", by_age),
         ("60-Day Readmission Rate", f"{m['rate']:.1f}%" if m["survivors"] else "—", by_age)])


# =========================================================================== PAGE 3: SIMULATOR
COND_PICK = {"CHF": "Heart Failure (CHF)", "AMI": "Heart Attack (AMI)",
             "COPD": "COPD (Chronic Obstructive Pulmonary Disease)"}
AGE_PICK = {"All ages": "All Ages", "Under 65": "Under 65", "65 and over": "65+"}
AGE_PHRASE = {"All ages": "", "Under 65": "under 65", "65 and over": "aged 65+"}
# Quick options; "custom" opens a whole-number entry over the full range the model accepts.
PCT_CHOICES = {
    "reduction": dict(presets=[0, 5, 10, 15], lo=0, hi=30, entry="Shorter Stays (%)",
                      fmt=lambda v: "No Change" if v == 0 else f"{v}%"),
    "readmit": dict(presets=[0, 5, 10, 15], lo=0, hi=50, entry="Fewer Readmissions (%)",
                    fmt=lambda v: "No Change" if v == 0 else f"{v}%"),
    "demand": dict(presets=[0, 10, 20], lo=-30, hi=40, entry="Change in Admissions (%)",
                   fmt=lambda v: "No Change" if v == 0 else f"{v:+d}%"),
}
BED_LO, BED_HI = 50, 30000
DURATIONS = [30, 60, 90, 120]          # simulated days; the DES takes any whole number of days
BED_PICK = {"reference": "Default Beds", "minus5": "5% Fewer", "minus10": "10% Fewer", "plus10": "10% More",
            "custom": "Custom"}
PATTERN_PICK = {"Annual average": "Typical Week", "Historical month-based": "Start from a Selected Month"}
PATTERN_CAPTION = {
    "Annual average": "Uses average admission patterns across the historical year.  \n*Best for general capacity planning.*",
    "Historical month-based": "Uses historical monthly demand patterns starting from your chosen month.  \n"
                              "*Best for testing busier or quieter periods.*"}
DEFAULT_BEDS_TIP = ("A starting bed number based on historical patient demand. You can change it to test other "
                    "capacity levels.")


def _num(v):
    """Signed whole number with a typographic minus."""
    return f"−{abs(v)}" if v < 0 else f"{v}"


def to_explorer():
    """Open Historical Overview at Explore Patient Groups, showing the scenario's group; nothing else changes."""
    ss.ui["ex_dx"], ss.ui["ex_sev"] = ss.cfg["diagnosis"], int(ss.cfg["severity"])
    ss.ui["ov_age"] = ss.cfg["age"]
    for k in ("w_ui_ov_age",):
        ss.pop(k, None)
    ss.ex_init = True
    ss.scroll_to = "explore-patient-groups"
    go_to("overview")


def group_return_rate(dx, sev):
    """60-day readmission probability the simulation uses for a diagnosis x severity group (patients discharged
    alive). Equals the group's observed all-ages cohort rate; the model applies it to every age."""
    d = S.calibration()
    gi = [str(g) for g in d["groups"]].index(f"{dx}|{sev}")
    return 100 * float(d[f"prob_survivor_{gi}"])


def period_timeline(season, days):
    """Calendar months the simulation runs through, from the model's own start-date rule (simulation.season_start):
    [(month name, simulated days in that month, days in that calendar month)]."""
    dates = H.sim_dates(season, days)
    out = []
    for (y, m), grp in pd.Series(dates).groupby([dates.year, dates.month], sort=False):
        out.append((H.MONTH_FULL[H.CAL_MONTHS[m - 1]], len(grp), pd.Period(f"{y}-{m:02d}").days_in_month))
    return out


def _period_phrase(season, days):
    """Short description of the historical pattern behind a period (used in Steps 1–2 and the preview)."""
    if season == "Annual average":
        return "a typical historical week"
    tl = period_timeline(season, days)
    return (f"historical {tl[0][0]} patterns" if len(tl) == 1
            else f"historical patterns from {tl[0][0]} to {tl[-1][0]}")


def _seg(name, label, options, fmt, store="cfg", **kw):
    """Segmented control bound to state; a click on the active option (deselect) keeps the previous value."""
    prev = ss[store].get(name)
    fn = st.segmented_control if hasattr(st, "segmented_control") else st.radio
    extra = {} if hasattr(st, "segmented_control") else {"horizontal": True}
    val = bind(name, fn, label, store=store, options=options, format_func=fmt, **extra, **kw)
    if val is None:
        val = ss[store][name] = prev if prev in options else options[0]
    return val


def range_hint(value, lo, hi, unit="", what="a whole number"):
    """Visible input constraint under a custom entry; turns into a clear message when the value is out of range
    (the value is never clamped silently; the Run button is disabled until it is fixed)."""
    ok = lo <= value <= hi
    rng = f"{_num(lo)}{unit} to {hi:,}{unit}" if isinstance(hi, int) and hi >= 1000 else f"{_num(lo)}{unit} to {_num(hi)}{unit}"
    if ok:
        UI.md(f'<p class="rangehint">Enter {what} from {rng}.</p>')
    else:
        UI.md(f'<p class="rangehint bad">{_num(value) if abs(value) < 1000 else f"{value:,}"}{unit} is outside the '
              f'supported range. Enter {what} from {rng}.</p>')
    return ok


def pct_control(name, label, help=None):
    """Quick options plus Custom (whole-number entry). Returns the value passed to the model."""
    spec = PCT_CHOICES[name]
    pick = f"{name}_pick"
    if f"w_ui_{pick}" not in ss:                       # derive the chip from the stored value
        ss.ui[pick] = ss.cfg[name] if ss.cfg[name] in spec["presets"] else "custom"
    choice = _seg(pick, label, spec["presets"] + ["custom"],
                  lambda v: "Custom" if v == "custom" else spec["fmt"](v), store="ui", help=help,
                  label_visibility="collapsed")
    if choice == "custom":
        val = bind(name, st.number_input, spec["entry"], step=1)
        range_hint(int(val), spec["lo"], spec["hi"], unit="%")
    else:
        ss.cfg[name] = val = int(choice)
        clear_widget(name)
    return int(val)


STEPS = [("step-1", "Choose a Period", "When and how long?"), ("step-2", "Set Admissions", "How much demand?"),
         ("step-3", "Set Beds", "How much capacity?"), ("step-4", "Test Improvements", "Could patient flow help?")]


def sim_head(n, title, sub, optional=False):
    UI.md(UI.step_head(n, title, sub, f"step-{n}", optional))


def period_section(n):
    with st.container(key="simsec_period"):
        sim_head(n, "Choose Your Planning Period",
                 "Choose how long to simulate and which historical admission pattern to use.")
        dur = _seg("duration", "Duration", DURATIONS, lambda x: f"{x} Days")
        with st.container(key="patpick"):
            pat = bind("pattern", st.radio, "Admission Pattern", options=list(PATTERN_PICK),
                       format_func=PATTERN_PICK.get, captions=[PATTERN_CAPTION[k] for k in PATTERN_PICK])
        if pat != "Historical month-based":
            UI.md(f'<p class="durline"><b>Your simulation covers {dur} days</b>, repeating the admission pattern of a '
                  'typical historical week.</p>')
            return
        a, b = st.columns([1, 2.6], gap="medium", vertical_alignment="bottom")
        with a:
            bind("start_month", st.selectbox, "Starting Month", options=H.CAL_MONTHS, format_func=H.MONTH_FULL.get)
        season = season_of(ss.cfg)
        tl = period_timeline(season, int(dur))
        dates = H.sim_dates(season, int(dur))
        segs = "".join(
            f'<div class="seg" style="flex:{n_} 1 0" title="{name}: {n_} of {full} days">'
            f'{name[:3] if n_ >= 7 else ""}</div>' for name, n_, full in tl)
        with b:
            UI.md(f'<div class="tl2" role="img" aria-label="'
                  + ", ".join(f"{name} {n_} days" for name, n_, _ in tl) + f'"><div class="bar">{segs}</div>'
                  f'<div class="ends"><span>{dates[0].day} {H.CAL_MONTHS[dates[0].month - 1]}</span>'
                  f'<span>{dates[-1].day} {H.CAL_MONTHS[dates[-1].month - 1]}</span></div></div>')
        UI.md(f'<p class="durline"><b>Your simulation covers {dur} days</b>, starting with '
              f'{H.MONTH_FULL[season]}\'s historical admission pattern.</p>')
        if any(name in ("July", "August", "September") for name, *_ in tl):
            UI.caution("Includes July–September, when the historical data show unusually few admissions.")


def demand_section(n):
    with st.container(key="simsec_demand"):
        sim_head(n, "Set Expected Admissions", "How many new admissions should the hospital plan for?")
        season, dur = season_of(ss.cfg), int(ss.cfg["duration"])
        a, b = st.columns([1, 1.15], gap="medium")
        with a:
            dem = pct_control("demand", "Admission demand change",
                              help="Changes the number of new (initial) admissions for every patient group by this "
                                   "percentage. Readmissions are not changed directly; they follow from the "
                                   "admissions simulated.")
        base = H.expected_admissions(season, dur)          # initial admissions/day the DES draws, this period
        if season == "Annual average":
            basis = f"Based on a typical historical week, over your {dur}-day period. New admissions only."
        else:
            basis = (f"Based on your selected {dur}-day period starting with {H.MONTH_FULL[season]}'s historical "
                     "pattern. New admissions only.")
        valid = PCT_CHOICES["demand"]["lo"] <= dem <= PCT_CHOICES["demand"]["hi"]
        chg = ("No change" if not dem else f"{'+' if dem > 0 else '−'}{abs(dem)}%")
        scen = (f'<div class="num">{base * (1 + dem / 100):,.0f}<small>per day</small><span class="chg">{chg}</span></div>'
                if valid else '<div class="num"><small>Enter a supported change</small></div>')
        with b:
            UI.md('<div class="admc"><div class="row">'
                  f'<div class="cell"><div class="lab">Historical Admissions</div>'
                  f'<div class="num">{base:,.0f}<small>per day</small></div></div>'
                  '<div class="arrow" aria-hidden="true">→</div>'
                  f'<div class="cell scen"><div class="lab">Admissions in Your Scenario</div>{scen}</div></div>'
                  f'<div class="basis">{UI.esc(basis)}</div></div>')


def beds_section(n):
    with st.container(key="simsec_beds"):
        sim_head(n, "Set Available Beds", "How many beds will be available in the hospital?")
        ref = rec_beds()
        if ss.cfg["custom_beds"] is None:
            ss.cfg["custom_beds"] = ref
        a, b = st.columns([1.35, 1], gap="large", vertical_alignment="center")
        with a:
            mode = _seg("bed_mode", "Bed capacity", list(BED_PICK), BED_PICK.get, label_visibility="collapsed")
            if mode == "custom":
                v = bind("custom_beds", st.number_input, "Available Beds", step=1,
                         help="Total number of beds available to patients in this simulation.")
                range_hint(int(v), BED_LO, BED_HI, what="a whole number of beds")
        beds = beds_for(ss.cfg, ref)
        with b:
            UI.md(f'<div class="bedbig"><b>{beds:,}</b> beds available '
                  + _tip("Total number of beds available to patients in this simulation.") + '</div>'
                  f'<p class="lvn">Default: {ref:,} beds {_tip(DEFAULT_BEDS_TIP)}</p>')


def flow_section(n):
    with st.container(key="simsec_flow"):
        sim_head(n, "Test Patient Flow Improvements",
                 "Could shorter stays or fewer readmissions help reduce pressure on beds?", optional=True)
        on = bind("flow_on", st.toggle, "Include Patient Flow Improvements")
        if not on:
            return
        UI.md('<div class="subq">Which patient group would you like to focus on?</div>')
        c1, c2, c3 = st.columns([1.55, 1.15, 0.8])
        with c1:
            dx = bind("diagnosis", st.selectbox, "Condition", options=H.diagnoses(),
                      format_func=lambda x: COND_PICK.get(x, x))
        with c2:
            sev = bind("severity", st.selectbox, "Severity", options=H.severities(dx),
                       format_func=lambda x: f"Severity {x} — {H.SEVERITY_NAMES.get(x, '').title()}")
        with c3:
            age = bind("age", st.selectbox, "Age Group", options=H.AGE_BANDS, format_func=AGE_PICK.get)
        gname = f"{cond_label(dx)} · Severity {sev}" + ("" if age == "All ages" else f" · {AGE_PICK[age]}")
        m = H.page_measures(dx, sev, age)          # every figure below is for the selected age group
        with st.container(key="aboutgrp"):
            UI.md('<div class="agh">About This Patient Group</div>'
                  f'<div class="agn">{UI.esc(gname)}</div>'
                  f'<div class="agm"><div><b>{m["init_per_day"]:,.1f}</b><span>Initial Admissions per Day '
                  f'{_tip("New (initial) admissions per day for this group, " + H.PERIOD_LABEL + ".")}</span></div>'
                  f'<div><b>{m["share_total"]:.1f}%</b><span>Share of Total Bed-days '
                  f'{_tip("Share of all historical Bed-days in the dataset, including initial stays and readmissions.")}'
                  '</span></div></div>')
            f1, f2 = st.columns([1.5, 1], vertical_alignment="center")
            f1.markdown(f'<div class="agfoot">Historical data, {H.PERIOD_LABEL}</div>', unsafe_allow_html=True)
            with f2:
                st.button("View Patient Group Details", key="sim_explore", type="tertiary",
                          icon=":material/arrow_forward:", icon_position="right", on_click=to_explorer)
        UI.md(f'<div class="impfor">Improvements for: <b>{UI.esc(gname)}</b></div>')
        a, b = st.columns(2, gap="large")
        with a:
            UI.md('<div class="lever"><div class="lvt">Shorter Patient Stays</div>'
                  '<div class="lvq">What if stays in this group were shorter?</div></div>')
            red = pct_control("reduction", "Stay reduction")
            UI.md('<div class="pvw">'
                  f'<div><span>Average Initial Stay '
                  f'{_tip("Historical average length of an initial stay for this group, " + H.PERIOD_LABEL + ".")}'
                  f'</span><b>{m["init_stay"]:.1f} days</b></div>'
                  f'<div><span>Reduction to Test '
                  f'{_tip("Each initial stay in this group is shortened by this percentage and rounded to whole days, so very short stays may not change. Stays of patients who died are not shortened.")}'
                  f'</span><b>{f"{red}%" if red else "None"}</b></div></div>')
        with b:
            rate = group_return_rate(dx, sev)
            UI.md('<div class="lever"><div class="lvt">Fewer Readmissions</div>'
                  '<div class="lvq">What if fewer patients in this group returned after discharge?</div></div>')
            rr = pct_control("readmit", "Readmission reduction")
            new_rate = rate * (1 - rr / 100)          # exactly the DES rule: p x (1 - r/100), for this group
            UI.md('<div class="pvw">'
                  f'<div><span>60-Day Readmission Rate '
                  f'{_tip("Readmission rate used by the simulation for this diagnosis and severity group (all ages).")}'
                  f'</span><b>{rate:.1f}%</b></div>'
                  f'<div><span>Reduction to Test</span><b>{f"{rr}%" if rr else "None"}</b></div></div>')
            whom = "" if age == "All ages" else f" for patients {AGE_PHRASE[age]}"
            if rate == 0:
                UI.md('<p class="rrline">This group has no recorded readmissions, so this setting has no effect.</p>')
            elif rr:
                UI.md(f'<p class="rrline">A {rr}% reduction would lower the readmission rate{whom} from '
                      f'<b>{rate:.1f}%</b> to about <b>{new_rate:.1f}%</b>.</p>')
            else:
                UI.md(f'<p class="rrline">Reductions are a share of the current rate: for example, 10% would lower '
                      f'{rate:.1f}% to about {rate * 0.9:.1f}%, not by 10 percentage points.</p>')
            if age != "All ages" and m["survivors"]:
                UI.md(f'<p class="lvsub">Historically, {m["rate"]:.1f}% of patients {AGE_PHRASE[age]} in this group '
                      'were readmitted. The simulation uses the group’s all-ages rate.</p>')
        if not red and not rr:
            UI.md('<p class="note">Choose a reduction above to test an improvement, or switch this step off.</p>')


def scenario_statement(s):
    """One short plain-language sentence built from the active inputs (never claims an outcome)."""
    month = s["season"] != "Annual average"
    demand_src = (f"admission demand based on {H.MONTH_FULL[s['season']]}'s historical pattern" if month
                  else "typical admission demand")
    beds_changed = s["beds"] != s["ref_beds"]
    beds = f"{s['beds']:,} available beds"
    dur = f"over {s['duration']} days"
    adm = (f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'fewer'} admissions" if s["demand"] else "")
    adm_ctx = (f" than {H.MONTH_FULL[s['season']]}'s historical pattern" if month else "")
    imp = " and ".join(x for x in (f"{s['reduction']}% shorter stays" if s["reduction"] else "",
                                   f"{s['readmit']}% fewer readmissions" if s["readmit"] else "") if x)
    if imp:
        grp = f"{cond_label(s['diagnosis'])} Severity {s['severity']} patients" + (
            f" {AGE_PHRASE[s['age']]}" if s["age"] != "All ages" else "")
        if s["demand"]:
            tail = (f" could help manage {abs(s['demand'])}% {'higher' if s['demand'] > 0 else 'lower'} admission "
                    f"demand{adm_ctx}")
        else:
            tail = " could reduce bed pressure" + (f" with {demand_src}" if month else "")
        tail += f" with {beds}" if beds_changed else ""
        return f"Test whether {imp} for {grp}{tail}."
    if s["demand"]:
        return f"Test how the hospital could manage {adm}{adm_ctx} with {beds} {dur}."
    if beds_changed:
        return f"Test how the hospital could manage {demand_src} with {beds} {dur}."
    return f"See how the hospital could manage {demand_src} with {beds} {dur}."


def summary_panel(settings):
    """Scenario Preview in the manager's order: period, demand, beds, then optional improvements."""
    s = settings
    improve = bool(s["reduction"] or s["readmit"])
    dem = "No change" if not s["demand"] else f"{_num(s['demand']) if s['demand'] < 0 else '+' + str(s['demand'])}%"
    period = "Typical Week" if s["season"] == "Annual average" else f"Starting in {H.MONTH_FULL[s['season']]}"
    beds_txt = f"{s['beds']:,}" + (" <small>default</small>" if s["beds"] == s["ref_beds"] else "")

    def rows(items):
        return "".join(f'<div class="sprow"><span>{k}</span><b>{v}</b></div>' for k, v in items)
    html = ('<div class="spanel"><div class="sph">Your Scenario</div>'
            f'<div class="spstmt">{UI.esc(scenario_statement(s))}</div>'
            '<div class="spg"><div class="spl">1 · Planning Period</div>'
            + rows([("Duration", f"{s['duration']} Days"), ("Admission Pattern", period)]) + '</div>'
            '<div class="spg"><div class="spl">2 · Expected Admissions</div>' + rows([("Change", dem)]) + '</div>'
            '<div class="spg"><div class="spl">3 · Available Beds</div>' + rows([("Beds", beds_txt)]) + '</div>'
            '<div class="spg"><div class="spl">4 · Patient Flow Improvements</div>')
    if improve:
        html += (f'<div class="spt">{cond_label(s["diagnosis"])} · Severity {s["severity"]}</div>'
                 f'<div class="spa">{AGE_PICK.get(s["age"], s["age"])}</div>'
                 + rows([("Shorter Stays", f"{s['reduction']}% shorter" if s["reduction"] else "No change"),
                         ("Fewer Readmissions", f"{s['readmit']}% fewer" if s["readmit"] else "No change")]))
    else:
        html += '<div class="spe">Not included</div>'
    UI.md(html + "</div></div>")


def page_simulator():
    sync_cfg()
    target = ss.pop("scroll_to", None)
    if target:                                  # arriving from a Welcome planning question: open at that step
        scroll_to_anchor(target)
    left, right = st.columns([2.15, 1], gap="large")
    with left:
        with st.container(key="simleft"):
            UI.md('<div class="ovhead simhead"><h1>Build a Scenario</h1><p>Set up a hospital capacity scenario in four '
                  'simple steps.</p></div>' + UI.step_nav(STEPS, optional={4}))
            period_section(1)
            demand_section(2)
            beds_section(3)
            flow_section(4)
            advanced_settings()

    # ---- live preview + primary action
    render_preview(right)


def advanced_settings():
        with st.expander("Advanced Settings"):
            a1, a2, a3 = st.columns(3)
            with a1:
                bind("reps", st.slider, "Number of Simulation Runs", min_value=3, max_value=30,
                     help="More runs give steadier averages but take longer.")
            with a2:
                bind("seed", st.number_input, "Random Seed", step=1,
                     help="The same seed and settings always give the same results.")
            with a3:
                bind("breakdown", st.checkbox, "Analyse Each Change Separately",
                     help="Also runs each change on its own when you change more than one of: stay length, "
                          "readmissions, admission demand. Separate effects need not add up to the combined effect.")



def render_preview(right):
    settings, ref = current_settings()
    key = tuple(settings[n] for n in NAMES)
    problem = run_problem(settings)
    run = False
    with right:
        with st.container(key="summary"):
            summary_panel(settings)
            if problem:
                UI.md(f'<p class="note">{problem}</p>')
            elif ss.result is not None and ss.result["key"] == key:
                UI.md('<p class="status-ok">✓ Your latest results match this scenario.</p>')
            elif ss.result is not None:
                UI.md('<p class="status-stale">Your latest results are for earlier settings. Run again to update.</p>')
            run = st.button("Run Simulation", type="primary", key="run_sim", icon=":material/arrow_forward:",
                            icon_position="right", disabled=bool(problem), **BTN_KW)
            if ss.result is not None:
                st.button("View Latest Results", key="sim_view", type="tertiary", on_click=go_to, args=("results",),
                          **BTN_KW)
    if run:
        do_run()


# =========================================================================== PAGE 4: RESULTS
RV = None  # current Results object, set in page_results


def M(metric, scen):
    """Mean and 95% interval half-width of a replication metric (simulation.ci_summary)."""
    return RV.m(metric, scen)


def E(metric, scen="Scenario"):
    """Paired difference vs Baseline, 95% half-width and clear-difference flag (simulation.paired_effects)."""
    return RV.e(metric, scen)


REF_NAMES = {"Reference": "Reference Scenario", "Conditions only": "Same Conditions, No Improvements"}
RES_SECTIONS = [("capacity-overview", "Capacity Overview"), ("compare-scenarios", "Compare Scenarios"),
                ("planning-impact", "Impact of Changes"), ("explore-options", "Explore Another Option")]
FULL_OCC = 98.5          # % average occupancy treated as "at capacity" in the wording
TAIL_DAYS = 140          # simulation follow-up after the period (simulation.TAIL_DAYS)


# ---------------------------------------------------------------- scenario description
def _pattern_phrase(s):
    return ("the average historical weekly admission pattern" if s["season"] == "Annual average"
            else f"historical admission patterns starting in {H.MONTH_FULL[s['season']]}")


def _group_phrase(s):
    return (f"{cond_label(s['diagnosis'])} Severity {s['severity']}"
            + ("" if s["age"] == "All ages" else f" ({AGE_PICK[s['age']]})"))


def _patients(s):
    """'Heart Failure Severity 3 patients aged 65+' (the targeted population, in plain words)."""
    return (f"{cond_label(s['diagnosis'])} Severity {s['severity']} patients"
            + ("" if s["age"] == "All ages" else f" {AGE_PHRASE[s['age']]}"))


def _imp_list(s):
    return " and ".join(x for x in (f"{s['reduction']}% shorter stays" if s["reduction"] else "",
                                    f"{s['readmit']}% fewer readmissions" if s["readmit"] else "") if x)


def scenario_sentences(s):
    """'The Scenario You Tested': one or two plain sentences generated from the run's own settings."""
    beds = f"{s['beds']:,} available beds" + (" (the default)" if s["beds"] == s["ref_beds"] else "")
    if RH.scenario_case(s) == "none":
        return [f"You tested the reference scenario: historical admission levels and {beds} over {s['duration']} days, "
                f"using {_pattern_phrase(s)}, with no changes."]
    dem = ("historical admission levels" if not s["demand"] else
           f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'fewer'} admissions")
    out = [f"You tested a {s['duration']}-day scenario with {dem} and {beds}, using {_pattern_phrase(s)}."]
    if s["reduction"] or s["readmit"]:
        out.append(f"You also tested whether {_imp_list(s)} for {_patients(s)} could help reduce bed pressure.")
    return out


def reference_text(s):
    """What the reference run is (matches results_helpers.build_runs: no changes, default beds, same period/seeds)."""
    return (f"The reference uses historical admission demand, the default {s['ref_beds']:,} beds and no patient-flow "
            f"improvements over the same {s['duration']}-day period and admission pattern.")


# ---------------------------------------------------------------- paired comparisons between any two runs
def pair(res, a, b, metric):
    """Run b minus run a for one replication metric, paired by run (same seeds). None if not estimable."""
    reps = res["reps"]
    x = reps[reps.scenario == a].set_index("rep")[metric].astype(float)
    y = reps[reps.scenario == b].set_index("rep")[metric].astype(float)
    if x.isna().any() or y.isna().any() or not len(x):
        return None
    d = (y - x).values
    half = S.t975(len(d)) * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else 0.0
    return dict(a=float(x.mean()), b=float(y.mean()), diff=float(d.mean()), half=float(half),
                clear=bool(abs(d.mean()) > half))


def pair_unlimited(res, a, b, key):
    """Same for the unlimited-bed runs: key 'nb' (busy-day bed demand) or 'bd' (bed-day demand)."""
    src = res.get("nb_vals" if key == "nb" else "bd_demand")
    if not src or a not in src or b not in src:
        return None
    x, y = np.asarray(src[a], float), np.asarray(src[b], float)
    d = y - x
    half = S.t975(len(d)) * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else 0.0
    return dict(a=float(x.mean()), b=float(y.mean()), diff=float(d.mean()), half=float(half),
                clear=bool(abs(d.mean()) > half))


def run_mean(res, name, metric):
    v = res["reps"][res["reps"].scenario == name][metric].astype(float)
    return float(v.mean()) if len(v) and not v.isna().any() else None


def full_day_share(res, name, beds):
    """Share of days on which beds were full in every run (replication-averaged occupancy at the limit)."""
    dl = res["daily"][res["daily"].scenario == name]
    return float((dl.occupied >= beds - 0.5).mean()) if len(dl) else 0.0


def waits_ok(res, *names):
    return all((run_mean(res, n, "unresolved_requests") or 0) == 0 for n in names)


# ---------------------------------------------------------------- semantic change chips
def dchip(p, unit="", dp=0, better=None, pts=False):
    """Change indicator. better: 'down' / 'up' / None (no favourable direction). Grey when within run-to-run
    variation. Arrow, number and unit always shown, so colour is never the only cue."""
    if p is None:
        return '<span class="dchip flat">Not estimable</span>'
    if not p["clear"] or round(p["diff"], dp) == 0:
        return '<span class="dchip flat">No clear difference</span>'
    up = p["diff"] > 0
    cls = "neutral" if better is None else ("good" if (up == (better == "up")) else "bad")
    u = " pts" if pts else (f" {unit}" if unit else "")
    return f'<span class="dchip {cls}">{"▲" if up else "▼"} {abs(p["diff"]):,.{dp}f}{u}</span>'


def _kcard(title, value, sub, chip="", tip=""):
    return (f'<div class="rk2"><div class="t">{title}{(" " + _tip(tip)) if tip else ""}</div>'
            f'<div class="v">{value}</div>{chip}<div class="n">{sub}</div></div>')


def _days(v):
    return "0 days" if v is not None and v < 0.005 else (f"{v:.2f} days" if v < 1 else f"{v:.1f} days")


def capacity_cards(s, res, a="Reference", b="Scenario", show_ref=True):
    """Main KPI row: occupancy, average wait, busy-day bed demand, requests that waited (scenario b vs run a)."""
    cards = []
    occ = pair(res, a, b, "occupancy_pct")
    full = full_day_share(res, b, s["beds"])
    occ_sub = (f"Reference: {occ['a']:.0f}% of {s['ref_beds']:,} beds" if show_ref else
               f"of {s['beds']:,} available beds")
    if occ["b"] >= FULL_OCC:
        occ_sub += f" · full on {full * 100:.0f}% of days"
    cards.append(_kcard("Bed Occupancy", f"{occ['b']:.0f}%", occ_sub,
                        dchip(occ, dp=0, pts=True) if show_ref else "",
                        "Average share of the available beds in use each day. It cannot go above 100%, so once beds "
                        "are full, waiting shows the extra pressure."))
    ok = waits_ok(res, b) and (waits_ok(res, a) or not show_ref)
    if waits_ok(res, b):
        w = pair(res, a, b, "mean_wait_days") if show_ref and waits_ok(res, a) else None
        wb = run_mean(res, b, "mean_wait_days")
        dw = RH.delay_if_waited(RH.Results(s, view_of(res, a)), "Scenario") if b == "Scenario" else None
        sub = (f"Reference: {_days(run_mean(res, a, 'mean_wait_days'))}" if show_ref and waits_ok(res, a)
               else ("Reference: not estimable" if show_ref else "per bed request"))
        if dw:
            sub += f" · about {dw:.1f} days for those who waited"
        cards.append(_kcard("Average Wait for a Bed", _days(wb), sub,
                            dchip(w, "days", 2, "down") if (show_ref and w) else "",
                            "Average days from asking for a bed to getting one, over all bed requests in the period "
                            "(new admissions and readmissions), counting same-day admissions as 0. Whole days."))
    else:
        us = run_mean(res, b, "unresolved_requests")
        cards.append(_kcard("Average Wait for a Bed", "Not estimable",
                            f"About {us:,.0f} requests were still waiting {TAIL_DAYS} days after the period, so an "
                            "average would understate waiting.", "", ""))
    nb = pair_unlimited(res, a, b, "nb")
    over = nb["b"] - s["beds"]
    nb_sub = (f"{over:,.0f} more than the {s['beds']:,} available" if over > 0 else
              f"within the {s['beds']:,} available")
    if show_ref:
        nb_sub += f" · Reference: {nb['a']:,.0f}"
    cards.append(_kcard("Estimated Busy-day Bed Demand", f"{nb['b']:,.0f} beds", nb_sub,
                        dchip(nb, "beds", 0, "down") if show_ref else "",
                        "An estimate of bed demand on busier days, before applying the available-bed limit: the "
                        "95th percentile of beds in use per day in separate runs with no bed limit. Not a staffed bed "
                        "count or a guaranteed requirement."))
    if waits_ok(res, b):
        wp = pair(res, a, b, "waited_pct") if show_ref and waits_ok(res, a) else None
        cards.append(_kcard("Bed Requests That Waited", RH.fmt_pct_small(run_mean(res, b, "waited_pct")),
                            (f"Reference: {RH.fmt_pct_small(run_mean(res, a, 'waited_pct'))}" if show_ref and waits_ok(res, a)
                             else ("Reference: not estimable" if show_ref else "waited at least one day")),
                            dchip(wp, dp=1, better="down", pts=True) if (show_ref and wp) else "",
                            "Share of bed requests (new admissions and readmissions) that waited at least one day."))
    else:
        cards.append(_kcard("Bed Requests That Waited", "Not estimable",
                            "Demand exceeded the available beds: some requests never got a bed within the follow-up.",
                            "", ""))
    return '<div class="rkrow2">' + "".join(cards) + "</div>"


# ---------------------------------------------------------------- key finding and implications
def _state(s, res, name, beds):
    """Capacity state of one run, from its own outputs."""
    if not waits_ok(res, name):
        return "overloaded"
    occ = run_mean(res, name, "occupancy_pct")
    waited = run_mean(res, name, "waited_pct")
    if occ >= FULL_OCC:
        return "full"
    if waited >= 5:
        return "busy"
    return "ok"


def key_finding(s, res):
    """(headline, supporting sentence) from this run's numbers and run-to-run variation; never fixed wording."""
    st_ = _state(s, res, "Scenario", s["beds"])
    occ = run_mean(res, "Scenario", "occupancy_pct")
    full = full_day_share(res, "Scenario", s["beds"])
    if st_ == "overloaded":
        head = ("Demand exceeded the available beds: some patients were still waiting for a bed long after the "
                "period ended.")
    elif st_ == "full":
        when = "throughout the period" if full >= 0.999 else ("for most of the period" if full >= 0.5 else "on average")
        head = (f"Beds were fully occupied {when}, and {RH.fmt_pct_small(run_mean(res, 'Scenario', 'waited_pct'))} "
                f"of bed requests had to wait (average {_days(run_mean(res, 'Scenario', 'mean_wait_days'))} per "
                "request).")
    elif st_ == "busy":
        head = (f"Beds were {occ:.0f}% occupied on an average day, and {RH.fmt_pct_small(run_mean(res, 'Scenario', 'waited_pct'))} "
                "of bed requests waited at least a day.")
    else:
        w = run_mean(res, "Scenario", "waited_pct")
        head = (f"The hospital managed the demand: beds were {occ:.0f}% occupied on an average day and "
                + ("almost no one had to wait for a bed." if w < 1 else f"{RH.fmt_pct_small(w)} of bed requests waited."))
    case = RH.scenario_case(s)
    if case == "none":
        return head, "This is the reference scenario, so there is nothing to compare it with yet."
    support = []
    ref_state = _state(s, res, "Reference", s["ref_beds"])
    if case in ("conditions", "combined"):
        what = _cond_phrase(s)
        w = pair(res, "Reference", "Scenario", "mean_wait_days") if waits_ok(res, "Reference", "Scenario") else None
        if ref_state in ("full", "overloaded") and st_ in ("full", "overloaded"):
            support.append(f"The reference was already at capacity in this period, so {what} mainly changed how long "
                           "patients waited rather than occupancy.")
        if w is None:
            if st_ == "overloaded" and ref_state != "overloaded":
                support.append(f"With {what}, the beds could no longer keep up, unlike in the reference.")
        elif w["clear"]:
            support.append(f"With {what}, the average wait {'rose' if w['diff'] > 0 else 'fell'} from {_days(w['a'])} "
                           f"to {_days(w['b'])} compared with the reference.")
        elif ref_state == "ok" and st_ == "ok":
            support.append(f"With {what}, waiting stayed low, as in the reference.")
        else:
            support.append(f"With {what}, waiting did not clearly change compared with the reference.")
    if case in ("improve", "combined"):
        support.append(improvement_sentence(s, res))
    return head, " ".join(x for x in support if x)


def improvement_sentence(s, res):
    """What the targeted improvements added, from the matching run without them (never the combined effect)."""
    comp = RH.improvement_comparator(s)
    bd = pair_unlimited(res, comp, "Scenario", "bd")
    rt = pair(res, comp, "Scenario", "returns") if s["readmit"] else None
    w = pair(res, comp, "Scenario", "mean_wait_days") if waits_ok(res, comp, "Scenario") else None
    gains = []
    if rt and rt["clear"] and rt["diff"] < 0:
        gains.append(f"reduced readmissions by about {-rt['diff']:,.0f}")
    if bd and bd["clear"] and bd["diff"] < 0:
        gains.append(f"lowered bed-day demand by about {-bd['diff']:,.0f} bed-days over {s['duration']} days")
    imp = f"The patient-flow improvements for {_patients(s)}"
    if not gains:
        return f"{imp} made no clear difference in this simulation."
    txt = f"{imp} {' and '.join(gains)}"
    if w is None:
        return txt + "."
    if w["clear"] and w["diff"] < 0:
        return txt + f", and shortened the average wait by {-w['diff']:.2f} days."
    if _state(s, res, comp, s["beds"]) == "ok":
        return txt + ", while waiting was already low."
    return txt + ", but did not clearly reduce waiting under these capacity conditions."


def _cond_phrase(s):
    bits = []
    if s["demand"]:
        bits.append(f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'fewer'} admissions")
    if s["beds"] != s["ref_beds"]:
        bits.append(f"{'fewer' if s['beds'] < s['ref_beds'] else 'more'} beds ({s['beds']:,})")
    return " and ".join(bits)


def capacity_plan_points(s, res):
    """'What This Means for Your Capacity Plan': two or three statements, each tied to this run's numbers."""
    out = []
    st_ = _state(s, res, "Scenario", s["beds"])
    nb = pair_unlimited(res, "Reference", "Scenario", "nb")
    over = nb["b"] - s["beds"]
    if st_ in ("overloaded", "full", "busy") and over > 0:
        out.append(f"On busy days this scenario would need about {nb['b']:,.0f} beds without a bed limit, "
                   f"{over:,.0f} more than the {s['beds']:,} available. Testing more beds would show how much waiting "
                   "could fall.")
    elif st_ in ("overloaded", "full", "busy"):
        out.append("Waiting occurred even though busy-day demand stayed close to the available beds; demand varies "
                   "from day to day, so short peaks can still fill every bed.")
    elif nb["b"] < 0.95 * s["beds"]:
        out.append(f"There was spare capacity: busy-day demand reached about {nb['b']:,.0f} beds, below the "
                   f"{s['beds']:,} available. Testing higher demand or fewer beds would show how much headroom "
                   "remains.")
    else:
        out.append(f"Busy-day demand (about {nb['b']:,.0f} beds) is close to the {s['beds']:,} available, so "
                   "small increases in demand could start to cause waiting.")
    if s["reduction"] or s["readmit"]:
        comp = RH.improvement_comparator(s)
        bd = pair_unlimited(res, comp, "Scenario", "bd")
        share = H.page_measures(s["diagnosis"], s["severity"], s["age"])["share_total"]
        if bd and bd["clear"] and bd["diff"] < 0:
            out.append(f"The improvements lowered bed-day demand by about {-bd['diff'] / s['duration']:,.0f} beds on "
                       "an average day. "
                       + ("Because beds stayed full, waiting patients used the freed beds, so occupied beds did not "
                          "fall." if st_ in ("full", "overloaded") else "That is capacity other admissions could use."))
        else:
            out.append(f"The selected group accounts for about {share:.0f}% of historical bed-days, so changes to this "
                       "group alone have a limited hospital-wide effect. A larger change or another group may matter "
                       "more.")
    if s["readmit"] and group_return_rate(s["diagnosis"], s["severity"]) == 0:
        out.append("This group has no recorded readmissions, so reducing readmissions has no effect in the model.")
    return out[:3]


# ---------------------------------------------------------------- 03 impact
def _row(label, p, unit, dp, better, pts=False, fmt=None):
    f = fmt or (lambda v: f"{v:,.{dp}f}{(' ' + unit) if unit and not pts else ''}{'%' if pts else ''}")
    if p is None:
        return f'<div class="ir"><span>{label}</span><b>Not estimable</b><b></b>{dchip(None)}</div>'
    return (f'<div class="ir"><span>{label}</span><b>{f(p["a"])}</b><b>{f(p["b"])}</b>'
            f'{dchip(p, unit, dp, better, pts)}</div>')


def effect_table(s, res, a, b, a_name, b_name, include_flow=False):
    ok = waits_ok(res, a, b)
    rows = [_row("Average wait for a bed", pair(res, a, b, "mean_wait_days") if ok else None, "days", 2, "down",
                 fmt=_days),
            _row("Bed requests that waited", pair(res, a, b, "waited_pct") if ok else None, "", 1, "down", pts=True),
            _row("Estimated busy-day bed demand", pair_unlimited(res, a, b, "nb"), "beds", 0, "down"),
            _row("Bed-day demand (before the bed limit)", pair_unlimited(res, a, b, "bd"), "", 0, "down"),
            _row("Occupied bed-days", pair(res, a, b, "bed_days"), "", 0, None)]
    if include_flow:
        if s["reduction"]:
            rows.insert(0, _row(f"Average initial stay, {_group_phrase(s)} patients", pair(res, a, b, "target_mean_los"),
                                "days", 2, "down"))
        if s["readmit"]:
            rows.insert(0, _row("Readmissions scheduled (all patients)", pair(res, a, b, "returns"), "", 0, "down"))
    return (f'<div class="itab"><div class="ir ih"><span></span><b>{a_name}</b><b>{b_name}</b><em>Change</em></div>'
            + "".join(rows) + "</div>")


def breakdown_simple(s, res):
    """Each change on its own, in plain words; the ± statistics stay in Detailed Simulation Results."""
    reps = res["reps"]
    others = [x for x in ("Demand only", "LOS only", "Readmissions only") if x in set(reps.scenario)]
    if not others:
        return False
    rows = []
    for sc in others + ["Scenario"]:
        bd = pair(res, "Baseline", sc, "bed_days")
        w = pair(res, "Baseline", sc, "mean_wait_days") if waits_ok(res, "Baseline", sc) else None
        if w and w["clear"]:
            short = "Adds pressure" if w["diff"] > 0 else "Eases pressure"
        elif w is None:
            short = "Waiting not estimable"
        else:
            short = "No clear effect on waiting"
        rows.append(f'<div class="ir"><span>{RH.LEVER_NAMES[sc]}</span>'
                    f'{dchip(bd, "bed-days", 0, None)}{dchip(w, "days", 2, "down")}<em>{short}</em></div>')
    UI.md('<div class="rsub">Each change on its own</div>'
          '<div class="itab four"><div class="ir ih"><span></span><b>Occupied bed-days</b><b>Average wait</b>'
          '<em>In short</em></div>' + "".join(rows) + "</div>"
          f'<p class="rnote">Each run is compared with no changes and the same {s["beds"]:,} beds. “No clear difference” '
          'means the change was within the variation between simulation runs. Separate effects need not add up to the '
          'combined effect because all patients share the same beds.</p>')
    return True


def impact_section(s, res):
    case = RH.scenario_case(s)
    if case == "none":
        UI.md('<p class="qsub">No planning changes were made, so there is no effect to show. Try one of the options '
              'below.</p>')
        return
    if case in ("conditions", "combined"):
        UI.md('<div class="rsub">Overall Scenario Effect</div><p class="rlead">Your full scenario compared with the '
              'reference.</p>' + effect_table(s, res, "Reference", "Scenario", "Reference", "Your Scenario",
                                              include_flow=case == "combined"))
    if case in ("improve", "combined"):
        comp = RH.improvement_comparator(s)
        lead = ("To understand their effect, we compared your scenario with the same demand and bed settings but "
                "without the improvements." if case == "combined" else
                "Demand and beds were not changed, so the improvements are compared directly with the reference.")
        UI.md('<div class="rsub">Did Patient Flow Improvements Help?</div>'
              f'<p class="rlead">{lead}</p>'
              + effect_table(s, res, comp, "Scenario", "Without Improvements" if case == "combined" else "Reference",
                             "With Improvements", include_flow=True))
        if _state(s, res, "Scenario", s["beds"]) in ("full", "overloaded"):
            UI.md('<p class="rnote">Beds stayed full, so beds freed by shorter stays or fewer readmissions were taken by '
                  'waiting patients: occupied bed-days cannot fall. Bed-day demand and waiting show the effect '
                  'instead.</p>')
    breakdown_simple(s, res)
    with st.expander("Detailed Simulation Results"):
        breakdown_table(s, res)
        results_stats(s)



def results_line(s):
    """Compact summary of what was tested: only active or relevant settings."""
    parts = []
    if s["reduction"] or s["readmit"]:
        parts.append(f"{cond_label(s['diagnosis'])} Severity {s['severity']}"
                     + ("" if s["age"] == "All ages" else f" · {AGE_PICK.get(s['age'], s['age'])}"))
        if s["reduction"]:
            parts.append(f"Shorter Stays −{s['reduction']}%")
        if s["readmit"]:
            parts.append(f"Fewer Readmissions −{s['readmit']}%")
    if s["demand"]:
        parts.append(f"Demand {s['demand']:+d}%")
    parts.append(f"{s['beds']:,} Beds" + (" (reference)" if s["beds"] == s["ref_beds"] else ""))
    parts.append(f"{s['duration']} Days" + ("" if s["season"] == "Annual average" else f" from {H.MONTH_FULL[s['season']]}"))
    return " · ".join(parts)


def results_view(result):
    s, res = result["settings"], result["res"]
    return RH.Results(s, view_of(res, comparator(s)))


def save_current():
    """Store this run's exact settings and the outcomes shown in Compare Your Options (never overwritten)."""
    if ss.result is None or any(x["key"] == ss.result["key"] for x in ss.saved):
        return
    st_s, res = ss.result["settings"], ss.result["res"]
    R = results_view(ss.result)
    rec = RH.compare_record(R, st_s, ss.result["bed_mode"])
    ok = waits_ok(res, "Scenario")
    rec.update(key=ss.result["key"], finished=ss.result["finished"],
               sentences=scenario_sentences(st_s), state=_state(st_s, res, "Scenario", st_s["beds"]),
               occ=run_mean(res, "Scenario", "occupancy_pct"),
               wait=run_mean(res, "Scenario", "mean_wait_days") if ok else None,
               waited=run_mean(res, "Scenario", "waited_pct") if ok else None,
               nb=float(np.mean(res["nb_vals"]["Scenario"])))
    ss.saved_seq += 1
    rec["title"] = f"Option {chr(64 + ((ss.saved_seq - 1) % 26) + 1)}"
    ss.saved = (ss.saved + [rec])[-MAX_SAVED:]


def remove_saved(key):
    ss.saved = [x for x in ss.saved if x["key"] != key]


def breakdown_table(s, res):
    reps = res["reps"]
    others = [x for x in ("LOS only", "Demand only", "Readmissions only") if x in set(reps.scenario)]
    if not others:
        return
    st.markdown("**Each change on its own, with 95% intervals**")
    sub = reps[reps.scenario.isin(["Baseline", "Scenario", *others])]
    eff = S.paired_effects(sub, ["bed_days", "mean_wait_days", "returns"], versus="Baseline")
    rows = []
    for sc in others + ["Scenario"]:
        r = {"Run": RH.LEVER_NAMES[sc]}
        for label, key, dp in (("Bed-days", "bed_days", 0), ("Average wait (days)", "mean_wait_days", 2),
                               ("Readmissions", "returns", 0)):
            e = eff[(eff.scenario == sc) & (eff.metric == key)].iloc[0]
            r[label] = (f"{e['diff']:+,.{dp}f} ± {e['ci95']:,.{dp}f}" + ("" if e["clear"] else " *")
                        if RH.finite(e["diff"]) else "Not estimable")
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, **DF_KW)
    st.caption(f"Each run compared with no changes and the same {s['beds']:,} beds. * within simulation noise. Separate "
               "effects need not add up to the combined effect because all patients share the same beds.")


def try_next(cfg_update, flow=None):
    """Prepare a variation of the current scenario and open the builder (nothing runs automatically; the latest
    results and any saved options are kept until a new run)."""
    for k, v in cfg_update.items():
        ss.cfg[k] = v
        clear_widget(k)
        if f"w_ui_{k}_pick" in ss:
            del ss[f"w_ui_{k}_pick"]
    if flow is not None:
        ss.cfg["flow_on"] = flow
        clear_widget("flow_on")
    go_to("simulator")


def next_ideas(s, res):
    """Relevant variations only, never one already applied at the same level."""
    ideas = []
    st_ = _state(s, res, "Scenario", s["beds"])
    more = int(round(s["beds"] * 1.10 / 10) * 10)
    fewer = int(round(s["beds"] * 0.90 / 10) * 10)
    if st_ in ("overloaded", "full", "busy") and more <= BED_HI:
        ideas.append((f"Test 10% More Beds ({more:,})", dict(bed_mode="custom", custom_beds=more), None))
    elif st_ == "ok" and fewer >= BED_LO:
        ideas.append((f"Test 10% Fewer Beds ({fewer:,})", dict(bed_mode="custom", custom_beds=fewer), None))
    lo, hi = PCT_CHOICES["demand"]["lo"], PCT_CHOICES["demand"]["hi"]
    if s["demand"] > 0 and st_ in ("overloaded", "full", "busy"):
        ideas.append(("Test Historical Admissions", dict(demand=0), None))
    elif not s["demand"]:
        ideas.append(("Test 10% More Admissions", dict(demand=10), None))
    elif s["demand"] + 10 <= hi:
        ideas.append((f"Test {s['demand'] + 10:+d}% Admissions", dict(demand=s["demand"] + 10), None))
    else:
        ideas.append(("Test Historical Admissions", dict(demand=0), None))
    rmax = PCT_CHOICES["reduction"]["hi"]
    if not (s["reduction"] or s["readmit"]):
        ideas.append((f"Test 10% Shorter Stays ({cond_label(s['diagnosis'])} {s['severity']})", dict(reduction=10), True))
    elif s["reduction"] and s["reduction"] + 5 <= rmax:
        ideas.append((f"Test a Larger Stay Reduction ({s['reduction'] + 5}%)", dict(reduction=s["reduction"] + 5), True))
    elif not s["reduction"]:
        ideas.append(("Add 10% Shorter Stays", dict(reduction=10), True))
    return ideas[:3]


def differences(s):
    """Settings of the run next to the reference (shown in View Scenario Settings)."""
    out = [("Planning Period", f"{s['duration']} days · " + ("Typical Week" if s["season"] == "Annual average"
                                                             else f"starting in {H.MONTH_FULL[s['season']]}"), "same"),
           ("Admission Demand", "No change" if not s["demand"] else f"{s['demand']:+d}%",
            "same" if not s["demand"] else "changed"),
           ("Available Beds", f"{s['beds']:,} (default {s['ref_beds']:,})" if s["beds"] != s["ref_beds"]
            else f"{s['beds']:,} (default)", "same" if s["beds"] == s["ref_beds"] else "changed")]
    if s["reduction"] or s["readmit"]:
        out.append(("Patient Flow Improvements", f"{_group_phrase(s)}: {_imp_list(s)}", "changed"))
    else:
        out.append(("Patient Flow Improvements", "None", "same"))
    out.append(("Simulation Runs", f"{s['reps']} runs · seed {s['seed']}", "same"))
    return out


def page_results():
    global RV
    if ss.result is None:
        UI.page_title("Results", "No results yet",
                      "Build a capacity scenario and press <b>Run Simulation</b>. Your results will appear here and "
                      "stay available while you move between pages.")
        st.button("Build a Capacity Scenario", type="primary", key="res_empty", icon=":material/arrow_forward:",
                  icon_position="right", on_click=go_to, args=("simulator",))
        return
    s, res = ss.result["settings"], ss.result["res"]
    if "nb_vals" not in res or "ref_beds" not in s or "bd_demand" not in res:
        UI.page_title("Results", "Please run the scenario again",
                      "These results were produced by an earlier version of the planner.")
        st.button("Edit Scenario", type="primary", key="res_edit", on_click=go_to, args=("simulator",))
        return
    case = RH.scenario_case(s)
    RV = RH.Results(s, view_of(res, "Reference"))
    UI.md(UI.section_nav(RES_SECTIONS))
    UI.md(f'<div class="ovhead simhead"><div class="eyebrow">Results · {ss.result["finished"]}</div>'
          '<h1>Capacity Results</h1><p>Could the hospital manage the demand in your scenario?</p></div>')

    # ---- the scenario you tested
    current, _ = current_settings()
    stale = tuple(current[n] for n in NAMES) != ss.result["key"]
    saved = any(x["key"] == ss.result["key"] for x in ss.saved)
    with st.container(key="restested"):
        UI.md('<div class="rtt">The Scenario You Tested</div>'
              + "".join(f'<p class="rts">{UI.esc(x)}</p>' for x in scenario_sentences(s)))
        with st.container(key="resactions", horizontal=True, gap="small", vertical_alignment="center"):
            st.button("Edit Scenario", key="res_edit", type="primary", icon=":material/edit:", on_click=go_to,
                      args=("simulator",))
            st.button("Saved for Comparison" if saved else "Save for Comparison", key="cmp_add", disabled=saved,
                      icon=":material/check:" if saved else ":material/add:", on_click=save_current)
            if stale:
                rerun = st.button("Re-run with New Settings", key="res_rerun")
                UI.md('<span class="status-stale">Your scenario settings have changed since this run.</span>')
                if rerun:
                    do_run()
        with st.expander("View Scenario Settings"):
            UI.md('<div class="diffs">' + "".join(
                f'<div class="dfr {st_}"><span>{k}</span><b>{UI.esc(v)}</b>'
                f'<em>{"Changed" if st_ == "changed" else "Same as reference"}</em></div>'
                for k, v, st_ in differences(s)) + "</div>")

    # ---- 01 capacity overview
    UI.qhead(1, "Hospital Capacity Overview", "capacity-overview")
    head, support = key_finding(s, res)
    UI.md(f'<div class="keyfind2"><div class="kh">{UI.esc(head)}</div>'
          + (f'<div class="ks">{UI.esc(support)}</div>' if support else "") + "</div>")
    UI.md(capacity_cards(s, res, show_ref=case != "none"))
    if case != "none":
        UI.md(f'<p class="rnote">Compared with the reference scenario ({s["ref_beds"]:,} beds, historical demand, no '
              'improvements). Grey means the difference was within the variation between simulation runs.</p>')
    occ = run_mean(res, "Scenario", "occupancy_pct")
    if occ >= FULL_OCC or (case != "none" and run_mean(res, "Reference", "occupancy_pct") >= FULL_OCC):
        UI.md('<div class="satnote"><b>Why occupancy may not change:</b> occupancy cannot go above 100%. Once beds are '
              'full, extra demand shows up as longer waits and busy-day bed demand above the available beds.</div>')
    pts = capacity_plan_points(s, res)
    if pts:
        UI.md('<div class="plan2"><div class="pt">What This Means for Your Capacity Plan</div><ul>'
              + "".join(f"<li>{UI.esc(p)}</li>" for p in pts) + "</ul></div>")

    # ---- 02 compare
    UI.qhead(2, "Compare Scenarios", "compare-scenarios")
    UI.md(f'<p class="qsub">{UI.esc(reference_text(s))}</p>'
          '<div class="legend2"><span><i class="lr"></i>Reference Scenario</span>'
          '<span><i class="ls"></i>Your Scenario</span></div>')
    names = ["Beds", "Waiting", "Admissions & Readmissions", "Length of Stay"]
    fns = {"Beds": details_beds, "Waiting": details_waiting, "Length of Stay": details_los,
           "Admissions & Readmissions": details_admissions}
    for tab, nm in zip(st.tabs(names), names):
        with tab:
            fns[nm](s)

    # ---- 03 impact
    UI.qhead(3, "Impact of Planning Changes", "planning-impact")
    impact_section(s, res)

    # ---- 04 next
    UI.qhead(4, "Explore Another Option", "explore-options")
    UI.md('<p class="qsub">Each option opens Build a Scenario with one change applied. Run the simulation to see its '
          'results; your current results stay here until then.</p>')
    with st.container(key="resexplore", horizontal=True, gap="small"):
        for i, (label, upd, flow) in enumerate(next_ideas(s, res)):
            st.button(label, key=f"res_try_{i}", on_click=try_next, args=(upd, flow))
        st.button("Edit Scenario", key="res_edit2", type="tertiary", icon=":material/edit:", on_click=go_to,
                  args=("simulator",))
        st.button("Export Data", key="res_export", type="tertiary", icon=":material/download:", on_click=go_to,
                  args=("export",))
    render_comparison(saved)



def details_beds(s):
    st.markdown("##### Beds in use over the period")
    opts = ["Weekly trend", "Daily", "Weekday pattern"] + (["Monthly"] if H.is_seasonal(s["season"]) else [])
    view = bind("bed_view", st.radio, "View", store="ui", options=opts, horizontal=True, label_visibility="collapsed")
    fig = go.Figure()
    if view == "Weekday pattern":
        prof = RV.weekday_profile("occupied")
        z = [prof[prof.scenario == sc].occupied.tolist() for sc in ("Baseline", "Scenario")]
        fig.add_trace(go.Heatmap(z=z, x=H.WEEKDAYS, y=["Reference", "Your Scenario"], colorscale=UI.HEAT, showscale=False,
                                 texttemplate="%{z:,.0f}", textfont=dict(size=14), xgap=4, ygap=4,
                                 hovertemplate="%{y} · %{x}: %{z:,.0f} beds in use on average<extra></extra>"))
        UI.style_fig(fig, 200, legend=False)
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=14, color=UI.INK), autorange="reversed")
        fig.update_xaxes(side="top", tickfont=dict(size=14, color=UI.INK))
        show(fig, "res_occ_weekday")
    else:
        agg, xlab = RV.by_period("occupied", {"Weekly trend": "Weekly"}.get(view, view), "mean")
        for name, color, dash in (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid")):
            a = agg[agg.scenario == name]
            if view == "Daily":
                fig.add_scatter(x=a.period, y=a.value, name=name, mode="lines", line=dict(color=color, width=2.4, dash=dash),
                                hovertemplate="Day %{x}: %{y:,.0f} beds<extra>" + name + "</extra>")
            elif view == "Weekly trend":
                fig.add_scatter(x=a.label, y=a.value, name=name, mode="lines+markers", marker=dict(size=8),
                                line=dict(color=color, width=3, dash=dash),
                                hovertemplate="%{x}: %{y:,.0f} beds on an average day<extra>" + name + "</extra>")
            else:
                fig.add_bar(x=a.label, y=a.value, name=name, marker_color=color, text=[f"{v:,.0f}" for v in a.value],
                            textposition="outside", cliponaxis=False)
        fig.add_hline(y=s["beds"], line_dash="dot", line_color=UI.TEAL_DARK, line_width=2,
                      annotation_text=f"Your scenario: {s['beds']:,} beds available", annotation_position="top left",
                      annotation_font_color=UI.TEAL_DARK)
        if s["ref_beds"] != s["beds"]:
            fig.add_hline(y=s["ref_beds"], line_dash="dot", line_color=UI.BASE, line_width=2,
                          annotation_text=f"Reference: {s['ref_beds']:,} beds available",
                          annotation_position="bottom left" if s["ref_beds"] < s["beds"] else "top right",
                          annotation_font_color=UI.MUTED)
        UI.style_fig(fig, 330)
        vals = agg.value
        lim = [s["beds"], s["ref_beds"]]
        fig.update_yaxes(title="Beds in use", range=[min(vals.min(), *lim) * 0.92, max(vals.max(), *lim) * 1.05])
        fig.update_xaxes(title=None)
        if view == "Daily":
            monday_ticks(fig, RV.daily_frame())
        show(fig, f"res_occ_{view}")
    if view in ("Daily", "Weekday pattern"):
        with st.expander("Why does bed use rise and fall each week?"):
            UI.md(RH.rhythm_text(RV))
    res = ss.result["res"]
    full_s = full_day_share(res, "Scenario", s["beds"])
    full_r = full_day_share(res, "Reference", s["ref_beds"])
    if full_s >= 0.5 or full_r >= 0.5:
        both = full_s >= 0.5 and full_r >= 0.5
        UI.md('<p class="rnote"><b>Flat lines at the limit do not mean capacity was sufficient.</b> '
              + ("Both runs" if both else ("Your scenario" if full_s >= 0.5 else "The reference"))
              + " had every bed in use on most days, so the line cannot rise any further while patients wait. "
              "See the Waiting tab for the extra pressure.</p>")
    UI.md('<p class="rnote">Average beds in use across the simulation runs, never more than the beds available.</p>')

    dx = RH.dx_bed_use(RV)
    constrained = dx.attrs.get("constrained", False)
    st.markdown("##### Estimated Bed Demand by Condition")
    UI.md('<p class="rnote">Roughly how many beds each condition’s patients need on an average day: new admissions per '
          'day × average modelled initial stay. An estimate, not beds counted in the model; the conditions share one '
          'pool of beds and are not separate wards.</p>')
    order = (([] if constrained else ["Return stays (all groups)"]) +
             dx[(dx.scenario == "Baseline") & (dx.kind == "dx")].sort_values("beds").label.tolist())
    fig = go.Figure()
    for name, color in (("Scenario", UI.TEAL), ("Baseline", UI.BASE)):
        a = dx[dx.scenario == name].set_index("label").loc[order]
        fig.add_bar(y=order, x=a.beds, name=name, orientation="h", marker_color=color,
                    text=[f"{v:,.0f}" for v in a.beds], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}: ≈ %{x:,.0f} beds needed on an average day<extra>" + name + "</extra>")
    UI.style_fig(fig, 300)
    fig.update_layout(barmode="group", bargap=0.3, legend=dict(traceorder="reversed"))
    fig.update_xaxes(visible=False, range=[0, dx.beds.max() * 1.2])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=14, color=UI.INK))
    show(fig, "res_dx_beds")
    if not constrained:
        UI.md('<p class="rnote">Return stays are not tracked by condition and are shown as one block.</p>')
    with st.expander("Why no busy-day bed numbers per diagnosis?"):
        UI.md("The model places every patient in one shared pool of beds and records only the hospital-wide daily "
              "count. Busy-day (95th-percentile) or peak beds per diagnosis would need the model to record daily "
              "occupied beds for each group — a backend change not made in this version. Dividing the hospital-wide "
              "busy-day reference by patient share would look precise but would not be a model result, so it is not "
              "shown.")


def details_waiting(s):
    (wb, _), (ws, _) = M("waited_pct", "Baseline"), M("waited_pct", "Scenario")
    (mb, _), (ms, _) = M("mean_wait_days", "Baseline"), M("mean_wait_days", "Scenario")
    (qb, _), (qs, _) = M("peak_queue", "Baseline"), M("peak_queue", "Scenario")
    (ub, _), (us, _) = M("unresolved_requests", "Baseline"), M("unresolved_requests", "Scenario")
    db, dsc = RH.delay_if_waited(RV, "Baseline"), RH.delay_if_waited(RV, "Scenario")
    f = lambda v: "none waited" if v is None else f"≈ {v:.1f} d"
    if ub > 0 or us > 0:
        UI.caution(f"<b>Waiting cannot be fully estimated.</b> On average {us:,.0f} scenario requests ({ub:,.0f} "
                   "baseline) were still unserved 140 days after the period, so averages would understate waiting.")
    UI.tiles([("Requests that waited", f"{RH.fmt_pct_small(wb)} → {RH.fmt_pct_small(ws)}",
               "share of bed requests waiting at least one day"),
              ("Wait for those who waited", f"{f(db)} → {f(dsc)}",
               f"all requests: {RH.fmt_days(mb)} → {RH.fmt_days(ms)} days on average"),
              ("Largest daily queue", f"{qb:,.0f} → {qs:,.0f}", "requests waiting on the busiest day")])
    daily = RV.daily_frame()
    daily = daily[daily.scenario.isin(["Baseline", "Scenario"])]
    if daily.queue.max() < 1:
        UI.insight("No queue formed in either run: every request got a bed on the day it arrived.")
    else:
        fig = go.Figure()
        for name, color, dash in (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid")):
            a = daily[daily.scenario == name]
            fig.add_scatter(x=a.day, y=a.queue, name=name, mode="lines", line=dict(color=color, width=2.4, dash=dash),
                            hovertemplate="Day %{x}: %{y:,.0f} waiting<extra>" + name + "</extra>")
        UI.style_fig(fig, 280, "Bed requests still waiting at the end of each day")
        fig.update_yaxes(rangemode="tozero")
        monday_ticks(fig, daily)
        show(fig, "res_queue")
        with st.expander("Why does waiting come in weekly spikes?"):
            UI.md(RH.rhythm_text(RV))
    UI.md('<p class="rnote">Waits are whole days in one shared first-come-first-served queue for a hospital bed. They '
          'show capacity pressure and are not emergency-department waiting times. Waiting is not recorded by '
          'condition.</p>')


def details_los(s):
    d = RH.dx_los(RV)
    order = d[d.scenario == "Baseline"].label.tolist()[::-1]
    b = d[d.scenario == "Baseline"].set_index("label").loc[order].los
    sc = d[d.scenario == "Scenario"].set_index("label").loc[order].los
    fig = go.Figure()
    for y, x0, x1 in zip(order, b, sc):
        fig.add_scatter(x=[x0, x1], y=[y, y], mode="lines", line=dict(color="#C9D3DD", width=6), showlegend=False,
                        hoverinfo="skip")
    fig.add_scatter(x=b, y=order, mode="markers+text", name="Baseline", marker=dict(size=16, color=UI.BASE),
                    text=[f"{v:.1f}" for v in b], textposition="middle left", textfont=dict(color=UI.MUTED))
    fig.add_scatter(x=sc, y=order, mode="markers+text", name="Scenario", marker=dict(size=16, color=UI.TEAL),
                    text=[f"{v:.1f}" for v in sc], textposition="middle right", textfont=dict(color=UI.TEAL_DARK))
    UI.style_fig(fig, 290, "Average modelled initial stay (days)")
    lo, hi = min(b.min(), sc.min()), max(b.max(), sc.max())
    fig.update_xaxes(range=[lo - 0.9, hi + 0.9], showgrid=True, gridcolor="#E6EBF0")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=14, color=UI.INK))
    show(fig, "res_los")
    short, _ = M("targeted_admissions", "Scenario")
    if s["reduction"]:
        UI.insight(f"About <b>{short:,.0f}</b> stays in {H.group_label(RV.group)} were shortened by the assumed "
                   f"{s['reduction']}% reduction. Other groups change only through random variation. The effect "
                   "comes from your assumption, not from evidence of a real intervention.")
    else:
        UI.insight("No length-of-stay change was assumed; differences are random variation.")


def details_admissions(s):
    (ab, _), (as_, _) = M("admissions", "Baseline"), M("admissions", "Scenario")
    (rb, _), (rs, _) = M("returns", "Baseline"), M("returns", "Scenario")
    da = RH.dx_admissions(RV)
    dx_txt = " · ".join(
        f"{dx} {da[(da.scenario == 'Baseline') & (da.diagnosis == dx)].per_day.iloc[0]:,.0f} → "
        f"{da[(da.scenario == 'Scenario') & (da.diagnosis == dx)].per_day.iloc[0]:,.0f}" for dx in H.diagnoses())
    UI.tiles([("New admissions in period", f"{ab:,.0f} → {as_:,.0f}", f"per day by diagnosis: {dx_txt}"),
              ("Return stays scheduled", f"{rb:,.0f} → {rs:,.0f}",
               "by patients admitted in the period; some return after it ends")])
    c1, c2 = st.columns(2)
    with c1:
        series = bind("adm_series", st.radio, "Show", store="ui", options=["New admissions", "Return stays scheduled"],
                      horizontal=True)
    with c2:
        opts = ["Daily", "Weekly"] + (["Monthly"] if H.is_seasonal(s["season"]) else []) + ["Weekday pattern"]
        view = bind("adm_view", st.radio, "View", store="ui", options=opts, horizontal=True)
    col = "new_admissions" if series == "New admissions" else "new_returns"
    fig = go.Figure()
    if view == "Weekday pattern":
        prof = RV.weekday_profile(col)
        z = [prof[prof.scenario == sc][col].tolist() for sc in ("Baseline", "Scenario")]
        fig.add_trace(go.Heatmap(z=z, x=H.WEEKDAYS, y=["Reference", "Your Scenario"], colorscale=UI.HEAT, showscale=False,
                                 texttemplate="%{z:,.0f}", textfont=dict(size=14), xgap=4, ygap=4,
                                 hovertemplate="%{y} · %{x}: %{z:,.0f} per day<extra></extra>"))
        UI.style_fig(fig, 200, legend=False)
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)", autorange="reversed", tickfont=dict(size=14, color=UI.INK))
        fig.update_xaxes(side="top", tickfont=dict(size=14, color=UI.INK))
    else:
        agg, _ = RV.by_period(col, view, "mean" if view == "Daily" else "sum")
        for name, color, dash in (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid")):
            a = agg[agg.scenario == name]
            if view == "Daily":
                fig.add_scatter(x=a.period, y=a.value, name=name, mode="lines", line=dict(color=color, width=2, dash=dash))
            else:
                fig.add_bar(x=a.label, y=a.value, name=name, marker_color=color, text=[f"{v:,.0f}" for v in a.value],
                            textposition="outside", cliponaxis=False)
        UI.style_fig(fig, 320)
        fig.update_yaxes(title="Per day" if view == "Daily" else "Total", rangemode="tozero")
        if view == "Daily":
            monday_ticks(fig, RV.daily_frame())
    show(fig, f"res_adm_{col}_{view}")
    if col == "new_returns":
        UI.note("Return stays are counted on the day the original patient got a bed, not the day they come back — "
                "not a 30-day readmission rate or an observed readmission count.")


def results_stats(s):
    UI.note(f"Mean over {s['reps']} runs ± half-width of a 95% Monte Carlo interval; differences are paired run by run. "
            "These intervals reflect simulation randomness only — not uncertainty in the data, the assumptions or "
            "real-world effectiveness.")

    def u(v, h, dp, sign=False):
        if not (RH.finite(v) and RH.finite(h)):
            return "Not estimable"
        return f"{v:{'+' if sign else ''},.{dp}f} ± {h:,.{dp}f}"

    table = [("Average stay, target group (days)", "target_mean_los", 2), ("Average stay, all patients (days)", "average_los", 2),
             ("New admissions per day", "avg_admissions_day", 1), ("Bed occupancy (%)", "occupancy_pct", 1),
             ("Average beds occupied", "avg_occupied", 0), ("Busiest day, beds occupied", "peak_occupied", 0),
             ("Total bed-days", "bed_days", 0),
             ("Average wait (days)", "mean_wait_days", 2), ("95th-percentile wait (days)", "p95_wait_days", 2),
             ("Requests that waited (%)", "waited_pct", 1), ("Largest daily queue", "peak_queue", 0),
             ("Return stays scheduled", "returns", 0), ("Stays shortened (target group)", "targeted_admissions", 0)]
    rows = []
    for name, key, dp in table:
        (bm, bc), (sm, sc_) = M(key, "Baseline"), M(key, "Scenario")
        d, ci, cl = E(key)
        rows.append({"Measure": name, "Reference": u(bm, bc, dp), "Tested Scenario": u(sm, sc_, dp),
                     "Difference": u(d, ci, dp, True),
                     "Clear difference?": "Not estimable" if not RH.finite(d) else ("Yes" if cl else "Within noise")})
    (bn, bc), (sn, sc_) = RV.nb("Baseline"), RV.nb("Scenario")
    d, ci, cl = RV.nb_effect()
    rows.append({"Measure": "Busy-day planning reference, unlimited beds (p95)", "Reference": u(bn, bc, 0),
                 "Tested Scenario": u(sn, sc_, 0), "Difference": u(d, ci, 0, True),
                 "Clear difference?": "Yes" if cl else "Within noise"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, **DF_KW)
    st.caption(f"The planning reference uses {min(s['reps'], 5)} separate unlimited-bed runs.")


STATE_LABEL = {"ok": ("Managed demand", "good"), "busy": ("Some waiting", "warn"), "full": ("At capacity", "bad"),
               "overloaded": ("Demand exceeded beds", "bad")}


def render_comparison(saved_now):
    UI.md('<div class="rsub" id="compare-options">Compare Your Options</div>'
          '<p class="rlead">Save this scenario, test another option, and compare the results side by side.</p>')
    st.button("Saved for Comparison" if saved_now else "Save This Scenario", key="cmp_add2", disabled=saved_now,
              icon=":material/check:" if saved_now else ":material/add:", on_click=save_current)
    recs = [r for r in ss.saved if "sentences" in r]
    if not recs:
        return
    cur = ss.result["key"] if ss.result else None
    cards = []
    for r in recs:
        lab, cls = STATE_LABEL.get(r["state"], ("", ""))
        wait = "Not estimable" if r["wait"] is None else _days(r["wait"])
        waited = "Not estimable" if r["waited"] is None else RH.fmt_pct_small(r["waited"])
        cards.append(
            f'<div class="cmp2{" cur" if r["key"] == cur else ""}"><div class="nm">{UI.esc(r["title"])}'
            f'{"<em>Current results</em>" if r["key"] == cur else ""}</div>'
            f'<div class="as">{UI.esc(" ".join(r["sentences"]))}</div>'
            f'<div class="st {cls}">{lab}</div>'
            f'<div class="m"><span>Available beds</span><b>{r["beds"]:,}</b></div>'
            f'<div class="m"><span>Bed occupancy</span><b>{r["occ"]:.0f}%</b></div>'
            f'<div class="m"><span>Average wait for a bed</span><b>{wait}</b></div>'
            f'<div class="m"><span>Requests that waited</span><b>{waited}</b></div>'
            f'<div class="m"><span>Busy-day bed demand</span><b>{r["nb"]:,.0f}</b></div></div>')
    UI.md(f'<div class="cmpgrid">{"".join(cards)}</div>')
    with st.container(key="cmprm", horizontal=True, gap="small"):
        for r in recs:
            st.button(f"Remove {r['title']}", key=f"cmp_rm_{r['title']}", type="tertiary", on_click=remove_saved,
                      args=(r["key"],))
    UI.md(f'<p class="rnote">{len(recs)} of {MAX_SAVED} saved. Each option keeps the settings and results of its own '
          'run. The tool does not pick a best option: weigh waiting, busy-day demand and beds against what is '
          'feasible for your hospital.</p>')


# =========================================================================== SECONDARY: EXPORT / DOCS
def page_export():
    UI.page_title("Export data", "Download data from your latest run",
                  "CSV and JSON files for further analysis (for example in SAS or Excel). Patient-level calibration "
                  "data are never included.")
    if ss.result is None:
        UI.insight("Run a simulation first — exports always correspond to your latest completed run.")
        st.button("Go to the Scenario Simulator →", key="dl_empty", on_click=go_to, args=("simulator",))
        return
    s = ss.result["settings"]
    res = ss.result["res"]
    UI.md(f'<div class="testedline">{UI.esc(results_line(s))}</div>')
    tag = (f"{s['diagnosis']}{s['severity']}_{s['age'].replace(' ', '')}_los{s['reduction']}_dem{s['demand']:+d}"
           f"_ret{s['readmit']}_{s['beds']}beds_{s['duration']}d_{s['season'].replace(' ', '')}")
    UI.note(f"Run completed {ss.result['finished']}. File names carry the tag <code>{tag}</code>; full settings are in "
            "the run-settings file.")
    run_json = json.dumps(dict(interface_version=APP_VERSION, model_version=MODEL_VERSION, completed=ss.result["finished"],
                               settings=s, bed_choice=BED_MODES[ss.result["bed_mode"]],
                               readmission_reduction_scope="selected patient group (condition, severity, age group)",
                               planning_reference_beds=ss.result["reference"],
                               warmup_days=S.WARMUP_DAYS, waiting_follow_up_days=S.TAIL_DAYS,
                               calibration_encounters=int(S.calibration()["total"]),
                               historical_period=H.PERIOD_LABEL), indent=2, default=str)
    files = [("Replication results", "One row per run and scenario", res["reps"].to_csv(index=False), f"replications_{tag}.csv", "text/csv"),
             ("Daily time series", "Beds in use, queue, cumulative admissions", res["daily"].to_csv(index=False), f"daily_{tag}.csv", "text/csv"),
             ("Patient-group summary", "Admissions and modelled stay per group", res["sub"].to_csv(index=False), f"groups_{tag}.csv", "text/csv"),
             ("Bed planning reference", "Unlimited-bed busy-day reference", res["nb"].to_csv(index=False), f"beds_reference_{tag}.csv", "text/csv"),
             ("Run settings", "All assumptions and versions (JSON)", run_json, f"run_settings_{tag}.json", "application/json"),
             ("Data dictionary", "What every column means", RH.DATA_DICTIONARY.to_csv(index=False), "data_dictionary.csv", "text/csv")]
    cols = st.columns(3)
    for i, (label, desc, data, name, mime) in enumerate(files):
        with cols[i % 3]:
            with st.container(border=True):
                UI.md(f"<b>{label}</b><br><span class='note'>{desc}</span>")
                st.download_button(f"⤓ Download {name.rsplit('.', 1)[1].upper()}", data.encode("utf-8"),
                                   file_name=name, mime=mime, key=f"dl_{i}", **DL_KW)


def page_docs():
    UI.page_title("Model documentation", "How the model works and what it cannot do")
    st.button("← Back", key="docs_back", on_click=go_to, args=(ss.prev_page if ss.prev_page != "docs" else "welcome",))
    st.markdown("""
**In brief**
- **What it simulates:** one shared pool of beds with a first-come-first-served queue, in daily steps, driven by
  2011–12 admission rates, stay lengths and return-stay patterns for AMI, CHF and COPD (pooled across hospitals).
- **Baseline vs scenario:** the same simulated hospital, run with the same random draws, with and without your
  assumptions. Results are averaged over repeat runs.
- **Busy-day bed reference:** 95th-percentile daily occupancy in separate runs with unlimited beds — a planning
  reference, not a guaranteed requirement or a zero-waiting threshold.
- **Default beds (Build a Scenario):** 2,800 with the current data: the 95th-percentile daily occupancy when the
  typical-week admission pattern is simulated with unlimited beds (120 days × 3 runs, seed 2026), rounded to the
  nearest 100. It is a model-derived planning default, not an observed or staffed bed count, and it does not change
  with the selected period. The same calculation for other periods gives different values (for example about
  3,900 for a January start and 2,500 for July); these are simulated unlimited-bed figures, so they are not shown as
  a comparison with the Available Beds setting.
- **Admission patterns:** *Typical Week* uses each patient group's average initial admissions per weekday over the
  whole historical year. *Start from a Selected Month* starts on the 1st of that month and uses that calendar month's
  weekday rates for each simulated day, moving on to the next month's rates as the calendar advances (real month
  lengths, e.g. February has 29 days in the 2012 data calendar), so a 120-day run from February covers February,
  March, April and 30 of May's 31 days. Historical Admissions in Step 2 is the average of exactly these daily rates
  over the selected duration (initial admissions only; readmissions are simulated separately).
- **Diagnosis-level bed use:** an estimate (admissions per day × average modelled stay). Busy-day or peak beds per
  diagnosis are not available because the model does not track occupancy by group.
- **Patient groups:** diagnosis (AMI heart attack, CHF heart failure, COPD) × APR-DRG severity level as recorded in
  the data (1 minor, 2 moderate, 3 major, 4 extreme). Severity is used for grouping only, not as a validated clinical
  score.
- **Readmissions:** recorded on each initial admission (READMIT_DATE / READMIT_DISCHARGE_DATE in the original
  file): at most one per initial admission, beginning 1–60 days after discharge. The model and the Historical
  Overview use readmissions of patients discharged alive with a recorded severity: 21,542 events (22,399 recorded;
  761 death-readmission conflicts and 96 without a severity code excluded). Readmission Rate = these readmissions ÷
  initial admissions discharged alive (15.7%).
- **Which basis each Historical Overview figure uses:** every count, per-day value, average stay and Bed-days figure
  on the page covers stays that *began* 1 Jul 2011 – 30 Jun 2012 (initial admissions by admission date,
  readmissions by readmission date): 141,810 initial admissions and 19,825 readmissions (54 per day), 955,741 Bed-days
  (stays still in progress on 30 June are counted in full). The Readmission Rate is the only cohort measure: it
  follows every initial admission of the year for 60 days, so its 21,542 readmissions include 1,717 in Jul–Aug 2012.
  The simulation is calibrated on the cohort measures. July–August 2011 readmissions are incomplete because
  readmissions of patients first admitted before July 2011 are not in the data.
- **Patient-flow improvements (v4.2):** shorter stays and fewer readmissions both apply only to the selected
  condition × severity × age group. Eligibility is set at the initial admission and carried with the patient; the
  readmission reduction is a relative cut in the group's modelled 60-day return probability (the same rate is used for
  all ages, as age-specific rates are not calibrated). Readmissions are not assumed to be avoidable, and the two
  improvements are independent assumptions.
- **Comparisons:** improvements alone are compared with the same demand and beds without them; demand or bed changes
  with the reference scenario (historical demand, planning-reference beds, no improvements); combined scenarios show
  both. Extra comparison runs use the same random seeds as the tested scenario.
- **Age groups:** age is recorded at the initial admission; each readmission is linked to that admission, so
  readmission counts, rates, stays and Bed-days are available for Under 65 and 65+ (age at the initial admission;
  age at the readmission itself is not recorded).
- **Time patterns** are counted from the original admission and readmission dates (history_calendar.npz, built by
  build_history_calendar.py with the same selection rules; aggregated daily counts only). Readmissions do not appear
  as separate initial-admission rows (checked by matching hospital, gender, ZIP and dates: fewer matches than chance),
  so Total Admissions does not double count.
- **Data characteristics to keep in mind:** admission dates cluster on some days (49 of 366 days have no initial
  admissions; readmissions fall on 143 of the 366 days in the reference year) about 39% of rows duplicate another row apart from their
  identifiers, and the 141,810 rows contain only about 2,900 distinct combinations of dates, condition, severity and
  age, which indicates a constructed (synthetic) dataset. Daily patterns are therefore not shown, and weekday
  differences should be read with care. July 2011 is missing an estimated ~60% and August ~13% of its readmissions
  (returns of patients admitted before July 2011); from September coverage is essentially complete. All 39 hospitals contribute admissions in every month, so the lower
  July–September 2011 volumes are not explained by hospitals joining the dataset; their cause is not documented.
- **Department field:** the original DEPARTMENT values (e.g. HEART, ONCOLOGY, placeholders such as "Hosp 46") do not
  form a verified ward mapping, so conditions are not presented as departments.
- **Not modelled:** wards, departments, ICU, staffing, triage, transfers, diversion, or deaths as separate events.
  One return stay at most per initial stay.
- **Interpretation:** hypothetical sensitivities for planning discussions, not forecasts for a specific hospital and
  not clinical advice. The model has internal numerical checks but no external validation.
""")
    docs = [(p, HERE / p) for p in ("README.md", "AUDIT_REPORT.md", "REDESIGN_NOTES.md")]
    docs = [(n, p) for n, p in docs if p.exists()]
    if not docs:
        st.info("No documentation files were found next to app.py.")
        return
    tabs = st.tabs([n for n, _ in docs])
    for tab, (n, p) in zip(tabs, docs):
        with tab:
            st.markdown(p.read_text(encoding="utf-8"))


# =========================================================================== router
render_nav()
{"welcome": page_welcome, "overview": page_overview, "simulator": page_simulator, "results": page_results,
 "export": page_export, "downloads": page_export, "docs": page_docs}.get(ss.page, page_welcome)()
if ss.page not in ("welcome", "overview", "simulator"):
    render_footer()
