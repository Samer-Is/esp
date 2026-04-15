import os
from dotenv import load_dotenv

load_dotenv()


# Polymarket
POLY_PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
POLY_WALLET_ADDRESS = os.getenv("POLY_WALLET_ADDRESS", "")

# API Keys
GRID_API_KEY = os.getenv("GRID_API_KEY", "")
LOL_API_KEY = os.getenv("LOL_API_KEY", "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z")

# Capital & Risk
STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "500.0"))
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.08"))
MAX_BET_PERCENT = float(os.getenv("MAX_BET_PERCENT", "0.10"))
MAX_SINGLE_BET_USD = float(os.getenv("MAX_SINGLE_BET_USD", "200.0"))
MIN_BET_USD = float(os.getenv("MIN_BET_USD", "5.0"))
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "0.20"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
MIN_MARKET_LIQUIDITY = float(os.getenv("MIN_MARKET_LIQUIDITY", "1000.0"))

# Polling intervals (seconds)
LIVE_CHECK_INTERVAL = int(os.getenv("LIVE_CHECK_INTERVAL", "60"))
MATCH_POLL_INTERVAL = int(os.getenv("MATCH_POLL_INTERVAL", "4"))
MARKET_REFRESH_INTERVAL = int(os.getenv("MARKET_REFRESH_INTERVAL", "300"))

# Mode
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Polymarket endpoints
POLYMARKET_CLOB_HOST = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
POLYMARKET_CHAIN_ID = 137  # Polygon

# LoL Esports endpoints
LOL_ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LOL_FEED_API = "https://feed.lolesports.com/livestats/v1"

# GRID endpoints
GRID_CENTRAL_DATA = "https://api-op.grid.gg/central-data/graphql"
GRID_LIVE_DATA = "https://api-op.grid.gg/live-data-feed/series-state/graphql"

# Database
TRADES_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trades.db")
