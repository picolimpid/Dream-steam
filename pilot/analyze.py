"""Pilot analyses for: do helpful votes depend on whether the reviewer kept playing?

Design
  outcome    votes_up
  treatment  kept  = hours_now >= 2x hours_at_review AND +10h   (vs. stopped = hours_now <= 1.1x)
  moderator  neg   = not recommended
  fixed by sampling   English, written Apr-Sep 2025 (12-18 months old), Steam purchase,
                      not free, not refunded, not early access, not edited, >= 1h at review
  held equal (match / FE)   game, hours at review, review length, review month, author #reviews
"""
import json
import sys
from pathlib import Path

import numpy as np
import patsy
import pandas as pd
import statsmodels.formula.api as smf

DATA = Path(__file__).parent / "data" / "reviews_raw.jsonl"
RNG = np.random.default_rng(568)

HOURS_BINS = [0, 1, 3, 10, 30, 100, 300, np.inf]
LEN_BINS = [0, 50, 200, 800, np.inf]


def load():
    rows = [json.loads(l) for l in DATA.open()]
    df = pd.json_normalize(rows)
    df.columns = [c.replace("author.", "a_") for c in df.columns]
    now = df["timestamp_created"].max()  # approx collection time
    out = pd.DataFrame({
        "appid": df["appid"], "game": df["game"],
        "votes_up": df["votes_up"].astype(int),
        "votes_funny": df["votes_funny"].astype(int),
        "wvs": df["weighted_vote_score"].astype(float),
        "neg": (~df["voted_up"].astype(bool)).astype(int),
        "hours_at": df["a_playtime_at_review"].fillna(0) / 60,
        "hours_now": df["a_playtime_forever"].fillna(0) / 60,
        "length": df["review"].str.len(),
        "age_days": (now - df["timestamp_created"]) / 86400,
        "month": pd.to_datetime(df["timestamp_created"], unit="s").dt.month,
        "a_nrev": df["a_num_reviews"],
        "a_ngames": df["a_num_games_owned"],
        "purchased_clean": df["steam_purchase"] & ~df["received_for_free"] & ~df["refunded"],
        "early_access": df["written_during_early_access"],
        "edited": (df["timestamp_updated"] - df["timestamp_created"]) > 86400,
    })
    out["ratio"] = out["hours_now"] / out["hours_at"].where(out["hours_at"] > 0)
    out["gain"] = out["hours_now"] - out["hours_at"]
    out["log_hours_at"] = np.log1p(out["hours_at"])
    out["log_len"] = np.log1p(out["length"])
    out["log_nrev"] = np.log1p(out["a_nrev"])
    out["any_vote"] = (out["votes_up"] > 0).astype(int)
    out["log_votes"] = np.log1p(out["votes_up"])
    out["hbin"] = pd.cut(out["hours_at"], HOURS_BINS, right=False, labels=False)
    out["lbin"] = pd.cut(out["length"], LEN_BINS, right=False, labels=False)
    return out


def restrict(df, clean=True, unedited=True, min_hours=1.0):
    m = df["hours_at"] >= min_hours
    if clean:
        m &= df["purchased_clean"] & ~df["early_access"]
    if unedited:
        m &= ~df["edited"]
    return df[m].copy()


def treat(df, mult=2.0, min_gain=10.0, stop_mult=1.1):
    d = df.copy()
    kept = (d["ratio"] >= mult) & (d["gain"] >= min_gain)
    stopped = d["ratio"] <= stop_mult
    d = d[kept | stopped].copy()
    d["kept"] = kept[kept | stopped].astype(int)
    d["kept_pos"] = d["kept"] * (1 - d["neg"])
    d["kept_neg"] = d["kept"] * d["neg"]
    return d


# ---------- estimators ----------

def cem(d, y="votes_up", treat_col="kept"):
    """Coarsened exact matching: within game x verdict x hours-bin x length-bin x month,
    compare kept vs stopped; average the within-stratum gaps weighted by stratum size."""
    keys = ["appid", "neg", "hbin", "lbin", "month"]
    g = d.groupby(keys + [treat_col], observed=True)[y].agg(["mean", "size"]).unstack(treat_col)
    g = g.dropna()
    g["gap"] = g[("mean", 1)] - g[("mean", 0)]
    g["w"] = g[("size", 0)] + g[("size", 1)]
    res = {}
    for neg, sub in g.groupby(level="neg"):
        res["neg" if neg else "pos"] = (np.average(sub["gap"], weights=sub["w"]), int(sub["w"].sum()), len(sub))
    return res


