import logging

from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

from config.settings import DRY_RUN
from src.signals.events import TradingSignal
from src.trading.polymarket_client import PolymarketClient
from src.logging_utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Executes trades on Polymarket CLOB (or simulates in DRY_RUN)."""

    def __init__(self, poly_client: PolymarketClient) -> None:
        self._poly = poly_client

    def execute(self, signal: TradingSignal, bet_amount_usd: float) -> dict:
        """Place a Fill-Or-Kill market order. Returns order response or dry-run stub."""
        if DRY_RUN:
            result = {
                "dry_run": True,
                "token_id": signal.token_id,
                "amount": bet_amount_usd,
                "direction": signal.direction,
                "market_price": signal.market_price,
                "estimated_probability": signal.estimated_probability,
                "edge": signal.edge,
                "status": "SIMULATED",
            }
            log_activity(
                "TRADE",
                f"[DRY_RUN] Would trade ${bet_amount_usd:.2f} {signal.direction} "
                f"on {signal.event.match_name} | edge={signal.edge:.3f} "
                f"| price={signal.market_price:.3f}",
            )
            logger.info("DRY_RUN trade: %s", result)
            return result

        order_args = MarketOrderArgs(
            token_id=signal.token_id,
            amount=bet_amount_usd,
            side=BUY,
            order_type=OrderType.FOK,
        )

        signed_order = self._poly.client.create_market_order(order_args)
        resp = self._poly.client.post_order(signed_order, OrderType.FOK)

        log_activity(
            "TRADE",
            f"EXECUTED ${bet_amount_usd:.2f} {signal.direction} "
            f"on {signal.event.match_name} | edge={signal.edge:.3f} "
            f"| response={resp}",
        )
        logger.info("Order response: %s", resp)
        return resp
