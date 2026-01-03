bl_info = {
    "name": "MSTS / OpenRails Shape Exporter",
    "author": "Pete Willard",
    "version": (4, 8, 2),
    "blender": (3, 8, 0),
    "location": "File > Export > OpenRails/MSTS (.s)",
    "description": "Exports Train Simulator shapes",
    "category": "Import-Export",
}

if "bpy" in locals():
    import importlib
    importlib.reload(export_msts)
else:
    from . import export_msts

def register():
    if hasattr(export_msts, "register"):
        export_msts.register()

def unregister():
    if hasattr(export_msts, "unregister"):
        export_msts.unregister()

if __name__ == "__main__":
    register()
