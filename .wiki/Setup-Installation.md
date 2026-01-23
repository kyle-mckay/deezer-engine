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
> **Precedence:** Environment variables will always override values found in your `config.yml`.

| Config Key (`config.yml`) | Environment Variable | Req. | Default | Description |
| --- | --- | --- | --- | --- |
| `arl_token` | `DEEZER_ARL_TOKEN` | **Yes** | N/A | Your Deezer ARL authentication token. See [Obtaining ARL token](https://www.google.com/search?q=%23obtaining-arl-token). |
| `user_id` | `DEEZER_USER_ID` | **Yes** | N/A | Your numeric Deezer user ID (found in profile URL). |
| `log_level` | `DEEZER_LOG_LEVEL` | No | `INFO` | Verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `write_logs` | `DEEZER_WRITE_LOGS` | No | `true` | Whether to write logs to `/app/data/logs/`. |
| `batch_size` | `DEEZER_BATCH_SIZE` | No | `50` | Max tracks processed in batch operation's. (Adding/removing from playlist, db checkpoint caching) |
| `log_interval` | `DEEZER_LOG_INTERVAL` | No | `120` | How many seconds before you get an update on progress when pulling tack data. |
| `print_banner` | `DEEZER_PRINT_BANNER` | No | `true` | Toggle the startup license/brand banner. |
| `playlist_cap` | `DEEZER_PLAYLIST_CAP` | No | `5000` | Max tracks allowed in **any** destination playlist (Deezer limit is 5k). |
| `favorites_cap` | `DEEZER_FAVORITES_CAP` | No | `10000` | Max tracks allowed in your "Favorites" (Deezer limit is 10k). |
| `retention` | `DEEZER_RETENTION` | No | `0` | Hours to use cached 'source' data before fetching live. |
| `track_stats_refresh` | `DEEZER_TRACK_STATS_REFRESH` | No | `7` | Days before refreshing dynamic metadata like track rank. |

### Logic Hierarchy

The engine follows a specific priority when loading settings. This allows you to have a base configuration in a file while overriding specific keys (like tokens) via Docker secrets or environments.

1. **Environment Variables:** Checked first (highest priority).
2. **`config.yml`:** Checked if environment variables are not set.
3. **Hardcoded Defaults:** Used if neither of the above provides a value.

## 🐳 3. Installation: Docker (Recommended)

Docker is the easiest way to run the engine without managing Python dependencies manually.

### Option A: Docker Compose

Create a `docker-compose.yml` file. You can run in **Standard mode** (one-time sync) or **Cron mode** (scheduled).

```yaml
services:
    deezer-engine:
        image: kylemmkay/deezer-engine:latest
        container_name: deezer-engine
        volumes:
            - './data:/app/data' # Stores ./db, ./logs, and ./strategies.yml
        environment:
            - DEEZER_USER_ID="123456789"
            - DEEZER_ARL_TOKEN="YOUR_ARL_HERE"
            - DEEZER_LOG_LEVEL=INFO
            - TZ=UTC
            #- DEEZER_SCHEDULE="0 3 * * *" # Optional: Daily at 3 AM (Based off env TZ)
        command: run
```

> [!TIP]
> If you do not want to mount the `/app/data` directory, you can create and bind mount `./strategies.yml:/app/data/strategies.yml` instead.

### Execution Modes

| Mode | Command | Behavior |
| --- | --- | --- |
| **Run** | `command: run` / not included | (Default) Dynamically executes strategies: runs once and exits unless `DEEZER_SCHEDULE` defined. |
| **Cron** | `command: cron` | Container stays alive and runs on your `DEEZER_SCHEDULE`. |
| **Shell** | `command: shell` | Starts an interactive bash shell for debugging. |

### Docker Run (CLI)

For quick testing or one-off syncs without a Compose file:

```bash
# Standard One-time Run
docker run --rm \
  -v $(pwd)/data:/app/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  kylemmkay/deezer-engine:latest run

# Scheduled Cron (stays running)
docker run -d \
  --name deezer-cron \
  -e DEEZER_SCHEDULE="0 3 * * *" \
  -v $(pwd)/data:/app/data \
  kylemmkay/deezer-engine:latest cron
```

### 🏗️ Build & Development

If you are modifying the source code and want to test your changes within the Docker environment, follow these steps to build locally.

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
  -v $(pwd)/data:/app/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  deezer-engine:dev run
```

**3. Development Tips:**

* **Entrypoint:** The image uses `docker-entrypoint.sh`. If you modify this script, you **must** rebuild the image.

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
cp config.yml.template config.yml
cp strategies.yml.template strategies.yml
```

*Edit these files with your specific settings.*

3. **Run:**

```bash
python3 deezer-engine.py
```

**Next Step:** Once installed, head over to the [Strategy Configuration](https://www.google.com/search?q=Strategy-Configuration) page to define your first smart playlist.
