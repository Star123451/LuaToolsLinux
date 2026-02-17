"""Shared logger instance for the LuaTools plugin backend."""

import PluginUtils  # type: ignore

_LOGGER_INSTANCE = None


def get_logger() -> PluginUtils.Logger:
    """Return a singleton PluginUtils.Logger instance."""
    global _LOGGER_INSTANCE
    if _LOGGER_INSTANCE is None:
        _LOGGER_INSTANCE = PluginUtils.Logger()
    return _LOGGER_INSTANCE


# Convenience alias so other modules can `from logger import logger`
logger = get_logger()


