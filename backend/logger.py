"""Shared logger instance for the LuaTools backend."""

from __future__ import annotations

import sys


class _StandaloneLogger:
    """Fallback logger used when Millennium PluginUtils is unavailable."""

    def log(self, message: str) -> None:
        print(message)

    def warn(self, message: str) -> None:
        print(message, file=sys.stderr)

    def error(self, message: str) -> None:
        print(message, file=sys.stderr)

    def info(self, message: str) -> None:
        self.log(message)

    def debug(self, message: str) -> None:
        self.log(message)


_LOGGER_INSTANCE = None


def get_logger():
    """Return a singleton logger instance."""
    global _LOGGER_INSTANCE
    if _LOGGER_INSTANCE is not None:
        return _LOGGER_INSTANCE

    try:
        import PluginUtils  # type: ignore

        _LOGGER_INSTANCE = PluginUtils.Logger()
    except ModuleNotFoundError:
        _LOGGER_INSTANCE = _StandaloneLogger()

    return _LOGGER_INSTANCE


# Convenience alias so other modules can `from logger import logger`
logger = get_logger()


