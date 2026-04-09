import pytest
from utils.infrastructure import logger as logger_module
from utils.infrastructure.logger import initialize_deezer_logger
from utils.api.auth import get_authenticated_client
"""
Test for basic deezer-python API client functionality, including field presence and types for various fetch types (track, album, artist, playlist).
Requires entity to be publicly available in Deezer.
"""

# Reference field sets for each entity type
TRACK_FIELDS = {
    "id", "readable", "title", "title_short", "title_version", "link", "isrc", "share", "duration",
    "track_position", "disk_number", "rank", "release_date", "explicit_lyrics", "explicit_content_lyrics",
    "explicit_content_cover", "preview", "bpm", "gain", "available_countries", "contributors", "md5_image",
    "track_token", "artist", "album", "type"
}

# Minimum fields required for other fetch types
SUB_ENTITY_TRACK_MINIMUM = {
    "id", "readable", "title", "link", "duration", "rank", "explicit_lyrics", 
    "explicit_content_lyrics", "explicit_content_cover", "md5_image", "artist", "album", "type"
}


pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.slow]

test_ids = [
    ('track', 2322611675, 1, 'idfc', 'blackbear', 'deadroses', 245),
    ('album', 451782425, 10, 'deadroses', 'blackbear', None, None),
    ('artist', 1948791, None, 'blackbear', None, None, None),
    ('playlist', 8640961382, None, '100% blackbear', None, None, None)
]

@pytest.fixture(scope="module")
def client():
    log = initialize_deezer_logger()
    return get_authenticated_client(None, log)

def validate_fields(actual_dict, expected_set, entity_name, strict=False):
    actual_fields = set(actual_dict.keys())
    missing = expected_set - actual_fields
    extra = actual_fields - expected_set
    
    assert not missing, f"Missing fields in {entity_name}: {missing}"
    
    if extra:
        if strict:
            assert not extra, f"Unexpected extra fields in {entity_name}: {extra}"
        else:
            print(f"\n[WARNING] {entity_name} contains extra headers: {extra}")

@pytest.mark.parametrize("entity,entity_id,object_len,name,artist,album,duration", test_ids)
def test_deezer_entities(client, entity, entity_id, object_len, name, artist, album, duration):
    """Checks track/album/artist/playlist fetches expose expected fields and core values."""
    if entity == 'track':
        c = client.get_track(entity_id)
        assert c.title == name, f"Track title mismatch: expected '{name}', got '{c.title}'"
        assert c.artist.name == artist, f"Track artist mismatch: expected '{artist}', got '{c.artist.name}'"
        assert c.album.title == album, f"Track album mismatch: expected '{album}', got '{c.album.title}'"
        assert c.duration == duration, f"Track duration mismatch: expected '{duration}', got '{c.duration}'"
        # Fail on extras
        validate_fields(c.as_dict(), TRACK_FIELDS, "full track", strict=True)

    elif entity == 'album':
        c = client.get_album(entity_id)
        assert c.title == name, f"Album title mismatch: expected '{name}', got '{c.title}'"
        assert c.artist.name == artist, f"Album artist mismatch: expected '{artist}', got '{c.artist.name}'"
        assert c.nb_tracks == object_len, f"Album nb_tracks mismatch: expected '{object_len}', got '{c.nb_tracks}'"
        
        tracks = c.get_tracks()
        assert len(tracks) == object_len, f"Album track count mismatch: expected '{object_len}', got '{len(tracks)}'"
        if tracks:
            # Warn on extras
            validate_fields(tracks[0].as_dict(), SUB_ENTITY_TRACK_MINIMUM, "album track", strict=False)

    elif entity == 'artist':
        c = client.get_artist(entity_id)
        assert c.name == name, f"Artist name mismatch: expected '{name}', got '{c.name}'"
        assert hasattr(c, 'nb_album'), f"Artist object missing 'nb_album' attribute"

    elif entity == 'playlist':
        c = client.get_playlist(entity_id)
        assert c.title == name, f"Playlist title mismatch: expected '{name}', got '{c.title}'"
        assert hasattr(c, 'tracks'), f"Playlist object missing 'tracks' attribute"
        
        tracks = c.get_tracks()
        if tracks:
            # Warn on extras
            validate_fields(tracks[0].as_dict(), SUB_ENTITY_TRACK_MINIMUM, "playlist track", strict=False)

    else:
        pytest.fail(f"Unknown entity type: {entity}")