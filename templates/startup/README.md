# Startup Templates

These files are for runtime onboarding templates (distinct from validation templates under templates/validation).

## Files

- `config.comprehensive.yml`
  - Advanced, grouped reference config with common and optional defaults.
- `strategies.comprehensive.yml`
  - Expanded strategy examples for users who want more than the default starter file.

## Recommended Flow

1. Start with the minimal runtime templates:
   - `app/config.yml.template`
   - `app/strategies.yml.template`
2. If you need more options and examples, copy from this folder.

## Notes

- Keep these templates valid and copy-paste friendly.
- Runtime defaults should remain beginner-focused in `app/*.template`.
- Validation scenarios belong in `templates/validation/` and should stay deterministic for tests.
