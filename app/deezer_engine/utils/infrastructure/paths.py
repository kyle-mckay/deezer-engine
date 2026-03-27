# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def get_data_dir():
    """Get the data directory path."""
    return PROJECT_ROOT / 'data'


def get_cache_dir():
    """Get the cache directory path."""
    return get_data_dir() / 'cache'


def get_logs_dir():
    """Get the logs directory path."""
    return get_data_dir() / 'logs'