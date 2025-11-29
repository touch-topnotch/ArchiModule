"""
Gen Video Behaviour Module.

This module handles the video generation pipeline:
- Shows frame selection UI (uses prepare.py)
- Initiates API calls for generation
- Polls for completion status
- Downloads generated video files
- Updates gallery/project with results
"""
import os
import asyncio
import datetime
import requests
from typing import Optional, Callable

import FreeCAD
import FreeCADGui
from PySide.QtCore import Qt, QObject, QTimer
from PySide.QtWidgets import QMessageBox, QWidget

from tools.authentication import AuthenticatedSession
from tools.master_api import MasterAPI
from tools import exporting, models
from tools.models import AsyncResponse
from tools.project_context.utils.gallery_utils import GalleryWidget, LoadingCell, VideoCell
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
from tools.project_context.pipelines.gen_video.prepare import PrepareForVideoGen
from tools.full_view import FullViewWindow, FullViewWindowData, FullViewVideoInteractable, FullViewButtonData
import tools.log as log


class UIStrings:
    """Constant strings used in the UI."""
    # Error messages
    ERROR_TITLE = "Ошибка"
    VIDEO_GEN_ERROR = "Ошибка при генерации видео: "
    AUTH_ERROR_TITLE = "Ошибка авторизации"
    AUTH_ERROR_TEXT = "Не удалось авторизоваться. Пожалуйста, проверьте ваш email и пароль."
    
    # Success
    SUCCESS_TITLE = "Готово"
    SUCCESS_TEXT = "Видео успешно сгенерировано и сохранено!"
    
    # Warnings
    NO_IMAGES_TITLE = "Нет изображений"
    NO_IMAGES_TEXT = "Добавьте скетчи или сгенерируйте 2D рендеры перед созданием видео."


