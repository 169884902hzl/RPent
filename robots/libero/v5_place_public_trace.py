"""Opt-in original-development placement evidence, outside rendered requests.

The probe adds current RGB-D observations after existing carry segments. It
never changes robot controls, held offsets or verifier thresholds. Fresher
measurements can change binding and receipts; this is not historical replay.
"""

from contextlib import contextmanager
from functools import wraps
import numpy as np

from scripts.v5_place527_evidence import public_placement_frame, file_record


class PublicPlacementTrace:
    """Persist only current perception/proprioception and explicit artifacts."""

    def __init__(self, executor):
        self.executor = executor
        self.action = None
        self.index = 0
        self.references = []
        self.in_move_observation = False

    def save(self, phase):
        executor = self.executor
        state = executor.toolkit._state
        objects = {e.id: e for e in executor.scene.entities.values()
                   if e.name in {"bowl", "cabinet", "drawer"} or e.part_of}
        frame = public_placement_frame(executor, objects, self.index, phase)
        frame.update(version="public-placement-carry-trace/1-dev",
                     runtime_format_changed=False, training_allowed=False,
                     action=self.action.text() if self.action else None,
                     held_offset_m=(executor.held_offset.tolist()
                                    if executor.held_offset is not None else None))
        # Robot quaternion is proprioception. Other raw-observation fields are
        # deliberately neither read nor copied into this public record.
        frame["robot"]["eef_body_quat_xyzw"] = list(map(float,
            executor.p.env.raw_obs()["robot0_eef_quat"]))
        for eid, item in frame["entities"].items():
            entity = executor.scene.entities[eid]
            cloud = executor.scene.measurement_clouds.get(eid)
            item["fused_cloud"] = None
            if cloud is not None:
                name = f"place_trace_{self.index:04d}_{eid}_fused.npz"
                if state.save(name, np.asarray(cloud), step=state.latest_step) is None:
                    raise RuntimeError("could not persist public fused cloud")
                item["fused_cloud"] = {**file_record(state.artifact_path(name, step=state.latest_step)),
                    "source_step": entity.source_step, "src": "perception",
                    "current": entity.visible and entity.source_step == state.latest_step,
                    "shape": list(np.asarray(cloud).shape)}
            if entity.visible and entity.source_step == state.latest_step:
                item["eef_minus_current_measured_midpoint_m"] = (
                    np.asarray(executor.p._last_obs_eef_pos) -
                    (np.asarray(entity.lower) + entity.upper) / 2).tolist()
        name = f"place_trace_{self.index:04d}_public.json"
        if state.save(name, frame, step=state.latest_step) is None:
            raise RuntimeError("could not persist public placement metadata")
        reference = {**file_record(state.artifact_path(name, step=state.latest_step)),
                     "source_step": state.latest_step, "phase": phase, "sample_index": self.index}
        # State.save owns artifact registration. The separate explicit index
        # permits CPU analysis without globbing the observation directory.
        self.references.append(reference)
        if state.save("place_trace_index.jsonl", self.references, step=None) is None:
            raise RuntimeError("could not persist explicit placement index")
        self.index += 1
        return reference


@contextmanager
def original_placement_trace():
    """Enable saved current masks/clouds and same-frame drawer queries in probe."""
    from robots.libero.v5_runtime import MeasuredScene, V5Executor
    original_init, original_refresh = V5Executor.__init__, MeasuredScene.refresh
    original_execute = V5Executor.execute

    @wraps(original_init)
    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        trace = PublicPlacementTrace(self)
        self.scene._placement_public_trace = trace
        self.scene.record_sam_masks_v6 = True
        primitive_move = self.p.move_to

        @wraps(primitive_move)
        def move(*args, **kwargs):
            collecting = bool(trace.action and trace.action.tool in {"place", "adjust_place"}
                              and self.held is not None and not trace.in_move_observation)
            if collecting:
                trace.save("before_existing_carry_segment")
            result = primitive_move(*args, **kwargs)
            if collecting:
                trace.in_move_observation = True
                try:
                    self.capture()
                    self.scene.refresh([self.scene.entities[trace.action.object].name], camera_view="agentview")
                    trace.save("after_existing_carry_segment")
                finally:
                    trace.in_move_observation = False
            return result

        self.p.move_to = move

    @wraps(original_refresh)
    def refresh(self, names, **kwargs):
        trace = getattr(self, "_placement_public_trace", None)
        if trace is not None:
            # Separate drawer segmentation is evidence for a fragment alias;
            # cabinet-derived bands alone never prove that semantic identity.
            names = list(dict.fromkeys([*names, "drawer"]))
        result = original_refresh(self, names, **kwargs)
        if trace is not None:
            trace.save("before_public_fixture_alias")
            from robots.libero.v5_public_fixture_identity import canonical_fixture_scene
            self.entities, alias = canonical_fixture_scene(self.entities, self.toolkit._state.latest_step,
                                                            allow_drawer_fragment_alias=True)
            name = f"place_trace_alias_{trace.index:04d}.json"
            self.toolkit._state.save(name, alias, step=self.toolkit._state.latest_step)
            trace.save("after_existing_scene_refresh")
        return result

    @wraps(original_execute)
    def execute(self, action, card=None):
        trace = self.scene._placement_public_trace
        trace.action = action
        trace.save("before_selected_skill")
        try:
            return original_execute(self, action, card=card)
        finally:
            trace.save("after_selected_skill")
            trace.action = None

    V5Executor.__init__, MeasuredScene.refresh, V5Executor.execute = initialize, refresh, execute
    try:
        yield
    finally:
        V5Executor.__init__, MeasuredScene.refresh, V5Executor.execute = original_init, original_refresh, original_execute
