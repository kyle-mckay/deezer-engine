# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path

# Put app/deezer_engine/ on sys.path so all bare module imports
# (utils.*, strategies.*, __version__) resolve correctly in every test session.
sys.path.insert(0, str(Path(__file__).resolve().parent / "app" / "deezer_engine"))
