import asyncio
from src.data_sources.lol_esports import LoLEsportsSource
from src.signals.probability import estimate_probability
from src.signals.events import Game, EventType, GameEvent
from datetime import datetime, timezone

async def test():
    # Test LoL API
    src = LoLEsportsSource()
    await src.start()
    matches = await src.get_live_matches()
    print(f"Live LoL matches: {len(matches)}")
    for m in matches:
        print(f"  {m['match_name']} (id={m['game_id']})")
    await src.stop()

    # Test event detection with mock data
    prev = {
        "game_id": "test", "blue_team": "T1", "red_team": "GenG",
        "game_state": "in_game",
        "blue": {"totalGold": 40000, "totalKills": 8, "towers": 3, "inhibitors": 0, "dragons": 2, "barons": 0},
        "red": {"totalGold": 38000, "totalKills": 6, "towers": 2, "inhibitors": 0, "dragons": 1, "barons": 0},
    }
    curr = {
        "game_id": "test", "blue_team": "T1", "red_team": "GenG",
        "game_state": "in_game",
        "blue": {"totalGold": 45000, "totalKills": 12, "towers": 5, "inhibitors": 1, "dragons": 2, "barons": 1},
        "red": {"totalGold": 38500, "totalKills": 6, "towers": 2, "inhibitors": 0, "dragons": 1, "barons": 0},
    }
    events = src.detect_events(curr, prev)
    print(f"\nMock event detection: {len(events)} events")
    for e in events:
        print(f"  {e.event_type.value} → {e.benefitting_team}")

    # Test probability
    mock_event = GameEvent(
        game=Game.LOL, event_type=EventType.BARON_KILL, benefitting_team="T1",
        match_id="test", match_name="T1 vs GenG", timestamp=datetime.now(timezone.utc), details={}
    )
    prob = estimate_probability(mock_event, 0.55)
    print(f"\nProbability: baron kill at price 0.55 → {prob:.3f}")

asyncio.run(test())
