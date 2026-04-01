# utils/blocklist

This folder is reserved for blocklist-specific domain modules if blocklist behavior is split out again.

## Put a module here when
- It represents high-level blocklist policy/rules as a distinct domain package.
- It does not primarily exist to run SQL CRUD operations.

## Do not put it here when
- It is mostly database reads/writes for blocklist tables (`utils/db/blocklist.py`).

## Current note
Active blocklist persistence helpers currently live under `utils/db/blocklist.py`.
