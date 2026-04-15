"""Launch ESP Bot + Dashboard together.

Starts the dashboard web server on port 8888 and the bot in the same process,
sharing live state via the BotState singleton.
"""

import asyncio
import sys
import os
import threading

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault("DRY_RUN", "true")

import uvicorn
from dashboard.server import app
from src.main import ESPBot


async def run_bot(bot: ESPBot):
    """Run the bot's main loop."""
    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        print(f"Bot error: {e}")
        await bot.stop()


def start_dashboard_thread(host: str, port: int):
    """Run the Uvicorn server in a background thread."""
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    # Uvicorn expects its own event loop in a thread
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def main():
    host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.environ.get("DASHBOARD_PORT", "8888"))

    print("=" * 56)
    print("  ESP — Esports Signal Parser & Polymarket Trader")
    print("=" * 56)
    print(f"  Dashboard:  http://localhost:{port}")
    print(f"  Mode:       {'DRY RUN' if os.environ.get('DRY_RUN', 'true').lower() == 'true' else 'LIVE'}")
    print("=" * 56)

    # Start dashboard in background thread
    start_dashboard_thread(host, port)

    # Run bot in main thread event loop
    bot = ESPBot()
    try:
        asyncio.run(run_bot(bot))
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
