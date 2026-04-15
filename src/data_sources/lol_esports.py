import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from config.settings import LOL_API_KEY, LOL_ESPORTS_API, LOL_FEED_API
from src.data_sources.base_source import BaseDataSource
from src.signals.events import Game, EventType, GameEvent

logger = logging.getLogger(__name__)

HEADERS = {"x-api-key": LOL_API_KEY}


class LoLEsportsSource(BaseDataSource):
    """Polls the Riot LoL Esports live API for real-time match data."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._previous_states: dict[str, dict] = {}

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=15, headers=HEADERS)
        logger.info("LoL Esports data source started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_live_matches(self) -> List[dict]:
        """Call getLive and return list of live game IDs with team info."""
        resp = await self._client.get(
            f"{LOL_ESPORTS_API}/getLive", params={"hl": "en-US"}
        )
        resp.raise_for_status()
        data = resp.json()

        matches = []
        schedule = data.get("data", {}).get("schedule", {})
        events = schedule.get("events", [])
        for event in events:
            match_obj = event.get("match", {})
            games = match_obj.get("games", [])
            teams = match_obj.get("teams", [])
            team_a = teams[0].get("name", "Unknown") if len(teams) > 0 else "Unknown"
            team_b = teams[1].get("name", "Unknown") if len(teams) > 1 else "Unknown"

            for game in games:
                state = game.get("state", "")
                if state == "inProgress":
                    matches.append({
                        "game_id": str(game.get("id", "")),
                        "team_a": team_a,
                        "team_b": team_b,
                        "match_name": f"{team_a} vs {team_b}",
                        "league": event.get("league", {}).get("name", ""),
                    })
        return matches

    async def poll_match_state(self, match_id: str) -> Optional[dict]:
        """Fetch the latest window frame for a game."""
        try:
            resp = await self._client.get(f"{LOL_FEED_API}/window/{match_id}")
            resp.raise_for_status()
            data = resp.json()

            frames = data.get("frames", [])
            if not frames:
                return None

            frame = frames[-1]  # latest frame
            meta = data.get("gameMetadata", {})

            return {
                "game_id": match_id,
                "blue_team": meta.get("blueTeamMetadata", {}).get("teamName", "Blue"),
                "red_team": meta.get("redTeamMetadata", {}).get("teamName", "Red"),
                "game_state": frame.get("gameState", ""),
                "blue": self._parse_team(frame.get("blueTeam", {})),
                "red": self._parse_team(frame.get("redTeam", {})),
            }
        except httpx.HTTPError as e:
            logger.warning("Failed to poll match %s: %s", match_id, e)
            return None

    @staticmethod
    def _parse_team(team: dict) -> dict:
        dragons = team.get("dragons", [])
        dragon_count = len(dragons) if isinstance(dragons, list) else int(dragons or 0)
        return {
            "totalGold": team.get("totalGold", 0),
            "totalKills": team.get("totalKills", 0),
            "towers": team.get("towers", 0),
            "inhibitors": team.get("inhibitors", 0),
            "dragons": dragon_count,
            "barons": team.get("barons", 0),
        }

    def detect_events(self, current: dict, previous: dict) -> List[GameEvent]:
        """Compare two consecutive frames and return detected events."""
        events: List[GameEvent] = []
        if not current or not previous:
            return events

        game_id = current["game_id"]
        blue_team = current["blue_team"]
        red_team = current["red_team"]
        match_name = f"{blue_team} vs {red_team}"
        now = datetime.now(timezone.utc)

        cur_blue = current["blue"]
        cur_red = current["red"]
        prev_blue = previous["blue"]
        prev_red = previous["red"]

        # --- Baron kills ---
        if cur_blue["barons"] > prev_blue["barons"]:
            events.append(self._event(EventType.BARON_KILL, blue_team, game_id, match_name, now, {"side": "blue"}))
        if cur_red["barons"] > prev_red["barons"]:
            events.append(self._event(EventType.BARON_KILL, red_team, game_id, match_name, now, {"side": "red"}))

        # --- Dragon Soul (4 dragons) ---
        if cur_blue["dragons"] >= 4 and prev_blue["dragons"] < 4:
            events.append(self._event(EventType.DRAGON_SOUL, blue_team, game_id, match_name, now, {"dragons": cur_blue["dragons"]}))
        if cur_red["dragons"] >= 4 and prev_red["dragons"] < 4:
            events.append(self._event(EventType.DRAGON_SOUL, red_team, game_id, match_name, now, {"dragons": cur_red["dragons"]}))

        # --- Elder Dragon (dragons > 4) ---
        if cur_blue["dragons"] > 4 and cur_blue["dragons"] > prev_blue["dragons"] and prev_blue["dragons"] >= 4:
            events.append(self._event(EventType.ELDER_DRAGON, blue_team, game_id, match_name, now, {"dragons": cur_blue["dragons"]}))
        if cur_red["dragons"] > 4 and cur_red["dragons"] > prev_red["dragons"] and prev_red["dragons"] >= 4:
            events.append(self._event(EventType.ELDER_DRAGON, red_team, game_id, match_name, now, {"dragons": cur_red["dragons"]}))

        # --- Inhibitor destroyed ---
        if cur_blue["inhibitors"] > prev_blue["inhibitors"]:
            events.append(self._event(EventType.INHIBITOR_DESTROYED, blue_team, game_id, match_name, now, {}))
        if cur_red["inhibitors"] > prev_red["inhibitors"]:
            events.append(self._event(EventType.INHIBITOR_DESTROYED, red_team, game_id, match_name, now, {}))

        # --- Tower destroyed ---
        if cur_blue["towers"] > prev_blue["towers"]:
            events.append(self._event(EventType.TOWER_DESTROYED, blue_team, game_id, match_name, now, {}))
        if cur_red["towers"] > prev_red["towers"]:
            events.append(self._event(EventType.TOWER_DESTROYED, red_team, game_id, match_name, now, {}))

        # --- Ace (5 kills in short span — approximated by kill diff) ---
        blue_kill_diff = cur_blue["totalKills"] - prev_blue["totalKills"]
        red_kill_diff = cur_red["totalKills"] - prev_red["totalKills"]
        if blue_kill_diff >= 5:
            events.append(self._event(EventType.ACE, blue_team, game_id, match_name, now, {"kills": blue_kill_diff}))
        if red_kill_diff >= 5:
            events.append(self._event(EventType.ACE, red_team, game_id, match_name, now, {"kills": red_kill_diff}))

        # --- Gold lead swings ---
        cur_gold_diff = cur_blue["totalGold"] - cur_red["totalGold"]
        prev_gold_diff = prev_blue["totalGold"] - prev_red["totalGold"]
        gold_swing = cur_gold_diff - prev_gold_diff

        abs_gold_diff = abs(cur_gold_diff)
        leader = blue_team if cur_gold_diff > 0 else red_team

        if abs(gold_swing) >= 3000:
            if abs_gold_diff >= 10000:
                events.append(self._event(EventType.GOLD_LEAD_10K, leader, game_id, match_name, now, {"gold_diff": cur_gold_diff}))
            elif abs_gold_diff >= 5000:
                events.append(self._event(EventType.GOLD_LEAD_5K, leader, game_id, match_name, now, {"gold_diff": cur_gold_diff}))
            else:
                events.append(self._event(EventType.GOLD_LEAD_3K, leader, game_id, match_name, now, {"gold_diff": cur_gold_diff}))

        # --- Game end ---
        if current.get("game_state") == "finished" and previous.get("game_state") != "finished":
            winner = blue_team if cur_blue["totalGold"] > cur_red["totalGold"] else red_team
            events.append(self._event(EventType.GAME_END, winner, game_id, match_name, now, {}))

        return events

    @staticmethod
    def _event(etype: EventType, team: str, game_id: str, match_name: str, ts: datetime, details: dict) -> GameEvent:
        return GameEvent(
            game=Game.LOL,
            event_type=etype,
            benefitting_team=team,
            match_id=game_id,
            match_name=match_name,
            timestamp=ts,
            details=details,
        )

    def update_previous(self, game_id: str, state: dict) -> Optional[dict]:
        """Store current state as previous; return the old previous state."""
        prev = self._previous_states.get(game_id)
        self._previous_states[game_id] = state
        return prev
