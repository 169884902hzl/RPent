"""Observe the real configured scene path without extra captures or queries."""

from robots.libero.v5_place_public_trace import original_placement_trace
from scripts.probe_v5_skill501_original import main


if __name__ == "__main__":
    with original_placement_trace(observe_runtime_only=True):
        main()
