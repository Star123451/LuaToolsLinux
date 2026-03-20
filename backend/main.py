import json
import os
import shutil
import sys
import webbrowser
import subprocess
import threading
import re
import platform
import stat  # <--- Importante para permissões no Linux
import json
import urllib.request

from typing import Any

import Millennium  # type: ignore
import PluginUtils  # type: ignore

from api_manifest import (
    fetch_free_apis_now as api_fetch_free_apis_now,
    get_init_apis_message as api_get_init_message,
    init_apis as api_init_apis,
    store_last_message,
)
from auto_update import (
    apply_pending_update_if_any,
    check_for_updates_now as auto_check_for_updates_now,
    restart_steam as auto_restart_steam,
    start_auto_update_background_check,
)
from config import WEBKIT_DIR_NAME, WEB_UI_ICON_FILE, WEB_UI_JS_FILE
from downloads import (
    cancel_add_via_luatools,
    delete_luatools_for_app,
    dismiss_loaded_apps,
    get_add_status,
    get_icon_data_url,
    get_installed_lua_scripts,
    has_luatools_for_app,
    init_applist,
    read_loaded_apps,
    start_add_via_luatools,
    load_launcher_path,
    browse_for_launcher,
    get_games_database,
    init_games_db,
)
from fixes import (
    apply_game_fix,
    cancel_apply_fix,
    check_for_fixes,
    get_apply_fix_status,
    get_installed_fixes,
    get_unfix_status,
    unfix_game,
    apply_linux_native_fix,
)
from utils import ensure_temp_download_dir
from http_client import close_http_client, ensure_http_client
from logger import logger as shared_logger
from paths import get_plugin_dir, public_path
from settings.manager import (
    apply_settings_changes,
    get_available_locales,
    get_settings_payload,
    get_translation_map,
)
from steam_utils import detect_steam_install_path, get_game_install_path_response, open_game_folder

logger = shared_logger

# ==========================================
#  WORKSHOP TOOL PATH (Leitura centralizada)
# ==========================================
def load_workshop_tool_path():
    try:
        from settings.manager import get_settings_payload
        settings_vals = get_settings_payload().get("values", {})
        return settings_vals.get("workshop", {}).get("workshopPath", "").strip()
    except:
        return ""

# ==========================================
#  GERENCIAMENTO DE FAKE APP ID (Atomic Write)
# ==========================================
def AddFakeAppId(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")

        if not os.path.exists(config_path):
             try:
                 os.makedirs(os.path.dirname(config_path), exist_ok=True)
                 tmp_path = config_path + ".tmp"
                 with open(tmp_path, 'w') as f:
                     f.write("FakeAppIds:\n")
                 os.replace(tmp_path, config_path)
             except:
                 return json.dumps({"success": False, "error": "Failed to create config.yaml"})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        entry_line = f"  {appid}: 480\n"

        for line in lines:
            if str(appid) in line and "480" in line:
                return json.dumps({"success": True, "message": "FakeAppId is already configured!"})

        new_lines = []
        inserted = False
        has_tag = False

        for line in lines:
            new_lines.append(line)
            if line.strip().lower().startswith("fakeappids:"):
                has_tag = True
                new_lines.append(entry_line)
                inserted = True

        if not has_tag:
            new_lines.append("\nFakeAppIds:\n")
            new_lines.append(entry_line)
        elif has_tag and not inserted:
             new_lines.append(entry_line)

        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        os.replace(tmp_path, config_path)

        logger.log(f"[LuaTools] FakeAppId 480 added for {appid}")
        return json.dumps({"success": True, "message": f"FakeAppId (480) adicionado!"})

    except Exception as e:
        logger.error(f"[LuaTools] FakeAppId Error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def RemoveFakeAppId(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "message": "Config não encontrada."})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        modified = False
        target_str = str(appid)

        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(f"{target_str}:") or stripped.startswith(f"'{target_str}':") or stripped.startswith(f'"{target_str}":')) and "480" in stripped:
                logger.log(f"[LuaTools] Removing FakeAppId for: {appid}")
                modified = True
                continue
            new_lines.append(line)

        if modified:
            tmp_path = config_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            os.replace(tmp_path, config_path)

        return json.dumps({"success": True, "message": "FakeAppId removido."})
    except Exception as e:
        logger.warn(f"[LuaTools] Error cleaning FakeAppId: {e}")
        return json.dumps({"success": False, "error": str(e)})

def CheckFakeAppIdStatus(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "exists": False})
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if f"  {appid}: 480" in content:
            return json.dumps({"success": True, "exists": True})
        return json.dumps({"success": True, "exists": False})
    except:
        return json.dumps({"success": True, "exists": False})

