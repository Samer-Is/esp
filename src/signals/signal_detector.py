import logging
from typing import Optional

from config.settings import MIN_EDGE_THRESHOLD
from src.signals.events import GameEvent, TradingSignal
from src.signals.probability import estimate_probability
from src.trading.market_finder import MarketFinder
from src.logging_utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class SignalDetector:
    """Converts game events into trading signals when edge exceeds threshold."""

    def __init__(self, market_finder: MarketFinder) -> None:
        self._market_finder = market_finder

    async def evaluate(self, event: GameEvent) -> Optional[TradingSignal]:
        """
        Given a detected game event:
        1. Find matching Polymarket market
        2. Get current market price
        3. Estimate post-event probability
        4. If edge >= threshold → return TradingSignal
        """
        log_activity(
            "SIGNAL",
            f"Event detected: {event.event_type.value} benefitting {event.benefitting_team} "
            f"in {event.match_name}",
        )

        # Extract team names for market search
        parts = event.match_name.split(" vs ")
        if len(parts) != 2:
            log_activity("SKIP", f"Cannot parse team names from '{event.match_name}'")
            return None

        team_a, team_b = parts[0].strip(), parts[1].strip()
        market_result = await self._market_finder.find_market_for_match(team_a, team_b)

        if market_result is None:
            log_activity("SKIP", f"No Polymarket market found for {event.match_name}")
            return None

        market = market_result["market"]
        market_id = market_result["market_id"]

        # Get token IDs
        token_ids = self._market_finder.get_token_ids(market_result)
        if not token_ids:
            log_activity("SKIP", f"No token IDs found for market {market_id}")
            return None

        # Determine which side to buy
        question = market_result.get("question", "").lower()
        team_in_question = team_a.lower()

        if event.benefitting_team.lower() == team_a.lower():
            # Benefitting team is team A — buy YES if question asks about team A winning
            if team_in_question in question:
                direction = "BUY_YES"
                token_id = token_ids.get("YES", "")
            else:
                direction = "BUY_NO"
                token_id = token_ids.get("NO", "")
        else:
            # Benefitting team is team B
            if team_in_question in question:
                direction = "BUY_NO"
                token_id = token_ids.get("NO", "")
            else:
                direction = "BUY_YES"
                token_id = token_ids.get("YES", "")

        if not token_id:
            log_activity("SKIP", f"Missing token ID for direction {direction}")
            return None

        # Get current market price (use outcomePrices from market data)
        try:
            outcome_prices = market.get("outcomePrices", "")
            if isinstance(outcome_prices, str):
                prices = [float(p) for p in outcome_prices.strip("[]").split(",") if p.strip()]
            elif isinstance(outcome_prices, list):
                prices = [float(p) for p in outcome_prices]
            else:
                prices = []

            if direction == "BUY_YES" and len(prices) >= 1:
                market_price = prices[0]
            elif direction == "BUY_NO" and len(prices) >= 2:
                market_price = prices[1]
            else:
                market_price = 0.50  # fallback
        except (ValueError, IndexError):
            market_price = 0.50

        # Estimate post-event probability
        estimated_prob = estimate_probability(event, market_price)
        edge = estimated_prob - market_price

        if edge < MIN_EDGE_THRESHOLD:
            log_activity(
                "SKIP",
                f"Edge too low: {edge:.3f} < {MIN_EDGE_THRESHOLD} "
                f"for {event.event_type.value} in {event.match_name}",
            )
            return None

        signal = TradingSignal(
            event=event,
            estimated_probability=estimated_prob,
            market_price=market_price,
            edge=edge,
            market_id=market_id,
            token_id=token_id,
            direction=direction,
        )

        log_activity(
            "SIGNAL",
            f"TRADING SIGNAL: {direction} on {event.match_name} "
            f"| prob={estimated_prob:.3f} price={market_price:.3f} edge={edge:.3f}",
        )

        return signal
