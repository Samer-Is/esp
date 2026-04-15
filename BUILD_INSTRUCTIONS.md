# ESP — Esports Signal Parser & Polymarket Trader
## MASTER BUILD INSTRUCTIONS v2

> **CRITICAL: This file is the single source of truth.** Always refer back to this file before starting any module. Log every action in `ACTIVITY_LOG.md`. Commit frequently to `https://github.com/Samer-Is/esp`.

## CHANGES FROM v1
- REMOVED all GSI / game client dependency. No Dota 2, CS2, or any game needs to be installed.
- REPLACED with GRID Open Access API (Dota 2/CS2) and LoL Esports API (LoL). All HTTP-based.
- Runs on any machine. Cloud-ready from day one.
- Build order: LoL first (instant, no approval), GRID games after approval.

## 1. PROJECT OVERVIEW
Automated bot that detects real-time in-game events from pro esports matches via official APIs before stream viewers see them, then trades on Polymarket esports markets where odds have not yet adjusted. The edge is 15-40 seconds of information advantage. Pure trading profit, no selling.

## 2. DATA SOURCES (All HTTP — No Games Installed)

| Game | Source | Method | Cost | Auth |
|---|---|---|---|---|
| LoL | Riot lolesports unofficial API | REST polling | Free | Public key in header |
| Dota 2 | GRID Open Access | GraphQL polling | Free | API key (apply grid.gg) |
| CS2 | GRID Open Access | GraphQL polling | Free | Same API key |

## 3. ARCHITECTURE
```
[LoL Esports API] ──polling──▶ ┌─────────────────────┐
[GRID Dota 2 API] ──polling──▶ │  SIGNAL DETECTOR     │──▶ [RISK MANAGER]──▶ [ORDER EXECUTOR]──▶ Polymarket
[GRID CS2 API]    ──polling──▶ │  (event detection +  │                     (py-clob-client)
                               │   probability calc)  │
                               └─────────────────────┘
                                         │
                                         ▼
                               [ACTIVITY LOG + TRADE DB]
```

## 4. TECH STACK
- Python 3.11+
- `py-clob-client` — Polymarket CLOB SDK
- `httpx` — async HTTP client for all API calls
- `gql[httpx]` — GraphQL client for GRID API
- `python-dotenv` — config from .env
- `asyncio` — concurrent polling
- `sqlite3` — trade/P&L database

## 5. DIRECTORY STRUCTURE
```
esp/
├── BUILD_INSTRUCTIONS.md
├── ACTIVITY_LOG.md
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── config/
│   ├── __init__.py
│   ├── settings.py              # Load env vars
│   └── constants.py             # Probability adjustments, thresholds
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── data_sources/
│   │   ├── __init__.py
│   │   ├── base_source.py       # Abstract base class
│   │   ├── lol_esports.py       # LoL live API poller
│   │   ├── grid_dota2.py        # GRID Dota 2 GraphQL poller
│   │   └── grid_cs2.py          # GRID CS2 GraphQL poller
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── events.py            # Event types, dataclasses
│   │   ├── probability.py       # Win% estimation model
│   │   └── signal_detector.py   # Core detection + edge calc
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── polymarket_client.py # py-clob-client wrapper
│   │   ├── market_finder.py     # Find active esports markets
│   │   ├── order_executor.py    # Execute trades (FOK orders)
│   │   └── position_tracker.py  # Track positions + P&L
│   ├── risk/
│   │   ├── __init__.py
│   │   └── risk_manager.py      # Sizing, limits, exposure
│   ├── logging_utils/           # Named to avoid shadowing stdlib
│   │   ├── __init__.py
│   │   ├── activity_logger.py   # Writes ACTIVITY_LOG.md
│   │   └── trade_logger.py      # SQLite trade database
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── test_signal_detector.py
│   ├── test_probability.py
│   ├── test_market_finder.py
│   └── test_order_executor.py
├── data/
│   └── trades.db                # Auto-created
└── scripts/
    └── paper_trade.py           # DRY_RUN=true wrapper
```

## 6. DATA SOURCE SPECIFICATIONS

### 6.1 LoL Esports API (BUILD FIRST — no approval needed)

**Discover live matches:**
```
GET https://esports-api.lolesports.com/persisted/gw/getLive?hl=en-US
Header: x-api-key: 0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z
```

**Get live game state:**
```
GET https://feed.lolesports.com/livestats/v1/window/{gameId}
Header: x-api-key: 0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z
```

**Get event details:**
```
GET https://feed.lolesports.com/livestats/v1/details/{gameId}
Header: x-api-key: 0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z
```

**Get schedule:**
```
GET https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=en-US
Header: x-api-key: 0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z
```

**Polling:** Check getLive every 60s. When match found, poll window/{gameId} every 3-5s. Compare consecutive frames to detect events.

