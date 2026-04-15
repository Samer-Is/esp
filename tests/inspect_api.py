import asyncio
import httpx
import json

async def main():
    c = httpx.AsyncClient(timeout=15, headers={"x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"})
    r = await c.get("https://feed.lolesports.com/livestats/v1/window/115548128962906288")
    d = r.json()
    f = d["frames"][-1]
    bt = f.get("blueTeam", {})
    print("blueTeam keys:", list(bt.keys()))
    print("dragons:", type(bt.get("dragons")), bt.get("dragons"))
    print("barons:", type(bt.get("barons")), bt.get("barons"))
    print("towers:", type(bt.get("towers")), bt.get("towers"))
    print("inhibitors:", type(bt.get("inhibitors")), bt.get("inhibitors"))
    print("totalGold:", type(bt.get("totalGold")), bt.get("totalGold"))
    print("totalKills:", type(bt.get("totalKills")), bt.get("totalKills"))
    await c.aclose()

asyncio.run(main())