def poisson_fe(d, y="votes_up"):
    f = f"{y} ~ kept_pos + kept_neg + neg + log_hours_at + log_len + age_days + log_nrev + C(appid)"
    m = smf.poisson(f, d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d["appid"]}, maxiter=200)
    return m


# Strata-level controls: game, hours-bin and length-bin each get their own intercept per verdict.
RHS = "C(appid)*neg + C(hbin)*neg + C(lbin)*neg + log_hours_at + log_len + age_days + log_nrev"


def ols_fe(d, y):
    f = f"{y} ~ kept_pos + kept_neg + {RHS}"
    return smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d["appid"]})


# Pre-treatment covariates: everything known at the moment the review was posted.
PS_COVARS = ["log_hours_at", "log_len", "age_days", "log_nrev"]


def smd(x, t, w=None):
    """Standardized mean difference treated - control; with strata labels w, the
    within-stratum gaps are averaged by stratum size (subclassification)."""
    sd = np.sqrt((x[t == 1].var() + x[t == 0].var()) / 2)
    if sd == 0:
        return 0.0
    if w is None:
        return (x[t == 1].mean() - x[t == 0].mean()) / sd
    df = pd.DataFrame({"x": x, "t": t, "s": w})
    g = df.groupby(["s", "t"])["x"].mean().unstack("t")
    n = df.groupby("s").size()
    return np.average(g[1] - g[0], weights=n[g.index]) / sd


def ps_stratify(sub, n_strata, min_per_arm=3):
    """Saha et al.-style stratified propensity score analysis within one verdict group.
    Returns the sub-sample kept after trimming, with a 'stratum' column."""
    sub = sub.copy()
    f = "kept ~ " + " + ".join(PS_COVARS) + " + I(log_hours_at**2) + C(appid)"
    m = smf.glm(f, sub, family=__import__("statsmodels.api").api.families.Binomial()).fit()
    sub["ps"] = m.predict(sub)
    sub["stratum"] = pd.qcut(sub["ps"], n_strata, labels=False, duplicates="drop")
    counts = sub.groupby("stratum")["kept"].agg(["sum", "size"])
    ok = counts[(counts["sum"] >= min_per_arm) & (counts["size"] - counts["sum"] >= min_per_arm)].index
    return sub[sub["stratum"].isin(ok)]


def strat_effect(sub, y):
    g = sub.groupby(["stratum", "kept"])[y].mean().unstack("kept")
    n = sub.groupby("stratum").size()
    return np.average(g[1] - g[0], weights=n[g.index])


def strat_bootstrap(sub, y, reps=1000):
    """Resample within strata, keeping the propensity-score strata fixed."""
    groups = [s.reset_index(drop=True) for _, s in sub.groupby("stratum")]
    est = []
    for _ in range(reps):
        b = pd.concat([s.iloc[RNG.integers(0, len(s), len(s))] for s in groups])
        if b.groupby("stratum")["kept"].nunique().min() < 2:
            continue
        est.append(strat_effect(b, y))
    return np.percentile(est, [2.5, 97.5])


def fmt_coef(m, name, irr=False):
    b, se, p = m.params[name], m.bse[name], m.pvalues[name]
    if irr:
        return f"IRR={np.exp(b):.2f} [{np.exp(b-1.96*se):.2f},{np.exp(b+1.96*se):.2f}] p={p:.3f}"
    return f"b={b:+.3f} (se {se:.3f}) p={p:.3f}"


def interaction_p(m):
    return m.t_test("kept_pos - kept_neg = 0").pvalue


