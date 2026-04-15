import os
from datetime import datetime, timezone


ACTIVITY_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ACTIVITY_LOG.md",
)

# Valid log categories
CATEGORIES = {"SYSTEM", "DATA", "SIGNAL", "TRADE", "RESOLUTION", "ERROR", "SKIP"}


def log_activity(category: str, message: str) -> None:
    """Append a timestamped entry to ACTIVITY_LOG.md."""
    if category not in CATEGORIES:
        category = "SYSTEM"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"- **[{category}]** `{ts}` — {message}\n"

    with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
