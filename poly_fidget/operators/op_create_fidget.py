"""Add Mesh > Fidget Star / Polygon, plus preset apply/save/rename/delete."""

import json
import math
import os

import bpy
from bpy.props import StringProperty

from .. import presets, properties
from ..ui.panel_poly_fidget import active_fidget, draw_all

ROOT_PACKAGE = presets.ROOT_PACKAGE
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


def _check_name(name):
    """Error message for an unusable user preset name, or "" if it is fine."""
    if not presets.user_path(name):
        return "Enter a preset name"
    if name.strip().lower() in presets.bundled_labels():
        return f'"{name.strip()}" is a built-in preset name, choose another'
    return ""


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
        presets.set_active(self.filepath)
        error = properties.rebuild(obj)
        if error:
            self.report({'WARNING'}, error)
        return {'FINISHED'}


class POLYFIDGET_OT_preset_save(bpy.types.Operator):
    bl_idname = "poly_fidget.preset_save"
    bl_label = "Save Preset"
    bl_description = ("Save the current fidget settings as a preset. Saving under an "
                      "existing name overwrites that preset")

    name: StringProperty(name="Name", default="My Fidget")

    @classmethod
    def poll(cls, context):
        return active_fidget(context) is not None

    def invoke(self, context, event):
        current = presets.active_user()
        if current:
            self.name = presets.label(current)
        return context.window_manager.invoke_props_dialog(self, confirm_text="Save")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        error = _check_name(self.name)
        path = presets.user_path(self.name)
        if error:
            layout.label(text=error, icon='ERROR')
        elif os.path.isfile(path):
            layout.label(text=f'Overwrites the preset "{presets.label(path)}"', icon='INFO')

    def execute(self, context):
        error = _check_name(self.name)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        s = active_fidget(context).poly_fidget
        values = {}
        for name in properties.PARAM_NAMES:
            value = getattr(s, name)
            values[name] = math.degrees(value) if name in ANGLE_PARAMS else value
        path = presets.user_path(self.name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(values, f, indent=2)
        presets.set_active(path)
        self.report({'INFO'}, f'Saved preset "{presets.label(path)}"')
        return {'FINISHED'}


class POLYFIDGET_OT_preset_rename(bpy.types.Operator):
    bl_idname = "poly_fidget.preset_rename"
    bl_label = "Rename Preset"
    bl_description = "Rename the active user preset"

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        if not presets.active_user():
            cls.poll_message_set("Apply or save one of your own presets first")
            return False
        return True

    def invoke(self, context, event):
        self.name = presets.label(presets.active_user())
        return context.window_manager.invoke_props_dialog(self, confirm_text="Rename")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        error = self._error()
        if error:
            layout.label(text=error, icon='ERROR')

    def _error(self):
        error = _check_name(self.name)
        if error:
            return error
        old, new = presets.active_user(), presets.user_path(self.name)
        if os.path.normcase(new) != os.path.normcase(old) and os.path.exists(new):
            return f'A preset named "{presets.label(new)}" already exists'
        return ""

    def execute(self, context):
        error = self._error()
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        old, new = presets.active_user(), presets.user_path(self.name)
        os.replace(old, new)
        presets.set_active(new)
        self.report({'INFO'}, f'Renamed preset to "{presets.label(new)}"')
        return {'FINISHED'}


class POLYFIDGET_OT_preset_remove(bpy.types.Operator):
    bl_idname = "poly_fidget.preset_remove"
    bl_label = "Delete Preset"
    bl_description = "Delete the active user preset. Built-in presets can't be deleted"

    @classmethod
    def poll(cls, context):
        if not presets.active_user():
            cls.poll_message_set("Apply one of your own presets first")
            return False
        return True

    def invoke(self, context, event):
        name = presets.label(presets.active_user())
        return context.window_manager.invoke_confirm(
            self, event, title="Delete Preset", message=f'Delete the preset "{name}"?',
            confirm_text="Delete", icon='WARNING')

    def execute(self, context):
        path = presets.active_user()
        os.remove(path)
        presets.set_active("")
        self.report({'INFO'}, f'Deleted preset "{presets.label(path)}"')
        return {'FINISHED'}


class POLYFIDGET_MT_presets(bpy.types.Menu):
    bl_label = "Fidget Presets"

    def draw(self, context):
        layout = self.layout
        user = presets.files(presets.user_dir())
        for path in presets.files(presets.BUNDLED_DIR):
            layout.operator("poly_fidget.preset_apply", text=presets.label(path)).filepath = path
        if user:
            layout.separator()
            for path in user:
                layout.operator("poly_fidget.preset_apply", text=presets.label(path)).filepath = path


def menu_func(self, context):
    self.layout.operator(MESH_OT_poly_fidget_add.bl_idname, icon='SOLO_ON')


classes = (
    MESH_OT_poly_fidget_add,
    POLYFIDGET_OT_preset_apply,
    POLYFIDGET_OT_preset_save,
    POLYFIDGET_OT_preset_rename,
    POLYFIDGET_OT_preset_remove,
    POLYFIDGET_MT_presets,
)
