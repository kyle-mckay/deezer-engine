# 🛠️ Strategy Configuration

This guide details how to build and maintain smart playlists using the pipeline-based YAML configuration.

## Quick Start

Start with the minimal runtime strategy template in [`app/strategies.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/strategies.yml.template).

It includes two practical defaults:
- A simple artist timeline playlist
- A discovery mix with dedupe + smart shuffle

If you want broader examples (file backups, history exclusion, extra source combinations), use [`templates/startup/strategies.comprehensive.yml`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/strategies.comprehensive.yml).

## 📂 Sources

Sources fetch tracks from Deezer. You can combine multiple sources into a single pipeline.

```yaml
    source:
      - type: "smarttracklist"
        name: "discovery"
      - type: "favorites"
```

### General Source Parameters

Every source entry supports these optional fields:

* `retention`: (Int) Hours to cache data. `0` (default) means fetch live.
* `override_collection`: (String) Optional explicit collection tag to apply to returned tracks.
* `modifiers`: (List) **Local Modifiers** that apply *only* to this source before merging. If the source block groups multiple IDs, names, or files, the modifier runs once against the combined tracks from that grouped block.

### Supported Types

| Type | Required Field | Description |
| --- | --- | --- |
| `favorites` | None | Tracks from your "Loved Tracks" profile. |
| `history` | None | Tracks from your play history |
| `playlist` | `id` | All tracks from one playlist ID or multiple playlist IDs. |
| `album` | `id` | All tracks from one album ID or multiple album IDs. |
| `artist` | `id` | Iterates through one or multiple artists' discographies. |
| `track` | `id` | Fetches one track ID or multiple track IDs directly. |
| `smarttracklist` | `name` | Curated: `discovery`, `new-releases`, `inspired-by-1` to `5`. |
| `file` | `format` | Imports tracks from a file on your computer. |

#### `favorites`

Gets songs from your favorite tracks: `https://www.deezer.com/us/profile/<user_id>/loved`

```yaml
    source:
      - type: "favorites"
```

#### `history`

Gets songs from your history: `https://www.deezer.com/en/profile/me/history`

> [!NOTE]
> Deezer only tracks the last 100 songs. At the moment history is not aggregated.

```yaml
    source:
      - type: "history"
        lookback: 14 # optional
```

**Optional keys**:

* `lookback` - How many days to look back in your history.

#### `playlist`

Gets songs from a specific playlist. Currently only supports playlist id: `https://www.deezer.com/us/playlist/<playlist_id>`

```yaml
    source:
      - type: "playlist"
        id: "12345678"

# You can also merge multiple playlist IDs in one source block
    source:
      - type: "playlist"
        id: ["12345678", "23456789", "34567890"]
```

#### `album`

Gets songs from a specific album. Currently only supports album id: `https://www.deezer.com/us/album/<album_id>`

```yaml
    source:
      - type: "album"
        id: "12345678"

# You can also merge multiple album IDs in one source block
    source:
      - type: "album"
        id: ["12345678", "23456789"]
```

#### `artist`

Gets all songs from a specific artist by itterating through their albums. Currently only supports album id: `https://www.deezer.com/us/artist/<artist_id>`

```yaml
    source:
      - type: "artist"
        id: "123"

# You can also merge multiple artists in one source block
    source:
      - type: "artist"
        id: ["123", "456"]
```

> [!NOTE]
> For `playlist`, `album`, `artist`, and `track`, the `id` field accepts either a single value or a list.
> If an ID list includes invalid entries (empty/null), they are skipped with a warning and valid IDs continue.

#### `track`

Gets one or more specific tracks by Deezer track ID: `https://www.deezer.com/us/track/<track_id>`

```yaml
    source:
      - type: "track"
        id: "1008610492"

# You can also merge multiple track IDs in one source block
    source:
      - type: "track"
        id: ["1008610492", "1008610493", "1008610494"]

# Optional: preserve or force a specific collection tag from an upstream workflow
    source:
      - type: "track"
        id: ["1008610492", "1008610493"]
        override_collection: "smarttracklist__discovery"
```

By default, the `track` source does not force a synthetic source collection tag.
Use `override_collection` when you want an explicit collection identity in output rows.

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

      # A single source can also merge multiple smarttracklist names
      - type: "smarttracklist"
        name: ["discovery", "new-releases", "inspired-by-1"]
```

#### `file`

Imports your tracklist from a local file in either JSON or CSV format. This is useful for restoring prior backups or exports. **Requires there to be an `id` column containing the deezer song ID.**

```yaml
    source:
      - type: "file"
        dir: "./exports" # optional, relative to script directory
        name: "my_favorites.csv"

      # A single source can import multiple files in order
      - type: "file"
        dir: "./exports"
        name: ["favorites_1.csv", "favorites_2.csv"]
```

**Optional keys**:

* `format` - The file extension and data structure to use. Defaults to `json`.
* `dir` - The directory where the file will be saved. Defaults to an `exports` folder in your data directory.
* `filename` - The name of the file. You can use the `{date}` placeholder to include a timestamp (formatted as `_YYYYMMDD_HHMM`). If `filename` is omitted, the filename defaults to the current timestamp (`file_YYYYMMDD_HHMM`).
* `retention` - How many **hours** to keep old files. The system will delete files with the same name prefix that are older than this value. Set to `0` to disable automatic deletion. Defaults to `168` (7 days). (Config `file_retention` or ENV `DEEZER_FILE_RETENTION`)


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
| **`interleave`** | Merges tracks from one or more inject sources into the pipeline at defined intervals. |

### Global vs Local

**Local Modifier**: Applies to all songs in the parent source `type`. If your source block has grouped sources the modifiers are applied to that block before the result is merged globally.

```yaml
    source:
      - type: "favorites"
        modifiers: 
          # Applies only to the "favorites" source before merging with other sources
          - type: "exclude"
            source:
              - type: "playlist"
                id: "PLAYLIST_ID"
      - type: "playlist"
        id: ["ID_1", "ID_2"]
        modifiers:
          # Applies combined tracks from both playlist IDs before merging with other sources
          - type: "limit"
            order: "top"
            count: 5
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

### `interleave`

Merges tracks from one or more inject sources into the current pipeline at defined intervals. For each inject entry, after every N origin tracks, M tracks from that source are inserted. All injection schedules operate relative to the original origin count — injected tracks are never counted as origin.

When the pipeline is empty (e.g. used as the first global modifier), the modifier appends all inject sources in definition order.

```yaml
modifiers:
  - type: "interleave"
    continue_on_exhaust: false  # optional — append remaining inject tracks when origin runs out (default: false)
    inject:
      - source:
          type: "playlist"
          id: "wife_playlist_id"
        every: 2    # after every 2 origin tracks...
        add: 1      # ...insert 1 track from this source
        continue_on_exhaust: false  # optional — inject partial batch when source runs low (default: false)
      - source:
          type: "favorites"
        every: 3
        add: 2
        continue_on_exhaust: false  # stop injecting from this source if a full batch of 2 can't be filled
```

**`inject` entry keys:**

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `source` | Map | Yes | A standard source block (`type`, `id`, `name`, etc.). |
| `every` | Int | Yes | Insert after every N origin tracks. |
| `add` | Int | Yes | Number of tracks to insert per cycle. |
| `continue_on_exhaust` | Bool | No | When the inject source runs out and a full `add` batch can't be filled: `true` injects whatever remains (partial batch), `false` discards it. Falls back to the top-level key, then the global config default (`false`). |

**Top-level keys:**

| Key | Type | Description |
| --- | --- | --- |
| `continue_on_exhaust` | Bool | When origin runs out, `true` appends all remaining inject tracks; `false` discards them. Also controls whether origin stops early when inject exhausts. Falls back to the global config default (`false`). |

**`continue_on_exhaust` precedence (highest → lowest):**

1. Per-inject-entry `continue_on_exhaust` key
2. Top-level `continue_on_exhaust` key on the interleave block
3. `interleave_continue_on_exhaust` in `config.yml` / `DEEZER_INTERLEAVE_CONTINUE_ON_EXHAUST` env var
4. Hardcoded default: `false`

**Example — family mix (alternating every 2 songs):**

```yaml
playlists:
  - name: "Family Mix"
    source:
      - type: "favorites"
    modifiers:
      - type: "interleave"
        inject:
          - source:
              type: "playlist"
              id: "WIFE_PLAYLIST_ID"
            every: 2
            add: 1
      - type: "dedupe"
      - type: "shuffle"
        order: "random"
    destination:
      - type: "playlist"
        id: "REPLACE_WITH_YOUR_ID"
        order: "replace"
```

**Example — as a local modifier (interleave before merging with other sources):**

```yaml
source:
  - type: "favorites"
    modifiers:
      - type: "interleave"
        inject:
          - source:
              type: "playlist"
              id: "WIFE_PLAYLIST_ID"
            every: 1
            add: 1
  - type: "smarttracklist"
    name: "discovery"
```

## 🎯 Destinations

Define where the final list is saved. 

### Destination Modes

| Type | Required Field | Description |
| --- | --- | --- |
| `playlist` | `id` | Save tracks to one of your playlists. |
| `file` | none | Export tracks from any collection of sources into a single file. |

#### `playlist`

**ID** (required) - The playlist ID you wish to save to: `https://www.deezer.com/us/playlist/<playlist_id>`
**Order** (optional) - The method of adding/removing songs from the destination:

| Mode | Behavior |
| --- | --- |
| `smart` | Compares the pipeline to the playlist; only adds/removes changes. |
| `replace` | Wipes the playlist entirely and adds the new pipeline (Preserves sort order). |
| `insert` | Appends tracks to the existing playlist without removing anything. |

**Retention** (optional) - How old the collection for this playlist is before it's considered stale and needs to be refreshed. Defaults to `0` (no caching, always fetch live).

```yaml
destination:
  - type: "playlist"
    id: "01234567"
    order: "smart"
    retention: 24
```

### `file`

Exports your tracklist to a local file. This is the primary method for creating versioned backups or maintaining a historical archive.

```yaml
    destination:
      - type: "file"
        dir: "./exports"                 # optional, defaults to './exports'
        name: "my_favorites_{date}.json" # optional, defaults to 'file_{date}.json'
        retention: 72                    # optional, duration in hours

```

**Key Details:**

* **Format:** Determined by the file extension in `name` (defaults to `.json` if omitted).
* **Auto-Provisioning:** The `dir` path will be created automatically if it doesn't exist.
* **The `{date}` Placeholder:** This is replaced by a timestamp at runtime to ensure unique filenames.

> [!NOTE]
> **Retention vs. Cache**
> Unlike other strategies where `retention` refers to cache age, for the `file` destination, it manages **disk cleanup**.
> The tool looks for files in the `dir` that share the same **basename** (the text before `{date}`). It parses the timestamp within those filenames; any file older than the specified `retention` hours is deleted, while newer backups are preserved.
> If retention is not specified, no files are deleted within `dir`.

# Examples

This page provides expanded examples beyond the minimal startup template.

> For first-run onboarding, start with [`app/strategies.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/strategies.yml.template).
>
> For a larger starter set you can copy directly, use [`templates/startup/strategies.comprehensive.yml`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/strategies.comprehensive.yml).

## The "Artist Super-Fan"

This strategy pulls every track from a specific artist's career and organizes them strictly by the date they were released. By using `release_date` with an ascending order, the resulting playlist functions as a musical timeline, starting with the artist's earliest work and ending with their most recent hits.

```yaml
playlists:
  - name: "EDEN: The Timeline"
    source:
      - type: "artist"
        id: "14450" # EDEN
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

This merges your Discovery mix with the "Inspired By" tracks, but uses a **Local Modifier** to filter out lower-ranked (less popular) songs from the discovery source before they even hit your main list. If you later switch that discovery source to a grouped source block, the child modifier would run once on the combined tracks returned by that block.

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
      - type: "exclude"
        source:
          - type: "history"
            retention: 0
            lookback: 7
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

### Favorites back-up

This strategy stores a copy of all tracks and their data within a file. Whenever the strategy is run, it will create a new file and delete any files where the export date is older than 1 week.

```yml
playlists:
  - name "Favorites back-up"
    source:
      - type: "favorites"
    destination:
      - type: "file"
        dir: "./exports" # Store in app directory
        name: "favorites-backup_{date}.json"
        retention: 168
```
