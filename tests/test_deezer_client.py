import pytest
from utils.infrastructure import logger as logger_module
from utils.infrastructure.logger import initialize_deezer_logger
from utils import deezer_auth
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

test_ids = [
    ('track', 2322611675, 1, 'idfc', 'blackbear', 'deadroses', 245),
    ('album', 451782425, 10, 'deadroses', 'blackbear', None, None),
    ('artist', 1948791, None, 'blackbear', None, None, None),
    ('playlist', 8640961382, None, '100% blackbear', None, None, None)
]

@pytest.fixture(scope="module")
def client():
    log = initialize_deezer_logger()
    return deezer_auth.get_authenticated_client(None, log)

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
    if entity == 'track':
        c = client.get_track(entity_id)
        assert c.title == name
        assert c.artist.name == artist
        assert c.album.title == album
        assert c.duration == duration
        # Fail on extras
        validate_fields(c.as_dict(), TRACK_FIELDS, "full track", strict=True)

    elif entity == 'album':
        c = client.get_album(entity_id)
        assert c.title == name
        assert c.artist.name == artist
        assert c.nb_tracks == object_len
        
        tracks = c.get_tracks()
        assert len(tracks) == object_len
        if tracks:
            # Warn on extras
            validate_fields(tracks[0].as_dict(), SUB_ENTITY_TRACK_MINIMUM, "album track", strict=False)

    elif entity == 'artist':
        c = client.get_artist(entity_id)
        assert c.name == name
        assert hasattr(c, 'nb_album')

    elif entity == 'playlist':
        c = client.get_playlist(entity_id)
        assert c.title == name
        assert hasattr(c, 'tracks')
        
        tracks = c.get_tracks()
        if tracks:
            # Warn on extras
            validate_fields(tracks[0].as_dict(), SUB_ENTITY_TRACK_MINIMUM, "playlist track", strict=False)

    else:
        pytest.fail(f"Unknown entity type: {entity}")