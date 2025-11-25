bl_info = {     "name": "Export OpenRails/MSTS Shape File(.s)",
                "author": "Wayne Campbell/Pete Willard",
                "version": (4, 9),
                "blender": (2, 8, 0),
                "location": "File > Export > OpenRails/MSTS (.s)",
                "description": "Export file to OpenRails/MSTS .S format",
                "category": "Import-Export"}

# Updated for Blender 4.0+ compatibility with fallback for older versions
# Version 4.8 2025-10-08


'''
COPYRIGHT 2019 by Wayne Campbell

	This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    A copy of the GNU General Public License is included in this distribution package
    or may be found here <http://www.gnu.org/licenses/>.

For complete documentation, and CONTACT info see the Instructions included in the distribution package.



REVISION HISTORY
2025-11-25      Released V4.9  - PKW - Fix for empty "BaseColorFilePath" in MSTS Materials Update.
2025-10-08      Released V4.8  - pkw - Fix for Blender 4.5 Update for changes related to shader sockets
2025-01-19      Released V4.7  - pkw - Fix for the deprecated specular which is now IOR (Index of Refraction) in 4.x
                Note: It was causing the "recreateShaderNodes function to fail and cause the material nodes to all become disconnected.
2024-12-12      Released V4.6  - pkw - Fix for the deprecated to.mesh in 4.x
2024-04-03      Released V4.5  - pkw - Handling issues created by Blender 4.1 deprecating smoothing related APIs.
2023-07-13      Released V4.4  - pkw
                Added support for exporting texture references as DDS files instead of just ACE files using a checkbox.
                Like the ACE file export, it changes *ALL* texture references to DDS when checked.
2019-07-23      Released V4.3
                Improved instructions around linking a part to multiple LOD collections
                Fixed program error - no material slots, or empty material slot
2019-07-21      Released V4.2 for testing
                Added HierarchyOptimization
                Added FastExport - improves speed 25 x
                Restructured AddMesh, AddTriangle with MSTSMaterialsDetail structure to improve performance
                Indexed vertices for faster export ( eg speedup by 3 times )
2019-07-18      Released V4.1 to beta testers
                Modified install package to work with 'Install from file..'
                Fixed ShapeViewer crashes on animations(0)
2019-07-17      Released V4.0 to beta testers
                Updated for Blender 2.8
2017-09-12      Released as V 3.5
                added SubObjID to SubObjectHeader per report from 'Spike'
                added support for Auto Smoothing per http://www.elvastower.com/forums/index.php?/topic/30491-blender-auto-smooth-and-msts-export/
2016-01-11      Released as V 3.4
                strip periods (.) from object names
                fixes to LOD inheritance
                remember RetainNames setting
                file export dialog, default to .s extension
2016-01-10      Testing as V 3.3
                Added RetainNames option
                Fixed bounding sphere bug
                Trimmed most numbers to 6 decimal places to reduce output file size
2016-01-10      Testing as V 3.2
                Documented hidden option to use Railworks style LOD naming
                Documented setting MAX values in Custom Properties
                Fixed AttributeError: 'NoneType' object has no attribute 'game_settings'
2016-01-09      Testing as V 3.1
                Added MipMapLODBias setting
                Fixed bug, untextured faces - AttributeError: 'NoneType' object has no attribute 'name'
                Implemented MSTS sub_object flags for sorting alpha blended faces ( not needed for OR )
                Implement MSTS sub_object flags for specularity ( not needed for OR )
                Added Alpha Sorted Transparency option to MSTS Material
                Improved descriptions and naming of MSTS Material settings
                Fixed MSTS Lighting value not being saved
                Sped up iVertexAdd, iNormalAdd, etc,  with spatial tree indexing, etc
2016-01-08      Testing as V 3.0
                Fix for WHEELS13, WHEELS23
                Changed use_shadeless, from selecting Cruciform, now done with MSTS Lighting
                Added MSTS Material panel for lighting options, etc
                Added support for Railworks style LOD naming
2015-11-11      Released as V 2
                Changed prim_state labels to be compatible with Polymaster
2013-11-01      Initial Release as V 2.6.3


TODO FUTURE
    - add a progress bar ( when available in the Blender API ) Still not available in 20205.
    - document or remove hidden Normals override options ( superceded by Blender's new Normals Modifier )

IDEAS FUTURE
    - add support for curves, particle systems, dupliverts
    - support undocumented MSTS capability, eg
        - Wrap, Clamp, Extend etc
        - double sided faces (still can't do then correctly in Blender 4.x)
        - bump mapping and environmental reflections
        - AddATex, SubractATex, etc and other undocumented shaders
        - zBias
        - use of lod_control objects to improve LOD efficiency
    - option to export texture files
    - option to compress shape file
    - options to generate .SD, .ENG, .WAG or .REF

'''

import bpy
import os
import re
from math import radians
from bpy.props import StringProperty, EnumProperty, BoolProperty
import mathutils
from mathutils import *

class MyException( Exception ):
        pass

