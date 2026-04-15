import logging

from config.constants import PROBABILITY_ADJUSTMENTS
from src.signals.events import GameEvent, EventType

logger = logging.getLogger(__name__)


def estimate_probability(
    event: GameEvent,
    current_market_price: float,
) -> float:
    """
    Estimate the post-event win probability for the benefitting team.

    Simple additive model: new_prob = current_price + adjustment.
    Clamped to [0.01, 0.99].
    """
    adjustment = PROBABILITY_ADJUSTMENTS.get(event.event_type, 0.0)
    new_prob = current_market_price + adjustment
    new_prob = max(0.01, min(0.99, new_prob))

    logger.debug(
        "Probability: %s on %s | price=%.3f + adj=%.3f → %.3f",
        event.event_type.value,
        event.match_name,
        current_market_price,
        adjustment,
        new_prob,
    )
    return new_prob
