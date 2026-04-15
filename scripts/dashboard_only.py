"""Launch just the ESP Dashboard (no bot) — for viewing trade history and config."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DRY_RUN", "true")

from dashboard.server import start_dashboard

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", "8888"))
    print(f"ESP Dashboard → http://localhost:{port}")
    start_dashboard(port=port)