# ==========================================
#  GERENCIAMENTO DE TOKENS (Atomic Write)
# ==========================================
def AddGameToken(appid: int, contentScriptQuery: str = "") -> str:
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_root = os.path.dirname(backend_dir)
        json_path = os.path.join(backend_dir, "appaccesstokens.json")

        if not os.path.exists(json_path):
             json_path = os.path.join(plugin_root, "appaccesstokens.json")

        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")

        if not os.path.exists(json_path):
            return json.dumps({"success": False, "error": f"appaccesstokens.json não encontrado."})

        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        if not os.path.exists(config_path):
             tmp_path = config_path + ".tmp"
             with open(tmp_path, 'w', encoding='utf-8') as f:
                 f.write("AppTokens:\n")
             os.replace(tmp_path, config_path)

        with open(json_path, 'r', encoding='utf-8') as f:
            tokens_db = json.load(f)

        token = tokens_db.get(str(appid))

        if not token:
            return json.dumps({"success": False, "error": f"Token não encontrado para o AppID {appid}."})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        entry = f"{appid}: {token}"
        for line in lines:
            if str(appid) in line and token in line:
                return json.dumps({"success": True, "message": "O Token já está no config.yaml."})

        new_lines = []
        inserted = False
        has_tag = False

        for line in lines:
            new_lines.append(line)
            if line.strip().startswith("AppTokens:"):
                has_tag = True
                new_lines.append(f"  {entry}\n")
                inserted = True

        if not has_tag:
            new_lines.append("\nAppTokens:\n")
            new_lines.append(f"  {entry}\n")
        elif has_tag and not inserted:
             new_lines.append(f"  {entry}\n")

        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        os.replace(tmp_path, config_path)

        return json.dumps({"success": True, "message": f"Token adicionado!"})
    except Exception as e:
        logger.error(f"[LuaTools] Token Error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def RemoveGameToken(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "message": "Config não encontrada."})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        token_removed = False
        target_id_str = str(appid)

        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(f"{target_id_str}:") or
                stripped.startswith(f"'{target_id_str}':") or
                stripped.startswith(f'"{target_id_str}":')):
                logger.log(f"[LuaTools] Removendo token do config para AppID: {appid}")
                token_removed = True
                continue
            new_lines.append(line)

        if token_removed:
            tmp_path = config_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            os.replace(tmp_path, config_path)

        return json.dumps({"success": True, "message": "Token successfully removed."})
    except Exception as e:
        logger.warn(f"[LuaTools] Erro ao tentar limpar token: {e}")
        return json.dumps({"success": False, "error": str(e)})

def CheckGameTokenStatus(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "exists": False})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_tokens = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("AppTokens:"):
                in_tokens = True
                continue
            if in_tokens:
                indent = len(line) - len(line.lstrip())
                if indent <= 2 and stripped and not stripped.startswith("#"):
                    in_tokens = False
                elif stripped.startswith(f"{appid}:"):
                    return json.dumps({"success": True, "exists": True})

        return json.dumps({"success": True, "exists": False})
    except:
        return json.dumps({"success": True, "exists": False})

# ==========================================
#  LOGGER & UTILS
# ==========================================
def GetPluginDir() -> str:
    return get_plugin_dir()

class Logger:
    @staticmethod
    def log(message: str) -> str:
        shared_logger.log(f"[Frontend] {message}")
        return json.dumps({"success": True})

    @staticmethod
    def warn(message: str) -> str:
        shared_logger.warn(f"[Frontend] {message}")
        return json.dumps({"success": True})

    @staticmethod
    def error(message: str) -> str:
        shared_logger.error(f"[Frontend] {message}")
        return json.dumps({"success": True})

def _steam_ui_path() -> str:
    return os.path.join(Millennium.steam_path(), "steamui", WEBKIT_DIR_NAME)

# ==========================================
#  EXPOSED API FUNCTIONS (WRAPPERS)
# ==========================================
def GetLauncherPath(contentScriptQuery: str = "") -> str:
    path = load_launcher_path()
    return json.dumps({"success": True, "path": path})

def GetWorkshopToolPath(contentScriptQuery: str = "") -> str:
    path = load_workshop_tool_path()
    return json.dumps({"success": True, "path": path})

def BrowseForLauncher(contentScriptQuery: str = "") -> str:
    return browse_for_launcher()

