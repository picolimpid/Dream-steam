# Pilot Study Report: Kept Playing vs. Helpful Votes on Steam

*CS 568 group project — preliminary analysis, Sept 30, 2026*

## TL;DR

- We ran a small pilot on **24,395 English reviews from 20 paid games** to test our design before scaling up.
- **Neither hypothesis is supported yet.**
  - For **positive reviews (H2)**, the effect of "kept playing" is a precise null (≈ 0, SE 0.009).
  - For **negative reviews (H1)**, the effect points the predicted way (−0.06 on log votes) but is not significant (p = 0.32), because we only had **538 negative reviews** in the analysis sample.
- The pilot's main value is methodological. It showed us five things to fix before full collection:
  1. **Oversample negative reviews.** We need about 8× more.
  2. **Matching on hours-at-review and review length is essential.** The raw group differences are heavily confounded.
  3. **84% of reviews get zero votes**, so "any vote" should be a primary outcome.
  4. **Some negative reviews from heavy players look like jokes**, which is a new threat to validity.
  5. **Drop two variables:** `num_games_owned` and `weighted_vote_score` are not usable.
- A first model specification gave a "significant" H1 result (p = 0.017). **It is an artifact of weak controls — please don't cite it.** See Section 5.

---

## 1. Research question (recap)

Do Steam readers trust reviews less when the reviewer's behavior contradicts their verdict?

- **H1:** Negative reviews from reviewers who *kept playing* get **fewer** helpful votes.
- **H2:** Positive reviews from reviewers who *kept playing* get **more** helpful votes.

## 2. Data

- **Source:** the public reviews endpoint `store.steampowered.com/appreviews/<appid>?json=1`. It needs no API key and returns more fields than the documented `IUserReviewsService/GetAppReviews`.
- **Games:** 20 paid titles across genres and popularity tiers.
  - Elden Ring, BG3, Cyberpunk 2077, RDR2, Terraria, Stardew Valley, Rust, Helldivers 2, Dead by Daylight, Valheim, RimWorld, Factorio, Hades, Hollow Knight, Slay the Spire, Balatro, RE4, Dave the Diver, Stray, Celeste.
- **Time window:** reviews written **Apr–Sep 2025**, so every review is 12–18 months old at collection.
  - We pulled up to 200 reviews per game per month using `filter=recent` with `start_date`/`end_date`.
- **Size:** 24,395 reviews collected. After filters, 17,974 remain; 10,737 of those fall into the kept or stopped groups.

## 3. Variable plan: from ~30 fields to ~10

The API returns about 30 fields per review. We cut them down as follows.

| Role | Variable | Definition / handling |
|---|---|---|
| **Outcome** | `votes_up` | Analyzed as *any vote* (0/1) and *log(1 + votes)* |
| **Treatment** | kept playing | `playtime_forever` ≥ 2× `playtime_at_review` **and** at least +10h. The **stopped** group is ≤ 1.1×. The middle group is dropped from the main analysis. |
| **Moderator** | `voted_up` | Positive and negative reviews are estimated separately |
| **Fixed by sampling** | language, review age, purchase status, edit status, minimum playtime | English only; written Apr–Sep 2025; Steam purchase; not free; not refunded; not early access; not edited later; ≥ 1h at review |
| **Held equal by fixed effects** | game, hours-at-review bin, review-length bin | Each of these gets its own intercept per verdict |
| **Linear controls** | review date, author's number of reviews | |

**Dropped fields and why:**

| Field(s) | Reason |
|---|---|
| `votes_funny`, `comment_count`, `reactions` | These are outcomes too. Controlling for them would bias the estimate ("bad controls"). `votes_funny` is reused as a negative-control outcome in E6. |
| `num_games_owned` | **58% are 0** because of private profiles, so it is unusable. |
| `weighted_vote_score` | Almost every review has 0 votes, so the score sits at the default 0.5 and carries no information. |
| game-level summary, `app_release_date` | Absorbed by game fixed effects. |
| steamid, name, avatar, hardware, Steam Deck fields | Irrelevant to the question, and ethically sensitive. |

## 4. Results

### E0. Descriptives
- **83.8% of reviews have zero helpful votes.** The maximum is 305.
- 6.6% of reviews were edited after posting.

### E1. Raw four-group comparison (no adjustment)

| Group | n | Mean votes | Share with ≥1 vote | Median hours at review | Median length (chars) |
|---|---|---|---|---|---|
| POS stopped | 4,561 | 0.67 | 16% | 66.5 | 46 |
| POS kept | 5,638 | 0.27 | 13% | 21.3 | 31 |
| NEG stopped | 383 | 2.02 | 62% | 32.2 | 100 |
| NEG kept | 155 | 1.59 | 51% | 36.0 | 62 |

**The groups are not comparable.**
- Kept-playing reviewers of positive reviews wrote their review much earlier: 21h vs. 66h at review.
- Kept-playing negative reviews are much shorter: 62 vs. 100 characters.

Raw gaps therefore mostly reflect these differences, not credibility.

### E2–E3. Matched comparison and main regression

The main model is OLS with fixed effects for game × verdict, hours-bin × verdict and length-bin × verdict, plus the linear controls. Standard errors are clustered by game.

| Outcome | Kept vs. stopped, **positive** | Kept vs. stopped, **negative** |
|---|---|---|
| Any vote (0/1) | +0.003 (p = 0.77) | −0.060 (p = 0.22) |
| log(1 + votes) | −0.005 (p = 0.55) | −0.057 (p = 0.32) |

