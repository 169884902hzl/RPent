# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Owned Pi0.5 noise-seeded service for original-task branch collection only.

The RPent baseline server is unchanged. Each request must register a policy
noise seed; CPU and visible CUDA RNG states are restored after inference.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import threading
from pathlib import Path

import torch

from rpent.robots.components.pi05_vla_server import Pi05VLAFacade
from rpent.utils.config import get_pi05_checkpoint_path

SEED_CONTRACT = "pi05_policy_noise_seed/1"
MAX_SEED = 2**63 - 1


def sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validated_seed(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SEED:
        raise ValueError("policy noise seed must be an explicit integer in [0, 2**63-1]")
    return value


class SeededPi05VLAFacade(Pi05VLAFacade):
    """Use the actual policy's Torch noise generator, isolated per request."""

    def __init__(self, **kwargs):
        self._noise_lock = threading.Lock()
        self._seeded_model_identity = {key: kwargs.get(key) for key in
                                      ("model_path", "model_backend", "norm_stats_path", "repo_id")}
        super().__init__(**kwargs)

    def _register_rpc(self) -> None:
        super()._register_rpc()
        self._rpc["vla.seeded_identity"] = self.seeded_identity
        self._readonly_methods.add("vla.seeded_identity")

    def seeded_identity(self) -> dict:
        return {"seed_contract": SEED_CONTRACT, "embodiment": self._embodiment,
                "server_sha256": sha(__file__), "upstream_server_sha256": sha(inspect.getfile(Pi05VLAFacade)),
                "torch_version": torch.__version__, "model": self._seeded_model_identity,
                "rng_isolation": "locked torch.random.fork_rng over CPU and all visible CUDA generators",
                "policy_noise_source": "Pi0.5 sample_noise uses torch.normal"}

    def predict(self, obs: dict, options: dict | None = None):
        options = dict(options or {})
        seed = validated_seed(options.pop("seed", None))
        if options.get("mode", "eval") != "eval" or set(options) - {"mode"}:
            raise ValueError("owned original branch service accepts only mode=eval and seed")
        devices = list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []
        # Inference requests must not interleave globally scoped generators.
        # Fork all visible CUDA generators because torch.manual_seed seeds all.
        with self._noise_lock, torch.random.fork_rng(devices=devices):
            torch.manual_seed(seed)
            return super().predict(obs, options)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--model-backend", choices=["openpi_pytorch", "openpi_rlinf"], default="openpi_pytorch")
    parser.add_argument("--norm-stats-path", default=os.environ.get("PI05_NORM_STATS_PATH"))
    parser.add_argument("--repo-id", default=None)
    parser.add_argument("--transport", choices=["socket", "http"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--parent-watch", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("dedicated original-task collection requires LIBERO_TYPE=standard")
    model_path = args.model_path or get_pi05_checkpoint_path()
    if not model_path:
        parser.error("explicit Pi0.5 checkpoint or PI05_CHECKPOINT_PATH required")
    SeededPi05VLAFacade(model_path=model_path, embodiment="libero", model_backend=args.model_backend,
                       norm_stats_path=args.norm_stats_path, repo_id=args.repo_id).serve(
        transport=args.transport, host=args.host, port=args.port, parent_watch=args.parent_watch)


if __name__ == "__main__":
    main()
