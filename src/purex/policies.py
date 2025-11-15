"""Paper baselines and small policy helpers."""

from __future__ import annotations

import numpy as np


class RandomPolicy:
    """Uniformly sample from actions marked legal by the environment."""

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int:
        del observation
        return int(self.rng.choice(np.flatnonzero(legal_actions)))


class GreedyDefender:
    """Review the highest-severity available priority with each available maintainer."""

    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int:
        del observation
        for priority in (0, 1, 2):
            if legal_actions[priority]:
                return priority
        return 3


class GreedyAttacker:
    """Fill the permitted batch, preferring priorities with lower detection probability."""

    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int:
        del observation
        for priority in (2, 1, 0):
            if legal_actions[priority]:
                return priority
        return 3

