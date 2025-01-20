bl_info = {     "name": "Export OpenRails/MSTS Shape File(.s)",
                "author": "Wayne Campbell/Pete Willard",
                "version": (4, 7),
                "blender": (3, 6, 0),
                "location": "File > Export > OpenRails/MSTS (.s)",
                "description": "Export file to OpenRails/MSTS .S format",
                "category": "Import-Export"}

# Updated for Blender 4.0+ compatibility with fallback for older versions
# Version 4.6


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
def RecreateShaderNodes( m ):

    # remove any existing nodes
    m.use_nodes = True
    m.node_tree.nodes.clear()
    m.node_tree.links.clear()
    # create the nodes
    MNode = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    BNode = m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    TNode = m.node_tree.nodes.new('ShaderNodeTexImage')
    UNode = m.node_tree.nodes.new('ShaderNodeUVMap')
    # layout the shader screen
    MNode.location.x = 300
    BNode.location.x = 0
    TNode.location.x = -300
    UNode.location.x = -550
    # Set active node
    MNode.select = False
    BNode.select = False
    TNode.select = False
    UNode.select = False
    m.node_tree.nodes.active = None
    # setup specularity

    if BlenderVersion < (4, 1, 0):
        if m.msts.Lighting == 'SPECULAR25':
            BNode.inputs['Specular'].default_value = 0.1
            BNode.inputs['Roughness'].default_value = 0.3
        elif m.msts.Lighting == 'SPECULAR750':  
            BNode.inputs['Specular'].default_value = 0.1
            BNode.inputs['Roughness'].default_value = 0.1
        else:
            BNode.inputs['Specular'].default_value = 0.0
            BNode.inputs['Roughness'].default_value = 1.0
    else:
        if m.msts.Lighting == 'SPECULAR25':
            BNode.inputs['IOR'].default_value = 0.1
            BNode.inputs['Roughness'].default_value = 0.3
        elif m.msts.Lighting == 'SPECULAR750':  
            BNode.inputs['IOR'].default_value = 0.1
            BNode.inputs['Roughness'].default_value = 0.1
        else:
            BNode.inputs['IOR'].default_value = 0.0
            BNode.inputs['Roughness'].default_value = 1.0
         
    # setup image
    if os.path.exists( bpy.path.abspath(m.msts.BaseColorFilepath) ):
        TNode.image = GetImage( m.msts.BaseColorFilepath )

    # setup uvs
    UNode.uv_map = 'UVMap'
    # link the nodes
    m.node_tree.links.new(MNode.inputs['Surface'],BNode.outputs['BSDF'])
    m.node_tree.links.new(BNode.inputs['Base Color'],TNode.outputs['Color'])
    if m.msts.Transparency != "OPAQUE":
        m.node_tree.links.new(BNode.inputs['Alpha'],TNode.outputs['Alpha'])
    m.node_tree.links.new(TNode.inputs['Vector'],UNode.outputs['UV'])
    # TODO Add support for additional msts lighting modes, eg cruciform, etc

#####################################
# called when the MSTS material panel settings are changed
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

    if hasattr(context, 'material'):
        if context.material != None:
            mstsmaterial= context.material.msts
            if mstsmaterial.UpdateNodes:

                blM = context.material
                blM.use_backface_culling = True

                if blM.msts.Transparency == "OPAQUE":
                    blM.blend_method = "OPAQUE"
                elif blM.msts.Transparency == "CLIP":
                    blM.blend_method = "CLIP"
                elif blM.msts.Transparency == "ALPHA":
                    blM.blend_method = "BLEND"
                elif blM.msts.Transparency == "ALPHA_SORT":
                    blM.blend_method = "BLEND"



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
                description = 'Change shader nodes to match these settings',
                default = True ,
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
    iHierarchy = ExportShape.VertexStates[iVertexState].iMatrix
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
    return object.type in ['MESH']  # TODO add support for 'CURVE','SURFACE','META','FONT'

#####################################
# adds to a sub_object in this distance_level
# iPointOffset informs the difference between the blender vertex index and the msts vertex index
# normal specifies an override to the blender supplied normal, eg Normals.Face .Out .Up .Smooth etc
# tranform the mesh points by relativeMatrix
# apply the normalOverrides
# generate triangle lists
def AddTriangleToSubObject( mesh, mstsMaterial, blTriangle , windingOrder, offsetMatrix, iPointOffset ):

    color1 = 0xFFFFFFFF   # vertex colors ( when vertex color layer not present )
    color2 = 0xFF000000

    normalOverride = mstsMaterial.normalOverride
    if normalOverride == Normals.Face:         # if we didn't specify a special normal mesh property
        if blTriangle.use_smooth:         # Per face override for smooth normals
            normalOverride = Normals.Smooth

    subObject = mstsMaterial.subObject
    vertexSet = subObject.VertexSets[mstsMaterial.iVertexState]

    iPrimitive = mstsMaterial.iPrimitive
    primitive = subObject.Primitives[iPrimitive]

    for indexList in windingOrder:
        mstsTriangle = []
        for i in indexList:
            iblVert = blTriangle.vertices[i]

            iLoop = blTriangle.loops[i]

            iUVs = []
            for eachLayer in mstsMaterial.uv_layers:
                bluv = eachLayer.data[iLoop].uv
                iUV = iUVPointAdd( bluv )
                iUVs.append(iUV)

            if normalOverride == Normals.Out:
                # use tree type tangent shading ( normals radiate out from center )
                normal = mesh.vertices[iblVert].co
                normal = offsetMatrix.to_3x3() @ normal
                normal.normalize()
            elif normalOverride == Normals.Up:
                normal = ( 0,0,1 )
            elif normalOverride == Normals.Smooth:
                # support Auto smooth
                normal=Vector(blTriangle.split_normals[i])
                normal = offsetMatrix.to_3x3() @ normal
                normal.normalize()
            elif normalOverride == Normals.OutX:
                # radiate out from below Y axis ( ie LPSTrack100m side vegetation )
                normal = offsetMatrix.translation
                normal = Vector( (normal.x-4, 0, normal.z + 12) )
                normal.normalize()
            else:
                # flat shading uses the face normal
                normal = blTriangle.normal
                normal = offsetMatrix.to_3x3() @ normal
                normal.normalize()

            iNormal = iNormalAdd( normal )

            iPoint = iblVert + iPointOffset
            if iPoint >= len( ExportShape.Points ):
                raise Exception( 'PROGRAM ERROR:  iPoint out of range' )

            mstsTriangle.append(  iVertexAdd( iPoint, iNormal, iUVs, vertexSet, color1, color2) )

        # Console output, inform new draw call started
        if len( primitive.Triangles ) == 0:
            sequence = mstsMaterial.subObject.sequence
            if len( mstsMaterial.iTextures) > 0:
                texture = ExportShape.Textures[mstsMaterial.iTextures[0]]
                filename = ExportShape.Images[texture.iImage]
            else:
                filename = ''
            # DEBUG print( "                           SubObject ",sequence," Draw ", filename, " ", mstsMaterial.blMaterial.msts.Transparency, " ",mstsMaterial.blMaterial.msts.Lighting, " MipBias=",mstsMaterial.blMaterial.msts.MipMapLODBias )
            print( "                              Draw ", filename, " ", mstsMaterial.blMaterial.msts.Transparency, " ",mstsMaterial.blMaterial.msts.Lighting, " MipBias=",mstsMaterial.blMaterial.msts.MipMapLODBias )

        primitive.Triangles.append( mstsTriangle )
        # add a face normal ( used by MSTS for culling purposes )
        normal =  offsetMatrix.to_3x3() @ blTriangle.normal
        normal.normalize()
        primitive.iNormals.append( iNormalAdd( normal ) )