- **Poisson model** (game FE + linear controls): positive IRR = 0.84 [0.43, 1.63]; negative IRR = 1.20 [0.69, 2.10]. The estimates are unstable because a handful of high-vote reviews drive them.
- **Coarsened exact matching** (game × verdict × hours bin × length bin × month) keeps only **90 negative reviews**. It gives a negative-review gap of −0.07 on log votes, which is too few reviews to be informative.

### E4. Dose-response by playtime ratio

- For **positive** reviews, the curve is flat across all ratio bins (<1.1× up to ≥5×).
- For **negative** reviews, it is noisy and not monotone. There is no clean trend yet.

### E5. Threshold robustness (negative-review effect on log votes)

| Kept-playing cutoff | Estimate | p |
|---|---|---|
| 1.5× | −0.055 | 0.26 |
| 2× | −0.057 | 0.32 |
| 3× | −0.085 | 0.23 |

The direction is consistent across cutoffs but never significant.

### E6. Alternative and negative-control outcomes
- **`weighted_vote_score`:** null in both groups. As expected, it carries no information for low-vote reviews.
- **Funny votes:** positive reviews show nothing. **Negative reviews from kept-playing players get more funny votes: +0.10, p = 0.067.** See threat #4 below.

### E7. Placebo test
We randomly shuffled the kept-playing label 1,000 times within game × verdict × hours-bin cells.
- The observed effects fall inside the placebo range: positive p = 0.54, negative p = 0.36.

### E8. Sensitivity to the sampling restrictions

| Specification | n | Positive | Negative |
|---|---|---|---|
| Main (all filters) | 10,737 | −0.005 | −0.057 |
| Drop purchase / early-access filter | 13,405 | +0.002 | −0.040 |
| Keep edited reviews | 11,506 | −0.007 | **+0.010** |
| Minimum 0h at review | 10,843 | −0.003 | −0.058 |
| Minimum 5h at review | 9,802 | −0.004 | −0.079 |

Including edited reviews wipes out the negative-review effect. Reviewers who kept playing may have gone back and revised their review, so **we should keep excluding edited reviews.**

### E9. Per-game heterogeneity
For negative reviews, 6 of the 9 games with enough data show a negative raw gap. The largest are Cyberpunk, Elden Ring, Dead by Daylight and RDR2. Each game has only 10–98 negative reviews, so these per-game gaps are very noisy.

## 5. A caution on model specification

Our first specification controlled for hours-at-review and review length **linearly**. It produced:

> negative-review effect = −0.122, p = 0.017

That looked like support for H1. The placebo test showed that the placebo distribution was **not centered on zero**, which means the specification itself was generating a negative estimate.

The cause is that kept-playing negative reviews are much shorter, and a linear length control does not absorb that difference. With bin-level fixed effects, the estimate halves to −0.057 and loses significance.

**Takeaway: use bin-level fixed effects or matching, and always run the placebo check.**

## 6. Threats surfaced by the pilot

1. **Too few negative reviews.** Popular paid games are overwhelmingly positive. The current SE on the negative-review effect is about 0.058. Detecting an effect of about −0.06 needs an SE of about 0.02, which means **~4,000–5,000 negative reviews** in the kept/stopped sample.
2. **Visibility dominates votes.** Most recent reviews are never seen, so zero votes often means "unseen", not "distrusted". Using any-vote as an outcome helps. We may also want a second sample drawn from the "most helpful" ranking.
3. **Group composition differs a lot.** Kept-playing reviewers tend to write their review early and write short reviews. This design only works with within-cell comparisons.
4. **Joke reviews.** Some "Not Recommended" reviews from heavy players are sarcastic (for example, "0/10, only 800 hours"). Readers don't read these as real verdicts, and they attract funny votes instead. We need to flag them, either with text rules or by using the funny/helpful vote ratio.
5. **Edited reviews** may have been revised *after* the extra playtime. Excluding them is the right default.

## 7. Recommended changes for the full study

1. **Collect negative reviews separately** using `review_type=negative`, so the sample has roughly as many negative reviews as positive ones.
2. **Scale to about 60 games first**, then decide whether 200–300 is needed based on the new standard errors.
3. **Main model:** OLS/LPM with game × verdict, hours-bin × verdict and length-bin × verdict fixed effects, clustered by game.
   - **Primary outcomes:** any vote and log votes.
   - **Secondary:** Poisson/negative binomial models for vote counts.
4. **Always report** the placebo (permutation) test and the threshold robustness checks alongside the main estimate.
5. **Add a joke-review filter** and report results with and without it.
6. **Drop `weighted_vote_score` and `num_games_owned`** from the design.
7. **Keep the two-snapshot plan.** Votes are cumulative, so new votes between snapshots are the cleanest test of whether *current* playtime matters.

## 8. Reproducing the pilot

```bash
python3 -m venv .venv && .venv/bin/pip install pandas numpy scipy statsmodels
.venv/bin/python pilot/collect.py    # ~15 min; resumes automatically if rate-limited (HTTP 429)
.venv/bin/python pilot/analyze.py    # runs E0–E9; full output in pilot/results.txt
```

Raw data is saved to `pilot/data/reviews_raw.jsonl`. It contains Steam IDs, so **do not commit or share it publicly.**
