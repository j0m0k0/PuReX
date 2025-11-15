"""Finite-horizon extensive-form game from the PuRe Defender formulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from purex.config import GameConfig

PRIORITIES = ("urgent", "normal", "low")


@dataclass(frozen=True)
class PullRequest:
    """A request is identified by its issue and priority; only the attacker sees its type."""

    request_id: int
    issue_id: int
    priority: int
    malicious: bool


@dataclass(frozen=True)
class Decision:
    observation: np.ndarray
    action: int
    reward: float
    legal_actions: np.ndarray


@dataclass(frozen=True)
class StepResult:
    defender_reward: float
    attacker_reward: float
    defender_decisions: tuple[Decision, ...]
    attacker_decisions: tuple[Decision, ...]
    backlog_size: int
    detected_malicious: int
    assigned_malicious: int


class DiscretePolicy(Protocol):
    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int: ...


class PullRequestGame:
    """A seeded simulator. Actions are autoregressive priority choices within each player turn.

    The paper defines joint subset-assignment and batch-submission actions. This implementation
    factorizes each joint action into repeated categorical choices over the three priority classes
    plus STOP/SKIP. Requests of the chosen class use FIFO order; issue identity is observational
    context, not a choice. This is an explicit approximation for tractable PPO policies.
    """

    def __init__(self, config: GameConfig, seed: int = 0):
        self.config = config
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.reset()

    @property
    def observation_size(self) -> int:
        return 11 + len(self.config.maintainer_expertise)

    def reset(self) -> None:
        self.time = 0
        self.loads = np.zeros(len(self.config.maintainer_expertise), dtype=np.int32)
        self.backlog: list[PullRequest] = []
        self.next_request_id = 0
        self.next_issue_id = 0
        self.detected_malicious = 0
        self.assigned_malicious = 0

    def observe(self, player: str, expertise: int | None = None, slot: int = 0) -> np.ndarray:
        """Encode public state for the defender and full typed state for the attacker."""
        if player not in {"defender", "attacker"}:
            raise ValueError("player must be 'defender' or 'attacker'")
        max_w = max(max(row) for row in self.config.resolution_steps)
        loads = self.loads.astype(np.float32) / max_w
        typed = np.zeros((2, 3), dtype=np.float32)
        for pr in self.backlog:
            if player == "attacker":
                typed[int(pr.malicious), pr.priority] += 1
            else:
                typed[0, pr.priority] += 1
        typed /= max(1, self.config.max_backlog)
        level = np.zeros(3, dtype=np.float32)
        if expertise is not None:
            level[expertise] = 1.0
        features = np.concatenate((
            np.asarray([self.time / self.config.horizon], dtype=np.float32),
            loads,
            typed.reshape(-1),
            level,
            np.asarray([slot / max(1, self.config.max_backlog)], dtype=np.float32),
        ))
        return features

    @staticmethod
    def _choose(policy: DiscretePolicy, observation: np.ndarray, legal: np.ndarray) -> int:
        action = int(policy(observation, legal))
        if action < 0 or action >= len(legal) or not bool(legal[action]):
            raise ValueError(
                f"policy selected illegal action {action}; legal mask={legal.tolist()}"
            )
        return action

    def _oldest_of_priority(self, priority: int) -> int | None:
        for index, request in enumerate(self.backlog):
            if request.priority == priority:
                return index
        return None

    def step(self, defender: DiscretePolicy, attacker: DiscretePolicy) -> StepResult:
        """Advance one defender-attacker cycle, then add exogenous benign arrivals."""
        if self.time >= self.config.horizon:
            raise RuntimeError("episode has ended; call reset() before stepping again")
        defender_decisions: list[Decision] = []
        attacker_decisions: list[Decision] = []
        d_reward = 0.0
        a_reward = 0.0
        had_assignment = False
        n_detected = 0
        n_assigned_malicious = 0
        assigned_maintainers: set[int] = set()

        # Defender acts first. Available maintainers act in stable senior-to-junior order.
        for maintainer, expertise in enumerate(self.config.maintainer_expertise):
            if self.loads[maintainer] != 0:
                continue
            legal = np.zeros(4, dtype=bool)
            legal[3] = True  # skip this maintainer
            for priority in range(3):
                legal[priority] = self._oldest_of_priority(priority) is not None
            observation = self.observe("defender", expertise, maintainer)
            action = self._choose(defender, observation, legal)
            decision_reward = 0.0
            if action < 3:
                index = self._oldest_of_priority(action)
                if index is None:
                    raise RuntimeError("legal-action mask referenced an empty priority class")
                request = self.backlog.pop(index)
                had_assignment = True
                if request.malicious:
                    n_assigned_malicious += 1
                    self.assigned_malicious += 1
                    caught = self.rng.random() < self.config.detection_probability[
                        expertise
                    ][action]
                    if caught:
                        n_detected += 1
                        self.detected_malicious += 1
                        decision_reward = self.config.detected_reward[action]
                    else:
                        decision_reward = self.config.missed_reward[action]
                    # The attacker receives the opposite malicious-request utility.
                    a_reward -= decision_reward
                else:
                    decision_reward = self.config.benign_reward[action]
                self.loads[maintainer] = self.config.resolution_steps[expertise][action]
                assigned_maintainers.add(maintainer)
                d_reward += decision_reward
            defender_decisions.append(Decision(observation, action, decision_reward, legal.copy()))

        if not had_assignment:
            d_reward += self.config.idle_reward
            if defender_decisions:
                last = defender_decisions[-1]
                defender_decisions[-1] = Decision(last.observation, last.action,
                                                  last.reward + self.config.idle_reward,
                                                  last.legal_actions)

        # The attacker observes the updated typed state, including the defender's assignments.
        room = max(0, self.config.max_backlog - len(self.backlog))
        per_priority_count = [sum(pr.priority == priority for pr in self.backlog)
                              for priority in range(3)]
        for _ in range(min(room, sum(self.config.malicious_capacity_by_priority))):
            legal = np.zeros(4, dtype=bool)
            legal[3] = True  # stop the batch
            for priority in range(3):
                legal[priority] = (
                    per_priority_count[priority]
                    < self.config.malicious_capacity_by_priority[priority]
                )
            observation = self.observe("attacker", slot=len(attacker_decisions))
            action = self._choose(attacker, observation, legal)
            if action == 3:
                attacker_decisions.append(Decision(observation, action, 0.0, legal.copy()))
                break
            per_priority_count[action] += 1
            pr = PullRequest(
                request_id=self.next_request_id,
                issue_id=self.next_issue_id % self.config.issue_catalog_size,
                priority=action,
                malicious=True,
            )
            self.next_request_id += 1
            self.next_issue_id += 1
            self.backlog.append(pr)
            attacker_decisions.append(Decision(observation, action, 0.0, legal.copy()))

        # Exogenous benign arrivals; the paper does not report their distribution.
        for priority, probability in enumerate(self.config.benign_arrival_probability_by_priority):
            if self.rng.random() < probability:
                self.backlog.append(PullRequest(
                    request_id=self.next_request_id,
                    issue_id=self.next_issue_id % self.config.issue_catalog_size,
                    priority=priority,
                    malicious=False,
                ))
                self.next_request_id += 1
                self.next_issue_id += 1

        # Sparse batch-level attacker return is shared over its decisions for PPO credit assignment.
        attacker_decisions = [Decision(x.observation, x.action, a_reward, x.legal_actions)
                              for x in attacker_decisions]
        # Match the transition equation: newly assigned loads are set to W; other loads decay.
        for maintainer in range(len(self.loads)):
            if maintainer not in assigned_maintainers:
                self.loads[maintainer] = max(0, int(self.loads[maintainer]) - 1)
        self.time += 1
        return StepResult(d_reward, a_reward, tuple(defender_decisions), tuple(attacker_decisions),
                          len(self.backlog), n_detected, n_assigned_malicious)
