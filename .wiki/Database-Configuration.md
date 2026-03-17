# Database Configuration

## Tables

Deezer Engine uses SQLite to maintain a record/cache of the tracks you are building playlists from. By performing a one-time (mass) fetch of metadata, it take time to initialy set up, however once the metadata is captured the playlist operations will be significantly smoother. 

Pipleline Order of Operations:

1. For an existin table, a metadata fetch for volatile fields will be performed. 
2. Source's are fetched 
  * Track ID's (only) will be obtained for each source being pulled in the current pipeline.
  * Once the tracks are downloaded, they will be appended to the collections table, and (if not present) added to the tracks table.
  * Track ID's for the strategy will be kept in memory for remaining operations.
3. Table metadata is updated
  * The table will then be queried for new tracks and fetch **all** metadata related to it
  * This will populate the artist and album tables as well
4. Modifiers will then reference the current pipleline memory and pull the needed metadata from the table to match up with the tracks and modify as needed.
5. Track id's are fed as normal to the destination pipeline and uploaded to deezer

### Tracks

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `id` (primary) | The track's Deezer id | int | `false` |
| `readable` | true if the track is readable in the player for the current user | boolean | `true` |
| `title` | The track's fulltitle | string | `false` |
| `title_short` | The track's short title | string | `false` |
| `title_version` | The track version | string | `false` |
| `unseen` | The track unseen status | boolean | `true` |
| `isrc` | The track isrc | string | `false` |
| `link` | The url of the track on Deezer | url | `false` |
| `share` | The share link of the track on Deezer | url | `false` |
| `duration` | The track's duration in seconds | int | `false` |
| `track_position` | The position of the track in its album | int | `false` |
| `disk_number` | The track's album's disk number | int | `false` |
| `rank` | The track's Deezer rank | int | `true` |
| `release_date` ? | The track's release date | date | `false` |
| `explicit_lyrics` | Whether the track contains explicit lyrics | boolean | `false` |
| `explicit_content_lyrics` | The explicit content lyrics values (0:Not Explicit; 1:Explicit; 2:Unknown; 3:Edited; 6:No Advice Available) | int | `false` |
| `explicit_content_cover` | The explicit cover value (0:Not Explicit; 1:Explicit; 2:Unknown; 3:Edited; 6:No Advice Available) | int | `false` |
| `preview` | The url of track's preview file. This file contains the first 30 seconds of the track | url | `false` |
| `bpm` | Beats per minute | float | `true` |
| `gain` | Signal strength | float | `true` |
| `available_countries` | List of countries where the track is available | list | `true` |
| `alternative` | Return an alternative readable track if the current track is not readable | track | `true` |
| `contributors` | Return a list of contributors on the track | list | `false` |
| `md5_image` | | string | `false` |
| `track_token` | The track token for media service | string | `false` |
| `artist_id` (external) | The track artists id | int | `false` |
| `album_id` (external) | The albums id | int | `false` |
| `date_cached` | The date the data was last cached | date | `true` |

### Artist

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `id` (primary)| The artist's Deezer id | int | `false` |
| `name` | The artist's name | string | `true` |
| `link` | The url of the artist on Deezer | url | `false` |
| `share` | The share link of the artist on Deezer | url | `false` |
| `picture` | The url of the artist picture. Add 'size' parameter to the url to change size. Can be 'small', 'medium', 'big', 'xl' | url | `false` |
| `picture_small` | The url of the artist picture in size small. | url | `false` |
| `picture_medium` | The url of the artist picture in size medium. | url | `false` |
| `picture_big` | The url of the artist picture in size big. | url | `false` |
| `picture_xl` | The url of the artist picture in size xl. | url | `false` |
| `nb_album` | The number of artist's albums | int | `true` |
| `nb_fan` | The number of artist's fans | int | `true` |
| `radio` | true if the artist has a smartradio | boolean | `true` |
| `tracklist` | API Link to the top of this artist | url | `false` |
| `date_cached` | The date the data was last cached | date | `true` |


