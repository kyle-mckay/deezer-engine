# Strategy Engine

This directory contains the modular components for building smart playlists. Strategies are defined in `strategies.yml` as a declarative pipeline: tracks flow from sources, through modifiers, and finally to a destination.

## Supported Components

### Sources

Sources fetch track lists from Deezer. All sources support caching with a `retention` parameter (hours to keep cache; 0 = always fresh).

**favorites** - Your library
```yaml
source:
  - type: "favorites"
    retention: 24
```

**playlist** - A specific playlist by ID
```yaml
source:
  - type: "playlist"
    id: "12345678"
    retention: 24
```

**smarttracklist** - Deezer's curated lists (discovery, new-releases, inspired-by-1 *through* inspired-by-5)
```yaml
source:
  - type: "smarttracklist"
    name: "discovery"
    retention: 24
```

Multiple sources can be combined in a single strategy:
```yaml
source:
  - type: "smarttracklist"
    name: "new-releases"
    retention: 24
  - type: "smarttracklist"
    name: "discovery"
    retention: 24
```

### Modifiers

Modifiers transform the track list. They are applied in order.

**dedupe** - Remove duplicate track IDs
```yaml
modifiers:
  - type: "dedupe"
```

**exclude** - Remove tracks found in another source
```yaml
modifiers:
  - type: "exclude"
    source:
      type: "favorites"
      retention: 24
```

You can exclude from a playlist, smart list, or any source:
```yaml
modifiers:
  - type: "exclude"
    source:
      type: "playlist"
      id: "98765432"
      retention: 24
```

**Planned Modifiers** - Some modifiers are in the works or not yet documented here:
- `sort`: [#9](https://github.com/kyle-mckay/deezer-engine/issues/9)
- `limit`: [#10](https://github.com/kyle-mckay/deezer-engine/issues/10)
- `artist-seperation`: [#11](https://github.com/kyle-mckay/deezer-engine/issues/11)
- `randomize`: [#12](https://github.com/kyle-mckay/deezer-engine/issues/12)

### Destinations

Destinations push the final track list to a **Deezer playlist**.

```yaml
destination:
  type: "smart"
  target: "01234567"
```

**Types** - There are a few different methods in which your playlist is updated:
- `smart` or `smartreplace` - (Recommended) Update playlist intelligently, preserving track dates by only adding/removing what changed
- `replace` - Removes **all** tracks in destination library first, then adds songs from pipeline.
- `insert` or `append` - Add tracks from pipeline to playlist without removing any

**replace**
---

## Complete Examples

>Will be moved to wiki when more strategies are available

### Example 1: Filter your library
Pull your favorite tracks but exclude a specific playlist, then update a target playlist.

```yaml
playlists:
  - name: "Filtered Favorites"
    source:
      - type: "favorites"
        retention: 48
    modifiers:
      - type: "exclude"
        source:
          type: "playlist"
          id: "12345678"
          retention: 48
    destination:
      type: "smart"
      target: "99999999"
```

### Example 2: Combine discovery sources
Merge new releases and discovery mixes, deduplicate, then exclude anything already in your library.

```yaml
playlists:
  - name: "Weekly Discovery"
    source:
      - type: "smarttracklist"
        name: "new-releases"
        retention: 24
      - type: "smarttracklist"
        name: "discovery"
        retention: 24
    modifiers:
      - type: "dedupe"
      - type: "exclude"
        source:
          type: "favorites"
          retention: 48
    destination:
      type: "smart"
      target: "88888888"
```

---

## How It Works

1. **Initialization:** `deezer-engine.py` reads `strategies.yml`.
2. **Source Phase:** Each source fetches tracks and writes to `./tmp/<strategy-name>.json`.
3. **Modifier Phase:** Each modifier reads the temp file, transforms it, and overwrites it.
4. **Destination Phase:** The final track list is pushed to your target playlist.

Caching is handled automatically based on `retention` values. Live data is fetched only when cache is expired or set to 0.