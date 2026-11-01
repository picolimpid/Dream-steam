"""Do readers notice playtime? Count reader comments that reference the reviewer's hours,
overall and by verdict x kept-playing group.

Writes random matched / unmatched examples to data/ (git-ignored) for manual precision checks.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"

PLAYTIME = re.compile(
    r"\b\d[\d,.]*\s*k?\s*(?:hours?|hrs?|h)\b"           # "500 hours", "2k hrs", "300h"
    r"|\b(?:hours?|hrs|playtime|play\s?time)\b"          # "all those hours", "your playtime"
    r"|\b(?:still|keep|kept|continue[sd]?\sto)\s+play",  # "yet you're still playing"
    re.I,
)
# Reader addressing the reviewer: playtime talk + second person, or a bare quote of the hours ("666 hours played")
SECOND_PERSON = re.compile(r"\b(?:you|your|you'?re|you'?ve|u|ur|ya)\b", re.I)
BARE_HOURS = re.compile(r"^\s*\d[\d,.]*\s*k?\s*(?:hours?|hrs?|h)\b", re.I)


def directed(t):
    return bool(PLAYTIME.search(t)) and (bool(SECOND_PERSON.search(t)) or bool(BARE_HOURS.match(t)))


def main():
    reviews = {r["recommendationid"]: r for r in map(json.loads, (DATA / "reviews_raw.jsonl").open())}
    threads = [json.loads(l) for l in (DATA / "comments_raw.jsonl").open()]
    # Copy-pasted comments that appear under several reviews are spam, not reactions to the review
    counts = pd.Series([t for c in threads for t in c["comments"]]).value_counts()
    spam = {t for t, n in counts.items() if n > 1 and len(t) >= 30}  # short repeats ("lol", "real") are normal replies
    rows, examples = [], []
    for c in threads:
        r = reviews[c["recommendationid"]]
        a = r["author"]
        at, now = a["playtime_at_review"] / 60, a["playtime_forever"] / 60
        c["comments"] = [t for t in c["comments"] if t not in spam]
        hits = [t for t in c["comments"] if PLAYTIME.search(t)]
        dhits = [t for t in c["comments"] if directed(t)]
        group = ("kept" if at > 0 and now >= 2 * at and now - at >= 10 else
                 "stopped" if at > 0 and now <= 1.1 * at else "middle")
        rows.append({"status": c["status"], "neg": not r["voted_up"], "group": group,
                     "n_comments": len(c["comments"]), "n_hits": len(hits), "any_hit": bool(hits),
                     "n_directed": len(dhits), "any_directed": bool(dhits),
                     "votes_up": r["votes_up"], "hours_at": at})
        examples += [(bool(PLAYTIME.search(t)), directed(t), r["voted_up"], round(at), round(now), t[:200]) for t in c["comments"]]
    d = pd.DataFrame(rows)

    print(f"threads fetched: {len(d)}  status: {d.status.value_counts().to_dict()}  "
          f"spam comments removed: {sum(counts[t] for t in spam)}")
    ok = d[d.n_comments > 0]
    print(f"threads with readable comments: {len(ok)}, comments: {ok.n_comments.sum()}")
    print(f"comments mentioning playtime: {ok.n_hits.sum()} ({ok.n_hits.sum() / ok.n_comments.sum():.1%})")
    print(f"threads with >=1 playtime mention: {ok.any_hit.mean():.1%}")
    print(f"comments addressing the REVIEWER's playtime (strict): {ok.n_directed.sum()} "
          f"({ok.n_directed.sum() / ok.n_comments.sum():.1%}); threads: {ok.any_directed.mean():.1%}")

    print("\nBy verdict and later-playtime group (thread level):")
    t = ok.groupby(["neg", "group"]).agg(threads=("any_hit", "size"), share_with_mention=("any_hit", "mean"),
                                         comments=("n_comments", "sum"), mentions=("n_hits", "sum"),
                                         share_directed=("any_directed", "mean"), directed=("n_directed", "sum"))
    t.index = t.index.map(lambda i: f"{'NEG' if i[0] else 'POS'} {i[1]}")
    print(t.round(3).to_string())

    ex = pd.DataFrame(examples, columns=["match", "directed", "voted_up", "hours_at", "hours_now", "comment"])
    sample = pd.concat([ex[ex.match].sample(min(40, ex.match.sum()), random_state=1),
                        ex[~ex.match].sample(min(40, (~ex.match).sum()), random_state=1)])
    sample.to_csv(DATA / "comment_coding_sample.csv", index=False)
    print(f"\nWrote {len(sample)} examples to data/comment_coding_sample.csv for manual precision/recall checks")


if __name__ == "__main__":
    main()