def InstallDependencies(contentScriptQuery: str = "") -> str:
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_root = current_dir

        for _ in range(2):
            if os.path.exists(os.path.join(plugin_root, "plugin.json")):
                break
            parent = os.path.dirname(plugin_root)
            if parent == plugin_root: break
            plugin_root = parent

        venv_dir = os.path.join(plugin_root, ".venv")
        requirements_file = os.path.join(plugin_root, "requirements.txt")

        if not os.path.exists(requirements_file):
             requirements_file = os.path.join(current_dir, "requirements.txt")

        if sys.platform == "win32":
            venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(venv_dir, "bin", "python")

        if not os.path.exists(requirements_file):
            return json.dumps({"success": False, "error": "Arquivo requirements.txt não encontrado!"})

        if not os.path.exists(venv_dir) or not os.path.exists(venv_python):
            logger.log(f"[LuaTools] Criando venv em: {venv_dir}")
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

        logger.log(f"[LuaTools] Instalando dependências...")
        subprocess.check_call([venv_python, "-m", "pip", "install", "-r", requirements_file])

        return json.dumps({"success": True, "message": "Dependencies installed successfully!"})

    except subprocess.CalledProcessError as e:
        logger.error(f"[LuaTools] Falha no PIP: {e}")
        return json.dumps({"success": False, "error": "Falha ao baixar bibliotecas (Verifique internet/proxy)"})
    except Exception as e:
        logger.error(f"[LuaTools] Erro geral: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})

# ==========================================
#  WORKSHOP DOWNLOADER LOGIC
# ==========================================

workshop_state = {
    "status": "idle",
    "progress": 0.0,
    "message": "",
    "download_path": "",
    "process": None
}

def _run_depot_downloader_workshop(appid: str, pubfile_id: str, download_dir: str):
    global workshop_state

    exe_path = None
    used_source = "Local"
    custom_path = load_workshop_tool_path()

    # 1. Tenta encontrar o executável (Mais robusto para pastas)
    if custom_path and os.path.exists(custom_path):
        if os.path.isdir(custom_path):
            for name in ["DepotDownloaderMod", "DepotDownloaderMod.exe", "DepotDownloader", "DepotDownloader.exe"]:
                potential_exe = os.path.join(custom_path, name)
                if os.path.exists(potential_exe):
                    exe_path = potential_exe
                    used_source = "Custom (Config)"
                    break
        elif os.path.isfile(custom_path):
            exe_path = custom_path
            used_source = "Custom (Config)"

    if not exe_path:
        try:
            base_path = os.path.join(get_plugin_dir(), "backend")
        except:
            base_path = os.path.dirname(os.path.abspath(__file__))

        if sys.platform == "win32":
            exe_path = os.path.join(base_path, "DepotDownloaderMod.exe")
        else:
            exe_path = os.path.join(base_path, "DepotDownloaderMod")

    if sys.platform != "win32" and os.path.exists(exe_path):
        try:
            st = os.stat(exe_path)
            os.chmod(exe_path, st.st_mode | stat.S_IEXEC)
        except Exception as e:
            logger.warn(f"Failed to chmod DepotDownloader: {e}")

    if not os.path.exists(exe_path):
        workshop_state["status"] = "failed"
        workshop_state["message"] = f"Executable not found: {exe_path}"
        logger.error(f"DepotDownloader not found at {exe_path}")
        return

    cmd = [
        exe_path,
        "-app", str(appid),
        "-pubfile", str(pubfile_id),
        "-dir", download_dir,
        "-max-downloads", "8"
    ]

    try:
        workshop_state["status"] = "downloading"
        workshop_state["message"] = f"Starting download ({used_source})..."
        workshop_state["progress"] = 0.0

        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        else:
            creation_flags = 0

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=creation_flags
        )
        workshop_state["process"] = process

        percent_regex = re.compile(r"(\d{1,3}\.\d{2})%")
        last_output_line = "Unknown Error"
        output_log = []

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            if line:
                clean_line = line.strip()
                if clean_line:
                    output_log.append(clean_line.lower())

                if not "%" in clean_line:
                     workshop_state["message"] = clean_line
                     if clean_line:
                        last_output_line = clean_line

                match = percent_regex.search(clean_line)
                if match:
                    try:
                        p = float(match.group(1))
                        workshop_state["progress"] = p
                        workshop_state["message"] = f"Downloading: {p}%"
                    except:
                        pass

        rc = process.poll()
        workshop_state["process"] = None

        has_valid_files = False
        if os.path.exists(download_dir):
            ignored_names = {".depotdownloader", "depotdownloader.config", ".ds_store", "thumbs.db"}
            total_size = 0
            file_count = 0

            for root, dirs, files in os.walk(download_dir):
                dirs[:] = [d for d in dirs if d.lower() not in ignored_names]
                for f in files:
                    if f.lower() not in ignored_names:
                        fp = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fp)
                            total_size += size
                            file_count += 1
                        except:
                            pass

            if file_count > 0 and total_size > 0:
                has_valid_files = True

        full_log_str = "\n".join(output_log)
        auth_error = "access denied" in full_log_str or "manifest not available" in full_log_str or "no subscription" in full_log_str or "purchase" in full_log_str

        if rc == 0 and has_valid_files and not auth_error:
            workshop_state["status"] = "done"
            workshop_state["message"] = "Download Complete!"
            workshop_state["progress"] = 100.0
            OpenGameFolder(download_dir)
        else:
            workshop_state["status"] = "failed"
            if auth_error or (rc == 0 and not has_valid_files):
                workshop_state["message"] = "LOGIN_REQUIRED"
                workshop_state["error"] = "Download resulted in empty folder (Anonymous restriction)"
            else:
                workshop_state["message"] = f"Error: {last_output_line}"

    except Exception as e:
        workshop_state["status"] = "failed"
        workshop_state["message"] = f"Internal Error: {str(e)}"
        logger.error(f"Workshop download error: {e}")

