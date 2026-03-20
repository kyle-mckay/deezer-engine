# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from difflib import get_close_matches

IO_VALIDATION_KEYS = {
    'i',
    'o',
    'validation_mode',
}

STRATEGY_TOP_LEVEL_KEYS = {
    'name',
    'source',
    'modifiers',
    'destination',
}

SOURCE_BASE_KEYS = {
    'type',
    'retention',
    'modifiers',
    *IO_VALIDATION_KEYS,
}

SOURCE_TYPE_KEYS = {
    'album': {'id', 'source'},
    'artist': {'id'},
    'favorites': set(),
    'file': {'filename', 'dir', 'format', 'name'},
    'history': {'lookback', 'limit'},
    'playlist': {'id'},
    'smarttracklist': {'name'},
}

MODIFIER_BASE_KEYS = {
    'type',
    *IO_VALIDATION_KEYS,
}

MODIFIER_TYPE_KEYS = {
    'dedupe': set(),
    'exclude': {'source'},
    'filter': {'field', 'operator', 'value'},
    'limit': {'count', 'order'},
    'shuffle': {'order'},
    'sort': {'field', 'order'},
}

DESTINATION_BASE_KEYS = {
    'type',
    *IO_VALIDATION_KEYS,
}

DESTINATION_TYPE_KEYS = {
    'file': {'dir', 'filename', 'name', 'extension', 'retention'},
    'playlist': {'id', 'order', 'retention'},
}

CONFIG_ROOT_KEYS = {
    'config',
}

CONFIG_SECTION_KEYS = {
    'user_id',
    'arl_token',
    'chunk_size',
    'api_batch_size',
    'rate_limit',
    'max_retries',
    'log_level',
    'write_logs',
    'print_banner',
    'playlist_cap',
    'favorites_cap',
    'retention',
    'file_retention',
    'track_stats_refresh',
    'album_stats_refresh',
    'blocklist_expiry_days',
    'log_interval',
    'history_lookback',
    'history_limit',
    'validation_mode',
}


def get_allowed_source_keys(source_type):
    stype = str(source_type or 'unknown').lower()
    return SOURCE_BASE_KEYS | SOURCE_TYPE_KEYS.get(stype, set())


def get_allowed_modifier_keys(modifier_type):
    mtype = str(modifier_type or 'unknown').lower()
    return MODIFIER_BASE_KEYS | MODIFIER_TYPE_KEYS.get(mtype, set())


def get_allowed_destination_keys(destination_type):
    dtype = str(destination_type or 'unknown').lower()
    return DESTINATION_BASE_KEYS | DESTINATION_TYPE_KEYS.get(dtype, set())


def get_unknown_keys(obj, allowed_keys):
    if not isinstance(obj, dict):
        return []
    return sorted(set(obj.keys()) - set(allowed_keys))


def format_key_with_suggestion(key_name, allowed_keys):
    best_match = get_close_matches(key_name, sorted(allowed_keys), n=1, cutoff=0.75)
    if best_match:
        return f"'{key_name}' (did you mean '{best_match[0]}'?)"
    return f"'{key_name}'"


def format_unknown_key_list(unknown_keys, allowed_keys):
    if not unknown_keys:
        return ''
    return ', '.join(format_key_with_suggestion(key, allowed_keys) for key in unknown_keys)