MaxVerticesPerPrimitive = 8000     # 8000 OK 20000 Fails
MaxVerticesPerSubObject = 15000      # 15000 OK 20000 Fails, Note: Spike reports 14000 failed, he uses 12000

FastExport = True       # do less compaction to reduce export time at cost of slightly larger file size
                        # no impact on frame rates for most files, very large files may see a couple of additional Draw calls
                        # eg L1-huge.blend exports in 28 sec vs 11 min 42 sec, file size = 63,628,192  vs 55,423,130 bytes

HierarchyOptimization = True  # gives better triangle fill, reduces subobject splitting in middle of primitive,
                              # creates new subobjects for each hierarchy level
                              # should improve frame rates by reducing Draw Calls, and creating smaller vertex sets, where possible
                              # yet places multiple primitives in a subobject when vertex sharing across large vertex sets make sense

RetainNames = False   # user option, when true, the exporter disables mesh
                      # consolidation and hierarchy collapse optimizations
                      # reduces frame rates due to more Draw Calls
UseDDS = False

BlenderVersion = bpy.app.version    # returns tuple of (major, minor, subversion)


#####################################

from bpy_extras.io_utils import ExportHelper, ImportHelper  # gives access to the FileSelectParams

ProgressIndicator = 0.0   # spins from 0 to 1
ProgressContext = None

def UpdateProgress():    # this is the little cursor counter progress indicator ( all thats available in Blender's API )

    global ProgressIndicator
    global ProgressContext
    ProgressContext.window_manager.progress_update(ProgressIndicator)
    ProgressIndicator += 0.0001
    if ProgressIndicator > 1.0:
        ProgressIndicator = 0

# Function to get mesh depending on Blender version
def get_evaluated_mesh(obj):
    if BlenderVersion < (4, 1, 0):
        # Pre-Blender 4.1, use the standard evaluated object approach
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()
    else:
        # Blender 4.1+ requires alternate handling
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    return mesh


class ExportHelper:
    filepath : StringProperty(
            name="File Path",
            description="Filepath used for exporting the file",
            maxlen=1024,
            subtype='FILE_PATH',
            )

    # set up the FileSelectParams
    filename_ext = ".s"
    filter_glob : StringProperty(default="*.s", options={'HIDDEN'})


class MSTSExporter(bpy.types.Operator, ExportHelper):


    bl_idname = "export.msts_s"
    bl_description = 'Export to OpenRails/MSTS .s file'
    bl_label = "Export OpenRails/MSTS S"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'UNDO'}

    filepath : StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):

        settings = context.scene.msts

        # set up default path
        blend_filepath = context.blend_data.filepath
        if not blend_filepath:
            blend_filepath = "untitled"
        else:
            blend_filepath = os.path.splitext(blend_filepath)[0]
        self.filepath = blend_filepath + self.filename_ext

        # override with last used path if it looks good
        if settings.SFilepath != "":
            lastSavedPath = os.path.abspath( bpy.path.abspath( settings.SFilepath ) )
            lastSavedFolder = os.path.split(lastSavedPath)[0]
            if os.path.exists( lastSavedFolder ):
                self.filepath = lastSavedPath

        WindowManager = context.window_manager
        WindowManager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw( self, context ):

        settings = context.scene.msts

        layout = self.layout

        layout.prop( self, "filepath" )
        layout.prop( settings, "RetainNames" )
        layout.prop( settings, "UseDDS" )

    def execute(self, context):

        settings = context.scene.msts

        global RetainNames
        RetainNames = settings.RetainNames
        global UseDDS
        UseDDS = settings.UseDDS

        #Append .s
        exportPath = bpy.path.ensure_ext(self.filepath, ".s")
        settings.SFilepath = TryGetRelPath( exportPath )

        # Validate root object
        rootName = 'MAIN'
        rootCollection = bpy.context.scene.collection.children.get( rootName )
        if rootCollection == None:
            print()
            print( "ERROR: MAIN not found in Scene Collection.")
            self.report( {'ERROR'}, "MAIN not found in Scene Collection" )
            return {'CANCELLED' }

        #force out of edit mode
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set( mode = 'OBJECT' )

        #Export
        print()
        print( "EXPORTING "+rootName + " TO " + exportPath )
        print()
        global ProgressContext
        ProgressContext = context
        context.window_manager.progress_begin( 0,1 )   # progress bar indication ( forthcoming feature )
        UpdateProgress()
        try:
            ExportShapeFile( rootName, exportPath )

            print( "FINISHED OK" )
            self.report( {'INFO'}, "Finished OK" )
            return {"FINISHED"}
        except MyException as error:   # when we raise an error it comes here
            context.window_manager.progress_end()
            print( "ERROR: " + ' '.join(error.args) )
            self.report( {'WARNING'}, ' '.join(error.args) )
            return { "CANCELLED" }
        # all other exceptions are passed up for traceback
        finally:
            context.window_manager.progress_end()

    def cancel( self, message ):
        print( "ERROR: ", message )
        self.report( {'ERROR'}, message )
        return {'CANCELLED' }


def menu_func(self, context):
    self.layout.operator(MSTSExporter.bl_idname, text="OpenRails/MSTS (.s)")

