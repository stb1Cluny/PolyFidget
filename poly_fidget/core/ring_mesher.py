"""Ring cross-sections and bmesh construction.

Each ring is described by a cross-section in (d, z) space, where ``d`` is
the inward offset from the outer silhouette and ``z`` the height. Every
cross-section point becomes one boundary loop (``polygon_builder.boundary``
at offset ``d``) placed at height ``z``; consecutive loops are joined with
quads. Hollow rings form a closed loop of cross-section points, the solid
core is capped top and bottom.

Flange types (ring 0 is the outermost, ring N-1 the solid core):

* TELESCOPIC_DOWN: each inner ring has an outward lip at its top that hangs
  on the inward lip at the bottom of its outer neighbour, so lifting the
  outer ring lets the inner rings drop into a cone.
* TELESCOPIC_UP: the same profile mirrored in Z; inner rings rise.
* CAPTIVE_DUAL: an outward bump in the middle of each inner ring is trapped
  between inward lips at the top and bottom of its outer neighbour.

Every overhang is a chamfer at ``flange_angle`` from the build plate. The
SLANTED wall style leans every surface by ``wall_angle`` in the direction
that lets the rings slide apart freely until the lips catch.
"""

import math

import bmesh

from . import handle_builder
from . import polygon_builder as pb
from .polygon_builder import FitError, GeometryError

WELD_DISTANCE = 1e-4
MIN_CORE_RADIUS = 1.0
HANDLE_MARGIN = 0.8
MIN_LIP_OVERLAP = 0.4   # radial overlap of neighbouring lips, about one nozzle width


class Ring:
    def __init__(self, outer, inner):
        self.outer = outer      # [(d, z)] bottom to top
        self.inner = inner      # [(d, z)] bottom to top, None for the core

    @property
    def is_core(self):
        return self.inner is None

    def section(self):
        """Cross-section points in loft order, consecutive duplicates removed."""
        pts = list(self.outer)
        if self.inner is not None:
            pts += list(reversed(self.inner))
        out = []
        for p in pts:
            if not out or abs(p[0] - out[-1][0]) > 1e-7 or abs(p[1] - out[-1][1]) > 1e-7:
                out.append(p)
        if self.inner is not None and len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out


class Plan:
    """Rings plus the derived numbers shown in the UI."""

    def __init__(self, shape, rings, stats):
        self.shape = shape
        self.rings = rings
        self.stats = stats


def _wall_widths(p):
    widths = []
    hollow = p.ring_count - 1
    for i in range(hollow):
        if p.scaling_mode == 'GEOMETRIC':
            widths.append(p.wall_thickness * p.geometric_ratio ** (hollow - 1 - i))
        else:
            widths.append(p.wall_thickness)
    return widths


def plan_rings(p):
    shape = pb.make_base_shape(p.shape_type, p.point_count, p.outer_radius,
                               p.indent_ratio, p.corner_radius, p.resolution)

    n_rings = p.ring_count
    height = p.total_height
    depth = p.flange_depth
    land = p.lip_land
    lip_h = depth * math.tan(p.flange_angle)
    slanted = p.wall_style == 'SLANTED'
    lean = 1.0 / math.tan(p.wall_angle) if slanted else 0.0
    gap = p.clearance_xy / math.sin(p.wall_angle) if slanted else p.clearance_xy
    ftype = p.flange_type
    frame = p.enable_handle and p.handle_anchor == 'OUTER_FRAME'

    # Neighbouring lips overlap radially by depth - gap; keep enough to hold.
    if depth - gap < MIN_LIP_OVERLAP - 1e-6:
        max_clearance = depth - MIN_LIP_OVERLAP
        if slanted:
            max_clearance *= math.sin(p.wall_angle)
        raise GeometryError(
            f"XY Clearance too large: max {max_clearance:.2f} mm with this Flange Depth")
    core_handle = p.enable_handle and p.handle_anchor == 'INNER_CORE'

    if ftype == 'CAPTIVE_DUAL':
        slack = height / 2.0 - 1.5 * land - lip_h - p.clearance_z
        needed = 2.0 * (1.5 * land + lip_h + p.clearance_z)
    else:
        slack = height - 2.0 * land - lip_h - p.clearance_z
        needed = 2.0 * land + lip_h + p.clearance_z
    if slack < 0.0:
        raise GeometryError(
            f"Total height too small for these flanges (needs {needed:.2f} mm)")
    chamfer = min(p.foot_chamfer, 0.8 * land)

    walls = _wall_widths(p)
    offsets = [0.0]
    for w in walls:
        offsets.append(offsets[-1] + w + depth + gap)

    def down_profile(a, wall, top_lip, hollow):
        b = a + wall
        outer = [(a, 0.0)]
        if top_lip:
            outer += [(a, height - land - lip_h), (a - depth, height - land),
                      (a - depth, height)]
        else:
            outer.append((a, height))
        inner = None
        if hollow:
            inner = [(b + depth, 0.0), (b + depth, land), (b, land + lip_h), (b, height)]
        return outer, inner

    def captive_profile(a, wall, bump, hollow):
        b = a + wall
        mid = height / 2.0
        outer = [(a, 0.0)]
        if bump:
            outer += [(a, mid - land / 2.0 - lip_h), (a - depth, mid - land / 2.0),
                      (a - depth, mid + land / 2.0), (a, mid + land / 2.0 + lip_h)]
        outer.append((a, height))
        inner = None
        if hollow:
            inner = [(b + depth, 0.0), (b + depth, land), (b, land + lip_h),
                     (b, height - land - lip_h), (b + depth, height - land),
                     (b + depth, height)]
        return outer, inner

    def mirror(pts):
        return None if pts is None else [(d, height - z) for d, z in reversed(pts)]

    rings = []
    for i in range(n_rings):
        hollow = i < n_rings - 1
        wall = walls[i] if hollow else 0.0
        a = offsets[i]
        if ftype == 'CAPTIVE_DUAL':
            outer, inner = captive_profile(a, wall, i > 0, hollow)
        else:
            outer, inner = down_profile(a, wall, i > 0, hollow)
            if ftype == 'TELESCOPIC_UP':
                outer, inner = mirror(outer), mirror(inner)

        top = height
        if frame and i == 0:
            top = max(height, p.handle_height)
            outer = [(a - p.handle_diameter, 0.0), (a - p.handle_diameter, top)]
            if inner is not None and top > height + 1e-6:
                inner = inner + [(inner[-1][0], top)]

        if chamfer > 0.0:
            d0 = outer[0][0]
            outer = [(d0 + chamfer, 0.0), (d0, chamfer)] + outer[1:]
            if inner is not None:
                d0 = inner[0][0]
                inner = [(d0 - chamfer, 0.0), (d0, chamfer)] + inner[1:]

        if ftype == 'TELESCOPIC_UP':
            def shift(z):
                return (height - z) * lean
        else:
            def shift(z):
                return z * lean
        outer = [(d + shift(z), z) for d, z in outer]
        if inner is not None:
            inner = [(d + shift(z), z) for d, z in inner]
        rings.append(Ring(outer, inner))

    core = rings[-1]
    deepest = max(d for d, _ in core.outer)
    core_pts = pb.boundary(shape, deepest)
    core_min = pb.min_radius(core_pts)
    need = MIN_CORE_RADIUS
    if core_handle:
        need = max(need, p.handle_diameter / 2.0 + HANDLE_MARGIN)
        top_d = core.outer[-1][0]
        top_min = pb.min_radius(pb.boundary(shape, top_d))
        if top_min < p.handle_diameter / 2.0 + HANDLE_MARGIN:
            raise GeometryError(
                f"Handle too wide for the core (max diameter "
                f"{2.0 * (top_min - HANDLE_MARGIN):.1f} mm)")
    if core_min < need:
        raise FitError("The centre core would vanish")

    if ftype == 'CAPTIVE_DUAL':
        travel = 2.0 * (slack + p.clearance_z + gap * math.tan(p.flange_angle))
    else:
        travel = slack + p.clearance_z + gap * math.tan(p.flange_angle)
    shallowest = min(d for r in rings for d, _ in r.outer)
    footprint = max(math.hypot(x, y) for x, y in pb.boundary(shape, shallowest))
    stats = {
        "footprint": 2.0 * footprint,
        "core": 2.0 * core_min,
        "travel": travel,
        "extended": height + (0.0 if ftype == 'CAPTIVE_DUAL' else travel * (n_rings - 1)),
    }
    return Plan(shape, rings, stats)


