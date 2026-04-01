# utils/config

Use this folder for runtime config loading, parsing, normalization, and validation.

## Put a module here when
- It reads/parses YAML or environment overrides.
- It validates config/strategy schema and constraints.
- It exposes config snapshots or bootstrap config values.

## Do not put it here when
- It is generic infrastructure that happens to be called during startup (`utils/infrastructure`).
- It performs database work (`utils/db`) or external API fetching (`utils/api`).

## Quick check
If the function answers "what config value should the app use and is it valid?" it belongs here.
