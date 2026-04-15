import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from config.settings import GRID_API_KEY, GRID_CENTRAL_DATA, GRID_LIVE_DATA
from src.data_sources.base_source import BaseDataSource
from src.signals.events import Game, EventType, GameEvent

logger = logging.getLogger(__name__)

# GRID title ID for CS2 (verify in GRID docs after access)
CS2_TITLE_ID = 1

# GraphQL queries
LIVE_SERIES_QUERY = """
query {
  allSeries(filter: { titleId: %d, status: LIVE }) {
    edges {
      node {
        id
        teams { name score }
        tournament { name }
      }
    }
  }
}
""" % CS2_TITLE_ID

SERIES_STATE_QUERY = """
query($id: ID!) {
  seriesState(id: $id) {
    teams { name score }
    maps {
      number state
      teams {
        side score
      }
      clock winner
    }
  }
}
"""


class GridCS2Source(BaseDataSource):
    """Polls GRID Open Access API for live CS2 match data via GraphQL."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._previous_states: dict[str, dict] = {}

    async def start(self) -> None:
        if not GRID_API_KEY:
            logger.warning("GRID_API_KEY not set — CS2 source disabled")
            return
        self._client = httpx.AsyncClient(
            timeout=15,
            headers={"x-auth-key": GRID_API_KEY, "Content-Type": "application/json"},
        )
        logger.info("GRID CS2 data source started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _graphql(self, url: str, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        result = resp.json()
        if "errors" in result:
            logger.error("GraphQL errors: %s", result["errors"])
        return result.get("data", {})

    async def get_live_matches(self) -> List[dict]:
        """Find live CS2 series via GRID central-data."""
        if not self._client:
            return []

        try:
            data = await self._graphql(GRID_CENTRAL_DATA, LIVE_SERIES_QUERY)
        except httpx.HTTPError as e:
            logger.warning("GRID central-data error (CS2): %s", e)
            return []

        matches = []
        edges = data.get("allSeries", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            teams = node.get("teams", [])
            team_a = teams[0].get("name", "Unknown") if len(teams) > 0 else "Unknown"
            team_b = teams[1].get("name", "Unknown") if len(teams) > 1 else "Unknown"
            matches.append({
                "game_id": f"cs2_{node.get('id', '')}",
                "team_a": team_a,
                "team_b": team_b,
                "match_name": f"{team_a} vs {team_b}",
                "tournament": node.get("tournament", {}).get("name", ""),
                "source": "cs2",
            })
        return matches

    async def poll_match_state(self, match_id: str) -> Optional[dict]:
        """Fetch current series state for a CS2 match."""
        if not self._client:
            return None

        # Strip cs2_ prefix for GRID API
        grid_id = match_id.replace("cs2_", "")

        try:
            data = await self._graphql(
                GRID_LIVE_DATA, SERIES_STATE_QUERY, {"id": grid_id}
            )
        except httpx.HTTPError as e:
            logger.warning("GRID series-state error for %s: %s", match_id, e)
            return None

        ss = data.get("seriesState")
        if not ss:
            return None

        teams = ss.get("teams", [])
        team_a = teams[0].get("name", "Team A") if len(teams) > 0 else "Team A"
        team_b = teams[1].get("name", "Team B") if len(teams) > 1 else "Team B"
        series_score_a = teams[0].get("score", 0) if len(teams) > 0 else 0
        series_score_b = teams[1].get("score", 0) if len(teams) > 1 else 0

        maps = ss.get("maps", [])
        active_map = None
        for m in maps:
            if m.get("state") in ("active", "started", "in_progress"):
                active_map = m
                break
        if active_map is None and maps:
            active_map = maps[-1]

        if active_map is None:
            return None

        map_teams = active_map.get("teams", [])
        rounds_a = map_teams[0].get("score", 0) if len(map_teams) > 0 else 0
        rounds_b = map_teams[1].get("score", 0) if len(map_teams) > 1 else 0

        return {
            "game_id": match_id,
            "team_a": team_a,
            "team_b": team_b,
            "map_number": active_map.get("number", 1),
            "map_state": active_map.get("state", ""),
            "winner": active_map.get("winner"),
            "rounds_a": rounds_a,
            "rounds_b": rounds_b,
            "series_score_a": series_score_a,
            "series_score_b": series_score_b,
            "total_maps": len(maps),
        }

    def detect_events(self, current: dict, previous: dict) -> List[GameEvent]:
        """Compare two consecutive CS2 states and return detected events."""
        events: List[GameEvent] = []
        if not current or not previous:
            return events

        game_id = current["game_id"]
        team_a = current["team_a"]
        team_b = current["team_b"]
        match_name = f"{team_a} vs {team_b}"
        now = datetime.now(timezone.utc)

        cur_ra = current["rounds_a"]
        cur_rb = current["rounds_b"]
        prev_ra = previous["rounds_a"]
        prev_rb = previous["rounds_b"]

        # Round win
        if cur_ra > prev_ra:
            events.append(self._event(EventType.ROUND_WIN, team_a, game_id, match_name, now, {"rounds": cur_ra}))
        if cur_rb > prev_rb:
            events.append(self._event(EventType.ROUND_WIN, team_b, game_id, match_name, now, {"rounds": cur_rb}))

        # Match point (12 rounds in MR13)
        if cur_ra == 12 and prev_ra < 12:
            events.append(self._event(EventType.MATCH_POINT, team_a, game_id, match_name, now, {"rounds": cur_ra}))
        if cur_rb == 12 and prev_rb < 12:
            events.append(self._event(EventType.MATCH_POINT, team_b, game_id, match_name, now, {"rounds": cur_rb}))

        # 5+ round lead
        round_diff = cur_ra - cur_rb
        prev_diff = prev_ra - prev_rb
        if abs(round_diff) >= 5 and abs(prev_diff) < 5:
            leader = team_a if round_diff > 0 else team_b
            events.append(self._event(EventType.ECONOMY_BREAK, leader, game_id, match_name, now, {"round_diff": round_diff}))

        # Map win
        if current.get("winner") and not previous.get("winner"):
            winner = current["winner"]
            benefitting = team_a if "a" in str(winner).lower() or team_a.lower() in str(winner).lower() else team_b
            events.append(self._event(EventType.MAP_WIN, benefitting, game_id, match_name, now, {"map": current.get("map_number")}))

        # Map state changed to finished
        if current.get("map_state") == "finished" and previous.get("map_state") != "finished":
            winner_team = team_a if cur_ra > cur_rb else team_b
            events.append(self._event(EventType.MAP_WIN, winner_team, game_id, match_name, now, {"map": current.get("map_number"), "score": f"{cur_ra}-{cur_rb}"}))

        return events

    @staticmethod
    def _event(etype: EventType, team: str, game_id: str, match_name: str, ts: datetime, details: dict) -> GameEvent:
        return GameEvent(
            game=Game.CS2,
            event_type=etype,
            benefitting_team=team,
            match_id=game_id,
            match_name=match_name,
            timestamp=ts,
            details=details,
        )

    def update_previous(self, game_id: str, state: dict) -> Optional[dict]:
        prev = self._previous_states.get(game_id)
        self._previous_states[game_id] = state
        return prev
