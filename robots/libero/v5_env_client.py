# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Preserve native success while completing the measured placement receipt."""

from contextlib import contextmanager

import numpy as np

from robots.libero.env_client import LiberoEnvClient


class V5PlacementEnvClient(LiberoEnvClient):
    """Allow release and retreat within a placement, never beyond truncation."""

    def __init__(self, *args, **kwargs):
        self._placement_active = False
        self._native_terminated = False
        super().__init__(*args, **kwargs)

    @property
    def terminated(self) -> bool:
        return self._native_terminated and not self._placement_active

    @terminated.setter
    def terminated(self, value: bool) -> None:
        self._native_terminated = bool(value)

    def check_done(self, term, trunc) -> None:
        self._native_terminated |= bool(np.asarray(term).any())
        self.truncated |= bool(np.asarray(trunc).any())

    @contextmanager
    def complete_placement(self):
        """Keep native success private to scoring during finite placement steps."""
        previous = self._placement_active
        self._placement_active = True
        try:
            yield
        finally:
            self._placement_active = previous
