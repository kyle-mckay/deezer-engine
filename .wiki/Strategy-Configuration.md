# 🛠️ Strategy Configuration

This guide details how to build and maintain smart playlists using the pipeline-based YAML configuration.

## 📂 Sources

Sources fetch tracks from Deezer. You can combine multiple sources into a single pipeline.

```yaml
    source:
      - type: "smarttracklist"
        name: "new-releases"
        retention: 23
      - type: "favorites"
        retention: 12
```

### General Source Parameters

Every source entry supports these optional fields:

* `retention`: (Int) Hours to cache data. `0` (default) means fetch live.
* `modifiers`: (List) **Local Modifiers** that apply *only* to this source before merging.

### Supported Types

| Type | Required Field | Description |
| --- | --- | --- |
| `favorites` | None | Tracks from your "Loved Tracks" profile. |
| `playlist` | `id` | All tracks from a specific playlist ID. |
| `album` | `id` | All tracks from a specific album ID. |
| `artist` | `id` | Iterates through an artist's discography. |
| `smarttracklist` | `name` | Curated: `discovery`, `new-releases`, `inspired-by-1` to `5`. |

#### `favorites`

Gets songs from your favorite tracks: `https://www.deezer.com/us/profile/<user_id>/loved`

```yaml
    source:
      - type: "favorites"

```

#### `playlist`

Gets songs from a specific playlist. Currently only supports playlist id: `https://www.deezer.com/us/playlist/<playlist_id>`

```yaml
    source:
      - type: "playlist"
        id: "12345678"

```

#### `album`

Gets songs from a specific album. Currently only supports album id: `https://www.deezer.com/us/album/<album_id>`

```yaml
    source:
      - type: "album"
        id: "12345678"

```

#### `artist`

Gets all songs from a specific artist by itterating through their albums. Currently only supports album id: `https://www.deezer.com/us/artist/<artist_id>`

```yaml
    source:
      - type: "artist"
        id: "123"

```

#### `smarttracklist`

Deezer's curated lists: `https://www.deezer.com/us/smarttracklist/<list name>`

* `discovery`: "Discover some brand new tracks and music that's just brand new to you."
* `new-releases`: "Every week get your friday releases playlist based on the artists, albums and tracks you favorite."
* `inspired-by-` `1` through `5`: "Discover music similar to the artists you've been listening to lately."

```yaml
    source:
      - type: "smarttracklist"
        name: "discovery"
      - type: "smarttracklist"
        name: "new-releases"
      - type: "smarttracklist"
        name: "inspired-by-1"
      # leaving out 2-4 for example
      - type: "smarttracklist"
        name: "inspired-by-5"
```

## 🔧 Modifiers

Modifiers is an *optional* section that allows you to transform your track list (should you decide to add them). They can be **Global** (applied after all sources are merged) or **Local** (applied within a source).

| Modifier | Primary Purpose |
| --- | --- |
| **`dedupe`** | Removes duplicate track IDs from the pipeline. |
| **`limit`** | Slices the list to keep only a specific number of tracks. |
| **`filter`** | Includes only tracks that meet specific metadata criteria. |
| **`shuffle`** | Randomizes the track order (Smart or Random). |
| **`sort`** | Organizes tracks by fields like Rank, Title, or Date. |
| **`exclude`** | Removes tracks found in a secondary source. |

### Global vs Local

**Local Modifier**: Exclude all songs in your favorites if they also exist in the defined playlist.

```yaml
    source:
      - type: "favorites"
        modifiers: 
          - type: "exclude"
            source:
              - type: "playlist"
                id: "PLAYLIST_ID"
```

**Global**: Applies to the **all** tracks gathered.

```yaml
    modifiers:
      - type: "dedupe"

```

### Supported Modifiers

#### `dedupe`

Removes duplicate track IDs. Note that sources already de-duplicate by ID during consolidation, but this forces the behavior at specific pipeline stages.

```yaml
modifiers:
  - type: "dedupe"

```

#### `limit`

Slices the list to keep only a specific number of items.

* **Orders:** `top`/`head`/`first` or `tail`/`bottom`/`last`.

```yaml
modifiers:
  - type: "limit"
    order: "top"
    count: 20

```

#### `filter`

Includes only tracks meeting metadata criteria. String comparisons are case-insensitive.

```yaml
modifiers:
  - type: "filter"
    field: "rank"
    operator: "gt"
    value: 400000
  - type: "filter"
    field: "contains"
    operator: "gt"
    value: "cool"
  - type: "filter"
    field: "unseen"
    operator: "eq"
    value: 1

```

