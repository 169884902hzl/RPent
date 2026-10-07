"""Isolated MAX observation bridge; it never re-renders a simulator image.

Feed ONLY the observation already returned by CosmosInterventionEnv. Pixel
transforms belong to that wrapper and must not be reapplied by this bridge.
Calibration is a separately declared evaluation configuration, not an object
pose oracle. This module imports neither LIBERO nor a private judge.
"""
from __future__ import annotations

import copy
import hashlib
import numpy as np

CAMERAS = {"agentview": "agentview", "robot0_eye_in_hand": "robot0_eye_in_hand", "wrist": "robot0_eye_in_hand"}
MODES = ("live_simulator_calibration", "initial_frozen_with_public_wrist_fk")
PUBLIC_ROBOT_KEYS = ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")


class ObservationContractError(RuntimeError):
    pass


def resize_nearest(array, height, width):
    """Deterministic RGB/depth resize of the SAME accepted observation."""
    array = np.asarray(array)
    if height < 1 or width < 1 or array.ndim not in (2, 3):
        raise ObservationContractError("Invalid camera buffer or output size")
    rows = np.minimum((np.arange(height) * array.shape[0] // height), array.shape[0] - 1)
    cols = np.minimum((np.arange(width) * array.shape[1] // width), array.shape[1] - 1)
    return array[rows[:, None], cols[None, :]].copy()


def eef_transform(raw):
    """World->EEF pose from public position and XYZW proprioception."""
    position = np.asarray(raw["robot0_eef_pos"], dtype=float)
    quat = np.asarray(raw["robot0_eef_quat"], dtype=float)
    if position.shape != (3,) or quat.shape != (4,) or not np.isfinite(position).all() or not np.isfinite(quat).all():
        raise ObservationContractError("Missing or invalid public EEF pose")
    norm = np.linalg.norm(quat)
    if norm < 1e-8:
        raise ObservationContractError("Invalid public EEF quaternion")
    x, y, z, w = quat / norm
    pose = np.eye(4)
    pose[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                    [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                    [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    pose[:3, 3] = position
    return pose


def axis_angle(quat):
    quat = np.asarray(quat, dtype=float)
    quat = quat / np.linalg.norm(quat)
    # Match RLinf's XYZW axis-angle formula; do not impose a new sign rule.
    w = float(np.clip(quat[3], -1, 1))
    denom = np.sqrt(1-w*w)
    return np.zeros(3) if denom < 1e-8 else quat[:3] * (2*np.arccos(w) / denom)


class CanonicalObserver:
    """Cache transformed RGB-D once per control; expose resized views only.

    live_meta(camera, h, w) may read simulator camera calibration ONLY in the
    live calibration configuration or during initial calibration. Frozen
    wrist metadata uses an initial camera-to-EEF transform and subsequent
    PUBLIC EEF pose, not future camera truth. Extra event payload fields,
    joints, object poses and task predicates are omitted from raw_obs().
    """

    def __init__(self, live_meta, *, calibration_mode, source_orientation="opengl", policy_resolution=256):
        if calibration_mode not in MODES:
            raise ObservationContractError("Declare one calibration configuration")
        if source_orientation != "opengl":
            raise ObservationContractError("Current RPent dump contract requires opengl buffers")
        self.live_meta = live_meta
        self.calibration_mode = calibration_mode
        self.policy_resolution = policy_resolution
        self.initial_metadata = {}
        self.initial_camera_to_eef = None
        self._raw = None
        self.control_step = None
        self.frame_records = []

    def accept(self, transformed_observation, *, control_step, measurement_capture=False):
        if (control_step < 0 or self.control_step is not None and control_step < self.control_step
                or self.control_step is not None and control_step == self.control_step and not measurement_capture):
            raise ObservationContractError("Accept each control once; repeated controls need an explicit fresh measurement capture")
        raw = transformed_observation
        eef_transform(raw)
        accepted = {name: np.asarray(raw[name]).copy() for name in PUBLIC_ROBOT_KEYS}
        for camera in ("agentview", "robot0_eye_in_hand"):
            rgb_key, depth_key = camera+"_image", camera+"_depth"
            if rgb_key not in raw or depth_key not in raw:
                raise ObservationContractError(f"Missing canonical RGB-D camera {camera}")
            rgb = np.asarray(raw[rgb_key])
            depth = np.asarray(raw[depth_key])
            if (rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8
                    or depth.shape[:2] != rgb.shape[:2] or depth.ndim not in (2, 3)
                    or depth.ndim == 3 and depth.shape[2] != 1):
                raise ObservationContractError(f"Misaligned canonical RGB-D camera {camera}")
            if not np.isfinite(depth).all() or np.any(depth < 0) or np.any(depth > 1):
                raise ObservationContractError("Canonical depth must be the normalized MuJoCo depth buffer")
            accepted[rgb_key], accepted[depth_key] = rgb.copy(), depth.copy()
            if camera not in self.initial_metadata:
                meta = self.live_meta(camera, rgb.shape[0], rgb.shape[1])
                if meta is None:
                    raise ObservationContractError(f"No initial calibration for {camera}")
                self.initial_metadata[camera] = copy.deepcopy(meta)
                if camera == "robot0_eye_in_hand":
                    self.initial_camera_to_eef = np.linalg.inv(eef_transform(raw)) @ np.asarray(meta["extrinsic_cam2world"])
        # Names are the LIBERO-supplied scene vocabulary. Never retain object
        # coordinates that happen to be attached to those names in raw obs.
        for key in raw:
            if key.endswith("_pos") and "robot0" not in key and "to_robot" not in key:
                accepted[key] = None
        self._raw, self.control_step = accepted, int(control_step)
        self.frame_records.append({"control_step": self.control_step,
                                   "frame_index": len(self.frame_records),
                                   "capture": "fresh_transformed_measurement" if measurement_capture else "native_control_observation",
                                   "calibration_configuration": self.calibration_mode,
                                   "source": "cosmos_transformed_observation_no_rerender",
                                   "rgb_sha256": {c: hashlib.sha256(accepted[c+"_image"].tobytes()).hexdigest()
                                                  for c in ("agentview", "robot0_eye_in_hand")}})

    def raw_obs(self):
        if self._raw is None:
            raise ObservationContractError("No canonical frame accepted")
        return {key: value.copy() if isinstance(value, np.ndarray) else value for key, value in self._raw.items()}

    def render_camera(self, camera_name="agentview", height=1024, width=1024, depth=False):
        camera = CAMERAS[camera_name]
        raw = self.raw_obs()
        rgb = resize_nearest(raw[camera+"_image"], height, width)
        return (rgb, resize_nearest(raw[camera+"_depth"], height, width)) if depth else rgb

    def get_camera_meta(self, camera_name="agentview", height=256, width=256):
        camera = CAMERAS[camera_name]
        if self._raw is None:
            raise ObservationContractError("No canonical frame accepted")
        if self.calibration_mode == "live_simulator_calibration":
            meta = copy.deepcopy(self.live_meta(camera, height, width))
            provenance = "live_simulator_camera_pose_and_fovy"
        else:
            meta = copy.deepcopy(self.initial_metadata[camera])
            scale = np.diag([width / meta["width"], height / meta["height"], 1.])
            meta["intrinsic_K"] = (scale @ np.asarray(meta["intrinsic_K"])).tolist()
            if camera == "robot0_eye_in_hand":
                meta["extrinsic_cam2world"] = (eef_transform(self._raw) @ self.initial_camera_to_eef).tolist()
                provenance = "initial_camera_to_eef_calibration_plus_public_proprioception"
            else:
                provenance = "initial_fixed_world_camera_calibration"
            meta["width"], meta["height"] = width, height
        if meta is None:
            raise ObservationContractError("Missing camera calibration")
        meta.update(calibration_configuration=self.calibration_mode, calibration_source=provenance,
                    observation_control_step=self.control_step,
                    observation_frame_index=len(self.frame_records)-1,
                    image_source="cosmos_transformed_observation_no_rerender")
        return meta

    def policy_obs(self, instruction):
        raw = self.raw_obs()
        resolution = self.policy_resolution
        return {"main_images": resize_nearest(raw["agentview_image"][::-1, ::-1], resolution, resolution),
                "wrist_images": resize_nearest(raw["robot0_eye_in_hand_image"][::-1, ::-1], resolution, resolution),
                "states": np.concatenate([raw["robot0_eef_pos"], axis_angle(raw["robot0_eef_quat"]), raw["robot0_gripper_qpos"]]).astype(np.float32),
                "task_descriptions": instruction}
