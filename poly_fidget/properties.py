"""Fidget parameters, shared by the Add Mesh operator and the object settings.

The same definitions feed two classes: the operator (redo panel) and a
PropertyGroup stored on each generated object, whose update callback
rebuilds the mesh so the sidebar sliders work in real time.
"""

import math

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

from .core import ring_mesher
from .core.polygon_builder import GeometryError

SHAPE_ITEMS = [
    ('STAR', "Star", "Pointed star"),
    ('POLYGON', "Polygon", "Regular polygon"),
    ('FLUTED', "Fluted", "Smooth wavy outline"),
]
SCALING_ITEMS = [
    ('LINEAR', "Linear", "Every ring has the same wall thickness"),
    ('GEOMETRIC', "Geometric", "Walls get thicker towards the outside by a fixed ratio"),
]
WALL_STYLE_ITEMS = [
    ('VERTICAL', "Vertical", "Straight walls with chamfered retaining lips"),
    ('SLANTED', "Slanted", "Walls lean at the wall angle, with retaining lips"),
]
FLANGE_ITEMS = [
    ('TELESCOPIC_DOWN', "Telescopic Down", "Inner rings drop below the outer ring"),
    ('TELESCOPIC_UP', "Telescopic Up", "Inner rings rise above the outer ring"),
    ('CAPTIVE_DUAL', "Captive Dual", "Rings are trapped with limited play both ways"),
]
HANDLE_STYLE_ITEMS = [
    ('CYLINDER', "Cylinder", "Plain post with a chamfered top"),
    ('KNURLED', "Knurled", "Post with a diamond knurl"),
    ('MUSHROOM_CAP', "Mushroom Cap", "Post with a domed cap"),
]
HANDLE_ANCHOR_ITEMS = [
    ('INNER_CORE', "Inner Core", "Grip post on top of the centre core"),
    ('OUTER_FRAME', "Outer Frame", "Thick, tall outer ring that acts as a cradle"),
]

# Names in UI order; also the keys used by presets.
PARAM_NAMES = (
    "shape_type", "point_count", "outer_radius", "indent_ratio", "corner_radius",
    "ring_count", "wall_thickness", "clearance_xy", "scaling_mode", "geometric_ratio",
    "total_height", "wall_style", "wall_angle", "flange_angle", "flange_depth",
    "flange_type", "clearance_z", "lip_land", "foot_chamfer",
    "enable_handle", "handle_style", "handle_height", "handle_diameter", "handle_anchor",
    "resolution",
)


def _length(name, default, lo, hi, desc, update):
    return FloatProperty(name=name, description=desc, default=default, min=lo, max=hi,
                         subtype='DISTANCE', unit='LENGTH', precision=2, step=10,
                         update=update)


def _angle(name, default, lo, hi, desc, update):
    return FloatProperty(name=name, description=desc, default=math.radians(default),
                         min=math.radians(lo), max=math.radians(hi),
                         subtype='ANGLE', update=update)