def StartWorkshopDownloadParams(appid: int, pubfile_id: int, contentScriptQuery: str = "") -> str:
    global workshop_state

    if workshop_state["status"] == "downloading":
        return json.dumps({"success": False, "error": "Download already in progress."})

    try:
        steam_root = Millennium.steam_path()
        download_dir = os.path.join(steam_root, "steamapps", "workshop", "content", str(appid), str(pubfile_id))
    except Exception as e:
        logger.error(f"Error resolving paths: {e}")
        return json.dumps({"success": False, "error": "Path resolution error"})

    try:
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
    except Exception as e:
        return json.dumps({"success": False, "error": f"Failed to create dir: {e}"})

    workshop_state = {
        "status": "downloading",
        "progress": 0,
        "message": "Initializing...",
        "download_path": download_dir,
        "process": None
    }

    t = threading.Thread(target=_run_depot_downloader_workshop, args=(appid, pubfile_id, download_dir))
    t.daemon = True
    t.start()

    return json.dumps({"success": True, "message": "Download started"})

def GetWorkshopDownloadStatus(contentScriptQuery: str = "") -> str:
    safe_state = workshop_state.copy()
    if "process" in safe_state:
        del safe_state["process"]
    return json.dumps(safe_state)

def CancelWorkshopDownload(contentScriptQuery: str = "") -> str:
    global workshop_state
    if workshop_state["process"]:
        try:
            workshop_state["process"].kill()
            workshop_state["status"] = "cancelled"
            workshop_state["message"] = "Cancelado pelo usuário."
        except:
            pass
    return json.dumps({"success": True})

# ==========================================
#  CORE FUNCTIONS
# ==========================================
def _copy_webkit_files() -> None:
    plugin_dir = get_plugin_dir()
    steam_ui_path = _steam_ui_path()
    os.makedirs(steam_ui_path, exist_ok=True)

    js_src = public_path(WEB_UI_JS_FILE)
    js_dst = os.path.join(steam_ui_path, WEB_UI_JS_FILE)
    logger.log(f"Copying LuaTools web UI from {js_src} to {js_dst}")
    try:
        shutil.copy(js_src, js_dst)
    except Exception as exc:
        logger.error(f"Failed to copy LuaTools web UI: {exc}")

    icon_src = public_path(WEB_UI_ICON_FILE)
    icon_dst = os.path.join(steam_ui_path, WEB_UI_ICON_FILE)
    if os.path.exists(icon_src):
        try:
            shutil.copy(icon_src, icon_dst)
            logger.log(f"Copied LuaTools icon to {icon_dst}")
        except Exception as exc:
            logger.error(f"Failed to copy LuaTools icon: {exc}")
    else:
        logger.warn(f"LuaTools icon not found at {icon_src}")


def _inject_webkit_files() -> None:
    js_path = os.path.join(WEBKIT_DIR_NAME, WEB_UI_JS_FILE)
    Millennium.add_browser_js(js_path)
    logger.log(f"LuaTools injected web UI: {js_path}")

def InitApis(contentScriptQuery: str = "") -> str:
    return api_init_apis(contentScriptQuery)

