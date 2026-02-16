# LuaTools (Linux)

> A [Millennium](https://steambrew.app) plugin that downloads game manifest files for Steam on Linux.

**By [StarWarsK](https://github.com/Star123451) & [geovanygrdt](https://github.com/gr33dster-glitch)**

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

**One-liner (Auto-installs everything):**
```bash
curl -fsSL https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main/install.sh | bash
```

The installer will automatically:
- ✅ Install Millennium if not found
- ✅ Install SLSsteam if not found (requires build-essential)
- ✅ Install ACCELA if not found
- ✅ Clone/update LuaTools plugin
- ✅ No pip or external Python packages needed

Each component installation is optional - you can skip any you want to install manually.

<details>
<summary>Manual installation</summary>

Please see this message in the LuaTools discord for manual installation steps:

https://discord.com/channels/1408201417834893385/1473040386908885122/1473047251319394581

</details>

## Project Structure

```
luatools/
├── plugin.json              # Millennium plugin manifest
├── requirements.txt         # Python dependencies (none - uses stdlib only!)
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

- **LuaTools (Linux)** — by [StarWarsK](https://github.com/Star123451) & [geovanygrdt](https://github.com/gr33dster-glitch)
- **LuaTools** — original plugin by [madoiscool](https://github.com/madoiscool)
- **SLSsteam** — by [AceSLS](https://github.com/AceSLS/SLSsteam)
- **ACCELA / Enter The Wired** — by [ciscosweater](https://github.com/ciscosweater/enter-the-wired)
- **Millennium** — by [SteamClientHomebrew](https://github.com/SteamClientHomebrew/Millennium)

## License

See the original LuaTools repository for license information.
