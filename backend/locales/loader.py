from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from paths import backend_path

from logger import logger

DEFAULT_LOCALE = "en"
PLACEHOLDER_VALUE = "translation missing"
LOCALES_DIR = backend_path("locales")


def _ensure_locales_dir() -> None:
    try:
        os.makedirs(LOCALES_DIR, exist_ok=True)
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to ensure locales dir: {exc}")


def _locale_path(locale: str) -> str:
    return os.path.join(LOCALES_DIR, f"{locale}.json")


def _read_locale_file(locale: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    path = _locale_path(locale)
    if not os.path.exists(path):
        return {}, {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to read locale file {path}: {exc}")
        return {}, {}

    meta = data.get("_meta")
    strings = data.get("strings")

    if not isinstance(meta, dict):
        meta = {}

    if isinstance(strings, dict):
        strings = {str(k): str(v) for k, v in strings.items()}
    else:
        # Backwards compatibility with flat files
        strings = {}
        for key, value in data.items():
            if key == "_meta":
                continue
            if isinstance(value, str):
                strings[str(key)] = value
    return meta, strings


def _write_locale_file(locale: str, meta: Dict[str, Any], strings: Dict[str, str]) -> None:
    _ensure_locales_dir()
    data = {
        "_meta": dict(meta or {}),
        "strings": {k: strings[k] for k in sorted(strings.keys())},
    }
    data["_meta"]["code"] = locale
    try:
        with open(_locale_path(locale), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to write locale file {locale}: {exc}")


def _normalise_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.lower() == PLACEHOLDER_VALUE:
        return None
    return value


class LocaleManager:
    """Utility class to load and serve locale strings with fallback logic."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._locales: Dict[str, Dict[str, Any]] = {}
        self._english_strings: Dict[str, str] = {}
        self._english_meta: Dict[str, Any] = {}
        self.refresh()

    def refresh(self) -> None:
        with self._lock:
            _ensure_locales_dir()

            # Load default locale first
            meta, strings = _read_locale_file(DEFAULT_LOCALE)
            if not strings:
                logger.warn("LuaTools: Default locale en.json is empty or missing.")
                strings = {}
            self._english_meta = {**meta, "code": DEFAULT_LOCALE}
            self._english_strings = strings.copy()
            self._locales = {}

            try:
                available_files = [
                    f for f in os.listdir(LOCALES_DIR) if f.endswith(".json")
                ]
            except OSError as exc:
                logger.warn(f"LuaTools: Failed to list locales dir: {exc}")
                available_files = []

            for filename in available_files:
                locale_code = filename[:-5]
                locale_meta, locale_strings = _read_locale_file(locale_code)
                if locale_code != DEFAULT_LOCALE:
                    updated = False
                    for key in self._english_strings.keys():
                        if key not in locale_strings:
                            locale_strings[key] = PLACEHOLDER_VALUE
                            updated = True
                    if updated:
                        _write_locale_file(locale_code, locale_meta, locale_strings)

                merged_strings = {}
                for key, english_value in self._english_strings.items():
                    candidate = locale_strings.get(key)
                    normalised = _normalise_value(candidate)
                    if normalised is not None and locale_code != DEFAULT_LOCALE:
                        merged_strings[key] = normalised
                    else:
                        fallback_value = _normalise_value(english_value)
                        merged_strings[key] = fallback_value or PLACEHOLDER_VALUE

                meta_payload = {**locale_meta, "code": locale_code}
                name = meta_payload.get("name") or meta_payload.get("nativeName")
                if not name:
                    meta_payload["name"] = locale_code
                    meta_payload["nativeName"] = locale_code

                self._locales[locale_code] = {
                    "meta": meta_payload,
                    "strings": merged_strings,
                    "raw": locale_strings,
                }

            # Ensure default locale is present in cache
            if DEFAULT_LOCALE not in self._locales:
                self._locales[DEFAULT_LOCALE] = {
                    "meta": self._english_meta,
                    "strings": {
                        key: _normalise_value(value) or PLACEHOLDER_VALUE
                        for key, value in self._english_strings.items()
                    },
                    "raw": self._english_strings.copy(),
                }

    def available_locales(self) -> List[Dict[str, Any]]:
        with self._lock:
            locales = []
            for code, payload in sorted(self._locales.items(), key=lambda item: item[0]):
                meta = payload.get("meta", {})
                locales.append(
                    {
                        "code": code,
                        "name": meta.get("name") or code,
                        "nativeName": meta.get("nativeName") or meta.get("name") or code,
                    }
                )
            return locales

    def get_locale_strings(self, locale: str) -> Dict[str, str]:
        with self._lock:
            payload = self._locales.get(locale)
            if not payload:
                payload = self._locales.get(DEFAULT_LOCALE)
            strings = payload.get("strings", {}) if payload else {}
            # Provide deep copy to avoid accidental mutation
            return dict(strings)

    def translate(self, key: str, locale: str) -> str:
        if not key:
            return PLACEHOLDER_VALUE
        with self._lock:
            payload = self._locales.get(locale)
            if payload:
                value = payload.get("strings", {}).get(key)
                if value is not None:
                    return value
            value = self._locales.get(DEFAULT_LOCALE, {}).get("strings", {}).get(key)
            if value is not None:
                return value
        return PLACEHOLDER_VALUE


_LOCALE_MANAGER: Optional[LocaleManager] = None


def get_locale_manager() -> LocaleManager:
    global _LOCALE_MANAGER
    if _LOCALE_MANAGER is None:
        _LOCALE_MANAGER = LocaleManager()
    return _LOCALE_MANAGER

