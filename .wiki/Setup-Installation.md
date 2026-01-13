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

## Docker Compose

```yml
services:
    deezer-engine:
        image: kylemmkay/deezer-engine:latest
        container_name: deezer-engine
        volumes:
            - './strategies.yml:/app/data/strategies.yml'
            #- './config.yml:/app/data/config.yml' # Can use bind mount instead of environment variables
            - './data:/app/data' # Contains cache/ tmp/ and logs/ folders
        environment:
            - DEEZER_USER_ID="123456789" # https://www.deezer.com/us/profile/123456789 <- these numbers
            - DEEZER_ARL_TOKEN="TOKEN_STRING_HERE"
            - DEEZER_LOG_LEVEL=INFO # Log level - DEBUG, INFO, WARNING, ERROR (default: INFO)
            # - DEEZER_BATCH_SIZE=50 # The batch size for performing add/remove operations on playlists (default: 50)
            #- DEEZER_WRITE_LOGS: Write logs to file - true/false (default: true)
            #- DEEZER_SCHEDULE="0 3 * * *" # Cron schedule expression (default: "0 3 * * *" for daily at 3 AM UTC)
            #- TZ=UTC # Timezone for cron (e.g., "ETC/UTC")
```


## Source

1. Clone and open the repository.
```bash
git clone https://github.com/kyle-mckay/deezer-engine.git
cd deezer-engine
```

### Docker Run

2. Build the container.
```bash
# Build the image
docker build -t deezer-engine .
```

3.1 Run the container with Docker.
```bash
# Example with mounted config directory
docker run --rm \
  -v $(pwd)/config.yml:/app/config.yml \
  -v $(pwd)/strategies.yml:/app/strategies.yml \
  deezer-engine
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