"""Polymarket CLOB order placement.

Wraps `py_clob_client` so the rest of the backend can hand off `place_order(...)`
without thinking about L1/L2 keys, signature types, or asyncio-vs-sync.

Threat model: this is the **self-hosted** path. The user pastes their own
Polymarket signer private key into `backend/.env`; the same person is the
backend operator and the trader. We deliberately skip Privy / WKWebView /
session-key delegation here — that's v0.2 when we ship a hosted backend.

Failure-mode philosophy:
- Missing `POLYMARKET_PRIVATE_KEY` → `MissingCredentialsError` → API returns
  503 with a clear message. Never auto-fall-back to a fake order.
- Invalid market (no `condition_id` or no token id for the chosen outcome) →
  `InvalidMarketError` → API returns 422.
- Anything else (CLOB error, network failure, signing failure, insufficient
  USDC, etc.) → bubbles as `OrderPlacementError` with the underlying message.

Order type: FOK (fill-or-kill) market orders only in this PR. GTC / GTD /
post-only / cancel are deferred — the v0.1 UX is "Buy X dollars at market or
nothing", which FOK encodes exactly. See PR description for the deferral list.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

log = logging.getLogger(__name__)

# Polygon mainnet. Polymarket's CLOB does not run on Amoy testnet for real
# trading; the SDK's AMOY constant exists for SDK dev only.
POLYGON_CHAIN_ID = 137
DEFAULT_CLOB_HOST = "https://clob.polymarket.com"

Outcome = Literal["Yes", "No"]
Side = Literal["BUY", "SELL"]


class TradingError(RuntimeError):
    """Base for anything trading-specific."""


class MissingCredentialsError(TradingError):
    """`POLYMARKET_PRIVATE_KEY` (or related) is not configured."""


class InvalidMarketError(TradingError):
    """The market is missing the CLOB ids needed to trade it."""


class OrderPlacementError(TradingError):
    """The CLOB rejected the order, or something else failed mid-placement."""


@dataclass(frozen=True, slots=True)
class OrderResult:
    order_id: str | None
    status: str
    transaction_hash: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Credentials:
    """Resolved env state. Cached on first use; cleared by tests via
    `_reset_credentials_cache_for_tests()`."""

    private_key: str
    funder: str | None
    signature_type: int
    clob_host: str


_creds_cache: _Credentials | None = None


def _reset_credentials_cache_for_tests() -> None:
    """Tests mutate env between cases; clear the singleton so each one re-reads."""
    global _creds_cache
    _creds_cache = None


def _load_credentials() -> _Credentials:
    """Read env once. Fail fast and loud if the private key is missing — we
    never want a 'silent fallback' that pretends to place an order."""
    global _creds_cache
    if _creds_cache is not None:
        return _creds_cache

    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY", "").strip()
    if not private_key:
        raise MissingCredentialsError(
            "POLYMARKET_PRIVATE_KEY is not set. Export your Polymarket signer "
            "key from polymarket.com (wallet → export private key) and put it "
            "in backend/.env. Never commit it."
        )

    # Default signature_type=1 (proxy / Magic-style funder) because that's what
    # 99% of polymarket.com accounts are. signature_type=0 is for self-custody
    # EOAs that hold USDC directly. Override with POLYMARKET_SIGNATURE_TYPE.
    sig_type_raw = os.environ.get("POLYMARKET_SIGNATURE_TYPE", "1").strip()
    try:
        signature_type = int(sig_type_raw)
    except ValueError as exc:
        raise MissingCredentialsError(
            f"POLYMARKET_SIGNATURE_TYPE must be 0, 1, or 2; got {sig_type_raw!r}"
        ) from exc
    if signature_type not in (0, 1, 2):
        raise MissingCredentialsError(
            f"POLYMARKET_SIGNATURE_TYPE must be 0, 1, or 2; got {signature_type}"
        )

    funder = os.environ.get("POLYMARKET_FUNDER_ADDRESS", "").strip() or None
    if signature_type != 0 and not funder:
        raise MissingCredentialsError(
            "POLYMARKET_FUNDER_ADDRESS is required when "
            "POLYMARKET_SIGNATURE_TYPE != 0. The funder is the proxy "
            "contract that actually holds your USDC — you can find it on "
            "polymarket.com under wallet / deposit address."
        )

    clob_host = (
        os.environ.get("POLYMARKET_CLOB_HOST", DEFAULT_CLOB_HOST).strip()
        or DEFAULT_CLOB_HOST
    )

    _creds_cache = _Credentials(
        private_key=private_key,
        funder=funder,
        signature_type=signature_type,
        clob_host=clob_host,
    )
    return _creds_cache


# Lazy module imports keep the test suite (which mocks the SDK) from needing
# py_clob_client + web3 installed in CI as test deps. The runtime image has them.
def _build_client():  # type: ignore[no-untyped-def]
    """Construct an authenticated `ClobClient` ready to post orders.

    Does the L1 → L2 derivation (`create_or_derive_api_creds`) on first call.
    Result is **not** cached across calls in this PR — the SDK's auth state is
    not obviously thread-safe and we'd rather pay the small extra round trip
    than chase a heisenbug. Cache it later if /order latency becomes an issue.
    """
    from py_clob_client.client import ClobClient  # type: ignore[import-not-found]

    creds = _load_credentials()
    kwargs: dict[str, Any] = {
        "key": creds.private_key,
        "chain_id": POLYGON_CHAIN_ID,
        "signature_type": creds.signature_type,
    }
    if creds.funder:
        kwargs["funder"] = creds.funder
    client = ClobClient(creds.clob_host, **kwargs)
    # Derive HMAC API creds from the EOA signature. Idempotent on Polymarket's
    # side — same key → same creds across calls.
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def _resolve_token_id(
    *,
    outcome: Outcome,
    clob_token_yes: str | None,
    clob_token_no: str | None,
) -> str:
    if outcome == "Yes":
        if not clob_token_yes:
            raise InvalidMarketError(
                "Market has no YES clob_token_id; cannot place a Yes-side order."
            )
        return clob_token_yes
    if outcome == "No":
        if not clob_token_no:
            raise InvalidMarketError(
                "Market has no NO clob_token_id; cannot place a No-side order."
            )
        return clob_token_no
    raise InvalidMarketError(f"Unknown outcome {outcome!r}; expected 'Yes' or 'No'.")


def _normalize_response(raw: Any) -> OrderResult:
    """py-clob-client's `post_order` returns a dict (per the SDK source); be
    defensive about shape because the API has been known to add fields."""
    data: dict[str, Any] = raw if isinstance(raw, dict) else {"raw": raw}
    order_id = (
        data.get("orderID")
        or data.get("order_id")
        or data.get("id")
    )
    status = str(data.get("status") or ("ok" if data.get("success") else "unknown"))
    tx_hash = data.get("transactionHash") or data.get("transaction_hash")
    return OrderResult(
        order_id=str(order_id) if order_id else None,
        status=status,
        transaction_hash=str(tx_hash) if tx_hash else None,
        raw=data,
    )


async def place_order(
    *,
    condition_id: str,
    outcome: Outcome,
    size_usdc: float,
    side: Side,
    clob_token_yes: str | None,
    clob_token_no: str | None,
) -> OrderResult:
    """Place a FOK market order.

    `condition_id` is taken for logging / future use (cancellation, lookup);
    the SDK only needs the `token_id`. We accept it explicitly so callers
    can't accidentally trade the wrong market by passing only token ids.
    """
    if size_usdc <= 0:
        raise InvalidMarketError(f"size_usdc must be > 0; got {size_usdc}")
    if side not in ("BUY", "SELL"):
        raise InvalidMarketError(f"side must be BUY or SELL; got {side!r}")

    token_id = _resolve_token_id(
        outcome=outcome,
        clob_token_yes=clob_token_yes,
        clob_token_no=clob_token_no,
    )

    log.info(
        "trading: placing %s %s on condition_id=%s for $%.2f USDC (token=%s)",
        side, outcome, condition_id, size_usdc, token_id,
    )

    # py-clob-client is synchronous and does HTTP + EIP-712 signing inline.
    # Run it on the default executor so we don't block the FastAPI event loop.
    return await asyncio.to_thread(
        _place_order_sync,
        token_id=token_id,
        size_usdc=size_usdc,
        side=side,
    )


def _place_order_sync(*, token_id: str, size_usdc: float, side: Side) -> OrderResult:
    """The synchronous half — runs in a worker thread so it doesn't block the loop."""
    from py_clob_client.clob_types import (  # type: ignore[import-not-found]
        MarketOrderArgs,
        OrderType,
    )
    from py_clob_client.order_builder.constants import BUY, SELL  # type: ignore[import-not-found]

    sdk_side = BUY if side == "BUY" else SELL
    client = _build_client()
    args = MarketOrderArgs(token_id=token_id, amount=float(size_usdc), side=sdk_side)
    try:
        signed = client.create_market_order(args)
        raw = client.post_order(signed, orderType=OrderType.FOK)
    except Exception as exc:  # noqa: BLE001 — surface SDK errors to the user
        log.exception("trading: order placement failed")
        raise OrderPlacementError(str(exc)) from exc

    result = _normalize_response(raw)
    log.info(
        "trading: order posted (status=%s, order_id=%s, tx=%s)",
        result.status, result.order_id, result.transaction_hash,
    )
    return result