# build one for each material in the mesh
class MSTSMaterialDetail:

    def __init__(self ):

        self.flags = '00000400 -1 -1 000001d2 000001c4'
        self.priority = 0
        self.uv_layers = []
        self.normalOverride = Normals.Face
        self.subObject = None
        self.iTextures = []
        self.uvops = []
        self.zBias = 0.0
        self.vertexFlags = 0
        self.vertexLight = LightingOptions[ 'NORMAL' ]
        self.alphaTestMode = 0
        self.iShader = 0
        self.iLightConfig = 0
        self.iVertexState = 0
        self.iHierarchy = 0
        self.iPrimState = 0
        self.subObject = None
        self.iPrimitive = 0
        self.blMaterial = None   # corresponding Blender material


def GetMSTSMaterialDetails( distanceLevel, mesh, blMaterial, normalOverride, iHierarchy, objectName):

    mstsMaterial = MSTSMaterialDetail()

    mstsMaterial.blMaterial = blMaterial

    mstsMaterial.iHierarchy = iHierarchy

    mstsMaterial.normalOverride = normalOverride

    if blMaterial.msts.Transparency == 'ALPHA':
        mstsMaterial.flags = '00000400 -1 -1 000001d2 000001c4'
        mstsMaterial.priority = 1
    elif blMaterial.msts.Transparency == 'ALPHA_SORT':
        mstsMaterial.flags = '00000500 0 0 000001d2 000001c4'
        mstsMaterial.priority = 2
    if blMaterial.msts.Lighting.startswith( 'SPECULAR'):
        # clear bit 10
        # eg  00000500 become 00000100 and 0000400 becomes  00000000
        d5 = int(mstsMaterial.flags[5],16)
        d5 &= 0b1011
        mstsMaterial.flags = mstsMaterial.flags[0:5]+hex(d5)[2]+mstsMaterial.flags[6:]

    subObject = FindSubObject( distanceLevel, mstsMaterial.flags, mstsMaterial.priority, iHierarchy)

    if subObject == None:
        # create the required subobject
        subObject = SubObject(distanceLevel)
        # DEBUG print( "new subobject ", subObject.sequence )
        subObject.Flags = mstsMaterial.flags
        subObject.Priority = mstsMaterial.priority
        subObject.iHierarchy = mstsMaterial.iHierarchy
        # every vertex_state needs a matching vertex_set
        for eachVertexState in ExportShape.VertexStates:    # note, unused vertexsets are purged at during write
            subObject.VertexSets.append( VertexSet() )
        distanceLevel.SubObjects.append( subObject )

    mstsMaterial.subObject = subObject

    #  this could be improved to look for the uv layer in the node tree
    #  and in the future handle multiple uvs here
    if not 'UVMap' in mesh.uv_layers:
        raise MyException( "Missing UVMap in: " + objectName)
    mstsMaterial.uv_layers = [ mesh.uv_layers['UVMap']] #but what about beziers generate map 'Orco'


    # find image used by material
    imageName = BaseColorImageFrom( blMaterial ) # may return None
    mipMapLODBias = blMaterial.msts.MipMapLODBias
    mstsMaterial.iTextures.append( iTextureAdd( imageName, mipMapLODBias ) )
    textureAddressMode = 1 # repeat
    # textureAddressMode = 3   # extend edges
    # textureAddressMode = 4   # clamp with border
    # textureAddressMode = 2   # mirror
    mstsMaterial.uvops.append( ( UVOpCopy, textureAddressMode ) )

    # now configure options based on the material settings
    mstsMaterial.zBias = 0.0

    # Set Up Vertex Lighting
    mstsMaterial.vertexFlags = 0
    mstsMaterial.vertexLight = LightingOptions[ blMaterial.msts.Lighting ]

    if blMaterial.msts.Transparency == 'CLIP':
        mstsMaterial.alphaTestMode = 1
    else:
        mstsMaterial.alphaTestMode = 0

    if blMaterial.msts.Lighting == "EMISSIVE":
        if blMaterial.msts.Transparency == 'OPAQUE':
            mstsMaterial.iShader = iShaderAdd( 'Tex' )
        else:
            mstsMaterial.iShader = iShaderAdd( 'BlendATex' )
    else:
        if blMaterial.msts.Transparency == 'OPAQUE':
            mstsMaterial.iShader = iShaderAdd( 'TexDiff' )
        else:
            mstsMaterial.iShader = iShaderAdd( 'BlendATexDiff' )


    mstsMaterial.iLightConfig = iLightConfigAdd( mstsMaterial.uvops )
    mstsMaterial.iVertexState = iVertexStateAdd( mstsMaterial.vertexFlags, iHierarchy, mstsMaterial.vertexLight, mstsMaterial.iLightConfig )

    mstsMaterial.iPrimState = iPrimStateAdd( mstsMaterial.iVertexState, mstsMaterial.zBias, mstsMaterial.iShader, mstsMaterial.alphaTestMode, mstsMaterial.iLightConfig, mstsMaterial.iTextures )
    mstsMaterial.iPrimitive = iPrimitiveAdd( subObject, mstsMaterial.iPrimState )


    return mstsMaterial



#####################################
# add this mesh,
# create any needed subObjects
# create a prim_state referencing iHierarchy
# translate the mesh points by relativeMatrix
# apply the normalOverrides
# transfer all vertex points to msts points
# generate triangle lists
def AddMesh( distanceLevel, mesh, iHierarchy, offsetMatrix, normalsProperty, objectName ):

    print( '              triangles = ', len( mesh.loop_triangles ) )

    # determine normal override from the object Properties
    normalOverride = Normals.Face
    if normalsProperty == 'UP':
        normalOverride = Normals.Up
    elif normalsProperty == 'OUT':
        normalOverride = Normals.Out
    elif normalsProperty == 'FILLET':
        normalOverride = Normals.Fillet
    elif normalsProperty == "OUTX":
        normalOverride = Normals.OutX
    # evaluate any special handling for normals
    #   Note: these may be overriden 'per face' in AddFaceToSubObject
    if normalOverride == Normals.Fillet:
        # preprocess normals for filleted appearance
        # verts in a flat face will use the face normal
        # verts in a smoothed face use the normal of the adjacent flat face
        for tri in mesh.loop_triangles:
            if not tri.use_smooth:
                for iVert in tri.vertices:
                  mesh.vertices[iVert].normal = tri.normal
        # now handle them like standard smoothed normals
        normalOverride = Normals.Face

    # for every vertex in the blender mesh, add a corresponding msts point
    iPointOffset = AddMeshVertexPoints( mesh, offsetMatrix )

    ExtendBoundsForMesh( mesh, offsetMatrix @ hierarchyObjects[iHierarchy][0].matrix_world )

    # create msts materials for each mesh material
    mstsMaterials = []
    for blMaterial in mesh.materials:
        if blMaterial != None:
            mstsMaterials.append( GetMSTSMaterialDetails( distanceLevel, mesh, blMaterial, normalOverride, iHierarchy, objectName ) )
        else:
            raise MyException( "Empty Material on object: " + objectName )

    #if scale is negative, invert winding order of triangles
    scale = offsetMatrix.to_scale()
    sign = scale.x * scale.y * scale.z
    if sign < 0:
       windingOrder = ( (0,1,2),  ) #inverted
    else:
       windingOrder = ( (0,2,1),  ) #forward


    # for speedup, resolve unique points only per mesh
    global UniqueUVPoints
    global UniqueNormals
    UniqueUVPoints.keys.clear()
    UniqueNormals.keys.clear()

    for iTriangle in range( 0, len( mesh.loop_triangles ) ):

        if iTriangle % 10 == 0:   # reduce the update rate
            UpdateProgress()

        blTriangle = mesh.loop_triangles[iTriangle]

        if blTriangle.material_index < len( mstsMaterials ):
            mstsMaterial = mstsMaterials[ blTriangle.material_index ]
        else:
            raise MyException( "Missing Materials on object: " + objectName )

        # check if the subobject is full
        subObject = mstsMaterial.subObject
        vertexCount = 0
        for eachVertexSet in subObject.VertexSets:
            vertexCount += len( eachVertexSet.Vertices )

        if vertexCount + 3 > MaxVerticesPerSubObject:
            # subObject is full so start a new one
            subObject = SplitSubObject( subObject)
            mstsMaterial.iPrimitive = iPrimitiveAdd( subObject, mstsMaterial.iPrimState )
            mstsMaterial.subObject = subObject

        # check if the primitive is full
        iPrimitive = mstsMaterial.iPrimitive
        primitive = subObject.Primitives[iPrimitive]

        if len(primitive.Triangles) * 3 + 3 > MaxVerticesPerPrimitive:
            # primitive is full so start a new one
            iPrimitive = iPrimitiveAppend( subObject, mstsMaterial.iPrimState )
            primitive = subObject.Primitives[iPrimitive]
            mstsMaterial.iPrimitive = iPrimitive


        AddTriangleToSubObject( mesh, mstsMaterial, blTriangle, windingOrder, offsetMatrix, iPointOffset )


