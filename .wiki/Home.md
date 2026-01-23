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

Running Deezer-Engine v0.8.0
This is free software under the GNU GPL v3.0.
For more details, see https://codeberg.org/kylemmkay/deezer-engine
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Environment: Local
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Database: Initialized
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Authenticated successfully as: xyz
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Loaded 1 strategies.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - >>> START: Processing Strategy: High-Rank Discovery
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Filter applied: 'rank > 500000'. Kept 14/40 tracks.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Dedupe applied: No duplicates found.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Applied 'dedupe': Processed 171 tracks.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Applying 'smart' shuffle.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Applied 'shuffle': Processed 171 tracks.
2026-01-22 19:27:35 - [DeezerEngine] [INFO] - Syncing 171 tracks to playlist (ID: 123... ).
2026-01-22 19:27:40 - [DeezerEngine] [INFO] - Syncing 'High-Rank Discovery' (Full Replace)
2026-01-22 19:27:41 - [DeezerEngine] [INFO] - Done: Removed 170 tracks.
2026-01-22 19:27:46 - [DeezerEngine] [INFO] - Injecting 171 tracks...
2026-01-22 19:27:47 - [DeezerEngine] [INFO] - Done: Added 171 tracks.
2026-01-22 19:27:47 - [DeezerEngine] [INFO] - Sync complete for 'High-Rank Discovery'.
2026-01-22 19:27:47 - [DeezerEngine] [INFO] - Successfully completed: High-Rank Discovery
```

### 🤖 AI Assistance

This project is developed with AI assistance to accelerate some aspects of development and/or documentation.
