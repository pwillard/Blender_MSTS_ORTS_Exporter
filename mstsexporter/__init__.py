bl_info = {
    "name": "OpenRails / MSTS Shape Exporter",
    "author": "Wayne Campbell/Pete Willard",
    "version": (4, 8, 1),
    "blender": (4, 0, 0),
    "location": "File > Export > OpenRails/MSTS (.s)",
    "description": "Exports Train Simulator shapes compatible with Open Rails and MSTS",
    "category": "Import-Export",
}

if "bpy" in locals():
    import importlib
    importlib.reload(MSTSExporter)
else:
    from . import MSTSExporter

def register():
    if hasattr(MSTSExporter, "register"):
        MSTSExporter.register()

def unregister():
    if hasattr(MSTSExporter, "unregister"):
        MSTSExporter.unregister()

if __name__ == "__main__":
    register()
