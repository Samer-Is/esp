import os
import sqlite3
from datetime import datetime, timezone

from config.settings import TRADES_DB_PATH


def _ensure_db_dir() -> None:
    os.makedirs(os.path.dirname(TRADES_DB_PATH), exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(TRADES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                game TEXT NOT NULL,
                match_name TEXT,
                event_type TEXT NOT NULL,
                signal_probability REAL,
                market_price REAL,
                edge REAL,
                direction TEXT,
                bet_amount_usd REAL,
                fill_price REAL,
                shares REAL,
                market_id TEXT,
                token_id TEXT,
                status TEXT DEFAULT 'open',
                payout REAL,
                profit_loss REAL,
                capital_after REAL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_summary (
                date TEXT PRIMARY KEY,
                trades_count INTEGER,
                wins INTEGER,
                losses INTEGER,
                total_profit_loss REAL,
                capital_start REAL,
                capital_end REAL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_trade(
    game: str,
    match_name: str,
    event_type: str,
    signal_probability: float,
    market_price: float,
    edge: float,
    direction: str,
    bet_amount_usd: float,
    fill_price: float,
    shares: float,
    market_id: str,
    token_id: str,
    capital_after: float,
    notes: str = "",
) -> int:
    """Insert a new trade record and return its id."""
    ts = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO trades (
                timestamp, game, match_name, event_type,
                signal_probability, market_price, edge, direction,
                bet_amount_usd, fill_price, shares,
                market_id, token_id, capital_after, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, game, match_name, event_type,
                signal_probability, market_price, edge, direction,
                bet_amount_usd, fill_price, shares,
                market_id, token_id, capital_after, notes,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def resolve_trade(trade_id: int, payout: float, profit_loss: float) -> None:
    """Mark a trade as resolved with payout info."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE trades SET status = 'resolved', payout = ?, profit_loss = ? WHERE id = ?",
            (payout, profit_loss, trade_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_open_trades() -> list:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM trades WHERE status = 'open'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_today_trades() -> list:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trades WHERE timestamp LIKE ?", (f"{today}%",)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
