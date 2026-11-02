# Development Notes

These notes capture project conventions and recent implementation decisions for future maintenance reviews.

## Release/version maintenance

- Keep `bl_info["version"]` synchronized in both add-on entry points:
  - `io_export_mstsexporter/__init__.py`
  - `io_export_mstsexporter/export_msts.py`
- Add a matching revision-history entry near the top of `io_export_mstsexporter/export_msts.py`.
- Add a short release note to:
  - `README.MD`
  - `io_export_mstsexporter/README.md`
- `package_release.py` checks that both `bl_info` versions match before packaging.

## Release packaging

Run from the repository root:

```bash
python package_release.py
```

This creates GitHub release artifacts in `dist/`:

- `MSTS_ORTS_Exporter_AddOn_vX.Y.Z.zip`
- `MSTS_ORTS_Exporter_Documentation_vX.Y.Z.zip`
- `SHA256SUMS.txt`

The add-on ZIP is Blender-installable and contains `io_export_mstsexporter/`. The documentation ZIP contains `Documentation/` plus top-level project docs.

`dist/` is ignored by git. Do not commit generated ZIP files unless the release process explicitly changes.

## Tests and local verification

- The `tests/` folder is intentionally ignored/untracked by git in this repository.
- Use ad-hoc static/helper checks when Blender is not available on PATH.
- Minimum verification after exporter edits:

```bash
python -m py_compile io_export_mstsexporter/__init__.py io_export_mstsexporter/export_msts.py package_release.py
git diff --check
python package_release.py
(cd dist && sha256sum -c SHA256SUMS.txt)
```

If Blender is available, also run a real headless export smoke test.

## Export hierarchy keywords

`IsMSTSDefinedName()` in `export_msts.py` controls object names/prefixes that should be retained instead of merged/collapsed during export.

Recent addition:

- `SNAP` is retained as a neutral utility marker for TSRE targets, avoiding reuse of animation-oriented names such as `MIRROR` or `WIPER`.

## Texture copy behavior

The exporter has an optional `Copy Textures` checkbox in the export dialog.

When enabled:

1. The exporter records only textures used by exported material base-color settings.
2. For a Blender material source such as `crate.tga`, it first looks for a runtime texture with the same base name and expected export extension:
   - `crate.ace` when `Use DDS` is off
   - `crate.dds` when `Use DDS` is on
3. If the matching ACE/DDS file exists, that file is copied beside the exported `.s` file.
4. If no matching ACE/DDS exists, the actual source image used in Blender is copied instead, such as `.bmp`, `.tga`, `.png`, etc.
5. No image conversion is performed.
6. Existing identical destination files are skipped.
7. Existing different destination files are not overwritten; a warning is printed.
8. Missing textures are reported but do not cancel the export.

Key functions:

- `BaseColorImageDetailsFrom(material)`
- `RegisterTextureCopyCandidate(imageName, sourcePath)`
- `FindTextureCopySource(exportedImageName, sourcePath)`
- `CopyReferencedTextures(MSTSFilePath)`

## Current behavior caveats

- The `.s` file still references `.ace` or `.dds` according to `Use DDS`; copied fallback source files such as `.png` or `.tga` are for user convenience and review, not a format conversion.
- Texture discovery is based on the MSTS material `BaseColorFilepath` first, then a linked image texture node feeding Base Color/Color.
- If future users expect Open Rails to consume fallback `.png`/`.tga` directly, verify simulator support before changing `.s` image-reference behavior.

## Export info sidecar reports

The exporter has a `Write Export Info` checkbox. It writes two files beside the exported `.s` file:

- `<shape>_export_info.json` for tools such as OpenRails Engineer
- `<shape>_export_info.txt` for quick human review

The report uses OpenRails/MSTS axes, not Blender labels:

- X = width/right = Blender X
- Y = height/up = Blender Z
- Z = length/forward = Blender Y

The report includes:

- bounding box min/max X/Y/Z
- width, height, and length in meters
- volume sphere center/radius as written to the shape data (JSON only; dropped from the .txt in V5.3.0 because the center is always the scene origin)
- exported image list
- LOD triangle and draw-call summary

Schema version 2 (V5.2.6) adds, without renaming any v1 field:

