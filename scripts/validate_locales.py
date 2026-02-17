from __future__ import annotations

import json
import os
from pathlib import Path

PLACEHOLDER = "translation missing"
DEFAULT_LOCALE = "en"


def load_locale(path: Path) -> tuple[dict, dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}, {}
    except Exception as exc:
        raise RuntimeError(f"Failed to parse locale file {path}: {exc}") from exc

    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}

    strings = data.get("strings")
    if not isinstance(strings, dict):
        strings = {
            key: value
            for key, value in data.items()
            if key != "_meta" and isinstance(value, str)
        }

    return meta, strings


def write_locale(path: Path, meta: dict, strings: dict) -> None:
    payload = {
        "_meta": dict(meta or {}),
        "strings": {key: strings[key] for key in sorted(strings.keys())},
    }
    payload["_meta"]["code"] = payload["_meta"].get("code") or path.stem
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def ensure_locales(base_dir: Path) -> int:
    en_path = base_dir / f"{DEFAULT_LOCALE}.json"
    meta_en, strings_en = load_locale(en_path)
    if not strings_en:
        raise RuntimeError(f"Default locale file {en_path} is empty or missing.")

    updated_files = 0

    for locale_path in base_dir.glob("*.json"):
        if locale_path.name == f"{DEFAULT_LOCALE}.json":
            continue

        meta, strings = load_locale(locale_path)
        changed = False

        for key, value in strings_en.items():
            if key not in strings:
                strings[key] = PLACEHOLDER
                changed = True

        if changed:
            write_locale(locale_path, meta, strings)
            updated_files += 1
            print(f"Updated missing keys in {locale_path.name}")

    # Ensure English file uses sorted keys as well (no automatic fill)
    write_locale(en_path, meta_en, strings_en)

    return updated_files


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    locales_dir = repo_root / "backend" / "locales"

    if not locales_dir.exists():
        raise RuntimeError(f"Locales directory not found: {locales_dir}")

    updated = ensure_locales(locales_dir)
    if updated == 0:
        print("All locale files already include the required keys.")
    else:
        print(f"Updated {updated} locale file(s) with missing keys.")


if __name__ == "__main__":
    main()

