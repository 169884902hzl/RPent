"""A shared current measured door can identify adjacent appliance surfaces."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_fixture_parts import measured_microwave_parent_groups
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity


def parents_and_doors():
    first = Entity("e1", "microwave", (-.1, .1, 1.1), (-.16, 0., 1.),
                   (-.04, .2, 1.2), source_step=5)
    second = Entity("e2", "microwave", (.02, .2, 1.1), (-.039, .19, 1.),
                    (.1, .22, 1.2), source_step=5)
    doors = {e.id: {"sha256": "same-current-measured-door", "source_step": 5}
             for e in (first, second)}
    return first, second, doors


def test_shared_current_door_and_adjacent_rigid_surfaces_can_join():
    first, second, doors = parents_and_doors()
    groups, evidence = measured_microwave_parent_groups([first, second], doors, 5)
    assert len(groups) == 1 and {e.id for e in groups[0]} == {"e1", "e2"}
    assert evidence["comparisons"][0]["surface_gap_m"] == pytest.approx(.001)
    assert evidence["source"] == "perception"


@pytest.mark.parametrize("difference", ["different_door", "stale", "remote", "high_robot"])
def test_two_appliances_or_stale_and_robot_surfaces_remain_unmerged(difference):
    first, second, doors = parents_and_doors()
    if difference == "different_door":
        doors[second.id]["sha256"] = "another-real-door"
    elif difference == "stale":
        doors[second.id]["source_step"] = 4
    elif difference == "remote":
        second = replace(second, lower=(.5, .19, 1.), upper=(.6, .22, 1.2))
    else:
        second = replace(second, upper=(.1, .22, 1.45))
    assert not measured_microwave_parent_groups([first, second], doors, 5)[0]


def test_an_incompatible_shared_door_bridge_does_not_force_an_identity():
    first, second, doors = parents_and_doors()
    second = replace(second, lower=(-.039, .19, 1.015), upper=(.1, .22, 1.215))
    third = replace(second, id="e3", lower=(-.039, .19, 1.03), upper=(.1, .22, 1.23))
    doors[third.id] = doors[second.id].copy()
    assert not measured_microwave_parent_groups([first, second, third], doors, 5)[0]


def test_a_tall_robot_alias_is_excluded_without_erasing_the_real_surface_group():
    first, second, doors = parents_and_doors()
    robot = replace(second, id="e3", upper=(.1, .22, 1.45))
    doors[robot.id] = doors[second.id].copy()
    groups, evidence = measured_microwave_parent_groups([first, second, robot], doors, 5)
    assert len(groups) == 1 and {e.id for e in groups[0]} == {"e1", "e2"}
    assert sum(item["accepted"] for item in evidence["comparisons"]) == 1


def test_runtime_joins_measured_clouds_and_retains_one_stable_parent_and_door(tmp_path, monkeypatch):
    first, second, doors = parents_and_doors()
    def save(name, value, *, step):
        np.savez_compressed(tmp_path / name, array=value)
        return tmp_path / name
    state = SimpleNamespace(latest_step=5, load=lambda _: {"extrinsic_cam2world": np.eye(4)},
                            save=save, artifact_path=lambda name, step: tmp_path / name)
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(), 0,
                          microwave_instance_geometry_v4=True, microwave_door_cloud_v6=True)
    child = Entity("e3", "microwave door", (-.1, .1, 1.1), (-.11, 0., 1.),
                   (-.1, .2, 1.2), part_of=first.id, source_step=5)
    children = [child, replace(child, id="e4", part_of=second.id)]
    scene.entities = {e.id: e for e in [first, second, *children]}
    samples = {first.id: np.array([(-.15, y, z) for y in np.linspace(0., .2, 20)
                                   for z in np.linspace(1., 1.2, 10)]
                                  + [(x, .2, z) for x in np.linspace(-.15, -.04, 12)
                                     for z in np.linspace(1., 1.2, 10)]),
               second.id: np.array([(x, .2, z) for x in np.linspace(-.039, .1, 30)
                                    for z in np.linspace(1., 1.2, 20)])}
    scene.measurement_clouds.update(samples)
    for parent in (first, second):
        scene.cache_independent_views(parent, {"agentview": samples[parent.id]})
        scene.fixture_measurement_evidence[parent.id] = {"door_measurement": doors[parent.id],
            "path": f"explicit-measured-cloud-{parent.id}.npz", "sha256": parent.id}
        scene.perception_evidence[parent.id] = {}
    masks = {first.id: np.array([[True, False]]), second.id: np.array([[False, True]])}
    scene._consolidate_microwave_parents(masks, "agentview")
    parents = [e for e in scene.entities.values() if e.visible and e.name == "microwave"]
    parts = [e for e in scene.entities.values() if e.visible and e.name == "microwave door"]
    assert len(parents) == len(parts) == 1
    assert parents[0].id == second.id and parts[0].part_of == second.id
    assert parents[0].lower[0] < -.14 and parents[0].upper[0] > .08
    assert masks[second.id].all()
    evidence = scene.fixture_measurement_evidence[second.id]
    assert len(evidence["source_parents"]) == len(evidence["source_clouds"]) == 2
    assert scene._microwave_parent_ids[first.id] == second.id
    assert evidence["point_selection"] == "shared_current_measured_microwave_door_adjacent_surfaces/1-dev"
    assert scene.measurement_clouds_by_view[second.id]["agentview"]["src"] == "perception"
    # A retired alias must not masquerade as an unmeasured second instance in
    # typed binding. The original clouds/provenance remain available privately.
    from robots.libero.v5_state import Candidate
    from robots.libero.v5_subtasks import subtask_prompt, SubtaskBindingError
    assert set(scene.entities) == {second.id, "e4"}
    assert first.id in scene.measurement_clouds
    assert scene.fixture_measurement_evidence[first.id]["path"] == "explicit-measured-cloud-e1.npz"
    assert subtask_prompt(Candidate("vla_subtask", second.id, mode="open"), scene.entities) == "open the microwave"
    assert subtask_prompt(Candidate("vla_subtask", "e4", mode="close"), scene.entities) == "close the microwave door"

    # The next public category observation associates to the sole canonical
    # parent, instead of resurrecting the retired alias by nearest distance.
    from rpent.robots.components.sam3_client import Sam3Client
    rows, columns = np.mgrid[:12, :12]
    world = np.stack((.04 + columns * .002, .20 + rows * .002, 1.05 + rows * .001), axis=-1)
    state.latest_step = 6
    state.load_bytes = lambda _: b"RGB"
    state.load = lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world
    scene.rpc = SimpleNamespace(call=lambda *args, **kwargs: {"instances": [
        {"mask": np.ones(world.shape[:2], dtype=bool), "score": .9}]})
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene.refresh(["microwave"])
    assert first.id not in scene.entities and scene.entities[second.id].source_step == 6
    assert scene.entities[second.id].visible and scene._microwave_parent_ids[first.id] == second.id

    # A genuinely separate appliance with unavailable measurement still makes
    # the class ambiguous. This fix does not globally ignore invisible peers.
    other = replace(second, id="e99", visible=False, xyz=(.7, .7, 1.1))
    scene.entities[other.id] = other
    with pytest.raises(SubtaskBindingError, match="measurement unavailable"):
        subtask_prompt(Candidate("vla_subtask", second.id, mode="open"), scene.entities)
