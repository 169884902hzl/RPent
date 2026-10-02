# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Preserve native success while completing finite measured skill receipts."""

from contextlib import contextmanager

import numpy as np

from robots.libero.env_client import LiberoEnvClient


class V5SkillEnvClient(LiberoEnvClient):
    """Complete measured manipulation skills without stepping past truncation."""

    def __init__(self, *args, **kwargs):
        self._skill_active = False
        self._native_terminated = False
        super().__init__(*args, **kwargs)

    @property
    def terminated(self) -> bool:
        return self._native_terminated and not self._skill_active

    @terminated.setter
    def terminated(self, value: bool) -> None:
        self._native_terminated = bool(value)

    def check_done(self, term, trunc) -> None:
        self._native_terminated |= bool(np.asarray(term).any())
        self.truncated |= bool(np.asarray(trunc).any())

    @contextmanager
    def complete_skill(self):
        """Keep native success private to scoring during finite skill steps."""
        previous = self._skill_active
        self._skill_active = True
        try:
            yield
        finally:
            self._skill_active = previous
