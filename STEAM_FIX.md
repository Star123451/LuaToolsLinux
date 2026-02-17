# Steam Won't Open - Fix Guide

## Problem
After installing LuaTools, Steam refuses to open. This was caused by incomplete urllib implementation in the HTTP client.

## What Was Wrong
The HTTP client was missing the `stream()` method and had incorrect error handling, causing Python errors when Millennium tried to load the plugin. This prevented Steam from starting.

## What Was Fixed
1. **Added `stream()` method** - Required for downloading large files (updates, fixes, etc.)
2. **Added `HTTPStreamResponse` class** - Context manager for streaming downloads
3. **Fixed error handling** - Properly handle both normal responses and HTTP errors
4. **Added `content=` parameter support** - The `post()` method now accepts both `data=` and `content=`
5. **String encoding** - POST data is automatically encoded to bytes

## How to Apply the Fix

### Option 1: Re-run the Installer (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main/install.sh | bash
```

### Option 2: Manual Pull
```bash
cd ~/.local/share/millennium/plugins/luatools
git pull origin main
```

### Option 3: Manual File Update
If git doesn't work, download just the fixed file:
```bash
cd ~/.local/share/millennium/plugins/luatools/backend
curl -fsSL https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main/backend/http_client.py -o http_client.py
curl -fsSL https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main/backend/main.py -o main.py
```

## Restart Steam
```bash
killall -9 steam steamwebhelper
steam
```

## Verify It Works
After Steam opens:
1. Open Steam settings
2. Look for LuaTools in the plugins section
3. Check that the plugin loaded without errors

## Still Having Issues?
If Steam still won't open after applying the fix:

1. **Check plugin logs:**
   ```bash
   cat ~/.local/share/millennium/plugins/luatools/backend/raw_startup.log
   ```

2. **Disable the plugin temporarily:**
   ```bash
   mv ~/.local/share/millennium/plugins/luatools ~/.local/share/millennium/plugins/luatools.disabled
   ```
   Then start Steam. If it works, the issue is confirmed to be with LuaTools.

3. **Check Millennium logs** for any other errors

## Technical Details
All HTTP functionality now uses Python's built-in `urllib` instead of external libraries (`requests`, `httpx`). This means:
- ✅ No pip installation required
- ✅ No external dependencies
- ✅ Works on any Linux system with Python 3.6+
- ✅ More reliable and faster installation
