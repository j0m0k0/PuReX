"""Typed configuration for the finite-horizon game and paper case studies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class GameConfig:
    name: str
    horizon: int
    expertise_counts: tuple[int, int, int]
    detection_probability: tuple[tuple[float, float, float], ...]
    resolution_steps: tuple[tuple[int, int, int], ...]
    detected_reward: tuple[float, float, float]
    missed_reward: tuple[float, float, float]
    benign_reward: tuple[float, float, float]
    idle_reward: float
    malicious_capacity_by_priority: tuple[int, int, int]
    benign_arrival_probability_by_priority: tuple[float, float, float]
    issue_catalog_size: int
    reported_state_space_size: int

    def __post_init__(self) -> None:
        if self.horizon < 1 or sum(self.expertise_counts) < 1:
            raise ValueError("horizon and maintainer count must be positive")
        invalid_detection = len(self.detection_probability) != 3 or any(
            len(row) != 3 for row in self.detection_probability
        )
        if invalid_detection:
            raise ValueError("detection_probability must be a 3x3 matrix")
        if len(self.resolution_steps) != 3 or any(len(row) != 3 for row in self.resolution_steps):
            raise ValueError("resolution_steps must be a 3x3 matrix")
        priority_fields = (
            "detected_reward", "missed_reward", "benign_reward",
            "malicious_capacity_by_priority", "benign_arrival_probability_by_priority",
        )
        for field_name in priority_fields:
            if len(getattr(self, field_name)) != 3:
                raise ValueError(f"{field_name} must contain three priority values")
        if not np.all((0.0 <= np.asarray(self.detection_probability)) &
                      (np.asarray(self.detection_probability) <= 1.0)):
            raise ValueError("detection probabilities must be in [0, 1]")
        if any(x < 1 for row in self.resolution_steps for x in row):
            raise ValueError("resolution times must be positive")
        if any(x < 0 for x in self.expertise_counts):
            raise ValueError("expertise counts cannot be negative")
        if any(x < 0 for x in self.malicious_capacity_by_priority):
            raise ValueError("malicious capacities cannot be negative")
        if any(not 0 <= x <= 1 for x in self.benign_arrival_probability_by_priority):
            raise ValueError("benign arrival probabilities must be in [0, 1]")
        if self.issue_catalog_size < 1:
            raise ValueError("issue_catalog_size must be positive")

    @property
    def maintainer_expertise(self) -> tuple[int, ...]:
        """Maintainers in greedy order; matrix rows map 0=junior through 2=senior.

        The paper's table increases detection probability and decreases resolution time by row,
        so senior maintainers map to row 2, intermediate to row 1, and junior to row 0.
        """
        counts = self.expertise_counts  # Table order: senior, intermediate, junior.
        return tuple(level for level, count in ((2, counts[0]), (1, counts[1]), (0, counts[2]))
                     for _ in range(count))

    @property
    def max_backlog(self) -> int:
        """Stealth limit used in the paper, represented as a per-priority capacity vector."""
        return sum(self.malicious_capacity_by_priority)


def load_config(path: str | Path) -> GameConfig:
    """Read a JSON case-study configuration."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tuple_fields = {
        "expertise_counts", "detected_reward", "missed_reward", "benign_reward",
        "malicious_capacity_by_priority", "benign_arrival_probability_by_priority",
    }
    matrix_fields = {"detection_probability", "resolution_steps"}
    for key in tuple_fields:
        raw[key] = tuple(raw[key])
    for key in matrix_fields:
        raw[key] = tuple(tuple(row) for row in raw[key])
    return GameConfig(**raw)
