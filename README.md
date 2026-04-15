# ESP — Esports Signal Parser & Polymarket Trader

Automated bot that detects real-time in-game events from pro esports matches via official APIs before stream viewers see them, then trades on Polymarket esports markets where odds have not yet adjusted.

## Supported Games
- **League of Legends** — Riot LoL Esports API (live)
- **Dota 2** — GRID Open Access API (pending approval)
- **CS2** — GRID Open Access API (pending approval)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Samer-Is/esp.git
cd esp

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your keys

# 4. Run (paper trading by default)
python -m src.main
```

## Architecture

```
[LoL Esports API]  ──polling──▶ ┌─────────────────────┐
[GRID Dota 2 API]  ──polling──▶ │  SIGNAL DETECTOR     │──▶ [RISK MANAGER]──▶ [ORDER EXECUTOR]──▶ Polymarket
[GRID CS2 API]     ──polling──▶ │  (event detection +  │                     (py-clob-client)
                                │   probability calc)  │
                                └─────────────────────┘
```

See `BUILD_INSTRUCTIONS.md` for full documentation.
