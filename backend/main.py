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
#  GERENCIAMENTO DE FAKE APP ID
# ==========================================

def AddFakeAppId(appid: int, contentScriptQuery: str = "") -> str:
    """Adds the line 'APPID: 480' to the FakeAppIds section in config.yaml."""
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")

        if not os.path.exists(config_path):
             try:
                 os.makedirs(os.path.dirname(config_path), exist_ok=True)
                 with open(config_path, 'w') as f:
                     f.write("FakeAppIds:\n")
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

        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        logger.log(f"[LuaTools] FakeAppId 480 added for {appid}")
        return json.dumps({"success": True, "message": f"FakeAppId (480) added for {appid}!"})

    except Exception as e:
        logger.error(f"[LuaTools] FakeAppId Error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def RemoveFakeAppId(appid: int) -> None:
    """Surgically removes the FakeAppId line for this game."""
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return

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
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
    except Exception as e:
        logger.warn(f"[LuaTools] Error cleaning FakeAppId: {e}")

# ==========================================
#  GERENCIAMENTO DE TOKENS
# ==========================================

def AddGameToken(appid: int, contentScriptQuery: str = "") -> str:
    """Busca o token do jogo no JSON e adiciona ao config.yaml."""
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
             with open(config_path, 'w', encoding='utf-8') as f:
                 f.write("AppTokens:\n")

        token = None
        with open(json_path, 'r', encoding='utf-8') as f:
            tokens_db = json.load(f)

        appid_str = str(appid)
        token = tokens_db.get(appid_str)

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

        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        return json.dumps({"success": True, "message": f"Token adicionado para AppID {appid}!"})

    except Exception as e:
        logger.error(f"[LuaTools] Token Error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def RemoveGameToken(appid: int) -> None:
    """Remove silenciosamente apenas a linha do token correspondente ao AppID."""
    try:
        config_path = os.path.expanduser("~/.config/SLSsteam/config.yaml")
        if not os.path.exists(config_path): return

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
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

    except Exception as e:
        logger.warn(f"[LuaTools] Erro ao tentar limpar token no UnFix: {e}")

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

        return json.dumps({"success": True, "message": "Dependências instaladas com sucesso!"})

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


def ApplySettingsChanges(
    contentScriptQuery: str = "", changes: Any = None, **kwargs: Any
) -> str:  # type: ignore[name-defined]
    try:
        if "changes" in kwargs and changes is None:
            changes = kwargs["changes"]
        if changes is None and isinstance(kwargs, dict):
            changes = kwargs

        try:
            logger.log(
                "LuaTools: ApplySettingsChanges raw argument "
                f"type={type(changes)} value={changes!r}"
            )
            logger.log(f"LuaTools: ApplySettingsChanges kwargs: {kwargs}")
        except Exception:
            pass

        payload: Any = None

        if isinstance(changes, str) and changes:
            try:
                payload = json.loads(changes)
            except Exception:
                logger.warn("LuaTools: Failed to parse changes string payload")
                return json.dumps({"success": False, "error": "Invalid JSON payload"})
            else:
                # When a full payload dict was sent as JSON, unwrap keys we expect.
                if isinstance(payload, dict) and "changes" in payload:
                    kwargs_payload = payload
                    payload = kwargs_payload.get("changes")
                    if "contentScriptQuery" in kwargs_payload and not contentScriptQuery:
                        contentScriptQuery = kwargs_payload.get("contentScriptQuery", "")
                elif isinstance(payload, dict) and "changesJson" in payload and isinstance(payload["changesJson"], str):
                    try:
                        payload = json.loads(payload["changesJson"])
                    except Exception:
                        logger.warn("LuaTools: Failed to parse changesJson string inside payload")
                        return json.dumps({"success": False, "error": "Invalid JSON payload"})
        elif isinstance(changes, dict) and changes:
            # When the bridge passes a dict argument directly.
            if "changesJson" in changes and isinstance(changes["changesJson"], str):
                try:
                    payload = json.loads(changes["changesJson"])
                except Exception:
                    logger.warn("LuaTools: Failed to parse changesJson payload from dict")
                    return json.dumps({"success": False, "error": "Invalid JSON payload"})
            elif "changes" in changes:
                payload = changes.get("changes")
            else:
                payload = changes
        else:
            # Look for JSON payload inside kwargs.
            changes_json = kwargs.get("changesJson")
            if isinstance(changes_json, dict):
                payload = changes_json
            elif isinstance(changes_json, str) and changes_json:
                try:
                    payload = json.loads(changes_json)
                except Exception:
                    logger.warn("LuaTools: Failed to parse changesJson payload")
                    return json.dumps({"success": False, "error": "Invalid JSON payload"})
            elif isinstance(changes_json, dict):
                payload = changes_json
            else:
                payload = changes

        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            logger.warn(f"LuaTools: Parsed payload is not a dict: {payload!r}")
            return json.dumps({"success": False, "error": "Invalid payload format"})

        try:
            logger.log(f"LuaTools: ApplySettingsChanges received payload: {payload}")
        except Exception:
            pass

        result = apply_settings_changes(payload)
        try:
            logger.log(f"LuaTools: ApplySettingsChanges result: {result}")
        except Exception:
            pass
        response = json.dumps(result)
        try:
            logger.log(f"LuaTools: ApplySettingsChanges response json: {response}")
        except Exception:
            pass
        return response
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

        # --- INICIALIZAÇÃO DA GAMES DB ---
        try:
            init_games_db()
        except Exception as exc:
            logger.warn(f"LuaTools: Games DB initialization failed: {exc}")
        # ---------------------------------

        _copy_webkit_files()
        _inject_webkit_files()

        try:
            result = InitApis("boot")
            logger.log(f"InitApis (boot) return: {result}")
        except Exception as exc:
            logger.error(f"InitApis (boot) failed: {exc}")

        try:
            start_auto_update_background_check()
        except Exception as exc:
            logger.warn(f"AutoUpdate: start background check failed: {exc}")

        Millennium.ready()

    def _unload(self):
        logger.log("unloading")
        close_http_client("InitApis")


plugin = Plugin()
