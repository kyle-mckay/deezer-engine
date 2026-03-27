# 🚀 Setup & Installation

This guide covers everything you need to get **Deezer Engine** running, from gathering your credentials to deploying via Docker or Python.

## 🔑 1. Prerequisites & Authentication

Before installing, you must have an active Deezer account and a valid **ARL Token**. This token allows the engine to act on your behalf.

### Obtaining your ARL Token

1. Open [deezer.com](https://www.deezer.com/) in your browser and **Log in**.
2. Press `F12` to open **Developer Tools**.
3. Follow the steps for your browser:

| Browser | Path to Token |
| --- | --- |
| **Chrome / Edge / Brave** | **Application** tab → **Storage** → **Cookies** → `https://www.deezer.com` |
| **Mozilla Firefox** | **Storage** tab → **Cookies** → `https://www.deezer.com` |

4. Locate the cookie named **`arl`**.
5. Copy the string in the **Value** column.

> [!CAUTION]
> **Keep this token secret.** It is your active session. Anyone with this token has full access to your Deezer account.

## ⚙️ 2. Configuration Reference

Deezer Engine can be configured via a `config.yml` file or **Environment Variables**.

> [!TIP]
> **Start simple first:** Use the minimal runtime templates in [`app/config.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/config.yml.template) and [`app/strategies.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/strategies.yml.template).
>
> If you want grouped advanced options and expanded examples, use [`templates/startup/config.comprehensive.yml`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/config.comprehensive.yml) and [`templates/startup/strategies.comprehensive.yml`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/strategies.comprehensive.yml).
>
> **Precedence:** Environment variables will always override values found in your `config.yml`.
>
> **Startup Snapshot:** Configuration is loaded and snapshotted at process startup. Changes to environment variables or `config.yml` require a restart to take effect.

| Config Key (`config.yml`) | Environment Variable | Req. | Default | Description |
| --- | --- | --- | --- | --- |
| `arl_token` | `DEEZER_ARL_TOKEN` | **Yes** | N/A | Your Deezer ARL authentication token. See [Obtaining ARL token](https://www.google.com/search?q=%23obtaining-arl-token). |
| `user_id` | `DEEZER_USER_ID` | **Yes** | N/A | Your numeric Deezer user ID (found in profile URL). |
| `log_level` | `DEEZER_LOG_LEVEL` | No | `INFO` | Verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `write_logs` | `DEEZER_WRITE_LOGS` | No | `true` | Whether to write logs to `/deezer_engine/data/logs/`. |
| `chunk_size` | `DEEZER_CHUNK_SIZE` | No | `50` | Max tracks processed in batch operation's. (Adding/removing from playlist, db checkpoint caching) |
| `api_batch_size` | `DEEZER_API_BATCH_SIZE` | No | `50` | API rate limit check interval (requests before pausing for rate limiting). |
| `rate_limit` | `DEEZER_RATE_LIMIT` | No | `60` | Maximum API requests per minute (for rate limiting). |
| `max_retries` | `DEEZER_MAX_RETRIES` | No | `4` | Number of retries for failed API requests (0 = try once, no retries; 4 = 1 attempt + 4 retries = 5 total attempts). |
| `log_interval` | `DEEZER_LOG_INTERVAL` | No | `120` | How many seconds before you get an update on progress when pulling tack data. |
| `print_banner` | `DEEZER_PRINT_BANNER` | No | `true` | Toggle the startup license/brand banner. |
| `playlist_cap` | `DEEZER_PLAYLIST_CAP` | No | `5000` | Max tracks allowed in **any** destination playlist (Deezer limit is 5k). |
| `favorites_cap` | `DEEZER_FAVORITES_CAP` | No | `10000` | Max tracks allowed in your "Favorites" (Deezer limit is 10k). |
| `retention` | `DEEZER_RETENTION` | No | `0` | Hours to use cached 'source' data before fetching live. |
| `file_retention` | `DEEZER_FILE_RETENTION` | No | `168` | The hours to retain a file export. |
| `track_stats_refresh` | `DEEZER_TRACK_STATS_REFRESH` | No | `90` | Days before refreshing dynamic metadata like track rank. |
| `album_stats_refresh` | `DEEZER_ALBUM_STATS_REFRESH` | No | `90` | Days before refreshing dynamic metadata like album fans and availability. |
| `blocklist_expiry_days` | `DEEZER_BLOCKLIST_EXPIRY_DAYS` | No | `7` | Days a failed track/album remains blocklisted before becoming eligible again. Set `0` to disable active blocklisting while still tracking failures. |
| `history_lookback` | `DEEZER_HISTORY_LOOKBACK` | No | `14` | Default lookback window in days for `history` sources when not set in strategy config. |
| `history_limit` | `DEEZER_HISTORY_LIMIT` | No | `100` | Default maximum number of history tracks to fetch when not set in strategy config. |
| `validation_mode` | `DEEZER_VALIDATION_MODE` | No | `warn` | Default validation mode for when used in conjunction with `i` / `o` keys: `fail` (stop strategy on validation failure) or `warn` (log warning, continue strategy). Can be overridden per component. |
| `run_before_cron` | `DEEZER_RUN_BEFORE_CRON` | No | `true` | In cron mode, run one sync immediately at container startup before waiting for the next cron slot. Set to `false` to wait until the next scheduled time. |

### Logic Hierarchy

The engine follows a specific priority when loading settings. This allows you to have a base configuration in a file while overriding specific keys (like tokens) via Docker secrets or environments.

1. **Environment Variables:** Checked first (highest priority).
2. **`config.yml`:** Checked if environment variables are not set.
3. **Hardcoded Defaults:** Used if neither of the above provides a value.

The resolved values are cached in memory for the lifetime of the process.

## 🐳 3. Installation: Docker (Recommended)

Docker is the easiest way to run the engine without managing Python dependencies manually.

### Option A: Docker Compose

Create a `docker-compose.yml` file. You can run in **Standard mode** (one-time sync) or **Cron mode** (scheduled).

> [!TIP]
> For first run, keep your runtime files minimal ([`app/config.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/config.yml.template) and [`app/strategies.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/strategies.yml.template) copied into your data directory). If you need more examples or grouped advanced config keys, copy from [`templates/startup/`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/).

```yaml
services:
    deezer-engine:
        image: kylemmkay/deezer-engine:latest
        container_name: deezer-engine
        volumes:
            - './data:/deezer_engine/data' # Stores ./db, ./logs, and ./strategies.yml
        environment:
            - DEEZER_USER_ID="123456789"
            - DEEZER_ARL_TOKEN="YOUR_ARL_HERE"
            - DEEZER_LOG_LEVEL=INFO
            - TZ=UTC
            #- DEEZER_SCHEDULE="0 3 * * *" # Optional: Daily at 3 AM (Based off env TZ)
            #- DEEZER_RUN_BEFORE_CRON=false # Optional: disable startup run and wait for first cron slot
```

> [!TIP]
> If you do not want to mount the `/deezer_engine/data` directory, you can create and bind mount `./strategies.yml:/deezer_engine/data/strategies.yml` instead.

### Execution Modes

| Mode | Command | Behavior |
| --- | --- | --- |
| **Default** | None | (Default) Dynamically executes cron if `DEEZER_SCHEDULE` configured, otherwise runs once. |
| **Run** | `command: run` / not included | Runs once and exits |
| **Cron** | `command: cron` | Container stays alive and runs on your `DEEZER_SCHEDULE`. |
| **Shell** | `command: shell` | Starts an interactive bash shell for debugging. |

### Docker Run (CLI)

For quick testing or one-off syncs without a Compose file:

```bash
# Standard One-time Run
docker run --rm \
  -v $(pwd)/data:/deezer_engine/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  kylemmkay/deezer-engine:latest run

# Scheduled Cron (stays running)
docker run -d \
  --name deezer-cron \
  -e DEEZER_SCHEDULE="0 3 * * *" \
  -v $(pwd)/data:/deezer_engine/data \
  kylemmkay/deezer-engine:latest cron

# Scheduled Cron (wait until first slot, skip startup run)
docker run -d \
  --name deezer-cron-delayed \
  -e DEEZER_SCHEDULE="0 3 * * *" \
  -e DEEZER_RUN_BEFORE_CRON=false \
  -v $(pwd)/data:/deezer_engine/data \
  kylemmkay/deezer-engine:latest cron
```

### 🏗️ Build & Development

If you are modifying the source code and want to test your changes within the Docker environment, follow these steps to build locally.

> [!TIP]
> Startup template options:
> - Minimal runtime defaults: [`app/config.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/config.yml.template) and [`app/strategies.yml.template`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/strategies.yml.template)
> - Expanded startup references: [`templates/startup/`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/)
>
> Validation-specific templates for parser and I/O checks live in [`templates/validation/`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/validation/) (see [`templates/validation/README.md`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/validation/README.md)).

>![NOTE]
>This assumes you have already cloned the repository and are within the working directory.

**1. Build the image:**
From the root of the repository:

```bash
docker build -t deezer-engine:dev .
```

**2. Run your dev build:**
Use your local image tag to verify changes:

```bash
docker run --rm \
  -v $(pwd)/data:/deezer_engine/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  deezer-engine:dev run
```

**3. Development Tips:**

* **Entrypoint:** The image uses [`docker-entrypoint.sh`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/docker-entrypoint.sh). If you modify this script, you **must** rebuild the image.

## 🐍 4. Deployment: Manual Python

Best for developers or running directly on a host machine (Python 3.11+ required).

1. **Clone & Setup:**

```bash
git clone https://codeberg.org/kylemmkay/deezer-engine.git
cd deezer-engine
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure:**

```bash
mkdir -p data
cp app/config.yml.template data/config.yml
cp app/strategies.yml.template data/strategies.yml
```

*Edit these files with your specific settings. For expanded examples, copy from [`templates/startup/`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/startup/) instead.*

3. **Run:**

```bash
cd app
python3 -m deezer_engine run
```

**Next Step:** Once installed, head over to the [Strategy Configuration](https://www.google.com/search?q=Strategy-Configuration) page to define your first smart playlist.