def register():
    bpy.utils.register_class( msts_material_props)  # define the new msts material properties
    bpy.utils.register_class( msts_scene_props)
    bpy.types.Material.msts = bpy.props.PointerProperty(type=msts_material_props)   # add the properties to the material type
    bpy.types.Scene.msts = bpy.props.PointerProperty(type=msts_scene_props)
    bpy.utils.register_class( msts_material_panel )                               # add a UI panel to the Materials window
    bpy.utils.register_class( MSTSExporter )                                    # define the exporter dialog panel
    bpy.types.TOPBAR_MT_file_export.append(menu_func)                             # add the exporter to the menu

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class( MSTSExporter )
    bpy.utils.unregister_class( msts_material_panel )
    del bpy.types.Scene.msts
    del bpy.types.Material.msts
    bpy.utils.unregister_class( msts_scene_props)
    bpy.utils.unregister_class( msts_material_props )

'''
************************ THE GUI *******************************
'''


#####################################
# find an image with the specified path, or create it
def GetImage( filepath ):

    return bpy.data.images.load( filepath, check_existing = True )


#####################################
# recreate the shader nodes to represent the msts settings

def RecreateShaderNodes(m):
    """
    Safely recreate shader nodes across Blender 3.6 → 4.5.
    Fixes issues with Update Shader checkbox causing disconnected nodes in Blender 4.x.

    - Detects correct socket names dynamically (Base Color / Alpha / IOR / Specular).
    - Rebuilds node tree safely without throwing errors on missing sockets.
    - Maintains compatibility with legacy 3.x setups.
    - Prints a confirmation line to the system console when completed.
    """
    import bpy, os

    # enable shader nodes
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links

    # remove any existing nodes to start clean
    nodes.clear()

    # create required nodes
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    uv = nodes.new("ShaderNodeUVMap")

    # position nodes for readability in the Shader Editor
    output.location = (300, 0)
    bsdf.location = (0, 0)
    tex.location = (-300, 0)
    uv.location = (-550, 0)

    # --- Image Texture Handling ---
    # Load image if valid path is set in MSTS material properties
    img_path = bpy.path.abspath(m.msts.BaseColorFilepath)
    if os.path.exists(img_path):
        tex.image = bpy.data.images.load(img_path, check_existing=True)

    # --- Node Linking ---
    # Connect Base Color (handle Blender naming variations)
    base_color_input = bsdf.inputs.get("Base Color") or bsdf.inputs.get("BaseColor")
    if base_color_input and tex.outputs.get("Color"):
        links.new(base_color_input, tex.outputs["Color"])

    # Connect Alpha channel for transparency support
    if bsdf.inputs.get("Alpha") and tex.outputs.get("Alpha"):
        links.new(bsdf.inputs["Alpha"], tex.outputs["Alpha"])

    # Connect UV map to texture
    if tex.inputs.get("Vector") and uv.outputs.get("UV"):
        links.new(tex.inputs["Vector"], uv.outputs["UV"])

    # Connect BSDF to Material Output surface
    if output.inputs.get("Surface") and bsdf.outputs.get("BSDF"):
        links.new(output.inputs["Surface"], bsdf.outputs["BSDF"])

    # --- Specularity / IOR Handling ---
    # Blender 4.0+ removed Specular; uses Index of Refraction instead.
    if bpy.app.version < (4, 0, 0):
        # Legacy Specular workflow
        spec_input = bsdf.inputs.get("Specular")
        if spec_input:
            if m.msts.Lighting == 'SPECULAR25':
                spec_input.default_value = 0.1
                bsdf.inputs["Roughness"].default_value = 0.3
            elif m.msts.Lighting == 'SPECULAR750':
                spec_input.default_value = 0.1
                bsdf.inputs["Roughness"].default_value = 0.1
            else:
                spec_input.default_value = 0.0
                bsdf.inputs["Roughness"].default_value = 1.0
    else:
        # Blender 4.x IOR workflow
        ior_input = bsdf.inputs.get("IOR")
        if ior_input:
            if m.msts.Lighting == 'SPECULAR25':
                ior_input.default_value = 1.25
                bsdf.inputs["Roughness"].default_value = 0.3
            elif m.msts.Lighting == 'SPECULAR750':
                ior_input.default_value = 1.75
                bsdf.inputs["Roughness"].default_value = 0.1
            else:
                ior_input.default_value = 1.0
                bsdf.inputs["Roughness"].default_value = 1.0

    # mark Principled BSDF as active node
    m.node_tree.nodes.active = bsdf

    # console confirmation
    print(f"✅ Shader updated for '{{m.name}}' using Blender {{bpy.app.version_string}}")


def SetDefaultViewportShading( screenName ):

    for screen in bpy.data.screens:
        if screen.name == screenName:

            area = next(area for area in screen.areas if area.type == 'VIEW_3D')
            space = next(space for space in area.spaces if space.type == 'VIEW_3D')

            space.shading.show_backface_culling = True
            space.shading.color_type = 'TEXTURE'
            space.shading.light = 'STUDIO'

            return

    print( "Warning: Screen " + screenName + " not found while setting viewport shading." )

