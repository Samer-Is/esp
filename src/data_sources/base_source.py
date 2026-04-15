from abc import ABC, abstractmethod
from typing import List, Optional

from src.signals.events import GameEvent


class BaseDataSource(ABC):
    """Abstract base for all game data sources."""

    @abstractmethod
    async def start(self) -> None:
        """Initialize the data source (e.g. create HTTP client)."""

    @abstractmethod
    async def stop(self) -> None:
        """Clean up resources."""

    @abstractmethod
    async def get_live_matches(self) -> List[dict]:
        """Return a list of currently live matches."""

    @abstractmethod
    async def poll_match_state(self, match_id: str) -> Optional[dict]:
        """Fetch current state for a specific match."""

    @abstractmethod
    def detect_events(self, current: dict, previous: dict) -> List[GameEvent]:
        """Compare two consecutive states and return detected events."""
