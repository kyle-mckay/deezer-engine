# Welcome to the Deezer Engine Wiki

Deezer Engine is designed for users who want "Smarter Playlists" for Deezer. By using a pipeline approach, you can automate the tedious parts of library management.

### 📚 Documentation Sections

* **[Setup & Installation](Setup-Installation):** Get running with Docker Compose.
* **[Strategy Examples](Strategy-Configuration#examples):** See examples of potential strategies.
* **[Environment Variables](Setup-Installation#configuration):** API keys and authentication.
* **[Strategy Guide](Strategy-Configuration):** Deep dive into the YAML syntax.
* **[Acknowledgments](Acknowledgments):** Credits to the libraries that make this possible.

### 🔍 Execution Example
When the engine runs a strategy, the logs will look like this:

```log
░█▀▄░█▀▀░█▀▀░▀▀█░█▀▀░█▀▄░░░█▀▀░█▀█░█▀▀░▀█▀░█▀█░█▀▀
░█░█░█▀▀░█▀▀░▄▀░░█▀▀░█▀▄░░░█▀▀░█░█░█░█░░█░░█░█░█▀▀
░▀▀░░▀▀▀░▀▀▀░▀▀▀░▀▀▀░▀░▀░░░▀▀▀░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀

Running Deezer-Engine v0.8.1
This is free software under the GNU GPL v3.0.
For more details, see https://codeberg.org/kylemmkay/deezer-engine
2026-01-23 04:27:05 - [DeezerEngine] [INFO] - Authenticated successfully as: k...y
2026-01-23 04:27:05 - [DeezerEngine] [INFO] - >>> START 1/5: Processing Strategy: Taylor Swift: The Timeline
2026-01-23 04:27:05 - [DeezerEngine] [INFO] - Action: Sorting by release_date (ascending)
2026-01-23 04:27:16 - [DeezerEngine] [INFO] - Syncing 789 tracks to 'Taylor Swift: Complete Discography' (Full Replace)
2026-01-23 04:27:50 - [DeezerEngine] [INFO] - Sync complete for 'Taylor Swift: Complete Discography'.
2026-01-23 04:27:50 - [DeezerEngine] [INFO] - >>> START 2/5: Processing Strategy: High-Rank Discovery
2026-01-23 04:27:50 - [DeezerEngine] [INFO] - Action: Filtered 'rank > 500000': Kept 14/40 tracks.
2026-01-23 04:27:50 - [DeezerEngine] [INFO] - Action: Deduplicated 0 tracks
2026-01-23 04:27:50 - [DeezerEngine] [INFO] - Action: Shuffling with 'smart' shuffle.
2026-01-23 04:27:53 - [DeezerEngine] [INFO] - Syncing 172 tracks to 'High-Rank Discovery' (Full Replace)
2026-01-23 04:28:04 - [DeezerEngine] [INFO] - Sync complete for 'High-Rank Discovery'.
...
```

### 🤖 AI Assistance

This project is developed with AI assistance to accelerate some aspects of development and/or documentation.
