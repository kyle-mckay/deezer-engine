# Prerequisites

- A Deezer account
- An ARL token
- (If building from source) Python 3.7 or higher

## Obtaining ARL token

To authenticate the engine, you need an `arl` token from your active Deezer session. Follow these steps for your specific browser:

1. Open your browser and go to [deezer.com](https://www.deezer.com/).
2. **Log in** to your account.
3. Press `F12` (or right-click anywhere and select **Inspect**) to open the **Developer Tools**.

### **Using Google Chrome / Brave / Edge**

4. Navigate to the **Application** tab at the top. (If you don't see it, click the `>>` arrows).
5. In the left sidebar, find the **Storage** section and expand **Cookies** and select `https://www.deezer.com`.
6. In the list of cookies, find the entry named **`arl`**.
7. Copy the text in the **Value** column. 

### **Using Mozilla Firefox**

4. Click on the **Storage** tab.
5. Expand **Cookies** in the left sidebar and select `https://www.deezer.com`.
6. In the list of cookies, find the entry named **`arl`**.
7. Double-click the **Value** field for that row and copy it.

> [!WARNING]
> **Keep this token secret.** Your ARL token is essentially your login session. Anyone with this token can access your Deezer account.

# Installation

## Configuration


Deezer Engine is configured either through `config.yml` file or docker environment variables. Environment variables take precedence over file values.

| Config Name | Environment Variable | Required | Type | Default | Description |
|---|---|---|---|---|---|
| `arl_token` | `DEEZER_ARL_TOKEN` | Yes | String | N/A | Your Deezer ARL authentication token. Required to authenticate with Deezer API. See [Obtaining ARL token](#obtaining-arl-token) section. |
| `user_id` | `DEEZER_USER_ID` | Yes | String | N/A | Your numeric Deezer user ID. Found in your profile URL: `https://www.deezer.com/us/profile/123456789` |
| `log_level` | `DEEZER_LOG_LEVEL` | No | String | `INFO` | Logging verbosity level. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `write_logs` | `DEEZER_WRITE_LOGS` | No | Boolean | `true` | Whether to write logs to file in `/app/data/logs/`. Accepts: `true`, `false`, `1`, `0`, `yes`, `no`. |
| `batch_size` | `DEEZER_BATCH_SIZE` | No | Integer | `50` | Tracks will be chunked and processed in groups not exceeding this value when adding or removing from playlists. |
| `print_banner` | `DEEZER_PRINT_BANNER` | No | Boolean | `true` | Whether to print the startup banner on launch. When run in docker mode, it prints on container start. When running locally it's printed on script execution while `log_level` is `INFO` or `DEBUG`. |

## Docker Compose

> Note: `config.yml` and `strategies.yml` can be bind mounted directly into the containers `/app/data/` folder.
> If you decide to bind mount these, ensure you create the file on your host first.

> If you do not provide a `strategies.yml` file, the container will generate a copy in the `/app/data` for you from the template.

```yml
services:
    deezer-engine:
        image: kylemmkay/deezer-engine:latest
        container_name: deezer-engine
        volumes:
            #- './strategies.yml:/app/data/strategies.yml' # If bind mounting file only
            - './data:/app/data' # Contains cache/ tmp/ and logs/ folders, will create strategies if not present
        environment:
            - DEEZER_USER_ID="123456789"
            - DEEZER_ARL_TOKEN="TOKEN_STRING_HERE"
            - DEEZER_LOG_LEVEL=INFO # Log level - DEBUG, INFO, WARNING, ERROR
```

### Command Modes

You can control how the script executes by specifying a `command:` option in Docker Compose or as a command argument in `docker run`. The supported modes are:

- **`run`** (default if `DEEZER_SCHEDULE` not set): Execute the engine once and exit. Useful for one-time operations or scheduled external triggers.
- **`cron`**: Run the engine on a forced schedule defined by the `DEEZER_SCHEDULE` environment variable (default: `0 3 * * *`). The container will stay running and execute the script at each scheduled interval.
- **`shell`**: Start an interactive bash shell for debugging or manual operations.

>[!WARNING]
>Cron behaviour is still under assessment

#### Docker Compose Example with Cron


```yml
services:
    deezer-engine:
        image: kylemmkay/deezer-engine:latest
        container_name: deezer-engine
        volumes:
            - './strategies.yml:/app/data/strategies.yml'
            - './data:/app/data'
        environment:
            - DEEZER_USER_ID="123456789"
            - DEEZER_ARL_TOKEN="TOKEN_STRING_HERE"
            - DEEZER_SCHEDULE="0 3 * * *" # Run daily at 3 AM UTC
            - TZ=UTC
        command: cron
```


## Source

1. Clone and open the repository.
```bash
git clone https://codeberg.org/kylemmkay/deezer-engine.git
cd deezer-engine
```

### Docker Run

2. Build the container.
```bash
# Build the image
docker build -t deezer-engine .
```

3.1 Run the container with Docker (single execution).
```bash
# Example with mounted config directory
docker run --rm \
  -v $(pwd)/config.yml:/app/config.yml \
  -v $(pwd)/strategies.yml:/app/strategies.yml \
  deezer-engine run
```

3.2 Run the container with cron scheduling.
```bash
# Run on a schedule (daily at 3 AM UTC)
docker run --rm \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="TOKEN_STRING_HERE" \
  -e DEEZER_SCHEDULE="0 3 * * *" \
  -e TZ=UTC \
  -v $(pwd)/strategies.yml:/app/data/strategies.yml \
  -v $(pwd)/data:/app/data \
  deezer-engine cron
```

3.3 Debug with interactive shell.
```bash
# Start an interactive shell for debugging
docker run --rm -it \
  -v $(pwd)/config.yml:/app/config.yml \
  -v $(pwd)/strategies.yml:/app/strategies.yml \
  deezer-engine shell
```

### Python

2. Set up a Python virtual environment (recommended).
```bash
python3 -m venv venv
source venv/bin/activate
```
> On Windows: `venv\Scripts\activate`

3. Install dependencies.
```bash
pip install -r requirements.txt
```

4. Copy the template files to create your local configuration.
```bash
cp config.yml.template config.yml
cp strategies.yml.template strategies.yml
```

5. Edit `config.yml` and `strategies.yml` with your settings. See [./Configuration.md](Configuration) for more details.

6. Run the engine.
```bash
python3 deezer-engine.py
```