"""ESP Dashboard — FastAPI backend serving real-time bot data + control panel."""

import asyncio
import json
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (
    STARTING_CAPITAL, MIN_EDGE_THRESHOLD, MAX_BET_PERCENT,
    MAX_SINGLE_BET_USD, MIN_BET_USD, MAX_DAILY_LOSS_PERCENT,
    MAX_OPEN_POSITIONS, MIN_MARKET_LIQUIDITY, LIVE_CHECK_INTERVAL,
    MATCH_POLL_INTERVAL, MARKET_REFRESH_INTERVAL, DRY_RUN, LOG_LEVEL,
    TRADES_DB_PATH, GRID_API_KEY,
)
from config.constants import PROBABILITY_ADJUSTMENTS, TEAM_ALIASES
from src.signals.events import EventType


# ── Shared bot state (set by main.py when running together) ──────────────
class BotState:
    """Holds mutable references to the live bot instance."""
    bot = None
    running = False
    start_time: Optional[float] = None
    events_detected: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    last_events: list = []       # last 50 events
    tracked_matches: dict = {}   # game_id → match info

    @classmethod
    def record_event(cls, event_dict: dict):
        cls.events_detected += 1
        cls.last_events.insert(0, event_dict)
        cls.last_events = cls.last_events[:50]

    @classmethod
    def record_signal(cls):
        cls.signals_generated += 1

    @classmethod
    def record_trade(cls):
        cls.trades_executed += 1


bot_state = BotState


# ── Database helpers ─────────────────────────────────────────────────────
def _db():
    """Get a read-only SQLite connection."""
    db_path = os.path.join(PROJECT_ROOT, TRADES_DB_PATH)
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _db()
    if not conn:
        return []
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── WebSocket manager ────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


# ── Background task: push updates every 2s ───────────────────────────────
async def _push_loop():
    while True:
        try:
            data = _build_dashboard_payload()
            await ws_manager.broadcast(data)
        except Exception:
            pass
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_push_loop())
    yield
    task.cancel()


