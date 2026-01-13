# Deezer Engine (Smart Playlists)

>Please note that this repository was built with AI 🤖 assistance.

Inspired by [Goofy](https://github.com/Chimildic/goofy) and [Playlist Machinery / Smarter Playlists](http://www.playlistmachinery.com/), Deezer Engine is a Python script that allows you to create and maintain smart playlists within Deezer using a declarative configuration approach.

> [!WARNING]
> **This script can delete songs from your playlists.** This goes without saying, but be aware that running this script with an incorrect configuration may result in permanently lost or broken playlists. At this time there is no backup functionality.

> [!WARNING]
> **Second Warning!.** This repository is under heavy revision. Any change has the potential of being a breaking change until a stable release is out. Until this time, limited support will be provided in setting this up. 

## Getting Started

- [Setup/Installation](https://github.com/kyle-mckay/deezer-engine/wiki/Setup-Installation)
  - [Docker Compose](https://github.com/kyle-mckay/deezer-engine/wiki/Setup-Installation#docker-compose)
- [Strategy Configuration](https://github.com/kyle-mckay/deezer-engine/wiki/Strategy-Configuration)
- [Environment Variables]() TBD

## Overview

This project implements a pipeline-based system for managing playlists. You define strategies in a YAML configuration file that specify:
- Which sources to pull tracks from (your library, playlists, discovery mixes, etc.)
- How to transform the track list (exclude certain songs, remove duplicates, etc.)
- Where to send the final results (create or update playlists)

The engine handles caching, 'API' interactions, and batch operations for you.

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

Here is a professionally formatted **"Acknowledgments"** or **"Credits"** section for your GitHub Wiki or `README.md`. It highlights the key open-source library that powers your engine's communication with Deezer.

---

## Acknowledgments & Dependencies

This project is made possible thanks to the following open-source libraries and resources:

### [deezer-python](https://github.com/browniebroke/deezer-python)

A friendly Python wrapper around the Deezer API. This library handles the heavy lifting of mapping Deezer's API responses to easy-to-use Python objects.

- **Author:** [Bruno Alla (browniebroke)](https://github.com/browniebroke)
- **License:** MIT

### Additional Python Dependencies

- **[Requests](https://github.com/psf/requests):** Used for low-level HTTP handling and session management during the authentication handshake.
- **[PyYAML](https://github.com/yaml/pyyaml):** Powering the logic behind the `strategies.yml` configuration.
