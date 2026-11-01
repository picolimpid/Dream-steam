# Was This Review Helpful? How Review Characteristics Shape Perceived Helpfulness on Steam

CS 568 (UIUC) group project — Eesha Mustafeez, Andy Mao, Arushi Agarwal, Kevin Lin.

Main question: does a reviewer's continued play after writing a review ("kept playing" vs "stopped")
change how many helpful votes the review gets, separately for positive and negative reviews?
We use a stratified propensity score design (Saha et al., ICWSM 2019) plus two vote snapshots.

## Repository layout

```
pilot/                  pilot study (20 games, 2025 reviews) — methods were tested here
  collect.py            review collection
  analyze.py            E0–E10 control experiments, propensity score stratification -> results.txt
  rq1.py                text features (readability, specificity, sentiment, formatting) -> rq1_results.txt
  tone_ps.py            propensity score for tone (humor-like mismatch, profanity) -> tone_results.txt
  comments.py           scrapes reader comment threads under sampled reviews
  comments_analysis.py  do readers mention the reviewer's playtime? -> comments_results.txt
  pilot_report.md       write-up of the pilot for the team
  proposal_sections.md  study design + preliminary analysis text for the proposal
study/
  collect.py            full-study collection (screen / plan / snapshot N / meta)
requirements.txt
```

`pilot/data/` and `study/data/` are **not in git** (see Data access below).

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Data access

The raw data contains Steam IDs, profile URLs and full review text, so it is never committed.
It is shared with the team only, as `steam_data_snapshot1.zip` on Google Drive (restricted access).
Download it into the project root and run:

```bash
unzip steam_data_snapshot1.zip      # creates study/data/ and pilot/data/
```

Please do not re-share the zip, upload it elsewhere, or quote reviews in a way that identifies the author.
In anything we publish, Steam IDs must be hashed.

## Data collection

### Source

Steam's official review API, `api.steampowered.com/IUserReviewsService/GetAppReviews/v1/` (no key needed),
with `filter=1` (newest first), `purchase_type=1` (all), `languages[0]=english`, and a `date_range_start`
/ `date_range_end` window. `review_type` is 1 for positive and 2 for negative. The older
`store.steampowered.com/appreviews/<appid>?json=1` endpoint now redirects to the store homepage.
Candidate games come from SteamSpy (`top100in2weeks`, `top100forever`, `all` pages 0–1); genre and tags
come from SteamSpy `appdetails`.

### Full study (`study/`)

| Step | Command | Output (in `study/data/`) |
|---|---|---|
| 1. Screen games | `python study/collect.py screen` | `games_screened.csv` — 1,526 paid games with window review counts |
| 2. Pick games | `python study/collect.py plan` | prints the plan: 125 games drawn at random (seed 568) from the 489 with ≥40 positive and ≥40 negative reviews in the window |
| 3. Snapshot 1 | `python study/collect.py snapshot 1` | `snapshot1.jsonl`, `negatives_all_snapshot1.jsonl` |
| 4. Game metadata | `python study/collect.py meta` | `games_meta.csv` — genre, top 8 tags, price, owners |
| 5. Snapshot 2 (**~Nov 14, 2026**) | `python study/collect.py snapshot 2` | `snapshot2.jsonl`, `negatives_all_snapshot2.jsonl` |

Every step can be resumed: if it stops, run the same command again and it continues from where it stopped.

**Review window.** English reviews posted between 2026-08-01 and 2026-10-16 (UTC). At snapshot 1 these
reviews were 2–13 weeks old. That is recent enough that they still gain votes before snapshot 2, and old
enough that reviewers have had time to keep playing or stop. The window is split into five sub-windows
(w1–w5) of about two weeks each.

**Games.** Paid games only. We did not stratify by genre: genre is recorded in `games_meta.csv`, so genres
can be compared afterwards.

**Two files per snapshot.**

- `snapshot{N}.jsonl` is the **balanced sample**. For each game we take up to a cap of reviews per verdict,
  and the cap is chosen so the totals reach about 5,000 positive and about 5,000 negative reviews. Each
  game's cap is split evenly across the five sub-windows, so a game's sample is not only its newest reviews.
  Snapshot 1 has 5,594 positive and 5,272 negative reviews.
- `negatives_all_snapshot{N}.jsonl` holds **every negative review** in the window for the same 125 games,
  28,307 in snapshot 1 (98–100% of the API's count per game). We added it because negative reviewers who
  kept playing are rare, and the capped sample alone had only 188.

**Snapshot 2.** This step reruns the same queries and fetches each sub-window twice as deep, so reviews
that were deleted in the meantime do not push snapshot-1 reviews out of reach. Join the two snapshots on
`recommendationid`. The outcome is the number of **new** helpful votes between the snapshots; treatment and
covariates are measured at snapshot 1.

### Record fields

Each JSONL row is one review as the API returns it (`recommendationid`, `review`, `voted_up`, `votes_up`,
`votes_funny`, `comment_count`, `timestamp_created`, `timestamp_updated`, `steam_purchase`,
`received_for_free`, `refunded`, `written_during_early_access`, `primarily_steam_deck`; under `author`:
`steamid`, `num_reviews`, `playtime_at_review`, `playtime_forever`, `playtime_last_two_weeks`,
`last_played`). Playtime is in **minutes**. We add these fields:

| Field | Meaning |
|---|---|
| `appid`, `game` | game |
| `sample_verdict` | `positive` / `negative`, the verdict the review was sampled under |
| `window` | `w1`–`w5`, or `all` in the all-negatives file |
| `rank_in_window` | position in the newest-first list |
| `snapshot`, `fetched_at` | snapshot number and Unix time of the fetch |

### Analysis definitions

These filters are applied at analysis time, not during collection:

- Keep a review only if it is a Steam purchase, was not received for free, was not refunded, was not
  written during early access, was not edited (`timestamp_updated − timestamp_created` ≤ 1 day), and the
  author had ≥1 hour at review.
- **Kept playing**: `playtime_forever` ≥ 2× `playtime_at_review` and at least 10 more hours.
  **Stopped**: `playtime_forever` ≤ 1.1× `playtime_at_review`. Reviews in between are dropped.
- Snapshot 1 after the filters: negatives 1,968 kept / 12,843 stopped (all-negatives file);
  positives 650 kept / 2,138 stopped.
- Days since posting (at the snapshot) is a covariate. Recent reviews have had less time to keep playing,
  and the balanced sample is weighted toward recent reviews.
- Known quirks: 5 rows in the all-negatives file have `voted_up = true`, probably because the author changed
  the verdict during collection. Filter on `voted_up`. One capped negative was missing from the full file,
  probably deleted. `weighted_vote_score` is not used, and `num_games_owned` is unreliable because private
  profiles report 0.

### Pilot (`pilot/`)

- **Reviews.** 20 games, English reviews from April to September 2025, about 200 per game and month,
  24,395 reviews in total (`pilot/data/reviews_raw.jsonl`).
- **Comment threads.** 831 reader comment threads, scraped from the public review pages
  (`steamcommunity.com/profiles/<id>/recommended/<appid>/`). 818 were readable
  (`pilot/data/comments_raw.jsonl`).
- **Write-up.** Results are in `pilot/pilot_report.md` and in the `*_results.txt` files.

Collection is polite: 1 request per second, backoff on HTTP 429, and a User-Agent that identifies a course
project.
