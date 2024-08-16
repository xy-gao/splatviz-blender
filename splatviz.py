#import bpy

#area  = [area for area in bpy.context.window.screen.areas if area.type == 'VIEW_3D'][0]

#with bpy.context.temp_override(area=area):
#    view3d = bpy.context.space_data
#    r3d = view3d.region_3d
#    

####!!!!!!!import this to _init

import os
import sys

import bpy
import array
dirpath = os.path.dirname(os.path.abspath(__file__))
print(f"---------{dirpath}")
sys.path.append(os.path.join(dirpath, "./gaussian-splatting"))
sys.path.append(os.path.join(dirpath, "./"))
from viz.async_renderer import AsyncRenderer
from viz.gaussian_renderer import GaussianRenderer
from viz_utils.camera_utils import create_cam2world_matrix
import sys
import torch
import numpy as np
import math
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator




def set_offset():
    x_offset = bpy.context.scene.gs_pos.x
    z_offset = bpy.context.scene.gs_pos.y
    y_offset = bpy.context.scene.gs_pos.z
    return x_offset, z_offset, y_offset

def cam_params_from_camera_mat(camera_mat, x_offset, y_offset, z_offset):
    forward = torch.tensor([-camera_mat[1][2], camera_mat[2][2], -camera_mat[0][2]], device="cuda")
    cam_pos = -torch.tensor([-camera_mat[1][3]+ x_offset, camera_mat[2][3]+ y_offset, -camera_mat[0][3]+ z_offset], device="cuda")
    up_vector = torch.tensor([-camera_mat[1][1], camera_mat[2][1], -camera_mat[0][1]], device="cuda")
    cam_params = create_cam2world_matrix(forward, cam_pos, up_vector).to("cuda")[0]
    return cam_params

def pixels_from_render_result(result, width, height):
    if result.image.shape[0] > height:
        start_pos = int((result.image.shape[0] - height)/2)
        end_pos = start_pos + height
        res_img = result.image[start_pos:end_pos,:,:]
    else:
        start_pos = int((result.image.shape[1] - width)/2)
        end_pos = start_pos + width
        res_img = result.image[:,start_pos:end_pos,:]
    pixels = np.ones((height, width,4),dtype=np.float32)
    pixels[:,:,:-1] = res_img/255
    return pixels

