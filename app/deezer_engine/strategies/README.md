# Strategy Engine

This directory contains the modular components for building smart playlists. Strategies are defined in `strategies.yml` as a declarative pipeline: tracks flow from sources, through modifiers, and finally to a destination.

See [Configuration](https://codeberg.org/kylemmkay/deezer-engine/wiki/Configuration) in the wiki for more details.

---

## How It Works

1. **Initialization:** `deezer-engine.py` reads `strategies.yml`.
2. **Source Phase:** Each source fetches tracks and writes to `./tmp/<strategy-name>.json`.
3. **Modifier Phase:** Each modifier reads the temp file, transforms it, and overwrites it.
4. **Destination Phase:** The final track list is pushed to your target playlist.

Caching is handled automatically based on `retention` values. Live data is fetched only when cache is expired or set to 0.