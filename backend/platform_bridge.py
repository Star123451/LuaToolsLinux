"""Runtime bridge for optional Millennium integration.

This module allows the backend to run in two modes:
1) Inside Millennium (real API available)
2) Standalone/Linux tooling mode (fallback shim)
"""

from __future__ import annotations

import os
import sys


def _detect_steam_path_fallback() -> str:
    """Best-effort Steam path discovery when Millennium is unavailable."""
    candidates = [
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.local/share/Steam"),
    ]

    if sys.platform.startswith("win"):
        candidates.extend(
            [
                os.path.expandvars(r"%ProgramFiles(x86)%\\Steam"),
                os.path.expandvars(r"%ProgramFiles%\\Steam"),
            ]
        )

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


try:
    import Millennium as Millennium  # type: ignore
except Exception:
    class _MillenniumFallback:
        @staticmethod
        def steam_path() -> str:
            return _detect_steam_path_fallback()

        @staticmethod
        def add_browser_js(_path: str) -> None:
            return None

        @staticmethod
        def ready() -> None:
            return None

        @staticmethod
        def version() -> str:
            return "standalone"

    Millennium = _MillenniumFallback()
