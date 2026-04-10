### 🧪 IO Verification (Assertions)

> [!IMPORTANT]
> `strategies.offline.yml` is a test-coupled template used by `pytest` in `tests/test_input_output_offline.py`.
> It intentionally points to `tests/fixtures/album` as source data and writes outputs to `./tmp/pytest/input_output/`.
> Treat it as a reproducible integration validation asset, not a production strategy file.
>
> Modifier coverage must stay in sync: when adding validation for a new modifier, update both
> `templates/validation/input_output/strategies.yml` and
> `templates/validation/input_output/strategies.offline.yml`.

The pipeline supports explicit Input (`i`) and Output (`o`) assertions at every stage. This is a powerful debugging and validation tool to ensure your modifiers are transforming the tracklist exactly as expected. If an assertion fails at runtime, the strategy will stop to prevent saving an incorrect playlist.

* **Sources**: Support `o` (The number of tracks fetched from Deezer).
* **Modifiers**: Support both `i` (Tracks entering the modifier) and `o` (Tracks remaining after the modifier).
* **Destinations**: Support `i` (The final count being sent to the playlist or file).

> [!TIP]
> **Stable Sources for I/O Validation**
> Use static sources like **albums** or **file imports** to ensure consistent track counts for your assertions. Avoid **SmartTracklists** or dynamic playlists, as their naturally fluctuating content will cause I/O validation to fail during routine updates.

> [!TIP]
> **Offline Determinism**
> Set `config.pull_metadata: false` in your validation config to prevent metadata enrichment and stats refresh API pulls during assertion-focused runs.

#### Validation Example

This example demonstrates a strict validation of a "Top 10" filter from a specific album.

```yaml
playlists:
  - name: "Validated Top 10"
    source:
      - type: "album"
        id: "91258" 
        o: 18         # Assert: The album must contain exactly 18 tracks
    modifiers:
      - type: "sort"
        field: "id"
        order: "asc"
        i: 18         # Assert: 18 tracks enter the sort
        o: 18         # Assert: 18 tracks exit the sort
      - type: "limit"
        order: "top"
        count: 10
        i: 18         # Assert: 18 tracks enter the limit
        o: 10         # Assert: Exactly 10 tracks remain
    destination:
      - type: "file"
        name: "top-10-nimrod.json"
        i: 10         # Assert: Exactly 10 tracks are written to disk
```

#### Local vs. Global Assertion Logic

Because **Local Modifiers** apply after a source is collected but before it is merged into the global stream, the source `o` value refers to the raw source-stage total for that source block.
When a source block groups multiple IDs, names, or filenames, the engine expands those inputs, combines the returned tracks, and validates `o` against the combined count for the whole block.

```yaml
    source:
      - type: "album"
        id: "91258"
        o: 18             # Raw album count
        modifiers:
          - type: "limit"
            order: "top"
            count: 5
            i: 18         # Input to local modifier
            o: 5          # Output of local modifier
      - type: "album"
        id: "76585"
        o: 2              # Raw album count
    destination:
      - type: "file"
        i: 7              # 5 (from local limit) + 2 = 7 total
```

```yaml
    source:
      - type: "album"
        id: ["1234", "4432"]
        o: 12             # Combined total across both expanded album inputs
```