#####################################
# add this collection and any child collections
def AddCollections( distanceLevel, collection, iHierarchy, relativeMatrix ):

    for eachObject in collection.objects:
        AddObject( distanceLevel, eachObject, iHierarchy, relativeMatrix @ eachObject.matrix_world )

    for eachChild in collection.children:
        AddCollections( distanceLevel, eachChild, iHierarchy, relativeMatrix )


#####################################
# add this object,
# transform its vertices by relativeMatrix
# link it to iHierarchy
def AddObject( distanceLevel, object, iHierarchy, relativeMatrix ):

        print( '    ',object.name )


        if object.is_instancer and object.instance_collection != None:

            # its a group instance, process each of its subobjects
            collection = object.instance_collection
            AddCollections( distanceLevel, collection, iHierarchy, relativeMatrix )

        # make sure its not a camera, light etc that do not have geometry
        elif HasGeometry( object ):

            # TODO handle particles
            # TODO handle dupliverts

            # determine normal override from the object Properties
            normalsProperty = object.data.get( 'NORMALS', '' )

            # Apply Modifiers as PREVIEW
            #depsgraph = bpy.context.evaluated_depsgraph_get()
            #ob_to_convert = object.evaluated_get(depsgraph)
            #Update here for Blender 4.1
            #mesh = ob_to_convert.to_mesh()
            
            mesh = get_evaluated_mesh(object)

            if BlenderVersion < (4,1,0):    # cope with loss of this feature in Blender 4.1 +
                mesh.calc_normals_split()
            
            mesh.calc_loop_triangles()

            AddMesh( distanceLevel, mesh, iHierarchy, relativeMatrix, normalsProperty, object.name )




#####################################
# eg MAIN_1000
# return ( 'MAIN',1000 )
def LodDistanceFromName( collectionName ):

    split = collectionName.rsplit( '_',1 )
    if len( split ) == 2:
        if split[0] != '':
            suffix = split[1]
            if suffix.isnumeric( ):
                distance = int( suffix )
                return distance

    return None



#####################################
# Add the specified   distanceLevel to the first LodControl
# Scan the hierarchy for objects that are in this collection and add them
# if it turns out to be empty, trim it out
def AppendDistanceLevel( lodCollection ):

    global ExportShape
    global hierarchy
    global hierarchyObjects

    distanceLimit = LodDistanceFromName( lodCollection.name )

    print( "DLEVEL "+str(distanceLimit) )
    # add the distance level
    lodControl = ExportShape.LodControls[0]
    distanceLevel = DistanceLevel( lodControl )
    distanceLevel.Selection = distanceLimit
    distanceLevel.Hierarchy = hierarchy
    lodControl.DistanceLevels.append( distanceLevel )

    for iHierarchy in range( 0, len( hierarchy ) ):
        for object in hierarchyObjects[iHierarchy]:
            if object in lodCollection.all_objects.values():
                nodeObject = hierarchyObjects[iHierarchy][0]
                relativeMatrix =  ConstructMatrix( nodeObject, object )
                AddObject( distanceLevel, object, iHierarchy, relativeMatrix )


    distanceLevel.SubObjects.sort( key=lambda subObject: subObject.Priority )

    if len( distanceLevel.SubObjects) == 0 or len( distanceLevel.SubObjects[0].Primitives ) == 0:
        print( 'WARNING - empty distance level ',distanceLevel.Selection )
        del lodControl.DistanceLevels[ len( lodControl.DistanceLevels )-1 ]



#####################################
# return a vector representing the geometric center of all the geometry
def FindCenter(  ):
    center = ( UpperBound + LowerBound ) / 2.0
    return center


#####################################
# from the bounds about the specified center
def FindBoundingRadius( center ):

    v = UpperBound - center
    BoundingRadiusSquared = v.x*v.x+v.y*v.y+v.z*v.z
    v = LowerBound - center
    dSquared = v.x*v.x+v.y*v.y+v.z*v.z
    if dSquared>BoundingRadiusSquared:
        BoundingRadiusSquared = dSquared
    return sqrt( BoundingRadiusSquared )

#####################################
def CompactPoints():
    global ExportShape

    oldPoints = ExportShape.Points
    ExportShape.Points = []
    uniquePoints = UniqueArray( ExportShape.Points,3,0.0001 )
    conversion = []

    for eachPoint in oldPoints:
       conversion.append( uniquePoints.IndexOf( eachPoint ) )

    for eachLODControl in ExportShape.LodControls:
        for eachDistanceLevel in eachLODControl.DistanceLevels:
            for eachSubObject in eachDistanceLevel.SubObjects:
                for eachVertexSet in eachSubObject.VertexSets:
                    for eachVertex in eachVertexSet.Vertices:
                        eachVertex.iPoint = conversion[eachVertex.iPoint]

#####################################
# remove empty primitives
def CompactPrimitives( ):

    emptyCount = 0
    for eachLODControl in ExportShape.LodControls:
        for eachDistanceLevel in eachLODControl.DistanceLevels:
            for eachSubObject in eachDistanceLevel.SubObjects:
                OKPrimitives = []
                for eachPrimitive in eachSubObject.Primitives:
                    if len( eachPrimitive.Triangles ) > 0:
                        OKPrimitives.append( eachPrimitive )
                    else:
                        emptyCount += 1
                eachSubObject.Primitives = OKPrimitives

    # DEBUG print ( "Compacting ",emptyCount," Empty Primitives" )

#####################################
# remove empty subobjects
def CompactSubObjects( ):

    emptyCount = 0
    for eachLODControl in ExportShape.LodControls:
        for eachDistanceLevel in eachLODControl.DistanceLevels:
                OKSubObjects = []
                for eachSubObject in eachDistanceLevel.SubObjects:
                    if len( eachSubObject.Primitives ) > 0:
                        OKSubObjects.append( eachSubObject )
                    else:
                        emptyCount += 1
                eachDistanceLevel.SubObjects = OKSubObjects

    # DEBUG print ( "Compacting ",emptyCount," Empty SubObjects" )


