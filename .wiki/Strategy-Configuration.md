This page provides details on each of the strategies supported by *Deezer Engine*.

# Examples

This section provides examples of different configurations that are possible.

## Filter playlist out of your library

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
      - type: "playlist"
        id: "99999999"
        order: "smart"

```

## Combine Discovery and New Releases (with Local Modifiers)

Merge new releases (limited to the top 10) and your discovery mix, deduplicate, then exclude anything already in your library.

```yaml
playlists:
  - name: "Weekly Discovery"
    source:
      - type: "smarttracklist"
        name: "new-releases"
        retention: 24
        modifiers:
          - type: "sort"
            field: "rank"
            order: "desc"
          - type: "limit"
            count: 10
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
      - type: "playlist"
        id: "88888888"
        order: "smart"

```

# Specifics

This section provides information on how each modifier is structured and used.

## Sources

Sources fetch track lists from Deezer. Will be combined into a single list of tracks for processing in [Modifiers](#modifiers).

### Usage

Multiple sources can be combined in a single strategy.

```yaml
    source:
      - type: "smarttracklist"
        name: "new-releases"
        retention: 23
      - type: "smarttracklist"
        name: "discovery"
        retention: 23
# ... rest of strategy

```

**Optional Parameters**: Parameters that all sources support but are not required.

* `retention` (defaults to `0`): The number of hours to cache the source; 0 = always live.
* `modifiers` (optional): A list of **Local Modifiers** that apply only to this specific source before it is merged into the global pipeline.

### `favorites`

Gets songs from your favorite tracks: `https://www.deezer.com/us/profile/<user_id>/loved`

```yaml
    source:
      - type: "favorites"

```

### `playlist`

Gets songs from a specific playlist. Currently only supports playlist id: `https://www.deezer.com/us/playlist/<playlist_id>`

```yaml
    source:
      - type: "playlist"
        id: "12345678"

```

### `smarttracklist`

Deezer's curated lists: `https://www.deezer.com/us/smarttracklist/...`

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

## Modifiers

Modifiers is an **optional** section designed to transform a track list. They can be applied **Globally** (to the whole pipeline) or **Locally** (within a specific source).

### Usage

**Global Modifiers**:
Applied after all sources have been collected.

```yaml
    modifiers:
      - type: "dedupe"

```

**Local Modifiers**:
Applied to a specific source before merging.

```yaml
    source:
      - type: "playlist"
        id: "12345"
        modifiers:
          - type: "shuffle"
            order: "random"

```

### `dedupe`

Remove duplicate track IDs. Deezer does not allow the same track to be in the same playlists, so sources currently de-duplicate by ID automatically when lists are consolidated. However, this allows you to force this behavior in the event future modifiers allow you to insert items after source collection.

```yaml
    modifiers:
      - type: "dedupe"

```

### `limit`

Slice your tracks to keep only a specific number of items from the start or end of the dataset.

```yaml
    modifiers:
      - type: "limit"
        order: "top"
        count: 20

```

**Supported limit orders**:

`top`, `head` or `first` - Retains the first `n` tracks from the beginning of the list.
`tail`, `bottom` or `last` - Retains the last `n` tracks from the end of the list.

### `filter`

Include only the tracks that meet specific criteria based on their metadata.

```yaml
    modifiers:
      - type: "filter"
        field: "rank"
        operator: "gt"
        value: 400000

```

**Supported Operators**:

> Note: String comparisons (equals, contains, starts_with, ends_with) are case-insensitive.

`eq`, `equals`, `==` or `is` - Match the exact value (e.g., `unseen: true`).
`ne`, `not`, `!=` or `is_not` - Exclude tracks matching the value.
`gt`, `greater_than`, `>` - True if the field is greater than the value.
`gte` or `>=` - True if the field is **greater than or equal** to the value.
`lt`, `less_than`, `<` - True if the field is less than the value.
`lte` or `<=` - True if the field is **less than or equal** to the value.
`contains`, `in` or `like` - Checks if the value exists anywhere within the field.
`starts_with`, `sw` or `startswith` - Checks if the field begins with the specified value.
`ends_with`, `ew` or `endswith` - Checks if the field ends with the specified value.

### `shuffle`

Shuffle the order of your tracks.

> It is recommended that your destination strategy is `replace` when using this as a global modifier.

```yaml
    modifiers:
      - type: "shuffle"
        order: "random"

```

**Types of shuffle**:

* **`smart`**: **Recommended.** Uses an interleaving algorithm to prevent "clustering." It groups tracks by artist and ensures that songs from the same artist are spread out as much as possible throughout the playlist.
* **`random`**: A true Fisher-Yates randomization. It ignores metadata like artist or album, providing a completely unbiased sequence.

### `sort`

Sort your tracks by a specific field in the order of your choice.

> It is recommended that your destination strategy is `replace` when using this as a global modifier.

```yaml
    modifiers:
      - type: "sort"
        order: "desc"
        field: "title"

```

**Supported sort orders**:

> Note: Fields are sorted with no case sensitivity.

`asc` or `ascending` - Sorts by `field` in ascending order (A-Z)
`desc` or `descending` - Sorts by `field` in descending order (Z-A)

**Supported sort fields**:

Currently the following fields are **always** fetched, though [more fields exist](https://deezer-python.readthedocs.io/en/stable/api_reference/resources/track.html#deezer.Track). This is currently due to the fetch API only returning *some* fields. Until an internal database is configured it would not be efficient to pull all info.

| Name | Description | Type |
| --- | --- | --- |
| `id` | The track's Deezer id | int |
| `title` | The track's full title | string |
| `unseen` | The track unseen status | boolean |
| `duration` | The track's duration in seconds | int |
| `rank` | The track's Deezer rank (bigger number = more popular) | int |
| `artist` | artist object (name, id, etc.) | object |
| `album` | album object (title, id, etc.) | object |

### `exclude`

Pull tracks from an additional [Source](#source) with the intent to remove them if present in the current track pipeline. Support's non-modifier optional parameters such as `retention`.

```yaml
    modifiers:
      - type: "exclude"
        source:
          type: "favorites"

```

## Destinations

Define where the final track list saves to.

### Usage

> Currently only supports output to playlists.

```yaml
# ... source section
# ... modifiers section
    destination:
      - type: "playlist"
        id: "01234567"
        order: "smart"

```
 
**Types** (required) - Different methods in which your playlist is updated
* `smart` or `smartreplace` - Adds or removes tracks by only processing what's changed. **Does not care about sorting order**.
* `replace` - Removes **all** tracks in destination library first, then adds songs from pipeline.
* `insert` or `append` - Add tracks from pipeline to playlist without removing any

**ID** (required) - The playlist ID you wish to save to: `https://www.deezer.com/us/playlist/<playlist_id>`