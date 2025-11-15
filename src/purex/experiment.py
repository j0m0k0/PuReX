"""Reproducible evaluation summaries for fixed policy pairs."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from purex.config import GameConfig
from purex.env import DiscretePolicy, PullRequestGame


def evaluate_pair(config: GameConfig, defender: DiscretePolicy, attacker: DiscretePolicy,
                  episodes: int, seed: int = 0) -> dict[str, float | int]:
    """Evaluate policies on independent seeded episodes; report means and 95% normal CIs."""
    if episodes < 1:
        raise ValueError("episodes must be positive")
    outcomes: list[tuple[float, float, float, float, float, float]] = []
    for episode in range(episodes):
        env = PullRequestGame(config, seed + episode)
        d_reward = a_reward = backlog_total = detected = assigned = injected = 0.0
        while env.time < config.horizon:
            result = env.step(defender, attacker)
            d_reward += result.defender_reward
            a_reward += result.attacker_reward
            backlog_total += result.backlog_size
            detected += result.detected_malicious
            assigned += result.assigned_malicious
            injected += sum(decision.action < 3 for decision in result.attacker_decisions)
        outcomes.append((d_reward, a_reward, backlog_total / config.horizon,
                         detected, assigned, injected))

    matrix = np.asarray(outcomes, dtype=np.float64)
    mean = matrix.mean(axis=0)
    se = matrix.std(axis=0, ddof=1) / np.sqrt(episodes) if episodes > 1 else np.zeros(5)
    detection_rate = 100.0 * mean[3] / mean[4] if mean[4] else 0.0
    return {
        "environment": config.name,
        "episodes": episodes,
        "seed": seed,
        "defender_reward_mean": float(mean[0]),
        "defender_reward_ci95": float(1.96 * se[0]),
        "attacker_reward_mean": float(mean[1]),
        "attacker_reward_ci95": float(1.96 * se[1]),
        "mean_backlog": float(mean[2]),
        "mean_backlog_ci95": float(1.96 * se[2]),
        "malicious_assignments_per_episode": float(mean[4]),
        "malicious_detection_percent": float(detection_rate),
        "malicious_injections_per_episode": float(mean[5]),
        "raw_episode_metrics": matrix.tolist(),
    }


def evaluate_population(
    config: GameConfig,
    defenders: Sequence[DiscretePolicy],
    attackers: Sequence[DiscretePolicy],
    defender_mix: np.ndarray,
    attacker_mix: np.ndarray,
    episodes: int,
    seed: int = 0,
) -> list[dict[str, object]]:
    """Evaluate the two PSRO mixtures against each other using deterministic mixture sampling."""
    if len(defenders) != len(defender_mix) or len(attackers) != len(attacker_mix):
        raise ValueError("mixture dimensions must match policy populations")
    rng = np.random.default_rng(seed)
    rows = []
    for episode in range(episodes):
        d = defenders[int(rng.choice(len(defenders), p=defender_mix))]
        a = attackers[int(rng.choice(len(attackers), p=attacker_mix))]
        result = evaluate_pair(config, d, a, 1, seed + 1009 * episode)
        result.pop("raw_episode_metrics", None)
        rows.append(result)
    return rows
