# 🛠️ Development Guide

This page provides guidance for developers working on Deezer Engine, including building, running, and testing the project locally. It also highlights the location and purpose of developer-focused templates.

## 🏗️ Build & Development

If you are modifying the source code and want to test your changes within the Docker environment, follow these steps to build locally.

> [!NOTE]
> This assumes you have already cloned the repository and are within the working directory.

### 1. Build the image
From the root of the repository:

```bash
docker build -t deezer-engine:dev .
```

### 2. Run your dev build
Use your local image tag to verify changes:

```bash
docker run --rm \
  -v $(pwd)/data:/deezer_engine/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  deezer-engine:dev run
```

### 3. Development Tips

* **Entrypoint:** The image uses `docker-entrypoint.sh` as a thin wrapper that delegates to `python -m deezer_engine` modes (`run`, `cron`, `pytest`, `shell`). If you modify this script, you **must** rebuild the image.

## 🧩 Developer Templates

Template scope, ownership boundaries, and maintenance rules are documented in [`templates/README.md`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/README.md).

From there, drill down.

## 🧪 Testing

Run tests from the repository root:

```bash
pytest
```

You can also run tests through the Deezer Engine CLI router:

```bash
cd app
python3 -m deezer_engine pytest -v -s tests/test_main_entrypoint.py
```

To run tests through the Docker image during development:

```bash
# Run a specific test module
docker run --rm -it \
  deezer-engine:dev pytest -v -s tests/test_main_entrypoint.py

# Run a specific test node
docker run --rm -it \
  deezer-engine:dev pytest -v -s tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors
```

Path normalization notes for pytest mode:

1. Relative `tests/...` targets are resolved to the correct project layout (`app/tests/...`) when required.
2. Docker-style absolute paths such as `/deezer_engine/app/tests/...` are remapped to local app-relative paths when they exist.
3. Absolute paths outside the Docker app root are left unchanged.

For test scope, per-module intent, and Forgejo pytest pipeline references, see [`app/tests/README.md`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/app/tests/README.md).
