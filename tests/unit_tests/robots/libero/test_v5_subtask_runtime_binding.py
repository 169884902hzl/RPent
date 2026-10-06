"""An unresolved public instance must not execute an ambiguous contact prompt."""

from types import SimpleNamespace

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def test_ambiguous_macro_returns_unmeasured_without_calling_contact_policy():
    first = Entity("e1", "bowl", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    second = Entity("e2", "bowl", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    plate = Entity("e3", "plate", (.2, 0., .9), (.1, -.1, .89), (.3, .1, .91))
    executor = V5Executor.__new__(V5Executor)
    executor.scene = SimpleNamespace(entities={e.id: e for e in (first, second, plate)},
                                     view_axes=((0., 1., 0.), (1., 0., 0.)))
    def unexpected_contact(*args, **kwargs):
        raise AssertionError("ambiguous contact prompt was executed")
    executor.vla_act = unexpected_contact
    receipt = {"executed": False}
    executor.execute_subtask(Candidate("vla_subtask", first.id, plate.id, "on"), receipt)
    assert receipt == {"executed": False, "verification": "unmeasured",
                       "failure_reason": "selected_instance_not_uniquely_measured"}
