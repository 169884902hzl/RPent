from types import SimpleNamespace

import pytest

from robots.libero.v5_state import Entity
from scripts.probe_v5_microwave_public571 import (
    bind_public_microwave, install_owned_adapter, registered_public_microwave_instruction,
)


def entity(eid="e1", name="microwave", *, visible=True, step=3, parent=None):
    return Entity(eid, name, (0., 0., 1.), (-.2, -.2, .8), (.2, .2, 1.2),
                  visible=visible, source_step=step, part_of=parent)


def executor(entities):
    return SimpleNamespace(scene=SimpleNamespace(entities={e.id: e for e in entities}),
                           toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=3)))


def spec(mode="open", **extra):
    return {"kind": "articulate", "object_category": "microwave", "mode": mode,
            "subtask_prompt": f"{mode} the microwave", **extra}


def test_parent_without_door_handle_or_private_symbol_binds():
    policy = SimpleNamespace(bind=lambda *a, **k: pytest.fail("private-symbol binding was called"))
    selected = bind_public_microwave(executor([entity()]), policy, spec(), "articulate")
    assert selected.text() == "articulate(e1,open)"
    assert policy.last_binding["private_symbol_or_geometry_used_for_selector"] is False


@pytest.mark.parametrize("others", [[], [entity(visible=False)], [entity(step=2)],
                                     [entity(), entity("e2")], [entity(name="microwave door", parent="e9")]])
def test_missing_stale_part_or_ambiguous_parent_rejects(others):
    with pytest.raises(LookupError):
        bind_public_microwave(executor(others), SimpleNamespace(), spec(), "articulate")


def test_cached_second_parent_does_not_fabricate_ambiguity_or_geometry():
    policy = SimpleNamespace()
    action = bind_public_microwave(executor([entity(), entity("e2", visible=False, step=1)]),
                                  policy, spec("close", object_symbol="deliberately_unused"), "articulate")
    assert action.object == "e1"
    assert policy.last_binding["public_condition_instruction"] == "close the microwave"


@pytest.mark.parametrize("change", [{"mode": "turn_on"}, {"subtask_prompt": "open the bottom drawer"},
                                  {"kind": "place"}, {"subtask_prompt": "close the microwave"}])
def test_only_registered_public_microwave_modes_and_phrases(change):
    with pytest.raises(ValueError):
        registered_public_microwave_instruction(spec(**change))


def test_original_drawer_path_remains_original():
    calls = []
    probe = SimpleNamespace(bind_action=lambda *a, **k: calls.append((a, k)) or "original_bind",
                            registered_drawer_instruction=lambda s: "original_drawer",
                            execute_stage=lambda *a, **k: "original_execute")
    install_owned_adapter(probe)
    drawer = {"object_category": "cabinet top drawer"}
    assert probe.bind_action(None, None, drawer, "articulate") == "original_bind"
    assert probe.registered_drawer_instruction(drawer) == "original_drawer"
    assert probe.execute_stage(None, None, None, drawer, "articulate", "setup") == "original_execute"
    assert len(calls) == 1