# ── FastAPI app ──────────────────────────────────────────────────────────
app = FastAPI(title="ESP Dashboard", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Payload builder ─────────────────────────────────────────────────────
def _build_dashboard_payload() -> dict:
    # Trades / PnL
    all_trades = _query("SELECT * FROM trades ORDER BY id DESC LIMIT 100")
    open_trades = _query("SELECT * FROM trades WHERE status = 'open' ORDER BY id DESC")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_trades = _query(
        "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY id DESC", (f"{today}%",)
    )
    daily_summaries = _query("SELECT * FROM daily_summary ORDER BY date DESC LIMIT 30")

    # Calculate metrics
    total_pnl = sum(t.get("profit_loss", 0) or 0 for t in all_trades)
    today_pnl = sum(t.get("profit_loss", 0) or 0 for t in today_trades)
    wins = sum(1 for t in all_trades if (t.get("profit_loss") or 0) > 0)
    losses = sum(1 for t in all_trades if (t.get("profit_loss") or 0) < 0)
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    total_traded = sum(t.get("bet_amount_usd", 0) or 0 for t in all_trades)

    # Capital
    if all_trades:
        last_capital = all_trades[0].get("capital_after", STARTING_CAPITAL), 
        current_capital = last_capital[0] if isinstance(last_capital, tuple) else last_capital
    else:
        current_capital = STARTING_CAPITAL

    # Uptime
    uptime_str = "Offline"
    if bot_state.start_time:
        elapsed = time.time() - bot_state.start_time
        hours, rem = divmod(int(elapsed), 3600)
        mins, secs = divmod(rem, 60)
        uptime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

    return {
        "type": "dashboard_update",
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Top-level KPIs
        "kpis": {
            "current_capital": float(current_capital),
            "starting_capital": STARTING_CAPITAL,
            "total_pnl": round(total_pnl, 2),
            "today_pnl": round(today_pnl, 2),
            "total_return_pct": round((total_pnl / STARTING_CAPITAL) * 100, 2) if STARTING_CAPITAL else 0,
            "win_rate": round(win_rate, 1),
            "total_trades": len(all_trades),
            "wins": wins,
            "losses": losses,
            "open_positions": len(open_trades),
            "total_traded": round(total_traded, 2),
        },

        # Bot status
        "bot": {
            "running": bot_state.running,
            "dry_run": DRY_RUN,
            "uptime": uptime_str,
            "events_detected": bot_state.events_detected,
            "signals_generated": bot_state.signals_generated,
            "trades_executed": bot_state.trades_executed,
            "tracked_matches": list(bot_state.tracked_matches.values()),
            "grid_enabled": bool(GRID_API_KEY),
        },

        # Config
        "config": {
            "min_edge_threshold": MIN_EDGE_THRESHOLD,
            "max_bet_percent": MAX_BET_PERCENT,
            "max_single_bet_usd": MAX_SINGLE_BET_USD,
            "min_bet_usd": MIN_BET_USD,
            "max_daily_loss_pct": MAX_DAILY_LOSS_PERCENT,
            "max_open_positions": MAX_OPEN_POSITIONS,
            "min_market_liquidity": MIN_MARKET_LIQUIDITY,
            "live_check_interval": LIVE_CHECK_INTERVAL,
            "match_poll_interval": MATCH_POLL_INTERVAL,
            "market_refresh_interval": MARKET_REFRESH_INTERVAL,
            "log_level": LOG_LEVEL,
        },

        # Recent data
        "recent_trades": all_trades[:20],
        "open_trades": open_trades,
        "today_trades": today_trades[:20],
        "daily_summaries": daily_summaries,
        "recent_events": bot_state.last_events[:20],

        # Probability adjustments for reference
        "probability_map": {et.value: adj for et, adj in PROBABILITY_ADJUSTMENTS.items()},
    }


# ── REST endpoints ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/dashboard")
async def api_dashboard():
    return JSONResponse(_build_dashboard_payload())


@app.get("/api/trades")
async def api_trades(limit: int = 100, status: Optional[str] = None):
    if status:
        rows = _query("SELECT * FROM trades WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        rows = _query("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
    return JSONResponse(rows)


@app.get("/api/daily")
async def api_daily(limit: int = 30):
    rows = _query("SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?", (limit,))
    return JSONResponse(rows)


@app.get("/api/events")
async def api_events():
    return JSONResponse(bot_state.last_events[:50])


@app.get("/api/matches")
async def api_matches():
    return JSONResponse(list(bot_state.tracked_matches.values()))


@app.get("/api/config")
async def api_config():
    return JSONResponse({
        "min_edge_threshold": MIN_EDGE_THRESHOLD,
        "max_bet_percent": MAX_BET_PERCENT,
        "max_single_bet_usd": MAX_SINGLE_BET_USD,
        "max_daily_loss_pct": MAX_DAILY_LOSS_PERCENT,
        "max_open_positions": MAX_OPEN_POSITIONS,
        "dry_run": DRY_RUN,
        "probability_map": {et.value: adj for et, adj in PROBABILITY_ADJUSTMENTS.items()},
        "team_aliases": {k: v for k, v in TEAM_ALIASES.items()},
    })


@app.get("/api/activity-log")
async def api_activity_log(lines: int = 50):
    log_path = PROJECT_ROOT / "ACTIVITY_LOG.md"
    if not log_path.exists():
        return JSONResponse([])
    text = log_path.read_text(encoding="utf-8")
    entries = []
    for line in reversed(text.splitlines()):
        if line.startswith("- **["):
            entries.append(line)
            if len(entries) >= lines:
                break
    return JSONResponse(entries)


# ── WebSocket for live updates ───────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial snapshot
        await ws.send_json(_build_dashboard_payload())
        # Keep connection alive, listen for control commands
        while True:
            data = await ws.receive_text()
            # Future: handle control commands here
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── Runner ───────────────────────────────────────────────────────────────
def start_dashboard(host: str = "0.0.0.0", port: int = 8888):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_dashboard()
