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
      type: "smart"
      target: "99999999"
```

## Combine Discovery and New Releases 

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

# Specifics

This section provides information on how each modifier is structured and used.

## Sources

Sources fetch track lists from Deezer. Will be combined into a single list of tracks for processing in [Modifiers](#modifiers).

>Sources do not currently support sub-modifers, though it is a planned feature within [Issue #13](https://github.com/kyle-mckay/deezer-engine/issues/13)

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

**Optional Parameters**: Parameters that all source support but are not required.
- `retention` (defaults to `0`): The number of hours to cache the source; 0 = always live

### `favorites`

Get's songs from your favorite tracks: `https://www.deezer.com/us/profile/<user_id>/loved`

```yaml
    source:
      - type: "favorites"
```

### `playlist`

Get's songs from a specific playlist. Currently only supports playlist id: `https://www.deezer.com/us/playlist/<playlist_id>`
```yaml
    source:
      - type: "playlist"
        id: "12345678"
```

### `smarttracklist`

Deezer's curated lists: `https://www.deezer.com/us/smarttracklist/...`
- `discovery`: "Discover some brand new tracks and music that's just brand new to you."
- `new-releases`: "Every week get your friday releases playlist based on the artists, albums and tracks you favorite."
- `inspired-by-` `1` through `5`: "Discover music similar to the artists you've been listening to lately."
 
```yaml
    source:
      - type: "smarttracklist"
        name: "discovery"
      - type: "smarttracklist"
        name: "new-releases"
      - type: "smarttracklist"
        name: "inspired-by-1"
      - type: "smarttracklist"
        name: "inspired-by-2"
      - type: "smarttracklist"
        name: "inspired-by-3"
      - type: "smarttracklist"
        name: "inspired-by-4"
      - type: "smarttracklist"
        name: "inspired-by-5"
```

## Modifiers

Modifiers is an **optional** section designed to transform the consolidated track list. They are applied in the same order as your `strategies.yml`.

### Usage

```yaml
# ... source section
    modifiers:
      - type: "exclude"
        source: 
          type: "favorites" 
          retention: 23
      - type: "dedupe"
# ... destination section
```

**Planned Modifiers** - Some modifiers are in the works or not yet documented here:
- `sort`: [#9](https://github.com/kyle-mckay/deezer-engine/issues/9)
- `limit`: [#10](https://github.com/kyle-mckay/deezer-engine/issues/10)
- `artist-seperation`: [#11](https://github.com/kyle-mckay/deezer-engine/issues/11)
- `randomize`: [#12](https://github.com/kyle-mckay/deezer-engine/issues/12)

### `dedupe`

Remove duplicate track IDs. Deezer does not allow the same track to be in the same playlists, so sources currently de-duplicate automatically when lists are consolidated. However this allows you to force this behaviour in the event future modifiers allow you to insert items after source collection.

```yaml
    modifiers:
      # ... other modifiers
      - type: "dedupe"
```

### `exclude`

Pull tracks from an additional [Source](#source) with intent to remove them if present in the current track pipeline. Support's non-modifier optional parameters such as `retention`.

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
      type: "smart"
      target: "01234567"
```
 
**Types** (required) - Different methods in which your playlist is updated
- `smart` or `smartreplace` - (Recommended over `replace`) Update playlist intelligently, preserving track dates by only adding/removing what changed
- `replace` - Removes **all** tracks in destination library first, then adds songs from pipeline.
- `insert` or `append` - Add tracks from pipeline to playlist without removing any

**Target** (required) - The playlist ID you wish to save to: `https://www.deezer.com/us/playlist/<playlist_id>`