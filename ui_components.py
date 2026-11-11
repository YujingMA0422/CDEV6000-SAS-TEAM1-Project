"""Visual building blocks for the Hospital Capacity Planner (v3.1).

Presentation only - no model logic lives here. Every number passed in is computed elsewhere.
Type scale: page title 34px · section 22px · card value 40-46px · body 16px · supporting 14px.
"""
import html

import streamlit as st

# Colour system -------------------------------------------------------------------------------
NAVY = "#0B2545"
NAVY_2 = "#13365C"
TEAL = "#0E8A7E"
TEAL_DARK = "#0A6158"
TEAL_LIGHT = "#E3F3F0"
BASE = "#8EA2B6"          # Baseline (neutral blue-grey)
HIST = "#3A6390"          # historical data
AMBER = "#B7770A"
AMBER_LIGHT = "#FDF4E3"
WARM = "#D9822B"         # highest value highlight (warm, not alarm red)
WARM_DARK = "#A85F16"
GOOD = "#1E7F3A"
BAD = "#C0392B"
INK = "#14212E"
MUTED = "#5B6B7A"
LINE = "#E2E8EF"
PANEL = "#F5F7FA"
CANVAS = "#F5F7FA"
FONT = "Inter, 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, Roboto, 'Helvetica Neue', Arial, sans-serif"
HEAT = [[0, "#F1F6FA"], [0.5, "#7FB7C9"], [1, NAVY_2]]
HEAT_SEQ = [[0, "#EAF2FA"], [0.45, "#7EA8CF"], [1, "#0B2545"]]   # light blue -> navy: lower -> higher demand

_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">{}</svg>')
ICONS = {
    "admit": _SVG.format('<path d="M3 21V8l9-5 9 5v13"/><path d="M9 21v-6h6v6"/><path d="M12 8v4"/><path d="M10 10h4"/>'),
    "readmit": _SVG.format('<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 8v4l3 2"/>'),
    "chart": _SVG.format('<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>'),
    "sliders": _SVG.format('<path d="M4 6h10"/><path d="M18 6h2"/><circle cx="16" cy="6" r="2"/><path d="M4 12h4"/>'
                           '<path d="M12 12h8"/><circle cx="10" cy="12" r="2"/><path d="M4 18h12"/><path d="M20 18h0"/>'
                           '<circle cx="18" cy="18" r="2"/>'),
    "flow": _SVG.format('<path d="M3 12h4l2-5 4 10 2-5h6"/>'),
    "bed": _SVG.format('<path d="M3 18V7"/><path d="M3 14h18v4"/><path d="M21 14v-2a3 3 0 0 0-3-3h-7v5"/>'
                       '<circle cx="7" cy="11" r="2"/>'),
    "calendar": _SVG.format('<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18"/><path d="M8 3v4"/>'
                            '<path d="M16 3v4"/>'),
    "compare": _SVG.format('<rect x="3" y="4" width="7" height="16" rx="2"/><rect x="14" y="4" width="7" height="16" rx="2"/>'
                           '<path d="M6.5 14v2"/><path d="M17.5 10v6"/>'),
}