def param_annotations(update=None):
    u = update
    return {
        "shape_type": EnumProperty(name="Shape", items=SHAPE_ITEMS, default='STAR', update=u),
        "point_count": IntProperty(name="Points", description="Star points or polygon vertices",
                                   default=5, min=3, max=16, update=u),
        "outer_radius": _length("Outer Radius", 45.0, 10.0, 200.0,
                                "Footprint radius of the outermost ring", u),
        "indent_ratio": FloatProperty(name="Indent Ratio",
                                      description="Inner-to-outer point ratio of the star",
                                      default=0.45, min=0.10, max=0.95, update=u),
        "corner_radius": _length("Corner Radius", 1.5, 0.0, 10.0,
                                 "Fillet radius on points and valleys", u),

        "ring_count": IntProperty(name="Rings", description="Nested shells, including the solid core",
                                  default=6, min=2, max=30, update=u),
        "wall_thickness": _length("Wall Thickness", 1.2, 0.8, 5.0,
                                  "Radial thickness of each ring wall", u),
        "clearance_xy": _length("XY Clearance", 0.4, 0.2, 1.0,
                                "Air gap between neighbouring rings", u),
        "scaling_mode": EnumProperty(name="Scaling", items=SCALING_ITEMS, default='LINEAR', update=u),
        "geometric_ratio": FloatProperty(name="Ratio",
                                         description="Wall growth per ring, from the core outwards",
                                         default=1.1, min=1.0, max=1.5, update=u),

        "total_height": _length("Total Height", 10.0, 4.0, 50.0,
                                "Height of the assembly when collapsed flat", u),
        "wall_style": EnumProperty(name="Walls", items=WALL_STYLE_ITEMS, default='VERTICAL', update=u),
        "wall_angle": _angle("Wall Angle", 75.0, 45.0, 89.0,
                             "Lean of slanted walls, measured from the build plate", u),
        "flange_angle": _angle("Flange Angle", 45.0, 30.0, 60.0,
                               "Overhang angle of the lips, measured from the build plate", u),
        "flange_depth": _length("Flange Depth", 1.0, 0.4, 3.0,
                                "Radial width of the interlocking lip", u),
        "flange_type": EnumProperty(name="Flange Type", items=FLANGE_ITEMS,
                                    default='TELESCOPIC_DOWN', update=u),
        "clearance_z": _length("Z Clearance", 0.4, 0.2, 0.8,
                               "Vertical gap between interlocking lips", u),
        "lip_land": _length("Lip Land", 0.8, 0.4, 3.0,
                            "Height of the flat edge on each lip", u),
        "foot_chamfer": _length("Foot Chamfer", 0.3, 0.0, 1.0,
                                "Bottom edge chamfer against elephant's foot fusing", u),

        "enable_handle": BoolProperty(name="Handle", description="Add a grip", default=False, update=u),
        "handle_style": EnumProperty(name="Style", items=HANDLE_STYLE_ITEMS, default='CYLINDER', update=u),
        "handle_height": _length("Height", 15.0, 5.0, 60.0,
                                 "Height of the grip above the core, or total frame height", u),
        "handle_diameter": _length("Diameter", 8.0, 3.0, 25.0,
                                   "Diameter of the post, or width of the outer frame", u),
        "handle_anchor": EnumProperty(name="Anchor", items=HANDLE_ANCHOR_ITEMS,
                                      default='INNER_CORE', update=u),

        "resolution": IntProperty(name="Corner Segments", description="Segments per rounded corner",
                                  default=8, min=2, max=32, update=u),
    }


_suspend_updates = False


def copy_params(src, dst):
    """Copy every parameter, rebuilding only once at the end."""
    global _suspend_updates
    _suspend_updates = True
    try:
        for name in PARAM_NAMES:
            setattr(dst, name, getattr(src, name))
    finally:
        _suspend_updates = False


def apply_params(dst, values):
    global _suspend_updates
    _suspend_updates = True
    try:
        for name, value in values.items():
            if name in PARAM_NAMES:
                setattr(dst, name, value)
    finally:
        _suspend_updates = False


def rebuild(obj):
    """Regenerate ``obj``'s mesh from its settings. Returns an error or None."""
    settings = obj.poly_fidget
    if obj.mode == 'EDIT':
        settings.status = "Leave Edit Mode to update the fidget"
        return settings.status
    try:
        bm, stats = ring_mesher.build_bmesh(settings)
    except GeometryError as exc:
        settings.status = str(exc)
        return settings.status
    try:
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()
    settings.status = ""
    settings.stat_footprint = stats["footprint"]
    settings.stat_core = stats["core"]
    settings.stat_travel = stats["travel"]
    settings.stat_extended = stats["extended"]
    return None


def _on_update(self, context):
    if _suspend_updates:
        return
    obj = self.id_data
    if isinstance(obj, bpy.types.Object) and self.is_fidget:
        rebuild(obj)


def _stat(name):
    return FloatProperty(name=name, subtype='DISTANCE', unit='LENGTH')


PolyFidgetSettings = type("PolyFidgetSettings", (bpy.types.PropertyGroup,), {
    "__annotations__": {
        **param_annotations(update=_on_update),
        "is_fidget": BoolProperty(default=False, options={'HIDDEN'}),
        "status": StringProperty(name="Status"),
        "stat_footprint": _stat("Footprint"),
        "stat_core": _stat("Core Size"),
        "stat_travel": _stat("Travel per Ring"),
        "stat_extended": _stat("Extended Height"),
    },
})


def register():
    bpy.utils.register_class(PolyFidgetSettings)
    bpy.types.Object.poly_fidget = PointerProperty(type=PolyFidgetSettings)


def unregister():
    del bpy.types.Object.poly_fidget
    bpy.utils.unregister_class(PolyFidgetSettings)
