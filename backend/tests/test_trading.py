"""Tests for app/trading.py.

We never import the real `py_clob_client` — every test installs fakes into
`sys.modules` *before* the trading module's lazy imports run, so this file
can pass on a checkout that hasn't installed the SDK.
"""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fake py_clob_client + web3 so tests don't depend on those packages being
# installed. Installed at module import time so trading.py's lazy imports
# pick up the fakes.
# ---------------------------------------------------------------------------


class _FakeClobClient:
    last_instance: _FakeClobClient | None = None

    def __init__(self, host: str, **kwargs: Any) -> None:
        self.host = host
        self.kwargs = kwargs
        self.api_creds_set = False
        self.created_orders: list[Any] = []
        self.posted_orders: list[tuple[Any, Any]] = []
        self.create_market_order_return: Any = SimpleNamespace(_signed=True)
        self.post_order_return: dict[str, Any] = {
            "orderID": "order-abc",
            "status": "matched",
            "transactionHash": "0xdeadbeef",
        }
        self.post_order_raises: Exception | None = None
        _FakeClobClient.last_instance = self

    def create_or_derive_api_creds(self) -> dict[str, str]:
        return {
            "api_key": "fake-key",
            "api_secret": "fake-secret",
            "api_passphrase": "fake-pass",
        }

    def set_api_creds(self, creds: dict[str, str]) -> None:
        self.api_creds_set = True
        self.creds = creds

    def create_market_order(self, args: Any) -> Any:
        self.created_orders.append(args)
        return self.create_market_order_return

    def post_order(self, signed: Any, orderType: Any) -> dict[str, Any]:  # noqa: N803
        self.posted_orders.append((signed, orderType))
        if self.post_order_raises is not None:
            raise self.post_order_raises
        return self.post_order_return


def _install_fake_sdk() -> None:
    """Replace py_clob_client.* in sys.modules with stubs."""
    pkg = ModuleType("py_clob_client")
    pkg.__path__ = []  # mark as package
    sys.modules["py_clob_client"] = pkg

    client_mod = ModuleType("py_clob_client.client")
    client_mod.ClobClient = _FakeClobClient  # type: ignore[attr-defined]
    sys.modules["py_clob_client.client"] = client_mod

    types_mod = ModuleType("py_clob_client.clob_types")

    class _MarketOrderArgs:
        def __init__(self, token_id: str, amount: float, side: str, **_: Any) -> None:
            self.token_id = token_id
            self.amount = amount
            self.side = side

    class _OrderType:
        FOK = "FOK"
        GTC = "GTC"

    types_mod.MarketOrderArgs = _MarketOrderArgs  # type: ignore[attr-defined]
    types_mod.OrderType = _OrderType  # type: ignore[attr-defined]
    sys.modules["py_clob_client.clob_types"] = types_mod

    builder_pkg = ModuleType("py_clob_client.order_builder")
    builder_pkg.__path__ = []
    sys.modules["py_clob_client.order_builder"] = builder_pkg

    constants_mod = ModuleType("py_clob_client.order_builder.constants")
    constants_mod.BUY = "BUY"  # type: ignore[attr-defined]
    constants_mod.SELL = "SELL"  # type: ignore[attr-defined]
    sys.modules["py_clob_client.order_builder.constants"] = constants_mod


_install_fake_sdk()

