import base64
import os
import json
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from ai_backend import get_ai_chat_recommendation, PLAYLISTS
from services.persistence import (
    get_pushpanjali_count,
    increment_pushpanjali,
    publish_location,
    get_locations,
    get_latest_location_event,
    submit_song_request,
    PersistenceError,
    supabase_enabled
)

st.set_page_config(
    page_title="বাঙালির উৎসব, বাঙালির গান",
    page_icon="🔔",
    layout="wide",
    initial_sidebar_state="collapsed"
)

RADIO_STATIONS = {
    "AIR FM Rainbow Kolkata": "https://airhlspush.pc.cdn.bitgravity.com/httppush/hlspbaudio004/hlspbaudio00464kbps.m3u8",
    "Radio Mirchi 98.3 FM": "https://eu8.fastcast4u.com/proxy/clyedupq/stream"
}

CURATED_PLAYLISTS = {
    name: (data.get("title_bn", name), data.get("playlist_id", ""))
    for name, data in PLAYLISTS.items()
}


SOUNDS = [
    ("🥁", "ঢাক", "Dhaak", "ঢাকের তালে পুজোর প্যান্ডালের প্রাণবন্ত আবহ।"),
    ("🪘", "কাঁসর", "Kasar", "কাঁসরের ধাতব অনুরণন ও আরতির আবহ।"),
    ("🔔", "ঘন্টা", "Bell", "পুজোর ঘণ্টাধ্বনি ও আরতির পবিত্র পরিবেশ।"),
    ("🕉️", "মন্ত্র", "Chanting", "মন্ত্রোচ্চারণের শান্ত ও ধ্যানমগ্ন আবহ।"),
    ("✨", "আতশবাজি", "Fireworks", "উৎসবের রাতের আতশবাজির উচ্ছ্বাস।"),
    ("🗣️", "হুল্লোড়", "Crowd", "প্যান্ডালের ভিড়, আড্ডা ও উৎসবের সম্মিলিত শব্দ।")
]

VIBES = {
    "morning": ("ভোরের আলো · Agamani", 5, 12, "assets/bg_morning.jpg", "#ffb366", "rgba(255,179,102,.15)"),
    "afternoon": ("দুপুরের আড্ডা · Nostalgia", 12, 17, "assets/bg_afternoon.jpg", "#ff8a3d", "rgba(255,138,61,.14)"),
    "evening": ("সন্ধ্যা আরতি · Festive", 17, 21, "assets/bg_evening.jpg", "#ff5577", "rgba(255,85,119,.15)"),
    "night": ("নিশীথ রাত · Ambient", 21, 5, "assets/bg_night.jpg", "#8aa4ff", "rgba(138,164,255,.15)")
}

def vibe_now():
    h = datetime.now().hour
    if 5 <= h < 12: return VIBES["morning"]
    if 12 <= h < 17: return VIBES["afternoon"]
    if 17 <= h < 21: return VIBES["evening"]
    return VIBES["night"]

label, _, _, bg_path, accent, accent_soft = vibe_now()

def b64(p):
    try:
        return base64.b64encode(Path(p).read_bytes()).decode()
    except Exception:
        return ""

bg = b64(bg_path if Path(bg_path).exists() else "assets/bg_durga.jpg")
deity = b64("assets/deity_icon.jpg")

# Session state initialization
if "active_section" not in st.session_state: st.session_state.active_section = "Puja Songs"
if "active_playlist" not in st.session_state: st.session_state.active_playlist = list(CURATED_PLAYLISTS)[0]
if "ai_result" not in st.session_state: st.session_state.ai_result = None
if "expanded_sound" not in st.session_state: st.session_state.expanded_sound = None
if "popup_message" not in st.session_state: st.session_state.popup_message = None
if "popup_kind" not in st.session_state: st.session_state.popup_kind = "flower"
if "last_location_event_id" not in st.session_state: st.session_state.last_location_event_id = None
if "pushpanjali_count" not in st.session_state:
    try:
        st.session_state.pushpanjali_count = get_pushpanjali_count()
        st.session_state.persistence_error = None
    except PersistenceError as exc:
        st.session_state.pushpanjali_count = 0
        st.session_state.persistence_error = str(exc)

# Footer hyperlinks drive the same section/panel state.
# Pushpanjali is intentionally handled by a native Streamlit button below so
# clicking the bell never navigates/reloads the page or opens another tab.
section_q = st.query_params.get("section")
panel_q = st.query_params.get("panel")
if section_q in {"songs", "sounds", "radio", "tv"}:
    st.session_state.active_section = {"songs": "Puja Songs", "sounds": "Puja Sound", "radio": "Live Radio", "tv": "Pujo TV"}[section_q]
if panel_q in {"gallery", "analytics"}:
    st.session_state.active_panel = panel_q
else:
    st.session_state.active_panel = None

