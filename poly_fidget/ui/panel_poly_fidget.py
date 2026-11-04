"""Sidebar panels (N-Panel > PolyFidget) and shared parameter layouts."""

import bpy

from .. import presets


def draw_shape(layout, s):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(s, "shape_type")
    col.prop(s, "point_count")
    col.prop(s, "outer_radius")
    row = col.row()
    row.active = s.shape_type != 'POLYGON'
    row.prop(s, "indent_ratio")
    row = col.row()
    row.active = s.shape_type != 'FLUTED'
    row.prop(s, "corner_radius")
    col.prop(s, "resolution")


def draw_nesting(layout, s):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(s, "ring_count")
    col.prop(s, "wall_thickness")
    col.prop(s, "clearance_xy")
    col.prop(s, "scaling_mode")
    if s.scaling_mode == 'GEOMETRIC':
        col.prop(s, "geometric_ratio")


def draw_flanges(layout, s):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(s, "total_height")
    col.prop(s, "flange_type")
    col.prop(s, "wall_style")
    if s.wall_style == 'SLANTED':
        col.prop(s, "wall_angle")
    col.prop(s, "flange_angle")
    col.prop(s, "flange_depth")
    col.prop(s, "clearance_z")
    col.prop(s, "lip_land")
    col.prop(s, "foot_chamfer")


def draw_handle(layout, s):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.active = s.enable_handle
    col.prop(s, "handle_anchor")
    frame = s.handle_anchor == 'OUTER_FRAME'
    if not frame:
        col.prop(s, "handle_style")
    col.prop(s, "handle_height", text="Frame Height" if frame else "Height")
    col.prop(s, "handle_diameter", text="Frame Width" if frame else "Diameter")


def draw_all(layout, s):
    for title, fn in (("Base Shape", draw_shape), ("Nesting", draw_nesting),
                      ("Height & Flanges", draw_flanges)):
        box = layout.box()
        box.label(text=title)
        fn(box, s)
    box = layout.box()
    box.prop(s, "enable_handle")
    draw_handle(box, s)


def active_fidget(context):
    obj = context.active_object
    if obj is not None and obj.type == 'MESH' and obj.poly_fidget.is_fidget:
        return obj
    return None


class FidgetPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyFidget"


class FidgetSubPanel(FidgetPanel):
    bl_parent_id = "VIEW3D_PT_poly_fidget"

    @classmethod
    def poll(cls, context):
        return active_fidget(context) is not None


class VIEW3D_PT_poly_fidget(FidgetPanel, bpy.types.Panel):
    bl_label = "PolyFidget"

    def draw(self, context):
        layout = self.layout
        layout.operator("mesh.poly_fidget_add", icon='SOLO_ON')
        obj = active_fidget(context)
        if obj is None:
            layout.label(text="Select a fidget to edit it", icon='INFO')
            return
        s = obj.poly_fidget
        if s.status:
            box = layout.box()
            box.alert = True
            for i, line in enumerate(_wrap(s.status, 40)):
                box.label(text=line, icon='ERROR' if i == 0 else 'BLANK1')
        row = layout.row(align=True)
        current = presets.active()
        row.menu("POLYFIDGET_MT_presets", text=presets.label(current) if current else "Presets",
                 icon='PRESET')
        row.operator("poly_fidget.preset_save", text="", icon='ADD')
        row.operator("poly_fidget.preset_rename", text="", icon='GREASEPENCIL')
        row.operator("poly_fidget.preset_remove", text="", icon='REMOVE')
        col = layout.column(align=True)
        col.enabled = False
        col.use_property_split = True
        col.prop(s, "stat_footprint")
        col.prop(s, "stat_core")
        col.prop(s, "stat_travel")
        col.prop(s, "stat_extended")


class VIEW3D_PT_poly_fidget_shape(FidgetSubPanel, bpy.types.Panel):
    bl_label = "Base Shape"

    def draw(self, context):
        draw_shape(self.layout, active_fidget(context).poly_fidget)


class VIEW3D_PT_poly_fidget_nesting(FidgetSubPanel, bpy.types.Panel):
    bl_label = "Nesting"

    def draw(self, context):
        draw_nesting(self.layout, active_fidget(context).poly_fidget)


class VIEW3D_PT_poly_fidget_flanges(FidgetSubPanel, bpy.types.Panel):
    bl_label = "Height & Flanges"

    def draw(self, context):
        draw_flanges(self.layout, active_fidget(context).poly_fidget)


class VIEW3D_PT_poly_fidget_handle(FidgetSubPanel, bpy.types.Panel):
    bl_label = "Handle"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(active_fidget(context).poly_fidget, "enable_handle", text="")

    def draw(self, context):
        draw_handle(self.layout, active_fidget(context).poly_fidget)


class VIEW3D_PT_poly_fidget_print(FidgetSubPanel, bpy.types.Panel):
    bl_label = "Print Prep"

    def draw(self, context):
        obj = active_fidget(context)
        col = self.layout.column(align=True)
        col.operator("poly_fidget.align_ground", icon='TRIA_DOWN_BAR')
        has_section = obj.modifiers.get("PolyFidget Section") is not None
        col.operator("poly_fidget.section_toggle", icon='MOD_BOOLEAN', depress=has_section,
                     text="Hide Cross-Section" if has_section else "Show Cross-Section")
        col.operator("poly_fidget.check_manifold", icon='CHECKMARK')
        col.separator()
        col.operator("poly_fidget.export_stl", icon='EXPORT')


def _wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


classes = (
    VIEW3D_PT_poly_fidget,
    VIEW3D_PT_poly_fidget_shape,
    VIEW3D_PT_poly_fidget_nesting,
    VIEW3D_PT_poly_fidget_flanges,
    VIEW3D_PT_poly_fidget_handle,
    VIEW3D_PT_poly_fidget_print,
)
