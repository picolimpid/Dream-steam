"""Collect reader comments under pilot reviews that have any (comment_count > 0).

Comments are read from the public review page (steamcommunity.com/profiles/<id>/recommended/<appid>/),
which shows the first page of comments. Only comment text is stored; commenter names are not.
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SRC = DATA / "reviews_raw.jsonl"
OUT = DATA / "comments_raw.jsonl"

COMMENT_RE = re.compile(r'class="commentthread_comment_text"[^>]*>(.*?)</div>', re.S)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CS568 research pilot)"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            time.sleep(30 * (attempt + 1))
            last = e
    raise last


def clean(t):
    t = re.sub(r"<br\s*/?>", "\n", t)
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def main():
    done = {json.loads(l)["recommendationid"] for l in OUT.open()} if OUT.exists() else set()
    todo = [r for r in map(json.loads, SRC.open())
            if r["comment_count"] > 0 and r["recommendationid"] not in done]
    print(f"{len(done)} done, {len(todo)} to fetch", flush=True)
    with OUT.open("a") as f:
        for i, r in enumerate(todo, 1):
            url = f"https://steamcommunity.com/profiles/{r['author']['steamid']}/recommended/{r['appid']}/"
            try:
                page = fetch(url)
                comments = [clean(c) for c in COMMENT_RE.findall(page)]
                status = "ok" if comments or "commentthread" in page else "unavailable"
            except Exception as e:
                comments, status = [], f"error: {e}"
            f.write(json.dumps({"recommendationid": r["recommendationid"], "status": status,
                                "comments": comments}) + "\n")
            f.flush()
            if i % 50 == 0:
                print(f"{i}/{len(todo)}", flush=True)
            time.sleep(1.5)


if __name__ == "__main__":
    main()