#####################################
def CreateEulerRotationController( iFC, fcurves ):

    rotationController = RotationController()

    #TODO this assumes all points are lined up at the same time
    for iKey in range(0,len(fcurves[iFC].keyframe_points)):
        key = RotationKey()
        key.Frame = fcurves[iFC].keyframe_points[iKey].co[0]
        x = fcurves[iFC+0].keyframe_points[iKey].co[1]
        y = fcurves[iFC+1].keyframe_points[iKey].co[1]  #Note coordinate conversion
        z = fcurves[iFC+2].keyframe_points[iKey].co[1]

        euler = mathutils.Euler( ( x,y,z ), 'XYZ' )
        quat = euler.to_quaternion()

        key.W = quat.w
        key.X = quat.x
        key.Y = quat.z
        key.Z = quat.y
        rotationController.Keys.append( key )

    return rotationController


#####################################
def CreateRotationController( iFC, fcurves ):

    rotationController = RotationController()

    #TODO this assumes all points are lined up at the same time
    for iKey in range(0,len(fcurves[iFC].keyframe_points)):
        key = RotationKey()
        key.Frame = fcurves[iFC].keyframe_points[iKey].co[0]
        key.W = fcurves[iFC].keyframe_points[iKey].co[1]
        key.X = fcurves[iFC+1].keyframe_points[iKey].co[1]
        key.Y = fcurves[iFC+3].keyframe_points[iKey].co[1]  #Note coordinate conversion
        key.Z = fcurves[iFC+2].keyframe_points[iKey].co[1]
        rotationController.Keys.append( key )

    return rotationController

#####################################
def CreateLinearController( iFC, fcurves ):

    linearController = PositionController()

    #TODO this assumes all points are lined up on the same frame
    for iKey in range( 0, len(fcurves[iFC].keyframe_points) ):
        key = LinearKey()
        key.Frame = fcurves[iFC].keyframe_points[iKey].co[0]
        key.X = fcurves[iFC].keyframe_points[iKey].co[1]
        key.Y = fcurves[iFC+2].keyframe_points[iKey].co[1]  #Note coordinate conversion
        key.Z = fcurves[iFC+1].keyframe_points[iKey].co[1]
        linearController.Keys.append( key )

    return linearController

#####################################
def CreateAnimationNode( nodeObject ):

    animationNode = AnimationNode()
    animationNode.Label = nodeObject.name
    if nodeObject.animation_data != None:
        if nodeObject.animation_data.action != None:
            fcurves = nodeObject.animation_data.action.fcurves
            iFC = 0
            while iFC < len( fcurves ):
                if fcurves[iFC].data_path == 'rotation_quaternion':
                    animationNode.Controllers.append( CreateRotationController( iFC, fcurves ) )
                    iFC += 4
                elif fcurves[iFC].data_path == 'rotation_euler':
                    animationNode.Controllers.append( CreateEulerRotationController( iFC, fcurves ) )
                    iFC += 3
                elif fcurves[iFC].data_path == 'location':
                    animationNode.Controllers.append( CreateLinearController( iFC, fcurves ) )
                    iFC += 3
                else:
                    print( 'Unknown controller type ',fcurves[iFC].data_path,' in ',nodeObject.name )
                    iFC += 1


    return animationNode

#####################################

class SceneCenterObject:    # a proxy to represent a node object at the center of the scene

    is_instancer = False
    type = 'PROXY'  # made up for this application, not one of Blender's recognized types
    animation_data = None
    matrix_world = Matrix()

    def __init__(self  ):
        self.children = []
        self.name = "MAIN"

    def get( self, parameter, default):
        return default

#####################################
def ExportShapeFile( collectionName, MSTSFilePath ):

    global ExportShape
    ExportShape = Shape()

    global UniqueUVPoints
    global UniqueNormals
    global UniqueColors
    global UniqueLightMaterials
    UniqueUVPoints = UniqueArray( ExportShape.UVPoints, 3, 0.0001 )
    UniqueNormals = UniqueArray( ExportShape.Normals, 2, 0.001 )
    UniqueColors = UniqueArray( ExportShape.Colors, 3, 0.0001 )
    UniqueLightMaterials = UniqueArray( ExportShape.LightMaterials, 1,1 )

    global UpperBound
    global LowerBound
    UpperBound = mathutils.Vector( ( -100000,-100000,-100000 ))
    LowerBound = mathutils.Vector( ( 100000, 100000, 100000 ) )

    global hierarchy        # linked list ie [-1,    0,1,1,0 ]
    global hierarchyObjects  # a list of objects for each level of the hierarchy, first element in list is the retained node [ MAIN, BOGIE1, WHEELS11, WHEELS12 .. ]
    hierarchy = []
    hierarchyObjects = []

    global LastSubObject
    global LastMaterial
    global LastiMatrix
    global LastiPrimState
    LastSubObject = None
    LastMaterial = None
    LastiMatrix = -1
    LastiPrimState = 0

    # For now, support a single LOD control
    lodControl = LodControl( ExportShape )
    ExportShape.LodControls.append( lodControl )

    mainCollection = bpy.context.scene.collection.children[collectionName]

    # get a sorted list of valid LOD Collections in MAIN
    lodNames = []
    for eachChild in mainCollection.children:
        childName = eachChild.name
        if childName.startswith( 'MAIN_' ):
            if LodDistanceFromName( childName ) != None:
                lodNames.append( childName )
    lodNames.sort()  #this sort fails if name does not have proper _xxxx suffix

    global LodCollections
    LodCollections = []
    for eachName in lodNames:
        LodCollections.append( mainCollection.children[eachName] )

    if len( LodCollections ) == 0:
        raise MyException( "No LOD collections in MAIN, eg MAIN_2000" )


    # add root objects to scene center
    rootObject = SceneCenterObject( )  # make everything relative to the scene center
    for eachObject in bpy.context.scene.objects:
        if eachObject.parent == None:
            rootObject.children.append( eachObject)

    BuildHierarchyFrom( rootObject, -1 )  # create global hierarchy array

    CreateMSTSMatrices( )

    # create a distance level for each one specified in MAIN
    for eachLodCollection in LodCollections:
        AppendDistanceLevel( eachLodCollection )

    # export animations
    if len( bpy.data.actions ) > 0:
        animation = Animation()
        ExportShape.Animations.append(animation)
        animation.FrameCount = bpy.context.scene.frame_end
        animation.FrameRate = 30
        for eachNode in hierarchyObjects:
            animation.AnimationNodes.append( CreateAnimationNode( eachNode[0] ) )

    # set up the volume sphere
    volumeSphere = VolumeSphere()
    # center = FindCenter( rootObject )  OR doesn't display properly with a computed center,
    center = rootObject.matrix_world.translation
    radius = FindBoundingRadius( center )
    MSTSvector = ( center.x, center.z, center.y )
    volumeSphere.Vector = MSTSvector
    volumeSphere.Radius = radius * 1.1  # add some safety margin
    ExportShape.Volumes.append( volumeSphere )

    print()
    print ( "Compacting ",len( ExportShape.Points )," Points ", end='' )
    CompactPoints()
    print ( " To ",len( ExportShape.Points ) )
    CompactPrimitives()
    CompactSubObjects()

    ExportShape.Write( MSTSFilePath )

    # Reporting
    print ( )
    for lodControl in ExportShape.LodControls:
        for distanceLevel in lodControl.DistanceLevels:
            triangleCount = 0
            primitiveCount = 0
            for eachSubObject in distanceLevel.SubObjects:
                for primitive in eachSubObject.Primitives:
                    if len( primitive.Triangles ) > 0:
                        primitiveCount += 1
                        triangleCount += len(primitive.Triangles)
            print ( "LOD: ",distanceLevel.Selection )
            print ( "     Triangles  = ", triangleCount )
            print ( "     Draw Calls = ", primitiveCount )
    print ( "IMAGES:" )
    for eachImage in ExportShape.Images:
        print( "   ",eachImage )
    print()
    return


