import logging
import time
from typing import Optional

import httpx

from config.settings import POLYMARKET_GAMMA_API, MIN_MARKET_LIQUIDITY, MARKET_REFRESH_INTERVAL
from config.constants import TEAM_ALIASES

logger = logging.getLogger(__name__)

# Tags to try when searching for esports markets
ESPORTS_TAGS = ["esports", "league-of-legends", "dota-2", "counter-strike"]


class MarketFinder:
    """Finds active esports markets on Polymarket via the Gamma API."""

    def __init__(self) -> None:
        self._cache: list[dict] = []
        self._last_refresh: float = 0.0

    async def refresh(self) -> list[dict]:
        """Fetch all active esports markets from Gamma API."""
        markets: list[dict] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for tag in ESPORTS_TAGS:
                try:
                    resp = await client.get(
                        f"{POLYMARKET_GAMMA_API}/events",
                        params={"tag": tag, "active": "true", "closed": "false"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, list):
                        markets.extend(data)
                except httpx.HTTPError as e:
                    logger.warning("Gamma API error for tag '%s': %s", tag, e)

        # Deduplicate by event id
        seen_ids: set[str] = set()
        unique: list[dict] = []
        for m in markets:
            mid = str(m.get("id", ""))
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                unique.append(m)

        self._cache = unique
        self._last_refresh = time.time()
        logger.info("MarketFinder refreshed: %d esports events found", len(unique))
        return unique

    async def get_markets(self) -> list[dict]:
        """Return cached markets, refreshing if stale."""
        if time.time() - self._last_refresh > MARKET_REFRESH_INTERVAL:
            await self.refresh()
        return self._cache

    def _team_names(self, team: str) -> list[str]:
        """Return all known name variants for a team (original + aliases)."""
        names = [team.lower()]
        for canonical, aliases in TEAM_ALIASES.items():
            if team.lower() == canonical.lower() or team.lower() in [a.lower() for a in aliases]:
                names.append(canonical.lower())
                names.extend(a.lower() for a in aliases)
        return list(set(names))

    async def find_market_for_match(
        self, team_a: str, team_b: str
    ) -> Optional[dict]:
        """Find a Polymarket event matching two team names."""
        markets = await self.get_markets()
        team_a_names = self._team_names(team_a)
        team_b_names = self._team_names(team_b)

        for event in markets:
            title = event.get("title", "").lower()
            description = event.get("description", "").lower()
            search_text = f"{title} {description}"

            a_match = any(n in search_text for n in team_a_names)
            b_match = any(n in search_text for n in team_b_names)
            if a_match and b_match:
                # Check liquidity on the sub-markets
                sub_markets = event.get("markets", [])
                for sm in sub_markets:
                    liquidity = float(sm.get("liquidityNum", 0) or 0)
                    if liquidity >= MIN_MARKET_LIQUIDITY and sm.get("active"):
                        return {
                            "event": event,
                            "market": sm,
                            "market_id": sm.get("id", ""),
                            "question": sm.get("question", ""),
                        }
        return None

    def get_token_ids(self, market: dict) -> dict:
        """Extract YES/NO token IDs from a market dict."""
        tokens = market.get("market", {}).get("clobTokenIds", "")
        if isinstance(tokens, str):
            parts = [t.strip() for t in tokens.split(",") if t.strip()]
        elif isinstance(tokens, list):
            parts = tokens
        else:
            parts = []

        result = {}
        if len(parts) >= 1:
            result["YES"] = parts[0]
        if len(parts) >= 2:
            result["NO"] = parts[1]
        return result