class SplatvizRenderEngine(bpy.types.RenderEngine):
    # These three members are used by blender to set up the
    # RenderEngine; define its internal name, visible name and capabilities.
    bl_idname = "Splatviz"
    bl_label = "Splatviz"
    bl_use_preview = True

    # Init is called whenever a new render engine instance is created. Multiple
    # instances may exist at the same time, for example for a viewport and final
    # render.
    def __init__(self):


        
        renderer = GaussianRenderer()
        self._async_renderer = AsyncRenderer(renderer)
        self.scene_data = None
        self.draw_data = None
        bpy.context.scene.view_settings.view_transform = 'Raw'

    # When the render engine instance is destroy, this is called. Clean up any
    # render engine data here, for example stopping running render threads.
    def __del__(self):
        pass

    # This is the method called by Blender for both final renders (F12) and
    # small preview for materials, world and lights.
    def render(self, depsgraph):
        scene = depsgraph.scene
        scale = scene.render.resolution_percentage / 100.0
        self.size_x = int(scene.render.resolution_x * scale)
        self.size_y = int(scene.render.resolution_y * scale)

        camera_mat = scene.camera.matrix_world
        x_offset, z_offset, y_offset = set_offset()
        cam_params = cam_params_from_camera_mat(camera_mat, x_offset, y_offset, z_offset)
        
        width, height = self.size_x, self.size_y
        resolution = max(width, height)
        fov = 45
        args = {'highlight_border': False, 'use_splitscreen': False, 'ply_file_paths': [bpy.types.Scene.gs_file_path], 'current_ply_names': [f'data_{bpy.types.Scene.gs_file_path.split()[0]}'], 'fast_render_mode': False, 'resolution': resolution, 'render_alpha': False, 'render_depth': False, 'render_gan_image': False, 'yaw': 0, 'pitch': 0, 'fov': fov, 'cam_params': cam_params, 'video_cams': [], 'edit_text': '', 'x': 1, 'eval_text': 'gaussian'}
        self._async_renderer.set_args(**args)
        result = self._async_renderer.get_result()

        pixels = pixels_from_render_result(result, width, height)
        # Here we write the pixel values to the RenderResult
        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
        layer.rect = pixels.reshape(-1,4).tolist()
        self.end_result(result)

    # For viewport renders, this method gets called once at the start and
    # whenever the scene or 3D viewport changes. This method is where data
    # should be read from Blender in the same thread. Typically a render
    # thread will be started to do the work while keeping Blender responsive.
    def view_update(self, context, depsgraph):
        region = context.region
        view3d = context.space_data
        scene = depsgraph.scene

        # Get viewport dimensions
        dimensions = region.width, region.height

        if not self.scene_data:
            # First time initialization
            self.scene_data = []
            first_time = True

            # Loop over all datablocks used in the scene.
            for datablock in depsgraph.ids:
                pass
        else:
            first_time = False

            # Test which datablocks changed
            for update in depsgraph.updates:
                print("Datablock updated: ", update.id.name)

            # Test if any material was added, removed or changed.
            if depsgraph.id_type_updated('MATERIAL'):
                print("Materials updated")

        # Loop over all object instances in the scene.
        if first_time or depsgraph.id_type_updated('OBJECT'):
            for instance in depsgraph.object_instances:
                pass

    # For viewport renders, this method is called whenever Blender redraws
    # the 3D viewport. The renderer is expected to quickly draw the render
    # with OpenGL, and not perform other expensive work.
    # Blender will draw overlays for selection and editing on top of the
    # rendered image automatically.
    def view_draw(self, context, depsgraph):
        # Lazily import GPU module, so that the render engine works in
        # background mode where the GPU module can't be imported by default.
        import gpu

        region = context.region
        scene = depsgraph.scene

        # Get viewport dimensions
        dimensions = region.width, region.height

        # Bind shader that converts from scene linear to display space,
        gpu.state.blend_set('ALPHA_PREMULT')
        self.bind_display_space_shader(scene)

        if not self.draw_data or self.draw_data.dimensions != dimensions:
            self.draw_data = SplatvizDrawData(dimensions, self._async_renderer)

        self.draw_data.draw()

        self.unbind_display_space_shader()
        gpu.state.blend_set('NONE')


class SplatvizDrawData:
    def __init__(self, dimensions, _async_renderer):
        self._async_renderer  = _async_renderer
        import gpu
        area  = [area for area in bpy.context.window.screen.areas if area.type == 'VIEW_3D'][0]
        with bpy.context.temp_override(area=area):
            view3d = bpy.context.space_data
            self.r3d = view3d.region_3d
            
        camera_mat = self.r3d.view_matrix.inverted()
        x_offset, z_offset, y_offset = set_offset()

        cam_params = cam_params_from_camera_mat(camera_mat, x_offset, y_offset, z_offset)
        # Generate dummy float image buffer
        self.dimensions = dimensions
        width, height = self.dimensions
        resolution = max(width, height)
        fov = 45
        bpy.context.space_data.lens = (0.1*968 / (2 * math.tan(45 / 2)))
        args = {'highlight_border': False, 'use_splitscreen': False, 'ply_file_paths': [bpy.types.Scene.gs_file_path], 'current_ply_names': [f'data_{bpy.types.Scene.gs_file_path.split()[0]}'], 'fast_render_mode': False, 'resolution': resolution, 'render_alpha': False, 'render_depth': False, 'render_gan_image': False, 'yaw': 0, 'pitch': 0, 'fov': fov, 'cam_params': cam_params, 'video_cams': [], 'edit_text': '', 'x': 1, 'eval_text': 'gaussian'}
        _async_renderer.set_args(**args)
        result = _async_renderer.get_result()

        pixels = pixels_from_render_result(result, width, height)
        pixels = gpu.types.Buffer('FLOAT', width * height * 4, pixels.ravel())

        # Generate texture
        self.texture = gpu.types.GPUTexture((width, height), format='RGBA16F', data=pixels)

    def __del__(self):
        del self.texture

    def draw(self):
        import gpu
        from gpu_extras.presets import draw_texture_2d
        import time

        camera_mat = self.r3d.view_matrix.inverted()
        x_offset, z_offset, y_offset = set_offset()

        cam_params = cam_params_from_camera_mat(camera_mat, x_offset, y_offset, z_offset)

        width, height = self.dimensions
        resolution = max(width, height)
        fov = 45

        args = {'highlight_border': False, 'use_splitscreen': False, 'ply_file_paths': [bpy.types.Scene.gs_file_path], 'current_ply_names': [f'data_{bpy.types.Scene.gs_file_path.split()[0]}'], 'fast_render_mode': False, 'resolution': resolution, 'render_alpha': False, 'render_depth': False, 'render_gan_image': False, 'yaw': 0, 'pitch': 0, 'fov': fov, 'cam_params': cam_params, 'video_cams': [], 'edit_text': '', 'x': 1, 'eval_text': 'gaussian'}
        self._async_renderer.set_args(**args)
        result = self._async_renderer.get_result()

        pixels = pixels_from_render_result(result, width, height)
        pixels = gpu.types.Buffer('FLOAT', width * height * 4, pixels.ravel())
        
        # Generate texture
        self.texture = gpu.types.GPUTexture((width, height), format='RGBA16F', data=pixels)
        draw_texture_2d(self.texture, (0, 0), self.texture.width, self.texture.height)


