
### 🧪 Schema Validation Templates

This folder contains reusable templates for validating the structure and schema of configuration and strategy files. These are intended for development and testing of config/strategy parsing, unknown key warnings, and schema enforcement.

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