# Show specified image in active UV window
def SetUVWindowImage( context, image ):

    if image != None:
        for eachArea in context.screen.areas:
            if eachArea.type == 'IMAGE_EDITOR':
                for eachSpace in eachArea.spaces:
                    if eachSpace.type == 'IMAGE_EDITOR':
                        eachSpace.image = image
                        return
    return

# Show specified image path in active UV window
def SetUVWindowImagePath( context, imagePath ):

    if os.path.exists( bpy.path.abspath(imagePath) ):
        image = GetImage( imagePath )
        SetUVWindowImage( context, image )


#####################################
# called when the image is changed in the MSTS material panel
# changes material name to match and updates material settings
def UpdateMSTSImage( self, context ):

    if hasattr(context, 'material'):
        if context.material != None:
            mstsmaterial= context.material.msts
            if mstsmaterial.UpdateNodes:

                materialName = bpy.path.display_name_from_filepath( mstsmaterial.BaseColorFilepath )

                if not materialName in bpy.data.materials:
                    context.material.name = materialName
                #else:
                    # if the suggested material name already exists,
                    # then leave it up to the user to sort it out

                SetUVWindowImagePath( context, mstsmaterial.BaseColorFilepath )

    UpdateMSTSMaterial( self, context )




#####################################
# called when the MSTS material panel settings are changed
def UpdateMSTSMaterial( self, context ):

    if hasattr(context, 'material') and context.material is not None:
        mstsmaterial = context.material.msts
        blM = context.material

        blM.use_backface_culling = True

        if blM.msts.Transparency == "OPAQUE":
            blM.blend_method = "OPAQUE"
        elif blM.msts.Transparency == "CLIP":
            blM.blend_method = "CLIP"
        elif blM.msts.Transparency in {"ALPHA", "ALPHA_SORT"}:
            blM.blend_method = "BLEND"

        # Only rebuild shader nodes when explicitly requested and path is set
        if mstsmaterial.UpdateNodes and mstsmaterial.BaseColorFilepath:
            RecreateShaderNodes( blM )

        SetDefaultViewportShading( 'Layout' )
        SetDefaultViewportShading( 'UV Editing' )

#####################################
class msts_material_panel(bpy.types.Panel):
    """Creates a Panel in the material context of the properties editor"""
    bl_label = "MSTS Materials"
    bl_idname = "MATERIAL_PT_msts"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    def draw(self, context):   # see bpy.context for info on available context's

        if context.material != None:
            mstsmaterial= context.material.msts

            layout = self.layout
            layout.use_property_split = True
            layout.use_property_decorate = False

            # Create a simple row.
            col = layout.column(align = True )
            col.prop(mstsmaterial, property="Transparency" )
            col.prop(mstsmaterial, property="Lighting" )
            col.prop(mstsmaterial, property="MipMapLODBias")  # this should be a texture property
                                                              # not a material property
                                                              # but here is simpler for the user to find
            col.prop(mstsmaterial, property="BaseColorFilepath" )
            col.prop(mstsmaterial, property="UpdateNodes" )


#####################################
class msts_material_props(bpy.types.PropertyGroup):
    # define custom material properties,  ie material.msts.shadername   note: these prop's will be saved in the blend file

    Transparency : bpy.props.EnumProperty(
                name="Transparency",
                description="Controls handling of alpha channel.",
                items = [ ( "OPAQUE",   "Solid Opaque",         "Alpha channel is ignored" ),
                          ( "CLIP",     "Transparency On/Off",  "Transparent if alpha value below a threshold" ),
                          ( "ALPHA",    "Alpha Blended",        "Alpha value blends from transparent up to opaque" ),
                          ( "ALPHA_SORT","Alpha Sorted",        "Alpha blending with depth sort" )
                        ],
                default="OPAQUE",
                update= UpdateMSTSMaterial,
                )

    Lighting : bpy.props.EnumProperty(
                name="Lighting",
                description="Adjusts light and shadow",
                items = [ ("NORMAL",         "Normal",       "Sun facing surfaces are lit and opposite are shaded" ),
                          ("SPECULAR25",     "Specular 25",  "Strong specular highlight" ),
                          ("SPECULAR750",    "Specular 750", "Small specular highlight" ),
                          ("FULLBRIGHT",     "Full Bright",  "Shaded surfaces appear lit" ),
                          ("HALFBRIGHT",     "Half Bright",  "Shaded surfaces appear partly lit" ),
                          ("DARK",           "Dark",         "Sun facing surfaces appear fully shaded" ),
                          ("CRUCIFORM",      "Cruciform",    "Indirect ambient lighting only" ),
                          ("EMISSIVE",       "Emissive",     "Surfaces emit light at night" )
                        ],
                default="NORMAL",
                update= UpdateMSTSMaterial,
                )

    MipMapLODBias : bpy.props.FloatProperty(
                name="Mip Bias",
                description="Controls sharpness of the image, default = -3",
                default = 0,
                soft_max = 8,
                soft_min = -8,
                precision = 1,
                step = 100
                )

    BaseColorFilepath : StringProperty(
                description = 'The texture image file path.',
                update= UpdateMSTSImage,
                subtype='FILE_PATH',
                )

    UpdateNodes : BoolProperty(
                name='Update Shader',
                description = 'Rebuild shader nodes from BaseColorFilepath',
                default = False,
                update= UpdateMSTSMaterial,
                )


