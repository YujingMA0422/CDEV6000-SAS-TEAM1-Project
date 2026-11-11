"""Hospital Capacity Planner - manager-facing Streamlit front end (v3.1).

Run:   python -m streamlit run app.py
Needs: simulation.py and calibration.npz in the same folder, plus the frontend helpers
       historical_summary.py, results_helpers.py and ui_components.py.

The discrete-event simulation (simulation.py) is used unchanged. This file arranges inputs, calls the
existing model functions and presents their outputs. Research prototype - not a clinical or forecasting tool.
"""
import inspect
import copy
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
                   adm_series="New admissions", adm_view="Weekly", res_tab="overview", trend_view="Beds")
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
        ss.page_changed = True               # a new page opens at its top unless an anchor is requested
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


def local_now():
    """Current time in the viewer's time zone (from the browser, Streamlit >= 1.42), else Sydney time.
    A hosted server usually runs on UTC, so datetime.now() alone would show the server's clock."""
    from zoneinfo import ZoneInfo
    for tz in (getattr(getattr(st, "context", None), "timezone", None), "Australia/Sydney"):
        try:
            if tz:
                return datetime.now(ZoneInfo(tz))
        except Exception:
            continue
    return datetime.now().astimezone()


def do_run():
    settings, ref = current_settings()
    if run_problem(settings):
        return
    t = tuple(settings[n] for n in NAMES)
    with st.spinner(f"Running the simulation ({settings['duration']} days × {settings['reps']} runs for your scenario "
                    "and its comparisons). This usually takes under a minute..."):
        res = run_all(*t)
    done = local_now()                              # timezone-aware completion time of this run
    ss.ui["res_tab"], ss.ui["trend_view"] = "overview", "Beds"
    ss.pop("w_ui_trend_view", None)
    ss.result = dict(settings=settings, key=t, res=res, bed_mode=ss.cfg["bed_mode"], reference=ref,
                     finished_at=done, finished=done.strftime("%d %b %Y, %H:%M %Z").strip())
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
            # compact alternative to the page links on narrow windows (shown by CSS below 1100px)
            with st.popover("Menu", icon=":material/menu:", help="Go to a page", key="nav_menu"):
                for key, label in NAV_ITEMS:
                    st.button(label, key=f"navm_{key}", type="primary" if ss.page == key else "tertiary",
                              on_click=go_to, args=(key,), width="stretch")
            with st.popover("", icon=":material/help:", help="Help and about", key="nav_help"):
                render_help()


NAV_SCRIPT = """<script>
(function(){
  const P = window.parent, D = P.document;
  if (P.__hcpNav) return; P.__hcpNav = true;
  // one listener in the parent page: compact header after scrolling, full header near the top (with hysteresis)
  const s = D.createElement('script');
  s.textContent = "(function(){var b=document.body,c=false;function top(t){return (t&&t.scrollTop!==undefined&&t!==document)?t.scrollTop:(document.scrollingElement||document.documentElement).scrollTop;}" +
    "function on(e){var t=e&&e.target;if(t&&t!==document&&!(t.contains&&t.contains(document.querySelector('.block-container'))))return;var y=top(t);if(!c&&y>48){c=true;b.setAttribute('data-hcp-nav','compact');}else if(c&&y<12){c=false;b.removeAttribute('data-hcp-nav');}}" +
    "document.addEventListener('scroll',on,{capture:true,passive:true});})();";
  D.body.appendChild(s);
})();
</script>"""


def nav_behaviour():
    """Installs the compact-on-scroll header once per browser tab (no reruns, no Python state)."""
    import streamlit.components.v1 as components
    components.html(NAV_SCRIPT, height=0)


def render_footer():
    c1, c2 = st.columns([5, 1.2], vertical_alignment="center")
    c1.markdown('<div class="footer">Research prototype for exploring hypothetical scenarios — not a clinical tool or a '
                f'forecast of bed requirements. Historical data {H.PERIOD_LABEL}.</div>', unsafe_allow_html=True)



# =========================================================================== PAGE 1: WELCOME
WELCOME_QUESTIONS = [
    # key, label, question, (what you can test, what the results show, decisions it can inform), action, anchor
    ("demand", "Rising Demand", "Can the hospital cope with more admissions?",
     ("Test how higher or lower admissions affect your hospital's available beds.",
      "How full beds become, how many beds a busy day would need, and how often and how long patients wait.",
      "Whether current capacity can absorb expected growth, or when extra beds or flow improvements are needed."),
     "Set Admission Demand", "step-2"),
    ("beds", "Bed Capacity", "How would changing the number of available beds affect pressure and waiting?",
     ("More or fewer available beds than the default for the same admission demand.",
      "Occupancy, how many days end with patients waiting, and how large queues become.",
      "Whether your hospital has enough beds, and how much extra capacity may be needed during busy periods."),
     "Set Available Beds", "step-3"),
    ("flow", "Patient Flow", "Could shorter stays or fewer readmissions help?",
     ("Shorter initial stays and fewer readmissions for one chosen patient group.",
      "Bed-days freed, return stays avoided and whether waiting changes.",
      "Which patient groups may benefit most from targeted improvements, and how these changes could ease bed pressure."),
     "Test Patient-Flow Improvements", "step-4"),
]


def open_step(anchor):
    """Open Build a Scenario at one step. Nothing in the scenario changes."""
    ss.scroll_to = anchor
    go_to("simulator")


def scroll_to_anchor(target):
    """Bring an anchor into view below the fixed header, reliably on the first click.

    Lands instantly, then re-checks for ~1.5 s while charts and widgets finish laying out (a smooth scroll started
    before the page has settled stops short). Stops as soon as the person scrolls, clicks or types. The anchor gets
    keyboard focus without a second jump. A nonce makes every request a fresh frame, so asking for the same step twice
    in a row still works."""
    import json
    import time
    import streamlit.components.v1 as components
    ss.anchored = True
    components.html(
        "<script>(function(){const D=window.parent.document,t=" + json.dumps(target) + ";let n=0,k=0,stop=false;"
        "const halt=()=>{stop=true;};['wheel','touchstart','keydown','mousedown'].forEach(e=>D.addEventListener(e,halt,{once:true,capture:true}));"
        "function go(){if(stop)return;const el=D.getElementById(t);if(!el){if(n++<80)setTimeout(go,100);return;}"
        "const y=el.getBoundingClientRect().top,want=parseFloat(getComputedStyle(el).scrollMarginTop)||0;"
        "if(k===0||Math.abs(y-want)>6){el.scrollIntoView({behavior:'instant',block:'start'});}"
        "if(k===0){if(!el.hasAttribute('tabindex'))el.setAttribute('tabindex','-1');try{el.focus({preventScroll:true});}catch(e){}}"
        "if(k++<6)setTimeout(go,250);}"
        "setTimeout(go,60);})();</script>"   # setTimeout, not requestAnimationFrame: rAF is paused in hidden frames
        f"<!-- {time.time_ns()} -->", height=0)


def welcome_picker():
    """"What would you like to explore?": three planning questions, chosen with plain HTML radio inputs.

    No input carries a `checked` attribute: Streamlit renders markdown through React, which turns `checked` into a
    controlled prop and restores it after every click (the cause of the earlier "first click selects the first
    option" bug). With uncontrolled inputs the browser owns the selection, so switching never reruns the app and
    never touches the scenario; CSS shows the first question while nothing has been chosen yet."""
    opts = "".join(
        f'<label class="wqo wqo-{k}" for="wq-{k}"><input type="radio" name="wq" id="wq-{k}" value="{k}">'
        f'<span class="wqi">{UI.WL_ICONS[k]}</span><span class="wqt"><b>{lab}</b><span>{UI.esc(q)}</span></span></label>'
        for k, lab, q, *_rest in WELCOME_QUESTIONS)
    panels = ""
    for k, lab, q, (test, see, decide), *_rest in WELCOME_QUESTIONS:
        rows = "".join(f'<div><dt>{t}</dt><dd>{UI.esc(x)}</dd></div>' for t, x in (
            ("What you can test", test), ("What the results show", see), ("Decisions it can inform", decide)))
        panels += (f'<div class="wqp wqp-{k}"><div class="wqp-top"><div><div class="wqp-k">{lab}'
                   f'{"<span class=wl-opt>Optional step</span>" if k == "flow" else ""}</div>'
                   f'<div class="wqp-q">{UI.esc(q)}</div></div>{UI.wl_preview(k)}</div><dl class="wqd">{rows}</dl></div>')
    with st.container(key="wl_pick"):
        UI.md('<h2 class="wl-h2">What Would You Like to Explore?</h2>'
              '<p class="wl-sub">Choose a planning question to see what you can test and what it can help you decide.</p>')
        c1, c2 = st.columns([0.9, 1.55], gap="medium")
        with c1:
            UI.md(f'<fieldset class="wqopts"><legend class="sr">Planning question</legend>{opts}</fieldset>')
        with c2:
            UI.md(f'<div class="wqps">{panels}</div>')
            with st.container(key="wl_go"):
                for k, *_rest, action, anchor in WELCOME_QUESTIONS:
                    st.button(action, key=f"wlgo_{k}", type="primary", icon=":material/arrow_forward:",
                              icon_position="right", on_click=open_step, args=(anchor,))


def welcome_workflow():
    """"One Connected Workflow": the three stages (the same wording as our presentation) and the loop back from
    Evaluate to Simulate. Text and connectors only, so the Welcome page stays short."""
    stages = [("01", "Understand", "What is happening?", "Explore historical demand, patterns and resource use.",
               "Historical Overview"),
              ("02", "Simulate", "What if things change?", "Test changes in demand, beds and patient flow.",
               "Build a Scenario"),
              ("03", "Evaluate", "What does it mean?",
               "Understand the results, their planning implications, and what to test next.", "Results")]
    cols = "".join(
        f'<li class="wfs"><div class="wfn"><span>{n}</span><b>{name}</b></div><h3>{UI.esc(q)}</h3>'
        f'<p>{UI.esc(d)}</p><em>{page}</em></li>' for n, name, q, d, page in stages)
    UI.md('<section class="wf"><h2 class="wl-h2">One Connected Workflow</h2>'
          '<p class="wl-sub">Understand hospital demand, test possible changes, and use the results to guide your next '
          'decision — all in one place.</p>'
          f'<ol class="wfstages3">{cols}</ol>'
          '<div class="wfback" aria-label="After evaluating, refine and test again in Simulate">'
          '<span class="wfarc" aria-hidden="true"></span>'
          '<p><b>↺ Refine and test again</b> Compare saved scenarios after testing multiple options.</p></div></section>')


