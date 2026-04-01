import logging

import pytest

from utils.db.connection import get_connection, initialize_all
from utils.db.cache import (
    mark_fully_populated_albums_as_cached,
    mark_fully_populated_artists_as_cached,
    mark_fully_populated_tracks_as_cached,
)
from utils.metadata.albums import flatten_albums
from utils.metadata.queries import get_unprocessed_album_ids, get_unprocessed_track_ids
from utils.metadata.tracks import flatten_tracks, insert_shallow_track_stubs


pytestmark = [pytest.mark.unit]


class FakeTrack:
    def __init__(self, payload):
        self._payload = payload

    def as_dict(self):
        return dict(self._payload)


def test_shallow_tracks_are_flattened_and_queued_for_enrichment(backup_restore_runtime_files):
    """Verifies shallow track payloads flatten correctly and remain queued for enrichment."""
    logger = logging.getLogger("tests.shallow_metadata")
    initialize_all(logger)

    raw_track = FakeTrack(
        {
            "id": 101,
            "title": "Shallow Song",
            "title_short": "Shallow",
            "duration": 180,
            "rank": 999,
            "preview": "https://example.test/preview.mp3",
            "playlist": {"id": 44, "title": "Ignored Playlist"},
            "artist": {"id": 9, "name": "Test Artist"},
            "album": {"id": 11, "title": "Test Album"},
        }
    )

    flattened_tracks = flatten_tracks([raw_track], logger)
    assert flattened_tracks == [
        {
            "id": 101,
            "title": "Shallow Song",
            "title_short": "Shallow",
            "duration": 180,
            "rank": 999,
            "preview": "https://example.test/preview.mp3",
            "artist_id": 9,
            "artist_name": "Test Artist",
            "album_id": 11,
            "album_name": "Test Album",
        }
    ]

    insert_shallow_track_stubs(flattened_tracks, logger)

    with get_connection(logger) as conn:
        track_row = conn.execute(
            "SELECT id, title, artist_id, artist_name, album_id, album_name, date_cached FROM tracks WHERE id = ?",
            (101,),
        ).fetchone()
        album_row = conn.execute(
            "SELECT id, title, artist_id, artist_name, date_cached FROM albums WHERE id = ?",
            (11,),
        ).fetchone()
        artist_row = conn.execute(
            "SELECT id, name, date_cached FROM artists WHERE id = ?",
            (9,),
        ).fetchone()

    assert dict(track_row) == {
        "id": 101,
        "title": "Shallow Song",
        "artist_id": 9,
        "artist_name": "Test Artist",
        "album_id": 11,
        "album_name": "Test Album",
        "date_cached": None,
    }
    assert dict(album_row) == {
        "id": 11,
        "title": "Test Album",
        "artist_id": 9,
        "artist_name": "Test Artist",
        "date_cached": None,
    }
    assert dict(artist_row) == {
        "id": 9,
        "name": "Test Artist",
        "date_cached": None,
    }
    assert get_unprocessed_track_ids(logger) == [{"id": 101}]


def test_shallow_insert_does_not_overwrite_enriched_tracks(backup_restore_runtime_files):
    """Ensures shallow track upserts do not overwrite rows already marked as cached."""
    logger = logging.getLogger("tests.shallow_metadata")
    initialize_all(logger)

    original_track = [{
        "id": 202,
        "title": "Original Shallow Title",
        "artist_id": 19,
        "artist_name": "Original Artist",
        "album_id": 29,
        "album_name": "Original Album",
    }]
    insert_shallow_track_stubs(original_track, logger)

    with get_connection(logger) as conn:
        conn.execute(
            "UPDATE tracks SET title = ?, date_cached = ? WHERE id = ?",
            ("Fully Enriched Title", "2026-03-30T00:00:00", 202),
        )
        conn.commit()

    updated_shallow_track = [{
        "id": 202,
        "title": "New Shallow Title",
        "artist_id": 19,
        "artist_name": "New Artist Name",
        "album_id": 29,
        "album_name": "New Album Name",
    }]
    insert_shallow_track_stubs(updated_shallow_track, logger)

    with get_connection(logger) as conn:
        track_row = conn.execute(
            "SELECT title, artist_name, album_name, date_cached FROM tracks WHERE id = ?",
            (202,),
        ).fetchone()

    assert dict(track_row) == {
        "title": "Fully Enriched Title",
        "artist_name": "Original Artist",
        "album_name": "Original Album",
        "date_cached": "2026-03-30T00:00:00",
    }


