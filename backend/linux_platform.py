"""
Platform detection and path resolution for LuaTools (Linux).

Centralises all platform-specific logic so that the rest of the codebase
can remain clean.  This build targets Linux desktop only.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional


# ---------------------------------------------------------------------------
# Steam path resolution
# ---------------------------------------------------------------------------

_STEAM_PATHS = [
    os.path.expanduser("~/.steam/steam"),
    os.path.expanduser("~/.local/share/Steam"),
    "/opt/steam/steam",
    "/usr/local/steam",
]


def find_steam_root() -> Optional[str]:
    """Search well-known locations for the Steam installation."""
    # Prefer paths containing steam.sh (strongest indicator)
    for path in _STEAM_PATHS:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "steam.sh")):
            return path
    # Fallback: directory just exists
    for path in _STEAM_PATHS:
        if os.path.isdir(path):
            return path
    return None


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def get_stplugin_dir(steam_root: Optional[str] = None) -> Optional[str]:
    """Return ``config/stplug-in/`` under the Steam root."""
    root = steam_root or find_steam_root()
    if root is None:
        return None
    return os.path.join(root, "config", "stplug-in")


def get_depotcache_dir(steam_root: Optional[str] = None) -> Optional[str]:
    """Return ``depotcache/`` under the Steam root."""
    root = steam_root or find_steam_root()
    if root is None:
        return None
    return os.path.join(root, "depotcache")


# ---------------------------------------------------------------------------
# SLSsteam paths
# ---------------------------------------------------------------------------

def get_slssteam_install_dir() -> str:
    return os.path.expanduser("~/.local/share/SLSsteam")


def get_slssteam_config_dir() -> str:
    return os.path.expanduser("~/.config/SLSsteam")


def get_slssteam_config_path() -> str:
    return os.path.join(get_slssteam_config_dir(), "config.yaml")


def check_slssteam_installed() -> bool:
    """Return *True* if ``SLSsteam.so`` exists in the install dir."""
    so_path = os.path.join(get_slssteam_install_dir(), "SLSsteam.so")
    return os.path.isfile(so_path)


# ---------------------------------------------------------------------------
# ACCELA paths
# ---------------------------------------------------------------------------

_ACCELA_CANDIDATES = [
    os.path.expanduser("~/.local/share/ACCELA"),
    os.path.expanduser("~/accela"),
]


def get_accela_dir() -> Optional[str]:
    """Return the ACCELA installation directory if found."""
    for path in _ACCELA_CANDIDATES:
        if os.path.isdir(path):
            return path
    return None


def check_accela_installed() -> bool:
    return get_accela_dir() is not None


def get_accela_run_script() -> Optional[str]:
    """Return the path to ACCELA's launcher script if it exists.

    Prefers launch_debug.sh (logs errors) over run.sh.
    """
    accela_dir = get_accela_dir()
    if not accela_dir:
        return None
    # Prefer the debug wrapper (handles venv + logging for non-terminal launches)
    for name in ("launch_debug.sh", "run.sh"):
        script = os.path.join(accela_dir, name)
        if os.path.isfile(script):
            return script
    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def open_directory(path: str) -> None:
    """Open a directory in the file manager via ``xdg-open``."""
    subprocess.Popen(
        ["xdg-open", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# SLSsteam injection verification
# ---------------------------------------------------------------------------

_LD_AUDIT_LINE = 'export LD_AUDIT=$HOME/.local/share/SLSsteam/library-inject.so:$HOME/.local/share/SLSsteam/SLSsteam.so'


def verify_slssteam_injected() -> dict:
    """Check that steam.sh has the LD_AUDIT export and patch it if missing.

    Returns a dict:  {"patched": bool, "already_ok": bool, "error": str|None}
    Matches the SLSsteam installer's ``patch_steam_sh()`` logic.
    """
    if not check_slssteam_installed():
        return {"patched": False, "already_ok": False, "error": "SLSsteam not installed"}

    # Find steam.sh
    steam_sh = None
    for candidate in _STEAM_PATHS:
        path = os.path.join(candidate, "steam.sh")
        if os.path.isfile(path):
            steam_sh = path
            break

    if not steam_sh:
        return {"patched": False, "already_ok": False, "error": "steam.sh not found"}

    try:
        with open(steam_sh, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        return {"patched": False, "already_ok": False, "error": f"read failed: {exc}"}

    # Already patched?
    if "LD_AUDIT" in content and "SLSsteam" in content:
        return {"patched": False, "already_ok": True, "error": None}

    # Patch: insert the export at line 10 (matching SLSsteam installer)
    try:
        lines = content.splitlines(keepends=True)
        insert_pos = min(9, len(lines))  # line 10 (0-indexed = 9)
        lines.insert(insert_pos, _LD_AUDIT_LINE + "\n")
        with open(steam_sh, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return {"patched": True, "already_ok": False, "error": None}
    except Exception as exc:
        return {"patched": False, "already_ok": False, "error": f"write failed: {exc}"}


def get_platform_summary() -> dict:
    """Return a dict of platform diagnostics for logging."""
    summary = {
        "steam_root": find_steam_root(),
        "slssteam_installed": check_slssteam_installed(),
        "accela_installed": check_accela_installed(),
        "accela_dir": get_accela_dir(),
    }
    if summary["slssteam_installed"]:
        inj = verify_slssteam_injected()
        summary["slssteam_injection"] = inj
    return summary

