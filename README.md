# LuaTools (Linux) BY StarWarsK

> A [Millennium](https://steambrew.app) plugin that downloads game manifest files for Steam on Linux.

This is the **Linux-only** fork of LuaTools, adapted to work with [SLSsteam](https://github.com/AceSLS/SLSsteam) and [ACCELA](https://github.com/ciscosweater/enter-the-wired) instead of the Windows-only SteamTools.

## NOTE

- **This Port is in EARLY ACCESS** - Do not expect a polished experience. Expect something that works (albeit messily). This plugin will improve overtime but basic functionality is operational.
- **If you get an error saying "Failed to find executable" or "Content still encrypted"** - Try opening the game executable from your file browser by clicking the gear, going to Manage, then "Browse Local Files".

## Features

- **Install your Favorite Games With the Press of a Button** - Click "Add via LuaTools" to install games via ACCELA without searching for a Manifest file Yourself!

## Requirements

- **Linux x86_64** (no ARM support — Millennium doesn't support ARM)
- **Steam** for Linux
- **[Millennium](https://steambrew.app)** — Steam client modding framework
- **Python 3.10+**

### Optional

- **[SLSsteam](https://github.com/AceSLS/SLSsteam)** — Steam patcher (`.so` injection via `LD_AUDIT`)
- **[ACCELA](https://github.com/ciscosweater/enter-the-wired)** — game client/downloader

## Installation
1. Install ACCELA + SLSsteam:
    ```bash
   curl -fsSL https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/enter-the-wired | bash
   ```
    
2. Install Millennium:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash
   ```
   
3. Make luatools folder in /.local/share/millennium/plugins

4. Clone this repo into the LuaTools plugin directory
   ```bash
   git clone https://github.com/Star123451/LuaToolsLinux
   ```

5. Install Python dependencies:
   ```bash
   pip install -r ~/.local/share/millennium/plugins/luatools/requirements.txt
   ```
   
6. Restart SLSsteam — LuaTools will load automatically via Millennium.

## Project Structure

```
luatools/
├── plugin.json              # Millennium plugin manifest
├── requirements.txt         # Python dependencies (requests, httpx)
├── backend/
│   ├── main.py              # Plugin entry point (Plugin class)
│   ├── linux_platform.py    # Linux path detection & platform helpers
│   ├── slssteam_config.py   # SLSsteam config.yaml reader/writer
│   ├── steam_utils.py       # Steam path detection, VDF parsing
│   ├── downloads.py         # Lua script download & installation
│   ├── fixes.py             # Game fix application
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

- **LuaTools** — original plugin by [madoiscool](https://github.com/madoiscool)
- **SLSsteam** — by [AceSLS](https://github.com/AceSLS/SLSsteam)
- **ACCELA / Enter The Wired** — by [ciscosweater](https://github.com/ciscosweater/enter-the-wired)
- **Millennium** — by [SteamClientHomebrew](https://github.com/SteamClientHomebrew/Millennium)
- **dont forget star** - hes cool :D

## Contributing

- **Make a pull request with a clear explanation** - If you are even somewhat competant, there is a good chance I will accept it.

## License

See the original LuaTools repository for license information.
