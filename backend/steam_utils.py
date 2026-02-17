"""Steam-related utilities used across LuaTools backend modules."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Dict, Optional

import Millennium  # type: ignore

from logger import logger

_STEAM_INSTALL_PATH: Optional[str] = None

if sys.platform.startswith("win"):
    try:
        import winreg  # type: ignore
    except Exception:  # pragma: no cover - registry import failure fallback
        winreg = None  # type: ignore
else:
    winreg = None  # type: ignore


def detect_steam_install_path() -> str:
    """Return the cached Steam installation path or discover it."""
    global _STEAM_INSTALL_PATH
    if _STEAM_INSTALL_PATH:
        return _STEAM_INSTALL_PATH

    path = None

    if sys.platform.startswith("win") and winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                path, _ = winreg.QueryValueEx(key, "SteamPath")
        except Exception:
            path = None

    if not path:
        try:
            path = Millennium.steam_path()
        except Exception:
            path = None

    _STEAM_INSTALL_PATH = path
    logger.log(f"LuaTools: Steam install path set to {_STEAM_INSTALL_PATH}")
    return _STEAM_INSTALL_PATH or ""


def _parse_vdf_simple(content: str) -> Dict[str, any]:
    """Simple VDF parser for libraryfolders.vdf and appmanifest files."""
    result: Dict[str, any] = {}
    stack = [result]
    current_key = None

    lines = content.split("\n")
    tokens = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        parts = re.findall(r'"[^"]*"|\{|\}', line)
        tokens.extend(parts)

    i = 0
    while i < len(tokens):
        token = tokens[i].strip('"')

        if tokens[i] == "{":
            if current_key:
                new_dict = {}
                stack[-1][current_key] = new_dict
                stack.append(new_dict)
                current_key = None
        elif tokens[i] == "}":
            if len(stack) > 1:
                stack.pop()
        elif current_key is None:
            current_key = token
        else:
            stack[-1][current_key] = token
            current_key = None
        i += 1

    return result


def _find_steam_path() -> str:
    global _STEAM_INSTALL_PATH
    if _STEAM_INSTALL_PATH:
        return _STEAM_INSTALL_PATH

    if sys.platform.startswith("win") and winreg:
        try:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                winreg.CloseKey(key)
                if steam_path and os.path.exists(steam_path):
                    _STEAM_INSTALL_PATH = steam_path
                    return steam_path
            except Exception:
                pass

            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam")
                steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
                winreg.CloseKey(key)
                if steam_path and os.path.exists(steam_path):
                    _STEAM_INSTALL_PATH = steam_path
                    return steam_path
            except Exception:
                pass
        except Exception as exc:
            logger.warn(f"LuaTools: Failed to read Steam path from registry: {exc}")

    return ""


def has_lua_for_app(appid: int) -> bool:
    try:
        base_path = detect_steam_install_path() or Millennium.steam_path()
        if not base_path:
            return False

        stplug_path = os.path.join(base_path, "config", "stplug-in")
        lua_file = os.path.join(stplug_path, f"{appid}.lua")
        disabled_file = os.path.join(stplug_path, f"{appid}.lua.disabled")
        return os.path.exists(lua_file) or os.path.exists(disabled_file)
    except Exception as exc:
        logger.error(f"LuaTools (steam_utils): Error checking Lua scripts for app {appid}: {exc}")
        return False


def get_game_install_path_response(appid: int) -> Dict[str, any]:
    """Find the game installation path. Returns dict mirroring previous JSON output."""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    steam_path = _find_steam_path()
    if not steam_path:
        return {"success": False, "error": "Could not find Steam installation path"}

    library_vdf_path = os.path.join(steam_path, "config", "libraryfolders.vdf")
    if not os.path.exists(library_vdf_path):
        logger.warn(f"LuaTools: libraryfolders.vdf not found at {library_vdf_path}")
        return {"success": False, "error": "Could not find libraryfolders.vdf"}

    try:
        with open(library_vdf_path, "r", encoding="utf-8") as handle:
            vdf_content = handle.read()
        library_data = _parse_vdf_simple(vdf_content)
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to parse libraryfolders.vdf: {exc}")
        return {"success": False, "error": "Failed to parse libraryfolders.vdf"}

    library_folders = library_data.get("libraryfolders", {})
    library_path = None
    appid_str = str(appid)
    all_library_paths = []

    for folder_data in library_folders.values():
        if isinstance(folder_data, dict):
            folder_path = folder_data.get("path", "")
            if folder_path:
                folder_path = folder_path.replace("\\\\", "\\")
                all_library_paths.append(folder_path)

            apps = folder_data.get("apps", {})
            if isinstance(apps, dict) and appid_str in apps:
                library_path = folder_path
                break

    appmanifest_path = None
    if not library_path:
        logger.log(
            f"LuaTools: appid {appid} not in libraryfolders.vdf, searching all libraries for appmanifest"
        )
        for lib_path in all_library_paths:
            candidate_path = os.path.join(lib_path, "steamapps", f"appmanifest_{appid}.acf")
            if os.path.exists(candidate_path):
                library_path = lib_path
                appmanifest_path = candidate_path
                logger.log(f"LuaTools: Found appmanifest at {appmanifest_path}")
                break
    else:
        appmanifest_path = os.path.join(library_path, "steamapps", f"appmanifest_{appid}.acf")

    if not library_path or not appmanifest_path or not os.path.exists(appmanifest_path):
        logger.log(f"LuaTools: appmanifest not found for {appid} in any library")
        return {"success": False, "error": "menu.error.notInstalled"}

    try:
        with open(appmanifest_path, "r", encoding="utf-8") as handle:
            manifest_content = handle.read()
        manifest_data = _parse_vdf_simple(manifest_content)
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to parse appmanifest: {exc}")
        return {"success": False, "error": "Failed to parse appmanifest"}

    app_state = manifest_data.get("AppState", {})
    install_dir = app_state.get("installdir", "")
    if not install_dir:
        logger.warn(f"LuaTools: installdir not found in appmanifest for {appid}")
        return {"success": False, "error": "Install directory not found"}

    full_install_path = os.path.join(library_path, "steamapps", "common", install_dir)
    if not os.path.exists(full_install_path):
        logger.warn(f"LuaTools: Game install path does not exist: {full_install_path}")
        return {"success": False, "error": "Game directory not found"}

    logger.log(f"LuaTools: Game install path for {appid}: {full_install_path}")
    return {
        "success": True,
        "installPath": full_install_path,
        "installDir": install_dir,
        "libraryPath": library_path,
        "path": full_install_path,
    }


def open_game_folder(path: str) -> bool:
    """Open the game folder using the platform default file explorer."""
    try:
        if not path or not os.path.exists(path):
            return False

        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to open game folder: {exc}")
        return False


__all__ = [
    "detect_steam_install_path",
    "get_game_install_path_response",
    "has_lua_for_app",
    "open_game_folder",
]

