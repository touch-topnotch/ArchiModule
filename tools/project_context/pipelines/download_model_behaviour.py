import os
import asyncio

from PySide.QtCore import Qt
from PySide.QtWidgets import QMessageBox
from tools.view_3d import View3DStyle
from tools.authentication import AuthenticatedSession
from tools import models as Models
from tools.gallery_utils import View3DCell, LoadingCell, GalleryWidget
from tools import exporting
from tools.models import AsyncResponse
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour

class DownloadModelBehaviour(ProjectBehaviour):
    obj_id: Models.Gen3dId = None
    auth_session: AuthenticatedSession = None
    view_3d_data: Models.Gen3dSaved = None
    gallery: GalleryWidget = None
    index: int = None
    is_loading = True
    update_rate = 2
    
    def __init__(self, on_complete, gallery: GalleryWidget, obj_id: Models.Gen3dId, view_3d_style:View3DStyle, auth_session:AuthenticatedSession):
        super().__init__(on_complete)
        self.gallery = gallery
        self.obj_id = obj_id
        self.auth_session = auth_session
        self.view_3d_style = view_3d_style

        self.loading_cell = LoadingCell()
        self.loading_cell.update_progress(0)
        self.index = self.gallery.add_cell(self.loading_cell)
        self.is_loading = True
        self.auth_session.masterAPI.run_async_task(self.__intervaled_responce, self.on_files_download)
        
    async def __intervaled_responce(self):
        while self.is_loading:
            await self.__get_response()
            await asyncio.sleep(self.update_rate)
        
    async def __get_response(self):
        if(self.auth_session.token):
            token = self.auth_session.token
        else:
            self.auth_session.auto_login(callback=lambda: self.__get_response())
            return
       
        try:
            result = await self.auth_session.masterAPI.get_3d_obj(token=token, obj_id=self.obj_id)
        except Exception as e:
            print(f"Failed to get 3D object: {e}")
            self.is_loading = False
            return

        if not result:
            self.is_loading = False
            print("no result")
            return

        if result.object:
            
            # result should be exactly Gen3dResult type
           
            try:
                self.view_3d_data = Models.Gen3dSaved(local=None, online=result.model_dump(), obj_id=self.obj_id.obj_id)
            except Exception as e:
                print(f"Failed to parse 3D object: {e}")
                self.is_loading = False
                return
            
            await self.__download_files(
                root_folder=f"{exporting.get_project_path()}/generations3d",
                name=self.obj_id.obj_id
            )

            self.is_loading = False
        else:
            print("is loading")
            
            print(result)
            self.loading_cell.update_progress(int(result.progress))

    async def __download_files(self, root_folder, name):
        try:
            gen_3d_result = self.view_3d_data.online
            obj_url = gen_3d_result.object.obj_url
            fbx_url = gen_3d_result.object.fbx_url
            usdz_url = gen_3d_result.object.usdz_url
            glb_url = gen_3d_result.object.glb_url

            base_color_url = gen_3d_result.texture.base_color_url
            metallic_url = gen_3d_result.texture.metallic_url
            roughness_url = gen_3d_result.texture.roughness_url
            normal_url = gen_3d_result.texture.normal_url
            folder = f"{root_folder}/{name}"
            if not os.path.exists(folder):
                os.makedirs(folder)
            from_to_source = [
                (obj_url, f"{folder}/{name}.obj"),
                (fbx_url, f"{folder}/{name}.fbx"),
                (usdz_url, f"{folder}/{name}.usdz"),
                (glb_url, f"{folder}/{name}.glb"),
                (base_color_url, f"{folder}/{name}_base_color.png"),
                (metallic_url, f"{folder}/{name}_metallic.png"),
                (roughness_url, f"{folder}/{name}_roughness.png"),
                (normal_url, f"{folder}/{name}_normal.png")
            ]

            self.view_3d_data = Models.Gen3dSaved(
                local=Models.Gen3dResult(
                    progress=100,
                    object=Models.Gen3dModel(
                        obj_url=from_to_source[0][1],
                        fbx_url=from_to_source[1][1],
                        usdz_url=from_to_source[2][1],
                        glb_url=from_to_source[3][1]
                    ),
                    texture=Models.Gen3dTexture(
                        base_color_url=from_to_source[4][1],
                        metallic_url=from_to_source[5][1],
                        roughness_url=from_to_source[6][1],
                        normal_url=from_to_source[7][1]
                    )
                ),
                online=gen_3d_result,
                obj_id=self.obj_id.obj_id
            )
            response = await self.auth_session.masterAPI.download_files(from_to_source)
            exporting.save_arr_item("generations3d", self.view_3d_data.model_dump())
        
        except Exception as e:
            print(f"Failed to download files: {e}")
        
    def on_files_download(self, response:AsyncResponse[Models.Gen3dSaved]):
        if response.error:
            # QMessageBox.warning(self, "Ошибка", "Ошибка при загрузке файлов: " + str(error))
            print(f"Failed to download files: {response.error}")
            # self.interrupt()
            return
        print(self.view_3d_data)
        self.gallery.change_cell(self.index, View3DCell(self.view_3d_data, self.view_3d_style))
     