"""Run the existing original probe with opt-in public placement evidence."""

from robots.libero.v5_place_public_trace import original_placement_trace
from scripts.probe_v5_skill501_original import main


if __name__ == "__main__":
    with original_placement_trace():
        main()