LightingOptions = { "NORMAL":-5,
                    "SPECULAR25":-6,
                    "SPECULAR750":-7,
                    "FULLBRIGHT":-8,
                    "HALFBRIGHT":-11,
                    "DARK":-12,
                    "CRUCIFORM":-9,
                    "EMISSIVE":-5
                  }

class msts_scene_props(bpy.types.PropertyGroup):
    # these properties appear in the file export dialog

    SFilepath : StringProperty( default = "" )

    RetainNames : BoolProperty(name='Retain Names', description = 'Disables object merging optimizations', default = False )


    UseDDS : BoolProperty(name='Use DDS', description = 'Export Texture type as DDS instead of ACE', default = False )

'''
This code converts from Blender data structures to MSTS data structures
from here down to the Library section, the code uses blender coordinate system unless specified as MSTS
'''

#####################################
def GetFileNameNoExtension( filepath ):  # eg filePath = '//textures\\redtile.tga'
    s = filepath.replace( '\\','/' )       # s = '//textures/redtile.tga'
    parts = s.split( '/' )              # parts = ['','','textures','redtile.tga']
    lastPart = parts[ len(parts)-1 ]        # lastPart = 'redtile.tga'
    noextension = os.path.splitext( lastPart )[0]   # noextension = 'redtile'
    return noextension

#####################################
# convert to path relative to this blend file if possible
# otherwise just return filepath
def TryGetRelPath( filepath ):

    try:
        return bpy.path.relpath( filepath )
    except:
        return filepath



#####################################
# specifies how normals are to be calculated
class Normals:       # passed to AddFaceToSubObject to request special handling of normals
        Face = 0        # flat normals
        Smooth = 1      # smoothed ( can be overriden per face )
        Out = 3         # normals radiate out from center of model   Mesh or Material Property:  NORMALS = OUT
        Up = 4          # all normals face up   Mesh or Material Property:  NORMALS = UP
        Fillet = 5      # bevels are modified to appear rounded  Mesh or Material Property: NORMALS = FILLET
        OutX = 6        # normals radiate out to the left and right along objects x=0,z=-4 axis


#####################################
# given a blender property override like NORMALS = UP, and an initialNormal,
# return the normal state after the override is applied
# propertyString represents eg "UP"
# initialNormal eg Normals.Face
def GetNormalsOverride( propertyString, initialNormal ):
        if propertyString == 'UP':
            return Normals.Up
        elif propertyString == 'OUT':
            return Normals.Out
        elif propertyString == 'FILLET':
            return Normals.Fillet
        elif propertyString == "OUTX":
            return Normals.OutX
        return initialNormal



#####################################
def iShaderAdd( shaderName ):

    if shaderName in ExportShape.Shaders:
        iShader = ExportShape.Shaders.index(shaderName)
    else:
        iShader = len( ExportShape.Shaders )
        ExportShape.Shaders.append( shaderName )
    return iShader


#####################################
def iFilterAdd( filterName ):

    if filterName in ExportShape.Filters:
        iFilter = ExportShape.Filters.index( filterName )
    else:
        iFilter = len( ExportShape.Filters )
        ExportShape.Filters.append( filterName )
    return iFilter


#####################################
# imageName is in msts format, eg unionstop.ace
def iImageAdd( imageName ):

    if imageName==None or imageName == '':
        imageName = 'blank'
    if UseDDS==False:
        imageName = imageName + '.ace'
    else:
        imageName = imageName + '.dds'

    for iImage in range(0, len( ExportShape.Images)):
        if ExportShape.Images[iImage] == imageName:
            return iImage

    iImage = len( ExportShape.Images)
    ExportShape.Images.append( imageName)
    return iImage


#####################################
def iTextureAdd( imageName, mipMapLODBias ):   # creates both texture and image entries

    iImage = iImageAdd( imageName )

    for iTexture in range( 0, len( ExportShape.Textures)):
        texture = ExportShape.Textures[iTexture]
        if texture.iImage == iImage and texture.MipMapLODBias == mipMapLODBias:
            return iTexture

    iTexture = len( ExportShape.Textures )
    newTexture = Texture()
    newTexture.iImage = iImage
    newTexture.iFilter = iFilterAdd( 'MipLinear' )
    newTexture.MipMapLODBias = mipMapLODBias
    ExportShape.Textures.append( newTexture )
    return iTexture

#####################################
def UVOpsMatch( opsList,  specifierList ):       # specifiers is a list ( operation, textureAddressMode ) pairs

    if len( opsList ) != len( specifierList ):
        return False
    for i in range( 0, len( opsList ) ):
        eachUVOp = opsList[i]
        operation = specifierList[i][0]
        if eachUVOp.__class__ != operation: return False
        if operation == UVOpCopy and eachUVOp.TextureAddressMode != specifierList[i][1]: return False
        elif operation == UVOpReflectMapFull: continue
    return True

