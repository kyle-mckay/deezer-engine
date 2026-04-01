# Changelog

## v0.14.2 - 2026-04-01

### Maintenance

- chore: utility sprawl (progress in #86) - chunk 8 (#134) (@kylemmkay)
- chore: utility sprawl chunk 7 - deezer_auth (progress #86) (#133) (@kylemmkay)
- chore: deal with utility sprawl - chunk 6 db_manager (progress in #86) (#132) (@kylemmkay)
- chore: clean up version bump logic (closes #101) (#131) (@kylemmkay)
- maint: use the paginated fetch outputs without stripping data for metadata collection (progress in #95) (#130) (@kylemmkay)
- chore: document delegate and mark unit tests (#128) (@kylemmkay)
- Merge branch 'template-upkeep' (@kylemmkay)
- maint: migrate entrypoint logic to python and support cli entry (closes #123) (#126) (@kylemmkay)

## v0.14.1 - 2026-03-27

### Maintenance

- maint: add environment variable to run before starting schedule (#124) (@kylemmkay)

## v0.14.0 - 2026-03-27

### Breaking

- breaking: standardize paths in project (closes #87) (#120) (@kylemmkay)

### Enhancements

- enhance: implement unit tests (#114) (@kylemmkay)
- enhance: add restore functionality if the database migration fails (#113) (@kylemmkay)

### Fixes
- fix: validation mode in config and correct log module in parsing (#110) (@kylemmkay)
- fix: re-enable container pytest (closes #118) (#121) (@kylemmkay)

### Maintenance

- chore: utility sprawl chunk 5 - migrate blocklist behaviour to use wrapper within db_manager (#86) (#112) (@kylemmkay)
- chore: utility sprawl cleanup chunk 4 - database and migrations (progress towards #86) (#110) (@kylemmkay)

## v0.13.0 - 2026-03-20

### Enhancements

- enhance: streamline get_ functions to perform other tasks if on cooldown (closes #85) (#103) (@kylemmkay)
- feat: add global variable for `max_tries` for `get_tracks` and `get_albums` (closes #84) (#99) (@kylemmkay)
- enhance: persist configuration in memory instead of file reads (#105) (@kylemmkay)
- enhance: add strategy and config deduplication (#105) (@kylemmkay)
- enhance: add deeper verification to strategy key validation (closes #106) (#105) (@kylemmkay)
- feat: IO verification checks for source, modifier, and destination stages (closes #92) (#85) (@kylemmkay)

### Fixes

- fix: eta not showing until a successfull get for track/album metadata (closes #90) (#99) (@kylemmkay)

### Maintenance

- chore: refactor utils chunks 1–3 - infrastructure, cache, config split and validation (progress in #86) (#105) (@kylemmkay)
- chore: cleanup and remove the manual `>>> START` / `<<< END` logs (closes #89) (#98) (@kylemmkay)
- chore: switch to lazy metadata collection and in-memory pipeline (closes #96) (#105) (@kylemmkay)

## v0.12.0 - 2026-03-17

### Breaking Changes

- breaking: overhaul database init and migration process (#93) (@kylemmkay)
    - Databases from prior migration epochs are no longer supported and must be deleted to allow the app to recreate them with the new baseline schema.
    - The migration history has been reset with a new baseline, so all existing databases will be rejected on startup until they are deleted.

### Enhancements

- feat: add genre collection during metadata enrichment (closes #18) (#82) (@kylemmkay)
- feat: add failure tracking logic for tracks/ablums removed from deezer (#82) (@kylemmkay)
- enhance: add table initialization to support album and genre tables and table migration/update logic (#82) (@kylemmkay)

### Fixes

- fix: finish implementation of blocklisting (closes #91) (#93) (@kylemmkay)
- fix: new log format expected in container verification (@kylemmkay)
- fix: missed some data conversions with the introduction of destination chache logic (@kylemmkay)
- fix: cache degrading due to db scoping not defined properly (#82) (@kylemmkay)

### Maintenance

- chore: Update logging to cache format instances and include call-site context for non-info logs (#88) (@kylemmkay)

## v0.11.0 - 2026-02-23

### Enhancements

- enhance: improve performance for fetching and change API limiting behaviour. (#78) (@kylemmkay)
-  	enhance: allow destination playlist to pull from collection cache (closes #73) (#80)

### Fixes

- fix: when saving a destination the final tracklist is cached (#80) (@kylemmkay)
- fix: smart lists not saving / fetching collection (#69) (@kylemmkay)

## v0.10.0 - 2026-02-21

### Enhancements

- feat: allow the use of a local file as a source for tracks (#72) (@kylemmkay)

### Fixes

- fix: add sigint support for script and container (#70) (@kylemmkay)

### Maintenance

- chore: correct source file description (@kylemmkay)

## v0.9.2 - 2026-01-27

### Fixes

- fix: scheduler no longer relies on cron service (closes #33) (#68) (@kylemmkay)

### Maintenance

- chore: update badge logo (@kylemmkay)
- chore: modify docker build to test and only push to latest on release (#67) (@kylemmkay)

## v0.9.1 - 2026-01-24

### Fixes

- fix: move shebang back to top of entrypoint (@kylemmkay)

## v0.9.0 - 2026-01-23

### Enhancements

- feat: add file destination (progress towards #25) (@kylemmkay)
- feat: add history source (closes #65) (#66) (@kylemmkay)

### Fixes

- fix: cache check ignoring retention, add placeholder for history (@kylemmkay)
- fix: typo and wrong variable for count (@kylemmkay)

### Maintenance

- chore: reduce-log-noise (closes #56) (#63) (@kylemmkay)

## v0.8.0 - 2026-01-20

### Enhancements

- feat: implement SQLLite db (completes #14) (#54) (@kylemmkay)
- feat: implement db refresh for dynamic fields (#14) (#55) (@kylemmkay)

### Fixes

- fix: type mismatch between list and dict (closes #58) (#55) (@kylemmkay)
- fix: exclude now checks cache (closes #57) (closes #61) (#55) (@kylemmkay)

### Maintenance

- chore: remove references to old cache system (#55) (@kylemmkay)
- chore: enhance debug logging (#55) (@kylemmkay)
- chore: add new strategies expected testing against (#55) (@kylemmkay)


## v0.7.0 - 2026-01-19

### Enhancements

- feat: add artist source (#53) (@kylemmkay)
- feat: add album source (progress in #2) (#52) (@kylemmkay)
- feat: add retention to config variables (cloeses #5) (#51) (@kylemmkay)
- feat: enhance destination to allow for future multiple destinations and define limit warnings (closes #6) #47 (@kylemmkay)
- feat: allow modifiers to funciton only to specific source (closes #13) (#46) (@kylemmkay)

### Fixes

- fix: update checker migrated to codeberg (#49) (@kylemmkay)
- fix: added the limiters enforcing destination caps (#48) (@kylemmkay)

## v0.6.0 - 2026-01-19

### Enhancements

- feat: add filter modifier (closes #39) (#45) (@kylemmkay)
- feat :add limit modifier (closes #10) (#44) (@kylemmkay)

## v0.5.1 - 2026-01-18

### Fixes

- fix: sort by rank was being treated as string (closes #42) (#43) (@kylemmkay)

## v0.5.0 - 2026-01-18

### Enhancements

- feat: implement shuffle modifier (closes #12) (#41) (@kylemmkay)

## v0.4.0 - 2026-01-18

### Enhancements

- feat: implement sort modifier (#9) (@kylemmkay)
- feat: collecting all track data and refactor functions' (#35) (@kylemmkay)

### Maintenance

- docs: update to codeberg link

## v0.3.0 - 2026-01-13

### Enhancement

- feat: added basic docker support

## v0.2.0 - 2026-01-12

Added source for smart track playlists (Discovery, Inspired by, new releases)

## v0.1.0 - 2026-01-10

Inital version that can pull and add to playlists
