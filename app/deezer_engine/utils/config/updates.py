# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import requests


def version_to_int(version_str):
    """
    Equivalent to: sed 's/v//' | awk -F. '{ printf("%03d%03d%03d\\n", $1,$2,$3); }'
    Converts 'v1.2.3' or '1.2.3' into 1002003
    """
    if not version_str:
        return 0

    clean_v = re.sub(r'^[^0-9]+', '', version_str)

    parts = clean_v.split('.')

    while len(parts) < 3:
        parts.append('0')

    try:
        normalized_str = "{:03d}{:03d}{:03d}".format(
            int(parts[0]),
            int(parts[1]),
            int(parts[2])
        )
        return normalized_str
    except (ValueError, IndexError):
        return 0


def extract_version(version_str):
    """
    Extracts version numbers (e.g., 0.7.0) from a string.
    """
    if not version_str:
        return ""

    # Matches sequences of digits and dots (e.g., 1.2.3)
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_str)
    return match.group(1) if match else version_str


def check_for_updates(current_version, containerized, logger):
    """
    Checks the Codeberg API for a newer release tag.
    Provides context-aware advice for Docker users.
    """
    owner = "kylemmkay"
    repo_name = "deezer-engine"

    # Updated to Codeberg/Gitea API v1 format
    api_url = f"https://codeberg.org/api/v1/repos/{owner}/{repo_name}/releases/latest"

    try:
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()

        # Codeberg/Gitea uses 'name' for the tag/release title in the 'latest' endpoint
        latest_version = extract_version(response.json().get('name'))
        logger.debug(f"Latest version from Codeberg: {latest_version}")
        current_version = extract_version(current_version)
        logger.debug(f"Current source version: {current_version}")

        if latest_version and version_to_int(latest_version) > version_to_int(current_version):
            logger.warning("=" * 60)
            logger.warning(f"  UPDATE AVAILABLE: {current_version} -> {latest_version}")

            if containerized:
                logger.warning("  Container detected: Please pull the latest image to update.")
                # Update this if you move your image hosting to Codeberg as well
                logger.warning(f"  Run: docker pull {owner}/{repo_name}:latest")
            else:
                # Updated link to Codeberg
                logger.warning(f"  Download: https://codeberg.org/{owner}/{repo_name}/releases")
                logger.warning("  Or run 'git pull' if you cloned the repository.")

            logger.warning("=" * 60)
        else:
            logger.debug(f"Version check: You are running the latest version ({current_version}).")

    except Exception as e:
        logger.debug(f"Update check skipped: {e}")