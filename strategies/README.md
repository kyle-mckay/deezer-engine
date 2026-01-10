# Strategy Engine Architecture

This directory contains the modular components of the parent script. 
The system follows a **Declarative Pipeline** pattern where tracks flow from a source, 
through various modifiers, and finally to a destination.

## Folder Structure

### `sources/`
**Responsibility:** Fetching raw track lists.
- Scripts here are responsible for interacting with the Deezer API or the local cache.
- **Caching Logic:** Should check `./cache/` for existing data. If `retention` is met (or 0), it performs a live fetch and updates the cache.
- **Output:** Returns a flat list of Track IDs to the Controller.

### `modifiers/`
**Responsibility:** Transforming and filtering data.
- These are "pure" functions. They take a list of Track IDs and return a modified list.
- Examples: `exclude.py` (subtracts one list from another), `dedupe.py` (removes duplicates), `sort.py` (reorders tracks).

### `destinations/`
**Responsibility:** Outputting the final list to Deezer.
- Handles the actual modification of your Deezer account.
- **Types:**
    - `replace`: Clears the target playlist before adding new tracks.
    - `append` or `insert`: Adds tracks to the end without checking for duplicates.

---

## Data Flow (The Pipeline)

1. **Initialization:** `deezer-playlists.py` reads `strategies.yml`.
2. **Source Phase:** The `StrategyController` (in `base.py`) calls a source worker. The worker saves the initial list to `./tmp/<strategy-name>.json`.
3. **Modification Phase:** The Controller iterates through the `modifiers` list in the YAML. Each modifier reads the `.json` file, performs its logic, and overwrites the file.
4. **Destination Phase:** The final IDs in the `.json` file are read and pushed to the target playlist via a destination worker.

## Guidelines for New Workers

- **Isolation:** Workers should not call each other directly (except for `exclude` calling a source).
- **Logging:** Use the centralized logger passed from the Controller to maintain a consistent audit trail.
- **Rate Limiting:** Destination workers must implement batching (e.g., 50 tracks per request) to respect Deezer API limits.