def GetInitApisMessage(contentScriptQuery: str = "") -> str:
    return api_get_init_message(contentScriptQuery)

def FetchFreeApisNow(contentScriptQuery: str = "") -> str:
    return api_fetch_free_apis_now(contentScriptQuery)

def CheckForUpdatesNow(contentScriptQuery: str = "") -> str:
    result = auto_check_for_updates_now()
    return json.dumps(result)

def RestartSteam(contentScriptQuery: str = "") -> str:
    success = auto_restart_steam()
    if success: return json.dumps({"success": True})
    return json.dumps({"success": False, "error": "Failed to restart Steam"})

def HasLuaToolsForApp(appid: int, contentScriptQuery: str = "") -> str:
    return has_luatools_for_app(appid)

def StartAddViaLuaTools(appid: int, contentScriptQuery: str = "") -> str:
    return start_add_via_luatools(appid)

def GetAddViaLuaToolsStatus(appid: int, contentScriptQuery: str = "") -> str:
    return get_add_status(appid)

def CancelAddViaLuaTools(appid: int, contentScriptQuery: str = "") -> str:
    return cancel_add_via_luatools(appid)

def GetIconDataUrl(contentScriptQuery: str = "") -> str:
    return get_icon_data_url()

def ReadLoadedApps(contentScriptQuery: str = "") -> str:
    return read_loaded_apps()

def DismissLoadedApps(contentScriptQuery: str = "") -> str:
    return dismiss_loaded_apps()

def DeleteLuaToolsForApp(appid: int, contentScriptQuery: str = "") -> str:
    return delete_luatools_for_app(appid)

def CheckForFixes(appid: int, contentScriptQuery: str = "") -> str:
    return check_for_fixes(appid)

def ApplyGameFix(appid: int, downloadUrl: str, installPath: str, fixType: str = "", gameName: str = "", contentScriptQuery: str = "") -> str:
    return apply_game_fix(appid, downloadUrl, installPath, fixType, gameName)

def GetApplyFixStatus(appid: int, contentScriptQuery: str = "") -> str:
    return get_apply_fix_status(appid)

def CancelApplyFix(appid: int, contentScriptQuery: str = "") -> str:
    return cancel_apply_fix(appid)

def UnFixGame(appid: int, installPath: str = "", fixDate: str = "", contentScriptQuery: str = "") -> str:
    RemoveGameToken(appid)
    RemoveFakeAppId(appid)
    return unfix_game(appid, installPath, fixDate)

def GetUnfixStatus(appid: int, contentScriptQuery: str = "") -> str:
    return get_unfix_status(appid)

def ApplyLinuxNativeFix(appid: int, installPath: str, contentScriptQuery: str = "") -> str:
    return apply_linux_native_fix(installPath)

def GetInstalledFixes(contentScriptQuery: str = "") -> str:
    return get_installed_fixes()

def GetInstalledLuaScripts(contentScriptQuery: str = "") -> str:
    return get_installed_lua_scripts()

def GetGameInstallPath(appid: int, contentScriptQuery: str = "") -> str:
    result = get_game_install_path_response(appid)
    return json.dumps(result)

def OpenGameFolder(path: str, contentScriptQuery: str = "") -> str:
    success = open_game_folder(path)
    if success: return json.dumps({"success": True})
    return json.dumps({"success": False, "error": "Failed to open path"})

def OpenExternalUrl(url: str, contentScriptQuery: str = "") -> str:
    try:
        value = str(url or "").strip()
        if not (value.startswith("http://") or value.startswith("https://")):
            return json.dumps({"success": False, "error": "Invalid URL"})
        if sys.platform.startswith("win"):
            try: os.startfile(value)
            except Exception: webbrowser.open(value)
        else:
            webbrowser.open(value)
        return json.dumps({"success": True})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

