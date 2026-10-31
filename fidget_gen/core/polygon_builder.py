"""2D profile generation: base silhouettes, corner fillets and inward offsets.

All values are millimetres (1 Blender unit = 1 mm). Shapes are regular and
centred on the origin. Every edge of a regular polygon or star lies at the
same distance (the apothem ``h``) from the centre, so offsetting all edges by
``d`` is a uniform scale of the sharp corners by ``(h - d) / h``.

The boundary at offset ``d`` is the morphological *opening* of the eroded base
shape: ``open_r(erode_d(S))``. In practice that means:

* convex corners always keep the base corner radius (nozzle friendly),
* concave corners grow to ``r + d`` (the exact offset, which keeps clearances),
* when a concave fillet swallows the neighbouring edge, the tip is rebuilt
  from the exact eroded shape (two valley arcs meeting) and rounded again.

Opening by a fixed radius never brings two offset boundaries closer than
their offset difference, so wall thickness and clearance are never reduced.
Every boundary has the same vertex count, so loops can be lofted directly.
"""

import math

MIN_RADIUS = 0.05       # radius used for "sharp" corners, avoids degenerate arcs
MIN_STRAIGHT = 0.005    # fraction of an edge kept straight when clamping
FLUTED_STRAIGHT = 0.02  # fraction of each edge left straight on fluted shapes


class GeometryError(ValueError):
    """Raised when the parameters cannot produce a valid shape."""