#####################################
def iLightConfigAdd( uvops ):    # it a list of   ( operation, textureAddressMode ) pairs

    # see if its already set up
    for i in range( 0, len( ExportShape.LightConfigs ) ):
        if UVOpsMatch( ExportShape.LightConfigs[i].UVOps, uvops ):
                return i

    # no, so create it
    i = len( ExportShape.LightConfigs )
    newLightConfig = LightConfig()
    for eachop in uvops:
        if eachop[0] == UVOpCopy:
            newUVOp = UVOpCopy()
            newUVOp.TextureAddressMode = eachop[1]
        elif op[0] == UVOpReflectMapFull:
            newUVOp = UVOpReflectMapFull()
        else:
            raise Exception( "PROGRAM ERROR: UNDEFINED UV OPERATION" )
        newLightConfig.UVOps.append( newUVOp )
    ExportShape.LightConfigs.append( newLightConfig )
    return i

#####################################
def iColorAdd( color ):   # a r g b
    global UniqueColors
    return UniqueColors.IndexOf( color )

#####################################
def iLightMaterialAdd( lm ):  # diff, amb, spec, emmisive, power
    global UniqueLightMaterials
    return UniqueLightMaterials.IndexOf( lm )


#####################################
def iVertexStateAdd( flags, iMatrix, iLightMaterial, iLightConfig ):
    i = len( ExportShape.VertexStates )  # use the last correct entry - earlier ones will have a full vtx_set
    while i > 0:
        i -= 1
        eachVertexState = ExportShape.VertexStates[i]
        if eachVertexState.Flags == flags \
          and eachVertexState.iMatrix == iMatrix \
          and eachVertexState.iLightMaterial == iLightMaterial \
          and eachVertexState.iLightConfig == iLightConfig:
            # we found one
            return i
    # we didn't find it, so add it and add a corresponding vertex set to every sub_object
    i = len( ExportShape.VertexStates )
    newVertexState = VertexState()
    newVertexState.Flags = flags
    newVertexState.iMatrix = iMatrix
    newVertexState.iLightMaterial = iLightMaterial
    newVertexState.iLightConfig = iLightConfig
    ExportShape.VertexStates.append( newVertexState )
    # every vertex_state needs a matching vertex_set
    for lodControl in ExportShape.LodControls:
        for distanceLevel in lodControl.DistanceLevels:
            for subobject in distanceLevel.SubObjects:
                subobject.VertexSets.append( VertexSet() ) #Note: unused vertexSets are purged during write
    return i

#####################################
def MatchList( lista, listb ):

    if len(lista) != len(listb):
        return False
    for i in range( 0, len(lista) ):
        if lista[i] != listb[i]:
            return False
    return True

#####################################
def ColorWord( floats ):

    value = 0;
    for f in floats:
        value = value * 256
        value = value + round( f * 255 )
    return value

#####################################
def IsLinkedToBaseColor( imageNode ):

    for eachLink in imageNode.outputs['Color'].links:
        if eachLink.to_socket.name == 'Base Color' or \
           eachLink.to_socket.name == 'Color':
                return True

    return False

#####################################
# return an msts format image name, eg unionstop.ace
def BaseColorImageFrom( material ):

    if material == None:
        return None

    # if we specified a filepath in MSTS Material panel, use it
    if material.msts.BaseColorFilepath != '':
        return GetFileNameNoExtension( material.msts.BaseColorFilepath )

    # Otherwise, look for an image in the shader node tree linked to a Color or Base Color input
    if material.node_tree != None:
        for eachNode in material.node_tree.nodes:
            if eachNode.bl_idname == 'ShaderNodeTexImage':
                if eachNode.image.source == 'FILE':
                    if IsLinkedToBaseColor( eachNode ):
                        return GetFileNameNoExtension( eachNode.image.filepath )

    return None


#####################################
def iPrimStateAdd( iVertexState, zBias, iShader, alphaTestMode, iLightConfig, iTextures ):

    global ExportShape

    # see if this one's already set up
    for i in range( 0, len( ExportShape.PrimStates ) ):
        eachPrimState = ExportShape.PrimStates[i]
        if eachPrimState.iVertexState == iVertexState \
          and eachPrimState.zBias == zBias \
          and eachPrimState.iShader == iShader \
          and eachPrimState.AlphaTestMode == alphaTestMode \
          and eachPrimState.iLightConfig == iLightConfig \
          and MatchList( eachPrimState.iTextures, iTextures ):
                return i

    # we didn't find it so add it
    i = len( ExportShape.PrimStates )
    newPrimState = PrimState()
    newPrimState.Label = ExportShape.Matrices[iHierarchy].Label
    if len( iTextures) > 0:
        texture = ExportShape.Textures[iTextures[0]]
        imagename = ExportShape.Images[texture.iImage]
        newPrimState.Label = newPrimState.Label + '_' + os.path.splitext( imagename)[0]
    for iTexture in iTextures:
        newPrimState.iTextures.append(iTexture)
    newPrimState.zBias = zBias
    newPrimState.iVertexState = iVertexState
    newPrimState.iShader = iShader
    newPrimState.AlphaTestMode = alphaTestMode
    newPrimState.iLightConfig = iLightConfig
    ExportShape.PrimStates.append( newPrimState )
    return i