def page_welcome():
    """Product value → connected workflow → planning questions → how the simulation works (kept short)."""
    UI.md(UI.WELCOME_CSS)
    with st.container(key="wl_hero"):
        c1, c2 = st.columns([1, 1.05], gap="large", vertical_alignment="center")
        with c1:
            UI.md('<h1 class="wl-h1">See the Impact<br>Before You Act</h1>'
                  '<p class="wl-lead">Turn hospital data into planning insights, test what-if scenarios, and make more '
                  'informed decisions.</p>')
            with st.container(key="wl_cta", horizontal=True):
                st.button("Build a Scenario", key="wl_build", type="primary", icon=":material/arrow_forward:",
                          icon_position="right", on_click=go_to, args=("simulator",))
                st.button("Explore Historical Data", key="wl_explore", type="tertiary", on_click=go_to,
                          args=("overview",))
        with c2:
            UI.md(UI.flow_art())

    welcome_workflow()
    welcome_picker()

    with st.container(key="wl_des"):
        a, b = st.columns([1, 1.45], gap="large", vertical_alignment="center")
        with a:
            UI.md('<div class="wl-des"><h2 class="wl-h2">How Does the Simulation Work?</h2>'
                  '<p>The planner uses Discrete-Event Simulation (DES) to model how patients arrive, occupy beds, wait '
                  'when capacity is full, and may return after discharge. This allows different planning scenarios to '
                  'be explored before making real-world changes.</p></div>')
        with b:
            UI.md(UI.mechanism())


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
SECTIONS = [("hospital-overview", "Hospital at a Glance"), ("admission-patterns", "Admission Patterns"),
            ("explore-patient-groups", "Explore Patient Groups")]
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
          '<p>Explore hospital activity, understand when demand is highest, and discover high-demand patient groups.</p>'
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

    # ================================================================ 02 How Does Admission Demand Change?
    UI.qhead(2, "How Does Admission Demand Change?", anchor="admission-patterns")
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

    # ================================================================ 03 Explore Patient Groups
    UI.qhead(3, "Explore Patient Groups", anchor="explore-patient-groups")
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



SVG_ICONS = {
    "bed": '<path d="M3 7v12M3 15h18v4M3 12h18v3"/><rect x="6" y="9" width="4" height="3" rx="1"/>',
    "schedule": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
    "check_circle": '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.2l2.4 2.4 4.7-5"/>',
    "warning": '<path d="M12 4l9 15.5H3z"/><path d="M12 10v4.5M12 17h.01"/>',
    "radio_button_partial": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17"/>',
    "trending_down": '<path d="M3 7l6 6 4-4 8 8"/><path d="M15 17h6v-6"/>',
    "trending_up": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "sync_alt": '<path d="M5 9h13l-3-3M19 15H6l3 3"/>',
    "lightbulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z"/>',
}


def ic(name):
    """Small inline line icon (no icon font needed)."""
    return (f'<span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{SVG_ICONS.get(name, SVG_ICONS["info"])}</svg></span>')


RUN_LABELS = {"Reference": "Baseline Scenario", "Scenario": "Your Scenario",
              "Conditions only": "Same demand and beds, without improvements",
              "Baseline": "No changes, same beds as your scenario", "Demand only": "Admission change only",
              "LOS only": "Shorter stays only", "Readmissions only": "Fewer readmissions only"}
FULL_OCC = 98.5          # % average occupancy treated as "at capacity" in the wording
TAIL_DAYS = 140          # simulation follow-up after the period (simulation.TAIL_DAYS)


# ---------------------------------------------------------------- formatting
def fmt_generated(result):
    """'9 Nov 2026, 5:54 pm AEDT' from the timezone-aware completion time stored with the run."""
    dt = result.get("finished_at")
    if dt is None:
        return result.get("finished", "")
    return f"{dt.day} {dt:%b %Y}, {dt.hour % 12 or 12}:{dt:%M} {'am' if dt.hour < 12 else 'pm'} {dt:%Z}".strip()


def fmt_wait(v):
    """Days, never showing a small non-zero average as '0 days' (the model counts whole days per request)."""
    if v is None or not RH.finite(v):
        return "Not estimable"
    if v == 0:
        return "0 days"
    if v < 0.01:
        return "under 0.01 days"
    return f"{v:.2f} days" if v < 10 else f"{v:.1f} days"


def fmt_pct(v):
    """Percent with enough precision that two different small values never both read '<1%'."""
    if v is None or not RH.finite(v):
        return "Not estimable"
    if v == 0:
        return "0%"
    if v < 0.1:
        return "<0.1%"
    return f"{v:.1f}%" if v < 10 else f"{v:.0f}%"


def _pattern_phrase(s):
    return ("the typical-week admission pattern" if s["season"] == "Annual average"
            else f"the historical admission pattern starting in {H.MONTH_FULL[s['season']]}")


def _group_phrase(s):
    return (f"{cond_label(s['diagnosis'])} Severity {s['severity']}"
            + ("" if s["age"] == "All ages" else f" ({AGE_PICK[s['age']]})"))


def _patients(s):
    """'Heart Failure Severity 3 patients aged 65+' (the targeted population, in plain words)."""
    return (f"{cond_label(s['diagnosis'])} Severity {s['severity']} patients"
            + ("" if s["age"] == "All ages" else f" {AGE_PHRASE[s['age']]}"))


def _imp_list(s, initial=True):
    return " and ".join(x for x in (f"{s['reduction']}% shorter {'initial ' if initial else ''}stays"
                                    if s["reduction"] else "",
                                    f"{s['readmit']}% fewer readmissions" if s["readmit"] else "") if x)


def scenario_question(s):
    """Short question the run answers; the detailed settings are shown right below it."""
    case = RH.scenario_case(s)
    beds = "its default beds" if s["beds"] == s["ref_beds"] else f"{s['beds']:,} beds"
    dem = ("historical admission demand" if not s["demand"] else
           f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'fewer'} admissions")
    what = " and ".join(x for x in ("shorter stays" if s["reduction"] else "",
                                    "fewer readmissions" if s["readmit"] else "") if x)
    who = (f"{cond_label(s['diagnosis'])} Severity {s['severity']} patients"
           + ("" if s["age"] == "All ages" else f" {AGE_PHRASE[s['age']]}"))
    if case == "none":
        return f"How does the hospital manage historical admission demand with {beds}?"
    if case == "conditions":
        return f"Could the hospital manage {dem} with {beds}?"
    if case == "improve":
        return f"Could {what} for {who} reduce bed pressure?"
    return f"Could the hospital manage {dem} with {beds}, and would {what} for {who} help?"


def scenario_settings_rows(s):
    """Compact settings overview shown under the question (only relevant rows; no bare 'No change')."""
    rows = [("Planning period", f"{s['duration']} days · " + ("typical-week pattern" if s["season"] == "Annual average"
                                                              else f"historical pattern from {H.MONTH_FULL[s['season']]}")),
            ("Expected admissions", "Historical level (0% change)" if not s["demand"] else
             f"{abs(s['demand'])}% {'above' if s['demand'] > 0 else 'below'} the historical level"),
            ("Available beds", f"{s['beds']:,} (default)" if s["beds"] == s["ref_beds"]
             else f"{s['beds']:,} (default {s['ref_beds']:,})")]
    if s["reduction"] or s["readmit"]:
        rows.append(("Target patient group", f"{cond_label(s['diagnosis'])} · Severity {s['severity']} · "
                                             f"{AGE_PICK[s['age']]}"))
        rows.append(("Shorter initial stays", f"{s['reduction']}% for eligible initial stays in this group"
                     if s["reduction"] else "None (0%)"))
        rows.append(("Readmission reduction", f"{s['readmit']}% lower readmission rate in this group"
                     if s["readmit"] else "None (0%)"))
    return rows


def baseline_text(s):
    """The baseline actually run (results_helpers.build_runs 'Reference'): no changes, default beds, same period,
    pattern, duration and random seeds."""
    return (f"Baseline: the same {s['duration']}-day period and {_pattern_phrase(s)}, with historical admission "
            f"levels, the default {s['ref_beds']:,} beds and no patient-flow improvements.")


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


def waited_delay(res, name):
    """Average wait among requests that waited (ratio of run means: mean wait / share waiting), in days."""
    mw, w = run_mean(res, name, "mean_wait_days"), run_mean(res, name, "waited_pct")
    return None if mw is None or not w else mw / (w / 100)


def full_day_share(res, name, beds):
    """Share of days on which beds were full in every run (replication-averaged occupancy at the limit)."""
    dl = res["daily"][res["daily"].scenario == name]
    return float((dl.occupied >= beds - 0.5).mean()) if len(dl) else 0.0


def waits_ok(res, *names):
    return all((run_mean(res, n, "unresolved_requests") or 0) == 0 for n in names)


# ---------------------------------------------------------------- plain-language change statements
UNCLEAR_TIP = "The simulations did not show a consistent enough change to draw a clear conclusion."


def change_text(p, kind, better=None, noun=""):
    """(text, css class). kind: 'pp' percentage points, 'days', 'beds', 'count', 'bed-days'.
    Colour only when the paired difference is clear and the metric has a favourable direction."""
    if p is None:
        return "Not estimable", "flat"
    if not p["clear"]:
        return "No clear difference between the two scenarios", "flat"
    d, up = abs(p["diff"]), p["diff"] > 0
    if kind == "pp":
        if d < 0.05:
            return "No clear difference between the two scenarios", "flat"
        txt = f"{d:.1f} point{'s' if round(d, 1) != 1 else ''} {'higher' if up else 'lower'}"
    elif kind == "days":
        if d < 0.005:
            return "No clear difference between the two scenarios", "flat"
        txt = f"{d:.2f} days {'longer' if up else 'shorter'}"
    elif kind == "beds":
        if round(d) == 0:
            return "No clear difference between the two scenarios", "flat"
        txt = f"{d:,.0f} {'more' if up else 'fewer'} beds"
    else:
        if round(d) == 0:
            return "No clear difference between the two scenarios", "flat"
        txt = f"{d:,.0f} {'more' if up else 'fewer'} {noun or kind}"
    # Consistent but negligible changes are not highlighted as improvements or deteriorations.
    base = abs(p.get("a") or 0)
    tiny = {"pp": 0.5, "days": 0.05}.get(kind, max(1.0, 0.01 * base))
    if d < tiny:
        return f"Slightly {txt.split()[-1]} ({txt.rsplit(' ', 1)[0]})", "flat"
    cls = "neutral" if better is None else ("good" if up == (better == "up") else "bad")
    return txt, cls


def chg(p, kind, better=None, noun=""):
    t, c = change_text(p, kind, better, noun)
    tip = (f' title="{UNCLEAR_TIP}"' if t.startswith("No clear") else
           ' title="Percentage points: the difference between the two percentages"' if kind == "pp" else "")
    return f'<span class="chg2 {c}"{tip}>{t}</span>'


def compare_line(a, b, show_base=True):
    """'Baseline 95% → Your Scenario 93%' (stacks on narrow screens)."""
    if not show_base:
        return f'<div class="cmpv"><span class="ls">Your Scenario</span><b class="sv">{b}</b></div>'
    return (f'<div class="cmpv"><span class="lb">Baseline</span><b>{a}</b><span class="ar" aria-hidden="true">→</span>'
            f'<span class="ls">Your Scenario</span><b class="sv">{b}</b></div>')


# ---------------------------------------------------------------- capacity state and findings
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


def capacity_answer(s, res):
    """(icon, finding, evidence [(value, label)], context) for 'Could the Hospital Manage This Demand?'.
    Evidence: average occupancy, share of bed requests that waited, average wait across ALL bed requests."""
    st_ = _state(s, res, "Scenario", s["beds"])
    occ = run_mean(res, "Scenario", "occupancy_pct")
    full = full_day_share(res, "Scenario", s["beds"])
    nb = float(np.mean(res["nb_vals"]["Scenario"]))
    waited = run_mean(res, "Scenario", "waited_pct")
    mw = run_mean(res, "Scenario", "mean_wait_days")
    ev = [(f"{occ:.0f}%", "average bed occupancy")]
    if st_ == "overloaded":
        us = run_mean(res, "Scenario", "unresolved_requests")
        ev += [(f"{full * 100:.0f}%", "of days with every bed full"),
               (f"{us:,.0f}", f"requests still waiting {TAIL_DAYS} days after the period")]
        return ("warn", "Hospital capacity was insufficient: demand exceeded the available beds and some patients "
                        "were still waiting long after the period ended.", ev, "")
    ev += [(fmt_pct(waited), "of bed requests waited at least one day"),
           (fmt_wait(mw), "average wait across all bed requests")]
    if st_ == "full":
        when = "throughout the period" if full >= 0.999 else ("for most of the period" if full >= 0.5 else "on average")
        head = ("Hospital capacity was insufficient to meet demand without substantial waiting." if waited >= 20 else
                f"Beds were full {when}, and some patients had to wait for a bed.")
        return ("warn", head, ev, f"Every bed was in use on {full * 100:.0f}% of days.")
    if st_ == "busy":
        return ("warn", "Capacity was tight: the hospital managed most of the demand, but a noticeable share of "
                        "patients waited for a bed.", ev, "")
    if nb > s["beds"]:
        return ("mixed", "The hospital mostly managed the demand, with little room to spare on busy days.", ev,
                f"Estimated busy-day demand ({nb:,.0f} beds) was above the {s['beds']:,} available, so short peaks "
                "may still cause waits.")
    return ("ok", "The hospital generally managed the simulated demand.", ev, "")


