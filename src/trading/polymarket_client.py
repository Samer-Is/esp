import logging

from py_clob_client.client import ClobClient

from config.settings import (
    POLYMARKET_CLOB_HOST,
    POLYMARKET_CHAIN_ID,
    POLY_PRIVATE_KEY,
    POLY_WALLET_ADDRESS,
    DRY_RUN,
)

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Thin wrapper around py-clob-client for Polymarket CLOB."""

    def __init__(self) -> None:
        self._client: ClobClient | None = None

    def connect(self) -> None:
        if DRY_RUN:
            logger.info("DRY_RUN mode — Polymarket client not connecting")
            return

        if not POLY_PRIVATE_KEY or not POLY_WALLET_ADDRESS:
            raise RuntimeError(
                "POLY_PRIVATE_KEY and POLY_WALLET_ADDRESS must be set in .env"
            )

        self._client = ClobClient(
            POLYMARKET_CLOB_HOST,
            key=POLY_PRIVATE_KEY,
            chain_id=POLYMARKET_CHAIN_ID,
            signature_type=0,
            funder=POLY_WALLET_ADDRESS,
        )
        creds = self._client.create_or_derive_api_creds()
        self._client.set_api_creds(creds)
        logger.info("Polymarket CLOB client connected")

    @property
    def client(self) -> ClobClient:
        if self._client is None:
            raise RuntimeError("Polymarket client not connected — call connect() first")
        return self._client

    def get_order_book(self, token_id: str) -> dict:
        return self.client.get_order_book(token_id)

    def get_midpoint(self, token_id: str) -> float:
        book = self.get_order_book(token_id)
        best_bid = float(book.get("bids", [{}])[0].get("price", 0)) if book.get("bids") else 0.0
        best_ask = float(book.get("asks", [{}])[0].get("price", 1)) if book.get("asks") else 1.0
        return (best_bid + best_ask) / 2