#####################################
def iPrimitiveAppend( subObject, iPrimState ):

    i = len( subObject.Primitives )
    newPrimitive = Primitive()
    newPrimitive.iPrimState = iPrimState
    subObject.Primitives.append( newPrimitive )
    return i

#####################################
def iPrimitiveAdd( subObject, iPrimState ):

    i = len( subObject.Primitives )
    while i > 0:                                                # use the last correct entry - earlier ones could be full
        i -= 1
        primitive = subObject.Primitives[i]
        if primitive.iPrimState == iPrimState:
            return i
    #we didn't find it, so add a new one
    i = iPrimitiveAppend( subObject, iPrimState )
    return i


#####################################
class UniqueArray:

    def __init__(self, data, hash, tolerance ):
        self.data = data
        self.keys = {}
        self.hash = hash
        self.tolerance = tolerance

    def __getitem__(self, i):
        return self.data[i]

    def Match( self, v1, v2 ):
        for i in range( 0, len( v1 ) ):
            if abs( v1[i] - v2[i] ) > self.tolerance:
                return False
        return True

    def Key( self, value ):
        key = 0.0
        for v in value:
            key += v
        return round(key,self.hash)

    def IndexOf( self, value ):
        key = self.Key( value )
        index = self.keys.get(key,-1)
        while index != -1:
            storedValue = self.data[index]
            if self.Match( value, storedValue):
                return index
            key += .9  # in case of a hash collision, we advance the key this amount
            index = self.keys.get(key,-1)
        # Performance improvement, live with some duplicate values to speed up export
        global FastExport
        if FastExport:
            if len( self.keys ) > 4000:
                self.keys.clear()
        # we didn't find it so add it
        index = len( self.data )
        self.data.append( value )
        self.keys[ key ] = index
        return index

#####################################
def iVertexAdd( iPoint, iNormal, iUVs, vertexSet, color1, color2 ):

    # search index to see if a matching vertex exists
    if iPoint in vertexSet.index:
        for iVertex in vertexSet.index[iPoint]:
            vertex = vertexSet.Vertices[iVertex]
            if vertex.iPoint == iPoint and vertex.iNormal == iNormal and MatchList(vertex.iUVs,iUVs) and vertex.Color1 == color1 and vertex.Color2 == color2 :
                return iVertex

    #we didnt' find it so add a new one
    vertex = Vertex()
    vertex.iPoint = iPoint
    vertex.iNormal = iNormal
    vertex.Color1 = color1
    vertex.Color2 = color2
    for iUV in iUVs:
        vertex.iUVs.append( iUV )
    iVertex = len( vertexSet.Vertices )
    vertexSet.Vertices.append( vertex )

    #index on iPoint for speedup
    if not iPoint in vertexSet.index:
        vertexSet.index[iPoint] = []
    vertexSet.index[iPoint].append( iVertex )

    return iVertex

#####################################
def iUVPointAdd( uvPoint ):
    global UniqueUVPoints
    MSTSuvPoint =  (uvPoint[0],1-uvPoint[1])
    return UniqueUVPoints.IndexOf( MSTSuvPoint )

#####################################
def iNormalAdd( vector ):
    global UniqueNormals
    MSTSvector =  (vector[0],vector[2],vector[1] )
    return UniqueNormals.IndexOf( MSTSvector )



#####################################
# When a subObject is full, create a new empty
def SplitSubObject( subObject):
    newSubObject = SubObject( subObject.DistanceLevel )
    # DEBUG print( 'split subObject ',subObject.sequence,' into ',newSubObject.sequence )
    newSubObject.Flags = subObject.Flags
    newSubObject.Priority = subObject.Priority
    newSubObject.iHierarchy = subObject.iHierarchy
    for eachVertexSet in subObject.VertexSets:
        newVertexSet = VertexSet()
        newSubObject.VertexSets.append( newVertexSet ) #unused vertex sets are purged during write
    subObject.DistanceLevel.SubObjects.append( newSubObject )
    return newSubObject

########################################
# find the last subobject that uses the specified flags
# or return None of none found
def FindSubObject( distanceLevel, flags, priority, iHierarchy):

    # starting at the end, look for one with the needed flags
    iLast = len( distanceLevel.SubObjects ) - 1
    while iLast >= 0:
        subObject = distanceLevel.SubObjects[iLast]
        if HierarchyOptimization:
            if subObject.Flags == flags and subObject.Priority == priority and subObject.iHierarchy == iHierarchy:
                return subObject
        else:
            if subObject.Flags == flags and subObject.Priority == priority:
                return subObject
        iLast -= 1

    return None


#####################################
def ChildOf( ancestor, object ):
    if object.parent == None:
        return False
    if object.parent == ancestor:
        return True
    if ChildOf( ancestor, object.parent ):
        return True
    return False

