# Copyright (C) 2026 kylemmkay
# Source: https://codeberg.org/kylemmkay/deezer-engine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import os
from pathlib import Path

def get_data_dir():
    """Get the data directory path, using app/data in containers, current dir otherwise."""
    if os.getenv('CONTAINERIZED', 'false').lower() == 'true':
        return Path('/app/data')
    else:
        return Path('.')

def get_cache_dir():
    """Get the cache directory path."""
    return get_data_dir() / 'cache'

def get_tmp_dir():
    """Get the tmp directory path."""
    return get_data_dir() / 'tmp'

def get_logs_dir():
    """Get the logs directory path."""
    return get_data_dir() / 'logs'