- `running_gear`: axles, bogies, axles_per_group, body_axles, wheel_radius_m (+ source), rigid_wheelbase_m, bogie_centre_m, features (pantograph/wiper/door/... counts)
- `couplers`: face_length_m, centre_offset_m, height_m, height_difference_m, lateral_offset_m (null when markers are missing)
- `markers`: COUPLER_F / COUPLER_R positions (aliases COUPLER_FRONT / COUPLER_REAR)
- `parts`: BOGIE*/WHEELS*/feature parts with parent, bogie, origin, bounds, copies
- `warnings`: informational list; also printed as `NOTE:` lines on the console

Implementation notes:

- `SummarizeRunningGear()` and its helpers are bpy-free and unit tested in `tests/test_export_info.py` (loaded via AST like `test_animated_names.py`).
- `ExportRunningGearInfo()` collects parts only from LOD collections (what is exported) and markers from the whole scene.
- Wheel radius = wheelset origin height above rail (Y = 0); falls back to half mesh height (includes flange) when the origin is not between 0.15 m and 1.5 m.
- Only MESH objects become geometry, so marker Empties never reach the .s file.
- Headless check: `blender --background --factory-startup --python tests/blender_smoke_export_info.py` (set `SMOKE_OUT` to choose the output folder). Verified with Blender 4.5 and 5.2.
- Consumer: ENGWAGtool (`C:\dev\git\ENGWAGtool`) uses these fields to seed .eng/.wag files.

Keep the JSON schema stable unless OpenRails Engineer is updated at the same time. Add fields rather than renaming existing ones when possible.

## PBR materials (Open Rails only)

Implemented in V5.3.0, following the TSRE/Shape Viewer PBR S-material proposal (step 3, exporter side). Decision: PBR is an Open Rails only option; Classic stays the default and its output is byte-identical to V5.2.6 (verified on L1, UnionStop and the smoke car, ACE and DDS).

- Material setting `Shading` = `CLASSIC` (default) / `PBR`, plus `OrmFilepath` and `NormalFilepath` overrides; the panel shows the PBR rows and an "Open Rails only" box only for PBR.
- Shaders: `PbrTexDiff` (Opaque, Clip; alpha test stays in the prim state) and `BlendAPbrTexDiff` (Alpha, Alpha Sorted). PBR takes precedence over the EMISSIVE `Tex`/`BlendATex` choice; Lighting still sets the vertex state light material (-5 to -12). Emission goes to `emissive_factor`.
- `tex_idxs`: base, ORM, normal; missing = `-1`; trailing missing slots dropped (`PbrTexIdxs`). Base is always present (`blank` when no image, as for Classic).
- Discovery: panel path first, then shader nodes. ORM = image feeding Roughness/Metallic directly or through Separate Color / Separate RGB; normal = image feeding a Normal Map node. `IsLinkedToBaseColor` now ignores links into Normal Map and Separate Color/RGB nodes (their input is also called `Color`), which could previously pick a normal/ORM image as the base color.
- Factors (glTF names: `base_color_factor`, `metallic_factor`, `roughness_factor`, `normal_scale`, `occlusion_strength`, `emissive_factor`) come from the Principled BSDF; a socket driven by a texture gets factor 1. Different factors make different prim states (`iPrimStateAdd` compares `PbrFactors`).
- Sidecar `<shape>.s.tsre.json`: `{ "materials": { key: { prim_state_index, prim_state_name, ...factors } } }`. Key = prim state name when unique, else its index (exporter labels `<matrix>_<texture>` can repeat). Written on every export: other top-level keys in an existing sidecar are kept, `materials` is replaced or removed, and a file with nothing left is deleted. The TSRE task 03 sidecar layout was not available when this was written; if TSRE publishes different field names, change only `BuildPbrSidecar`/`PbrFactorsFrom`.
- Warnings (console `NOTE:`, export info `warnings`, and a WARNING status report): Open Rails only; PBR material without ORM or normal; PBR with ACE references (Use DDS recommended). Export info schema stays 2 (warnings are an existing list).
- `GetMSTSMaterialDetails` reads `blMaterial.original`: evaluated-mesh materials are depsgraph copies whose MSTS settings stay stale after script edits until the material is tagged. Affects Classic settings too (only where they were stale).
- Tests: `tests/test_pbr_materials.py` (bpy-free helpers, AST-loaded) and `tests/blender_pbr_smoke.py` (headless export, sidecar merge/removal, Rebuild nodes): `blender --factory-startup -b --python tests/blender_pbr_smoke.py` with `PBR_OUT` for the output folder. Verified with Blender 4.5, 5.1 and 5.2.
- Not done (later TSRE steps): MSTS test of the new shader names, clearcoat/reflective glass, generated tangents (viewer side).
