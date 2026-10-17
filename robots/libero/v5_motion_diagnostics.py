"""Private contact and joint evidence for recorded-prefix motion diagnosis."""

import types

import numpy as np


def motion_diagnostic(wrapper):
    """Read the current simulator; never add this evidence to a model prompt."""
    env = wrapper.env
    model, data = env.sim.model, env.sim.data
    joints = []
    for robot in env.robots:
        for joint_id in robot._ref_joint_indexes:
            address = int(model.jnt_qposadr[joint_id])
            value = float(data.qpos[address])
            limits = np.asarray(model.jnt_range[joint_id], dtype=float)
            limited = bool(model.jnt_limited[joint_id])
            joints.append({
                "name": model.joint_id2name(int(joint_id)), "qpos": value,
                "limited": limited, "range": limits.tolist(),
                "limit_margin_rad": float(min(value - limits[0], limits[1] - value))
                if limited else None,
            })
    contacts = []
    for index in range(data.ncon):
        contact = data.contact[index]
        contacts.append({
            "geom1": model.geom_id2name(int(contact.geom1)),
            "geom2": model.geom_id2name(int(contact.geom2)),
            "distance_m": float(contact.dist),
        })
    return {"source": "simulation_diagnostic_only", "contacts": contacts,
            "joints": joints, "sim_time": float(data.time)}


def attach_motion_diagnostic(wrapper):
    wrapper.v5_motion_diagnostic = types.MethodType(motion_diagnostic, wrapper)
    wrapper.v5_pixel_geometry_diagnostic = types.MethodType(pixel_geometry_diagnostic, wrapper)
    return wrapper


def pixel_geometry_diagnostic(wrapper, camera, height, width):
    """Render private geometry identities for offline prefix diagnosis only.

    These identities never pass through an observation or candidate API.
    Use the same vertical flip as the saved public calibrated images.
    """
    if camera not in {'agentview', 'robot0_eye_in_hand'}:
        raise ValueError('diagnostic camera must be a recorded LIBERO view')
    env = wrapper.env
    segmentation = env.sim.render(width=width, height=height,
        camera_name=camera, segmentation=True)[::-1].copy()
    return {'source': 'simulation_pixel_geometry_diagnostic_only',
        'camera': camera, 'segmentation': segmentation,
        'geom_names': {str(i): env.sim.model.geom_id2name(i) for i in range(env.sim.model.ngeom)}}
