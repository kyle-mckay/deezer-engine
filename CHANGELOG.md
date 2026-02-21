# Changelog

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
