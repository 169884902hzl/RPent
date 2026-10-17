"""C3 piecewise-quintic Cartesian references with vector derivative limits.

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
        squared = np.zeros(1)
        for axis in c.T:
            squared = poly.polyadd(squared, poly.polymul(axis, axis))
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


def quintic_transition(p0, p1, v0, v1, a0, a1, duration, *, j0=None, j1=None):
    """Quintic spline with continuous jerk, including rest/chunk boundaries.

    Two internal knots supply the degrees of freedom missing from a single
    quintic when position, velocity, acceleration AND jerk are constrained.
    This is an interpolating smooth trajectory, not a global optimality claim.
    """
    from scipy.interpolate import PPoly, make_interp_spline

    p0, p1, v0, v1, a0, a1 = map(lambda x: np.asarray(x, float), (p0, p1, v0, v1, a0, a1))
    zero = np.zeros_like(p0)
    j0 = zero if j0 is None else np.asarray(j0, float)
    j1 = zero if j1 is None else np.asarray(j1, float)
    knots = np.r_[np.zeros(6), 1/3, 2/3, np.ones(6)]
    curve = make_interp_spline([0., 1.], [p0, p1], k=5, t=knots,
        bc_type=([(1, v0*duration), (2, a0*duration**2), (3, j0*duration**3)],
                 [(1, v1*duration), (2, a1*duration**2), (3, j1*duration**3)]))
    polynomials = [PPoly.from_spline((curve.t, curve.c[:, axis], curve.k)) for axis in range(len(p0))]
    segments = []
    for index, (left, right) in enumerate(zip(curve.t[:-1], curve.t[1:])):
        width = right-left
        if width > 0:
            coefficients = np.stack([poly.c[:, index][::-1] for poly in polynomials], axis=1)
            coefficients *= width**np.arange(len(coefficients))[:, None]
            segments.append(Segment(coefficients, float(duration*width)))
    return segments


@dataclass
class Trajectory:
    segments: list[Segment]
    waypoint_times: list[float] | None = None

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
         minimum_duration: float = .1, initial_derivatives=None) -> Trajectory:
    """Fit C3 quintic transitions, retiming until all norm limits hold.

    Each coordinate group blends independently, without mixing units. A
    reversal or a stationary adjacent leg stops that group at the waypoint.
    Otherwise its tangent bisector passes through with common velocity and
    zero acceleration.
    """
    points = np.asarray(waypoints, float)
    if points.ndim != 2 or len(points) < 2 or not np.isfinite(points).all():
        raise ValueError("at least two finite waypoint vectors required")
    times = np.maximum.reduce([np.full(len(points)-1, minimum_duration),
        *[np.linalg.norm(np.diff(points[:, indices], axis=0), axis=1)/limit.velocity for indices, limit in groups]])
    for _ in range(20):
        velocities = np.zeros_like(points)
        if blend:
            for i in range(1, len(points)-1):
                for indices, _ in groups:
                    incoming = points[i, indices]-points[i-1, indices]
                    outgoing = points[i+1, indices]-points[i, indices]
                    n0, n1 = np.linalg.norm(incoming), np.linalg.norm(outgoing)
                    if n0 > 1e-9 and n1 > 1e-9 and np.dot(incoming, outgoing)/(n0*n1) > -.1:
                        tangent = incoming/n0 + outgoing/n1
                        velocities[i, indices] = tangent/np.linalg.norm(tangent) * .6 * min(n0/times[i-1], n1/times[i])
        zero = np.zeros(points.shape[1])
        v0, a0, j0 = (zero, zero, zero) if initial_derivatives is None else tuple(np.asarray(v, float) for v in initial_derivatives)
        if any(v.shape != zero.shape or not np.isfinite(v).all() for v in (v0, a0, j0)):
            raise ValueError("initial derivatives must match finite waypoint vectors")
        velocities[0] = v0
        segments = [segment for i, (a, b) in enumerate(zip(points[:-1], points[1:]))
                    for segment in quintic_transition(a, b, velocities[i], velocities[i+1], a0 if i == 0 else zero,
                        zero, times[i], j0=j0 if i == 0 else zero)]
        ratio = max([1., *[segment.maximum(d, indices)**(1/d) / bound**(1/d)
                     for segment in segments for indices, limit in groups
                     for d, bound in enumerate((limit.velocity, limit.acceleration, limit.jerk), 1)]])
        if ratio <= 1.000001:
            return Trajectory(segments, np.cumsum(times).tolist())
        # With inherited v/a/j, increasing duration also increases the
        # normalized boundary coefficients. The usual rest-to-rest scaling
        # ratio is no longer a guaranteed improvement. Bound each search
        # step so an infeasible retarget reaches the explicit nonconvergence
        # result instead of overflowing before the adapter can brake.
        times *= min(ratio, 1.5) * 1.001
    raise RuntimeError("quintic retiming did not converge")


def brake(position, velocity, acceleration, *, jerk=None, limits: Limits = Limits()) -> Trajectory:
    """Continuous p/v/a/j stop from a measured public state (no abrupt zero)."""
    p, v, a = map(lambda x: np.asarray(x, float), (position, velocity, acceleration))
    j = np.zeros_like(p) if jerk is None else np.asarray(jerk, float)
    if np.linalg.norm(j) > 1e-9:
        # Remove inherited jerk over one control interval before time-scaling
        # the remainder. Scaling a nonzero boundary jerk with the whole stop
        # duration can instead make acceleration grow without bound.
        interval = .05
        ramp = Segment(np.array([p, v*interval, a*interval**2/2,
            j*interval**3/6, -j*interval**3/24, np.zeros_like(p)]), interval)
        tail = brake(ramp.at(interval), ramp.at(interval, 1), ramp.at(interval, 2), limits=limits)
        return Trajectory([ramp, *tail.segments])
    if np.linalg.norm(a) > 1e-9:
        # Cancelling acceleration first is a convergent upper bound, but
        # discards useful inherited deceleration and can overshoot the
        # workspace. Try a direct continuous stop within that time bound.
        duration = max(.05, 1.5*np.linalg.norm(a)/limits.jerk)
        cancel = Segment(np.array([p, v*duration, a*duration**2/2,
            np.zeros_like(p), -a*duration**2/4, a*duration**2/10]), duration)
        tail = brake(cancel.at(duration), cancel.at(duration, 1), np.zeros_like(a), limits=limits)
        split = Trajectory([cancel, *tail.segments])
        duration = max(.15, 2*np.linalg.norm(v)/limits.acceleration,
                       2*np.sqrt(np.linalg.norm(v)/limits.jerk))
        bounds = (max(limits.velocity, np.linalg.norm(v)+np.linalg.norm(a)**2/(2*limits.jerk)),
                  max(limits.acceleration, np.linalg.norm(a)), limits.jerk)
        while duration < split.duration:
            end = p + .5*v*duration + a*duration**2/12
            direct = quintic_transition(p, end, v, np.zeros_like(v), a, np.zeros_like(a), duration)
            if all(segment.maximum(d, slice(None)) <= bound*1.00001
                   for segment in direct for d, bound in enumerate(bounds, 1)):
                return Trajectory(direct)
            duration *= 1.05
        # Outward acceleration can make direct time-scaling diverge; keep
        # the bounded split stop when no shorter direct stop passes.
        return split
    duration = max(.15, 2*np.linalg.norm(v)/limits.acceleration,
                   2*np.sqrt(np.linalg.norm(v)/limits.jerk), 2*np.linalg.norm(a)/limits.jerk)
    for _ in range(30):
        end = p + .5*v*duration + a*duration**2/12
        segments = quintic_transition(p, end, v, np.zeros_like(v), a, np.zeros_like(a), duration, j0=j)
        # An inherited overspeed cannot disappear instantly; the initial
        # measured derivative is explicitly allowed while decelerating.
        # An outward initial acceleration requires a finite speed increment
        # while jerk brings it to zero. Do not pretend the inherited state
        # can instantaneously satisfy the nominal speed limit.
        bounds = (max(limits.velocity, np.linalg.norm(v)+np.linalg.norm(a)**2/(2*limits.jerk)),
                  max(limits.acceleration, np.linalg.norm(a)),
                  max(limits.jerk, np.linalg.norm(j)))
        if all(segment.maximum(d, slice(None)) <= bound*1.00001
               for segment in segments for d, bound in enumerate(bounds, 1)):
            return Trajectory(segments)
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
