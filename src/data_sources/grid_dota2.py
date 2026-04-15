import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from config.settings import GRID_API_KEY, GRID_CENTRAL_DATA, GRID_LIVE_DATA
from src.data_sources.base_source import BaseDataSource
from src.signals.events import Game, EventType, GameEvent

logger = logging.getLogger(__name__)

# GRID title ID for Dota 2
DOTA2_TITLE_ID = 2

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
""" % DOTA2_TITLE_ID

SERIES_STATE_QUERY = """
query($id: ID!) {
  seriesState(id: $id) {
    teams { name score players { name kills deaths assists netWorth } }
    maps {
      number state
      teams {
        side score totalGold
        objectives { type completedAt }
      }
      clock winner
    }
  }
}
"""


class GridDota2Source(BaseDataSource):
    """Polls GRID Open Access API for live Dota 2 match data via GraphQL."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._previous_states: dict[str, dict] = {}

    async def start(self) -> None:
        if not GRID_API_KEY:
            logger.warning("GRID_API_KEY not set — Dota 2 source disabled")
            return
        self._client = httpx.AsyncClient(
            timeout=15,
            headers={"x-auth-key": GRID_API_KEY, "Content-Type": "application/json"},
        )
        logger.info("GRID Dota 2 data source started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _graphql(self, url: str, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query and return the data."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._client.post(url, json=payload)
        if resp.status_code == 204 or not resp.content:
            return {}
        resp.raise_for_status()
        result = resp.json()
        if "errors" in result:
            logger.error("GraphQL errors: %s", result["errors"])
        return result.get("data", {})

    async def get_live_matches(self) -> List[dict]:
        """Find live Dota 2 series via GRID central-data."""
        if not self._client:
            return []

        try:
            data = await self._graphql(GRID_CENTRAL_DATA, LIVE_SERIES_QUERY)
        except httpx.HTTPError as e:
            logger.warning("GRID central-data error: %s", e)
            return []

        matches = []
        edges = data.get("allSeries", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            teams = node.get("teams", [])
            team_a = teams[0].get("name", "Unknown") if len(teams) > 0 else "Unknown"
            team_b = teams[1].get("name", "Unknown") if len(teams) > 1 else "Unknown"
            matches.append({
                "game_id": f"dota2_{node.get('id', '')}",
                "team_a": team_a,
                "team_b": team_b,
                "match_name": f"{team_a} vs {team_b}",
                "tournament": node.get("tournament", {}).get("name", ""),
                "source": "dota2",
            })
        return matches

    async def poll_match_state(self, match_id: str) -> Optional[dict]:
        """Fetch current series state for a Dota 2 match."""
        if not self._client:
            return None

        # Strip dota2_ prefix for GRID API
        grid_id = match_id.replace("dota2_", "")

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
        team_a_map = map_teams[0] if len(map_teams) > 0 else {}
        team_b_map = map_teams[1] if len(map_teams) > 1 else {}

        return {
            "game_id": match_id,
            "team_a": team_a,
            "team_b": team_b,
            "map_number": active_map.get("number", 1),
            "map_state": active_map.get("state", ""),
            "winner": active_map.get("winner"),
            "team_a_data": {
                "side": team_a_map.get("side", ""),
                "score": team_a_map.get("score", 0),
                "totalGold": team_a_map.get("totalGold", 0),
                "objectives": team_a_map.get("objectives", []),
            },
            "team_b_data": {
                "side": team_b_map.get("side", ""),
                "score": team_b_map.get("score", 0),
                "totalGold": team_b_map.get("totalGold", 0),
                "objectives": team_b_map.get("objectives", []),
            },
            "players": {
                team_a: teams[0].get("players", []) if len(teams) > 0 else [],
                team_b: teams[1].get("players", []) if len(teams) > 1 else [],
            },
        }

    def detect_events(self, current: dict, previous: dict) -> List[GameEvent]:
        """Compare two consecutive states and return detected Dota 2 events."""
        events: List[GameEvent] = []
        if not current or not previous:
            return events

        game_id = current["game_id"]
        team_a = current["team_a"]
        team_b = current["team_b"]
        match_name = f"{team_a} vs {team_b}"
        now = datetime.now(timezone.utc)

        cur_a = current["team_a_data"]
        cur_b = current["team_b_data"]
        prev_a = previous["team_a_data"]
        prev_b = previous["team_b_data"]

        # Detect new objectives
        cur_a_objs = {(o["type"], o.get("completedAt", "")) for o in cur_a["objectives"]}
        cur_b_objs = {(o["type"], o.get("completedAt", "")) for o in cur_b["objectives"]}
        prev_a_objs = {(o["type"], o.get("completedAt", "")) for o in prev_a["objectives"]}
        prev_b_objs = {(o["type"], o.get("completedAt", "")) for o in prev_b["objectives"]}

        new_a_objs = cur_a_objs - prev_a_objs
        new_b_objs = cur_b_objs - prev_b_objs

        for team, new_objs in [(team_a, new_a_objs), (team_b, new_b_objs)]:
            for obj_type, completed_at in new_objs:
                obj_lower = obj_type.lower() if obj_type else ""
                if "roshan" in obj_lower:
                    events.append(self._event(EventType.ROSHAN_KILL, team, game_id, match_name, now, {"type": obj_type}))
                elif "barracks" in obj_lower or "rax" in obj_lower:
                    events.append(self._event(EventType.BARRACKS_DESTROYED, team, game_id, match_name, now, {"type": obj_type}))
                elif "tower" in obj_lower:
                    events.append(self._event(EventType.TOWER_DESTROYED, team, game_id, match_name, now, {"type": obj_type}))

        # Check for mega creeps (all 6 barracks)
        a_barracks = sum(1 for o in cur_a["objectives"] if "barracks" in (o.get("type", "").lower()) or "rax" in (o.get("type", "").lower()))
        b_barracks = sum(1 for o in cur_b["objectives"] if "barracks" in (o.get("type", "").lower()) or "rax" in (o.get("type", "").lower()))
        prev_a_barracks = sum(1 for o in prev_a["objectives"] if "barracks" in (o.get("type", "").lower()) or "rax" in (o.get("type", "").lower()))
        prev_b_barracks = sum(1 for o in prev_b["objectives"] if "barracks" in (o.get("type", "").lower()) or "rax" in (o.get("type", "").lower()))

        if a_barracks >= 6 and prev_a_barracks < 6:
            events.append(self._event(EventType.MEGA_CREEPS, team_a, game_id, match_name, now, {"barracks": a_barracks}))
        if b_barracks >= 6 and prev_b_barracks < 6:
            events.append(self._event(EventType.MEGA_CREEPS, team_b, game_id, match_name, now, {"barracks": b_barracks}))

        # Gold lead swings
        cur_diff = cur_a["totalGold"] - cur_b["totalGold"]
        prev_diff = prev_a["totalGold"] - prev_b["totalGold"]
        swing = cur_diff - prev_diff
        abs_diff = abs(cur_diff)
        leader = team_a if cur_diff > 0 else team_b

        if abs(swing) >= 3000:
            if abs_diff >= 10000:
                events.append(self._event(EventType.GOLD_LEAD_10K, leader, game_id, match_name, now, {"gold_diff": cur_diff}))
            elif abs_diff >= 5000:
                events.append(self._event(EventType.GOLD_LEAD_5K, leader, game_id, match_name, now, {"gold_diff": cur_diff}))

        # Team wipe detection via kill surges
        a_kills = sum(p.get("kills", 0) for p in current.get("players", {}).get(team_a, []))
        b_kills = sum(p.get("kills", 0) for p in current.get("players", {}).get(team_b, []))
        prev_a_kills = sum(p.get("kills", 0) for p in previous.get("players", {}).get(team_a, []))
        prev_b_kills = sum(p.get("kills", 0) for p in previous.get("players", {}).get(team_b, []))

        if a_kills - prev_a_kills >= 4:
            events.append(self._event(EventType.ACE, team_a, game_id, match_name, now, {"kills": a_kills - prev_a_kills}))
        if b_kills - prev_b_kills >= 4:
            events.append(self._event(EventType.ACE, team_b, game_id, match_name, now, {"kills": b_kills - prev_b_kills}))

        return events

    @staticmethod
    def _event(etype: EventType, team: str, game_id: str, match_name: str, ts: datetime, details: dict) -> GameEvent:
        return GameEvent(
            game=Game.DOTA2,
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
