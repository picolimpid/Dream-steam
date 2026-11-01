"""Controlled comparison of tone: does a sarcastic / profane review get more helpful votes than a
comparable sincere / clean one? Stratified propensity score analysis, separately by verdict.

Treatments (from rq1.py features)
  sarcasm    sentiment strongly contradicts the verdict (VADER |compound| >= 0.5, opposite sign)
  profanity  contains Steam's masked profanity
Covariates (fixed at posting, not tone): length, line breaks, hours at review, author #reviews, game, month
Outcomes: any helpful vote, log helpful votes, any funny vote (tone should move this one)
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from analyze import smd
from rq1 import FEATURES

RNG = np.random.default_rng(568)
COVARS = ["log_words", "log_lines", "log_hours_at", "log_nrev"]


def stratify(sub, t, n_strata=5, min_per_arm=5):
    f = f"{t} ~ " + " + ".join(COVARS) + " + I(log_words**2) + C(appid) + C(month)"
    m = smf.glm(f, sub, family=sm.families.Binomial()).fit()
    sub = sub.assign(ps=m.predict(sub))
    sub["stratum"] = pd.qcut(sub["ps"], n_strata, labels=False, duplicates="drop")
    c = sub.groupby("stratum")[t].agg(["sum", "size"])
    ok = c[(c["sum"] >= min_per_arm) & (c["size"] - c["sum"] >= min_per_arm)].index
    return sub[sub.stratum.isin(ok)]


def effect(sub, t, y):
    g = sub.groupby(["stratum", t])[y].mean().unstack(t)
    n = sub.groupby("stratum").size()
    return np.average(g[1] - g[0], weights=n[g.index])


def boot(sub, t, y, reps=500):
    groups = [s for _, s in sub.groupby("stratum")]
    est = [effect(pd.concat([s.iloc[RNG.integers(0, len(s), len(s))] for s in groups]), t, y)
           for _ in range(reps)]
    return np.percentile(est, [2.5, 97.5])


def main():
    d = pd.read_parquet(FEATURES)
    d = d[(d.hours_at > 0) & (d.refunded == 0)].copy()
    d["any_vote"] = (d.votes_up > 0).astype(int)
    d["log_votes"] = np.log1p(d.votes_up)
    d["any_funny"] = (d.votes_funny > 0).astype(int)
    d = d.rename(columns={"sent_mismatch": "sarcasm"})
    for t in ["sarcasm", "profanity"]:
        print(f"\n{'=' * 80}\nTreatment: {t}\n{'=' * 80}")
        for neg, label in [(0, "POS"), (1, "NEG")]:
            sub = d[d.neg == neg]
            st = stratify(sub, t)
            print(f"{label}: treated {int(sub[t].sum())} / {len(sub)};  after trimming {len(st)} in "
                  f"{st.stratum.nunique()} strata")
            worst_before = max(abs(smd(sub[c].values, sub[t].values)) for c in COVARS)
            worst_after = max(abs(smd(st[c].values, st[t].values, st.stratum.values)) for c in COVARS)
            print(f"   max |SMD| before {worst_before:.2f}  after {worst_after:.2f}")
            for y in ["any_vote", "log_votes", "any_funny"]:
                raw = sub[sub[t] == 1][y].mean() - sub[sub[t] == 0][y].mean()
                lo, hi = boot(st, t, y)
                print(f"   {y:9s} raw gap {raw:+.3f}   matched {effect(st, t, y):+.3f}  [{lo:+.3f}, {hi:+.3f}]")


if __name__ == "__main__":
    main()