def section(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def main():
    raw = load()
    section("E0  Sample flow and descriptives")
    print(f"raw reviews            {len(raw):6d}   games={raw.appid.nunique()}")
    base = restrict(raw)
    print(f"after fixed filters    {len(base):6d}")
    d = treat(base)
    print(f"kept or stopped        {len(d):6d}   (middle group dropped: {len(base) - len(d)})")
    print(f"zero helpful votes     {1 - d.any_vote.mean():.1%}   max votes_up={d.votes_up.max()}")
    print(f"num_games_owned == 0   {(raw.a_ngames == 0).mean():.1%}  (private profiles -> not usable as control)")
    print(f"edited reviews         {raw.edited.mean():.1%}")

    section("E1  Raw four-group comparison (no matching)")
    t = d.groupby(["neg", "kept"]).agg(n=("votes_up", "size"), mean_votes=("votes_up", "mean"),
                                       median=("votes_up", "median"), any_vote=("any_vote", "mean"),
                                       hours_at=("hours_at", "median"), length=("length", "median"))
    t.index = t.index.map(lambda i: f"{'NEG' if i[0] else 'POS'} {'kept' if i[1] else 'stopped'}")
    print(t.round(2).to_string())
    print("-> note how groups differ on hours_at / length: raw gaps are confounded")

    section("E2  Matched within-stratum comparison (CEM: game x verdict x hours x length x month)")
    for y in ["votes_up", "any_vote", "log_votes"]:
        r = cem(d, y)
        print(f"{y:10s}  POS kept-stopped = {r['pos'][0]:+.3f} (n={r['pos'][1]}, strata={r['pos'][2]})"
              f"   NEG kept-stopped = {r['neg'][0]:+.3f} (n={r['neg'][1]}, strata={r['neg'][2]})")
    print("H1 predicts NEG < 0, H2 predicts POS > 0")

    section("E3  Regression: game x verdict, hours-bin x verdict, length-bin x verdict FE (clustered by game)")
    m = poisson_fe(d)
    print("Poisson   kept | POS :", fmt_coef(m, "kept_pos", irr=True))
    print("Poisson   kept | NEG :", fmt_coef(m, "kept_neg", irr=True))
    print(f"          H1 vs H2 difference p={interaction_p(m):.3f}")
    for y in ["any_vote", "log_votes"]:
        o = ols_fe(d, y)
        print(f"OLS {y:9s} POS: {fmt_coef(o, 'kept_pos')}   NEG: {fmt_coef(o, 'kept_neg')}")

    section("E4  Dose-response: playtime ratio bins (log1p votes, within game via demeaning)")
    b = base.copy()
    b = b[b.ratio.notna()]
    b["rbin"] = pd.cut(b["ratio"], [0, 1.1, 1.5, 2, 3, 5, np.inf], right=False,
                       labels=["<1.1x", "1.1-1.5x", "1.5-2x", "2-3x", "3-5x", ">=5x"])
    b["log_votes_dm"] = b["log_votes"] - b.groupby(["appid", "neg", "hbin"])["log_votes"].transform("mean")
    p = b.pivot_table(index="rbin", columns="neg", values="log_votes_dm", aggfunc=["mean", "size"], observed=True)
    p.columns = [f"{a}_{'NEG' if n else 'POS'}" for a, n in p.columns]
    print(p.round(3).to_string())
    print("(values are deviations from game x verdict x hours-bin mean; a monotone trend is more convincing than a cutoff)")

    section("E5  Robustness: kept-playing threshold")
    for mult in [1.5, 2.0, 3.0]:
        dd = treat(base, mult=mult)
        mm = ols_fe(dd, "log_votes")
        print(f"{mult:.1f}x  n={len(dd):5d}  POS: {fmt_coef(mm, 'kept_pos')}   NEG: {fmt_coef(mm, 'kept_neg')}")

    section("E6  Alternative outcome and negative-control outcome")
    o = ols_fe(d, "wvs")
    print(f"weighted_vote_score  POS: {fmt_coef(o, 'kept_pos')}   NEG: {fmt_coef(o, 'kept_neg')}")
    d["log_funny"] = np.log1p(d["votes_funny"])
    o = ols_fe(d, "log_funny")
    print(f"log funny votes      POS: {fmt_coef(o, 'kept_pos')}   NEG: {fmt_coef(o, 'kept_neg')}")
    print("(funny votes are not about credibility: an effect here signals visibility/exposure confounding)")

    section("E7  Placebo: shuffle kept within game x verdict x hours-bin (1000 permutations)")
    # Same OLS-FE model as E3/E5; only the kept labels are shuffled.
    C = np.asarray(patsy.dmatrix(RHS, d))
    y, neg = d["log_votes"].values, d["neg"].values

    def coefs(k):
        X = np.column_stack([k * (1 - neg), k * neg, C])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        return b[0], b[1]

    obs_pos, obs_neg = coefs(d["kept"].values)
    grp = d.groupby(["appid", "neg", "hbin"], observed=True).ngroup().values
    blocks = [np.where(grp == g)[0] for g in np.unique(grp)]
    perms = []
    for _ in range(1000):
        k = d["kept"].values.copy()
        for idx in blocks:
            k[idx] = RNG.permutation(k[idx])
        perms.append(coefs(k))
    perms = np.array(perms)
    p_pos = (np.abs(perms[:, 0]) >= abs(obs_pos)).mean()
    p_neg = (np.abs(perms[:, 1]) >= abs(obs_neg)).mean()
    print(f"POS observed {obs_pos:+.3f}  placebo 95% range [{np.percentile(perms[:, 0], 2.5):+.3f},"
          f"{np.percentile(perms[:, 0], 97.5):+.3f}]  permutation p={p_pos:.3f}")
    print(f"NEG observed {obs_neg:+.3f}  placebo 95% range [{np.percentile(perms[:, 1], 2.5):+.3f},"
          f"{np.percentile(perms[:, 1], 97.5):+.3f}]  permutation p={p_neg:.3f}")

    section("E8  Sensitivity to what we fix by sampling")
    specs = {
        "main (all filters)": dict(),
        "drop purchase/EA filter": dict(clean=False),
        "keep edited reviews": dict(unedited=False),
        "min 0h at review": dict(min_hours=0.0),
        "min 5h at review": dict(min_hours=5.0),
    }
    for name, kw in specs.items():
        dd = treat(restrict(raw, **kw))
        mm = ols_fe(dd, "log_votes")
        print(f"{name:24s} n={len(dd):5d}  POS: {fmt_coef(mm, 'kept_pos')}   NEG: {fmt_coef(mm, 'kept_neg')}")

    section("E9  Heterogeneity: per-game NEG effect (is it driven by a few games?)")
    rows = []
    for (appid, game), sub in d.groupby(["appid", "game"]):
        s = sub[sub.neg == 1]
        if s.kept.sum() >= 5 and (1 - s.kept).sum() >= 5:
            rows.append((game, len(s), s.kept.mean(),
                         s[s.kept == 1].log_votes.mean() - s[s.kept == 0].log_votes.mean()))
    h = pd.DataFrame(rows, columns=["game", "n_neg", "share_kept", "raw_gap_log_votes"]).sort_values("raw_gap_log_votes")
    print(h.round(3).to_string(index=False))
    print(f"games with NEG gap < 0: {(h.raw_gap_log_votes < 0).sum()}/{len(h)}")

    section("E10 Stratified propensity score analysis (Saha et al. 2019 style), per verdict")
    print("PS model: logit(kept) ~ log hours at review (+sq) + log length + review date + log author #reviews + game")
    for neg, label, n_strata in [(0, "POS", 10), (1, "NEG", 5)]:
        sub = d[d.neg == neg]
        st = ps_stratify(sub, n_strata)
        print(f"\n{label}: n={len(sub)} -> {len(st)} after trimming strata without overlap "
              f"(kept={st.kept.sum()}, stopped={(1 - st.kept).sum()}, strata={st.stratum.nunique()})")
        print(f"  {'covariate':16s} {'SMD before':>11s} {'SMD after':>10s}")
        for c in PS_COVARS:
            print(f"  {c:16s} {smd(sub[c].values, sub.kept.values):+11.3f} "
                  f"{smd(st[c].values, st.kept.values, st.stratum.values):+10.3f}")
        games = pd.get_dummies(sub.appid, dtype=float)
        games_st = pd.get_dummies(st.appid, dtype=float)
        before = max(abs(smd(games[g].values, sub.kept.values)) for g in games)
        after = max(abs(smd(games_st[g].values, st.kept.values, st.stratum.values)) for g in games_st)
        print(f"  {'game (max |SMD|)':16s} {before:11.3f} {after:10.3f}")
        for y in ["any_vote", "log_votes"]:
            lo, hi = strat_bootstrap(st, y)
            print(f"  effect on {y:9s} = {strat_effect(st, y):+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    print("\nBalance rule of thumb: |SMD| < 0.1 good, < 0.25 acceptable.")


if __name__ == "__main__":
    main()
