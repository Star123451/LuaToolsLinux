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

<details>
<summary>Manual installation</summary>

Please see this message in the LuaTools discord for manual installation steps:

https://discord.com/channels/1408201417834893385/1473040386908885122/1473047251319394581

</details>

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