'''  LIBRARY FUNCTIONS
All code below uses the MSTS coordinate system.

Structure matches the MSTS .s file with the following
top level name substitutions:

VolumeSphere
Matrix
VertexState
Texture
PrimState
Vertex
Primitive
VertexSet
SubObject
DistanceLevel
LodControl
RotationKey
TCBRotationKey
LinearKey
PositionController
RotationController
AnimationNode
Animation

This structure matches the MSTS .s file with the following exceptions

Add vertices to vertex_sets, not subobject.vertices as in MSTS.
It not needed to populate the sub_object_header data.

    Both of the above are generated from the underlying data on write.

'''

import codecs
import bpy

import math
from math import *



####################################
class STFWriter:
####################################
#
# Writes an MSTS structured unicode text file
#


        def __init__( self, filename):
                self.f = codecs.open(filename, 'w', encoding='utf-16')

        def WriteLine( self, string ):
                self.f.write( string )
                self.f.write( '\r\n' )

        def Write( self, string ):
                self.f.write( string )

        def Close(self ):
                self.f.close()




########################################
class VolumeSphere:

        def __init__( self ):
            self.Vector = ( 0.0,0.0,0.0 )
            self.Radius = 100.0

        def Write( self, stf ):
            stf.WriteLine( '        vol_sphere (' )
            stf.WriteLine( '            vector ( {0} {1} {2} ) {3}'.format( self.Vector[0],self.Vector[1],self.Vector[2],self.Radius))
            stf.WriteLine( '        )' )



########################################
class MSTSMatrix:

        def __init__( self ):
            self.Label = 'MAIN'
            self.M11 = 1.0
            self.M12 = 0.0
            self.M13 = 0.0
            self.M21 = 0.0
            self.M22 = 1.0
            self.M23 = 0.0
            self.M31 = 0.0
            self.M32 = 0.0
            self.M33 = 1.0
            self.M41 = 0.0
            self.M42 = 0.0
            self.M43 = 0.0


        def Write( self, stf ):
            stf.WriteLine( '        matrix {0} ( {1} {2} {3} {4} {5} {6} {7} {8} {9} {10} {11} {12} )'.format( self.Label,self.M11,self.M12,self.M13,self.M21,self.M22,self.M23,self.M31,self.M32,self.M33,self.M41,self.M42,self.M43 ))


########################################
class VertexState:

    def __init__( self ):
        self.Flags = 0
        self.iMatrix = 0
        self.iLightMaterial = -5
        self.iLightConfig = 0

    def Write( self, stf ):
        stf.WriteLine( '        vtx_state ( {0:08X} {1} {2} {3} 00000002 )'.format( self.Flags, self.iMatrix, self.iLightMaterial, self.iLightConfig ))



########################################
class Texture:

    def __init__(self):
        self.iImage = 0
        self.iFilter = 0
        self.MipMapLODBias = 0 # often -3 in MSTS


    def Write( self, stf ):
        stf.WriteLine( '        texture ( {0} {1} {2} ff000000 )'.format( self.iImage,self.iFilter,self.MipMapLODBias))

########################################
class UVOpCopy:   # uv_op_copy

    def __init__( self ):
        self.TextureAddressMode = 0     #TexAddrMode
        self.SourceUVIndex = 0          #SrcUVIdx

    def Write( self, stf ):
        stf.WriteLine( '                uv_op_copy ( {0} {1} )'\
                .format( self.TextureAddressMode, self.SourceUVIndex ) )

########################################
class UVOpReflectMapFull:   #uv_op_reflectmap        ==> :uint,TexAddrMode .

    def __init__( self ):
        self.TextureAddressMode = 0     #TexAddrMode

    def Write( self, stf ):
        stf.WriteLine( '                uv_op_reflectmapfull ( {0} )'\
                .format( self.TextureAddressMode ) )

########################################
class LightConfig:       #light_model_cfg         ==> :dword,flags :uv_ops .

    def __init__( self ):
        self.UVOps = []

    def Write( self, stf ):
        stf.WriteLine( '		light_model_cfg ( 00000000' )
        count = len( self.UVOps )
        stf.WriteLine( '			uv_ops ( {0}'.format( count ) )
        for i in range( 0, count ):
            self.UVOps[i].Write( stf )
        stf.WriteLine( '			)' )
        stf.WriteLine( '		)' )


########################################
class PrimState:

                    # eg        prim_state (    00000000 0
                    #                                        tex_idxs ( 1 0 ) 0 0 0 0 1
                    #                                   )

    def __init__( self ):
        self.Label = ''
        self.iShader = 0
        self.iTextures = []
        self.ZBias = 0.0
        self.iVertexState = 0
        self.AlphaTestMode = 1
        self.iLightConfig = 0
        self.ZBufMode = 1


    def Write( self,stf ):
        stf.WriteLine( '        prim_state {0} ( 00000000 {1}'.format( self.Label,self.iShader) )
        stf.Write( '            tex_idxs ( {0}'.format(len(self.iTextures)) )
        for eachiTexture in self.iTextures:
            stf.Write( ' {0}'.format( eachiTexture ) )
        stf.WriteLine(' ) {0} {1} {2} {3} {4}'.format( self.ZBias,self.iVertexState, self.AlphaTestMode, self.iLightConfig, self.ZBufMode ) )
        stf.WriteLine( '        )' )



########################################
class Vertex:

        # eg vertex ( 00000000 0 0 ffffffff ff000000
        #        vertex_uvs ( 1 0 )
        #               )

        def __init__( self ):
                self.iPoint = 0
                self.iNormal = 0
                self.iUVs = []  #TODO multiple UV's
                self.Color1 = 0xffffffff
                self.Color2 = 0xff000000


        def Write( self, stf ):
                stf.WriteLine( '                                vertex ( 00000000 {0} {1} {2:08X} {3:08X}'.format(self.iPoint,self.iNormal,self.Color1, self.Color2 ) )
                stf.Write( '                                    vertex_uvs ( {0}'.format( len(self.iUVs) ) )
                for eachiUV in self.iUVs:
                    stf.Write( ' {0}'.format(eachiUV))
                stf.WriteLine( ' )' )
                stf.WriteLine( '                                )')



########################################

