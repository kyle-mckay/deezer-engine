# utils/collections

Use this folder for collection semantics and orchestration, not low-level DB persistence.

## Put a module here when
- It resolves or normalizes collection naming/identity.
- It coordinates collection cache flow across layers (fetch callback, fallback policy, integrity checks).
- It represents collection-focused behavior at the strategy/runtime level.

## Do not put it here when
- It is mainly SQL query/update logic for `collections` tables (`utils/db`).

## Quick check
If the function's core job is "what collection does this represent?" or "how should collection cache flow run?" -> `utils/collections`.
If the core job is "execute SQL for collections" -> `utils/db`.
