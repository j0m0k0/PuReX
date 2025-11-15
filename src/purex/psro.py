"""PPO-oracle PSRO loop with an alpha-rank empirical-game meta-solver."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from purex.config import GameConfig
from purex.env import Decision, DiscretePolicy, PullRequestGame
from purex.ppo import PPOConfig, PPOPolicy, Rollout


@dataclass(frozen=True)
class PSROConfig:
    iterations: int = 5
    episodes_per_oracle: int = 16
    episodes_per_payoff: int = 8
    alpha: float = 10.0
    population_size: int = 50
    stationary_iterations: int = 20_000
    seed: int = 0
    ppo: PPOConfig = PPOConfig()

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.episodes_per_oracle < 1 or self.episodes_per_payoff < 1:
            raise ValueError("PSRO iterations and episode counts must be positive")
        if self.alpha < 0 or self.population_size < 1 or self.stationary_iterations < 1:
            raise ValueError("alpha-rank parameters are invalid")


class _Recorder:
    def __init__(self, agent: PPOPolicy):
        self.agent = agent
        self.records: list[tuple[np.ndarray, int, float, float, np.ndarray]] = []

    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int:
        action, log_prob, value = self.agent.sample(observation, legal_actions)
        self.records.append((observation.copy(), action, log_prob, value, legal_actions.copy()))
        return action

    def take(
        self, decisions: tuple[Decision, ...]
    ) -> list[tuple[np.ndarray, int, float, float, float, bool, np.ndarray]]:
        if len(self.records) < len(decisions):
            raise RuntimeError("policy recorder and environment decisions are out of sync")
        records, self.records = self.records[:len(decisions)], self.records[len(decisions):]
        return [(obs, action, log_prob, value, decision.reward, False, mask)
                for (obs, action, log_prob, value, mask), decision in zip(records, decisions)]


def alpha_rank(
    payoff_defender: np.ndarray,
    payoff_attacker: np.ndarray,
    alpha: float = 10.0,
    population_size: int = 50,
    iterations: int = 20_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Approximate two-player alpha-rank marginals by a finite-population Markov chain.

    Rows and columns are pure policies. The stationary distribution over joint profiles is
    computed by power iteration; its player marginals are used as PSRO mixture weights.
    """
    if payoff_defender.shape != payoff_attacker.shape or payoff_defender.ndim != 2:
        raise ValueError("both payoff matrices must have the same two-dimensional shape")
    if min(payoff_defender.shape) < 1 or population_size < 1 or iterations < 1 or alpha < 0:
        raise ValueError("alpha-rank requires nonempty games and valid iteration parameters")
    if not np.all(np.isfinite(payoff_defender)) or not np.all(np.isfinite(payoff_attacker)):
        raise ValueError("payoff matrices must contain finite values")
    rows, cols = payoff_defender.shape
    profiles = rows * cols
    transition = np.zeros((profiles, profiles), dtype=np.float64)

    def fixation(delta: float) -> float:
        x = alpha * float(np.clip(delta, -50.0, 50.0))
        if abs(x) < 1e-9:
            return 1.0 / population_size
        # Moran-process fixation, evaluated in log space for numerical stability.
        if x > 0:
            return float((1.0 - np.exp(-x)) / (1.0 - np.exp(-population_size * x)))
        y = -x
        return float(np.exp((1 - population_size) * y) *
                     (1.0 - np.exp(-y)) / (1.0 - np.exp(-population_size * y)))

    for i in range(rows):
        for j in range(cols):
            source = i * cols + j
            outgoing = 0.0
            if rows > 1:
                for candidate in range(rows):
                    if candidate == i:
                        continue
                    target = candidate * cols + j
                    delta = payoff_defender[candidate, j] - payoff_defender[i, j]
                    probability = 0.5 * fixation(delta) / (rows - 1)
                    transition[source, target] += probability
                    outgoing += probability
            if cols > 1:
                for candidate in range(cols):
                    if candidate == j:
                        continue
                    target = i * cols + candidate
                    delta = payoff_attacker[i, candidate] - payoff_attacker[i, j]
                    probability = 0.5 * fixation(delta) / (cols - 1)
                    transition[source, target] += probability
                    outgoing += probability
            transition[source, source] = 1.0 - outgoing

    stationary = np.full(profiles, 1.0 / profiles, dtype=np.float64)
    for _ in range(iterations):
        updated = stationary @ transition
        if np.max(np.abs(updated - stationary)) < 1e-13:
            stationary = updated
            break
        stationary = updated
    joint = stationary.reshape(rows, cols)
    d = joint.sum(axis=1)
    a = joint.sum(axis=0)
    return d / d.sum(), a / a.sum()


def _roll_episode(config: GameConfig, seed: int, defender: DiscretePolicy,
                  attacker: DiscretePolicy) -> tuple[float, float, float, int, int]:
    env = PullRequestGame(config, seed)
    env.reset()
    d_total = a_total = 0.0
    backlog_sum = detected = assigned = 0
    while env.time < config.horizon:
        result = env.step(defender, attacker)
        d_total += result.defender_reward
        a_total += result.attacker_reward
        backlog_sum += result.backlog_size
        detected += result.detected_malicious
        assigned += result.assigned_malicious
    return d_total, a_total, backlog_sum / config.horizon, detected, assigned


