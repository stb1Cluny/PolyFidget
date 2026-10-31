"""3D print helpers: ground alignment, cross-section view, checks and STL export."""

import bmesh
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

from ..ui.panel_fidget_gen import active_fidget

SECTION_MODIFIER = "FidgetGen Section"
SECTION_CUTTER = "FidgetGen Section Cutter"


class FidgetOperator:
    @classmethod
    def poll(cls, context):
        return active_fidget(context) is not None


class FIDGETGEN_OT_align_ground(FidgetOperator, bpy.types.Operator):
    bl_idname = "fidget_gen.align_ground"
    bl_label = "Align to Ground"
    bl_description = "Move the fidget so its lowest point sits at Z = 0"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_fidget(context)
        lowest = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
        obj.location.z -= lowest
        return {'FINISHED'}


def _cutter_mesh(size):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x + 0.5, v.co.y, v.co.z)) * size
    mesh = bpy.data.meshes.new(SECTION_CUTTER)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


class FIDGETGEN_OT_section_toggle(FidgetOperator, bpy.types.Operator):
    bl_idname = "fidget_gen.section_toggle"
    bl_label = "Toggle Cross-Section"
    bl_description = ("Cut away half of the fidget in the viewport to inspect ring "
                      "clearances. Move or rotate the cutter to change the plane. "
                      "Never exported")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_fidget(context)
        mod = obj.modifiers.get(SECTION_MODIFIER)
        if mod is not None:
            cutter = mod.object
            obj.modifiers.remove(mod)
            if cutter is not None:
                mesh = cutter.data
                bpy.data.objects.remove(cutter)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            return {'FINISHED'}

        size = max(obj.dimensions) * 3.0 + 10.0
        cutter = bpy.data.objects.new(SECTION_CUTTER, _cutter_mesh(size))
        for collection in obj.users_collection:
            collection.objects.link(cutter)
        cutter.parent = obj
        cutter.display_type = 'WIRE'
        cutter.hide_render = True
        mod = obj.modifiers.new(SECTION_MODIFIER, 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        solvers = {i.identifier for i in mod.bl_rna.properties["solver"].enum_items}
        mod.solver = 'MANIFOLD' if 'MANIFOLD' in solvers else 'EXACT'
        mod.show_render = False   # STL export evaluates render settings
        return {'FINISHED'}


def mesh_report(mesh):
    """Return (non_manifold_edges, degenerate_faces, shells) for ``mesh``."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    bm.verts.ensure_lookup_table()
    seen = set()
    shells = 0
    for v in bm.verts:
        if v.index in seen:
            continue
        shells += 1
        stack = [v]
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other.index not in seen:
                    seen.add(other.index)
                    stack.append(other)
    bm.free()
    return non_manifold, degenerate, shells


class FIDGETGEN_OT_check_manifold(FidgetOperator, bpy.types.Operator):
    bl_idname = "fidget_gen.check_manifold"
    bl_label = "Check Printability"
    bl_description = "Check that the mesh is watertight and count the separate parts"

    def execute(self, context):
        non_manifold, degenerate, shells = mesh_report(active_fidget(context).data)
        if non_manifold or degenerate:
            self.report({'WARNING'}, f"{non_manifold} non-manifold edges, "
                                     f"{degenerate} degenerate faces, {shells} parts")
        else:
            self.report({'INFO'}, f"Watertight: {shells} separate parts")
        return {'FINISHED'}


class FIDGETGEN_OT_export_stl(FidgetOperator, bpy.types.Operator, ExportHelper):
    bl_idname = "fidget_gen.export_stl"
    bl_label = "Export STL"
    bl_description = "Export the active fidget as an STL in millimetres"

    filename_ext = ".stl"
    filter_glob: StringProperty(default="*.stl", options={'HIDDEN'})

    def invoke(self, context, event):
        self.filepath = bpy.path.clean_name(active_fidget(context).name) + ".stl"
        return super().invoke(context, event)

    def execute(self, context):
        obj = active_fidget(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        non_manifold, degenerate, _ = mesh_report(obj.data)

        selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        for other in selected:
            other.select_set(False)
        obj.select_set(True)
        try:
            # 1 Blender unit is 1 mm, so export raw coordinates.
            bpy.ops.wm.stl_export(filepath=self.filepath, export_selected_objects=True,
                                  apply_modifiers=True, global_scale=1.0,
                                  use_scene_unit=False, ascii_format=False)
        finally:
            obj.select_set(False)
            for other in selected:
                other.select_set(True)
            context.view_layer.objects.active = active

        if non_manifold or degenerate:
            self.report({'WARNING'}, f"Exported with {non_manifold} non-manifold edges")
        else:
            self.report({'INFO'}, f"Exported {self.filepath}")
        return {'FINISHED'}


classes = (
    FIDGETGEN_OT_align_ground,
    FIDGETGEN_OT_section_toggle,
    FIDGETGEN_OT_check_manifold,
    FIDGETGEN_OT_export_stl,
)
