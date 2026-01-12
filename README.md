# Deezer Engine (Smart Playlists)

>Please note that this repository was built with AI 🤖 assistance.

Inspired by [Goofy](https://github.com/Chimildic/goofy) and [Playlist Machinery / Smarter Playlists](http://www.playlistmachinery.com/), Deezer Engine is a Python script that allows you to create and maintain smart playlists within Deezer using a declarative configuration approach.

## Overview

This project implements a pipeline-based system for managing playlists. You define strategies in a YAML configuration file that specify:
- Which sources to pull tracks from (your library, playlists, discovery mixes, etc.)
- How to transform the track list (exclude certain songs, remove duplicates, etc.)
- Where to send the final results (create or update playlists)

The engine handles caching, API interactions, and batch operations for you.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Deezer account
- An ARL token (authentication key) from your Deezer session

### Installation

1. Clone the repository.
```bash
git clone https://github.com/kyle-mckay/deezer-engine.git
cd deezer-engine
```

2. Set up a Python virtual environment (recommended).
```bash
python3 -m venv venv
source venv/bin/activate
```

> On Windows: venv\Scripts\activate

3. Install dependencies.
```bash
pip install -r requirements.txt
```

### Configuration

1. Copy the template files to create your local configuration.
```bash
cp config.yml.template config.yml
cp strategies.yml.template strategies.yml
```

2. Edit `config.yml` with your Deezer credentials.
   - Get your ARL token from your Deezer browser session (see the template for instructions).
   - Add your numeric user ID from your Deezer profile URL.

3. Edit `strategies.yml` to define your smart playlists.
   - Each strategy specifies sources, modifiers, and a destination.
   - See the [strategies.yml.template](strategies.yml.template) and [strategies/README.md](strategies/README.md) for example configurations.

### Running the Engine

```bash
python3 deezer-engine.py
```

The engine will process each strategy defined in `strategies.yml`, updating your playlists accordingly.

![ExampleImageTBD]()

## Development

If you make changes to the dependencies, update the requirements file.
```bash
pip freeze > requirements.txt
```
