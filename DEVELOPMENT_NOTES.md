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
- volume sphere center/radius as written to the shape data
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

## Planned: PBR materials (Open Rails only)

Status: design only, not implemented. Driven by the TSRE/Shape Viewer PBR S-material proposal.

Decision: PBR export is an Open Rails only option. MSTS behavior with the new shader names is unknown, so the classic path stays the default and is unchanged.

- Opt-in per material (e.g. a `Shading` setting: Classic / PBR (Open Rails only)); default Classic.
- PBR shaders: `PbrTexDiff` (Opaque, Clip) and `BlendAPbrTexDiff` (Alpha, Alpha Sorted). EMISSIVE has no PBR mapping yet; decide before implementing.
- `tex_idxs` becomes base colour, ORM, normal; a missing slot is `-1`. `PrimState.Write` already writes a variable count.
- Texture discovery: Base Color image as now; ORM = image feeding Roughness/Metallic via Separate Color (glTF style); normal = image feeding a Normal Map node; plus optional file path overrides like `BaseColorFilepath`.
- Factors go to the `<shape>.s.tsre.json` sidecar (materials object). Prim state labels (`<matrix>_<texture>`) are not unique, so key by index or make labels unique for PBR shapes. Always rewrite (or delete when no PBR materials) the sidecar on export so a stale Shape Viewer copy can't misapply factors.
- Warn (console `NOTE:` + export info `warnings`) that the shape is Open Rails only, and when PBR textures export as ACE instead of DDS.
- Classic exports must stay byte-identical; test both paths.