### Album

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `id` (primary) | The Deezer album id | int | `false` |
| `title` | The album title | string | `false` |
| `upc` | The album UPC | string | `false` |
| `link` | The url of the album on Deezer | url | `false` |
| `share` | The share link of the album on Deezer | url | `false` |
| `cover` | The url of the album's cover. Add 'size' parameter to the url to change size. Can be 'small', 'medium', 'big', 'xl' | url | `false` |
| `cover_small` | The url of the album's cover in size small. | url | `false` |
| `cover_medium` | The url of the album's cover in size medium. | url | `false` |
| `cover_big` | The url of the album's cover in size big. | url | `false` |
| `cover_xl` | The url of the album's cover in size xl. | url | `false` |
| `md5_image` | The album cover hash | string | `false` |
| `genre_id` (external) | The album's primary genre id | int | `false` |
| `label` | The album's label name | string | `false` |
| `nb_tracks` | The number of tracks | int | `false` |
| `duration` | The album's duration (seconds) | int | `false` |
| `fans` | The number of album's Fans | int | `true` |
| `release_date` | The album's release date | date | `false` |
| `record_type` | The record type of the album (EP / ALBUM / etc..) | string | `false` |
| `available` | Whether the album is available | boolean | `true` |
| `tracklist` | API Link to the tracklist of this album | url | `false` |
| `explicit_lyrics` | Whether the album contains explicit lyrics | boolean | `false` |
| `explicit_content_lyrics` | The explicit content lyrics values (0:Not Explicit; 1:Explicit; 2:Unknown; 3:Edited; 4:Partially Explicit (Album "lyrics" only); 5:Partially Unknown (Album "lyrics" only); 6:No Advice Available; 7:Partially No Advice Available (Album "lyrics" only)) | int | `false` |
| `explicit_content_cover` | The explicit cover values (0:Not Explicit; 1:Explicit; 2:Unknown; 3:Edited; 4:Partially Explicit (Album "lyrics" only); 5:Partially Unknown (Album "lyrics" only); 6:No Advice Available; 7:Partially No Advice Available (Album "lyrics" only)) | int | `false` |
| `contributors` | Return a list of contributors on the album | list | `false` |
| `artist_id` (external) | The artists id | int | `false` |
| `artist_name` | The artists name | string | `false` |
| `date_cached` | The date the data was last cached | date | `true` |

### Genres

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `id` (primary) | The genre id | int | `false` |
| `name` | The genre name | string | `false` |

### Album_Genres

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `album_id` (external) | The album id | int | `false` |
| `genre_id` (external) | The genre id | int | `false` |

### Track_Genres

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `track_id` (external) | The track id | int | `false` |
| `genre_id` (external) | The genre id | int | `false` |

### Schema_Version

| Name | Description | Type | Gets refresh? |
| --- | --- | --- | --- |
| `id` (primary) | The schema version row id | int | `false` |
| `migration_name` | The applied migration name | string | `false` |
| `applied_at` | The migration timestamp | date | `false` |
| `script_version` | The script version when the migration was applied | string | `false` |

### Collections (Cached Source Contents)

| Name | Description | Type | Gets Refresh? |
| --- | --- | --- | --- |
| `id` | The tables primary key (creates its own) | int | `true` |
| `track_id` | The ID of the track which source it has been mapped to. One source per column, can contain the same ID in this column. | int | `true` |
| `source_name` | The name of the source that contained this track | string | `true` |
| `date_cached` | The date the data was last cached | date | `true` |

### Blocklist

The blocklist system tracks metadata fetch failures for tracks and albums. When the Deezer API fails to return metadata for an entity, the failure is recorded and the entity is marked as blocklisted to prevent repeated failed fetch attempts.

| Name | Description | Type |
| --- | --- | --- |
| `id` (primary) | The blocklist entry's unique identifier | int |
| `entity_type` | The type of entity: `'track'` or `'album'` | text |
| `entity_id` | The primary key ID of the track or album being tracked | int |
| `total_errors` | Lifetime count of all metadata fetch failures for this entity | int |
| `streak_errors` | Count of consecutive fetch failures since the last successful metadata cache. Resets to 1 when metadata is successfully cached after a failure. | int |
| `last_error_code` | The most recent API/transport error code or type (e.g., `"404"`, `"ConnectionError"`) | text |
| `last_failed_at` | ISO 8601 timestamp of the most recent metadata fetch failure | text |
| `blocklist_applied_at` | ISO 8601 timestamp when blocklisting became active for this entity. Used by the expiry mechanism to determine when to release the block. | text |

#### Tracks & Albums Blocklist Columns

Both `tracks` and `albums` tables include blocklist-related columns:

| Column | Description | Type |
| --- | --- | --- |
| `blacklist_id` | Foreign key reference to the `blocklist` table's `id`. Links the entity to its failure tracking record. | int |
| `blocklisted` | Boolean flag (0 = not blocklisted, 1 = blocklisted). Prevents the engine from attempting metadata enrichment for blocklisted entities. | int |