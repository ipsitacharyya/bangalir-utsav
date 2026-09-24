# Bangalir Utsav — music player + AI DJ build

This build keeps the existing Streamlit page structure and retro-deck visual language, while replacing the non-functional music controls with a real YouTube IFrame Player API deck and upgrading the AI DJ into a curated-playlist recommender.

## Run locally

```bash
pip install -r requirements.txt
streamlit run main.py
```

The app can run without any API keys. In that case the AI DJ uses its local keyword/mood fallback. To enable Gemini interpretation, copy `.streamlit/secrets.toml` to `.streamlit/secrets.toml` and add `GEMINI_API_KEY`.

## Music playlists

The six curated playlists are stored in `data/playlists.json`:

- Rabindra Sangeet — `PLdPc6Zh7RXuI`
- Bangla Nostalgia — `PLWdmTN0RK6Bg`
- Bangla Dance Number — `PLR3nEniIImBs`
- Bangla Rock — `PLdM1f1Ja3FfQ`
- Pujor Gaan — `PLBI0x1hR947U`
- Mahalaya — `PLe9aEHPEmPds`

The main player loads a playlist by ID and uses one YouTube player instance. The retro REV / PLAY / PAUSE / FWD / VOL controls are wired to the YouTube IFrame Player API.

You can change playlist IDs later without changing `main.py`.

## AI DJ

The AI DJ now interprets a prompt across:

- energy
- warmth
- dance
- nostalgia
- festive intensity

Gemini returns a structured recommendation when `GEMINI_API_KEY` is configured. The app then routes the user to one of the six curated playlists. If Gemini is unavailable, a deterministic local fallback ranks the same playlists using keyword and mood signals.

Interaction logs are written to `recommendation_log.xlsx` when the environment permits, with CSV fallback.

## Existing integrations

Supabase, the Google Apps Script song-request webhook, Pushpanjali counter, location board, radio streams, gallery and admin analytics remain in the existing architecture.

For persistent cloud state, configure the relevant Supabase values in Streamlit Secrets. For song requests, configure `SONG_REQUEST_WEBHOOK`.

## Important security note

Do not commit real API keys, passwords or Supabase credentials. The distributed build intentionally contains only `.streamlit/secrets.toml`.


## Supabase persistence (important)

The Pushpanjali counter and live locations are designed to persist in Supabase when `SUPABASE_URL` and `SUPABASE_KEY` are configured. The app no longer silently writes to the local JSON file when Supabase is configured but a database operation fails. Instead, it shows the database error so a broken schema/RLS configuration cannot go unnoticed.

### One-time setup
1. Open your Supabase project.
2. Go to **SQL Editor**.
3. Run `database/migration.sql` once.
4. Put `SUPABASE_URL` and `SUPABASE_KEY` in Streamlit Cloud **Secrets** (or `.streamlit/secrets.toml` locally).
5. Restart the Streamlit app.

The Pushpanjali increment uses an atomic Postgres function (`increment_pushpanjali`) so simultaneous visitors do not overwrite each other. Locations are inserted into `public.live_locations`.

If Supabase credentials are absent, local `data/site_state.json` is used only for local development.
