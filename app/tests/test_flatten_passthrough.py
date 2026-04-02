# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Tests for the album/artist list passthrough chain:
    flatten_tracks → flatten_albums → flatten_artists → insert_shallow_*_stubs

Strategy
--------
* Each layer patches only the *next* downstream call so the function under
  test runs completely but nothing touches the database.
* The full-chain tests mock only the three database-facing insert stubs,
  letting all three flatten functions run end-to-end.
* skip_fully_populated=True is used throughout to suppress the
  mark_fully_populated_* cache calls inside the insert stubs.
"""

import logging
from unittest.mock import patch

import pytest

from utils.metadata.albums import flatten_albums
from utils.metadata.artists import flatten_artists
from utils.metadata.tracks import flatten_tracks

_LOGGER = logging.getLogger("tests.flatten_passthrough")

# ---------------------------------------------------------------------------
# Shared base payloads
# ---------------------------------------------------------------------------

ARTIST_A = {"id": 10, "name": "Artist A"}
# Album without a nested artist — tests that don't need the artist-in-album path.
ALBUM_A = {"id": 20, "title": "Album A"}
# Track with both embedded album and embedded artist.
TRACK_A = {
    "id": 1,
    "title": "Track A",
    "artist": {"id": 10, "name": "Artist A"},
    "album": {"id": 20, "title": "Album A"},
}


# ---------------------------------------------------------------------------
# flatten_artists — terminal node
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFlattenArtistsTerminal:
    """flatten_artists is the terminal node: its only side-effect is calling
    insert_shallow_artist_stubs. All verification stops here."""

    def test_artists_forwarded_to_insert_stub(self):
        with patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub:
            flatten_artists([ARTIST_A], _LOGGER, skip_fully_populated=True)
        stub.assert_called_once()
        assert any(a["id"] == 10 for a in stub.call_args.args[0])

    def test_multiple_artists_all_forwarded(self):
        artists = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}]
        with patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub:
            flatten_artists(artists, _LOGGER, skip_fully_populated=True)
        ids = {a["id"] for a in stub.call_args.args[0]}
        assert ids == {1, 2, 3}

    def test_skip_fully_populated_forwarded_to_stub(self):
        with patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub:
            flatten_artists([ARTIST_A], _LOGGER, skip_fully_populated=True)
        assert stub.call_args.kwargs["skip_fully_populated"] is True

    def test_playlist_and_album_keys_stripped_before_insert(self):
        """flatten_artists removes stray 'playlist' / 'album' keys before inserting."""
        noisy = {**ARTIST_A, "playlist": {"id": 99}, "album": {"id": 88}}
        with patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub:
            flatten_artists([noisy], _LOGGER, skip_fully_populated=True)
        inserted = stub.call_args.args[0][0]
        assert "playlist" not in inserted
        assert "album" not in inserted
        assert inserted["id"] == 10

    def test_none_artistlist_returns_empty_without_calling_stub(self):
        with patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub:
            result = flatten_artists(None, _LOGGER, skip_fully_populated=True)
        assert result == []
        stub.assert_not_called()


# ---------------------------------------------------------------------------
# flatten_albums → flatten_artists passthrough
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFlattenAlbumsToArtists:
    """flatten_albums extracts embedded artists and merges them with any artistlist=
    passthrough before forwarding the full set to flatten_artists."""

    def test_embedded_artist_forwarded_to_flatten_artists(self):
        album_with_artist = {**ALBUM_A, "artist": {"id": 10, "name": "Artist A"}}
        with (
            patch("utils.metadata.albums.flatten_artists") as mock_artists,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
        ):
            flatten_albums([album_with_artist], _LOGGER, skip_fully_populated=True)
        mock_artists.assert_called_once()
        assert any(a["id"] == 10 for a in mock_artists.call_args.args[0])

    def test_artistlist_passthrough_forwarded_when_album_has_no_artist(self):
        extra_artist = {"id": 99, "name": "Extra"}
        with (
            patch("utils.metadata.albums.flatten_artists") as mock_artists,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
        ):
            flatten_albums(
                [ALBUM_A],
                _LOGGER,
                skip_fully_populated=True,
                artistlist=[extra_artist],
            )
        assert any(a["id"] == 99 for a in mock_artists.call_args.args[0])

    def test_embedded_and_passthrough_artists_combined(self):
        """Both the album-embedded artist and the artistlist= entry arrive together."""
        album_with_artist = {**ALBUM_A, "artist": {"id": 10, "name": "Artist A"}}
        extra_artist = {"id": 99, "name": "Extra"}
        with (
            patch("utils.metadata.albums.flatten_artists") as mock_artists,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
        ):
            flatten_albums(
                [album_with_artist],
                _LOGGER,
                skip_fully_populated=True,
                artistlist=[extra_artist],
            )
        ids = {a["id"] for a in mock_artists.call_args.args[0]}
        assert 10 in ids   # from album's embedded artist
        assert 99 in ids   # from artistlist passthrough

    def test_skip_fully_populated_forwarded_to_flatten_artists(self):
        with (
            patch("utils.metadata.albums.flatten_artists") as mock_artists,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
        ):
            flatten_albums([ALBUM_A], _LOGGER, skip_fully_populated=True)
        assert mock_artists.call_args.kwargs["skip_fully_populated"] is True

    def test_flattened_albums_forwarded_to_insert_stub(self):
        with (
            patch("utils.metadata.albums.flatten_artists"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
        ):
            flatten_albums([ALBUM_A], _LOGGER, skip_fully_populated=True)
        stub.assert_called_once()
        assert any(a["id"] == 20 for a in stub.call_args.args[0])

    def test_skip_fully_populated_forwarded_to_album_insert_stub(self):
        with (
            patch("utils.metadata.albums.flatten_artists"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
        ):
            flatten_albums([ALBUM_A], _LOGGER, skip_fully_populated=True)
        assert stub.call_args.kwargs["skip_fully_populated"] is True


# ---------------------------------------------------------------------------
# flatten_tracks → flatten_albums passthrough
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFlattenTracksToAlbums:
    """flatten_tracks extracts embedded albums/artists and merges them with any
    albumlist=/artistlist= passthrough before forwarding to flatten_albums."""

    def test_embedded_album_forwarded_to_flatten_albums(self):
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        mock_albums.assert_called_once()
        assert any(a["id"] == 20 for a in mock_albums.call_args.args[0])

    def test_embedded_artist_forwarded_as_artistlist_to_flatten_albums(self):
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        artistlist = mock_albums.call_args.kwargs.get("artistlist", [])
        assert any(a["id"] == 10 for a in artistlist)

    def test_albumlist_passthrough_forwarded_when_track_has_no_album(self):
        track_no_album = {"id": 2, "title": "Track B"}
        extra_album = {"id": 99, "title": "Extra Album"}
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [track_no_album],
                _LOGGER,
                skip_fully_populated=True,
                albumlist=[extra_album],
            )
        assert any(a["id"] == 99 for a in mock_albums.call_args.args[0])

    def test_artistlist_passthrough_forwarded_as_artistlist_to_flatten_albums(self):
        track_no_artist = {"id": 2, "title": "Track B"}
        extra_artist = {"id": 99, "name": "Extra Artist"}
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [track_no_artist],
                _LOGGER,
                skip_fully_populated=True,
                artistlist=[extra_artist],
            )
        artistlist = mock_albums.call_args.kwargs.get("artistlist", [])
        assert any(a["id"] == 99 for a in artistlist)

    def test_embedded_and_passthrough_albums_combined(self):
        """Track-embedded album and albumlist= entry both appear in the flatten_albums call."""
        extra_album = {"id": 99, "title": "Extra Album"}
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [TRACK_A],
                _LOGGER,
                skip_fully_populated=True,
                albumlist=[extra_album],
            )
        ids = {a["id"] for a in mock_albums.call_args.args[0]}
        assert 20 in ids   # from track's embedded album
        assert 99 in ids   # from albumlist passthrough

    def test_embedded_and_passthrough_artists_combined_in_artistlist(self):
        """Track-embedded artist and artistlist= entry both appear in artistlist forwarded to flatten_albums."""
        extra_artist = {"id": 99, "name": "Extra Artist"}
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [TRACK_A],
                _LOGGER,
                skip_fully_populated=True,
                artistlist=[extra_artist],
            )
        ids = {a["id"] for a in mock_albums.call_args.kwargs.get("artistlist", [])}
        assert 10 in ids   # from track's embedded artist
        assert 99 in ids   # from artistlist passthrough

    def test_skip_fully_populated_forwarded_to_flatten_albums(self):
        with (
            patch("utils.metadata.tracks.flatten_albums") as mock_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        assert mock_albums.call_args.kwargs["skip_fully_populated"] is True

    def test_flattened_tracks_forwarded_to_insert_stub(self):
        with (
            patch("utils.metadata.tracks.flatten_albums"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs") as stub,
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        stub.assert_called_once()
        assert any(t["id"] == 1 for t in stub.call_args.args[0])

    def test_skip_fully_populated_forwarded_to_track_insert_stub(self):
        with (
            patch("utils.metadata.tracks.flatten_albums"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs") as stub,
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        assert stub.call_args.kwargs["skip_fully_populated"] is True


# ---------------------------------------------------------------------------
# Full chain — only the three DB-touching insert stubs are mocked
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFullChain:
    """All three flatten functions run end-to-end. Only the insert stubs are
    mocked to keep the tests DB-free."""

    def test_all_three_insert_stubs_called_for_a_complete_track(self):
        track = {
            "id": 1,
            "title": "Track A",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {"id": 20, "title": "Album A", "artist": {"id": 10, "name": "Artist A"}},
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub_artists,
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub_albums,
            patch("utils.metadata.tracks.insert_shallow_track_stubs") as stub_tracks,
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)

        stub_artists.assert_called_once()
        stub_albums.assert_called_once()
        stub_tracks.assert_called_once()

    def test_track_reaches_track_stub_with_correct_id(self):
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs") as stub,
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        assert any(t["id"] == 1 for t in stub.call_args.args[0])

    def test_embedded_album_reaches_album_stub_with_correct_id(self):
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([TRACK_A], _LOGGER, skip_fully_populated=True)
        assert any(a["id"] == 20 for a in stub.call_args.args[0])

    def test_embedded_artist_reaches_artist_stub_with_correct_id(self):
        track = {
            "id": 1,
            "title": "Track A",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {"id": 20, "title": "Album A", "artist": {"id": 10, "name": "Artist A"}},
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)
        assert any(a["id"] == 10 for a in stub.call_args.args[0])

    def test_artist_shared_by_track_and_album_deduplicated_at_stub(self):
        """An artist appearing in both the track and its nested album must arrive exactly
        once at insert_shallow_artist_stubs after deduplication."""
        track = {
            "id": 1,
            "title": "Track",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {
                "id": 20,
                "title": "Album",
                "artist": {"id": 10, "name": "Artist A"},
            },
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)
        count = sum(1 for a in stub.call_args.args[0] if a.get("id") == 10)
        assert count == 1, "Duplicate artist must be deduplicated before reaching the insert stub"

    def test_albumlist_passthrough_reaches_album_stub(self):
        """Albums supplied via albumlist= travel the full chain to insert_shallow_album_stubs."""
        extra_album = {"id": 77, "title": "Passthrough Album"}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([], _LOGGER, skip_fully_populated=True, albumlist=[extra_album])
        assert any(a["id"] == 77 for a in stub.call_args.args[0])

    def test_artistlist_passthrough_reaches_artist_stub(self):
        """Artists supplied via artistlist= travel the full chain to insert_shallow_artist_stubs."""
        extra_artist = {"id": 77, "name": "Passthrough Artist"}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([], _LOGGER, skip_fully_populated=True, artistlist=[extra_artist])
        assert any(a["id"] == 77 for a in stub.call_args.args[0])

    def test_artist_merged_from_passthrough_and_embedded(self):
        """An artist supplied via artistlist= with extra fields is merged with
        the same artist embedded in the album before reaching the stub."""
        track = {
            "id": 1,
            "title": "Track",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {"id": 20, "title": "Album", "artist": {"id": 10, "name": "Artist A"}},
        }
        richer_artist = {"id": 10, "nb_fan": 999}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True, artistlist=[richer_artist])
        artists = stub.call_args.args[0]
        merged = next(a for a in artists if a.get("id") == 10)
        assert merged["name"] == "Artist A"
        assert merged["nb_fan"] == 999


# ---------------------------------------------------------------------------
# Cross-level entity depth — nested objects with different field sets
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCrossLevelEntityDepth:
    """
    In real Deezer API responses the same entity can appear at more than one
    nesting level with different amounts of data.  For example:

        track.artist          → {id, name}            (sparse)
        track.album.artist    → {id, name, nb_fan, picture, nb_album, ...}  (richer)

    All three flatten functions must accumulate them in order and pass the
    full merged payload to the insert stubs.
    """

    # -- Artist depth ---------------------------------------------------------

    def test_richer_album_artist_fields_survive_when_track_artist_is_sparse(self):
        track = {
            "id": 1,
            "title": "Track",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {
                "id": 20,
                "title": "Album",
                "artist": {
                    "id": 10,
                    "name": "Artist A",
                    "nb_fan": 5000,
                    "picture": "https://example.test/pic.jpg",
                    "nb_album": 12,
                },
            },
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 10)
        assert merged["name"] == "Artist A"
        assert merged["nb_fan"] == 5000
        assert merged["picture"] == "https://example.test/pic.jpg"
        assert merged["nb_album"] == 12

    def test_richer_track_artist_fields_survive_when_album_artist_is_sparse(self):
        track = {
            "id": 1,
            "title": "Track",
            "artist": {
                "id": 10,
                "name": "Artist A",
                "nb_fan": 5000,
                "picture": "https://example.test/pic.jpg",
            },
            "album": {
                "id": 20,
                "title": "Album",
                "artist": {"id": 10, "name": "Artist A"},
            },
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 10)
        assert merged["nb_fan"] == 5000
        assert merged["picture"] == "https://example.test/pic.jpg"

    def test_complementary_artist_fields_at_both_levels_are_fully_merged(self):
        track = {
            "id": 1,
            "title": "Track",
            "artist": {"id": 10, "name": "Artist A", "nb_fan": 5000},
            "album": {
                "id": 20,
                "title": "Album",
                "artist": {"id": 10, "picture": "https://example.test/pic.jpg", "nb_album": 12},
            },
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 10)
        assert merged["name"] == "Artist A"
        assert merged["nb_fan"] == 5000
        assert merged["picture"] == "https://example.test/pic.jpg"
        assert merged["nb_album"] == 12

    def test_none_in_album_artist_does_not_overwrite_richer_track_artist_field(self):
        track = {
            "id": 1,
            "title": "Track",
            "artist": {"id": 10, "name": "Artist A", "nb_fan": 5000},
            "album": {
                "id": 20,
                "title": "Album",
                "artist": {"id": 10, "name": "Artist A", "nb_fan": None},
            },
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track], _LOGGER, skip_fully_populated=True)

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 10)
        assert merged["nb_fan"] == 5000

    def test_same_artist_across_multiple_tracks_accumulates_all_fields(self):
        track1 = {
            "id": 1,
            "title": "Track 1",
            "artist": {"id": 10, "name": "Artist A"},
            "album": {"id": 20, "title": "Album 1"},
        }
        track2 = {
            "id": 2,
            "title": "Track 2",
            "artist": {"id": 10, "name": "Artist A", "nb_fan": 5000, "picture": "url"},
            "album": {"id": 21, "title": "Album 2"},
        }
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs") as stub,
            patch("utils.metadata.albums.insert_shallow_album_stubs"),
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks([track1, track2], _LOGGER, skip_fully_populated=True)

        id10 = [a for a in stub.call_args.args[0] if a.get("id") == 10]
        assert len(id10) == 1
        assert id10[0]["nb_fan"] == 5000
        assert id10[0]["picture"] == "url"

    # -- Album depth ----------------------------------------------------------

    def test_richer_albumlist_passthrough_fields_survive_with_sparse_track_album(self):
        sparse_in_track = {"id": 20, "title": "Album A"}
        richer_passthrough = {
            "id": 20,
            "title": "Album A",
            "cover": "https://example.test/cover.jpg",
            "release_date": "2024-06-01",
            "nb_tracks": 10,
        }
        track = {"id": 1, "title": "Track", "album": sparse_in_track}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [track], _LOGGER, skip_fully_populated=True, albumlist=[richer_passthrough]
            )

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 20)
        assert merged["cover"] == "https://example.test/cover.jpg"
        assert merged["release_date"] == "2024-06-01"
        assert merged["nb_tracks"] == 10

    def test_sparse_albumlist_passthrough_does_not_overwrite_richer_track_album(self):
        rich_in_track = {
            "id": 20,
            "title": "Album A",
            "cover": "https://example.test/cover.jpg",
            "nb_tracks": 10,
        }
        sparse_passthrough = {"id": 20, "title": "Album A"}
        track = {"id": 1, "title": "Track", "album": rich_in_track}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [track], _LOGGER, skip_fully_populated=True, albumlist=[sparse_passthrough]
            )

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 20)
        assert merged["cover"] == "https://example.test/cover.jpg"
        assert merged["nb_tracks"] == 10

    def test_complementary_album_fields_from_track_and_passthrough_are_fully_merged(self):
        track = {
            "id": 1,
            "title": "Track",
            "album": {"id": 20, "title": "Album A", "release_date": "2024-06-01"},
        }
        passthrough = {"id": 20, "cover": "https://example.test/cover.jpg", "nb_tracks": 10}
        with (
            patch("utils.metadata.artists.insert_shallow_artist_stubs"),
            patch("utils.metadata.albums.insert_shallow_album_stubs") as stub,
            patch("utils.metadata.tracks.insert_shallow_track_stubs"),
        ):
            flatten_tracks(
                [track], _LOGGER, skip_fully_populated=True, albumlist=[passthrough]
            )

        merged = next(a for a in stub.call_args.args[0] if a.get("id") == 20)
        assert merged["title"] == "Album A"
        assert merged["release_date"] == "2024-06-01"
        assert merged["cover"] == "https://example.test/cover.jpg"
        assert merged["nb_tracks"] == 10
