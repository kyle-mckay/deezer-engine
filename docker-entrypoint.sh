#!/bin/bash
# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

set -e

export PYTHONPATH="/deezer_engine/app${PYTHONPATH:+:$PYTHONPATH}"

case "$1" in
    shell)
        exec /bin/bash -i
        ;;
    pytest)
        cd /deezer_engine
        exec python -m deezer_engine "$@"
        ;;
    *)
        cd /deezer_engine/app
        exec python -m deezer_engine "$@"
        ;;
esac