def baseline_change_sentence(s, res):
    """How the scenario's waiting differed from the baseline (demand/bed changes), or None."""
    if RH.scenario_case(s) not in ("conditions", "combined"):
        return None
    what = _cond_phrase(s)
    if not waits_ok(res, "Reference", "Scenario"):
        if not waits_ok(res, "Scenario") and waits_ok(res, "Reference"):
            return f"With {what}, the beds could no longer keep up, unlike in the baseline."
        return f"With {what}, waiting could not be fully estimated in at least one of the two scenarios."
    metric, w = wait_compare(res, "Reference", "Scenario")
    ref_state, st_ = _state(s, res, "Reference", s["ref_beds"]), _state(s, res, "Scenario", s["beds"])
    if not w["clear"] or abs(w["diff"]) < (0.05 if metric == "waited_pct" else 0.005):
        return (f"With {what}, waiting stayed low, as in the baseline." if ref_state == st_ == "ok"
                else f"With {what}, there was no clear difference in waiting compared with the baseline.")
    if metric == "mean_wait_days":
        return (f"Almost every request waited in both scenarios; with {what}, the average wait "
                f"{'rose' if w['diff'] > 0 else 'fell'} from {fmt_wait(w['a'])} in the baseline to {fmt_wait(w['b'])}.")
    return (f"With {what}, the share of bed requests that waited {'rose' if w['diff'] > 0 else 'fell'} from "
            f"{fmt_pct(w['a'])} in the baseline to {fmt_pct(w['b'])}.")


def wait_compare(res, a, b):
    """Which waiting measure shows the difference: share that waited, or, when nearly every request waited in both
    runs (the share is saturated near 100%), the average wait in days."""
    wp = pair(res, a, b, "waited_pct")
    if wp["a"] >= 95 and wp["b"] >= 95:
        return "mean_wait_days", pair(res, a, b, "mean_wait_days")
    return "waited_pct", wp


def _cond_phrase(s):
    bits = []
    if s["demand"]:
        bits.append(f"{abs(s['demand'])}% {'more' if s['demand'] > 0 else 'fewer'} admissions")
    if s["beds"] != s["ref_beds"]:
        bits.append(f"{'fewer' if s['beds'] < s['ref_beds'] else 'more'} beds ({s['beds']:,})")
    return " and ".join(bits)


def improvement_headline(s, res):
    """One-line answer to 'How much did the targeted patient-flow changes help?' (matching runs only)."""
    comp = RH.improvement_comparator(s)
    bd = pair_unlimited(res, comp, "Scenario", "bd")
    rt = pair(res, comp, "Scenario", "returns") if s["readmit"] else None
    metric, w = wait_compare(res, comp, "Scenario") if waits_ok(res, comp, "Scenario") else (None, None)
    gains = []
    if rt and rt["clear"] and rt["diff"] < -0.5:
        gains.append(f"about {-rt['diff']:,.0f} fewer readmissions")
    if bd and bd["clear"] and bd["diff"] < -0.5:
        gains.append(f"about {-bd['diff']:,.0f} fewer bed-days of demand over {s['duration']} days")
    if not gains:
        return "The improvements made no clear difference in this simulation."
    txt = "The improvements led to " + " and ".join(gains)
    if w is None:
        return txt + "."
    if metric == "mean_wait_days" and w["clear"] and w["diff"] < -0.005:
        return txt + f", and the average wait fell from {fmt_wait(w['a'])} to {fmt_wait(w['b'])}."
    if metric == "waited_pct" and w["clear"] and w["diff"] < -0.05:
        return txt + f", and the share of requests that waited fell by {-w['diff']:.1f} percentage points."
    if _state(s, res, comp, s["beds"]) == "ok":
        return txt + "; waiting was already low."
    return txt + ", but waiting did not clearly change."


def decision_insights(s, res):
    """(key, finding, why it matters, scenario to test, action) — action = (label, cfg update, flow flag) or a tab."""
    out = []
    st_ = _state(s, res, "Scenario", s["beds"])
    nb = float(np.mean(res["nb_vals"]["Scenario"]))
    more = int(round(s["beds"] * 1.10 / 10) * 10)
    if st_ in ("overloaded", "full", "busy"):
        out.append(("beds", "Busy-day demand is above the available beds." if nb > s["beds"] else
                    "Short peaks in admissions fill every bed.",
                    "Patients wait when demand peaks, and waiting can carry over into the following days.",
                    "More available beds", (f"Test More Available Beds ({more:,})",
                                            dict(bed_mode="custom", custom_beds=more), None)))
    elif nb >= 0.95 * s["beds"]:
        nd = min(s["demand"] + 10, PCT_CHOICES["demand"]["hi"])
        out.append(("demand", "There is limited room for higher demand.",
                    f"Busy-day demand ({nb:,.0f} beds) is close to the {s['beds']:,} available, so a rise in "
                    "admissions could quickly lead to waiting.",
                    "Higher admission demand", (f"Test Higher Admission Demand ({nd:+d}%)", dict(demand=nd), None)))
    else:
        nd = min(s["demand"] + 10, PCT_CHOICES["demand"]["hi"])
        out.append(("ok", "There was spare capacity on busy days.",
                    f"Busy-day demand ({nb:,.0f} beds) stayed below the {s['beds']:,} available beds.",
                    "Higher demand or fewer beds", (f"Test Higher Admission Demand ({nd:+d}%)", dict(demand=nd), None)))
    case = RH.scenario_case(s)
    if case in ("conditions", "combined") and waits_ok(res, "Reference", "Scenario"):
        metric, w = wait_compare(res, "Reference", "Scenario")
        if w["clear"] and abs(w["diff"]) >= (0.5 if metric == "waited_pct" else 0.05):
            worse = w["diff"] > 0
            what = _cond_phrase(s)
            out.append(("wait", f"{what[0].upper() + what[1:]} {'increased' if worse else 'reduced'} waiting.",
                        (f"The share of bed requests that waited went from {fmt_pct(w['a'])} in the baseline to "
                         f"{fmt_pct(w['b'])}." if metric == "waited_pct" else
                         f"The average wait went from {fmt_wait(w['a'])} in the baseline to {fmt_wait(w['b'])}."),
                        "Compare it with another plan", ("Compare Another Plan", "compare", None)))
    if s["reduction"] or s["readmit"]:
        comp = RH.improvement_comparator(s)
        bd = pair_unlimited(res, comp, "Scenario", "bd")
        nr = min(s["reduction"] + 5, PCT_CHOICES["reduction"]["hi"]) if s["reduction"] else 10
        if bd and bd["clear"] and bd["diff"] < -0.5:
            meaning = ("Beds stayed full, so the freed beds went to waiting patients: the benefit shows as shorter "
                       "waits rather than empty beds." if st_ in ("full", "overloaded") else
                       "That frees capacity that other admissions could use.")
            out.append(("flow", f"The patient-flow changes lowered bed demand by about "
                                f"{-bd['diff'] / s['duration']:,.0f} beds on an average day.", meaning,
                        "A different improvement level (hypothetical)",
                        (f"Test a Larger Stay Reduction ({nr}%)", dict(reduction=nr), True)))
        else:
            share = H.page_measures(s["diagnosis"], s["severity"], s["age"])["share_total"]
            out.append(("flow", "The patient-flow changes had little measurable effect.",
                        f"This group accounts for about {share:.0f}% of historical bed-days, so changes to it alone "
                        "have a limited hospital-wide effect.", "Another patient group or a larger change",
                        ("Explore Patient Groups", "groups", None)))
    return out[:3]


# ---------------------------------------------------------------- KPI groups
ICON = {"ok": "check_circle", "warn": "warning", "mixed": "radio_button_partial"}


# ---------------------------------------------------------------- 03 improvements
def flow_table(s, res):
    comp = RH.improvement_comparator(s)
    rows = []

    def row(label, p, kind, better, fa, noun=""):
        if p is None:
            rows.append(f'<div class="ir"><span>{label}</span><b>Not estimable</b><b>Not estimable</b>'
                        f'{chg(None, kind)}</div>')
        else:
            rows.append(f'<div class="ir"><span>{label}</span><b>{fa(p["a"])}</b><b>{fa(p["b"])}</b>'
                        f'{chg(p, kind, better, noun)}</div>')
    if s["reduction"]:
        row(f"Average initial stay, {_group_phrase(s)} patients", pair(res, comp, "Scenario", "target_mean_los"),
            "days", "down", lambda v: f"{v:.2f} days")
    if s["readmit"]:
        row("Readmissions scheduled (all patients)", pair(res, comp, "Scenario", "returns"), "count", "down",
            lambda v: f"{v:,.0f}", "readmissions")
    row("Bed-day demand (before the bed limit)", pair_unlimited(res, comp, "Scenario", "bd"), "bed-days", "down",
        lambda v: f"{v:,.0f}")
    ok = waits_ok(res, comp, "Scenario")
    metric, wp = wait_compare(res, comp, "Scenario") if ok else ("waited_pct", None)
    if metric == "mean_wait_days":                   # nearly everyone waited in both runs: the average wait shows it
        row("Average wait for a bed (all requests)", wp, "days", "down", fmt_wait)
    else:
        row("Bed requests that waited", wp, "pp", "down", fmt_pct)
    if len(rows) < 4:
        row("Estimated beds needed on busy days", pair_unlimited(res, comp, "Scenario", "nb"), "beds", "down",
            lambda v: f"{v:,.0f}")
    left = "Without improvements" if RH.scenario_case(s) == "combined" else "Baseline Scenario"
    return (f'<div class="itab"><div class="ir ih"><span></span><b>{left}</b><b>With improvements</b>'
            '<em>Difference</em></div>' + "".join(rows) + "</div>")


# ---------------------------------------------------------------- saved options
def save_current():
    """Store this run's exact settings, outputs and timestamp under a stable id (never modified by later edits;
    the same completed run is never saved twice)."""
    if ss.result is None or any(x["key"] == ss.result["key"] for x in ss.saved):
        return
    st_s, res = copy.deepcopy(ss.result["settings"]), ss.result["res"]
    R = results_view(ss.result)
    rec = RH.compare_record(R, st_s, ss.result["bed_mode"])
    ok = waits_ok(res, "Scenario")
    ss.saved_seq += 1
    rec.update(id=ss.saved_seq, key=ss.result["key"], settings=st_s, generated=fmt_generated(ss.result),
               finished_at=ss.result.get("finished_at"), question=scenario_question(st_s),
               baseline=baseline_text(st_s), state=_state(st_s, res, "Scenario", st_s["beds"]),
               occ=run_mean(res, "Scenario", "occupancy_pct"),
               wait=run_mean(res, "Scenario", "mean_wait_days") if ok else None,
               waited=run_mean(res, "Scenario", "waited_pct") if ok else None,
               queue=run_mean(res, "Scenario", "peak_queue"),
               nb=float(np.mean(res["nb_vals"]["Scenario"])),
               bd_day=float(np.mean(res["bd_demand"]["Scenario"])) / st_s["duration"],
               returns_day=run_mean(res, "Scenario", "returns") / st_s["duration"],
               target_los=run_mean(res, "Scenario", "target_mean_los") if st_s["reduction"] else None)
    ss.saved = (ss.saved + [rec])[-MAX_SAVED:]