# Now safe to import the trading module.
from app import trading  # noqa: E402


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with a clean creds cache + clean env for trading vars."""
    trading._reset_credentials_cache_for_tests()
    for var in (
        "POLYMARKET_PRIVATE_KEY",
        "POLYMARKET_FUNDER_ADDRESS",
        "POLYMARKET_SIGNATURE_TYPE",
        "POLYMARKET_CLOB_HOST",
    ):
        monkeypatch.delenv(var, raising=False)
    _FakeClobClient.last_instance = None


# ---------------------------------------------------------------------------
# Credentials loading
# ---------------------------------------------------------------------------


def test_missing_private_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(trading.MissingCredentialsError, match="POLYMARKET_PRIVATE_KEY"):
        trading._load_credentials()


def test_proxy_default_requires_funder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    # No funder + default signature_type=1 → must fail.
    with pytest.raises(trading.MissingCredentialsError, match="POLYMARKET_FUNDER_ADDRESS"):
        trading._load_credentials()


def test_eoa_signature_type_does_not_require_funder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "0")
    creds = trading._load_credentials()
    assert creds.signature_type == 0
    assert creds.funder is None


def test_invalid_signature_type_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "9")
    with pytest.raises(trading.MissingCredentialsError, match="must be 0, 1, or 2"):
        trading._load_credentials()


def test_funder_threaded_to_clob_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "1")
    monkeypatch.setenv("POLYMARKET_CLOB_HOST", "https://clob.example")
    client = trading._build_client()
    assert isinstance(client, _FakeClobClient)
    assert client.host == "https://clob.example"
    assert client.kwargs["key"] == "0xabc"
    assert client.kwargs["funder"] == "0xfunder"
    assert client.kwargs["signature_type"] == 1
    assert client.kwargs["chain_id"] == trading.POLYGON_CHAIN_ID
    assert client.api_creds_set is True


# ---------------------------------------------------------------------------
# Token id mapping
# ---------------------------------------------------------------------------


def test_resolve_token_id_yes() -> None:
    assert trading._resolve_token_id(
        outcome="Yes", clob_token_yes="yes-tok", clob_token_no="no-tok"
    ) == "yes-tok"


def test_resolve_token_id_no() -> None:
    assert trading._resolve_token_id(
        outcome="No", clob_token_yes="yes-tok", clob_token_no="no-tok"
    ) == "no-tok"


def test_resolve_token_id_yes_missing() -> None:
    with pytest.raises(trading.InvalidMarketError, match="YES"):
        trading._resolve_token_id(
            outcome="Yes", clob_token_yes=None, clob_token_no="no-tok"
        )


def test_resolve_token_id_no_missing() -> None:
    with pytest.raises(trading.InvalidMarketError, match="NO"):
        trading._resolve_token_id(
            outcome="No", clob_token_yes="yes-tok", clob_token_no=None
        )


# ---------------------------------------------------------------------------
# place_order — the happy path + error surfaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_order_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")

    result = await trading.place_order(
        condition_id="0xcond",
        outcome="Yes",
        size_usdc=5.0,
        side="BUY",
        clob_token_yes="yes-tok",
        clob_token_no="no-tok",
    )
    assert result.order_id == "order-abc"
    assert result.status == "matched"
    assert result.transaction_hash == "0xdeadbeef"

    client = _FakeClobClient.last_instance
    assert client is not None
    assert len(client.created_orders) == 1
    args = client.created_orders[0]
    assert args.token_id == "yes-tok"
    assert args.amount == 5.0
    assert args.side == "BUY"
    # Posted with FOK order type.
    assert client.posted_orders[0][1] == "FOK"


@pytest.mark.asyncio
async def test_place_order_no_outcome_uses_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")

    await trading.place_order(
        condition_id="0xcond",
        outcome="No",
        size_usdc=1.0,
        side="BUY",
        clob_token_yes="yes-tok",
        clob_token_no="no-tok",
    )
    client = _FakeClobClient.last_instance
    assert client is not None
    assert client.created_orders[0].token_id == "no-tok"


@pytest.mark.asyncio
async def test_place_order_invalid_size_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")

    with pytest.raises(trading.InvalidMarketError, match="size_usdc"):
        await trading.place_order(
            condition_id="0xcond",
            outcome="Yes",
            size_usdc=0.0,
            side="BUY",
            clob_token_yes="yes-tok",
            clob_token_no="no-tok",
        )


@pytest.mark.asyncio
async def test_place_order_missing_creds_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # No env at all.
    with pytest.raises(trading.MissingCredentialsError):
        await trading.place_order(
            condition_id="0xcond",
            outcome="Yes",
            size_usdc=5.0,
            side="BUY",
            clob_token_yes="yes-tok",
            clob_token_no="no-tok",
        )


@pytest.mark.asyncio
async def test_place_order_clob_failure_wraps_as_placement_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")

    # Pre-build a client and rig it to raise on post_order. We can't intercept
    # the per-call instance directly; instead, monkeypatch _build_client.
    rigged = _FakeClobClient("https://clob.example")
    rigged.post_order_raises = RuntimeError("insufficient USDC balance")
    monkeypatch.setattr(trading, "_build_client", lambda: rigged)

    with pytest.raises(trading.OrderPlacementError, match="insufficient USDC"):
        await trading.place_order(
            condition_id="0xcond",
            outcome="Yes",
            size_usdc=5.0,
            side="BUY",
            clob_token_yes="yes-tok",
            clob_token_no="no-tok",
        )


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------


def test_normalize_response_handles_dict() -> None:
    out = trading._normalize_response(
        {"orderID": "X", "status": "matched", "transactionHash": "0xfeed"}
    )
    assert out.order_id == "X"
    assert out.status == "matched"
    assert out.transaction_hash == "0xfeed"


def test_normalize_response_handles_alt_field_names() -> None:
    out = trading._normalize_response({"id": "Y", "success": True})
    assert out.order_id == "Y"
    assert out.status == "ok"
    assert out.transaction_hash is None


def test_normalize_response_handles_non_dict() -> None:
    out = trading._normalize_response("oops")
    assert out.raw == {"raw": "oops"}
    assert out.order_id is None


# ---------------------------------------------------------------------------
# /order endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_endpoint_503_when_creds_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint must surface MissingCredentialsError as a 503 with a
    human-readable message — no leaking that we hit an exception path."""
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    # Stub session so we can inject a market without a real DB.
    market = SimpleNamespace(
        id="m1",
        active=True,
        condition_id="0xcond",
        clob_token_yes="yes-tok",
        clob_token_no="no-tok",
    )
    fake_session = MagicMock()

    class _Result:
        def scalar_one_or_none(self) -> Any:
            return market

    async def _execute(_stmt: Any) -> _Result:
        return _Result()

    fake_session.execute = _execute

    async def override_session():
        yield fake_session

    app.dependency_overrides[get_session] = override_session

    # No POLYMARKET_PRIVATE_KEY in env → MissingCredentialsError → 503.
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/order",
                json={
                    "market_id": "m1",
                    "outcome": "Yes",
                    "size_usdc": 1.0,
                    "side": "BUY",
                },
            )
        assert r.status_code == 503
        assert "POLYMARKET_PRIVATE_KEY" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_order_endpoint_404_when_market_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    fake_session = MagicMock()

    class _Result:
        def scalar_one_or_none(self) -> Any:
            return None

    async def _execute(_stmt: Any) -> _Result:
        return _Result()

    fake_session.execute = _execute

    async def override_session():
        yield fake_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/order",
                json={
                    "market_id": "missing",
                    "outcome": "Yes",
                    "size_usdc": 1.0,
                    "side": "BUY",
                },
            )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_order_endpoint_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0xfunder")

    market = SimpleNamespace(
        id="m1",
        active=True,
        condition_id="0xcond",
        clob_token_yes="yes-tok",
        clob_token_no="no-tok",
    )
    fake_session = MagicMock()

    class _Result:
        def scalar_one_or_none(self) -> Any:
            return market

    async def _execute(_stmt: Any) -> _Result:
        return _Result()

    fake_session.execute = _execute

    async def override_session():
        yield fake_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/order",
                json={
                    "market_id": "m1",
                    "outcome": "Yes",
                    "size_usdc": 5.0,
                    "side": "BUY",
                },
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["order_id"] == "order-abc"
        assert body["status"] == "matched"
        assert body["transaction_hash"] == "0xdeadbeef"
    finally:
        app.dependency_overrides.clear()
