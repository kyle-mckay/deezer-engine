# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir():
    """Get the data directory path, using app/data in containers and project root otherwise."""
    if os.getenv('CONTAINERIZED', 'false').lower() == 'true':
        return Path('/app/data')
    else:
        return PROJECT_ROOT


def get_cache_dir():
    """Get the cache directory path."""
    return get_data_dir() / 'cache'


def get_logs_dir():
    """Get the logs directory path."""
    return get_data_dir() / 'logs'