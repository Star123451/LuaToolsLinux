"""Shared logger instance for the LuaTools plugin backend."""

import PluginUtils  # type: ignore

_LOGGER_INSTANCE = None


import os
import sys

class FileLogger:
    def __init__(self):
        self._wrapped = None
        # Use absolute path relative to this file
        self._log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "luatools.log")
        
        # Initialize/clear log file
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- LuaTools Log Session Started ---\n")
        except Exception as e:
            print(f"Failed to init log file: {e}", file=sys.stderr)

    @property
    def wrapped(self):
        if self._wrapped is None:
            try:
                import PluginUtils  # type: ignore
                self._wrapped = PluginUtils.Logger("LuaTools")
            except ImportError:
                class DummyLogger:
                    def log(self, m): print(f"[M_LOG] {m}")
                    def warn(self, m): print(f"[M_WARN] {m}")
                    def error(self, m): print(f"[M_ERR] {m}")
                self._wrapped = DummyLogger()
        return self._wrapped

    def _write_to_file(self, level, message):
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"[{level}] {message}\n")
        except Exception:
            pass

    def log(self, message):
        self._write_to_file("INFO", message)
        try:
            self.wrapped.log(message)
        except Exception:
            print(f"[INFO] {message}")

    def warn(self, message):
        self._write_to_file("WARN", message)
        try:
            self.wrapped.warn(message)
        except Exception:
            print(f"[WARN] {message}")

    def error(self, message):
        self._write_to_file("ERROR", message)
        try:
            self.wrapped.error(message)
        except Exception:
            print(f"[ERROR] {message}")

_LOGGER_INSTANCE = None

def get_logger() -> FileLogger:
    """Return a singleton FileLogger instance."""
    global _LOGGER_INSTANCE
    if _LOGGER_INSTANCE is None:
        _LOGGER_INSTANCE = FileLogger()
    return _LOGGER_INSTANCE

# Convenience alias so other modules can `from logger import logger`
logger = get_logger()


