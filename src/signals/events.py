from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class Game(Enum):
    DOTA2 = "dota2"
    CS2 = "cs2"
    LOL = "lol"


class EventType(Enum):
    BARON_KILL = "baron_kill"
    ELDER_DRAGON = "elder_dragon"
    DRAGON_SOUL = "dragon_soul"
    INHIBITOR_DESTROYED = "inhibitor_destroyed"
    ROSHAN_KILL = "roshan_kill"
    BARRACKS_DESTROYED = "barracks_destroyed"
    MEGA_CREEPS = "mega_creeps"
    ROUND_WIN = "round_win"
    MATCH_POINT = "match_point"
    MAP_WIN = "map_win"
    ECONOMY_BREAK = "economy_break"
    ACE = "ace"
    TOWER_DESTROYED = "tower_destroyed"
    GOLD_LEAD_3K = "gold_lead_3k"
    GOLD_LEAD_5K = "gold_lead_5k"
    GOLD_LEAD_10K = "gold_lead_10k"
    GAME_END = "game_end"


@dataclass
class GameEvent:
    game: Game
    event_type: EventType
    benefitting_team: str
    match_id: str
    match_name: str
    timestamp: datetime
    details: dict


@dataclass
class TradingSignal:
    event: GameEvent
    estimated_probability: float
    market_price: float
    edge: float
    market_id: str
    token_id: str
    direction: str  # BUY_YES or BUY_NO