STATE_LABEL = {"ok": ("Managed demand", "good"), "busy": ("Some waiting", "warn"), "full": ("At capacity", "bad"),
               "overloaded": ("Demand exceeded beds", "bad")}


def _opt_settings(r):
    s = r["settings"]
    return [("Planning period", f"{s['duration']} days · " + ("typical week" if s["season"] == "Annual average"
                                                              else f"from {H.MONTH_FULL[s['season']]}")),
            ("Admission demand", "Historical (0%)" if not s["demand"] else f"{s['demand']:+d}%"),
            ("Available beds", f"{s['beds']:,}"),
            ("Targeted improvements", (f"{_group_phrase(s)}: {_imp_list(s, initial=False)}"
                                       if (s["reduction"] or s["readmit"]) else "None"))]


def comparison_matrix(recs):
    """Saved options side by side, settings first; differences against Option A only when they are not trivial."""
    base = recs[0]

    def diff(r, key, kind, better, noun=""):
        if r is base or r.get(key) is None or base.get(key) is None:
            return ""
        d = r[key] - base[key]
        small = abs(d) < (0.5 if kind == "pp" else 0.05 if kind == "days" else max(1.0, 0.01 * abs(base[key])))
        if small:
            return f'<div class="mdiff">About the same as {base["title"]}</div>'
        t, c = change_text(dict(a=base[key], b=r[key], diff=d, half=0.0, clear=True), kind, better, noun)
        return f'<div class="mdiff {c}">{t} than {base["title"]}</div>'

    head = "".join(f'<th scope="col"><div class="mo">{UI.esc(r["title"])}</div><div class="mq">{UI.esc(r["question"])}</div>'
                   f'<div class="mt">{UI.esc(r.get("generated", ""))}</div></th>' for r in recs)
    rows = ['<tr class="grp"><th colspan="99">Scenario Settings</th></tr>']
    for i, (label, _) in enumerate(_opt_settings(base)):
        vals = [_opt_settings(r)[i][1] for r in recs]
        same = len(set(vals)) == 1
        rows.append(f'<tr{" class=same" if same else ""}><th scope="row">{label}</th>'
                    + "".join(f"<td>{UI.esc(v)}</td>" for v in vals) + "</tr>")
    rows.append('<tr class="grp"><th colspan="99">Capacity Outcomes</th></tr>')
    lab = lambda r: '<span class="st {1}">{0}</span>'.format(*STATE_LABEL.get(r["state"], ("", "")))
    rows.append('<tr><th scope="row">Overall</th>' + "".join(f"<td>{lab(r)}</td>" for r in recs) + "</tr>")
    for label, key, fmt, kind, better, noun in (
            ("Average occupancy", "occ", lambda v: f"{v:.0f}%", "pp", None, ""),
            ("Estimated beds needed on busy days", "nb", lambda v: f"{v:,.0f}", "beds", "down", ""),
            ("Bed requests that waited", "waited", fmt_pct, "pp", "down", ""),
            ("Average wait (all requests)", "wait", fmt_wait, "days", "down", ""),
            ("Largest daily queue", "queue", lambda v: f"{v:,.0f}", "count", "down", "requests waiting")):
        rows.append(f'<tr><th scope="row">{label}</th>' + "".join(
            f'<td><b>{"Not estimable" if r.get(key) is None else fmt(r[key])}</b>{diff(r, key, kind, better, noun)}</td>'
            for r in recs) + "</tr>")
    rows.append('<tr class="grp"><th colspan="99">Improvement Outcomes</th></tr>')
    rows.append('<tr><th scope="row">Average bed demand per day (before the bed limit)</th>' + "".join(
        f'<td><b>{r["bd_day"]:,.0f}</b>{diff(r, "bd_day", "beds", "down")}</td>' for r in recs) + "</tr>")
    if any(r["settings"]["readmit"] for r in recs) and all("returns_day" in r for r in recs):
        rows.append('<tr><th scope="row">Readmissions scheduled per day</th>' + "".join(
            f'<td><b>{r["returns_day"]:,.1f}</b></td>' for r in recs) + "</tr>")

    def los_cell(r):
        if r.get("target_los") is None:
            return "—"
        return f"{r['target_los']:.2f} days ({UI.esc(_group_phrase(r['settings']))})"
    if any(r.get("target_los") is not None for r in recs):
        rows.append('<tr><th scope="row">Average initial stay, target group</th>'
                    + "".join(f"<td>{los_cell(r)}</td>" for r in recs) + "</tr>")
    return (f'<div class="mwrap"><table class="cmpmx"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


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


def remove_saved(key):
    ss.saved = [x for x in ss.saved if x["key"] != key]


def breakdown_table(s, res):
    reps = res["reps"]
    others = [x for x in ("LOS only", "Demand only", "Readmissions only") if x in set(reps.scenario)]
    if not others:
        return
    st.markdown(f"**Each change on its own** — every run uses the same {s['beds']:,} beds as your scenario and is "
                "compared with a run with no changes and those beds")
    sub = reps[reps.scenario.isin(["Baseline", "Scenario", *others])]
    eff = S.paired_effects(sub, ["bed_days", "mean_wait_days", "returns"], versus="Baseline")
    rows = []
    for sc in others + ["Scenario"]:
        r = {"Change tested": RH.LEVER_NAMES[sc]}
        for label, key, dp in (("Occupied bed-days", "bed_days", 0), ("Average wait (days)", "mean_wait_days", 2),
                               ("Readmissions scheduled", "returns", 0)):
            e = eff[(eff.scenario == sc) & (eff.metric == key)].iloc[0]
            r[label] = ((f"{e['diff']:+,.{dp}f} ± {e['ci95']:,.{dp}f}" if e["clear"] else
                         f"No clear difference ({e['diff']:+,.{dp}f} ± {e['ci95']:,.{dp}f})")
                        if RH.finite(e["diff"]) else "Not estimable")
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, **DF_KW)
    st.caption("Occupied bed-days are capped by the beds available, so at full capacity they barely change even when "
               "demand falls; waiting shows the pressure instead. Separate effects need not add up to the combined "
               "effect because all patients share the same beds.")


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




# ---------------------------------------------------------------- downloads (what the files really contain)
def _tag(s):
    return (f"{s['diagnosis']}{s['severity']}_{s['age'].replace(' ', '')}_los{s['reduction']}_dem{s['demand']:+d}"
            f"_ret{s['readmit']}_{s['beds']}beds_{s['duration']}d_{s['season'].replace(' ', '')}")


def _named(df):
    out = df.copy()
    out.insert(0, "run", out.scenario.map(RUN_LABELS).fillna(out.scenario))
    return out


def summary_table(s, res):
    """One row per measure: Baseline Scenario vs Your Scenario, run means, 95% interval half-widths and the paired
    difference (the numbers behind the page)."""
    rows = []
    for name, key in (("Bed occupancy (%)", "occupancy_pct"), ("Average beds occupied", "avg_occupied"),
                      ("Occupied bed-days", "bed_days"), ("Bed requests that waited (%)", "waited_pct"),
                      ("Average wait, all requests (days)", "mean_wait_days"), ("Largest daily queue", "peak_queue"),
                      ("Requests still waiting after follow-up", "unresolved_requests"),
                      ("New admissions", "admissions"), ("Readmissions scheduled", "returns"),
                      ("Average initial stay, target group (days)", "target_mean_los")):
        (bm, bc), (sm, sc_) = M(key, "Baseline"), M(key, "Scenario")
        d, ci, cl = E(key)
        rows.append(dict(measure=name, baseline_mean=bm, baseline_ci95_halfwidth=bc, scenario_mean=sm,
                         scenario_ci95_halfwidth=sc_, difference=d, difference_ci95_halfwidth=ci,
                         clear_difference=bool(cl) if RH.finite(d) else None))
    for name, key in (("Estimated beds needed on busy days (p95, no bed limit)", "nb"),
                      ("Bed-day demand before the bed limit", "bd")):
        p = pair_unlimited(res, "Reference", "Scenario", key)
        rows.append(dict(measure=name, baseline_mean=p["a"], baseline_ci95_halfwidth=None, scenario_mean=p["b"],
                         scenario_ci95_halfwidth=None, difference=p["diff"], difference_ci95_halfwidth=p["half"],
                         clear_difference=p["clear"]))
    return pd.DataFrame(rows)


def comparison_table(recs):
    rows = []
    for r in recs:
        s = r["settings"]
        rows.append(dict(option=r["title"], question=r["question"], generated=r.get("generated", ""),
                         duration_days=s["duration"], admission_pattern=s["season"], demand_change_pct=s["demand"],
                         available_beds=s["beds"], default_beds=s["ref_beds"],
                         target_group=f"{s['diagnosis']}|{s['severity']}|{s['age']}" if (s["reduction"] or s["readmit"]) else "",
                         shorter_stays_pct=s["reduction"], fewer_readmissions_pct=s["readmit"], runs=s["reps"], seed=s["seed"],
                         avg_occupancy_pct=r["occ"], busy_day_beds_needed=r["nb"], requests_waited_pct=r["waited"],
                         avg_wait_days_all_requests=r["wait"], largest_daily_queue=r["queue"],
                         bed_day_demand_per_day=r["bd_day"], target_group_initial_stay_days=r.get("target_los")))
    return pd.DataFrame(rows)


def downloads(s, res, recs):
    tag = _tag(s)
    run_json = json.dumps(dict(interface_version=APP_VERSION, model_version=MODEL_VERSION,
                               generated=fmt_generated(ss.result),
                               generated_iso=(ss.result["finished_at"].isoformat() if ss.result.get("finished_at")
                                              else None),
                               settings=s, baseline=baseline_text(s), question=scenario_question(s),
                               readmission_reduction_scope="selected patient group (condition, severity, age group)",
                               warmup_days=S.WARMUP_DAYS, waiting_follow_up_days=S.TAIL_DAYS,
                               historical_period=H.PERIOD_LABEL), indent=2, default=str)
    files = [("Download Results Summary (CSV)",
              "Baseline Scenario vs Your Scenario for each measure: averages over the runs, 95% interval half-widths "
              "and the paired difference.", summary_table(s, res).to_csv(index=False), f"results_summary_{tag}.csv"),
             ("Download Detailed Simulation Results (CSV)",
              "One row per simulation run for every run behind this page (baseline, your scenario and comparison "
              "runs). Simulated outputs only, no patient records.", _named(res["reps"]).to_csv(index=False),
              f"simulation_runs_{tag}.csv"),
             ("Download Daily Results (CSV)", "Beds in use, queue and cumulative admissions per day, averaged over runs.",
              _named(res["daily"]).to_csv(index=False), f"daily_{tag}.csv"),
             ("Download Scenario Settings (JSON)", "The settings, baseline and model assumptions behind these results.",
              run_json, f"scenario_settings_{tag}.json"),
             ("Download Data Dictionary (CSV)", "What each column in the CSV files means.",
              RH.DATA_DICTIONARY.to_csv(index=False), "data_dictionary.csv")]
    files = [(lab.replace("Download ", "").replace(" (CSV)", "").replace(" (JSON)", ""), d, data, name)
             for lab, d, data, name in files]
    with st.expander("Download Results"):
        UI.md(f'<p class="rnote">All files describe the completed simulation generated {fmt_generated(ss.result)}, '
              'not unsaved changes in Build a Scenario. They contain simulated results, not historical patient '
              'records.</p>')
        for i, (label, desc, data, name) in enumerate(files):
            c1, c2 = st.columns([1.3, 2], vertical_alignment="center")
            with c1:
                st.download_button(label, data.encode("utf-8"), file_name=name,
                                   mime="application/json" if name.endswith(".json") else "text/csv",
                                   key=f"dl_{i}", type="tertiary", icon=":material/download:")
            c2.markdown(f'<span class="rnote">{desc} ({name.rsplit(".", 1)[1].upper()} file)</span>', unsafe_allow_html=True)


