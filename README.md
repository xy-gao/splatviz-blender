# splatviz-blender
Blender addon for gaussian splatting rendering.


https://github.com/user-attachments/assets/10a1ac61-c77d-4941-b1e9-7e6ad444b7b4


https://github.com/user-attachments/assets/66d85ec8-cfd8-417b-9f42-505c90bf3062

Used composite.blend file to render this video. Two scene in the blend file. One for 3dgs render and one for eevee or cycles render, and composite based on depth and alpha images.

This blender addon is based on [splatviz](https://github.com/Florian-Barthel/splatviz).

Tested on
- Win11
- Blender 4.2
- cuda 11.8

## Usage
1. Download zip 
2. Install addon from blender preference
3. Install dependencies
4. Change render engine to Splatviz
5. switch viewport render to material preview or render preview.
6. Preview and render with animated camera.

(Since this addon has no editing capability, simple editing for example aligning with ground can be done at [supersplat](https://playcanvas.com/supersplat/editor))

