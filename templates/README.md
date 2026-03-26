# Templates Scope

This folder contains developer-facing template files used to validate configuration and strategy behavior.

## What Belongs Here

- Reusable validation templates that can be copied into runtime files for local checks.
- Deterministic scenario definitions used to validate parser behavior and I/O assertions.
- Documentation for how each template set is intended to be used.

## Current Structure

- `validation/schema/`
  - Schema and unknown-key validation templates.
  - Focus: parser warnings, key suggestions, and structural validation.
  - See: `templates/validation/schema/README.md`.

- `validation/input_output/`
  - Input/output assertion templates for strategy execution validation.
  - Includes API-backed and deterministic offline variants.
  - See: `templates/validation/input_output/README.md`.

## Boundaries

- `templates/` defines scenarios and expected behavior shapes.
- `tests/` contains test harnesses and assertions.
- Some templates are intentionally test-coupled (for example, the offline I/O template consumed by pytest).

## Maintenance Rules

- Keep templates deterministic where possible for reproducible validation runs.
- If a new modifier is added to I/O validation coverage, update both:
  - `templates/validation/input_output/strategies.yml`
  - `templates/validation/input_output/strategies.offline.yml`