# ---------------------------------------------------------------- page
WEEKDAY_NOTE = ("Bed demand follows the historical admission pattern. More admissions on busier days can increase "
                "pressure on beds and create waiting that carries into later days.")


def impact_tab(s, res):
    case = RH.scenario_case(s)
    comp = RH.improvement_comparator(s)
    UI.md('<div class="tq2">What did the targeted patient-flow changes contribute?</div>'
          f'<p class="ta">{UI.esc(improvement_headline(s, res))}</p>')
    rate = group_return_rate(s["diagnosis"], s["severity"])
    tested = [f"{s['reduction']}% shorter initial stays" if s["reduction"] else "",
              f"{s['readmit']}% lower chance of readmission ({rate:.1f}% → {rate * (1 - s['readmit'] / 100):.1f}%)"
              if s["readmit"] else ""]
    vs = ("the same demand and beds as your scenario, without the improvements" if case == "combined" else
          "the Baseline")
    UI.md('<div class="wyt"><div class="wyh">What You Tested</div>'
          f'<div class="wyg">{UI.esc(cond_label(s["diagnosis"]))} · Severity {s["severity"]} · '
          f'{UI.esc(AGE_PICK[s["age"]])}</div><ul>' + "".join(f"<li>{UI.esc(x)}</li>" for x in tested if x)
          + "</ul></div>"
          f'<div class="wyh2">What Changed</div><p class="rlead">Your scenario compared with {vs}'
          + (f" ({UI.esc(_cond_phrase(s))})" if case == "combined" else "") + ".</p>" + flow_table(s, res))
    occ = pair(res, comp, "Scenario", "bed_days")
    full = _state(s, res, "Scenario", s["beds"]) in ("full", "overloaded")
    UI.md('<details class="why"><summary>Why do occupied bed-days hardly change?</summary><p><i>Bed-day demand</i> is '
          'what patients would use with no bed limit. <i>Occupied bed-days</i> are capped by the available beds '
          f'({occ["a"]:,.0f} → {occ["b"]:,.0f} here). The fall in demand only becomes extra admissions if patients '
          'are waiting for those beds. '
          + ("Here beds stayed full, so freed beds were taken by waiting patients; that does not mean the "
             "improvement had no effect." if full else "") + "</p></details>")
    reps = set(res["reps"].scenario)
    if s["reduction"] and s["readmit"]:
        if case == "improve" and {"LOS only", "Readmissions only"} <= reps:
            rows = []
            for sc, name in (("LOS only", "Shorter stays only"), ("Readmissions only", "Fewer readmissions only"),
                             ("Scenario", "Both together")):
                ok = waits_ok(res, "Baseline", sc)
                metric, w = wait_compare(res, "Baseline", sc) if ok else ("waited_pct", None)
                rt = pair(res, "Baseline", sc, "returns")
                rows.append(f'<div class="ir"><span>{name}</span>{chg(rt, "count", "down", "readmissions")}'
                            f'{chg(w, "pp" if metric == "waited_pct" else "days", "down")}<em></em></div>')
            UI.md('<div class="rsub">Which Change Contributed What?</div><p class="rlead">Each run compared with the '
                  'Baseline. Effects need not add up to the combined effect, because all patients share the same beds.</p>'
                  '<div class="itab four"><div class="ir ih"><span></span><b>Readmissions scheduled</b>'
                  '<b>Waiting</b><em></em></div>' + "".join(rows) + "</div>")
        else:
            UI.md('<p class="rnote">Both changes were tested together. Their separate effects were not simulated under '
                  'your demand and bed settings, so only the combined effect is shown.</p>')


def saved_options():
    """Saved options in saved order, with visible labels Option A, B, C… assigned by current position."""
    recs = [r for r in ss.saved if "settings" in r]
    for i, r in enumerate(recs):
        r["title"] = f"Option {chr(65 + i)}"
    return recs


def compare_tab(s, res, saved_now):
    """Guided workflow: Save → Test Another Plan → Run → Save → Compare."""
    recs = saved_options()
    n = len(recs)
    stage = 0 if n == 0 else (1 if n == 1 else 4)
    steps = ["Save", "Test Another Plan", "Run", "Save", "Compare"]
    UI.md('<div class="tq">Which plan is worth exploring further?</div><ol class="prog">' + "".join(
        f'<li class="{"done" if i < stage or (i == 0 and saved_now) else ("now" if i == stage else "")}">{t}</li>'
        for i, t in enumerate(steps)) + f'</ol><p class="rnote">{n} of {MAX_SAVED} plans saved.</p>')
    cur = ss.result["key"]
    UI.md('<div class="curplan"><span>Current results</span><b>' + UI.esc(scenario_question(s)) + '</b><em>'
          + ("Saved as " + next(r["title"] for r in recs if r["key"] == cur) if saved_now else "Not saved yet")
          + "</em></div>")
    if n == 0:
        UI.md('<div class="cmpstart"><div class="ch">Compare Different Capacity Plans</div><p>Save your current '
              'scenario, then test another plan to compare their effects on capacity and waiting.</p></div>')
    elif n == 1:
        UI.md('<div class="cmpstart one"><div class="ch">1 plan saved — save one more to compare.</div>'
              '<p>Test Another Plan opens Build a Scenario; your saved result stays here.</p></div>')
    with st.container(key="cmpactions", horizontal=True, gap="small"):
        st.button("Saved" if saved_now else "Save Current Scenario", key="cmp_add2", disabled=saved_now,
                  type="secondary" if saved_now else "primary",
                  icon=":material/check:" if saved_now else ":material/bookmark_add:", on_click=save_current)
        st.button("Test Another Plan", key="cmp_test", type="primary" if saved_now else "secondary",
                  icon=":material/arrow_forward:", icon_position="right", on_click=go_to, args=("simulator",))
        st.button("Edit Scenario", key="res_edit2", type="tertiary", icon=":material/edit:", on_click=go_to,
                  args=("simulator",))
    if n >= 2:
        durs = {(r["settings"]["duration"], r["settings"]["season"]) for r in recs}
        if len(durs) > 1:
            UI.md('<div class="satnote"><b>Different planning periods.</b> These plans use different durations or '
                  'admission patterns, so totals are not directly comparable; the table uses percentages and per-day '
                  'figures.</div>')
        UI.md(comparison_matrix(recs))
        UI.md(f'<p class="rnote">Differences are against {recs[0]["title"]}. The tool does not rank plans: weigh '
              'waiting, busy-day demand and beds against what is feasible for your hospital.</p>')
        st.download_button("Download Comparison (CSV)", comparison_table(recs).to_csv(index=False).encode("utf-8"),
                           file_name="scenario_comparison.csv", mime="text/csv", key="dl_cmp", type="tertiary",
                           icon=":material/download:")
    if recs:
        with st.container(key="cmprm", horizontal=True, gap="small"):
            for r in recs:
                st.button(f"Remove {r['title']}", key=f"cmp_rm_{r['id']}", type="tertiary", on_click=remove_saved,
                          args=(r["key"],))
    UI.md('<div class="rsub">Quick Plans to Test</div><p class="rlead">Each opens Build a Scenario with one change '
          'applied for you to review; run the simulation there to see new results.</p>')
    with st.container(key="resexplore", horizontal=True, gap="small"):
        for i, (label, upd, fl) in enumerate(next_ideas(s, res)):
            st.button(label, key=f"res_try_{i}", on_click=try_next, args=(upd, fl))


def why(summary, text):
    """Small expandable contextual note (used only where a chart could be misread)."""
    return f'<details class="why"><summary>{summary}</summary><p>{text}</p></details>'


RES_TABS = [("overview", "Overview", ":material/space_dashboard:"),
            ("explore", "Explore Results", ":material/insights:"),
            ("compare", "Compare Plans", ":material/compare_arrows:")]


def goto_tab(tab, view=None):
    """Switch the Results tab (and optionally the Explore view) and return to the top of the tab content."""
    ss.ui["res_tab"] = tab
    if view:
        ss.ui["trend_view"] = view
        ss.pop("w_ui_trend_view", None)
    ss.scroll_to = "res-tabs"


def summary_columns(s):
    plan = [("Planning period", f"{s['duration']} days"),
            ("Admission pattern", "Typical week" if s["season"] == "Annual average"
             else f"Historical pattern starting in {H.MONTH_FULL[s['season']]}"),
            ("Admission demand", "Historical level (0% change)" if not s["demand"] else
             f"{s['demand']:+d}% vs historical level"),
            ("Available beds", f"{s['beds']:,}" + (" (default)" if s["beds"] == s["ref_beds"] else
                                                   f" (default {s['ref_beds']:,})"))]
    if s["reduction"] or s["readmit"]:
        flow = [("Target group", f"{cond_label(s['diagnosis'])} · Severity {s['severity']}"),
                ("Age group", AGE_PICK[s["age"]]),
                ("Shorter initial stays", f"{s['reduction']}% shorter" if s["reduction"] else "None"),
                ("Readmission reduction", f"{s['readmit']}% lower chance" if s["readmit"] else "None")]
    else:
        flow = None
    return plan, flow


def bar_pair(label, a, b, fmt, scale_max, show_base, delta="", note="", cap=None):
    """Baseline and Your Scenario as two labelled bars on one shared scale; optional capacity marker."""
    def bar(cls, name, v):
        w = 0 if scale_max <= 0 else min(100, 100 * v / scale_max)
        return (f'<div class="bp"><span class="bn">{name}</span><div class="bt"><i class="{cls}" style="width:{w:.1f}%"></i>'
                + (f'<em class="cap" style="left:{min(100, 100 * cap / scale_max):.1f}%" title="Available beds"></em>'
                   if cap else "") + f'</div><b>{fmt(v)}</b></div>')
    rows = (bar("b0", "Baseline", a) if show_base else "") + bar("b1", "Your Scenario", b)
    return (f'<div class="cmpr"><div class="cl">{label}</div>{rows}'
            + (f'<div class="cd">{delta}</div>' if delta else "") + (f'<div class="cnote">{note}</div>' if note else "")
            + "</div>")


