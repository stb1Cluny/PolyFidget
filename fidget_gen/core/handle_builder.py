"""Centre grip geometry: plain, knurled and mushroom-cap posts.

Handles are built as stacks of vertex rings around the Z axis. The bottom
ring is returned so the caller can fill the core's top face around it,
which fuses the handle to the core without a boolean.
"""

import math

from .polygon_builder import GeometryError

KNURL_HELIX = 1.2   # vertical period per ridge, relative to the ridge spacing


def _ring(radius_fn, z, count):
    pts = []
    for i in range(count):
        a = 2.0 * math.pi * i / count
        r = radius_fn(a)
        pts.append((r * math.cos(a), r * math.sin(a), z))
    return pts


def _revolve(profile, count):
    """Rings for a lathe profile [(radius, z), ...]; radius 0 means apex."""
    rings = []
    apex = None
    for r, z in profile:
        if r <= 1e-9:
            apex = (0.0, 0.0, z)
            break
        rings.append(_ring(lambda a, r=r: r, z, count))
    return rings, apex


def _knurled(radius, height):
    depth = min(0.5, radius * 0.12)
    ridges = max(12, round(2.0 * math.pi * radius / 1.8))
    count = ridges * 6
    period = 2.0 * math.pi * radius / ridges * KNURL_HELIX
    chamfer = min(0.6, radius * 0.3, height * 0.2)
    top = height - chamfer
    fade_len = min(1.0, top * 0.25)

    def radius_at(a, z):
        u = ridges * a / (2.0 * math.pi)
        v1 = abs(2.0 * ((u + z / period) % 1.0) - 1.0)
        v2 = abs(2.0 * ((u - z / period) % 1.0) - 1.0)
        fade = min(1.0, z / fade_len, (top - z) / fade_len)
        return radius - depth + depth * min(v1, v2) * max(fade, 0.0)

    rows = max(2, math.ceil(top / (period / 8.0)))
    rings = []
    for k in range(rows + 1):
        z = top * k / rows
        rings.append(_ring(lambda a, z=z: radius_at(a, z), z, count))
    rings.append(_ring(lambda a: radius - depth - chamfer, height, count))
    return rings, None


def handle_rings(style, height, diameter, segments=64):
    """Return (rings, apex) in local coordinates with the base at z = 0."""
    radius = diameter / 2.0
    if style == 'KNURLED':
        return _knurled(radius, height)
    if style == 'MUSHROOM_CAP':
        cap = radius * 1.6
        flare = cap - radius           # 45 degree flare prints without support
        band = 1.0
        dome = cap * 0.5
        stem = height - flare - band - dome
        if stem < 1.0:
            raise GeometryError(
                f"Handle too short for a mushroom cap (needs {height - stem + 1.0:.1f} mm)")
        base = stem + flare + band
        profile = [(radius, 0.0), (radius, stem), (cap, stem + flare), (cap, base)]
        steps = 8
        for k in range(1, steps + 1):
            t = 0.5 * math.pi * k / steps
            profile.append((cap * math.cos(t), base + dome * math.sin(t)))
        profile[-1] = (0.0, height)
        return _revolve(profile, segments)
    chamfer = min(0.6, radius * 0.3, height * 0.2)
    return _revolve([(radius, 0.0), (radius, height - chamfer),
                     (radius - chamfer, height)], segments)


def build_handle(bm, style, height, diameter, z0, segments=64):
    """Add the handle to ``bm`` and return its bottom ring of BMVerts."""
    rings, apex = handle_rings(style, height, diameter, segments)
    vert_rings = [[bm.verts.new((x, y, z + z0)) for x, y, z in ring] for ring in rings]
    for lower, upper in zip(vert_rings, vert_rings[1:]):
        n = len(lower)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((lower[i], lower[j], upper[j], upper[i]))
    top = vert_rings[-1]
    if apex is not None:
        tip = bm.verts.new((apex[0], apex[1], apex[2] + z0))
        n = len(top)
        for i in range(n):
            bm.faces.new((top[i], top[(i + 1) % n], tip))
    else:
        bm.faces.new(top)
    return vert_rings[0]
