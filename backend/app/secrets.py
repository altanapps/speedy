"""Secret resolution: env first, then macOS Keychain.

Why env wins over Keychain: `POLYMARKET_PRIVATE_KEY=foo make test` and CI both
need to override Keychain values without touching the user's login keychain.
Tests use `monkeypatch.setenv` extensively. Keychain is the "set once and
forget" production tier; env is always the explicit override.

Service name `speedy` — visible to the user in Keychain Access.app under
that label, with one entry per `KEYS` constant below.
"""
from __future__ import annotations

import logging
import os
from typing import Final

log = logging.getLogger(__name__)

SERVICE: Final = "speedy"

# The set of secrets Speedy stores. Used by the CLI to enumerate what to
# prompt for; used by callers to look secrets up by canonical name.
KEYS: Final = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "POLYMARKET_PRIVATE_KEY",
    "POLYMARKET_FUNDER_ADDRESS",
)


def get_secret(name: str) -> str | None:
    """Resolve a secret. Env first, then Keychain. Returns None if neither.

    Empty strings are treated as unset — same as the previous `os.environ.get(...)
    .strip() or None` pattern.
    """
    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value
    try:
        kc_value = _keyring_get(name)
    except Exception as exc:  # noqa: BLE001
        # Keychain access can fail in headless contexts (CI, Docker without a
        # daemon). Don't crash the request — just behave as if no secret is set.
        log.debug("keyring lookup for %s failed: %s", name, exc)
        return None
    if kc_value:
        return kc_value.strip() or None
    return None


def set_secret(name: str, value: str) -> None:
    """Store a secret in macOS Keychain under the `speedy` service."""
    import keyring

    keyring.set_password(SERVICE, name, value)


def delete_secret(name: str) -> bool:
    """Remove a Keychain entry. Returns True if something was removed."""
    import keyring
    from keyring.errors import PasswordDeleteError

    try:
        keyring.delete_password(SERVICE, name)
    except PasswordDeleteError:
        return False
    return True


def _keyring_get(name: str) -> str | None:
    import keyring

    return keyring.get_password(SERVICE, name)