CSS = f"""
<style>
.stApp {{ background:{CANVAS}; color:{INK}; font-family:{FONT}; }}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp button p,
.stApp input, .stApp [data-testid="stMarkdownContainer"] {{ font-family:{FONT}; }}
[data-testid="stHeader"] {{ background:transparent; }}
[data-testid="stDecoration"] {{ display:none; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{ display:none; }}
.block-container {{ max-width:100% !important; padding-top:.8rem; padding-bottom:2.5rem; padding-left:3rem !important; padding-right:3rem !important; }}
@media (max-width: 760px) {{ .block-container {{ padding-left:1rem !important; padding-right:1rem !important; }} }}
h1, h2, h3, h4 {{ color:{NAVY}; font-family:{FONT}; letter-spacing:-0.01em; }}
p, li {{ font-size:1rem; line-height:1.55; }}
[data-testid="stWidgetLabel"] p {{ font-size:.98rem !important; font-weight:600 !important; color:{INK} !important; }}
[data-testid="stTabs"] button p {{ font-size:1.02rem !important; font-weight:650 !important; }}
[data-testid="stExpander"] summary p {{ font-size:.98rem !important; font-weight:600 !important; }}
[data-testid="stExpander"] details {{ background:#fff; border-radius:12px; }}

/* bordered containers become white cards on the light canvas */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ background:#fff; border-radius:16px; }}
.st-key-card, [class*="st-key-card"] {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:18px 20px 12px; }}

/* ---------------- top navigation (v3.3) ---------------- */
.st-key-topnav {{ background:rgba(255,255,255,.94); border:1px solid #E8EDF3; border-radius:16px;
  padding:8px 12px 8px 24px; margin-bottom:1.4rem; box-shadow:0 1px 2px rgba(16,39,66,.03); }}
.brand {{ font-weight:650; color:{NAVY}; font-size:1.3rem; letter-spacing:-0.015em; white-space:nowrap; }}
.st-key-navlinks {{ padding:0 8px; }}
.st-key-navlinks button {{ border-radius:999px !important; min-height:2.4rem; padding:0 16px !important; border:none !important;
  transition:background-color .18s ease, color .18s ease; }}
.st-key-navlinks button p {{ font-size:1rem !important; font-weight:500 !important; white-space:nowrap; letter-spacing:-0.005em; }}
.st-key-navlinks [data-testid="stBaseButton-tertiary"], .st-key-navlinks button[kind="tertiary"] {{ color:{MUTED} !important; background:transparent !important; }}
.st-key-navlinks [data-testid="stBaseButton-tertiary"]:hover, .st-key-navlinks button[kind="tertiary"]:hover {{
  background:#F0F3F7 !important; color:{NAVY} !important; }}
.st-key-navlinks [data-testid="stBaseButton-primary"], .st-key-navlinks button[kind="primary"] {{
  background:#EDF2F8 !important; color:{NAVY} !important; box-shadow:none !important; }}
.st-key-navlinks [data-testid="stBaseButton-primary"] p, .st-key-navlinks button[kind="primary"] p {{ font-weight:650 !important; }}
/* Export + Help: quieter than the main links */
.st-key-navactions button {{ border-radius:999px !important; min-height:2.1rem; padding:0 12px !important;
  transition:background-color .18s ease, color .18s ease; }}
.st-key-navactions button p {{ font-size:.9rem !important; font-weight:500 !important; white-space:nowrap; }}
.st-key-navactions [data-testid="stBaseButton-tertiary"], .st-key-navactions button[kind="tertiary"] {{ color:#7A8A9A !important; border:none !important; }}
.st-key-navactions [data-testid="stBaseButton-tertiary"]:hover, .st-key-navactions button[kind="tertiary"]:hover {{
  background:#F0F3F7 !important; color:{NAVY} !important; }}
.st-key-navactions [data-testid="stBaseButton-primary"], .st-key-navactions button[kind="primary"] {{
  background:#EDF2F8 !important; color:{NAVY} !important; border:none !important; }}
.st-key-navactions [data-testid="stPopover"] button, .st-key-navactions [data-testid="stPopoverButton"] {{
  border:1px solid #E3E8EE !important; background:transparent !important; color:#7A8A9A !important; min-height:2.1rem; }}
.st-key-navactions [data-testid="stPopover"] button:hover {{ color:{NAVY} !important; background:#F0F3F7 !important; }}
.st-key-topnav button:focus-visible {{ outline:2px solid {TEAL} !important; outline-offset:2px; }}
.helpbox {{ max-width:380px; }}
.helpbox .hb-t {{ font-weight:700; color:{NAVY}; font-size:.95rem; margin:.2rem 0 .15rem; }}
.helpbox p {{ color:{MUTED}; font-size:.9rem; line-height:1.5; margin:0 0 .7rem; }}
.helpbox .hb-v {{ font-size:.78rem; color:#8696A6; }}

/* ---------------- welcome (v3.3) ---------------- */
.hero2 {{ position:relative; overflow:hidden; background:{NAVY}; border-radius:24px; padding:58px 64px 56px; margin:0 0 2.4rem;
  box-shadow:0 10px 28px rgba(16,39,66,.10); }}
.hero2::after {{ content:""; position:absolute; right:-10%; bottom:-60%; width:55%; height:140%;
  background:radial-gradient(closest-side, rgba(17,143,133,.24), rgba(17,143,133,0)); pointer-events:none; }}
.hero2 h1 {{ position:relative; z-index:1; color:#fff !important; font-size:clamp(2.3rem, 4.2vw, 3.7rem) !important;
  line-height:1.06 !important; letter-spacing:-0.03em; font-weight:750 !important; margin:0 0 16px !important; padding:0 !important; }}
.hero2 p {{ position:relative; z-index:1; color:#D3DEEA; font-size:clamp(1.06rem, 1.35vw, 1.28rem); line-height:1.55;
  max-width:760px; margin:0; }}
.wh2 {{ font-size:1.85rem !important; font-weight:750 !important; color:{NAVY} !important; letter-spacing:-0.02em;
  margin:0 0 1rem !important; padding:0 !important; }}
/* equal-height cards: columns stretch, card fills its column, action sits on the bottom */
[data-testid="stHorizontalBlock"]:has([class*="st-key-howcard_"]) {{ align-items:stretch; }}
[data-testid="stColumn"]:has([class*="st-key-howcard_"]) > div,
[data-testid="column"]:has([class*="st-key-howcard_"]) > div {{ height:100%; }}
[class*="st-key-howcard_"] {{ position:relative; height:100%; background:#fff; border:1px solid #E6EBF1; border-radius:20px;
  padding:22px 22px 20px; box-shadow:0 1px 3px rgba(16,39,66,.05); cursor:pointer;
  transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease; }}
[class*="st-key-howcard_"]:hover {{ transform:translateY(-2px); box-shadow:0 8px 22px rgba(16,39,66,.09); border-color:#D3DCE6; }}
.st-key-howcard_explore {{ border-color:#CFE7E3; }}
.st-key-howcard_explore:hover {{ border-color:#A9D6CF; }}
/* whole card clickable: the card's real button stretches an invisible hit area over the card */
[class*="st-key-howcard_"] [data-testid="stElementContainer"], [class*="st-key-howcard_"] [data-testid="stButton"],
[class*="st-key-howcard_"] .stButton, [class*="st-key-howcard_"] [data-testid="stTooltipHoverTarget"],
[class*="st-key-howcard_"] button {{ position:static !important; }}
[class*="st-key-howcard_"] [data-testid="stElementContainer"]:last-child {{ margin-top:auto; }}
[class*="st-key-howcard_"] button::after {{ content:""; position:absolute; inset:0; border-radius:20px; }}
[class*="st-key-howcard_"]:has(button:focus-visible) {{ outline:2px solid {TEAL}; outline-offset:3px; }}
[class*="st-key-howcard_"] button {{ border-radius:999px !important; min-height:2.5rem; padding:0 18px !important;
  transition:background-color .18s ease, color .18s ease; }}
[class*="st-key-howcard_"] button p {{ font-weight:650 !important; font-size:.97rem !important; white-space:nowrap; }}
[class*="st-key-howcard_"] [data-testid="stBaseButton-secondary"], [class*="st-key-howcard_"] button[kind="secondary"] {{
  background:{TEAL_LIGHT} !important; border:none !important; color:{TEAL_DARK} !important; }}
[class*="st-key-howcard_"]:hover [data-testid="stBaseButton-secondary"], [class*="st-key-howcard_"]:hover button[kind="secondary"] {{
  background:#CFEAE5 !important; }}
.hc-top {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }}
.hc-icon {{ width:46px; height:46px; border-radius:14px; background:{TEAL_LIGHT}; color:{TEAL_DARK}; display:flex;
  align-items:center; justify-content:center; }}
.hc-icon svg {{ width:25px; height:25px; }}
.hc-start {{ font-size:.72rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{TEAL_DARK};
  background:{TEAL_LIGHT}; border-radius:999px; padding:4px 10px; }}
.hc-title {{ font-size:1.4rem; font-weight:720; color:{NAVY}; letter-spacing:-0.015em; margin-bottom:6px; }}
.hc-desc {{ font-size:1.02rem; color:{MUTED}; line-height:1.5; min-height:3em; margin-bottom:16px; }}
@media (max-width: 900px) {{ .hero2 {{ padding:40px 28px; }} }}
/* ---------------- historical overview (v3.4) ---------------- */
.periodchip {{ display:inline-block; margin-top:.7rem; background:#fff; border:1px solid {LINE}; border-radius:999px;
  padding:4px 12px; font-size:.85rem; color:{MUTED}; cursor:help; }}
.qhead {{ display:flex; align-items:baseline; gap:14px; margin:2.6rem 0 1rem; }}
.qhead .qn {{ flex:none; width:34px; height:34px; border-radius:50%; background:{NAVY}; color:#fff; font-weight:750;
  font-size:1rem; display:flex; align-items:center; justify-content:center; transform:translateY(-3px); }}
.qhead h2 {{ font-size:1.75rem !important; font-weight:750 !important; letter-spacing:-0.02em; margin:0 !important;
  padding:0 !important; color:{NAVY} !important; }}
.qhead span {{ color:{MUTED}; font-size:.95rem; }}
.lead {{ color:{MUTED}; font-size:1.02rem; margin:-.4rem 0 .6rem; }}
.info {{ color:{TEAL_DARK}; cursor:help; font-weight:600; }}
.fcard {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:20px 24px 18px;
  box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.fcard .ft {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.15rem; color:{NAVY}; margin-bottom:14px; }}
.fcard .dot {{ width:12px; height:12px; border-radius:4px; }}
.fflow {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.fflow .fs {{ flex:1; min-width:120px; }}
.fflow .fs span {{ display:block; font-size:.78rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:{MUTED}; }}
.fflow .fs b {{ font-size:1.65rem; font-weight:760; color:{NAVY}; letter-spacing:-0.02em; }}
.fflow .fs.res b {{ color:{TEAL_DARK}; }}
.fflow .op {{ color:#A9B6C3; font-size:1.3rem; }}
.fcard .fn {{ margin-top:12px; padding-top:10px; border-top:1px solid #EEF2F6; color:{MUTED}; font-size:.92rem; }}
.fcard .fn b {{ color:{NAVY}; }}
.pbar {{ margin:22px 0 4px; clear:both; }}
.pbar .track {{ display:flex; height:16px; border-radius:999px; overflow:hidden; background:#E8EDF3; }}
.pbar .lg {{ display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-top:8px; font-size:.92rem; color:{MUTED}; }}
.pbar .lg b {{ color:{NAVY}; }}
.pbar i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; }}
.st-key-ovprofile {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:18px 20px 12px;
  box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.pfb {{ margin:.4rem 0 .6rem; }}
.pfb .pt {{ font-size:.78rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{MUTED}; margin-bottom:4px; }}
.pfb .pr {{ display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #F0F3F7; font-size:.95rem; }}
.pfb .pr span {{ color:{MUTED}; }} .pfb .pr b {{ color:{INK}; }}
.agetag {{ background:#EEF2F7; color:{MUTED}; border-radius:999px; padding:1px 7px; font-size:.68rem; letter-spacing:.04em; }}
.pf-total {{ display:flex; align-items:baseline; gap:10px; background:{TEAL_LIGHT}; border-radius:12px; padding:10px 14px; margin:.4rem 0 .6rem; }}
.pf-total span {{ color:{TEAL_DARK}; font-weight:650; font-size:.92rem; flex:1; }}
.pf-total b {{ color:{NAVY}; font-size:1.3rem; }} .pf-total small {{ color:{MUTED}; }}
.st-key-ovstart {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:18px 22px 8px;
  box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.startlbl {{ font-weight:700; color:{NAVY}; font-size:1.05rem; margin-bottom:.3rem; }}

/* ---------------- welcome attribution (v3.4) ---------------- */
.attrib {{ margin-top:2.2rem; padding-top:1rem; border-top:1px solid #E6EBF1; color:#8494A5; font-size:.88rem;
  letter-spacing:.01em; }}
/* ---------------- historical overview refinement (v3.5) ---------------- */
.ovhead {{ margin:.2rem 0 .4rem; }}
.ovhead h1 {{ font-size:clamp(2rem, 3vw, 2.6rem) !important; font-weight:760 !important; letter-spacing:-0.025em;
  color:{NAVY} !important; margin:0 0 .35rem !important; padding:0 !important; }}
.ovhead p {{ color:{MUTED}; font-size:1.12rem; margin:0 0 .7rem; }}
.ovhead .periodchip {{ margin-top:0; font-size:.88rem; color:#55677A; cursor:default; }}
.qh {{ display:flex; align-items:center; gap:12px; margin:2.3rem 0 1rem; }}
.qh .qi {{ font-size:.85rem; font-weight:700; color:{TEAL_DARK}; background:{TEAL_LIGHT}; border-radius:8px;
  padding:3px 8px; font-variant-numeric:tabular-nums; }}
.qh h2 {{ font-size:clamp(1.5rem, 2.1vw, 1.8rem) !important; font-weight:750 !important; letter-spacing:-0.02em;
  color:{NAVY} !important; margin:0 !important; padding:0 !important; line-height:1.2 !important; }}
.tip {{ color:#7D9AB0; cursor:help; font-weight:500; font-size:.85em; }}
.sc2 .sub span.tip, .sc2 .sub > div > span .tip, .gc .sec span.tip, .gc .prim span.tip, .gc .prim span.agetag, .gc .sec span.agetag {{ display:inline !important; min-height:0 !important; margin:0 0 0 3px; }}
.sc2 {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:22px 24px 20px; box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.sc2 .hd {{ display:flex; align-items:center; gap:10px; color:{NAVY}; font-weight:680; font-size:1.08rem; }}
.sc2 .ic {{ width:36px; height:36px; border-radius:11px; display:flex; align-items:center; justify-content:center; }}
.sc2 .ic svg {{ width:20px; height:20px; }}
.sc2 .ic.teal {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }} .sc2 .ic.navy {{ background:#E5ECF5; color:{NAVY_2}; }}
.sc2 .big {{ font-size:2.7rem; font-weight:780; letter-spacing:-0.03em; color:{NAVY}; line-height:1.1; margin:14px 0 2px; }}
.sc2 .big small {{ font-size:1rem; font-weight:550; color:{MUTED}; letter-spacing:0; margin-left:6px; }}
.sc2 .sub {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:14px 16px; margin-top:16px; padding-top:14px; border-top:1px solid #EEF2F6; }}
.sc2 .sub.n4 {{ grid-template-columns:repeat(4, 1fr); }}
@media (max-width: 1300px) {{ .sc2 .sub.n4 {{ grid-template-columns:repeat(2, 1fr); }} }}
@media (max-width: 640px) {{ .sc2 .sub, .sc2 .sub.n4 {{ grid-template-columns:repeat(2, 1fr); }} }}
.sc2 .sub > div {{ display:flex; flex-direction:column; justify-content:space-between; }}
.sc2 .sub > div > span {{ display:block; font-size:.9rem; color:#46586A; font-weight:550; margin-bottom:4px; line-height:1.3; min-height:2.6em; }}
.sc2 .sub b {{ font-size:1.42rem; color:{NAVY}; font-weight:740; letter-spacing:-0.01em; }}
.tbar {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:18px 24px; margin-top:16px;
  box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.tbar .top {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:12px; }}
.tbar .top b {{ font-size:1.9rem; font-weight:780; color:{NAVY}; letter-spacing:-0.02em; }}
.tbar .top span {{ color:{MUTED}; font-size:1rem; }}
.tbar .track {{ display:flex; height:14px; border-radius:999px; overflow:hidden; }}
.tbar .lg {{ display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-top:10px; font-size:.95rem; color:{MUTED}; }}
.tbar .lg b {{ color:{NAVY}; font-size:1.05rem; }}
.tbar i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:7px; }}
.charttitle {{ font-weight:700; color:{NAVY}; font-size:1.1rem; }}
.chartsub {{ color:{MUTED}; font-size:.9rem; }}
.terms {{ font-size:.92rem; min-width:290px; }}
.terms table {{ border-collapse:collapse; width:100%; margin:.2rem 0 .7rem; }}
.terms td {{ padding:5px 8px 5px 0; border-bottom:1px solid #EEF2F6; vertical-align:top; }}
.terms td:first-child {{ font-weight:700; color:{NAVY}; white-space:nowrap; width:56px; }}
.terms .tt {{ font-size:.75rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{MUTED}; margin-top:.2rem; }}
.terms .tn {{ color:{MUTED}; font-size:.82rem; }}
.gc .gname {{ font-size:1.45rem; font-weight:750; color:{NAVY}; letter-spacing:-0.015em; margin:.3rem 0 .8rem; }}
.gc .prim {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }}
.gc .prim div {{ background:{PANEL}; border-radius:14px; padding:12px 14px; }}
.gc .prim span {{ display:block; font-size:.8rem; color:{MUTED}; line-height:1.3; min-height:2.1em; }}
.gc .prim b {{ font-size:1.4rem; font-weight:760; color:{NAVY}; letter-spacing:-0.01em; }}
.gc .sec {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:12px; padding:0 4px; }}
.gc .sec span {{ display:block; font-size:.8rem; color:{MUTED}; }}
.gc .sec b {{ font-size:1.05rem; color:{INK}; font-weight:650; }}
.gc .why {{ margin-top:16px; border-left:3px solid {TEAL}; padding:2px 0 2px 14px; }}
.gc .why .wl {{ font-size:.78rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{TEAL_DARK}; }}
.gc .why p {{ margin:.2rem 0 0; font-size:1.02rem; color:{INK}; line-height:1.5; }}
.ki {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:20px 22px; box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.ki .kl {{ font-size:.78rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; color:{TEAL_DARK}; margin-bottom:12px; }}
.ki .kr {{ display:flex; justify-content:space-between; align-items:baseline; padding:10px 0; border-bottom:1px solid #EEF2F6; }}
.ki .kr span {{ font-size:.85rem; color:{MUTED}; display:block; }}
.ki .kr b {{ font-size:1.3rem; color:{NAVY}; font-weight:740; }}
.ki .kr em {{ font-style:normal; font-size:1.1rem; color:{INK}; font-weight:650; }}
.ki .kr em small {{ color:{MUTED}; font-weight:500; font-size:.8rem; }}
.ki p {{ margin:12px 0 0; color:{INK}; font-size:.98rem; line-height:1.5; }}
.st-key-ovcta {{ background:#fff; border:1px solid #E6EBF1; border-radius:22px; padding:20px 26px 14px; margin-top:2.4rem;
  box-shadow:0 6px 20px rgba(16,39,66,.06); border-left:5px solid {TEAL}; }}
.ctah {{ font-size:1.5rem; font-weight:750; color:{NAVY}; letter-spacing:-0.015em; }}
.ctas {{ color:{MUTED}; font-size:1rem; margin:.15rem 0 .55rem; }}
/* ---------------- hierarchical explorer (v3.6) ---------------- */
.st-key-crumbs {{ margin:-.3rem 0 .6rem; }}
.st-key-crumbs button {{ padding:0 6px !important; min-height:1.9rem !important; }}
.st-key-crumbs button p {{ font-size:.95rem !important; font-weight:600 !important; color:{TEAL_DARK}; }}
.st-key-crumbs button:disabled p {{ color:{NAVY} !important; }}
.crsep {{ color:#A9B6C3; margin:0 2px; }} .crcur {{ color:{NAVY}; font-weight:650; font-size:.95rem; padding:0 6px; }}
.lvl {{ font-weight:700; color:{NAVY}; font-size:1.05rem; margin:.2rem 0 .55rem; }}
.lvl span {{ color:{MUTED}; font-weight:500; font-size:.9rem; }}
.emptylvl {{ background:#fff; border:1px dashed #CBD5E0; border-radius:16px; padding:28px; color:{MUTED}; text-align:center; }}
[class*="st-key-pick_"] {{ position:relative; background:#fff; border:1px solid #E6EBF1; border-radius:18px; cursor:pointer;
  box-shadow:0 1px 3px rgba(16,39,66,.05); transition:border-color .18s ease, box-shadow .18s ease, background-color .18s ease; }}
[class*="st-key-pick_dx_"] {{ padding:16px 18px 6px; }}
[class*="st-key-pick_sev_"] {{ padding:10px 16px 2px; margin-bottom:-4px; border-radius:14px; }}
[class*="st-key-pick_"]:hover {{ border-color:#BFD0DF; box-shadow:0 6px 18px rgba(16,39,66,.08); }}
[class*="st-key-pick_"][class*="_on"] {{ border:2px solid {TEAL}; background:#F6FBFA; }}
[class*="st-key-pick_"] [data-testid="stElementContainer"], [class*="st-key-pick_"] [data-testid="stButton"],
[class*="st-key-pick_"] .stButton, [class*="st-key-pick_"] [data-testid="stTooltipHoverTarget"],
[class*="st-key-pick_"] button {{ position:static !important; }}
[class*="st-key-pick_"] button::after {{ content:""; position:absolute; inset:0; border-radius:16px; }}
[class*="st-key-pick_"]:has(button:focus-visible) {{ outline:2px solid {TEAL}; outline-offset:2px; }}
[class*="st-key-pick_"] button p {{ font-size:.9rem !important; font-weight:650 !important; color:{TEAL_DARK}; }}
[class*="st-key-pick_sev_"] button {{ min-height:0 !important; height:2px; padding:0 !important; border:none !important; background:none !important; }}
[class*="st-key-pick_sev_"] button p {{ position:absolute !important; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }}
.dxc .dn {{ display:flex; align-items:baseline; gap:8px; }}
.dxc .dn b {{ font-size:1.35rem; color:{NAVY}; font-weight:760; }}
.dxc .dn span {{ color:{MUTED}; font-size:.85rem; }}
.dxc .dv {{ font-size:1.7rem; font-weight:770; color:{NAVY}; letter-spacing:-0.02em; margin:8px 0 0; }}
.dxc .dv small {{ font-size:.9rem; color:{MUTED}; font-weight:500; margin-left:4px; }}
.dxc .bar {{ height:8px; background:#EDF1F5; border-radius:999px; overflow:hidden; margin:8px 0 6px; }}
.dxc .bar div {{ height:100%; background:#9DB3C9; border-radius:999px; }}
.dxc.on .bar div {{ background:{TEAL}; }}
.dxc .ds {{ color:{MUTED}; font-size:.86rem; }}
.dxc .ds b {{ color:{INK}; }}
.sevr {{ display:grid; grid-template-columns:150px 1fr 140px 76px; align-items:center; gap:12px; padding:4px 0 6px; }}
.sevr .act {{ text-align:right; font-size:.85rem; font-weight:650; color:{TEAL_DARK}; }}
.sevr .sl b {{ color:{NAVY}; font-size:1rem; }} .sevr .sl span {{ color:{MUTED}; font-size:.82rem; margin-left:4px; }}
.sevr .bar {{ height:10px; background:#EDF1F5; border-radius:999px; overflow:hidden; }}
.sevr .bar div {{ height:100%; background:#9DB3C9; border-radius:999px; }}
.sevr.on .bar div {{ background:{TEAL}; }}
.sevr .sv {{ text-align:right; font-size:.92rem; color:{MUTED}; }} .sevr .sv b {{ color:{INK}; font-size:1rem; }}
.agec {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:.6rem 0 .2rem; }}
.agec > div {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:14px 16px; }}
.agec > div.on {{ border:2px solid {TEAL}; background:#F6FBFA; }}
.agec .ah {{ font-weight:700; color:{NAVY}; margin-bottom:6px; display:flex; justify-content:space-between; }}
.agec .ah span {{ color:{TEAL_DARK}; font-size:.95rem; }}
.agec .ar {{ display:flex; justify-content:space-between; font-size:.9rem; padding:3px 0; color:{MUTED}; }}
.agec .ar b {{ color:{INK}; }}
.cap {{ margin-top:12px; display:grid; gap:8px; }}
.cap div {{ display:flex; justify-content:space-between; align-items:baseline; background:{PANEL}; border-radius:12px; padding:9px 14px; }}
.cap span {{ color:{MUTED}; font-size:.88rem; }} .cap b {{ color:{NAVY}; font-size:1.1rem; }}
.cap small {{ color:{MUTED}; font-weight:500; font-size:.78rem; }}
.st-key-slcap {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:10px 16px; margin:.2rem 0 1.4rem; }}
.slcap {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 18px; font-size:.95rem; }}
.slcap .sl-l {{ font-weight:700; color:{NAVY}; }} .slcap .sl-v b {{ color:{NAVY}; }}
.slcap .sl-v, .slcap .sl-s {{ color:{MUTED}; }} .slcap .sl-s b {{ color:{TEAL_DARK}; }}
.need {{ color:{AMBER} !important; }}
@media (max-width: 900px) {{ .sevr {{ grid-template-columns:110px 1fr 70px; }} .sevr .sv {{ display:none; }} }}
/* ---------------- historical overview v3.7 ---------------- */
.ovhead .periodchip {{ font-size:.95rem !important; color:{NAVY} !important; background:#fff; font-weight:600; padding:6px 14px !important; }}
.tip {{ position:relative; display:inline-block; }}
.tip:hover::after, .tip:focus::after {{ content:attr(data-tip); position:absolute; z-index:50; left:50%; bottom:135%;
  transform:translateX(-50%); width:max-content; max-width:280px; white-space:normal; background:{NAVY}; color:#fff;
  font-size:.82rem; font-weight:500; line-height:1.45; padding:8px 11px; border-radius:10px; box-shadow:0 6px 18px rgba(16,39,66,.18);
  text-transform:none; letter-spacing:0; text-align:left; }}
.tip:focus {{ outline:2px solid {TEAL}; border-radius:50%; }}
.tbar .top {{ align-items:baseline; }} .tbar .top .tl {{ font-weight:700; color:{NAVY}; font-size:1.05rem; margin-right:6px; }}
.bigins {{ font-size:1.3rem; font-weight:680; color:{NAVY}; line-height:1.4; letter-spacing:-0.01em; margin:.1rem 0 1rem;
  padding-left:14px; border-left:4px solid {TEAL}; }}
.bigins.sm {{ font-size:1.12rem; margin:.2rem 0 .8rem; }}
.lvl2 {{ font-weight:740; color:{NAVY}; font-size:1.18rem; margin:.2rem 0 .5rem; }}
.selnote {{ display:inline-block; margin:.6rem 0 .4rem; background:{TEAL_LIGHT}; color:{TEAL_DARK}; font-weight:650;
  font-size:.92rem; border-radius:999px; padding:5px 14px; }}
.dxc .dn b {{ font-size:1.15rem !important; }}
.pfh {{ margin-bottom:.5rem; }} .pfh span {{ display:block; font-size:.78rem; font-weight:750; letter-spacing:.07em;
  text-transform:uppercase; color:{TEAL_DARK}; }} .pfh b {{ font-size:1.45rem; color:{NAVY}; font-weight:760; letter-spacing:-0.015em; }}
.mg {{ margin-top:.6rem; }}
.mgp {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }}
.mgp .p {{ background:{PANEL}; border-radius:14px; padding:12px 14px; }}
.mgp .p span, .mgs .s span {{ display:block; font-size:.86rem; color:#46586A; font-weight:550; line-height:1.3; min-height:2.2em; }}
.mgp .p b {{ font-size:1.5rem; color:{NAVY}; font-weight:770; letter-spacing:-0.01em; }}
.mgs {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:10px; padding:0 4px; }}
.mgs .s b {{ font-size:1.2rem; color:{INK}; font-weight:700; }}
.mg .age {{ box-shadow:inset 3px 0 0 {TEAL}; }}
.mgs .s.age {{ box-shadow:none; }} .mgs .s.age b {{ color:{TEAL_DARK}; }}
.mgp .p span .tip, .mgs .s span .tip {{ display:inline-block; min-height:0; }}
.pfnote {{ color:#46586A; font-size:.9rem; margin:.5rem 0 0; }}
.pflegend {{ font-size:.84rem; color:#46586A; margin:.1rem 0 .2rem; }} .pflegend i {{ display:inline-block; width:3px; height:12px; background:{TEAL}; border-radius:2px; margin-right:7px; vertical-align:-1px; }}
.agestrip {{ margin-top:14px; }} .agestrip .al {{ font-size:.86rem; font-weight:650; color:#46586A; margin-bottom:6px; }}
.agestrip .track {{ display:flex; height:12px; border-radius:999px; overflow:hidden; background:#EDF1F5; }}
.agestrip .track div {{ background:#B5C4D3; }} .agestrip .track div.o {{ background:#8DA3B8; }}
.agestrip .track div.on {{ background:{TEAL} !important; }}
.agestrip .lg {{ display:flex; justify-content:space-between; font-size:.88rem; color:{MUTED}; margin-top:5px; }}
.agestrip .lg b {{ color:{NAVY}; }}
.gi {{ margin-top:16px; border-left:3px solid {TEAL}; padding:2px 0 2px 14px; }}
.gi .gil {{ font-size:.8rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{TEAL_DARK}; }}
.gi p {{ margin:.25rem 0 0; font-size:1.05rem; color:{INK}; line-height:1.5; }}
.st-key-ovprofile [data-testid="stButtonGroup"] {{ margin-top:.2rem; }}
.tins {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:18px 22px; margin:.4rem 0 .6rem;
  box-shadow:0 1px 3px rgba(16,39,66,.05); }}
.tins .th {{ font-size:1.35rem; font-weight:720; color:{NAVY}; letter-spacing:-0.015em; margin-bottom:12px; }}
.tstats {{ display:flex; flex-wrap:wrap; align-items:stretch; gap:12px; }}
.tstats > div {{ border-radius:14px; padding:10px 16px; min-width:190px; }}
.tstats .hi {{ background:#FDF1E6; }} .tstats .lo {{ background:{TEAL_LIGHT}; }}
.tstats span {{ display:block; font-size:.78rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; }}
.tstats .hi span {{ color:{WARM_DARK}; }} .tstats .lo span {{ color:{TEAL_DARK}; }}
.tstats b {{ display:block; font-size:1.2rem; color:{NAVY}; }} .tstats em {{ font-style:normal; font-size:1.05rem; font-weight:700; color:{INK}; }}
.tplan {{ flex:1; min-width:240px; margin:0; align-self:center; font-size:1rem; color:{INK}; line-height:1.5; }}
.tnote {{ margin:.7rem 0 0; font-size:.9rem; color:#5E4100; }}
.ctas a.chg {{ color:{TEAL_DARK}; font-weight:650; margin-left:6px; text-decoration:none; }}
.ctas a.chg:hover {{ text-decoration:underline; }}
@media (prefers-reduced-motion: reduce) {{
  [class*="st-key-howcard_"], [class*="st-key-howcard_"]:hover, .st-key-topnav button {{ transition:none !important; transform:none !important; }}
}}

/* sticky scenario summary on the simulator */
.st-key-summary {{ position:sticky; top:4.2rem; }}

/* page title */
.ptitle {{ margin:.2rem 0 1.1rem; }}
.ptitle .eyebrow {{ color:{TEAL}; font-weight:750; font-size:.8rem; letter-spacing:.12em; text-transform:uppercase; }}
.ptitle h1 {{ font-size:2.15rem !important; margin:.1rem 0 .3rem !important; padding:0 !important; font-weight:750; line-height:1.15; }}
.ptitle p {{ color:{MUTED}; margin:0; font-size:1.05rem; max-width:860px; }}
.sect {{ display:flex; align-items:center; gap:10px; margin:1.6rem 0 .7rem; }}
.sect::before {{ content:""; width:5px; height:24px; border-radius:3px; background:{TEAL}; }}
.sect h2 {{ font-size:1.4rem !important; margin:0 !important; padding:0 !important; font-weight:720; }}
.sect span {{ color:{MUTED}; font-size:.92rem; margin-left:6px; }}
.note {{ color:{MUTED}; font-size:.9rem; line-height:1.5; margin:.3rem 0 .4rem; }}
.note b {{ color:{INK}; }}

/* welcome */
.hero {{ background:{NAVY}; border-radius:22px; padding:52px 56px 46px; margin:.2rem 0 1.4rem; position:relative; overflow:hidden; }}
.hero::after {{ content:""; position:absolute; right:-80px; top:-80px; width:320px; height:320px; border-radius:50%; background:rgba(14,138,126,.22); }}
.hero .kicker {{ color:#8EDFD3; font-size:.8rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase; margin-bottom:14px; }}
.hero h1 {{ color:#fff !important; font-size:3rem !important; line-height:1.08; margin:0 0 14px !important; padding:0 !important; font-weight:800; }}
.hero p {{ color:#DCE6F0; font-size:1.25rem; max-width:900px; margin:0 0 26px; line-height:1.5; }}
.flow {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; position:relative; z-index:1; }}
.flow .s {{ background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18); border-radius:12px; padding:10px 16px; color:#fff; }}
.flow .s b {{ display:block; font-size:1.05rem; }}
.flow .s span {{ color:#B9C9D9; font-size:.86rem; }}
.flow .arr {{ color:#8EDFD3; font-size:1.3rem; }}
.how {{ display:flex; align-items:stretch; gap:10px; margin:.2rem 0 1.6rem; }}
.howcard {{ flex:1; background:#fff; border:1px solid {LINE}; border-radius:18px; padding:28px 28px 26px; }}
.howcard .num {{ display:inline-flex; align-items:center; justify-content:center; width:44px; height:44px; border-radius:50%;
  background:{NAVY}; color:#fff; font-weight:800; font-size:1.2rem; margin-bottom:16px; }}
.howcard h4 {{ margin:0 0 8px !important; padding:0 !important; font-size:1.5rem !important; color:{NAVY}; font-weight:750; }}
.howcard p {{ margin:0; color:{MUTED}; font-size:1.08rem; line-height:1.55; }}
.howarr {{ display:flex; align-items:center; color:{TEAL}; font-size:1.8rem; font-weight:700; }}
@media (max-width: 760px) {{ .how {{ flex-direction:column; }} .howarr {{ justify-content:center; transform:rotate(90deg); }} }}
.notice {{ color:{MUTED}; font-size:.9rem; margin-top:1rem; }}

/* stat tiles */
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin:.2rem 0 .6rem; }}
.tile {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:16px 18px; }}
.tile .l {{ color:{MUTED}; font-size:.86rem; font-weight:650; }}
.tile .v {{ color:{NAVY}; font-size:2rem; font-weight:780; line-height:1.15; margin:4px 0 2px; }}
.tile .v small {{ font-size:.95rem; font-weight:600; color:{MUTED}; }}
.tile .n {{ color:{MUTED}; font-size:.84rem; line-height:1.4; }}
.tile.accent {{ border-left:4px solid {TEAL}; }}

/* insight line */
.insight1 {{ background:{TEAL_LIGHT}; border-radius:12px; padding:12px 16px; color:{INK}; font-size:1rem; margin:.3rem 0 .8rem; }}
.insight1 b {{ color:{NAVY}; }}
.caution {{ background:{AMBER_LIGHT}; border-radius:12px; padding:10px 14px; color:#5E4100; font-size:.92rem; margin:.4rem 0 .6rem; }}

/* simulator */
.step {{ display:flex; align-items:center; gap:12px; margin:.1rem 0 .5rem; }}
.step .n {{ flex:none; width:32px; height:32px; border-radius:50%; background:{NAVY}; color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; }}
.step h3 {{ margin:0 !important; padding:0 !important; font-size:1.25rem !important; font-weight:720; }}
.scope {{ font-size:.72rem; font-weight:800; letter-spacing:.07em; text-transform:uppercase; border-radius:999px; padding:3px 10px; margin-left:auto; white-space:nowrap; }}
.scope.group {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }}
.scope.all {{ background:#E5ECF5; color:{NAVY_2}; }}
.facts {{ display:flex; flex-wrap:wrap; gap:8px; margin:.2rem 0 .3rem; }}
.facts div {{ background:{PANEL}; border-radius:10px; padding:7px 12px; font-size:.9rem; color:{MUTED}; }}
.facts b {{ color:{NAVY}; font-size:1.05rem; }}
.ctx {{ color:{MUTED}; font-size:.9rem; margin:.1rem 0 .6rem; }}
.calc {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:.3rem 0 .2rem; }}
.calc div {{ text-align:center; background:{PANEL}; border-radius:12px; padding:8px 14px; min-width:110px; }}
.calc span {{ display:block; font-size:.72rem; font-weight:800; letter-spacing:.07em; text-transform:uppercase; color:{MUTED}; }}
.calc b {{ font-size:1.45rem; color:{NAVY}; }}
.calc .sc {{ background:{TEAL_LIGHT}; }} .calc .sc b {{ color:{TEAL_DARK}; }}
.calc i {{ color:{MUTED}; font-style:normal; font-size:1.2rem; }}
.bigbeds {{ background:{NAVY}; color:#fff; border-radius:14px; padding:12px 18px; }}
.bigbeds span {{ display:block; font-size:.74rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:#A9C0D6; }}
.bigbeds b {{ font-size:2.1rem; line-height:1.1; }}
.bigbeds small {{ color:#C8D6E4; font-size:.86rem; }}
.sumpanel {{ background:#fff; border:1px solid {LINE}; border-top:5px solid {TEAL}; border-radius:16px; padding:16px 18px 6px; }}
.sumpanel h4 {{ margin:0 0 .6rem !important; padding:0 !important; font-size:1.15rem !important; }}
.sumrow {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid {LINE}; font-size:.93rem; }}
.sumrow:last-child {{ border-bottom:none; }}
.sumrow span {{ color:{MUTED}; }} .sumrow b {{ color:{INK}; text-align:right; }}
.tag {{ display:inline-block; font-size:.66rem; font-weight:800; letter-spacing:.06em; border-radius:999px; padding:1px 7px; margin-left:6px; vertical-align:2px; }}
.tag.group {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }} .tag.all {{ background:#E5ECF5; color:{NAVY_2}; }}
.status-ok {{ color:{TEAL_DARK}; font-weight:650; font-size:.92rem; }}
.status-stale {{ color:#8A5A00; font-weight:650; font-size:.92rem; }}

/* results: key message */
.keymsg {{ background:{NAVY}; border-radius:20px; padding:26px 30px; color:#fff; margin:.4rem 0 1rem; }}
.keymsg .lbl {{ color:#8EDFD3; font-size:.78rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
.keymsg .h {{ font-size:1.55rem; line-height:1.4; font-weight:600; margin:.4rem 0 .9rem; color:#fff; }}
.keymsg .h b {{ color:#9FF0E2; font-weight:800; }}
.press {{ display:flex; flex-wrap:wrap; align-items:center; gap:10px; font-size:.98rem; color:#DCE6F0; }}
.pill {{ border-radius:999px; padding:4px 12px; font-weight:800; font-size:.86rem; color:#fff; }}
.pill.low {{ background:{GOOD}; }} .pill.moderate {{ background:{AMBER}; }} .pill.high {{ background:{BAD}; }}
.keymsg .fine {{ color:#A9BCCF; font-size:.84rem; margin-top:.6rem; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:.1rem 0 .4rem; }}
.chip {{ background:#fff; border:1px solid {LINE}; border-radius:999px; padding:4px 12px; font-size:.86rem; color:{INK}; }}
.chip b {{ color:{NAVY}; }}

/* results: impact cards */
.impact {{ background:#fff; border:1px solid {LINE}; border-radius:18px; padding:20px 22px; height:100%; }}
.impact .t {{ font-size:.82rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:{MUTED}; }}
.impact .vals {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin:.35rem 0 .2rem; }}
.impact .from {{ font-size:1.6rem; font-weight:650; color:#7A8C9E; }}
.impact .to {{ font-size:2.9rem; font-weight:800; color:{NAVY}; line-height:1; }}
.impact .ar {{ color:{MUTED}; font-size:1.5rem; }}
.impact .unit {{ color:{MUTED}; font-size:1rem; }}
.impact .sub {{ color:{MUTED}; font-size:.92rem; margin-top:.35rem; }}
.chg {{ display:inline-block; border-radius:999px; padding:3px 11px; font-weight:750; font-size:.9rem; }}
.chg.good {{ background:#E7F4EA; color:{GOOD}; }} .chg.bad {{ background:#FBEAE8; color:{BAD}; }}
.chg.neutral {{ background:#E8EEF5; color:{NAVY_2}; }} .chg.flat {{ background:#EEF1F4; color:{MUTED}; }}
.bullet {{ margin:1rem 0 .3rem; }}
.bullet .track {{ position:relative; height:30px; background:#EEF2F6; border-radius:8px; }}
.bullet .fill {{ position:absolute; left:0; top:0; bottom:0; background:#BFE3DD; border-radius:8px 0 0 8px; }}
.bullet .mk {{ position:absolute; top:-5px; bottom:-5px; width:4px; border-radius:2px; transform:translateX(-2px); }}
.bullet .cap {{ position:absolute; top:-9px; bottom:-9px; width:3px; background:{NAVY}; transform:translateX(-1px); }}
.bullet .ax {{ display:flex; justify-content:space-between; color:{MUTED}; font-size:.76rem; margin-top:6px; }}
.blegend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:.86rem; color:{MUTED}; margin-top:.4rem; }}
.blegend i {{ display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
.blegend b {{ color:{INK}; }}
.support {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:12px; margin:.9rem 0 .2rem; }}
.sup {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:13px 16px; }}
.sup .t {{ font-size:.86rem; font-weight:700; color:{MUTED}; }}
.sup .v {{ font-size:1.35rem; font-weight:750; color:{NAVY}; margin:.15rem 0 .25rem; }}
.sup .v span {{ color:#7A8C9E; font-weight:600; }}
.sup .n {{ font-size:.82rem; color:{MUTED}; margin-top:.3rem; }}

/* results: why */
.why3 {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:6px 20px; margin:1rem 0 .3rem; }}
.why3 .r {{ display:grid; grid-template-columns:190px 1fr; gap:14px; padding:11px 0; border-bottom:1px solid {LINE}; }}
.why3 .r:last-child {{ border-bottom:none; }}
.why3 .q {{ color:{TEAL_DARK}; font-weight:800; font-size:.84rem; letter-spacing:.05em; text-transform:uppercase; padding-top:2px; }}
.why3 .a {{ font-size:1rem; color:{INK}; }}
@media (max-width: 760px) {{ .why3 .r {{ grid-template-columns:1fr; gap:2px; }} .hero {{ padding:30px 24px; }} .hero h1 {{ font-size:2.2rem !important; }} }}

/* comparison */
.cmp {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:14px; margin:.4rem 0 .5rem; }}
.cmpc {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:16px 18px; }}
.cmpc.cur {{ border:2px solid {TEAL}; }}
.cmpc .nm {{ font-weight:800; color:{NAVY}; font-size:1.02rem; margin-bottom:.15rem; }}
.cmpc .as {{ color:{MUTED}; font-size:.82rem; line-height:1.45; min-height:3.4em; }}
.cmpc .m {{ display:flex; justify-content:space-between; align-items:baseline; padding:7px 0; border-top:1px solid {LINE}; font-size:.9rem; }}
.cmpc .m span {{ color:{MUTED}; }} .cmpc .m b {{ color:{INK}; font-size:1.02rem; }}
.cmpc .m b.good {{ color:{GOOD}; }} .cmpc .m b.bad {{ color:{BAD}; }}
.cmpc .m b.low {{ color:{GOOD}; }} .cmpc .m b.moderate {{ color:{AMBER}; }} .cmpc .m b.high {{ color:{BAD}; }}

.footer {{ border-top:1px solid {LINE}; margin-top:2.4rem; padding-top:.8rem; color:{MUTED}; font-size:.86rem; }}

/* ---------------- historical overview v3.8 ---------------- */
html, [data-testid="stMain"], [data-testid="stAppViewContainer"] {{ scroll-behavior:smooth; }}
@media (prefers-reduced-motion: reduce) {{ html, [data-testid="stMain"], [data-testid="stAppViewContainer"] {{ scroll-behavior:auto; }} }}
[id="hospital-overview"], [id="explore-patient-groups"], [id="admission-patterns"] {{ scroll-margin-top:24px; }}
.secnav {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:0 0 .8rem; }}
.secnav .snt {{ font-size:.75rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; color:{MUTED}; margin-right:6px; }}
.secnav a {{ font-size:.9rem; font-weight:600; color:{NAVY} !important; text-decoration:none !important; background:#fff;
  border:1px solid {LINE}; border-radius:999px; padding:4px 12px; }}
.secnav a:hover, .secnav a:focus-visible {{ border-color:{TEAL}; color:{TEAL_DARK} !important; }}
@media (min-width: 1280px) {{
  .secnav {{ position:fixed; z-index:20; left:1.5rem; top:7.5rem; width:170px; flex-direction:column; align-items:stretch;
    gap:2px; margin:0; padding:12px 10px; background:rgba(255,255,255,.96); border:1px solid #E6EBF1; border-radius:16px;
    box-shadow:0 2px 10px rgba(16,39,66,.06); }}
  .secnav .snt {{ margin:0 0 6px 8px; }}
  .secnav a {{ border:none; background:transparent; border-radius:10px; padding:7px 10px; border-left:3px solid transparent; }}
  .secnav a:hover, .secnav a:focus-visible {{ background:{TEAL_LIGHT}; }}
  .block-container:has(.secnav) > [data-testid="stVerticalBlock"] > :not(:has(.st-key-topnav)):not(.st-key-topnav) {{
    padding-left:190px; box-sizing:border-box; }}
}}
.stApp:has(#hospital-overview:target) .secnav a[href="#hospital-overview"],
.stApp:has(#explore-patient-groups:target) .secnav a[href="#explore-patient-groups"],
.stApp:has(#admission-patterns:target) .secnav a[href="#admission-patterns"] {{ color:{TEAL_DARK} !important; border-left-color:{TEAL}; font-weight:720; }}
.sc2 .sub small.sn {{ display:block; font-size:.8rem; color:{MUTED}; font-weight:500; margin-top:1px; }}
.basis {{ color:#46586A; font-size:.9rem; margin:.6rem 0 0; }}
.tbar .lg em {{ font-style:normal; color:{MUTED}; margin-left:4px; }}
.tbar .lgn {{ font-size:.8rem; color:#7A8A99; margin-top:4px; }}
.bigins b {{ font-weight:720; color:{NAVY}; }}
.bigins .bsup {{ display:block; font-size:1.02rem; font-weight:500; color:#34475A; margin-top:4px; letter-spacing:0; }}
.dxc .dd {{ color:{MUTED}; font-size:.86rem; margin-top:1px; }}
.sevr {{ grid-template-columns:148px minmax(80px, 1fr) 84px 52px 84px !important; }}
.sevr .sv {{ text-align:right; font-size:1.05rem !important; font-weight:700; color:{INK} !important; font-variant-numeric:tabular-nums; }}
.sevr .sp {{ text-align:right; font-size:.9rem; color:{MUTED}; font-variant-numeric:tabular-nums; }}
.sevr.sevh {{ padding:0 0 2px; font-size:.75rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:#7A8A99; }}
.sevr.sevh .sv {{ font-size:.75rem !important; font-weight:700; color:#7A8A99 !important; }}
.sevr.sevh .sp {{ font-size:.75rem; }}
.sevr.on .sv {{ color:{TEAL_DARK} !important; }}
@media (max-width: 900px) {{ .sevr {{ grid-template-columns:110px 1fr 70px 44px !important; }} .sevr .act {{ display:none; }}
  .sevr .sv {{ display:block; }} }}
.sevlv {{ min-width:220px; }} .sevlv .tt {{ font-weight:700; color:{NAVY}; margin-bottom:6px; }}
.sevlv > div:not(.tt) {{ display:flex; gap:10px; padding:3px 0; font-size:.95rem; }}
.sevlv > div b {{ width:18px; color:{TEAL_DARK}; }}
.sevlv p {{ font-size:.82rem; color:{MUTED}; margin:8px 0 0; line-height:1.45; }}
.st-key-ovprofile {{ padding:20px 22px 24px !important; }}
.st-key-ovprofile [data-testid="stMarkdownContainer"], .st-key-ovcta [data-testid="stMarkdownContainer"],
.st-key-ovprofile .stMarkdown, .st-key-ovcta .stMarkdown {{ margin-bottom:0 !important; }}
.st-key-ovprofile .gi {{ margin-bottom:4px; }}
.mgp .p span, .mgs .s span {{ font-size:.9rem !important; }}
.mgp .p b {{ font-size:1.6rem !important; }} .mgs .s b {{ font-size:1.25rem !important; }}
.mgp .p.age {{ background:#EEF7F5; }}
@media (max-width: 1300px) {{ .mgp .p b {{ font-size:1.3rem !important; }} .mgs .s b {{ font-size:1.1rem !important; }}
  .mgp .p {{ padding:10px 11px; }}
  .sevr {{ grid-template-columns:96px minmax(50px, 1fr) 70px 46px 76px !important; gap:8px !important; }}
  .sevr .act {{ font-size:.8rem; }} .sevr .sl b {{ white-space:nowrap; }}
  .sevr .sl span {{ display:block; margin-left:0 !important; }} .sevr.sevh {{ letter-spacing:.02em; }} }}
@media (max-width: 700px) {{ .mgp, .mgs {{ grid-template-columns:repeat(2, 1fr) !important; }} }}
.abu {{ margin-top:16px; }} .abu .al {{ font-size:.9rem; font-weight:700; color:#46586A; margin-bottom:6px; }}
.abr {{ display:grid; grid-template-columns:72px 1fr 118px; gap:10px; align-items:center; padding:4px 6px; border-radius:10px; }}
.abr.on {{ background:#F2F8F7; }} .abr.on .abl {{ color:{TEAL_DARK}; font-weight:750; }}
.abl {{ font-weight:650; color:{NAVY}; font-size:.95rem; }}
.abt {{ display:flex; height:14px; background:#EDF1F5; border-radius:999px; overflow:hidden; }}
.abt .i {{ background:{TEAL}; }} .abt .r {{ background:{NAVY_2}; }}
.abv {{ text-align:right; }} .abv b {{ display:block; color:{INK}; font-size:1rem; font-variant-numeric:tabular-nums; }}
.abv span {{ font-size:.78rem; color:{MUTED}; }}
.abk {{ display:flex; flex-wrap:wrap; gap:4px 14px; font-size:.82rem; color:{MUTED}; margin-top:6px; }}
.abk i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
.abk .abn {{ flex-basis:100%; font-size:.78rem; }}
.tins .tk {{ font-size:.75rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; color:{TEAL_DARK}; margin-bottom:4px; }}
.tins .th {{ font-size:1.22rem !important; line-height:1.4; }}
.hleg {{ max-width:420px; margin:.2rem 0 .4rem; }}
.hleg .hlt {{ font-weight:700; color:{NAVY}; font-size:.95rem; margin-bottom:4px; }}
.hleg .hlr {{ display:grid; grid-template-columns:44px 1fr 44px; align-items:center; gap:8px; font-size:.82rem; color:{MUTED}; }}
.hleg .hlr > span:first-child {{ text-align:right; }}
.hleg .hlw > div {{ display:flex; justify-content:space-between; font-size:.8rem; }}
.hleg .hlb {{ height:12px; border-radius:999px; background:linear-gradient(90deg, #EAF2FA, #7EA8CF 45%, #0B2545); }}
.st-key-ovcta {{ padding:22px 28px 22px !important; }}
.ctab {{ background:{PANEL}; border-radius:16px; padding:14px 16px 10px; }}
.ctal {{ font-weight:720; color:{NAVY}; font-size:1.05rem; display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:2px; }}
.ctal a.chg {{ font-size:.9rem; font-weight:650; color:{TEAL_DARK} !important; text-decoration:none; }}
.ctal a.chg:hover {{ text-decoration:underline; }}
.ctak {{ font-size:.82rem; color:{MUTED}; margin-bottom:8px; }}
.st-key-ctago {{ margin-top:.9rem; }}
.st-key-ctago button[kind="primary"] {{ min-height:2.9rem; padding:0 28px; font-size:1.05rem; }}
.st-key-ctago .pfnote {{ margin:0; }}

/* ---------------- historical overview v3.9 ---------------- */
.period {{ display:inline-flex; align-items:flex-start; gap:12px; margin-top:.2rem; padding:12px 18px 12px 14px;
  background:#EEF6F5; border:1px solid #D5E9E6; border-radius:14px; }}
.period .pic {{ width:34px; height:34px; border-radius:10px; background:#fff; color:{TEAL_DARK}; display:flex;
  align-items:center; justify-content:center; flex:none; }}
.period .pic svg {{ width:19px; height:19px; }}
.period .pl {{ font-size:.78rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:{TEAL_DARK}; }}
.period .pv {{ font-size:1.12rem; font-weight:700; color:{NAVY}; margin-top:1px; }}
.period .pv span {{ font-weight:550; color:#46586A; }}
.period .pn {{ font-size:.84rem; color:#46586A; margin-top:3px; }}
.secnav a {{ display:flex; align-items:baseline; gap:8px; }}
.secnav a .sn {{ font-size:.74rem; font-weight:700; color:{TEAL_DARK}; font-variant-numeric:tabular-nums; opacity:.85; }}
@media (min-width: 1280px) {{ .secnav {{ width:216px; }} .secnav a {{ white-space:nowrap; font-size:.88rem; }}
  .block-container:has(.secnav) > [data-testid="stVerticalBlock"] > :not(:has(.st-key-topnav)):not(.st-key-topnav) {{ padding-left:232px; }} }}
.sc2 .sub > div {{ justify-content:flex-start !important; text-align:center; align-items:center; }}
.sc2 .sub > div > span {{ min-height:2.6em !important; margin-bottom:8px !important; display:flex !important;
  align-items:flex-end; justify-content:center; }}
.sc2 .sub {{ padding-top:16px !important; gap:12px 10px !important; }}
.sevr .sp {{ font-size:1rem !important; font-weight:650; color:#2C3E50 !important; }}
.sevr.sevh .sp {{ font-size:.75rem !important; font-weight:700; color:#7A8A99 !important; white-space:nowrap; }}
.sevr.sevh .sp .tip {{ text-transform:none; letter-spacing:0; }}
[data-testid="stPopoverBody"]:has(.sevlv) {{ min-width:0 !important; width:auto !important; max-width:260px !important; padding:14px 16px !important; }}
.sevlv {{ min-width:200px !important; }}
.sevlv > div:not(.tt) b {{ width:auto !important; min-width:78px; color:{NAVY} !important; font-weight:650; }}
.sevlv > div:not(.tt) {{ color:#46586A; }}
.abl {{ white-space:nowrap; }} .abhd {{ margin-top:18px; }} .abhd .al {{ font-size:.95rem; font-weight:700; color:{NAVY}; }}
.abhd .as {{ font-size:.84rem; color:{MUTED}; margin-top:1px; }}
.st-key-ovprofile .stCheckbox, .st-key-ovprofile [data-testid="stCheckbox"] {{ margin-top:-2px; }}
.abu {{ margin-top:4px !important; }}
.abr {{ grid-template-columns:78px minmax(60px, 1fr) 186px !important; padding:6px 6px !important; }}
.abt {{ background:transparent !important; height:16px !important; border-radius:6px !important; }}
.abt > div {{ height:100%; }} .abt .t {{ background:#5B84AE; border-radius:6px; }}
.abt .i {{ border-radius:6px 0 0 6px; }} .abt .r {{ border-radius:0 6px 6px 0; }}
.abr.on .abt .t {{ background:{TEAL}; }}
.abv {{ text-align:left !important; font-size:.88rem; color:#46586A; white-space:nowrap; }}
.abv b {{ display:inline !important; font-size:1rem; color:{INK}; }} .abv span {{ font-size:.88rem !important; color:#46586A !important; }}
@media (max-width: 1000px) {{ .sc2 .sub > div > span {{ min-height:3.9em !important; }}
  .abr {{ grid-template-columns:66px minmax(50px, 1fr) 168px !important; }} .abv {{ font-size:.78rem; }} .abv b {{ font-size:.9rem !important; }} }}
.sevr .act {{ white-space:nowrap; }}
.mgs .s span {{ display:block; min-height:2.6em; }}
.tchart-note {{ font-size:.84rem; color:#55677A; margin:-.4rem 0 .6rem; }}
.st-key-ovcta {{ display:flex; flex-direction:row !important; flex-wrap:wrap; align-items:center; justify-content:center;
  gap:12px 28px !important; padding:34px 24px 10px !important;
  margin-top:2rem; background:transparent !important; border:none !important; border-top:1px solid #E3E9EF !important;
  border-radius:0 !important; box-shadow:none !important; }}
.st-key-ovcta::before {{ display:none !important; }}
.st-key-ovcta .ctaq {{ font-size:1.15rem; font-weight:650; color:{NAVY}; margin:0; white-space:nowrap; }}
.st-key-ovcta > div {{ width:auto !important; flex:0 0 auto !important; }}
.st-key-ovcta button[kind="primary"] {{ min-height:3rem; padding:0 32px; font-size:1.05rem; border-radius:999px; }}

/* ---------------- build a scenario v4.0 ---------------- */
.simhead {{ margin-bottom:.6rem; }}
[class*="st-key-simsec"] {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:22px 26px 22px !important;
  box-shadow:0 1px 3px rgba(16,39,66,.05); margin-bottom:.4rem; }}
[class*="st-key-simsec"] .qh {{ margin:0 0 2px !important; padding:0 !important; }}
[class*="st-key-simsec"] [data-testid="stMarkdownContainer"] {{ margin-bottom:0 !important; }}
.qsub {{ color:#55677A; font-size:1rem; margin:0 0 .6rem 0; }}
.snap {{ background:{PANEL}; border-radius:16px; padding:14px 18px; margin-top:.3rem; }}
.snh {{ font-size:.95rem; color:#46586A; margin-bottom:10px; }} .snh b {{ color:{NAVY}; }}
.sng {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; }}
.sng b {{ display:block; font-size:1.45rem; font-weight:740; color:{NAVY}; letter-spacing:-0.01em; }}
.sng span {{ font-size:.86rem; color:#55677A; }}
.snn {{ font-size:.88rem; color:{TEAL_DARK}; margin-top:10px; }}
.lever {{ display:flex; flex-direction:column; gap:4px; margin:.2rem 0 .5rem; }}
.lvt {{ font-size:1.12rem; font-weight:720; color:{NAVY}; }}
.lscope {{ align-self:flex-start; font-size:.8rem; font-weight:650; border-radius:999px; padding:3px 10px; }}
.lscope.grp {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }}
.lscope.all {{ background:#E8EEF6; color:{NAVY_2}; }}
.pvw {{ display:flex; flex-wrap:wrap; gap:10px; margin:.7rem 0 .4rem; }}
.pvw > div {{ flex:1 1 120px; background:{PANEL}; border-radius:12px; padding:9px 12px; }}
.pvw span {{ display:block; font-size:.8rem; color:#55677A; font-weight:600; }}
.pvw b {{ display:block; font-size:1.3rem; color:{NAVY}; font-weight:730; }}
.pvw small {{ display:block; font-size:.76rem; color:{MUTED}; }}
.pvw .hl {{ background:{TEAL_LIGHT}; }} .pvw .hl b {{ color:{TEAL_DARK}; }}
.lvx {{ font-size:.92rem; color:#46586A; margin:.2rem 0 0; }}
.lvn {{ font-size:.86rem; color:#55677A; margin:.3rem 0 0; }}
.bedbig {{ margin:.7rem 0 .1rem; color:#46586A; font-size:1rem; }}
.bedbig b {{ font-size:2.1rem; font-weight:780; color:{NAVY}; letter-spacing:-0.02em; margin-right:6px; }}
[class*="st-key-simsec"] [data-testid="stSegmentedControl"] button, [class*="st-key-simsec"] [data-testid="stButtonGroup"] button {{ min-height:2.4rem; }}
.st-key-sim_explore button {{ margin-top:.3rem; color:{TEAL_DARK} !important; }}
.spanel {{ background:#fff; border:1px solid #E6EBF1; border-radius:20px; padding:20px 22px 8px;
  box-shadow:0 6px 20px rgba(16,39,66,.06); }}
.sph {{ font-size:1.3rem; font-weight:760; color:{NAVY}; letter-spacing:-0.01em; }}
.sps {{ font-size:.88rem; color:{MUTED}; margin:2px 0 6px; }}
.spg {{ border-top:1px solid #EEF2F6; padding:12px 0 6px; }}
.spl {{ font-size:.74rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; color:{TEAL_DARK}; margin-bottom:4px; }}
.spt {{ font-size:1.15rem; font-weight:740; color:{NAVY}; }} .spa {{ font-size:.92rem; color:#46586A; }}
.sprow {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; padding:4px 0; font-size:.95rem; }}
.sprow span {{ color:#46586A; }} .sprow span em {{ display:block; font-style:normal; font-size:.76rem; color:{MUTED}; }}
.sprow b {{ color:{INK}; text-align:right; font-weight:680; }} .sprow b small {{ display:block; font-weight:500; color:{MUTED}; font-size:.76rem; }}
.st-key-summary .status-ok, .st-key-summary .status-stale {{ margin:.7rem 0 .2rem; }}
.st-key-summary button[kind="primary"] {{ min-height:3rem; font-size:1.05rem; margin-top:.5rem; }}
@media (max-width: 1100px) {{ .sng {{ grid-template-columns:1fr 1fr; }} }}

/* ---------------- goal-based scenario v4.1 ---------------- */
[class*="st-key-pick_goal_"] {{ padding:20px 22px 8px; border-radius:20px; }}
.goalc .gic {{ width:42px; height:42px; border-radius:12px; background:#EEF2F6; color:{NAVY}; display:flex;
  align-items:center; justify-content:center; margin-bottom:10px; }}
.goalc .gic svg {{ width:22px; height:22px; }}
.goalc.on .gic {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }}
.goalc .gt {{ font-size:1.35rem; font-weight:760; color:{NAVY}; letter-spacing:-0.01em; }}
.goalc .gd {{ font-size:.98rem; color:#46586A; margin-top:4px; }}
.goalc .gq {{ font-size:.9rem; color:{MUTED}; font-style:italic; margin-top:8px; }}
.goalhint {{ background:#fff; border:1px dashed #C9D6E2; border-radius:16px; padding:22px; color:#55677A; text-align:center; }}
.spgoal {{ display:inline-block; margin:2px 0 6px; font-size:.84rem; font-weight:700; color:{TEAL_DARK};
  background:{TEAL_LIGHT}; border-radius:999px; padding:3px 10px; }}
.spe {{ font-size:.9rem; color:{MUTED}; }}
.qh .opt {{ font-size:.78rem; font-weight:650; color:{MUTED}; background:#EEF2F6; border-radius:999px; padding:2px 9px; margin-left:8px; }}

/* ---------------- goal-focused results v4.1 ---------------- */
.simhead .eyebrow {{ font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:{TEAL_DARK}; }}
.keyins {{ background:#fff; border:1px solid #E6EBF1; border-left:4px solid {TEAL}; border-radius:16px; padding:14px 20px; margin:.4rem 0 .9rem; }}
.keyins p {{ margin:.25rem 0; font-size:1.05rem; color:{INK}; }} .keyins p:first-child {{ font-weight:650; color:{NAVY}; font-size:1.12rem; }}
.rkl {{ font-size:.78rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; color:{MUTED}; margin:.6rem 0 .35rem; }}
.rkrow {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:.5rem; }}
@media (max-width: 1100px) {{ .rkrow {{ grid-template-columns:repeat(2, 1fr); }} }}
.rk {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:14px 16px; }}
.rk .t {{ font-size:.9rem; font-weight:650; color:#46586A; }}
.rk .v {{ font-size:1.55rem; font-weight:760; color:{NAVY}; margin:4px 0 4px; letter-spacing:-0.01em; }}
.rk .v span {{ font-size:1.05rem; font-weight:600; color:{MUTED}; }}
.rk .n {{ font-size:.8rem; color:{MUTED}; margin-top:6px; }}
.secbox {{ background:{PANEL}; border-radius:16px; padding:14px 18px; margin:.6rem 0 .4rem; }}
.secbox .st {{ font-weight:720; color:{NAVY}; font-size:1.02rem; }} .secbox .sd {{ font-size:.86rem; color:#55677A; margin:2px 0 8px; }}
.secbox .sg {{ display:flex; flex-wrap:wrap; gap:10px 24px; }} .secbox .sg span {{ display:block; font-size:.8rem; color:#55677A; }}
.st-key-resactions, .st-key-resexplore {{ margin:.2rem 0 .8rem; }}

/* ---------------- guided scenarios v4.2 ---------------- */
.subq {{ font-weight:680; color:{NAVY}; margin:.4rem 0 .1rem; }}
.lvq {{ font-size:.9rem; color:#55677A; }}
.lvn.warn {{ color:#8A5A00; }}
.spstmt {{ background:{TEAL_LIGHT}; color:{NAVY}; border-radius:12px; padding:10px 12px; font-size:.95rem; font-weight:600;
  line-height:1.4; margin:4px 0 6px; }}
.testedline {{ display:inline-block; margin-top:8px; background:#fff; border:1px solid #E6EBF1; border-radius:999px;
  padding:6px 14px; font-size:.92rem; font-weight:600; color:{NAVY}; }}
.keyfind {{ background:#fff; border:1px solid #E6EBF1; border-left:5px solid {TEAL}; border-radius:16px; padding:16px 20px;
  font-size:1.2rem; font-weight:650; color:{NAVY}; line-height:1.45; margin:.3rem 0 .8rem; }}
.plan {{ background:{PANEL}; border-radius:16px; padding:14px 20px; margin:.7rem 0 .4rem; }}
.plan .pt {{ font-weight:720; color:{NAVY}; font-size:1.05rem; margin-bottom:4px; }}
.plan ul {{ margin:0; padding-left:1.1rem; }} .plan li {{ margin:.25rem 0; color:{INK}; }}
[class*="st-key-simsec"] [data-testid="stVerticalBlock"] {{ gap:.55rem; }}

/* ---------------- goal-guided builder v4.3 ---------------- */
.goalc .gd {{ font-size:1.02rem !important; color:{NAVY} !important; font-weight:550; }}
.goalc .gq {{ font-style:normal !important; color:{MUTED} !important; font-size:.9rem !important; }}
/* segmented controls: wrap instead of clipping when a column is narrow */
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div {{ flex-wrap:wrap !important; max-width:100%; row-gap:6px; }}
[data-testid="stButtonGroup"] button {{ flex:0 0 auto; white-space:nowrap; }}
/* desktop: one page scroll; Your Scenario stays in view as a sticky panel (v5.5: the left column no longer scrolls
   on its own, which had created a second scrollbar competing with the page) */
@media (min-width: 1100px) and (min-height: 700px) {{
  [data-testid="stHorizontalBlock"]:has(.st-key-simleft):has(.st-key-summary) {{ align-items:stretch !important; }}
  [data-testid="stColumn"]:has(.st-key-summary) {{ display:flex !important; flex-direction:column; }}
  [data-testid="stColumn"]:has(.st-key-summary) > * {{ flex:1 1 auto; }}
  .st-key-summary, [data-testid="stLayoutWrapper"]:has(> .st-key-summary) {{ position:sticky !important;
    top:calc(var(--hcp-nav) + 4px) !important; }}
}}
@media (max-width: 1099px), (max-height: 699px) {{ .st-key-summary {{ position:static !important; }} }}
/* room at the end of Build a Scenario so the Welcome step links (Step 3, Step 4) can bring their
   step to the top of the window instead of stopping at the page end */
.block-container:has(.st-key-simleft) {{ padding-bottom:45vh !important; }}

@media (max-width: 1099px) {{
  [data-testid="stHorizontalBlock"]:has(.st-key-simleft):has(.st-key-summary) {{ flex-direction:column !important; }}
  [data-testid="stHorizontalBlock"]:has(.st-key-simleft):has(.st-key-summary) > [data-testid="stColumn"] {{
    width:100% !important; flex:1 1 auto !important; min-width:0 !important; }}
}}

/* ---------------- capacity-first v4.4 ---------------- */
.opttag {{ display:inline-block; font-size:.76rem; font-weight:700; color:{MUTED}; background:#EEF2F6; border-radius:999px;
  padding:2px 9px; margin:-2px 0 4px; }}
.pvw.tight {{ margin-top:0; }}
[class*="st-key-simsec"] .bedbig {{ margin-top:0; }}
.diffs {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:12px 18px; margin:.3rem 0 .6rem; }}
.dft {{ font-weight:720; color:{NAVY}; margin-bottom:4px; }}
.dfr {{ display:grid; grid-template-columns:200px 1fr 140px; gap:10px; padding:6px 0; border-top:1px solid #EEF2F6; font-size:.95rem; }}
.dfr span {{ color:#46586A; }} .dfr b {{ color:{INK}; font-weight:650; }} .dfr em {{ font-style:normal; font-size:.84rem; color:{MUTED}; text-align:right; }}
.dfr.changed em {{ color:{TEAL_DARK}; font-weight:650; }}
@media (max-width: 800px) {{ .dfr {{ grid-template-columns:1fr; }} .dfr em {{ text-align:left; }} }}

/* ---------------- guided steps v4.5 ---------------- */
.stepnav {{ display:flex; gap:8px; flex-wrap:wrap; margin:.5rem 0 .8rem; }}
.stepnav a {{ flex:1 1 150px; min-width:140px; display:flex; flex-direction:column; gap:1px; background:#fff;
  border:1px solid #E2E8EF; border-radius:12px; padding:8px 12px; text-decoration:none !important; }}
.stepnav a:hover, .stepnav a:focus-visible {{ border-color:{TEAL}; background:{TEAL_LIGHT}; }}
.stepnav .sn {{ font-size:.74rem; font-weight:750; color:{TEAL_DARK}; letter-spacing:.03em; }}
.stepnav b {{ font-size:.95rem; color:{NAVY}; font-weight:700; }}
.stepnav em {{ font-style:normal; font-size:.8rem; color:{MUTED}; }}
.stApp:has(#step-1:target) .stepnav a[href="#step-1"], .stApp:has(#step-2:target) .stepnav a[href="#step-2"],
.stApp:has(#step-3:target) .stepnav a[href="#step-3"], .stApp:has(#step-4:target) .stepnav a[href="#step-4"] {{
  border-color:{TEAL}; background:{TEAL_LIGHT}; }}
.stph {{ scroll-margin-top:12px; margin-bottom:.2rem; }}
.stph .stpl {{ display:flex; align-items:center; gap:8px; margin-bottom:2px; }}
.stph .stpn {{ font-size:.8rem; font-weight:750; color:{TEAL_DARK}; background:{TEAL_LIGHT}; border-radius:999px; padding:2px 10px; }}
.stph .stopt {{ font-size:.76rem; font-weight:700; color:{MUTED}; background:#EEF2F6; border-radius:999px; padding:2px 9px; }}
.stph h2 {{ font-size:1.45rem !important; font-weight:760 !important; color:{NAVY} !important; margin:0 !important; padding:0 !important; }}
.stph .qsub {{ margin:.15rem 0 .5rem; }}
.guide {{ font-size:.92rem; color:#3E5164; background:{PANEL}; border-radius:10px; padding:8px 12px; margin:.3rem 0 0; }}
.guide b {{ color:{NAVY}; }}
.impfor {{ font-size:.98rem; color:#46586A; margin:.8rem 0 .2rem; padding-top:.7rem; border-top:1px solid #EEF2F6; }}
.impfor b {{ color:{NAVY}; }}
/* Your Scenario: readable on a laptop */
.spanel .sph {{ font-size:1.4rem !important; }}
.spanel .spstmt {{ font-size:1rem !important; }}
.spanel .spl {{ font-size:.86rem !important; letter-spacing:.01em !important; text-transform:none !important; color:{TEAL_DARK} !important; font-weight:750 !important; }}
.spanel .sprow {{ font-size:1rem !important; padding:5px 0 !important; }}
.spanel .sprow span {{ color:#34475A !important; }} .spanel .sprow b {{ font-weight:700 !important; color:{INK} !important; }}
.spanel .sprow b small {{ font-size:.82rem !important; }}
.spanel .spt {{ font-size:1.1rem !important; }} .spanel .spa, .spanel .spe {{ font-size:.95rem !important; color:#46586A !important; }}
/* ---- v4.7 plain-language builder ---- */
.stph h2 .stopt {{ display:inline-block; vertical-align:middle; position:relative; top:-2px; margin-left:10px;
  font-size:.72rem; font-weight:700; letter-spacing:.01em; line-height:1.5; }}
.st-key-patpick [role="radiogroup"] {{ display:grid !important; grid-template-columns:1fr 1fr; gap:10px; width:100%; }}
.st-key-patpick [role="radiogroup"] > div {{ position:relative; margin:0 !important; padding:10px 12px !important;
  border:1px solid {LINE}; border-radius:12px; background:#fff; min-width:0; cursor:pointer; transition:border-color .15s ease; }}
.st-key-patpick [role="radiogroup"] > div:hover {{ border-color:#9FC9C2; }}
.st-key-patpick [role="radiogroup"] > div[data-selected="true"] {{ border-color:{TEAL}; background:{TEAL_LIGHT};
  box-shadow:0 0 0 1px {TEAL} inset; }}
.st-key-patpick [role="radiogroup"] > div > label {{ position:static !important; }}
.st-key-patpick [role="radiogroup"] > div > label::after {{ content:""; position:absolute; inset:0; border-radius:12px; z-index:2; }}
.st-key-patpick [data-testid="stRadioCaption"] {{ pointer-events:none; }}
.st-key-patpick [role="radiogroup"] > div > label p {{ font-weight:700; color:{NAVY}; font-size:.97rem; }}
.st-key-patpick [data-testid="stCaptionContainer"] p, .st-key-patpick [data-testid="stCaptionContainer"] {{ font-weight:400 !important;
  color:#46586A !important; font-size:.86rem !important; line-height:1.4; }}
@media (max-width: 640px) {{ .st-key-patpick [role="radiogroup"] {{ grid-template-columns:1fr; }} }}
.tline {{ margin:.25rem 0 .2rem; }}
.tline .tlbar {{ display:flex; gap:3px; }}
.tline .tlseg {{ min-width:0; background:{TEAL_LIGHT}; border-top:3px solid {TEAL}; border-radius:6px; padding:5px 8px; }}
.tline .tlseg.part {{ background:#F1F5F8; border-top-color:#9FC9C2; }}
.tline .tlseg b {{ display:block; font-size:.86rem; color:{NAVY}; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.tline .tlseg span {{ display:block; font-size:.76rem; color:#55677A; white-space:nowrap; }}
.tline p {{ font-size:.88rem; color:#46586A; margin:.35rem 0 0; }}
.stepnav {{ gap:6px !important; }} .stepnav a {{ padding:8px 10px !important; }} .stepnav b {{ font-size:.88rem !important; }}
.stepnav .sn .nopt {{ display:inline-block; vertical-align:middle; position:relative; top:-1px; margin-left:4px; white-space:nowrap;
  font-size:.6rem; font-weight:700; color:{MUTED}; background:#EEF2F6; border-radius:999px; padding:1px 6px; letter-spacing:.01em; }}
/* v4.8 continuous month timeline */
.tl2 {{ margin:.35rem 0 0; }}
.tl2 .bar {{ display:flex; height:30px; border-radius:9px; overflow:hidden; background:{TEAL_LIGHT}; }}
.tl2 .seg {{ min-width:0; display:flex; align-items:center; justify-content:center; background:#D4ECE7;
  color:{TEAL_DARK}; font-size:.8rem; font-weight:700; letter-spacing:.01em; white-space:nowrap; overflow:hidden; }}
.tl2 .seg:nth-child(even) {{ background:#C3E4DD; }}
.tl2 .seg + .seg {{ border-left:2px solid #fff; }}
.tl2 .ends {{ display:flex; justify-content:space-between; font-size:.78rem; color:#55677A; margin-top:4px; }}
.durline {{ font-size:.98rem; color:#34475A; margin:.55rem 0 .1rem; line-height:1.45; }}
.durline b {{ color:{NAVY}; font-weight:700; }}
/* v4.8 Step 2 comparison */
.admc {{ background:{PANEL}; border-radius:14px; padding:12px 16px 10px; }}
.admc .row {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
.admc .cell {{ min-width:0; }}
.admc .lab {{ font-size:.82rem; font-weight:650; color:#55677A; }}
.admc .num {{ font-size:1.35rem; font-weight:740; color:#34475A; letter-spacing:-.01em; white-space:nowrap; }}
.admc .num small {{ font-size:.85rem; font-weight:600; color:#55677A; margin-left:4px; letter-spacing:0; }}
.admc .arrow {{ font-size:1.3rem; color:#9FB0C0; }}
.admc .scen .lab {{ color:{TEAL_DARK}; }} .admc .scen .num {{ color:{NAVY}; font-size:1.6rem; }}
.admc .chg {{ display:inline-block; font-size:.8rem; font-weight:700; color:{TEAL_DARK}; background:{TEAL_LIGHT};
  border-radius:999px; padding:1px 8px; margin-left:6px; vertical-align:middle; }}
.admc .basis {{ font-size:.82rem; color:#66778A; margin-top:6px; padding-top:6px; border-top:1px solid #E6EBF1; }}
.rrline {{ font-size:.9rem; color:#34475A; background:#F3F8F7; border-left:3px solid {TEAL}; border-radius:6px;
  padding:6px 10px; margin:.45rem 0 0; }}
.rrline b {{ color:{NAVY}; }}
.agfoot {{ font-size:.8rem; color:#66778A; }}
.st-key-aboutgrp [data-testid="stHorizontalBlock"] {{ align-items:center; }}
.st-key-sim_explore {{ margin-left:auto; }}
/* v4.8 brand */
.brand2 {{ display:flex; align-items:center; gap:10px; line-height:1.15; }}
.brand2 .bmark {{ width:30px; height:30px; border-radius:9px; background:{TEAL}; display:flex; align-items:center;
  justify-content:center; flex:0 0 auto; }}
.brand2 .bmark svg {{ width:17px; height:17px; }}
.st-key-navbrand {{ align-self:center; justify-content:center; }}
.st-key-navbrand [data-testid="stMarkdownContainer"], .st-key-navbrand [data-testid="stMarkdown"],
.st-key-navbrand .stMarkdown {{ margin:0 !important; padding:0 !important; }}
.st-key-navbrand [data-testid="stMarkdownContainer"] > div {{ margin:0 !important; }}
.brand2 .btext {{ display:flex; flex-direction:column; justify-content:center; }}
.brand2 .bname {{ display:block;  font-weight:700; color:{NAVY}; font-size:1.14rem; letter-spacing:-0.018em; white-space:nowrap; }}
.brand2 .bsub {{ display:block; font-size:.72rem; color:#7A8A9A; font-weight:500; letter-spacing:.01em; white-space:nowrap; margin-top:2px; }}
@media (max-width: 1250px) {{ .brand2 .bsub {{ display:none; }} }}
@media (max-width: 1200px) {{
  .brand2 .bmark {{ display:none; }} .brand2 .bname {{ font-size:1.05rem; }}
  .st-key-topnav {{ gap:10px !important; padding-left:16px !important; }}
  .st-key-navlinks {{ padding:0 2px !important; gap:4px !important; }}
  .st-key-navlinks button {{ padding:0 11px !important; }} .st-key-navlinks button p {{ font-size:.95rem !important; }} }}
/* ---- v4.9 Results ---- */
[id="capacity-overview"], [id="compare-scenarios"], [id="planning-impact"], [id="explore-options"], [id="compare-options"] {{ scroll-margin-top:24px; }}
.stApp:has(#capacity-overview:target) .secnav a[href="#capacity-overview"],
.stApp:has(#compare-scenarios:target) .secnav a[href="#compare-scenarios"],
.stApp:has(#planning-impact:target) .secnav a[href="#planning-impact"],
.stApp:has(#explore-options:target) .secnav a[href="#explore-options"] {{ color:{TEAL_DARK} !important; border-left-color:{TEAL}; font-weight:720; }}
.st-key-restested {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:16px 20px 6px; margin:.2rem 0 .6rem; gap:.5rem; }}
.rtt {{ font-size:.86rem; font-weight:700; color:{TEAL_DARK}; margin-bottom:2px; }}
.rts {{ font-size:1.05rem; color:{INK}; margin:0 0 .25rem; line-height:1.5; }}
.keyfind2 {{ background:#fff; border:1px solid #E6EBF1; border-left:5px solid {TEAL}; border-radius:16px; padding:16px 20px; margin:.3rem 0 .8rem; }}
.keyfind2 .kh {{ font-size:1.22rem; font-weight:700; color:{NAVY}; line-height:1.4; letter-spacing:-0.005em; }}
.keyfind2 .ks {{ font-size:1rem; color:#3E5164; margin-top:.4rem; line-height:1.5; }}
.rkrow2 {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:.4rem; }}
@media (max-width: 1100px) {{ .rkrow2 {{ grid-template-columns:repeat(2, 1fr); }} }}
@media (max-width: 640px) {{ .rkrow2 {{ grid-template-columns:1fr; }} }}
.rk2 {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:14px 16px; min-width:0; }}
.rk2 .t {{ font-size:.92rem; font-weight:650; color:#3E5164; }}
.rk2 .v {{ font-size:1.75rem; font-weight:770; color:{NAVY}; margin:4px 0 6px; letter-spacing:-0.015em; line-height:1.15; }}
.rk2 .n {{ font-size:.86rem; color:#55677A; margin-top:6px; line-height:1.4; }}
.dchip {{ display:inline-block; border-radius:999px; padding:2px 10px; font-weight:700; font-size:.84rem; white-space:nowrap; }}
.dchip.good {{ background:#E0F2EE; color:{TEAL_DARK}; }}
.dchip.bad {{ background:#FCE9E4; color:#B5452E; }}
.dchip.neutral {{ background:#E8EEF5; color:{NAVY_2}; }}
.dchip.flat {{ background:#EEF1F4; color:#5B6B7A; font-weight:600; }}
.rnote {{ font-size:.88rem; color:#55677A; margin:.35rem 0 .6rem; line-height:1.5; }}
.rnote b {{ color:#34475A; }}
.satnote {{ font-size:.92rem; color:#34475A; background:{PANEL}; border-radius:12px; padding:10px 14px; margin:.4rem 0 .6rem; }}
.satnote b {{ color:{NAVY}; }}
.plan2 {{ background:{PANEL}; border-radius:16px; padding:14px 20px 8px; margin:.5rem 0 .4rem; }}
.plan2 .pt {{ font-weight:720; color:{NAVY}; font-size:1.08rem; margin-bottom:4px; }}
.plan2 ul {{ margin:.2rem 0 .3rem 1.1rem; padding:0; }} .plan2 li {{ font-size:.98rem; color:#34475A; margin:.25rem 0; line-height:1.5; }}
.legend2 {{ display:flex; gap:18px; font-size:.9rem; color:#34475A; margin:-.2rem 0 .4rem; }}
.legend2 i {{ display:inline-block; width:22px; height:4px; border-radius:2px; vertical-align:middle; margin-right:7px; }}
.legend2 i.lr {{ background:{BASE}; }} .legend2 i.ls {{ background:{TEAL}; }}
.rsub {{ font-size:1.12rem; font-weight:720; color:{NAVY}; margin:1rem 0 .2rem; }}
.rlead {{ font-size:.95rem; color:#46586A; margin:0 0 .5rem; }}
.itab {{ background:#fff; border:1px solid #E6EBF1; border-radius:14px; padding:4px 16px; margin:.2rem 0 .4rem; }}
.itab .ir {{ display:grid; grid-template-columns:minmax(0, 2.2fr) 1fr 1fr 1.2fr; gap:10px; align-items:center; padding:9px 0;
  border-top:1px solid #EEF2F6; font-size:.95rem; }}
.itab.four .ir {{ grid-template-columns:minmax(0, 1.6fr) 1.2fr 1.2fr 1.2fr; }}
.itab .ir:first-child {{ border-top:none; }}
.itab .ir span {{ color:#34475A; }} .itab .ir b {{ color:{NAVY}; font-weight:650; }}
.itab .ir em {{ font-style:normal; color:#46586A; font-size:.9rem; }}
.itab .ih b, .itab .ih em {{ font-size:.82rem; color:#66778A !important; font-weight:650; }}
@media (max-width: 760px) {{ .itab .ir, .itab.four .ir {{ grid-template-columns:1fr 1fr; }} }}
.cmpgrid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:12px; margin:.6rem 0 .3rem; }}
.cmp2 {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:14px 16px; }}
.cmp2.cur {{ border-color:{TEAL}; box-shadow:0 0 0 1px {TEAL} inset; }}
.cmp2 .nm {{ font-weight:740; color:{NAVY}; font-size:1.05rem; display:flex; gap:8px; align-items:center; }}
.cmp2 .nm em {{ font-style:normal; font-size:.74rem; font-weight:700; color:{TEAL_DARK}; background:{TEAL_LIGHT}; border-radius:999px; padding:1px 8px; }}
.cmp2 .as {{ font-size:.86rem; color:#46586A; margin:.35rem 0 .5rem; line-height:1.45; }}
.cmp2 .st {{ display:inline-block; font-size:.8rem; font-weight:700; border-radius:999px; padding:2px 9px; margin-bottom:.4rem; }}
.cmp2 .st.good {{ background:#E0F2EE; color:{TEAL_DARK}; }} .cmp2 .st.warn {{ background:#FFF3DC; color:#8A5A00; }}
.cmp2 .st.bad {{ background:#FCE9E4; color:#B5452E; }}
.cmp2 .m {{ display:flex; justify-content:space-between; gap:8px; font-size:.9rem; padding:4px 0; border-top:1px solid #F0F3F6; }}
.cmp2 .m span {{ color:#55677A; }} .cmp2 .m b {{ color:{NAVY}; font-weight:680; }}
/* ---- v5.1 Results ---- */
[id="operations"], [id="flow-impact"] {{ scroll-margin-top:24px; }}
.stApp:has(#operations:target) .secnav a[href="#operations"],
.stApp:has(#flow-impact:target) .secnav a[href="#flow-impact"],
.stApp:has(#compare-options:target) .secnav a[href="#compare-options"] {{ color:{TEAL_DARK} !important; border-left-color:{TEAL}; font-weight:720; }}
.ic {{ display:inline-flex; width:1.15em; height:1.15em; vertical-align:-0.2em; }} .ic svg {{ width:100%; height:100%; }}
.rgen {{ font-size:.9rem; font-weight:600; color:{TEAL_DARK}; margin-bottom:.2rem; }}
.stale2 {{ display:flex; gap:10px; align-items:flex-start; background:#FFF6E5; color:#6B4A00; border-radius:12px;
  padding:10px 14px; font-size:.95rem; margin:0 0 .8rem; }} .stale2 .ic {{ color:#B07800; margin-top:2px; }}
.rq {{ font-size:1.32rem; font-weight:720; color:{NAVY}; line-height:1.35; letter-spacing:-0.01em; margin:.15rem 0 .8rem; max-width:46em; }}
.rset {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:2px 28px; margin:0 0 .5rem; }}
.rset > div {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid #EEF2F6; font-size:.97rem; }}
.rset span {{ color:#55677A; }} .rset b {{ color:{NAVY}; font-weight:650; text-align:right; }}
@media (max-width: 760px) {{ .rset {{ grid-template-columns:1fr; }} }}
.rbase {{ background:{PANEL}; border-radius:12px; padding:10px 14px; font-size:.95rem; color:#34475A; margin:.6rem 0 .9rem; line-height:1.5; }}
.rbase b {{ color:{NAVY}; }}
.st-key-resactions {{ margin:.2rem 0 .4rem; }}
.simdet p {{ font-size:.92rem; color:#34475A; line-height:1.55; margin:0 0 .45rem; }}
.rguide {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0; margin:.4rem 0 1.4rem;
  border-top:1px solid #E3EAF0; border-bottom:1px solid #E3EAF0; }}
.rguide a {{ display:block; padding:12px 16px 12px 0; text-decoration:none !important; border-left:none; }}
.rguide a + a {{ padding-left:16px; border-left:1px solid #E3EAF0; }}
.rguide b {{ display:block; color:{NAVY}; font-size:.98rem; font-weight:700; }}
.rguide span {{ display:block; color:#55677A; font-size:.9rem; margin-top:2px; }}
.rguide a:hover b {{ color:{TEAL_DARK}; }}
.fq {{ font-size:1rem; font-weight:650; color:#46586A; margin:.3rem 0 .35rem; }}
.ans {{ display:flex; gap:14px; align-items:flex-start; background:#fff; border:1px solid #E6EBF1; border-radius:16px;
  padding:16px 20px; margin:0 0 1rem; }}
.ans > .ic {{ width:30px; height:30px; flex:0 0 auto; margin-top:2px; }}
.ans.ok > .ic {{ color:{TEAL}; }} .ans.warn > .ic {{ color:#C2552F; }} .ans.mixed > .ic {{ color:#8A6D1F; }} .ans.imp > .ic {{ color:{TEAL_DARK}; }}
.ans .ah {{ font-size:1.28rem; font-weight:740; color:{NAVY}; line-height:1.35; letter-spacing:-0.01em; }}
.ans .ah2 {{ font-size:1.08rem; font-weight:680; color:{NAVY}; line-height:1.45; }}
.ans .as2 {{ font-size:1rem; color:#3E5164; margin-top:.35rem; line-height:1.55; }}
.ans .seemore {{ display:inline-block; margin-top:.4rem; font-size:.92rem; font-weight:650; color:{TEAL_DARK} !important; }}
.kgrid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:16px; margin:.2rem 0 .6rem; }}
@media (max-width: 980px) {{ .kgrid {{ grid-template-columns:1fr; }} }}
.kg {{ background:#fff; border:1px solid #E6EBF1; border-radius:18px; padding:16px 20px 14px; min-width:0; }}
.kgh {{ display:flex; gap:8px; align-items:center; font-size:1rem; font-weight:720; color:{TEAL_DARK}; margin-bottom:.6rem; }}
.kp {{ padding-bottom:12px; border-bottom:1px solid #EEF2F6; margin-bottom:12px; }}
.kt {{ font-size:1rem; font-weight:680; color:{NAVY}; margin-bottom:6px; }}
.ks2 .kt {{ font-size:.96rem; }}
.kn {{ font-size:.9rem; color:#55677A; margin:6px 0 4px; line-height:1.45; }}
.ksub {{ font-size:.86rem; font-weight:650; color:#55677A; margin:8px 0 2px; }}
.cmpv {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 10px; margin:2px 0 6px; }}
.cmpv .lb, .cmpv .ls {{ font-size:.86rem; color:#66778A; font-weight:600; }}
.cmpv b {{ font-size:1.35rem; font-weight:720; color:#5B6B7A; letter-spacing:-0.01em; }}
.kp .cmpv b {{ font-size:1.65rem; }}
.cmpv .sv {{ color:{NAVY} !important; }} .cmpv .ar {{ color:#9FB0C0; font-size:1.1rem; }}
.chg2 {{ display:inline-block; border-radius:999px; padding:2px 11px; font-weight:650; font-size:.88rem; margin:2px 0 2px; }}
.chg2.good {{ background:#E0F2EE; color:{TEAL_DARK}; }} .chg2.bad {{ background:#FCE9E4; color:#A9412B; }}
.chg2.neutral {{ background:#E8EEF5; color:{NAVY_2}; }} .chg2.flat {{ background:#EEF1F4; color:#56677A; font-weight:600; cursor:help; }}
.capbar {{ margin:6px 0 8px; }}
.cbr {{ display:grid; grid-template-columns:132px 1fr 64px; gap:10px; align-items:center; font-size:.88rem; color:#46586A; margin:4px 0; }}
.cbr b {{ color:{NAVY}; text-align:right; font-weight:680; }}
.cbr .trk {{ height:10px; background:#EEF2F6; border-radius:6px; overflow:hidden; }}
.cbr .trk i {{ display:block; height:100%; border-radius:6px; }}
.cbr .trk i.d {{ background:{TEAL}; }} .cbr .trk i.d.over {{ background:#D9785A; }} .cbr .trk i.c {{ background:{NAVY}; opacity:.75; }}
.dins {{ margin:1rem 0 .5rem; padding:18px 22px 6px; background:linear-gradient(120deg, #FFFFFF, #F2F8F7); border:1px solid #DDE9E6; border-radius:18px; }}
.dins .dt {{ font-size:1.22rem; font-weight:750; color:{NAVY}; letter-spacing:-0.01em; margin-bottom:.4rem; }}
.dins .di {{ display:flex; gap:14px; padding:12px 0; border-top:1px solid #E3ECEA; }}
.dins .di:first-of-type {{ border-top:none; }}
.dins .di > .ic {{ width:24px; height:24px; color:{TEAL_DARK}; flex:0 0 auto; margin-top:3px; }}
.dins .dh {{ font-size:1.06rem; font-weight:720; color:{NAVY}; margin-bottom:3px; }}
.dins p {{ font-size:.98rem; color:#34475A; margin:0 0 4px; line-height:1.55; }}
.dins p.dn {{ color:{TEAL_DARK}; font-weight:600; font-size:.94rem; }}
.tq {{ font-size:1.08rem; font-weight:720; color:{NAVY}; margin:.6rem 0 .2rem; }}
.ta {{ font-size:.97rem; color:#34475A; margin:0 0 .6rem; line-height:1.55; max-width:52em; }}
.bdnote {{ font-size:.93rem; color:#34475A; background:{PANEL}; border-radius:12px; padding:12px 16px; margin:.5rem 0 .8rem; line-height:1.55; }}
.bdnote b {{ color:{NAVY}; }}
.cmpempty {{ font-size:.97rem; color:#46586A; background:{PANEL}; border-radius:12px; padding:14px 16px; margin:.6rem 0; }}
.mwrap {{ overflow-x:auto; margin:.6rem 0 .3rem; border:1px solid #E6EBF1; border-radius:16px; background:#fff; }}
.cmpmx {{ border-collapse:collapse; width:100%; min-width:560px; font-size:.94rem; }}
.cmpmx th, .cmpmx td {{ padding:9px 14px; text-align:left; vertical-align:top; border-top:1px solid #EEF2F6; }}
.cmpmx thead th {{ border-top:none; background:#FAFBFC; vertical-align:bottom; }}
.cmpmx tbody th {{ color:#46586A; font-weight:600; width:24%; }}
.cmpmx td b {{ color:{NAVY}; font-weight:680; }}
.cmpmx .mo {{ font-weight:740; color:{NAVY}; font-size:1.02rem; }}
.cmpmx .mq {{ font-weight:400; color:#46586A; font-size:.85rem; line-height:1.4; margin-top:3px; }}
.cmpmx .mt {{ font-weight:400; color:#7A8A9A; font-size:.78rem; margin-top:3px; }}
.cmpmx tr.grp th {{ background:{PANEL}; color:{TEAL_DARK}; font-size:.86rem; font-weight:700; padding:7px 14px; }}
.cmpmx .mdiff {{ font-size:.82rem; margin-top:2px; color:#56677A; }}
.cmpmx .mdiff.good {{ color:{TEAL_DARK}; }} .cmpmx .mdiff.bad {{ color:#A9412B; }}
.cmpmx .st {{ display:inline-block; font-size:.8rem; font-weight:700; border-radius:999px; padding:2px 9px; }}
.cmpmx .st.good {{ background:#E0F2EE; color:{TEAL_DARK}; }} .cmpmx .st.warn {{ background:#FFF3DC; color:#8A5A00; }}
.cmpmx .st.bad {{ background:#FCE9E4; color:#A9412B; }}
.explore2 {{ margin:2.2rem 0 .5rem; padding-top:1.4rem; border-top:1px solid #E3EAF0; }}
.explore2 .et {{ font-size:1.3rem; font-weight:740; color:{NAVY}; letter-spacing:-0.01em; }}
.explore2 p {{ font-size:.98rem; color:#46586A; margin:.3rem 0 .6rem; max-width:48em; }}
/* ---- v5.2 Results: overview + tabs ---- */
.st-key-reshead {{ margin-bottom:.4rem; flex-wrap:wrap; gap:12px; }}
.st-key-reshead .ovhead {{ margin-bottom:0 !important; }}
.stale2 span {{ flex:1; }}
.scols {{ display:grid; grid-template-columns:1.15fr 1fr; gap:14px; margin:.2rem 0 .8rem; }}
@media (max-width: 860px) {{ .scols {{ grid-template-columns:1fr; }} }}
.scol {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:14px 18px 6px; }}
.sch {{ font-size:.95rem; font-weight:720; color:{TEAL_DARK}; margin-bottom:.4rem; }}
.sg {{ padding:8px 0; border-top:1px solid #EEF2F6; }} .sch + .sg {{ border-top:none; }}
.sl {{ font-size:.84rem; font-weight:650; color:#66778A; }}
.sv1 {{ font-size:1.05rem; font-weight:680; color:{NAVY}; margin-top:2px; }}
.sv2 {{ font-size:.9rem; color:#55677A; margin-top:1px; line-height:1.45; }}
.snone {{ font-size:.97rem; color:#55677A; padding:6px 0 10px; }}
.rbh {{ font-size:.92rem; font-weight:720; color:{TEAL_DARK}; margin-bottom:3px; }}
.evid {{ display:flex; flex-wrap:wrap; gap:10px 32px; margin:.7rem 0 .2rem; }}
.evid div {{ display:flex; flex-direction:column; min-width:150px; }}
.evid b {{ font-size:1.9rem; font-weight:770; color:{NAVY}; letter-spacing:-0.02em; line-height:1.1; }}
.evid span {{ font-size:.9rem; color:#46586A; margin-top:3px; max-width:15em; line-height:1.35; }}
.dins .dh span, .dins .dl {{ display:block; font-size:.76rem; font-weight:700; color:#7A8A9A; letter-spacing:.01em; margin-bottom:1px; }}
.dins p {{ margin:4px 0 4px; }}
.xh {{ font-size:1.45rem; font-weight:760; color:{NAVY}; letter-spacing:-0.015em; margin:2.2rem 0 .1rem; padding-top:1.4rem;
  border-top:1px solid #E3EAF0; }}
.xs {{ font-size:1rem; color:#46586A; margin:0 0 .4rem; }}
.st-key-maintabs [data-baseweb="tab-list"] {{ gap:6px; overflow-x:auto; scrollbar-width:thin; border-bottom:1px solid #DCE4EC; }}
.st-key-maintabs [data-baseweb="tab-list"] > button[role="tab"] {{ padding:10px 18px !important; height:auto; }}
.st-key-maintabs [data-baseweb="tab-list"] > button[role="tab"] p {{ font-size:1.08rem !important; font-weight:700 !important; white-space:nowrap; }}
.st-key-maintabs [data-baseweb="tab-list"] > button[aria-selected="true"] p {{ color:{NAVY} !important; }}
.st-key-maintabs [data-baseweb="tab-highlight"] {{ background-color:{TEAL} !important; height:3px; }}
.st-key-trendnav {{ margin:.2rem 0 .6rem; }}
.st-key-trendnav [data-testid="stButtonGroup"] {{ overflow-x:auto; }}
.st-key-trendnav button p {{ font-size:.92rem !important; }}
.tq {{ font-size:1.12rem; font-weight:720; color:{NAVY}; margin:.8rem 0 .4rem; }}
.tq2 {{ font-size:1.02rem; font-weight:700; color:{NAVY}; margin:.9rem 0 .25rem; }}
details.why {{ margin:.2rem 0 .5rem; font-size:.92rem; color:#34475A; }}
details.why summary {{ cursor:pointer; color:{TEAL_DARK}; font-weight:650; list-style:none; display:inline-flex; gap:6px; align-items:center; }}
details.why summary::-webkit-details-marker {{ display:none; }}
details.why summary::before {{ content:"i"; display:inline-flex; width:16px; height:16px; border-radius:50%; border:1.5px solid {TEAL};
  font-size:.7rem; font-weight:800; align-items:center; justify-content:center; font-family:Georgia, serif; }}
details.why p {{ margin:.35rem 0 0 22px; line-height:1.55; max-width:52em; }}
.wyt {{ background:#fff; border:1px solid #E6EBF1; border-radius:14px; padding:12px 18px; margin:.2rem 0 .8rem; }}
.wyh, .wyh2 {{ font-size:.95rem; font-weight:720; color:{TEAL_DARK}; }}
.wyh2 {{ margin:.6rem 0 .1rem; }}
.wyg {{ font-size:1.05rem; font-weight:700; color:{NAVY}; margin:.2rem 0 .1rem; }}
.wyt ul {{ margin:.2rem 0 .2rem 1.1rem; padding:0; }} .wyt li {{ font-size:.95rem; color:#34475A; margin:.15rem 0; }}
.cmpstart {{ background:linear-gradient(120deg, #FFFFFF, #F2F8F7); border:1px solid #DDE9E6; border-radius:16px; padding:16px 20px; margin:.2rem 0 .7rem; }}
.cmpstart .ch {{ font-size:1.15rem; font-weight:740; color:{NAVY}; }}
.cmpstart p {{ font-size:.97rem; color:#34475A; margin:.3rem 0 .2rem; }}
.cmpstart .steps {{ display:flex; flex-wrap:wrap; gap:6px 0; margin:.5rem 0 .1rem; padding:0; list-style:none; counter-reset:st; }}
.cmpstart .steps li {{ counter-increment:st; font-size:.88rem; font-weight:650; color:{TEAL_DARK}; }}
.cmpstart .steps li::before {{ content:counter(st); display:inline-flex; width:20px; height:20px; border-radius:50%; background:{TEAL_LIGHT};
  align-items:center; justify-content:center; font-size:.75rem; margin-right:6px; }}
.cmpstart .steps li + li::before {{ margin-left:14px; }}
.st-key-cmpactions {{ margin:.2rem 0 .6rem; }}
.cmpmx tr.same td {{ color:#7A8A9A; }}
/* ---- v5.3 Results: interactive tabs + connected overview ---- */
.st-key-restabs {{ position:sticky; top:0; z-index:20; background:rgba(245,247,250,.92); backdrop-filter:blur(8px);
  padding:8px 6px; margin:.6rem 0 1rem; border-radius:16px; border:1px solid #E3EAF0; flex-wrap:nowrap; overflow-x:auto; }}
.st-key-restabs button {{ border-radius:12px !important; min-height:2.6rem; padding:0 18px !important;
  transition:background-color .18s ease, color .18s ease; white-space:nowrap; }}
.st-key-restabs button p {{ font-size:1rem !important; font-weight:680 !important; white-space:nowrap; }}
.st-key-restabs [data-testid="stBaseButton-primary"] {{ background:{NAVY} !important; color:#fff !important; border:none !important;
  box-shadow:0 4px 12px -6px rgba(11,37,69,.6); }}
.st-key-restabs [data-testid="stBaseButton-tertiary"] {{ color:#46586A !important; }}
.st-key-restabs [data-testid="stBaseButton-tertiary"]:hover {{ background:#E8EEF5 !important; color:{NAVY} !important; }}
@media (max-width: 640px) {{ .st-key-restabs button {{ padding:0 12px !important; }} .st-key-restabs button p {{ font-size:.92rem !important; }} }}
.st-key-ovintro {{ margin:0 0 .6rem; flex-wrap:wrap; gap:10px; }}
.ovt .ovh {{ font-size:1.5rem; font-weight:760; color:{NAVY}; letter-spacing:-0.015em; }}
.ovt p {{ font-size:1rem; color:#46586A; margin:.15rem 0 0; }}
[class*="st-key-stg_"] {{ position:relative; padding:0 0 1.4rem 30px; border-left:2px solid #D6E7E3; margin-left:9px; gap:.4rem; }}
[class*="st-key-stg_"]::before {{ content:""; position:absolute; left:-8px; top:2px; width:14px; height:14px; border-radius:50%;
  background:#fff; border:3px solid {TEAL}; }}
.st-key-stg_d {{ border-left-color:transparent; }}
.stg {{ font-size:.82rem; font-weight:720; color:{TEAL_DARK}; letter-spacing:.02em; margin:-1px 0 .35rem; }}
.rbase {{ margin-top:.2rem; }}
.kv {{ display:flex; justify-content:space-between; gap:12px; padding:6px 0; border-top:1px solid #EEF2F6; font-size:.95rem; }}
.sch + .kv {{ border-top:none; }} .kv span {{ color:#55677A; }} .kv b {{ color:{NAVY}; font-weight:650; text-align:right; }}
.hero2 {{ border-radius:20px; padding:20px 24px 16px; background:#fff; border:1px solid #E6EBF1; }}
.hero2.warn {{ background:linear-gradient(120deg, #FFFFFF 0%, #FDF3EF 100%); border-color:#F2D9CF; }}
.hero2.ok {{ background:linear-gradient(120deg, #FFFFFF 0%, #EEF7F5 100%); border-color:#D6E9E5; }}
.hero2.mixed {{ background:linear-gradient(120deg, #FFFFFF 0%, #FBF6EA 100%); border-color:#EEE3C8; }}
.hero2 .hh {{ display:flex; gap:12px; align-items:flex-start; font-size:1.42rem; font-weight:760; color:{NAVY}; line-height:1.3;
  letter-spacing:-0.012em; }}
.hero2 .hh .ic {{ width:30px; height:30px; flex:0 0 auto; margin-top:1px; }}
.hero2.warn .hh .ic {{ color:#C2552F; }} .hero2.ok .hh .ic {{ color:{TEAL}; }} .hero2.mixed .hh .ic {{ color:#8A6D1F; }}
.hero2 .evid {{ margin:.9rem 0 .2rem 42px; }}
.hero2 .hc {{ margin:.5rem 0 0 42px; font-size:.97rem; color:#3E5164; line-height:1.5; }}
.st-key-ansacts {{ margin-left:42px; }}
.eband {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:0; background:#fff; border:1px solid #E6EBF1;
  border-radius:18px; overflow:hidden; }}
@media (max-width: 980px) {{ .eband {{ grid-template-columns:1fr; }} }}
.ecol {{ padding:16px 20px 12px; min-width:0; }} .ecol + .ecol {{ border-left:1px solid #EEF2F6; }}
@media (max-width: 980px) {{ .ecol + .ecol {{ border-left:none; border-top:1px solid #EEF2F6; }} }}
.eh {{ display:flex; gap:8px; align-items:center; font-size:1.02rem; font-weight:720; color:{TEAL_DARK}; margin-bottom:.4rem; }}
.cmpr {{ padding:8px 0 10px; border-bottom:1px solid #F0F3F6; }} .cmpr:last-child {{ border-bottom:none; }}
.cl {{ font-size:.95rem; font-weight:680; color:{NAVY}; margin-bottom:6px; }}
.bp {{ display:grid; grid-template-columns:96px minmax(60px,1fr) minmax(92px,max-content); gap:10px; align-items:center; margin:3px 0; }}
.bn {{ font-size:.84rem; color:#55677A; font-weight:600; }}
.bt {{ position:relative; height:12px; background:#EEF2F6; border-radius:7px; }}
.bt i {{ display:block; height:100%; border-radius:7px; }} .bt i.b0 {{ background:{BASE}; }} .bt i.b1 {{ background:{TEAL}; }}
.bt .cap {{ position:absolute; top:-4px; bottom:-4px; width:3px; background:{NAVY}; border-radius:2px; transform:translateX(-1px); }}
.bp b {{ font-size:1.06rem; font-weight:740; color:{NAVY}; text-align:right; white-space:nowrap; }}
.cd {{ margin-top:4px; }} .cnote {{ font-size:.86rem; color:#55677A; margin-top:4px; line-height:1.45; }}
.wq {{ font-size:.92rem; font-weight:720; color:#34475A; margin:.3rem 0 .1rem; }}
.wmini {{ display:grid; grid-template-columns:auto auto; justify-content:space-between; gap:3px 12px; font-size:.9rem; padding:4px 0 8px; }}
.wmini span {{ color:#55677A; }} .wmini b {{ color:{NAVY}; font-weight:680; text-align:right; }}
.imphl {{ display:flex; gap:12px; align-items:flex-start; margin:.8rem 0 0; padding:12px 16px; border-radius:14px; background:{PANEL}; }}
.imphl .ic {{ width:22px; height:22px; color:{TEAL_DARK}; flex:0 0 auto; margin-top:2px; }}
.ih1 {{ font-size:.82rem; font-weight:720; color:{TEAL_DARK}; }} .ih2 {{ font-size:1rem; color:{NAVY}; font-weight:620; line-height:1.45; }}
.dt2 {{ font-size:1.25rem; font-weight:760; color:{NAVY}; margin:0 0 .3rem; letter-spacing:-0.01em; }}
[class*="st-key-ins_row_"] {{ background:#fff; border:1px solid #E6EBF1; border-radius:16px; padding:12px 16px 4px; gap:0; }}
.di2 {{ display:flex; gap:12px; }} .di2 > .ic {{ width:24px; height:24px; color:{TEAL_DARK}; flex:0 0 auto; margin-top:2px; }}
.di2 .f {{ font-size:1.06rem; font-weight:720; color:{NAVY}; margin-bottom:4px; }}
.di2 .w {{ font-size:.95rem; color:#34475A; margin:2px 0; line-height:1.5; }}
.di2 .w span {{ font-weight:700; color:#66778A; margin-right:6px; font-size:.84rem; }}
[class*="st-key-ins_row_"] [data-testid="stButton"] {{ margin-left:36px; }}
.mstrip {{ display:flex; flex-wrap:wrap; gap:6px 20px; font-size:.88rem; color:#46586A; margin:.2rem 0 .3rem; }}
.mstrip b {{ color:{NAVY}; margin-left:4px; }}
.mstrip .k {{ display:inline-block; width:22px; height:0; vertical-align:middle; margin-right:6px; }}
.mstrip .k.dot {{ border-top:2px dotted {TEAL_DARK}; }} .mstrip .k.dotb {{ border-top:2px dotted {BASE}; }}
.mstrip .k.dash {{ border-top:2px dashed #D9785A; }}
.tq3 {{ font-size:.95rem; font-weight:720; color:#34475A; margin:.6rem 0 .2rem; }}
.st-key-trendnav [data-testid="stButtonGroup"] button[aria-checked="true"], .st-key-trendnav [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] {{
  background:{TEAL_LIGHT} !important; color:{TEAL_DARK} !important; border-color:{TEAL} !important; }}
.st-key-exback {{ margin:.8rem 0 .4rem; }}
.prog {{ display:flex; flex-wrap:wrap; gap:6px; list-style:none; padding:0; margin:.3rem 0 .2rem; counter-reset:p; }}
.prog li {{ counter-increment:p; font-size:.88rem; font-weight:650; color:#66778A; background:#EEF2F6; border-radius:999px; padding:4px 12px 4px 6px; }}
.prog li::before {{ content:counter(p); display:inline-flex; width:20px; height:20px; border-radius:50%; background:#fff; color:#66778A;
  align-items:center; justify-content:center; font-size:.75rem; margin-right:6px; }}
.prog li.done {{ background:{TEAL_LIGHT}; color:{TEAL_DARK}; }} .prog li.done::before {{ content:"✓"; color:{TEAL_DARK}; }}
.prog li.now {{ background:{NAVY}; color:#fff; }} .prog li.now::before {{ color:{NAVY}; }}
.curplan {{ display:flex; flex-wrap:wrap; gap:4px 12px; align-items:baseline; background:#fff; border:1px solid #E6EBF1; border-radius:14px;
  padding:10px 16px; margin:.4rem 0 .6rem; }}
.curplan span {{ font-size:.82rem; font-weight:700; color:{TEAL_DARK}; }} .curplan b {{ color:{NAVY}; font-size:.98rem; }}
.curplan em {{ font-style:normal; font-size:.85rem; color:#66778A; }}
/* Fallback so primary buttons keep the navy brand colour even if .streamlit/config.toml is not deployed
   (Streamlit's default theme colour is red). Keyed overrides above (hero, navigation) still take precedence. */
button[data-testid="stBaseButton-primary"] {{ background-color:{NAVY}; border-color:{NAVY}; color:#fff; }}
button[data-testid="stBaseButton-primary"]:hover {{ background-color:{NAVY_2}; border-color:{NAVY_2}; color:#fff; }}
button[data-testid="stBaseButton-primary"]:focus:not(:active) {{ border-color:{NAVY}; color:#fff; }}
.rangehint {{ font-size:.82rem; color:#55677A; margin:-.4rem 0 .3rem; }}
.rangehint.bad {{ color:#A33A1E; font-weight:600; }}
.admv {{ margin:.1rem 0 0; }}
.admv .main {{ background:{TEAL_LIGHT}; border-radius:12px; padding:10px 14px; }}
.admv .lab {{ font-size:.82rem; font-weight:650; color:{TEAL_DARK}; }}
.admv .num {{ font-size:1.6rem; font-weight:770; color:{NAVY}; letter-spacing:-.01em; }}
.admv .num small {{ font-size:.9rem; font-weight:600; color:#46586A; margin-left:4px; letter-spacing:0; }}
.admv .chg {{ font-size:.88rem; color:#34475A; }}
.admv .hist {{ padding:8px 14px 0; font-size:.86rem; color:#55677A; }}
.admv .hist b {{ color:#34475A; font-weight:700; }}
.st-key-aboutgrp {{ background:{PANEL}; border-radius:14px; padding:12px 16px 4px; margin-top:.3rem; gap:.35rem; }}
.agh {{ font-size:.82rem; font-weight:700; color:{TEAL_DARK}; }}
.agn {{ font-size:1.02rem; font-weight:700; color:{NAVY}; margin-bottom:.2rem; }}
.agm {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:10px; }}
.agm b {{ display:block; font-size:1.3rem; font-weight:740; color:{NAVY}; }}
.agm span {{ font-size:.84rem; color:#55677A; }}
.agf {{ font-size:.86rem; color:#55677A; margin-top:.35rem; }}
.st-key-aboutgrp [data-testid="stButton"] button {{ padding-left:0 !important; min-height:0 !important; }}
.lvsub {{ font-size:.82rem; color:#55677A; margin:.15rem 0 0; }}
</style>
"""


