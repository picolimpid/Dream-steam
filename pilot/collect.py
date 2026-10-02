"""Pilot collection: English reviews written Apr-Sep 2025 for a small, genre-diverse set of paid games.

Reviews are pulled month by month (filter=recent inside a date window) so every review
has had 12-18 months to accumulate votes and for its author to keep playing.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "data" / "reviews_raw.jsonl"

# appid: (name, genre, popularity tier)
GAMES = {
    1245620: ("Elden Ring", "action-rpg", "huge"),
    1086940: ("Baldur's Gate 3", "rpg", "huge"),
    1091500: ("Cyberpunk 2077", "rpg", "huge"),
    1174180: ("Red Dead Redemption 2", "action", "huge"),
    105600: ("Terraria", "sandbox", "huge"),
    413150: ("Stardew Valley", "sim", "huge"),
    252490: ("Rust", "multiplayer-survival", "huge"),
    553850: ("Helldivers 2", "multiplayer-shooter", "huge"),
    381210: ("Dead by Daylight", "multiplayer-horror", "large"),
    892970: ("Valheim", "survival", "large"),
    294100: ("RimWorld", "strategy-sim", "large"),
    427520: ("Factorio", "strategy-sim", "large"),
    1145360: ("Hades", "roguelike", "large"),
    367520: ("Hollow Knight", "metroidvania", "large"),
    646570: ("Slay the Spire", "roguelike", "large"),
    2379780: ("Balatro", "roguelike", "large"),
    2050650: ("Resident Evil 4", "action-horror", "mid"),
    1868140: ("Dave the Diver", "adventure", "mid"),
    1332010: ("Stray", "adventure", "mid"),
    504230: ("Celeste", "platformer", "mid"),
}

MONTHS = [(2025, m) for m in range(4, 10)]  # Apr..Sep 2025
PER_MONTH = 200  # max reviews per game-month


def ts(y, m, d=1):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


def fetch(appid, start, end, cursor):
    params = {
        "json": 1, "language": "english", "filter": "recent", "purchase_type": "all",
        "num_per_page": 100, "cursor": cursor,
        "start_date": start, "end_date": end, "date_range_type": "include",
    }
    url = f"https://store.steampowered.com/appreviews/{appid}?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # rate limit / transient
            time.sleep(60 * (attempt + 1))
            last = e
    raise last


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Resume: keep games that finished, drop the partial one that was interrupted.
    rows = [json.loads(l) for l in OUT.open()] if OUT.exists() else []
    done = list(dict.fromkeys(r["appid"] for r in rows))[:-1]
    rows = [r for r in rows if r["appid"] in done]
    seen = {r["recommendationid"] for r in rows}
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        for appid, (name, genre, tier) in GAMES.items():
            if appid in done:
                continue
            n_game = 0
            for y, m in MONTHS:
                start = ts(y, m)
                end = ts(y + (m == 12), m % 12 + 1) - 1
                cursor, got = "*", 0
                while got < PER_MONTH:
                    d = fetch(appid, start, end, cursor)
                    revs = d.get("reviews", [])
                    new = [r for r in revs if r["recommendationid"] not in seen]
                    for r in new:
                        seen.add(r["recommendationid"])
                        r.update(appid=appid, game=name, genre=genre, tier=tier)
                        f.write(json.dumps(r) + "\n")
                    got += len(new)
                    if not new or d.get("cursor") in (None, cursor):
                        break
                    cursor = d["cursor"]
                    time.sleep(0.7)
                n_game += got
            print(f"{name:25s} {n_game:5d}", flush=True)


if __name__ == "__main__":
    main()
