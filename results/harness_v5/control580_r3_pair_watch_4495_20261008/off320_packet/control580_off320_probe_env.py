"""Fixed-budget original-only development scope; truth cannot stop controls."""

import stove564_probe_env as inherited
from robots.libero.v5_stove_probe_env import StoveProbeFacade


class Off320StoveProbeFacade(inherited.ScoredStoveProbeFacade):
    def stove_chunk_start(self, phase, max_chunks):
        expected = 160 if phase == "on" else 320 if phase == "off" else None
        if max_chunks != expected:
            raise ValueError("registered on160/off320 diagnostic budget changed")
        # Reuse the original order/step contract, then install the registered
        # off budget before any control or private score is recorded.
        StoveProbeFacade.stove_chunk_start(self, phase, 160)
        self._stove_chunk_scope.update(max_chunks=max_chunks, max_controls=max_chunks * 5)
        self._write_private_score(dict(self._stove_chunk_scope), "before_phase")
        return dict(self._stove_chunk_scope)


def main():
    inherited.ScoredStoveProbeFacade = Off320StoveProbeFacade
    inherited.main()


if __name__ == "__main__":
    main()
