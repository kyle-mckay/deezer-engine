import sys
from pathlib import Path

# Ensure app/deezer_engine/ is on sys.path so bare imports like
# `from utils.x import ...`, `from strategies.x import ...`, and
# `from __version__ import ...` all resolve when running `python -m deezer_engine`.
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from entrypoint import main  # noqa: E402

if __name__ == "__main__":
    main()