class _Override:
    def __init__(self, base, **values):
        self._base = base
        self._values = values

    def __getattr__(self, name):
        if name in self._values:
            return self._values[name]
        return getattr(self._base, name)


def _plan_or_explain(p):
    try:
        return plan_rings(p)
    except FitError:
        pass
    for count in range(p.ring_count - 1, 1, -1):
        try:
            plan_rings(_Override(p, ring_count=count))
        except FitError:
            continue
        raise GeometryError(
            f"Too many rings: at most {count} fit with these settings")
    raise GeometryError(
        "Rings do not fit: enlarge the shape or reduce wall, flange or clearance")


def build_bmesh(p):
    """Build the whole fidget. Returns (bmesh, stats)."""
    plan = _plan_or_explain(p)
    shape = plan.shape
    cache = {}

    def loop_xy(d):
        key = round(d, 7)
        pts = cache.get(key)
        if pts is None:
            pts = cache[key] = pb.boundary(shape, d)
        return pts

    bm = bmesh.new()
    caps = []       # (bottom loop, top loop, top z) per core
    for ring in plan.rings:
        section = ring.section()
        loops = [[bm.verts.new((x, y, z)) for x, y in loop_xy(d)] for d, z in section]
        count = len(loops)
        pairs = count if not ring.is_core else count - 1
        for k in range(pairs):
            lower, upper = loops[k], loops[(k + 1) % count]
            m = len(lower)
            for j in range(m):
                jn = (j + 1) % m
                bm.faces.new((lower[j], lower[jn], upper[jn], upper[j]))
        if ring.is_core:
            caps.append((loops[0], loops[-1], section[-1][1]))

    # Coincident points (where a valley arc meets a rounded tip) leave
    # zero-width strips; weld them so the result stays clean and manifold.
    targets = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=WELD_DISTANCE)["targetmap"]
    bmesh.ops.weld_verts(bm, targetmap=targets)

    def resolve(loop):
        out = []
        for v in loop:
            v = targets.get(v, v)
            if not out or out[-1] is not v:
                out.append(v)
        if len(out) > 1 and out[0] is out[-1]:
            out.pop()
        return out

    core_handle = p.enable_handle and p.handle_anchor == 'INNER_CORE'
    for bottom, top, top_z in caps:
        bm.faces.new(resolve(bottom))
        top = resolve(top)
        if core_handle:
            base = handle_builder.build_handle(bm, p.handle_style, p.handle_height,
                                               p.handle_diameter, top_z)
            edges = []
            for loop in (top, base):
                for i in range(len(loop)):
                    edges.append(bm.edges.get((loop[i], loop[(i + 1) % len(loop)])))
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False,
                                    edges=edges, normal=(0.0, 0.0, 1.0))
        else:
            bm.faces.new(top)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, plan.stats
