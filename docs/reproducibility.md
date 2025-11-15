# Reproducibility

## Recorded inputs

Each case-study JSON stores the environment name, horizon, maintainer expertise counts, detection and resolution matrices, reward vectors, attacker capacity, assumed benign-arrival probabilities, issue-catalog size, and the paper's reported state-space cardinality. `purex train` writes the environment config, PPO and PSRO options, seed, per-iteration payoff estimates, meta-strategies, and checkpoints to the selected output directory.

The direct runtime dependencies are pinned in `pyproject.toml` and `requirements.txt`. A platform-specific transitive lockfile is not included; record the resolved environment when publishing results.

## Determinism

Pass an explicit integer `--seed`. Environment and baseline policies use NumPy generators seeded from that value and episode offsets. PPO initialization and categorical action sampling use PyTorch's seeded generator state; minibatch shuffling uses a seeded NumPy generator. Results are reproducible for the same Python, NumPy, PyTorch, platform, and device versions. PyTorch operations may not be bitwise identical across different hardware or library builds.

## Paper-scale protocol versus runnable defaults

The paper reports five PSRO iterations, 100,000 training timesteps for the small setting and 500,000 for the large setting, and evaluation over 1,000 episodes for the large case. The text also describes 1,000 independent small-case runs with 100 uniformly sampled episodes each. Several PPO settings, oracle rollout counts, payoff-sampling counts, random seeds, source snapshots, and the benign arrival distribution are not published. CLI defaults (`16` oracle episodes and `8` payoff episodes per iteration) are practical run sizes, not the paper's training budget. Increase `--oracle-episodes` and `--payoff-episodes` for larger studies; do not label them as exact reproductions of the paper protocol.

## Outputs

- `defender-NN.pt`, `attacker-NN.pt`: PyTorch state dictionaries and PPO settings.
- `run.json`: complete run configuration, iteration history, empirical payoff matrices, and final alpha-rank mixtures.
- `purex evaluate --output result.json`: episode-level metrics and raw per-episode values, including reward, mean backlog, malicious assignments, detection percentage, and injection counts.

For a new study, report the repository revision, software versions, config files, all seeds, oracle and payoff episode counts, hardware, and whether the run used GPU acceleration. The original paper reports Apple M4 hardware and approximate wall-clock times; those times are not expected to transfer to other systems.

