# Proposal text: Preliminary Analysis and Response to Feedback

## Preliminary Analysis

**Data and design.** We collected 24,395 English Steam reviews for 20 paid games spanning genres and popularity tiers. All reviews were written between April and September 2025, so each had 12–18 months to accumulate votes. We restricted the sample to reviews that:
- were purchased on Steam,
- were not received for free,
- were not refunded,
- were not written during early access,
- were not edited after posting, and
- were written after at least one hour of play.

This left 17,974 reviews. We classified reviewers as having *kept playing* if their total playtime was at least twice their playtime at review and at least 10 hours higher. We classified them as having *stopped* if their total playtime was at most 1.1 times their playtime at review. The 10,737 reviews in these two groups form the analysis sample: 10,199 positive and 538 negative.

**Descriptive patterns.** Helpful votes are sparse: 83.8% of reviews received none. Raw comparisons are heavily confounded. Positive reviewers who kept playing had written their reviews much earlier than those who stopped (median 21 vs. 66 hours at review). Negative reviews from kept-playing reviewers were shorter (median 62 vs. 100 characters).

**Stratified propensity score analysis.** We used a logistic model to estimate each review's propensity to belong to the kept-playing group. Its predictors were measured at review time: hours at review, review length, review date, author review count, and game. Reviews were then stratified on this score.
- **Balance.** Stratification balanced the groups. For positive reviews, the standardized mean difference in hours at review fell from −0.72 to 0.03, and all covariates ended within |SMD| < 0.1.
- **Positive reviews (H2).** We found a precise null on the probability of receiving any helpful vote: −0.001, 95% CI [−0.022, 0.019].
- **Negative reviews (H1).** The estimate was in the predicted direction but too imprecise to interpret: −0.030, 95% CI [−0.131, 0.071].

The following checks were consistent with these results:
- fixed-effects regressions,
- alternative kept-playing thresholds (1.5× and 3×), and
- a permutation placebo test.

A specification that controlled for review length only linearly produced a spuriously significant negative-review effect. This underscores the need for stratified comparisons.

**Implications for the full study.** The pilot shaped four design decisions:
1. **Negative-review sample size.** Negative reviews are only 5% of the pilot sample, so the full study will collect them separately (`review_type=negative`). The target is roughly 4,000–5,000 negative reviews, the number needed to detect an effect of the observed size.
2. **Outcomes.** We will use whether a review received any helpful vote as a primary outcome alongside log vote counts.
3. **Joke reviews.** We will flag joke reviews. Negative reviews from kept-playing reviewers attracted more "funny" votes (+0.10, p = 0.067), which suggests some are sarcastic rather than sincere.
4. **Dropped variables.** We will not use Steam's weighted helpfulness score, which is uninformative for low-vote reviews, or the number of games owned, which is missing for 58% of reviewers because of private profiles.

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
