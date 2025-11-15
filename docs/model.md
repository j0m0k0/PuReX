# Game model and implementation assumptions

This document separates the published formulation from details that the paper leaves open. The source is J. Mokhtari Koushyar, M. Guirguis, and G. K. Atia, “PuRe Defender: A Game-Theoretic Pull Request Assignment with Deep RL,” *Game Theory and AI for Security*, 2025, pp. 193–212, [doi:10.1007/978-3-032-08064-6_10](https://doi.org/10.1007/978-3-032-08064-6_10).

## Published formulation implemented here

- Two-player finite-horizon extensive-form game, with the defender acting before the attacker in each cycle.
- Defender state includes maintainer loads and an unresolved PR backlog. The defender sees issue identity and priority, but not PR type. The attacker sees the full state and PR types.
- Maintainers have three expertise levels. PRs have urgent, normal, or low priority and benign or malicious type.
- Defender assignments are one-to-one between available maintainers and PRs. Attacker submissions obey a stealth limit based on the backlog and a per-priority capacity vector.
- Detection probability and resolution time depend on maintainer expertise and PR priority. Busy maintainers' loads decrease by one per cycle.
- A detected malicious PR gives the defender the positive detection reward; an undetected malicious PR gives the negative missed-detection reward. Benign assignments give the priority-specific benign reward. The attacker receives the opposite malicious-request utility and zero for benign requests. An idle defender receives the paper's negative idle reward.
- PPO uses clipped policy updates, value loss, entropy regularization, and generalized advantage estimation. PSRO evaluates the empirical meta-game, computes an alpha-rank mixture, trains both players' PPO response oracles, and adds them to their policy populations.
- Random and Greedy baselines are implemented for both players.

## Paper values

The checked-in JSON files preserve the case-study table: horizon 100; detection matrix `[[.57,.35,.10],[.79,.50,.25],[.89,.55,.40]]`; resolution matrix `[[3,3,3],[2,2,2],[1,1,1]]`; detected rewards `[60,24,12]`; missed rewards `[-20,-12,-4]`; benign rewards `[2.6,1.2,0.4]`; idle reward `-5`; small environment maintainer counts `[1,0,2]` (senior, intermediate, junior) and per-priority attack capacities `[2,2,2]`; large environment counts `[2,3,3]` and capacities `[5,5,5]`. The table reports `|S|=432` and `|S|=746,494`; these are recorded as reported state-space cardinalities, not interpreted as issue counts.

**Expertise row mapping.** The text gives the expertise labels but does not explicitly map labels to matrix rows. Since detection probability increases and resolution time decreases across matrix rows, this implementation maps row 0 to junior, row 1 to intermediate, and row 2 to senior. This makes the Greedy baseline's senior-first processing consistent with the parameter matrices. Maintainer counts in the configuration remain in the paper table's senior/intermediate/junior order.

## Explicit assumptions

The paper does not fully specify the following, so defaults are implementation choices and are exposed in the configuration or training options:

1. **Action factorization.** PPO chooses one priority at a time (or skip/stop), processing maintainers in the configured stable order. At a chosen priority, the oldest request is selected. The attacker constructs its batch through repeated priority choices. The paper defines joint set-valued actions but does not publish a neural action encoding.
2. **Benign arrivals.** The paper specifies an exogenous distribution over benign batches but provides no probabilities. The case-study configurations use independent Bernoulli arrivals by priority with probabilities `[0.10, 0.25, 0.10]` per cycle. Change these values to study other arrival distributions.
3. **Issue catalog.** A finite catalog of 1,000 issue IDs is used to instantiate request tuples. The paper does not report an issue count. Request IDs are unique; issue IDs wrap at the configured catalog size.
4. **Attacker rewards.** The implementation uses the signed zero-sum counterpart of the defender's utility on malicious assignments, consistent with the paper's stated attacker goal and negative/positive missed-detection utilities.
5. **PPO defaults.** Unless overridden, the implementation uses learning rate `3e-4`, discount `0.99`, GAE lambda `0.95`, clip `0.2`, value coefficient `0.5`, entropy coefficient `0.01`, four epochs, minibatches of 128, a two-layer 128-unit MLP, and gradient-norm clipping at `0.5`. The paper reports the clip value but not the other values.
6. **PSRO details.** Alpha-rank uses selection intensity 10, population size 50, and a Moran fixation approximation; each payoff entry is estimated from the configured number of seeded episodes. The paper does not report the meta-solver parameters, rollout sizes, or the full PPO implementation settings.
7. **Evaluation metric.** Reported estimates use episode means and normal 95% confidence intervals. This is an implementation choice; the paper does not specify interval construction in its experiment description.

Because the source PR snapshots, extraction procedure output, benign-arrival distribution, action encoding, and complete optimizer settings are not available in the paper, the included case studies instantiate reported parameters but do not recreate the authors' exact training trajectory or guarantee the paper's table values.

