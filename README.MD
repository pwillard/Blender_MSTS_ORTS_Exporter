# README

<<<<<<< HEAD
This latest update adds support for Blender 4.1 release to deal with 
breaking changes in the Python API for this version of Blender and beyond
	
The Blender API no longer supports the older autosmooth options so calls to 
"calc_normals_split" no longer function in version 4.1 and newer.
=======
This latest update adds a Blender 4.1 release `crudely` patched to deal with breaking changes in the Python API for this version of Blender and beyond. (Most other existing addons have made this same change as well) 
	
Use the exporter with 4_1 in the name if you are using Blender 4.1, all other older versions of Blender (from 2.8+)  will continue to use original Add-On file.
>>>>>>> 7ca7e25692a0819c751e161a0a9475edee24c9c4

The exporter will now recognize if you are using a newer version of Blender 
and not make the call to that API and instead rely on the default replacement 
for these functions, or rather, the new way Blender handles this.

pete (April 3, 2024)