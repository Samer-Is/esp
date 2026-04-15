"""Probability adjustment constants for event types."""

from src.signals.events import EventType

# How much each event shifts the benefitting team's win probability
PROBABILITY_ADJUSTMENTS = {
    # LoL events
    EventType.BARON_KILL: 0.12,
    EventType.ELDER_DRAGON: 0.15,
    EventType.DRAGON_SOUL: 0.10,
    EventType.ACE: 0.10,
    EventType.INHIBITOR_DESTROYED: 0.08,
    EventType.TOWER_DESTROYED: 0.02,
    EventType.GOLD_LEAD_3K: 0.05,
    EventType.GOLD_LEAD_5K: 0.08,
    EventType.GOLD_LEAD_10K: 0.12,

    # Dota 2 events
    EventType.ROSHAN_KILL: 0.08,
    EventType.BARRACKS_DESTROYED: 0.12,
    EventType.MEGA_CREEPS: 0.25,

    # CS2 events
    EventType.ROUND_WIN: 0.03,
    EventType.MATCH_POINT: 0.20,
    EventType.MAP_WIN: 0.25,
    EventType.ECONOMY_BREAK: 0.05,

    # Shared
    EventType.GAME_END: 0.0,  # resolved — no trade needed
}

# Team name aliases for fuzzy matching
TEAM_ALIASES = {
    "T1": ["T1", "SK Telecom T1", "SKT T1", "SKT"],
    "Gen.G": ["Gen.G", "GenG", "Gen.G Esports"],
    "JDG": ["JDG", "JD Gaming", "JDG Intel"],
    "BLG": ["BLG", "Bilibili Gaming"],
    "Fnatic": ["Fnatic", "FNC"],
    "G2": ["G2", "G2 Esports"],
    "Cloud9": ["Cloud9", "C9"],
    "Team Liquid": ["Team Liquid", "TL", "Liquid"],
    "100 Thieves": ["100 Thieves", "100T"],
    "NRG": ["NRG", "NRG Esports"],
    "NAVI": ["NAVI", "Natus Vincere", "Na'Vi"],
    "FaZe": ["FaZe", "FaZe Clan"],
    "Vitality": ["Vitality", "Team Vitality"],
    "MOUZ": ["MOUZ", "mousesports"],
    "Spirit": ["Spirit", "Team Spirit"],
    "OG": ["OG"],
    "Tundra": ["Tundra", "Tundra Esports"],
    "Gaimin Gladiators": ["Gaimin Gladiators", "GG"],
}
