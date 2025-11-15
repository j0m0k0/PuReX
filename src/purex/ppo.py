"""Compact categorical PPO oracle with GAE for the factorized action model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical


@dataclass(frozen=True)
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coefficient: float = 0.5
    entropy_coefficient: float = 0.01
    epochs: int = 4
    minibatch_size: int = 128
    hidden_size: int = 128
    max_gradient_norm: float = 0.5

    def __post_init__(self) -> None:
        if self.learning_rate <= 0 or self.minibatch_size < 1 or self.epochs < 1:
            raise ValueError("learning rate, minibatch size, and epochs must be positive")
        if not 0 <= self.gamma <= 1 or not 0 <= self.gae_lambda <= 1:
            raise ValueError("gamma and gae_lambda must be in [0, 1]")
        if not 0 < self.clip_epsilon < 1 or self.hidden_size < 1 or self.max_gradient_norm <= 0:
            raise ValueError("clip epsilon, hidden size, or gradient norm is invalid")
        if self.value_coefficient < 0 or self.entropy_coefficient < 0:
            raise ValueError("loss coefficients cannot be negative")


class ActorCritic(nn.Module):
    def __init__(self, observation_size: int, action_count: int, hidden_size: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(observation_size, hidden_size), nn.Tanh(),
            nn.Linear(hidden_size, hidden_size), nn.Tanh(),
        )
        self.policy_head = nn.Linear(hidden_size, action_count)
        self.value_head = nn.Linear(hidden_size, 1)

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.encoder(observations)
        return self.policy_head(features), self.value_head(features).squeeze(-1)


class PPOPolicy:
    """PPO policy that also exposes log-probability and value for rollout collection."""

    def __init__(self, observation_size: int, seed: int, config: PPOConfig | None = None,
                 device: str = "cpu"):
        self.config = config or PPOConfig()
        self.device = torch.device(device)
        torch.manual_seed(seed)
        self.model = ActorCritic(observation_size, 4, self.config.hidden_size).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config.learning_rate)
        self.rng = np.random.default_rng(seed)

    @torch.no_grad()
    def sample(
        self, observation: np.ndarray, legal_actions: np.ndarray
    ) -> tuple[int, float, float]:
        obs = torch.as_tensor(observation, dtype=torch.float32, device=self.device).unsqueeze(0)
        logits, value = self.model(obs)
        mask = torch.as_tensor(legal_actions, dtype=torch.bool, device=self.device).unsqueeze(0)
        logits = logits.masked_fill(~mask, torch.finfo(logits.dtype).min)
        distribution = Categorical(logits=logits)
        action = distribution.sample()
        return int(action.item()), float(distribution.log_prob(action).item()), float(value.item())

    def __call__(self, observation: np.ndarray, legal_actions: np.ndarray) -> int:
        return self.sample(observation, legal_actions)[0]

    def update(
        self,
        observations: np.ndarray,
        actions: np.ndarray,
        old_log_probs: np.ndarray,
        legal_masks: np.ndarray,
        returns: np.ndarray,
        advantages: np.ndarray,
    ) -> dict[str, float]:
        """Perform clipped PPO epochs using behavior-policy masks captured in the rollout."""
        cfg = self.config
        obs = torch.as_tensor(observations, dtype=torch.float32, device=self.device)
        act = torch.as_tensor(actions, dtype=torch.int64, device=self.device)
        old_lp = torch.as_tensor(old_log_probs, dtype=torch.float32, device=self.device)
        masks = torch.as_tensor(legal_masks, dtype=torch.bool, device=self.device)
        ret = torch.as_tensor(returns, dtype=torch.float32, device=self.device)
        adv = torch.as_tensor(advantages, dtype=torch.float32, device=self.device)
        if len(obs) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
        if len(adv) > 1:
            adv = (adv - adv.mean()) / (adv.std(unbiased=False) + 1e-8)
        losses: list[tuple[float, float, float]] = []
        for _ in range(cfg.epochs):
            order = self.rng.permutation(len(obs))
            for start in range(0, len(obs), cfg.minibatch_size):
                ix = torch.as_tensor(order[start:start + cfg.minibatch_size], device=self.device)
                logits, values = self.model(obs[ix])
                logits = logits.masked_fill(~masks[ix], torch.finfo(logits.dtype).min)
                dist = Categorical(logits=logits)
                new_lp = dist.log_prob(act[ix])
                ratio = torch.exp(new_lp - old_lp[ix])
                unclipped = ratio * adv[ix]
                clipped = torch.clamp(ratio, 1 - cfg.clip_epsilon,
                                      1 + cfg.clip_epsilon) * adv[ix]
                policy_loss = -torch.minimum(unclipped, clipped).mean()
                value_loss = 0.5 * (values - ret[ix]).square().mean()
                entropy = dist.entropy().mean()
                loss = (policy_loss + cfg.value_coefficient * value_loss
                        - cfg.entropy_coefficient * entropy)
                self.optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_gradient_norm)
                self.optimizer.step()
                losses.append((
                    float(policy_loss.item()), float(value_loss.item()), float(entropy.item())
                ))
        mean = np.mean(losses, axis=0)
        return {"policy_loss": float(mean[0]), "value_loss": float(mean[1]),
                "entropy": float(mean[2])}


@dataclass
class Rollout:
    observations: list[np.ndarray]
    actions: list[int]
    log_probs: list[float]
    values: list[float]
    rewards: list[float]
    dones: list[bool]
    masks: list[np.ndarray]

    @classmethod
    def empty(cls) -> "Rollout":
        return cls([], [], [], [], [], [], [])

    def add(self, observation: np.ndarray, action: int, log_prob: float, value: float,
            reward: float, done: bool, legal_mask: np.ndarray) -> None:
        self.observations.append(observation.copy())
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.rewards.append(reward)
        self.dones.append(done)
        self.masks.append(legal_mask.copy())

    def arrays(self, config: PPOConfig) -> tuple[np.ndarray, ...]:
        rewards = np.asarray(self.rewards, dtype=np.float32)
        values = np.asarray(self.values + [0.0], dtype=np.float32)
        dones = np.asarray(self.dones, dtype=np.float32)
        advantages = np.zeros_like(rewards)
        gae = 0.0
        for t in reversed(range(len(rewards))):
            delta = rewards[t] + config.gamma * values[t + 1] * (1 - dones[t]) - values[t]
            gae = delta + config.gamma * config.gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae
        returns = advantages + values[:-1]
        return (np.asarray(self.observations, dtype=np.float32),
                np.asarray(self.actions, dtype=np.int64),
                np.asarray(self.log_probs, dtype=np.float32),
                np.asarray(self.masks, dtype=bool), returns, advantages)
