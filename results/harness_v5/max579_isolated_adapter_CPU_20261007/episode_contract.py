"""Per-control MAX bridge and exact paired-prefix validation, isolated only."""
from __future__ import annotations

import numpy as np


class PairIntegrityError(RuntimeError):
    pass


class PairedEpisodeBridge:
    """CosmosInterventionEnv -> the RPent env observation/step contract.

    Lifecycle/reset/official renderer QA remain the caller's responsibility.
    Start AFTER native warmup, accept its last transformed observation with
    initialize(), and then count precisely the registered suite controls.
    The bridge does not expose MAX event payloads, private goal labels or raw
    simulator positions. Native done remains an allowed termination signal.
    """

    def __init__(self, wrapped, observer, *, budget_controls, base_record=None, fresh_measurement_provider=None):
        if budget_controls <= 0:
            raise ValueError("Positive suite control budget required")
        self.wrapped, self.observer = wrapped, observer
        self.budget_controls = budget_controls
        self.base_record = base_record
        # Pass wrapped.backend.refresh_observation, which applies the source
        # and MAX transforms once. It does not advance simulator controls.
        # Never pass an untransformed sim.render or _get_observations callback.
        self.fresh_measurement_provider = fresh_measurement_provider
        self.base_actions = {} if base_record is None else {int(r["policy_step"]): np.asarray(r["action"], dtype=np.float32)
                                                          for r in base_record["executed_actions"]}
        self.base_queries = {} if base_record is None else {int(q["policy_step"]): np.asarray(q["actions"], dtype=np.float32)
                                                          for q in base_record["policy_queries"]}
        if len(self.base_actions) != (0 if base_record is None else len(base_record["executed_actions"])):
            raise PairIntegrityError("Duplicate Base control steps")
        if len(self.base_queries) != (0 if base_record is None else len(base_record["policy_queries"])):
            raise PairIntegrityError("Duplicate Base query boundaries")
        self.terminated = self.truncated = False
        self.controls = 0
        self.last_obs = None
        self.prefix_checked_controls = 0

    def initialize(self, transformed_observation):
        if self.controls != 0 or self.last_obs is not None:
            raise PairIntegrityError("Initialize one episode once")
        if self.wrapped.total_env_steps != self.wrapped.warmup_steps:
            raise PairIntegrityError("Finish the registered native warmup first")
        if self.base_record is not None:
            for key in ("init_state_sha256", "policy_seed"):
                if self.base_record[key] != getattr(self.wrapped, key):
                    raise PairIntegrityError(f"Paired {key} differs")
        self.observer.accept(transformed_observation, control_step=0)
        self.last_obs = self.observer.policy_obs(self.wrapped.runtime.current_instruction)
        return self.last_obs

    def step(self, action):
        if self.last_obs is None or self.terminated or self.truncated:
            raise PairIntegrityError("Cannot step before initialize or after termination")
        actual = np.asarray(action, dtype=np.float32).reshape(-1)
        if actual.shape != (7,) or not np.isfinite(actual).all():
            raise ValueError("Finite 7D control required")
        # Simulator wrapper appends policy_step AFTER executing the action.
        next_step = self.controls + 1
        if self.base_record is not None and not self.wrapped.runtime.applied:
            if next_step not in self.base_actions:
                raise PairIntegrityError("Base action prefix ended before the event")
            expected = self.base_actions[next_step]
            if not np.array_equal(actual, expected):
                raise PairIntegrityError(f"Pre-event control prefix differs at {next_step}")
            self.prefix_checked_controls += 1
        raw, reward, done, _private_info = self.wrapped.step(actual.tolist())
        self.controls += 1
        self.terminated = bool(done)
        self.truncated = self.controls >= self.budget_controls and not self.terminated
        self.observer.accept(raw, control_step=self.controls)
        self.last_obs = self.observer.policy_obs(self.wrapped.runtime.current_instruction)
        return self.last_obs, reward, self.terminated, self.truncated, {}

    def chunk_step(self, actions, *, return_all_frames=False):
        observations, rewards, term, trunc = [], [], [], []
        for action in np.asarray(actions):
            obs, reward, ended, exhausted, _ = self.step(action)
            observations.append(obs); rewards.append(reward); term.append(ended); trunc.append(exhausted)
            if ended or exhausted:
                break
        if not observations:
            raise ValueError("Empty action chunk")
        return (observations if return_all_frames else observations[-1],
                np.asarray(rewards), np.asarray(term), np.asarray(trunc), {})

    def query_actions(self, model, observation, options=None):
        """Wrap Pi0.5.predict to replay Base VLA queries before the event."""
        source = "model"
        if self.base_record is not None and not self.wrapped.runtime.applied:
            if self.controls not in self.base_queries:
                raise PairIntegrityError(f"Base query boundary missing at {self.controls}")
            actions = self.base_queries[self.controls].copy()
            source = "control_replay"
        else:
            actions = np.asarray(model.predict(observation, options=options or {}), dtype=np.float32)
        self.wrapped.record_policy_query(actions, instruction=observation["task_descriptions"], source=source)
        return actions

    def raw_obs(self):
        if self.fresh_measurement_provider is None:
            raise PairIntegrityError("Fresh transformed measurement provider required for harness captures")
        raw = self.fresh_measurement_provider()
        self.observer.accept(raw, control_step=self.controls, measurement_capture=True)
        return self.observer.raw_obs()

    def render_camera(self, *args, **kwargs):
        return self.observer.render_camera(*args, **kwargs)

    def get_camera_meta(self, *args, **kwargs):
        return self.observer.get_camera_meta(*args, **kwargs)

    def get_task_language(self):
        return self.wrapped.runtime.current_instruction
