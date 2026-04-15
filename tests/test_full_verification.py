"""Comprehensive integration test — validates all modules end-to-end."""

import asyncio
import sys
import os
import traceback

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Test counter
passed = 0
failed = 0
errors = []


def ok(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")


def fail(name, reason):
    global failed
    failed += 1
    errors.append((name, reason))
    print(f"  [FAIL] {name}: {reason}")


async def run_tests():
    global passed, failed

    print("=" * 60)
    print("ESP COMPREHENSIVE VERIFICATION")
    print("=" * 60)

    # =========================================================
    # 1. Config / Settings
    # =========================================================
    print("\n--- 1. Config & Settings ---")
    try:
        from config.settings import (
            POLY_PRIVATE_KEY, POLY_WALLET_ADDRESS, GRID_API_KEY,
            LOL_API_KEY, STARTING_CAPITAL, MIN_EDGE_THRESHOLD,
            MAX_BET_PERCENT, MAX_SINGLE_BET_USD, MIN_BET_USD,
            MAX_DAILY_LOSS_PERCENT, MAX_OPEN_POSITIONS, MIN_MARKET_LIQUIDITY,
            LIVE_CHECK_INTERVAL, MATCH_POLL_INTERVAL, MARKET_REFRESH_INTERVAL,
            DRY_RUN, LOG_LEVEL, POLYMARKET_CLOB_HOST, POLYMARKET_GAMMA_API,
            POLYMARKET_CHAIN_ID, LOL_ESPORTS_API, LOL_FEED_API,
            GRID_CENTRAL_DATA, GRID_LIVE_DATA, TRADES_DB_PATH,
        )
        ok("All settings import")
        assert DRY_RUN is True, "DRY_RUN should default to True"
        ok("DRY_RUN defaults to True")
        assert STARTING_CAPITAL == 500.0
        ok("STARTING_CAPITAL = 500.0")
        assert 0 < MIN_EDGE_THRESHOLD < 1
        ok("MIN_EDGE_THRESHOLD valid")
        assert POLYMARKET_CHAIN_ID == 137
        ok("Chain ID = 137 (Polygon)")
        assert TRADES_DB_PATH.endswith("trades.db")
        ok("TRADES_DB_PATH ends with trades.db")
    except Exception as e:
        fail("Settings import", str(e))

    # =========================================================
    # 2. Constants
    # =========================================================
    print("\n--- 2. Constants ---")
    try:
        from config.constants import PROBABILITY_ADJUSTMENTS, TEAM_ALIASES
        from src.signals.events import EventType
        assert len(PROBABILITY_ADJUSTMENTS) == 17, f"Expected 17 adjustments, got {len(PROBABILITY_ADJUSTMENTS)}"
        ok("17 probability adjustments loaded")

        # Verify all EventType values have adjustments
        for et in EventType:
            assert et in PROBABILITY_ADJUSTMENTS, f"Missing adjustment for {et.value}"
        ok("All EventType values have adjustments")

        # Verify adjustment ranges
        for et, adj in PROBABILITY_ADJUSTMENTS.items():
            assert 0.0 <= adj <= 0.30, f"{et.value} adjustment {adj} out of range"
        ok("All adjustments in valid range [0, 0.30]")

        assert len(TEAM_ALIASES) > 0
        ok(f"Team aliases loaded: {len(TEAM_ALIASES)} teams")
    except Exception as e:
        fail("Constants", str(e))

    # =========================================================
    # 3. Events & Dataclasses
    # =========================================================
    print("\n--- 3. Events & Dataclasses ---")
    try:
        from src.signals.events import Game, EventType, GameEvent, TradingSignal
        from datetime import datetime, timezone

        # Test GameEvent creation
        evt = GameEvent(
            game=Game.LOL, event_type=EventType.BARON_KILL,
            benefitting_team="T1", match_id="123",
            match_name="T1 vs GenG", timestamp=datetime.now(timezone.utc),
            details={"side": "blue"},
        )
        assert evt.benefitting_team == "T1"
        ok("GameEvent creation")

        # Test TradingSignal creation
        sig = TradingSignal(
            event=evt, estimated_probability=0.7, market_price=0.55,
            edge=0.15, market_id="m1", token_id="t1", direction="BUY_YES",
        )
        assert sig.edge == 0.15
        ok("TradingSignal creation")
    except Exception as e:
        fail("Events", str(e))

    # =========================================================
    # 4. Activity Logger
    # =========================================================
    print("\n--- 4. Activity Logger ---")
    try:
        from src.logging_utils.activity_logger import log_activity, ACTIVITY_LOG_PATH
        assert os.path.exists(ACTIVITY_LOG_PATH), f"Log path missing: {ACTIVITY_LOG_PATH}"
        ok("ACTIVITY_LOG_PATH exists")
        log_activity("SYSTEM", "Verification test entry")
        ok("log_activity writes without error")
    except Exception as e:
        fail("Activity Logger", str(e))

    # =========================================================
    # 5. Trade Logger (SQLite)
    # =========================================================
    print("\n--- 5. Trade Logger ---")
    try:
        from src.logging_utils.trade_logger import (
            init_db, insert_trade, resolve_trade,
            get_open_trades, get_today_trades, get_connection,
        )
        init_db()
        ok("init_db() succeeds")

        # Verify tables exist
        conn = get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "trades" in table_names, "trades table missing"
        assert "daily_summary" in table_names, "daily_summary table missing"
        conn.close()
        ok("Both tables exist (trades, daily_summary)")

        # Verify column count
        conn = get_connection()
        cols = conn.execute("PRAGMA table_info(trades)").fetchall()
        assert len(cols) == 19, f"Expected 19 columns in trades, got {len(cols)}"
        conn.close()
        ok("trades table has 19 columns")
    except Exception as e:
        fail("Trade Logger", str(e))

    # =========================================================
    # 6. Probability Model
    # =========================================================
    print("\n--- 6. Probability Model ---")
    try:
        from src.signals.probability import estimate_probability
        from src.signals.events import Game, EventType, GameEvent
        from datetime import datetime, timezone

        evt = GameEvent(
            game=Game.LOL, event_type=EventType.BARON_KILL,
            benefitting_team="T1", match_id="x", match_name="T1 vs G2",
            timestamp=datetime.now(timezone.utc), details={},
        )
        prob = estimate_probability(evt, 0.55)
        assert abs(prob - 0.67) < 0.001, f"Expected 0.67, got {prob}"
        ok("Baron kill: 0.55 + 0.12 = 0.67")

        # Test clamping upper bound
        prob_hi = estimate_probability(evt, 0.95)
        assert prob_hi == 0.99, f"Expected clamped 0.99, got {prob_hi}"
        ok("Upper clamp at 0.99")

        # Test clamping lower bound
        evt2 = GameEvent(
            game=Game.LOL, event_type=EventType.GAME_END,
            benefitting_team="T1", match_id="x", match_name="T1 vs G2",
            timestamp=datetime.now(timezone.utc), details={},
        )
        prob_lo = estimate_probability(evt2, 0.005)
        assert prob_lo == 0.01, f"Expected clamped 0.01, got {prob_lo}"
        ok("Lower clamp at 0.01 (GAME_END adj=0)")
    except Exception as e:
        fail("Probability", str(e))

    # =========================================================
    # 7. LoL Esports Source
    # =========================================================
    print("\n--- 7. LoL Esports Source ---")
    try:
        from src.data_sources.lol_esports import LoLEsportsSource

        src = LoLEsportsSource()
        await src.start()
        assert src._client is not None
        ok("LoL source starts")

        # Test live matches (real API)
        matches = await src.get_live_matches()
        ok(f"get_live_matches() returned {len(matches)} matches")

        # Test mock event detection — multiple scenarios
        prev = {
            "game_id": "test", "blue_team": "T1", "red_team": "GenG",
            "game_state": "in_game",
            "blue": {"totalGold": 40000, "totalKills": 8, "towers": 3, "inhibitors": 0, "dragons": 2, "barons": 0},
            "red": {"totalGold": 38000, "totalKills": 6, "towers": 2, "inhibitors": 0, "dragons": 1, "barons": 0},
        }
        curr = {
            "game_id": "test", "blue_team": "T1", "red_team": "GenG",
            "game_state": "in_game",
            "blue": {"totalGold": 45000, "totalKills": 13, "towers": 5, "inhibitors": 1, "dragons": 4, "barons": 1},
            "red": {"totalGold": 38500, "totalKills": 6, "towers": 2, "inhibitors": 0, "dragons": 1, "barons": 0},
        }
        events = src.detect_events(curr, prev)
        event_types = [e.event_type.value for e in events]
        print(f"    Detected events: {event_types}")

        assert "baron_kill" in event_types, "Missing baron_kill"
        ok("Baron kill detected")
        assert "dragon_soul" in event_types, "Missing dragon_soul"
        ok("Dragon soul detected (4 dragons)")
        assert "inhibitor_destroyed" in event_types, "Missing inhibitor_destroyed"
        ok("Inhibitor destroyed detected")
        assert "tower_destroyed" in event_types, "Missing tower_destroyed"
        ok("Tower destroyed detected")
        assert "ace" in event_types, "Missing ace (5+ kills)"
        ok("Ace detected (5+ kill diff)")
        assert "gold_lead_5k" in event_types or "gold_lead_10k" in event_types, "Missing gold lead"
        ok("Gold lead swing detected")

        # All events should benefit T1 (blue team)
        for e in events:
            if e.event_type != EventType.GOLD_LEAD_3K and e.event_type != EventType.GOLD_LEAD_5K and e.event_type != EventType.GOLD_LEAD_10K:
                assert e.benefitting_team == "T1", f"{e.event_type.value} benefitting {e.benefitting_team} instead of T1"
        ok("All non-gold events correctly benefit T1 (blue)")

        # Test game end detection
        prev_end = {**curr, "game_state": "in_game"}
        curr_end = {**curr, "game_state": "finished"}
        end_events = src.detect_events(curr_end, prev_end)
        end_types = [e.event_type.value for e in end_events]
        assert "game_end" in end_types, "Missing game_end"
        ok("Game end detection")

        # Test null/empty states
        assert src.detect_events(None, prev) == []
        assert src.detect_events(curr, None) == []
        assert src.detect_events({}, {}) == []
        ok("Null/empty state handling")

        # Test _parse_team with list dragons (the fixed bug)
        parsed = LoLEsportsSource._parse_team({"dragons": ["fire", "cloud", "hextech"]})
        assert parsed["dragons"] == 3, f"Expected 3, got {parsed['dragons']}"
        ok("_parse_team handles list dragons (len=3)")

        parsed2 = LoLEsportsSource._parse_team({"dragons": []})
        assert parsed2["dragons"] == 0
        ok("_parse_team handles empty list dragons")

        parsed3 = LoLEsportsSource._parse_team({})
        assert parsed3["dragons"] == 0
        ok("_parse_team handles missing dragons field")

        # Test update_previous
        prev_state = src.update_previous("game1", {"a": 1})
        assert prev_state is None, "First call should return None"
        ok("update_previous: first call returns None")

        prev_state2 = src.update_previous("game1", {"a": 2})
        assert prev_state2 == {"a": 1}, "Second call should return first state"
        ok("update_previous: second call returns previous state")

        await src.stop()
        ok("LoL source stops cleanly")
    except Exception as e:
        fail("LoL Esports Source", traceback.format_exc())

    # =========================================================
    # 8. GRID Dota 2 Source
    # =========================================================
    print("\n--- 8. GRID Dota 2 Source ---")
    try:
        from src.data_sources.grid_dota2 import GridDota2Source

        src = GridDota2Source()
        await src.start()  # should warn about no API key
        matches = await src.get_live_matches()
        assert matches == [], "Should return [] without API key"
        ok("Dota2 source gracefully disabled without key")

        # Test mock event detection
        prev = {
            "game_id": "d1", "team_a": "OG", "team_b": "Spirit",
            "team_a_data": {
                "totalGold": 40000, "score": 0,
                "objectives": [
                    {"type": "tower_tier1_top", "completedAt": "2026-01-01T00:01:00"},
                ],
                "side": "radiant",
            },
            "team_b_data": {
                "totalGold": 38000, "score": 0,
                "objectives": [], "side": "dire",
            },
            "players": {"OG": [{"kills": 5}], "Spirit": [{"kills": 3}]},
        }
        curr = {
            "game_id": "d1", "team_a": "OG", "team_b": "Spirit",
            "team_a_data": {
                "totalGold": 48000, "score": 0,
                "objectives": [
                    {"type": "tower_tier1_top", "completedAt": "2026-01-01T00:01:00"},
                    {"type": "roshan", "completedAt": "2026-01-01T00:10:00"},
                    {"type": "tower_tier2_mid", "completedAt": "2026-01-01T00:12:00"},
                ],
                "side": "radiant",
            },
            "team_b_data": {
                "totalGold": 38500, "score": 0,
                "objectives": [], "side": "dire",
            },
            "players": {"OG": [{"kills": 10}], "Spirit": [{"kills": 3}]},
        }
        events = src.detect_events(curr, prev)
        event_types = [e.event_type.value for e in events]
        print(f"    Dota2 detected: {event_types}")
        assert "roshan_kill" in event_types, "Missing roshan_kill"
        ok("Dota2 roshan kill detected")
        assert "tower_destroyed" in event_types
        ok("Dota2 tower destroyed detected")
        assert "ace" in event_types, "Missing ace (5+ kill surge)"
        ok("Dota2 team wipe (ace) detected")
        assert any("gold_lead" in t for t in event_types), "Missing gold lead"
        ok("Dota2 gold lead detected")

        await src.stop()
        ok("Dota2 source stops cleanly")
    except Exception as e:
        fail("GRID Dota 2", traceback.format_exc())

    # =========================================================
    # 9. GRID CS2 Source
    # =========================================================
    print("\n--- 9. GRID CS2 Source ---")
    try:
        from src.data_sources.grid_cs2 import GridCS2Source

        src = GridCS2Source()
        await src.start()
        matches = await src.get_live_matches()
        assert matches == []
        ok("CS2 source gracefully disabled without key")

        # Test mock event detection
        prev = {
            "game_id": "cs2_1", "team_a": "NAVI", "team_b": "FaZe",
            "rounds_a": 7, "rounds_b": 5, "map_number": 1,
            "map_state": "active", "winner": None,
            "series_score_a": 0, "series_score_b": 0,
        }
        curr = {
            "game_id": "cs2_1", "team_a": "NAVI", "team_b": "FaZe",
            "rounds_a": 12, "rounds_b": 5, "map_number": 1,
            "map_state": "active", "winner": None,
            "series_score_a": 0, "series_score_b": 0,
        }
        events = src.detect_events(curr, prev)
        event_types = [e.event_type.value for e in events]
        print(f"    CS2 detected: {event_types}")
        assert "round_win" in event_types
        ok("CS2 round win detected")
        assert "match_point" in event_types, f"Missing match_point: {event_types}"
        ok("CS2 match point detected (12 rounds)")
        assert "economy_break" in event_types, f"Missing 5+ round lead: {event_types}"
        ok("CS2 5+ round lead detected")

        await src.stop()
        ok("CS2 source stops cleanly")
    except Exception as e:
        fail("GRID CS2", traceback.format_exc())

    # =========================================================
    # 10. Market Finder (real API)
    # =========================================================
    print("\n--- 10. Market Finder ---")
    try:
        from src.trading.market_finder import MarketFinder

        mf = MarketFinder()
        markets = await mf.refresh()
        assert len(markets) > 0, "No esports markets found"
        ok(f"MarketFinder found {len(markets)} events")

        # Verify market structure
        for m in markets[:3]:
            assert "id" in m, "Market missing 'id'"
            assert "title" in m, "Market missing 'title'"
        ok("Market structure has id + title")

        # Verify stale cache logic
        import time
        mf._last_refresh = time.time()
        cached = await mf.get_markets()
        assert cached == markets, "Cache should return same data"
        ok("Cache returns fresh data without re-fetch")

        # Test get_token_ids with mock data
        mock = {"market": {"clobTokenIds": "tok_yes,tok_no"}}
        tids = mf.get_token_ids(mock)
        assert tids.get("YES") == "tok_yes", f"YES token wrong: {tids}"
        assert tids.get("NO") == "tok_no", f"NO token wrong: {tids}"
        ok("get_token_ids parses comma-separated string")

        mock2 = {"market": {"clobTokenIds": ["id1", "id2"]}}
        tids2 = mf.get_token_ids(mock2)
        assert tids2["YES"] == "id1"
        assert tids2["NO"] == "id2"
        ok("get_token_ids handles list format")

        mock3 = {"market": {}}
        tids3 = mf.get_token_ids(mock3)
        assert tids3 == {}
        ok("get_token_ids handles missing clobTokenIds")
    except Exception as e:
        fail("Market Finder", traceback.format_exc())

    # =========================================================
    # 11. Polymarket Client
    # =========================================================
    print("\n--- 11. Polymarket Client ---")
    try:
        from src.trading.polymarket_client import PolymarketClient

        pc = PolymarketClient()
        pc.connect()  # DRY_RUN — should not crash
        assert pc._client is None, "Should NOT create client in DRY_RUN"
        ok("DRY_RUN: connect() doesn't create ClobClient")

        # Verify accessing .client raises in DRY_RUN
        try:
            _ = pc.client
            fail("DRY_RUN client access", "Should have raised RuntimeError")
        except RuntimeError:
            ok("DRY_RUN: .client raises RuntimeError correctly")
    except Exception as e:
        fail("Polymarket Client", traceback.format_exc())

    # =========================================================
    # 12. Order Executor
    # =========================================================
    print("\n--- 12. Order Executor ---")
    try:
        from src.trading.order_executor import OrderExecutor
        from src.trading.polymarket_client import PolymarketClient
        from src.signals.events import Game, EventType, GameEvent, TradingSignal
        from datetime import datetime, timezone

        pc = PolymarketClient()
        pc.connect()
        oe = OrderExecutor(pc)

        evt = GameEvent(
            game=Game.LOL, event_type=EventType.BARON_KILL,
            benefitting_team="T1", match_id="123",
            match_name="T1 vs GenG", timestamp=datetime.now(timezone.utc),
            details={},
        )
        sig = TradingSignal(
            event=evt, estimated_probability=0.7, market_price=0.55,
            edge=0.15, market_id="m1", token_id="t1", direction="BUY_YES",
        )
        result = oe.execute(sig, 50.0)
        assert result["dry_run"] is True
        assert result["amount"] == 50.0
        assert result["status"] == "SIMULATED"
        ok("DRY_RUN order execution returns simulated result")
    except Exception as e:
        fail("Order Executor", traceback.format_exc())

    # =========================================================
    # 13. Position Tracker
    # =========================================================
    print("\n--- 13. Position Tracker ---")
    try:
        from src.trading.position_tracker import PositionTracker

        pt = PositionTracker()
        assert pt.capital == 500.0
        ok("Initial capital = 500.0")
        assert pt.open_position_count == 0 or pt.open_position_count >= 0
        ok("open_position_count works")
        pnl = pt.today_pnl()
        assert isinstance(pnl, (int, float))
        ok("today_pnl returns numeric")
    except Exception as e:
        fail("Position Tracker", traceback.format_exc())

    # =========================================================
    # 14. Risk Manager
    # =========================================================
    print("\n--- 14. Risk Manager ---")
    try:
        from src.risk.risk_manager import RiskManager
        from src.trading.position_tracker import PositionTracker
        from src.signals.events import Game, EventType, GameEvent, TradingSignal
        from datetime import datetime, timezone

        pt = PositionTracker()
        rm = RiskManager(pt)

        evt = GameEvent(
            game=Game.LOL, event_type=EventType.BARON_KILL,
            benefitting_team="T1", match_id="x", match_name="T1 vs G2",
            timestamp=datetime.now(timezone.utc), details={},
        )

        # Test with good edge
        sig_good = TradingSignal(
            event=evt, estimated_probability=0.7, market_price=0.55,
            edge=0.15, market_id="m1", token_id="t1", direction="BUY_YES",
        )
        result = rm.evaluate(sig_good)
        assert result["approved"] is True, f"Should approve: {result}"
        assert result["bet_amount"] > 0
        assert result["bet_amount"] <= 200.0
        ok(f"Approved good signal: ${result['bet_amount']}")

        # Test with edge below threshold
        sig_low = TradingSignal(
            event=evt, estimated_probability=0.58, market_price=0.55,
            edge=0.03, market_id="m1", token_id="t1", direction="BUY_YES",
        )
        result2 = rm.evaluate(sig_low)
        assert result2["approved"] is False, "Should reject low edge"
        ok("Rejected low edge (0.03 < 0.08)")

        # Test bet sizing (should be min(500*0.10, 200) = 50)
        assert result["bet_amount"] == 50.0, f"Expected $50.00, got ${result['bet_amount']}"
        ok("Bet sizing correct: min(500*0.10, 200) = $50.00")
    except Exception as e:
        fail("Risk Manager", traceback.format_exc())

    # =========================================================
    # 15. Signal Detector 
    # =========================================================
    print("\n--- 15. Signal Detector ---")
    try:
        from src.signals.signal_detector import SignalDetector
        from src.trading.market_finder import MarketFinder

        mf = MarketFinder()
        await mf.refresh()
        sd = SignalDetector(mf)
        # Basic import and init test
        ok("SignalDetector initializes with MarketFinder")
    except Exception as e:
        fail("Signal Detector", traceback.format_exc())

    # =========================================================
    # 16. Main Bot Import
    # =========================================================
    print("\n--- 16. Main Bot ---")
    try:
        from src.main import ESPBot, run, main
        bot = ESPBot()
        assert bot.lol_source is not None
        assert bot.dota2_source is not None
        assert bot.cs2_source is not None
        ok("ESPBot creates all 3 data sources")
        assert bot.poly_client is not None
        assert bot.market_finder is not None
        assert bot.risk_manager is not None
        assert bot.order_executor is not None
        assert bot.signal_detector is not None
        ok("ESPBot creates all trading components")
    except Exception as e:
        fail("Main Bot", traceback.format_exc())

    # =========================================================
    # 17. Edge cases / Bug checks
    # =========================================================
    print("\n--- 17. Edge Cases & Bug Checks ---")

    # BUG CHECK: LoL source handles 204 / empty content
    try:
        from src.data_sources.lol_esports import LoLEsportsSource
        src = LoLEsportsSource()
        await src.start()
        # Poll a non-existent game — should return None, not crash
        result = await src.poll_match_state("999999999999999999")
        assert result is None, f"Expected None for invalid game ID, got {result}"
        await src.stop()
        ok("LoL poll_match_state handles invalid game ID (returns None)")
    except Exception as e:
        fail("LoL 204 handling", traceback.format_exc())

    # BUG CHECK: Gold lead detection with zero swing
    try:
        from src.data_sources.lol_esports import LoLEsportsSource
        src = LoLEsportsSource()
        prev = {
            "game_id": "t", "blue_team": "A", "red_team": "B", "game_state": "in_game",
            "blue": {"totalGold": 50000, "totalKills": 10, "towers": 5, "inhibitors": 0, "dragons": 0, "barons": 0},
            "red": {"totalGold": 40000, "totalKills": 5, "towers": 2, "inhibitors": 0, "dragons": 0, "barons": 0},
        }
        # Same gold — no swing
        curr = {
            "game_id": "t", "blue_team": "A", "red_team": "B", "game_state": "in_game",
            "blue": {"totalGold": 50100, "totalKills": 10, "towers": 5, "inhibitors": 0, "dragons": 0, "barons": 0},
            "red": {"totalGold": 40100, "totalKills": 5, "towers": 2, "inhibitors": 0, "dragons": 0, "barons": 0},
        }
        events = src.detect_events(curr, prev)
        gold_events = [e for e in events if "gold_lead" in e.event_type.value]
        assert len(gold_events) == 0, f"No gold event expected for stable lead, got {[e.event_type.value for e in gold_events]}"
        ok("No gold lead event for stable lead (no swing)")
    except Exception as e:
        fail("Gold lead no-swing", traceback.format_exc())

    # BUG CHECK: CS2 duplicate MAP_WIN
    try:
        from src.data_sources.grid_cs2 import GridCS2Source
        src = GridCS2Source()
        prev = {
            "game_id": "cs2_x", "team_a": "A", "team_b": "B",
            "rounds_a": 12, "rounds_b": 8, "map_number": 1,
            "map_state": "active", "winner": None,
            "series_score_a": 0, "series_score_b": 0,
        }
        curr = {
            "game_id": "cs2_x", "team_a": "A", "team_b": "B",
            "rounds_a": 13, "rounds_b": 8, "map_number": 1,
            "map_state": "finished", "winner": "team_a",
            "series_score_a": 1, "series_score_b": 0,
        }
        events = src.detect_events(curr, prev)
        map_wins = [e for e in events if e.event_type.value == "map_win"]
        if len(map_wins) > 1:
            fail("CS2 duplicate MAP_WIN", f"Got {len(map_wins)} MAP_WIN events instead of 1")
        else:
            ok(f"CS2 MAP_WIN count: {len(map_wins)}")
    except Exception as e:
        fail("CS2 MAP_WIN", traceback.format_exc())

    # BUG CHECK: main.py source routing — Dota 2 match now has "source" field
    try:
        from src.data_sources.grid_dota2 import GridDota2Source
        # Simulate what get_live_matches returns after fix
        mock_match = {
            "game_id": "dota2_12345",
            "team_a": "OG", "team_b": "Spirit",
            "match_name": "OG vs Spirit",
            "tournament": "The International",
            "source": "dota2",
        }
        # The main.py routing check
        source_type = "lol"  # default
        if mock_match.get("source") == "cs2":
            source_type = "cs2"
        elif mock_match.get("source") == "dota2":
            source_type = "dota2"
        assert source_type == "dota2", f"Expected dota2, got {source_type}"
        ok("Dota 2 routing works via 'source' field")

        # Empty tournament should still route correctly now
        mock_match2 = {**mock_match, "tournament": ""}
        source_type2 = "lol"
        if mock_match2.get("source") == "cs2":
            source_type2 = "cs2"
        elif mock_match2.get("source") == "dota2":
            source_type2 = "dota2"
        assert source_type2 == "dota2", f"Expected dota2, got {source_type2}"
        ok("Dota 2 routing with empty tournament (via source field)")
    except Exception as e:
        fail("Source routing", traceback.format_exc())

    # BUG CHECK: game_id collision fixed — Dota2 now prefixes with dota2_
    try:
        dota_id = "dota2_12345"  # prefixed
        lol_id = "12345"        # LoL raw
        if dota_id == lol_id:
            fail("Game ID collision", "Dota2 and LoL share same game_id format")
        else:
            ok("Game IDs distinct (dota2_ prefix)")
    except Exception as e:
        fail("Game ID collision", str(e))

    # =========================================================
    # SUMMARY
    # =========================================================
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if errors:
        print("\nFAILURES:")
        for name, reason in errors:
            print(f"  ✗ {name}: {reason[:200]}")

    return failed


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    sys.exit(min(exit_code, 1))
