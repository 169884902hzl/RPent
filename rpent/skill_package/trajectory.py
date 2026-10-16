"""C2 quintic Cartesian references with vector derivative limits.

Limits constrain references, not measured robot motion. An adapter must screen
the sampled curve and braking tail against its public scene before execution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.polynomial import polynomial as poly


@dataclass(frozen=True)
class Limits:
    """Norm limits for one group of coordinates, in SI units."""

    velocity: float = .15
    acceleration: float = .5
    jerk: float = 2.

    def __post_init__(self):
        if min(self.velocity, self.acceleration, self.jerk) <= 0:
            raise ValueError("trajectory limits must be positive")


@dataclass
class Segment:
    """Power coefficients in normalized time, with physical duration."""

    coefficients: np.ndarray
    duration: float

    def at(self, time_s: float, derivative: int = 0) -> np.ndarray:
        u = np.clip(time_s / self.duration, 0., 1.)
        c = poly.polyder(self.coefficients, m=derivative, axis=0)
        return poly.polyval(u, c) / self.duration ** derivative

    def maximum(self, derivative: int, indices: slice) -> float:
        """Find norm extrema from polynomial roots, including endpoints."""
        c = poly.polyder(self.coefficients[:, indices], m=derivative, axis=0)
        squared = sum((poly.polymul(axis, axis) for axis in c.T), np.zeros(1))
        roots = poly.polyroots(poly.polyder(squared))
        candidates = [0., 1., *[r.real for r in roots
                                if abs(r.imag) < 1e-7 and 0. < r.real < 1.]]
        return max(float(np.linalg.norm(poly.polyval(t, c)))
                   for t in candidates) / self.duration ** derivative


def hermite(p0, p1, v0, v1, a0, a1, duration: float) -> Segment:
    """Quintic interpolation with physical position/velocity/acceleration."""
    p0, p1, v0, v1, a0, a1 = map(lambda x: np.asarray(x, float), (p0, p1, v0, v1, a0, a1))
    c0, c1, c2 = p0, v0 * duration, a0 * duration ** 2 / 2
    rhs = np.array([p1-c0-c1-c2, v1*duration-c1-2*c2, a1*duration**2-2*c2])
    c3 = np.linalg.solve(np.array([[1, 1, 1], [3, 4, 5], [6, 12, 20]]), rhs)
    return Segment(np.array([c0, c1, c2, *c3]), float(duration))


@dataclass
class Trajectory:
    segments: list[Segment]

    @property
    def duration(self) -> float:
        return sum(segment.duration for segment in self.segments)

    def at(self, time_s: float, derivative: int = 0) -> np.ndarray:
        for segment in self.segments:
            if time_s <= segment.duration:
                return segment.at(time_s, derivative)
            time_s -= segment.duration
        return self.segments[-1].at(self.segments[-1].duration, derivative)

    def samples(self, hz: float = 20.) -> tuple[np.ndarray, np.ndarray]:
        times = np.r_[np.arange(0., self.duration, 1/hz), self.duration]
        return times, np.array([self.at(t) for t in times])


def plan(waypoints, *, blend: bool = True,
         groups: tuple[tuple[slice, Limits], ...] = ((slice(0, 3), Limits()),),
         minimum_duration: float = .1) -> Trajectory:
    """Fit shared-velocity quintics, retiming until all norm limits hold.

    A reversal stops at its waypoint. Otherwise a tangent bisector passes
    through the waypoint with common velocity and zero acceleration.
    """
    points = np.asarray(waypoints, float)
    if points.ndim != 2 or len(points) < 2 or not np.isfinite(points).all():
        raise ValueError("at least two finite waypoint vectors required")
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    times = np.maximum(distances / min(limit.velocity for _, limit in groups), minimum_duration)
    for _ in range(20):
        velocities = np.zeros_like(points)
        if blend:
            for i in range(1, len(points)-1):
                incoming, outgoing = points[i]-points[i-1], points[i+1]-points[i]
                n0, n1 = np.linalg.norm(incoming), np.linalg.norm(outgoing)
                if n0 > 1e-9 and n1 > 1e-9 and np.dot(incoming, outgoing)/(n0*n1) > -.1:
                    tangent = incoming/n0 + outgoing/n1
                    velocities[i] = tangent/np.linalg.norm(tangent) * .6 * min(n0/times[i-1], n1/times[i])
        zero = np.zeros(points.shape[1])
        segments = [hermite(a, b, velocities[i], velocities[i+1], zero, zero, times[i])
                    for i, (a, b) in enumerate(zip(points[:-1], points[1:]))]
        ratio = max([1., *[segment.maximum(d, indices)**(1/d) / bound**(1/d)
                     for segment in segments for indices, limit in groups
                     for d, bound in enumerate((limit.velocity, limit.acceleration, limit.jerk), 1)]])
        if ratio <= 1.000001:
            return Trajectory(segments)
        times *= ratio * 1.001
    raise RuntimeError("quintic retiming did not converge")


def brake(position, velocity, acceleration, *, limits: Limits = Limits()) -> Trajectory:
    """Continuous p/v/a stop from a measured public state (no abrupt zero)."""
    p, v, a = map(lambda x: np.asarray(x, float), (position, velocity, acceleration))
    duration = max(.15, 2*np.linalg.norm(v)/limits.acceleration,
                   2*np.sqrt(np.linalg.norm(v)/limits.jerk), 2*np.linalg.norm(a)/limits.jerk)
    for _ in range(30):
        end = p + .5*v*duration + a*duration**2/12
        segment = hermite(p, end, v, np.zeros_like(v), a, np.zeros_like(a), duration)
        # An inherited overspeed cannot disappear instantly; the initial
        # measured derivative is explicitly allowed while decelerating.
        bounds = (max(limits.velocity, np.linalg.norm(v)), max(limits.acceleration, np.linalg.norm(a)), limits.jerk)
        if all(segment.maximum(d, slice(None)) <= bound*1.00001
               for d, bound in enumerate(bounds, 1)):
            return Trajectory([segment])
        duration *= 1.25
    raise RuntimeError("unable to form a bounded braking tail")


def motion_metrics(positions, *, hz: float = 20., waypoint_indices=()) -> dict:
    """Measured metrics; stops are velocity troughs at internal waypoints."""
    p = np.asarray(positions, float)
    if len(p) < 5:
        raise ValueError("five measured samples required")
    velocity = np.diff(p, axis=0)*hz
    jerk = np.diff(p, n=3, axis=0)*hz**3
    length = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
    chord = float(np.linalg.norm(p[-1]-p[0]))
    stops = sum(float(np.linalg.norm(velocity[max(0, i-2):min(len(velocity), i+2)], axis=1).min()) < .005
                for i in waypoint_indices if 0 < i < len(p)-1)
    return {"waypoint_stops": stops, "jerk_rms_m_s3": float(np.sqrt(np.mean(np.sum(jerk**2, axis=1)))),
            "path_length_m": length, "endpoint_chord_m": chord,
            "path_to_chord_ratio": length/chord if chord > 1e-6 else None}
