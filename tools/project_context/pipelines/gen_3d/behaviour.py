"""
Gen 3D Behaviour Module.

This module handles the 3D generation pipeline:
- Polling for generation status
- Downloading generated model files
- Processing ZIP archives
- Updating gallery with results
"""
import os
import asyncio
import zipfile
import shutil
from typing import Optional, Callable

import FreeCADGui
from PySide.QtCore import Qt
from PySide.QtWidgets import QMessageBox

from tools.view_3d import View3DStyle
from tools.authentication.authentication import AuthenticatedSession
from tools import models as Models
from tools import exporting
from tools.project_context.utils.gallery_utils import View3DCell, LoadingCell, GalleryWidget
from tools.models import AsyncResponse
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
import tools.log as log


class Generate3dBehaviour(ProjectBehaviour):
    """
    Behavior for downloading and managing 3D model generation.
    
    Handles the complete 3D download pipeline:
    1. Polls API for generation status
    2. Downloads model files when ready
    3. Extracts ZIP archives if needed
    4. Updates gallery with 3D view cell
    """
    
    GENERATIONS_DIR = "generations3d"
    UPDATE_RATE_SECONDS = 2
    
    def __init__(
        self, 
        on_complete: Callable,
        gallery: GalleryWidget, 
        obj_id: Models.Gen3dId, 
        view_3d_style: View3DStyle, 
        auth_session: AuthenticatedSession
    ):
        """
        Initialize the 3D generation behaviour.
        
        Args:
            on_complete: Callback when download completes
            gallery: Gallery widget to display 3D model
            obj_id: ID of the 3D generation task
            view_3d_style: Style settings for 3D view
            auth_session: Authenticated session for API calls
        """
        super().__init__(on_complete)
        
        self.gallery = gallery
        self.obj_id = obj_id
        self.auth_session = auth_session
        self.view_3d_style = view_3d_style
        self.view_3d_data: Optional[Models.Gen3dSaved] = None
        self.index: Optional[int] = None
        self.is_loading = True

        # Create loading cell
        self.loading_cell = LoadingCell()
        self.loading_cell.update_progress(0)
        self.index = self.gallery.add_cell(self.loading_cell)
        
        # Start polling
        self.auth_session.masterAPI.run_async_task(
            self._poll_for_completion, 
            self._on_files_download
        )
    
    # ==================== Polling ====================
        
    async def _poll_for_completion(self):
        """Poll the API until generation is complete."""
        while self.is_loading:
            await self._check_generation_status()
            await asyncio.sleep(self.UPDATE_RATE_SECONDS)
        
    async def _check_generation_status(self):
        """Check the current generation status from API."""
        if not self.auth_session.token:
            self.auth_session.auto_login(callback=lambda: self._check_generation_status())
            return
       
        try:
            result = await self.auth_session.masterAPI.get_3d_obj(
                token=self.auth_session.token, 
                obj_id=self.obj_id
            )
        except Exception as e:
            log.error(f"Generate3dBehaviour: Failed to get 3D object: {e}")
            self.is_loading = False
            return

        if not result:
            self.is_loading = False
            log.warning("Generate3dBehaviour: No result from API")
            return

        # Check if generation is complete (API returns object only when state == "success")
        if result.object:
            task_id = self.obj_id.get_id()
           
            try:
                self.view_3d_data = Models.Gen3dSaved(
                    local=None, 
                    online=result.model_dump(), 
                    obj_id=task_id
                )
            except Exception as e:
                log.error(f"Generate3dBehaviour: Failed to parse 3D object: {e}")
                self.is_loading = False
                return
            
            await self._download_model_files(
                root_folder=f"{exporting.get_project_path()}/{self.GENERATIONS_DIR}",
                name=task_id
            )

            self.is_loading = False
        else:
            # Generation still in progress - update progress
            progress = result.progress if result.progress is not None else 0
            estimated_time = getattr(result, 'estimated_time', None)
            self.loading_cell.update_progress(int(progress), estimated_time=estimated_time)
            log.debug(f"Generate3dBehaviour: Progress: {progress}%, estimated_time: {estimated_time}")

    # ==================== File Download ====================

    async def _download_model_files(self, root_folder: str, name: str):
        """
        Download and process model files.
        
        Args:
            root_folder: Base folder for downloaded files
            name: Name/ID for the model folder
        """
        try:
            gen_3d_result = self.view_3d_data.online
            obj_url = gen_3d_result.object.obj_url
            fbx_url = gen_3d_result.object.fbx_url
            usdz_url = gen_3d_result.object.usdz_url
            glb_url = gen_3d_result.object.glb_url

            folder = f"{root_folder}/{name}"
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            # Build download list
            from_to_source = []
            is_zip_file = False
            
            # Check for ZIP files first (priority)
            for url in [obj_url, glb_url, fbx_url, usdz_url]:
                if url and url.strip() and self._is_zip_url(url):
                    is_zip_file = True
                    from_to_source.append((url, f"{folder}/{name}.zip"))
                    log.debug(f"Generate3dBehaviour: Detected ZIP archive URL")
                    break
            
            # If no ZIP found, use regular format selection
            if not is_zip_file:
                if obj_url and obj_url.strip():
                    from_to_source.append((obj_url, f"{folder}/{name}.obj"))
                elif glb_url and glb_url.strip():
                    from_to_source.append((glb_url, f"{folder}/{name}.glb"))
                elif fbx_url and fbx_url.strip():
                    from_to_source.append((fbx_url, f"{folder}/{name}.fbx"))
                elif usdz_url and usdz_url.strip():
                    from_to_source.append((usdz_url, f"{folder}/{name}.usdz"))

            # Handle textures
            texture_urls = self._build_texture_download_list(gen_3d_result, folder, name)
            
            # Download all files
            all_downloads = from_to_source + texture_urls
            await self.auth_session.masterAPI.download_files(all_downloads)
            
            # Process ZIP if needed
            if is_zip_file and from_to_source:
                await self._process_zip_archive(from_to_source[0][1], folder, name)

            # Update model data with local paths
            self._update_local_paths(folder, name, from_to_source, texture_urls, is_zip_file)
            
            exporting.save_arr_item(self.GENERATIONS_DIR, self.view_3d_data.model_dump())
        
        except Exception as e:
            log.error(f"Generate3dBehaviour: Failed to download files: {e}")

    def _is_zip_url(self, url: str) -> bool:
        """Check if URL points to a ZIP file."""
        if not url:
            return False
        url_without_query = url.split('?')[0] if '?' in url else url
        url_lower = url_without_query.lower()
        return url_lower.endswith(".zip") or ".zip" in url_lower

    def _build_texture_download_list(
        self, 
        gen_3d_result, 
        folder: str, 
        name: str
    ) -> list[tuple[str, str]]:
        """Build list of texture files to download."""
        texture_urls = []
        texture = gen_3d_result.texture if gen_3d_result.texture else None
        
        if texture:
            # Support both old and new API field names
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
        
        return texture_urls

    async def _process_zip_archive(self, zip_path: str, folder: str, name: str):
        """Extract and process ZIP archive."""
        if not os.path.exists(zip_path):
            return
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder)
            
            # Find and rename files
            extracted_files = os.listdir(folder)
            obj_file_path = None
            material_png_path = None
            
            for file in extracted_files:
                file_path = os.path.join(folder, file)
                if file.lower() == "model.obj":
                    obj_file_path = file_path
                elif file.lower() == "material_0.png":
                    material_png_path = file_path
            
            # Rename material_0.png to base_color_texture.png
            if material_png_path and os.path.exists(material_png_path):
                base_color_path = os.path.join(folder, "base_color_texture.png")
                shutil.move(material_png_path, base_color_path)
                log.debug("Generate3dBehaviour: Renamed material_0.png to base_color_texture.png")
            
            # Rename model.obj to {name}.obj
            if obj_file_path:
                final_obj_path = os.path.join(folder, f"{name}.obj")
                if obj_file_path != final_obj_path:
                    shutil.move(obj_file_path, final_obj_path)
            
            # Remove ZIP file
            os.remove(zip_path)
            log.debug(f"Generate3dBehaviour: Extracted and processed zip archive")
            
        except Exception as e:
            log.error(f"Generate3dBehaviour: Failed to extract zip file: {e}")
            raise

    def _update_local_paths(
        self, 
        folder: str, 
        name: str, 
        from_to_source: list, 
        texture_urls: list, 
        is_zip_file: bool
    ):
        """Update view_3d_data with local file paths."""
        gen_3d_result = self.view_3d_data.online
        
        # Build local texture info
        local_texture = None
        if texture_urls:
            local_texture = Models.Gen3dTexture(
                base_color_url=texture_urls[0][1] if len(texture_urls) > 0 else "",
                metallic_url=texture_urls[1][1] if len(texture_urls) > 1 else "",
                roughness_url=texture_urls[2][1] if len(texture_urls) > 2 else "",
                normal_url=texture_urls[3][1] if len(texture_urls) > 3 else ""
            )
        elif is_zip_file:
            base_color_path = os.path.join(folder, "base_color_texture.png")
            if os.path.exists(base_color_path):
                local_texture = Models.Gen3dTexture(
                    base_color_url=base_color_path,
                    metallic_url="",
                    roughness_url="",
                    normal_url=""
                )

        # Build local model info
        local_model = Models.Gen3dModel(
            glb_url="",
            fbx_url="",
            usdz_url="",
            obj_url=""
        )
        
        if from_to_source:
            local_path = from_to_source[0][1]
            local_path_lower = local_path.lower()
            
            if is_zip_file:
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

    # ==================== Callbacks ====================
        
    def _on_files_download(self, response: AsyncResponse[Models.Gen3dSaved]):
        """Handle completion of file download."""
        if not response or response.error:
            log.error(f"Generate3dBehaviour: Failed to download files: {getattr(response, 'error', None)}")
            QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "Ошибка",
                "Не удалось загрузить 3D модель. Попробуйте снова."
            )
            return
        if not response.result:
            log.error("Generate3dBehaviour: Download response missing result")
            QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "Ошибка",
                "Ответ сервера пустой. Попробуйте снова."
            )
            return
        
        self.view_3d_data = response.result
        log.info(f"Generate3dBehaviour: Download complete: {self.view_3d_data}")
        self.gallery.change_cell(self.index, View3DCell(self.view_3d_data, self.view_3d_style))
