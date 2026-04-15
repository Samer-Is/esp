"""Paper-trading launcher — ensures DRY_RUN=true."""

import os
import sys

# Force DRY_RUN regardless of .env
os.environ["DRY_RUN"] = "true"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import main  # noqa: E402

if __name__ == "__main__":
    print("=== ESP Paper Trading Mode ===")
    print("DRY_RUN is forced ON — no real trades will be placed.")
    print("Press Ctrl+C to stop.\n")
    main()
