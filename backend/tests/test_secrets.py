from __future__ import annotations

import pytest

from app import secrets


@pytest.fixture(autouse=True)
def _stub_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Replace the keyring lookup with an in-memory dict so tests don't touch
    the developer's real macOS Keychain."""
    store: dict[str, str] = {}
    monkeypatch.setattr(secrets, "_keyring_get", lambda name: store.get(name))
    return store


def test_env_wins_over_keychain(
    monkeypatch: pytest.MonkeyPatch, _stub_keyring: dict[str, str]
) -> None:
    _stub_keyring["OPENAI_API_KEY"] = "kc-value"
    monkeypatch.setenv("OPENAI_API_KEY", "env-value")
    assert secrets.get_secret("OPENAI_API_KEY") == "env-value"


def test_keychain_used_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, _stub_keyring: dict[str, str]
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _stub_keyring["OPENAI_API_KEY"] = "kc-value"
    assert secrets.get_secret("OPENAI_API_KEY") == "kc-value"


def test_empty_env_falls_through_to_keychain(
    monkeypatch: pytest.MonkeyPatch, _stub_keyring: dict[str, str]
) -> None:
    """Whitespace-only env value should be treated as unset, same as the
    previous os.environ.get(...).strip() or None pattern."""
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    _stub_keyring["OPENAI_API_KEY"] = "kc-value"
    assert secrets.get_secret("OPENAI_API_KEY") == "kc-value"


def test_neither_returns_none(
    monkeypatch: pytest.MonkeyPatch, _stub_keyring: dict[str, str]
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert secrets.get_secret("OPENAI_API_KEY") is None


def test_keychain_failure_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Headless / Docker / locked-keychain contexts can raise. We must not
    crash a request just because Keychain is unreachable — fall back to None."""
    def _boom(_name: str) -> str | None:
        raise RuntimeError("keyring unavailable")

    monkeypatch.setattr(secrets, "_keyring_get", _boom)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert secrets.get_secret("OPENAI_API_KEY") is None