# RenderEngines also need to tell UI Panels that they are compatible with.
# We recommend to enable all panels marked as BLENDER_RENDER, and then
# exclude any panels that are replaced by custom panels registered by the
# render engine, or that are not supported.
def get_panels():
    exclude_panels = {
        'VIEWLAYER_PT_filter',
        'VIEWLAYER_PT_layer_passes',
    }
    panels = []
    for panel in bpy.types.Panel.__subclasses__():
        if hasattr(panel, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in panel.COMPAT_ENGINES:
            if panel.__name__ not in exclude_panels:
                panels.append(panel)
    return panels

class OpenFilebrowser(Operator, ImportHelper):
    bl_idname = "test.open_filebrowser"
    bl_label = "Open the file browser"
    filter_glob: StringProperty(default='*.ply',options={'HIDDEN'})
    def execute(self, context):
        bpy.types.Scene.gs_file_path = self.filepath
        return {'FINISHED'}
    
class GS_PANEL(bpy.types.Panel):
    bl_idname = 'GS_PANEL'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_label = 'GS_PANEL'
 
    def draw(self, context):
        layout = self.layout
        layout.operator("test.open_filebrowser")
        layout.prop(context.scene.gs_pos, "x")
        layout.prop(context.scene.gs_pos, "y")
        layout.prop(context.scene.gs_pos, "z")
            
class GS_POS_OFFSET(bpy.types.PropertyGroup):
    x: bpy.props.FloatProperty(name="x",description="gs offset x",min=-10, max=10, default=0)
    y: bpy.props.FloatProperty(name="y",description="gs offset y",min=-10, max=10, default=0)
    z: bpy.props.FloatProperty(name="z",description="gs offset z",min=-10, max=10, default=0)




def register():
    # Register the RenderEngine
    bpy.utils.register_class(SplatvizRenderEngine)
    bpy.utils.register_class(GS_POS_OFFSET)
    bpy.utils.register_class(GS_PANEL)
    bpy.types.Scene.gs_pos = bpy.props.PointerProperty(type=GS_POS_OFFSET)
    bpy.types.Scene.gs_file_path = bpy.props.StringProperty()
    bpy.utils.register_class(OpenFilebrowser)
    for panel in get_panels():
        panel.COMPAT_ENGINES.add('Splatviz')


def unregister():
    bpy.utils.unregister_class(SplatvizRenderEngine)
    del bpy.types.Scene.gs_pos
    del bpy.types.Scene.gs_file_path

    bpy.utils.unregister_class(GS_POS_OFFSET)
    bpy.utils.unregister_class(GS_PANEL)

    bpy.utils.unregister_class(OpenFilebrowser)

    for panel in get_panels():
        if 'Splatviz' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('Splatviz')

if __name__ == "__main__":
    register()
    
