# Spotify Auto-Playlists

### Intelligent playlist generation using external audio features, rule-based mood classification, and incremental synchronization with Spotify via an API-first backend.

---

## 🚀 Overview

Spotify Auto-Playlists is a backend-focused project designed to automatically categorize your liked Spotify tracks and generate curated playlists based on mood, genre, year, and other metadata.  
It uses external open datasets (MusicBrainz + AcousticBrainz) to infer musical mood, and synchronizes playlists incrementally through the Spotify API.

This project is built with:

- **Python 3.11+**
- **FastAPI backend**
- **Rule‑based mood classifier**
- **MusicBrainz + AcousticBrainz data enrichment**
- **Incremental Spotify playlist sync**
- **Local caching to avoid repeat API calls**

---

## ✨ Features

### 🎧 External Audio Feature Enrichment
- Fetches high‑level audio descriptors from AcousticBrainz  
- Automatically resolves MusicBrainz track IDs  
- Stores results in local cache to avoid repeated requests  
- Parallel fetching (10 threads) for high performance  

### 🧠 Mood Classification Engine
Rule‑based classification using AcousticBrainz high‑level data:
- `Workout`
- `Party`
- `Cleaning`
- `Focus`
- `Chill`
- `Sleep`
- `Unclassified`

Easily replaceable with ML/AI in the future.

### 🗂 Playlist Generation
Automatically builds:
- **"Auto – All"** (all your liked tracks)
- **One playlist per inferred mood**
- Scaffolding ready for Genre + Year playlists  

### 🔄 Incremental Playlist Synchronization
- Detects duplicates already present on Spotify  
- Adds only missing tracks  
- Creates `.diff` files only for playlists with changes  
- Preview mode or fully automatic mode  

### 🧱 API‑First Architecture
- Clean separation of concerns  
- FastAPI backend serving `/run` pipeline endpoint  
- Future‑ready for a React/Tauri/Flutter UI  

---

## 📦 Project Structure

```
app/
  api/
    fastapi_app.py        # FastAPI entrypoint
  core/
    cli_utils.py          # CLI printing utilities (to be replaced by logging)
    fs_utils.py           # JSON + filesystem helpers
    models.py             # Track + Classification dataclasses
  pipeline/
    orchestration.py      # Pipeline coordinator
    external_features.py  # MusicBrainz + AcousticBrainz integration
    classifier.py         # Rule-based mood engine
    playlist_manager.py   # Spotify diffing + sync
    cache_manager.py      # Liked tracks cache
  spotify/
    auth.py               # OAuth handling + token refresh
    tracks.py             # Fetch liked tracks
    playlists.py          # Playlist operations
```

---

## 🔧 Setup

### 1. Clone the repository
```bash
git clone https://github.com/me-odo/spotify-auto-playlists.git
cd spotify-auto-playlists
```

### 2. Install dependencies
If using `pip`:
```bash
pip install -r requirements.txt
```

or with `poetry`:
```bash
poetry install
```

### 3. Create your `.env`
```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
MUSICBRAINZ_USER_AGENT=spotify-auto-playlists/0.1 (your_email@example.com)
```

---

## ▶️ Running the API

Start FastAPI:

```bash
uvicorn api_main:app --reload
```

Then use:

```
POST /run
```

Example request body:

```json
{
  "refresh_tracks": false,
  "force_external_refresh": false,
  "refresh_classification": false,
  "apply_changes": false
}
```

The response includes:
- Number of tracks processed  
- Mood distribution  
- Playlists created / updated  
- Detailed diffs for each playlist  

---

## 🧪 CLI Mode (Optional)
A legacy CLI mode exists:

```bash
python main.py
```

It provides an interactive version of the pipeline.

---

## 🛠 Next Steps

Future versions will focus on:

- Full React/Tauri front‑end
- User‑editable playlist previews
- AI-assisted mood classification (OpenAI/TensorFlow)
- Genre/year/tempo clustering
- Advanced semantic deduplication  
- Export/import pipeline presets  

---

## 🤝 Contributing

Pull requests are welcome!  
If you'd like to propose major changes, please open an issue first.

---

## 📄 License

MIT License – free to use and modify.