def GetSettingsConfig(contentScriptQuery: str = "") -> str:
    try:
        payload = get_settings_payload()
        response = {
            "success": True,
            "schemaVersion": payload.get("version"),
            "schema": payload.get("schema", []),
            "values": payload.get("values", {}),
            "language": payload.get("language"),
            "locales": payload.get("locales", []),
            "translations": payload.get("translations", {}),
        }
        return json.dumps(response)
    except Exception as exc:
        logger.warn(f"LuaTools: GetSettingsConfig failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})

def GetThemes(contentScriptQuery: str = "") -> str:
    try:
        themes_path = os.path.join(get_plugin_dir(), 'public', 'themes', 'themes.json')
        if os.path.exists(themes_path):
            with open(themes_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                return json.dumps({"success": True, "themes": data})
        else:
            return json.dumps({"success": True, "themes": []})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

def ApplySettingsChanges(contentScriptQuery: str = "", changesJson: str = "") -> str:
    try:
        payload: Any = {}
        if changesJson:
            try: payload = json.loads(changesJson)
            except Exception: return json.dumps({"success": False, "error": "Invalid JSON payload"})

        if not isinstance(payload, dict):
            return json.dumps({"success": False, "error": "Invalid payload format"})

        # ÚNICA INTERCEPTAÇÃO NECESSÁRIA (Modifica um YAML externo do sistema)
        if "slssteam" in payload and "playNotOwnedGames" in payload["slssteam"]:
            SetSLSPlayStatus(payload["slssteam"]["playNotOwnedGames"])

        # O Resto (Ryu, Morrenus, Launcher, DepotDownloader) será gravado lindamente
        # e automaticamente no settings.json pelo gerenciador oficial!

        result = apply_settings_changes(payload)
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

def GetAvailableLocales(contentScriptQuery: str = "") -> str:
    try:
        locales = get_available_locales()
        return json.dumps({"success": True, "locales": locales})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

def GetTranslations(contentScriptQuery: str = "", language: str = "", **kwargs: Any) -> str:
    try:
        if not language and "language" in kwargs:
            language = kwargs["language"]
        bundle = get_translation_map(language)
        bundle["success"] = True
        return json.dumps(bundle)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

def GetGamesDatabase(contentScriptQuery: str = "") -> str:
    return get_games_database()

# ==========================================
#  FUNÇÕES AUXILIARES E LÓGICA DE LIMPEZA
# ==========================================

def _cleanup_nested_plugin_folder():
    """Merge nested plugin folders into root and remove the nested copy."""
    try:
        plugin_root = get_plugin_dir()
        candidate_names = [
            "luatools",
            "ltsteamplugin",
            "ltstools",
            "lts",
            "LuaToolsLinux",
        ]

        for name in candidate_names:
            nested_folder = os.path.join(plugin_root, name)
            if not os.path.isdir(nested_folder):
                continue

            has_plugin_json = os.path.isfile(os.path.join(nested_folder, "plugin.json"))
            has_backend = os.path.isdir(os.path.join(nested_folder, "backend"))
            has_public = os.path.isdir(os.path.join(nested_folder, "public"))
            if not (has_plugin_json or (has_backend and has_public)):
                continue

            logger.log(
                f"LuaTools: Nested plugin folder detected at {nested_folder}. Merging into plugin root..."
            )

            for entry in os.listdir(nested_folder):
                src = os.path.join(nested_folder, entry)
                dst = os.path.join(plugin_root, entry)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            shutil.rmtree(nested_folder, ignore_errors=True)
            logger.log(f"LuaTools: Nested folder merged and removed: {nested_folder}")
    except Exception as e:
        logger.warn(f"LuaTools: Falha ao tentar limpar pasta aninhada: {e}")

def load_workshop_tool_path():
    try:
        from settings.manager import get_settings_payload
        settings_vals = get_settings_payload().get("values", {})
        return settings_vals.get("workshop", {}).get("workshopPath", "").strip()
    except:
        return ""

# ==========================================
#  PLUGIN CLASS (Brain do Sistema)
# ==========================================

class Plugin:
    def _front_end_loaded(self):
        _copy_webkit_files()

    def _load(self):
        # 1. Limpa a pasta duplicada IMEDIATAMENTE antes de carregar o resto
        _cleanup_nested_plugin_folder()

        logger.log(f"bootstrapping LuaTools plugin, millennium {Millennium.version()}")
        try:
            detect_steam_install_path()
        except Exception as exc:
            logger.warn(f"LuaTools: steam path detection failed: {exc}")

        ensure_http_client("InitApis")
        ensure_temp_download_dir()

        _copy_webkit_files()
        _inject_webkit_files()
        Millennium.ready()

        def _background_init():
            try:
                message = apply_pending_update_if_any()
                if message: store_last_message(message)
            except Exception: pass
            try: init_applist()
            except Exception: pass
            try: init_games_db()
            except Exception: pass
            try: InitApis("boot")
            except Exception: pass
            try: start_auto_update_background_check()
            except Exception: pass

        t = threading.Thread(target=_background_init, daemon=True, name="LuaTools-init")
        t.start()

    def _unload(self):
        logger.log("unloading")
        close_http_client("InitApis")

plugin = Plugin()

def GetProtonDBStatus(appid: int, contentScriptQuery: str = "") -> str:
    try:
        url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
        client = ensure_http_client("ProtonDB")
        resp = client.get(url, timeout=3)
        if resp.status_code == 200:
            return json.dumps({"success": True, "data": resp.json()})
        elif resp.status_code == 404:
            return json.dumps({"success": False, "error": "Not Found"})
        else:
            return json.dumps({"success": False, "error": f"Status {resp.status_code}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

# ==========================================
#  GERENCIAMENTO DE DLCS (Atomic Write)
# ==========================================
def _fetch_dlc_list(appid: int):
    try:
        client = ensure_http_client("LuaTools: DLC Fetcher")
        url_list = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic,dlc"
        resp = client.get(url_list, timeout=10)
        data = resp.json()

        if not data or str(appid) not in data or not data[str(appid)]['success']: return []

        game_data = data[str(appid)]['data']
        dlc_ids = game_data.get('dlc', [])
        if not dlc_ids: return []

        dlc_info = []
        chunk_size = 10
        for i in range(0, len(dlc_ids), chunk_size):
            chunk = dlc_ids[i:i + chunk_size]
            ids_str = ",".join(map(str, chunk))
            try:
                url_names = f"https://store.steampowered.com/api/appdetails?appids={ids_str}&filters=basic"
                resp_names = client.get(url_names, timeout=10)
                names_data = resp_names.json()

                for d_id in chunk:
                    name = f"DLC {d_id}"
                    if names_data and str(d_id) in names_data and names_data[str(d_id)]['success']:
                        name = names_data[str(d_id)]['data']['name']
                    name = name.replace('"', '').replace("'", "")
                    dlc_info.append((d_id, name))
            except:
                for d_id in chunk: dlc_info.append((d_id, f"DLC {d_id}"))
        return dlc_info
    except Exception as e:
        return []

def AddGameDLCs(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": False, "error": "Config não encontrada. Instale o SLSsteam primeiro."})

        dlcs = _fetch_dlc_list(appid)
        if not dlcs: return json.dumps({"success": False, "error": "Nenhuma DLC encontrada."})

        with open(config_path, 'r', encoding='utf-8') as f: lines = f.readlines()

        in_dlc_data = False
        for line in lines:
            if line.strip().startswith("DlcData:"): in_dlc_data = True
            if in_dlc_data and line.strip().startswith(f"{appid}:"):
                return json.dumps({"success": True, "message": "DLCs já configuradas!"})

        new_block = [f"  {appid}:\n"]
        for d_id, d_name in dlcs: new_block.append(f"    {d_id}: \"{d_name}\"\n")

        new_lines = []
        inserted = False
        has_tag = False
        for line in lines:
            new_lines.append(line)
            if line.strip().startswith("DlcData:"):
                has_tag = True
                new_lines.extend(new_block)
                inserted = True

        if not has_tag:
            new_lines.append("\nDlcData:\n")
            new_lines.extend(new_block)

        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
        os.replace(tmp_path, config_path)
        return json.dumps({"success": True, "message": f"{len(dlcs)} DLCs adicionadas!"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def RemoveGameDLCs(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return json.dumps({"success": True})
        with open(config_path, 'r', encoding='utf-8') as f: lines = f.readlines()

        new_lines = []
        in_target = False
        for line in lines:
            if line.strip().startswith(f"{appid}:"):
                in_target = True
                continue
            if in_target:
                if len(line) - len(line.lstrip()) <= 2 and line.strip():
                    in_target = False
                    new_lines.append(line)
                continue
            new_lines.append(line)

        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
        os.replace(tmp_path, config_path)
        return json.dumps({"success": True, "message": "DLCs removidas."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def CheckGameDLCsStatus(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return json.dumps({"success": True, "exists": False})
        with open(config_path, 'r', encoding='utf-8') as f: content = f.read()
        if f"\n  {appid}:" in content or f"  {appid}:" in content:
             return json.dumps({"success": True, "exists": True})
        return json.dumps({"success": True, "exists": False})
    except:
        return json.dumps({"success": True, "exists": False})

def CheckGameUpdate(appid: int, contentScriptQuery: str = "") -> str:
    try:
        accela_path = load_launcher_path()
        if not accela_path or not os.path.exists(accela_path):
            default_accela = os.path.expanduser("~/.local/share/ACCELA/run.sh")
            if os.path.exists(default_accela): accela_path = default_accela
            else: return json.dumps({"success": False, "status": "Launcher Config Missing", "color": "#FF5252"})

        if os.path.isfile(accela_path): accela_path = os.path.dirname(accela_path)

        depots_dir = os.path.join(accela_path, "depots")
        depot_file = os.path.join(depots_dir, f"{appid}.depot")

        if not os.path.exists(depot_file):
            return json.dumps({"success": True, "status": "Not Managed by ACCELA", "color": "#777"})

        local_manifest = ""
        local_depot_id = ""
        try:
            with open(depot_file, 'r', encoding='utf-8') as f:
                parts = f.read().strip().split(':')
                if len(parts) >= 2:
                    local_manifest = parts[-1].strip()
                    local_depot_id = "".join(filter(str.isdigit, parts[-2]))
        except: return json.dumps({"success": False, "status": "Read Error", "color": "#FF5252"})

        if not local_manifest or not local_depot_id:
            return json.dumps({"success": False, "status": "Invalid Depot File", "color": "#FF5252"})

        client = ensure_http_client("LuaTools: Update Checker")
        url = f"https://api.steamcmd.net/v1/info/{appid}"
        resp = client.get(url, timeout=5)

        if resp.status_code != 200: return json.dumps({"success": False, "status": "API Error", "color": "#FF5252"})

        data = resp.json()
        if data.get('status') != 'success': return json.dumps({"success": False, "status": "API Failed", "color": "#FF5252"})

        app_data = data['data'].get(str(appid), {})
        depots_data = app_data.get('depots', {})

        if local_depot_id in depots_data:
            manifests = depots_data[local_depot_id].get('manifests', {})
            if 'public' in manifests:
                remote_manifest = manifests['public'].get('gid')
                if str(local_manifest) == str(remote_manifest):
                    return json.dumps({"success": True, "status": "Up to Date", "color": "#4CAF50"})
                else:
                    return json.dumps({"success": True, "status": "Update Available", "color": "#00FF00"})

        return json.dumps({"success": True, "status": "Unknown Version", "color": "#FF5252"})
    except Exception as e:
        return json.dumps({"success": False, "status": "Error", "color": "#FF5252"})

def _get_sls_state_file():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(backend_dir), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "sls_state.json")

def GetSLSPlayStatus(contentScriptQuery: str = "") -> str:
    try:
        state_file = _get_sls_state_file()
        is_enabled = False
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                is_enabled = json.load(f).get("enabled", False)
        else:
            config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    is_enabled = "playnotownedgames: yes" in f.read().lower()
        return json.dumps({"success": True, "enabled": is_enabled})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def SetSLSPlayStatus(enabled, contentScriptQuery: str = "") -> str:
    try:
        is_enabled = str(enabled).lower() in ['true', '1', 'yes', 'y']
        state_file = _get_sls_state_file()
        with open(state_file, 'w', encoding='utf-8') as f: json.dump({"enabled": is_enabled}, f)

        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return json.dumps({"success": True})

        with open(config_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        new_val = "yes" if is_enabled else "no"
        new_lines, found_play = [], False

        for line in lines:
            if line.strip().lower().startswith("playnotownedgames:"):
                new_lines.append(f"PlayNotOwnedGames: {new_val}\n")
                found_play = True
            elif line.strip().lower().startswith("notifications:"):
                new_lines.append("Notifications: no\n")
            else:
                new_lines.append(line)

        if not found_play: new_lines.append(f"PlayNotOwnedGames: {new_val}\n")

        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
        os.replace(tmp_path, config_path)
        return json.dumps({"success": True})
    except Exception as e: return json.dumps({"success": False, "error": str(e)})

def _remove_from_additional_apps(appid: int):
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return

        with open(config_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        new_lines, modified, target_str = [], False, f"- {appid}"

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(target_str):
                rem = stripped[len(target_str):]
                if not rem or rem[0] in " \t#":
                    modified = True
                    continue
            new_lines.append(line)

        if modified:
            tmp_path = config_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
            os.replace(tmp_path, config_path)
    except Exception: pass

def UninstallGameFull(appid: int, contentScriptQuery: str = "") -> str:
    try:
        path_info = get_game_install_path_response(appid)
        install_path = path_info.get("installPath") if isinstance(path_info, dict) else None

        if install_path and os.path.exists(install_path):
            shutil.rmtree(install_path, ignore_errors=True)
            steamapps_dir = os.path.dirname(os.path.dirname(install_path))
            acf_file = os.path.join(steamapps_dir, f"appmanifest_{appid}.acf")
            if os.path.exists(acf_file): os.remove(acf_file)

        delete_luatools_for_app(appid)
        _remove_from_additional_apps(appid)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

plugin = Plugin()
