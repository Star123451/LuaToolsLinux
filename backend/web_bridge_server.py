#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

import main as luatools_main


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _call_backend(method_name: str, args: Dict[str, Any]) -> Any:
    if method_name.startswith("_"):
        raise ValueError("Private method is not accessible")

    parts = method_name.split(".")
    obj = luatools_main
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            raise ValueError(f"Unknown method: {method_name}")

    if not callable(obj):
        raise ValueError(f"Method exists but is not callable: {method_name}")

    if not isinstance(args, dict):
        raise ValueError("args must be a JSON object")

    return obj(**args)


class _BridgeHandler(BaseHTTPRequestHandler):
    server_version = "LuaToolsBridge/1.0"

    def do_OPTIONS(self) -> None:
        _json_response(self, 200, {"success": True})

    def do_GET(self) -> None:
        if self.path == "/health":
            _json_response(self, 200, {"success": True, "service": "luatools-bridge"})
            return
        _json_response(self, 404, {"success": False, "error": "Not Found"})

    def do_POST(self) -> None:
        if self.path != "/rpc":
            _json_response(self, 404, {"success": False, "error": "Not Found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            method = str(body.get("method", "")).strip()
            args = body.get("args", {})

            if not method:
                _json_response(self, 400, {"success": False, "error": "Missing method"})
                return

            result = _call_backend(method, args)
            _json_response(self, 200, {"success": True, "result": result})
        except Exception as exc:
            _json_response(self, 500, {"success": False, "error": str(exc)})

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="LuaTools web bridge server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38495)
    args = parser.parse_args()

    try:
        luatools_main.detect_steam_install_path()
    except Exception:
        pass
    try:
        luatools_main.ensure_http_client("BridgeInit")
    except Exception:
        pass
    try:
        luatools_main.ensure_temp_download_dir()
    except Exception:
        pass
    try:
        luatools_main.init_applist()
    except Exception:
        pass
    try:
        luatools_main.init_games_db()
    except Exception:
        pass
    try:
        luatools_main.InitApis("bridge-init")
    except Exception:
        pass

    httpd = ThreadingHTTPServer((args.host, args.port), _BridgeHandler)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