def evidence_band(s, res, show_ref):
    """Bed capacity and patient waiting, side by side, as compact comparisons."""
    a, b = "Reference", "Scenario"
    occ = pair(res, a, b, "occupancy_pct")
    nb = pair_unlimited(res, a, b, "nb")
    top = max(nb["a"], nb["b"], s["beds"], s["ref_beds"]) * 1.06
    cap = (bar_pair("Average bed occupancy", occ["a"], occ["b"], lambda v: f"{v:.0f}%", 100, show_ref,
                    chg(occ, "pp") if show_ref else "")
           + bar_pair("Estimated beds needed on busy days " + _tip(
                          "About how many beds would be needed on a busier day if everyone could be admitted without "
                          "waiting. Not the beds actually occupied, and not an exact shortfall or a number of beds to "
                          "add."), nb["a"], nb["b"], lambda v: f"{v:,.0f}", top, show_ref,
                      chg(nb, "beds", "down") if show_ref else "",
                      f'The dark marker shows the {s["beds"]:,} available beds. Beds actually in use can never exceed '
                      'it; demand above it means patients wait.', cap=s["beds"]))
    ok_b, ok_a = waits_ok(res, b), waits_ok(res, a)
    if ok_b:
        wp = pair(res, a, b, "waited_pct") if ok_a else None
        qd = res["daily"]
        qshare = {n: float((qd[qd.scenario == n].queue >= 1).mean()) * 100 for n in (a, b)}
        q = pair(res, a, b, "peak_queue")
        qtxt = (f"{q['a']:,.0f} → " if show_ref else "") + f"{q['b']:,.0f}"
        dtxt = (f"{qshare[a]:.0f}% → " if show_ref else "") + f"{qshare[b]:.0f}%"
        often = ('<div class="wq">How often did patients have to wait?</div>'
                 + bar_pair("Bed requests that waited (of all requests)", run_mean(res, a, "waited_pct") or 0,
                            run_mean(res, b, "waited_pct"), fmt_pct, 100, show_ref and ok_a,
                            chg(wp, "pp", "down") if (show_ref and wp) else "")
                 + '<div class="wmini"><span>Largest daily queue</span><b>' + qtxt + '</b>'
                 + '<span>Days with patients waiting</span><b>' + dtxt + '</b></div>')
        mw = pair(res, a, b, "mean_wait_days") if (show_ref and ok_a) else None
        da, db = waited_delay(res, a), waited_delay(res, b)
        mw_b = run_mean(res, b, "mean_wait_days")
        top_w = max(run_mean(res, a, "mean_wait_days") or 0, mw_b, 0.1) * 1.1
        long_ = ('<div class="wq">How long did they wait?</div>'
                 + bar_pair("Average wait across all bed requests", run_mean(res, a, "mean_wait_days") or 0, mw_b,
                            fmt_wait, top_w, show_ref and ok_a, chg(mw, "days", "down") if mw else "",
                            "Most requests wait 0 days, so this average is small when few patients wait."
                            if (run_mean(res, b, "waited_pct") or 0) < 5 else "")
                 + '<div class="wmini"><span>Among patients who waited (approx.)</span><b>'
                 + ("" if not show_ref else ("none → " if da is None else f"{da:.1f} → "))
                 + ("none waited" if db is None else f"{db:.1f} days") + "</b></div>")
        wait = often + long_
    else:
        us = run_mean(res, b, "unresolved_requests")
        wait = (f'<div class="wq">How often did patients have to wait?</div><div class="cnote">Waiting could not be '
                f'fully measured: about {us:,.0f} requests were still waiting {TAIL_DAYS} days after the period.</div>')
    return (f'<div class="eband"><div class="ecol"><div class="eh">{ic("bed")}Bed Capacity</div>{cap}</div>'
            f'<div class="ecol"><div class="eh">{ic("schedule")}Patient Waiting</div>{wait}</div></div>')


