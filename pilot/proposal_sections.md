# Proposal text: Study Design, Preliminary Analysis, and Response to Feedback

## Proposed Study Design

Our study asks how the characteristics of a Steam review shape whether readers find it helpful. We address two research questions:

- **RQ1:** Which characteristics of a review's *content*, *reviewer*, and *context* are associated with receiving helpful votes?
- **RQ2:** Does *behavioral consistency* affect perceived helpfulness, and does the effect differ for positive and negative reviews? Behavioral consistency is whether the reviewer's later playtime confirms or contradicts their verdict.
  - **H1:** Negative reviews from reviewers who kept playing receive fewer helpful votes.
  - **H2:** Positive reviews from reviewers who kept playing receive more helpful votes.

RQ1 maps the broad landscape of helpfulness cues. RQ2 isolates the one cue that is uniquely hard to fake, platform-recorded playtime, and tests it with a quasi-experimental design.

### Data Collection

**Source.** We use Steam's public review endpoint (`store.steampowered.com/appreviews/<appid>?json=1`). For each review it returns:
- the review text and verdict;
- helpful and funny vote counts;
- creation and edit timestamps;
- purchase flags (Steam purchase, received for free, refunded, early access); and
- the reviewer's playtime at the time of review, total playtime, and number of reviews.

**Sampling.** We will sample 200–300 paid games, stratified by genre and popularity tier. Genre comes from Steam's `appdetails` endpoint, and popularity from total review counts. The pilot used only well-rated games, so two contextual characteristics could not be tested. We will therefore deliberately include:
- games with "Mixed" overall ratings, so that agreement with the overall rating varies; and
- games that left early access during the sampling window, so that early-access status varies within a game.

For each game, we collect English reviews written in a fixed 12-month window that ends at least 12 months before collection. This means every review has had comparable time to accumulate votes and for its author to keep playing.

Negative reviews made up only 5% of the pilot sample. We will therefore collect positive and negative reviews separately (`review_type=positive|negative`), with a per-game-month cap for each. The target is about 4,000–5,000 negative reviews in the analysis sample, which is what the pilot's standard errors require to detect an effect of the observed size. We will scale to the full game list in stages, starting with about 60 games, and re-estimate statistical power after each stage.

**Two snapshots.** We will collect the same reviews twice, about one month apart, and link them by review ID. The first snapshot defines each reviewer's playtime status. The second gives the number of helpful votes each review gained in between. This ordering puts the treatment (continued play) before the outcome (new votes).

**Comment threads.** We will collect the public comment threads of every sampled review that has comments. In the pilot this was 3.4% of reviews, and each thread took about 5 seconds to retrieve. These threads let us check whether readers explicitly reference a reviewer's playtime, for example "500 hours and you call it bad?"

**Ethics.** All data are public. Steam IDs will be hashed at collection, raw data will be stored only on group members' machines, and no review will be quoted in identifiable form.

### Measures

| Construct | Operationalization |
|---|---|
| **Perceived helpfulness (outcome)** | (a) Whether a review received any helpful vote. (b) log(1 + helpful votes). (c) For RQ2, new helpful votes between snapshots. |
| **Content characteristics** | Length; readability (Flesch reading ease); formatting (line breaks; BBCode headings and lists); specificity (numbers per 100 words, price or value mentions, number of game aspects named); sentiment intensity (VADER); joke markers (sentiment contradicting the verdict, masked profanity, ASCII art) |
| **Reviewer characteristics** | Hours played at review; number of reviews written; **behavioral consistency** (below) |
| **Context characteristics** | Verdict; agreement with the game's overall rating (e.g., a negative review of a "Very Positive" game); early-access status; received for free; non-Steam key; whether the review was edited. Review month enters as a fixed effect. |
| **Behavioral consistency (RQ2 treatment)** | *Kept playing:* total playtime ≥ 2× playtime at review **and** at least 10 hours more. *Stopped:* total playtime ≤ 1.1× playtime at review. Cutoffs of 1.5× and 3× are tested for robustness. |

The pilot led us to exclude three kinds of fields:
- **Steam's weighted helpfulness score**, because it sits at its default for the 84% of reviews with no votes.
- **The number of games owned**, because it is missing for 58% of reviewers whose profiles are private.
- **Funny votes, comment counts, and award reactions as controls**, because they are themselves reader responses. We use funny votes instead as a negative-control outcome.
- **Developer responses**, because only 2 of 24,395 pilot reviews had one.

### Data Analysis