st.markdown(
    f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Noto+Serif+Bengali:wght@500;600;700&family=Special+Elite&display=swap');

.stApp {{
    background: radial-gradient(circle at 50% 0%, rgba(255,100,35,.12), transparent 34%),
                linear-gradient(rgba(5,7,11,.78), rgba(5,7,11,.95)),
                url("data:image/jpeg;base64,{bg}");
    background-size: cover; background-position: center; background-attachment: fixed; color: #fff;
}}

.stApp::after {{
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999; opacity: .095;
    mix-blend-mode: soft-light;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    animation: grain .18s steps(2) infinite;
}}
@keyframes grain {{ 50% {{ transform: translate(1%,-1%); }} }}

#MainMenu, header, footer {{ visibility: hidden; }}
.block-container {{ max-width: 1180px; padding-top: 1rem; padding-bottom: 0rem; }}

/* Centered Hero */
.hero {{
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    margin: 0 auto 10px auto !important;
}}
.hero-icon {{
    width: 86px; height: 86px; object-fit: contain; margin: 0 auto 10px auto;
    filter: drop-shadow(0 0 22px rgba(255,145,55,.55)); animation: float 4s ease-in-out infinite;
}}
@keyframes float {{ 50% {{ transform: translateY(-7px); }} }}
.hero-title {{
    font: clamp(2.2rem, 5vw, 3.8rem)/1.15 'Noto Serif Bengali', serif;
    background: linear-gradient(120deg, #ffd08a, #ff6a21, #ff477e);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center;
}}
.hero-subtitle, .footer-meta, .nav-caption, .footer-link {{ font-family: 'Cinzel', serif; letter-spacing: 1.3px; }}
.hero-subtitle {{ color: #9da5b5; font-size: .82rem; text-align: center; }}

/* Top Status */
.status-row {{ display: flex; justify-content: space-between; margin-bottom: 12px; }}
.status-pill {{
    padding: 7px 14px; border-radius: 999px; background: rgba(10,12,17,.55);
    border: 1px solid rgba(255,255,255,.09); font: .68rem 'Cinzel', serif; letter-spacing: 1px;
}}
.live-dot {{
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #00e676; box-shadow: 0 0 12px #00e676;
}}

/* Pushpanjali Counter (Transparent) */
.puja-counter {{
    width: 100%; margin: 8px auto 0px; display: flex; justify-content: center;
    gap: 8px; align-items: center; background: transparent; border: none; font-family: 'Noto Serif Bengali', serif;
}}
.puja-counter strong {{ color: #00e676; font-size: 1.15rem; }}

/* Bell Button (Icon-Only Transparent) */
/* Pushpanjali bell: the visual is an exact viewport-centered control. */
.push-bell-wrap {{ width:100%; display:flex; justify-content:center; align-items:center; margin:0 auto; padding:0; }}
/* Native Streamlit bell: exact viewport-centred icon, no navigation. */
[class*="st-key-push_bell_container"] {{ width:100% !important; display:flex !important; justify-content:center !important; align-items:center !important; margin:0 auto !important; padding:0 !important; }}
[class*="st-key-push_bell_container"] [data-testid="stButton"] {{ width:46px !important; min-width:46px !important; margin:0 auto !important; display:flex !important; justify-content:center !important; }}
[class*="st-key-push_bell_container"] [data-testid="stButton"] > button {{ width:46px !important; min-width:46px !important; height:46px !important; min-height:46px !important; padding:0 !important; margin:0 auto !important; display:flex !important; align-items:center !important; justify-content:center !important; background:transparent !important; border:0 !important; box-shadow:none !important; border-radius:50% !important; font-size:2.15rem !important; line-height:1 !important; color:inherit !important; }}
[class*="st-key-push_bell_container"] [data-testid="stButton"] > button:hover {{ transform:scale(1.12); filter:drop-shadow(0 0 18px rgba(255,153,51,.9)); background:transparent !important; border:0 !important; }}
.pushpanjali-text {{ text-align: center; background: transparent; margin-bottom: 22px; }}
.pushpanjali-text .ben {{ font-family: 'Noto Serif Bengali', serif; font-size: 0.95rem; color: #fff; }}
.pushpanjali-text .eng {{ font-family: 'Cinzel', serif; font-size: 0.78rem; color: #a0aec0; margin-top: 4px; letter-spacing: 1px; }}

/* Pill Buttons */
div[data-testid="stButton"] > button {{
    border-radius: 999px !important; min-height: 42px !important;
    border: 1px solid rgba(255,190,92,.48) !important;
    background: linear-gradient(135deg, rgba(255,98,28,.18), rgba(255,46,101,.12)) !important;
    color: #ffe4c4 !important; font-family: 'Noto Serif Bengali', serif !important;
    box-shadow: 0 8px 25px rgba(0,0,0,.2); transition: .2s;
}}
div[data-testid="stButton"] > button:hover {{
    border-color: rgba(255,210,120,.9) !important; transform: translateY(-1px);
}}

/* Cards & Controls */
.content-card {{
    background: linear-gradient(145deg, rgba(58,24,29,.42), rgba(17,13,18,.48));
    border: 1px solid rgba(255,190,92,.58); border-radius: 28px; padding: clamp(18px, 4vw, 40px);
    box-shadow: 0 25px 70px rgba(0,0,0,.46), 0 0 0 1px rgba(255,190,92,.08); backdrop-filter: blur(18px); margin-bottom: 18px;
}}
.section-kicker {{ color: {accent}; font: 600 .66rem 'Cinzel', serif; letter-spacing: 2px; text-transform: uppercase; }}
.section-title {{ font: 1.65rem 'Noto Serif Bengali', serif; margin: 4px 0; }}
.section-description {{ color: #9da5b5; font-size: .88rem; margin-bottom: 18px; }}

/* Transparent inputs and dropdowns */
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextArea"] div[data-baseweb="textarea"],
div[data-baseweb="input"],
div[data-baseweb="textarea"] {{
    background: rgba(12,10,14,.20) !important;
    border: 1px solid rgba(255,190,92,.42) !important;
    box-shadow: none !important;
}}
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
input, textarea {{
    background: transparent !important; color: #fff !important;
    border: none !important; box-shadow: none !important;
}}
div[data-baseweb="select"] > div {{
    background: rgba(12,10,14,.20) !important; border: 1px solid rgba(255,190,92,.42) !important;
    border-radius: 10px !important; color: #ffd9ad !important; box-shadow: none !important;
}}
div[data-baseweb="select"] [data-baseweb="select"] {{ background: transparent !important; }}
ul[data-baseweb="menu"] {{
    background: rgba(31,12,17,.98) !important; border: 1px solid rgba(255,190,92,.58) !important;
}}
[data-baseweb="popover"] {{ background: rgba(31,12,17,.98) !important; }}


/* Realistic audio hardware */
.retro-deck {{
    max-width: 1080px; margin: 24px auto; padding: 18px;
    background: linear-gradient(145deg, #3a1f18 0%, #1b100d 18%, #0b0a09 58%, #21120d 100%);
    border: 1px solid rgba(220,171,103,.72); border-radius: 16px;
    box-shadow: 0 28px 70px rgba(0,0,0,.72), inset 0 1px 0 rgba(255,235,195,.18), inset 0 -1px 0 rgba(0,0,0,.9);
    position: relative; overflow: hidden;
}}
.retro-deck::before {{
    content:""; position:absolute; inset:0; pointer-events:none; opacity:.22;
    background: repeating-linear-gradient(92deg, rgba(255,220,170,.08) 0 1px, transparent 1px 5px);
    mix-blend-mode: screen;
}}
.deck-top {{ display:flex; justify-content:space-between; align-items:center; gap:12px; color:#b9a38c; font:600 .62rem 'Cinzel',serif; letter-spacing:1.5px; padding:0 4px 12px; position:relative; }}
.deck-brand {{ color:#e0b46f; }}
.hardware-panel {{ position:relative; display:grid; grid-template-columns:minmax(0,1fr) 150px; gap:14px; align-items:stretch; }}
.display-panel {{ min-width:0; background:linear-gradient(180deg,#090806,#12100c); border:1px solid #5b452e; border-radius:8px; padding:13px; box-shadow:inset 0 0 28px rgba(0,0,0,.9), inset 0 1px rgba(255,230,185,.08); }}
.artwork-screen {{ float:left; width:92px; aspect-ratio:1; margin-right:14px; border:1px solid #9b7445; border-radius:5px; background:url("data:image/jpeg;base64,{deity}") center/cover; box-shadow:0 0 0 4px #17110d, 0 8px 18px rgba(0,0,0,.55); }}
.track-heading {{ color:#f0c988; font:600 clamp(1rem,2.3vw,1.35rem) 'Noto Serif Bengali',serif; margin-top:3px; }}
.track-sub {{ color:#9d8b79; font:.66rem 'Cinzel',serif; letter-spacing:1px; margin-top:5px; }}
.track-time {{ display:flex; justify-content:space-between; clear:both; color:#a99683; font:.62rem monospace; padding-top:12px; }}
.progress {{ height:4px; background:#302219; border-radius:99px; margin-top:7px; overflow:hidden; }}
.progress > span {{ display:block; width:36%; height:100%; background:linear-gradient(90deg,#8e5424,#e6ad58); box-shadow:0 0 9px rgba(230,173,88,.5); }}
.vu-rack {{ display:grid; grid-template-columns:1fr 1fr; gap:7px; background:#0a0907; border:1px solid #5b452e; border-radius:8px; padding:10px; }}
.vu {{ position:relative; min-height:88px; border:1px solid #3e3022; background:radial-gradient(circle at 50% 90%,#3a1e10,#0c0906 62%); overflow:hidden; }}
.vu::before {{ content:""; position:absolute; left:12%; right:12%; bottom:18%; height:1px; background:#b87938; box-shadow:0 -8px #684323,0 -16px #4b321f; transform:rotate(-12deg); transform-origin:left; }}
.vu::after {{ content:"VU"; position:absolute; left:50%; bottom:5px; transform:translateX(-50%); color:#9d7446; font:600 .5rem monospace; }}
.vu-needle {{ position:absolute; width:45%; height:2px; left:7%; bottom:28%; background:#e7a85a; transform-origin:100% 50%; transform:rotate(-24deg); box-shadow:0 0 7px rgba(231,168,90,.55); animation:vuMove .95s ease-in-out infinite alternate; }}
@keyframes vuMove {{ from{{transform:rotate(-24deg)}} to{{transform:rotate(17deg)}} }}
.control-strip {{ display:flex; align-items:center; justify-content:center; gap:8px; flex-wrap:wrap; padding:14px 2px 2px; }}
.transport-key {{ min-width:42px; height:34px; padding:0 11px; border-radius:5px; background:linear-gradient(180deg,#4b4034,#18140f); border:1px solid #806542; color:#dbc09a; font:600 .58rem 'Cinzel',serif; letter-spacing:.5px; cursor:pointer; box-shadow:inset 0 1px rgba(255,255,255,.12),0 4px 9px rgba(0,0,0,.4); }}
.transport-key.play {{ min-width:58px; background:linear-gradient(180deg,#b87531,#5a2a13); color:#ffe9c5; border-color:#c89354; }}
.transport-key:hover {{ filter:brightness(1.18); transform:translateY(-1px); }}
.transport-key:active {{ transform:translateY(1px); }}
.volume-knob {{ width:55px; height:55px; border-radius:50%; margin:auto; background:radial-gradient(circle at 35% 30%,#d7c09c 0,#8d704b 30%,#3a2a1b 58%,#0d0b08 62%); border:2px solid #9e784b; box-shadow:0 4px 13px #000,inset 0 1px 3px rgba(255,255,255,.25); position:relative; }}
.volume-knob::after {{ content:""; position:absolute; width:2px; height:17px; background:#271b10; left:50%; top:5px; transform:translateX(-50%); border-radius:2px; }}
.volume-label {{ text-align:center; color:#98754d; font:.48rem 'Cinzel',serif; letter-spacing:1px; margin-top:4px; }}
.deck-status {{ text-align:center; color:#9d8b79; font:.62rem monospace; letter-spacing:.8px; margin-top:8px; min-height:15px; }}
@media(max-width:700px){{
    .retro-deck{{margin:14px auto;padding:11px;border-radius:12px;}}
    .deck-top{{font-size:.5rem;letter-spacing:.8px;padding-bottom:8px;}}
    .hardware-panel{{grid-template-columns:1fr;}}
    .vu-rack{{grid-template-columns:1fr 1fr; order:2;}}
    .display-panel{{padding:10px;}}
    .artwork-screen{{width:68px;margin-right:10px;}}
    .track-heading{{font-size:1rem;}}
    .track-sub{{font-size:.54rem;}}
    .transport-key{{height:32px;min-width:38px;padding:0 8px;font-size:.52rem;}}
    .volume-knob{{width:46px;height:46px;}}
}}
@media(max-width:420px){{
    .retro-deck{{padding:9px;}}
    .deck-top{{flex-direction:column;align-items:flex-start;gap:4px;}}
    .artwork-screen{{width:58px;}}
    .control-strip{{gap:5px;}}
    .transport-key{{min-width:35px;padding:0 6px;font-size:.48rem;}}
}}

/* Animated global event popup */
.global-puja-popup {{ position:fixed; left:50%; top:18%; transform:translate(-50%,-20px) scale(.96); z-index:2147483000; width:min(92vw,520px); padding:16px 22px; border:1px solid rgba(239,194,112,.8); border-radius:18px; background:linear-gradient(145deg,rgba(74,17,24,.97),rgba(25,8,13,.98)); box-shadow:0 22px 65px rgba(0,0,0,.58),0 0 35px rgba(211,143,54,.14); color:#ffe9c7; text-align:center; pointer-events:none; animation:pujaPopup 3.4s ease forwards; }}
.global-puja-popup .flower {{ display:block; font-size:2rem; line-height:1; margin-bottom:7px; filter:drop-shadow(0 0 12px rgba(255,182,83,.55)); }}
.global-puja-popup .popup-title {{ font:600 1rem 'Noto Serif Bengali',serif; }}
.global-puja-popup .popup-sub {{ margin-top:4px; color:#c8a98b; font:.58rem 'Cinzel',serif; letter-spacing:1.3px; }}
@keyframes pujaPopup {{ 0%{{opacity:0;transform:translate(-50%,-25px) scale(.94)}} 12%{{opacity:1;transform:translate(-50%,0) scale(1)}} 78%{{opacity:1;transform:translate(-50%,0) scale(1)}} 100%{{opacity:0;transform:translate(-50%,-8px) scale(.98)}} }}

.countdown {{ text-align: center; margin: 4px auto 18px; }}
.countdown-label {{ font: 600 .7rem 'Cinzel', serif; letter-spacing: 2px; color: #aab1bf; }}
.countdown-value {{ font: 2.2rem 'Special Elite', monospace; color: #ffb366; text-shadow: 0 0 18px rgba(255,153,51,.25); }}

.footer {{
    width: 100vw; margin-left: calc(50% - 50vw); margin-right: calc(50% - 50vw);
    margin-top: 45px; padding: 35px max(24px, 5vw) 28px;
    border-top: 1px solid rgba(255,210,120,.72);
    background: linear-gradient(180deg, rgba(92,30,38,.99), rgba(52,14,22,.99));
    box-shadow: inset 0 1px 0 rgba(255,235,190,.08), 0 -18px 45px rgba(0,0,0,.24);
    border-radius: 0; backdrop-filter: blur(10px);
}}
.footer-links {{ display: flex; justify-content: center; gap: 28px; flex-wrap: wrap; margin-bottom: 20px; }}
.footer-link {{ color: #f7d59b; text-decoration: none; font-weight: 600; font-size: .75rem; }}
.footer-link:hover {{ color: #fff1cf; text-decoration: underline; text-underline-offset: 4px; }}
.footer-email {{ color: #ffd27a; font: 600 .78rem Arial, Helvetica, sans-serif; font-variant: normal; font-feature-settings: "smcp" 0; text-transform: none; letter-spacing: .25px; text-align: center; margin-bottom: 12px; }}
.footer-meta {{ text-align: center; color: #d7b9ad; font-size: .7rem; line-height: 1.8; }}

@media(max-width:800px) {{
    .speaker-layout {{ grid-template-columns: 1fr; }}
    .speaker {{ display: none; }}
    .status-row {{ flex-direction: column; gap: 8px; }}
}}
</style>""",
    unsafe_allow_html=True
)

if st.session_state.get("persistence_error"):
    st.error(f"Database connection/setup issue: {st.session_state.persistence_error}")
elif not supabase_enabled():
    st.warning("Supabase is not configured in Streamlit Secrets. The app is using local fallback storage.")

# ---------------- Global live event watcher ----------------
def _render_global_popup():
    if st.session_state.get("popup_message"):
        icon = "🌸" if st.session_state.get("popup_kind") == "flower" else "📍" if st.session_state.get("popup_kind") == "location" else "⚠️"
        st.markdown(
            f'''<div class="global-puja-popup"><span class="flower">{icon}</span><div class="popup-title">{st.session_state.popup_message}</div><div class="popup-sub">BANGALIR UTSAV · LIVE PUJA MOMENT</div></div>''',
            unsafe_allow_html=True
        )
        st.session_state.popup_message = None

if hasattr(st, "fragment"):
    @st.fragment(run_every="3s")
    def _live_location_watcher():
        try:
            event = get_latest_location_event()
            if event:
                event_id = f"{event.get('created_at','')}|{event.get('location','')}"
                if st.session_state.last_location_event_id is None:
                    st.session_state.last_location_event_id = event_id
                elif event_id != st.session_state.last_location_event_id:
                    st.session_state.last_location_event_id = event_id
                    st.session_state.popup_message = f"📍 {event.get('location','')}"
                    st.session_state.popup_kind = "location"
                    _render_global_popup()
        except PersistenceError:
            pass
    _live_location_watcher()

# ---------------- Countdown ----------------
def countdown():
    today = date.today()
    m = date(2026, 10, 10)
    b = date(2026, 10, 20)
    return "শুভ বিজয়া" if today > b else ("শুভ শারদীয়া" if today > m else f"{(m - today).days} DAYS")

st.markdown(f'<div class="countdown"><div class="countdown-label">Days Till Mahalaya...</div><div class="countdown-value">{countdown()}</div></div>', unsafe_allow_html=True)

# ---------------- Status & Hero ----------------
st.markdown(
    f"""<div class="status-row">
        <div class="status-pill"><span class="live-dot"></span> ON AIR · PUJA RADIO</div>
        <div class="status-pill" style="background:{accent_soft}">✦ {label}</div>
    </div>
    <div class="hero">
        <img src="data:image/jpeg;base64,{deity}" class="hero-icon">
        <div class="hero-title">বাঙালির উৎসব, বাঙালির গান</div>
        <div class="hero-subtitle">BENGALI MUSIC · PUJA SOUNDS · RADIO · ATMOSPHERE</div>
    </div>""",
    unsafe_allow_html=True
)

# ---------------- Pushpanjali Counter & Bell ----------------
st.markdown(
    f"""<div class="puja-counter">
        🪔 <span>এই মুহূর্তে পুষ্পাঞ্জলি নিবেদন করেছেন</span>
        <strong>{st.session_state.pushpanjali_count}</strong>
        <span>জন</span>
    </div>""",
    unsafe_allow_html=True
)

with st.container(key="push_bell_container"):
    if st.button("🔔", key="pushpanjali_btn", help="Offer Pushpanjali"):
        try:
            st.session_state.pushpanjali_count = increment_pushpanjali()
            st.session_state.persistence_error = None
            st.session_state.popup_message = "পুষ্পাঞ্জলি নিবেদন সম্পন্ন · শুভ শারদীয়া!"
            st.session_state.popup_kind = "flower"
        except PersistenceError as exc:
            st.session_state.persistence_error = str(exc)
            st.session_state.popup_message = "পুষ্পাঞ্জলি সংরক্ষণ করা যায়নি"
            st.session_state.popup_kind = "error"

_render_global_popup()

st.markdown(
    """<div class="pushpanjali-text">
        <div class="ben">পুষ্পাঞ্জলি প্রদান করুন এবং পবিত্র ঘণ্টা বাজান</div>
        <div class="eng">CLICK TO OFFER PUSHPANJALI AND RING THE SACRED BELL</div>
    </div>""",
    unsafe_allow_html=True
)

# ---------------- Atmospheric Navigation ----------------
st.markdown('<div class="nav-caption" style="text-align:center;color:#747d8d;font-size:.65rem;margin:4px 0 8px;">SELECT YOUR PUJA ATMOSPHERE</div>', unsafe_allow_html=True)
nav1, nav2, nav3, nav4 = st.columns(4)
with nav1:
    if st.button("🎵  Puja Songs", use_container_width=True, key="nav_songs"):
        st.session_state.active_section = "Puja Songs"
        st.rerun()
with nav2:
    if st.button("📺  Pujo TV", use_container_width=True, key="nav_tv"):
        st.session_state.active_section = "Pujo TV"
        st.rerun()
with nav3:
    if st.button("📻  Live Radio", use_container_width=True, key="nav_radio"):
        st.session_state.active_section = "Live Radio"
        st.rerun()
with nav4:
    if st.button("🥁  Puja Sounds", use_container_width=True, key="nav_sounds"):
        st.session_state.active_section = "Puja Sound"
        st.rerun()

section_anchor = {"Puja Songs":"songs", "Puja Sound":"sounds", "Live Radio":"radio", "Pujo TV":"tv"}[st.session_state.active_section]
st.markdown(f'<div id="{section_anchor}"></div>', unsafe_allow_html=True)
st.markdown(f'<div style="text-align:center;color:{accent};font:.68rem Cinzel,serif;letter-spacing:1.5px;margin:5px 0 18px;">NOW EXPLORING · {st.session_state.active_section.upper()}</div>', unsafe_allow_html=True)

def deck(playlist_id: str, title: str, component_key: str = "main_deck"):
    if not playlist_id:
        st.error("This playlist is not configured.")
        return

    playlist_json = json.dumps(str(playlist_id))
    title_json = json.dumps(str(title))
    html = r'''<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>
*{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;color:#eee;font-family:Arial,sans-serif}body{overflow-x:hidden;overflow-y:auto}
.vinyl{position:absolute;top:10px;right:10px;width:62px;height:62px;border-radius:50%;background:radial-gradient(circle at 50% 50%,#d6a15a 0 9%,#2b1710 10% 13%,#050505 14% 100%);border:2px solid #9a663b;box-shadow:0 5px 12px rgba(0,0,0,.7),inset 0 0 0 1px rgba(255,220,170,.18);z-index:20;transform-origin:50% 50%}.vinyl:before{content:"";position:absolute;inset:7px;border-radius:50%;border:1px solid rgba(255,255,255,.12);box-shadow:inset 0 0 0 4px rgba(255,255,255,.025),inset 0 0 0 10px rgba(255,255,255,.018)}.vinyl:after{content:"";position:absolute;left:50%;top:50%;width:5px;height:5px;border-radius:50%;background:#d9b06c;transform:translate(-50%,-50%);box-shadow:0 0 4px #000}.vinyl.playing{animation:vinylSpin 5.5s linear infinite}@keyframes vinylSpin{to{transform:rotate(360deg)}}.vinyl-title{position:absolute;inset:19px 8px 18px;display:flex;align-items:center;justify-content:center;text-align:center;color:#f2d19b;font:700 6px Georgia,serif;letter-spacing:.35px;text-transform:uppercase;overflow:hidden;pointer-events:none;z-index:2}.vinyl-label{position:absolute;top:7px;left:0;right:0;text-align:center;color:#8e6a44;font:6px Georgia,serif;letter-spacing:1px;z-index:2}
.console{width:100%;max-width:1120px;margin:0 auto;padding:18px 18px 20px;border-radius:8px;background:linear-gradient(90deg,rgba(255,255,255,.035),transparent 10%,transparent 90%,rgba(0,0,0,.16)),linear-gradient(180deg,#6b3e24 0,#3c2115 9%,#24140e 14%,#160e0b 100%);border:2px solid #9a663b;box-shadow:0 20px 45px rgba(0,0,0,.72),inset 0 1px rgba(255,230,190,.24),inset 0 -2px 0 rgba(0,0,0,.75);position:relative}.console:before{content:"";position:absolute;inset:5px;border:1px solid rgba(232,183,113,.28);border-radius:5px;pointer-events:none}.grain{position:absolute;inset:0;pointer-events:none;opacity:.12;background:repeating-linear-gradient(88deg,rgba(255,220,170,.12) 0 1px,transparent 1px 5px);mix-blend-mode:screen}
.header{position:relative;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 4px 13px;color:#c5a17e;font:600 9px Georgia,serif;letter-spacing:1.8px;text-transform:uppercase}.brand{color:#f0c77d;font-size:10px}.model{color:#9e8066}
.stereo{position:relative;display:grid;grid-template-columns:190px minmax(0,1fr) 190px;gap:14px;align-items:stretch}.speaker{min-height:360px;border:2px solid #765036;border-radius:4px;padding:13px;background:linear-gradient(145deg,#2d1a12,#130c09);box-shadow:inset 0 0 18px rgba(0,0,0,.95),inset 0 1px rgba(255,235,205,.08),0 8px 18px rgba(0,0,0,.48);position:relative;overflow:hidden}.speaker:before{content:"";position:absolute;inset:10px;border:1px solid #63432d;background:radial-gradient(circle at 50% 22%,#090807 0 10%,#2c2119 10.5% 11%,#090807 11.5% 20%,transparent 20.5%),radial-gradient(circle at 50% 22%,transparent 0 20%,#4a3524 20.5% 21%,#0b0907 21.5% 36%,transparent 36.5%),radial-gradient(circle at 50% 72%,#090807 0 18%,#31251d 18.5% 19.5%,#080706 20% 31%,transparent 31.5%),repeating-linear-gradient(0deg,#0b0908 0 4px,#2e2118 5px 6px);box-shadow:inset 0 0 30px #000}.speaker:after{content:"BANGALIR UTSAV";position:absolute;left:24px;right:24px;bottom:22px;padding:6px 4px;text-align:center;border-top:1px solid #7c5838;border-bottom:1px solid #5b3d28;color:#caa36c;font:600 8px Georgia,serif;letter-spacing:1.5px;background:rgba(13,8,6,.72)}
.center{min-width:0;border:2px solid #69472e;border-radius:4px;padding:12px;background:linear-gradient(180deg,#1b110c,#0b0907 22%,#15100d 100%);box-shadow:inset 0 0 30px rgba(0,0,0,.9),0 8px 18px rgba(0,0,0,.42)}.faceplate{border:1px solid #5e432e;background:linear-gradient(#0d0b09,#18110c);padding:9px;border-radius:3px;box-shadow:inset 0 0 16px #000}.display-row{display:grid;grid-template-columns:72px minmax(0,1fr) 72px;gap:10px;align-items:center}.meter{height:42px;border:1px solid #5a422b;background:#080706;position:relative;overflow:hidden;box-shadow:inset 0 0 10px #000}.meter .ticks{position:absolute;inset:6px 6px 8px;background:repeating-linear-gradient(90deg,#7b5c39 0 1px,transparent 1px 9px);opacity:.5}.meter .needle{position:absolute;width:42%;height:2px;left:7%;bottom:17%;background:#df9c51;transform-origin:100% 50%;transform:rotate(-23deg);box-shadow:0 0 7px #df9c51}.playing .meter .needle{animation:needle .55s ease-in-out infinite alternate}@keyframes needle{from{transform:rotate(-25deg)}to{transform:rotate(13deg)}}
.screen{min-width:0;height:78px;border:1px solid #604126;background:radial-gradient(circle at 50% 40%,#4a2a12,#120b07 65%);box-shadow:inset 0 0 22px #000;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;overflow:hidden}.screen-title{width:100%;text-align:center;color:#f0bd69;font:600 clamp(12px,2vw,18px) 'Noto Serif Bengali',Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 0 8px rgba(231,161,70,.25)}.screen-sub{color:#b9864b;font:8px monospace;letter-spacing:1.2px;margin-top:5px}.screen-time{color:#8d673f;font:8px monospace;margin-top:3px}
.tuning{margin-top:10px;border:1px solid #513b27;background:#0a0806;height:56px;position:relative;overflow:hidden}.freq{position:absolute;left:5%;right:5%;top:7px;display:flex;justify-content:space-between;color:#8e6a44;font:8px monospace}.scale{position:absolute;left:5%;right:5%;bottom:12px;height:18px;border-bottom:1px solid #7b5a39;background:repeating-linear-gradient(90deg,transparent 0 4.6%,#765638 4.8% 5%,transparent 5.2% 10%)}.tuning-needle{position:absolute;top:9px;bottom:8px;left:53%;width:2px;background:#e3a354;box-shadow:0 0 9px #e3a354}
.album{margin-top:10px;position:relative;aspect-ratio:16/8.8;border:1px solid #5a422c;background:#030303;overflow:hidden;box-shadow:inset 0 0 20px #000}.yt{position:absolute;inset:0;width:100%;height:100%;z-index:2}.yt iframe{width:100% !important;height:100% !important;border:0 !important;display:block}.album-caption{position:absolute;left:10px;right:10px;bottom:9px;color:#f1d19b;font:600 9px Georgia,serif;letter-spacing:1px;text-shadow:0 1px 3px #000;z-index:4;pointer-events:none;background:linear-gradient(transparent,rgba(0,0,0,.72));padding-top:24px}
.transport{margin-top:11px;padding:9px 7px;border-top:1px solid #65462e;border-bottom:1px solid #3b291d;display:flex;justify-content:center;align-items:center;gap:6px;flex-wrap:wrap;background:linear-gradient(#1a100b,#0c0907)}.physical{position:relative;height:38px;min-width:42px;padding:0 9px;border-radius:3px;border:1px solid #7b5a3b;background:linear-gradient(180deg,#6b5540 0,#30251b 44%,#110e0b 100%);color:#e5cba5;font:700 8px Georgia,serif;letter-spacing:.4px;box-shadow:0 2px 0 #080706,0 4px 7px rgba(0,0,0,.65),inset 0 1px rgba(255,255,255,.2);cursor:pointer;text-shadow:0 1px #000;transition:transform .08s,box-shadow .08s,filter .12s}.physical:before{content:"";position:absolute;left:7px;right:7px;top:4px;height:2px;background:rgba(255,239,210,.18);border-radius:3px}.physical:hover{filter:brightness(1.18)}.physical:active,.physical.pressed{transform:translateY(2px);box-shadow:0 0 0 #080706,0 2px 4px rgba(0,0,0,.55),inset 0 1px rgba(0,0,0,.3)}.physical.play{min-width:58px;background:linear-gradient(180deg,#a56a34,#5d2d17 48%,#2b160c);border-color:#a97b4a;color:#ffe8bd}.physical.stop{background:linear-gradient(180deg,#71453a,#2c1714)}
.knob-bank{display:grid;grid-template-columns:repeat(2,54px);gap:8px 14px;justify-content:center;margin-top:10px}.knob-wrap{text-align:center}.knob{width:50px;height:50px;border-radius:50%;margin:auto;background:radial-gradient(circle at 32% 28%,#d9c6a6 0,#9e8663 18%,#4d3b29 48%,#17110c 66%,#090706 68%);border:2px solid #9a7047;box-shadow:0 4px 9px #000,inset 0 1px 3px rgba(255,255,255,.22);position:relative;cursor:pointer}.knob:after{content:"";position:absolute;left:50%;top:5px;width:2px;height:15px;background:#24170e;transform:translateX(-50%);box-shadow:0 0 1px #000}.knob-label{margin-top:3px;color:#9f7a51;font:7px Georgia,serif;letter-spacing:1px}
.lower{margin-top:10px;display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center}.brand-plate{text-align:left;color:#c8a275;font:600 9px Georgia,serif;letter-spacing:1.5px}.status{text-align:center;min-height:14px;color:#b89a79;font:8px monospace;letter-spacing:.8px}.power{text-align:right;color:#d5aa69;font:700 8px monospace;letter-spacing:1px}.lamp{display:inline-block;width:7px;height:7px;border-radius:50%;background:#54281a;border:1px solid #8d4d31;vertical-align:middle;margin-right:5px}.playing .lamp{background:#e08b45;box-shadow:0 0 10px rgba(224,139,69,.7)}
@media(max-width:820px){.console{padding:12px}.stereo{grid-template-columns:1fr}.speaker{min-height:100px;height:100px}.speaker:before{inset:7px;background:repeating-linear-gradient(0deg,#0b0908 0 3px,#2e2118 4px 5px)}.speaker:after{bottom:8px;left:22%;right:22%;padding:3px;font-size:6px}.center{order:2}.speaker.left{order:1}.speaker.right{order:3}.display-row{grid-template-columns:58px minmax(0,1fr) 58px}.meter{height:36px}.album{aspect-ratio:16/7}.transport{gap:5px}.physical{height:36px;min-width:38px;padding:0 7px;font-size:7px}.physical.play{min-width:54px}.knob-bank{grid-template-columns:repeat(4,50px);gap:8px;margin-bottom:2px}.lower{grid-template-columns:1fr;gap:5px;text-align:center}.brand-plate,.power{text-align:center}}
@media(max-width:430px){.header{flex-direction:column;align-items:flex-start;gap:4px}.console{padding:9px}.speaker{min-height:74px;height:74px}.center{padding:8px}.display-row{grid-template-columns:48px minmax(0,1fr) 48px;gap:6px}.meter{height:32px}.screen{height:66px}.screen-title{font-size:12px}.tuning{height:48px}.album{aspect-ratio:16/6.8}.transport{gap:4px;padding:7px 3px}.physical{height:34px;min-width:34px;padding:0 5px;font-size:6.5px}.physical.play{min-width:49px}.knob-bank{grid-template-columns:repeat(4,44px);gap:5px}.knob{width:42px;height:42px}.knob:after{height:12px}}
</style></head><body>
<div class="console" id="console"><div class="grain"></div><div class="vinyl" id="vinyl"><div class="vinyl-label">PUJA</div><div class="vinyl-title" id="vinylTitle">__TITLE__</div></div><div class="header"><span>● <span class="brand">BANGALIR UTSAV</span> · VINTAGE HI-FI CONSOLE</span><span class="model">MODEL 76 · WOODGRAIN STEREO</span></div><div class="stereo"><div class="speaker left"></div><div class="center"><div class="faceplate"><div class="display-row"><div class="meter"><div class="ticks"></div><div class="needle"></div></div><div class="screen"><div class="screen-title" id="title">__TITLE__</div><div class="screen-sub" id="sub">PLAYLIST · READY</div><div class="screen-time"><span id="current">00:00</span> / <span id="duration">--:--</span></div></div><div class="meter"><div class="ticks"></div><div class="needle"></div></div></div><div class="tuning"><div class="freq"><span>FM 88</span><span>92</span><span>96</span><span>100</span><span>104</span><span>108</span></div><div class="scale"></div><div class="tuning-needle"></div></div><div class="album"><div class="yt" id="yt-host"></div><div class="album-caption">DURGAPUJA · BENGALI MUSIC</div></div><div class="transport"><button class="physical" id="prev">⏮ REV</button><button class="physical" id="rewind">◀◀ 10</button><button class="physical play" id="play">▶ PLAY</button><button class="physical stop" id="stop">■ STOP</button><button class="physical" id="forward">10 ▶▶</button><button class="physical" id="next">FWD ⏭</button><button class="physical" id="mute">MUTE</button></div><div class="knob-bank"><div class="knob-wrap"><div class="knob" id="volDown"></div><div class="knob-label">VOL −</div></div><div class="knob-wrap"><div class="knob" id="volUp"></div><div class="knob-label">VOL +</div></div><div class="knob-wrap"><div class="knob" id="prevTrack"></div><div class="knob-label">TRACK ◀</div></div><div class="knob-wrap"><div class="knob" id="nextTrack"></div><div class="knob-label">TRACK ▶</div></div></div></div><div class="lower"><div class="brand-plate">ANALOGUE AUDIO · STEREO RECEIVER</div><div class="status" id="status">READY · PRESS PLAY</div><div class="power"><span class="lamp"></span><span id="powerText">STANDBY</span></div></div></div><div class="speaker right"></div></div></div>
<script>
const PLAYLIST_ID=__PLAYLIST__;let player=null,ready=false,apiReady=false;const $=id=>document.getElementById(id);const fmt=s=>{s=Math.max(0,Math.floor(s||0));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')};function status(t){$('status').textContent=t}function sync(){if(!player||!ready)return;try{const d=player.getDuration()||0,c=player.getCurrentTime()||0,idx=player.getPlaylistIndex();$('current').textContent=fmt(c);$('duration').textContent=fmt(d);$('sub').textContent='PLAYLIST · TRACK '+(idx>=0?idx+1:'—')}catch(e){}}function playing(on){$('console').classList.toggle('playing',on);$('vinyl').classList.toggle('playing',on);$('powerText').textContent=on?'PLAYING':'STANDBY';$('play').textContent=on?'❚❚ PAUSE':'▶ PLAY';if(player){try{const d=player.getVideoData();if(d&&d.title)$('vinylTitle').textContent=d.title}catch(e){}}}function press(id){const b=$(id);if(!b)return;b.classList.add('pressed');setTimeout(()=>b.classList.remove('pressed'),130)}function onYTReady(){if(apiReady)return;apiReady=true;player=new YT.Player('yt-player',{height:'100%',width:'100%',playerVars:{controls:0,rel:0,playsinline:1,fs:0,modestbranding:1,iv_load_policy:3},events:{onReady:()=>{ready=true;player.cuePlaylist({listType:'playlist',list:PLAYLIST_ID,index:0});status('READY · FIRST TRACK QUEUED')},onStateChange:e=>{if(e.data===YT.PlayerState.PLAYING){playing(true);status('PLAYING · TRACK '+(player.getPlaylistIndex()+1))}else if(e.data===YT.PlayerState.PAUSED){playing(false);status('PAUSED · TRACK '+(player.getPlaylistIndex()+1))}else if(e.data===YT.PlayerState.ENDED){playing(false);status('TRACK COMPLETE')}sync()}}})}function boot(){const host=$('yt-host');if(host&&!$('yt-player')){const d=document.createElement('div');d.id='yt-player';host.appendChild(d)}if(window.YT&&window.YT.Player)onYTReady();else{window.onYouTubeIframeAPIReady=onYTReady;const tag=document.createElement('script');tag.src='https://www.youtube.com/iframe_api';document.head.appendChild(tag)}}$('play').onclick=()=>{press('play');if(player)player.getPlayerState()===1?player.pauseVideo():player.playVideo()};$('stop').onclick=()=>{press('stop');if(player){player.pauseVideo();player.seekTo(0,true);status('STOPPED · 00:00');playing(false)}};$('rewind').onclick=()=>{press('rewind');if(player)player.seekTo(Math.max(0,player.getCurrentTime()-10),true)};$('forward').onclick=()=>{press('forward');if(player)player.seekTo(Math.max(0,player.getCurrentTime()+10),true)};$('prev').onclick=()=>{press('prev');if(player)player.previousVideo()};$('next').onclick=()=>{press('next');if(player)player.nextVideo()};$('prevTrack').onclick=()=>{press('prevTrack');if(player)player.previousVideo()};$('nextTrack').onclick=()=>{press('nextTrack');if(player)player.nextVideo()};$('volDown').onclick=()=>{press('volDown');if(player)player.setVolume(Math.max(0,player.getVolume()-10))};$('volUp').onclick=()=>{press('volUp');if(player)player.setVolume(Math.min(100,player.getVolume()+10))};$('mute').onclick=()=>{press('mute');if(player){const wasMuted=player.isMuted();wasMuted?player.unMute():player.mute();status(wasMuted?'SOUND ON':'MUTED')}};setInterval(sync,500);boot();
</script></body></html>'''
    html=html.replace('__PLAYLIST__',playlist_json).replace('__TITLE__',title_json)
    components.html(html, height=760, scrolling=False)


def radio_deck(stations: dict):
    stations_json=json.dumps(stations)
    html=r"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><script src="https://cdn.jsdelivr.net/npm/hls.js@1.6.2/dist/hls.min.js"></script><style>
*{box-sizing:border-box}html,body{margin:0;background:transparent}body{font-family:Arial,sans-serif;color:#fff}.radio-vinyl{position:absolute;top:9px;right:78px;width:52px;height:52px;border-radius:50%;background:radial-gradient(circle at 50% 50%,#d6a15a 0 10%,#2b1710 11% 14%,#050505 15% 100%);border:2px solid #9a663b;box-shadow:0 4px 10px rgba(0,0,0,.65),inset 0 0 0 1px rgba(255,220,170,.18);z-index:15;transform-origin:50% 50%}.radio-vinyl:before{content:"";position:absolute;inset:6px;border-radius:50%;border:1px solid rgba(255,255,255,.12);box-shadow:inset 0 0 0 8px rgba(255,255,255,.018)}.radio-vinyl:after{content:"";position:absolute;left:50%;top:50%;width:5px;height:5px;border-radius:50%;background:#d9b06c;transform:translate(-50%,-50%)}.radio-vinyl.playing{animation:radioVinylSpin 5.5s linear infinite}@keyframes radioVinylSpin{to{transform:rotate(360deg)}}.radio-vinyl-title{position:absolute;inset:16px 6px 15px;display:flex;align-items:center;justify-content:center;text-align:center;color:#f2d19b;font:700 5px Georgia,serif;letter-spacing:.25px;text-transform:uppercase;overflow:hidden}.radio-vinyl-label{position:absolute;top:5px;left:0;right:0;text-align:center;color:#8e6a44;font:5px Georgia,serif;letter-spacing:.8px}.radio{position:relative;width:100%;max-width:1080px;margin:auto;padding:15px;border-radius:14px;background:linear-gradient(145deg,#3b2119,#17100d 40%,#090807);border:1px solid #a27a49;box-shadow:0 22px 55px rgba(0,0,0,.65),inset 0 1px rgba(255,240,205,.14);position:relative;overflow:hidden}.radio:before{content:"";position:absolute;inset:0;opacity:.13;background:repeating-linear-gradient(90deg,rgba(255,220,170,.08) 0 1px,transparent 1px 6px);pointer-events:none}.top{position:relative;display:flex;justify-content:space-between;color:#aa967f;font:600 10px Georgia,serif;letter-spacing:1.2px;padding-bottom:10px}.brand{color:#e0b46f}.radio-main{position:relative;display:grid;grid-template-columns:150px 1fr 145px;gap:12px;align-items:stretch}.speaker{min-height:205px;border:1px solid #72583a;border-radius:7px;background:repeating-linear-gradient(0deg,#0b0907 0 5px,#3a2a1c 6px 7px);box-shadow:inset 0 0 28px #000}.speaker-label{margin:82px 12px 0;padding:6px;text-align:center;border:1px solid #8b6b42;color:#c9a76d;font:600 9px Georgia,serif;letter-spacing:1px;background:#1b120c}.tuner{background:linear-gradient(#090807,#15100c);border:1px solid #5b452e;border-radius:7px;padding:12px;box-shadow:inset 0 0 28px #000}.channel{display:flex;justify-content:space-between;gap:8px;color:#f0c988;font:600 clamp(15px,2.4vw,21px) 'Noto Serif Bengali',Georgia,serif}.station{color:#a08c75;font:10px Arial,sans-serif;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dial{margin-top:17px;height:54px;border:1px solid #59442e;border-radius:5px;background:linear-gradient(#17100b,#0a0806);position:relative;overflow:hidden}.ticks{position:absolute;left:5%;right:5%;bottom:14px;height:22px;border-bottom:1px solid #9c713e;background:repeating-linear-gradient(90deg,transparent 0 7%,#8c6539 7.2% 7.5%,transparent 7.7% 10%)}.needle{position:absolute;top:6px;bottom:9px;width:2px;left:50%;background:#e9ae5d;box-shadow:0 0 9px #e9ae5d}.freq{position:absolute;left:6%;right:6%;top:6px;display:flex;justify-content:space-between;color:#9c794e;font:9px monospace}.radio-controls{display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:center;margin-top:12px}.key{height:31px;min-width:40px;padding:0 8px;border-radius:5px;border:1px solid #7f6544;background:linear-gradient(#4b4034,#17130f);color:#ddc39b;font:600 8px Georgia,serif;cursor:pointer}.key.play{min-width:57px;background:linear-gradient(#b87531,#5a2a13);color:#fff0d0}.station-select{width:100%;margin-top:11px;padding:9px;border-radius:5px;border:1px solid #765a39;background:#120d09;color:#e3c590;font:10px Georgia,serif}.knob{width:58px;height:58px;margin:auto;border-radius:50%;background:radial-gradient(circle at 35% 30%,#d7c09c,#8d704b 32%,#3a2a1b 59%,#0d0b08 63%);border:2px solid #9e784b;box-shadow:0 4px 12px #000;position:relative}.knob:after{content:"";position:absolute;width:2px;height:16px;background:#251a10;left:50%;top:5px;transform:translateX(-50%)}.label{text-align:center;color:#98754d;font:8px Georgia,serif;letter-spacing:1px;margin-top:3px}.vu-line{height:4px;margin-top:13px;background:#2e2015;border-radius:9px;overflow:hidden}.vu-line i{display:block;width:35%;height:100%;background:linear-gradient(90deg,#8d5125,#e7ad5a);animation:level .9s ease-in-out infinite alternate}.status{text-align:center;color:#a99580;font:9px monospace;letter-spacing:.8px;min-height:14px;margin-top:8px}@keyframes level{from{width:22%}to{width:74%}}.onair{display:inline-block;color:#f2a15b;border:1px solid #774122;padding:2px 6px;border-radius:3px;font:600 8px monospace;letter-spacing:1px;margin-left:5px}.playing .onair{box-shadow:0 0 10px rgba(240,110,40,.4)}
@media(max-width:700px){.radio{padding:9px;border-radius:10px}.top{font-size:8px}.radio-main{grid-template-columns:1fr}.speaker{display:none}.tuner{padding:10px}.dial{margin-top:11px;height:48px}.knob{width:46px;height:46px}.radio-controls{gap:4px}.key{min-width:34px;height:30px;font-size:8px;padding:0 6px}}@media(max-width:390px){.top{flex-direction:column;gap:3px}.radio{padding:8px}.key{min-width:32px}}
</style></head><body><div class="radio" id="radio"><div class="radio-vinyl" id="radioVinyl"><div class="radio-vinyl-label">RADIO</div><div class="radio-vinyl-title" id="radioVinylTitle">PUJA RADIO</div></div><div class="top"><span>● <span class="brand">BANGALIR UTSAV</span> · LIVE RADIO</span><span>VINTAGE BROADCAST RECEIVER</span></div><div class="radio-main"><div class="speaker"><div class="speaker-label">BENGAL RADIO</div></div><div class="tuner"><div class="channel" id="channel">বাংলা রেডিও <span class="onair" id="onair">OFF AIR</span></div><div class="station" id="station">Select a station below</div><div class="dial"><div class="freq"><span>88</span><span>92</span><span>96</span><span>100</span><span>104</span><span>108</span></div><div class="ticks"></div><div class="needle"></div></div><select id="stationSelect" class="station-select"></select><div class="radio-controls"><button class="key" id="prev">◀ PREV</button><button class="key play" id="play">PLAY</button><button class="key" id="stop">STOP</button><button class="key" id="next">NEXT ▶</button><button class="key" id="mute">MUTE</button></div><div class="vu-line"><i></i></div><div class="status" id="status">READY · SELECT A CHANNEL</div></div><div><div class="knob"></div><div class="label">VOLUME</div><div style="height:18px"></div><div class="knob" style="width:45px;height:45px"></div><div class="label">TUNE</div></div></div><audio id="audio" preload="none" crossorigin="anonymous"></audio></div><script>
const STATIONS=__STATIONS__;const sel=document.getElementById('stationSelect'),audio=document.getElementById('audio'),radio=document.getElementById('radio'),statusEl=document.getElementById('status'),onair=document.getElementById('onair'),playBtn=document.getElementById('play');let names=Object.keys(STATIONS),hls=null;names.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;sel.appendChild(o)});function current(){return sel.value}function cleanup(){if(hls){hls.destroy();hls=null}audio.pause();audio.removeAttribute('src');audio.load()}function load(){cleanup();const n=current(),src=STATIONS[n];document.getElementById('station').textContent=n;statusEl.textContent='READY · '+n;onair.textContent='OFF AIR';playBtn.textContent='PLAY';if(!src)return;if(src.includes('.m3u8')){if(audio.canPlayType('application/vnd.apple.mpegurl')){audio.src=src}else if(window.Hls&&Hls.isSupported()){hls=new Hls({enableWorker:true,lowLatencyMode:true});hls.loadSource(src);hls.attachMedia(audio);hls.on(Hls.Events.ERROR,(e,d)=>{if(d.fatal)statusEl.textContent='STREAM ERROR · HLS SOURCE UNAVAILABLE'})}else{statusEl.textContent='HLS NOT SUPPORTED IN THIS BROWSER'}}else{audio.src=src}}async function play(){try{if(!audio.src&&!hls)load();await audio.play();radio.classList.add('playing');document.getElementById('radioVinyl').classList.add('playing');document.getElementById('radioVinylTitle').textContent=current();onair.textContent='ON AIR';statusEl.textContent='PLAYING · '+current();playBtn.textContent='PAUSE'}catch(e){statusEl.textContent='STREAM UNAVAILABLE · CHECK THE LIVE SOURCE'}}function pause(){audio.pause();radio.classList.remove('playing');document.getElementById('radioVinyl').classList.remove('playing');onair.textContent='OFF AIR';statusEl.textContent='PAUSED · '+current();playBtn.textContent='PLAY'}sel.onchange=()=>load();playBtn.onclick=()=>audio.paused?play():pause();document.getElementById('stop').onclick=()=>{audio.pause();audio.currentTime=0;pause()};document.getElementById('mute').onclick=()=>{audio.muted=!audio.muted;document.getElementById('mute').textContent=audio.muted?'UNMUTE':'MUTE'};document.getElementById('prev').onclick=()=>{sel.selectedIndex=(sel.selectedIndex-1+names.length)%names.length;load()};document.getElementById('next').onclick=()=>{sel.selectedIndex=(sel.selectedIndex+1)%names.length;load()};audio.addEventListener('playing',()=>{radio.classList.add('playing');document.getElementById('radioVinyl').classList.add('playing');document.getElementById('radioVinylTitle').textContent=current();onair.textContent='ON AIR';playBtn.textContent='PAUSE'});audio.addEventListener('pause',()=>{if(!audio.ended)pause()});audio.addEventListener('error',()=>{radio.classList.remove('playing');document.getElementById('radioVinyl').classList.remove('playing');onair.textContent='OFF AIR';statusEl.textContent='STREAM ERROR · TRY ANOTHER CHANNEL';playBtn.textContent='PLAY'});load();
</script></body></html>"""
    html=html.replace('__STATIONS__',stations_json)
    components.html(html, height=430, scrolling=False)


def pujo_tv_deck(playlist_id: str, title: str, component_key: str = "pujo_tv_deck"):
    if not playlist_id:
        st.error("This playlist is not configured.")
        return
    playlist_json=json.dumps(str(playlist_id)); title_json=json.dumps(str(title))
    html=r"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>
*{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;color:#eee;font-family:Arial,sans-serif}body{overflow-x:hidden}.tv{width:100%;max-width:1080px;margin:0 auto;padding:18px 20px 22px;border-radius:20px;background:linear-gradient(145deg,#70472d 0,#3b2418 12%,#24150f 55%,#120c09 100%);border:2px solid #a87543;box-shadow:0 24px 60px rgba(0,0,0,.75),inset 0 1px rgba(255,238,200,.2);position:relative}.tv:before{content:"";position:absolute;inset:6px;border:1px solid rgba(244,194,120,.3);border-radius:15px;pointer-events:none}.tv-head{position:relative;display:flex;justify-content:space-between;gap:12px;color:#caa477;font:600 10px Georgia,serif;letter-spacing:1.7px;text-transform:uppercase;padding:0 4px 12px}.tv-brand{color:#f2c77c}.tv-body{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 190px;gap:16px;align-items:stretch}.crt{min-width:0;padding:15px;border:2px solid #5e3d27;border-radius:18px;background:linear-gradient(145deg,#1a110c,#090706);box-shadow:inset 0 0 32px #000,0 8px 18px rgba(0,0,0,.5)}.screen-frame{position:relative;background:#020202;border:10px solid #2e2119;border-radius:26px;box-shadow:inset 0 0 24px #000,0 0 0 2px #765137;overflow:hidden;aspect-ratio:16/9}.screen-frame:after{content:"";position:absolute;inset:0;border-radius:18px;pointer-events:none;background:radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,.42) 100%),repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 1px,transparent 1px 3px);z-index:4}.yt{position:absolute;inset:0;width:100%;height:100%;z-index:2}.yt iframe{width:100%;height:100%;border:0}.side{border:2px solid #60412c;border-radius:13px;background:linear-gradient(180deg,#2a1b13,#120c09);padding:14px;box-shadow:inset 0 0 22px #000;display:flex;flex-direction:column;justify-content:space-between}.speaker-grille{height:115px;border:1px solid #755337;border-radius:8px;background:repeating-linear-gradient(0deg,#0b0907 0 4px,#493523 5px 6px);box-shadow:inset 0 0 20px #000}.dial{margin-top:13px;height:52px;border:1px solid #795536;border-radius:6px;background:#0b0806;position:relative;overflow:hidden}.dial-scale{position:absolute;left:8%;right:8%;top:11px;display:flex;justify-content:space-between;color:#a68154;font:8px monospace}.dial-line{position:absolute;left:8%;right:8%;bottom:11px;height:1px;background:#87603a}.dial-needle{position:absolute;left:51%;top:8px;bottom:7px;width:2px;background:#e4aa5b;box-shadow:0 0 8px #e4aa5b}.knobs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:13px}.knob{width:54px;height:54px;margin:auto;border-radius:50%;background:radial-gradient(circle at 34% 28%,#d5bd92,#8a6b45 33%,#3a2919 60%,#0b0907 64%);border:2px solid #a27b4c;box-shadow:0 5px 12px #000;position:relative}.knob:after{content:"";position:absolute;width:2px;height:16px;left:50%;top:5px;transform:translateX(-50%);background:#24180f}.knob-label{text-align:center;color:#a7865c;font:8px Georgia,serif;letter-spacing:1px;margin-top:4px}.controls{margin-top:13px;display:flex;flex-wrap:wrap;justify-content:center;gap:6px;padding-top:11px;border-top:1px solid #4e3625}.key{height:34px;min-width:48px;padding:0 9px;border-radius:5px;border:1px solid #866445;background:linear-gradient(#554535,#1b130e);color:#e6cda5;font:600 8px Georgia,serif;cursor:pointer;box-shadow:inset 0 1px rgba(255,255,255,.08),0 3px 6px #000}.key:active{transform:translateY(2px);box-shadow:inset 0 2px 5px #000}.key.play{background:linear-gradient(#b56b2e,#5b2a12);color:#fff1d2}.timeline{margin-top:11px;height:8px;border-radius:8px;background:#2d1e15;border:1px solid #5d412a;overflow:hidden}.timeline input{width:100%;height:100%;margin:0;padding:0;accent-color:#e1a253;cursor:pointer}.meta{display:flex;justify-content:space-between;gap:8px;color:#9c7a54;font:8px monospace;margin-top:5px}.status{text-align:center;color:#b6956e;font:9px monospace;letter-spacing:.8px;margin-top:7px;min-height:13px}.now{margin-top:7px;color:#e7bd7b;text-align:center;font:600 10px Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.playing .crt{box-shadow:inset 0 0 32px #000,0 0 20px rgba(224,157,73,.13),0 8px 18px rgba(0,0,0,.5)}
@media(max-width:760px){.tv{padding:12px;border-radius:14px}.tv-head{font-size:8px}.tv-body{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr;gap:10px}.speaker-grille{height:70px}.dial{margin-top:0}.knobs{margin-top:0}.controls{grid-column:1/-1;margin-top:0}.timeline{grid-column:1/-1}.meta,.status,.now{grid-column:1/-1}.key{min-width:42px;height:33px;padding:0 7px}}@media(max-width:430px){.tv-head{flex-direction:column;gap:4px}.crt{padding:8px}.screen-frame{border-width:7px;border-radius:19px}.side{grid-template-columns:1fr}.speaker-grille{height:62px}.controls{gap:4px}.key{min-width:40px;font-size:7px}}
</style></head><body><div class="tv" id="tv"><div class="tv-head"><span>● <span class="tv-brand">BANGALIR UTSAV</span> · PUJO TV</span><span>VINTAGE TELEVISION RECEIVER</span></div><div class="tv-body"><div class="crt"><div class="screen-frame"><div class="yt" id="yt-host"></div></div><div class="now" id="now">__TITLE__</div><div class="controls"><button class="key" id="prev">◀ CH−</button><button class="key" id="rewind">◀◀ 10</button><button class="key play" id="play">▶ PLAY</button><button class="key" id="stop">■ STOP</button><button class="key" id="forward">10 ▶▶</button><button class="key" id="next">CH+ ▶</button><button class="key" id="mute">MUTE</button></div><div class="timeline"><input id="progress" type="range" min="0" max="1000" value="0" step="1" aria-label="Video progress"></div><div class="meta"><span id="elapsed">00:00</span><span id="duration">00:00</span></div><div class="status" id="status">READY · SELECTED PLAYLIST · PRESS PLAY</div></div><div class="side"><div><div class="speaker-grille"></div><div class="dial"><div class="dial-scale"><span>2</span><span>4</span><span>6</span><span>8</span><span>10</span><span>12</span></div><div class="dial-line"></div><div class="dial-needle"></div></div></div><div class="knobs"><div><div class="knob"></div><div class="knob-label">VOLUME</div></div><div><div class="knob"></div><div class="knob-label">TUNE</div></div></div></div></div></div><script>
const PLAYLIST_ID=__PLAYLIST__,TITLE=__TITLE__;let player=null,ready=false;const $=id=>document.getElementById(id),progress=$("progress");function fmt(sec){sec=Math.max(0,Math.floor(sec||0));return String(Math.floor(sec/60)).padStart(2,"0")+":"+String(sec%60).padStart(2,"0")}function setStatus(x){$("status").textContent=x}function setPlaying(v){$("tv").classList.toggle("playing",v);$("play").textContent=v?"❚❚ PAUSE":"▶ PLAY"}function onReady(){if(ready)return;ready=true;player=new YT.Player("yt-player",{width:"100%",height:"100%",playerVars:{playsinline:1,rel:0,modestbranding:1,controls:1},events:{onReady:()=>{player.cuePlaylist({listType:"playlist",list:PLAYLIST_ID,index:0});setStatus("READY · PRESS PLAY");sync()},onStateChange:e=>{if(e.data===1){setPlaying(true);setStatus("PLAYING · "+TITLE)}else if(e.data===2){setPlaying(false);setStatus("PAUSED · "+TITLE)}else if(e.data===0){setPlaying(false);setStatus("TRACK COMPLETE")}}}})}function boot(){const host=$("yt-host");if(host&&!$("yt-player")){const d=document.createElement("div");d.id="yt-player";host.appendChild(d)}if(window.YT&&window.YT.Player)onReady();else{window.onYouTubeIframeAPIReady=onReady;const tag=document.createElement("script");tag.src="https://www.youtube.com/iframe_api";document.head.appendChild(tag)}}function sync(){if(!player||!ready)return;const cur=player.getCurrentTime()||0,dur=player.getDuration()||0;progress.value=dur?Math.round(cur/dur*1000):0;$("elapsed").textContent=fmt(cur);$("duration").textContent=fmt(dur);const idx=player.getPlaylistIndex();if(idx!=null&&idx>=0)$("now").textContent=TITLE+" · TRACK "+(idx+1)}$("play").onclick=()=>{if(!player)return;if(player.getPlayerState()===1)player.pauseVideo();else player.playVideo()};$("stop").onclick=()=>{if(player){player.pauseVideo();player.seekTo(0,true);setPlaying(false);setStatus("STOPPED · 00:00")}};$("rewind").onclick=()=>{if(player)player.seekTo(Math.max(0,(player.getCurrentTime()||0)-10),true)};$("forward").onclick=()=>{if(player)player.seekTo(Math.min(player.getDuration()||0,(player.getCurrentTime()||0)+10),true)};$("prev").onclick=()=>{if(player)player.previousVideo()};$("next").onclick=()=>{if(player)player.nextVideo()};$("mute").onclick=()=>{if(player){const m=player.isMuted();m?player.unMute():player.mute();setStatus(m?"SOUND ON":"MUTED")}};progress.addEventListener("input",()=>{if(player){const dur=player.getDuration()||0;player.seekTo(dur*(Number(progress.value)/1000),true)}});setInterval(sync,500);boot();
</script></body></html>"""
    html=html.replace('__PLAYLIST__',playlist_json).replace('__TITLE__',title_json)
    components.html(html, height=690, scrolling=False)


# ---------------- Main Sections ----------------
if st.session_state.active_section == "Puja Songs":
    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">The Main Deck</div>
            <div class="section-title">🎵 দুর্গাপূজার গান · Puja Songs</div>
            <div class="section-description">Curated Bengali playlists inside the signature retro console.</div>""",
        unsafe_allow_html=True
    )
    names = list(CURATED_PLAYLISTS)
    selected = st.selectbox("Curated playlist", names, index=names.index(st.session_state.active_playlist), label_visibility="collapsed")
    st.session_state.active_playlist = selected
    st.markdown(f'<div style="text-align:center;color:#ffb366;font:600 .72rem Cinzel,serif;letter-spacing:1.5px;margin-bottom:8px;">{CURATED_PLAYLISTS[selected][0]}</div>', unsafe_allow_html=True)
    deck(CURATED_PLAYLISTS[selected][1], CURATED_PLAYLISTS[selected][0], component_key="curated_deck")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">AI Music Director</div>
            <div class="section-title">🤖 মায়ার গান · AI DJ</div>
            <div class="section-description">Describe a mood, setting, or musical style. Gemini dynamically interprets it into authentic Bengali music.</div>""",
        unsafe_allow_html=True
    )
    prompt = st.text_input("AI DJ prompt", placeholder="e.g. আজ সন্ধ্যার আরতিতে energetic pandal hopping rock চাই...", label_visibility="collapsed")
    if st.button("✦ Ask the AI DJ", key="ai_btn"):
        if prompt.strip():
            st.session_state.ai_result = get_ai_chat_recommendation(prompt)
        else:
            st.warning("Please describe your vibe first.")
    if st.session_state.ai_result:
        r = st.session_state.ai_result
        st.markdown(f'<div style="background:rgba(255,153,51,0.1);border-left:3px solid #ff9933;padding:12px 18px;border-radius:10px;margin:15px 0;font-size:.9rem;color:#ffe4c4;">✦ {r["response"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8993a3;font-size:.75rem;letter-spacing:1px;margin-bottom:4px;">AI ROUTE · {r.get("playlist_name", r.get("category", "Bengali Music"))} · ENERGY {r.get("energy", 3)}/5 · NOSTALGIA {r.get("nostalgia", 2)}/5 · FESTIVE {r.get("festive", 3)}/5</div>', unsafe_allow_html=True)
        deck(r.get("playlist_id", ""), CURATED_PLAYLISTS.get(r.get("playlist_name"), (r.get("category", "Bengali Music"), ""))[0], component_key="ai_deck")
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.active_section == "Puja Sound":
    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">Pandal Ambience</div>
            <div class="section-title">🥁 পুজোর শব্দ · Puja Sounds</div>
            <div class="section-description">Click a card to expand its atmosphere and acoustic player.</div>""",
        unsafe_allow_html=True
    )
    for i in range(0, 6, 3):
        cols = st.columns(3)
        for j in range(3):
            icon, bn, en, desc = SOUNDS[i + j]
            with cols[j]:
                st.markdown(
                    f"""<div style="padding:16px;border-radius:16px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.025);margin-bottom:12px;">
                        <div style="font-size:1.6rem;">{icon}</div>
                        <div style="font-family:'Noto Serif Bengali',serif;font-size:1.1rem;color:#f2f3f5;margin-top:4px;">{bn}</div>
                        <div style="font-family:'Cinzel',serif;font-size:.65rem;color:{accent};letter-spacing:1.5px;">{en}</div>
                    </div>""",
                    unsafe_allow_html=True
                )
                if st.button(f"Explore {en}", key=f"snd_{i+j}", use_container_width=True):
                    st.session_state.expanded_sound = None if st.session_state.expanded_sound == (i + j) else (i + j)
                    st.rerun()
                if st.session_state.expanded_sound == (i + j):
                    st.markdown(f'<div style="color:#8993a3;font-size:.8rem;line-height:1.5;margin:10px 0;">{desc}</div><div style="padding:10px;border:1px solid rgba(255,255,255,.06);border-radius:10px;color:#8993a3;font-size:.76rem;">Sound effect source not configured yet. Add licensed audio files under <code>assets/sounds/</code> to activate this module.</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.active_section == "Pujo TV":
    PUJO_TV_PLAYLISTS = {
        "Pujo Parikrama": ("Pujo Parikrama", "PLfTjRpsb1rY8"),
        "Pujo Documentaries": ("Pujo Documentaries", "PLecb9cZC82BA"),
        "Pujo Vlogs": ("Pujo Vlogs", "PLJqqjUoAyYQc"),
        "Pujo Food Vlogs": ("Pujo Food Vlogs", "PLE5h4EdnvhlE"),
        "Bhasan": ("Bhasan", "PLfVh5eUbKEO8"),
    }
    if "active_tv_playlist" not in st.session_state:
        st.session_state.active_tv_playlist = next(iter(PUJO_TV_PLAYLISTS))
    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">Vintage Television</div>
            <div class="section-title">📺 পুজোর টিভি · Pujo TV</div>
            <div class="section-description">Explore Puja journeys, documentaries, vlogs, food stories and Bhasan through the vintage television.</div>""",
        unsafe_allow_html=True
    )
    tv_names = list(PUJO_TV_PLAYLISTS)
    tv_selected = st.selectbox("Pujo TV playlist", tv_names, index=tv_names.index(st.session_state.active_tv_playlist), label_visibility="collapsed", key="pujo_tv_playlist")
    st.session_state.active_tv_playlist = tv_selected
    st.markdown(f'<div style="text-align:center;color:#ffb366;font:600 .72rem Cinzel,serif;letter-spacing:1.5px;margin-bottom:8px;">{PUJO_TV_PLAYLISTS[tv_selected][0]}</div>', unsafe_allow_html=True)
    pujo_tv_deck(PUJO_TV_PLAYLISTS[tv_selected][1], PUJO_TV_PLAYLISTS[tv_selected][0])
    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">Live Broadcast</div>
            <div class="section-title">📻 বাংলা রেডিও · Live Radio</div>
            <div class="section-description">Stream live radio broadcasts directly in the browser.</div>""",
        unsafe_allow_html=True
    )
    radio_deck(RADIO_STATIONS)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Location Board ----------------
st.markdown(
    """<div class="content-card">
        <div class="section-kicker">Live Pandal Map</div>
        <div class="section-title">📍 Share Your Puja Location</div>
        <div class="section-description">Broadcast your neighborhood or city to the live community board.</div>""",
    unsafe_allow_html=True
)
loc = st.text_input("Location", placeholder="e.g. Kolkata · Salt Lake · Howrah · North Kolkata", label_visibility="collapsed")
if st.button("📍 Broadcast my location", key="loc_btn"):
    if loc.strip():
        try:
            publish_location(loc.strip())
            st.session_state.persistence_error = None
            latest = get_latest_location_event()
            if latest:
                st.session_state.last_location_event_id = f"{latest.get('created_at','')}|{latest.get('location','')}"
            st.session_state.popup_message = f"📍 {loc.strip()}"
            st.session_state.popup_kind = "location"
        except PersistenceError as exc:
            st.session_state.persistence_error = str(exc)
            st.session_state.popup_message = f"Location could not be broadcast: {exc}"
            st.session_state.popup_kind = "error"
    _render_global_popup()
try:
    live_locations = get_locations(30)
except PersistenceError as exc:
    live_locations = []
    st.session_state.persistence_error = str(exc)
if live_locations:
    st.markdown(f'<div style="color:#8993a3;font-size:.82rem;line-height:1.6;margin-top:10px;"><b>LIVE VISITORS:</b> {" · ".join(live_locations)}</div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Song Request ----------------
st.markdown(
    """<div class="content-card">
        <div class="section-kicker">Community Requests</div>
        <div class="section-title">🎶 Submit Song Request</div>
        <div class="section-description">Send song requests directly to our curation sheet and notification alerts.</div>""",
    unsafe_allow_html=True
)
col_a, col_b = st.columns(2)
with col_a: rt = st.text_input("Song title", placeholder="e.g. Dhaker Tale")
with col_b: ra = st.text_input("Artist / Band", placeholder="e.g. Fossils / Cactus")
ru = st.text_input("YouTube URL (Optional)", placeholder="https://www.youtube.com/watch?v=...")
rl = st.text_input("Pandal / Location", placeholder="e.g. Bagbazar, Kolkata")
if st.button("✦ Send Song Request", key="song_req_btn", use_container_width=True):
    if rt.strip():
        ok, msg = submit_song_request(rt, ra, ru, rl)
        (st.success if ok else st.warning)(msg)
    else:
        st.warning("Please enter at least the song title.")
st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Footer ----------------
st.markdown(
    """<div class="footer">
        <div class="footer-links">
            <a class="footer-link" href="?section=songs#songs">🎵 Puja Songs</a>
            <a class="footer-link" href="?section=sounds#sounds">🥁 Puja Sounds</a>
            <a class="footer-link" href="?section=radio#radio">📻 Live Radio</a>
            <a class="footer-link" href="?section=tv#tv">📺 Pujo TV</a>
            <a class="footer-link" href="?panel=gallery#gallery">📸 Puja Gallery</a>
            <a class="footer-link" href="?panel=analytics#analytics">📊 Analytics</a>
        </div>
        <div class="footer-email">datascientistipsitacharyya@gmail.com</div>
        <div class="footer-meta">
            <div style="color:#dce2ea;font-size:.8rem;font-weight:700;">SHARODIYA DIGITAL RADIO · শুভ শারদীয়া</div>
            <div style="color:#ffb366;margin-top:4px;">BUILT WITH LOVE BY IPSIT ACHARYYA</div>
            <div style="color:#7f8795;margin-top:4px;">FESTIVALS OF THE BENGALI, FOR THE BENGALI, BY THE BENGALI</div>
        </div>
    </div>""",
    unsafe_allow_html=True
)


# ---------------- Footer-linked panels ----------------
if st.session_state.get("active_panel") == "gallery":
    st.markdown('<div id="gallery"></div>', unsafe_allow_html=True)
    st.markdown(
        """<div class="content-card footer-panel">
            <div class="section-kicker">Puja Gallery</div>
            <div class="section-title">📸 Puja Gallery</div>
            <div class="section-description">A quiet corner for your Puja memories and celebration photographs.</div>
        </div>""",
        unsafe_allow_html=True
    )
    gallery_dir = Path("assets/gallery")
    imgs = [p for p in gallery_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}] if gallery_dir.exists() else []
    if imgs:
        st.image([str(p) for p in imgs], use_container_width=True)
    else:
        st.info("Add your Puja celebration photos to assets/gallery/ to view them here.")
    st.markdown('<div style="text-align:center;margin:18px 0 8px;"><a class="footer-link" href="?panel=#gallery">← Back to footer</a></div>', unsafe_allow_html=True)

elif st.session_state.get("active_panel") == "analytics":
    st.markdown('<div id="analytics"></div>', unsafe_allow_html=True)
    st.markdown(
        """<div class="content-card footer-panel">
            <div class="section-kicker">Admin Analytics</div>
            <div class="section-title">📊 Analytics · Admin</div>
            <div class="section-description">Private interaction analytics for the site administrator.</div>
        </div>""",
        unsafe_allow_html=True
    )
    pw = st.text_input("Admin Password", type="password", key="admin_pw")
    if pw and pw == st.secrets.get("ADMIN_PASSWORD", "BangalirPujoBangalirThakbe"):
        log_file = Path("recommendation_log.xlsx")
        if log_file.exists():
            st.dataframe(pd.read_excel(log_file), use_container_width=True)
        elif Path("recommendation_log.csv").exists():
            st.dataframe(pd.read_csv("recommendation_log.csv"), use_container_width=True)
        else:
            st.info("No interaction logs recorded yet.")
    st.markdown('<div style="text-align:center;margin:18px 0 8px;"><a class="footer-link" href="?panel=#analytics">← Back to footer</a></div>', unsafe_allow_html=True)