**Window response structure:**
```json
{
  "gameMetadata": {
    "blueTeamMetadata": { "teamName": "T1" },
    "redTeamMetadata": { "teamName": "Gen.G" }
  },
  "frames": [{
    "gameState": "in_game",
    "blueTeam": {
      "totalGold": 45230, "totalKills": 12,
      "towers": 5, "inhibitors": 0,
      "dragons": 2, "barons": 1,
      "participants": [...]
    },
    "redTeam": { "...same..." }
  }]
}
```

**LoL events to detect:**
| Event | Detection | Probability Shift |
|---|---|---|
| Baron kill | barons count increases | +0.12 |
| Elder Dragon | dragons > 4 | +0.15 |
| Dragon Soul | dragons reaches 4 | +0.10 |
| Ace | 5 kills in ~10 sec | +0.10 |
| Inhibitor destroyed | inhibitors increases | +0.08 |
| Tower destroyed | towers increases | +0.02 |
| Gold lead >3K swing | totalGold diff swings 3000+ | +0.05 |
| Gold lead >5K swing | swings 5000+ | +0.08 |
| Gold lead >10K | absolute diff > 10000 | +0.12 |

**NOTE:** The x-api-key is public (used by lolesports.com frontend). Could change without notice. If 403 errors appear, check lolesports.com page source for current key.

### 6.2 GRID Dota 2 (BUILD AFTER GRID approval)

**Two GraphQL endpoints:**
- Central Data: `POST https://api-op.grid.gg/central-data/graphql` — tournaments, series, teams
- Series State: `POST https://api-op.grid.gg/live-data-feed/series-state/graphql` — live gameplay
- Header: `x-auth-key: {GRID_API_KEY}`

**IMPORTANT:** Exact endpoint URLs and GraphQL schema must be verified against GRID's documentation once access is granted. The URLs above are based on known patterns.

**Stage 1 query — find live Dota 2 series:**
```graphql
query { allSeries(filter: { titleId: 2, status: LIVE }) {
  edges { node { id teams { name score } tournament { name } } }
}}
```

**Stage 2 query — get live state:**
```graphql
query($id: ID!) { seriesState(id: $id) {
  teams { name score players { name kills deaths assists netWorth } }
  maps { number state teams { side score totalGold objectives { type completedAt } } clock winner }
}}
```

**Dota 2 events:**
| Event | Detection | Shift |
|---|---|---|
| Roshan kill | New roshan objective | +0.08 |
| Barracks destroyed | New barracks objective | +0.12 |
| Team wipe | 4-5 kills in 15 sec | +0.10 |
| Tower destroyed | New tower objective | +0.03 |
| Gold lead >5K | totalGold diff | +0.08 |
| Gold lead >10K | totalGold diff | +0.12 |
| Mega creeps | All 6 barracks down | +0.25 |

### 6.3 GRID CS2 (BUILD AFTER Dota 2 working)

Same GRID API, title ID for CS2 (likely titleId: 1, verify in docs).

**CS2 events:**
| Event | Detection | Shift |
|---|---|---|
| Round win | Round count change | +0.03 |
| 5+ round lead | Score diff >= 5 | +0.15 |
| Match point | Team at 12 rounds (MR13) | +0.20 |
| Map win | Map finishes | +0.25 (series) |
| Economy break | Money + round loss pattern | +0.05 |

### 6.4 Base Class
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from src.signals.events import GameEvent

class BaseDataSource(ABC):
    @abstractmethod
    async def start(self): pass
    @abstractmethod
    async def stop(self): pass
    @abstractmethod
    async def get_live_matches(self) -> List[dict]: pass
    @abstractmethod
    async def poll_match_state(self, match_id: str) -> Optional[dict]: pass
    @abstractmethod
    def detect_events(self, current: dict, previous: dict) -> List[GameEvent]: pass