class GenerateVideoBehaviour(ProjectBehaviour):
    """
    Behavior for generating videos from image frames.
    
    Handles the complete video generation pipeline:
    1. Shows frame selection UI (PrepareForVideoGen)
    2. Initiates API calls for generation
    3. Polls for completion
    4. Downloads generated video
    5. Saves to project
    """
    
    ESTIMATED_GENERATION_TIME_SECONDS: int = 120  # ~2 minutes
    GENERATIONS_DIR = "generations_video"
    UPDATE_RATE_SECONDS = 5  # Poll every 5 seconds
    
    def __init__(
        self,
        authSession: AuthenticatedSession,
        masterApi: MasterAPI,
        sketches: GalleryWidget,
        generations_2d: GalleryWidget,
        video_gallery: GalleryWidget,
        parent: QObject = None
    ):
        """
        Initialize the GenerateVideoBehaviour.
        
        Args:
            authSession: The authenticated session
            masterApi: API for generating videos
            sketches: Gallery widget containing sketch images
            generations_2d: Gallery widget containing 2D generations
            video_gallery: Gallery widget to display generated videos
            parent: Optional parent QObject
        """
        super().__init__(parent)
        
        # Set properties
        self.status = self.Status.RUNNING
        self.authSession = authSession
        self.masterApi = masterApi
        self.sketches = sketches
        self.generations_2d = generations_2d
        self.video_gallery = video_gallery
        self.full_view: Optional[FullViewWindow] = None  # Will be set from project_context_window
        self.on_video_cell_created: Optional[Callable[[VideoCell], None]] = None  # Callback to connect action
        self._downloaded_temp_path: Optional[str] = None  # Temp file path for downloaded video
        self._download_error: Optional[Exception] = None  # Error during download
        
        # Current generation state
        self.current_input: Optional[models.VideoGenInput] = None
        self.loading_cell: Optional[LoadingCell] = None
        self.loading_cell_id: Optional[int] = None
        self.task_id: Optional[str] = None
        self.is_loading = False
        
        # Dialog reference
        self.prepare_dialog: Optional[PrepareForVideoGen] = None
        
        # Show the preparation dialog
        self._show_prepare_dialog()
    
    # ==================== UI Management ====================
    
    def _show_prepare_dialog(self):
        """Create and display the frame selection dialog."""
        # Check if we have any images
        has_sketches = self.sketches and self.sketches.cells
        has_gen2d = self.generations_2d and self.generations_2d.cells
        
        if not has_sketches and not has_gen2d:
            QMessageBox.warning(None, UIStrings.NO_IMAGES_TITLE, UIStrings.NO_IMAGES_TEXT)
            self.deleteLater()
            return
        
        try:
            self.prepare_dialog = PrepareForVideoGen(
                sketches=self.sketches,
                generations_2d=self.generations_2d,
                on_approve=self._on_video_input_approved
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"GenerateVideoBehaviour._show_prepare_dialog: Error creating dialog: {e}\n"
            )
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            QMessageBox.critical(None, UIStrings.ERROR_TITLE, f"Не удалось создать окно: {e}")
            self.deleteLater()
            return
        
        try:
            main_window = FreeCADGui.getMainWindow()
            if not main_window:
                FreeCAD.Console.PrintError(
                    "GenerateVideoBehaviour._show_prepare_dialog: Failed to get main window!\n"
                )
                self.prepare_dialog.deleteLater()
                self.deleteLater()
                return
            
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.prepare_dialog)
            self.prepare_dialog.setFloating(True)
            self.prepare_dialog.show()
            
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"GenerateVideoBehaviour._show_prepare_dialog: Error showing dialog: {e}\n"
            )
            if self.prepare_dialog:
                self.prepare_dialog.deleteLater()
            self.deleteLater()
    
    def _on_error_occurred(self, message: str):
        """Slot to handle errors on main thread."""
        self._show_error_message(message)
        
        # Remove loading cell
        if self.loading_cell_id is not None:
            self.video_gallery.remove(self.loading_cell_id)
            self.loading_cell_id = None

    def _show_error_message(self, message: str):
        """Display an error message to the user."""
        QMessageBox.warning(
            FreeCADGui.getMainWindow(),
            UIStrings.ERROR_TITLE,
            message,
            QMessageBox.Ok
        )
    
    # ==================== Generation Flow ====================
    
    def _on_video_input_approved(self, video_input: models.VideoGenInput):
        """
        Handle approved video generation input.
        
        Args:
            video_input: The input parameters from the preparation dialog
        """
        
        log.info(f"GenerateVideoBehaviour: Video input approved")
        # Check, if there are only two images and set mode to 'pro' if needed
        image_count = 2
        if video_input.image3_base64:
            image_count += 1
        if video_input.image4_base64:
            image_count += 1
        if image_count == 2 and video_input.mode != "pro":
            log.info("Setting mode to 'pro' because only two images were provided")
            video_input.mode = "pro"
        log.debug(f"  Prompt: {video_input.prompt[:50] if video_input.prompt else '(empty)'}...")
        
        self.current_input = video_input
        
        # Show loading animation
        self.loading_cell = LoadingCell()
        self.loading_cell.set_estimated_time(self.ESTIMATED_GENERATION_TIME_SECONDS)
        self.loading_cell_id = self.video_gallery.add_cell(self.loading_cell)
        
        self._start_generation(video_input)
    
    def _start_generation(self, video_input: models.VideoGenInput):
        """
        Start the video generation process.
        
        Args:
            video_input: Input parameters for the video generation
        """
        # Check authentication
        if self.authSession.is_authenticated():
            token = self.authSession.token
        else:
            log.info("GenerateVideoBehaviour: Starting auto login")
            
            def on_auto_login(response: AsyncResponse):
                if response.has_result():
                    self._start_generation(video_input)
                else:
                    QMessageBox.critical(
                        None,
                        UIStrings.AUTH_ERROR_TITLE,
                        UIStrings.AUTH_ERROR_TEXT
                    )
            
            self.authSession.auto_login(on_auto_login)
            return
        
        # Start API call
        self.masterApi.run_async_task(
            self.masterApi.generate_video,
            self._on_video_task_created,
            token=token,
            videoGenInput=video_input
        )
    
    # ==================== Polling ====================
    
    def _on_video_task_created(self, response: AsyncResponse[Optional[models.VideoGenId]]):
        """Handle task creation response."""
        if response.has_error() or not response.has_result():
            self._handle_generation_error(response.error)
            return
        
        self.task_id = response.result.task_id
        log.info(f"GenerateVideoBehaviour: Task created: {self.task_id}")
        
        # Start polling for status
        self.is_loading = True
        self._start_polling()
    
    def _start_polling(self):
        """Start polling for video generation status."""
        self.masterApi.run_async_task(
            self._poll_for_completion,
            self._on_polling_finished
        )
    
    async def _poll_for_completion(self):
        """Poll the API until generation is complete."""
        log.info("GenerateVideoBehaviour: Starting polling loop")
        poll_count = 0
        while self.is_loading:
            poll_count += 1
            log.debug(f"GenerateVideoBehaviour: Poll iteration {poll_count}")
            await self._check_video_status()
            if self.is_loading:
                await asyncio.sleep(self.UPDATE_RATE_SECONDS)
        log.info(f"GenerateVideoBehaviour: Polling loop finished after {poll_count} iterations")
    
    async def _check_video_status(self):
        """Check video generation status."""
        if not self.authSession.token:
            log.warning("GenerateVideoBehaviour: No token, cannot check status")
            return
        
        try:
            log.debug(f"GenerateVideoBehaviour: Checking status for task {self.task_id}")
            status = await self.masterApi.get_video(self.authSession.token, self.task_id)
            log.debug(f"GenerateVideoBehaviour: Status received - task_status={status.task_status}, progress={status.progress}")
            
            # Update progress
            if self.loading_cell:
                self.loading_cell.update_progress(
                    status.progress,
                    estimated_time=status.estimated_time
                )
            
            # Check completion
            if status.task_status == "succeed":
                log.info(f"GenerateVideoBehaviour: Task succeeded! Videos count: {len(status.videos) if status.videos else 0}")
                self.is_loading = False
                if status.videos and len(status.videos) > 0:
                    video_url = status.videos[0].url
                    log.info(f"GenerateVideoBehaviour: Video URL: {video_url}")
                    if video_url:
                        # Download video
                        log.info("GenerateVideoBehaviour: Starting video download...")
                        await self._download_video_async(video_url)
                    else:
                        log.error("GenerateVideoBehaviour: Video URL is empty")
                else:
                    log.error("GenerateVideoBehaviour: No video in response")
            elif status.task_status == "failed":
                self.is_loading = False
                error_msg = status.task_status_msg or "Generation failed"
                log.error(f"GenerateVideoBehaviour: Task failed: {error_msg}")
                self._handle_generation_error(Exception(error_msg))
        except Exception as e:
            log.error(f"GenerateVideoBehaviour: Status check error: {e}")
            import traceback
            log.error(traceback.format_exc())
            self.is_loading = False
            self._handle_generation_error(e)
    
    def _on_polling_finished(self, response: AsyncResponse):
        """Handle polling completion (called when polling loop exits)."""
        log.info(f"GenerateVideoBehaviour: _on_polling_finished called, has_error={response.has_error()}")
        
        # Check for polling errors
        if response.has_error():
            log.error(f"GenerateVideoBehaviour: Polling finished with error: {response.error}")
            self._handle_generation_error(response.error)
            return
        
        # Check for download errors
        if hasattr(self, '_download_error') and self._download_error:
            log.error(f"GenerateVideoBehaviour: Download error occurred: {self._download_error}")
            self._handle_generation_error(self._download_error)
            return
        
        # Process downloaded file if available
        if self._downloaded_temp_path:
            log.info(f"GenerateVideoBehaviour: Processing downloaded file: {self._downloaded_temp_path}")
            self._save_video_file(self._downloaded_temp_path)
            self._downloaded_temp_path = None
        else:
            log.warning("GenerateVideoBehaviour: Polling finished but no downloaded file to process")
    
    async def _download_video_async(self, video_url: str):
        """Download video asynchronously."""
        log.info(f"GenerateVideoBehaviour: _download_video_async called with URL: {video_url}")
        try:
            # Download in async context
            log.info("GenerateVideoBehaviour: Sending GET request...")
            response = requests.get(video_url, timeout=300, stream=True)
            response.raise_for_status()
            log.info(f"GenerateVideoBehaviour: Response status: {response.status_code}, content-length: {response.headers.get('content-length', 'unknown')}")
            
            # Save to temp first, then move
            import tempfile
            total_bytes = 0
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                    total_bytes += len(chunk)
                temp_path = tmp.name
            
            log.info(f"GenerateVideoBehaviour: Downloaded {total_bytes} bytes to temp file: {temp_path}")
            # Store path for processing in main thread callback
            self._downloaded_temp_path = temp_path
            
        except Exception as e:
            log.error(f"GenerateVideoBehaviour: Failed to download video: {e}")
            import traceback
            log.error(traceback.format_exc())
            # Store error for main thread handling
            self._download_error = e
    
    def _handle_generation_error(self, error: Optional[Exception]):
        """Handle errors during video generation."""
        error_msg = str(error) if error else "Unknown error"
        log.error(f"GenerateVideoBehaviour: Generation error: {error_msg}")
        self._invoke_on_main_thread(self._on_error_occurred, UIStrings.VIDEO_GEN_ERROR + error_msg)

    def _invoke_on_main_thread(self, func: Callable, *args, **kwargs):
        """Ensure callable runs in the GUI thread."""
        log.debug(f"GenerateVideoBehaviour: _invoke_on_main_thread scheduling {func.__name__}")
        def wrapper():
            log.debug(f"GenerateVideoBehaviour: _invoke_on_main_thread executing {func.__name__}")
            try:
                func(*args, **kwargs)
            except Exception as e:
                log.error(f"GenerateVideoBehaviour: Error in main thread call: {e}")
                import traceback
                log.error(traceback.format_exc())
        QTimer.singleShot(0, wrapper)
    
    # ==================== File Management ====================
    
    def _save_video_file(self, temp_path: str):
        """Save video file from temp path to project directory."""
        log.info(f"GenerateVideoBehaviour: _save_video_file called with temp_path: {temp_path}")
        try:
            # Verify temp file exists
            if not os.path.exists(temp_path):
                raise FileNotFoundError(f"Temp file not found: {temp_path}")
            
            temp_size = os.path.getsize(temp_path)
            log.info(f"GenerateVideoBehaviour: Temp file size: {temp_size} bytes")
            
            # Create directory if needed
            project_path = exporting.get_project_path()
            log.info(f"GenerateVideoBehaviour: Project path: {project_path}")
            gen_dir = f"{project_path}/{self.GENERATIONS_DIR}"
            if not os.path.exists(gen_dir):
                os.makedirs(gen_dir)
                log.info(f"GenerateVideoBehaviour: Created directory: {gen_dir}")
            
            # Generate filename
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            video_path = f"{gen_dir}/{timestamp}.mp4"
            
            # Move temp file to final location
            import shutil
            shutil.move(temp_path, video_path)
            
            log.info(f"GenerateVideoBehaviour: Video saved to {video_path}")
            
            # Verify final file exists
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found after move: {video_path}")
            
            final_size = os.path.getsize(video_path)
            log.info(f"GenerateVideoBehaviour: Final file size: {final_size} bytes")
            
            # Remove loading cell
            if self.loading_cell_id is not None:
                log.info(f"GenerateVideoBehaviour: Removing loading cell {self.loading_cell_id}")
                self.video_gallery.remove(self.loading_cell_id)
                self.loading_cell_id = None
            
            # Save to project
            log.info(f"GenerateVideoBehaviour: Saving to exporting: {self.GENERATIONS_DIR} -> {video_path}")
            exporting.save_arr_item(self.GENERATIONS_DIR, video_path)
            
            # Add VideoCell to gallery
            log.info("GenerateVideoBehaviour: Creating VideoCell...")
            video_cell = VideoCell(video_path)
            cell_id = self.video_gallery.add_cell(video_cell)
            log.info(f"GenerateVideoBehaviour: VideoCell added with id {cell_id}")
            
            # Connect action if callback is available
            if self.on_video_cell_created:
                log.info("GenerateVideoBehaviour: Calling on_video_cell_created callback")
                self.on_video_cell_created(video_cell)
            
            log.info("GenerateVideoBehaviour: Showing success message")
            QMessageBox.information(
                FreeCADGui.getMainWindow(),
                UIStrings.SUCCESS_TITLE,
                UIStrings.SUCCESS_TEXT
            )
        except Exception as e:
            log.error(f"GenerateVideoBehaviour: Failed to save video: {e}")
            import traceback
            log.error(traceback.format_exc())
            self._handle_generation_error(e)
    
    # ==================== Lifecycle ====================
    
    def __del__(self):
        """Destructor to clean up resources."""
        log.info(f"GenerateVideoBehaviour instance {id(self)} being deleted.")
        if hasattr(self, 'prepare_dialog') and self.prepare_dialog:
            self.prepare_dialog.close()
            self.prepare_dialog.deleteLater()
