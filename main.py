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
    "AIR FM Rainbow Kolkata": "https://air.live-stream.co.in/rainbow_kolkata.mp3",
    "Radio Mirchi 98.3 FM": "https://stream-mz.planetradio.co.uk/mirchi.mp3"
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
if "pushpanjali_count" not in st.session_state:
    try:
        st.session_state.pushpanjali_count = get_pushpanjali_count()
        st.session_state.persistence_error = None
    except PersistenceError as exc:
        st.session_state.pushpanjali_count = 0
        st.session_state.persistence_error = str(exc)

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
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999; opacity: .065;
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
div[data-testid="stButton"] button:has(.bell-icon-marker) {{
    background: transparent !important; border: none !important; box-shadow: none !important;
    font-size: 3rem !important; padding: 0 !important; margin: 0 auto; display: block;
}}
div[data-testid="stButton"] button:has(.bell-icon-marker):hover {{
    transform: scale(1.15); filter: drop-shadow(0 0 18px rgba(255,153,51,.9)); background: transparent !important;
}}

.pushpanjali-text {{ text-align: center; background: transparent; margin-bottom: 22px; }}
.pushpanjali-text .ben {{ font-family: 'Noto Serif Bengali', serif; font-size: 0.95rem; color: #fff; }}
.pushpanjali-text .eng {{ font-family: 'Cinzel', serif; font-size: 0.78rem; color: #a0aec0; margin-top: 4px; letter-spacing: 1px; }}

/* Pill Buttons */
div[data-testid="stButton"] > button {{
    border-radius: 999px !important; min-height: 42px !important;
    border: 1px solid rgba(255,153,51,.32) !important;
    background: linear-gradient(135deg, rgba(255,98,28,.18), rgba(255,46,101,.12)) !important;
    color: #ffe4c4 !important; font-family: 'Noto Serif Bengali', serif !important;
    box-shadow: 0 8px 25px rgba(0,0,0,.2); transition: .2s;
}}
div[data-testid="stButton"] > button:hover {{
    border-color: rgba(255,153,51,.75) !important; transform: translateY(-1px);
}}

/* Cards & Controls */
.content-card {{
    background: linear-gradient(145deg, rgba(20,23,32,.82), rgba(9,11,16,.72));
    border: 1px solid rgba(255,255,255,.09); border-radius: 28px; padding: clamp(18px, 4vw, 40px);
    box-shadow: 0 25px 70px rgba(0,0,0,.46); backdrop-filter: blur(18px); margin-bottom: 18px;
}}
.section-kicker {{ color: {accent}; font: 600 .66rem 'Cinzel', serif; letter-spacing: 2px; text-transform: uppercase; }}
.section-title {{ font: 1.65rem 'Noto Serif Bengali', serif; margin: 4px 0; }}
.section-description {{ color: #9da5b5; font-size: .88rem; margin-bottom: 18px; }}

div[data-baseweb="select"] > div {{ background: transparent !important; border: none !important; border-bottom: 1px solid rgba(255,153,51,0.4) !important; border-radius: 0 !important; color: #ffd9ad !important; }}
ul[data-baseweb="menu"] {{ background: rgba(8,10,15,.96) !important; border: 1px solid rgba(255,153,51,.25) !important; }}
input, textarea {{ background: rgba(0,0,0,.25) !important; color: #fff !important; border: 1px solid rgba(255,255,255,.14) !important; border-radius: 8px !important; }}

/* Retro Deck */
.retro-deck {{
    max-width: 1040px; margin: 22px auto; padding: 20px; border-radius: 30px;
    background: linear-gradient(145deg, #30343e, #12141a 48%, #08090d);
    border: 3px solid #4b5262; box-shadow: 0 30px 65px rgba(0,0,0,.72), inset 0 2px 5px rgba(255,255,255,.09);
}}
.deck-top {{ display: flex; justify-content: space-between; color: #9aa4b5; font: 700 .66rem monospace; letter-spacing: 2px; padding-bottom: 14px; }}
.deck-brand {{ color: #ff9d45; }}
.speaker-layout {{ display: grid; grid-template-columns: 145px 1fr 145px; gap: 18px; align-items: center; }}
.speaker {{
    height: 380px; border-radius: 18px;
    background: radial-gradient(circle, #3a414e 0 6%, #11141a 7% 28%, #303746 29% 31%, #11141a 32%);
    border: 2px solid #596174; box-shadow: inset 0 0 30px #000, 0 10px 25px #000;
}}
.screen-frame {{
    background: #050609; border: 7px solid #181b23; border-radius: 20px; padding: 5px;
    box-shadow: inset 0 0 35px #000, 0 0 24px rgba(255,140,50,.09); overflow: hidden;
}}
.control-row {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; padding-top: 16px; margin-top: 16px; border-top: 1px solid rgba(255,255,255,.08); }}
.transport-key {{ padding: 8px 12px; border-radius: 7px; background: linear-gradient(145deg, #343b4d, #151821); border: 1px solid #515b72; color: #dce2ea; font: .66rem monospace; }}
.transport-key.play {{ background: linear-gradient(145deg, #ff6b21, #c62e00); color: #fff; }}

.countdown {{ text-align: center; margin: 4px auto 18px; }}
.countdown-label {{ font: 600 .7rem 'Cinzel', serif; letter-spacing: 2px; color: #aab1bf; }}
.countdown-value {{ font: 2.2rem 'Special Elite', monospace; color: #ffb366; text-shadow: 0 0 18px rgba(255,153,51,.25); }}

.footer {{
    margin-top: 45px; padding: 35px 24px 24px; border-top: 1px solid rgba(255,255,255,.1);
    background: rgba(7,9,13,.88); backdrop-filter: blur(16px); border-radius: 26px 26px 0 0;
}}
.footer-links {{ display: flex; justify-content: center; gap: 28px; flex-wrap: wrap; margin-bottom: 20px; }}
.footer-link {{ color: #aeb6c5; text-decoration: none; font-weight: 600; font-size: .75rem; }}
.footer-link:hover {{ color: #ffb366; }}
.footer-email {{ color: #ffb366; font: 600 .75rem 'Cinzel', serif; text-align: center; margin-bottom: 12px; }}
.footer-meta {{ text-align: center; color: #7f8795; font-size: .7rem; line-height: 1.8; }}

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

_, bell_col, _ = st.columns([2, 1, 2])
with bell_col:
    if st.button("🔔", use_container_width=True, help="Offer Pushpanjali", key="pushpanjali_btn"):
        try:
            new_total = increment_pushpanjali()
            st.session_state.pushpanjali_count = new_total
            st.session_state.persistence_error = None
            st.toast("🪔 পুষ্পাঞ্জলি নিবেদন সম্পন্ন · শুভ শারদীয়া!", icon="✨")
            st.rerun()
        except PersistenceError as exc:
            st.session_state.persistence_error = str(exc)
            st.error(f"Pushpanjali could not be saved to Supabase: {exc}")

st.markdown(
    """<div class="pushpanjali-text">
        <div class="ben">পুষ্পাঞ্জলি প্রদান করুন এবং পবিত্র ঘণ্টা বাজান</div>
        <div class="eng">CLICK TO OFFER PUSHPANJALI AND RING THE SACRED BELL</div>
    </div>""",
    unsafe_allow_html=True
)

# ---------------- Atmospheric Navigation ----------------
st.markdown('<div class="nav-caption" style="text-align:center;color:#747d8d;font-size:.65rem;margin:4px 0 8px;">SELECT YOUR PUJA ATMOSPHERE</div>', unsafe_allow_html=True)
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("🎵  Puja Songs", use_container_width=True, key="nav_songs"):
        st.session_state.active_section = "Puja Songs"
        st.rerun()
with nav2:
    if st.button("🥁  Puja Sounds", use_container_width=True, key="nav_sounds"):
        st.session_state.active_section = "Puja Sound"
        st.rerun()
with nav3:
    if st.button("📻  Live Radio", use_container_width=True, key="nav_radio"):
        st.session_state.active_section = "Live Radio"
        st.rerun()

st.markdown(f'<div style="text-align:center;color:{accent};font:.68rem Cinzel,serif;letter-spacing:1.5px;margin:5px 0 18px;">NOW EXPLORING · {st.session_state.active_section.upper()}</div>', unsafe_allow_html=True)

def deck(playlist_id: str, title: str, component_key: str = "main_deck"):
    """One YouTube IFrame player with real transport controls and playlist navigation."""
    if not playlist_id:
        st.error("This playlist is not configured.")
        return

    safe_title = json.dumps(title)
    safe_playlist = json.dumps(playlist_id)
    html = f"""
    <div class="retro-deck">
      <div class="deck-top">
        <div>● <span class="deck-brand">ANALOGUE AUDIO CORP.</span> · MODEL V-909</div>
        <div>HI-FI STEREO DIGITAL DECK</div>
      </div>
      <div class="speaker-layout">
        <div class="speaker"></div>
        <div class="screen-frame">
          <div id="yt-player" style="width:100%;height:380px;background:#050609;"></div>
        </div>
        <div class="speaker"></div>
      </div>
      <div style="text-align:center;color:#ffb366;font:600 .72rem Cinzel,serif;letter-spacing:1.5px;margin-top:12px;">{title}</div>
      <div id="track-status" style="text-align:center;color:#9da5b5;font:.72rem monospace;margin-top:6px;min-height:18px;">READY · CLICK PLAY</div>
      <div class="control-row">
        <button class="transport-key" id="prev">⏮ REV</button>
        <button class="transport-key play" id="play">▶ PLAY</button>
        <button class="transport-key" id="pause">⏸ PAUSE</button>
        <button class="transport-key" id="next">⏭ FWD</button>
        <button class="transport-key" id="vol-down">VOL −</button>
        <button class="transport-key" id="mute">◉</button>
        <button class="transport-key" id="vol-up">VOL +</button>
      </div>
    </div>
    <style>
      * {{ box-sizing:border-box; }}
      body {{ margin:0; background:transparent; font-family:monospace; }}
      .retro-deck {{ max-width:1040px; margin:22px auto; padding:20px; border-radius:30px; background:linear-gradient(145deg,#30343e,#12141a 48%,#08090d); border:3px solid #4b5262; box-shadow:0 30px 65px rgba(0,0,0,.72),inset 0 2px 5px rgba(255,255,255,.09); }}
      .deck-top {{ display:flex; justify-content:space-between; gap:12px; color:#9aa4b5; font:700 .66rem monospace; letter-spacing:2px; padding-bottom:14px; }}
      .deck-brand {{ color:#ff9d45; }}
      .speaker-layout {{ display:grid; grid-template-columns:145px 1fr 145px; gap:18px; align-items:center; }}
      .speaker {{ height:380px; border-radius:18px; background:radial-gradient(circle,#3a414e 0 6%,#11141a 7% 28%,#303746 29% 31%,#11141a 32%); border:2px solid #596174; box-shadow:inset 0 0 30px #000,0 10px 25px #000; }}
      .screen-frame {{ background:#050609; border:7px solid #181b23; border-radius:20px; padding:5px; box-shadow:inset 0 0 35px #000,0 0 24px rgba(255,140,50,.09); overflow:hidden; }}
      .control-row {{ display:flex; justify-content:center; gap:10px; flex-wrap:wrap; padding-top:16px; margin-top:16px; border-top:1px solid rgba(255,255,255,.08); }}
      .transport-key {{ padding:8px 12px; border-radius:7px; background:linear-gradient(145deg,#343b4d,#151821); border:1px solid #515b72; color:#dce2ea; font:.66rem monospace; cursor:pointer; }}
      .transport-key.play {{ background:linear-gradient(145deg,#ff6b21,#c62e00); color:#fff; }}
      .transport-key:hover {{ transform:translateY(-1px); filter:brightness(1.12); }}
      @media (max-width:800px) {{ .speaker-layout {{ grid-template-columns:1fr; }} .speaker {{ display:none; }} .screen-frame {{ width:100%; }} .deck-top {{ flex-direction:column; }} }}
    </style>
    <script>
      const PLAYLIST_ID = {safe_playlist};
      let player = null;
      let ready = false;
      let apiLoaded = false;

      function status(text) {{
        const el = document.getElementById('track-status');
        if (el) el.textContent = text;
      }}

      function loadPlaylist() {{
        if (!player || !ready) return;
        try {{
          player.cuePlaylist({{listType:'playlist', list:PLAYLIST_ID, index:0}});
          status('READY · FIRST TRACK QUEUED');
        }} catch (e) {{ status('PLAYER ERROR · TRY REFRESH'); }}
      }}

      function onYouTubeIframeAPIReady() {{
        apiLoaded = true;
        player = new YT.Player('yt-player', {{
          height: '380', width: '100%',
          playerVars: {{ controls: 0, rel: 0, playsinline: 1, fs: 1 }},
          events: {{
            onReady: function() {{ ready = true; loadPlaylist(); }},
            onStateChange: function(e) {{
              if (e.data === YT.PlayerState.PLAYING) status('PLAYING · TRACK ' + (player.getPlaylistIndex() + 1));
              else if (e.data === YT.PlayerState.PAUSED) status('PAUSED · TRACK ' + (player.getPlaylistIndex() + 1));
              else if (e.data === YT.PlayerState.ENDED) status('PLAYLIST COMPLETE');
            }}
          }}
        }});
      }}

      document.getElementById('play').onclick = () => {{ if (player) player.playVideo(); }};
      document.getElementById('pause').onclick = () => {{ if (player) player.pauseVideo(); }};
      document.getElementById('prev').onclick = () => {{ if (player) player.previousVideo(); }};
      document.getElementById('next').onclick = () => {{ if (player) player.nextVideo(); }};
      document.getElementById('vol-down').onclick = () => {{ if (player) player.setVolume(Math.max(0, player.getVolume() - 10)); }};
      document.getElementById('vol-up').onclick = () => {{ if (player) player.setVolume(Math.min(100, player.getVolume() + 10)); }};
      document.getElementById('mute').onclick = () => {{ if (player) player.isMuted() ? player.unMute() : player.mute(); }};

      if (!window.YT) {{
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);
      }} else if (window.YT.Player) {{
        onYouTubeIframeAPIReady();
      }}
    </script>
    """
    components.html(html, height=610, scrolling=False)

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

else:
    st.markdown(
        """<div class="content-card">
            <div class="section-kicker">Live Broadcast</div>
            <div class="section-title">📻 বাংলা রেডিও · Live Radio</div>
            <div class="section-description">Stream live radio broadcasts directly in the browser.</div>""",
        unsafe_allow_html=True
    )
    station = st.selectbox("Station", list(RADIO_STATIONS), label_visibility="collapsed")
    st.audio(RADIO_STATIONS[station])
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
            st.success("Your location is now active on the live board.")
            st.rerun()
        except PersistenceError as exc:
            st.session_state.persistence_error = str(exc)
            st.error(f"Location could not be saved to Supabase: {exc}")
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
            <a class="footer-link" href="#songs">🎵 Puja Songs</a>
            <a class="footer-link" href="#sounds">🥁 Puja Sounds</a>
            <a class="footer-link" href="#radio">📻 Live Radio</a>
            <a class="footer-link" href="#gallery">📸 Pujo Gallery</a>
            <a class="footer-link" href="#analytics">📊 Analytics</a>
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

st.markdown('<div id="gallery"></div>', unsafe_allow_html=True)
with st.expander("Pujo Gallery"):
    gallery_dir = Path("assets/gallery")
    imgs = [p for p in gallery_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}] if gallery_dir.exists() else []
    if imgs:
        st.image([str(p) for p in imgs], use_container_width=True)
    else:
        st.info("Add your Pujo celebration photos to assets/gallery/ to view them here.")

st.markdown('<div id="analytics"></div>', unsafe_allow_html=True)
with st.expander("Analytics · Admin"):
    pw = st.text_input("Admin Password", type="password", key="admin_pw")
    if pw and pw == st.secrets.get("ADMIN_PASSWORD", "BangalirPujoBangalirThakbe"):
        log_file = Path("recommendation_log.xlsx")
        if log_file.exists():
            st.dataframe(pd.read_excel(log_file), use_container_width=True)
        elif Path("recommendation_log.csv").exists():
            st.dataframe(pd.read_csv("recommendation_log.csv"), use_container_width=True)
        else:
            st.info("No interaction logs recorded yet.")