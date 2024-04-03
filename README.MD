# README

This latest update adds support for Blender 4.1 release to deal with 
breaking changes in the Python API for this version of Blender and beyond
	
The Blender API no longer supports the older autosmooth options so calls to 
"calc_normals_split" no longer function in version 4.1 and newer.

The exporter will now recognize if you are using a newer version of Blender 
and not make the call to that API and instead rely on the default replacement 
for these functions, or rather, the new way Blender handles this.

pete (April 3, 2024)