class Primitive:

        def __init__( self ):
                self.iPrimState = 0
                self.Triangles = []
                self.iNormals = []


        def Write( self, stf, indexOffset ):
                stf.WriteLine( '                                indexed_trilist (' )

                stf.Write( '                                    vertex_idxs ( {0} '.format( len(self.Triangles) * 3) )
                linecount = 0
                for eachTriangle in self.Triangles:
                        for eachIndex in eachTriangle:
                                stf.Write( '{0} '.format( eachIndex + indexOffset ) )
                                linecount += 1
                                if linecount > 100:
                                        linecount = 0
                                        stf.WriteLine( '' )
                                        stf.Write( '                                    ')
                stf.WriteLine( ')') #vertex_idxs

                stf.Write( '                                    normal_idxs ( {0} '.format( len(self.Triangles)) )
                linecount = 0
                for i in self.iNormals:
                            stf.Write( '{0} 3 '.format( i ) )
                            linecount += 1
                            if linecount > 100:
                                    linecount = 0
                                    stf.WriteLine( '' )
                                    stf.Write( '                                    ')
                stf.WriteLine( ')') #normal_idxs

                stf.Write( '                                    flags ( {0} '.format( len(self.Triangles)) )
                linecount = 0
                for i in self.iNormals:
                            stf.Write( '00000000 ' )
                            linecount += 1
                            if linecount > 100:
                                    linecount = 0
                                    stf.WriteLine( '' )
                                    stf.Write( '                                    ')
                stf.WriteLine( ')') #flags

                stf.WriteLine( '                                )') #indexed_trilist


########################################
class GeometryInfoPerMatrix:

        def __init__( self, ShapeVertexStatesCount ):
            self.PrimitivesCount = 0
            self.TrianglesCount = 0
            self.VerticesCount = 0
            self.VertexStatesCount = 0
            self.VertexStatesUsed = []
            for i in range(0,ShapeVertexStatesCount):
                self.VertexStatesUsed.append( False )


########################################
class VertexSet:

        def __init__( self ):
                self.Vertices = []
                self.iStart = 0     # first vertex used by this set
                self.index = {}     # not exported, keyed on iPoint, list of iVertex referencing that point


########################################
class SubObject:


        def __init__( self, parent ):
                self.VertexSets = []
                self.Primitives = []
                self.DistanceLevel = parent
                self.Flags = '00000400 -1 -1 000001d2 000001c4'
                self.Priority = 0       # sub_objects are sorted by this number, 0 comes first
                self.iHierarchy = 0     # not exported, see HierarchyOptimization
                self.sequence = len( self.DistanceLevel.SubObjects )  # not exported, for debugging


        def Write( self, stf ):
                stf.WriteLine( '                        sub_object (' )
                self.WriteSubObjectHeader( stf )
                self.WriteVertices( stf )
                self.WriteVertexSets( stf )
                self.WritePrimitives( stf )
                stf.WriteLine( '                        )') #sub_object
                return


        def WriteSubObjectHeader( self, stf ):
                stf.WriteLine( '                            sub_object_header ( ' + self.Flags )
                self.WriteSubObjectGeometryInfo( stf )
                self.WriteSubObjectShaders( stf )
                self.WriteSubObjectLightConfigs( stf )
                self.WriteSubObjectID( stf )
                stf.WriteLine( '                            )')


        def WriteSubObjectGeometryInfo( self, stf ):
                shape = self.DistanceLevel.LodControl.Shape
                # Set up data collection array and initialize
                matrixInfo = []
                for i in range(0,len(shape.Matrices) ):
                        matrixInfo.append( GeometryInfoPerMatrix( len(shape.VertexStates) ))
                #Scan all geometry and accumulate the statistics per matrix
                for primitive in self.Primitives:
                        primState = shape.PrimStates[primitive.iPrimState]
                        vertexState = shape.VertexStates[primState.iVertexState]
                        iMatrix = vertexState.iMatrix
                        matrixInfo[iMatrix].PrimitivesCount += 1
                        matrixInfo[iMatrix].TrianglesCount += len(primitive.Triangles)
                        matrixInfo[iMatrix].VerticesCount += len(primitive.Triangles) * 3
                        matrixInfo[iMatrix].VertexStatesUsed[primState.iVertexState] = True
                # Calculate VertexStates (txLightCmds) per matrix
                for i in range( 0, len(matrixInfo) ):
                        matrixInfo[i].VertexStatesCount = 0
                        for b in matrixInfo[i].VertexStatesUsed:
                                if b : matrixInfo[i].VertexStatesCount += 1
                # Now update the summary data
                # Calculate FaceNormals
                faceNormalsCount = 0
                for primitive in self.Primitives:
                        faceNormalsCount += len(primitive.Triangles)
                # Calculate number of vtx_states used by primitives in this sub_objects
                vertexStatesCount = 0
                for eachVertexSet in self.VertexSets:
                    if len(eachVertexSet.Vertices)>0:
                        vertexStatesCount += 1
                # Calculate number of vertices (VertIdxs) in all the vertex_idxs statements ( 3 x FaceNormals )
                verticesCount = faceNormalsCount * 3
                # Calculate Trilists - number of indexed_trilist statements ( in all the files I've seen, all primitives are trilists )
                trilistsCount = len(self.Primitives)
                # UNKNOWN use - NodeTxLightCmds, LineListIdxs, NodeXTrilistIdxs, LineLists, PtLists , NodeXTrilists - always seems to be 0
                stf.WriteLine( '                                geometry_info ( {0} {1} 0 {2} 0 0 {3} 0 0 0'.format(faceNormalsCount,vertexStatesCount,verticesCount,trilistsCount))
                # Write geometry nodes
                # Create a new empty geometry node map and geometry nodes array
                geometryNodeMap = []
                geometryNodeCount = 0
                for i in range( 0, len( shape.Matrices) ):
                        geometryNodeMap.append(-1)  # initialize to -1's
                        if matrixInfo[i].PrimitivesCount > 0:
                                geometryNodeCount += 1
                # Populate the new  geometry_node_map and write out the geometry_nodes
                stf.WriteLine( '                                    geometry_nodes ( {0}'.format(geometryNodeCount))
                iGeometryNode = 0
                for iMatrix in range( 0, len(shape.Matrices)):
                        matrix_info = matrixInfo[iMatrix]
                        if matrix_info.PrimitivesCount > 0:
                                stf.WriteLine( '                                        geometry_node ( {0} 0 0 0 0'.format(matrix_info.VertexStatesCount))
                                stf.WriteLine( '                                            cullable_prims ( {0} {1} {2} )'.format(matrix_info.PrimitivesCount,matrix_info.TrianglesCount,matrix_info.VerticesCount))
                                stf.WriteLine( '                                        )')
                                geometryNodeMap[iMatrix] = iGeometryNode
                                iGeometryNode += 1
                stf.WriteLine( '                                    )')
                # Write geometry node map
                stf.Write( '                                    geometry_node_map ( {0} '.format(len(shape.Matrices)))
                for iGeometryNode in geometryNodeMap:
                        stf.Write( '{0} '.format( iGeometryNode) )
                stf.WriteLine( ')' ) #geometry_node_map
                stf.WriteLine( '                                )') #geometry_info
                return

        def WriteSubObjectShaders( self, stf ):
                shape = self.DistanceLevel.LodControl.Shape
                subObjectShaders = set()
                for eachPrimitive in self.Primitives:
                        primState = shape.PrimStates[eachPrimitive.iPrimState]
                        subObjectShaders |= set([primState.iShader])
                stf.Write( '                                subobject_shaders ( {0} '.format(len(subObjectShaders) ) )
                for iShader in subObjectShaders:
                        stf.Write( '{0} '.format( iShader ) )
                stf.WriteLine( ')' )

        def WriteSubObjectLightConfigs( self, stf ):
                shape = self.DistanceLevel.LodControl.Shape
                subObjectLightConfigs = set()
                for primitive in self.Primitives:
                        primState = shape.PrimStates[primitive.iPrimState]
                        subObjectLightConfigs |= set([primState.iLightConfig])
                stf.Write( '                                subobject_light_cfgs ( {0} '.format(len(subObjectLightConfigs) ) )
                for iLightConfig in subObjectLightConfigs:
                        stf.Write( '{0} '.format( iLightConfig ) )
                stf.Write( ')' )

        def WriteSubObjectID( self, stf ):
                stf.WriteLine( ' 0' )  # [:uint,SubObjID]

        def WriteVertices( self, stf ):  # and set start location for vertex_set's
                # count the vertices
                count = 0
                for vertexSet in self.VertexSets:
                        count += len( vertexSet.Vertices )
                stf.WriteLine( '                            vertices ( {0}'.format(count))
                # write out the vertices
                iStart = 0
                for vertexSet in self.VertexSets:
                    vertexSet.iStart = iStart
                    for vertex in vertexSet.Vertices:
                        vertex.Write( stf )
                    iStart += len( vertexSet.Vertices )
                stf.WriteLine( '                            )') # vertices


        def WriteVertexSets( self, stf ):
                # count the vertex sets
                count = 0
                for vertexSet in self.VertexSets:
                        if len( vertexSet.Vertices ) > 0:
                                count += 1
                stf.WriteLine( '                            vertex_sets ( {0}'.format(count) )

                # write out the vertex sets
                for i in range( 0, len( self.VertexSets ) ):
                        vertexSet = self.VertexSets[i]
                        if len( vertexSet.Vertices ) > 0:
                                stf.WriteLine( '                                vertex_set ( {0} {1} {2} )'.format(i,vertexSet.iStart,len(vertexSet.Vertices)))

                stf.WriteLine( '                            )' ) #vertex_sets
                return


        def WritePrimitives( self,stf ):
                shape = self.DistanceLevel.LodControl.Shape
                print ("Writing primitives")
                # determine count
                count = 0
                iPrimState = -1
                for eachPrimitive in self.Primitives:
                        count += 1
                        if eachPrimitive.iPrimState != iPrimState:
                                iPrimState = eachPrimitive.iPrimState
                                count += 1
                stf.WriteLine( '                            primitives ( {0}'.format(count))

                # and write out the primitives
                iPrimState = -1
                for eachPrimitive in self.Primitives:
                        if eachPrimitive.iPrimState != iPrimState:
                                iPrimState = eachPrimitive.iPrimState
                                stf.WriteLine( '                                prim_state_idx ( {0} )'.format( iPrimState ) )
                        primState = shape.PrimStates[iPrimState]
                        vertexSet = self.VertexSets[ primState.iVertexState]
                        eachPrimitive.Write( stf, vertexSet.iStart )

                stf.WriteLine( '                            )' ) # primitives






