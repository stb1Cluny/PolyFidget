"""PolyFidget: parametric print-in-place nested fidget stars and polygons."""

import bpy

from . import operators, properties, ui
from .operators import op_create_fidget


class PolyFidgetPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    set_scene_millimetres: bpy.props.BoolProperty(
        name="Use Millimetres",
        description=("Switch metric scenes still at 1 unit = 1 m to millimetres when "
                     "adding a fidget, so sizes match the slicer"),
        default=True,
    )

    def draw(self, context):
        self.layout.prop(self, "set_scene_millimetres")


classes = (PolyFidgetPreferences,) + operators.classes + ui.classes


def register():
    properties.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_mesh_add.append(op_create_fidget.menu_func)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(op_create_fidget.menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    properties.unregister()