def insight_action(i, action):
    label, upd, fl = action
    if upd == "compare":
        st.button(label, key=f"ins_{i}", type="tertiary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=goto_tab, args=("compare",))
    elif upd == "groups":
        st.button(label, key=f"ins_{i}", type="tertiary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=to_explorer)
    else:
        st.button(label, key=f"ins_{i}", type="tertiary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=try_next, args=(upd, fl),
                  help="Opens Build a Scenario with this change applied for you to review. Nothing runs until you "
                       "press Run Simulation.")


def overview_tab(s, res, saved):
    case = RH.scenario_case(s)
    flow = bool(s["reduction"] or s["readmit"])
    with st.container(key="ovintro", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        UI.md('<div class="ovt"><div class="ovh">Your Capacity Overview</div><p>See whether the hospital could manage '
              'demand, what changed, and what this means for planning.</p></div>')
        st.button("Explore Detailed Results", key="ov_explore", icon=":material/arrow_forward:", icon_position="right",
                  on_click=goto_tab, args=("explore",))
    plan, fl = summary_columns(s)
    col = lambda rows: "".join(f'<div class="kv"><span>{k}</span><b>{UI.esc(v)}</b></div>' for k, v in rows)
    # stage 1 — the question
    with st.container(key="stg_q"):
        UI.md('<div class="stg">The Question</div>'
              f'<div class="rq">{UI.esc(scenario_question(s))}</div>'
              '<div class="scols"><div class="scol"><div class="sch">Hospital Planning Conditions</div>' + col(plan)
              + '</div><div class="scol"><div class="sch">Patient Flow Improvements</div>'
              + (col(fl) if fl else '<div class="snone">No patient-flow changes were tested.</div>') + '</div></div>'
              '<div class="rbase"><b>Compared against the Baseline:</b> '
              f'{UI.esc(baseline_text(s)[len("Baseline: "):])}</div>')
    # stage 2 — the answer
    icon, head, evidence, context = capacity_answer(s, res)
    extra = baseline_change_sentence(s, res)
    with st.container(key="stg_a"):
        UI.md('<div class="stg">The Answer</div>'
              f'<div class="hero2 {icon}"><div class="hh">{ic(ICON[icon])}<span>{UI.esc(head)}</span></div>'
              '<div class="evid">' + "".join(f'<div><b>{UI.esc(v)}</b><span>{UI.esc(l)}</span></div>' for v, l in evidence)
              + "</div>" + (f'<p class="hc">{UI.esc(" ".join(x for x in (context, extra) if x))}</p>'
                            if (context or extra) else "") + "</div>")
        with st.container(key="ansacts", horizontal=True, gap="small"):
            st.button("Explore Bed Use", key="go_beds", type="tertiary", icon=":material/arrow_forward:",
                      icon_position="right", on_click=goto_tab, args=("explore", "Beds"))
            st.button("See Waiting Patterns", key="go_wait", type="tertiary", icon=":material/arrow_forward:",
                      icon_position="right", on_click=goto_tab, args=("explore", "Waiting"))
    # stage 3 — the evidence
    with st.container(key="stg_e"):
        UI.md('<div class="stg">The Evidence</div>'
              + ('<div class="legend2"><span><i class="lr"></i>Baseline</span><span><i class="ls"></i>Your Scenario</span></div>'
                 if case != "none" else '<p class="rnote">This run has no changes, so it is the baseline itself.</p>')
              + evidence_band(s, res, show_ref=case != "none"))
        if flow:
            UI.md(f'<div class="imphl">{ic("trending_down")}<div><div class="ih1">What the patient-flow changes '
                  f'did</div><div class="ih2">{UI.esc(improvement_headline(s, res))}</div></div></div>')
            st.button("Explore Improvement Impact", key="go_impact", type="tertiary", icon=":material/arrow_forward:",
                      icon_position="right", on_click=goto_tab, args=("explore", "Improvement Impact"))
    # stage 4 — the decision implication
    with st.container(key="stg_d"):
        UI.md('<div class="stg">The Decision Implication</div><div class="dt2">What This Means for Your Capacity Plan</div>')
        INS_ICON = {"beds": "bed", "demand": "trending_up", "ok": "check_circle", "wait": "schedule", "flow": "sync_alt"}
        for i, (k, f, why_, test, action) in enumerate(decision_insights(s, res)):
            with st.container(key=f"ins_row_{i}"):
                UI.md(f'<div class="di2">{ic(INS_ICON.get(k, "lightbulb"))}<div><div class="f">{UI.esc(f)}</div>'
                      f'<div class="w"><span>Why it matters</span>{UI.esc(why_)}</div>'
                      f'<div class="w"><span>Scenario to test</span>{UI.esc(test)}</div></div></div>')
                insight_action(i, action)
        with st.container(key="ovfoot", horizontal=True, gap="small"):
            st.button("Compare Another Plan", key="go_compare", type="tertiary", icon=":material/compare_arrows:",
                      on_click=goto_tab, args=("compare",))
            st.button("How These Figures Are Calculated", key="ov_tech", type="tertiary", icon=":material/info:",
                      on_click=open_technical)


def open_technical():
    """Open Explore Results with Technical Details expanded and in view."""
    ss.tech_open = True
    goto_tab("explore")
    ss.scroll_to = "technical-details"


def technical_details(s):
    """How the numbers on this page are defined. Secondary reference: collapsed, in Explore Results."""
    UI.md('<div id="technical-details"></div>')
    with st.expander("Technical Details", expanded=bool(ss.pop("tech_open", False))):
        rate = group_return_rate(s["diagnosis"], s["severity"])
        UI.md(f"""<ul class="simdet">
<li><b>Simulation runs:</b> {s['reps']} runs of the {s['duration']}-day period for each scenario, with the same random seeds (seed {s['seed']}), so differences are compared run by run. Results are averages across runs.</li>
<li><b>Clear differences:</b> a difference is called clear when the 95% interval of the run-by-run difference excludes zero. This reflects simulation randomness only, not uncertainty in the data or in how well a real change would work.</li>
<li><b>Busy-day bed demand:</b> the 95th percentile of beds in use per day in {min(s['reps'], 5)} separate runs with no bed limit (same demand and changes). Bed-day demand comes from the same runs.</li>
<li><b>Waiting:</b> whole days from asking for a bed to getting one, for every bed request in the period (new admissions and readmissions); requests are followed for up to {S.TAIL_DAYS} days after the period. {S.WARMUP_DAYS} warm-up days are not counted.</li>
<li><b>Shorter stays:</b> each eligible initial stay in the target group (and age band) is shortened by the percentage and rounded to whole days, with a minimum of one day; stays of patients who died are not shortened.</li>
<li><b>Fewer readmissions:</b> a relative reduction of the chance of return, e.g. {rate:.1f}% → {rate * (1 - (s['readmit'] or 10) / 100):.1f}% for a {s['readmit'] or 10}% reduction; the model uses one rate for all ages in a group.</li>
<li><b>Readmissions scheduled:</b> return stays booked by patients admitted during the period; some occur after it ends.</li>
<li><b>Bed demand by condition:</b> admissions per day × average initial stay; an estimate, not beds measured per condition.</li>
</ul>""")
        st.button("Model Documentation", key="res_method", type="tertiary", icon=":material/menu_book:",
                  on_click=go_to, args=("docs",))


def explore_tab(s, res, saved):
    flow = bool(s["reduction"] or s["readmit"])
    views = ["Beds", "Waiting", "Admissions & Readmissions", "Length of Stay"] + (["Improvement Impact"] if flow else [])
    if ss.ui.get("trend_view") not in views:
        ss.ui["trend_view"] = "Beds"
    with st.container(key="trendnav"):
        view = _seg("trend_view", "Explore", views, lambda x: x, store="ui", label_visibility="collapsed")
    {"Beds": details_beds, "Waiting": details_waiting, "Admissions & Readmissions": details_admissions,
     "Length of Stay": details_los, "Improvement Impact": lambda s_: impact_tab(s_, res)}[view](s)
    with st.container(key="exback", horizontal=True, gap="small"):
        st.button("Back to Overview", key="ex_overview", type="tertiary", icon=":material/arrow_back:",
                  on_click=goto_tab, args=("overview",))
        st.button("Compare Another Plan", key="ex_compare", type="tertiary", icon=":material/compare_arrows:",
                  on_click=goto_tab, args=("compare",))
    if RH.scenario_case(s) != "none":
        with st.expander("Detailed Simulation Results"):
            UI.md('<p class="rnote">The full set of simulation measures, with differences between scenarios and how '
                  'results varied across repeated runs.</p>')
            results_stats(s)
            breakdown_table(s, res)
    technical_details(s)
    downloads(s, res, saved_options())


def page_results():
    global RV
    if ss.result is None:
        UI.page_title("Capacity Results", "No results yet",
                      "Build a capacity scenario and press <b>Run Simulation</b>. Your results will appear here and "
                      "stay available while you move between pages.")
        st.button("Build a Capacity Scenario", type="primary", key="res_empty", icon=":material/arrow_forward:",
                  icon_position="right", on_click=go_to, args=("simulator",))
        return
    s, res = ss.result["settings"], ss.result["res"]
    if "nb_vals" not in res or "ref_beds" not in s or "bd_demand" not in res:
        UI.page_title("Capacity Results", "Please run the scenario again",
                      "These results were produced by an earlier version of the planner.")
        st.button("Edit Scenario", type="primary", key="res_edit", on_click=go_to, args=("simulator",))
        return
    flow = bool(s["reduction"] or s["readmit"])
    RV = RH.Results(s, view_of(res, "Reference"))
    current, _ = current_settings()
    stale = tuple(current[n] for n in NAMES) != ss.result["key"]
    saved = any(x["key"] == ss.result["key"] for x in ss.saved)
    target = ss.pop("scroll_to", None)
    if target:
        scroll_to_anchor(target)

    with st.container(key="reshead", horizontal=True, vertical_alignment="bottom", horizontal_alignment="distribute"):
        UI.md(f'<div class="ovhead simhead"><div class="rgen">Results generated · {UI.esc(fmt_generated(ss.result))}</div>'
              '<h1>Capacity Results</h1><p>Could the hospital manage the demand in your scenario?</p></div>')
        with st.container(key="resactions", horizontal=True, gap="small", width="content"):
            st.button("Edit Scenario", key="res_edit", type="primary", icon=":material/edit:", on_click=go_to,
                      args=("simulator",))
            st.button("Saved" if saved else "Save for Comparison", key="cmp_add", disabled=saved,
                      icon=":material/check:" if saved else ":material/bookmark_add:", on_click=save_current)
    if stale:
        UI.md('<div class="stale2">' + ic("info") + '<span>Your scenario settings have changed since these results were '
              'generated. Run the simulation again to see the updated results. This page still describes the run that '
              'produced them.</span></div>')
        if st.button("Run Again with New Settings", key="res_rerun", icon=":material/refresh:"):
            do_run()

    tab = ss.ui.get("res_tab", "overview")
    UI.md('<div id="res-tabs"></div>')
    with st.container(key="restabs", horizontal=True, gap="small"):
        for key, label, icon in RES_TABS:
            st.button(label, key=f"res_tab_{key}", icon=icon, type="primary" if tab == key else "tertiary",
                      on_click=goto_tab, args=(key,))
    {"overview": overview_tab, "explore": explore_tab, "compare": compare_tab}[tab](s, res, saved)


# ---------------------------------------------------------------- 02 tabs
def tab_q(question, answer=None):
    UI.md(f'<div class="tq2">{question}</div>' + (f'<p class="ta">{answer}</p>' if answer else ""))


def _weekday_extremes(col):
    prof = RV.weekday_profile(col)
    p = prof[prof.scenario == "Scenario"].set_index("weekday")[col]
    return p.idxmax(), p.max(), p.idxmin(), p.min()


def _identical(agg):
    a = agg[agg.scenario == "Baseline"].value.to_numpy()
    b = agg[agg.scenario == "Scenario"].value.to_numpy()
    return len(a) == len(b) and np.allclose(a, b)


def details_beds(s):
    res = ss.result["res"]
    full_s = full_day_share(res, "Scenario", s["beds"])
    full_r = full_day_share(res, "Reference", s["ref_beds"])
    nb_s = float(np.mean(res["nb_vals"]["Scenario"]))
    flat = full_s >= 0.5 or full_r >= 0.5
    occ_s = run_mean(res, "Scenario", "occupancy_pct")
    UI.md('<div class="tq2">How did bed use change over time?</div><p class="ta">'
          + (f"Every bed was in use on {full_s * 100:.0f}% of days in your scenario, so bed use sits at the limit "
             "while the extra demand waits." if full_s >= 0.5 else
             f"Your scenario used {occ_s:.0f}% of its beds on an average day and reached the limit on "
             f"{full_s * 100:.0f}% of days.") + "</p>")
    opts = ["Weekly trend", "Daily", "Weekday pattern"] + (["Monthly"] if H.is_seasonal(s["season"]) else [])
    view = bind("bed_view", st.radio, "View", store="ui", options=opts, horizontal=True, label_visibility="collapsed")
    fig = go.Figure()
    if view == "Weekday pattern":
        prof = RV.weekday_profile("occupied")
        z = [prof[prof.scenario == sc].occupied.tolist() for sc in ("Baseline", "Scenario")]
        fig.add_trace(go.Heatmap(z=z, x=H.WEEKDAYS, y=["Baseline", "Your Scenario"], colorscale=UI.HEAT, showscale=False,
                                 texttemplate="%{z:,.0f}", textfont=dict(size=14), xgap=4, ygap=4,
                                 hovertemplate="%{y} · %{x}: %{z:,.0f} beds in use on average<extra></extra>"))
        UI.style_fig(fig, 200, legend=False)
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=14, color=UI.INK), autorange="reversed")
        fig.update_xaxes(side="top", tickfont=dict(size=14, color=UI.INK))
        show(fig, "res_occ_weekday")
        p = prof[prof.scenario == "Scenario"].set_index("weekday").occupied
        if p.max() - p.min() < max(1.0, 0.005 * s["beds"]):
            read = "In your scenario bed use was at about the same level on every weekday."
        else:
            read = (f"Average beds in use on each weekday. In your scenario bed use was highest on {p.idxmax()} "
                    f"({p.max():,.0f}) and lowest on {p.idxmin()} ({p.min():,.0f}).")
    else:
        agg, xlab = RV.by_period("occupied", {"Weekly trend": "Weekly"}.get(view, view), "mean")
        same = _identical(agg)
        series = (("Scenario", UI.TEAL, "solid"),) if same else (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid"))
        for name, color, dash in series:
            a = agg[agg.scenario == name]
            label = "Baseline and Your Scenario (identical)" if same else name
            if view == "Daily":
                fig.add_scatter(x=a.period, y=a.value, name=label, mode="lines", line=dict(color=color, width=2.4, dash=dash),
                                hovertemplate="Day %{x}: %{y:,.0f} beds<extra>" + label + "</extra>")
            elif view == "Weekly trend":
                fig.add_scatter(x=a.label, y=a.value, name=label, mode="lines+markers", marker=dict(size=8),
                                line=dict(color=color, width=3, dash=dash),
                                hovertemplate="%{x}: %{y:,.0f} beds on an average day<extra>" + label + "</extra>")
            else:                                    # monthly bars: values in hover, no stacked labels near the limit
                fig.add_bar(x=a.label, y=a.value, name=label, marker_color=color,
                            hovertemplate="%{x}: %{y:,.0f} beds on an average day<extra>" + label + "</extra>")
        fig.add_hline(y=s["beds"], line_dash="dot", line_color=UI.TEAL_DARK, line_width=2)
        if s["ref_beds"] != s["beds"]:
            fig.add_hline(y=s["ref_beds"], line_dash="dot", line_color=UI.BASE, line_width=2)
        fig.add_hline(y=nb_s, line_dash="dash", line_color="#D9785A", line_width=1.5)
        UI.style_fig(fig, 340)
        UI.md('<div class="mstrip">'
              f'<span><i class="k dot"></i>Available beds, your scenario <b>{s["beds"]:,}</b></span>'
              + (f'<span><i class="k dotb"></i>Available beds, baseline <b>{s["ref_beds"]:,}</b></span>'
                 if s["ref_beds"] != s["beds"] else "")
              + f'<span><i class="k dash"></i>Busy-day demand estimate (no bed limit) <b>{nb_s:,.0f}</b></span></div>')
        vals = agg.value
        lim = [s["beds"], s["ref_beds"], nb_s]
        lo = min(vals.min(), *lim)
        fig.update_yaxes(title="Beds", range=[lo * (0.0 if view == "Monthly" else 0.92), max(vals.max(), *lim) * 1.04])
        fig.update_xaxes(title=None)
        if view == "Daily":
            monday_ticks(fig, RV.daily_frame())
        show(fig, f"res_occ_{view}")
        read = {"Weekly trend": "Each point is the average number of beds in use per day in that week.",
                "Daily": "Beds in use on each day, averaged over the simulation runs.",
                "Monthly": "Average beds in use per day in each month of the historical admission pattern."}[view]
        if same:
            read += " Both scenarios are identical here, so one series is shown."
    UI.md(f'<p class="rnote">{read}' + (" Lines show beds actually in use, which never exceed the beds available "
          "(dotted)." if view != "Weekday pattern" else "") + "</p>")
    if flat:
        who = ("Both scenarios" if full_s >= 0.5 and full_r >= 0.5 else
               ("Your scenario" if full_s >= 0.5 else "The baseline"))
        UI.md(why("Why is bed use flat?", f"{who} reached the available-bed limit on most days. The chart cannot show "
                  "unmet demand, so look at the Waiting results to see the pressure on capacity."))
    if nb_s > s["beds"]:
        UI.md(why("Why can estimated demand exceed available beds?",
                  f"Actual bed use is limited to the {s['beds']:,} available beds. Estimated demand shows how many beds "
                  "could be needed on busier days without that limit. When demand exceeds capacity, patients may have "
                  "to wait. The gap is not an exact number of beds to add."))
    if view in ("Daily", "Weekday pattern"):
        UI.md(why("Why does bed use vary by weekday?", WEEKDAY_NOTE + (
            " Here every bed was in use on most days, so this chart cannot show the weekday differences; the Waiting "
            "results show the extra pressure." if flat else "")))

    dx = RH.dx_bed_use(RV)
    constrained = dx.attrs.get("constrained", False)
    UI.md('<div class="tq2">Which Conditions Contribute Most to Bed Demand?</div>'
          '<p class="rlead">Compare estimated demand for Heart Failure, Heart Attack and COPD to see which conditions '
          'contribute most to bed pressure.</p>')
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
    UI.md('<p class="rnote">Approximate demand on an average day: new admissions per day × average initial stay. These '
          'estimates cover initial stays; they are not beds measured for each condition, and the conditions share one '
          'pool of beds rather than separate wards. '
          + ("Return stays are not included in this chart." if constrained else
             "Return stays cannot be split by condition and are shown as one block (average beds in use minus the "
             "condition estimates).") + "</p>")


def details_waiting(s):
    (ub, _), (us, _) = M("unresolved_requests", "Baseline"), M("unresolved_requests", "Scenario")
    daily = RV.daily_frame()
    daily = daily[daily.scenario.isin(["Baseline", "Scenario"])]
    if ub > 0 or us > 0:
        ans = ("Waiting could not be fully measured: some requests were still waiting "
               f"{TAIL_DAYS} days after the period, so the queue kept growing.")
    elif daily.queue.max() < 1:
        ans = "No queue formed in either scenario: every request got a bed on the day it was made."
    else:
        q = daily.groupby("scenario").queue.apply(lambda x: (x >= 1).mean())
        ans = (f"A queue was present at the end of {q.get('Scenario', 0) * 100:.0f}% of days in your scenario and "
               f"{q.get('Baseline', 0) * 100:.0f}% in the baseline.")
    tab_q("When did patients have to wait for a bed?", ans)
    (wb, _), (ws, _) = M("waited_pct", "Baseline"), M("waited_pct", "Scenario")
    (mb, _), (ms, _) = M("mean_wait_days", "Baseline"), M("mean_wait_days", "Scenario")
    (qb, _), (qs, _) = M("peak_queue", "Baseline"), M("peak_queue", "Scenario")
    db, dsc = RH.delay_if_waited(RV, "Baseline"), RH.delay_if_waited(RV, "Scenario")
    qd = daily.groupby("scenario").queue.apply(lambda x: (x >= 1).mean() * 100)
    f = lambda v: "none waited" if v is None else f"{v:.1f} days"
    UI.md('<div class="tq3">How often did patients have to wait?</div>')
    UI.tiles([("Bed requests that waited", f"{fmt_pct(wb)} → {fmt_pct(ws)}", "of all bed requests, at least one day"),
              ("Largest daily queue", f"{qb:,.0f} → {qs:,.0f}", "requests waiting at the end of the busiest day"),
              ("Days with patients waiting", f"{qd.get('Baseline', 0):.0f}% → {qd.get('Scenario', 0):.0f}%",
               "share of days ending with a queue")])
    UI.md('<div class="tq3">How long did they wait?</div>')
    pair_txt = lambda a, b: f"{a} in both" if a == b and len(a) > 9 else f"{a} → {b}"
    UI.tiles([("Average wait, all bed requests", pair_txt(fmt_wait(mb), fmt_wait(ms)), "includes requests that waited 0 days"),
              ("Average wait, patients who waited", pair_txt(f(db), f(dsc)), "only requests that waited (approximate)")])
    UI.md('<p class="rnote">Each pair reads Baseline → Your Scenario.</p>')
    if daily.queue.max() >= 1:
        fig = go.Figure()
        for name, color, dash in (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid")):
            a = daily[daily.scenario == name]
            fig.add_scatter(x=a.day, y=a.queue, name=name, mode="lines", line=dict(color=color, width=2.4, dash=dash),
                            hovertemplate="Day %{x}: %{y:,.0f} waiting<extra>" + name + "</extra>")
        UI.style_fig(fig, 280, "Bed requests still waiting at the end of each day")
        fig.update_yaxes(rangemode="tozero")
        monday_ticks(fig, daily)
        show(fig, "res_queue")
        UI.md(why("Why does waiting rise and fall?", WEEKDAY_NOTE))
    UI.md('<p class="rnote">Waits are whole days in one shared first-come-first-served queue for a hospital bed. They '
          'show capacity pressure and are not emergency-department waiting times. Waiting is not recorded by '
          'condition.</p>')


def details_los(s):
    d = RH.dx_los(RV)
    if s["reduction"]:
        tab_q("Which patient groups experienced shorter hospital stays?",
              f"Only {_patients(s)} had shorter initial stays in this scenario; other groups change only through "
              "random variation.")
    else:
        tab_q("Which patient groups experienced shorter hospital stays?",
              "None: this scenario did not change length of stay, so only the three condition groups are shown and "
              "any differences are random variation.")
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
    if s["reduction"]:
        short, _ = M("targeted_admissions", "Scenario")
        who = "" if s["age"] == "All ages" else (f" (only patients {AGE_PHRASE[s['age']]}; the target row shows all "
                                                  "ages in the group)")
        UI.md(f'<p class="rnote">About {short:,.0f} initial stays in {H.group_label(RV.group)}{who} were shortened by '
              f'the assumed {s["reduction"]}%. The effect comes from your assumption, not from evidence of a real '
              'intervention.</p>')


def details_admissions(s):
    (ab, _), (as_, _) = M("admissions", "Baseline"), M("admissions", "Scenario")
    (rb, _), (rs, _) = M("returns", "Baseline"), M("returns", "Scenario")
    same_adm = abs(ab - as_) < 0.5
    tab_q("Did admissions or return stays change?",
          ("New admissions are unchanged because this scenario does not change admission demand. "
           if same_adm else f"New admissions changed from {ab:,.0f} to {as_:,.0f} over the period. ")
          + f"Readmissions scheduled went from {rb:,.0f} to {rs:,.0f}.")
    UI.md('<p class="rnote"><b>New admissions</b> are patients arriving for a first (initial) stay. <b>Readmissions '
          'scheduled</b> are return stays booked by patients admitted during the period; they are counted when the '
          'original patient gets a bed, and some happen after the period ends.</p>')
    c1, c2 = st.columns(2)
    with c1:
        series = bind("adm_series", st.radio, "Show", store="ui", options=["New admissions", "Readmissions scheduled"],
                      horizontal=True)
    with c2:
        opts = ["Daily", "Weekly"] + (["Monthly"] if H.is_seasonal(s["season"]) else []) + ["Weekday pattern"]
        view = bind("adm_view", st.radio, "View", store="ui", options=opts, horizontal=True)
    col = "new_admissions" if series == "New admissions" else "new_returns"
    fig = go.Figure()
    if view == "Weekday pattern":
        prof = RV.weekday_profile(col)
        z = [prof[prof.scenario == sc][col].tolist() for sc in ("Baseline", "Scenario")]
        fig.add_trace(go.Heatmap(z=z, x=H.WEEKDAYS, y=["Baseline", "Your Scenario"], colorscale=UI.HEAT, showscale=False,
                                 texttemplate="%{z:,.0f}", textfont=dict(size=14), xgap=4, ygap=4,
                                 hovertemplate="%{y} · %{x}: %{z:,.0f} per day<extra></extra>"))
        UI.style_fig(fig, 200, legend=False)
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)", autorange="reversed", tickfont=dict(size=14, color=UI.INK))
        fig.update_xaxes(side="top", tickfont=dict(size=14, color=UI.INK))
        hi, hv, lo, lv = _weekday_extremes(col)
        note = f"Per day on each weekday, in your scenario highest on {hi} ({hv:,.0f}) and lowest on {lo} ({lv:,.0f})."
    else:
        agg, _ = RV.by_period(col, view, "mean" if view == "Daily" else "sum")
        same = _identical(agg)
        names = (("Scenario", UI.TEAL, "solid"),) if same else (("Baseline", UI.BASE, "dash"), ("Scenario", UI.TEAL, "solid"))
        many = agg[agg.columns[agg.columns.isin(["label", "period"])][0]].nunique() > 8
        for name, color, dash in names:
            a = agg[agg.scenario == name]
            label = "Baseline and Your Scenario (identical)" if same else name
            if view == "Daily":
                fig.add_scatter(x=a.period, y=a.value, name=label, mode="lines", line=dict(color=color, width=2, dash=dash))
            else:
                fig.add_bar(x=a.label, y=a.value, name=label, marker_color=color,
                            text=None if (same or many) else [f"{v:,.0f}" for v in a.value],
                            textposition="outside", cliponaxis=False)
        UI.style_fig(fig, 320)
        fig.update_yaxes(title="Per day" if view == "Daily" else "Total", rangemode="tozero")
        if view == "Daily":
            monday_ticks(fig, RV.daily_frame())
        note = ("Both scenarios are identical here, so one series is shown." if same else
                {"Daily": "Per day, averaged over the simulation runs.", "Weekly": "Total in each week.",
                 "Monthly": "Total in each month of the historical pattern."}[view])
    show(fig, f"res_adm_{col}_{view}")
    UI.md(f'<p class="rnote">{note}</p>')
    if view == "Daily":
        UI.md(why("Why does this pattern repeat?", "The simulation follows historical differences between weekdays. "
                  "Select Weekday Pattern to compare the days."))
        st.button("Show Weekday Pattern", key="adm_to_weekday", type="tertiary", icon=":material/calendar_view_week:",
                  on_click=lambda: (ss.ui.__setitem__("adm_view", "Weekday pattern"), ss.pop("w_ui_adm_view", None)))


def results_stats(s):
    UI.md(f'<p class="rnote">Average over {s["reps"]} runs ± half-width of a 95% interval; differences are paired run by '
          'run (same random seeds). The intervals reflect simulation randomness only, not uncertainty in the data, the '
          'assumptions or how well a real intervention would work.</p>')

    def u(v, h, dp, sign=False):
        if not (RH.finite(v) and RH.finite(h)):
            return "Not estimable"
        return f"{v:{'+' if sign else ''},.{dp}f} ± {h:,.{dp}f}"

    groups = {"Bed Capacity": [("Bed occupancy (%)", "occupancy_pct", 1), ("Average beds occupied", "avg_occupied", 0),
                               ("Busiest day, beds occupied", "peak_occupied", 0), ("Occupied bed-days", "bed_days", 0)],
              "Patient Waiting": [("Bed requests that waited (%)", "waited_pct", 1),
                                  ("Average wait, all requests (days)", "mean_wait_days", 2),
                                  ("95th-percentile wait (days)", "p95_wait_days", 2),
                                  ("Largest daily queue", "peak_queue", 0)],
              "Admissions & Readmissions": [("New admissions per day", "avg_admissions_day", 1),
                                            ("Readmissions scheduled", "returns", 0)],
              "Patient Flow and Length of Stay": [("Average initial stay, target group (days)", "target_mean_los", 2),
                                                  ("Average initial stay, all patients (days)", "average_los", 2),
                                                  ("Stays shortened (target group)", "targeted_admissions", 0)]}
    for g, table in groups.items():
        rows = []
        for name, key, dp in table:
            (bm, bc), (sm, sc_) = M(key, "Baseline"), M(key, "Scenario")
            d, ci, cl = E(key)
            rows.append({"Measure": name, "Baseline": u(bm, bc, dp), "Your Scenario": u(sm, sc_, dp),
                         "Difference": u(d, ci, dp, True),
                         "Clear difference?": "Not estimable" if not RH.finite(d) else ("Yes" if cl else "No clear difference")})
        if g == "Bed Capacity":
            (bn, bc), (sn, sc_) = RV.nb("Baseline"), RV.nb("Scenario")
            d, ci, cl = RV.nb_effect()
            rows.append({"Measure": "Estimated beds needed on busy days (p95, no bed limit)", "Baseline": u(bn, bc, 0),
                         "Your Scenario": u(sn, sc_, 0), "Difference": u(d, ci, 0, True),
                         "Clear difference?": "Yes" if cl else "No clear difference"})
        st.markdown(f"**{g}**")
        st.dataframe(pd.DataFrame(rows), hide_index=True, **DF_KW)


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
nav_behaviour()
{"welcome": page_welcome, "overview": page_overview, "simulator": page_simulator, "results": page_results,
 "export": page_results, "downloads": page_results, "docs": page_docs}.get(ss.page, page_welcome)()
if ss.pop("page_changed", False) and not ss.pop("anchored", False):
    # Streamlit keeps the scroll position of the previous page; start a newly opened page at its top
    import streamlit.components.v1 as _components
    import time as _time
    # (repeated for ~1 s while the old page's elements are replaced; stops if the person scrolls or clicks)
    _components.html("<script>(function(){const D=window.parent.document;let k=0,stop=false;"
                     "['wheel','touchstart','keydown','mousedown'].forEach(e=>D.addEventListener(e,()=>{stop=true;},{once:true,capture:true}));"
                     "function go(){if(stop)return;const m=D.querySelector('[data-testid=\"stMain\"]');"
                     "if(m&&m.scrollTop>0)m.scrollTo({top:0,behavior:'instant'});"
                     "const se=D.scrollingElement;if(se&&se.scrollTop>0)se.scrollTop=0;if(k++<8)setTimeout(go,150);}go();})();</script>"
                     f"<!-- {_time.time_ns()} -->", height=0)
ss.pop("anchored", None)
if ss.page == "docs":                              # caveats live in Help and the documentation, not on every page
    render_footer()
