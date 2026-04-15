import asyncio
from src.data_sources.grid_dota2 import GridDota2Source

async def main():
    s = GridDota2Source()
    await s.start()
    m = await s.get_live_matches()
    print("Live Dota2 matches (no key expected):", m)
    await s.stop()
    print("GridDota2Source OK")

asyncio.run(main())
