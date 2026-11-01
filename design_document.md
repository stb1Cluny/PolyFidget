# Design Document: Blender Parametric Fidget Star / Polygon Generator

* **Project Title:** Parametric Print-in-Place Fidget Generator
* **Working Add-on Name:** `PolyFidget`
* **Target Software:** Blender 5.2 LTS+ (`bpy`, `bmesh`, Geometry Nodes)
* **Author / Project Lead:** Add-on Development Team
* **Document Version:** 1.0.0
* **Status:** Draft / Initial Architecture
* **Tools:** Blender 5.2, mcp-for-blender(https://github.com/ahujasid/mcp-for-blender)

---

## 1. Project Overview & Vision

### 1.1 Problem Statement
Print-in-place nested fidget toys (such as telescoping star fidgets, collapsing polyhedra, and fractal spin stars) are widely popular on platforms like Printables, Thangs, and MakerWorld. However, designing them manually in CAD or 3D software requires tedious offset calculations, clearance tuning, and repetitive boolean operations for every nested layer. Changing parameters like wall thickness or overhang angle often requires rebuilding the model from scratch.

### 1.2 Objective
Develop a native Blender add-on that empowers 3D printing hobbyists, digital modelers, and commercial print shops to generate customized, sliced-ready, manifold, print-in-place nested fidget toys via real-time sliders and toggles.

### 1.3 Key Features
* Fully procedural base polygon generation (regular polygons, stars, fluted/wavy shapes).
* Automatic generation of nested concentric rings with clearance offsets.
* Configurable retaining flanges (angles, widths, step profiles) to enable smooth telescoping or captive retention without requiring assembly or print supports.
* Optional integrated center handle or exterior cradle.
* Export preparation (automatic orientation, origin centering, non-manifold checks).

---

## 2. Reference & Mechanical Analysis from Existing Designs

### 2.1 Mechanical Archetypes

#### A. The Gravity Telescopic / Collapsing Star (e.g., *Grandpa's Nested Star*, *Print-in-Place Telescoping Octagon*)
* **Motion Profile:** Rings slide along the Z-axis under gravity or flicking motion, forming an extended 3D cone/pyramid, then nesting completely flat when placed on a table.
* **Mechanism:** Asymmetric internal chamfers. The bottom rim of ring $n$ has an outward-protruding lip that catches the inward-protruding upper ledge of ring $n+1$.
* **Critical Tolerance:** 
  * Radial Clearance ($XY$ gap): $0.35\text{ mm} - 0.55\text{ mm}$ (tuned for typical FDM 0.4 mm nozzles).
  * Axial Clearance ($Z$ gap between interlocking lips): $0.3\text{ mm} - 0.5\text{ mm}$.

#### B. The Center-Handle Sensory Fidget (e.g., *Fractal Star with Center Stem*)
* **Motion Profile:** Held between thumb and index finger by a central core, allowing rapid rotational spinning and back-and-forth flicking without user fingers contacting the moving outer rings.
* **Mechanism:** The innermost shell is solid or fused to a cylindrical vertical post, often with knurling or caps for grip.

#### C. Bi-Directional Captive Shells
* **Motion Profile:** Rings cannot pop out from either side. They have limited loose play up and down within a bounded range.
* **Mechanism:** Dual-chamfer / hourglass cross-sections or stepped T-slots along the ring profile.

### 2.2 Slicing & FDM Printability Rules
1. **Overhang Angle:** Flanges must maintain angles between $35^\circ$ and $55^\circ$ from the horizontal plane to eliminate the need for slicer-generated supports.
2. **First Layer Bridging / Fusing Prevention:** The bottom face must feature a minimum chamfer or elephant's foot compensation to prevent neighboring concentric rings from fusing on the build plate.
3. **Corner Geometry:** Sharp inner and outer corners cause nozzle deceleration and local over-extrusion. Automatic corner filleting/radiusing is essential for reliable clearances.

---

## 3. Parameter Specifications & UI Architecture

The add-on will expose controls in the 3D Viewport Sidebar (`N-Panel > PolyFidget`) and via an `Add Mesh` operator dialog (`Shift + A > Mesh > Fidget Star / Polygon`).

### 3.1 Base Polygon Geometry
| Parameter | Type | Default | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `shape_type` | Enum | `STAR` | `STAR`, `POLYGON`, `FLUTED` | Profile silhouette type. |
| `point_count` | Int | `5` | `3 – 16` | Number of star points or polygon vertices. |
| `outer_radius` | Float | `45.0 mm` | `10.0 – 200.0 mm` | Overall footprint radius of the outermost ring. |
| `indent_ratio` | Float | `0.45` | `0.10 – 0.95` | Inner-to-outer point ratio for star shapes. |
| `corner_radius` | Float | `1.5 mm` | `0.0 – 10.0 mm` | Fillet radius on outer points and internal valleys. |

### 3.2 Nesting & Clearance Engine
| Parameter | Type | Default | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `ring_count` | Int | `6` | `2 – 30` | Number of concentric nested shells. |
| `wall_thickness`| Float | `1.2 mm` | `0.8 – 5.0 mm` | Radial thickness of each ring wall (3 perimeters on 0.4mm nozzle). |
| `clearance_xy` | Float | `0.4 mm` | `0.2 – 1.0 mm` | Air gap between adjacent shells in neutral position. |
| `scaling_mode` | Enum | `LINEAR` | `LINEAR`, `GEOMETRIC` | Method for distributing ring widths from outer shell to core. |

### 3.3 Height & Flange Overhang Parameters
| Parameter | Type | Default | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `total_height` | Float | `10.0 mm` | `4.0 – 50.0 mm` | Height of the nested assembly when collapsed flat. |
| `flange_angle` | Float | `45.0°` | `30.0° – 60.0°` | Overhang angle relative to the horizontal build plate. |
| `flange_depth` | Float | `1.0 mm` | `0.4 – 3.0 mm` | Radial width of the interlocking lip. |
| `flange_type` | Enum | `TELESCOPIC_DOWN` | `TELESCOPIC_DOWN`, `TELESCOPIC_UP`, `CAPTIVE_DUAL` | Direction and action of the interlocking overhang. |
| `clearance_z` | Float | `0.4 mm` | `0.2 – 0.8 mm` | Vertical slip gap between interlocking flanges. |

### 3.4 Handle & Grip Configuration
| Parameter | Type | Default | Range | Description |
| :--- | :--- | :--- | :--- | :--- |
| `enable_handle` | Bool | `False` | `True / False` | Toggle to spawn a central grip on the innermost ring. |
| `handle_style` | Enum | `CYLINDER` | `CYLINDER`, `KNURLED`, `MUSHROOM_CAP` | Visual and functional style of handle. |
| `handle_height` | Float | `15.0 mm` | `5.0 – 60.0 mm` | Total height of the grip extension. |
| `handle_diameter`| Float| `8.0 mm` | `3.0 – 25.0 mm` | Diameter of the handle stem. |
| `handle_anchor` | Enum | `INNER_CORE` | `INNER_CORE`, `OUTER_FRAME` | Whether the handle attaches to center or outer frame. |

### 3.5 3D Print Preparation Helpers
* **Align to Ground Plane:** One-click utility setting minimum bounding box Z to $0.0$.
* **Cross-Section Inspector:** Generates a temporary non-destructive clipping plane to inspect internal ring clearance and flange engagement.
* **Direct Export:** Quick export to `.stl` and `.3mf` with applied scale and normals checked.

---

## 4. Technical Architecture

### 4.1 Topology Generation Strategy
The add-on will utilize Blender’s `bmesh` API for robust, deterministic procedural construction:

```
[User Parameters]
       │
       ▼
[2D Profile Generator] ──> Calculates 2D boundary polygons with fillet offsets
       │
       ▼
[Concentric Insetter]  ──> Generates N nested loops separated by (wall + clearance_xy)
       │
       ▼
[Cross-Section Sweep]  ──> Extrudes loops along Z with angled bevel edges (flanges)
       │
       ▼
[Handle / Cap Merge]   ──> Booleans or welds center handle geometry to inner loop
       │
       ▼
[Mesh Sanitization]    ──> Recalculate normals, remove doubles, check 2-manifold
```

### 4.2 Mathematical Profile Formulation
For ring index $i$ (where $i=0$ is the outermost ring):
1. **Outer Boundary Offset ($R_{outer, i}$):**
   $$R_{outer, i} = R_{outer, 0} - i \cdot (W + \delta_{xy})$$
   where $W$ is `wall_thickness` and $\delta_{xy}$ is `clearance_xy`.
2. **Inner Boundary Offset ($R_{inner, i}$):**
   $$R_{inner, i} = R_{outer, i} - W$$
3. **Flange Step Transition:**
   At height $Z_{split}$, an extrusion normal offset is applied:
   $$\Delta X = \tan(90^\circ - \theta) \cdot \Delta Z$$
   where $\theta$ is the `flange_angle` from horizontal.

---

## 5. Directory Structure

```text
poly_fidget/
├── __init__.py                # Add-on registration, bl_info, and preferences
├── operators/
│   ├── __init__.py
│   ├── op_create_fidget.py    # Main creation operator (Shift + A menu)
│   └── op_export_print.py     # STL/3MF export and validation operators
├── ui/
│   ├── __init__.py
│   └── panel_poly_fidget.py    # N-panel UI layouts, sliders, and buttons
├── core/
│   ├── __init__.py
│   ├── polygon_builder.py     # 2D profile and corner filleting algorithms
│   ├── ring_mesher.py         # bmesh 3D extrusion, chamfering, and flange generator
│   └── handle_builder.py      # Knurled, cylindrical, and ergonomic center posts
└── assets/
    └── presets/               # Default presets (e.g., tight_clearance, loose_fidget)
```

---

## 6. Implementation Roadmap

### Phase 1: Core Geometry Engine
* [ ] Implement 2D regular polygon, star, and fluted curve math in `polygon_builder.py`.
* [ ] Implement 2D corner rounder/fillet using tangent arc discretization.
* [ ] Create simple vertical extrusion test for nested concentric rings.

### Phase 2: Overhangs & Interlocking Flanges
* [ ] Add cross-section profile logic for single-direction retaining flanges.
* [ ] Implement directional control (`TELESCOPIC_DOWN` vs `TELESCOPIC_UP`).
* [ ] Add captive dual-step profile support.
* [ ] Validate clearances ($\delta_{xy}$, $\delta_z$) in slicing software.

### Phase 3: Handles & Ergonomics
* [ ] Construct cylinder and mushroom cap handle shapes fused to the innermost ring.
* [ ] Implement procedural knurling pattern generation on the handle surface.

### Phase 4: UI, Presets, and Polish
* [ ] Build clean N-Panel interface with real-time property updates.
* [ ] Implement cross-section viewer tool for checking internal gaps.
* [ ] Provide preset profiles for 0.4 mm and 0.6 mm nozzles.
* [ ] Package as standard `.zip` for Blender add-on installation.