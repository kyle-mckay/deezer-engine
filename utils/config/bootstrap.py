# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from .parsing import load_config_with_env_overrides


def get_bootstrap_logging_settings():
    """
    Resolve logging settings early, before full config loading.
    """
    try:
        config = load_config_with_env_overrides(force_reload=True)
        cfg = config.get('config', {})
        resolved_level = str(cfg.get('log_level', 'INFO')).upper()
        resolved_write_logs = cfg.get('write_logs', True)
        if isinstance(resolved_write_logs, str):
            resolved_write_logs = resolved_write_logs.lower() in ('true', '1', 'yes', 'on')
        return resolved_level, bool(resolved_write_logs)
    except Exception:
        return "INFO", True