def test_flatten_albums_stubs_artists_via_dedicated_artist_path(backup_restore_runtime_files):
    """Confirms album flattening also routes artist stubs through the dedicated artist path."""
    logger = logging.getLogger("tests.shallow_metadata")
    initialize_all(logger)

    flattened_albums = flatten_albums(
        [
            {
                "id": 303,
                "title": "Album Source Payload",
                "cover": "https://example.test/cover.jpg",
                "artist": {
                    "id": 33,
                    "name": "Album Artist",
                    "link": "https://www.deezer.com/artist/33",
                    "share": "https://share.example/artist/33",
                    "picture": "https://example.test/artist.jpg",
                    "picture_small": "https://example.test/artist-small.jpg",
                    "picture_medium": "https://example.test/artist-medium.jpg",
                    "picture_big": "https://example.test/artist-big.jpg",
                    "picture_xl": "https://example.test/artist-xl.jpg",
                    "nb_album": 12,
                    "nb_fan": 3400,
                    "radio": True,
                    "tracklist": "https://api.deezer.com/artist/33/top?limit=50",
                },
            }
        ],
        logger,
    )

    assert flattened_albums == [
        {
            "id": 303,
            "title": "Album Source Payload",
            "cover": "https://example.test/cover.jpg",
            "artist_id": 33,
            "artist_name": "Album Artist",
        }
    ]

    with get_connection(logger) as conn:
        album_row = conn.execute(
            "SELECT id, title, cover, artist_id, artist_name, date_cached FROM albums WHERE id = ?",
            (303,),
        ).fetchone()
        artist_row = conn.execute(
            """
            SELECT id, name, link, share, picture, picture_small, picture_medium,
                   picture_big, picture_xl, nb_album, nb_fan, radio, tracklist, date_cached
            FROM artists WHERE id = ?
            """,
            (33,),
        ).fetchone()

    assert dict(album_row) == {
        "id": 303,
        "title": "Album Source Payload",
        "cover": "https://example.test/cover.jpg",
        "artist_id": 33,
        "artist_name": "Album Artist",
        "date_cached": None,
    }
    artist_payload = dict(artist_row)
    assert artist_payload["id"] == 33
    assert artist_payload["name"] == "Album Artist"
    assert artist_payload["link"] == "https://www.deezer.com/artist/33"
    assert artist_payload["share"] == "https://share.example/artist/33"
    assert artist_payload["picture"] == "https://example.test/artist.jpg"
    assert artist_payload["picture_small"] == "https://example.test/artist-small.jpg"
    assert artist_payload["picture_medium"] == "https://example.test/artist-medium.jpg"
    assert artist_payload["picture_big"] == "https://example.test/artist-big.jpg"
    assert artist_payload["picture_xl"] == "https://example.test/artist-xl.jpg"
    assert artist_payload["nb_album"] == 12
    assert artist_payload["nb_fan"] == 3400
    assert artist_payload["radio"] == 1
    assert artist_payload["tracklist"] == "https://api.deezer.com/artist/33/top?limit=50"
    assert artist_payload["date_cached"] is not None


def test_flatteners_deduplicate_by_entity_id(backup_restore_runtime_files):
    """Checks duplicate input entities collapse to a single persisted row per ID."""
    logger = logging.getLogger("tests.shallow_metadata")
    initialize_all(logger)

    duplicate_track = {
        "id": 404,
        "title": "Duplicate Track",
        "duration": 200,
        "artist": {
            "id": 44,
            "name": "Duplicate Artist",
            "link": "https://www.deezer.com/artist/44",
        },
        "album": {
            "id": 55,
            "title": "Duplicate Album",
            "cover": "https://example.test/dup-cover.jpg",
            "artist": {
                "id": 44,
                "name": "Duplicate Artist",
                "link": "https://www.deezer.com/artist/44",
            },
        },
    }

    flattened_tracks = flatten_tracks([duplicate_track, duplicate_track], logger)

    assert flattened_tracks == [
        {
            "id": 404,
            "title": "Duplicate Track",
            "duration": 200,
            "artist_id": 44,
            "artist_name": "Duplicate Artist",
            "album_id": 55,
            "album_name": "Duplicate Album",
        }
    ]

    with get_connection(logger) as conn:
        track_count = conn.execute("SELECT COUNT(*) FROM tracks WHERE id = ?", (404,)).fetchone()[0]
        album_count = conn.execute("SELECT COUNT(*) FROM albums WHERE id = ?", (55,)).fetchone()[0]
        artist_count = conn.execute("SELECT COUNT(*) FROM artists WHERE id = ?", (44,)).fetchone()[0]

    assert track_count == 1
    assert album_count == 1
    assert artist_count == 1


