# LuaTools (Linux)

> A [Millennium](https://steambrew.app) plugin that downloads game manifest files for Steam on Linux.

**By [StarWarsK](https://github.com/StarWarsK) & geovanygrdt**

This is the **Linux-only** fork of LuaTools, adapted to work with [SLSsteam](https://github.com/AceSLS/SLSsteam) and [ACCELA](https://github.com/ciscosweater/enter-the-wired) instead of the Windows-only SteamTools.

## Features

- **One-Click Game Install** — Click "Add via LuaTools" to download games via ACCELA without manually hunting for manifests
- **Workshop Downloader** — Download Steam Workshop content via DepotDownloaderMod
- **Game Fix System** — Apply, manage, and remove game-specific fixes
- **Linux Native Fix** — Recursively set execute permissions on game files (`chmod +x`)
- **FakeAppId & Token Management** — Automatically configure SLSsteam's `config.yaml`
- **Ryuu Cookie & Morrenus Key Support** — Manage API credentials from the UI
- **Games Database** — Status pills showing game compatibility info
- **Themes** — Customizable UI themes
- **Auto-Update** — Self-update from GitHub releases
- **Configurable Launcher Path** — Point to Bifrost or any custom launcher

## Requirements

- **Linux x86_64** (no ARM support — Millennium doesn't support ARM)
- **Steam** for Linux
- **[Millennium](https://steambrew.app)** — Steam client modding framework
- **Python 3.10+**

### Important!

- **[SLSsteam](https://github.com/AceSLS/SLSsteam)** — Steam patcher (`.so` injection via `LD_AUDIT`)
- **[ACCELA](https://github.com/ciscosweater/enter-the-wired)** — game downloader (DepotDownloader GUI)

## Installation

**One-liner:**
```bash
curl -fsSL https://raw.githubusercontent.com/StarWarsK/LuaToolsLinux/main/install.sh | bash
```

<details>
<summary>Manual installation</summary>

1. Install Millennium:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash
   ```

2. Clone this repo into the Millennium plugins directory:
   ```bash
   git clone <repo-url> ~/.local/share/millennium/plugins/luatools
   ```

3. Install Python dependencies:
   ```bash
   pip install -r ~/.local/share/millennium/plugins/luatools/requirements.txt
   ```

4. Restart Steam — LuaTools will load automatically via Millennium.

</details>

## Project Structure

```
luatools/
├── plugin.json              # Millennium plugin manifest
├── requirements.txt         # Python dependencies (httpx)
├── backend/
│   ├── main.py              # Plugin entry point + API wrappers
│   ├── linux_platform.py    # Linux path detection & platform helpers
│   ├── slssteam_config.py   # SLSsteam config.yaml reader/writer
│   ├── steam_utils.py       # Steam path detection, VDF parsing
│   ├── downloads.py         # Download engine, Games DB, Ryuu/Morrenus
│   ├── fixes.py             # Game fixes + Linux native fix
│   ├── auto_update.py       # Self-update from GitHub releases
│   ├── donate_keys.py       # Key donation system
│   ├── config.py            # Constants (API URLs, filenames)
│   ├── api_manifest.py      # API manifest fetching
│   ├── http_client.py       # HTTP client management
│   ├── settings/
│   │   ├── manager.py       # Settings persistence (JSON)
│   │   └── options.py       # Settings schema (General + SLSsteam)
│   └── ...
└── public/
    ├── luatools.js          # Frontend UI (injected into Steam)
    └── luatools-icon.png    # Plugin icon
```

## How It Works

### Path Resolution

LuaTools discovers Steam and related tools at these locations:

| Component | Path |
|-----------|------|
| Steam root | `~/.steam/steam` or `~/.local/share/Steam` |
| Lua scripts | `{steam_root}/config/stplug-in/*.lua` |
| Depot manifests | `{steam_root}/depotcache/*.manifest` |
| SLSsteam binary | `~/.local/share/SLSsteam/SLSsteam.so` |
| SLSsteam config | `~/.config/SLSsteam/config.yaml` |
| ACCELA | `~/.local/share/ACCELA/` or `~/accela/` |

## Credits

- **LuaTools (Linux)** — by [StarWarsK](https://github.com/StarWarsK) & geovanygrdt
- **LuaTools** — original plugin by [madoiscool](https://github.com/madoiscool)
- **SLSsteam** — by [AceSLS](https://github.com/AceSLS/SLSsteam)
- **ACCELA / Enter The Wired** — by [ciscosweater](https://github.com/ciscosweater/enter-the-wired)
- **Millennium** — by [SteamClientHomebrew](https://github.com/SteamClientHomebrew/Millennium)

## License

See the original LuaTools repository for license information.
