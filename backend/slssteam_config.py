"""
SLSsteam ``config.yaml`` management.

Provides helpers to read, update, and query the SLSsteam configuration
stored at ``~/.config/SLSsteam/config.yaml``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from logger import logger
from linux_platform import get_slssteam_config_path, get_slssteam_config_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_yaml(path: str) -> Dict[str, Any]:
    """Minimal YAML-ish reader for SLSsteam's flat key:value config.

    SLSsteam config is a simple ``Key: value`` format (one level, no nesting),
    so we avoid pulling in a full YAML library.
    """
    data: Dict[str, Any] = {}
    if not os.path.isfile(path):
        return data
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" not in line:
                    continue
                key, _, raw_value = line.partition(":")
                key = key.strip()
                raw_value = raw_value.strip()
                # Normalise common YAML boolean literals
                if raw_value.lower() in ("yes", "true"):
                    data[key] = True
                elif raw_value.lower() in ("no", "false"):
                    data[key] = False
                else:
                    # Try integer, fall back to string
                    try:
                        data[key] = int(raw_value)
                    except ValueError:
                        data[key] = raw_value
    except Exception as exc:
        logger.warn(f"SLSsteam: failed to read config at {path}: {exc}")
    return data


def _write_yaml(path: str, data: Dict[str, Any]) -> None:
    """Write a flat dict back to the SLSsteam config format."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'yes' if value else 'no'}")
        else:
            lines.append(f"{key}: {value}")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception as exc:
        logger.warn(f"SLSsteam: failed to write config at {path}: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_config() -> Dict[str, Any]:
    """Return the current SLSsteam configuration as a dict."""
    return _read_yaml(get_slssteam_config_path())


def write_config(data: Dict[str, Any]) -> None:
    """Persist *data* to the SLSsteam config file."""
    _write_yaml(get_slssteam_config_path(), data)


def get_value(key: str, default: Any = None) -> Any:
    """Read a single value from the SLSsteam config."""
    return read_config().get(key, default)


def set_value(key: str, value: Any) -> None:
    """Set a single value and persist."""
    cfg = read_config()
    cfg[key] = value
    write_config(cfg)


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

def is_play_not_owned_enabled() -> bool:
    return bool(get_value("PlayNotOwnedGames", False))


def set_play_not_owned(enabled: bool) -> None:
    set_value("PlayNotOwnedGames", enabled)


def is_safe_mode_enabled() -> bool:
    return bool(get_value("SafeMode", False))


def set_safe_mode(enabled: bool) -> None:
    set_value("SafeMode", enabled)


def config_exists() -> bool:
    """Return *True* if the SLSsteam config file exists on disk."""
    return os.path.isfile(get_slssteam_config_path())


def get_sls_version() -> Optional[str]:
    """Return the SLSsteam version string from config, or None if unavailable."""
    return get_value("Version", None)
