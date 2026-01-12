# Deezer Engine (Smart Playlists)

>Please note that this repository was built with AI 🤖 assistance.

Inspired by [Goofy](https://github.com/Chimildic/goofy) and [Playlist Machinery / Smarter Playlists](http://www.playlistmachinery.com/), Deezer Engine is a Python script that allows you to create and maintain smart playlists within Deezer using a declarative configuration approach.

## Overview

This project implements a pipeline-based system for managing playlists. You define strategies in a YAML configuration file that specify:
- Which sources to pull tracks from (your library, playlists, discovery mixes, etc.)
- How to transform the track list (exclude certain songs, remove duplicates, etc.)
- Where to send the final results (create or update playlists)

The engine handles caching, API interactions, and batch operations for you.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Deezer account
- An ARL token (authentication key) from your Deezer session

### Installation

1. Clone the repository.
```bash
git clone https://github.com/kyle-mckay/deezer-engine.git
cd deezer-engine
```

2. Set up a Python virtual environment (recommended).
```bash
python3 -m venv venv
source venv/bin/activate
```

> On Windows: venv\Scripts\activate

3. Install dependencies.
```bash
pip install -r requirements.txt
```

### Configuration

1. Copy the template files to create your local configuration.
```bash
cp config.yml.template config.yml
cp strategies.yml.template strategies.yml
```

2. Edit `config.yml` with your Deezer credentials.
   - Get your ARL token from your Deezer browser session (see the template for instructions).
   - Add your numeric user ID from your Deezer profile URL.

3. Edit `strategies.yml` to define your smart playlists.
   - Each strategy specifies sources, modifiers, and a destination.
   - See the [strategies.yml.template](strategies.yml.template) and [strategies/README.md](strategies/README.md) for example configurations.

### Running the Engine

```bash
python3 deezer-engine.py
```

The engine will process each strategy defined in `strategies.yml`, updating your playlists accordingly.

**Example**:

```log
2026-01-12 20:08:40 - [DeezerEngine] [INFO] - --- Starting Deezer Engine ---
2026-01-12 20:08:41 - [DeezerEngine] [INFO] - Authenticated successfully as: (redacted)
2026-01-12 20:08:41 - [DeezerEngine] [INFO] - --- Executing Strategy: No Sad Boy ---
2026-01-12 20:08:41 - [DeezerEngine] [INFO] - Fetching live favorites from Deezer API for User (redacted)...
2026-01-12 20:08:44 - [DeezerEngine] [INFO] - Looking through your library... found 250 songs so far.
...
2026-01-12 20:09:12 - [DeezerEngine] [INFO] - Looking through your library... found 2750 songs so far.
2026-01-12 20:09:12 - [DeezerEngine] [INFO] - Found 2767 songs in source: favorites
2026-01-12 20:09:12 - [DeezerEngine] [INFO] - Applying 'exclude' modifier...
2026-01-12 20:09:13 - [DeezerEngine] [INFO] - Fetching live tracks from playlist: 'Depresso'
2026-01-12 20:09:16 - [DeezerEngine] [INFO] - Exclusion complete: Removed 212 matching tracks.
2026-01-12 20:09:16 - [DeezerEngine] [INFO] - Modifier 'exclude' applied. Pipeline now contains 2555 tracks.
2026-01-12 20:09:16 - [DeezerEngine] [INFO] - Preparing destination for type 'smart' with 2555 tracks.
2026-01-12 20:09:47 - [DeezerEngine] [INFO] - Connected to 'No Sad Boi'. Running Smart Sync...
2026-01-12 20:09:47 - [DeezerEngine] [INFO] - 'No Sad Boi' is already in sync.
2026-01-12 20:09:47 - [DeezerEngine] [INFO] - --- Executing Strategy: Daily Discovery Mix ---
2026-01-12 20:09:49 - [DeezerEngine] [INFO] - Fetching songs for 'discovery'...
2026-01-12 20:09:49 - [DeezerEngine] [INFO] - Found 40 songs in source: discovery
2026-01-12 20:09:51 - [DeezerEngine] [INFO] - Fetching songs for 'new-releases'...
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Found 40 songs in source: new-releases
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Applying 'exclude' modifier...
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Exclusion complete: Removed 0 matching tracks.
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Modifier 'exclude' applied. Pipeline now contains 80 tracks.
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Applying 'dedupe' modifier...
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Dedupe complete: No duplicates found.
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Modifier 'dedupe' applied. Pipeline now contains 80 tracks.
2026-01-12 20:09:52 - [DeezerEngine] [INFO] - Preparing destination for type 'smart' with 80 tracks.
2026-01-12 20:09:54 - [DeezerEngine] [INFO] - Connected to 'Daily Discover Mix'. Running Smart Sync...
2026-01-12 20:09:54 - [DeezerEngine] [INFO] - 'Daily Discover Mix' is already in sync.
```

## Development

If you make changes to the dependencies, update the requirements file.
```bash
pip freeze > requirements.txt
```
