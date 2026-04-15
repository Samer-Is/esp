import logging
from typing import Optional

from config.settings import STARTING_CAPITAL
from src.logging_utils.trade_logger import (
    insert_trade,
    resolve_trade,
    get_open_trades,
    get_today_trades,
)
from src.signals.events import TradingSignal

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks open positions, capital, and P&L."""

    def __init__(self) -> None:
        self.capital = STARTING_CAPITAL

    def record_trade(self, signal: TradingSignal, bet_amount: float, fill_price: float, shares: float) -> int:
        """Record a new trade in the database."""
        self.capital -= bet_amount
        trade_id = insert_trade(
            game=signal.event.game.value,
            match_name=signal.event.match_name,
            event_type=signal.event.event_type.value,
            signal_probability=signal.estimated_probability,
            market_price=signal.market_price,
            edge=signal.edge,
            direction=signal.direction,
            bet_amount_usd=bet_amount,
            fill_price=fill_price,
            shares=shares,
            market_id=signal.market_id,
            token_id=signal.token_id,
            capital_after=self.capital,
        )
        logger.info(
            "Trade #%d recorded: $%.2f on %s, capital=$%.2f",
            trade_id, bet_amount, signal.event.match_name, self.capital,
        )
        return trade_id

    def resolve(self, trade_id: int, payout: float) -> float:
        """Resolve a trade with payout. Returns profit/loss."""
        open_trades = get_open_trades()
        trade = next((t for t in open_trades if t["id"] == trade_id), None)
        if trade is None:
            logger.warning("Trade #%d not found in open trades", trade_id)
            return 0.0

        pl = payout - trade["bet_amount_usd"]
        self.capital += payout
        resolve_trade(trade_id, payout, pl)
        logger.info("Trade #%d resolved: payout=$%.2f, P&L=$%.2f", trade_id, payout, pl)
        return pl

    @property
    def open_positions(self) -> list[dict]:
        return get_open_trades()

    @property
    def open_position_count(self) -> int:
        return len(self.open_positions)

    def today_pnl(self) -> float:
        trades = get_today_trades()
        return sum(t.get("profit_loss", 0) or 0 for t in trades)