For available filter fields, see the official [deezer documentation for tracks](https://deezer-python.readthedocs.io/en/stable/api_reference/resources/track.html#deezer.Track).

> [!NOTE]
> Fields that are boolean are stored as `0` (false) and `1` (true) in the database.

**Supported Operators:**

> [!NOTE]
> Text comparrisons are case insensitive.

* `eq`, `equals`, `==`, `is`
* `ne`, `not`, `!=`, `is_not`
* `gt`, `greater_than`, `>` | `gte`, `>=`
* `lt`, `less_than`, `<` | `lte`, `<=`
* `contains`, `in`, `like`
* `starts_with`, `sw` | `ends_with`, `ew`

### `shuffle`

Randomizes the order. **Recommended:** Use `replace` as your destination mode when shuffling.

* **`smart`**: Uses an interleaving algorithm to prevent artist clustering.
* **`random`**: Traditional Fisher-Yates randomization.

```yaml
modifiers:
  - type: "shuffle"
    order: "smart"

```

### `sort`

Organizes tracks by a specific field. **Recommended:** Use `replace` destination mode.

* **Orders:** `asc` (A-Z) or `desc` (Z-A).

```yaml
modifiers:
  - type: "sort"
    order: "desc"
    field: "release_date"

```

For available sort fields, see the official [deezer documentation for tracks](https://deezer-python.readthedocs.io/en/stable/api_reference/resources/track.html#deezer.Track).

## 🎯 Destinations

Define where the final list is saved. Currently, only **playlists** are supported.

### Destination Modes

| Mode | Behavior |
| --- | --- |
| `smart` | Compares the pipeline to the playlist; only adds/removes changes. |
| `replace` | Wipes the playlist entirely and adds the new pipeline (Preserves sort order). |
| `insert` | Appends tracks to the existing playlist without removing anything. |

**ID** (required) - The playlist ID you wish to save to: `https://www.deezer.com/us/playlist/<playlist_id>`

```yaml
destination:
  - type: "playlist"
    id: "01234567"
    order: "smart"

```



# Examples

This page provides examples of different configurations that are possible.

## The "Artist Super-Fan"

This strategy pulls every track from a specific artist's career and organizes them strictly by the date they were released. By using `release_date` with an ascending order, the resulting playlist functions as a musical timeline, starting with the artist's earliest work and ending with their most recent hits.

```yaml
playlists:
  - name: "Taylor Swift: The Timeline"
    source:
      - type: "artist"
        id: "12246" # Taylor Swift
    modifiers:
      - type: "sort"
        field: "release_date"
        order: "asc"
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"

```

### High-Energy "Popular Only" Discovery

This merges your Discovery mix with the "Inspired By" tracks, but uses a **Local Modifier** to filter out lower-ranked (less popular) songs from the discovery source before they even hit your main list.

```yaml
playlists:
  - name: "High-Rank Discovery"
    source:
      - type: "smarttracklist"
        name: "discovery"
        modifiers:
          - type: "filter"
            field: "rank"
            operator: "gt"
            value: 500000 # Only keep very popular tracks
      - type: "smarttracklist"
        name: "inspired-by-1"
      - type: "smarttracklist"
        name: "inspired-by-2"
      - type: "smarttracklist"
        name: "inspired-by-3"
    modifiers:
      - type: "dedupe"
      - type: "shuffle"
        order: "smart" # Spread out artists for a better mix
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"

```

### The "Unseen" Global Hits Radar

This pulls from the **Top 50 Global** playlist but uses the `unseen` field to create a "New to Me" dashboard. It removes anything you have already "seen" in the Deezer interface.

```yaml
playlists:
  - name: "Unseen Global Hits"
    source:
      - type: "playlist"
        id: "10064140302" # Top 50 Global 2026
    modifiers:
      - type: "filter"
        field: "unseen"
        operator: "eq"
        value: 1
      - type: "limit"
        count: 20
        order: "top"
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"

```

### "Fresh Heavy Rotation" (Album + Favorites)

This combines a specific new album (e.g., **Robbie Williams'** *Britpop*) with your all-time favorites, then excludes a "Exclude" playlist you might have so you don't hear the same songs too often.

```yaml
playlists:
  - name: "Fresh Favorites"
    source:
      - type: "album"
        id: "897621962" # Britpop by Robbie Williams
      - type: "favorites"
    modifiers:
      - type: "exclude"
        source:
          type: "playlist"
          id: "1363560485" # Example ID for a 'Recently Played' list
      - type: "shuffle"
        order: "random"
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"

```

### Short-Track "Workout" Generator

This strategy pulls from a specific genre playlist (e.g., **Deep House 2026**) and uses a filter to only keep tracks under 3 minutes (180 seconds) to keep the energy high and the transitions frequent.

```yaml
playlists:
  - name: "Fast-Paced House"
    source:
      - type: "playlist"
        id: "10064138682" # Using Top 50 USA as a base
    modifiers:
      - type: "filter"
        field: "duration"
        operator: "lt"
        value: 180 # Tracks shorter than 3 mins
      - type: "limit"
        count: 30
        order: "first"
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"

```