#######################################

class DistanceLevel:

        #hierarchy
        #dlevel_selection

        def __init__(self,parent):
                self.LodControl = parent
                self.SubObjects = []
                self.Selection = 0      # maximum distance this distance level is visible
                self.Hierarchy = []


        def Write( self, stf ):
                stf.WriteLine( '                distance_level (' )
                print ("Writing distance level")

                self.WriteHeader( stf )

                count = len( self.SubObjects )
                stf.WriteLine( '                    sub_objects ( {0}'.format(count))
                for i in range( 0,count):
                    self.SubObjects[i].Write(stf)
                stf.WriteLine( '                    )')

                stf.WriteLine( '                )')

        def WriteHeader( self, stf ):
                stf.WriteLine( '                    distance_level_header (' )
                stf.WriteLine( '                        dlevel_selection ( {0} )'.format( self.Selection ) )

                count = len( self.Hierarchy )
                stf.Write( '                        hierarchy ( {0} '.format( count ) )
                for i in range( 0,count ):
                    stf.Write( '{0} '.format( self.Hierarchy[i] ) )
                stf.WriteLine( ')')

                stf.WriteLine( '                    )' )


########################################

class LodControl:

        def __init__( self, parent ):
                self.Shape = parent
                self.DistanceLevels = []


        def Write( self, stf ):
                stf.WriteLine( '        lod_control (' )
                stf.WriteLine( '            distance_levels_header ( 0 )' )

                count = len( self.DistanceLevels )
                stf.WriteLine( '            distance_levels ( {0}'.format(count))
                for i in range(0,count):
                    self.DistanceLevels[i].Write(stf)
                stf.WriteLine( '            )')

                stf.WriteLine( '        )')

########################################

class RotationKey:   #key

    def __init__(self ):
        self.Frame = 0
        self.X = 0
        self.Y = 0
        self.Z = 0
        self.W = 0


    def Write( self, stf ):

        stf.WriteLine( '                            slerp_rot ( {0} {1} {2} {3} {4} )'\
                .format( int(self.Frame), round(self.X,8), round(self.Y,8), round(self.Z,8), round(self.W,8) ))  # note frame must be an int for ffeditc_unicode to compress it properly


########################################

class TCBRotationKey:    #key

    def __init__(self ):
        self.Frame = 0
        self.X = 0
        self.Y = 0
        self.Z = 0
        self.W = 0
        self.Tension =  0
        self.Continuity =  0
        self.Bias =  0
        self.In =  0
        self.Out =  0


    def Write( self, stf ):

        stf.WriteLine( '                            tcb_key ( {0} {1} {2} {3} {4} {5} {6} {7} {8} {9} )'\
                .format( int(self.Frame), self.X, self.Y, self.Z, self.W, self.Tension, self.Continuity, self.Bias, self.In, self.Out ))

########################################

class LinearKey:   # key

    def __init__(self ):
        self.Frame = 0
        self.X = 0
        self.Y = 0
        self.Z = 0


    def Write( self, stf ):

        stf.WriteLine( '                            linear_key ( {0} {1} {2} {3} )'\
                .format( int(self.Frame), round(self.X,8), round(self.Y,8),round( self.Z,8) ))

########################################

class PositionController:   # controller

    def __init__( self ):
        self.Keys = []


    def Write( self, stf ):

        stf.WriteLine('                     linear_pos ( {0}'.format(len(self.Keys)))
        for eachKey in self.Keys:
            eachKey.Write( stf )
        stf.WriteLine('                     )')



########################################

class RotationController:     # controller

    def __init__( self ):
        self.Keys = []


    def Write( self, stf ):

        stf.WriteLine('                     tcb_rot ( {0}'.format(len(self.Keys)))
        for eachKey in self.Keys:
            eachKey.Write( stf )
        stf.WriteLine('                     )')

########################################

class AnimationNode:

        def __init__( self ):
            self.Label = None
            self.Controllers = []


        def Write( self, stf ):
            stf.WriteLine( '                anim_node {0} ('.format( self.Label ) )
            stf.WriteLine( '                    controllers ( {0}'.format( len(self.Controllers) ) )
            for eachController in self.Controllers:
                eachController.Write( stf )
            stf.WriteLine( '                    )' )
            stf.WriteLine( '                )' )

########################################

class Animation:

        def __init__( self ):
            self.FrameCount = 0
            self.FrameRate = 30
            self.AnimationNodes = []


        def Write( self, stf ):
            stf.WriteLine( '        animation ( {0} {1}'.format( int(self.FrameCount), self.FrameRate) )
            stf.WriteLine( '            anim_nodes ( {0}'.format( len(self.AnimationNodes) ) )
            for eachAnimationNode in self.AnimationNodes:
                eachAnimationNode.Write( stf )
            stf.WriteLine( '            )')
            stf.WriteLine( '        )' )


########################################

