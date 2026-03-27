# Templates Scope

This folder contains both runtime onboarding templates and developer-facing validation templates.

## What Belongs Here

- Startup templates that users can copy for real runtime configuration.
- Reusable validation templates for parser and I/O behavior checks.
- Documentation for how each template set is intended to be used.

## Current Structure

- `startup/`
  - Comprehensive runtime starter templates for users who want more than the minimal defaults.
  - Minimal runtime defaults remain in `app/config.yml.template` and `app/strategies.yml.template`.
  - See: `templates/startup/README.md`.

- `validation/schema/`
  - Schema and unknown-key validation templates.
  - Focus: parser warnings, key suggestions, and structural validation.
  - See: `templates/validation/schema/README.md`.

- `validation/input_output/`
  - Input/output assertion templates for strategy execution validation.
  - Includes API-backed and deterministic offline variants.
  - See: `templates/validation/input_output/README.md`.

## Boundaries

- `app/*.template` is optimized for first-run user onboarding.
- `templates/startup/` is expanded runtime guidance.
- `templates/validation/` defines deterministic validation scenarios.
- `tests/` contains test harnesses and assertions.

## Maintenance Rules

- Keep runtime templates copy-paste friendly and valid YAML.
- Keep validation templates deterministic where possible for reproducible runs.
- If a new modifier is added to I/O validation coverage, update both:
  - `templates/validation/input_output/strategies.yml`
  - `templates/validation/input_output/strategies.offline.yml`
