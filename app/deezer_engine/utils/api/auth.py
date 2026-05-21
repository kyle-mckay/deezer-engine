# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API authentication helpers."""

import base64
import json
import logging
import random
import sys
import time

import deezer
import requests

from utils.config import get_global_value


def _create_session(arl, refresh_token=None):
    """Create a requests.Session pre-loaded with the ARL cookie and standard browser headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    session.cookies.set('arl', arl, domain='.deezer.com')
    if refresh_token:
        # auth.deezer.com/login/renew requires both refresh-token and refresh-token-Deezer
        # (same value, different expiry). The browser sends both; we mirror that here.
        session.cookies.set('refresh-token', refresh_token, domain='.deezer.com')
        session.cookies.set('refresh-token-Deezer', refresh_token, domain='.deezer.com')
    return session


def _warm_and_handshake(session, warm_url, logger):
    """
    Load warm_url to establish session cookies, then perform the deezer.getUserData
    CSRF handshake. Returns (api_token, results_dict).
    """
    logger.debug(f"Warming Deezer session: {warm_url}")
    session.get(warm_url)

    cid = random.randint(100000000, 999999999)
    token_url = (
        f"https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData"
        f"&input=3&api_version=1.0&api_token=&cid={cid}"
    )
    handshake_headers = {
        'Content-Type': 'text/plain;charset=UTF-8',
        'Referer': warm_url,
    }
    try:
        resp = session.post(token_url, data="{}", headers=handshake_headers).json()
        api_token = resp.get('results', {}).get('checkForm')
        results = resp.get('results', {})

        if not api_token:
            logger.error(f"CSRF handshake failed. Gateway response keys: {list(results.keys())}")
            return None, {}

        logger.debug("Deezer CSRF handshake successful.")
        return api_token, results
    except Exception as e:
        logger.error(f"CSRF handshake error: {e}")
        return None, {}


def _decode_jwt_exp(jwt_token):
    """Decode the payload of a JWT and return its exp timestamp, or 0 on failure."""
    try:
        payload_b64 = jwt_token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_b64))
        return int(data.get('exp', 0))
    except Exception:
        return 0


def _fetch_pipe_jwt(session, logger):
    """
    Obtain a pipe.deezer.com JWT.

    Strategy (in order):
    1. Check whether the session already has a ``jwt`` cookie set by the server
       during the warm-up page load.
    2. Call auth.deezer.com/login/renew to get or refresh the JWT.

    Returns the JWT string, or None if both strategies fail.
    """
    # 1. Cookie already in session (set by www.deezer.com during warm-up)
    session_jwt = session.cookies.get('jwt')
    if session_jwt and isinstance(session_jwt, str) and session_jwt.startswith('eyJ'):
        logger.debug("Pipe JWT found in session cookies.")
        return session_jwt

    # 2. Explicit renew call
    try:
        resp = session.post(
            "https://auth.deezer.com/login/renew?jo=p&rto=c&i=c",
            headers={
                'Accept': 'application/json',
                'Referer': 'https://www.deezer.com/',
                'Origin': 'https://www.deezer.com',
            }
        )
        try:
            data = resp.json()
        except Exception:
            logger.debug(
                f"login/renew response is not valid JSON "
                f"(status={resp.status_code}): {resp.text[:200]}"
            )
            return None

        if not isinstance(data, dict):
            logger.debug(
                f"login/renew returned unexpected type {type(data).__name__}: {str(data)[:200]}"
            )
            return None

        jwt = data.get('jwt')
        if jwt and isinstance(jwt, str) and jwt.startswith('eyJ'):
            logger.debug("Pipe JWT obtained from auth.deezer.com/login/renew.")
            return jwt

        logger.debug(f"login/renew returned no usable jwt. Response keys: {list(data.keys())}")
        return None
    except Exception as e:
        logger.debug(f"Pipe JWT fetch failed: {e}")
        return None


def get_or_refresh_pipe_jwt(client, logger):
    """
    Return a valid pipe.deezer.com JWT from the client, refreshing via
    auth.deezer.com/login/renew if it has expired or is within 60 s of expiry.
    Returns None if the session is unavailable or the refresh fails.
    """
    if not client.session:
        return None

    grace = 60
    if client.pipe_jwt:
        exp = _decode_jwt_exp(client.pipe_jwt)
        if exp > time.time() + grace:
            return client.pipe_jwt

    logger.debug("Pipe JWT missing or near-expiry; refreshing...")
    new_jwt = _fetch_pipe_jwt(client.session, logger)
    if new_jwt:
        client.pipe_jwt = new_jwt
    return client.pipe_jwt


def get_authenticated_session(arl, logger, warm_url=None):
    """
    Create a new authenticated session and return (session, api_token).
    Kept for backward compatibility with callers that manage their own sessions.
    Prefer attaching to the client via get_authenticated_client when possible.
    """
    target_url = warm_url or "https://www.deezer.com/us/"
    session = _create_session(arl)
    api_token, _ = _warm_and_handshake(session, target_url, logger)
    if not api_token:
        return None, None
    return session, api_token


def get_authenticated_client(config, logger, pipe_jwt_needed=False):
    """
    Initialize the Deezer public-API client and attach a shared authenticated web
    session (client.session, client.api_token, client.pipe_jwt) for gw-light and
    pipe.deezer.com calls that require ARL auth.

    pipe_jwt_needed: when True, warn if no pipe JWT is obtained (caller has strategies
    that use playlist metadata writes). When False, skip the warning — JWT acquisition
    is still attempted, but silently.
    """
    if config is None:
        if logger:
            logger.debug("Config is None, returning unauthenticated Deezer client for testing.")
        client = deezer.Client()
        client.session = None
        client.api_token = None
        client.pipe_jwt = None
        client.chunk_size = 50
        return client

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("--- Initializing Deezer Authentication ---")
        logger.debug(f"Raw config keys available: {list(config.get('config', {}).keys())}")

    arl = config.get('config', {}).get('arl_token')
    user_id = config.get('config', {}).get('user_id')

    if not arl or arl == "PASTE_YOUR_ARL_HERE":
        logger.error("ARL token is missing in config.yml")
        sys.exit(1)

    if logger.isEnabledFor(logging.DEBUG):
        masked_arl = f"{arl[:6]}...{arl[-6:]}" if len(arl) > 12 else "***"
        logger.debug(f"Auth headers prepared with ARL: {masked_arl}")

    chunk_size = config.get('config', {}).get('chunk_size', get_global_value('chunk_size', 50))
    logger.debug(f"Global chunk size set to: {chunk_size}")

    try:
        logger.debug("Attempting to instantiate deezer.Client...")
        client = deezer.Client(headers={"Cookie": f"arl={arl}", "Accept-Language": "en-US"})
        client.chunk_size = chunk_size

        # Initialise shared web session — used by gw-light and pipe.deezer.com calls
        warm_url = "https://www.deezer.com/us/"
        refresh_token = config.get('config', {}).get('refresh_token') or None
        session = _create_session(arl, refresh_token=refresh_token)
        api_token, _ = _warm_and_handshake(session, warm_url, logger)
        if api_token:
            client.session = session
            client.api_token = api_token
            client.pipe_jwt = _fetch_pipe_jwt(session, logger)
            if not client.pipe_jwt and pipe_jwt_needed:
                hint = (
                    " Add 'refresh_token' to config.yml (export from browser cookies) to enable them."
                    if not refresh_token else ""
                )
                logger.warning(
                    "Could not obtain pipe.deezer.com JWT. Playlist metadata write operations "
                    f"(rename, privacy, description) will not be available this run.{hint}"
                )
        else:
            logger.warning("Web session initialisation failed. ARL-authenticated features may not work.")
            client.session = None
            client.api_token = None
            client.pipe_jwt = None

        # Verify connection via public API
        if user_id:
            logger.debug(f"Testing connection for User ID: {user_id}")
            user = client.get_user(user_id)
            masked_name = f"{user.name[0]}...{user.name[-1]}" if len(user.name) > 2 else "***"
            logger.info(f"Authenticated successfully as: {masked_name}")

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"User Metadata: Name='{user.name}', "
                    f"Status='{getattr(user, 'status', 'N/A')}', "
                    f"Link={user.link}"
                )
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("No user_id provided. Performing fallback connectivity test...")
            track = client.get_track(3135553)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Fallback test successful. Track retrieved: '{track.title}'")
            logger.warning(
                "Connection successful, but user_id is missing in config.yml. "
                "Exclusion strategies may fail without it."
            )

        return client

    except Exception as e:
        logger.error(f"Failed to connect to Deezer API: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Traceback for authentication failure:")
        logger.debug("Check if your ARL token has expired or if your user_id is correct.")
        sys.exit(1)
