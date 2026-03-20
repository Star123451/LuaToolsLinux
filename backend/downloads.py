"""Handling of LuaTools add/download flows and related utilities."""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import subprocess
from typing import Dict, Any

import Millennium  # type: ignore

from api_manifest import load_api_manifest
from config import (
    APPID_LOG_FILE,
    LOADED_APPS_FILE,
    USER_AGENT,
    WEBKIT_DIR_NAME,
    WEB_UI_ICON_FILE,
    WEB_UI_JS_FILE,
)
from http_client import ensure_http_client
from logger import logger
from paths import backend_path, public_path
from steam_utils import detect_steam_install_path, has_lua_for_app
from utils import count_apis, ensure_temp_download_dir, normalize_manifest_text, read_text, write_text

DOWNLOAD_STATE: Dict[int, Dict[str, Any]] = {}
DOWNLOAD_LOCK = threading.Lock()

# Cache for app names to avoid repeated API calls
APP_NAME_CACHE: Dict[int, str] = {}
APP_NAME_CACHE_LOCK = threading.Lock()

# Rate limiting for Steam API calls
LAST_API_CALL_TIME = 0
API_CALL_MIN_INTERVAL = 0.3  # 300ms between calls to avoid 429 errors

# In-memory applist for fallback app name lookup
APPLIST_DATA: Dict[int, str] = {}
APPLIST_LOADED = False
APPLIST_LOCK = threading.Lock()
APPLIST_FILE_NAME = "all-appids.json"
APPLIST_URL = "https://applist.morrenus.xyz/"
APPLIST_DOWNLOAD_TIMEOUT = 300  # 5 minutes for large file

# --- STATUS PILL: Games Database Config ---
GAMES_DB_FILE_NAME = "games.json"
GAMES_DB_URL = "https://toolsdb.piqseu.cc/games.json"

# In-memory games database cache and lock
GAMES_DB_DATA: Dict[str, Any] = {}
GAMES_DB_LOADED = False
GAMES_DB_LOCK = threading.Lock()


def load_launcher_path() -> str:
    """Lê o caminho do launcher salvo DIRETAMENTE do settings.json."""
    default_path = os.path.expanduser("~/.local/share/ACCELA/run.sh")
    try:
        from settings.manager import get_settings_payload
        settings_vals = get_settings_payload().get("values", {})
        saved_path = settings_vals.get("launcher", {}).get("launcherPath", "").strip()
        if saved_path and os.path.exists(saved_path):
            return saved_path
    except Exception as e:
        logger.warn(f"LuaTools: Erro ao ler caminho do launcher do settings: {e}")

    return default_path if os.path.exists(default_path) else "/home/deck/.local/share/ACCELA/run.sh"

