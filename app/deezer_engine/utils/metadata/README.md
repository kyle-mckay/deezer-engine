# utils/metadata

Use this folder for track/album/artist/genre metadata transformation and enrichment flow.

## Put a module here when
- It flattens/coerces Deezer entity payloads into app metadata shapes.
- It orchestrates metadata enrichment steps and sequencing.
- It applies metadata safeguards/consistency rules tied to entity meaning.
- It contains metadata-oriented queries selecting what to enrich next.

## Do not put it here when
- It is generic SQL plumbing with no metadata semantics (`utils/db`).
- It is network transport/auth/retry policy (`utils/api`).
- It is generic infrastructure utility (`utils/infrastructure`).

## Quick check
If the function's main question is "what should this entity metadata look like or how should it be enriched?" put it here.
