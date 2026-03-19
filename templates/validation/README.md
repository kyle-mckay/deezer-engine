# Validation Templates

This folder stores reusable templates for configuration and strategy validation checks.

## Folder Layout

- `config.validation.template.yml`: Template that validates config parsing behavior.
- `strategies.validation.template.yml`: Template that validates strategy schema behavior.

## Templates

- `config.validation.template.yml`
  - Verifies unknown top-level config keys.
  - Verifies unknown keys inside the `config` section.
  - Includes typo examples to validate suggestion messages.

- `strategies.validation.template.yml`
  - Verifies unknown strategy top-level keys.
  - Verifies duplicate source-type warnings.
  - Verifies nested unknown-key warnings in sources/modifiers/destinations.
  - Includes full coverage examples for supported source/modifier/destination types.

## Usage

1. Copy the desired templates into runtime files:

```bash
cp templates/validation/config.validation.template.yml config.yml
cp templates/validation/strategies.validation.template.yml strategies.yml
```

2. Replace placeholders before running:

- `PASTE_ARL_TOKEN_HERE`
- `PASTE_NUMERIC_USER_ID_HERE`
- `REPLACE_PLAYLIST_ID`
- `REPLACE_SOURCE_PLAYLIST_ID`
- `REPLACE_ALBUM_ID`
- `REPLACE_ARTIST_ID`

3. Run the engine and inspect logs for warning behavior.

## Notes

- These templates intentionally include typo keys to trigger warning paths.
- Keep production `config.yml` and `strategies.yml` free of intentional typo fields.