def browse_for_launcher() -> str:
    """Abre uma janela nativa do Linux (Zenity) para escolher o arquivo."""
    try:
        cmd = [
            'zenity',
            '--file-selection',
            '--title=Select Executable or Folder',
            '--filename=' + os.path.expanduser("~/.local/share/")
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            selected_path = stdout.decode('utf-8').strip()
            return json.dumps({"success": True, "path": selected_path})
        else:
            return json.dumps({"success": False, "error": "No file selected or user cancelled"})
    except Exception as e:
        logger.error(f"LuaTools: File picker error: {e}")
        return json.dumps({"success": False, "error": str(e)})


def _set_download_state(appid: int, update: dict) -> None:
    with DOWNLOAD_LOCK:
        state = DOWNLOAD_STATE.get(appid) or {}
        state.update(update)
        DOWNLOAD_STATE[appid] = state

def _get_download_state(appid: int) -> dict:
    with DOWNLOAD_LOCK:
        return DOWNLOAD_STATE.get(appid, {}).copy()

def _loaded_apps_path() -> str:
    return backend_path(LOADED_APPS_FILE)

def _appid_log_path() -> str:
    return backend_path(APPID_LOG_FILE)

def _fetch_app_name(appid: int) -> str:
    global LAST_API_CALL_TIME
    with APP_NAME_CACHE_LOCK:
        if appid in APP_NAME_CACHE:
            cached = APP_NAME_CACHE[appid]
            if cached: return cached

    applist_name = _get_app_name_from_applist(appid)
    if applist_name:
        with APP_NAME_CACHE_LOCK:
            APP_NAME_CACHE[appid] = applist_name
        return applist_name

    with APP_NAME_CACHE_LOCK:
        time_since_last_call = time.time() - LAST_API_CALL_TIME
        if time_since_last_call < API_CALL_MIN_INTERVAL:
            time.sleep(API_CALL_MIN_INTERVAL - time_since_last_call)
        LAST_API_CALL_TIME = time.time()

    client = ensure_http_client("LuaTools: _fetch_app_name")
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
        resp = client.get(url, follow_redirects=True, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        entry = data.get(str(appid)) or data.get(int(appid)) or {}
        if isinstance(entry, dict):
            inner = entry.get("data") or {}
            name = inner.get("name")
            if isinstance(name, str) and name.strip():
                name = name.strip()
                with APP_NAME_CACHE_LOCK:
                    APP_NAME_CACHE[appid] = name
                return name
    except Exception as exc:
        logger.warn(f"LuaTools: _fetch_app_name failed for {appid}: {exc}")

    with APP_NAME_CACHE_LOCK:
        APP_NAME_CACHE[appid] = ""
    return ""

def _append_loaded_app(appid: int, name: str) -> None:
    try:
        path = _loaded_apps_path()
        lines = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        prefix = f"{appid}:"
        lines = [line for line in lines if not line.startswith(prefix)]
        lines.append(f"{appid}:{name}")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except Exception as exc:
        logger.warn(f"LuaTools: _append_loaded_app failed for {appid}: {exc}")

def _remove_loaded_app(appid: int) -> None:
    try:
        path = _loaded_apps_path()
        if not os.path.exists(path): return
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        prefix = f"{appid}:"
        new_lines = [line for line in lines if not line.startswith(prefix)]
        if len(new_lines) != len(lines):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(new_lines) + ("\n" if new_lines else ""))
    except Exception as exc:
        logger.warn(f"LuaTools: _remove_loaded_app failed for {appid}: {exc}")

def _log_appid_event(action: str, appid: int, name: str) -> None:
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        line = f"[{action}] {appid} - {name} - {stamp}\n"
        with open(_appid_log_path(), "a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception as exc:
        logger.warn(f"LuaTools: _log_appid_event failed: {exc}")

def _preload_app_names_cache() -> None:
    try:
        log_path = _appid_log_path()
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as handle:
                for line in handle.read().splitlines():
                    if "]" in line and " - " in line:
                        try:
                            parts = line.split("]", 1)
                            if len(parts) < 2: continue
                            content = parts[1].strip()
                            content_parts = content.split(" - ", 2)
                            if len(content_parts) >= 2:
                                appid_str = content_parts[0].strip()
                                name = content_parts[1].strip()
                                appid = int(appid_str)
                                if name and not name.startswith("Unknown") and not name.startswith("UNKNOWN"):
                                    with APP_NAME_CACHE_LOCK:
                                        APP_NAME_CACHE[appid] = name
                        except (ValueError, IndexError):
                            continue
    except Exception as exc:
        logger.warn(f"LuaTools: _preload_app_names_cache from logs failed: {exc}")

    try:
        path = _loaded_apps_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle.read().splitlines():
                    if ":" in line:
                        parts = line.split(":", 1)
                        try:
                            appid = int(parts[0].strip())
                            name = parts[1].strip()
                            if name:
                                with APP_NAME_CACHE_LOCK:
                                    APP_NAME_CACHE[appid] = name
                        except (ValueError, IndexError):
                            continue
    except Exception as exc:
        logger.warn(f"LuaTools: _preload_app_names_cache from loaded_apps failed: {exc}")

    try:
        _load_applist_into_memory()
    except Exception as exc:
        logger.warn(f"LuaTools: _preload_app_names_cache from applist failed: {exc}")

def _get_loaded_app_name(appid: int) -> str:
    try:
        path = _loaded_apps_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle.read().splitlines():
                    if line.startswith(f"{appid}:"):
                        name = line.split(":", 1)[1].strip()
                        if name:
                            return name
    except Exception:
        pass
    return _get_app_name_from_applist(appid)

def _applist_file_path() -> str:
    temp_dir = ensure_temp_download_dir()
    return os.path.join(temp_dir, APPLIST_FILE_NAME)

def _load_applist_into_memory() -> None:
    global APPLIST_DATA, APPLIST_LOADED
    with APPLIST_LOCK:
        if APPLIST_LOADED: return
        file_path = _applist_file_path()
        if not os.path.exists(file_path):
            logger.log("LuaTools: Applist file not found, skipping load")
            APPLIST_LOADED = True
            return
        try:
            logger.log("LuaTools: Loading applist into memory...")
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                count = 0
                for entry in data:
                    if isinstance(entry, dict):
                        appid = entry.get("appid")
                        name = entry.get("name")
                        if appid and name and isinstance(name, str) and name.strip():
                            APPLIST_DATA[int(appid)] = name.strip()
                            count += 1
                logger.log(f"LuaTools: Loaded {count} app names from applist into memory")
            else:
                logger.warn("LuaTools: Applist file has invalid format (expected array)")
            APPLIST_LOADED = True
        except Exception as exc:
            logger.warn(f"LuaTools: Failed to load applist into memory: {exc}")
            APPLIST_LOADED = True

def _get_app_name_from_applist(appid: int) -> str:
    global APPLIST_DATA, APPLIST_LOADED
    if not APPLIST_LOADED: _load_applist_into_memory()
    with APPLIST_LOCK:
        return APPLIST_DATA.get(int(appid), "")

def _ensure_applist_file() -> None:
    file_path = _applist_file_path()
    if os.path.exists(file_path):
        logger.log("LuaTools: Applist file already exists, skipping download")
        return
    logger.log("LuaTools: Applist file not found, downloading...")
    client = ensure_http_client("LuaTools: DownloadApplist")
    try:
        resp = client.get(APPLIST_URL, follow_redirects=True, timeout=APPLIST_DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        try:
            data = resp.json()
            if not isinstance(data, list):
                logger.warn("LuaTools: Downloaded applist has invalid format")
                return
        except json.JSONDecodeError as exc:
            logger.warn(f"LuaTools: Downloaded applist is not valid JSON: {exc}")
            return
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        logger.log(f"LuaTools: Successfully downloaded and saved applist file ({len(data)} entries)")
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to download applist file: {exc}")

def init_applist() -> None:
    try:
        _ensure_applist_file()
        _load_applist_into_memory()
    except Exception as exc:
        logger.warn(f"LuaTools: Applist initialization failed: {exc}")

def _games_db_file_path() -> str:
    temp_dir = ensure_temp_download_dir()
    return os.path.join(temp_dir, GAMES_DB_FILE_NAME)

def _load_games_db_into_memory() -> None:
    global GAMES_DB_DATA, GAMES_DB_LOADED
    with GAMES_DB_LOCK:
        if GAMES_DB_LOADED: return
        file_path = _games_db_file_path()
        if not os.path.exists(file_path):
            logger.log("LuaTools: Games DB file not found, skipping load")
            GAMES_DB_LOADED = True
            return
        try:
            logger.log("LuaTools: Loading Games DB into memory...")
            with open(file_path, "r", encoding="utf-8") as handle:
                GAMES_DB_DATA = json.load(handle)
            logger.log(f"LuaTools: Loaded Games DB ({len(GAMES_DB_DATA)} entries)")
            GAMES_DB_LOADED = True
        except Exception as exc:
            logger.warn(f"LuaTools: Failed to load Games DB: {exc}")
            GAMES_DB_LOADED = True

def _ensure_games_db_file() -> None:
    file_path = _games_db_file_path()
    logger.log("LuaTools: Downloading Games DB...")
    client = ensure_http_client("LuaTools: DownloadGamesDB")
    try:
        logger.log(f"LuaTools: Downloading Games DB from {GAMES_DB_URL}")
        resp = client.get(GAMES_DB_URL, follow_redirects=True, timeout=60)
        logger.log(f"LuaTools: Games DB download response: status={resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        logger.log(f"LuaTools: Successfully downloaded Games DB")
    except Exception as exc:
        logger.warn(f"LuaTools: Failed to download Games DB: {exc}")

def init_games_db() -> None:
    try:
        _ensure_games_db_file()
        _load_games_db_into_memory()
    except Exception as exc:
        logger.warn(f"LuaTools: Games DB initialization failed: {exc}")

def get_games_database() -> str:
    if not GAMES_DB_LOADED:
        init_games_db()
    with GAMES_DB_LOCK:
        return json.dumps(GAMES_DB_DATA)

def fetch_app_name(appid: int) -> str:
    return _fetch_app_name(appid)

def _validate_zip_payload(appid: int, archive) -> tuple[str, list[str]]:
    names = archive.namelist()
    expected_lua = f"{appid}.lua"
    chosen_lua = None
    manifest_candidates = []

    for name in names:
        pure = os.path.basename(name)
        if not pure:
            continue
        if pure == expected_lua:
            chosen_lua = name
        if pure.lower().endswith(".manifest"):
            manifest_candidates.append(name)

    if not chosen_lua:
        raise RuntimeError(f"Manifest mismatch: package does not contain expected {expected_lua}")
    if not manifest_candidates:
        raise RuntimeError("Manifest mismatch: package does not contain any .manifest files")

    return chosen_lua, manifest_candidates

def _process_and_install_lua(appid: int, zip_path: str) -> None:
    import zipfile
    if _is_download_cancelled(appid):
        raise RuntimeError("cancelled")

    base_path = detect_steam_install_path() or Millennium.steam_path()
    target_dir = os.path.join(base_path or "", "config", "stplug-in")
    os.makedirs(target_dir, exist_ok=True)

    launcher_bin = load_launcher_path()
    logger.log(f"LuaTools: Usando launcher em: {launcher_bin}")

    if os.path.exists(launcher_bin):
        logger.log(f"LuaTools: Enviando {zip_path} para o Launcher...")
        try:
            if not os.access(launcher_bin, os.X_OK):
                 os.chmod(launcher_bin, 0o755)

            clean_env = os.environ.copy()
            clean_env.pop("LD_LIBRARY_PATH", None)
            clean_env.pop("LD_PRELOAD", None)
            clean_env.pop("STEAM_RUNTIME", None)

            proc = subprocess.Popen([launcher_bin, zip_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    env=clean_env)

            stdout, stderr = proc.communicate()
            if stdout: logger.log(f"Launcher Output: {stdout[:200]}...")
            if stderr: logger.warn(f"Launcher Stderr: {stderr}")

            if proc.returncode != 0:
                logger.warn(f"Launcher terminou com código de erro: {proc.returncode}")
            else:
                logger.log("Launcher finalizado com sucesso.")
        except Exception as e:
            logger.error(f"LuaTools: Falha ao executar Launcher: {e}")
    else:
        logger.warn(f"LuaTools: Launcher não encontrado em {launcher_bin}")

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = archive.namelist()
        chosen, manifest_paths = _validate_zip_payload(appid, archive)
        try:
            depotcache_dir = os.path.join(base_path or "", "depotcache")
            os.makedirs(depotcache_dir, exist_ok=True)
            for name in manifest_paths:
                try:
                    if _is_download_cancelled(appid): raise RuntimeError("cancelled")
                    pure = os.path.basename(name)
                    if not pure:
                        continue
                    data = archive.read(name)
                    out_path = os.path.join(depotcache_dir, pure)
                    with open(out_path, "wb") as manifest_file:
                        manifest_file.write(data)
                    logger.log(f"LuaTools: Extracted manifest -> {out_path}")
                except Exception as manifest_exc:
                    logger.warn(f"LuaTools: Failed to extract manifest {name}: {manifest_exc}")
        except Exception as depot_exc:
            logger.warn(f"LuaTools: depotcache extraction failed: {depot_exc}")

        if _is_download_cancelled(appid): raise RuntimeError("cancelled")

        data = archive.read(chosen)
        try: text = data.decode("utf-8")
        except Exception: text = data.decode("utf-8", errors="replace")

        processed_lines = []
        for line in text.splitlines(True):
            if re.match(r"^\s*setManifestid\(", line) and not re.match(r"^\s*--", line):
                line = re.sub(r"^(\s*)", r"\1--", line)
            processed_lines.append(line)
        processed_text = "".join(processed_lines)

        _set_download_state(appid, {"status": "installing"})
        dest_file = os.path.join(target_dir, f"{appid}.lua")
        if _is_download_cancelled(appid): raise RuntimeError("cancelled")
        with open(dest_file, "w", encoding="utf-8") as output:
            output.write(processed_text)
        logger.log(f"LuaTools: Installed lua -> {dest_file} (source={os.path.basename(chosen)})")
        _set_download_state(appid, {"installedPath": dest_file})

    try:
        os.remove(zip_path)
    except Exception:
        try:
            for _ in range(3):
                time.sleep(0.2)
                try: os.remove(zip_path); break
                except Exception: continue
        except Exception: pass

def _is_download_cancelled(appid: int) -> bool:
    try: return _get_download_state(appid).get("status") == "cancelled"
    except Exception: return False

def _download_zip_for_app(appid: int):
    client = ensure_http_client("LuaTools: download")
    apis = load_api_manifest()
    if not apis:
        logger.warn("LuaTools: No enabled APIs in manifest")
        _set_download_state(appid, {"status": "failed", "error": "No APIs available"})
        return

    # AQUI ESTÁ A MÁGICA: Puxamos as chaves diretamente do settings.json de forma dinâmica!
    morrenus_key = ""
    ryuu_cookie = ""
    try:
        from settings.manager import get_settings_payload
        settings_vals = get_settings_payload().get("values", {})
        api_auth = settings_vals.get("api_auth", {})
        morrenus_key = api_auth.get("morrenusKey", "").strip()
        ryuu_cookie = api_auth.get("ryuuCookie", "").strip()
    except Exception as e:
        logger.warn(f"LuaTools: Falha ao carregar senhas do settings: {e}")

    dest_root = ensure_temp_download_dir()
    dest_path = os.path.join(dest_root, f"{appid}.zip")
    _set_download_state(
        appid,
        {"status": "checking", "currentApi": None, "bytesRead": 0, "totalBytes": 0, "dest": dest_path},
    )

    for api in apis:
        name = api.get("name", "Unknown")
        template = api.get("url", "")
        success_code = int(api.get("success_code", 200))
        unavailable_code = int(api.get("unavailable_code", 404))
        url = template.replace("<appid>", str(appid))

        # INJEÇÃO DINÂMICA DA CHAVE DO MORRENUS
        if ("morrenus" in name.lower() or "morrenus.xyz" in url.lower()) and morrenus_key:
            if "api_key=" in url:
                base_url = url.split("api_key=")[0]
                url = base_url + "api_key=" + morrenus_key

        _set_download_state(
            appid, {"status": "checking", "currentApi": name, "bytesRead": 0, "totalBytes": 0}
        )
        logger.log(f"LuaTools: Trying API '{name}' -> {url}")

        try:
            headers = {"User-Agent": USER_AGENT}

            # INJEÇÃO DINÂMICA DO COOKIE DO RYUU
            if "ryuu.lol" in url:
                if ryuu_cookie:
                    logger.log(f"LuaTools: Injetando cookie do Ryuu a partir do Settings para a API '{name}'")
                    clean_cookie = ryuu_cookie
                    if not clean_cookie.startswith("session="):
                        clean_cookie = f"session={clean_cookie}"
                    headers["Cookie"] = clean_cookie
                    headers["Referer"] = "https://generator.ryuu.lol/"
                    headers["Authority"] = "generator.ryuu.lol"
                    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                    headers["Upgrade-Insecure-Requests"] = "1"
                    headers["Sec-Fetch-Dest"] = "document"
                    headers["Sec-Fetch-Mode"] = "navigate"
                    headers["Sec-Fetch-Site"] = "same-origin"
                else:
                    logger.warn("LuaTools: API Ryuu detectada, mas Cookie não está configurado no Settings!")

            if _is_download_cancelled(appid):
                logger.log(f"LuaTools: Download cancelled before contacting API '{name}'")
                return

            with client.stream("GET", url, headers=headers, follow_redirects=True, timeout=30) as resp:
                code = resp.status_code
                logger.log(f"LuaTools: API '{name}' status={code}")
                if code == unavailable_code:
                    continue
                if code != success_code:
                    if "ryuu.lol" in url and (code == 403 or code == 401):
                        logger.warn(f"LuaTools: Acesso negado no Ryuu ({code}). Verifique se o cookie expirou.")
                    elif "morrenus" in url.lower() and (code == 401):
                        logger.warn(f"LuaTools: Acesso negado no Morrenus ({code}). Verifique sua API Key no Settings.")
                    continue

                total = int(resp.headers.get("Content-Length", "0") or "0")
                _set_download_state(appid, {"status": "downloading", "bytesRead": 0, "totalBytes": total})

                with open(dest_path, "wb") as output:
                    for chunk in resp.iter_bytes():
                        if not chunk: continue
                        if _is_download_cancelled(appid): raise RuntimeError("cancelled")
                        output.write(chunk)
                        state = _get_download_state(appid)
                        read = int(state.get("bytesRead", 0)) + len(chunk)
                        _set_download_state(appid, {"bytesRead": read})
                        if _is_download_cancelled(appid): raise RuntimeError("cancelled")
                logger.log(f"LuaTools: Download complete -> {dest_path}")

                if _is_download_cancelled(appid): raise RuntimeError("cancelled")

                try:
                    with open(dest_path, "rb") as fh:
                        magic = fh.read(4)
                        if magic not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
                            file_size = os.path.getsize(dest_path)
                            with open(dest_path, "rb") as check_f:
                                preview = check_f.read(512)
                                content_preview = preview[:100].decode("utf-8", errors="ignore")
                            logger.warn(f"LuaTools: API '{name}' returned non-zip file")
                            if "Login required" in content_preview or "Sign in" in content_preview:
                                logger.error("LuaTools: O site pediu login. Cookie inválido.")
                            try: os.remove(dest_path)
                            except Exception: pass
                            continue
                except FileNotFoundError:
                    continue
                except Exception as validation_exc:
                    logger.warn(f"LuaTools: File validation failed for API '{name}': {validation_exc}")
                    try: os.remove(dest_path)
                    except Exception: pass
                    continue

                try:
                    if _is_download_cancelled(appid): raise RuntimeError("cancelled")
                    _set_download_state(appid, {"status": "processing"})
                    _process_and_install_lua(appid, dest_path)
                    if _is_download_cancelled(appid): raise RuntimeError("cancelled")
                    try:
                        fetched_name = _fetch_app_name(appid) or f"UNKNOWN ({appid})"
                        _append_loaded_app(appid, fetched_name)
                        _log_appid_event(f"ADDED - {name}", appid, fetched_name)
                    except Exception: pass
                    _set_download_state(appid, {"status": "done", "success": True, "api": name})
                    return
                except Exception as install_exc:
                    if isinstance(install_exc, RuntimeError) and str(install_exc) == "cancelled":
                        try:
                            if os.path.exists(dest_path): os.remove(dest_path)
                        except Exception: pass
                        return
                    logger.warn(f"LuaTools: Processing failed -> {install_exc}")
                    _set_download_state(appid, {"status": "failed", "error": f"Processing failed: {install_exc}"})
                    try: os.remove(dest_path)
                    except Exception: pass
                    return
        except RuntimeError as cancel_exc:
            if str(cancel_exc) == "cancelled":
                try:
                    if os.path.exists(dest_path): os.remove(dest_path)
                except Exception: pass
                return
            logger.warn(f"LuaTools: Runtime error during download for appid={appid}: {cancel_exc}")
            _set_download_state(appid, {"status": "failed", "error": str(cancel_exc)})
            return
        except Exception as err:
            logger.warn(f"LuaTools: API '{name}' failed with error: {err}")
            continue

    _set_download_state(appid, {"status": "failed", "error": "Not available on any API"})

def start_add_via_luatools(appid: int) -> str:
    try: appid = int(appid)
    except Exception: return json.dumps({"success": False, "error": "Invalid appid"})
    logger.log(f"LuaTools: StartAddViaLuaTools appid={appid}")
    _set_download_state(appid, {"status": "queued", "bytesRead": 0, "totalBytes": 0})
    thread = threading.Thread(target=_download_zip_for_app, args=(appid,), daemon=True)
    thread.start()
    return json.dumps({"success": True})

def get_add_status(appid: int) -> str:
    try: appid = int(appid)
    except Exception: return json.dumps({"success": False, "error": "Invalid appid"})
    state = _get_download_state(appid)
    return json.dumps({"success": True, "state": state})

def read_loaded_apps() -> str:
    try:
        path = _loaded_apps_path()
        entries = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle.read().splitlines():
                    if ":" in line:
                        appid_str, name = line.split(":", 1)
                        if appid_str.strip().isdigit() and name.strip():
                            entries.append({"appid": int(appid_str.strip()), "name": name.strip()})
        return json.dumps({"success": True, "apps": entries})
    except Exception as exc: return json.dumps({"success": False, "error": str(exc)})

def dismiss_loaded_apps() -> str:
    try:
        path = _loaded_apps_path()
        if os.path.exists(path): os.remove(path)
        return json.dumps({"success": True})
    except Exception as exc: return json.dumps({"success": False, "error": str(exc)})

def delete_luatools_for_app(appid: int) -> str:
    try: appid = int(appid)
    except Exception: return json.dumps({"success": False, "error": "Invalid appid"})

    base = detect_steam_install_path() or Millennium.steam_path()
    target_dir = os.path.join(base or "", "config", "stplug-in")
    paths = [os.path.join(target_dir, f"{appid}.lua"), os.path.join(target_dir, f"{appid}.lua.disabled")]
    deleted = []
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                deleted.append(path)
        except Exception as exc: logger.warn(f"LuaTools: Failed to delete {path}: {exc}")
    try:
        name = _get_loaded_app_name(appid) or _fetch_app_name(appid) or f"UNKNOWN ({appid})"
        _remove_loaded_app(appid)
        if deleted: _log_appid_event("REMOVED", appid, name)
    except Exception: pass
    return json.dumps({"success": True, "deleted": deleted, "count": len(deleted)})

def get_icon_data_url() -> str:
    try:
        steam_ui_path = os.path.join(Millennium.steam_path(), "steamui", WEBKIT_DIR_NAME)
        icon_path = os.path.join(steam_ui_path, WEB_UI_ICON_FILE)
        if not os.path.exists(icon_path): icon_path = public_path(WEB_UI_ICON_FILE)
        with open(icon_path, "rb") as handle: data = handle.read()
        b64 = base64.b64encode(data).decode("ascii")
        return json.dumps({"success": True, "dataUrl": f"data:image/png;base64,{b64}"})
    except Exception as exc: return json.dumps({"success": False, "error": str(exc)})

def has_luatools_for_app(appid: int) -> str:
    try: appid = int(appid)
    except Exception: return json.dumps({"success": False, "error": "Invalid appid"})
    return json.dumps({"success": True, "exists": has_lua_for_app(appid)})

def cancel_add_via_luatools(appid: int) -> str:
    try: appid = int(appid)
    except Exception: return json.dumps({"success": False, "error": "Invalid appid"})
    state = _get_download_state(appid)
    if not state or state.get("status") in {"done", "failed"}:
        return json.dumps({"success": True, "message": "Nothing to cancel"})
    _set_download_state(appid, {"status": "cancelled", "error": "Cancelled by user"})
    return json.dumps({"success": True})

def get_installed_lua_scripts() -> str:
    try:
        _preload_app_names_cache()
        base_path = detect_steam_install_path() or Millennium.steam_path()
        if not base_path: return json.dumps({"success": False, "error": "Could not find Steam installation path"})
        target_dir = os.path.join(base_path, "config", "stplug-in")
        if not os.path.exists(target_dir): return json.dumps({"success": True, "scripts": []})

        installed_scripts = []
        for filename in os.listdir(target_dir):
            if filename.endswith(".lua") or filename.endswith(".lua.disabled"):
                try:
                    appid_str = filename.replace(".lua.disabled", "").replace(".lua", "")
                    appid = int(appid_str)
                    is_disabled = filename.endswith(".lua.disabled")
                    game_name = ""
                    with APP_NAME_CACHE_LOCK: game_name = APP_NAME_CACHE.get(appid, "")
                    if not game_name: game_name = _get_loaded_app_name(appid)
                    if not game_name: game_name = f"Unknown Game ({appid})"
                    file_path = os.path.join(target_dir, filename)
                    file_stat = os.stat(file_path)
                    import datetime
                    modified_time = datetime.datetime.fromtimestamp(file_stat.st_mtime)
                    installed_scripts.append({
                        "appid": appid, "gameName": game_name, "filename": filename,
                        "isDisabled": is_disabled, "fileSize": file_stat.st_size,
                        "modifiedDate": modified_time.strftime("%Y-%m-%d %H:%M:%S"), "path": file_path
                    })
                except ValueError: continue
                except Exception as exc: logger.warn(f"LuaTools: Failed to process Lua file {filename}: {exc}")
        installed_scripts.sort(key=lambda x: x["appid"])
        return json.dumps({"success": True, "scripts": installed_scripts})
    except Exception as exc: return json.dumps({"success": False, "error": str(exc)})

__all__ = [
    "cancel_add_via_luatools",
    "delete_luatools_for_app",
    "dismiss_loaded_apps",
    "fetch_app_name",
    "get_add_status",
    "get_icon_data_url",
    "get_installed_lua_scripts",
    "has_luatools_for_app",
    "init_applist",
    "read_loaded_apps",
    "start_add_via_luatools",
    "load_launcher_path",
    "browse_for_launcher",
    "init_games_db",
    "get_games_database",
]