#####################################
def ConstructMatrix( ancestor, object ):
    # construct a cumulative transfer matrix from object to ancestor
    if object == ancestor:
        return mathutils.Matrix.Translation((0,0,0))
    if object.parent == None:
        return object.matrix_local
    if object.parent == ancestor:
        return object.matrix_local
    return ConstructMatrix( ancestor, object.parent ) @ object.matrix_local


#####################################
def IsMSTSDefinedName( name ):

    #if its one of the automatically animated parts
    # TODO Include any allcaps part
    mstsName = MSTSName( name)
    animatedParts = ('BOGIE1','BOGIE2','WHEELS11','WHEELS12','WHEELS13','WHEELS21','WHEELS22','WHEELS23' )
    return animatedParts.count( mstsName.upper() ) > 0


#####################################
def IsAnimated( nodeObject ):

    #it has some animation defined
    if nodeObject.animation_data != None:
        if nodeObject.animation_data.action != None:
            fcurves = nodeObject.animation_data.action.fcurves
            if len(fcurves) > 0:
                return True
    return False

#####################################
def InLodCollections( nodeObject ):

    global LodCollections
    for eachLodCollection in LodCollections:
        if nodeObject in eachLodCollection.all_objects.values():
            return True
    return False

#####################################
def IsRetained( nodeObject ):
    # return true if we should retain this level of hierarchy else collapse it down

    if InLodCollections( nodeObject ):
        return RetainNames or IsAnimated( nodeObject) or IsMSTSDefinedName( nodeObject.name )
    else:
        return False


#####################################
def MergeChildren( nodeObject, iParent ):

    for eachNode in nodeObject.children:
        if IsRetained( eachNode ):
            BuildHierarchyFrom( eachNode, iParent )
        else:
            MergeChildren( eachNode, iParent )
            hierarchyObjects[iParent].append( eachNode )

#####################################
def BuildHierarchyFrom( nodeObject, iParent ):
    global hierarchy
    global hierarchyObjects

    index = len(hierarchy)
    hierarchy.append( iParent )
    hierarchyObjects.append( [ nodeObject ] )
    MergeChildren( nodeObject, index )




#####################################
# make a blender name into a legal MSTS name
def MSTSName( name ):

    name = name.replace( '.','_')
    return name


#####################################
def CreateMSTSMatrices():
    global ExportShape
    global hierarchy
    global hierarchyObjects

    ExportShape.Matrices = []
    for i in range( 0, len( hierarchy ) ):
        thisNodeObject = hierarchyObjects[i][0]
        mstsMatrix = MSTSMatrix()
        mstsMatrix.Label = MSTSName(thisNodeObject.name)
        if hierarchy[i] != -1:
            parentNodeObject = hierarchyObjects[hierarchy[i]][0]
            blenderMatrix = ConstructMatrix( parentNodeObject, thisNodeObject )

            mstsMatrix.M11 = blenderMatrix[0][0]  # note coordinate conversion and use of new 2.62 indexing
            mstsMatrix.M13 = blenderMatrix[1][0]
            mstsMatrix.M12 = blenderMatrix[2][0]

            mstsMatrix.M31 = blenderMatrix[0][1]
            mstsMatrix.M33 = blenderMatrix[1][1]
            mstsMatrix.M32 = blenderMatrix[2][1]

            mstsMatrix.M21 = blenderMatrix[0][2]
            mstsMatrix.M23 = blenderMatrix[1][2]
            mstsMatrix.M22 = blenderMatrix[2][2]

            mstsMatrix.M41 = blenderMatrix[0][3]
            mstsMatrix.M43 = blenderMatrix[1][3]
            mstsMatrix.M42 = blenderMatrix[2][3]

        ExportShape.Matrices.append( mstsMatrix )


#####################################
# create an msts point for each vertex in the blender mesh
# return an offset into the shape's point table
def AddMeshVertexPoints( mesh, offsetMatrix ):

    iPointOffset = len( ExportShape.Points )
    for v in mesh.vertices:
        blenderPoint = offsetMatrix @ v.co
        mstspoint = (blenderPoint[0],blenderPoint[2],blenderPoint[1] )
        ExportShape.Points.append( mstspoint )

    return iPointOffset


#####################################
# update the global lowerBound and upperBound vectors
# transform its points into world coordinates via the offsetMatrix
def ExtendBoundsForMesh( mesh, offsetMatrix ):

    global UpperBound
    global LowerBound

    for eachVertex in mesh.vertices:
        v = offsetMatrix @ eachVertex.co
        if v.x > UpperBound.x:  UpperBound.x = v.x
        if v.y > UpperBound.y:  UpperBound.y = v.y
        if v.z > UpperBound.z:  UpperBound.z = v.z
        if v.x < LowerBound.x:  LowerBound.x = v.x
        if v.y < LowerBound.y:  LowerBound.y = v.y
        if v.z < LowerBound.z:  LowerBound.z = v.z



#####################################
def HasGeometry( object ):

    # make sure its not a camera, light etc that do not have geometry
    return object.type in ['MESH']  # TODO add sup
