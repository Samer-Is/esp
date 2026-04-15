"""ESP — Esports Signal Parser & Polymarket Trader.

Main orchestrator: starts data sources, runs polling loops,
detects events, evaluates signals, and executes trades.
"""

import asyncio
import logging
import signal
import sys

from config.settings import (
    DRY_RUN,
    LIVE_CHECK_INTERVAL,
    MATCH_POLL_INTERVAL,
    LOG_LEVEL,
)
from src.data_sources.lol_esports import LoLEsportsSource
from src.signals.signal_detector import SignalDetector
from src.trading.market_finder import MarketFinder
from src.trading.polymarket_client import PolymarketClient
from src.trading.order_executor import OrderExecutor
from src.trading.position_tracker import PositionTracker
from src.risk.risk_manager import RiskManager
from src.logging_utils.activity_logger import log_activity
from src.logging_utils.trade_logger import init_db

logger = logging.getLogger("esp")


class ESPBot:
    """Main bot orchestrator."""

    def __init__(self) -> None:
        self._running = False

        # Trading stack
        self.poly_client = PolymarketClient()
        self.market_finder = MarketFinder()
        self.position_tracker = PositionTracker()
        self.risk_manager = RiskManager(self.position_tracker)
        self.order_executor = OrderExecutor(self.poly_client)
        self.signal_detector = SignalDetector(self.market_finder)

        # Data sources
        self.lol_source = LoLEsportsSource()

    async def start(self) -> None:
        """Initialize everything and begin polling."""
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        mode = "DRY_RUN" if DRY_RUN else "LIVE"
        log_activity("SYSTEM", f"ESP Bot starting in {mode} mode")
        logger.info("ESP Bot starting in %s mode", mode)

        # Database
        init_db()

        # Polymarket
        self.poly_client.connect()

        # Data sources
        await self.lol_source.start()

        # Pre-fetch markets
        await self.market_finder.refresh()

        self._running = True
        log_activity("SYSTEM", "All systems initialized — entering main loop")

        await self._main_loop()

    async def _main_loop(self) -> None:
        """Discover live matches, poll them, detect events, trade."""
        tracked_matches: dict[str, dict] = {}  # game_id → match info

        while self._running:
            try:
                # --- Discover live matches ---
                live = await self.lol_source.get_live_matches()
                new_ids = {m["game_id"] for m in live}

                # Add newly discovered matches
                for match in live:
                    gid = match["game_id"]
                    if gid not in tracked_matches:
                        tracked_matches[gid] = match
                        log_activity("DATA", f"Now tracking: {match['match_name']} (id={gid})")
                        logger.info("Tracking new match: %s", match["match_name"])

                # Remove ended matches
                ended = [gid for gid in tracked_matches if gid not in new_ids]
                for gid in ended:
                    name = tracked_matches[gid]["match_name"]
                    log_activity("DATA", f"Match ended/removed: {name}")
                    del tracked_matches[gid]

                if not tracked_matches:
                    logger.debug("No live matches — sleeping %ds", LIVE_CHECK_INTERVAL)
                    await asyncio.sleep(LIVE_CHECK_INTERVAL)
                    continue

                # --- Poll each tracked match ---
                for gid, match_info in list(tracked_matches.items()):
                    if not self._running:
                        break

                    state = await self.lol_source.poll_match_state(gid)
                    if state is None:
                        continue

                    previous = self.lol_source.update_previous(gid, state)
                    if previous is None:
                        continue  # first poll — no comparison yet

                    # Detect events
                    events = self.lol_source.detect_events(state, previous)
                    for event in events:
                        log_activity(
                            "DATA",
                            f"Event: {event.event_type.value} → {event.benefitting_team} "
                            f"in {event.match_name}",
                        )

                        # Check for trading signal
                        signal_result = await self.signal_detector.evaluate(event)
                        if signal_result is None:
                            continue

                        # Risk check
                        decision = self.risk_manager.evaluate(signal_result)
                        if not decision["approved"]:
                            continue

                        # Execute trade
                        bet_amount = decision["bet_amount"]
                        resp = self.order_executor.execute(signal_result, bet_amount)

                        # Record trade
                        fill_price = signal_result.market_price  # approximate for DRY_RUN
                        shares = bet_amount / fill_price if fill_price > 0 else 0
                        self.position_tracker.record_trade(
                            signal_result, bet_amount, fill_price, shares
                        )

                    await asyncio.sleep(MATCH_POLL_INTERVAL)

            except Exception:
                logger.exception("Error in main loop")
                log_activity("ERROR", "Exception in main loop — see logs")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        log_activity("SYSTEM", "ESP Bot shutting down")
        logger.info("Shutting down...")
        await self.lol_source.stop()


async def run() -> None:
    bot = ESPBot()

    loop = asyncio.get_event_loop()

    def _shutdown():
        asyncio.ensure_future(bot.stop())

    # Register signal handlers for graceful shutdown
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)

    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