def payoff_matrices(
    defender_population: list[DiscretePolicy],
    attacker_population: list[DiscretePolicy],
    config: GameConfig,
    episodes: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate each empirical-game payoff from independent seeded episode blocks."""
    if not defender_population or not attacker_population or episodes < 1:
        raise ValueError("payoff estimation requires nonempty populations and positive episodes")
    d_payoff = np.zeros((len(defender_population), len(attacker_population)), dtype=np.float64)
    a_payoff = np.zeros_like(d_payoff)
    for i, defender in enumerate(defender_population):
        for j, attacker in enumerate(attacker_population):
            outcomes = [_roll_episode(config, seed + 100_003 * i + 10_007 * j + ep,
                                      defender, attacker) for ep in range(episodes)]
            d_payoff[i, j] = np.mean([x[0] for x in outcomes])
            a_payoff[i, j] = np.mean([x[1] for x in outcomes])
    return d_payoff, a_payoff


def _train_oracle(agent: PPOPolicy, player: str, opponent_population: list[DiscretePolicy],
                  mixture: np.ndarray, config: GameConfig, train_config: PSROConfig,
                  seed_base: int) -> dict[str, float]:
    recorder = _Recorder(agent)
    rollout = Rollout.empty()
    episode_returns: list[float] = []
    rng = np.random.default_rng(seed_base)
    for episode in range(train_config.episodes_per_oracle):
        opponent = opponent_population[int(rng.choice(len(opponent_population), p=mixture))]
        env = PullRequestGame(config, seed_base + episode + 1)
        env.reset()
        episode_records: list[tuple[np.ndarray, int, float, float, float, bool, np.ndarray]] = []
        d_return = a_return = 0.0
        while env.time < config.horizon:
            if player == "defender":
                result = env.step(recorder, opponent)
                episode_records.extend(recorder.take(result.defender_decisions))
            else:
                result = env.step(opponent, recorder)
                episode_records.extend(recorder.take(result.attacker_decisions))
            d_return += result.defender_reward
            a_return += result.attacker_reward
        episode_returns.append(d_return if player == "defender" else a_return)
        # Attacker return is batched and arrives when submissions are resolved. We assign the
        # episode's strategic return evenly across attack decisions to preserve total return.
        if player == "attacker" and episode_records:
            share = a_return / len(episode_records)
            episode_records = [(o, a, lp, v, share, done, mask)
                               for o, a, lp, v, _r, done, mask in episode_records]
        for record in episode_records:
            rollout.add(*record)
        if rollout.dones:
            rollout.dones[-1] = True
    arrays = rollout.arrays(agent.config)
    losses = agent.update(*arrays)
    losses["mean_episode_return"] = float(np.mean(episode_returns)) if episode_returns else 0.0
    losses["decisions"] = float(len(rollout.actions))
    return losses


def train_psro(
    config: GameConfig, train_config: PSROConfig
) -> tuple[list[PPOPolicy], list[PPOPolicy], list[dict[str, object]]]:
    """Train both populations with PPO approximate best responses over alpha-rank mixtures."""
    observation_size = 11 + len(config.maintainer_expertise)
    defender_population = [PPOPolicy(observation_size, train_config.seed + 101, train_config.ppo)]
    attacker_population = [PPOPolicy(observation_size, train_config.seed + 202, train_config.ppo)]
    history: list[dict[str, object]] = []
    for iteration in range(train_config.iterations):
        defender_opponents = defender_population.copy()
        attacker_opponents = attacker_population.copy()
        d_matrix, a_matrix = payoff_matrices(
            defender_opponents, attacker_opponents, config,
            train_config.episodes_per_payoff,
            train_config.seed + iteration * 1_000_003,
        )
        d_mix, a_mix = alpha_rank(d_matrix, a_matrix, train_config.alpha,
                                  train_config.population_size, train_config.stationary_iterations)
        defender = PPOPolicy(observation_size, train_config.seed + 10_000 + iteration,
                             train_config.ppo)
        d_loss = _train_oracle(defender, "defender", attacker_opponents, a_mix, config,
                               train_config, train_config.seed + 20_000 + iteration * 101)
        attacker = PPOPolicy(observation_size, train_config.seed + 30_000 + iteration,
                             train_config.ppo)
        a_loss = _train_oracle(attacker, "attacker", defender_opponents, d_mix, config,
                               train_config, train_config.seed + 40_000 + iteration * 101)
        defender_population.append(defender)
        attacker_population.append(attacker)
        history.append({
            "iteration": iteration + 1,
            "defender_meta_strategy": d_mix.tolist(),
            "attacker_meta_strategy": a_mix.tolist(),
            "defender_payoffs": d_matrix.tolist(),
            "attacker_payoffs": a_matrix.tolist(),
            "defender_oracle": d_loss,
            "attacker_oracle": a_loss,
        })
    return defender_population, attacker_population, history
