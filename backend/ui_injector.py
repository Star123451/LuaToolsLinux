#!/usr/bin/env python3
"""LuaTools Steam UI injector/self-heal utility."""

from __future__ import annotations

import os
import shutil


MARKER_START = "<!-- LuaToolsLinux Inject START -->"
MARKER_END = "<!-- LuaToolsLinux Inject END -->"
SCRIPT_TAG = '<script src="LuaTools/luatools.js"></script>'


def _candidate_steam_roots() -> list[str]:
    return [
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.steam/steam"),
    ]


def _sync_assets(public_dir: str, target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)

    js_src = os.path.join(public_dir, "luatools.js")
    if os.path.isfile(js_src):
        shutil.copy2(js_src, os.path.join(target_dir, "luatools.js"))

    icon_src = os.path.join(public_dir, "luatools-icon.png")
    if os.path.isfile(icon_src):
        shutil.copy2(icon_src, os.path.join(target_dir, "luatools-icon.png"))

    themes_src = os.path.join(public_dir, "themes")
    themes_dst = os.path.join(target_dir, "themes")
    if os.path.isdir(themes_src):
        if os.path.isdir(themes_dst):
            shutil.rmtree(themes_dst)
        shutil.copytree(themes_src, themes_dst)


def _inject_index(index_html: str, script_tag: str) -> bool:
    with open(index_html, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    snippet = f"\n{MARKER_START}\n{script_tag}\n{MARKER_END}\n"

    if MARKER_START in html and MARKER_END in html:
        start_idx = html.find(MARKER_START)
        end_idx = html.find(MARKER_END)
        if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
            return False
        end_idx += len(MARKER_END)
        existing_block = html[start_idx:end_idx]
        if existing_block == snippet.strip():
            return False
        patched = html[:start_idx] + snippet.strip() + html[end_idx:]
        with open(index_html, "w", encoding="utf-8") as f:
            f.write(patched)
        return True

    idx = html.lower().rfind("</body>")
    if idx == -1:
        return False

    patched = html[:idx] + snippet + html[idx:]
    with open(index_html, "w", encoding="utf-8") as f:
        f.write(patched)
    return True


def _build_inline_script_tag(script_path: str) -> str | None:
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
    except Exception:
        return None

    script_content = script_content.replace("</script>", "<\\/script>")
    return f"<script>\n{script_content}\n</script>"


def ensure_ui_injection(install_root: str) -> dict[str, int]:
    public_dir = os.path.join(install_root, "public")
    result = {"roots_seen": 0, "roots_patched": 0, "assets_synced": 0}
    script_tag = _build_inline_script_tag(os.path.join(public_dir, "luatools.js")) or SCRIPT_TAG

    for root in _candidate_steam_roots():
        steamui = os.path.join(root, "steamui")
        index_html = os.path.join(steamui, "index.html")
        if not os.path.isfile(index_html):
            continue

        result["roots_seen"] += 1
        target_dir = os.path.join(steamui, "LuaTools")
        _sync_assets(public_dir, target_dir)
        result["assets_synced"] += 1
        if _inject_index(index_html, script_tag):
            result["roots_patched"] += 1

    return result


def main() -> int:
    install_root = os.path.expanduser(os.environ.get("LUATOOLS_INSTALL_ROOT", "~/.local/share/LuaToolsLinux"))
    stats = ensure_ui_injection(install_root)
    print(
        f"roots_seen={stats['roots_seen']} roots_patched={stats['roots_patched']} assets_synced={stats['assets_synced']}"
    )
    if stats["roots_seen"] == 0:
        print("Steam UI not found. Open Steam and rerun luatools-heal-ui after Steam has started.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