**RQ1: Which characteristics matter.** We model each helpfulness outcome on all characteristics simultaneously.
- **Models.** A linear probability model for any vote, and OLS for log votes, with negative binomial models as a robustness check for counts.
- **Fixed effects.** Game × verdict and review-month fixed effects, so that reviews are compared only with other reviews of the same game and verdict, written at a similar time.
- **Rare features.** A binary feature enters a verdict group's model only if it occurs at least 30 times in that group.
- **Inference.** Standard errors clustered by game.
- **Comparisons.** We standardize predictors to compare effect sizes across characteristics, and interact each characteristic with verdict to test whether cues work differently for positive and negative reviews.
- **Multiple comparisons.** Because RQ1 tests many characteristics, we control the false discovery rate (Benjamini–Hochberg).

**RQ2: Behavioral consistency (quasi-experimental).** Following the stratified propensity score approach of Saha et al. (ICWSM 2019), we treat continued play as the treatment and stopping as the control, separately for positive and negative reviews.
1. **Propensity model.** A logistic regression estimates each review's probability of treatment from covariates fixed when the review was posted: hours at review (with a squared term), review length, review date, reviewer experience, and game.
2. **Stratification.** Reviews are divided into propensity strata. Strata lacking either treated or control reviews are trimmed.
3. **Balance.** We report standardized mean differences (SMD) before and after stratification, targeting |SMD| < 0.1. The pilot achieved this for all covariates in the positive-review group.
4. **Effect estimation.** We compute the treatment effect as the size-weighted average of within-stratum differences, with bootstrapped 95% confidence intervals.

**Robustness and validity checks for RQ2:**
- fixed-effects regressions with hours-at-review, length, and game strata interacted with verdict;
- alternative treatment cutoffs (1.5× and 3×) and a dose-response analysis across playtime-ratio bins;
- a permutation placebo test that shuffles treatment within strata;
- funny votes as a negative-control outcome, which should not respond to credibility;
- re-estimation excluding likely joke reviews, flagged by text cues and high funny-to-helpful vote ratios; and
- re-estimation excluding reviewer experience, since the API reports the reviewer's *current* review count rather than the count at review time.

**Supporting evidence.** In the comment threads, we will count comments that address the reviewer's playtime. This tests whether readers notice playtime at all, a precondition for H1 and H2.
- **Automatic coding.** A dictionary flags comments that mention playtime *and* address the reviewer (second person or a quoted hour count). Copy-pasted spam comments are removed first.
- **Validation.** In the pilot, about two-thirds of automatically flagged comments were true references to the reviewer's playtime. Two team members will therefore hand-code a random sample of 200 comments, report inter-rater agreement (Cohen's κ), and use the result to correct prevalence estimates.

### Interpreting and Presenting Findings

We will present:
- a coefficient plot comparing standardized effects of all RQ1 characteristics, split by verdict;
- a covariate balance plot (Love plot) for the propensity stratification;
- a four-group plot of helpfulness for kept-playing vs. stopped reviewers, by verdict, with confidence intervals; and
- a dose-response curve of helpfulness across playtime ratios.

Helpful votes are a behavioral proxy that mixes credibility with usefulness, agreement, and visibility. We therefore interpret effects as *perceived helpfulness*. We also note that Steam's helpfulness ranking gives some reviews more exposure, which game fixed effects and review-age restrictions reduce but cannot remove. Because the pilot shows the design can yield precise estimates, a well-powered null for H1 or H2 would itself be informative. It would suggest that readers do not use behavioral consistency as a credibility cue, even though Steam displays it.

## Preliminary Analysis

**Pilot data.** We collected 24,395 English Steam reviews for 20 paid games spanning genres and popularity tiers. All reviews were written between April and September 2025, so each had 12–18 months to accumulate votes. We also collected the comment threads under the 831 reviews (3.4%) that had any comments. Helpful votes are sparse: 83.8% of reviews received none.

### RQ1: Review characteristics

We regressed whether a review received any helpful vote on all characteristics, separately for 22,743 positive and 1,583 negative reviews. The models included game and month fixed effects, with Benjamini–Hochberg correction. The effects below are percentage-point changes per standard deviation, or for binary features, for having the feature.

**Length is the strongest cue.** It raises the chance of any vote by 4.6 points for positive reviews and 11.2 points for negative reviews (both q < .001).

**Cues differ by verdict.**
- *Negative reviews* are rewarded for *specificity*. Each SD of numeric detail adds 1.6 points (q = .003), and naming more game aspects raises vote counts (q = .003).
- *Positive reviews* are rewarded for *structure*. BBCode formatting adds 10.9 points (q = .003), although only 158 reviews used it.
- *Readability* had no detectable effect for either verdict (q > .69).

