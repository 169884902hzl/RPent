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
        expected = kwargs.get("expected_meta")
        if expected is not None and expected.get("suite") == "libero_90":
            # V5 admits original90 only through its read-only grasp diagnostic.
            # Generic LIBERO connector metadata has the four normal fields;
            # keep strict equality while carrying this required V5 identity.
            expected = dict(expected)
            expected.setdefault("original90_grasp_diagnostic_v1", True)
            kwargs["expected_meta"] = expected
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