def test_mark_fully_populated_entities_as_cached(backup_restore_runtime_files):
    """Validates cache finalization marks fully populated artist/album/track rows as cached."""
    logger = logging.getLogger("tests.shallow_metadata")
    initialize_all(logger)

    with get_connection(logger) as conn:
        conn.execute(
            """
            INSERT INTO artists (
                id, name, link, share, picture, picture_small, picture_medium,
                picture_big, picture_xl, nb_album, nb_fan, radio, tracklist, date_cached
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                901,
                "Cached Artist",
                "https://www.deezer.com/artist/901",
                "https://share.example/artist/901",
                "https://img.example/artist-901.jpg",
                "https://img.example/artist-901-s.jpg",
                "https://img.example/artist-901-m.jpg",
                "https://img.example/artist-901-b.jpg",
                "https://img.example/artist-901-xl.jpg",
                10,
                500,
                1,
                "https://api.deezer.com/artist/901/top?limit=50",
            ),
        )

        conn.execute(
            """
            INSERT INTO albums (
                id, title, upc, link, share, cover, cover_small, cover_medium,
                cover_big, cover_xl, md5_image, label, nb_tracks, duration, fans,
                release_date, record_type, available, tracklist, explicit_lyrics,
                explicit_content_lyrics, explicit_content_cover, genres, contributors,
                artist_id, artist_name, date_cached, genre_mapped
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                902,
                "Cached Album",
                "UPC-902",
                "https://www.deezer.com/album/902",
                "https://share.example/album/902",
                "https://img.example/album-902.jpg",
                "https://img.example/album-902-s.jpg",
                "https://img.example/album-902-m.jpg",
                "https://img.example/album-902-b.jpg",
                "https://img.example/album-902-xl.jpg",
                "md5album902",
                "Label 902",
                12,
                2500,
                1000,
                "2026-01-01",
                "album",
                1,
                "https://api.deezer.com/album/902/tracks",
                1,
                0,
                2,
                '[{"id": 132, "name": "Pop"}]',
                '[{"id": 901, "name": "Cached Artist"}]',
                901,
                "Cached Artist",
                1,
            ),
        )

        conn.execute(
            """
            INSERT INTO tracks (
                id, readable, title, title_short, title_version, unseen, isrc, link,
                share, duration, track_position, disk_number, rank, release_date,
                explicit_lyrics, explicit_content_lyrics, explicit_content_cover,
                preview, bpm, gain, available_countries, contributors, md5_image,
                track_token, artist_id, album_id, date_cached
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                903,
                1,
                "Cached Track",
                "Cached Track",
                "Original Mix",
                0,
                "ISRC903",
                "https://www.deezer.com/track/903",
                "https://share.example/track/903",
                210,
                1,
                1,
                777,
                "2026-01-02",
                0,
                0,
                2,
                "https://preview.example/903.mp3",
                120.0,
                -5.0,
                '["US","CA"]',
                '[{"id": 901, "name": "Cached Artist"}]',
                "md5track903",
                "token903",
                901,
                902,
            ),
        )
        conn.commit()

    assert get_unprocessed_track_ids(logger) == [{"id": 903}]
    assert get_unprocessed_album_ids(logger) == [902]

    marked_artists = mark_fully_populated_artists_as_cached(logger)
    marked_albums = mark_fully_populated_albums_as_cached(logger)
    marked_tracks = mark_fully_populated_tracks_as_cached(logger)

    assert marked_artists == 1
    assert marked_albums == 1
    assert marked_tracks == 1

    with get_connection(logger) as conn:
        artist_cached = conn.execute("SELECT date_cached FROM artists WHERE id = ?", (901,)).fetchone()[0]
        album_cached = conn.execute("SELECT date_cached FROM albums WHERE id = ?", (902,)).fetchone()[0]
        track_cached = conn.execute("SELECT date_cached FROM tracks WHERE id = ?", (903,)).fetchone()[0]

    assert artist_cached is not None
    assert album_cached is not None
    assert track_cached is not None
    assert get_unprocessed_track_ids(logger) == []
    assert get_unprocessed_album_ids(logger) == []