**Helpful votes partly reward entertainment.** Positive reviews whose sentiment contradicts their verdict gain 5.2 points (q = .006). Manual inspection shows these are mostly humorous or dramatized reviews (e.g., darkly comic anecdotes) rather than sarcasm, so this lexicon measure is only a rough proxy for tone. These reviews also receive five times as many "funny" votes (0.66 vs. 0.13).

**Edited negative reviews receive far fewer votes** (−27.7 points, q < .001). The reason remains to be investigated.

**Overall, characteristics explain little.** Beyond game and month, the features add only 2.3 points of R² for positive reviews (0.005 → 0.028) and 7.6 points for negative reviews (0.137 → 0.213). Exposure, not content, likely drives most variation in votes.

### RQ2: Behavioral consistency

We restricted the sample to reviews that were purchased on Steam, not received for free, not refunded, not written during early access, not edited, and written after at least one hour of play. Of these, 10,737 reviews were classified as *kept playing* (total playtime ≥ 2× playtime at review and at least 10 hours more) or *stopped* (≤ 1.1×). Of the 10,737, 538 were negative reviews.

**Raw comparisons are confounded.** Positive reviewers who kept playing had written their reviews much earlier than those who stopped (median 21 vs. 66 hours at review).

**Stratified propensity score analysis.** Stratifying on a propensity score estimated from at-review covariates (hours at review, length, date, reviewer experience, and game) balanced the groups. Hours at review went from SMD −0.72 to 0.03, and all covariates ended below |SMD| = 0.1 for positive reviews.
- **H2 (positive reviews).** We found a precise null: −0.001, 95% CI [−0.022, 0.019].
- **H1 (negative reviews).** The estimate pointed in the predicted direction but was too imprecise to interpret: −0.030, 95% CI [−0.131, 0.071].

**Robustness.** Fixed-effects regressions, alternative thresholds (1.5× and 3×), and a permutation placebo test agreed. A specification that controlled for length only linearly produced a spuriously significant H1 effect, which underscores the need for stratified comparisons.

### Do readers notice playtime?

**Collection.** We retrieved 818 of the 831 comment threads. After removing 214 copy-pasted spam comments, 1,127 comments remained.

**How often readers address the reviewer's playtime.** 3.6% of comments did so (5.1% of threads).
- These comments concentrate on **negative reviews**: 13% of negative-review threads, compared with 2% of positive-review threads.
- Typical comments challenge the verdict, for example by asking how a reviewer could log dozens of hours yet not recommend the game.
- They cite hours already played more often than *later* play. Threads under kept-playing and stopped negative reviews mention playtime at similar rates (12% vs. 15%; n = 25 vs. 95 threads).

**Implication.** Readers do use playtime to judge negative reviews, which supports the premise of H1. Whether they also track continued play needs the larger sample.

### Implications for the full study

1. **Oversample negative reviews.** They were 6.5% of the pilot. To detect an H1 effect of the observed size, we need roughly 4,000–5,000 negative reviews in the RQ2 sample, so we will collect them separately.
2. **Primary outcomes.** We will use any helpful vote as a primary outcome alongside log votes, since most reviews get none.
3. **Joke reviews.** We will flag joke reviews and report results with and without them, because helpful votes partly reward humor.
4. **Sample games so that context varies.** Every pilot game was positively rated, and only one was in early access. The full sample will include Mixed-rated games and games that left early access.
5. **Validate comment coding by hand**, because the dictionary is only moderately precise.
6. **Drop uninformative fields.** These are Steam's weighted helpfulness score, number of games owned (missing for 58% of reviewers), developer responses (2 cases), and readability unless it shows effects at scale.

## Addressing Instructor Feedback

The instructor suggested operationalizing the study in a causal-inference fashion, following quasi-experimental social media studies (Saha et al., ICWSM 2019; Yuan et al., CHI 2026). We adopt that approach as follows.

**Treatment and control.** Following Saha et al. (2019), we treat continued play after posting a review as the treatment and stopping as the control.

**Matching and balance.**
- We estimate effects within propensity score strata built only from covariates fixed at the moment of posting.
- Strata without overlap between the two groups are trimmed.
- We report covariate balance (standardized mean differences) before and after stratification. The pilot shows the approach is feasible: stratification reduces the largest imbalance from |SMD| = 0.72 to below 0.1.

**Time order.** To ensure the treatment precedes the outcome, the full study uses two data snapshots about one month apart.
- Treatment status is defined from playtime at the first snapshot.
- The outcome is the number of helpful votes a review gains *between* the snapshots.
- This separates the reviewer's behavior from the votes it may influence.

**Robustness.** We complement the stratified estimates with:
- fixed-effects regressions,
- alternative treatment thresholds, and
- a permutation placebo test.
