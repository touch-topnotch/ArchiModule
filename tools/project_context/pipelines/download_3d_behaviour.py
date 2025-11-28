import os
import asyncio
import zipfile
import shutil

from PySide.QtCore import Qt
from PySide.QtWidgets import QMessageBox
from tools.view_3d import View3DStyle
from tools.authentication.authentication import AuthenticatedSession
from tools import models as Models
from tools.project_context.utils.gallery_utils import View3DCell, LoadingCell, GalleryWidget
from tools import exporting
from tools.models import AsyncResponse
import tools.log as log
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

        # Проверяем, завершена ли генерация (новый API возвращает object только при state == "success")
        # Используем проверку object для определения успешного завершения
        if result.object:
            # Генерация завершена успешно - начинаем загрузку файлов
            task_id = self.obj_id.get_id()  # Use get_id() to handle both task_id and obj_id
           
            try:
                self.view_3d_data = Models.Gen3dSaved(local=None, online=result.model_dump(), obj_id=task_id)
            except Exception as e:
                print(f"Failed to parse 3D object: {e}")
                self.is_loading = False
                return
            
            await self.__download_files(
                root_folder=f"{exporting.get_project_path()}/generations3d",
                name=task_id
            )

            self.is_loading = False
        else:
            # Генерация еще в процессе - обновляем прогресс
            progress = result.progress if result.progress is not None else 0
            # Получаем estimated_time из ответа API (если доступен)
            estimated_time = getattr(result, 'estimated_time', None)
            self.loading_cell.update_progress(int(progress), estimated_time=estimated_time)
            log.debug(f"DownloadModelBehaviour: Generation in progress, progress: {progress}%, estimated_time: {estimated_time}")

    async def __download_files(self, root_folder, name):
        try:
            gen_3d_result = self.view_3d_data.online
            obj_url = gen_3d_result.object.obj_url
            fbx_url = gen_3d_result.object.fbx_url
            usdz_url = gen_3d_result.object.usdz_url
            glb_url = gen_3d_result.object.glb_url

            folder = f"{root_folder}/{name}"
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            # Build download list with only available URLs (API возвращает только один URL)
            from_to_source = []
            is_zip_file = False
            
            # Вспомогательная функция для проверки на ZIP архив
            def is_zip_url(url: str) -> bool:
                if not url:
                    return False
                url_without_query = url.split('?')[0] if '?' in url else url
                url_lower = url_without_query.lower()
                return url_lower.endswith(".zip") or ".zip" in url_lower
            
            # Определяем, какой URL использовать (приоритет: obj > glb > fbx > usdz)
            # НО! Сначала проверяем ВСЕ URL на наличие .zip - это может быть ZIP архив с OBJ внутри
            available_url = None
            
            # Проверяем все URL на наличие .zip
            for url in [obj_url, glb_url, fbx_url, usdz_url]:
                if url and url.strip() and is_zip_url(url):
                    is_zip_file = True
                    available_url = url
                    from_to_source.append((url, f"{folder}/{name}.zip"))
                    log.debug(f"DownloadModelBehaviour: Detected ZIP archive URL: {url[:100]}...")
                    break
            
            # Если ZIP не найден, используем обычную логику выбора формата
            if not is_zip_file:
                if obj_url and obj_url.strip():
                    from_to_source.append((obj_url, f"{folder}/{name}.obj"))
                elif glb_url and glb_url.strip():
                    from_to_source.append((glb_url, f"{folder}/{name}.glb"))
                elif fbx_url and fbx_url.strip():
                    from_to_source.append((fbx_url, f"{folder}/{name}.fbx"))
                elif usdz_url and usdz_url.strip():
                    from_to_source.append((usdz_url, f"{folder}/{name}.usdz"))

            # Handle textures if available (поддержка новой модели API с другими именами полей)
            texture = gen_3d_result.texture if gen_3d_result.texture else None
            texture_urls = []
            if texture:
                # Старая модель: base_color_url, metallic_url, roughness_url, normal_url
                # Новая модель API: base_color_texture, metallic_texture, roughness_texture, normal_texture
                # Поддерживаем оба формата для обратной совместимости
                base_color = getattr(texture, 'base_color_url', None) or getattr(texture, 'base_color_texture', None)
                metallic = getattr(texture, 'metallic_url', None) or getattr(texture, 'metallic_texture', None)
                roughness = getattr(texture, 'roughness_url', None) or getattr(texture, 'roughness_texture', None)
                normal = getattr(texture, 'normal_url', None) or getattr(texture, 'normal_texture', None)
                
                if base_color:
                    texture_urls.append((base_color, f"{folder}/{name}_base_color.png"))
                if metallic:
                    texture_urls.append((metallic, f"{folder}/{name}_metallic.png"))
                if roughness:
                    texture_urls.append((roughness, f"{folder}/{name}_roughness.png"))
                if normal:
                    texture_urls.append((normal, f"{folder}/{name}_normal.png"))

            # Combine all downloads
            all_downloads = from_to_source + texture_urls
            
            # Download files first
            response = await self.auth_session.masterAPI.download_files(all_downloads)
            
            # Если скачали zip файл, распаковываем его и обрабатываем файлы
            if is_zip_file and from_to_source:
                zip_path = from_to_source[0][1]  # Путь к скачанному zip файлу
                if os.path.exists(zip_path):
                    try:
                        # Распаковываем zip архив
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(folder)
                        
                        # Ищем и переименовываем файлы
                        extracted_files = os.listdir(folder)
                        obj_file_path = None
                        mtl_file_path = None
                        material_png_path = None
                        
                        for file in extracted_files:
                            file_path = os.path.join(folder, file)
                            if file.lower() == "model.obj":
                                obj_file_path = file_path
                            elif file.lower() == "material.mtl":
                                mtl_file_path = file_path
                            elif file.lower() == "material_0.png":
                                material_png_path = file_path
                        
                        # Переименовываем material_0.png в base_color_texture.png
                        if material_png_path and os.path.exists(material_png_path):
                            base_color_path = os.path.join(folder, "base_color_texture.png")
                            shutil.move(material_png_path, base_color_path)
                            log.debug(f"DownloadModelBehaviour: Renamed material_0.png to base_color_texture.png")
                        
                        # Обновляем путь к obj файлу, если он был найден
                        if obj_file_path:
                            # Используем стандартное имя для obj файла
                            final_obj_path = os.path.join(folder, f"{name}.obj")
                            if obj_file_path != final_obj_path:
                                shutil.move(obj_file_path, final_obj_path)
                            obj_file_path = final_obj_path
                        
                        # Удаляем zip файл после распаковки
                        os.remove(zip_path)
                        log.debug(f"DownloadModelBehaviour: Extracted and processed zip archive: {zip_path}")
                        
                    except Exception as e:
                        log.error(f"DownloadModelBehaviour: Failed to extract zip file {zip_path}: {e}")
                        raise

            # Update local paths in model
            local_texture = None
            if texture and texture_urls:
                local_texture = Models.Gen3dTexture(
                    base_color_url=texture_urls[0][1] if len(texture_urls) > 0 else "",
                    metallic_url=texture_urls[1][1] if len(texture_urls) > 1 else "",
                    roughness_url=texture_urls[2][1] if len(texture_urls) > 2 else "",
                    normal_url=texture_urls[3][1] if len(texture_urls) > 3 else ""
                )
            elif is_zip_file:
                # Если это zip архив, проверяем наличие base_color_texture.png в распакованных файлах
                base_color_path = os.path.join(folder, "base_color_texture.png")
                if os.path.exists(base_color_path):
                    local_texture = Models.Gen3dTexture(
                        base_color_url=base_color_path,
                        metallic_url="",
                        roughness_url="",
                        normal_url=""
                    )

            # Определяем формат скачанного файла и заполняем только соответствующий URL
            local_model = Models.Gen3dModel(
                glb_url="",
                fbx_url="",
                usdz_url="",
                obj_url=""
            )
            
            # Заполняем только тот формат, который был скачан
            if from_to_source:
                local_path = from_to_source[0][1]  # Берем первый (и единственный) файл
                local_path_lower = local_path.lower()
                
                if is_zip_file:
                    # Для zip файла используем путь к распакованному obj файлу
                    obj_file_path = os.path.join(folder, f"{name}.obj")
                    if os.path.exists(obj_file_path):
                        local_model.obj_url = obj_file_path
                elif local_path_lower.endswith(".glb"):
                    local_model.glb_url = local_path
                elif local_path_lower.endswith(".fbx"):
                    local_model.fbx_url = local_path
                elif local_path_lower.endswith(".usdz"):
                    local_model.usdz_url = local_path
                elif local_path_lower.endswith(".obj"):
                    local_model.obj_url = local_path
            
            self.view_3d_data = Models.Gen3dSaved(
                local=Models.Gen3dResult(
                    progress=100,
                    object=local_model,
                    texture=local_texture
                ),
                online=gen_3d_result,
                obj_id=name
            )
            
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
     