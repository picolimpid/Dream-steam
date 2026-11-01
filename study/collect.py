"""Full-study collection: ~5,000 positive + ~5,000 negative recent English reviews across many paid games.

Steps (run in order; every step is resumable):
  python study/collect.py screen        # candidate games from SteamSpy -> review counts in the window
  python study/collect.py snapshot 1    # capped balanced sample + ALL window negatives (treatment + covariates)
  python study/collect.py snapshot 2    # ~2 weeks later: re-collect the same reviews (new helpful votes)
  python study/collect.py meta          # genres / tags per game, for later genre comparisons

Design
  window     reviews posted 2026-08-01 .. 2026-10-16 (2-13 weeks old at snapshot 1): recent enough to
             still gain votes before snapshot 2, old enough for reviewers to keep playing (or not)
  games      paid games from SteamSpy's popular lists; not stratified by genre (genre is recorded in `meta`)
  balance    per game, a cap per verdict set so the totals reach the targets; spread over 5 sub-windows
             so a game's sample is not just its newest reviews
  source     api.steampowered.com/IUserReviewsService/GetAppReviews (store.steampowered.com/appreviews
             now redirects); filter=1 (newest first), review_type 1=positive 2=negative, purchase_type 1=all
"""
import csv
import json
import math
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"
API = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"

TARGET = {"positive": 5000, "negative": 5000}
TARGET_BUFFER = 1.1  # aim 10% above target: a few sub-windows always come up short
MIN_PER_VERDICT = 40  # a game needs at least this many window reviews of each verdict
N_GAMES = 125  # random draw from eligible games: ~40 reviews per verdict per game, enough within-game contrast
SEED = 568


