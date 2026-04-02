#!/usr/bin/env python3
"""Standalone CLI for LuaTools backend operations.

This CLI lets SLSsteam/headcrab users use core LuaTools features without
Millennium UI integration.
"""

from __future__ import annotations

import argparse
import json
import sys

from main import (
    AddFakeAppId,
    AddGameDLCs,
    AddGameToken,
    CheckFakeAppIdStatus,
    CheckGameDLCsStatus,
    CheckGameTokenStatus,
    CheckForFixes,
    GetGameInstallPath,
    InitApis,
    RemoveFakeAppId,
    RemoveGameDLCs,
    RemoveGameToken,
)


def _emit(result: str) -> int:
    try:
        parsed = json.loads(result)
        print(json.dumps(parsed, ensure_ascii=True, indent=2))
        if isinstance(parsed, dict) and parsed.get("success") is False:
            return 1
        return 0
    except Exception:
        print(result)
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LuaTools standalone CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-apis", help="Initialize free API list")

    p = sub.add_parser("add-fakeappid", help="Add FakeAppId mapping to SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("remove-fakeappid", help="Remove FakeAppId mapping from SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("check-fakeappid", help="Check FakeAppId mapping status")
    p.add_argument("appid", type=int)

    p = sub.add_parser("add-token", help="Add AppToken to SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("remove-token", help="Remove AppToken from SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("check-token", help="Check AppToken status")
    p.add_argument("appid", type=int)

    p = sub.add_parser("add-dlcs", help="Add DLC data for app to SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("remove-dlcs", help="Remove DLC data block from SLSsteam config")
    p.add_argument("appid", type=int)

    p = sub.add_parser("check-dlcs", help="Check DLC data status")
    p.add_argument("appid", type=int)

    p = sub.add_parser("get-install-path", help="Resolve game install path from Steam libraries")
    p.add_argument("appid", type=int)

    p = sub.add_parser("check-fixes", help="Check available fixes for an app")
    p.add_argument("appid", type=int)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-apis":
        return _emit(InitApis("standalone-cli"))
    if args.command == "add-fakeappid":
        return _emit(AddFakeAppId(args.appid))
    if args.command == "remove-fakeappid":
        return _emit(RemoveFakeAppId(args.appid))
    if args.command == "check-fakeappid":
        return _emit(CheckFakeAppIdStatus(args.appid))
    if args.command == "add-token":
        return _emit(AddGameToken(args.appid))
    if args.command == "remove-token":
        return _emit(RemoveGameToken(args.appid))
    if args.command == "check-token":
        return _emit(CheckGameTokenStatus(args.appid))
    if args.command == "add-dlcs":
        return _emit(AddGameDLCs(args.appid))
    if args.command == "remove-dlcs":
        return _emit(RemoveGameDLCs(args.appid))
    if args.command == "check-dlcs":
        return _emit(CheckGameDLCsStatus(args.appid))
    if args.command == "get-install-path":
        return _emit(GetGameInstallPath(args.appid))
    if args.command == "check-fixes":
        return _emit(CheckForFixes(args.appid))

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
