"""Add Mesh > Fidget Star / Polygon, plus preset load/save."""

import json
import math
import os

import bpy
from bpy.props import StringProperty

from .. import properties
from ..ui.panel_poly_fidget import active_fidget, draw_all

ROOT_PACKAGE = __package__.rpartition(".")[0]
BUNDLED_PRESETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "presets")
ANGLE_PARAMS = {"wall_angle", "flange_angle"}   # stored in degrees in preset files


def _set_millimetres(scene):
    units = scene.unit_settings
    if units.system == 'METRIC' and units.scale_length == 1.0:
        units.scale_length = 0.001
        units.length_unit = 'MILLIMETERS'


def _execute(self, context):
    prefs = context.preferences.addons[ROOT_PACKAGE].preferences
    if prefs.set_scene_millimetres:
        _set_millimetres(context.scene)

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    mesh = bpy.data.meshes.new("Fidget")
    obj = bpy.data.objects.new("Fidget", mesh)
    obj.location = context.scene.cursor.location
    obj.poly_fidget.is_fidget = True
    properties.copy_params(self, obj.poly_fidget)
    error = properties.rebuild(obj)
    if error:
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
        self.report({'ERROR'}, error)
        return {'CANCELLED'}

    context.collection.objects.link(obj)
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return {'FINISHED'}


def _draw(self, context):
    draw_all(self.layout, self)


MESH_OT_poly_fidget_add = type("MESH_OT_poly_fidget_add", (bpy.types.Operator,), {
    "__annotations__": properties.param_annotations(),
    "bl_idname": "mesh.poly_fidget_add",
    "bl_label": "Fidget Star / Polygon",
    "bl_description": "Add a parametric print-in-place nested fidget",
    "bl_options": {'REGISTER', 'UNDO'},
    "execute": _execute,
    "draw": _draw,
})


def user_preset_dir():
    try:
        return bpy.utils.extension_path_user(ROOT_PACKAGE, path="presets", create=True)
    except ValueError:  # installed as a legacy add-on
        return bpy.utils.user_resource('CONFIG', path="poly_fidget_presets", create=True)


def _preset_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json"))


def _preset_label(path):
    return bpy.path.display_name(os.path.basename(path))


class POLYFIDGET_OT_preset_apply(bpy.types.Operator):
    bl_idname = "poly_fidget.preset_apply"
    bl_label = "Apply Preset"
    bl_description = "Load the settings stored in this preset"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return active_fidget(context) is not None

    def execute(self, context):
        obj = active_fidget(context)
        try:
            with open(self.filepath, encoding="utf-8") as f:
                values = json.load(f)
        except (OSError, ValueError) as exc:
            self.report({'ERROR'}, f"Could not read preset: {exc}")
            return {'CANCELLED'}
        for name in ANGLE_PARAMS & values.keys():
            values[name] = math.radians(values[name])
        properties.apply_params(obj.poly_fidget, values)
        error = properties.rebuild(obj)
        if error:
            self.report({'WARNING'}, error)
        return {'FINISHED'}


class POLYFIDGET_OT_preset_save(bpy.types.Operator):
    bl_idname = "poly_fidget.preset_save"
    bl_label = "Save Preset"
    bl_description = "Save the current fidget settings as a preset"

    name: StringProperty(name="Name", default="My Fidget")

    @classmethod
    def poll(cls, context):
        return active_fidget(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        s = active_fidget(context).poly_fidget
        values = {}
        for name in properties.PARAM_NAMES:
            value = getattr(s, name)
            values[name] = math.degrees(value) if name in ANGLE_PARAMS else value
        filename = bpy.path.clean_name(self.name).lower() + ".json"
        path = os.path.join(user_preset_dir(), filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(values, f, indent=2)
        self.report({'INFO'}, f"Saved preset {path}")
        return {'FINISHED'}


class POLYFIDGET_MT_presets(bpy.types.Menu):
    bl_label = "Fidget Presets"

    def draw(self, context):
        layout = self.layout
        bundled = _preset_files(BUNDLED_PRESETS)
        user = _preset_files(user_preset_dir())
        for path in bundled:
            layout.operator("poly_fidget.preset_apply", text=_preset_label(path)).filepath = path
        if user:
            layout.separator()
            for path in user:
                layout.operator("poly_fidget.preset_apply", text=_preset_label(path)).filepath = path


def menu_func(self, context):
    self.layout.operator(MESH_OT_poly_fidget_add.bl_idname, icon='SOLO_ON')


classes = (
    MESH_OT_poly_fidget_add,
    POLYFIDGET_OT_preset_apply,
    POLYFIDGET_OT_preset_save,
    POLYFIDGET_MT_presets,
)
