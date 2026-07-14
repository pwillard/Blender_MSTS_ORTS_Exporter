# README

June 21, 2026

Release 5.1.1 - Animation Update

 Add to the list of known Animation types.

June 19,  2026

 Release 5.1.0 - Blender 5.x compatible release.  
 Maintain support for older releases and fix minor compatibility issues. 
 Tweaks how Animations are handled.

January 3, 2026

Release 4.8.2 - Removes Attempts to make operational for Blender 5.  Maintains Blender 4.5 functionality.


October 8, 2025

Release 4.8.1 - do not use - there are ongoing issues with V5.0 Compatibility.

Repackage for easier installation in Blender.  **Use the Releases link on the right.**

The ADD-ON is packaged and made available under the *Releases* section of this repository.
The Documentation ane examples are packaged a separate Zip file.

This has been done to make the installation cleaner and easier. The Add-On code no longer needs to be extracted if you just want the documentation, and only the add-on code gets installed into the Blender environment.  This eliminates some extra steps. 

Release 4.8.0

This update adds support for Blender 4.5 LTS, which changed some shader sockets, breaking the "UPDATE SHADER" checkbox in the exporter.

January 19, 2024

Release 4.7.0

This update adds a fix for the Specular material setting that has been deprecated as an attachment in the Principled BSDF shader in place of an Incidence of refraction setting. It will still use the old setting for older Blender releases to maintain functionality. However, these settings have no impact on the exported model.

December 12, 2024

Update the exporter to support Blender 4.3, handling some deprecated items while still allowing it to run on older versions of Blender (like 3.6 LTS). The API is deprecating a `mesh` related call that was used by the exporter. When using Blender 4.x, the newer API method is used.

April 3, 2024

This update adds support for Blender 4.1 to address breaking changes in the Python API for this version of Blender and newer.
	
The Blender API no longer supports the older autosmooth options, so calls to "calc_normals_split" no longer function in version 4.1 and newer.

Overall, the exporter will now recognize when you are using a newer version of Blender and will not call deprecated API items; instead, it will rely on the replacements for these functions.

 Report Problems to me, and I will try to fix them.

pete willard