```

## 7. SIGNAL DETECTION

### Events (`src/signals/events.py`)
```python
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
```

### Signal flow
```
Event → lookup adjustment from constants.py → new_prob = current_prob + adjustment
→ find Polymarket market → get market price → edge = new_prob - price
→ if edge >= 0.08: emit TradingSignal → else: log skip
```

## 8. POLYMARKET INTEGRATION

### Market Finder
```
GET https://gamma-api.polymarket.com/events?tag=esports&active=true&closed=false
```
Also try tags: league-of-legends, dota-2, counter-strike. Cache results, refresh every 5 min.
Only trade markets with liquidity > $1000, active=true, closed=false, feesEnabled=false (or fees < edge).

### Client Setup
```python
from py_clob_client.client import ClobClient
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon
client = ClobClient(HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=0, funder=WALLET_ADDRESS)
client.set_api_creds(client.create_or_derive_api_creds())
```

### Order Execution
```python
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
order = MarketOrderArgs(token_id=TOKEN_ID, amount=BET_USD, side=BUY, order_type=OrderType.FOK)
signed = client.create_market_order(order)
resp = client.post_order(signed, OrderType.FOK)
```

Always check feesEnabled before trading. If fees exist, include feeRateBps in signed order.

## 9. RISK MANAGER
```python
MAX_BET_PERCENT = 0.10       # 10% of capital per trade
MAX_SINGLE_BET_USD = 200.0
MIN_BET_USD = 5.0
MAX_DAILY_LOSS_PERCENT = 0.20
MAX_OPEN_POSITIONS = 5
MIN_MARKET_LIQUIDITY = 1000.0
```

## 10. LOGGING

**ACTIVITY_LOG.md** — every action timestamped: SYSTEM, DATA, SIGNAL, TRADE, RESOLUTION, ERROR, SKIP

**SQLite trades.db:**
```sql
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, game TEXT NOT NULL, match_name TEXT,
    event_type TEXT NOT NULL, signal_probability REAL, market_price REAL,
    edge REAL, direction TEXT, bet_amount_usd REAL, fill_price REAL,
    shares REAL, market_id TEXT, token_id TEXT,
    status TEXT DEFAULT 'open', payout REAL, profit_loss REAL,
    capital_after REAL, notes TEXT
);
CREATE TABLE IF NOT EXISTS daily_summary (
    date TEXT PRIMARY KEY, trades_count INTEGER, wins INTEGER,
    losses INTEGER, total_profit_loss REAL, capital_start REAL, capital_end REAL
);
```

## 11. CONFIGURATION

### .env.example
```bash
POLY_PRIVATE_KEY=0x_YOUR_KEY
POLY_WALLET_ADDRESS=0x_YOUR_ADDRESS
GRID_API_KEY=your_grid_key_here
LOL_API_KEY=0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z
STARTING_CAPITAL=500.0
MIN_EDGE_THRESHOLD=0.08
MAX_BET_PERCENT=0.10
MAX_SINGLE_BET_USD=200.0
MAX_DAILY_LOSS_PERCENT=0.20
MAX_OPEN_POSITIONS=5
MIN_MARKET_LIQUIDITY=1000.0
LIVE_CHECK_INTERVAL=60
MATCH_POLL_INTERVAL=4
MARKET_REFRESH_INTERVAL=300
DRY_RUN=true
LOG_LEVEL=INFO
```

### .gitignore
```
.env
__pycache__/
*.pyc
data/*.db
.venv/
venv/
.idea/
.vscode/
```

### requirements.txt
```
py-clob-client>=0.34.5
python-dotenv>=1.0.0
httpx>=0.27.0
gql[httpx]>=3.5.0
```

## 12. BUILD ORDER — Follow Exactly

### Phase 1: Foundation
1. All directories + __init__.py files
2. .env.example, .gitignore, requirements.txt, README.md
3. config/settings.py, config/constants.py
4. src/logging_utils/activity_logger.py
5. src/logging_utils/trade_logger.py (SQLite)
6. src/signals/events.py (dataclasses + enums)
7. TEST: logger creates entries, db initializes
8. **COMMIT: "Phase 1: Foundation — config, logging, event types"**

### Phase 2: Polymarket Integration
9. src/trading/polymarket_client.py
10. src/trading/market_finder.py
11. src/trading/order_executor.py (with DRY_RUN)
12. src/trading/position_tracker.py
13. src/risk/risk_manager.py
14. TEST: market_finder returns real esports markets
15. **COMMIT: "Phase 2: Polymarket integration"**

### Phase 3: LoL + Signal Detection
16. src/data_sources/base_source.py
17. src/data_sources/lol_esports.py
18. src/signals/probability.py
19. src/signals/signal_detector.py
20. TEST: poll LoL API, detect events (live or mock)
21. **COMMIT: "Phase 3: LoL data source and signal detection"**

### Phase 4: Main Orchestrator
22. src/main.py (startup, polling loops, signal→trade pipeline, graceful shutdown)
23. scripts/paper_trade.py
24. TEST: full pipeline DRY_RUN, verify end-to-end
25. **COMMIT: "Phase 4: Main orchestrator — paper trading ready"**

### Phase 5: GRID Dota 2 (after approval)
26. src/data_sources/grid_dota2.py
27. Register in main.py
28. **COMMIT: "Phase 5: GRID Dota 2 data source"**

### Phase 6: GRID CS2 (after approval)
29. src/data_sources/grid_cs2.py
30. Register in main.py
31. **COMMIT: "Phase 6: GRID CS2 data source"**

## 13. RUNNING

```bash
pip install -r requirements.txt

# Paper trading (default)
python -m src.main

# Live trading (after validation)
# Set DRY_RUN=false in .env
python -m src.main
```

## 14. CRITICAL REMINDERS

1. Check feesEnabled on every market before trading
2. LoL API key is public but could change — monitor for 403s
3. GRID schema may differ from examples — verify after access granted
4. Start DRY_RUN=true — validate 10+ matches minimum
5. Log everything — logs are your tuning tool
6. Commit after every phase
7. Team name matching needs fuzzy logic or alias map
8. Probability model is intentionally simple — speed > precision

## 15. SETUP CHECKLIST
- [ ] Polymarket account + wallet + USDC on Polygon ($300-500)
- [ ] Private key in .env
- [ ] GRID Open Access applied (grid.gg/open-access)
- [ ] Paper trading 10+ matches
- [ ] Probability model tuned from paper results

## END OF BUILD INSTRUCTIONS v2
