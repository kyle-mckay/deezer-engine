# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import yaml
from utils.infrastructure.paths import get_data_dir


def get_bootstrap_logging_settings():
    """
    Resolve logging settings early, before full config loading.
    """
    log_level = os.getenv("DEEZER_LOG_LEVEL")
    write_logs_env = os.getenv("DEEZER_WRITE_LOGS")

    # Prioritize environment variables
    if log_level is not None or write_logs_env is not None:
        resolved_level = (log_level or "INFO").upper()
        resolved_write_logs = True if write_logs_env is None else write_logs_env.lower() in ('true', '1', 'yes', 'on')
        return resolved_level, resolved_write_logs

    # Fall back to config.yml values
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            cfg = config.get('config', {})
            resolved_level = str(cfg.get('log_level', 'INFO')).upper()
            resolved_write_logs = cfg.get('write_logs', True)
            if isinstance(resolved_write_logs, str):
                resolved_write_logs = resolved_write_logs.lower() in ('true', '1', 'yes', 'on')
            return resolved_level, bool(resolved_write_logs)
    except Exception:
        return "INFO", True