class FitError(GeometryError):
    """Raised when the rings leave no room for the centre core."""


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, s):
    return (a[0] * s, a[1] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _length(a):
    return math.hypot(a[0], a[1])


def _norm(a):
    length = _length(a)
    return (a[0] / length, a[1] / length)


class BaseShape:
    """Sharp regular silhouette plus the per-corner fillet radii at offset 0."""

    def __init__(self, corners, radii, segments):
        self.corners = corners
        self.radii = radii
        self.segments = segments
        m = len(corners)
        self.convex = []
        self.half_angle = []    # half of the (non-reflex) angle between edges
        self.bisector = []
        for k in range(m):
            p = corners[k]
            u = _norm(_sub(corners[k - 1], p))
            v = _norm(_sub(corners[(k + 1) % m], p))
            phi = math.acos(max(-1.0, min(1.0, _dot(u, v))))
            self.half_angle.append(phi / 2.0)
            self.bisector.append(_norm(_add(u, v)))
            edge_in = _sub(p, corners[k - 1])
            edge_out = _sub(corners[(k + 1) % m], p)
            self.convex.append(_cross(edge_in, edge_out) > 0.0)
        a, b = corners[0], corners[1]
        self.apothem = abs(_cross(a, b)) / _length(_sub(b, a))
        # Opening radius: the convex radius every inner boundary keeps.
        convex_radii = [r for r, c in zip(radii, self.convex) if c]
        self.round_radius = min(convex_radii) if convex_radii else MIN_RADIUS

    @property
    def points_per_loop(self):
        return len(self.corners) * (self.segments + 1)


def make_base_shape(shape_type, point_count, outer_radius, indent_ratio,
                    corner_radius, segments):
    n = point_count
    corners = []
    if shape_type == 'POLYGON':
        for k in range(n):
            a = math.pi / 2.0 + 2.0 * math.pi * k / n
            corners.append((outer_radius * math.cos(a), outer_radius * math.sin(a)))
    else:
        for k in range(2 * n):
            a = math.pi / 2.0 + math.pi * k / n
            r = outer_radius if k % 2 == 0 else outer_radius * indent_ratio
            corners.append((r * math.cos(a), r * math.sin(a)))

    m = len(corners)
    if shape_type == 'FLUTED':
        # Fully rounded star: lobes and valleys share one radius that uses up
        # nearly the whole edge, giving a smooth wavy outline.
        probe = BaseShape(corners, [MIN_RADIUS] * m, segments)
        edge = _length(_sub(corners[1], corners[0]))
        cot_sum = (1.0 / math.tan(probe.half_angle[0])
                   + 1.0 / math.tan(probe.half_angle[1]))
        radius = edge * (1.0 - FLUTED_STRAIGHT) / cot_sum
        return BaseShape(corners, [radius] * m, segments * 2)

    radius = max(corner_radius, MIN_RADIUS)
    return BaseShape(corners, [radius] * m, segments)


def boundary(shape, d):
    """Closed CCW loop (list of (x, y)) of the shape offset inward by ``d``.

    Negative ``d`` grows the shape outward (used for the outer frame).
    """
    h = shape.apothem
    if d >= h - 1e-6:
        raise FitError("Rings do not fit inside the base shape")
    scale = (h - d) / h
    m = len(shape.corners)
    q = [_mul(c, scale) for c in shape.corners]
    rr = shape.round_radius

    # Desired fillet radius per corner (case A: fillets tangent to the
    # offset edges).
    rho = []
    for k in range(m):
        r = shape.radii[k]
        if shape.convex[k]:
            rho.append(r - d if d < 0.0 else max(r, rr))
        else:
            rho.append(max(r + d, MIN_RADIUS))

    def center(k, radius):
        return _add(q[k], _mul(shape.bisector[k], radius / math.sin(shape.half_angle[k])))

    # Case B: a valley arc swallows the edge next to a convex tip. The exact
    # eroded tip is where the two valley circles (grown by the rounding
    # radius) cross the tip axis; round it again with radius ``rr``.
    tip_center = {}
    if d > 0.0:
        for k in range(m):
            if not shape.convex[k]:
                continue
            t_a = center(k, rr)
            axis = _norm(shape.corners[k])
            lowest = None
            for j in ((k - 1) % m, (k + 1) % m):
                if shape.convex[j]:
                    continue
                cv = center(j, rho[j])
                big_r = rho[j] + rr
                if _length(_sub(t_a, cv)) >= big_r:
                    continue
                ac = _dot(axis, cv)
                disc = ac * ac - _dot(cv, cv) + big_r * big_r
                s = ac - math.sqrt(max(disc, 0.0))
                if s <= 1e-6:
                    raise FitError("Rings do not fit inside the base shape")
                lowest = s if lowest is None else min(lowest, s)
            if lowest is not None:
                tip_center[k] = _mul(axis, lowest)

    # Tangent distances for case A corners, clamped so fillets fit on edges.
    tan_len = [rho[k] / math.tan(shape.half_angle[k]) for k in range(m)]
    for k in range(m):
        j = (k + 1) % m
        if k in tip_center or j in tip_center:
            continue
        avail = _length(_sub(q[j], q[k])) * (1.0 - MIN_STRAIGHT)
        total = tan_len[k] + tan_len[j]
        if total > avail:
            f = avail / total
            tan_len[k] *= f
            tan_len[j] *= f
    for k in range(m):
        if k not in tip_center:
            rho[k] = tan_len[k] * math.tan(shape.half_angle[k])

    centers = []
    starts = []
    ends = []
    for k in range(m):
        if k in tip_center:
            centers.append(tip_center[k])
        else:
            centers.append(center(k, rho[k]))
    for k in range(m):
        prev_k, next_k = (k - 1) % m, (k + 1) % m
        u = _norm(_sub(q[prev_k], q[k]))
        v = _norm(_sub(q[next_k], q[k]))
        if k in tip_center:
            t = tip_center[k]
            starts.append(_add(t, _mul(_norm(_sub(centers[prev_k], t)), rr)))
            ends.append(_add(t, _mul(_norm(_sub(centers[next_k], t)), rr)))
            rho[k] = rr
        else:
            if prev_k in tip_center:
                t = tip_center[prev_k]
                starts.append(_add(t, _mul(_norm(_sub(centers[k], t)), rr)))
            else:
                starts.append(_add(q[k], _mul(u, tan_len[k])))
            if next_k in tip_center:
                t = tip_center[next_k]
                ends.append(_add(t, _mul(_norm(_sub(centers[k], t)), rr)))
            else:
                ends.append(_add(q[k], _mul(v, tan_len[k])))

    pts = []
    seg = shape.segments
    for k in range(m):
        c = centers[k]
        a1 = math.atan2(starts[k][1] - c[1], starts[k][0] - c[0])
        a2 = math.atan2(ends[k][1] - c[1], ends[k][0] - c[0])
        if shape.convex[k]:
            delta = (a2 - a1) % (2.0 * math.pi)
            if delta > 2.0 * math.pi - 1e-9:
                delta = 0.0
        else:
            delta = -((a1 - a2) % (2.0 * math.pi))
            if delta < -2.0 * math.pi + 1e-9:
                delta = 0.0
        radius = _length(_sub(starts[k], c))
        for s in range(seg + 1):
            a = a1 + delta * s / seg
            pts.append((c[0] + radius * math.cos(a), c[1] + radius * math.sin(a)))
    return pts


def min_radius(pts):
    return min(math.hypot(x, y) for x, y in pts)