# v5.4 shared design layer: global navigation, page rhythm, controls and motion. Loaded after CSS so it wins.
NAV_H, NAV_H_C, NAV_TOP, NAV_TOP_C = 72, 56, 12, 8
STICKY_BELOW_NAV = NAV_TOP_C + NAV_H_C + 12          # where page-level sticky bars sit under the compact header
DESIGN_CSS = f"""
<style>
/* ---- tokens ---- */
.stApp {{ --hcp-navy:{NAVY}; --hcp-teal:{TEAL}; --hcp-teal-d:{TEAL_DARK}; --hcp-ink:{INK}; --hcp-muted:#4E6072;
  --hcp-line:#E3E9EF; --hcp-ease:cubic-bezier(.2,.7,.2,1); --hcp-nav:{STICKY_BELOW_NAV}px;
  background:radial-gradient(1100px 420px at 88% -140px, rgba(14,138,126,.10), rgba(14,138,126,0) 70%),
             radial-gradient(900px 360px at -5% -180px, rgba(11,37,69,.07), rgba(11,37,69,0) 70%), {CANVAS}; }}

/* ---- global navigation: fixed, truly centred, compact after scrolling ---- */
/* Streamlit's header is fixed over the top ~60px of the window (z-index far above page content) and its toolbar
   strip spans the full width. Transparent, but it swallowed clicks on the top of the nav, and on all of the compact
   nav after scrolling. Only its real controls may take clicks; everything else lets them through. */
[data-testid="stHeader"], [data-testid="stHeader"] * {{ pointer-events:none !important; }}
[data-testid="stHeader"] button, [data-testid="stHeader"] a, [data-testid="stHeader"] [role="button"],
[data-testid="stHeader"] input, [data-testid="stHeader"] select {{ pointer-events:auto !important; }}
.block-container {{ padding-top:{NAV_TOP + NAV_H + 12}px !important; }}
/* Streamlit gives the container an inline width; left/right alone would let it overflow the right edge */
/* above Streamlit's header layer (999990) so nothing in that strip can sit over the nav; below popovers, menus and
   tooltips (1000060+) so the Help popover and dropdowns still open over it */
.st-key-topnav {{ position:fixed !important; z-index:999995; top:{NAV_TOP}px; left:3rem; right:3rem; height:{NAV_H}px;
  width:auto !important; max-width:none !important; min-width:0 !important;
  box-sizing:border-box; margin:0 !important; display:grid !important;
  grid-template-columns:minmax(0, 1fr) auto minmax(0, 1fr); align-items:center; column-gap:16px;
  padding:0 16px !important; background:rgba(255,255,255,.80); -webkit-backdrop-filter:saturate(1.6) blur(14px);
  backdrop-filter:saturate(1.6) blur(14px); border:1px solid rgba(11,37,69,.08) !important; border-radius:18px;
  box-shadow:0 1px 2px rgba(11,37,69,.04), 0 10px 28px -20px rgba(11,37,69,.22);
  transition:top .28s var(--hcp-ease), height .28s var(--hcp-ease), border-radius .28s var(--hcp-ease),
             box-shadow .28s var(--hcp-ease), background-color .28s var(--hcp-ease); }}
.st-key-topnav > * {{ min-width:0; width:auto !important; flex:none !important; }}
.st-key-topnav > :nth-child(1) {{ justify-self:start; }}
.st-key-topnav > :nth-child(2) {{ justify-self:center; }}
.st-key-topnav > :nth-child(3) {{ justify-self:end; }}
.st-key-navlinks {{ gap:10px !important; padding:0 !important; }}
.st-key-navlinks button {{ position:relative; min-height:42px !important; height:42px; padding:0 18px !important; cursor:pointer;
  transition:background-color .2s ease, color .2s ease !important; }}
.st-key-navlinks button::after {{ content:""; position:absolute; left:50%; bottom:4px; width:0; height:2px; border-radius:2px;
  background:{TEAL}; transform:translateX(-50%); transition:width .25s var(--hcp-ease); pointer-events:none; }}
.st-key-navlinks button * {{ pointer-events:none; }}
.st-key-navlinks [data-testid="stBaseButton-primary"], .st-key-navlinks button[kind="primary"] {{
  background:rgba(11,37,69,.06) !important; color:{NAVY} !important; }}
.st-key-navlinks [data-testid="stBaseButton-primary"]::after, .st-key-navlinks button[kind="primary"]::after {{ width:18px; }}
.brand2 {{ display:flex; align-items:center; gap:10px; }}
.brand2 .bmark {{ transition:width .28s var(--hcp-ease), height .28s var(--hcp-ease); }}
.brand2 .bsub {{ max-height:1.3em; overflow:hidden; transition:opacity .2s ease, max-height .28s var(--hcp-ease), margin .28s var(--hcp-ease); }}
body[data-hcp-nav="compact"] .st-key-topnav {{ top:{NAV_TOP_C}px; height:{NAV_H_C}px; border-radius:14px;
  background:rgba(255,255,255,.90); box-shadow:0 1px 2px rgba(11,37,69,.05), 0 14px 32px -20px rgba(11,37,69,.38); }}
body[data-hcp-nav="compact"] .brand2 .bsub {{ opacity:0; max-height:0; margin-top:0; }}
body[data-hcp-nav="compact"] .brand2 .bmark {{ width:26px; height:26px; }}
.st-key-nav_menu {{ display:none !important; }}
.st-key-nav_menu button {{ border-radius:999px !important; border:1px solid #E3E8EE !important; min-height:2.2rem; }}
[data-testid="stPopoverBody"] [class*="st-key-navm_"] button {{ justify-content:flex-start; border-radius:10px !important; }}
@media (max-width: 1099px) {{
  .st-key-topnav {{ grid-template-columns:minmax(0, 1fr) auto; }}
  .st-key-topnav > :has(.st-key-navlinks), .st-key-navlinks {{ display:none !important; }}
  .st-key-nav_menu {{ display:flex !important; }} }}
@media (max-width: 760px) {{
  .st-key-topnav {{ left:1rem; right:1rem; padding-left:14px !important; }}
  .block-container {{ padding-top:{NAV_TOP + NAV_H_C + 12}px !important; }}
  .st-key-topnav, body[data-hcp-nav="compact"] .st-key-topnav {{ height:{NAV_H_C}px; }}
  .brand2 .bname {{ font-size:1rem !important; }} }}

/* ---- page-level sticky elements sit below the header, never under it ---- */
.st-key-restabs {{ top:var(--hcp-nav) !important; z-index:20 !important; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-restabs) {{ position:sticky; top:var(--hcp-nav); z-index:20; }}

@media (min-width: 1280px) {{ .secnav {{ top:{NAV_TOP + NAV_H + 34}px !important; }} }}
.stApp [id] {{ scroll-margin-top:calc(var(--hcp-nav) + 24px); }}
/* zero-height helper frames (scrolling, header behaviour) take no space */
[data-testid="stElementContainer"]:has(> iframe[height="0"]), .stElementContainer:has(> iframe[height="0"]),
[data-testid="stElementContainer"]:has(iframe[data-testid="stIFrame"][height="0"]) {{ position:absolute !important;
  width:0 !important; height:0 !important; overflow:hidden !important; }}

/* style-only markdown blocks (this CSS) still take a slot and a gap in the page flow; the styles apply anyway */
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] style):not(:has(p, h1, h2, h3, span, svg, button, img, label, table, ul)) {{
  display:none !important; }}
/* Streamlit's hover link icon next to headings is not useful here */
[tabindex="-1"]:focus {{ outline:none; }}
[data-testid="stHeaderActionElements"], [data-testid="stMarkdownContainer"] h1 a[href^="#"] svg,
[data-testid="stMarkdownContainer"] h2 a[href^="#"] svg {{ display:none !important; }}
/* ---- typography: one hierarchy across pages ---- */
.ovhead h1, .ptitle h1 {{ font-size:clamp(2.1rem, 3.1vw, 2.7rem) !important; font-weight:760 !important;
  letter-spacing:-0.032em !important; line-height:1.08 !important; color:{NAVY} !important; }}
.ovhead p, .ptitle p {{ color:var(--hcp-muted); font-size:1.08rem; line-height:1.55; max-width:44em; }}
.qh h2, .stph h2, .sect h2 {{ letter-spacing:-0.022em !important; }}
.tq2, .xh, .dt2, .ovh {{ letter-spacing:-0.02em; }}
.rnote, .cnote, .qsub {{ color:var(--hcp-muted); }}

/* ---- controls: shared states ---- */
.stApp button {{ transition:background-color .18s ease, border-color .18s ease, color .18s ease, box-shadow .2s ease,
  transform .2s var(--hcp-ease); }}
.stApp [data-testid="stBaseButton-secondary"] {{ border-color:#D6DEE7 !important; }}
.stApp [data-testid="stBaseButton-secondary"]:hover {{ border-color:{TEAL} !important; color:{TEAL_DARK} !important;
  background:#F3FAF8 !important; }}
.block-container [data-testid="stBaseButton-primary"]:hover {{
  box-shadow:0 8px 18px -10px rgba(11,37,69,.55); }}
.stApp [data-testid="stBaseButton-tertiary"]:hover p {{ text-decoration:underline; text-underline-offset:3px;
  text-decoration-thickness:1px; }}
.st-key-topnav [data-testid="stBaseButton-tertiary"]:hover p, .st-key-restabs [data-testid="stBaseButton-tertiary"]:hover p,
.st-key-wl_cta [data-testid="stBaseButton-tertiary"]:hover p, [data-testid="stPopoverBody"] [data-testid="stBaseButton-tertiary"]:hover p {{
  text-decoration:none; }}
.stApp button:focus-visible, .stApp a:focus-visible, .stApp summary:focus-visible {{
  outline:2px solid {TEAL} !important; outline-offset:2px; }}
[data-testid="stExpander"] details {{ border:1px solid var(--hcp-line) !important; border-radius:14px !important;
  box-shadow:none !important; }}
[data-testid="stExpander"] summary {{ border-radius:14px; transition:background-color .18s ease; }}
[data-testid="stExpander"] summary:hover {{ background:#F6F9FB; }}
[data-testid="stButtonGroup"] button {{ transition:background-color .2s ease, color .2s ease, border-color .2s ease; }}

.ctanote {{ text-align:center; font-size:.9rem; color:var(--hcp-muted); margin:.4rem auto 0; max-width:40em; }}
/* ---- restrained motion, always optional ---- */
@keyframes hcpIn {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
.st-key-restabs ~ * .stg, .tq2 {{ animation:hcpIn .35s var(--hcp-ease) both; }}
@media (prefers-reduced-motion: reduce) {{
  .st-key-topnav, .st-key-navlinks button, .st-key-navlinks button::after, .brand2 .bsub, .brand2 .bmark, .stApp button {{
    transition:none !important; }}
  .st-key-restabs ~ * .stg, .tq2 {{ animation:none !important; }}
  html, [data-testid="stMain"], [data-testid="stAppViewContainer"] {{ scroll-behavior:auto !important; }} }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(DESIGN_CSS, unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def md(x):
    st.markdown(x, unsafe_allow_html=True)


def page_title(eyebrow, title, sub=None):
    md(f'<div class="ptitle"><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(title)}</h1>'
       + (f"<p>{sub}</p>" if sub else "") + "</div>")


def section(title, aside=None):
    md(f'<div class="sect"><h2>{esc(title)}</h2>' + (f"<span>{aside}</span>" if aside else "") + "</div>")


def note(text):
    md(f'<p class="note">{text}</p>')


def insight(text):
    md(f'<div class="insight1">{text}</div>')


def caution(text):
    md(f'<div class="caution">{text}</div>')


def tiles(items, accent_first=False):
    """items: (label, value, note[, unit])"""
    out = []
    for i, it in enumerate(items):
        label, value, nt = it[:3]
        unit = it[3] if len(it) > 3 else ""
        u = f" <small>{esc(unit)}</small>" if unit else ""
        out.append(f'<div class="tile{" accent" if accent_first and i == 0 else ""}"><div class="l">{esc(label)}</div>'
                   f'<div class="v">{esc(value)}{u}</div><div class="n">{nt}</div></div>')
    md('<div class="tiles">' + "".join(out) + "</div>")


def step(n, title, scope=None):
    tag = {"group": '<span class="scope group">Selected group only</span>',
           "all": '<span class="scope all">Whole hospital</span>'}.get(scope, "")
    md(f'<div class="step"><div class="n">{n}</div><h3>{esc(title)}</h3>{tag}</div>')


def change_chip(diff, unit, clear, better, dp=0, pct=None):
    """Green/red only for outcomes with a capacity direction; blue for inputs; grey when within noise."""
    if diff is None:
        return '<span class="chg flat">Not estimable</span>'
    if not clear or round(diff, dp) == 0:
        return '<span class="chg flat">≈ no clear change</span>'
    up = diff > 0
    if better is None:
        cls = "neutral"
    else:
        cls = "good" if (not up if better == "down" else up) else "bad"
    p = "" if pct is None else f" ({pct:+.1f}%)"
    return f'<span class="chg {cls}">{"▲" if up else "▼"} {abs(diff):,.{dp}f} {esc(unit)}{p}</span>'


def bullet_bar(beds, ref_b, ref_s, occ_s):
    """Capacity bullet chart: scenario average in use (fill), busy-day references (markers), available beds (line)."""
    vals = [beds, ref_b, ref_s, occ_s]
    lo = max(0, int(min(vals) * 0.9 // 100 * 100))
    hi = int((max(vals) * 1.04) // 100 * 100 + 100)
    pos = lambda v: 100 * (v - lo) / (hi - lo)
    return (f'<div class="bullet"><div class="track"><div class="fill" style="width:{pos(occ_s):.1f}%"></div>'
            f'<div class="mk" style="left:{pos(ref_b):.1f}%;background:{BASE}"></div>'
            f'<div class="mk" style="left:{pos(ref_s):.1f}%;background:{TEAL}"></div>'
            f'<div class="cap" style="left:{pos(beds):.1f}%"></div></div>'
            f'<div class="ax"><span>{lo:,}</span><span>scale starts at {lo:,} beds</span><span>{hi:,}</span></div></div>'
            f'<div class="blegend"><span><i style="background:#BFE3DD"></i>Average in use (scenario) <b>{occ_s:,.0f}</b></span>'
            f'<span><i style="background:{BASE}"></i>Busy-day reference, baseline <b>{ref_b:,.0f}</b></span>'
            f'<span><i style="background:{TEAL}"></i>scenario <b>{ref_s:,.0f}</b></span>'
            f'<span><i style="background:{NAVY}"></i>Beds available <b>{beds:,}</b></span></div>')


def compare_cards(records, current_key=None):
    cards = []
    for r in records:
        s = r["settings"]
        gap = r["beds"] - r["ref_scen"]
        assumptions = (f"Target {esc(s['diagnosis'])} S{s['severity']}{'' if s['age'] == 'All ages' else ' · ' + esc(s['age'])} · "
                       f"LOS −{s['reduction']}% · demand {s['demand']:+d}%"
                       + (f" · returns −{s['readmit']}%" if s["readmit"] else "")
                       + f"<br>{s['duration']} days · {'annual-average pattern' if s['season'] == 'Annual average' else 'from ' + esc(s['season'])}")
        bd = ("≈ no clear change" if not r["bd_clear"] else f"{r['bd']:+,.0f}")
        bdcls = "" if not r["bd_clear"] else ("good" if r["bd"] < 0 else "bad")
        w = r["waited_txt"]
        cards.append(
            f'<div class="cmpc{" cur" if r["key"] == current_key else ""}"><div class="nm">{esc(r["title"])}</div>'
            f'<div class="as">{assumptions}</div>'
            f'<div class="m"><span>Beds available</span><b>{r["beds"]:,}</b></div>'
            f'<div class="m"><span>Busy-day reference</span><b>{r["ref_base"]:,.0f} → {r["ref_scen"]:,.0f}</b></div>'
            f'<div class="m"><span>Spare (+) / short (−)</span><b class="{"good" if gap >= 0 else "bad"}">{gap:+,.0f}</b></div>'
            f'<div class="m"><span>Bed-days vs baseline</span><b class="{bdcls}">{bd}</b></div>'
            f'<div class="m"><span>Requests that wait</span><b>{w}</b></div>'
            f'<div class="m"><span>Target-group stay</span><b>{r["tlos_base"]:.1f} → {r["tlos"]:.1f} d</b></div>'
            f'<div class="m"><span>Modelled pressure</span><b class="{r["pressure"]}">{r["pressure"].capitalize()}</b></div></div>')
    md('<div class="cmp">' + "".join(cards) + "</div>")


def style_fig(fig, height=340, title=None, legend=True):
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=16, color=NAVY), x=0, xanchor="left"))
    fig.update_layout(
        height=height, margin=dict(l=8, r=16, t=52 if title else 28, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, system-ui, Arial, sans-serif", color=INK, size=14),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="white", font_size=13))
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED, size=13),
                     title_font=dict(size=13, color=MUTED))
    fig.update_yaxes(gridcolor="#E6EBF0", zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED, size=13),
                     title_font=dict(size=13, color=MUTED))
    return fig


def question(n, title, aside=None):
    md(f'<div class="qhead"><div class="qn">{n}</div><h2>{esc(title)}</h2>'
       + (f"<span>{esc(aside)}</span>" if aside else "") + "</div>")


def flow_card(title, tone, steps, footer):
    """Stays -> average stay -> bed-days, read left to right."""
    dot = TEAL if tone == "teal" else NAVY_2
    cells = []
    for i, (lab, val) in enumerate(steps):
        if i:
            cells.append('<div class="op">→</div>')
        cells.append(f'<div class="fs{" res" if i == len(steps) - 1 else ""}"><span>{esc(lab)}</span><b>{esc(val)}</b></div>')
    return (f'<div class="fcard"><div class="ft"><span class="dot" style="background:{dot}"></span>{esc(title)}</div>'
            f'<div class="fflow">{"".join(cells)}</div><div class="fn">{footer}</div></div>')


def proportion_bar(ini, ret):
    tot = ini + ret
    a = 100 * ini / tot
    return (f'<div class="pbar"><div class="track"><div style="width:{a:.1f}%;background:{TEAL}"></div>'
            f'<div style="width:{100 - a:.1f}%;background:{NAVY_2}"></div></div>'
            f'<div class="lg"><span><i style="background:{TEAL}"></i>Initial stays <b>{a:.0f}%</b></span>'
            f'<span>Total bed-days used <b>{tot:,}</b></span>'
            f'<span><i style="background:{NAVY_2}"></i>Return stays <b>{100 - a:.0f}%</b></span></div></div>')


def profile_block(title, rows):
    return (f'<div class="pfb"><div class="pt">{title}</div>'
            + "".join(f'<div class="pr"><span>{k}</span><b>{esc(v)}</b></div>' for k, v in rows) + "</div>")


def qhead(n, title, anchor=None):
    aid = f' id="{anchor}"' if anchor else ""
    md(f'<div class="qh"{aid}><span class="qi">{n:02d}</span><h2>{esc(title)}</h2></div>')


def step_head(n, title, sub, anchor, optional=False):
    opt = '<span class="stopt">Optional</span>' if optional else ""
    return (f'<div class="stph" id="{anchor}"><div class="stpl"><span class="stpn">Step {n}</span>{opt}</div>'
            f'<h2>{esc(title)}</h2><p class="qsub">{esc(sub)}</p></div>')


def step_nav(steps, optional=()):
    opt = '<span class="nopt">Optional</span>'
    items = "".join(
        f'<a href="#{a}" target="_self"><span class="sn">Step {i}{opt if i in optional else ""}</span><b>{esc(t)}</b>'
        f'<em>{esc(q)}</em></a>'
        for i, (a, t, q) in enumerate(steps, 1))
    return f'<nav class="stepnav" aria-label="Scenario steps">{items}</nav>'


def tip(text):
    return f'<span class="tip" tabindex="0" data-tip="{esc(text)}" aria-label="{esc(text)}">ⓘ</span>'


def stat_card(title, icon, tone, big, unit, subs):
    """One primary figure with three aligned supporting figures (labels may contain a tooltip span)."""
    return (f'<div class="sc2"><div class="hd"><span class="ic {tone}">{ICONS[icon]}</span>{title}</div>'
            f'<div class="big">{esc(big)}{f"<small>{esc(unit)}</small>" if unit else ""}</div><div class="sub{" n4" if len(subs) == 4 else ""}">'
            + "".join(f'<div><span>{it[0]}</span><b>{esc(it[1])}</b>'
                      + (f'<small class="sn">{esc(it[2])}</small>' if len(it) > 2 else "") + "</div>" for it in subs)
            + "</div></div>")


def total_bar(ini, ret, tip=""):
    tot = ini + ret
    a = 100 * ini / tot
    return (f'<div class="tbar"><div class="top"><span class="tl">Total Bed-days {tip}</span><b>{tot:,}</b></div>'
            f'<div class="track"><div style="width:{a:.1f}%;background:{TEAL}"></div>'
            f'<div style="width:{100 - a:.1f}%;background:{NAVY_2}"></div></div>'
            f'<div class="lg"><span><i style="background:{TEAL}"></i>Initial-stay Bed-days — <b>{a:.0f}%</b> '
            f'<em>{ini:,}</em></span>'
            f'<span><i style="background:{NAVY_2}"></i>Readmission Bed-days — <b>{100 - a:.0f}%</b> '
            f'<em>{ret:,}</em></span></div>'
            '</div>')


def group_card(name, primary, secondary, why, extra="", why_label="Why explore this group?"):
    return (f'<div class="gc"><div class="gname">{esc(name)}</div><div class="prim">'
            + "".join(f'<div><span>{k}</span><b>{esc(v)}</b></div>' for k, v in primary) + '</div><div class="sec">'
            + "".join(f'<div><span>{k}</span><b>{esc(v)}</b></div>' for k, v in secondary) + "</div>" + extra
            + f'<div class="why"><div class="wl">{esc(why_label)}</div><p>{esc(why)}</p></div></div>')


def key_insight(d):
    return (f'<div class="ki"><div class="kl">Key insights</div>'
            f'<div class="kr"><div><span>{esc(d["hi_label"])}</span><b>{esc(d["hi"])}</b></div>'
            f'<em>{d["hi_v"]:,.0f} <small>/ day</small></em></div>'
            f'<div class="kr"><div><span>{esc(d["lo_label"])}</span><b>{esc(d["lo"])}</b></div>'
            f'<em>{d["lo_v"]:,.0f} <small>/ day</small></em></div><p>{esc(d["note"])}</p></div>')


TERMS_HTML = (
    '<div class="terms"><div class="tt">Diagnosis groups</div><table>'
    '<tr><td>AMI</td><td>Heart attack (acute myocardial infarction)</td></tr>'
    '<tr><td>CHF</td><td>Heart failure (congestive heart failure)</td></tr>'
    '<tr><td>COPD</td><td>Chronic obstructive pulmonary disease</td></tr></table>'
    '<div class="tt">Severity levels</div><table>'
    '<tr><td>1</td><td>Minor</td></tr><tr><td>2</td><td>Moderate</td></tr>'
    '<tr><td>3</td><td>Major</td></tr><tr><td>4</td><td>Extreme</td></tr></table>'
    '<div class="tn">APR-DRG severity level as recorded in the data; used for grouping only.</div></div>')


def dx_card(name, desc, total_bd, share, admissions, returns, on):
    return (f'<div class="dxc{" on" if on else ""}"><div class="dn"><b>{esc(name)}</b></div>'
            f'<div class="dd">{esc(desc)}</div>'
            f'<div class="dv">{share:.0f}%<small>of total Bed-days</small></div>'
            f'<div class="bar"><div style="width:{share:.1f}%"></div></div>'
            f'<div class="ds"><b>{total_bd:,}</b> Bed-days · {admissions:,} initial admissions · '
            f'{returns:,} readmissions</div></div>')


SEVERITY_HTML = (
    '<div class="sevlv"><div class="tt">APR-DRG Severity of Illness</div>'
    '<div><b>Severity 1</b>Minor</div><div><b>Severity 2</b>Moderate</div><div><b>Severity 3</b>Major</div>'
    '<div><b>Severity 4</b>Extreme</div></div>')


def sev_head(share_tip=""):
    return ('<div class="sevr sevh"><div>Severity</div><div></div><div class="sv">Bed-days</div>'
            f'<div class="sp">Share (%){share_tip}</div><div></div></div>')


def sev_row(sev, name, total_bd, share, max_share, on):
    """Label | bar (scaled to the largest level) | Bed-days | share | selection state. No values inside the bar."""
    w = 100 * share / max_share if max_share else 0
    return (f'<div class="sevr{" on" if on else ""}"><div class="sl"><b>Severity {sev}</b><span>{esc(name)}</span></div>'
            f'<div class="bar"><div style="width:{w:.1f}%"></div></div>'
            f'<div class="sv">{total_bd:,}</div><div class="sp">{share:.0f}%</div>'
            f'<div class="act">{"✓ Selected" if on else "Select →"}</div></div>')


def age_compare(df, selected):
    cells = []
    for r in df.itertuples():
        on = selected == r.band
        cells.append(f'<div class="{"on" if on else ""}"><div class="ah">{esc(r.band)}<span>{r.share:.0f}%</span></div>'
                     f'<div class="ar">Initial admissions<b>{r.admissions:,}</b></div>'
                     f'<div class="ar">Avg initial stay<b>{r.mean_los:.1f} days</b></div>'
                     f'<div class="ar">Initial-stay bed-days<b>{r.ini_bd:,}</b></div></div>')
    return '<div class="agec">' + "".join(cells) + "</div>"


def capacity_rows(beds_eq, ref, eq_tip, ref_label=None, ref_tip=""):
    tip = lambda t: f'<span class="tip" title="{esc(t)}">ⓘ</span>'
    out = (f'<div class="cap"><div><span>≈ Beds in use on an average day {tip(eq_tip)}</span>'
           f'<b>{beds_eq:,.0f} <small>historical</small></b></div>')
    if ref is not None:
        out += (f'<div><span>{esc(ref_label)} {tip(ref_tip)}</span><b>{ref:,.0f} <small>modelled</small></b></div>')
    return out + "</div>"


SLCAP_HTML = (
    '<div class="terms" style="max-width:420px"><div class="tt">How it is calculated</div>'
    '<p>For each diagnosis, the unchanged simulation model is run with only that diagnosis\'s admissions (and the '
    'readmissions they generate), unlimited beds and no changes: 120 days × 3 runs, using the same settings as the '
    'simulator\'s planning reference. The value is the 95th-percentile daily occupancy.</p>'
    '<div class="tt">How to read it</div>'
    '<p>A busy-day planning reference if that service line were planned on its own. Planning separately needs '
    '{summ} beds in total; sharing one pool needs {pooled}, because busy days of different service lines do not all '
    'coincide. AMI, CHF and COPD are illustrative service lines, not separately staffed wards, and these are not '
    'guaranteed requirements.</p></div>')


def big_insight(text, supporting="", small=False):
    sup = f'<span class="bsup">{esc(supporting)}</span>' if supporting else ""
    return f'<div class="bigins{" sm" if small else ""}"><b>{esc(text)}</b>{sup}</div>'


def profile_head(kicker, name):
    return f'<div class="pfh"><span>{esc(kicker)}</span><b>{esc(name)}</b></div>'


def metric_grid(primary, secondary):
    """Items are (label, value) or (label, value, True) where True marks a value that follows the age group."""
    def cell(it, cls):
        lab, val = it[0], it[1]
        by_age = len(it) > 2 and it[2]
        return (f'<div class="{cls}{" age" if by_age else ""}"><span>{lab}</span><b>{esc(val)}</b></div>')
    return ('<div class="mg"><div class="mgp">' + "".join(cell(i, "p") for i in primary) + '</div><div class="mgs">'
            + "".join(cell(i, "s") for i in secondary) + "</div></div>")


def age_bed_use(df, selected, split=False):
    """Total Bed-days by Age Group: one bar per band on a shared scale (longest = largest band).
    split=True stacks Initial-stay (teal) and Readmission (navy) Bed-days inside the same total length."""
    mx = df.total_bd.max() or 1
    rows = []
    for r in df.itertuples():
        on = r.band == selected
        lab = "65+" if r.band == "65 and over" else r.band
        if split:
            bar = (f'<div class="i" style="width:{100 * r.init_bd / mx:.2f}%" title="Initial-stay Bed-days {r.init_bd:,}"></div>'
                   f'<div class="r" style="width:{100 * r.ret_bd / mx:.2f}%" title="Readmission Bed-days {r.ret_bd:,}"></div>')
        else:
            bar = f'<div class="t" style="width:{100 * r.total_bd / mx:.2f}%"></div>'
        rows.append(f'<div class="abr{" on" if on else ""}"><div class="abl">{lab}</div><div class="abt">{bar}</div>'
                    f'<div class="abv"><b>{r.total_bd:,}</b> Bed-days <span>({r.share:.0f}%)</span></div></div>')
    key = (f'<div class="abk"><span><i style="background:{TEAL}"></i>Initial-stay Bed-days</span>'
           f'<span><i style="background:{NAVY_2}"></i>Readmission Bed-days</span></div>') if split else ""
    return '<div class="abu">' + "".join(rows) + key + "</div>"


def goal_card(title, question, support, icon, on):
    """Guided starting point: the management question first, one short supporting line."""
    return (f'<div class="goalc{" on" if on else ""}"><div class="gic">{ICONS[icon]}</div>'
            f'<div class="gt">{esc(title)}</div><div class="gd">{esc(question)}</div>'
            f'<div class="gq">{esc(support)}</div></div>')


def period_strip(label, value, note=""):
    n = f'<div class="pn">{esc(note)}</div>' if note else ""
    return (f'<div class="period"><span class="pic">{ICONS["calendar"]}</span><div><div class="pl">{esc(label)}</div>'
            f'<div class="pv">{value}</div>{n}</div></div>')


def section_nav(items):
    links = "".join(f'<a href="#{a}" target="_self"><span class="sn">{i:02d}</span>{esc(t)}</a>'
                    for i, (a, t) in enumerate(items, 1))
    return f'<nav class="secnav" aria-label="On this page"><div class="snt">On This Page</div>{links}</nav>'


def heat_legend(unit, lo, hi):
    return (f'<div class="hleg"><div class="hlt">{esc(unit)}</div>'
            f'<div class="hlr"><span>0</span><div class="hlb"></div><span>{hi:,.0f}</span></div>'
            '<div class="hlr hlw"><span></span><div><span>Lower Demand</span><span>Higher Demand →</span></div>'
            '<span></span></div></div>')


def age_strip(under, over, selected):
    return (f'<div class="agestrip"><div class="al">Initial Bed-days by Age Group</div>'
            f'<div class="track"><div class="{"on" if selected == "Under 65" else ""}" style="width:{under:.1f}%"></div>'
            f'<div class="{"on" if selected == "65 and over" else ""} o" style="width:{over:.1f}%"></div></div>'
            f'<div class="lg"><span>Under 65 <b>{under:.0f}%</b></span><span>65+ <b>{over:.0f}%</b></span></div></div>')


def insight_line(label, text):
    return f'<div class="gi"><div class="gil">{esc(label)}</div><p>{esc(text)}</p></div>'


def time_insight(d, hi_label="Highest", lo_label="Lowest"):
    """One prominent pattern sentence + highest / lowest cards. Data qualifications live under the chart."""
    return (f'<div class="tins"><div class="tk">Key Insight</div><div class="th">{esc(d["head"])}</div><div class="tstats">'
            f'<div class="hi"><span>{esc(hi_label)}</span><b>{esc(d["hi"])}</b><em>{d["hi_v"]:,.0f} {esc(d["unit"])}</em></div>'
            f'<div class="lo"><span>{esc(lo_label)}</span><b>{esc(d["lo"])}</b><em>{d["lo_v"]:,.0f} {esc(d["unit"])}</em></div>'
            '</div></div>')


# =========================================================================== v5.0 Welcome
def _bed(x, y, filled, pulse=None):
    """One bed seen from above: frame + pillow. pulse = animation delay (s) for a bed that empties and refills."""
    cls = "bed" + (" on" if filled else "") + (" pulse" if pulse is not None else "")
    st_ = f' style="animation-delay:{pulse}s"' if pulse is not None else ""
    return (f'<g class="{cls}"{st_}><rect x="{x}" y="{y}" width="44" height="28" rx="7"/>'
            f'<rect class="pw" x="{x + 5}" y="{y + 6}" width="8" height="16" rx="3"/></g>')


def flow_art():
    """Abstract hero illustration: patients flowing along curves into a pool of beds, a short queue when beds are
    full, and a return loop after discharge. Purely illustrative (aria-hidden); no data are shown."""
    paths = ["M -20 70 C 90 70, 170 128, 318 120", "M -20 176 C 100 176, 190 160, 318 154",
             "M -20 292 C 110 292, 196 206, 318 188"]
    ret = "M 432 236 C 432 330, 170 344, 40 300"
    beds = []
    pulses = {(0, 3): 0, (2, 1): 3.5, (3, 2): 7}
    for r in range(4):
        for c in range(4):
            filled = not (r == 3 and c == 3)
            beds.append(_bed(330 + c * 54, 78 + r * 40, filled, pulses.get((r, c))))
    movers = []
    for i, p in enumerate(paths):
        for k, dur in enumerate((9 + i, 13 + i)):
            begin = f"-{(i * 2.3 + k * 4.1) % dur:.1f}s"
            movers.append(
                f'<circle r="3.6" class="dot"><animateMotion dur="{dur}s" begin="{begin}" repeatCount="indefinite" '
                f'path="{p}"/><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.12;.86;1" '
                f'dur="{dur}s" begin="{begin}" repeatCount="indefinite"/></circle>')
    movers.append(f'<circle r="3.2" class="dot ret"><animateMotion dur="16s" begin="-5s" repeatCount="indefinite" '
                  f'path="{ret}"/><animate attributeName="opacity" values="0;.9;.9;0" keyTimes="0;.1;.85;1" dur="16s" '
                  'begin="-5s" repeatCount="indefinite"/></circle>')
    static = "".join(f'<circle class="dot" cx="{x}" cy="{y}" r="3.4"/>' for x, y in
                     ((60, 72), (150, 112), (232, 124), (88, 177), (196, 160), (128, 270), (226, 214)))
    queue = "".join(f'<circle class="q" cx="{x}" cy="{y}" r="3.4" style="animation-delay:{d}s"/>'
                    for x, y, d in ((276, 196, 0), (291, 192, .4), (306, 189, .8)))
    return ('<div class="flowart" aria-hidden="true"><svg viewBox="10 36 545 312" preserveAspectRatio="xMidYMid meet">'
            '<defs><linearGradient id="fg" x1="0" x2="1"><stop offset="0" stop-color="#5FD1C1" stop-opacity="0"/>'
            '<stop offset=".55" stop-color="#5FD1C1" stop-opacity=".55"/><stop offset="1" stop-color="#5FD1C1" '
            'stop-opacity=".8"/></linearGradient><radialGradient id="glow" cx=".5" cy=".5" r=".5">'
            '<stop offset="0" stop-color="#1AA191" stop-opacity=".35"/><stop offset="1" stop-color="#1AA191" '
            'stop-opacity="0"/></radialGradient></defs>'
            '<ellipse cx="433" cy="153" rx="118" ry="108" fill="url(#glow)"/>'
            + "".join(f'<path class="fl" d="{p}"/>' for p in paths)
            + f'<path class="rl" d="{ret}"/>' + static + queue + "".join(beds)
            + '<g class="mv">' + "".join(movers) + "</g></svg></div>")


WL_ICONS = {
    "demand": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"><path d="M4 24 L12 16 L18 20 L28 9"/><path d="M21 9 H28 V16"/></svg>',
    "beds": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M4 9 V25"/><path d="M4 20 H28 V25"/><path d="M4 16 H28 V20"/>'
            '<rect x="7" y="11" width="6" height="5" rx="2"/></svg>',
    "flow": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M6 12 A10 10 0 0 1 25 10"/><path d="M25 4 V10 H19"/>'
            '<path d="M26 20 A10 10 0 0 1 7 22"/><path d="M7 28 V22 H13"/></svg>',
    "arrive": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
              '<circle cx="8" cy="16" r="2.5" fill="currentColor"/><circle cx="16" cy="16" r="2.5" fill="currentColor"/>'
              '<path d="M21 16 H28 M25 12 L28 16 L25 20"/></svg>',
    "stay": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><rect x="5" y="9" width="22" height="14" rx="4"/><rect x="8" y="12" width="5" '
            'height="8" rx="2"/></svg>',
    "wait": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
            '<circle cx="16" cy="16" r="10"/><path d="M16 10 V16 L20 19"/></svg>',
    "return": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"><path d="M26 12 A10 10 0 1 0 26 20"/><path d="M26 6 V12 H20"/></svg>',
}


def mechanism():
    """What the simulation recreates, in plain English (static; mirrors the hero's flow motif)."""
    items = [("arrive", "Patients arrive", "Day by day, following historical patterns."),
             ("stay", "Stay in a bed", "For a length of stay drawn from past records."),
             ("wait", "Wait if beds are full", "Queue for the next free bed."),
             ("return", "Some return after discharge", "And need a bed again.")]
    return ('<ol class="wl-mech">' + "".join(
        f'<li class="mi"><span class="mn">{WL_ICONS[k]}</span><span class="ml">{esc(t)}</span>'
        f'<span class="md">{esc(d)}</span></li>' for k, t, d in items) + "</ol>")


def wl_preview(kind):
    """Small schematic for each planning question, each showing a different idea. Illustrative only: no data and no
    simulated values. Demand: rising demand crossing a capacity line. Beds: steady demand against two bed levels,
    with the gap below the lower level marked. Flow: the same demand before and after an improvement."""
    if kind == "demand":
        line = "M8 62 C 34 60, 52 54, 74 44 S 120 22, 148 14"
        art = (f'<path d="{line} L148 72 L8 72 Z" class="area"/><path d="{line}" class="ln"/>'
               '<clipPath id="wqc-over"><rect x="0" y="0" width="156" height="30"/></clipPath>'
               f'<path d="{line}" class="ln over" clip-path="url(#wqc-over)"/>'
               '<line x1="6" x2="150" y1="30" y2="30" class="cap"/><text x="8" y="26" class="lbl">Beds</text>'
               '<circle cx="104" cy="30" r="3" class="hit"/>')
    elif kind == "beds":
        line = "M8 40 C 22 30, 34 30, 46 38 S 70 48, 82 36 S 106 24, 120 34 S 140 44, 148 36"
        art = ('<rect x="6" y="18" width="144" height="16" class="room"/>'
               '<clipPath id="wqc-gap"><rect x="0" y="0" width="156" height="34"/></clipPath>'
               f'<path d="{line} L148 34 L8 34 Z" class="gap" clip-path="url(#wqc-gap)"/>'
               f'<path d="{line}" class="ln dk"/>'
               '<line x1="6" x2="150" y1="34" y2="34" class="cap dim"/><line x1="6" x2="150" y1="18" y2="18" class="cap"/>'
               '<text x="8" y="13" class="lbl">More beds</text><text x="146" y="55" class="lbl dim e">Fewer beds</text>'
               '<path d="M152 31 V21 M149 24 L152 20.5 L155 24" class="arr"/>')
    else:
        art = ('<rect x="30" y="16" width="30" height="56" rx="5" class="before"/>'
               '<rect x="96" y="30" width="30" height="42" rx="5" class="b"/>'
               '<path d="M66 30 C 78 30, 82 38, 90 40" class="arr"/><path d="M85 37 L90.5 40.2 L85 43" class="arr"/>'
               '<line x1="96" x2="126" y1="16" y2="16" class="cap dim"/><rect x="96" y="16" width="30" height="14" rx="3" class="freed"/>'
               '<text x="45" y="80" class="lbl c">Before</text><text x="111" y="80" class="lbl c">After</text>')
    return ('<figure class="wqv" aria-hidden="true"><svg viewBox="0 0 156 84">' + art
            + '</svg><figcaption>Illustrative only, not simulation output</figcaption></figure>')


WELCOME_CSS = f"""
<style>
/* ---------------- v5.0 Welcome: editorial, one moving element ---------------- */
.st-key-wl_hero {{ position:relative; overflow:hidden; border-radius:30px; padding:52px 48px 46px 56px; margin:0 0 3rem;
  background:radial-gradient(900px 520px at 82% 42%, rgba(26,161,145,.26), rgba(26,161,145,0) 62%),
             linear-gradient(155deg, #0B2545 0%, #0F3057 58%, #0B2545 100%);
  box-shadow:0 18px 40px -18px rgba(11,37,69,.45); }}
.st-key-wl_hero [data-testid="stHorizontalBlock"] {{ align-items:center; }}
.wl-h1 {{ font-family:"Segoe UI Variable Display", "SF Pro Display", -apple-system, "Segoe UI", system-ui, sans-serif;
  color:#fff !important; font-size:clamp(2.6rem, 5vw, 4.4rem) !important; line-height:1.0 !important;
  letter-spacing:-0.04em; font-weight:760 !important; margin:0 0 22px !important; padding:0 !important; }}
.wl-lead {{ color:#D7E2EC; font-size:clamp(1.05rem, 1.3vw, 1.22rem); line-height:1.6; max-width:34em; margin:0 0 22px; }}
.wl-q {{ color:#fff; font-size:1.05rem; font-weight:600; line-height:1.45; max-width:30em; margin:0 0 8px;
  padding-left:14px; border-left:3px solid #3FC1B0; }}
.st-key-wl_cta {{ margin-top:14px; gap:10px; flex-wrap:wrap; }}
.st-key-wl_cta button {{ border-radius:999px !important; min-height:2.75rem; padding:0 20px !important;
  transition:background-color .2s ease, color .2s ease, transform .2s ease; }}
.st-key-wl_cta button p {{ font-size:.96rem !important; font-weight:650 !important; white-space:nowrap; }}
.st-key-wl_cta [data-testid="stBaseButton-primary"], .st-key-wl_cta button[kind="primary"] {{
  background:#fff !important; color:{NAVY} !important; border:none !important; }}
.st-key-wl_cta [data-testid="stBaseButton-primary"]:hover {{ background:{TEAL_LIGHT} !important; transform:translateY(-1px); }}
.st-key-wl_cta [data-testid="stBaseButton-tertiary"], .st-key-wl_cta button[kind="tertiary"] {{
  color:#D7E2EC !important; background:transparent !important; border:1px solid rgba(215,226,236,.35) !important; }}
.st-key-wl_cta [data-testid="stBaseButton-tertiary"]:hover {{ color:#fff !important; border-color:#fff !important; }}
.st-key-wl_cta button:focus-visible {{ outline:2px solid #3FC1B0 !important; outline-offset:3px; }}
.st-key-wl_start_cta {{ margin-top:14px; gap:10px; flex-wrap:wrap; }}
.st-key-wl_start_cta button {{ border-radius:999px !important; min-height:2.9rem; padding:0 22px !important;
  transition:background-color .2s ease, color .2s ease, transform .2s ease; }}
.st-key-wl_start_cta button p {{ font-size:1rem !important; font-weight:650 !important; white-space:nowrap; }}
.st-key-wl_start_cta [data-testid="stBaseButton-primary"], .st-key-wl_start_cta button[kind="primary"] {{
  background:#fff !important; color:{NAVY} !important; border:none !important; }}
.st-key-wl_start_cta [data-testid="stBaseButton-primary"]:hover {{ background:{TEAL_LIGHT} !important; transform:translateY(-1px); }}
.st-key-wl_start_cta [data-testid="stBaseButton-tertiary"], .st-key-wl_start_cta button[kind="tertiary"] {{
  color:#D7E2EC !important; background:transparent !important; border:1px solid rgba(215,226,236,.35) !important; }}
.st-key-wl_start_cta [data-testid="stBaseButton-tertiary"]:hover {{ color:#fff !important; border-color:#fff !important; }}
.st-key-wl_start_cta button:focus-visible {{ outline:2px solid #3FC1B0 !important; outline-offset:3px; }}
/* load sequence: one orchestrated moment */
@keyframes wlRise {{ from {{ opacity:0; transform:translateY(14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes wlFade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.wl-h1, .wl-lead, .wl-q {{ animation:wlRise .8s cubic-bezier(.2,.7,.2,1) both; }}
.wl-lead {{ animation-delay:.1s; }} .wl-q {{ animation-delay:.2s; }}
.st-key-wl_cta {{ animation:wlRise .8s cubic-bezier(.2,.7,.2,1) .3s both; }}
.flowart {{ animation:wlFade 1.4s ease .15s both; }}
/* illustration */
.flowart svg {{ width:100%; height:auto; max-height:380px; display:block; }}
.flowart .fl {{ fill:none; stroke:url(#fg); stroke-width:1.8; }}
.flowart .rl {{ fill:none; stroke:rgba(215,226,236,.28); stroke-width:1.4; stroke-dasharray:2 7; stroke-linecap:round; }}
.flowart .dot {{ fill:#E3F3F0; }} .flowart .dot.ret {{ fill:#9FD9D0; }}
.flowart .q {{ fill:#F2C8A0; animation:wlWait 3.2s ease-in-out infinite; }}
.flowart .bed rect {{ fill:rgba(255,255,255,.04); stroke:rgba(215,226,236,.35); stroke-width:1.2; }}
.flowart .bed .pw {{ fill:rgba(255,255,255,.18); stroke:none; }}
.flowart .bed.on rect {{ fill:#1AA191; stroke:#3FC1B0; }} .flowart .bed.on .pw {{ fill:rgba(255,255,255,.55); }}
.flowart .bed.pulse {{ animation:wlBed 11s ease-in-out infinite; }}
@keyframes wlBed {{ 0%, 62%, 100% {{ opacity:1; }} 72%, 84% {{ opacity:.25; }} }}
@keyframes wlWait {{ 0%, 100% {{ opacity:.95; }} 50% {{ opacity:.55; }} }}
/* section heads */
.wl-h2 {{ font-size:clamp(1.6rem, 2.2vw, 2.05rem) !important; font-weight:750 !important; color:{NAVY} !important;
  letter-spacing:-0.025em; margin:0 0 .35rem !important; padding:0 !important; }}
.wl-sub {{ font-size:1.06rem; color:#46586A; margin:0 0 1.5rem; max-width:48em; line-height:1.55; }}
/* management questions: open layout, hairline dividers, no boxes */
.st-key-wl_qs [data-testid="stHorizontalBlock"] {{ gap:0 !important; }}
.st-key-wl_qs [data-testid="stColumn"] {{ padding:4px 30px 6px; border-left:1px solid #DCE4EC; }}
.st-key-wl_qs [data-testid="stColumn"]:first-child {{ border-left:none; padding-left:0; }}
.wlq-ic {{ width:40px; height:40px; color:{TEAL}; margin-bottom:14px; }}
.wlq-ic svg {{ width:40px; height:40px; }}
.wlq-k {{ font-size:.92rem; font-weight:650; color:{TEAL_DARK}; margin-bottom:4px; }}
.wlq-k .wl-opt {{ font-size:.72rem; font-weight:700; color:{MUTED}; background:#EEF2F6; border-radius:999px; padding:1px 8px;
  margin-left:6px; vertical-align:1px; }}
.wlq-t {{ font-size:1.36rem; font-weight:720; color:{NAVY}; line-height:1.28; letter-spacing:-0.015em; margin-bottom:8px; }}
.wlq-d {{ font-size:1rem; color:#46586A; line-height:1.55; margin-bottom:6px; }}
.st-key-wl_qs button {{ padding-left:0 !important; min-height:0 !important; }}
.st-key-wl_qs button p {{ color:{TEAL_DARK} !important; font-weight:650 !important; font-size:.97rem !important; }}
.st-key-wl_qs button:hover p {{ text-decoration:underline; }}
/* mechanism strip */
.st-key-wl_des {{ margin:3rem 0 2.6rem; padding:30px 36px; border-radius:24px;
  background:linear-gradient(120deg, #FFFFFF 0%, #F2F8F7 100%); border:1px solid #E3EBF0; }}
.st-key-wl_des [data-testid="stHorizontalBlock"] {{ align-items:center; }}
.wl-des p {{ font-size:1.02rem; color:#34475A; line-height:1.6; margin:0 0 .5rem; max-width:34em; }}
.wl-mech {{ position:relative; display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; }}
.wl-mech::before {{ content:""; position:absolute; left:12.5%; right:12.5%; top:26px; height:2px;
  background:linear-gradient(90deg, #3FC1B0, {TEAL}); opacity:.45; border-radius:2px; }}
.wl-mech .mi {{ position:relative; display:flex; flex-direction:column; align-items:center; text-align:center; gap:10px; }}
.wl-mech .mn {{ width:54px; height:54px; border-radius:50%; background:#fff; border:1.5px solid #BFE2DC; color:{TEAL_DARK};
  display:flex; align-items:center; justify-content:center; box-shadow:0 4px 12px -6px rgba(14,138,126,.35); }}
.wl-mech .mn svg {{ width:26px; height:26px; }}
.wl-mech .ml {{ font-size:.92rem; font-weight:600; color:{NAVY}; line-height:1.3; max-width:9em; }}
/* how it works: one connected path */
.st-key-wl_path [data-testid="stColumn"] {{ position:relative; }}
.st-key-wl_path [data-testid="stColumn"]:not(:last-child)::after {{ content:""; position:absolute; top:19px; left:52px;
  right:-12px; height:2px; background:linear-gradient(90deg, {TEAL}, #BFE2DC); border-radius:2px; }}
.wlp-n {{ position:relative; z-index:1; width:40px; height:40px; border-radius:50%; background:{NAVY}; color:#fff;
  font-weight:720; font-size:1rem; display:flex; align-items:center; justify-content:center; margin-bottom:14px; }}
.wlp-n.cur {{ background:{TEAL}; }}
.wlp-t {{ font-size:1.18rem; font-weight:720; color:{NAVY}; margin-bottom:4px; letter-spacing:-0.01em; }}
.wlp-d {{ font-size:.98rem; color:#46586A; line-height:1.55; margin-bottom:10px; max-width:24em; }}
.wlp-none {{ font-size:.92rem; color:#66778A; font-style:normal; }}
.st-key-wl_path button {{ border-radius:999px !important; min-height:2.5rem; padding:0 18px !important; }}
.st-key-wl_path button p {{ font-weight:650 !important; font-size:.96rem !important; white-space:nowrap; }}
/* ---- v5.4 hero proof line ---- */
.st-key-wl_hero {{ margin-bottom:3.4rem; }}
.wl-lead {{ max-width:31em; color:#DCE6EF; }}
/* ---- v5.4 planning-question picker (CSS only: choosing does not rerun the app) ---- */
.sr {{ position:absolute !important; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }}
.st-key-wl_pick {{ margin:0 0 .6rem; }}
.st-key-wl_pick [data-testid="stHorizontalBlock"] {{ align-items:flex-start; }}
.wqopts {{ border:none; margin:0; padding:0; min-width:0; display:flex; flex-direction:column; gap:6px; }}
.wqo {{ position:relative; display:flex; gap:14px; align-items:flex-start; padding:16px 18px 16px 16px; border-radius:16px;
  cursor:pointer; border:1px solid transparent; transition:background-color .2s ease, border-color .2s ease, box-shadow .25s ease; }}
.wqo input {{ position:absolute; opacity:0; width:1px; height:1px; margin:0; pointer-events:none; }}
.wqo:hover {{ background:rgba(255,255,255,.75); border-color:#E3EAF0; }}
.wqo:hover .wqi {{ color:{TEAL_DARK}; }}
.wqo:has(input:checked), .st-key-wl_pick:not(:has(input:checked)) .wqo-demand {{ background:#fff; border-color:#DCE6EE; box-shadow:0 14px 30px -22px rgba(11,37,69,.5); }}
.wqo::before {{ content:""; position:absolute; left:-1px; top:18px; bottom:18px; width:3px; border-radius:3px; background:{TEAL};
  transform:scaleY(0); transition:transform .25s cubic-bezier(.2,.7,.2,1); }}
.wqo:has(input:checked)::before, .st-key-wl_pick:not(:has(input:checked)) .wqo-demand::before {{ transform:scaleY(1); }}
.wqo:has(input:focus-visible) {{ outline:2px solid {TEAL}; outline-offset:2px; }}
.wqi {{ flex:none; width:42px; height:42px; border-radius:12px; background:#E9F0F5; color:{NAVY_2}; display:flex;
  align-items:center; justify-content:center; transition:background-color .2s ease, color .2s ease; }}
.wqi svg {{ width:22px; height:22px; }}
.wqo:has(input:checked) .wqi, .st-key-wl_pick:not(:has(input:checked)) .wqo-demand .wqi {{ background:{TEAL}; color:#fff; }}
.wqt b {{ display:block; font-size:.88rem; font-weight:700; color:{TEAL_DARK}; margin-bottom:3px; }}
.wqt span {{ display:block; font-size:1.04rem; font-weight:560; color:#34475A; line-height:1.38; }}
.wqo:has(input:checked) .wqt span, .st-key-wl_pick:not(:has(input:checked)) .wqo-demand .wqt span {{ color:{NAVY}; font-weight:640; }}
/* all three panels share one grid cell, so the section keeps the height of the tallest: no layout jump */
.wqps {{ display:grid; }}
.wqp {{ grid-area:1 / 1; visibility:hidden; opacity:0; transform:translateY(4px); padding:26px 28px 24px;
  border-radius:22px; border:1px solid #E1EAEF; background:linear-gradient(160deg, #FFFFFF 0%, #F2F8F7 100%);
  transition:opacity .2s ease, transform .2s cubic-bezier(.2,.7,.2,1), visibility 0s linear .2s; }}
.st-key-wl_pick:has(#wq-demand:checked) .wqp-demand, .st-key-wl_pick:has(#wq-beds:checked) .wqp-beds,
.st-key-wl_pick:has(#wq-flow:checked) .wqp-flow, .st-key-wl_pick:not(:has(input:checked)) .wqp-demand {{
  visibility:visible; opacity:1; transform:none; transition:opacity .2s ease, transform .2s cubic-bezier(.2,.7,.2,1); }}
.wqd {{ margin:20px 0 0; padding:16px 0 0; border-top:1px solid #E1E9EF; display:grid; gap:12px; }}
.wqd > div {{ display:grid; grid-template-columns:11.5em 1fr; gap:16px; align-items:baseline; }}
.wqd dt {{ font-size:.86rem; font-weight:700; color:{TEAL_DARK}; }}
.wqd dd {{ margin:0; font-size:.98rem; color:#34475A; line-height:1.5; }}
.wqd > div:last-child dd {{ color:{NAVY}; font-weight:600; }}
.wqp-top {{ display:flex; gap:22px; justify-content:space-between; align-items:flex-start; }}
.wqp-k {{ font-size:.88rem; font-weight:700; color:{TEAL_DARK}; }}
.wqp-k .wl-opt {{ font-size:.72rem; font-weight:700; color:{MUTED}; background:#EEF2F6; border-radius:999px; padding:1px 8px;
  margin-left:8px; vertical-align:1px; }}
.wqp-q {{ font-size:1.42rem; font-weight:740; color:{NAVY}; letter-spacing:-0.02em; line-height:1.25; margin:5px 0 8px; max-width:22em; }}
.wqp p {{ font-size:1rem; color:#46586A; line-height:1.55; max-width:34em; margin:0; }}
.wqv {{ margin:0; flex:none; width:156px; text-align:right; }}
.wqv svg {{ width:156px; height:84px; display:block; overflow:visible; }}
.wqv .b {{ fill:{TEAL}; opacity:.85; }} .wqv .o {{ fill:#E3A55A; }}
.wqv .area {{ fill:{TEAL}; opacity:.12; }} .wqv .ln {{ fill:none; stroke:{TEAL}; stroke-width:2; stroke-linecap:round; }}
.wqv .ln.over {{ stroke:#D98A2B; stroke-width:2.4; }} .wqv .ln.dk {{ stroke:{NAVY_2}; }}
.wqv .hit {{ fill:#fff; stroke:#D98A2B; stroke-width:1.5; }}
.wqv .room {{ fill:{TEAL}; opacity:.10; }} .wqv .gap {{ fill:#E3A55A; opacity:.45; }}
.wqv .before {{ fill:#DCE4EB; }} .wqv .freed {{ fill:none; stroke:{TEAL}; stroke-width:1.2; stroke-dasharray:3 2; }}
.wqv .lbl {{ font:600 7.5px/1 {FONT}; fill:{NAVY}; }} .wqv .lbl.dim {{ fill:#7A8A9A; }} .wqv .lbl.c {{ text-anchor:middle; fill:#55677A; }} .wqv .lbl.e {{ text-anchor:end; }}
.wqv .g {{ fill:none; stroke:#AFC0CE; stroke-width:1.2; stroke-dasharray:2 2; }}
.wqv .cap {{ stroke:{NAVY}; stroke-width:1.5; stroke-dasharray:4 3; }} .wqv .cap.dim {{ stroke:#B4C1CD; }}
.wqv .arr {{ stroke:{NAVY}; stroke-width:1.5; fill:none; stroke-linecap:round; stroke-linejoin:round; }}
.wqv .ax {{ stroke:#C9D4DE; }}
.wqv figcaption {{ font-size:.68rem; color:#8696A6; margin-top:4px; line-height:1.3; text-align:right; white-space:nowrap; }}
.st-key-wl_go {{ min-height:3.2rem; }}
.st-key-wl_pick [class*="st-key-wlgo_"] {{ margin-top:6px; }}
.st-key-wl_pick [class*="st-key-wlgo_"] button {{ border-radius:999px !important; min-height:2.8rem; padding:0 22px !important; }}
.st-key-wl_pick [class*="st-key-wlgo_"] button p {{ font-weight:650 !important; }}
@supports selector(:has(*)) {{
  .st-key-wl_pick [class*="st-key-wlgo_"] {{ display:none !important; }}
  .st-key-wl_pick:has(#wq-demand:checked) .st-key-wlgo_demand, .st-key-wl_pick:has(#wq-beds:checked) .st-key-wlgo_beds,
  .st-key-wl_pick:has(#wq-flow:checked) .st-key-wlgo_flow,
  .st-key-wl_pick:not(:has(input:checked)) .st-key-wlgo_demand {{ display:flex !important; }} }}
@supports not selector(:has(*)) {{ .wqps {{ display:block; }} .wqp {{ visibility:visible; opacity:1; transform:none; margin-bottom:12px; }} }}
@media (max-width: 1100px) {{
  .st-key-wl_pick [data-testid="stHorizontalBlock"], .st-key-wl_des [data-testid="stHorizontalBlock"] {{ flex-direction:column !important; gap:1rem !important; }}
  .st-key-wl_pick [data-testid="stColumn"], .st-key-wl_des [data-testid="stColumn"] {{ width:100% !important; flex:1 1 auto !important; }}
  .wqopts {{ flex-direction:row; flex-wrap:wrap; }} .wqo {{ flex:1 1 200px; }} }}
/* mechanism with plain-English descriptions */
ol.wl-mech {{ list-style:none; margin:0; padding:0; }}
.wl-mech .mi {{ margin:0; }}
.wl-mech .md {{ font-size:.86rem; color:#55677A; line-height:1.45; max-width:13em; }}
.st-key-wl_des {{ background:radial-gradient(700px 260px at 100% 0%, rgba(14,138,126,.08), rgba(14,138,126,0) 70%), #FFFFFF; }}
/* responsive */
/* ---- v5.7 One Connected Workflow (text and connectors only) ---- */
.wf {{ margin:0 0 3.4rem; padding:2.6rem 3rem 2.2rem; border-radius:28px;
  background:linear-gradient(180deg, #EAF2F5 0%, #F4F8FA 75%, rgba(244,248,250,0) 100%); }}
.wf .wl-sub {{ margin-bottom:2rem; }}
.wfstages3 {{ list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:32px; }}
.wfs {{ position:relative; display:flex; flex-direction:column; }}
ol.wfstages3 > li.wfs {{ margin:0 !important; padding:0 !important; }}   /* Streamlit indents markdown list items */
@supports (grid-template-rows: subgrid) {{
  .wfstages3 {{ grid-template-rows:auto auto 1fr auto; row-gap:0; }}
  .wfs {{ display:grid; grid-row:span 4; grid-template-rows:subgrid; }} }}
.wfs:not(:last-child)::after {{ content:""; position:absolute; top:16px; left:44px; right:-24px; height:2px; border-radius:2px;
  background:linear-gradient(90deg, {TEAL}, rgba(14,138,126,.18)); }}
.wfn {{ display:flex; flex-direction:column; gap:12px; margin-bottom:6px; }}
.wfn span {{ width:34px; height:34px; border-radius:50%; background:#fff; border:1.5px solid {TEAL}; color:{TEAL_DARK};
  font-size:.8rem; font-weight:750; display:flex; align-items:center; justify-content:center;
  transition:background-color .25s ease, color .25s ease; }}
.wfs:hover .wfn span {{ background:{TEAL}; color:#fff; }}
.wfn b {{ font-size:.9rem; font-weight:700; color:{TEAL_DARK}; }}
.wfs h3 {{ font-size:1.3rem !important; font-weight:740 !important; color:{NAVY} !important; letter-spacing:-0.02em;
  line-height:1.25 !important; margin:0 0 .4rem !important; padding:0 !important; }}
.wfs p {{ font-size:.98rem; color:#46586A; line-height:1.55; margin:0 0 .7rem; max-width:24em; }}
.wfs em {{ font-style:normal; align-self:start; justify-self:start; width:fit-content; font-size:.76rem; font-weight:620; color:{NAVY_2}; background:#fff;
  border:1px solid #DCE5EC; border-radius:999px; padding:3px 10px; }}
/* the loop: an arc from Evaluate back to Simulate */
.wfback {{ position:relative; margin:14px 0 0 calc((100% - 64px) / 3 + 32px + 17px); width:calc((100% - 64px) / 3 + 32px); }}
.wfarc {{ display:block; height:22px; border:2px dashed rgba(14,138,126,.55); border-top:none; border-radius:0 0 18px 18px; }}
.wfarc::before {{ content:""; position:absolute; left:-5px; top:-6px; border:6px solid transparent;
  border-bottom:8px solid rgba(14,138,126,.75); border-top:none; }}
.wfback p {{ margin:10px 0 0 50%; transform:translateX(-50%); width:max-content; text-align:center; font-size:.9rem; color:#46586A; }}
.wfback p b {{ color:{TEAL_DARK}; font-weight:700; margin-right:6px; }}
@media (max-width: 1000px) {{
  .wf {{ padding:2.2rem 1.4rem 1.8rem; }}
  .wfstages3 {{ grid-template-columns:1fr; gap:24px; }} .wfs::after {{ display:none; }}
  .wfback {{ margin:18px 0 0; width:auto; }} .wfarc {{ display:none; }}
  .wfback p {{ text-align:left; margin-left:0; transform:none; width:auto; }} }}
@media (prefers-reduced-motion: reduce) {{ .wfn span {{ transition:none !important; }} }}
@media (max-width: 1100px) {{ .st-key-wl_hero {{ padding:40px 32px 34px; }} .st-key-wl_qs [data-testid="stColumn"] {{ padding:4px 18px 6px; }} }}
@media (max-width: 760px) {{
  .st-key-wl_hero {{ padding:32px 22px 26px; border-radius:22px; }}
  .flowart svg {{ max-height:220px; }}
  .st-key-wl_qs [data-testid="stColumn"] {{ border-left:none; padding:0 0 18px; border-bottom:1px solid #DCE4EC; }}
  .st-key-wl_des {{ padding:24px 20px; }}
  .wl-mech {{ grid-template-columns:repeat(2, 1fr); row-gap:18px; }} .wl-mech::before {{ display:none; }}
  .st-key-wl_path [data-testid="stColumn"]::after {{ display:none; }}
  .wqd > div {{ grid-template-columns:1fr; gap:2px; }}
  .wqp-top {{ flex-direction:column; }} .wqv {{ display:none; }} .wqp {{ padding:22px 20px 18px; }} }}
@media (prefers-reduced-motion: reduce) {{
  .wqp, .wqo, .wqo::before, .wqi {{ transition:none !important; transform:none !important; }}
  .wl-h1, .wl-lead, .wl-q, .st-key-wl_cta, .flowart {{ animation:none !important; }}
  .flowart .mv {{ display:none; }} .flowart .bed.pulse, .flowart .q {{ animation:none !important; }}
  .st-key-wl_cta button {{ transition:none !important; }} }}
</style>
"""
