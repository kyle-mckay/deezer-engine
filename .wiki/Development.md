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
  -v $(pwd)/data:/app/data \
  -e DEEZER_USER_ID="123456789" \
  -e DEEZER_ARL_TOKEN="YOUR_TOKEN" \
  deezer-engine:dev run
```

### 3. Development Tips

* **Entrypoint:** The image uses `docker-entrypoint.sh`. If you modify this script, you **must** rebuild the image.

## 🧩 Developer Templates

Reusable templates for configuration and strategy validation are located in the `templates/validation/` directory. These include:

- **Schema validation templates:** For checking config/strategy file structure and keys. Located in [`templates/validation/schema`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/validation/schema).
- **IO validation templates:** For testing input/output behavior of strategies against expected results. Located in [`templates/validation/input_output`](https://codeberg.org/kylemmkay/deezer-engine/src/branch/main/templates/validation/input_output).

See each folders `templates/*/README.md` for more details and usage instructions.