class Shape:


        def __init__( self ):
                self.Volumes = []
                self.Shaders = []
                self.Filters = []
                self.Points = []
                self.UVPoints = []
                self.Normals = []
                self.Matrices = []
                self.Images = []
                self.Textures = []
                self.Colors = []
                self.LightMaterials = []
                self.LightConfigs = []
                self.VertexStates = []
                self.PrimStates = []
                self.LodControls = []
                self.Animations = []



        def Write( self, filepath ):
                stf = STFWriter( filepath )
                stf.WriteLine( 'SIMISA@@@@@@@@@@JINX0s1t______\r\n' )
                stf.WriteLine( 'shape (' )
                stf.WriteLine( '    shape_header ( 00000000 00000000 )' )
                self.WriteVolumes( stf )
                self.WriteShaders( stf )
                self.WriteFilters( stf )
                self.WritePoints( stf )
                self.WriteUVPoints( stf )
                self.WriteNormals( stf )
                self.WriteSortVectors( stf )
                self.WriteColours( stf )
                self.WriteMatrices( stf )
                self.WriteImages(stf)
                self.WriteTextures(stf )
                self.WriteLightMaterials(stf)
                self.WriteLightConfigs( stf )
                self.WriteVertexStates(stf)
                self.WritePrimStates(stf)
                self.WriteLodControls(stf)
                self.WriteAnimations(stf)
                stf.WriteLine( ')' )
                stf.Close()

        def WriteVolumes( self, stf ):
                print ("Writing volumes")
                count = len( self.Volumes )
                stf.WriteLine( '    volumes ( {0}'.format(count) )
                for i in range( 0,count):
                    self.Volumes[i].Write( stf )
                stf.WriteLine( '    )' )

        def WriteShaders( self, stf ):
                print ("Writing shader names")
                count = len( self.Shaders )
                stf.WriteLine( '    shader_names ( {0}'.format( count ))
                for i in range( 0, count ):
                    stf.WriteLine( '        named_shader ( {0} )'.format( self.Shaders[i] ))
                stf.WriteLine( '    )')

        def WriteFilters( self, stf ):
                print ("Writing texture filter names")
                count = len( self.Filters )
                stf.WriteLine( '    texture_filter_names ( {0}'.format(count))
                for i in range( 0, count ):
                    stf.WriteLine( '        named_filter_mode ( {0} )'.format( self.Filters[i]))
                stf.WriteLine( '    )')


        def WritePoints( self, stf ):
                print ("Writing points")
                count =  len( self.Points )
                stf.WriteLine( '    points ( {0}'.format(count) )
                for i in range( 0, count ):
                    p = self.Points[i]
                    stf.WriteLine( '        point ( {0} {1} {2} )'.format(round(p[0],6),round(p[1],6),round(p[2],6) ) )
                stf.WriteLine( '    )' )


        def WriteUVPoints( self, stf ):
                print ("Writing uv points")
                count =  len( self.UVPoints )
                stf.WriteLine( '    uv_points ( {0}'.format(count) )
                for i in range( 0, count ):
                    p = self.UVPoints[i]
                    stf.WriteLine( '        uv_point ( {0} {1} )'.format(round(p[0],6),round(p[1],6)) )
                stf.WriteLine( '    )' )


        def WriteNormals( self, stf ):
                print ("Writing normals")
                count =  len( self.Normals )
                stf.WriteLine( '    normals ( {0}'.format(count) )
                for i in range( 0, count ):
                    p = self.Normals[i]
                    stf.WriteLine( '        vector ( {0} {1} {2} )'.format(round(p[0],6),round(p[1],6),round(p[2],6) ) )
                stf.WriteLine( '    )' )

        def WriteSortVectors( self, stf ):
                stf.WriteLine( '    sort_vectors ( 1' )
                stf.WriteLine( '    	vector ( 0 0 0 )' )
                stf.WriteLine( '    )' )


        def WriteMatrices( self, stf ):
                print ("Writing matrices")
                count = len( self.Matrices )
                stf.WriteLine( '    matrices ( {0}'.format( count ) )
                for i in range( 0,count):
                    self.Matrices[i].Write( stf )
                stf.WriteLine( '    )' )

        def WriteImages( self, stf ):
                print ("Writing image names")
                count = len( self.Images )
                stf.WriteLine( '    images ( {0}'.format(count))
                for i in range(0,count):
                    imageFileName = self.Images[i]
                    if imageFileName.count( ' ' ) == 0:   #only use quotes when spaces exist in name for SVIEW compatibility
                        stf.WriteLine( '        image ( {0} )'.format( imageFileName ) )
                    else:
                        stf.WriteLine( '        image ( "{0}" )'.format( imageFileName ) )
                stf.WriteLine( '    )' )

        def WriteTextures( self, stf ):
                print ("Writing textures")
                count = len( self.Textures )
                stf.WriteLine( '    textures ( {0}'.format(count))
                for i in range(0,count):
                    self.Textures[i].Write(stf)
                stf.WriteLine( '    )' )

        def WriteColours( self, stf ):
                count = len( self.Colors )
                stf.WriteLine( '    colours ( {0}'.format( count) )
                for i in range( 0, count ):
                    c = self.Colors[i]              # a r g b
                    stf.WriteLine( '        colour ( {0} {1} {2} {3} )'.format( c[0],c[1],c[2],c[3] ) )
                stf.WriteLine( '    )' )

        def WriteLightMaterials( self, stf ):
                count = len( self.LightMaterials )
                stf.WriteLine( '    light_materials ( {0}'.format( count) )
                for i in range( 0, count ):
                    m = self.LightMaterials[i]
                    stf.WriteLine( '        light_material ( 00000000 {0} {1} {2} {3} {4} )'.format( m[0],m[1],m[2],m[3],m[4] ) )
                stf.WriteLine( '    )' )


        def WriteLightConfigs( self, stf ):
                print( "Writing light configs" )
                count = len( self.LightConfigs )
                stf.WriteLine( '    light_model_cfgs ( {0}'.format(count))
                for i in range( 0,count ):
                    self.LightConfigs[i].Write(stf)
                stf.WriteLine( '    )')


        def WriteVertexStates( self, stf ):
                print ("Writing vertex states")
                count = len( self.VertexStates )
                stf.WriteLine( '    vtx_states ( {0}'.format(count))
                for i in range( 0,count):
                    self.VertexStates[i].Write( stf )
                stf.WriteLine( '    )')


        def WritePrimStates( self, stf ):
                print ("Writing prim states")
                count = len( self.PrimStates )
                stf.WriteLine( '    prim_states ( {0}'.format(count))
                for i in range( 0,count ):
                    self.PrimStates[i].Write(stf)
                stf.WriteLine( '    )')

        def WriteLodControls(self, stf ):
                count = len( self.LodControls )
                stf.WriteLine( '    lod_controls ( {0}'.format( count ) )
                for i in range(0,count):
                    self.LodControls[i].Write(stf)
                stf.WriteLine( '    )')



        def WriteAnimations(self, stf ):
                count = len( self.Animations )
                if count > 0:    # ShapeViewer crashes if you have animations( 0 )
                    stf.WriteLine( '    animations ( {0}'.format( count ) )
                    for i in range(0,count):
                        self.Animations[i].Write(stf)
                    stf.WriteLine( '    )')

'''
************************* end library *******************************
'''


if __name__ == "__main__":
   unregister()
   register()

#   print( "START" )
#   ExportShapeFile( 'MAIN', r'C:\MSTS\GLOBAL\SHAPES\LPSTrack100m.s' ) #r'c:\users\wayne\desktop\out.s' ) #
#   print( "DONE" )


