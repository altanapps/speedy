"""`speedy-keys` — manage Speedy's Keychain entries.

Usage:
    speedy-keys set            # interactive: prompts for each key, hides input
    speedy-keys set <NAME>     # interactive: prompts for one key
    speedy-keys show           # list which entries exist (never prints values)
    speedy-keys clear          # delete every Speedy entry
    speedy-keys clear <NAME>   # delete one

Why a CLI instead of putting secrets in `.env`: pasting a wallet private key
into a dotfile leaves it on disk in plaintext and is easy to leak via shell
history or accidental `git add`. macOS Keychain encrypts at rest and is the
same store every other Mac dev tool uses.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.secrets import KEYS, SERVICE, delete_secret, set_secret

# Per-key prompt copy. Plain English, no jargon — this is the first thing
# a user sees after `make set-keys`.
PROMPTS: dict[str, str] = {
    "OPENAI_API_KEY": (
        "OpenAI API key (required). Used to embed Polymarket markets and "
        "your highlighted text. Get one at https://platform.openai.com/api-keys."
    ),
    "ANTHROPIC_API_KEY": (
        "Anthropic API key (optional, recommended). Used to rerank search "
        "results — big quality win. Press enter to skip. "
        "Get one at https://console.anthropic.com/."
    ),
    "POLYMARKET_PRIVATE_KEY": (
        "Polymarket signer private key (required for trading). Export from "
        "polymarket.com → wallet → Settings → Export Private Key. "
        "Stored in macOS Keychain — never written to disk in plaintext."
    ),
    "POLYMARKET_FUNDER_ADDRESS": (
        "Polymarket funder address (required for trading on a proxy wallet — "
        "i.e. most polymarket.com accounts). It's the deposit address shown "
        "on polymarket.com → wallet → Deposit. Press enter if you use a raw "
        "self-custody EOA."
    ),
}


def _prompt_for(name: str) -> str | None:
    print()
    print(f"--- {name} ---")
    print(PROMPTS.get(name, ""))
    value = getpass.getpass(f"{name}: ").strip()
    return value or None


def _cmd_set(args: argparse.Namespace) -> int:
    names = [args.name] if args.name else list(KEYS)
    stored: list[str] = []
    skipped: list[str] = []
    for name in names:
        if name not in KEYS:
            print(f"Unknown key: {name}. Known keys: {', '.join(KEYS)}", file=sys.stderr)
            return 2
        value = _prompt_for(name)
        if value is None:
            skipped.append(name)
            continue
        set_secret(name, value)
        stored.append(name)

    print()
    if stored:
        print(f"Stored in Keychain ({SERVICE}): {', '.join(stored)}")
    if skipped:
        print(f"Skipped (left empty): {', '.join(skipped)}")
    return 0


def _cmd_show(_args: argparse.Namespace) -> int:
    import keyring

    print(f"Keychain service: {SERVICE}")
    print()
    for name in KEYS:
        value = keyring.get_password(SERVICE, name)
        marker = "set" if value else "—"
        print(f"  {name:30s} {marker}")
    return 0


def _cmd_clear(args: argparse.Namespace) -> int:
    names = [args.name] if args.name else list(KEYS)
    removed: list[str] = []
    for name in names:
        if name not in KEYS:
            print(f"Unknown key: {name}. Known keys: {', '.join(KEYS)}", file=sys.stderr)
            return 2
        if delete_secret(name):
            removed.append(name)
    if removed:
        print(f"Removed from Keychain: {', '.join(removed)}")
    else:
        print("Nothing to remove.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="speedy-keys",
        description="Manage Speedy's macOS Keychain entries.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set", help="Store one or all keys")
    p_set.add_argument("name", nargs="?", help=f"One of: {', '.join(KEYS)}")
    p_set.set_defaults(func=_cmd_set)

    p_show = sub.add_parser("show", help="List which keys are stored (never prints values)")
    p_show.set_defaults(func=_cmd_show)

    p_clear = sub.add_parser("clear", help="Delete one or all keys")
    p_clear.add_argument("name", nargs="?", help=f"One of: {', '.join(KEYS)}")
    p_clear.set_defaults(func=_cmd_clear)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
