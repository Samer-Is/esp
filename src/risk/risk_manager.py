import logging

from config.settings import (
    MAX_BET_PERCENT,
    MAX_SINGLE_BET_USD,
    MIN_BET_USD,
    MAX_DAILY_LOSS_PERCENT,
    MAX_OPEN_POSITIONS,
    MIN_EDGE_THRESHOLD,
    MIN_MARKET_LIQUIDITY,
    STARTING_CAPITAL,
)
from src.signals.events import TradingSignal
from src.trading.position_tracker import PositionTracker
from src.logging_utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class RiskManager:
    """Determines whether a signal should be traded and at what size."""

    def __init__(self, tracker: PositionTracker) -> None:
        self._tracker = tracker

    def evaluate(self, signal: TradingSignal) -> dict:
        """
        Returns {"approved": bool, "bet_amount": float, "reason": str}.
        """
        # Check minimum edge
        if signal.edge < MIN_EDGE_THRESHOLD:
            return self._reject(f"Edge {signal.edge:.3f} < threshold {MIN_EDGE_THRESHOLD}")

        # Check open position limit
        if self._tracker.open_position_count >= MAX_OPEN_POSITIONS:
            return self._reject(f"Open positions at limit ({MAX_OPEN_POSITIONS})")

        # Check daily loss limit
        daily_loss = self._tracker.today_pnl()
        max_loss = STARTING_CAPITAL * MAX_DAILY_LOSS_PERCENT
        if daily_loss <= -max_loss:
            return self._reject(f"Daily loss ${daily_loss:.2f} hit limit ${-max_loss:.2f}")

        # Calculate bet size
        capital = self._tracker.capital
        bet = min(capital * MAX_BET_PERCENT, MAX_SINGLE_BET_USD)

        if bet < MIN_BET_USD:
            return self._reject(f"Computed bet ${bet:.2f} below minimum ${MIN_BET_USD}")

        log_activity(
            "SIGNAL",
            f"Risk APPROVED: ${bet:.2f} on {signal.event.match_name} "
            f"| edge={signal.edge:.3f}",
        )

        return {"approved": True, "bet_amount": round(bet, 2), "reason": "approved"}

    @staticmethod
    def _reject(reason: str) -> dict:
        log_activity("SKIP", f"Risk REJECTED: {reason}")
        logger.info("Trade rejected: %s", reason)
        return {"approved": False, "bet_amount": 0.0, "reason": reason}
