"""RQ1 pilot: which review characteristics are associated with helpful votes?

Content   length, readability, formatting, specificity, sentiment intensity, joke markers
Reviewer  hours at review, author #reviews, later-playtime ratio
Context   edited, received for free, early access, Steam purchase, review date
All models: separate for positive / negative reviews, game + month fixed effects,
SEs clustered by game, Benjamini-Hochberg across coefficients within each model.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import textstat
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DATA = Path(__file__).parent / "data" / "reviews_raw.jsonl"
FEATURES = Path(__file__).parent / "data" / "features.parquet"

BBCODE = re.compile(r"\[/?(h1|h2|h3|b|i|u|strike|list|olist|\*|table|tr|td|th|spoiler|quote|hr|url|code)\b", re.I)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")
PRICE = re.compile(r"[$€£]|\b(price|priced|worth|money|sale|discount|refund|full price|value)\b", re.I)
ASPECTS = ["gameplay", "story", "graphic", "visual", "performance", "fps", "frame", "optimi", "bug", "crash",
           "combat", "multiplayer", "co-op", "coop", "server", "matchmaking", "control", "soundtrack", "music",
           "sound", "ui", "menu", "content", "dlc", "update", "patch", "difficulty", "boss", "level", "map",
           "character", "quest", "mission", "progression", "grind", "dev", "cheater", "hacker", "anti-cheat",
           "microtransaction", "pc port", "port", "stutter", "load", "save", "mod", "community", "price"]
ASPECT_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in ASPECTS) + r")", re.I)
ASCII_ART = re.compile(r"[⠀-⣿▀-▟─-╿]")

CONTENT = ["log_words", "readability", "short", "formatted", "log_lines", "numbers_per100", "price_mention",
           "log_aspects", "sent_intensity", "sent_mismatch", "profanity", "ascii_art"]
REVIEWER = ["log_hours_at", "log_nrev", "log_ratio"]
# early access: only Valheim in the pilot (collinear with game FE); review age: absorbed by month FE
CONTEXT = ["edited", "free", "non_steam"]
BINARY = {"short", "formatted", "price_mention", "sent_mismatch", "profanity", "ascii_art",
          "edited", "free", "early_access", "non_steam"}
LABELS = {
    "log_words": "Length (log words)", "readability": "Readability (Flesch)", "short": "Short (<20 words)",
    "formatted": "BBCode formatting", "log_lines": "Line breaks (log)", "numbers_per100": "Numbers per 100 words",
    "price_mention": "Mentions price/value", "log_aspects": "Game aspects mentioned (log)",
    "sent_intensity": "Sentiment intensity", "sent_mismatch": "Sentiment contradicts verdict",
    "profanity": "Contains filtered profanity", "ascii_art": "ASCII art",
    "log_hours_at": "Hours at review (log)", "log_nrev": "Author #reviews (log)",
    "log_ratio": "Later/at-review playtime (log)", "edited": "Edited", "free": "Received for free",
    "early_access": "Early access", "non_steam": "Non-Steam key", "age_days": "Review age (days)",
}


def build():
    if FEATURES.exists():
        return pd.read_parquet(FEATURES)
    rows = [json.loads(l) for l in DATA.open()]
    vader = SentimentIntensityAnalyzer()
    out = []
    now = max(r["timestamp_created"] for r in rows)
    for r in rows:
        t, a = r["review"], r["author"]
        words = len(t.split())
        comp = vader.polarity_scores(t[:5000])["compound"]
        hours_at, hours_now = a.get("playtime_at_review", 0) / 60, a.get("playtime_forever", 0) / 60
        out.append({
            "appid": r["appid"], "game": r["game"], "recommendationid": r["recommendationid"],
            "neg": int(not r["voted_up"]),
            "votes_up": r["votes_up"], "votes_funny": r["votes_funny"], "comment_count": r["comment_count"],
            "words": words,
            "log_words": np.log1p(words),
            "readability": np.clip(textstat.flesch_reading_ease(t), -20, 120) if words >= 20 else np.nan,
            "short": int(words < 20),
            "formatted": int(bool(BBCODE.search(t))),
            "log_lines": np.log1p(t.count("\n")),
            "numbers_per100": 100 * len(NUMBER.findall(t)) / max(words, 1),
            "price_mention": int(bool(PRICE.search(t))),
            "log_aspects": np.log1p(len({m.lower() for m in ASPECT_RE.findall(t)})),
            "sent_compound": comp,
            "sent_intensity": abs(comp),
            # strong sentiment pointing the other way from the verdict (sarcasm / jokes)
            "sent_mismatch": int((comp <= -0.5 and r["voted_up"]) or (comp >= 0.5 and not r["voted_up"])),
            "profanity": int("♥♥" in t),  # Steam masks profanity with hearts
            "ascii_art": int(len(ASCII_ART.findall(t)) >= 20),
            "hours_at": hours_at,
            "log_hours_at": np.log1p(hours_at),
            "log_nrev": np.log1p(a.get("num_reviews", 0)),
            "log_ratio": np.log(hours_now / hours_at) if hours_at > 0 and hours_now >= hours_at else np.nan,
            "edited": int(r["timestamp_updated"] - r["timestamp_created"] > 86400),
            "free": int(r["received_for_free"]),
            "early_access": int(r["written_during_early_access"]),
            "non_steam": int(not r["steam_purchase"]),
            "refunded": int(r["refunded"]),
            "age_days": (now - r["timestamp_created"]) / 86400,
            "month": pd.Timestamp(r["timestamp_created"], unit="s").month,
        })
    df = pd.DataFrame(out)
    df.to_parquet(FEATURES)
    return df


def prepare(df):
    d = df[(df.hours_at > 0) & (df.refunded == 0) & df.log_ratio.notna()].copy()
    d["any_vote"] = (d.votes_up > 0).astype(int) * 100  # percentage points
    d["log_votes"] = np.log1p(d.votes_up)
    # Readability only defined for >= 20 words: impute the mean and let `short` absorb the difference
    d["readability"] = d["readability"].fillna(d["readability"].mean())
    return d


def standardize(d, cols):
    d = d.copy()
    for c in cols:
        if c not in BINARY:
            d[c] = (d[c] - d[c].mean()) / d[c].std()
    return d


MIN_CASES = 30


def usable(sub, cols):
    """Drop binary features with < MIN_CASES occurrences, and features that never vary within a game
    (they are absorbed by game fixed effects, e.g. early access is only Valheim in the pilot)."""
    keep = []
    for c in cols:
        if c in BINARY and sub[c].sum() < MIN_CASES:
            continue
        if sub.groupby("appid")[c].nunique().max() < 2:
            continue
        keep.append(c)
    return keep


def fit(d, y, cols):
    f = f"{y} ~ " + " + ".join(cols) + " + C(appid) + C(month)"
    return smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d["appid"]})


def section(t):
    print(f"\n{'=' * 90}\n{t}\n{'=' * 90}")


def main():
    df = build()
    d = prepare(df)
    cols = CONTENT + REVIEWER + CONTEXT

    section("R0  Sample and feature descriptives")
    print(f"reviews {len(d)} (POS {int((d.neg == 0).sum())}, NEG {int(d.neg.sum())}), games {d.appid.nunique()}")
    desc = d.groupby("neg")[["words", "readability", "formatted", "price_mention", "log_aspects",
                             "sent_intensity", "sent_mismatch", "profanity", "ascii_art", "short"]].mean().T
    desc.columns = ["POS mean", "NEG mean"]
    print(desc.round(3).to_string())

    section("R1  Multicollinearity check (VIF, full sample, standardized)")
    s = standardize(d, cols)
    X = s[cols].astype(float).assign(const=1.0).values
    vif = pd.Series([variance_inflation_factor(X, i) for i in range(len(cols))], index=cols)
    print(vif.round(2).sort_values(ascending=False).head(6).to_string())
    print("(VIF > 5 would signal redundant predictors)")

    results = []
    for neg, label in [(0, "POS"), (1, "NEG")]:
        sub = standardize(d[d.neg == neg], cols)
        use = usable(sub, cols)
        print(f"{label}: dropped as too rare or absorbed by game FE: {sorted(set(cols) - set(use))}")
        for y in ["any_vote", "log_votes"]:
            m = fit(sub, y, use)
            p_bh = multipletests(m.pvalues[use], method="fdr_bh")[1]
            for c, q in zip(use, p_bh):
                results.append({"verdict": label, "outcome": y, "feature": c, "group":
                                "content" if c in CONTENT else "reviewer" if c in REVIEWER else "context",
                                "b": m.params[c], "se": m.bse[c], "p": m.pvalues[c], "q_bh": q,
                                "share": sub[c].mean() if c in BINARY else np.nan})
    res = pd.DataFrame(results)
    res.to_csv(Path(__file__).parent / "rq1_coefficients.csv", index=False)

    section("R2  Coefficients: any helpful vote (percentage points; continuous = per 1 SD)")
    tab = res[res.outcome == "any_vote"].pivot_table(index=["group", "feature"], columns="verdict",
                                                     values=["b", "q_bh"])
    tab.columns = [f"{v}_{s}" for s, v in tab.columns]
    tab = tab[["POS_b", "POS_q_bh", "NEG_b", "NEG_q_bh"]]
    tab.index = [f"{g:8s} {LABELS[f]}" for g, f in tab.index]
    print(tab.round(3).to_string())
    print("q_bh = Benjamini-Hochberg adjusted p; binary features: effect of having the feature")

    section("R3  Same model, outcome log(1 + helpful votes)")
    tab = res[res.outcome == "log_votes"].pivot_table(index=["group", "feature"], columns="verdict",
                                                      values=["b", "q_bh"])
    tab.columns = [f"{v}_{s}" for s, v in tab.columns]
    tab = tab[["POS_b", "POS_q_bh", "NEG_b", "NEG_q_bh"]]
    tab.index = [f"{g:8s} {LABELS[f]}" for g, f in tab.index]
    print(tab.round(3).to_string())

    section("R4  Unique explanatory power of each feature group (drop-one, within-game R2, any vote)")
    for neg, label in [(0, "POS"), (1, "NEG")]:
        sub = standardize(d[d.neg == neg], cols)
        use = usable(sub, cols)
        base = smf.ols("any_vote ~ C(appid) + C(month)", sub).fit().rsquared
        full = fit(sub, "any_vote", use).rsquared
        line = f"{label}: FE only R2={base:.3f}, full R2={full:.3f} | unique:"
        for g, gcols in [("content", CONTENT), ("reviewer", REVIEWER), ("context", CONTEXT)]:
            r2 = fit(sub, "any_vote", [c for c in use if c not in gcols]).rsquared
            line += f"  {g} {full - r2:.3f}"
        print(line)

    section("R5  Joke/sarcasm markers vs. funny votes (validity check for the joke filter)")
    for c in ["sent_mismatch", "profanity", "ascii_art", "short"]:
        g = d.groupby(c)[["votes_funny", "votes_up"]].mean()
        print(f"{LABELS[c]:30s} funny/helpful with={g.loc[1, 'votes_funny']:.2f}/{g.loc[1, 'votes_up']:.2f}"
              f"  without={g.loc[0, 'votes_funny']:.2f}/{g.loc[0, 'votes_up']:.2f}")


if __name__ == "__main__":
    main()
