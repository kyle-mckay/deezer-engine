
### 🧪 Schema Validation Templates

This folder contains reusable templates for validating the structure and schema of configuration and strategy files. These are intended for development and testing of config/strategy parsing, unknown key warnings, and schema enforcement.

#### Developer Workflow

From the repository root, copy these templates into active runtime files before running the engine:

```bash
cp templates/validation/schema/config.yml config.yml
cp templates/validation/schema/strategies.yml strategies.yml
python3 deezer-engine.py run
```

Expected behavior for these templates:
- The engine should continue running, but emit warning logs for intentional unknown/typo keys.
- Placeholders like `PASTE_ARL_TOKEN_HERE` and `REPLACE_*` must be replaced before running API-backed sources.
- These files validate parser and warning paths, not playlist quality.

#### Template Overview

- **config.yml**
  - Checks for unknown top-level config keys.
  - Checks for unknown keys inside the `config` section.
  - Includes intentional typos to validate warning and suggestion logic.

- **strategies.yml**
  - Checks for unknown top-level strategy keys.
  - Checks for duplicate source-type warnings.
  - Checks for nested unknown-key warnings in sources, modifiers, and destinations.
  - Includes broad coverage for supported source/modifier/destination types.

> [!TIP]
> These templates are for schema/structure validation only. 

---

#### Notes

- These templates intentionally include typo keys to trigger warning and suggestion paths.
- Do not use these templates in production—remove all intentional typo fields from your live `config.yml` and `strategies.yml`.
- For deterministic offline I/O validation scenarios, use `templates/validation/input_output/strategies.offline.yml` with `tests/fixtures/album` instead of these schema templates.
