"""Command-line entry points for paper case studies and PPO-PSRO training."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch

from purex.config import load_config
from purex.experiment import evaluate_pair
from purex.policies import GreedyAttacker, GreedyDefender, RandomPolicy
from purex.ppo import PPOConfig, PPOPolicy
from purex.psro import PSROConfig, alpha_rank, payoff_matrices, train_psro


def _read_json(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _save_policy(path: Path, policy: PPOPolicy) -> None:
    torch.save(
        {
            "model": policy.model.state_dict(),
            "observation_size": policy.model.encoder[0].in_features,
            "config": asdict(policy.config),
        },
        path,
    )


def _load_policy(path: str | Path, seed: int) -> PPOPolicy:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    policy = PPOPolicy(checkpoint["observation_size"], seed,
                       PPOConfig(**checkpoint["config"]))
    policy.model.load_state_dict(checkpoint["model"])
    policy.model.eval()
    return policy


def train_command(args: argparse.Namespace) -> None:
    game = load_config(args.config)
    ppo_config = PPOConfig(**(_read_json(args.ppo_config) if args.ppo_config else {}))
    train_config = PSROConfig(
        iterations=args.iterations,
        episodes_per_oracle=args.oracle_episodes,
        episodes_per_payoff=args.payoff_episodes,
        alpha=args.alpha,
        population_size=args.population_size,
        seed=args.seed,
        ppo=ppo_config,
    )
    defenders, attackers, history = train_psro(game, train_config)
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    for i, policy in enumerate(defenders):
        _save_policy(destination / f"defender-{i:02d}.pt", policy)
    for i, policy in enumerate(attackers):
        _save_policy(destination / f"attacker-{i:02d}.pt", policy)
    # Meta-strategy is recomputed on the full final meta-game after oracle insertion.
    d_payoff, a_payoff = payoff_matrices(defenders, attackers, game,
                                         max(1, args.payoff_episodes), args.seed + 70_001)
    d_mix, a_mix = alpha_rank(d_payoff, a_payoff, args.alpha, args.population_size)
    _write_json(destination / "run.json", {
        "environment": asdict(game), "psro": asdict(train_config), "seed": args.seed,
        "iterations": history,
        "final_defender_payoffs": d_payoff.tolist(),
        "final_attacker_payoffs": a_payoff.tolist(),
        "defender_meta_strategy": d_mix.tolist(),
        "attacker_meta_strategy": a_mix.tolist(),
    })
    print(
        f"Saved {len(defenders)} defender and {len(attackers)} attacker policies "
        f"to {destination}"
    )


def evaluate_command(args: argparse.Namespace) -> None:
    game = load_config(args.config)
    if args.defender:
        defender = _load_policy(args.defender, args.seed)
    elif args.defender_baseline == "greedy":
        defender = GreedyDefender()
    else:
        defender = RandomPolicy(args.seed + 1)
    if args.attacker:
        attacker = _load_policy(args.attacker, args.seed + 2)
    elif args.attacker_baseline == "greedy":
        attacker = GreedyAttacker()
    else:
        attacker = RandomPolicy(args.seed + 3)
    report = evaluate_pair(game, defender, attacker, args.episodes, args.seed)
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="purex", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="train a PPO-oracle PSRO population")
    train.add_argument("--config", required=True, help="case-study JSON configuration")
    train.add_argument("--output", required=True, help="directory for checkpoints and run manifest")
    train.add_argument("--seed", type=int, default=0)
    train.add_argument("--iterations", type=int, default=5)
    train.add_argument("--oracle-episodes", type=int, default=16)
    train.add_argument("--payoff-episodes", type=int, default=8)
    train.add_argument("--alpha", type=float, default=10.0)
    train.add_argument("--population-size", type=int, default=50)
    train.add_argument("--ppo-config", help="JSON file overriding PPO defaults")
    train.set_defaults(func=train_command)

    evaluate = commands.add_parser("evaluate", help="evaluate a policy pair across seeded episodes")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--defender", help="PPO policy checkpoint")
    evaluate.add_argument("--attacker", help="PPO policy checkpoint")
    evaluate.add_argument("--defender-baseline", choices=["random", "greedy"], default="greedy")
    evaluate.add_argument("--attacker-baseline", choices=["random", "greedy"], default="greedy")
    evaluate.add_argument("--episodes", type=int, default=1000)
    evaluate.add_argument("--seed", type=int, default=0)
    evaluate.add_argument("--output", help="optional JSON result path")
    evaluate.set_defaults(func=evaluate_command)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
