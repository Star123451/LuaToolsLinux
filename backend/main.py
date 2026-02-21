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
    # --- NOVOS IMPORTS DE DOWNLOADS ---
    save_ryu_cookie,
    update_morrenus_key,
    save_launcher_path_config,
    load_launcher_path,
    browse_for_launcher,
    # --- STATUS PILL IMPORTS ---
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
    # --- NOVO IMPORT DE FIXES ---
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
#  CONFIGURAÇÃO DO WORKSHOP TOOL (DepotDownloader)
# ==========================================

def _get_workshop_config_file():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.path.dirname(backend_dir)
    data_dir = os.path.join(plugin_root, "data")

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, "workshop_path.txt")

def save_workshop_tool_path(path: str):
    try:
        config_file = _get_workshop_config_file()
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(path.strip())
        return {"success": True, "message": "Path saved"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def load_workshop_tool_path():
    try:
        config_file = _get_workshop_config_file()
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except:
        pass
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
    """Verifica se o FakeAppId já existe no config."""
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
    """Verifica se o Token já existe no config."""
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

def SaveRyuuCookie(cookie: str, contentScriptQuery: str = "") -> str:
    return save_ryu_cookie(cookie)

def UpdateMorrenusKey(key: str, contentScriptQuery: str = "") -> str:
    return update_morrenus_key(key)

def GetLauncherPath(contentScriptQuery: str = "") -> str:
    path = load_launcher_path()
    accela_default = os.path.expanduser("~/.local/share/ACCELA/run.sh")

    # Se o caminho salvo for do Bifrost OU estiver vazio OU não existir, força o ACCELA
    if not path or "Bifrost" in path or not os.path.exists(path):
        path = accela_default if os.path.exists(accela_default) else "/home/deck/.local/share/ACCELA/run.sh"
        # Opcional: Descomente a linha abaixo se quiser que ele salve no .txt automaticamente
        # save_launcher_path_config(path)

    return json.dumps({"success": True, "path": path})

def SaveLauncherPath(path: str, contentScriptQuery: str = "") -> str:
    return save_launcher_path_config(path)

def GetWorkshopToolPath(contentScriptQuery: str = "") -> str:
    path = load_workshop_tool_path()
    return json.dumps({"success": True, "path": path})

def SaveWorkshopToolPath(path: str, contentScriptQuery: str = "") -> str:
    result = save_workshop_tool_path(path)
    return json.dumps(result)

def BrowseForLauncher(contentScriptQuery: str = "") -> str:
    return browse_for_launcher()

def InstallDependencies(contentScriptQuery: str = "") -> str:
    """Instala dependências de forma compatível com Windows e Linux."""
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

    # 1. Tenta encontrar o executável (Custom ou Padrão)
    if custom_path and os.path.exists(custom_path):
        if os.path.isdir(custom_path):
            if sys.platform == "win32":
                potential_exe = os.path.join(custom_path, "DepotDownloaderMod.exe")
            else:
                potential_exe = os.path.join(custom_path, "DepotDownloaderMod")

            if os.path.exists(potential_exe):
                exe_path = potential_exe
                used_source = "Custom (Config)"
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

    # Garante permissão de execução no Linux
    if sys.platform != "win32" and os.path.exists(exe_path):
        try:
            st = os.stat(exe_path)
            os.chmod(exe_path, st.st_mode | stat.S_IEXEC)
        except Exception as e:
            logger.warn(f"Failed to chmod DepotDownloader: {e}")

    if not os.path.exists(exe_path):
        workshop_state["status"] = "failed"
        workshop_state["message"] = f"Executable not found: {exe_path}"
        logger.error(f"DepotDownloader not found")
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

        # Guardamos o log completo para procurar erros de autenticação que não geram crash
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

        # --- VERIFICAÇÃO RIGOROSA DE SUCESSO ---
        has_valid_files = False

        if os.path.exists(download_dir):
            # Lista ficheiros ignorando lixo do sistema ou do downloader
            ignored_names = {".depotdownloader", "depotdownloader.config", ".ds_store", "thumbs.db"}

            # Verifica se existe algum ficheiro válido e com tamanho > 0
            total_size = 0
            file_count = 0

            for root, dirs, files in os.walk(download_dir):
                # Filtra pastas ignoradas
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

        # Verifica erros conhecidos no log
        full_log_str = "\n".join(output_log)
        auth_error = "access denied" in full_log_str or "manifest not available" in full_log_str or "no subscription" in full_log_str or "purchase" in full_log_str

        # Lógica Final:
        # Sucesso APENAS SE: Código 0 E Ficheiros Válidos Existem E Sem Erro de Auth
        if rc == 0 and has_valid_files and not auth_error:
            workshop_state["status"] = "done"
            workshop_state["message"] = "Download Complete!"
            workshop_state["progress"] = 100.0
            OpenGameFolder(download_dir)
        else:
            workshop_state["status"] = "failed"

            # Se falhou por autenticação ou se diz que acabou mas a pasta está "vazia" (proteção anónima)
            if auth_error or (rc == 0 and not has_valid_files):
                workshop_state["message"] = "LOGIN_REQUIRED" # Código para o JS exibir o alerta em inglês
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
    if success:
        return json.dumps({"success": True})
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

# --- ATUALIZAÇÃO DA FUNÇÃO UNFIX (COMBINADA) ---
def UnFixGame(appid: int, installPath: str = "", fixDate: str = "", contentScriptQuery: str = "") -> str:
    # 1. Remove Token
    RemoveGameToken(appid)
    # 2. Remove FakeAppId
    RemoveFakeAppId(appid)
    # 3. Limpa arquivos
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
    if success:
        return json.dumps({"success": True})
    return json.dumps({"success": False, "error": "Failed to open path"})


def OpenExternalUrl(url: str, contentScriptQuery: str = "") -> str:
    try:
        value = str(url or "").strip()
        if not (value.startswith("http://") or value.startswith("https://")):
            return json.dumps({"success": False, "error": "Invalid URL"})
        if sys.platform.startswith("win"):
            try:
                os.startfile(value)  # type: ignore[attr-defined]
            except Exception:
                webbrowser.open(value)
        else:
            webbrowser.open(value)
        return json.dumps({"success": True})
    except Exception as exc:
        logger.warn(f"LuaTools: OpenExternalUrl failed: {exc}")
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
            try:
                with open(themes_path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    return json.dumps({"success": True, "themes": data})
            except Exception as exc:
                logger.warn(f"LuaTools: Failed to read themes.json: {exc}")
                return json.dumps({"success": False, "error": "Failed to read themes.json"})
        else:
            return json.dumps({"success": True, "themes": []})
    except Exception as exc:
        logger.warn(f"LuaTools: GetThemes failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})


def ApplySettingsChanges(contentScriptQuery: str = "", changesJson: str = "") -> str:
    try:
        payload: Any = {}
        if changesJson:
            try:
                payload = json.loads(changesJson)
            except Exception:
                logger.warn("LuaTools: Failed to parse changesJson")
                return json.dumps({"success": False, "error": "Invalid JSON payload"})

        if not isinstance(payload, dict):
            logger.warn(f"LuaTools: Payload is not a dict: {payload!r}")
            return json.dumps({"success": False, "error": "Invalid payload format"})

        try:
            logger.log(f"LuaTools: ApplySettingsChanges payload: {payload}")
        except Exception:
            pass

        result = apply_settings_changes(payload)
        return json.dumps(result)
    except Exception as exc:
        logger.warn(f"LuaTools: ApplySettingsChanges failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})


def GetAvailableLocales(contentScriptQuery: str = "") -> str:
    try:
        locales = get_available_locales()
        return json.dumps({"success": True, "locales": locales})
    except Exception as exc:
        logger.warn(f"LuaTools: GetAvailableLocales failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})


def GetTranslations(contentScriptQuery: str = "", language: str = "", **kwargs: Any) -> str:
    try:
        if not language and "language" in kwargs:
            language = kwargs["language"]
        bundle = get_translation_map(language)
        bundle["success"] = True
        return json.dumps(bundle)
    except Exception as exc:
        logger.warn(f"LuaTools: GetTranslations failed: {exc}")
        return json.dumps({"success": False, "error": str(exc)})

# ==========================================
#  API EXPOSTA PARA O FRONTEND (PILL)
# ==========================================

def GetGamesDatabase(contentScriptQuery: str = "") -> str:
    return get_games_database()

# ==========================================

class Plugin:
    def _front_end_loaded(self):
        _copy_webkit_files()

    def _load(self):
        logger.log(f"bootstrapping LuaTools plugin, millennium {Millennium.version()}")

        try:
            detect_steam_install_path()
        except Exception as exc:
            logger.warn(f"LuaTools: steam path detection failed: {exc}")

        ensure_http_client("InitApis")
        ensure_temp_download_dir()

        # Webkit files must be registered before Millennium.ready()
        _copy_webkit_files()
        _inject_webkit_files()

        # Signal Millennium that the plugin is ready immediately — all heavy
        # I/O (applist load, games DB download, InitApis, auto-update) runs
        # in a background thread so it never blocks the main thread.
        Millennium.ready()

        def _background_init():
            try:
                message = apply_pending_update_if_any()
                if message:
                    store_last_message(message)
            except Exception as exc:
                logger.warn(f"AutoUpdate: apply pending failed: {exc}")

            try:
                init_applist()
            except Exception as exc:
                logger.warn(f"LuaTools: Applist initialization failed: {exc}")

            try:
                init_games_db()
            except Exception as exc:
                logger.warn(f"LuaTools: Games DB initialization failed: {exc}")

            try:
                result = InitApis("boot")
                logger.log(f"InitApis (boot) return: {result}")
            except Exception as exc:
                logger.error(f"InitApis (boot) failed: {exc}")

            try:
                start_auto_update_background_check()
            except Exception as exc:
                logger.warn(f"AutoUpdate: start background check failed: {exc}")

        t = threading.Thread(target=_background_init, daemon=True, name="LuaTools-init")
        t.start()

    def _unload(self):
        logger.log("unloading")
        close_http_client("InitApis")

        # ... (no final do arquivo main.py, antes de "class Plugin:") ...

def GetProtonDBStatus(appid: int, contentScriptQuery: str = "") -> str:
    """Busca o status do ProtonDB direto pelo Python (sem CORS, sem Proxy)."""
    try:
        url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
        client = ensure_http_client("ProtonDB")

        # Timeout curto (3s) para ser rápido. Se demorar, falha logo.
        resp = client.get(url, timeout=3)

        if resp.status_code == 200:
            return json.dumps({"success": True, "data": resp.json()})
        elif resp.status_code == 404:
            # Jogo não encontrado no ProtonDB (ex: muito novo)
            return json.dumps({"success": False, "error": "Not Found"})
        else:
            return json.dumps({"success": False, "error": f"Status {resp.status_code}"})
    except Exception as e:
        logger.warn(f"LuaTools: ProtonDB fetch failed for {appid}: {e}")
        return json.dumps({"success": False, "error": str(e)})
# ==========================================
#  GERENCIAMENTO DE DLCS (Atomic Write)
# ==========================================

def _fetch_dlc_list(appid: int):
    """Busca a lista de DLCs e seus nomes na Steam."""
    try:
        client = ensure_http_client("LuaTools: DLC Fetcher")

        url_list = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic,dlc"
        resp = client.get(url_list, timeout=10)
        data = resp.json()

        if not data or str(appid) not in data or not data[str(appid)]['success']:
            return []

        game_data = data[str(appid)]['data']
        dlc_ids = game_data.get('dlc', [])

        if not dlc_ids:
            return []

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
                    d_id_str = str(d_id)
                    name = f"DLC {d_id}"
                    if names_data and d_id_str in names_data and names_data[d_id_str]['success']:
                        name = names_data[d_id_str]['data']['name']

                    name = name.replace('"', '').replace("'", "")
                    dlc_info.append((d_id, name))
            except:
                for d_id in chunk:
                    dlc_info.append((d_id, f"DLC {d_id}"))

        return dlc_info

    except Exception as e:
        logger.error(f"[LuaTools] Erro ao buscar DLCs: {e}")
        return []

def AddGameDLCs(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": False, "error": "Config não encontrada. Instale o SLSsteam primeiro."})

        dlcs = _fetch_dlc_list(appid)
        if not dlcs:
            return json.dumps({"success": False, "error": "Nenhuma DLC encontrada para este jogo na Steam."})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_dlc_data = False
        for line in lines:
            if line.strip().startswith("DlcData:"):
                in_dlc_data = True
            if in_dlc_data and line.strip().startswith(f"{appid}:"):
                return json.dumps({"success": True, "message": "As DLCs já estão configuradas!"})

        new_block = []
        new_block.append(f"  {appid}:\n")
        for d_id, d_name in dlcs:
            new_block.append(f"    {d_id}: \"{d_name}\"\n")

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
        elif has_tag and not inserted:
            pass

        # Escrita Atômica
        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        os.replace(tmp_path, config_path)

        return json.dumps({"success": True, "message": f"{len(dlcs)} DLCs successfully added!"})

    except Exception as e:
        logger.error(f"[LuaTools] Add DLC Error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def RemoveGameDLCs(appid: int, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return json.dumps({"success": True})

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        in_target_block = False
        target_str = f"{appid}:"
        found = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(target_str):
                in_target_block = True
                found = True
                continue

            if in_target_block:
                indent = len(line) - len(line.lstrip())
                if indent <= 2 and stripped:
                    in_target_block = False
                    new_lines.append(line)
                else:
                    continue
            else:
                new_lines.append(line)

        # Escrita Atômica
        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        os.replace(tmp_path, config_path)

        return json.dumps({"success": True, "message": "DLCs removidas do config."})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def CheckGameDLCsStatus(appid: int, contentScriptQuery: str = "") -> str:
    """Verifica se as DLCs já estão no config."""
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "exists": False})

        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verificação simples: se "  APPID:" está no arquivo.
        # Pode dar falso positivo se o número aparecer em outro lugar, mas com a indentação é seguro.
        if f"\n  {appid}:" in content or f"  {appid}:" in content: # Tenta achar com quebra de linha antes
             return json.dumps({"success": True, "exists": True})

        return json.dumps({"success": True, "exists": False})
    except:
        return json.dumps({"success": True, "exists": False})


def CheckGameUpdate(appid: int, contentScriptQuery: str = "") -> str:
    """Verifica atualização comparando o manifesto local (.depot) com a API SteamCMD."""
    try:
        # 1. Tenta carregar o caminho salvo pelo usuário
        accela_path = load_launcher_path()

        # [NOVO] Se não houver caminho salvo ou se o caminho salvo não existir (ex: era o Bifrost antigo)
        # ele tenta encontrar o ACCELA no local padrão automaticamente
        if not accela_path or not os.path.exists(accela_path):
            default_accela = os.path.expanduser("~/.local/share/ACCELA/run.sh")
            if os.path.exists(default_accela):
                accela_path = default_accela
            else:
                # Se não achou em lugar nenhum, aí sim ele desiste
                return json.dumps({"success": False, "status": "Launcher Config Missing", "color": "#FF5252"})

        # Se o caminho apontar para o executável (run.sh), pegamos a pasta pai para acessar /depots
        if os.path.isfile(accela_path):
            accela_path = os.path.dirname(accela_path)

        # 2. Buscar arquivo .depot dentro da pasta do ACCELA
        depots_dir = os.path.join(accela_path, "depots")
        depot_file = os.path.join(depots_dir, f"{appid}.depot")

        # Log de debug (você pode ver isso nos logs do Millennium para confirmar o caminho)
        logger.log(f"[LuaTools] Verificando arquivo depot em: {depot_file}")

        if not os.path.exists(depot_file):
            # Se não tem arquivo .depot, o jogo não foi baixado pelo ACCELA
            return json.dumps({"success": True, "status": "Not Managed by ACCELA", "color": "#777"})

        # 3. Ler manifesto local
        local_manifest = ""
        local_depot_id = ""
        try:
            with open(depot_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                parts = content.split(':')
                if len(parts) >= 2:
                    local_manifest = parts[-1].strip()
                    raw_depot = parts[-2]
                    local_depot_id = "".join(filter(str.isdigit, raw_depot))
        except:
            return json.dumps({"success": False, "status": "Read Error", "color": "#FF5252"})

        if not local_manifest or not local_depot_id:
            return json.dumps({"success": False, "status": "Invalid Depot File", "color": "#FF5252"})

        # 4. Consultar API SteamCMD
        client = ensure_http_client("LuaTools: Update Checker")
        url = f"https://api.steamcmd.net/v1/info/{appid}"
        resp = client.get(url, timeout=5)

        if resp.status_code != 200:
            return json.dumps({"success": False, "status": "API Error", "color": "#FF5252"})

        data = resp.json()
        if data.get('status') != 'success':
            return json.dumps({"success": False, "status": "API Failed", "color": "#FF5252"})

        app_data = data['data'].get(str(appid), {})
        depots_data = app_data.get('depots', {})

        if local_depot_id in depots_data:
            manifests = depots_data[local_depot_id].get('manifests', {})
            if 'public' in manifests:
                remote_manifest = manifests['public'].get('gid')
                # Comparação
                if str(local_manifest) == str(remote_manifest):
                    return json.dumps({"success": True, "status": "Up to Date", "color": "#4CAF50"})
                else:
                    return json.dumps({"success": True, "status": "Update Available", "color": "#00FF00"})

        return json.dumps({"success": True, "status": "Unknown Version", "color": "#FF5252"})

    except Exception as e:
        logger.error(f"[LuaTools] Update Check Error: {e}")
        return json.dumps({"success": False, "status": "Error", "color": "#FF5252"})

# ==========================================
#  SLSsteam - Engine Core (Safe Mode)
# ==========================================

def GetSLSPlayStatus(contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": True, "enabled": False})

        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Verifica se está configurado como 'yes'
            is_enabled = "PlayNotOwnedGames: yes" in content.lower()
            return json.dumps({"success": True, "enabled": is_enabled})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
import os

def SetSLSPlayStatus(enabled: bool, contentScriptQuery: str = "") -> str:
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return json.dumps({"success": False, "error": "Config not found"})

        # 1. Lê tudo para a memória
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_val = "yes" if enabled else "no"
        new_lines = []
        found_play = False

        # 2. Modifica apenas as linhas necessárias
        for line in lines:
            if line.strip().lower().startswith("playnotownedgames:"):
                new_lines.append(f"PlayNotOwnedGames: {new_val}\n")
                found_play = True
            elif line.strip().lower().startswith("notifications:"):
                # Já força o desligamento das notificações também
                new_lines.append("Notifications: no\n")
            else:
                new_lines.append(line)

        if not found_play:
            new_lines.append(f"PlayNotOwnedGames: {new_val}\n")

        # 3. ESCRITA ATÔMICA: Escreve num arquivo temporário primeiro
        tmp_path = config_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 4. Substitui o arquivo original instantaneamente (o SLSsteam só vê o arquivo quando estiver pronto)
        os.replace(tmp_path, config_path)

        return json.dumps({"success": True})
    except Exception as e:
        import traceback
        logger.error(f"[LuaTools] Error saving SLSsteam config: {traceback.format_exc()}")
        return json.dumps({"success": False, "error": str(e)})
# ==========================================
#  FULL UNINSTALL LOGIC (Apaga a pasta toda, ACF e AdditionalApps)
# ==========================================

def _remove_from_additional_apps(appid: int):
    """Limpa o ID do jogo da lista AdditionalApps do config.yaml do SLS"""
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path):
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        modified = False
        target_str = f"- {appid}"

        for line in lines:
            stripped = line.strip()
            # Procura a linha com o ID do jogo
            if stripped.startswith(target_str):
                # Garante que é exatamente esse ID (ex: não confundir 440 com 4405)
                remainder = stripped[len(target_str):]
                if not remainder or remainder[0] in " \t#":
                    logger.log(f"[LuaTools] Removendo AppID {appid} do AdditionalApps no config.yaml")
                    modified = True
                    continue # Pula essa linha para ela ser deletada

            new_lines.append(line)

        # Se encontrou e removeu algo, salva usando escrita atômica (sem spamar notificações)
        if modified:
            tmp_path = config_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            os.replace(tmp_path, config_path)

    except Exception as e:
        logger.warn(f"[LuaTools] Erro limpando AdditionalApps: {e}")


def UninstallGameFull(appid: int, contentScriptQuery: str = "") -> str:
    try:
        # 1. Pega o caminho de instalação do jogo
        path_info = get_game_install_path_response(appid)
        install_path = path_info.get("installPath") if isinstance(path_info, dict) else None

        if install_path and os.path.exists(install_path):
            # 2. Deleta a pasta inteira e tudo dentro dela sem deixar rastros
            shutil.rmtree(install_path, ignore_errors=True)

            # 3. Remove o manifesto (ACF) da pasta pai para a Steam esquecer o jogo
            steamapps_dir = os.path.dirname(os.path.dirname(install_path))
            acf_file = os.path.join(steamapps_dir, f"appmanifest_{appid}.acf")
            if os.path.exists(acf_file):
                os.remove(acf_file)

        # 4. Remove o jogo dos registros do próprio LuaTools
        delete_luatools_for_app(appid)

        # 5. NOVO: Remove o AppID da lista "AdditionalApps" do config.yaml
        _remove_from_additional_apps(appid)

        return json.dumps({"success": True})
    except Exception as e:
        logger.error(f"[LuaTools] Erro crítico ao desinstalar jogo: {e}")
        return json.dumps({"success": False, "error": str(e)})

plugin = Plugin()