def ts(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


WINDOWS = [  # [start, end) in UTC
    ("w1", ts(2026, 8, 1), ts(2026, 8, 16)),
    ("w2", ts(2026, 8, 16), ts(2026, 9, 1)),
    ("w3", ts(2026, 9, 1), ts(2026, 9, 16)),
    ("w4", ts(2026, 9, 16), ts(2026, 10, 1)),
    ("w5", ts(2026, 10, 1), ts(2026, 10, 17)),
]
START, END = WINDOWS[0][1], WINDOWS[-1][2] - 1
REVIEW_TYPE = {"positive": 1, "negative": 2}


def get_json(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CS568-research (UIUC course project)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # 429 / transient
            last = e
            time.sleep(min(30 * (attempt + 1), 180))
    raise last


def reviews_page(appid, start, end, cursor="*", review_type=0, n=100):
    q = {"appid": appid, "filter": 1, "review_type": review_type, "purchase_type": 1,
         "languages[0]": "english", "date_range_start": start, "date_range_end": end,
         "num_per_page": n, "cursor": cursor}
    return get_json(API + "?" + urllib.parse.urlencode(q))["response"]


# ---------------------------------------------------------------- screen

def screen():
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "games_screened.csv"
    done = {int(r["appid"]) for r in csv.DictReader(out.open())} if out.exists() else set()

    pool = {}
    for req in ["top100in2weeks", "top100forever", "all&page=0", "all&page=1"]:
        for g in get_json(f"https://steamspy.com/api.php?request={req}").values():
            if str(g.get("price", "0")) not in ("0", "", "None"):  # paid only
                pool[int(g["appid"])] = g
        time.sleep(2)
    print(f"{len(pool)} paid candidates; {len(done)} already screened", flush=True)

    new = not out.exists()
    with out.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["appid", "name", "price_cents", "owners", "window_positive", "window_negative"])
        for i, (appid, g) in enumerate(pool.items(), 1):
            if appid in done:
                continue
            q = reviews_page(appid, START, END, n=1).get("query_summary", {})
            w.writerow([appid, g["name"], g["price"], g["owners"],
                        q.get("total_positive", 0), q.get("total_negative", 0)])
            f.flush()
            if i % 50 == 0:
                print(f"  screened {i}/{len(pool)}", flush=True)
            time.sleep(1)


def water_fill(counts, target):
    """Smallest per-game cap C with sum(min(n_g, C)) >= target."""
    lo, hi = 1, max(counts)
    while lo < hi:
        mid = (lo + hi) // 2
        if sum(min(n, mid) for n in counts) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def plan():
    eligible = [r for r in csv.DictReader((DATA / "games_screened.csv").open())
                if int(r["window_positive"]) >= MIN_PER_VERDICT and int(r["window_negative"]) >= MIN_PER_VERDICT]
    eligible.sort(key=lambda r: int(r["appid"]))
    games = random.Random(SEED).sample(eligible, min(N_GAMES, len(eligible)))
    caps = {}
    for v in TARGET:
        counts = [int(g[f"window_{v}"]) for g in games]
        need = int(TARGET[v] * TARGET_BUFFER)
        caps[v] = water_fill(counts, need) if sum(counts) >= need else max(counts)
    return games, caps


# ---------------------------------------------------------------- snapshots

def snapshot(n):
    games, caps = plan()
    out = DATA / f"snapshot{n}.jsonl"
    log = DATA / f"snapshot{n}_progress.json"
    progress = json.loads(log.read_text()) if log.exists() else {}
    # Snapshot 2 re-runs the same queries but fetches twice as deep, so deleted reviews in a
    # sub-window cannot push snapshot-1 reviews out of reach.
    depth = 1 if n == 1 else 2
    print(f"{len(games)} eligible games; per-game caps {caps}; per sub-window "
          f"{ {v: math.ceil(c / len(WINDOWS)) for v, c in caps.items()} }", flush=True)

    with out.open("a") as f:
        for gi, g in enumerate(games, 1):
            appid = int(g["appid"])
            for v, rt in REVIEW_TYPE.items():
                per_window = math.ceil(caps[v] / len(WINDOWS)) * depth
                for wname, ws, we in WINDOWS:
                    key = f"{appid}|{v}|{wname}"
                    if key in progress:
                        continue
                    got, cursor = 0, "*"
                    fetched_at = int(time.time())
                    while got < per_window:
                        r = reviews_page(appid, ws, we - 1, cursor, rt, min(100, per_window - got))
                        revs = r.get("reviews", [])
                        for x in revs:
                            x.update(appid=appid, game=g["name"], sample_verdict=v, window=wname,
                                     rank_in_window=got, snapshot=n, fetched_at=fetched_at)
                            f.write(json.dumps(x) + "\n")
                            got += 1
                        nxt = r.get("cursor")
                        if not revs or not nxt or nxt == cursor:
                            break
                        cursor = nxt
                        time.sleep(1)
                    f.flush()
                    progress[key] = got
                    log.write_text(json.dumps(progress))
                    time.sleep(1)
            tot = {v: sum(c for k, c in progress.items() if k.split("|")[1] == v) for v in REVIEW_TYPE}
            print(f"[{gi}/{len(games)}] {g['name'][:40]:40s} totals {tot}", flush=True)
    all_negatives(n)


def all_negatives(n):
    """Every negative review in the window for the selected games. Kept-playing negatives are only
    ~6% of recent negatives, so the capped sample alone cannot power H1 (snapshot 1: 188 kept)."""
    games, _ = plan()
    out = DATA / f"negatives_all_snapshot{n}.jsonl"
    log = DATA / f"negatives_all_snapshot{n}_progress.json"
    progress = json.loads(log.read_text()) if log.exists() else {}
    with out.open("a") as f:
        for gi, g in enumerate(games, 1):
            appid = int(g["appid"])
            if str(appid) in progress:
                continue
            got, cursor, fetched_at = 0, "*", int(time.time())
            while True:
                r = reviews_page(appid, START, END, cursor, REVIEW_TYPE["negative"], 100)
                revs = r.get("reviews", [])
                for x in revs:
                    x.update(appid=appid, game=g["name"], sample_verdict="negative", window="all",
                             rank_in_window=got, snapshot=n, fetched_at=fetched_at)
                    f.write(json.dumps(x) + "\n")
                    got += 1
                nxt = r.get("cursor")
                if not revs or not nxt or nxt == cursor:
                    break
                cursor = nxt
                time.sleep(1)
            f.flush()
            progress[str(appid)] = got
            log.write_text(json.dumps(progress))
            print(f"[neg {gi}/{len(games)}] {g['name'][:40]:40s} {got:5d} (window count "
                  f"{g['window_negative']})  total {sum(progress.values())}", flush=True)


# ---------------------------------------------------------------- metadata

def meta():
    games, _ = plan()
    out = DATA / "games_meta.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["appid", "name", "genre", "top_tags", "release_date", "price_cents", "owners",
                    "positive_all_time", "negative_all_time", "window_positive", "window_negative"])
        for g in games:
            d = get_json(f"https://steamspy.com/api.php?request=appdetails&appid={g['appid']}")
            tags = sorted((d.get("tags") or {}).items(), key=lambda kv: -kv[1]) if isinstance(d.get("tags"), dict) else []
            w.writerow([g["appid"], g["name"], d.get("genre", ""), "; ".join(t for t, _ in tags[:8]),
                        d.get("release_date", ""), d.get("price", ""), d.get("owners", ""),
                        d.get("positive", ""), d.get("negative", ""),
                        g["window_positive"], g["window_negative"]])
            time.sleep(1.2)
    print(f"wrote {out}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "screen":
        screen()
    elif cmd == "plan":
        games, caps = plan()
        print(f"{len(games)} eligible games, caps {caps}")
    elif cmd == "snapshot":
        snapshot(int(sys.argv[2]))
    elif cmd == "meta":
        meta()
