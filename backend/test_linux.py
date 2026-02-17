#!/usr/bin/env python3
"""LuaTools Linux — Smoke Tests

Run from the project root:
    python3 backend/test_linux.py
"""

import os
import sys

# Ensure backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

passed = 0
failed = 0
total = 0


def test(name, fn):
    global passed, failed, total
    total += 1
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1


# ─── 1. Platform Detection ──────────────────────────────────────────

print("\n── linux_platform.py ──")

from linux_platform import (
    find_steam_root,
    get_stplugin_dir,
    get_depotcache_dir,
    get_slssteam_install_dir,
    get_slssteam_config_path,
    check_slssteam_installed,
    check_accela_installed,
    get_accela_dir,
    get_platform_summary,
    open_directory,
)


def test_steam_root():
    root = find_steam_root()
    assert root is not None, "Steam root not found — is Steam installed?"
    assert os.path.isdir(root), f"Steam root is not a directory: {root}"
    print(f"       → {root}")

test("find_steam_root", test_steam_root)


def test_stplugin_dir():
    d = get_stplugin_dir()
    assert d is not None, "stplug-in dir returned None"
    assert "stplug-in" in d
    print(f"       → {d}")

test("get_stplugin_dir", test_stplugin_dir)


def test_depotcache_dir():
    d = get_depotcache_dir()
    assert d is not None, "depotcache dir returned None"
    assert "depotcache" in d
    print(f"       → {d}")

test("get_depotcache_dir", test_depotcache_dir)


def test_slssteam_paths():
    install = get_slssteam_install_dir()
    config = get_slssteam_config_path()
    assert "SLSsteam" in install
    assert config.endswith("config.yaml")
    print(f"       → install: {install}")
    print(f"       → config:  {config}")

test("slssteam paths", test_slssteam_paths)


def test_slssteam_detection():
    installed = check_slssteam_installed()
    print(f"       → installed: {installed}")

test("slssteam detection", test_slssteam_detection)


def test_accela_detection():
    installed = check_accela_installed()
    accela_dir = get_accela_dir()
    print(f"       → installed: {installed}, dir: {accela_dir}")

test("accela detection", test_accela_detection)


def test_platform_summary():
    summary = get_platform_summary()
    assert isinstance(summary, dict)
    assert "steam_root" in summary
    print(f"       → {summary}")

test("get_platform_summary", test_platform_summary)


# ─── 2. SLSsteam Config ─────────────────────────────────────────────

print("\n── slssteam_config.py ──")

try:
    from slssteam_config import read_config, get_sls_version, is_play_not_owned_enabled


    def test_read_config():
        config = read_config()
        assert isinstance(config, dict)
        print(f"       → keys: {list(config.keys()) if config else '(empty/not installed)'}")

    test("read_config", test_read_config)


    def test_sls_version():
        ver = get_sls_version()
        print(f"       → version: {ver}")

    test("get_sls_version", test_sls_version)


    def test_play_not_owned():
        val = is_play_not_owned_enabled()
        print(f"       → PlayNotOwnedGames: {val}")

    test("is_play_not_owned_enabled", test_play_not_owned)

except ImportError as e:
    print(f"  ⚠️  Skipped (requires Millennium/PluginUtils): {e}")


# ─── 3. Steam Utils ─────────────────────────────────────────────────

print("\n── steam_utils.py ──")

# steam_utils imports Millennium which won't be available outside Steam,
# so we test it in a guarded way
try:
    from steam_utils import detect_steam_install_path, has_lua_for_app

    def test_detect_path():
        path = detect_steam_install_path()
        print(f"       → {path}")

    test("detect_steam_install_path", test_detect_path)
except ImportError as e:
    print(f"  ⚠️  Skipped (Millennium not available outside Steam): {e}")


# ─── 4. Settings ────────────────────────────────────────────────────

print("\n── settings/options.py ──")

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "settings"))
    from settings.options import get_settings_schema, get_default_settings_values


    def test_schema_has_slssteam():
        schema = get_settings_schema()
        group_keys = [g["key"] for g in schema]
        assert "slssteam" in group_keys, f"SLSsteam group missing, got: {group_keys}"
        print(f"       → groups: {group_keys}")

    test("settings schema has slssteam", test_schema_has_slssteam)


    def test_defaults():
        defaults = get_default_settings_values()
        sls = defaults.get("slssteam", {})
        assert "playNotOwnedGames" in sls
        assert "safeMode" in sls
        print(f"       → slssteam defaults: {sls}")

    test("default settings values", test_defaults)

except ImportError as e:
    print(f"  ⚠️  Skipped (requires Millennium/PluginUtils): {e}")


# ─── Summary ─────────────────────────────────────────────────────────

print(f"\n{'═' * 40}")
print(f"  Results: {passed}/{total} passed, {failed} failed")
print(f"{'═' * 40}\n")

sys.exit(1 if failed else 0)
