# README

December 12, 2024

Update the exporter to support Blender 4.3, dealing with some deprecated items while still maintaining the ability to run on older versions of Blender (Like 3.6 LTS). The API is deprecating a `mesh` related call that was used by the exporter. When using Blender 4.x, the newer API is method is used.

April 3, 2024

This update adds support for Blender 4.1 release to deal with breaking changes in the Python API for this version of Blender and newer.
	
The Blender API no longer supports the older autosmooth options so calls to "calc_normals_split" no longer function in version 4.1 and newer.

Overall, The exporter will now recognize if you are using a newer version of Blender and not make a call to deprecated API items and instead rely on the replacement for these functions.

pete willard
